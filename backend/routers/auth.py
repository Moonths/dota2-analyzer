from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
from config import settings

router = APIRouter(prefix="/api", tags=["auth"])

class LoginRequest(BaseModel):
    code: str

@router.post("/login")
async def wechat_login(req: LoginRequest):
    if not settings.wechat_appid or not settings.wechat_secret:
        raise HTTPException(status_code=500, detail="微信配置未设置")
    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": settings.wechat_appid,
        "secret": settings.wechat_secret,
        "js_code": req.code,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        data = resp.json()
    if "errcode" in data and data["errcode"] != 0:
        raise HTTPException(status_code=400, detail=f"微信登录失败: {data.get('errmsg','')}")
    return {"openid": data["openid"]}
