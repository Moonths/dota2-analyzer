"""约战模块路由

规则（与产品约定一致）:
- 未绑定 Steam 不能发起/参与
- 段位门槛: 用 rank_tier (OpenDota 稳定返回) 校验；用户段位未知则放行
- 固定队伍: 报名时自选队，每队容量 = 上限/2
- 自由组队: 报名不分队，满员后发起人一键随机分队，之后可手动对调
- 编辑: 仅名称/说明/时间；人数上限与段位门槛创建后锁定
- 状态: 满员动态计算；过时间未满员 → 已结束(未成局)；取消为软删
"""
import random
import uuid
from datetime import datetime, timedelta, timezone

import aiosqlite
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.db import get_db
from services.steam import rank_name
from services.opendota import get_match, get_heroes
from services.hero_cn import cn_name
from services.cache import cache_get_json, cache_set_json, cache_delete_json

router = APIRouter(prefix="/api/challenge", tags=["challenges"])

CHINA_TIMEZONE = timezone(timedelta(hours=8))
MODES = ("free", "fixed")

# 段位档位: 1=先锋 ... 8=不朽; rank_tier = tier*10 + star(0-7)
RANK_TIERS = (
    (1, "先锋"), (2, "卫士"), (3, "中军"), (4, "统帅"),
    (5, "传奇"), (6, "万古流芳"), (7, "超凡入圣"), (8, "不朽"),
)


def _tier_floor(tier: int) -> int:
    """段位档位 → rank_tier 下限 (如统帅=40)"""
    return tier * 10


def _tier_ceil(tier: int) -> int:
    """段位档位 → rank_tier 上限 (如统帅=47, 含0-7星)"""
    return tier * 10 + 7


def _tier_label(rank_tier_val) -> str | None:
    """rank_tier 数值 → 中文段位名（复用 services.steam.rank_name）"""
    if rank_tier_val is None:
        return None
    return rank_name(rank_tier_val)


class CreateRequest(BaseModel):
    openid: str
    name: str
    description: str = ""
    activity_time: str  # "YYYY-MM-DD HH:MM"
    rank_tier_min: int | None = None  # 段位档位 1-8 (先锋-不朽)
    rank_tier_max: int | None = None
    max_players: int = 10
    mode: str = "free"
    team_a_name: str = ""
    team_b_name: str = ""
    self_join: bool = True


class JoinRequest(BaseModel):
    openid: str
    team: int | None = None  # 固定队伍模式必填: 0 或 1


class LeaveRequest(BaseModel):
    openid: str


class SwitchTeamRequest(BaseModel):
    openid: str
    team: int


class SwapRequest(BaseModel):
    openid: str
    participant_a: int  # challenge_participants.id
    participant_b: int


class UpdateRequest(BaseModel):
    openid: str
    name: str | None = None
    description: str | None = None
    activity_time: str | None = None


class CancelRequest(BaseModel):
    openid: str


# ── 工具 ──

def _now() -> datetime:
    return datetime.now(CHINA_TIMEZONE).replace(tzinfo=None)


def _parse_time(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="活动时间格式应为 YYYY-MM-DD HH:MM")


async def _get_user_row(db, openid: str):
    async with db.execute(
        "SELECT * FROM users WHERE openid = ?", (openid,)
    ) as cursor:
        return await cursor.fetchone()


async def _get_challenge_row(db, challenge_id: str):
    async with db.execute(
        "SELECT * FROM challenges WHERE id = ?", (challenge_id,)
    ) as cursor:
        return await cursor.fetchone()


async def _participants(db, challenge_id: str) -> list[dict]:
    async with db.execute(
        """SELECT * FROM challenge_participants
           WHERE challenge_id = ? ORDER BY joined_at ASC""",
        (challenge_id,),
    ) as cursor:
        rows = await cursor.fetchall()
    return [
        {
            "id": r["id"], "openid": r["openid"], "team": r["team"],
            "steam_name": r["steam_name"], "avatar": r["avatar"],
            "rank_tier": r["rank_tier"], "rank_name": r["rank_name"],
            "mmr": r["mmr"],
        }
        for r in rows
    ]


def _compute_status(challenge, count: int) -> dict:
    """返回 {status, status_label}。满员为动态计算。"""
    if challenge["status"] == "cancelled":
        return {"status": "cancelled", "status_label": "已取消"}
    if _now() >= _parse_time(challenge["activity_time"]):
        label = "已结束" if count >= challenge["max_players"] else "已结束(未成局)"
        return {"status": "ended", "status_label": label}
    if count >= challenge["max_players"]:
        return {"status": "full", "status_label": "已满员"}
    return {"status": "open", "status_label": "报名中"}


def _challenge_dict(db_row, count: int) -> dict:
    d = {
        "id": db_row["id"],
        "creator_openid": db_row["creator_openid"],
        "name": db_row["name"],
        "description": db_row["description"],
        "activity_time": db_row["activity_time"],
        "rank_tier_min": db_row["rank_tier_min"],
        "rank_tier_max": db_row["rank_tier_max"],
        "max_players": db_row["max_players"],
        "mode": db_row["mode"],
        "team_a_name": db_row["team_a_name"],
        "team_b_name": db_row["team_b_name"],
        "participant_count": count,
        "created_at": db_row["created_at"],
    }
    d.update(_compute_status(db_row, count))
    return d


async def _count(db, challenge_id: str) -> int:
    async with db.execute(
        "SELECT COUNT(*) AS c FROM challenge_participants WHERE challenge_id = ?",
        (challenge_id,),
    ) as cursor:
        row = await cursor.fetchone()
    return row["c"]


async def _require_bound(db, openid: str):
    user = await _get_user_row(db, openid)
    if not user:
        raise HTTPException(status_code=403, detail="请先在「我的」页面绑定 Steam 账号")
    return user


def _check_rank(challenge, user) -> None:
    """段位门槛: 用 rank_tier 校验；用户段位未知(None)则放行。"""
    rt = user["rank_tier"]
    if rt is None:
        return
    lo, hi = challenge["rank_tier_min"], challenge["rank_tier_max"]
    if lo is not None and rt < lo:
        raise HTTPException(
            status_code=400,
            detail=f"段位门槛 {_tier_label(lo) or lo} 起，你的段位 {_tier_label(rt) or '未知'} 不达标",
        )
    if hi is not None and rt > hi:
        raise HTTPException(
            status_code=400,
            detail=f"段位上限 {_tier_label(hi) or hi}，你的段位 {_tier_label(rt) or '未知'} 超出",
        )


async def _join_locked(db, challenge, user, team: int | None) -> None:
    """调用方已确认: 活动 open / 未满 / 段位达标。"""
    if challenge["mode"] == "fixed":
        if team not in (0, 1):
            raise HTTPException(status_code=400, detail="固定队伍模式需选择队伍")
        cap = challenge["max_players"] // 2
        async with db.execute(
            "SELECT COUNT(*) AS c FROM challenge_participants WHERE challenge_id = ? AND team = ?",
            (challenge["id"], team),
        ) as cursor:
            row = await cursor.fetchone()
        if row["c"] >= cap:
            raise HTTPException(status_code=400, detail="该队伍已满，请选另一队")
    else:
        team = -1

    await db.execute(
        """INSERT INTO challenge_participants
           (challenge_id, openid, team, steam_name, avatar, rank_tier, rank_name, mmr)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            challenge["id"], user["openid"], team,
            user["steam_name"], user["avatar"],
            user["rank_tier"], user["rank_name"], user["mmr_estimate"],
        ),
    )
    await db.execute(
        "UPDATE challenges SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (challenge["id"],),
    )
    await db.commit()


# ── 接口 ──

@router.post("/create")
async def create_challenge(req: CreateRequest):
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="请填写活动名称")
    if len(name) > 40:
        raise HTTPException(status_code=400, detail="活动名称最多 40 字")
    if req.mode not in MODES:
        raise HTTPException(status_code=400, detail="模式参数错误")
    if req.max_players < 2 or req.max_players > 20 or req.max_players % 2 != 0:
        raise HTTPException(status_code=400, detail="人数上限需为 2-20 的偶数")
    # 段位门槛: 前端传档位 1-8 (先锋-不朽)，存为 rank_tier 数值
    rt_min = None
    rt_max = None
    if req.rank_tier_min is not None:
        if req.rank_tier_min < 1 or req.rank_tier_min > 8:
            raise HTTPException(status_code=400, detail="最低段位档位 1-8")
        rt_min = _tier_floor(req.rank_tier_min)
    if req.rank_tier_max is not None:
        if req.rank_tier_max < 1 or req.rank_tier_max > 8:
            raise HTTPException(status_code=400, detail="最高段位档位 1-8")
        rt_max = _tier_ceil(req.rank_tier_max)
    if rt_min is not None and rt_max is not None and rt_min > rt_max:
        raise HTTPException(status_code=400, detail="最低段位不能高于最高段位")
    activity_time = _parse_time(req.activity_time)
    if activity_time <= _now():
        raise HTTPException(status_code=400, detail="活动时间必须晚于当前时间")

    team_a, team_b = "天辉", "夜魇"
    if req.mode == "fixed":
        team_a = (req.team_a_name or "").strip()
        team_b = (req.team_b_name or "").strip()
        if not team_a or not team_b:
            raise HTTPException(status_code=400, detail="固定队伍模式需填写两个队伍名称")
        if team_a == team_b:
            raise HTTPException(status_code=400, detail="两个队伍名称不能相同")
        if len(team_a) > 12 or len(team_b) > 12:
            raise HTTPException(status_code=400, detail="队伍名称最多 12 字")

    db = await get_db()
    try:
        user = await _require_bound(db, req.openid)
        challenge_id = uuid.uuid4().hex[:12]
        await db.execute(
            """INSERT INTO challenges
               (id, creator_openid, name, description, activity_time,
                rank_tier_min, rank_tier_max, max_players, mode, team_a_name, team_b_name)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                challenge_id, req.openid, name, (req.description or "").strip(),
                req.activity_time, rt_min, rt_max, req.max_players,
                req.mode, team_a, team_b,
            ),
        )
        challenge = await _get_challenge_row(db, challenge_id)
        if req.self_join:
            await _join_locked(db, challenge, user, team=None if req.mode == "free" else 0)
        else:
            await db.commit()
        return {"id": challenge_id}
    finally:
        await db.close()


@router.get("/list")
async def list_challenges(openid: str = ""):
    """约战列表: 报名中 + 未过期，按创建时间倒序（最新发起在前）。"""
    db = await get_db()
    try:
        async with db.execute(
            "SELECT * FROM challenges WHERE status = 'open' ORDER BY created_at DESC LIMIT 100"
        ) as cursor:
            rows = await cursor.fetchall()
        out = []
        for r in rows:
            count = await _count(db, r["id"])
            status = _compute_status(r, count)
            if status["status"] != "open":
                continue
            item = _challenge_dict(r, count)
            async with db.execute(
                "SELECT steam_name, avatar FROM users WHERE openid = ?",
                (r["creator_openid"],),
            ) as cursor:
                creator = await cursor.fetchone()
            item["creator_name"] = creator["steam_name"] if creator else "未知"
            item["creator_avatar"] = creator["avatar"] if creator else ""
            async with db.execute(
                "SELECT 1 FROM challenge_participants WHERE challenge_id = ? AND openid = ?",
                (r["id"], openid),
            ) as cursor:
                item["joined"] = bool(await cursor.fetchone())
            out.append(item)
        return {"challenges": out}
    finally:
        await db.close()


@router.get("/mine")
async def my_challenges(openid: str):
    """我参与的（含我发起的），按创建时间倒序。"""
    if not openid:
        raise HTTPException(status_code=400, detail="缺少用户身份")
    db = await get_db()
    try:
        async with db.execute(
            """SELECT DISTINCT c.* FROM challenges c
               LEFT JOIN challenge_participants p ON p.challenge_id = c.id
               WHERE c.creator_openid = ? OR p.openid = ?
               ORDER BY c.created_at DESC LIMIT 100""",
            (openid, openid),
        ) as cursor:
            rows = await cursor.fetchall()
        out = []
        for r in rows:
            count = await _count(db, r["id"])
            item = _challenge_dict(r, count)
            item["is_creator"] = r["creator_openid"] == openid
            async with db.execute(
                "SELECT team FROM challenge_participants WHERE challenge_id = ? AND openid = ?",
                (r["id"], openid),
            ) as cursor:
                mine = await cursor.fetchone()
            item["joined"] = mine is not None
            item["my_team"] = mine["team"] if mine else None
            async with db.execute(
                "SELECT steam_name FROM users WHERE openid = ?",
                (r["creator_openid"],),
            ) as cursor:
                creator = await cursor.fetchone()
            item["creator_name"] = creator["steam_name"] if creator else "未知"
            out.append(item)
        return {"challenges": out}
    finally:
        await db.close()


@router.get("/{challenge_id}")
async def challenge_detail(challenge_id: str, openid: str = ""):
    db = await get_db()
    try:
        challenge = await _get_challenge_row(db, challenge_id)
        if not challenge:
            raise HTTPException(status_code=404, detail="约战不存在")
        participants = await _participants(db, challenge_id)
        item = _challenge_dict(challenge, len(participants))
        item["is_creator"] = bool(openid) and challenge["creator_openid"] == openid
        item["my_openid"] = openid
        me = next((p for p in participants if p["openid"] == openid), None)
        item["joined"] = me is not None
        item["my_team"] = me["team"] if me else None
        item["my_rank_unknown"] = bool(me and me["rank_tier"] is None)
        item["participants"] = participants
        async with db.execute(
            "SELECT steam_name, avatar FROM users WHERE openid = ?",
            (challenge["creator_openid"],),
        ) as cursor:
            creator = await cursor.fetchone()
        item["creator_name"] = creator["steam_name"] if creator else "未知"
        item["creator_avatar"] = creator["avatar"] if creator else ""
        return item
    finally:
        await db.close()


@router.post("/{challenge_id}/join")
async def join_challenge(challenge_id: str, req: JoinRequest):
    db = await get_db()
    try:
        challenge = await _get_challenge_row(db, challenge_id)
        if not challenge:
            raise HTTPException(status_code=404, detail="约战不存在")
        if challenge["status"] == "cancelled":
            raise HTTPException(status_code=400, detail="该约战已取消")
        if _now() >= _parse_time(challenge["activity_time"]):
            raise HTTPException(status_code=400, detail="该约战已过活动时间")
        if challenge["creator_openid"] != req.openid and await _count(db, challenge_id) >= challenge["max_players"]:
            raise HTTPException(status_code=400, detail="该约战已满员")

        user = await _require_bound(db, req.openid)
        async with db.execute(
            "SELECT 1 FROM challenge_participants WHERE challenge_id = ? AND openid = ?",
            (challenge_id, req.openid),
        ) as cursor:
            if await cursor.fetchone():
                raise HTTPException(status_code=400, detail="你已经报名过了")
        _check_rank(challenge, user)
        await _join_locked(db, challenge, user, req.team)
        return {"ok": True}
    finally:
        await db.close()


@router.post("/{challenge_id}/leave")
async def leave_challenge(challenge_id: str, req: LeaveRequest):
    db = await get_db()
    try:
        challenge = await _get_challenge_row(db, challenge_id)
        if not challenge:
            raise HTTPException(status_code=404, detail="约战不存在")
        async with db.execute(
            "SELECT * FROM challenge_participants WHERE challenge_id = ? AND openid = ?",
            (challenge_id, req.openid),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="你不在该约战中")

        await db.execute("DELETE FROM challenge_participants WHERE id = ?", (row["id"],))

        # 自由组队已分队后有人退出 → 名单变化，重置全部分队待重新分配
        assigned = any(p["team"] >= 0 for p in await _participants(db, challenge_id))
        if challenge["mode"] == "free" and assigned:
            await db.execute(
                "UPDATE challenge_participants SET team = -1 WHERE challenge_id = ?",
                (challenge_id,),
            )
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@router.post("/{challenge_id}/switch_team")
async def switch_team(challenge_id: str, req: SwitchTeamRequest):
    """固定队伍模式: 参与者自己换队（受每队容量限制）。"""
    db = await get_db()
    try:
        challenge = await _get_challenge_row(db, challenge_id)
        if not challenge:
            raise HTTPException(status_code=404, detail="约战不存在")
        if challenge["mode"] != "fixed":
            raise HTTPException(status_code=400, detail="自由组队模式不支持自选换队")
        if req.team not in (0, 1):
            raise HTTPException(status_code=400, detail="队伍参数错误")
        if _now() >= _parse_time(challenge["activity_time"]):
            raise HTTPException(status_code=400, detail="该约战已过活动时间")

        async with db.execute(
            "SELECT * FROM challenge_participants WHERE challenge_id = ? AND openid = ?",
            (challenge_id, req.openid),
        ) as cursor:
            me = await cursor.fetchone()
        if not me:
            raise HTTPException(status_code=400, detail="你不在该约战中")
        if me["team"] == req.team:
            raise HTTPException(status_code=400, detail="你已在该队伍中")

        cap = challenge["max_players"] // 2
        async with db.execute(
            "SELECT COUNT(*) AS c FROM challenge_participants WHERE challenge_id = ? AND team = ?",
            (challenge_id, req.team),
        ) as cursor:
            row = await cursor.fetchone()
        if row["c"] >= cap:
            raise HTTPException(status_code=400, detail="目标队伍已满")

        await db.execute(
            "UPDATE challenge_participants SET team = ? WHERE id = ?", (req.team, me["id"])
        )
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@router.post("/{challenge_id}/shuffle")
async def shuffle_teams(challenge_id: str, req: LeaveRequest):
    """自由组队: 满员后发起人一键随机分队。"""
    db = await get_db()
    try:
        challenge = await _get_challenge_row(db, challenge_id)
        if not challenge:
            raise HTTPException(status_code=404, detail="约战不存在")
        if challenge["creator_openid"] != req.openid:
            raise HTTPException(status_code=403, detail="只有发起人可以分队")
        if challenge["mode"] != "free":
            raise HTTPException(status_code=400, detail="固定队伍模式无需分队")
        if _now() >= _parse_time(challenge["activity_time"]):
            raise HTTPException(status_code=400, detail="该约战已过活动时间")

        participants = await _participants(db, challenge_id)
        if len(participants) != challenge["max_players"]:
            raise HTTPException(status_code=400, detail="满员后才能分队")

        ids = [p["id"] for p in participants]
        random.shuffle(ids)
        half = len(ids) // 2
        for idx, pid in enumerate(ids):
            team = 0 if idx < half else 1
            await db.execute(
                "UPDATE challenge_participants SET team = ? WHERE id = ?", (team, pid)
            )
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@router.post("/{challenge_id}/swap")
async def swap_participants(challenge_id: str, req: SwapRequest):
    """发起人微调: 对调两名参与者的队伍。"""
    db = await get_db()
    try:
        challenge = await _get_challenge_row(db, challenge_id)
        if not challenge:
            raise HTTPException(status_code=404, detail="约战不存在")
        if challenge["creator_openid"] != req.openid:
            raise HTTPException(status_code=403, detail="只有发起人可以调整")

        rows = []
        for pid in (req.participant_a, req.participant_b):
            async with db.execute(
                "SELECT * FROM challenge_participants WHERE id = ? AND challenge_id = ?",
                (pid, challenge_id),
            ) as cursor:
                r = await cursor.fetchone()
            if not r:
                raise HTTPException(status_code=400, detail="参与者不存在")
            rows.append(r)
        a, b = rows
        await db.execute("UPDATE challenge_participants SET team = ? WHERE id = ?", (b["team"], a["id"]))
        await db.execute("UPDATE challenge_participants SET team = ? WHERE id = ?", (a["team"], b["id"]))
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@router.post("/{challenge_id}/update")
async def update_challenge(challenge_id: str, req: UpdateRequest):
    """发起人编辑: 仅名称/说明/时间。"""
    db = await get_db()
    try:
        challenge = await _get_challenge_row(db, challenge_id)
        if not challenge:
            raise HTTPException(status_code=404, detail="约战不存在")
        if challenge["creator_openid"] != req.openid:
            raise HTTPException(status_code=403, detail="只有发起人可以编辑")

        sets, params = [], []
        if req.name is not None:
            name = req.name.strip()
            if not name:
                raise HTTPException(status_code=400, detail="活动名称不能为空")
            if len(name) > 40:
                raise HTTPException(status_code=400, detail="活动名称最多 40 字")
            sets.append("name = ?"); params.append(name)
        if req.description is not None:
            sets.append("description = ?"); params.append(req.description.strip())
        if req.activity_time is not None:
            activity_time = _parse_time(req.activity_time)
            if activity_time <= _now():
                raise HTTPException(status_code=400, detail="活动时间必须晚于当前时间")
            sets.append("activity_time = ?"); params.append(req.activity_time)
        if not sets:
            raise HTTPException(status_code=400, detail="没有需要更新的内容")

        params.extend(["CURRENT_TIMESTAMP", challenge_id])
        await db.execute(
            f"UPDATE challenges SET {', '.join(sets)}, updated_at = ? WHERE id = ?", params
        )
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


@router.post("/{challenge_id}/cancel")
async def cancel_challenge(challenge_id: str, req: CancelRequest):
    db = await get_db()
    try:
        challenge = await _get_challenge_row(db, challenge_id)
        if not challenge:
            raise HTTPException(status_code=404, detail="约战不存在")
        if challenge["creator_openid"] != req.openid:
            raise HTTPException(status_code=403, detail="只有发起人可以取消")
        if challenge["status"] == "cancelled":
            raise HTTPException(status_code=400, detail="该约战已是取消状态")
        await db.execute(
            "UPDATE challenges SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (challenge_id,),
        )
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()


# ── 约战挂比赛 ──

class AddMatchRequest(BaseModel):
    openid: str
    match_id: int


def _match_redis_key(challenge_id: str) -> str:
    return f"dota2:challenge_match:{challenge_id}"


def _norm(v, mx):
    return round(min(v / mx, 1.0) * 100, 1) if mx else 0.0


async def _participant_acct_map(db, challenge_id: str) -> dict:
    """{account_id: openid} 本约战参与者映射，用于把场上 player 归属到人。"""
    async with db.execute(
        """SELECT u.account_id AS acct, cp.openid AS openid
           FROM challenge_participants cp
           JOIN users u ON cp.openid = u.openid
           WHERE cp.challenge_id = ? AND u.account_id IS NOT NULL""",
        (challenge_id,),
    ) as cursor:
        rows = await cursor.fetchall()
    return {r["acct"]: r["openid"] for r in rows}


async def _fetch_and_persist_match(
    db, challenge_id: str, match_id: int, submitted_by: str
) -> dict:
    """拉 OpenDota → 算雷达 → 写 challenge_matches + challenge_match_players + redis。

    覆盖语义: 同一约战只保留一场比赛，录入新场前清掉旧的。
    """
    try:
        data = await get_match(match_id)
    except Exception:
        raise HTTPException(status_code=502, detail="拉取比赛数据失败，请确认比赛ID正确且为公开比赛")
    if not data or not data.get("players"):
        raise HTTPException(status_code=400, detail="该比赛ID无数据，可能是私企/未公开")

    heroes = await get_heroes()
    radiant_win = data.get("radiant_win", False)
    players_raw = data.get("players", []) or []
    acct_to_openid = await _participant_acct_map(db, challenge_id)

    # 每维最大值（含本约战参与者标记）
    kdas, gpms, xpms, hdmg, tdmg, heal = [], [], [], [], [], []
    for p in players_raw:
        k, d, a = p.get("kills", 0), p.get("deaths", 0), p.get("assists", 0)
        kdas.append((k + a) / (d + 1))
        gpms.append(p.get("gold_per_min", 0))
        xpms.append(p.get("xp_per_min", 0))
        hdmg.append(p.get("hero_damage", 0))
        tdmg.append(p.get("tower_damage", 0))
        heal.append(p.get("hero_healing", 0))
    max_kda = max(kdas) if kdas else 1
    max_gpm = max(gpms) if gpms else 1
    max_xpm = max(xpms) if xpms else 1
    max_hdmg = max(hdmg) if hdmg else 1
    max_tdmg = max(tdmg) if tdmg else 1
    max_heal = max(heal) if heal else 1

    # 组装 player payload + 入库行
    players_out = []
    insert_rows = []
    for p in players_raw:
        hero = heroes.get(p.get("hero_id"), {})
        en_name = hero.get("localized_name", "")
        acct = p.get("account_id")
        is_radiant = p.get("isRadiant", (p.get("player_slot", 0) or 0) < 128)
        k, d, a = p.get("kills", 0), p.get("deaths", 0), p.get("assists", 0)
        gpm = p.get("gold_per_min", 0)
        xpm = p.get("xp_per_min", 0)
        hdmg_v = p.get("hero_damage", 0)
        tdmg_v = p.get("tower_damage", 0)
        heal_v = p.get("hero_healing", 0)
        kda_v = (k + a) / (d + 1)
        hero_name = cn_name(en_name) or f"Hero_{p.get('hero_id')}"
        hero_icon = f"/hero-img/{hero.get('name', 'unknown').replace('npc_dota_hero_', '')}.png"
        openid_match = acct_to_openid.get(acct) if acct else None

        radar = {
            "kda": _norm(kda_v, max_kda),
            "eco": _norm(gpm, max_gpm),
            "exp": _norm(xpm, max_xpm),
            "dmg": _norm(hdmg_v, max_hdmg),
            "push": _norm(tdmg_v, max_tdmg),
            "sustain": _norm(heal_v, max_heal),
        }
        players_out.append({
            "account_id": acct,
            "openid": openid_match,
            "player_name": p.get("personaname") or (str(acct) if acct else "未知"),
            "hero_id": p.get("hero_id"),
            "hero_name": hero_name,
            "hero_icon": hero_icon,
            "is_radiant": is_radiant,
            "is_winner": is_radiant == radiant_win,
            "is_participant": openid_match is not None,
            "kills": k, "deaths": d, "assists": a,
            "gpm": gpm, "xpm": xpm,
            "hero_damage": hdmg_v, "tower_damage": tdmg_v, "healing": heal_v,
            "last_hits": p.get("last_hits", 0), "denies": p.get("denies", 0),
            "level": p.get("level", 1),
            "radar": radar,
        })
        insert_rows.append((
            challenge_id, match_id, openid_match, acct,
            p.get("personaname") or (str(acct) if acct else "未知"),
            1 if is_radiant else 0,
            1 if is_radiant == radiant_win else 0,
            p.get("hero_id"), hero_name, hero_icon,
            k, d, a, gpm, xpm, hdmg_v, tdmg_v, heal_v,
            p.get("last_hits", 0), p.get("denies", 0), p.get("level", 1),
            radar["kda"], radar["eco"], radar["exp"],
            radar["dmg"], radar["push"], radar["sustain"],
        ))

    # 覆盖: 先清旧数据
    await db.execute("DELETE FROM challenge_match_players WHERE challenge_id = ?", (challenge_id,))
    await db.execute("DELETE FROM challenge_matches WHERE challenge_id = ?", (challenge_id,))
    # 写新场（含比赛级字段）
    await db.execute(
        """INSERT INTO challenge_matches
           (challenge_id, match_id, submitted_by, duration, radiant_score, dire_score, avg_mmr)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            challenge_id, match_id, submitted_by,
            data.get("duration", 0), data.get("radiant_score", 0),
            data.get("dire_score", 0), data.get("avg_mmr"),
        ),
    )
    await db.executemany(
        """INSERT INTO challenge_match_players
           (challenge_id, match_id, openid, account_id, player_name,
            is_radiant, is_winner, hero_id, hero_name, hero_icon,
            kills, deaths, assists, gpm, xpm, hero_damage, tower_damage, healing,
            last_hits, denies, level,
            radar_kda, radar_eco, radar_exp, radar_dmg, radar_push, radar_sustain)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        insert_rows,
    )
    await db.commit()

    payload = {
        "match_id": match_id,
        "radiant_win": radiant_win,
        "duration": data.get("duration", 0),
        "radiant_score": data.get("radiant_score", 0),
        "dire_score": data.get("dire_score", 0),
        "avg_mmr": data.get("avg_mmr"),
        "players": players_out,
    }
    # 写 redis (TTL 1天); 失败不影响主流程
    await cache_set_json(_match_redis_key(challenge_id), [payload], ttl=86400)
    return payload


async def _matches_from_db(db, challenge_id: str) -> list[dict]:
    """从 challenge_match_players 读已持久化的数据组装 payload。"""
    async with db.execute(
        "SELECT match_id, submitted_by, created_at FROM challenge_matches "
        "WHERE challenge_id = ? ORDER BY created_at ASC",
        (challenge_id,),
    ) as cursor:
        mrows = await cursor.fetchall()
    if not mrows:
        return []

    out = []
    for mr in mrows:
        mid = mr["match_id"]
        async with db.execute(
            "SELECT * FROM challenge_match_players WHERE challenge_id = ? AND match_id = ? "
            "ORDER BY is_radiant DESC, account_id ASC",
            (challenge_id, mid),
        ) as cursor:
            prows = await cursor.fetchall()
        players = []
        radiant_win = False
        for p in prows:
            is_radiant = bool(p["is_radiant"])
            is_winner = bool(p["is_winner"])
            # 第一条天辉玩家推断 radiant_win
            if is_radiant:
                radiant_win = is_winner if not radiant_win else radiant_win
            players.append({
                "account_id": p["account_id"],
                "openid": p["openid"],
                "player_name": p["player_name"],
                "hero_id": p["hero_id"],
                "hero_name": p["hero_name"],
                "hero_icon": p["hero_icon"],
                "is_radiant": is_radiant,
                "is_winner": is_winner,
                "is_participant": p["openid"] is not None,
                "kills": p["kills"], "deaths": p["deaths"], "assists": p["assists"],
                "gpm": p["gpm"], "xpm": p["xpm"],
                "hero_damage": p["hero_damage"], "tower_damage": p["tower_damage"],
                "healing": p["healing"],
                "last_hits": p["last_hits"], "denies": p["denies"], "level": p["level"],
                "radar": {
                    "kda": p["radar_kda"], "eco": p["radar_eco"], "exp": p["radar_exp"],
                    "dmg": p["radar_dmg"], "push": p["radar_push"], "sustain": p["radar_sustain"],
                },
            })
        # 重新正确推断 radiant_win: 任一天辉玩家 is_winner 即天辉胜
        any_radiant = next((p for p in players if p["is_radiant"]), None)
        if any_radiant:
            radiant_win = any_radiant["is_winner"]
        out.append({
            "match_id": mid,
            "radiant_win": radiant_win,
            "duration": mr["duration"] or 0,
            "radiant_score": mr["radiant_score"] or 0,
            "dire_score": mr["dire_score"] or 0,
            "avg_mmr": mr["avg_mmr"],
            "players": players,
            "created_at": mr["created_at"],
        })
    return out


@router.post("/{challenge_id}/match")
async def add_match(challenge_id: str, req: AddMatchRequest):
    """发起人录入比赛ID。覆盖语义: 每约战只保留一场，再次录入覆盖旧的。

    拉取数据 → 算雷达 → 持久化到 challenge_match_players → 写 redis 缓存。
    """
    db = await get_db()
    try:
        challenge = await _get_challenge_row(db, challenge_id)
        if not challenge:
            raise HTTPException(status_code=404, detail="约战不存在")
        if challenge["creator_openid"] != req.openid:
            raise HTTPException(status_code=403, detail="只有发起人可以录入比赛")
        await _fetch_and_persist_match(db, challenge_id, req.match_id, req.openid)
        return {"ok": True, "match_id": req.match_id}
    finally:
        await db.close()


@router.get("/{challenge_id}/matches")
async def list_matches(challenge_id: str):
    """列出约战挂的比赛。优先读 redis，未命中读 DB 持久化数据。"""
    db = await get_db()
    try:
        challenge = await _get_challenge_row(db, challenge_id)
        if not challenge:
            raise HTTPException(status_code=404, detail="约战不存在")
        participants = await _participants(db, challenge_id)

        # 1. 先查 redis
        cached = await cache_get_json(_match_redis_key(challenge_id))
        if cached is not None:
            return {"matches": cached, "participant_count": len(participants)}

        # 2. 读 DB 持久化数据
        matches = await _matches_from_db(db, challenge_id)
        if matches:
            await cache_set_json(_match_redis_key(challenge_id), matches, ttl=86400)
        return {"matches": matches, "participant_count": len(participants)}
    finally:
        await db.close()


@router.delete("/{challenge_id}/match/{match_id}")
async def remove_match(challenge_id: str, match_id: int, openid: str):
    """发起人删除挂的比赛（连同持久化的 player 数据 + redis 缓存）。"""
    db = await get_db()
    try:
        challenge = await _get_challenge_row(db, challenge_id)
        if not challenge:
            raise HTTPException(status_code=404, detail="约战不存在")
        if challenge["creator_openid"] != openid:
            raise HTTPException(status_code=403, detail="只有发起人可以删除比赛")
        cur = await db.execute(
            "DELETE FROM challenge_matches WHERE challenge_id = ? AND match_id = ?",
            (challenge_id, match_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="该比赛未挂到本约战")
        await db.execute(
            "DELETE FROM challenge_match_players WHERE challenge_id = ? AND match_id = ?",
            (challenge_id, match_id),
        )
        await db.commit()
        await cache_delete_json(_match_redis_key(challenge_id))
        return {"ok": True}
    finally:
        await db.close()
