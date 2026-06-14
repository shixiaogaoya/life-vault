"""智能摘要：按时间范围聚合消息 → 分块 → LLM 摘要。"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

import aiosqlite

from app.ai.providers.base import ChatMessage, LLMProvider


MAX_CHUNK_CHARS = 3000  # 每块约 1000 tokens（粗略估算）
MAX_TOTAL_CHARS = 24000  # 总消息文本上限（避免超过 LLM context 限制）


@dataclass
class SummaryResult:
    """摘要响应"""

    summary: str
    period: str
    chat_id: str | None
    message_count: int
    chunks_processed: int
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)


def _resolve_period_range(
    period: str,
    *,
    base_dt: datetime | None = None,
) -> tuple[int, int]:
    """解析 day/week/month 范围为 (timestamp_from, timestamp_to)

    以本地时区（UTC+8 默认）为参考。
    """
    import os

    tz_offset_str = os.getenv("LIFEVAULT_TIMEZONE_OFFSET", "8")
    try:
        tz_offset = int(tz_offset_str)
    except (TypeError, ValueError):
        tz_offset = 8

    tz = timezone(timedelta(hours=tz_offset))
    now = base_dt or datetime.now(tz=tz)

    if period == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif period == "week":
        # 本周一为起点
        days_since_monday = now.weekday()
        start = (now - timedelta(days=days_since_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end = start + timedelta(days=7)
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # 下个月 1 号
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
    else:
        raise ValueError(f"unsupported period: {period}, expected day/week/month")

    return int(start.timestamp()), int(end.timestamp())


def _split_into_chunks(messages: list[dict[str, Any]]) -> list[str]:
    """将消息列表分块，每块控制在 MAX_CHUNK_CHARS 内"""
    chunks: list[str] = []
    current: list[str] = []
    used = 0
    total_used = 0

    for msg in messages:
        time_str = datetime.fromtimestamp(int(msg["timestamp"])).strftime("%m-%d %H:%M")
        sender = msg.get("sender_name") or msg.get("sender_id") or "Unknown"
        chat = msg.get("chat_name") or msg.get("chat_id") or ""
        body = (msg.get("content") or "").strip()
        if not body:
            continue
        line = f"[{time_str}] {sender}@{chat}: {body}"
        line_len = len(line) + 1  # +1 for newline

        if total_used + line_len > MAX_TOTAL_CHARS:
            break

        if used + line_len > MAX_CHUNK_CHARS and current:
            chunks.append("\n".join(current))
            current = []
            used = 0

        current.append(line)
        used += line_len
        total_used += line_len

    if current:
        chunks.append("\n".join(current))

    return chunks


async def fetch_messages_for_summary(
    messages_db_path: str,
    *,
    timestamp_from: int,
    timestamp_to: int,
    chat_id: str | None = None,
) -> list[dict[str, Any]]:
    """拉取指定时间窗口的消息"""
    async with aiosqlite.connect(messages_db_path) as db:
        db.row_factory = aiosqlite.Row
        if chat_id:
            cursor = await db.execute(
                """
                SELECT timestamp, chat_id, chat_name, sender_name, content
                FROM unified_messages
                WHERE timestamp >= ? AND timestamp < ? AND chat_id = ? AND msg_type = 1
                ORDER BY timestamp ASC
                """.strip(),
                (timestamp_from, timestamp_to, chat_id),
            )
        else:
            cursor = await db.execute(
                """
                SELECT timestamp, chat_id, chat_name, sender_name, content
                FROM unified_messages
                WHERE timestamp >= ? AND timestamp < ? AND msg_type = 1
                ORDER BY timestamp ASC
                """.strip(),
                (timestamp_from, timestamp_to),
            )
        rows = await cursor.fetchall()
        await cursor.close()

    return [dict(row) for row in rows]


async def summarize(
    *,
    llm: LLMProvider,
    messages_db_path: str,
    period: str,
    chat_id: str | None = None,
    base_dt: datetime | None = None,
) -> SummaryResult:
    """生成摘要

    流程：
    1. 计算时间窗口
    2. 拉取消息并分块
    3. 对每块生成局部摘要（如果只有一块则跳过这步）
    4. 聚合所有局部摘要为最终摘要
    """
    ts_from, ts_to = _resolve_period_range(period, base_dt=base_dt)
    messages = await fetch_messages_for_summary(
        messages_db_path,
        timestamp_from=ts_from,
        timestamp_to=ts_to,
        chat_id=chat_id,
    )

    if not messages:
        return SummaryResult(
            summary="选定的时间范围内没有可分析的消息。",
            period=period,
            chat_id=chat_id,
            message_count=0,
            chunks_processed=0,
            model=llm.model,
        )

    chunks = _split_into_chunks(messages)

    period_zh = {"day": "今天", "week": "本周", "month": "本月"}.get(period, period)

    # 第一步：每块的局部摘要（map 阶段）
    partial_summaries: list[str] = []
    last_model = llm.model
    total_usage: dict[str, int] = {}

    async def summarize_chunk(idx: int, chunk: str) -> str:
        nonlocal last_model
        messages_for_llm = [
            ChatMessage(
                role="system",
                content=(
                    f"你是聊天记录分析助手。下面是{period_zh}聊天记录的一个片段。"
                    "请用简洁的中文总结这个片段讨论的主要话题、关键事件和情绪倾向。"
                    "不要罗列每条消息，提取要点即可。"
                ),
            ),
            ChatMessage(role="user", content=f"聊天片段：\n\n{chunk}"),
        ]
        response = await llm.chat_completion(messages_for_llm, temperature=0.3)
        last_model = response.model or last_model
        # 累计 usage（不同 provider 字段不同，简单求和）
        for k, v in (response.usage or {}).items():
            if isinstance(v, (int, float)):
                total_usage[k] = total_usage.get(k, 0) + int(v)
        return response.content

    # 串行处理避免压垮 LLM（特别是本地 Ollama）
    for idx, chunk in enumerate(chunks):
        summary = await summarize_chunk(idx, chunk)
        partial_summaries.append(summary)

    # 第二步：最终聚合（reduce 阶段）
    if len(partial_summaries) == 1:
        final_summary = partial_summaries[0]
    else:
        combined = "\n\n---\n\n".join(
            f"片段 {i+1}：\n{s}" for i, s in enumerate(partial_summaries)
        )
        final_messages = [
            ChatMessage(
                role="system",
                content=(
                    f"你是聊天记录分析助手。下面是{period_zh}聊天记录多个片段的局部摘要。"
                    "请合并这些摘要，输出一份完整的总结报告："
                    "1. 主要话题（按重要性排序）"
                    "2. 关键事件"
                    "3. 整体情绪和互动特征"
                    "4. 值得注意的趋势或模式"
                    "用中文回答，结构清晰。"
                ),
            ),
            ChatMessage(role="user", content=f"各片段摘要：\n\n{combined}"),
        ]
        response = await llm.chat_completion(final_messages, temperature=0.4)
        final_summary = response.content
        last_model = response.model or last_model
        for k, v in (response.usage or {}).items():
            if isinstance(v, (int, float)):
                total_usage[k] = total_usage.get(k, 0) + int(v)

    return SummaryResult(
        summary=final_summary,
        period=period,
        chat_id=chat_id,
        message_count=len(messages),
        chunks_processed=len(chunks),
        model=last_model,
        usage=total_usage,
    )
