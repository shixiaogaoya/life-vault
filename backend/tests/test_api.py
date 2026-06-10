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
