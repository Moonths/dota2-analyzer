"""小号检测路由"""
from fastapi import APIRouter, HTTPException, Query
from config import settings
from database.db import DAILY_QUOTA_LIMIT, check_and_deduct_quota
from services.cache import CacheLockTimeout, resource_lock
from services.smurf_detector import detect_smurf, get_cached_smurf_result

router = APIRouter(prefix="/api", tags=["smurf"])


@router.get("/smurf-check/{player_id}/cache")
async def get_cached_smurf(player_id: int):
    """只读查询小号检测缓存，不消耗额度。"""
    cached = await get_cached_smurf_result(player_id)
    if not cached:
        raise HTTPException(status_code=404, detail="暂无该玩家的小号检测缓存")
    return cached


@router.get("/smurf-check/{player_id}")
async def smurf_check(
    player_id: int,
    openid: str = Query(default="anonymous"),
):
    """检测玩家是否为小号/炸鱼账号"""
    cached = await get_cached_smurf_result(player_id)
    if cached:
        return cached

    try:
        async with resource_lock(f"smurf:{player_id}"):
            cached = await get_cached_smurf_result(player_id)
            if cached:
                return cached

            if not await check_and_deduct_quota(openid, "analysis", DAILY_QUOTA_LIMIT):
                raise HTTPException(
                    status_code=429,
                    detail="今天 3 次分析机会已用完，明天再来！",
                )

            try:
                result = await detect_smurf(player_id)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"小号检测失败: {str(e)}",
                )

            result["cached"] = False
            result["quota_deducted"] = not settings.dev_mode
            result["cache_source"] = "fresh"
            result["message"] = (
                "检测完成，本次已消耗 1 次今日机会"
                if not settings.dev_mode
                else "开发模式：本次检测未扣除额度"
            )
            return result
    except CacheLockTimeout:
        cached = await get_cached_smurf_result(player_id)
        if cached:
            return cached
        raise HTTPException(
            status_code=503,
            detail="该玩家的小号检测正在执行中，请稍后再试",
        )
