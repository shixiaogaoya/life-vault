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
import httpx

from app.ai import (
    AIDisabledError,
    AIProviderNotConfiguredError,
    apply_config,
    embedding_provider_factory,
    get_config,
    get_status,
    llm_provider_factory,
    reset_config,
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


# ===== 运行时配置（UI 直接填写 URL / API Key，无需环境变量或重启） =====


class AIConfigUpdate(BaseModel):
    """用户从 UI 提交的配置更新。

    所有字段可选：只传需要修改的字段。
    api_key 传空串 = 清除；传非空串 = 更新。
    其他字段传空串 = 保留原值。
    """

    llm_provider: str | None = Field(None, description="disabled/openai/anthropic/ollama")
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    embedding_provider: str | None = Field(
        None, description="disabled/openai/ollama/local"
    )
    embedding_model: str | None = None
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None


@router.get("/config")
async def get_ai_config() -> dict[str, Any]:
    """获取当前 AI 配置（脱敏：API Key 仅返回是否已设置）。

    前端用此接口回填表单（provider / model / base_url），并在 UI 上
    提示「API Key 已设置 / 未设置」。
    """
    cfg = get_config()
    return cfg.to_public_dict()


@router.put("/config")
async def update_ai_config(update: AIConfigUpdate) -> dict[str, Any]:
    """更新 AI 配置（写入文件 + 热加载，无需重启）。

    隐私：API Key 仅保存在本地配置文件，不上传任何服务器。
    保存后立即清缓存，后续请求使用新配置。
    """
    # 过滤掉 None（pydantic 已保证字段存在，但显式过滤更安全）
    updates = {k: v for k, v in update.model_dump().items() if v is not None}

    # 校验 provider 合法性（给出清晰错误而非静默回退）
    if "llm_provider" in updates:
        from app.ai.config import SUPPORTED_LLM_PROVIDERS

        if updates["llm_provider"] not in SUPPORTED_LLM_PROVIDERS:
            raise HTTPException(
                status_code=400,
                detail=f"unsupported llm_provider: {updates['llm_provider']}, "
                f"expected one of {list(SUPPORTED_LLM_PROVIDERS)}",
            )
    if "embedding_provider" in updates:
        from app.ai.config import SUPPORTED_EMBEDDING_PROVIDERS

        if updates["embedding_provider"] not in SUPPORTED_EMBEDDING_PROVIDERS:
            raise HTTPException(
                status_code=400,
                detail=f"unsupported embedding_provider: {updates['embedding_provider']}, "
                f"expected one of {list(SUPPORTED_EMBEDDING_PROVIDERS)}",
            )

    new_cfg = apply_config(updates)
    return new_cfg.to_public_dict()


@router.delete("/config")
async def delete_ai_config() -> dict[str, Any]:
    """清除运行时配置文件，恢复到环境变量 / 默认值。"""
    new_cfg = reset_config()
    return new_cfg.to_public_dict()


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


# ===== 连接测试与模型拉取（配置前验证 base_url + api_key 是否可用） =====


class AITestRequest(BaseModel):
    """测试连接请求：用用户填写的 base_url + api_key 验证可用性并拉取模型列表。

    不依赖已保存的配置 —— 用户在表单里填完还没点保存时就能测试。
    """

    base_url: str = Field(..., description="API base URL，如 https://api.deepseek.com/v1")
    api_key: str = Field("", description="API Key（Ollama 不需要）")
    provider: str = Field("openai", description="openai / ollama")
    kind: str = Field("llm", description="llm（测聊天）/ embedding（测向量）")


class AITestResponse(BaseModel):
    """连接测试结果"""

    ok: bool
    models: list[str] = Field(default_factory=list, description="可用模型列表")
    latency_ms: int = 0
    error: str = ""


@router.post("/test", response_model=AITestResponse)
async def test_ai_connection(req: AITestRequest) -> AITestResponse:
    """测试 AI 连接：拉取模型列表 + （LLM）发最小 chat 请求验证。

    流程：
    1. GET {base_url}/models 拉取可用模型（OpenAI 兼容协议标准端点）
    2. 若 kind=llm，额外 POST /chat/completions 发 "hi" 验证模型可对话
    3. 返回模型列表 + 延迟 + 错误信息（若有）

    隐私：此端点仅用请求体里的临时凭据测试，不读取/写入任何配置文件。
    """
    import time

    base_url = req.base_url.rstrip("/")
    if not base_url:
        return AITestResponse(ok=False, error="base_url is required")

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if req.api_key:
        headers["Authorization"] = f"Bearer {req.api_key}"

    # Ollama 的 /api/models 端点返回格式不同（{ models: [{name}, ...] }），
    # 但 Ollama 也兼容 OpenAI 的 /v1/models（返回 { data: [{id}, ...] }）。
    # 这里统一走 OpenAI 兼容协议，要求 base_url 已含 /v1 后缀。
    timeout = httpx.Timeout(15.0, connect=10.0)

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=timeout) as client:
            # 1. 拉取模型列表
            try:
                resp = await client.get("/models")
                if resp.status_code >= 400:
                    return AITestResponse(
                        ok=False,
                        error=f"/models returned {resp.status_code}: {resp.text[:200]}",
                        latency_ms=int((time.monotonic() - start) * 1000),
                    )
                models_data = resp.json()
                # OpenAI 格式: { data: [{ id: "gpt-4o-mini" }, ...] }
                # Ollama 格式: { models: [{ name: "llama3.2:latest" }, ...] }
                models: list[str] = []
                if isinstance(models_data.get("data"), list):
                    for item in models_data["data"]:
                        model_id = item.get("id") or item.get("name", "")
                        if model_id:
                            models.append(model_id)
                elif isinstance(models_data.get("models"), list):
                    for item in models_data["models"]:
                        model_id = item.get("name") or item.get("id", "")
                        if model_id:
                            models.append(model_id)
                models.sort()
            except httpx.HTTPError as exc:
                return AITestResponse(
                    ok=False,
                    error=f"Failed to reach {base_url}/models: {exc}",
                    latency_ms=int((time.monotonic() - start) * 1000),
                )

            # 2. LLM 额外验证：发最小 chat 请求
            if req.kind == "llm" and models:
                test_model = models[0]
                try:
                    chat_resp = await client.post(
                        "/chat/completions",
                        json={
                            "model": test_model,
                            "messages": [{"role": "user", "content": "hi"}],
                            "max_tokens": 5,
                        },
                    )
                    if chat_resp.status_code >= 400:
                        return AITestResponse(
                            ok=False,
                            models=models,
                            error=f"/chat/completions returned {chat_resp.status_code}: {chat_resp.text[:200]}",
                            latency_ms=int((time.monotonic() - start) * 1000),
                        )
                except httpx.HTTPError as exc:
                    return AITestResponse(
                        ok=False,
                        models=models,
                        error=f"Chat test failed: {exc}",
                        latency_ms=int((time.monotonic() - start) * 1000),
                    )

            latency = int((time.monotonic() - start) * 1000)
            return AITestResponse(ok=True, models=models, latency_ms=latency)

    except Exception as exc:
        return AITestResponse(
            ok=False,
            error=f"Unexpected error: {exc}",
            latency_ms=int((time.monotonic() - start) * 1000),
        )

