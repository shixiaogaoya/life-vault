"""向量索引构建器：从 unified_messages 抽取文本 → 生成 embedding → 写入 vector store。"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import aiosqlite

from app.ai.embeddings.base import EmbeddingProvider
from app.ai.vector_store import VectorStore


DEFAULT_VECTOR_DB_PATH = "~/.lifevault/vectors.db"
DEFAULT_BATCH_SIZE = 32
MAX_TEXT_LENGTH = 500  # 截断长消息，避免 embedding token 浪费


@dataclass
class IndexProgress:
    """索引任务进度"""

    status: str = "idle"  # idle / running / completed / failed
    total: int = 0
    processed: int = 0
    failed: int = 0
    started_at: str = ""
    finished_at: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "total": self.total,
            "processed": self.processed,
            "failed": self.failed,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
        }


def _get_vector_db_path() -> str:
    raw = os.getenv("LIFEVAULT_VECTOR_DB_PATH", DEFAULT_VECTOR_DB_PATH)
    return str(os.path.expanduser(raw))


def get_vector_store(dimensions: int) -> VectorStore:
    """获取配置好的 VectorStore 实例"""
    return VectorStore(_get_vector_db_path(), dimensions=dimensions)


async def fetch_unindexed_messages(
    messages_db_path: str,
    vectors_db_path: str,
    *,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """拉取尚未索引的文本消息（msg_type=1）"""
    store = VectorStore(vectors_db_path, dimensions=0)  # dimensions 不影响 list_message_ids
    try:
        indexed_ids = await store.list_message_ids()
    except Exception:
        # 表未初始化时返回空集
        indexed_ids = set()

    async with aiosqlite.connect(messages_db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, content, chat_id, chat_name, sender_name, timestamp
            FROM unified_messages
            WHERE msg_type = 1 AND content != '' AND id NOT IN (
                SELECT DISTINCT message_id FROM message_vectors
            )
            ORDER BY id ASC
            LIMIT ?
            """.strip(),
            (limit,),
        )
        rows = await cursor.fetchall()
        await cursor.close()

    return [
        {
            "id": int(row["id"]),
            "content": (row["content"] or "")[:MAX_TEXT_LENGTH],
            "chat_id": row["chat_id"] or "",
            "chat_name": row["chat_name"] or "",
            "sender_name": row["sender_name"] or "",
            "timestamp": int(row["timestamp"]),
        }
        for row in rows
        if int(row["id"]) not in indexed_ids
    ]


async def build_index(
    embedding_provider: EmbeddingProvider,
    messages_db_path: str,
    vectors_db_path: str,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    progress: IndexProgress | None = None,
    cancel_event: asyncio.Event | None = None,
) -> IndexProgress:
    """构建（增量）向量索引

    参数：
        embedding_provider: 已配置好的 embedding provider
        messages_db_path: unified_messages 所在 SQLite 文件
        vectors_db_path: 向量存储文件
        batch_size: 每批 embedding 数量
        progress: 可选的进度对象（用于跨任务共享）
        cancel_event: 可选的取消信号

    返回：最终的 IndexProgress
    """
    if progress is None:
        progress = IndexProgress()

    progress.status = "running"
    progress.started_at = datetime.now().isoformat(timespec="seconds")
    progress.error = ""

    try:
        store = VectorStore(vectors_db_path, dimensions=embedding_provider.dimensions)
        await store.init_schema()

        # 先统计总数（用于进度展示）
        async with aiosqlite.connect(messages_db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM unified_messages WHERE msg_type = 1 AND content != ''"
            )
            total_row = await cursor.fetchone()
            await cursor.close()
        progress.total = int(total_row[0]) if total_row else 0

        # 已索引数
        indexed_count = await store.count()
        progress.processed = indexed_count

        while True:
            if cancel_event is not None and cancel_event.is_set():
                progress.status = "failed"
                progress.error = "cancelled by user"
                break

            batch = await fetch_unindexed_messages(
                messages_db_path, vectors_db_path, limit=batch_size
            )
            if not batch:
                progress.status = "completed"
                progress.finished_at = datetime.now().isoformat(timespec="seconds")
                break

            texts = [item["content"] for item in batch]
            try:
                results = await embedding_provider.embed_texts(texts)
            except Exception as exc:
                progress.failed += len(batch)
                progress.error = f"embedding batch failed: {exc}"
                # 跳过这批继续下一批（避免单批失败终止整个索引）
                continue

            records = []
            for item, result in zip(batch, results):
                records.append(
                    {
                        "message_id": item["id"],
                        "chunk_text": item["content"],
                        "vector": result.vector,
                        "chat_id": item["chat_id"],
                        "timestamp": item["timestamp"],
                        "model": result.model or embedding_provider.model,
                        "metadata": {
                            "chat_name": item["chat_name"],
                            "sender_name": item["sender_name"],
                        },
                    }
                )

            try:
                await store.batch_upsert(records)
                progress.processed += len(records)
            except Exception as exc:
                progress.failed += len(records)
                progress.error = f"batch upsert failed: {exc}"

    except Exception as exc:
        progress.status = "failed"
        progress.error = str(exc)
        progress.finished_at = datetime.now().isoformat(timespec="seconds")

    return progress
