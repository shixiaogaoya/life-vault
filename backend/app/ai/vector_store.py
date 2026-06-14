"""SQLite-based 向量存储，用于 RAG 检索。

设计原则：
- 不引入 sqlite-vec / faiss 等二进制依赖，保持纯 Python
- 对个人项目规模（万级消息）brute-force KNN 完全够用
- 用 struct 打包 float32 数组为 BLOB，节省存储
- 支持 metadata（chat_id、timestamp、message_id）以便过滤
- cosine similarity 通过点积 / 模长计算（向量需先归一化）
"""
from __future__ import annotations

import asyncio
import json
import math
import struct
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

import aiosqlite


def _pack_vector(vector: list[float]) -> bytes:
    """float list -> packed little-endian float32 bytes"""
    return struct.pack(f"<{len(vector)}f", *vector)


def _unpack_vector(blob: bytes) -> list[float]:
    """packed bytes -> float list"""
    count = len(blob) // 4
    return list(struct.unpack(f"<{count}f", blob))


def _normalize(vector: list[float]) -> list[float]:
    """L2 归一化"""
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        return vector
    return [v / norm for v in vector]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """计算 cosine 相似度（假设向量已归一化时即点积）"""
    if len(a) != len(b):
        return 0.0
    if not a:
        return 0.0
    return sum(x * y for x, y in zip(a, b))


@dataclass
class VectorRecord:
    """向量记录"""

    id: int | None
    message_id: int
    chunk_text: str
    vector: list[float]
    chat_id: str
    timestamp: int
    metadata: dict[str, Any]


@dataclass
class SearchHit:
    """向量检索命中"""

    id: int
    message_id: int
    chunk_text: str
    score: float
    chat_id: str
    timestamp: int
    metadata: dict[str, Any]


class VectorStore:
    """SQLite-based 向量存储（持久化在独立 . vectors.db 文件中）"""

    def __init__(self, db_path: str, dimensions: int = 768) -> None:
        self.db_path = str(db_path)
        self.dimensions = dimensions

    @asynccontextmanager
    async def _connect(self) -> AsyncIterator[aiosqlite.Connection]:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            yield db

    async def init_schema(self) -> None:
        async with self._connect() as db:
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS message_vectors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL DEFAULT 0,
                    chunk_text TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    chat_id TEXT NOT NULL DEFAULT '',
                    timestamp INTEGER NOT NULL DEFAULT 0,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    model TEXT NOT NULL DEFAULT '',
                    created_at INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(message_id, chunk_index)
                );

                CREATE INDEX IF NOT EXISTS idx_message_id
                    ON message_vectors(message_id);
                CREATE INDEX IF NOT EXISTS idx_chat_id
                    ON message_vectors(chat_id);
                CREATE INDEX IF NOT EXISTS idx_timestamp
                    ON message_vectors(timestamp);
                """
            )
            await db.commit()

    async def upsert(
        self,
        message_id: int,
        chunk_text: str,
        vector: list[float],
        *,
        chat_id: str = "",
        timestamp: int = 0,
        chunk_index: int = 0,
        model: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """插入或更新一条向量记录"""
        if len(vector) != self.dimensions:
            raise ValueError(
                f"vector dimension mismatch: expected {self.dimensions}, got {len(vector)}"
            )

        normalized = _normalize(vector)
        blob = _pack_vector(normalized)
        meta_json = json.dumps(metadata or {}, ensure_ascii=False)
        created_at = int(time.time())

        async with self._connect() as db:
            cursor = await db.execute(
                """
                INSERT INTO message_vectors (
                    message_id, chunk_index, chunk_text, embedding,
                    chat_id, timestamp, metadata, model, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id, chunk_index) DO UPDATE SET
                    chunk_text = excluded.chunk_text,
                    embedding = excluded.embedding,
                    chat_id = excluded.chat_id,
                    timestamp = excluded.timestamp,
                    metadata = excluded.metadata,
                    model = excluded.model,
                    created_at = excluded.created_at
                """,
                (
                    message_id,
                    chunk_index,
                    chunk_text,
                    blob,
                    chat_id,
                    timestamp,
                    meta_json,
                    model,
                    created_at,
                ),
            )
            await db.commit()
            record_id = cursor.lastrowid or 0
            await cursor.close()
            return record_id

    async def batch_upsert(self, records: list[dict[str, Any]]) -> int:
        """批量插入（性能更优）

        records 字段同 upsert 的关键字参数
        """
        if not records:
            return 0

        rows: list[tuple] = []
        for r in records:
            vector = r["vector"]
            if len(vector) != self.dimensions:
                raise ValueError(
                    f"vector dimension mismatch: expected {self.dimensions}, got {len(vector)}"
                )
            rows.append(
                (
                    r["message_id"],
                    r.get("chunk_index", 0),
                    r["chunk_text"],
                    _pack_vector(_normalize(vector)),
                    r.get("chat_id", ""),
                    r.get("timestamp", 0),
                    json.dumps(r.get("metadata") or {}, ensure_ascii=False),
                    r.get("model", ""),
                    int(time.time()),
                )
            )

        async with self._connect() as db:
            cursor = await db.executemany(
                """
                INSERT INTO message_vectors (
                    message_id, chunk_index, chunk_text, embedding,
                    chat_id, timestamp, metadata, model, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id, chunk_index) DO UPDATE SET
                    chunk_text = excluded.chunk_text,
                    embedding = excluded.embedding,
                    chat_id = excluded.chat_id,
                    timestamp = excluded.timestamp,
                    metadata = excluded.metadata,
                    model = excluded.model,
                    created_at = excluded.created_at
                """,
                rows,
            )
            await db.commit()
            inserted = cursor.rowcount if cursor.rowcount else 0
            await cursor.close()
            return inserted

    async def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 5,
        chat_id: str | None = None,
        timestamp_from: int | None = None,
        timestamp_to: int | None = None,
    ) -> list[SearchHit]:
        """KNN 检索（brute-force cosine similarity）"""
        if not query_vector:
            return []

        normalized_query = _normalize(query_vector)

        clauses: list[str] = []
        params: list[Any] = []
        if chat_id:
            clauses.append("chat_id = ?")
            params.append(chat_id)
        if timestamp_from is not None:
            clauses.append("timestamp >= ?")
            params.append(timestamp_from)
        if timestamp_to is not None:
            clauses.append("timestamp <= ?")
            params.append(timestamp_to)

        where_sql = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        async with self._connect() as db:
            cursor = await db.execute(
                f"""
                SELECT id, message_id, chunk_text, embedding, chat_id, timestamp, metadata
                FROM message_vectors
                {where_sql}
                """,
                params,
            )
            rows = await cursor.fetchall()
            await cursor.close()

        # Python 端 cosine similarity 计算
        scored: list[tuple[float, aiosqlite.Row]] = []
        for row in rows:
            vec = _unpack_vector(row["embedding"])
            score = cosine_similarity(normalized_query, vec)
            scored.append((score, row))

        scored.sort(key=lambda item: item[0], reverse=True)
        hits: list[SearchHit] = []
        for score, row in scored[:top_k]:
            hits.append(
                SearchHit(
                    id=int(row["id"]),
                    message_id=int(row["message_id"]),
                    chunk_text=row["chunk_text"],
                    score=score,
                    chat_id=row["chat_id"],
                    timestamp=int(row["timestamp"]),
                    metadata=json.loads(row["metadata"] or "{}"),
                )
            )
        return hits

    async def delete_by_message(self, message_id: int) -> int:
        async with self._connect() as db:
            cursor = await db.execute(
                "DELETE FROM message_vectors WHERE message_id = ?",
                (message_id,),
            )
            await db.commit()
            deleted = cursor.rowcount if cursor.rowcount else 0
            await cursor.close()
            return deleted

    async def count(self) -> int:
        async with self._connect() as db:
            cursor = await db.execute("SELECT COUNT(*) AS total FROM message_vectors")
            row = await cursor.fetchone()
            await cursor.close()
            return int(row["total"]) if row else 0

    async def list_message_ids(self) -> set[int]:
        """获取已索引的 message_id 集合（用于增量构建）"""
        async with self._connect() as db:
            cursor = await db.execute("SELECT DISTINCT message_id FROM message_vectors")
            rows = await cursor.fetchall()
            await cursor.close()
            return {int(row["message_id"]) for row in rows}
