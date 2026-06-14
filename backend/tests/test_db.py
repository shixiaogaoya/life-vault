import pytest

from app.db import (
    count_messages,
    get_contact_activity_stats,
    get_db_path,
    get_relationship_analysis,
    get_visualization_stats,
    init_database,
    insert_messages,
    query_messages,
    search_messages,
)
from app.models.message import MessageSource, UnifiedMessage


@pytest.mark.asyncio
class TestDatabase:
    """Database operations tests"""

    async def test_init_database_creates_tables(self, tmp_path):
        """Test that init_database creates tables and FTS5 virtual table"""
        db_path = tmp_path / "test_init.db"
        await init_database(str(db_path))

        assert db_path.exists()

        # Verify tables exist
        import aiosqlite

        async with aiosqlite.connect(str(db_path)) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in await cursor.fetchall()]
            await cursor.close()

        assert "unified_messages" in tables
        assert "messages_fts" in tables
        assert "import_errors" in tables

    async def test_init_database_creates_indexes(self, tmp_path):
        """Test that init_database creates indexes"""
        db_path = tmp_path / "test_indexes.db"
        await init_database(str(db_path))

        import aiosqlite

        async with aiosqlite.connect(str(db_path)) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
            indexes = [row[0] for row in await cursor.fetchall()]
            await cursor.close()

        assert "idx_timestamp" in indexes
        assert "idx_chat_id" in indexes
        assert "idx_msg_type" in indexes

    async def test_insert_and_query_messages(self):
        """Test append-only write and query operations"""
        db_path = await get_db_path()
        await init_database(db_path)

        messages = [
            UnifiedMessage(
                id=0,
                source=MessageSource.WECHAT_4X,
                msg_svr_id=1001,
                local_id=1,
                msg_type=1,
                timestamp=1704067200,
                chat_id="user_a",
                chat_name="User A",
                content="Test message 1",
            ),
            UnifiedMessage(
                id=0,
                source=MessageSource.WECHAT_4X,
                msg_svr_id=1002,
                local_id=2,
                msg_type=1,
                timestamp=1704153600,
                chat_id="user_b",
                chat_name="User B",
                content="Test message 2",
            ),
        ]

        inserted = await insert_messages(messages)
        assert inserted == 2

        # Query all messages
        results = await query_messages()
        assert len(results) == 2
        assert results[0].content == "Test message 2"  # DESC order
        assert results[1].content == "Test message 1"

    async def test_insert_duplicate_messages_ignored(self):
        """Test that duplicate messages (same source + msg_svr_id) are ignored"""
        db_path = await get_db_path()
        await init_database(db_path)

        message = UnifiedMessage(
            id=0,
            source=MessageSource.WECHAT_4X,
            msg_svr_id=2001,
            local_id=1,
            msg_type=1,
            timestamp=1704067200,
            chat_id="user_a",
            content="Original",
        )

        inserted1 = await insert_messages([message])
        assert inserted1 == 1

        # Insert again with different content
        duplicate = UnifiedMessage(
            id=0,
            source=MessageSource.WECHAT_4X,
            msg_svr_id=2001,  # Same msg_svr_id
            local_id=1,
            msg_type=1,
            timestamp=1704067200,
            chat_id="user_a",
            content="Modified",
        )

        inserted2 = await insert_messages([duplicate])
        assert inserted2 == 0  # Should be ignored

        # Verify original content unchanged
        results = await query_messages()
        assert len(results) == 1
        assert results[0].content == "Original"

    async def test_fts5_search(self):
        """Test FTS5 full-text search"""
        db_path = await get_db_path()
        await init_database(db_path)

        messages = [
            UnifiedMessage(
                id=0,
                source=MessageSource.WECHAT_4X,
                msg_svr_id=3001,
                local_id=1,
                msg_type=1,
                timestamp=1704067200,
                chat_id="user_a",
                content="Python programming is great",
            ),
            UnifiedMessage(
                id=0,
                source=MessageSource.WECHAT_4X,
                msg_svr_id=3002,
                local_id=2,
                msg_type=1,
                timestamp=1704153600,
                chat_id="user_b",
                content="JavaScript is also good",
            ),
            UnifiedMessage(
                id=0,
                source=MessageSource.WECHAT_4X,
                msg_svr_id=3003,
                local_id=3,
                msg_type=1,
                timestamp=1704240000,
                chat_id="user_a",
                content="Python and JavaScript are both useful",
            ),
        ]

        await insert_messages(messages)

        # Search for "Python"
        results = await search_messages("Python")
        assert len(results) == 2
        assert all("Python" in msg.content for msg in results)

        # Search for "JavaScript"
        results = await search_messages("JavaScript")
        assert len(results) == 2
        assert all("JavaScript" in msg.content for msg in results)

        # Search for non-existent term
        results = await search_messages("Rust")
        assert len(results) == 0

    async def test_count_messages(self):
        """Test message counting"""
        db_path = await get_db_path()
        await init_database(db_path)

        messages = [
            UnifiedMessage(
                id=0,
                source=MessageSource.WECHAT_4X,
                msg_svr_id=4000 + i,
                local_id=i,
                msg_type=1,
                timestamp=1704067200 + i * 1000,
                chat_id=f"user_{i % 2}",
                content=f"Message {i}",
            )
            for i in range(10)
        ]

        await insert_messages(messages)

        # Count all
        total = await count_messages()
        assert total == 10

        # Count filtered by chat_id
        count_user_0 = await count_messages({"chat_id": "user_0"})
        assert count_user_0 == 5

        count_user_1 = await count_messages({"chat_id": "user_1"})
        assert count_user_1 == 5

    async def test_visualization_stats_empty_db(self):
        """Test get_visualization_stats with empty database returns zeroed structure"""
        db_path = await get_db_path()
        await init_database(db_path)

        stats = await get_visualization_stats()

        assert "activity_heatmap" in stats
        assert len(stats["activity_heatmap"]["matrix"]) == 7
        assert all(len(row) == 24 for row in stats["activity_heatmap"]["matrix"])
        assert stats["activity_heatmap"]["max_count"] == 0
        assert len(stats["hourly_distribution"]) == 24
        assert sum(stats["hourly_distribution"]) == 0
        assert len(stats["weekday_distribution"]) == 7
        assert stats["daily_timeseries"] == []
        assert stats["emoji_stats"] == []
        assert stats["top_terms"] == []
        assert stats["media_type_distribution"] == {}
        assert stats["sender_receiver_ratio"]["sent"] == 0
        assert stats["sender_receiver_ratio"]["received"] == 0
        assert stats["sender_receiver_ratio"]["sent_percentage"] == 0.0
        assert stats["timezone_offset"] == 8  # default China timezone

    async def test_visualization_stats_with_messages(self):
        """Test get_visualization_stats aggregates heatmap, hourly, emoji correctly"""
        db_path = await get_db_path()
        await init_database(db_path)

        # All timestamps at 08:00 UTC+8: Monday/Tuesday/Wednesday respectively
        # 1704067200 = 2024-01-01 08:00 UTC+8 (Monday, ISO weekday 0)
        # 1704153600 = 2024-01-02 08:00 UTC+8 (Tuesday, ISO weekday 1)
        # 1704240000 = 2024-01-03 08:00 UTC+8 (Wednesday, ISO weekday 2)
        messages = [
            UnifiedMessage(
                id=0,
                source=MessageSource.WECHAT_4X,
                msg_svr_id=5001,
                local_id=1,
                msg_type=1,
                timestamp=1704067200,  # Monday 08:00 UTC+8
                chat_id="user_a",
                sender_name="Alice",
                is_sender=False,
                content="Hello 😀 world",
            ),
            UnifiedMessage(
                id=0,
                source=MessageSource.WECHAT_4X,
                msg_svr_id=5002,
                local_id=2,
                msg_type=1,
                timestamp=1704153600,  # Tuesday 08:00 UTC+8
                chat_id="user_a",
                sender_name="Bob",
                is_sender=True,
                content="Hello 😀😀",
            ),
            UnifiedMessage(
                id=0,
                source=MessageSource.WECHAT_4X,
                msg_svr_id=5003,
                local_id=3,
                msg_type=3,  # 图片
                timestamp=1704240000,
                chat_id="user_a",
                sender_name="Alice",
                is_sender=False,
                content="",
            ),
        ]
        await insert_messages(messages)

        stats = await get_visualization_stats()

        # Heatmap: Monday(0) at 08:00 = 1, Tuesday(1) at 08:00 = 1, Wednesday(2) at 08:00 = 1
        assert stats["activity_heatmap"]["matrix"][0][8] == 1
        assert stats["activity_heatmap"]["matrix"][1][8] == 1
        assert stats["activity_heatmap"]["matrix"][2][8] == 1
        assert stats["activity_heatmap"]["max_count"] == 1

        # Hourly: hour 08 has all 3 messages (heatmap aggregates ALL message types)
        assert stats["hourly_distribution"][8] == 3

        # Daily timeseries: 3 entries (one per day)
        assert len(stats["daily_timeseries"]) == 3

        # Emoji: 😀 appears 3 times
        emoji_counts = {item["emoji"]: item["count"] for item in stats["emoji_stats"]}
        assert emoji_counts.get("😀") == 3

        # Media distribution: 文本 x 2, 图片 x 1
        assert stats["media_type_distribution"]["文本"] == 2
        assert stats["media_type_distribution"]["图片"] == 1

        # Sender/receiver: 1 sent (is_sender=True), 2 received
        assert stats["sender_receiver_ratio"]["sent"] == 1
        assert stats["sender_receiver_ratio"]["received"] == 2

    async def test_visualization_stats_with_filters(self):
        """Test get_visualization_stats respects chat_id filter"""
        db_path = await get_db_path()
        await init_database(db_path)

        messages = [
            UnifiedMessage(
                id=0,
                source=MessageSource.WECHAT_4X,
                msg_svr_id=6000 + i,
                local_id=i,
                msg_type=1,
                timestamp=1704067200 + i * 1000,
                chat_id="chat_a" if i % 2 == 0 else "chat_b",
                sender_name="Alice" if i % 2 == 0 else "Bob",
                content=f"Msg {i}",
            )
            for i in range(10)
        ]
        await insert_messages(messages)

        stats = await get_visualization_stats(filters={"chat_id": "chat_a"})
        # Only chat_a messages (i=0,2,4,6,8) => 5 messages
        total_in_heatmap = sum(sum(row) for row in stats["activity_heatmap"]["matrix"])
        assert total_in_heatmap == 5

    async def test_contact_activity_stats_empty_db(self):
        """空数据库应返回零值结构，不报错"""
        db_path = await get_db_path()
        await init_database(db_path)

        stats = await get_contact_activity_stats()

        assert stats["total_contacts"] == 0
        assert stats["total_senders"] == 0
        assert stats["top_contacts"] == []
        assert stats["top_senders"] == []
        assert stats["hourly_by_top_contacts"] == []

    async def test_contact_activity_stats_ranking_and_ratios(self):
        """联系人活跃度排名、发送/接收比例、首末时间戳应正确"""
        db_path = await get_db_path()
        await init_database(db_path)

        # chat_a: 6 条（5 Alice 收到，1 Bob 发出）
        # chat_b: 4 条（全部 Bob 发出）
        messages = [
            *[
                UnifiedMessage(
                    id=0,
                    source=MessageSource.WECHAT_4X,
                    msg_svr_id=7000 + i,
                    local_id=i,
                    msg_type=1,
                    timestamp=1704067200 + i * 1000,  # 2024-01-01 起
                    chat_id="chat_a",
                    chat_name="Chat A",
                    sender_name="Alice",
                    is_sender=False,
                    content=f"Hello {i}",
                )
                for i in range(5)
            ],
            UnifiedMessage(
                id=0,
                source=MessageSource.WECHAT_4X,
                msg_svr_id=7999,
                local_id=99,
                msg_type=1,
                timestamp=1704067200,
                chat_id="chat_a",
                chat_name="Chat A",
                sender_name="Bob",
                is_sender=True,
                content="Hi",
            ),
            *[
                UnifiedMessage(
                    id=0,
                    source=MessageSource.WECHAT_4X,
                    msg_svr_id=8000 + i,
                    local_id=200 + i,
                    msg_type=1,
                    timestamp=1704067200 + i * 1000,
                    chat_id="chat_b",
                    chat_name="Chat B",
                    sender_name="Bob",
                    is_sender=True,
                    content=f"Yo {i}",
                )
                for i in range(4)
            ],
        ]
        await insert_messages(messages)

        stats = await get_contact_activity_stats()

        # 聚合层面
        assert stats["total_contacts"] == 2
        assert stats["total_senders"] == 2  # Alice + Bob

        # chat_a 应排在首位（6 条 > chat_b 的 4 条）
        top_contacts = stats["top_contacts"]
        assert len(top_contacts) == 2
        assert top_contacts[0]["chat_id"] == "chat_a"
        assert top_contacts[0]["chat_name"] == "Chat A"
        assert top_contacts[0]["message_count"] == 6
        assert top_contacts[0]["received"] == 5  # Alice 的 5 条
        assert top_contacts[0]["sent"] == 1  # Bob 的 1 条
        assert top_contacts[1]["chat_id"] == "chat_b"
        assert top_contacts[1]["message_count"] == 4

        # 首末时间戳应非空
        assert top_contacts[0]["first_seen"] is not None
        assert top_contacts[0]["last_seen"] is not None

        # 发送者排名：Bob 5 条 (1+4)，Alice 5 条；按计数同分时排序顺序由 SQL 决定
        top_senders = stats["top_senders"]
        sender_counts = {s["sender_name"]: s["message_count"] for s in top_senders}
        assert sender_counts["Bob"] == 5
        assert sender_counts["Alice"] == 5
        # Bob 同时活跃于 chat_a 和 chat_b
        bob = next(s for s in top_senders if s["sender_name"] == "Bob")
        assert bob["distinct_chats"] == 2

        # hourly_by_top_contacts 应有 2 个条目，每个 hourly 长度为 24
        hourly = stats["hourly_by_top_contacts"]
        assert len(hourly) == 2
        assert all(len(item["hourly"]) == 24 for item in hourly)

    async def test_contact_activity_stats_respects_filters(self):
        """chat_id 过滤应只统计匹配的聊天"""
        db_path = await get_db_path()
        await init_database(db_path)

        messages = [
            UnifiedMessage(
                id=0,
                source=MessageSource.WECHAT_4X,
                msg_svr_id=9000 + i,
                local_id=i,
                msg_type=1,
                timestamp=1704067200 + i * 1000,
                chat_id="chat_a" if i % 2 == 0 else "chat_b",
                sender_name="Alice" if i % 2 == 0 else "Bob",
                content=f"Msg {i}",
            )
            for i in range(10)
        ]
        await insert_messages(messages)

        stats = await get_contact_activity_stats(filters={"chat_id": "chat_b"})
        assert stats["total_contacts"] == 1
        # chat_b 有 5 条（i=1,3,5,7,9），全部 Bob 发出
        assert stats["top_contacts"][0]["chat_id"] == "chat_b"
        assert stats["top_contacts"][0]["message_count"] == 5
        # 过滤后 total_senders 也只看 chat_b
        assert stats["total_senders"] == 1

    async def test_relationship_analysis_empty_db(self):
        """空数据库应返回零值结构，不报错"""
        db_path = await get_db_path()
        await init_database(db_path)

        result = await get_relationship_analysis()

        assert result["total_senders"] == 0
        assert result["total_group_chats"] == 0
        assert result["top_pairs"] == []
        assert result["sender_nodes"] == []
        assert result["edges"] == []

    async def test_relationship_analysis_detects_shared_chat(self):
        """两个发送者在同一群聊出现应产生一条关系"""
        db_path = await get_db_path()
        await init_database(db_path)

        # group_chat: Alice 与 Bob 都发过消息（群聊）
        # private_chat: 只有 Carol（单聊，无关系对）
        messages = [
            UnifiedMessage(
                id=0, source=MessageSource.WECHAT_4X, msg_svr_id=10001,
                local_id=1, msg_type=1, timestamp=1704067200,
                chat_id="group_chat", sender_name="Alice", content="hi",
            ),
            UnifiedMessage(
                id=0, source=MessageSource.WECHAT_4X, msg_svr_id=10002,
                local_id=2, msg_type=1, timestamp=1704067300,
                chat_id="group_chat", sender_name="Bob", content="hello",
            ),
            UnifiedMessage(
                id=0, source=MessageSource.WECHAT_4X, msg_svr_id=10003,
                local_id=3, msg_type=1, timestamp=1704067400,
                chat_id="group_chat", sender_name="Alice", content="again",
            ),
            UnifiedMessage(
                id=0, source=MessageSource.WECHAT_4X, msg_svr_id=10004,
                local_id=4, msg_type=1, timestamp=1704067500,
                chat_id="private_chat", sender_name="Carol", content="solo",
            ),
        ]
        await insert_messages(messages)

        result = await get_relationship_analysis()

        # 3 个 sender
        assert result["total_senders"] == 3
        # group_chat 有 2 个成员，private_chat 有 1 个 => 1 个群聊
        assert result["total_group_chats"] == 1

        # Alice-Bob 应是唯一的关系对
        pairs = result["top_pairs"]
        assert len(pairs) == 1
        pair = pairs[0]
        assert {pair["a"], pair["b"]} == {"Alice", "Bob"}
        assert pair["shared_chats"] == 1
        # Alice 2 条 + Bob 1 条 = 3
        assert pair["message_volume"] == 3
        # 强度 = 共同聊天数(1)*10 + 消息量(3) = 13
        assert pair["strength"] == 13

        # 节点应包含 Alice 和 Bob
        node_names = {n["name"] for n in result["sender_nodes"]}
        assert "Alice" in node_names
        assert "Bob" in node_names

        # 边应连接 Alice-Bob
        assert len(result["edges"]) == 1
        edge = result["edges"][0]
        assert {edge["source"], edge["target"]} == {"Alice", "Bob"}

    async def test_relationship_analysis_strength_ordering(self):
        """多个关系对应按强度降序排列"""
        db_path = await get_db_path()
        await init_database(db_path)

        # chat1: Alice + Bob（高频，2 条 each）
        # chat2: Alice + Carol（低频，1 条 each）
        messages = [
            *[
                UnifiedMessage(
                    id=0, source=MessageSource.WECHAT_4X,
                    msg_svr_id=20000 + i, local_id=i, msg_type=1,
                    timestamp=1704067200 + i,
                    chat_id="chat1",
                    sender_name="Alice" if i % 2 == 0 else "Bob",
                    content=f"m{i}",
                )
                for i in range(4)
            ],
            *[
                UnifiedMessage(
                    id=0, source=MessageSource.WECHAT_4X,
                    msg_svr_id=30000 + i, local_id=100 + i, msg_type=1,
                    timestamp=1704067200 + i,
                    chat_id="chat2",
                    sender_name="Alice" if i % 2 == 0 else "Carol",
                    content=f"c{i}",
                )
                for i in range(2)
            ],
        ]
        await insert_messages(messages)

        result = await get_relationship_analysis()

        pairs = result["top_pairs"]
        assert len(pairs) == 2
        # Alice-Bob 强度 = 1*10 + 4 = 14
        # Alice-Carol 强度 = 1*10 + 2 = 12
        # Alice-Bob 应排第一
        first = pairs[0]
        assert {first["a"], first["b"]} == {"Alice", "Bob"}
        assert pairs[0]["strength"] >= pairs[1]["strength"]
