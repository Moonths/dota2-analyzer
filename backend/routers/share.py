"""分享功能路由"""
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from database.db import get_db

router = APIRouter(tags=["share"])


@router.get("/api/share/{share_id}")
async def get_shared_analysis(share_id: str):
    """通过分享ID获取已缓存的分析结果"""
    db = await get_db()
    async with db.execute(
        "SELECT analysis_result FROM match_analyses WHERE share_id = ?",
        (share_id,)
    ) as cursor:
        row = await cursor.fetchone()
    await db.close()

    if not row:
        raise HTTPException(status_code=404, detail="分享不存在或已过期")

    return json.loads(row["analysis_result"])
