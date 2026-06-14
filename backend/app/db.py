import json
import os
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

import aiosqlite

from app.models.message import UnifiedMessage
from app.utils.text import extract_text_tokens, is_emoji_char


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


def _get_tz_offset() -> int:
    """获取时区偏移（小时），默认 +8（中国时区），可通过环境变量配置"""
    raw = os.getenv("LIFEVAULT_TIMEZONE_OFFSET", "8")
    try:
        offset = int(raw)
    except (TypeError, ValueError):
        return 8
    # 允许 -12 ~ +14 的有效时区范围
    if -12 <= offset <= 14:
        return offset
    return 8


def _tz_modifier(tz_offset: int) -> str:
    """构造 SQLite strftime 用的时区修饰符（如 '+8 hours' 或 '-5 hours'）"""
    sign = "+" if tz_offset >= 0 else "-"
    return f"{sign}{abs(tz_offset)} hours"


def _get_type_name_for_stats(msg_type: int, sub_type: int = 0) -> str:
    """统计用的消息类型名称（独立于 export.py，避免反向依赖）"""
    if msg_type == 49:
        return {
            3: "音乐", 5: "链接", 6: "文件", 19: "合并转发",
            33: "小程序", 51: "视频号", 57: "引用消息", 2000: "转账",
        }.get(sub_type, f"应用消息({sub_type})")
    return {
        1: "文本", 3: "图片", 34: "语音", 42: "名片",
        43: "视频", 47: "表情包", 48: "位置",
        50: "音视频通话", 66: "OpenIM名片", 10000: "系统消息",
    }.get(msg_type, f"未知({msg_type})")


async def get_visualization_stats(
    filters: dict[str, Any] | None = None,
    top_emoji_limit: int = 20,
    top_terms_limit: int = 30,
) -> dict[str, Any]:
    """获取可视化统计数据

    返回：
    - activity_heatmap: 7x24 矩阵 [weekday][hour]，weekday 0=Monday..6=Sunday
    - hourly_distribution: 24 个时段的消息数
    - weekday_distribution: 7 天（周一~周日）的消息数
    - daily_timeseries: 按天的 [{date, count}, ...] 时序数据（最多 365 天）
    - emoji_stats: Top N emoji 列表
    - top_terms: Top N 高频词
    - media_type_distribution: 媒体类型分布
    - sender_receiver_ratio: {sent, received}
    """
    tz_offset = _get_tz_offset()
    tz_modifier = _tz_modifier(tz_offset)
    where_sql, params = _build_message_filters(filters)

    async with _connect() as db:
        # 24x7 热力图：weekday (0=Monday) 和 hour
        cursor = await db.execute(
            f"""
            SELECT
                CAST(strftime('%w', timestamp, 'unixepoch', '{tz_modifier}') AS INTEGER) AS sqlite_wday,
                CAST(strftime('%H', timestamp, 'unixepoch', '{tz_modifier}') AS INTEGER) AS hour,
                COUNT(*) AS cnt
            FROM unified_messages
            {where_sql}
            GROUP BY sqlite_wday, hour
            """.strip(),
            params,
        )
        heatmap_rows = await cursor.fetchall()
        await cursor.close()

        # 按天时序数据
        cursor = await db.execute(
            f"""
            SELECT
                strftime('%Y-%m-%d', timestamp, 'unixepoch', '{tz_modifier}') AS day,
                COUNT(*) AS cnt
            FROM unified_messages
            {where_sql}
            GROUP BY day
            ORDER BY day ASC
            LIMIT 366
            """.strip(),
            params,
        )
        daily_rows = await cursor.fetchall()
        await cursor.close()

        # 媒体类型分布
        cursor = await db.execute(
            f"""
            SELECT msg_type, sub_type, COUNT(*) AS cnt
            FROM unified_messages
            {where_sql}
            GROUP BY msg_type, sub_type
            ORDER BY cnt DESC
            """.strip(),
            params,
        )
        type_rows = await cursor.fetchall()
        await cursor.close()

        # 发送/接收比例
        cursor = await db.execute(
            f"""
            SELECT
                SUM(CASE WHEN is_sender = 1 THEN 1 ELSE 0 END) AS sent,
                SUM(CASE WHEN is_sender = 0 THEN 1 ELSE 0 END) AS received
            FROM unified_messages
            {where_sql}
            """.strip(),
            params,
        )
        sr_row = await cursor.fetchone()
        await cursor.close()

        # 拉取文本内容用于 emoji/词频统计（仅文本类消息，避免图片/语音的空内容）
        text_filters = {"msg_type": 1}
        if filters:
            for key in ("chat_id", "source", "date_from", "date_to"):
                if filters.get(key) is not None:
                    text_filters[key] = filters[key]
        text_where, text_params = _build_message_filters(text_filters)
        cursor = await db.execute(
            f"""
            SELECT content
            FROM unified_messages
            {text_where}
            ORDER BY timestamp DESC
            LIMIT 50000
            """.strip(),
            text_params,
        )
        text_rows = await cursor.fetchall()
        await cursor.close()

    # SQLite %w 返回 0=Sunday..6=Saturday，转换为 0=Monday..6=Sunday
    def _to_iso_weekday(sqlite_wday: int) -> int:
        # SQLite: 0=Sunday,1=Monday,...,6=Saturday
        # ISO:    0=Monday,...,5=Saturday,6=Sunday
        if sqlite_wday == 0:
            return 6  # Sunday -> 6
        return sqlite_wday - 1

    heatmap = [[0] * 24 for _ in range(7)]
    hourly = [0] * 24
    weekday = [0] * 7
    heatmap_max = 0
    for row in heatmap_rows:
        iso_wday = _to_iso_weekday(row["sqlite_wday"])
        hour = int(row["hour"])
        cnt = int(row["cnt"])
        heatmap[iso_wday][hour] = cnt
        hourly[hour] += cnt
        weekday[iso_wday] += cnt
        if cnt > heatmap_max:
            heatmap_max = cnt

    daily_timeseries = [
        {"date": row["day"], "count": int(row["cnt"])}
        for row in daily_rows
        if row["day"]
    ]

    media_distribution: dict[str, int] = {}
    for row in type_rows:
        name = _get_type_name_for_stats(int(row["msg_type"]), int(row["sub_type"] or 0))
        media_distribution[name] = media_distribution.get(name, 0) + int(row["cnt"])

    # Emoji 统计 & 词频统计（在 Python 端聚合，避免 SQLite regex 限制）
    emoji_counter: Counter = Counter()
    term_counter: Counter = Counter()
    for row in text_rows:
        content = row["content"] or ""
        for ch in content:
            if is_emoji_char(ch):
                emoji_counter[ch] += 1
        for token in extract_text_tokens(content):
            term_counter[token] += 1

    emoji_stats = [
        {"emoji": emoji, "count": cnt}
        for emoji, cnt in emoji_counter.most_common(top_emoji_limit)
    ]
    top_terms = [
        {"term": term, "count": cnt}
        for term, cnt in term_counter.most_common(top_terms_limit)
    ]

    sent = int(sr_row["sent"] or 0) if sr_row else 0
    received = int(sr_row["received"] or 0) if sr_row else 0

    return {
        "activity_heatmap": {
            "matrix": heatmap,
            "max_count": heatmap_max,
            "weekday_labels": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
            "hour_labels": [f"{h:02d}" for h in range(24)],
        },
        "hourly_distribution": hourly,
        "weekday_distribution": weekday,
        "daily_timeseries": daily_timeseries,
        "emoji_stats": emoji_stats,
        "top_terms": top_terms,
        "media_type_distribution": media_distribution,
        "sender_receiver_ratio": {
            "sent": sent,
            "received": received,
            "sent_percentage": round(sent * 100.0 / (sent + received), 2) if (sent + received) > 0 else 0.0,
        },
        "timezone_offset": tz_offset,
    }


async def get_contact_activity_stats(
    filters: dict[str, Any] | None = None,
    *,
    top_contacts_limit: int = 20,
    top_senders_limit: int = 20,
) -> dict[str, Any]:
    """获取联系人 / 发送者活跃度对比数据（用于"对比视图"仪表板）

    返回：
    - total_contacts: 不重复的 chat_id 数量
    - total_senders: 不重复的 sender_name 数量
    - top_contacts: 按消息数排序的聊天列表 [{chat_id, chat_name, message_count, first_seen, last_seen, sent, received, media_count, text_count}]
    - top_senders: 按消息数排序的发送者列表 [{sender_name, message_count, sent, received, distinct_chats}]
    - hourly_by_top_contacts: 前若干个聊天在 24 小时上的活跃度分布 [{chat_id, chat_name, hourly: [24]}]
    """
    tz_offset = _get_tz_offset()
    tz_modifier = _tz_modifier(tz_offset)
    where_sql, params = _build_message_filters(filters)

    async with _connect() as db:
        # 聊天活跃度（按消息数排序）
        cursor = await db.execute(
            f"""
            SELECT
                chat_id,
                COALESCE(NULLIF(chat_name, ''), chat_id) AS chat_name,
                COUNT(*) AS message_count,
                MIN(timestamp) AS first_seen,
                MAX(timestamp) AS last_seen,
                SUM(CASE WHEN is_sender = 1 THEN 1 ELSE 0 END) AS sent,
                SUM(CASE WHEN is_sender = 0 THEN 1 ELSE 0 END) AS received,
                SUM(CASE WHEN msg_type = 1 THEN 1 ELSE 0 END) AS text_count,
                SUM(CASE WHEN msg_type != 1 THEN 1 ELSE 0 END) AS media_count
            FROM unified_messages
            {where_sql}
            GROUP BY chat_id, chat_name
            ORDER BY message_count DESC, last_seen DESC
            LIMIT ?
            """.strip(),
            (*params, top_contacts_limit),
        )
        contact_rows = await cursor.fetchall()
        await cursor.close()

        # 发送者活跃度
        sender_clause = where_sql or "WHERE sender_name != ''"
        # 上面的 where_sql 可能为空字符串；这里需要单独处理"过滤掉空 sender_name"
        if where_sql:
            sender_where = f"{where_sql} AND sender_name != ''"
        else:
            sender_where = "WHERE sender_name != ''"
        cursor = await db.execute(
            f"""
            SELECT
                sender_name,
                COUNT(*) AS message_count,
                SUM(CASE WHEN is_sender = 1 THEN 1 ELSE 0 END) AS sent,
                SUM(CASE WHEN is_sender = 0 THEN 1 ELSE 0 END) AS received,
                COUNT(DISTINCT chat_id) AS distinct_chats
            FROM unified_messages
            {sender_where}
            GROUP BY sender_name
            ORDER BY message_count DESC
            LIMIT ?
            """.strip(),
            (*params, top_senders_limit),
        )
        sender_rows = await cursor.fetchall()
        await cursor.close()

        # 总计（不受 LIMIT 影响）
        cursor = await db.execute(
            f"""
            SELECT
                COUNT(DISTINCT chat_id) AS total_contacts,
                COUNT(DISTINCT CASE WHEN sender_name != '' THEN sender_name END) AS total_senders
            FROM unified_messages
            {where_sql}
            """.strip(),
            params,
        )
        totals_row = await cursor.fetchone()
        await cursor.close()

        # 前 N 个聊天的小时分布（用于雷达/堆叠对比图）
        top_chat_ids = [row["chat_id"] for row in contact_rows[: min(top_contacts_limit, 5)]]
        hourly_by_contacts: list[dict[str, Any]] = []
        if top_chat_ids:
            placeholders = ",".join("?" for _ in top_chat_ids)
            cursor = await db.execute(
                f"""
                SELECT
                    chat_id,
                    COALESCE(NULLIF(chat_name, ''), chat_id) AS chat_name,
                    CAST(strftime('%H', timestamp, 'unixepoch', '{tz_modifier}') AS INTEGER) AS hour,
                    COUNT(*) AS cnt
                FROM unified_messages
                {where_sql} {'AND' if where_sql else 'WHERE'} chat_id IN ({placeholders})
                GROUP BY chat_id, hour
                """.strip(),
                (*params, *top_chat_ids),
            )
            hour_rows = await cursor.fetchall()
            await cursor.close()

            # 索引化以便快速填充
            index: dict[str, dict[str, Any]] = {
                cid: {"chat_id": cid, "chat_name": "", "hourly": [0] * 24}
                for cid in top_chat_ids
            }
            # 用 contact_rows 的 chat_name 填充（保证顺序与名称一致）
            name_map = {row["chat_id"]: row["chat_name"] for row in contact_rows}
            for cid in top_chat_ids:
                index[cid]["chat_name"] = name_map.get(cid, cid)
            for row in hour_rows:
                cid = row["chat_id"]
                if cid in index:
                    index[cid]["hourly"][int(row["hour"])] = int(row["cnt"])
            # 按 top_chat_ids 顺序输出
            hourly_by_contacts = [index[cid] for cid in top_chat_ids]

    top_contacts = [
        {
            "chat_id": row["chat_id"],
            "chat_name": row["chat_name"],
            "message_count": int(row["message_count"]),
            "first_seen": int(row["first_seen"]) if row["first_seen"] else None,
            "last_seen": int(row["last_seen"]) if row["last_seen"] else None,
            "sent": int(row["sent"] or 0),
            "received": int(row["received"] or 0),
            "text_count": int(row["text_count"] or 0),
            "media_count": int(row["media_count"] or 0),
        }
        for row in contact_rows
    ]

    top_senders = [
        {
            "sender_name": row["sender_name"],
            "message_count": int(row["message_count"]),
            "sent": int(row["sent"] or 0),
            "received": int(row["received"] or 0),
            "distinct_chats": int(row["distinct_chats"] or 0),
        }
        for row in sender_rows
    ]

    return {
        "total_contacts": int(totals_row["total_contacts"] or 0) if totals_row else 0,
        "total_senders": int(totals_row["total_senders"] or 0) if totals_row else 0,
        "top_contacts": top_contacts,
        "top_senders": top_senders,
        "hourly_by_top_contacts": hourly_by_contacts,
    }


async def get_relationship_analysis(
    filters: dict[str, Any] | None = None,
    *,
    top_pairs_limit: int = 20,
    top_senders_limit: int = 15,
) -> dict[str, Any]:
    """关系分析：基于"同一聊天中共同出现"的发送者关系网络

    核心思路：如果两个 sender_name 在同一个 chat_id 中都发过消息，
    则认为他们之间存在关系（例如群聊里的两个成员）。关系强度由
    共同聊天数与这些聊天中的消息量共同决定。

    返回：
    - total_senders: 不重复的 sender_name 数量
    - total_group_chats: 多人聊天（distinct sender >= 2）的数量
    - top_pairs: 按强度排序的发送者对 [{a, b, shared_chats, message_volume, strength}]
    - sender_nodes: 节点列表（用于前端图谱）[{name, message_count, chat_count}]
    - edges: 与 top_pairs 对应的边列表 [{source, target, strength}]
    """
    where_sql, params = _build_message_filters(filters)

    # 组装"过滤掉空 sender_name"的 where 子句
    if where_sql:
        sender_where = f"{where_sql} AND sender_name != ''"
    else:
        sender_where = "WHERE sender_name != ''"

    async with _connect() as db:
        # 1) 每个 (sender, chat) 的消息量 —— 用于构建邻接关系
        cursor = await db.execute(
            f"""
            SELECT
                sender_name,
                chat_id,
                COUNT(*) AS msg_count
            FROM unified_messages
            {sender_where}
            GROUP BY sender_name, chat_id
            """.strip(),
            params,
        )
        membership_rows = await cursor.fetchall()
        await cursor.close()

        # 2) 每个聊天的成员数 —— 用于区分群聊 vs 单聊
        cursor = await db.execute(
            f"""
            SELECT
                chat_id,
                COUNT(DISTINCT sender_name) AS member_count
            FROM unified_messages
            {sender_where}
            GROUP BY chat_id
            """.strip(),
            params,
        )
        chat_member_rows = await cursor.fetchall()
        await cursor.close()

        # 3) 每个 sender 的总量（节点用）
        cursor = await db.execute(
            f"""
            SELECT
                sender_name,
                COUNT(*) AS message_count,
                COUNT(DISTINCT chat_id) AS chat_count
            FROM unified_messages
            {sender_where}
            GROUP BY sender_name
            ORDER BY message_count DESC
            LIMIT ?
            """.strip(),
            (*params, top_senders_limit),
        )
        sender_rows = await cursor.fetchall()
        await cursor.close()

        # 4) 总发送者数
        cursor = await db.execute(
            f"""
            SELECT COUNT(DISTINCT sender_name) AS total_senders
            FROM unified_messages
            {sender_where}
            """.strip(),
            params,
        )
        totals_row = await cursor.fetchone()
        await cursor.close()

    # ===== 在 Python 端构建关系图 =====
    # sender -> {chat_id: msg_count}
    sender_chats: dict[str, dict[str, int]] = {}
    for row in membership_rows:
        sender_chats.setdefault(row["sender_name"], {})[row["chat_id"]] = int(
            row["msg_count"]
        )

    chat_members: dict[str, int] = {
        row["chat_id"]: int(row["member_count"]) for row in chat_member_rows
    }
    group_chat_count = sum(1 for c in chat_members.values() if c >= 2)

    # 计算两两关系强度（共同聊天数 + 这些聊天中的消息量）
    senders = list(sender_chats.keys())
    pairs: list[dict[str, Any]] = []
    for i in range(len(senders)):
        sa = senders[i]
        chats_a = sender_chats[sa]
        for j in range(i + 1, len(senders)):
            sb = senders[j]
            chats_b = sender_chats[sb]
            shared = set(chats_a.keys()) & set(chats_b.keys())
            if not shared:
                continue
            # 强度 = 共同聊天数 × 10 + 这些聊天中两人的消息总量
            volume = sum(chats_a[c] + chats_b[c] for c in shared)
            strength = len(shared) * 10 + volume
            pairs.append(
                {
                    "a": sa,
                    "b": sb,
                    "shared_chats": len(shared),
                    "message_volume": volume,
                    "strength": strength,
                }
            )

    # 按强度降序，取 Top N
    pairs.sort(key=lambda p: p["strength"], reverse=True)
    top_pairs = pairs[:top_pairs_limit]

    # 节点：取出现在 top_pairs 中的发送者，补充消息量
    involved = set()
    for p in top_pairs:
        involved.add(p["a"])
        involved.add(p["b"])
    sender_node_map = {
        row["sender_name"]: {
            "name": row["sender_name"],
            "message_count": int(row["message_count"]),
            "chat_count": int(row["chat_count"]),
        }
        for row in sender_rows
    }
    nodes = [sender_node_map[name] for name in involved if name in sender_node_map]

    edges = [
        {"source": p["a"], "target": p["b"], "strength": p["strength"]}
        for p in top_pairs
    ]

    return {
        "total_senders": int(totals_row["total_senders"] or 0) if totals_row else 0,
        "total_group_chats": group_chat_count,
        "top_pairs": top_pairs,
        "sender_nodes": nodes,
        "edges": edges,
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
