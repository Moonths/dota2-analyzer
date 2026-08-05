"""Dota 2 AI 比赛分析 - FastAPI 主入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database.db import init_db
from routers import matches, analysis, share


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Dota 2 AI Analyzer",
    description="Dota 2 比赛 AI 赛后复盘分析",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(matches.router)
app.include_router(analysis.router)
app.include_router(share.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "dota2-analyzer"}
