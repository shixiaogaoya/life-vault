import os
import json

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db import init_database
from app.main import app
from app.models.message import MessageSource


@pytest.mark.asyncio
class TestAPI:
    """API endpoint integration tests"""

    @pytest_asyncio.fixture(autouse=True)
    async def setup_db(self, tmp_path):
        """Setup database before each test"""
        db_path = tmp_path / "test_api.db"
        os.environ["LIFEVAULT_DB_PATH"] = str(db_path)
        await init_database(str(db_path))

    async def test_health_check(self):
        """Test health check endpoint"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    async def test_get_stats_returns_200(self):
        """Test GET /api/stats returns 200"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total_messages" in data
        assert "sources" in data
        assert "chat_count" in data

    async def test_get_messages_returns_200(self):
        """Test GET /api/messages returns 200"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/messages")

        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert isinstance(data["messages"], list)
        assert "total" in data
        assert "page" in data

    async def test_get_messages_with_pagination(self):
        """Test GET /api/messages with pagination parameters"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/messages?page=1&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    async def test_search_returns_200(self):
        """Test GET /api/search returns 200"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/search?q=测试")

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert isinstance(data["results"], list)
        assert "total" in data
        assert "query" in data
        assert data["query"] == "测试"

    async def test_search_without_query_returns_422(self):
        """Test GET /api/search without query parameter returns 422"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/search")

        assert response.status_code == 422  # Validation error

    async def test_export_json_returns_200(self):
        """Test GET /api/export/json returns 200"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export/json")

        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert "total" in data

    async def test_export_csv_returns_200(self):
        """Test GET /api/export/csv returns 200"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export/csv")

        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]

    async def test_import_lifevault_json_file(self):
        """Test POST /api/import accepts LifeVault JSON file uploads"""
        payload = {
            "messages": [
                {
                    "id": 0,
                    "source": MessageSource.WECHAT_4X.value,
                    "msg_svr_id": 9001,
                    "local_id": 1,
                    "msg_type": 1,
                    "sub_type": 0,
                    "timestamp": 1704067200,
                    "chat_id": "user_import",
                    "chat_name": "Import User",
                    "sender_id": "user_import",
                    "sender_name": "Import User",
                    "is_sender": False,
                    "content": "Imported from JSON upload",
                    "status": 0,
                    "raw": {},
                    "metadata": {},
                }
            ]
        }

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/import",
                files={
                    "file": (
                        "demo.json",
                        json.dumps(payload).encode("utf-8"),
                        "application/json",
                    )
                },
            )
            messages_response = await client.get("/api/messages")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_messages"] == 1
        assert data["imported"] == 1
        assert data["failed"] == 0
        assert messages_response.json()["total"] == 1

    async def test_import_lifevault_json_body(self):
        """Test POST /api/import accepts LifeVault JSON request bodies"""
        payload = {
            "messages": [
                {
                    "id": 0,
                    "source": MessageSource.WECHAT_4X.value,
                    "msg_svr_id": 9051,
                    "local_id": 51,
                    "msg_type": 1,
                    "timestamp": 1704067200,
                    "chat_id": "user_import_body",
                    "content": "Imported from JSON body",
                    "raw": {},
                    "metadata": {},
                }
            ]
        }

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/import", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_messages"] == 1
        assert data["imported"] == 1
        assert data["failed"] == 0

    async def test_export_report_returns_summary(self):
        """Test GET /api/export/report returns analysis summary"""
        payload = {
            "messages": [
                {
                    "id": 0,
                    "source": MessageSource.WECHAT_4X.value,
                    "msg_svr_id": 9101,
                    "local_id": 1,
                    "msg_type": 1,
                    "sub_type": 0,
                    "timestamp": 1704067200,
                    "chat_id": "user_report",
                    "sender_name": "Reporter",
                    "content": "Report message",
                    "raw": {},
                    "metadata": {},
                }
            ]
        }

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post(
                "/api/import",
                files={
                    "file": (
                        "report.json",
                        json.dumps(payload).encode("utf-8"),
                        "application/json",
                    )
                },
            )
            response = await client.get("/api/export/report")

        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["total_messages"] == 1
        assert data["summary"]["message_types"]["文本"] == 1
        assert data["summary"]["top_senders"][0]["name"] == "Reporter"

    async def test_visualization_stats_empty(self):
        """Test GET /api/stats/visualization returns zeroed structure on empty DB"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/stats/visualization")

        assert response.status_code == 200
        data = response.json()
        assert "activity_heatmap" in data
        assert len(data["activity_heatmap"]["matrix"]) == 7
        assert len(data["hourly_distribution"]) == 24
        assert len(data["weekday_distribution"]) == 7
        assert data["daily_timeseries"] == []
        assert data["emoji_stats"] == []
        assert data["media_type_distribution"] == {}
        assert data["sender_receiver_ratio"]["sent"] == 0

    async def test_visualization_stats_with_messages(self):
        """Test GET /api/stats/visualization aggregates imported messages"""
        payload = {
            "messages": [
                {
                    "id": 0,
                    "source": MessageSource.WECHAT_4X.value,
                    "msg_svr_id": 9201,
                    "local_id": 1,
                    "msg_type": 1,
                    "timestamp": 1704067200,  # 2024-01-01 08:00 UTC+8 (Monday)
                    "chat_id": "viz_chat",
                    "sender_name": "Alice",
                    "is_sender": False,
                    "content": "Hello 😊 world",
                    "raw": {},
                    "metadata": {},
                },
                {
                    "id": 0,
                    "source": MessageSource.WECHAT_4X.value,
                    "msg_svr_id": 9202,
                    "local_id": 2,
                    "msg_type": 1,
                    "timestamp": 1704153600,  # 2024-01-02 08:00 UTC+8 (Tuesday)
                    "chat_id": "viz_chat",
                    "sender_name": "Bob",
                    "is_sender": True,
                    "content": "Hi 😊😊",
                    "raw": {},
                    "metadata": {},
                },
            ]
        }

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/api/import", json=payload)
            response = await client.get("/api/stats/visualization")

        assert response.status_code == 200
        data = response.json()
        assert data["activity_heatmap"]["matrix"][0][8] == 1  # Monday 08:00
        assert data["activity_heatmap"]["matrix"][1][8] == 1  # Tuesday 08:00
        assert data["hourly_distribution"][8] == 2
        assert len(data["daily_timeseries"]) == 2

        emoji_map = {item["emoji"]: item["count"] for item in data["emoji_stats"]}
        assert emoji_map.get("😊") == 3

        assert data["media_type_distribution"]["文本"] == 2
        assert data["sender_receiver_ratio"]["sent"] == 1
        assert data["sender_receiver_ratio"]["received"] == 1

    async def test_visualization_stats_with_chat_filter(self):
        """Test GET /api/stats/visualization respects chat_id filter"""
        payload = {
            "messages": [
                {
                    "id": 0,
                    "source": MessageSource.WECHAT_4X.value,
                    "msg_svr_id": 9300 + i,
                    "local_id": i,
                    "msg_type": 1,
                    "timestamp": 1704067200 + i * 86400,
                    "chat_id": "chat_alpha" if i % 2 == 0 else "chat_beta",
                    "sender_name": "Alice",
                    "content": f"Message {i}",
                    "raw": {},
                    "metadata": {},
                }
                for i in range(6)
            ]
        }

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/api/import", json=payload)
            response = await client.get("/api/stats/visualization?chat_id=chat_alpha")

        assert response.status_code == 200
        data = response.json()
        # chat_alpha has i=0,2,4 => 3 messages
        total_in_heatmap = sum(sum(row) for row in data["activity_heatmap"]["matrix"])
        assert total_in_heatmap == 3

    async def test_visualization_stats_rejects_invalid_top_emoji(self):
        """Test GET /api/stats/visualization validates top_emoji range"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/stats/visualization?top_emoji=0")

        assert response.status_code == 422  # Pydantic validation error

    async def test_contact_stats_empty(self):
        """Test GET /api/stats/contacts on empty DB returns zeroed structure"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/stats/contacts")

        assert response.status_code == 200
        data = response.json()
        assert data["total_contacts"] == 0
        assert data["total_senders"] == 0
        assert data["top_contacts"] == []
        assert data["top_senders"] == []
        assert data["hourly_by_top_contacts"] == []

    async def test_contact_stats_with_messages(self):
        """Test GET /api/stats/contacts aggregates ranking correctly"""
        from app.db import insert_messages
        from app.models.message import UnifiedMessage

        messages = [
            UnifiedMessage(
                id=0,
                source=MessageSource.WECHAT_4X,
                msg_svr_id=10000 + i,
                local_id=i,
                msg_type=1,
                timestamp=1704067200 + i * 1000,
                chat_id="chat_a" if i < 6 else "chat_b",
                chat_name="Chat A" if i < 6 else "Chat B",
                sender_name="Alice" if i < 6 else "Bob",
                is_sender=i >= 6,
                content=f"Message {i}",
            )
            for i in range(10)
        ]
        await insert_messages(messages)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/stats/contacts")

        assert response.status_code == 200
        data = response.json()
        assert data["total_contacts"] == 2
        assert data["total_senders"] == 2
        # chat_a (6) 应排在 chat_b (4) 之前
        assert data["top_contacts"][0]["chat_id"] == "chat_a"
        assert data["top_contacts"][0]["message_count"] == 6
        assert data["top_contacts"][0]["chat_name"] == "Chat A"
        # hourly_by_top_contacts 包含 2 个聊天的 24 小时分布
        assert len(data["hourly_by_top_contacts"]) == 2
        assert all(len(item["hourly"]) == 24 for item in data["hourly_by_top_contacts"])

    async def test_contact_stats_rejects_invalid_limit(self):
        """Test GET /api/stats/contacts validates top_contacts range"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/stats/contacts?top_contacts=0")

        assert response.status_code == 422

    async def test_relationships_empty(self):
        """Test GET /api/stats/relationships on empty DB returns zeroed structure"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/stats/relationships")

        assert response.status_code == 200
        data = response.json()
        assert data["total_senders"] == 0
        assert data["total_group_chats"] == 0
        assert data["top_pairs"] == []
        assert data["sender_nodes"] == []
        assert data["edges"] == []

    async def test_relationships_with_shared_chat(self):
        """Test GET /api/stats/relationships detects co-participation"""
        from app.db import insert_messages
        from app.models.message import UnifiedMessage

        messages = [
            UnifiedMessage(
                id=0, source=MessageSource.WECHAT_4X, msg_svr_id=50001,
                local_id=1, msg_type=1, timestamp=1704067200,
                chat_id="group", sender_name="Alice", content="hi",
            ),
            UnifiedMessage(
                id=0, source=MessageSource.WECHAT_4X, msg_svr_id=50002,
                local_id=2, msg_type=1, timestamp=1704067300,
                chat_id="group", sender_name="Bob", content="hello",
            ),
        ]
        await insert_messages(messages)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/stats/relationships")

        assert response.status_code == 200
        data = response.json()
        assert data["total_senders"] == 2
        assert data["total_group_chats"] == 1
        assert len(data["top_pairs"]) == 1
        pair = data["top_pairs"][0]
        assert {pair["a"], pair["b"]} == {"Alice", "Bob"}
        assert pair["shared_chats"] == 1

    async def test_relationships_rejects_invalid_limit(self):
        """Test GET /api/stats/relationships validates top_pairs range"""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/stats/relationships?top_pairs=0")

        assert response.status_code == 422
