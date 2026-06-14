"""RAG（检索增强生成）流程。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ai.embeddings.base import EmbeddingProvider
from app.ai.providers.base import ChatMessage, ChatResponse, LLMProvider
from app.ai.vector_store import SearchHit, VectorStore


DEFAULT_TOP_K = 5
MAX_CONTEXT_CHARS = 4000  # 控制 LLM context 体积


@dataclass
class RagCitation:
    """RAG 答案的引用来源"""

    message_id: int
    chunk_text: str
    score: float
    chat_id: str
    timestamp: int
    chat_name: str = ""
    sender_name: str = ""


@dataclass
class RagAnswer:
    """RAG 完整响应"""

    answer: str
    citations: list[RagCitation] = field(default_factory=list)
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)


def _build_context_prompt(hits: list[SearchHit], max_chars: int = MAX_CONTEXT_CHARS) -> str:
    """将检索结果组装为 LLM 上下文文本"""
    lines: list[str] = []
    used = 0
    for idx, hit in enumerate(hits, start=1):
        meta = hit.metadata or {}
        chat_name = meta.get("chat_name") or hit.chat_id
        sender = meta.get("sender_name") or "Unknown"
        time_str = _format_timestamp(hit.timestamp)
        header = f"[{idx}] {sender} in {chat_name} ({time_str})"
        body = hit.chunk_text.strip()
        block = f"{header}\n{body}\n"
        if used + len(block) > max_chars:
            break
        lines.append(block)
        used += len(block)
    return "\n".join(lines)


def _format_timestamp(ts: int) -> str:
    from datetime import datetime
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OSError):
        return "unknown time"


def build_rag_messages(
    query: str,
    hits: list[SearchHit],
    *,
    history: list[ChatMessage] | None = None,
    system_prompt: str | None = None,
) -> list[ChatMessage]:
    """构造 RAG 聊天消息列表"""
    default_system = (
        "你是 LifeVault 的助手，根据用户提供的聊天记录片段回答问题。\n"
        "如果上下文中没有相关信息，请明确说明，不要编造内容。\n"
        "回答时可以引用 [N] 标记，对应给定的上下文片段编号。"
    )
    messages: list[ChatMessage] = [
        ChatMessage(role="system", content=system_prompt or default_system)
    ]

    if history:
        messages.extend(history)

    context = _build_context_prompt(hits)
    user_content = f"以下是相关的聊天记录片段：\n\n{context}\n\n用户问题：{query}"
    messages.append(ChatMessage(role="user", content=user_content))
    return messages


async def rag_query(
    *,
    llm: LLMProvider,
    embedding: EmbeddingProvider,
    store: VectorStore,
    query: str,
    top_k: int = DEFAULT_TOP_K,
    chat_id: str | None = None,
    history: list[ChatMessage] | None = None,
    temperature: float = 0.3,
) -> RagAnswer:
    """执行完整的 RAG 检索+生成流程"""
    query_vec_result = await embedding.embed_text(query)
    hits = await store.search(
        query_vec_result.vector,
        top_k=top_k,
        chat_id=chat_id,
    )

    messages = build_rag_messages(query, hits, history=history)
    response: ChatResponse = await llm.chat_completion(
        messages,
        temperature=temperature,
    )

    citations = [
        RagCitation(
            message_id=hit.message_id,
            chunk_text=hit.chunk_text,
            score=hit.score,
            chat_id=hit.chat_id,
            timestamp=hit.timestamp,
            chat_name=(hit.metadata or {}).get("chat_name", ""),
            sender_name=(hit.metadata or {}).get("sender_name", ""),
        )
        for hit in hits
    ]

    return RagAnswer(
        answer=response.content,
        citations=citations,
        model=response.model,
        usage=response.usage,
    )
