from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db import get_stats as get_db_stats


router = APIRouter(prefix="/api", tags=["stats"])


class TopChat(BaseModel):
    """热门聊天"""
    chat_id: str
    chat_name: str = ""
    message_count: int = Field(ge=0)


class StatsResponse(BaseModel):
    """统计信息响应"""
    total_messages: int = Field(ge=0)
    sources: dict[str, int]
    earliest_message: int | None = None
    latest_message: int | None = None
    chat_count: int = Field(ge=0)
    top_chats: list[TopChat]


@router.get("/stats", response_model=StatsResponse)
async def get_stats() -> dict[str, Any]:
    """获取统计信息"""
    try:
        return await get_db_stats()
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal server error") from exc
