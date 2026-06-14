"""AI 路由：RAG 聊天、智能摘要、向量索引管理。

隐私设计：
- 所有端点在 AI 禁用时返回 503
- 状态接口明确告知 provider 与数据流向（local/remote）
- 索引任务在后台运行，避免阻塞请求
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.ai import (
    AIDisabledError,
    AIProviderNotConfiguredError,
    embedding_provider_factory,
    get_status,
    llm_provider_factory,
)
from app.ai.indexer import IndexProgress, build_index, get_vector_store
from app.ai.rag import rag_query
from app.ai.summarizer import summarize
from app.db import get_db_path


router = APIRouter(prefix="/api/ai", tags=["ai"])


# ===== 索引任务状态（进程内单例） =====


@dataclass
class _IndexTaskState:
    """索引任务的进程内状态"""

    task: asyncio.Task | None = None
    progress: IndexProgress = field(default_factory=IndexProgress)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


_index_state = _IndexTaskState()


# ===== 请求/响应模型 =====


class ChatRequest(BaseModel):
    """RAG 聊天请求"""

    query: str = Field(..., min_length=1, max_length=2000)
    chat_id: str | None = Field(None, description="限定检索范围到指定聊天")
    top_k: int = Field(5, ge=1, le=20)
    history: list[dict[str, str]] = Field(
        default_factory=list,
        description="历史对话，例如 [{'role': 'user', 'content': '...'}, {'role': 'assistant', 'content': '...'}]",
    )


class CitationOut(BaseModel):
    message_id: int
    chunk_text: str
    score: float
    chat_id: str
    timestamp: int
    chat_name: str = ""
    sender_name: str = ""


class ChatResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
    model: str = ""
    usage: dict[str, int] = {}


class SummaryRequest(BaseModel):
    period: str = Field(..., description="day / week / month")
    chat_id: str | None = None


class SummaryResponse(BaseModel):
    summary: str
    period: str
    chat_id: str | None
    message_count: int
    chunks_processed: int
    model: str = ""


class IndexStartResponse(BaseModel):
    started: bool
    message: str = ""


class IndexStatusResponse(BaseModel):
    status: str
    total: int
    processed: int
    failed: int
    started_at: str = ""
    finished_at: str = ""
    error: str = ""


# ===== Helper =====


def _ensure_llm_enabled():
    """检查 LLM 是否启用，未启用则抛 503"""
    try:
        llm_provider_factory()
    except AIDisabledError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"AI module disabled: {exc}",
        ) from exc
    except AIProviderNotConfiguredError as exc:
        raise HTTPException(
            status_code=509,
            detail=f"AI provider not configured: {exc}",
        ) from exc


def _ensure_embedding_enabled():
    try:
        embedding_provider_factory()
    except AIDisabledError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Embedding module disabled: {exc}",
        ) from exc
    except AIProviderNotConfiguredError as exc:
        raise HTTPException(
            status_code=509,
            detail=f"Embedding provider not configured: {exc}",
        ) from exc


def _validate_history(history: list[dict[str, str]]) -> list:
    from app.ai.providers.base import ChatMessage

    valid_roles = {"system", "user", "assistant"}
    messages: list[ChatMessage] = []
    for item in history:
        role = item.get("role")
        content = item.get("content", "")
        if role not in valid_roles:
            raise HTTPException(
                status_code=400,
                detail=f"invalid history role: {role}, expected one of {valid_roles}",
            )
        messages.append(ChatMessage(role=role, content=content))
    return messages


# ===== 端点 =====


@router.get("/status")
async def ai_status() -> dict[str, Any]:
    """获取 AI 模块状态（不包含敏感信息）"""
    status = get_status()
    # 附加索引任务进度
    status["index_progress"] = _index_state.progress.to_dict()
    return status


@router.post("/chat", response_model=ChatResponse)
async def ai_chat(request: ChatRequest) -> ChatResponse:
    """RAG 聊天接口"""
    _ensure_llm_enabled()
    _ensure_embedding_enabled()

    history = _validate_history(request.history)

    llm = None
    embedding = None
    try:
        llm = llm_provider_factory()
        embedding = embedding_provider_factory()
        store = get_vector_store(embedding.dimensions)
        await store.init_schema()

        answer = await rag_query(
            llm=llm,
            embedding=embedding,
            store=store,
            query=request.query,
            top_k=request.top_k,
            chat_id=request.chat_id,
            history=history,
        )
    except AIDisabledError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIProviderNotConfiguredError as exc:
        raise HTTPException(status_code=509, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"AI chat failed: {exc}"
        ) from exc
    finally:
        # provider 内部 httpx client 由调用方关闭
        # 注意：llm/embedding 可能因前面抛异常而未赋值，需 None-check
        for provider in (llm, embedding):
            if provider is not None:
                try:
                    await provider.close()
                except Exception:
                    pass

    return ChatResponse(
        answer=answer.answer,
        citations=[
            CitationOut(
                message_id=c.message_id,
                chunk_text=c.chunk_text,
                score=c.score,
                chat_id=c.chat_id,
                timestamp=c.timestamp,
                chat_name=c.chat_name,
                sender_name=c.sender_name,
            )
            for c in answer.citations
        ],
        model=answer.model,
        usage=answer.usage,
    )


@router.post("/summary", response_model=SummaryResponse)
async def ai_summary(request: SummaryRequest) -> SummaryResponse:
    """智能摘要接口"""
    _ensure_llm_enabled()

    if request.period not in ("day", "week", "month"):
        raise HTTPException(
            status_code=400,
            detail=f"invalid period: {request.period}, expected day/week/month",
        )

    llm = None
    try:
        llm = llm_provider_factory()
        messages_db_path = await get_db_path()
        result = await summarize(
            llm=llm,
            messages_db_path=messages_db_path,
            period=request.period,
            chat_id=request.chat_id,
        )
    except AIDisabledError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIProviderNotConfiguredError as exc:
        raise HTTPException(status_code=509, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"AI summary failed: {exc}"
        ) from exc
    finally:
        if llm is not None:
            try:
                await llm.close()
            except Exception:
                pass

    return SummaryResponse(
        summary=result.summary,
        period=result.period,
        chat_id=result.chat_id,
        message_count=result.message_count,
        chunks_processed=result.chunks_processed,
        model=result.model,
    )


@router.post("/index", response_model=IndexStartResponse)
async def ai_index_start() -> IndexStartResponse:
    """触发向量索引构建（异步后台任务）"""
    _ensure_embedding_enabled()

    async with _index_state.lock:
        if (
            _index_state.task is not None
            and not _index_state.task.done()
        ):
            return IndexStartResponse(
                started=False,
                message="an index task is already running",
            )

        # 初始化新的进度对象
        _index_state.progress = IndexProgress(status="pending")

        try:
            embedding = embedding_provider_factory()
        except (AIDisabledError, AIProviderNotConfiguredError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        messages_db_path = await get_db_path()
        vectors_db_path = os.path.expanduser(
            os.getenv("LIFEVAULT_VECTOR_DB_PATH", "~/.lifevault/vectors.db")
        )

        async def _run():
            try:
                await build_index(
                    embedding_provider=embedding,
                    messages_db_path=messages_db_path,
                    vectors_db_path=vectors_db_path,
                    progress=_index_state.progress,
                )
            finally:
                try:
                    await embedding.close()
                except Exception:
                    pass

        _index_state.task = asyncio.create_task(_run())

    return IndexStartResponse(started=True, message="index task started")


@router.get("/index/status", response_model=IndexStatusResponse)
async def ai_index_status() -> IndexStatusResponse:
    """查询索引构建进度"""
    p = _index_state.progress
    return IndexStatusResponse(
        status=p.status,
        total=p.total,
        processed=p.processed,
        failed=p.failed,
        started_at=p.started_at,
        finished_at=p.finished_at,
        error=p.error,
    )
