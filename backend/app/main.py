from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import get_db_path, init_database
from app.routers import export, import_router, messages, search, stats


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期管理：启动时初始化数据库"""
    db_path = await get_db_path()
    await init_database(db_path)
    yield


app = FastAPI(title="LifeVault API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(messages.router)
app.include_router(search.router)
app.include_router(stats.router)
app.include_router(export.router)
app.include_router(import_router.router)


@app.get("/health")
async def health() -> dict[str, str]:
    """健康检查接口"""
    return {"status": "ok"}
