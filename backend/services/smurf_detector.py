"""小号检测引擎 — 多维加权评分模型"""
import json
import asyncio
from typing import Optional
from database.db import get_db
from services.opendota import (
    get_player,
    get_player_matches,
    get_match,
    get_benchmarks,
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

# ── 缓存过期时间 ──
CACHE_TTL = {
    "profile": 3600,     # 玩家档案 1 小时
    "benchmark": 86400,  # 英雄基准 24 小时
    "match": None,       # 比赛数据永不过期（靠 match_id 唯一性）
    "smurf_result": None,  # 结果按 last_match_count 判别过期
}

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
    key = "gold_per_min"
    return _calc_pct_from_benchmark(player_gpm, hero_bench, key)


def _calc_xpm_percentile(
    player_xpm: float, hero_bench: Optional[dict]
) -> float:
    if not hero_bench:
        return 0.5
    key = "xp_per_min"
    return _calc_pct_from_benchmark(player_xpm, hero_bench, key)


def _calc_kda_percentile(
    player_kda: float, hero_bench: Optional[dict]
) -> float:
    if not hero_bench:
        return 0.5
    key = "kda"
    return _calc_pct_from_benchmark(player_kda, hero_bench, key)


def _calc_pct_from_benchmark(
    value: float, bench_data: dict, key: str
) -> float:
    """从 benchmark JSON 推算值所在的百分位"""
    result = bench_data.get("result", {})
    gold_per_min_list = result.get(key, [])
    if not gold_per_min_list:
        return 0.5

    pct_map = {
        item.get("percentile", 0): item.get("value", 0)
        for item in gold_per_min_list
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
    # 65% 开始计分，80% 满分
    score = _normalize(wr, 0.55, 0.80)
    return score, wr


def _score_gpm_xpm(matches: list[dict], benchmarks: dict) -> tuple[float, float, float, float]:
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
        kda = (k + a) / d
        kdas.append(kda)
    avg_kda = sum(kdas) / len(kdas)
    score = _normalize(avg_kda, 1.5, 5.0)
    return score, avg_kda


def _score_win_streak(matches: list[dict]) -> tuple[float, int]:
    """近 20 场最大连胜"""
    if not matches:
        return 0.0, 0
    recent = matches[:20]
    max_streak = 0
    current = 0
    for m in recent:
        won = _match_winner(
            m.get("player_slot", 0), m.get("radiant_win", False)
        )
        if won:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    score = _normalize(max_streak, 4, 12)
    return score, max_streak


def _score_hero_pool(matches: list[dict]) -> tuple[float, int]:
    """英雄池深度 — 非典型小号极窄，但这里降权很低"""
    heroes = set(m.get("hero_id") for m in matches if m.get("hero_id"))
    pool = len(heroes)
    # 小号通常 < 8 个英雄，但也有全能型小号
    score = _normalize(pool, 2, 15)  # 英雄池越窄分越高
    score = 1.0 - score  # 反转：越窄越可疑
    return score, pool


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
            f"胜率{summary.get('win_rate',0):.0%}，GPM把同分段当提款机。"
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


async def _ensure_benchmarks(
    hero_ids: set[int],
) -> dict[int, Optional[dict]]:
    """确保需要 benchmark 的英雄数据已缓存"""
    db = await get_db()
    benchmarks: dict[int, Optional[dict]] = {}

    for hid in hero_ids:
        async with db.execute(
            "SELECT data FROM benchmark_cache WHERE hero_id = ?",
            (hid,),
        ) as cursor:
            row = await cursor.fetchone()
        if row:
            benchmarks[hid] = json.loads(row["data"])
            continue

        # 拉取并写入缓存
        try:
            data = await get_benchmarks(hid)
            if data:
                await db.execute(
                    "INSERT OR REPLACE INTO benchmark_cache (hero_id, data, fetched_at) "
                    "VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (hid, json.dumps(data, ensure_ascii=False)),
                )
        except Exception:
            data = None
        benchmarks[hid] = data

    await db.commit()
    await db.close()
    return benchmarks



async def _get_total_matches(player_id: int, fallback: int) -> int:
    """从 OpenDota wl 接口获取真实比赛总数"""
    BASE_URL = "https://api.opendota.com/api"
    try:
        wl = await _request(f"{BASE_URL}/players/{player_id}/wl")
        if isinstance(wl, dict):
            return wl.get("win", 0) + wl.get("lose", 0)
    except Exception:
        pass
    return fallback


async def detect_smurf(player_id: int) -> dict:
    """
    小号检测主函数。
    返回 { score, confidence, signals, roast, ... }
    """
    db = await get_db()

    # 1. 检查 smurf_check_cache
    profile_data = await get_player(player_id)
    total_matches = 0
    # 尝试从 profile 里拿总场次数；OpenDota 不一定有
    profile_inner = profile_data.get("profile", {}) if isinstance(profile_data, dict) else {}

    # 拉比赛列表
    raw_matches = await get_player_matches(player_id, MATCHES_TO_FETCH)
    if not raw_matches:
        await db.close()
        return {
            "player_id": player_id,
            "player_name": profile_inner.get("personaname", str(player_id)),
            "score": 0.0,
            "confidence": "low",
            "signals": [],
            "roast": "没有足够的比赛数据来判断，可能是个真正的萌新。",
            "details": {},
        }

    current_match_count = len(raw_matches)

    # 检查缓存：如果 match 数量没变，直接返回
    async with db.execute(
        "SELECT result, last_match_count FROM smurf_check_cache WHERE account_id = ?",
        (player_id,),
    ) as cursor:
        cached = await cursor.fetchone()

    if cached and cached["last_match_count"] >= current_match_count:
        await db.close()
        return json.loads(cached["result"])

    # 2. 确保每场比赛的详细数据已缓存
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
            continue

        new_match_ids.append(mid)

    # 拉取未缓存的比赛详情（间隔 200ms）
    for mid in new_match_ids:
        try:
            match_detail = await get_match(mid)
            detailed_matches.append(match_detail)
            await db.execute(
                "INSERT OR REPLACE INTO player_match_cache (match_id, account_id, data) "
                "VALUES (?, ?, ?)",
                (mid, player_id, json.dumps(match_detail, ensure_ascii=False)),
            )
        except Exception:
            # 拉不到的跳过
            pass
        await asyncio.sleep(0.2)

    await db.commit()

    # 3. 拉取所有用过的英雄的 benchmark
    benchmarks = await _ensure_benchmarks(hero_ids)

    # 4. 提取该玩家的比赛表现
    player_matches = []
    for match_detail in detailed_matches:
        players = match_detail.get("players", [])
        for p in players:
            if p.get("account_id") == player_id:
                pm = {
                    "match_id": match_detail.get("match_id"),
                    "hero_id": p.get("hero_id"),
                    "kills": p.get("kills", 0),
                    "deaths": p.get("deaths", 0),
                    "assists": p.get("assists", 0),
                    "gold_per_min": p.get("gold_per_min", 0),
                    "xp_per_min": p.get("xp_per_min", 0),
                    "player_slot": p.get("player_slot", 0),
                    "radiant_win": match_detail.get("radiant_win", False),
                }
                player_matches.append(pm)
                break

    if not player_matches:
        await db.close()
        return {
            "player_id": player_id,
            "player_name": profile_inner.get("personaname", str(player_id)),
            "score": 0.0,
            "confidence": "low",
            "signals": [],
            "roast": "无法提取该玩家的比赛表现数据。",
            "details": {},
        }

    # 5. 计算各信号
    win_rate_score, wr = _score_win_rate(player_matches)
    gpm_score, xpm_score, avg_gpm, avg_xpm = _score_gpm_xpm(player_matches, benchmarks)
    kda_score, avg_kda = _score_kda(player_matches, benchmarks)
    streak_score, max_streak = _score_win_streak(player_matches)
    hero_score, hero_pool = _score_hero_pool(player_matches)

    # total_matches: 用 profile 里的或拉取列表长度估算
    total = await _get_total_matches(player_id, current_match_count)
    matches_score = _normalize(total, 100, 500)
    matches_score = 1.0 - matches_score  # 场次越少越可疑

    # 6. 加权汇总
    composite = (
        WEIGHTS["win_rate"] * win_rate_score +
        WEIGHTS["gpm_percentile"] * gpm_score +
        WEIGHTS["xpm_percentile"] * xpm_score +
        WEIGHTS["kda_ratio"] * kda_score +
        WEIGHTS["total_matches"] * matches_score +
        WEIGHTS["win_streak"] * streak_score +
        WEIGHTS["hero_pool"] * hero_score
    )

    # 降权：如果近 20 场输了超过 5 场（= 胜率 < 75%），小号特征不明显
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
        "player_name": profile_inner.get("personaname", str(player_id)),
        "score": round(composite, 2),
        "confidence": confidence,
        "signals": signals,
        "roast": _roast(composite, details),
        "details": details,
    }

    # 7. 写入结果缓存
    await db.execute(
        "INSERT OR REPLACE INTO smurf_check_cache (account_id, last_match_count, result) "
        "VALUES (?, ?, ?)",
        (player_id, current_match_count, json.dumps(result, ensure_ascii=False)),
    )
    await db.commit()
    await db.close()

    return result
