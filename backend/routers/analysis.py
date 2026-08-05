"""比赛分析相关路由"""
import json
import uuid
from fastapi import APIRouter, HTTPException
from models.schemas import AnalyzeRequest, AnalysisResult
from services.opendota import get_match
from services.analyzer import analyze_match
from database.db import get_db
from config import settings

router = APIRouter(prefix="/api", tags=["analysis"])


@router.post("/analyze")
async def analyze_match_endpoint(req: AnalyzeRequest):
    openid = req.openid or "anonymous"
    """分析一场比赛"""
    try:
        match_data = await get_match(req.match_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"无法获取比赛数据: {str(e)}")

    if not match_data.get("players"):
        raise HTTPException(status_code=404, detail="比赛数据为空或尚未解析")

    provider = req.provider or settings.default_ai_provider

    # 检查缓存
    db = await get_db()
    async with db.execute(
        "SELECT analysis_result FROM match_analyses WHERE match_id = ? AND provider = ? AND openid = ?",
        (req.match_id, provider, openid)
    ) as cursor:
        row = await cursor.fetchone()

    if row:
        result = json.loads(row["analysis_result"])
        await db.close()
        return result

    # 检查每日配额（缓存未命中才检查）
    from datetime import date
    today = date.today().isoformat()
    async with db.execute("SELECT count FROM daily_quota WHERE openid = ? AND date = ?", (openid, today)) as cursor:
        quota_row = await cursor.fetchone()
    if quota_row and quota_row["count"] >= 1:
        await db.close()
        raise HTTPException(status_code=429, detail="今天的新分析次数已用完，请明天再来！已分析过的比赛不受限制。")

    # 执行 AI 分析
    try:
        result = await analyze_match(match_data, provider=provider, model=req.model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI 分析失败: {str(e)}")

    # 生成分享 ID 并存储
    share_id = uuid.uuid4().hex[:12]
    result["share_id"] = share_id
    result["match_id"] = req.match_id
    result["provider"] = provider
    result["model"] = req.model or settings.default_ai_provider

    # 提取选手名和英雄名
    player_names = json.dumps([c["player_name"] for c in result.get("player_cards", [])])
    hero_names = json.dumps([c["hero_name"] for c in result.get("player_cards", [])])

    await db.execute(
        """INSERT INTO match_analyses (id, match_id, share_id, provider, model, raw_data, analysis_result, player_names, hero_names, skill_level, avg_mmr, radiant_win, duration, openid)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            f"{req.match_id}_{provider}",
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
        ),
    )

    # 更新每日配额
    await db.execute(
        "INSERT INTO daily_quota (openid, date, count) VALUES (?, ?, 1) ON CONFLICT(openid, date) DO UPDATE SET count = count + 1",
        (openid, today)
    )
    await db.commit()
    await db.close()

    result["share_url"] = f"{settings.share_base_url}/share/{share_id}"
    return result


@router.get("/providers")
async def list_providers():
    """返回可用的 AI 提供商列表"""
    providers = []
    if settings.openai_api_key:
        providers.append({"id": "openai", "name": "OpenAI", "models": ["gpt-4o", "gpt-4o-mini"]})
    if settings.deepseek_api_key:
        providers.append({"id": "deepseek", "name": "DeepSeek", "models": ["deepseek-chat"]})
    if settings.anthropic_api_key:
        providers.append({"id": "claude", "name": "Claude", "models": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022"]})
    return {"providers": providers}
