from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.db import count_search_messages, search_messages as search_db_messages
from app.models.message import UnifiedMessage
from app.routers.messages import _type_name


router = APIRouter(prefix="/api", tags=["search"])


class SearchResultItem(BaseModel):
    """搜索结果项"""
    id: int
    timestamp: int
    chat_name: str = ""
    sender_name: str = ""
    content: str = ""
    snippet: str
    type_name: str


class SearchResponse(BaseModel):
    """搜索响应"""
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=10, le=200)
    query: str = Field(min_length=1)
    results: list[SearchResultItem]


@router.get("/search", response_model=SearchResponse)
async def search_messages(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=200),
) -> SearchResponse:
    """全文检索消息"""
    try:
        total = await count_search_messages(q)
        messages = await search_db_messages(q, page=page, page_size=page_size)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="internal server error") from exc

    return SearchResponse(
        total=total,
        page=page,
        page_size=page_size,
        query=q,
        results=[_to_search_result(message, q) for message in messages],
    )


def _to_search_result(message: UnifiedMessage, query: str) -> SearchResultItem:
    """将 UnifiedMessage 转换为搜索结果项"""
    return SearchResultItem(
        id=message.id,
        timestamp=message.timestamp,
        chat_name=message.chat_name,
        sender_name=message.sender_name,
        content=message.content,
        snippet=_build_snippet(message.content, query),
        type_name=_type_name(message.msg_type, message.sub_type),
    )


def _build_snippet(content: str, query: str, radius: int = 40) -> str:
    """生成搜索摘要（高亮关键词周围文本）"""
    if not content:
        return ""

    first_term = next((term for term in query.split() if term), "")
    if not first_term:
        return content[: radius * 2]

    index = content.lower().find(first_term.lower())
    if index < 0:
        return content[: radius * 2]

    start = max(0, index - radius)
    end = min(len(content), index + len(first_term) + radius)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(content) else ""
    return f"{prefix}{content[start:end]}{suffix}"
