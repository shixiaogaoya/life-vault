import csv
import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.db import init_database, insert_messages
from app.main import app
from app.models.message import MessageSource, UnifiedMessage


@pytest.mark.asyncio
class TestExporters:
    """Exporter tests for JSON, CSV, and HTML formats"""

    async def test_json_export_no_error(self):
        """Test JSON export completes without error"""
        from app.db import get_db_path

        db_path = await get_db_path()
        await init_database(db_path)

        messages = [
            UnifiedMessage(
                id=0,
                source=MessageSource.WECHAT_4X,
                msg_svr_id=5001,
                local_id=1,
                msg_type=1,
                timestamp=1704067200,
                chat_id="user_a",
                content="Test export",
            )
        ]
        await insert_messages(messages)

        # Export JSON via API
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export/json")

        assert response.status_code == 200
        result = response.json()
        assert isinstance(result, dict)
        assert "messages" in result
        assert "total" in result
        assert result["total"] > 0

    async def test_json_export_can_be_parsed(self):
        """Test that JSON export can be parsed by json.loads"""
        from app.db import get_db_path

        db_path = await get_db_path()
        await init_database(db_path)

        messages = [
            UnifiedMessage(
                id=0,
                source=MessageSource.WECHAT_4X,
                msg_svr_id=5002,
                local_id=2,
                msg_type=1,
                timestamp=1704067200,
                chat_id="user_b",
                content="JSON test",
            )
        ]
        await insert_messages(messages)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export/json")

        assert response.status_code == 200
        result = response.json()
        json_str = json.dumps(result)
        parsed = json.loads(json_str)

        assert parsed["total"] == result["total"]
        assert len(parsed["messages"]) == len(result["messages"])

    async def test_csv_export_no_error(self):
        """Test CSV export completes without error"""
        from app.db import get_db_path

        db_path = await get_db_path()
        await init_database(db_path)

        messages = [
            UnifiedMessage(
                id=0,
                source=MessageSource.WECHAT_4X,
                msg_svr_id=5003,
                local_id=3,
                msg_type=1,
                timestamp=1704067200,
                chat_id="user_c",
                content="CSV test",
            )
        ]
        await insert_messages(messages)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export/csv")

        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]

    async def test_csv_export_utf8_bom_encoding(self):
        """Test that CSV export uses UTF-8-BOM encoding"""
        from app.db import get_db_path

        db_path = await get_db_path()
        await init_database(db_path)

        messages = [
            UnifiedMessage(
                id=0,
                source=MessageSource.WECHAT_4X,
                msg_svr_id=5004,
                local_id=4,
                msg_type=1,
                timestamp=1704067200,
                chat_id="user_d",
                content="中文测试",
            )
        ]
        await insert_messages(messages)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export/csv")

        assert response.status_code == 200
        body_bytes = response.content

        # Check for UTF-8 BOM
        assert body_bytes.startswith(b"\xef\xbb\xbf"), "CSV should start with UTF-8 BOM"

        # Verify it can be decoded
        csv_text = body_bytes.decode("utf-8-sig")
        assert "中文测试" in csv_text

    async def test_csv_export_valid_format(self):
        """Test that CSV export produces valid CSV format"""
        from app.db import get_db_path

        db_path = await get_db_path()
        await init_database(db_path)

        messages = [
            UnifiedMessage(
                id=0,
                source=MessageSource.WECHAT_4X,
                msg_svr_id=5005,
                local_id=5,
                msg_type=1,
                timestamp=1704067200,
                chat_id="user_e",
                content="CSV format test",
            )
        ]
        await insert_messages(messages)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export/csv")

        assert response.status_code == 200
        body_bytes = response.content
        csv_text = body_bytes.decode("utf-8-sig")

        # Parse CSV
        lines = csv_text.strip().split("\n")
        reader = csv.DictReader(lines)
        rows = list(reader)

        assert len(rows) > 0
        assert "id" in rows[0]
        assert "content" in rows[0]
        assert "chat_id" in rows[0]

    async def test_json_export_can_mask_sensitive_data(self):
        """Test JSON export masks sensitive data when requested"""
        from app.db import get_db_path

        db_path = await get_db_path()
        await init_database(db_path)

        await insert_messages(
            [
                UnifiedMessage(
                    id=0,
                    source=MessageSource.WECHAT_4X,
                    msg_svr_id=5101,
                    local_id=101,
                    msg_type=1,
                    timestamp=1704067200,
                    chat_id="user_mask_json",
                    chat_name="Alice",
                    sender_name="Alice",
                    content=(
                        "Alice 手机 13812345678 身份证 11010119900101123X "
                        "邮箱 alice@example.com 文件 C:\\Users\\alice\\a.txt"
                    ),
                    raw={"path": "C:\\Users\\alice\\raw.txt"},
                    metadata={"note": "Alice"},
                )
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/export/json?mask_sensitive=true&mask_terms=Alice"
            )

        assert response.status_code == 200
        result = response.json()
        body = json.dumps(result, ensure_ascii=False)

        assert result["privacy"]["enabled"] is True
        assert "13812345678" not in body
        assert "11010119900101123X" not in body
        assert "alice@example.com" not in body
        assert "C:\\Users\\alice" not in body
        assert "Alice" not in body
        assert "138****5678" in body
        assert "110101********123X" in body
        assert "a***@example.com" in body

    async def test_csv_export_can_mask_sensitive_data(self):
        """Test CSV export masks sensitive data when requested"""
        from app.db import get_db_path

        db_path = await get_db_path()
        await init_database(db_path)

        await insert_messages(
            [
                UnifiedMessage(
                    id=0,
                    source=MessageSource.WECHAT_4X,
                    msg_svr_id=5102,
                    local_id=102,
                    msg_type=1,
                    timestamp=1704067200,
                    chat_id="user_mask_csv",
                    sender_name="Bob",
                    content="Bob 手机 13900001111",
                )
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/export/csv?mask_sensitive=true&mask_terms=Bob"
            )

        assert response.status_code == 200
        csv_text = response.content.decode("utf-8-sig")
        assert "13900001111" not in csv_text
        assert "Bob" not in csv_text
        assert "139****1111" in csv_text
        assert "[MASKED]" in csv_text

    async def test_report_export_masks_top_senders(self):
        """Test report export uses masked sender names in summary"""
        from app.db import get_db_path

        db_path = await get_db_path()
        await init_database(db_path)

        await insert_messages(
            [
                UnifiedMessage(
                    id=0,
                    source=MessageSource.WECHAT_4X,
                    msg_svr_id=5103,
                    local_id=103,
                    msg_type=1,
                    timestamp=1704067200,
                    chat_id="user_mask_report",
                    sender_name="Carol",
                    content="Carol 邮箱 carol@example.com",
                )
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/export/report?mask_sensitive=true&mask_terms=Carol"
            )

        assert response.status_code == 200
        result = response.json()
        body = json.dumps(result, ensure_ascii=False)
        assert result["summary"]["top_senders"][0]["name"] == "[MASKED]"
        assert "Carol" not in body
        assert "carol@example.com" not in body

    async def test_markdown_export_generates_chat_log(self):
        """Test Markdown export produces a structured chat log"""
        from app.db import get_db_path

        db_path = await get_db_path()
        await init_database(db_path)

        await insert_messages(
            [
                UnifiedMessage(
                    id=0,
                    source=MessageSource.WECHAT_4X,
                    msg_svr_id=5201,
                    local_id=201,
                    msg_type=1,
                    timestamp=1704067200,
                    chat_id="user_markdown",
                    chat_name="Markdown Chat",
                    sender_name="Dora",
                    content="Dora 手机 13812345678",
                )
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/export/markdown?mask_sensitive=true&mask_terms=Dora"
            )

        assert response.status_code == 200
        assert "text/markdown" in response.headers["content-type"]
        text = response.text
        assert "# LifeVault Chat Export" in text
        assert "Markdown Chat" in text
        assert "13812345678" not in text
        assert "Dora" not in text
        assert "138****5678" in text
        assert "[MASKED]" in text

    async def test_html_export_generates_escaped_report(self):
        """Test HTML export produces an escaped self-contained report"""
        from app.db import get_db_path

        db_path = await get_db_path()
        await init_database(db_path)

        await insert_messages(
            [
                UnifiedMessage(
                    id=0,
                    source=MessageSource.WECHAT_4X,
                    msg_svr_id=5202,
                    local_id=202,
                    msg_type=1,
                    timestamp=1704067200,
                    chat_id="user_html",
                    chat_name="HTML Chat",
                    sender_name="Eve",
                    content="Eve <script>alert(1)</script> 13900001111",
                )
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/export/html?mask_sensitive=true&mask_terms=Eve"
            )

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        text = response.text
        assert "<!doctype html>" in text
        assert "LifeVault Export Report" in text
        assert "<script>alert(1)</script>" not in text
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text
        assert "13900001111" not in text
        assert "Eve" not in text
        assert "139****1111" in text
