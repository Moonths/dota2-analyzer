"""用户 Steam 绑定与档案路由"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import settings
from database.db import get_db
from services import steam
from services.opendota import get_player_ratings
from services.cache import cache_get_json, cache_set_json, cache_delete_json

router = APIRouter(prefix="/api/user", tags=["users"])

PROFILE_TTL = timedelta(hours=24)
CHINA_TIMEZONE = timezone(timedelta(hours=8))
HISTORY_RANK_TTL = 86400  # 历史段位缓存 1 天


class BindRequest(BaseModel):
    openid: str
    steam_input: str


class UnbindRequest(BaseModel):
    openid: str


def _row_to_profile(row) -> dict:
    return {
        "bound": True,
        "steam_id64": row["steam_id64"],
        "account_id": row["account_id"],
        "steam_name": row["steam_name"],
        "avatar": row["avatar"],
        "profile_url": row["profile_url"],
        "rank_tier": row["rank_tier"],
        "rank_name": row["rank_name"],
        "mmr_estimate": row["mmr_estimate"],
        "win_rate": row["win_rate"],
        "total_games": row["total_games"],
        "main_position": row["main_position"],
        "main_position_label": row["main_position_label"],
        "refreshed_at": row["refreshed_at"],
    }


async def _internal_record(db, openid: str) -> dict:
    """该用户在已录入的约战比赛里的内战胜率 (wins/total/win_rate)。"""
    async with db.execute(
        "SELECT COUNT(*) AS total, SUM(is_winner) AS wins "
        "FROM challenge_match_players WHERE openid = ?",
        (openid,),
    ) as cursor:
        row = await cursor.fetchone()
    total = row["total"] or 0
    wins = row["wins"] or 0
    rate = round(wins / total * 100, 1) if total else None
    return {"wins": wins, "total": total, "win_rate": rate}


async def _record_rank_history(db, openid: str, account_id: int,
                                rank_tier, rank_name: str | None) -> None:
    """记录段位快照, 用于历史段位梯状图。

    每次绑定/刷新都插入一条记录。OpenDota 公开 API 不暴露历史段位,
    只能自己跟踪累积。按年聚合时取每年最高值即可。
    """
    if rank_tier is None:
        return
    now = datetime.now(CHINA_TIMEZONE).isoformat(timespec="seconds")
    await db.execute(
        """INSERT INTO user_rank_history
           (openid, account_id, rank_tier, rank_name, recorded_at)
           VALUES (?, ?, ?, ?, ?)""",
        (openid, account_id, int(rank_tier), rank_name, now),
    )
    # 段位有变化时清掉历史段位缓存, 让下次请求重读
    await cache_delete_json(f"history_rank:{openid}")


async def _refresh_profile(db, row) -> dict:
    """拉取 Steam + Dota 最新数据并更新库，返回合并后的档案。"""
    steam_profile = await steam.get_steam_profile(row["steam_id64"]) or {}
    dota = await steam.build_dota_profile(row["account_id"])
    now = datetime.now(CHINA_TIMEZONE).isoformat(timespec="seconds")
    await db.execute(
        """UPDATE users SET steam_name = ?, avatar = ?, profile_url = ?,
           rank_tier = ?, rank_name = ?, mmr_estimate = ?,
           win_rate = ?, total_games = ?, main_position = ?, main_position_label = ?,
           refreshed_at = ?
           WHERE openid = ?""",
        (
            steam_profile.get("steam_name") or row["steam_name"],
            steam_profile.get("avatar") or row["avatar"],
            steam_profile.get("profile_url") or row["profile_url"],
            dota["rank_tier"], dota["rank_name"], dota["mmr_estimate"],
            dota["win_rate"], dota["total_games"],
            dota["main_position"], dota["main_position_label"],
            now, row["openid"],
        ),
    )
    # 记录段位快照 (用于历史段位梯状图)
    await _record_rank_history(
        db, row["openid"], row["account_id"],
        dota.get("rank_tier"), dota.get("rank_name"),
    )
    await db.commit()

    class Merged:
        """用 row 兜底、新数据覆盖"""

        def __getitem__(self, key):
            if key in steam_profile and steam_profile[key] is not None:
                return steam_profile[key]
            if key in dota and dota[key] is not None:
                return dota[key]
            return row[key]

    return _row_to_profile(Merged())


@router.post("/bind")
async def bind_steam(req: BindRequest):
    openid = (req.openid or "").strip()
    if not openid:
        raise HTTPException(status_code=400, detail="缺少用户身份")
    if not settings.steam_api_key:
        raise HTTPException(status_code=500, detail="服务端未配置 Steam API Key")

    try:
        steamid64 = await steam.resolve_steam_id(req.steam_input)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError:
        raise HTTPException(status_code=500, detail="Steam API Key 无效")
    except Exception:
        raise HTTPException(status_code=502, detail="Steam 接口暂时不可用，请稍后再试")

    try:
        steam_profile = await steam.get_steam_profile(steamid64)
    except PermissionError:
        raise HTTPException(status_code=500, detail="Steam API Key 无效")
    except Exception:
        raise HTTPException(status_code=502, detail="Steam 接口暂时不可用，请稍后再试")
    if not steam_profile:
        raise HTTPException(status_code=400, detail="Steam 账号不存在，请检查输入")

    account_id = steam.account_id_from_steam64(steamid64)
    dota = await steam.build_dota_profile(account_id)
    now = datetime.now(CHINA_TIMEZONE).isoformat(timespec="seconds")

    db = await get_db()
    try:
        # 同一个 Steam 账号只能被一个微信身份绑定，先清掉旧绑定
        await db.execute(
            "DELETE FROM users WHERE steam_id64 = ? AND openid != ?",
            (steamid64, openid),
        )
        await db.execute(
            """INSERT INTO users
               (openid, steam_id64, account_id, steam_name, avatar, profile_url,
                rank_tier, rank_name, mmr_estimate, win_rate, total_games,
                main_position, main_position_label, refreshed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(openid) DO UPDATE SET
                 steam_id64 = excluded.steam_id64,
                 account_id = excluded.account_id,
                 steam_name = excluded.steam_name,
                 avatar = excluded.avatar,
                 profile_url = excluded.profile_url,
                 rank_tier = excluded.rank_tier,
                 rank_name = excluded.rank_name,
                 mmr_estimate = excluded.mmr_estimate,
                 win_rate = excluded.win_rate,
                 total_games = excluded.total_games,
                 main_position = excluded.main_position,
                 main_position_label = excluded.main_position_label,
                 refreshed_at = excluded.refreshed_at""",
            (
                openid, steamid64, account_id,
                steam_profile["steam_name"], steam_profile["avatar"],
                steam_profile["profile_url"],
                dota["rank_tier"], dota["rank_name"], dota["mmr_estimate"],
                dota["win_rate"], dota["total_games"],
                dota["main_position"], dota["main_position_label"],
                now,
            ),
        )
        await db.commit()
        # 记录初始段位快照 (用于历史段位梯状图)
        await _record_rank_history(
            db, openid, account_id,
            dota.get("rank_tier"), dota.get("rank_name"),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM users WHERE openid = ?", (openid,)
        ) as cursor:
            row = await cursor.fetchone()
    finally:
        await db.close()

    return _row_to_profile(row)


@router.get("/profile")
async def get_profile(openid: str):
    openid = (openid or "").strip()
    if not openid:
        raise HTTPException(status_code=400, detail="缺少用户身份")

    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM users WHERE openid = ?", (openid,)
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return {"bound": False}

        profile = None
        # 超过 24h 自动刷新（失败时返回旧数据）
        try:
            refreshed = datetime.fromisoformat(row["refreshed_at"])
            if datetime.now(CHINA_TIMEZONE) - refreshed > PROFILE_TTL:
                profile = await _refresh_profile(db, row)
        except Exception:
            pass
        if profile is None:
            profile = _row_to_profile(row)
        # 内战胜率 (基于已录入的约战比赛)
        profile["internal_record"] = await _internal_record(db, openid)
        return profile
    finally:
        await db.close()


@router.post("/unbind")
async def unbind_steam(req: UnbindRequest):
    openid = (req.openid or "").strip()
    if not openid:
        raise HTTPException(status_code=400, detail="缺少用户身份")
    db = await get_db()
    try:
        await db.execute("DELETE FROM users WHERE openid = ?", (openid,))
        await db.commit()
    finally:
        await db.close()
    return {"bound": False}


@router.get("/history_rank")
async def get_history_rank(openid: str):
    """历史段位: 返回原始记录点 (时间+段位), 用于折线图。

    数据源 (同日同段位去重后按时间排序):
    1. OpenDota /ratings 接口: OpenDota 从 2025-12 起在处理排位赛时
       记录每位玩家的当时段位, 免费无鉴权, 对所有玩家生效 (无需登录
       opendota.com)。覆盖不了 2025-12 之前的比赛, 也不含不朽玩家。
    2. 本地 user_rank_history: 我们在用户绑定/刷新档案时自己记录的快照,
       兜底保证至少有绑定当天的数据。
    """
    openid = (openid or "").strip()
    if not openid:
        raise HTTPException(status_code=400, detail="缺少用户身份")

    db = await get_db()
    try:
        async with db.execute(
            "SELECT account_id FROM users WHERE openid = ?", (openid,)
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="未绑定 Steam 账号")
        account_id = row["account_id"]
    finally:
        await db.close()

    # Redis 缓存优先 (1 天 TTL)
    cache_key = f"history_rank:{openid}"
    cached = await cache_get_json(cache_key)
    if cached is not None:
        return {"data": cached}

    year_best: dict[int, int] = {}
    points: list[dict] = []

    def _add_point(iso_time: str, rank_tier: int) -> None:
        """原始记录点, 同日同段位去重"""
        try:
            t = datetime.fromisoformat(str(iso_time).replace("Z", "+00:00"))
        except (TypeError, ValueError, OSError):
            return
        year = t.astimezone(CHINA_TIMEZONE).year
        if year not in year_best or rank_tier > year_best[year]:
            year_best[year] = rank_tier
        day_key = (t.date().isoformat(), rank_tier)
        if day_key not in _seen_days:
            _seen_days.add(day_key)
            points.append({
                "t": t.astimezone(CHINA_TIMEZONE).isoformat(timespec="seconds"),
                "v": rank_tier,
                "rank_name": steam.rank_name(rank_tier),
            })

    _seen_days: set = set()

    # 1. OpenDota ratings (真实历史段位, 2025-12 起对全量玩家生效)
    try:
        ratings = await get_player_ratings(account_id)
    except Exception:
        ratings = None
    for r in ratings or []:
        rt = r.get("rank_tier")
        ts = r.get("time")
        if rt is None or not ts:
            continue
        try:
            _add_point(ts, int(rt))
        except (TypeError, ValueError):
            continue

    # 2. 本地 user_rank_history 兜底合并 (绑定/刷新时记录的快照)
    db = await get_db()
    try:
        async with db.execute(
            """SELECT rank_tier, recorded_at FROM user_rank_history
               WHERE openid = ? AND rank_tier IS NOT NULL
               ORDER BY recorded_at ASC""",
            (openid,),
        ) as cursor:
            rows = await cursor.fetchall()
    finally:
        await db.close()
    for r in rows:
        try:
            _add_point(r["recorded_at"], int(r["rank_tier"]))
        except (TypeError, ValueError):
            continue

    points.sort(key=lambda p: p["t"])
    await cache_set_json(cache_key, points, ttl=HISTORY_RANK_TTL)
    return {"data": points}
