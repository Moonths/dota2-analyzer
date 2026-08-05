"""OpenDota API 客户端"""
import asyncio
import httpx
from typing import Optional

BASE_URL = "https://api.opendota.com/api"
HEADERS = {
    "User-Agent": "Dota2Analyzer/1.0 (contact@example.com)",
    "Accept": "application/json",
}


async def _request(url: str, params: dict = None, retries: int = 1) -> dict | list:
    """带重试的请求（仅对临时性错误重试）"""
    last_err = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, params=params, headers=HEADERS)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            # 429 限流或 5xx 服务端错误 → 重试；522/523/524 Cloudflare → 不重试
            if status == 429 or (500 <= status < 522):
                last_err = e
                if attempt < retries:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
            raise
        except (httpx.ConnectError, httpx.ReadError) as e:
            last_err = e
            if attempt < retries:
                await asyncio.sleep(2 * (attempt + 1))
                continue
            raise
    raise last_err


async def get_match(match_id: int) -> dict:
    """获取单场比赛完整数据"""
    return await _request(f"{BASE_URL}/matches/{match_id}")


async def get_player(player_id: int) -> dict:
    """获取玩家档案"""
    return await _request(f"{BASE_URL}/players/{player_id}")


async def get_player_matches(player_id: int, limit: int = 20) -> list[dict]:
    """获取玩家最近比赛列表"""
    return await _request(f"{BASE_URL}/players/{player_id}/matches", {"limit": limit})


async def get_heroes() -> dict[int, dict]:
    """获取英雄列表 {id: {name, localized_name, ...}}"""
    heroes = await _request(f"{BASE_URL}/heroes")
    return {h["id"]: h for h in heroes}


async def get_benchmarks(hero_id: int) -> Optional[dict]:
    """获取指定英雄在各分段的基准数据"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BASE_URL}/benchmarks",
            params={"hero_id": hero_id},
            headers=HEADERS,
        )
        if resp.status_code == 200:
            return resp.json()
        return None


def parse_match_overview(data: dict) -> dict:
    """从比赛原始数据中提取关键概览"""
    players = data.get("players", [])
    radiant_win = data.get("radiant_win", False)
    duration = data.get("duration", 0)
    skill = data.get("skill")
    avg_mmr = data.get("avg_mmr")

    return {
        "match_id": data.get("match_id"),
        "radiant_win": radiant_win,
        "duration": duration,
        "skill": skill,
        "avg_mmr": avg_mmr,
        "radiant_score": data.get("radiant_score", 0),
        "dire_score": data.get("dire_score", 0),
        "radiant_team": data.get("radiant_team", {}).get("name", "Radiant"),
        "dire_team": data.get("dire_team", {}).get("name", "Dire"),
    }
