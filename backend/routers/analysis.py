"""比赛分析相关路由"""
import json
import uuid

import httpx
from fastapi import APIRouter, HTTPException, Query

from config import settings
from database.db import (
    DAILY_QUOTA_LIMIT,
    check_and_deduct_quota,
    get_cached_analysis_by_match,
    get_db,
    get_quota_usage,
    save_match_analysis_cache,
)
from models.schemas import AnalyzeRequest
from services.analyzer import analyze_match
from services.cache import (
    CacheLockTimeout,
    cache_get_json,
    cache_set_json,
    resource_lock,
)
from services.opendota import get_match

router = APIRouter(prefix="/api", tags=["analysis"])

ANALYSIS_LOCK_TTL = 180
ANALYSIS_LOCK_WAIT_SECONDS = 90.0


def _analysis_cache_key(match_id: int) -> str:
    return f"dota2:analysis:{match_id}"


def _with_share_url(result: dict) -> dict:
    if result.get("share_id") and not result.get("share_url"):
        result["share_url"] = f"{settings.share_base_url}/share/{result['share_id']}"
    return result


def _mark_cached(result: dict, source: str) -> dict:
    out = dict(result)
    out["cached"] = True
    out["quota_deducted"] = False
    out["cache_source"] = source
    out["message"] = "已使用共享缓存，不消耗今日分析次数"
    return _with_share_url(out)


def _mark_fresh(result: dict) -> dict:
    out = dict(result)
    out["cached"] = False
    out["quota_deducted"] = not settings.dev_mode
    out["cache_source"] = "fresh"
    out["message"] = (
        "分析完成，本次已消耗 1 次今日机会"
        if not settings.dev_mode
        else "开发模式：本次分析未扣除额度"
    )
    return _with_share_url(out)


async def _load_cached_analysis(match_id: int) -> tuple[dict | None, str | None]:
    """按 Redis -> SQLite 顺序读取共享缓存。"""
    cache_key = _analysis_cache_key(match_id)
    redis_cached = await cache_get_json(cache_key)
    if redis_cached:
        return redis_cached, "redis"

    db_cached = await get_cached_analysis_by_match(match_id)
    if db_cached:
        await cache_set_json(cache_key, db_cached)
        return db_cached, "database"
    return None, None


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


@router.get("/analysis/{match_id}/cache")
async def get_cached_match_analysis(match_id: int):
    """只读查询已有比赛分析，不消耗额度。"""
    cached, source = await _load_cached_analysis(match_id)
    if not cached:
        raise HTTPException(status_code=404, detail="暂无该比赛的缓存分析")
    return _mark_cached(cached, source or "database")


@router.post("/analyze")
async def analyze_match_endpoint(req: AnalyzeRequest):
    openid = req.openid or "anonymous"
    cache_key = _analysis_cache_key(req.match_id)

    cached, source = await _load_cached_analysis(req.match_id)
    if cached:
        return _mark_cached(cached, source or "database")

    try:
        async with resource_lock(
            f"analysis:{req.match_id}",
            ttl=ANALYSIS_LOCK_TTL,
            wait_timeout=ANALYSIS_LOCK_WAIT_SECONDS,
        ):
            # 拿到锁后必须再查一次，避免两个请求同时通过首轮缓存检查。
            cached, source = await _load_cached_analysis(req.match_id)
            if cached:
                return _mark_cached(cached, source or "database")

            try:
                match_data = await get_match(req.match_id)
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status in (502, 503, 504, 520, 521, 522, 523, 524, 525):
                    raise HTTPException(
                        status_code=502,
                        detail="OpenDota 暂时不可用，请稍后再试",
                    )
                if status == 404:
                    raise HTTPException(
                        status_code=404,
                        detail="比赛不存在或 OpenDota 尚未收录",
                    )
                if status == 429:
                    raise HTTPException(
                        status_code=503,
                        detail="OpenDota 请求过于频繁，请稍后再试",
                    )
                raise HTTPException(status_code=500, detail=f"无法获取比赛数据: {str(e)}")
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
            analysis_result_json = json.dumps(result, ensure_ascii=False)
            raw_data_json = json.dumps(match_data, ensure_ascii=False)

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
                        raw_data_json,
                        analysis_result_json,
                        player_names,
                        hero_names,
                        result.get("skill_level", ""),
                        result.get("avg_mmr"),
                        result.get("radiant_win", False),
                        result.get("duration", 0),
                        openid,
                    ),
                )
                await save_match_analysis_cache(
                    db,
                    match_id=req.match_id,
                    share_id=share_id,
                    provider=provider,
                    model=result["model"],
                    raw_data=raw_data_json,
                    analysis_result=analysis_result_json,
                    player_names=player_names,
                    hero_names=hero_names,
                    skill_level=result.get("skill_level", ""),
                    avg_mmr=result.get("avg_mmr"),
                    radiant_win=result.get("radiant_win", False),
                    duration=result.get("duration", 0),
                    openid=openid,
                )
                await db.commit()
            finally:
                await db.close()

            # 比赛分析结果永久缓存，不设置 Redis TTL。
            await cache_set_json(cache_key, result)
            return _mark_fresh(result)
    except CacheLockTimeout:
        cached, source = await _load_cached_analysis(req.match_id)
        if cached:
            return _mark_cached(cached, source or "database")
        raise HTTPException(
            status_code=503,
            detail="该比赛正在被其他用户分析，请稍后再试",
        )


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
