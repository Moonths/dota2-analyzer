from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import httpx

router = APIRouter(prefix="/api", tags=["proxy"])

@router.get("/hero-img/{hero_name}")
async def proxy_hero_image(hero_name: str):
    url = f"https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/{hero_name}.png"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        return StreamingResponse(
            resp.aiter_bytes(),
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=86400"},
        )
