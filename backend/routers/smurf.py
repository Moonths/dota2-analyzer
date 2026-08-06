"""小号检测路由"""
from fastapi import APIRouter, HTTPException, Query
from services.smurf_detector import detect_smurf
from database.db import check_and_deduct_quota

router = APIRouter(prefix="/api", tags=["smurf"])


@router.get("/smurf-check/{player_id}")
async def smurf_check(
    player_id: int,
    openid: str = Query(default="anonymous"),
):
    """检测玩家是否为小号/炸鱼账号"""
    # 检查每日配额
    if not await check_and_deduct_quota(openid, "smurf"):
        raise HTTPException(
            status_code=429,
            detail="今天的捕鱼执法次数已用完，请明天再来！",
        )

    try:
        result = await detect_smurf(player_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"小号检测失败: {str(e)}",
        )
