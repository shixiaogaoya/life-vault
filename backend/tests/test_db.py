import pytest

from app.db import (
    count_messages,
    get_db_path,
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
