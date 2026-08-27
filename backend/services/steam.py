"""Steam 官方 Web API + OpenDota 档案聚合

绑定链路（方案A）:
1. 解析用户输入（SteamID64 / 自定义URL ID / 个人主页链接）→ steamid64
2. Steam 官方 GetPlayerSummaries 验证账号并取头像昵称
3. OpenDota 取段位 / MMR估算 / 近百场胜率 / 常玩位置（拿不到的字段为 None，不阻塞绑定）
"""
import re

import httpx

from config import settings
from services.opendota import get_player, get_player_matches

STEAM_API_BASE = "https://api.steampowered.com"
STEAM_ID_OFFSET = 76561197960265728

RANK_NAMES = {
    1: "先锋", 2: "卫士", 3: "中军", 4: "统帅",
    5: "传奇", 6: "万古流芳", 7: "超凡入圣", 8: "不朽",
}
POSITION_LABELS = {1: "1号位", 2: "2号位", 3: "3号位", 4: "4号位", 5: "5号位"}


def account_id_from_steam64(steamid64: str | int) -> int:
    return int(steamid64) - STEAM_ID_OFFSET


async def resolve_steam_id(raw: str) -> str:
    """把用户输入解析成 steamid64，失败抛 ValueError（中文提示）。"""
    s = (raw or "").strip()
    if not s:
        raise ValueError("请输入 Steam ID 或个人主页链接")

    # [U:1:accountid] 格式
    m = re.fullmatch(r"\[U:1:(\d+)\]", s)
    if m:
        return str(int(m.group(1)) + STEAM_ID_OFFSET)

    # 个人主页链接: .../profiles/7656119xxx 或 .../id/vanity
    m = re.search(r"steamcommunity\.com/(?:profiles/(\d{15,17})|id/([\w.\-]{2,64}))", s)
    if m:
        if m.group(1):
            return m.group(1)
        s = m.group(2)
    elif re.fullmatch(r"\d+", s):
        if len(s) == 17 and s.startswith("7656119"):
            return s
        # 短数字 → Dota2 游戏内数字 ID（好友码 / account_id），直接换算
        if len(s) <= 10:
            return str(int(s) + STEAM_ID_OFFSET)
        raise ValueError(
            "数字 ID 格式不对：游戏内数字 ID 是短号（10 位以内），"
            "SteamID64 是 7656119 开头的 17 位"
        )

    # 其余按自定义 URL ID 处理
    if re.fullmatch(r"[\w.\-]{2,64}", s):
        steamid = await _resolve_vanity(s)
        if not steamid:
            raise ValueError("找不到该 Steam 账号，请检查自定义 URL ID 是否正确")
        return steamid
    raise ValueError("无法识别的 Steam ID 格式")


async def _resolve_vanity(vanity: str) -> str | None:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{STEAM_API_BASE}/ISteamUser/ResolveVanityURL/v1/",
            params={"key": settings.steam_api_key, "vanityurl": vanity},
        )
        resp.raise_for_status()
        data = resp.json().get("response", {})
        if data.get("success") == 1 and data.get("steamid"):
            return data["steamid"]
    return None


async def get_steam_profile(steamid64: str) -> dict | None:
    """Steam 官方接口取玩家概要，账号不存在返回 None。"""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{STEAM_API_BASE}/ISteamUser/GetPlayerSummaries/v2/",
            params={"key": settings.steam_api_key, "steamids": steamid64},
        )
        if resp.status_code == 403:
            raise PermissionError("Steam API Key 无效")
        resp.raise_for_status()
        players = resp.json().get("response", {}).get("players", [])
    if not players:
        return None
    p = players[0]
    return {
        "steam_id64": p.get("steamid", steamid64),
        "steam_name": p.get("personaname", ""),
        "avatar": p.get("avatarfull") or p.get("avatarmedium") or p.get("avatar", ""),
        "profile_url": p.get("profileurl", ""),
    }


def rank_name(rank_tier) -> str | None:
    """rank_tier（如 42=统帅2星）→ 中文段位名。"""
    if not rank_tier:
        return None
    tier, star = divmod(int(rank_tier), 10)
    name = RANK_NAMES.get(tier)
    if not name:
        return None
    return name if tier >= 8 else f"{name}{star}"


async def build_dota_profile(account_id: int, match_limit: int = 100) -> dict:
    """OpenDota 聚合: 段位 / MMR估算 / 近百场胜率场次 / 常玩位置。

    任何一步失败都返回空数据而不是抛错 — 绑定不被游戏数据可用性阻塞。
    """
    profile = {
        "rank_tier": None, "rank_name": None, "mmr_estimate": None,
        "win_rate": None, "total_games": None,
        "main_position": None, "main_position_label": None,
    }
    try:
        p = await get_player(account_id)
    except Exception:
        p = {}
    profile["rank_tier"] = p.get("rank_tier")
    profile["rank_name"] = rank_name(p.get("rank_tier"))
    est = (p.get("mmr_estimate") or {}).get("estimate")
    profile["mmr_estimate"] = est

    try:
        matches = await get_player_matches(account_id, match_limit)
    except Exception:
        matches = []

    if matches:
        wins = sum(
            1 for m in matches
            if (m.get("player_slot", 0) < 128) == bool(m.get("radiant_win"))
        )
        profile["total_games"] = len(matches)
        profile["win_rate"] = round(wins / len(matches) * 100, 1)

    # 常玩位置: 近百场英雄主位出现频次最高者
    try:
        from services.position_detector import hero_primary
        counts: dict[int, int] = {}
        for m in matches:
            pos = hero_primary(m.get("hero_id"))
            if pos:
                counts[pos] = counts.get(pos, 0) + 1
        if counts:
            top = max(counts.items(), key=lambda kv: kv[1])[0]
            profile["main_position"] = top
            profile["main_position_label"] = POSITION_LABELS.get(top)
    except Exception:
        pass

    return profile
