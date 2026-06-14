from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import get_contact_activity_stats
from app.db import get_relationship_analysis
from app.db import get_stats as get_db_stats
from app.db import get_visualization_stats


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


@router.get("/stats/visualization")
async def get_visual_stats(
    chat_id: str | None = Query(None, description="按聊天 ID 过滤"),
    date_from: str | None = Query(None, description="起始日期（ISO 8601 或 epoch 秒）"),
    date_to: str | None = Query(None, description="结束日期（ISO 8601 或 epoch 秒）"),
    top_emoji: int = Query(20, ge=1, le=100, description="返回的 emoji 数量"),
    top_terms: int = Query(30, ge=1, le=200, description="返回的高频词数量"),
) -> dict[str, Any]:
    """获取可视化统计数据（热力图、时段分布、词频、emoji 等）"""
    filters: dict[str, Any] = {}
    if chat_id:
        filters["chat_id"] = chat_id
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to

    try:
        return await get_visualization_stats(
            filters=filters,
            top_emoji_limit=top_emoji,
            top_terms_limit=top_terms,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal server error") from exc


@router.get("/stats/contacts")
async def get_contact_stats(
    chat_id: str | None = Query(None, description="按聊天 ID 过滤"),
    date_from: str | None = Query(None, description="起始日期（ISO 8601 或 epoch 秒）"),
    date_to: str | None = Query(None, description="结束日期（ISO 8601 或 epoch 秒）"),
    top_contacts: int = Query(20, ge=1, le=100, description="返回的聊天活跃度排名数量"),
    top_senders: int = Query(20, ge=1, le=100, description="返回的发送者排名数量"),
) -> dict[str, Any]:
    """获取联系人 / 发送者活跃度对比数据（用于对比视图仪表板）

    返回聊天的消息量排名、发送/接收比例、首末消息时间、以及前若干个聊天的小时分布。
    """
    filters: dict[str, Any] = {}
    if chat_id:
        filters["chat_id"] = chat_id
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to

    try:
        return await get_contact_activity_stats(
            filters=filters,
            top_contacts_limit=top_contacts,
            top_senders_limit=top_senders,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal server error") from exc


@router.get("/stats/relationships")
async def get_relationships(
    chat_id: str | None = Query(None, description="按聊天 ID 过滤"),
    date_from: str | None = Query(None, description="起始日期（ISO 8601 或 epoch 秒）"),
    date_to: str | None = Query(None, description="结束日期（ISO 8601 或 epoch 秒）"),
    top_pairs: int = Query(20, ge=1, le=100, description="返回的关系对数量"),
    top_senders: int = Query(15, ge=1, le=100, description="参与图谱的发送者上限"),
) -> dict[str, Any]:
    """关系分析：基于共同聊天出现的发送者关系网络

    返回发送者两两关系对（强度排序）、图谱节点与边、群聊数量。
    用于前端"关系图谱"可视化。
    """
    filters: dict[str, Any] = {}
    if chat_id:
        filters["chat_id"] = chat_id
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to

    try:
        return await get_relationship_analysis(
            filters=filters,
            top_pairs_limit=top_pairs,
            top_senders_limit=top_senders,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal server error") from exc
