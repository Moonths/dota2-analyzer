"""小号检测引擎 — 多维加权评分模型"""
import asyncio
import json
from datetime import datetime
from typing import Optional

from database.db import get_db
from services.opendota import (
    get_benchmarks,
    get_match,
    get_player,
    get_player_matches,
)

# ── 信号权重 ──
WEIGHTS = {
    "win_rate": 0.25,
    "gpm_percentile": 0.20,
    "xpm_percentile": 0.15,
    "kda_ratio": 0.15,
    "total_matches": 0.10,
    "win_streak": 0.10,
    "hero_pool": 0.05,
}

# ── 缓存过期时间：小号检测结果按周更新，玩家档案同步按周刷新 ──
PROFILE_CACHE_TTL_SECONDS = 7 * 24 * 3600
SMURF_CACHE_TTL_SECONDS = 7 * 24 * 3600
REQUEST_TIMEOUT_SECONDS = 8
MATCH_CONCURRENCY = 12
BENCH_CONCURRENCY = 8

MATCHES_TO_FETCH = 30


def _normalize(value: float, low: float, high: float) -> float:
    """将值线性映射到 0~1，超出边界截断"""
    if value <= low:
        return 0.0
    if value >= high:
        return 1.0
    return (value - low) / (high - low)


def _calc_gpm_percentile(
    player_gpm: float, hero_bench: Optional[dict]
) -> float:
    """推算玩家 GPM 在同分段同英雄中的大致百分位"""
    if not hero_bench:
        return 0.5
    return _calc_pct_from_benchmark(player_gpm, hero_bench, "gold_per_min")


def _calc_xpm_percentile(
    player_xpm: float, hero_bench: Optional[dict]
) -> float:
    if not hero_bench:
        return 0.5
    return _calc_pct_from_benchmark(player_xpm, hero_bench, "xp_per_min")


def _calc_kda_percentile(
    player_kda: float, hero_bench: Optional[dict]
) -> float:
    if not hero_bench:
        return 0.5
    return _calc_pct_from_benchmark(player_kda, hero_bench, "kda")


def _calc_pct_from_benchmark(
    value: float, bench_data: dict, key: str
) -> float:
    """从 benchmark JSON 推算值所在的百分位"""
    result = bench_data.get("result", {})
    percentile_list = result.get(key, [])
    if not percentile_list:
        return 0.5

    pct_map = {
        item.get("percentile", 0): item.get("value", 0)
        for item in percentile_list
    }
    sorted_pcts = sorted(pct_map.keys())

    for pct in sorted_pcts:
        if value <= pct_map[pct]:
            return pct / 100.0

    return 0.99


def _score_win_rate(matches: list[dict]) -> tuple[float, float]:
    """近 N 场胜率 → 信号值 + 原始胜率"""
    if not matches:
        return 0.0, 0.0
    wins = sum(
        1 for m in matches
        if _match_winner(m.get("player_slot", 0), m.get("radiant_win", False))
    )
    wr = wins / len(matches)
    score = _normalize(wr, 0.55, 0.80)
    return score, wr


def _score_gpm_xpm(
    matches: list[dict], benchmarks: dict
) -> tuple[float, float, float, float]:
    """GPM/XPM 平均超分段百分位"""
    if not matches:
        return 0.0, 0.0, 0.0, 0.0
    gpm_pcts = []
    xpm_pcts = []
    avg_gpm = 0.0
    avg_xpm = 0.0
    for m in matches:
        gpm = m.get("gold_per_min", 0)
        xpm = m.get("xp_per_min", 0)
        avg_gpm += gpm
        avg_xpm += xpm
        hero_id = m.get("hero_id")
        bench = benchmarks.get(hero_id) if hero_id else None
        gpm_pcts.append(_calc_gpm_percentile(gpm, bench))
        xpm_pcts.append(_calc_xpm_percentile(xpm, bench))
    n = len(matches)
    avg_gpm /= n
    avg_xpm /= n
    gpm_score = _normalize(sum(gpm_pcts) / n, 0.50, 0.90)
    xpm_score = _normalize(sum(xpm_pcts) / n, 0.50, 0.90)
    return gpm_score, xpm_score, avg_gpm, avg_xpm


def _score_kda(matches: list[dict], benchmarks: dict) -> tuple[float, float]:
    """KDA 超分段程度"""
    if not matches:
        return 0.0, 0.0
    kdas = []
    for m in matches:
        k = m.get("kills", 0)
        d = m.get("deaths", 1) or 1
        a = m.get("assists", 0)
        kdas.append((k + a) / d)
    avg_kda = sum(kdas) / len(kdas)
    score = _normalize(avg_kda, 1.5, 5.0)
    return score, avg_kda


def _score_win_streak(matches: list[dict]) -> tuple[float, int]:
    """近 20 场最大连胜"""
    if not matches:
        return 0.0, 0
    max_streak = 0
    current = 0
    for m in matches[:20]:
        won = _match_winner(
            m.get("player_slot", 0), m.get("radiant_win", False)
        )
        if won:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return _normalize(max_streak, 4, 12), max_streak


def _score_hero_pool(matches: list[dict]) -> tuple[float, int]:
    """英雄池深度 — 非典型小号极窄，但这里降权很低"""
    heroes = {m.get("hero_id") for m in matches if m.get("hero_id")}
    pool = len(heroes)
    score = _normalize(pool, 2, 15)
    return 1.0 - score, pool


def _match_winner(player_slot: int, radiant_win: bool) -> bool:
    is_radiant = (player_slot & 128) == 0
    return is_radiant == radiant_win


def _roast(score: float, summary: dict) -> str:
    """根据得分生成毒舌评语"""
    if score >= 0.85:
        return (
            "这数据已经不是炸鱼了，是开着航母在儿童泳池里转圈。"
            "建议直接举报，或者劝他找个班上。"
        )
    if score >= 0.70:
        return (
            f"胜率{summary.get('win_rate', 0):.0%}，GPM把同分段当提款机。"
            "这要是真新手，我把显示器蘸酱油吃了。"
        )
    if score >= 0.55:
        return (
            "数据明显高于分段均值，十有八九是来捕鱼的。"
            "建议下次排到他秒退，别给他爽。"
        )
    if score >= 0.40:
        return (
            "有些数据偏高但还没到离谱的程度。"
            "可能是刚从别的MOBA转过来的天赋型选手，也可能是状态好。再观察观察。"
        )
    return (
        "看起来像是个正常的该分段选手。"
        "如果他还是把你打爆了...那可能只是你菜。"
    )


def _parse_db_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _age_seconds(value: Optional[str]) -> Optional[float]:
    parsed = _parse_db_time(value)
    if parsed is None:
        return None
    return (datetime.utcnow() - parsed).total_seconds()


async def _load_smurf_cache(db, player_id: int) -> Optional[dict]:
    async with db.execute(
        "SELECT result, last_match_count, created_at "
        "FROM smurf_check_cache WHERE account_id = ?",
        (player_id,),
    ) as cursor:
        row = await cursor.fetchone()
    if not row:
        return None
    return {
        "result": json.loads(row["result"]),
        "last_match_count": row["last_match_count"],
        "created_at": row["created_at"],
    }


async def get_cached_smurf_result(player_id: int) -> Optional[dict]:
    """只读返回仍处于有效期的小号检测缓存，供路由在扣费前判断。"""
    db = await get_db()
    try:
        cache = await _load_smurf_cache(db, player_id)
        if not cache:
            return None
        age = _age_seconds(cache["created_at"])
        if age is None or age >= SMURF_CACHE_TTL_SECONDS:
            return None

        result = dict(cache["result"])
        result["cached"] = True
        result["quota_deducted"] = False
        result["cache_source"] = "database"
        result["message"] = "已使用小号检测缓存，不消耗今日分析次数"
        return result
    finally:
        await db.close()


async def _load_profile_cache(db, player_id: int) -> Optional[dict]:
    async with db.execute(
        "SELECT data, fetched_at FROM player_profile_cache WHERE account_id = ?",
        (player_id,),
    ) as cursor:
        row = await cursor.fetchone()
    if not row:
        return None
    return {
        "data": json.loads(row["data"]),
        "fetched_at": row["fetched_at"],
    }


async def _fetch_profile(db, player_id: int, cached: Optional[dict]) -> dict:
    if cached:
        age = _age_seconds(cached["fetched_at"])
        if age is not None and age < PROFILE_CACHE_TTL_SECONDS:
            return cached["data"]

    try:
        profile_data = await asyncio.wait_for(
            get_player(player_id), timeout=REQUEST_TIMEOUT_SECONDS
        )
    except Exception:
        return cached["data"] if cached else {}

    if isinstance(profile_data, dict):
        await db.execute(
            "INSERT OR REPLACE INTO player_profile_cache "
            "(account_id, data, fetched_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (player_id, json.dumps(profile_data, ensure_ascii=False)),
        )
        await db.commit()
        return profile_data
    return cached["data"] if cached else {}


async def _fetch_player_matches(player_id: int) -> list[dict]:
    try:
        raw_matches = await asyncio.wait_for(
            get_player_matches(player_id, MATCHES_TO_FETCH),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        return raw_matches if isinstance(raw_matches, list) else []
    except Exception:
        return []


async def _fetch_missing_matches(
    db, player_id: int, match_ids: list[int]
) -> list[dict]:
    if not match_ids:
        return []

    semaphore = asyncio.Semaphore(MATCH_CONCURRENCY)

    async def fetch_one(match_id: int) -> tuple[int, Optional[dict]]:
        async with semaphore:
            try:
                data = await asyncio.wait_for(
                    get_match(match_id), timeout=REQUEST_TIMEOUT_SECONDS
                )
                return match_id, data
            except Exception:
                return match_id, None

    fetched = await asyncio.gather(*(fetch_one(mid) for mid in match_ids))
    detailed = []
    for match_id, data in fetched:
        if not data:
            continue
        detailed.append(data)
        await db.execute(
            "INSERT OR REPLACE INTO player_match_cache "
            "(match_id, account_id, data) VALUES (?, ?, ?)",
            (match_id, player_id, json.dumps(data, ensure_ascii=False)),
        )
    await db.commit()
    return detailed


async def _ensure_benchmarks(
    db, hero_ids: set[int]
) -> dict[int, Optional[dict]]:
    """确保需要 benchmark 的英雄数据已缓存"""
    if not hero_ids:
        return {}

    placeholders = ",".join("?" for _ in hero_ids)
    async with db.execute(
        f"SELECT hero_id, data FROM benchmark_cache "
        f"WHERE hero_id IN ({placeholders})",
        tuple(hero_ids),
    ) as cursor:
        rows = await cursor.fetchall()

    benchmarks: dict[int, Optional[dict]] = {}
    cached_ids = set()
    for row in rows:
        benchmarks[row["hero_id"]] = json.loads(row["data"])
        cached_ids.add(row["hero_id"])

    missing_ids = sorted(hero_ids - cached_ids)
    semaphore = asyncio.Semaphore(BENCH_CONCURRENCY)

    async def fetch_one(hero_id: int) -> tuple[int, Optional[dict]]:
        async with semaphore:
            try:
                data = await asyncio.wait_for(
                    get_benchmarks(hero_id), timeout=REQUEST_TIMEOUT_SECONDS
                )
                return hero_id, data
            except Exception:
                return hero_id, None

    fetched = await asyncio.gather(*(fetch_one(hid) for hid in missing_ids))
    for hero_id, data in fetched:
        benchmarks[hero_id] = data
        if data:
            await db.execute(
                "INSERT OR REPLACE INTO benchmark_cache "
                "(hero_id, data, fetched_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (hero_id, json.dumps(data, ensure_ascii=False)),
            )
    await db.commit()
    return benchmarks


def _unavailable_result(
    player_id: int, player_name: str, message: str
) -> dict:
    return {
        "player_id": player_id,
        "player_name": player_name,
        "score": 0.0,
        "confidence": "low",
        "signals": [],
        "roast": message,
        "details": {},
    }


async def detect_smurf(player_id: int) -> dict:
    """
    小号检测主函数。
    返回 { score, confidence, signals, roast, ... }
    """
    db = await get_db()
    try:
        smurf_cache = await _load_smurf_cache(db, player_id)
        if smurf_cache:
            age = _age_seconds(smurf_cache["created_at"])
            if age is not None and age < SMURF_CACHE_TTL_SECONDS:
                return smurf_cache["result"]

        profile_cache = await _load_profile_cache(db, player_id)
        profile_task = asyncio.create_task(
            _fetch_profile(db, player_id, profile_cache)
        )
        matches_task = asyncio.create_task(_fetch_player_matches(player_id))
        profile_data, raw_matches = await asyncio.gather(
            profile_task, matches_task
        )
        profile_inner = (
            profile_data.get("profile", {})
            if isinstance(profile_data, dict)
            else {}
        )
        player_name = profile_inner.get("personaname", str(player_id))

        if not raw_matches:
            if smurf_cache:
                return smurf_cache["result"]
            return _unavailable_result(
                player_id,
                player_name,
                "OpenDota 暂时没响应，小号检测没有完成。稍后再试一次，结果会快很多。",
            )

        current_match_count = len(raw_matches)
        if smurf_cache and (
            smurf_cache["last_match_count"] >= current_match_count
        ):
            return smurf_cache["result"]

        hero_ids = set()
        detailed_matches = []
        new_match_ids = []

        for m in raw_matches:
            mid = m.get("match_id")
            if not mid:
                continue
            hero_id = m.get("hero_id")
            if hero_id:
                hero_ids.add(hero_id)

            async with db.execute(
                "SELECT data FROM player_match_cache WHERE match_id = ?",
                (mid,),
            ) as cursor:
                row = await cursor.fetchone()
            if row:
                detailed_matches.append(json.loads(row["data"]))
            else:
                new_match_ids.append(mid)

        detailed_matches.extend(
            await _fetch_missing_matches(db, player_id, new_match_ids)
        )

        if not detailed_matches:
            if smurf_cache:
                return smurf_cache["result"]
            return _unavailable_result(
                player_id,
                player_name,
                "比赛详情暂时拉不到，小号检测没有完成。稍后再试一次。",
            )

        benchmarks = await _ensure_benchmarks(db, hero_ids)

        player_matches = []
        for match_detail in detailed_matches:
            players = match_detail.get("players", [])
            for p in players:
                if p.get("account_id") == player_id:
                    player_matches.append(
                        {
                            "match_id": match_detail.get("match_id"),
                            "hero_id": p.get("hero_id"),
                            "kills": p.get("kills", 0),
                            "deaths": p.get("deaths", 0),
                            "assists": p.get("assists", 0),
                            "gold_per_min": p.get("gold_per_min", 0),
                            "xp_per_min": p.get("xp_per_min", 0),
                            "player_slot": p.get("player_slot", 0),
                            "radiant_win": match_detail.get(
                                "radiant_win", False
                            ),
                        }
                    )
                    break

        if not player_matches:
            if smurf_cache:
                return smurf_cache["result"]
            return _unavailable_result(
                player_id,
                player_name,
                "无法提取该玩家的比赛表现数据。",
            )

        win_rate_score, wr = _score_win_rate(player_matches)
        gpm_score, xpm_score, avg_gpm, avg_xpm = _score_gpm_xpm(
            player_matches, benchmarks
        )
        kda_score, avg_kda = _score_kda(player_matches, benchmarks)
        streak_score, max_streak = _score_win_streak(player_matches)
        hero_score, hero_pool = _score_hero_pool(player_matches)

        total = current_match_count
        matches_score = 1.0 - _normalize(total, 100, 500)

        composite = (
            WEIGHTS["win_rate"] * win_rate_score
            + WEIGHTS["gpm_percentile"] * gpm_score
            + WEIGHTS["xpm_percentile"] * xpm_score
            + WEIGHTS["kda_ratio"] * kda_score
            + WEIGHTS["total_matches"] * matches_score
            + WEIGHTS["win_streak"] * streak_score
            + WEIGHTS["hero_pool"] * hero_score
        )

        recent_losses = sum(
            1 for m in player_matches[:20]
            if not _match_winner(
                m.get("player_slot", 0), m.get("radiant_win", False)
            )
        )
        if recent_losses > 5:
            composite *= 0.7

        details = {
            "win_rate": round(wr, 3),
            "win_rate_score": round(win_rate_score, 2),
            "gpm": round(avg_gpm, 1),
            "gpm_percentile_score": round(gpm_score, 2),
            "xpm": round(avg_xpm, 1),
            "xpm_percentile_score": round(xpm_score, 2),
            "kda": round(avg_kda, 2),
            "kda_score": round(kda_score, 2),
            "estimated_matches": total,
            "matches_score": round(matches_score, 2),
            "max_win_streak": max_streak,
            "streak_score": round(streak_score, 2),
            "hero_pool": hero_pool,
            "hero_pool_score": round(hero_score, 2),
            "recent_losses": recent_losses,
        }

        signals = [
            {
                "label": "胜率",
                "value": f"{wr:.0%}",
                "detail": f"近{len(player_matches)}场",
                "score": round(win_rate_score, 2),
            },
            {
                "label": "GPM",
                "value": f"{avg_gpm:.0f}",
                "detail": "超分段平均",
                "score": round(gpm_score, 2),
            },
            {
                "label": "XPM",
                "value": f"{avg_xpm:.0f}",
                "detail": "超分段平均",
                "score": round(xpm_score, 2),
            },
            {
                "label": "KDA",
                "value": f"{avg_kda:.1f}",
                "detail": "(K+A)/D",
                "score": round(kda_score, 2),
            },
            {
                "label": "场次",
                "value": str(total),
                "detail": "总场次越少越可疑",
                "score": round(matches_score, 2),
            },
            {
                "label": "连胜",
                "value": f"{max_streak}场",
                "detail": "近20场最大连胜",
                "score": round(streak_score, 2),
            },
            {
                "label": "英雄池",
                "value": f"{hero_pool}个",
                "detail": "近30场使用英雄",
                "score": round(hero_score, 2),
            },
        ]

        confidence = "high" if len(player_matches) >= 20 else "medium"
        result = {
            "player_id": player_id,
            "player_name": player_name,
            "score": round(composite, 2),
            "confidence": confidence,
            "signals": signals,
            "roast": _roast(composite, details),
            "details": details,
        }

        await db.execute(
            "INSERT OR REPLACE INTO smurf_check_cache "
            "(account_id, last_match_count, result) VALUES (?, ?, ?)",
            (
                player_id,
                current_match_count,
                json.dumps(result, ensure_ascii=False),
            ),
        )
        await db.commit()
        return result
    finally:
        await db.close()
