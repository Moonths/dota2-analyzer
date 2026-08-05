"""比赛相关路由"""
from fastapi import APIRouter, HTTPException
from services.opendota import get_player, get_player_matches, get_match, get_heroes
from services.hero_cn import cn_name

router = APIRouter(prefix="/api", tags=["matches"])


@router.get("/players/{player_id}")
async def get_player_info(player_id: int):
    """获取玩家档案"""
    try:
        profile = await get_player(player_id)
        return {"profile": profile}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"无法获取玩家信息: {str(e)}")


@router.get("/players/{player_id}/matches")
async def get_player_recent_matches(player_id: int, limit: int = 20):
    """获取玩家最近比赛"""
    try:
        matches = await get_player_matches(player_id, limit)
        heroes = await get_heroes()

        result = []
        for m in matches:
            hero_id = m.get("hero_id", 0)
            hero = heroes.get(hero_id, {})
            en_name = hero.get("localized_name", "")
            result.append({
                "match_id": m.get("match_id"),
                "hero_name": cn_name(en_name) or f"Hero_{hero_id}",
                "hero_icon": f"/hero-img/{hero.get('name', 'unknown').replace('npc_dota_hero_', '')}.png",
                "kills": m.get("kills", 0),
                "deaths": m.get("deaths", 0),
                "assists": m.get("assists", 0),
                "is_win": m.get("radiant_win") if not (m.get("player_slot", 0) & 128) else not m.get("radiant_win"),
                "duration": m.get("duration", 0),
                "start_time": m.get("start_time", 0),
                "skill": m.get("skill"),
            })

        profile = await get_player(player_id)
        return {
            "player_name": profile.get("profile", {}).get("personaname", str(player_id)),
            "matches": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取比赛列表失败: {str(e)}")


@router.get("/matches/{match_id}")
async def get_match_info(match_id: int):
    """获取比赛基本信息 (不包含AI分析)"""
    try:
        data = await get_match(match_id)
        heroes = await get_heroes()

        players = []
        for p in data.get("players", []):
            hero = heroes.get(p.get("hero_id"), {})
            en_name = hero.get("localized_name", "")
            players.append({
                "player_name": p.get("personaname", str(p.get("account_id", "Unknown"))),
                "hero_name": cn_name(en_name) or f"Hero_{p.get('hero_id')}",
                "hero_icon": f"/hero-img/{hero.get('name', 'unknown').replace('npc_dota_hero_', '')}.png",
                "kills": p.get("kills", 0),
                "deaths": p.get("deaths", 0),
                "assists": p.get("assists", 0),
                "gpm": p.get("gold_per_min", 0),
                "xpm": p.get("xp_per_min", 0),
                "is_winner": p.get("isRadiant") == data.get("radiant_win"),
            })

        return {
            "match_id": match_id,
            "radiant_win": data.get("radiant_win"),
            "duration": data.get("duration", 0),
            "skill": data.get("skill"),
            "avg_mmr": data.get("avg_mmr"),
            "radiant_score": data.get("radiant_score", 0),
            "dire_score": data.get("dire_score", 0),
            "players": players,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取比赛信息失败: {str(e)}")
from services.position_detector import detect_positions
