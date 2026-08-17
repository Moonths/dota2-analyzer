"""比赛分析相关路由"""
import json
import uuid

from fastapi import APIRouter, HTTPException, Query

from config import settings
from database.db import (
    DAILY_QUOTA_LIMIT,
    check_and_deduct_quota,
    get_cached_analysis_by_match,
    get_db,
    get_quota_usage,
)
from models.schemas import AnalyzeRequest
from services.analyzer import analyze_match
from services.cache import cache_get_json, cache_set_json
from services.opendota import get_match

router = APIRouter(prefix="/api", tags=["analysis"])

ANALYSIS_CACHE_TTL = 30 * 24 * 3600


def _analysis_cache_key(match_id: int) -> str:
    return f"dota2:analysis:{match_id}"


def _with_share_url(result: dict) -> dict:
    if result.get("share_id") and not result.get("share_url"):
        result["share_url"] = f"{settings.share_base_url}/share/{result['share_id']}"
    return result


@router.get("/quota")
async def get_quota(openid: str = Query(default="anonymous")):
    """返回当前用户今天剩余的共享分析额度。"""
    if settings.dev_mode:
        used = 0
    else:
        used = await get_quota_usage(openid)

    remaining = max(DAILY_QUOTA_LIMIT - used, 0)
    return {
        "limit": DAILY_QUOTA_LIMIT,
        "used": used,
        "remaining": remaining,
        # 保留旧字段，方便小程序过渡。
        "analysis_limit": DAILY_QUOTA_LIMIT,
        "analysis_remaining": remaining,
        "smurf_limit": DAILY_QUOTA_LIMIT,
        "smurf_remaining": remaining,
    }


@router.post("/analyze")
async def analyze_match_endpoint(req: AnalyzeRequest):
    openid = req.openid or "anonymous"
    cache_key = _analysis_cache_key(req.match_id)

    cached = await cache_get_json(cache_key)
    if cached:
        return _with_share_url(cached)

    db_cached = await get_cached_analysis_by_match(req.match_id)
    if db_cached:
        db_cached = _with_share_url(db_cached)
        await cache_set_json(cache_key, db_cached, ANALYSIS_CACHE_TTL)
        return db_cached

    try:
        match_data = await get_match(req.match_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"无法获取比赛数据: {str(e)}")

    if not match_data.get("players"):
        raise HTTPException(status_code=404, detail="比赛数据为空或尚未解析")

    provider = req.provider or settings.default_ai_provider

    if not await check_and_deduct_quota(openid, "analysis", DAILY_QUOTA_LIMIT):
        raise HTTPException(
            status_code=429,
            detail="今天 3 次分析机会已用完，明天再来！已分析过的比赛仍可直接查看。",
        )

    try:
        result = await analyze_match(match_data, provider=provider, model=req.model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 分析失败: {str(e)}")

    share_id = uuid.uuid4().hex[:12]
    result["share_id"] = share_id
    result["match_id"] = req.match_id
    result["provider"] = provider
    result["model"] = req.model or provider
    result["share_url"] = f"{settings.share_base_url}/share/{share_id}"

    player_names = json.dumps([c["player_name"] for c in result.get("player_cards", [])])
    hero_names = json.dumps([c["hero_name"] for c in result.get("player_cards", [])])

    db = await get_db()
    try:
        await db.execute(
            """INSERT INTO match_analyses
               (id, match_id, share_id, provider, model, raw_data,
                analysis_result, player_names, hero_names,
                skill_level, avg_mmr, radiant_win, duration, openid)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f"{req.match_id}_{provider}_{openid}",
                req.match_id,
                share_id,
                provider,
                result["model"],
                json.dumps(match_data, ensure_ascii=False),
                json.dumps(result, ensure_ascii=False),
                player_names,
                hero_names,
                result.get("skill_level", ""),
                result.get("avg_mmr"),
                result.get("radiant_win", False),
                result.get("duration", 0),
                openid,
            ),
        )
        await db.commit()
    finally:
        await db.close()

    await cache_set_json(cache_key, result, ANALYSIS_CACHE_TTL)
    return result


@router.get("/providers")
async def list_providers():
    providers = []
    if settings.openai_api_key:
        providers.append({"id": "openai", "name": "OpenAI", "models": ["gpt-4o", "gpt-4o-mini"]})
    if settings.deepseek_api_key:
        providers.append({"id": "deepseek", "name": "DeepSeek", "models": ["deepseek-chat"]})
    if settings.anthropic_api_key:
        providers.append({"id": "claude", "name": "Claude", "models": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022"]})
    return {"providers": providers}
