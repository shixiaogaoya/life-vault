import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

import aiosqlite

from app.models.message import UnifiedMessage


DEFAULT_DB_PATH = "~/.lifevault/archive.db"

MESSAGE_COLUMNS = (
    "id",
    "source",
    "msg_svr_id",
    "local_id",
    "msg_type",
    "sub_type",
    "timestamp",
    "created_at",
    "updated_at",
    "chat_id",
    "chat_name",
    "sender_id",
    "sender_name",
    "is_sender",
    "content",
    "status",
    "raw",
    "metadata",
)


async def get_db_path() -> str:
    """获取数据库路径（支持环境变量 LIFEVAULT_DB_PATH）"""
    db_path = os.getenv("LIFEVAULT_DB_PATH", DEFAULT_DB_PATH)
    return str(Path(db_path).expanduser())


@asynccontextmanager
async def _connect(db_path: str | None = None) -> AsyncIterator[aiosqlite.Connection]:
    path = db_path or await get_db_path()
    async with aiosqlite.connect(path) as conn:
        conn.row_factory = aiosqlite.Row
        yield conn


async def init_database(db_path: str) -> None:
    """初始化数据库（创建表、索引和 FTS5 触发器）"""
    resolved_path = Path(db_path).expanduser()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    async with _connect(str(resolved_path)) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS unified_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                msg_svr_id INTEGER NOT NULL,
                local_id INTEGER NOT NULL,
                msg_type INTEGER NOT NULL,
                sub_type INTEGER DEFAULT 0,
                timestamp INTEGER NOT NULL CHECK(timestamp > 0),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                chat_id TEXT NOT NULL CHECK(chat_id != ''),
                chat_name TEXT DEFAULT '',
                sender_id TEXT DEFAULT '',
                sender_name TEXT DEFAULT '',
                is_sender INTEGER DEFAULT 0,
                content TEXT DEFAULT '',
                status INTEGER DEFAULT 0,
                raw TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',

                UNIQUE(source, msg_svr_id)
            );

            CREATE INDEX IF NOT EXISTS idx_timestamp
                ON unified_messages(timestamp);
            CREATE INDEX IF NOT EXISTS idx_chat_id
                ON unified_messages(chat_id);
            CREATE INDEX IF NOT EXISTS idx_msg_type
                ON unified_messages(msg_type, sub_type);

            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                content,
                sender_name,
                chat_name,
                content='unified_messages',
                content_rowid='id',
                tokenize='unicode61'
            );

            CREATE TRIGGER IF NOT EXISTS messages_fts_insert
            AFTER INSERT ON unified_messages BEGIN
                INSERT INTO messages_fts(rowid, content, sender_name, chat_name)
                VALUES (new.id, new.content, new.sender_name, new.chat_name);
            END;

            CREATE TRIGGER IF NOT EXISTS messages_fts_delete
            AFTER DELETE ON unified_messages BEGIN
                DELETE FROM messages_fts WHERE rowid = old.id;
            END;

            CREATE TABLE IF NOT EXISTS import_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                local_id INTEGER,
                error_type TEXT NOT NULL,
                error_message TEXT,
                raw_data TEXT,
                timestamp INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_error_timestamp
                ON import_errors(timestamp);
            """
        )
        await db.commit()


async def insert_messages(messages: list[UnifiedMessage]) -> int:
    """批量插入消息，返回成功插入的行数"""
    if not messages:
        return 0

    sql = """
        INSERT OR IGNORE INTO unified_messages (
            id, source, msg_svr_id, local_id, msg_type, sub_type, timestamp,
            created_at, updated_at, chat_id, chat_name, sender_id, sender_name,
            is_sender, content, status, raw, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    values = [_message_to_row(message) for message in messages]

    async with _connect() as db:
        cursor = await db.executemany(sql, values)
        await db.commit()
        inserted = cursor.rowcount if cursor.rowcount is not None else 0
        await cursor.close()
        return inserted


async def query_messages(
    filters: dict[str, Any] | None = None,
    page: int = 1,
    page_size: int = 50,
) -> list[UnifiedMessage]:
    """分页查询消息（支持过滤条件）"""
    where_sql, params = _build_message_filters(filters)
    offset = _offset(page, page_size)
    sql = f"""
        SELECT {", ".join(MESSAGE_COLUMNS)}
        FROM unified_messages
        {where_sql}
        ORDER BY timestamp DESC, id DESC
        LIMIT ? OFFSET ?
    """

    async with _connect() as db:
        cursor = await db.execute(sql, [*params, page_size, offset])
        rows = await cursor.fetchall()
        await cursor.close()
        return [_row_to_message(row) for row in rows]


async def count_messages(filters: dict[str, Any] | None = None) -> int:
    """统计符合过滤条件的消息数量"""
    where_sql, params = _build_message_filters(filters)
    sql = f"SELECT COUNT(*) AS total FROM unified_messages {where_sql}"

    async with _connect() as db:
        cursor = await db.execute(sql, params)
        row = await cursor.fetchone()
        await cursor.close()
        return row["total"] if row else 0


async def get_message_by_id(id: int) -> UnifiedMessage:
    """根据 ID 查询单条消息"""
    sql = f"""
        SELECT {", ".join(MESSAGE_COLUMNS)}
        FROM unified_messages
        WHERE id = ?
    """

    async with _connect() as db:
        cursor = await db.execute(sql, [id])
        row = await cursor.fetchone()
        await cursor.close()

    if row is None:
        raise ValueError(f"message not found: {id}")
    return _row_to_message(row)


async def search_messages(
    query: str,
    page: int = 1,
    page_size: int = 50,
) -> list[UnifiedMessage]:
    """使用 FTS5 全文检索消息"""
    fts_query = _build_fts_query(query)
    offset = _offset(page, page_size)
    sql = f"""
        SELECT m.{", m.".join(MESSAGE_COLUMNS)}
        FROM messages_fts fts
        JOIN unified_messages m ON m.id = fts.rowid
        WHERE messages_fts MATCH ?
        ORDER BY bm25(messages_fts), m.timestamp DESC, m.id DESC
        LIMIT ? OFFSET ?
    """

    async with _connect() as db:
        cursor = await db.execute(sql, [fts_query, page_size, offset])
        rows = await cursor.fetchall()
        await cursor.close()
        return [_row_to_message(row) for row in rows]


async def count_search_messages(query: str) -> int:
    """统计 FTS5 搜索命中的消息数量"""
    fts_query = _build_fts_query(query)
    sql = """
        SELECT COUNT(*) AS total
        FROM messages_fts
        WHERE messages_fts MATCH ?
    """

    async with _connect() as db:
        cursor = await db.execute(sql, [fts_query])
        row = await cursor.fetchone()
        await cursor.close()
        return row["total"] if row else 0


async def insert_import_errors(errors: list[dict[str, Any]]) -> int:
    """批量记录导入错误"""
    if not errors:
        return 0

    sql = """
        INSERT INTO import_errors (
            source, local_id, error_type, error_message, raw_data, timestamp, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    values = [
        (
            error["source"],
            error.get("local_id"),
            error["error_type"],
            error.get("error_message", ""),
            json.dumps(error.get("raw_data", {}), ensure_ascii=False),
            error["timestamp"],
            error["created_at"],
        )
        for error in errors
    ]

    async with _connect() as db:
        cursor = await db.executemany(sql, values)
        await db.commit()
        inserted = cursor.rowcount if cursor.rowcount is not None else 0
        await cursor.close()
        return inserted


async def get_stats() -> dict[str, Any]:
    """获取统计信息"""
    async with _connect() as db:
        cursor = await db.execute(
            """
            SELECT
                COUNT(*) AS total_messages,
                MIN(timestamp) AS earliest_message,
                MAX(timestamp) AS latest_message,
                COUNT(DISTINCT chat_id) AS chat_count
            FROM unified_messages
            """
        )
        totals = await cursor.fetchone()
        await cursor.close()

        cursor = await db.execute(
            """
            SELECT source, COUNT(*) AS count
            FROM unified_messages
            GROUP BY source
            """
        )
        source_rows = await cursor.fetchall()
        await cursor.close()

        cursor = await db.execute(
            """
            SELECT chat_id, chat_name, COUNT(*) AS message_count
            FROM unified_messages
            GROUP BY chat_id, chat_name
            ORDER BY message_count DESC, MAX(timestamp) DESC
            LIMIT 10
            """
        )
        top_chat_rows = await cursor.fetchall()
        await cursor.close()

    return {
        "total_messages": totals["total_messages"] or 0,
        "sources": {row["source"]: row["count"] for row in source_rows},
        "earliest_message": totals["earliest_message"],
        "latest_message": totals["latest_message"],
        "chat_count": totals["chat_count"] or 0,
        "top_chats": [
            {
                "chat_id": row["chat_id"],
                "chat_name": row["chat_name"],
                "message_count": row["message_count"],
            }
            for row in top_chat_rows
        ],
    }


def _message_to_row(message: UnifiedMessage) -> tuple[Any, ...]:
    data = message.to_dict()
    message_id = data["id"] if data.get("id", 0) else None
    return (
        message_id,
        data["source"],
        data["msg_svr_id"],
        data["local_id"],
        data["msg_type"],
        data["sub_type"],
        data["timestamp"],
        data["created_at"],
        data["updated_at"],
        data["chat_id"],
        data["chat_name"],
        data["sender_id"],
        data["sender_name"],
        int(data["is_sender"]),
        data["content"],
        data["status"],
        json.dumps(data["raw"], ensure_ascii=False),
        json.dumps(data["metadata"], ensure_ascii=False),
    )


def _row_to_message(row: aiosqlite.Row) -> UnifiedMessage:
    data = dict(row)
    data["source"] = data["source"]
    data["is_sender"] = bool(data["is_sender"])
    data["raw"] = json.loads(data["raw"] or "{}")
    data["metadata"] = json.loads(data["metadata"] or "{}")
    return UnifiedMessage.from_dict(data)


def _build_message_filters(filters: dict[str, Any] | None) -> tuple[str, list[Any]]:
    if not filters:
        return "", []

    clauses: list[str] = []
    params: list[Any] = []

    if filters.get("chat_id"):
        clauses.append("chat_id = ?")
        params.append(filters["chat_id"])
    if filters.get("msg_type") is not None:
        clauses.append("msg_type = ?")
        params.append(filters["msg_type"])
    if filters.get("source"):
        clauses.append("source = ?")
        params.append(filters["source"])
    if filters.get("date_from") is not None:
        clauses.append("timestamp >= ?")
        params.append(_parse_timestamp_filter(filters["date_from"]))
    if filters.get("date_to") is not None:
        clauses.append("timestamp <= ?")
        params.append(_parse_timestamp_filter(filters["date_to"], end_of_day=True))

    if not clauses:
        return "", []
    return "WHERE " + " AND ".join(clauses), params


def _parse_timestamp_filter(value: Any, end_of_day: bool = False) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    text = str(value).strip()
    if text.isdigit():
        return int(text)

    parsed = datetime.fromisoformat(text)
    if end_of_day and len(text) == 10:
        parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
    return int(parsed.timestamp())


def _build_fts_query(query: str) -> str:
    terms = [term.strip() for term in query.split() if term.strip()]
    if not terms:
        raise ValueError("search query must not be empty")
    return " AND ".join(f'"{term.replace(chr(34), chr(34) + chr(34))}"' for term in terms)


def _offset(page: int, page_size: int) -> int:
    if page < 1:
        raise ValueError("page must be >= 1")
    if page_size < 1:
        raise ValueError("page_size must be >= 1")
    return (page - 1) * page_size
