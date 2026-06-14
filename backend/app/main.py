from contextlib import asynccontextmanager
import os
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import get_db_path, init_database
from app.routers import ai, export, import_router, messages, search, stats


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期管理：启动时初始化数据库"""
    db_path = await get_db_path()
    await init_database(db_path)
    yield


app = FastAPI(title="LifeVault API", version="0.2.0", lifespan=lifespan)


def _cors_origins() -> list[str]:
    origins = os.getenv("LIFEVAULT_CORS_ORIGINS", "http://localhost:3000")
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(messages.router)
app.include_router(search.router)
app.include_router(stats.router)
app.include_router(export.router)
app.include_router(import_router.router)
app.include_router(ai.router)


@app.get("/health")
async def health() -> dict[str, str]:
    """健康检查接口"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("LIFEVAULT_HOST", "127.0.0.1"),
        port=int(os.getenv("LIFEVAULT_PORT", "8000")),
        reload=os.getenv("LIFEVAULT_RELOAD", "0") == "1",
    )
