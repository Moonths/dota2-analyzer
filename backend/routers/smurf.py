"""小号检测路由"""
from fastapi import APIRouter, HTTPException, Query
from database.db import DAILY_QUOTA_LIMIT, check_and_deduct_quota
from services.smurf_detector import detect_smurf

router = APIRouter(prefix="/api", tags=["smurf"])


@router.get("/smurf-check/{player_id}")
async def smurf_check(
    player_id: int,
    openid: str = Query(default="anonymous"),
):
    """检测玩家是否为小号/炸鱼账号"""
    # 检查每日配额
    if not await check_and_deduct_quota(openid, "analysis", DAILY_QUOTA_LIMIT):
        raise HTTPException(
            status_code=429,
            detail="今天 3 次分析机会已用完，明天再来！",
        )

    try:
        result = await detect_smurf(player_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"小号检测失败: {str(e)}",
        )
