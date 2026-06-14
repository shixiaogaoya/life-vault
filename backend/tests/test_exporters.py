import csv
import base64
import json
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from httpx import ASGITransport, AsyncClient

from app.db import init_database, insert_messages
from app.main import app
from app.models.message import MessageSource, UnifiedMessage


def _decrypt_export(content: bytes, password: str) -> tuple[dict, bytes]:
    envelope = json.loads(content.decode("utf-8"))
    salt = base64.b64decode(envelope["salt"])
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=envelope["iterations"],
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))
    plaintext = Fernet(key).decrypt(envelope["ciphertext"].encode("ascii"))
    return envelope, plaintext


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

    async def test_html_export_contains_visualization(self):
        """Test HTML export embeds heatmap, SVG charts, emoji, and term cloud"""
        from app.db import get_db_path

        db_path = await get_db_path()
        await init_database(db_path)

        await insert_messages(
            [
                UnifiedMessage(
                    id=0,
                    source=MessageSource.WECHAT_4X,
                    msg_svr_id=5210 + i,
                    local_id=i,
                    msg_type=1,
                    timestamp=1704067200 + i * 3600,
                    chat_id="user_viz",
                    sender_name="Alice" if i % 2 else "Bob",
                    is_sender=bool(i % 2),
                    content=f"Hello 😀 Python msg {i}",
                )
                for i in range(10)
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export/html")

        assert response.status_code == 200
        text = response.text
        # 可视化各组件都应出现
        assert "Activity Heatmap" in text
        assert "Hourly Distribution" in text
        assert "Weekday Distribution" in text
        assert "Daily Timeline" in text
        assert "Sender / Receiver" in text
        assert "Top Terms" in text
        assert "Top Emoji" in text
        # SVG 图表元素
        assert "<svg" in text
        # 热力图单元格
        assert 'class="cell"' in text
        # 高频词云容器
        assert 'terms-cloud' in text
        # Emoji 出现（emoji-list 容器）
        assert 'emoji-list' in text

    async def test_report_export_includes_visualization_payload(self):
        """Test /api/export/report returns visualization field"""
        from app.db import get_db_path

        db_path = await get_db_path()
        await init_database(db_path)

        await insert_messages(
            [
                UnifiedMessage(
                    id=0,
                    source=MessageSource.WECHAT_4X,
                    msg_svr_id=5301,
                    local_id=1,
                    msg_type=1,
                    timestamp=1704067200,
                    chat_id="user_rpt",
                    sender_name="Reporter",
                    content="Report 😀 message",
                )
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export/report")

        assert response.status_code == 200
        data = response.json()
        assert "visualization" in data
        viz = data["visualization"]
        assert "activity_heatmap" in viz
        assert "hourly_distribution" in viz
        assert "weekday_distribution" in viz
        assert "daily_timeseries" in viz
        assert "emoji_stats" in viz
        assert "top_terms" in viz
        assert "sender_receiver_ratio" in viz
        assert viz["sender_receiver_ratio"]["received"] == 1

    async def test_json_export_can_anonymize_for_sharing(self):
        """Test JSON export replaces names, strips location metadata, and sanitizes paths."""
        from app.db import get_db_path

        db_path = await get_db_path()
        await init_database(db_path)

        await insert_messages(
            [
                UnifiedMessage(
                    id=0,
                    source=MessageSource.WECHAT_4X,
                    msg_svr_id=5301,
                    local_id=301,
                    msg_type=1,
                    timestamp=1704067200,
                    chat_id="room_sensitive",
                    chat_name="Project Chat",
                    sender_id="alice_id",
                    sender_name="Alice",
                    content="Alice shared C:\\Users\\alice\\secret.txt with Project Chat",
                    raw={
                        "path": "C:\\Users\\alice\\secret.txt",
                        "location": {"latitude": 39.9, "longitude": 116.4},
                    },
                    metadata={"address": "北京市朝阳区望京街道1号"},
                ),
                UnifiedMessage(
                    id=0,
                    source=MessageSource.WECHAT_4X,
                    msg_svr_id=5302,
                    local_id=302,
                    msg_type=1,
                    timestamp=1704067201,
                    chat_id="room_sensitive",
                    chat_name="Project Chat",
                    sender_id="alice_id",
                    sender_name="Alice",
                    content="Alice followed up",
                ),
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export/json?anonymize=true")

        assert response.status_code == 200
        result = response.json()
        body = json.dumps(result, ensure_ascii=False)
        messages = [
            message
            for message in result["messages"]
            if message["msg_svr_id"] in (5301, 5302)
        ]

        assert result["anonymization"]["enabled"] is True
        assert len(messages) == 2
        assert {message["sender_name"] for message in messages} == {"Person 1"}
        assert {message["sender_id"] for message in messages} == {"Person 1"}
        assert {message["chat_name"] for message in messages} == {"Chat 1"}
        assert "Alice" not in body
        assert "Project Chat" not in body
        assert "C:\\Users\\alice" not in body
        assert "39.9" not in body
        assert "116.4" not in body
        assert "北京市朝阳区望京街道1号" not in body
        assert "[PATH]" in body
        assert "[LOCATION_REMOVED]" in body

    async def test_report_export_anonymizes_top_senders(self):
        """Test report summaries use pseudonyms when anonymization is enabled."""
        from app.db import get_db_path

        db_path = await get_db_path()
        await init_database(db_path)

        await insert_messages(
            [
                UnifiedMessage(
                    id=0,
                    source=MessageSource.WECHAT_4X,
                    msg_svr_id=5303,
                    local_id=303,
                    msg_type=48,
                    timestamp=1704067200,
                    chat_id="location_chat",
                    chat_name="Location Chat",
                    sender_name="Bob",
                    content="Bob sent location 北京市朝阳区望京街道1号",
                    raw={"latitude": 39.9, "longitude": 116.4},
                )
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export/report?anonymize=true")

        assert response.status_code == 200
        result = response.json()
        body = json.dumps(result, ensure_ascii=False)

        assert result["summary"]["top_senders"][0]["name"] == "Person 1"
        assert result["messages"][0]["content"] == "[LOCATION_REMOVED]"
        assert "Bob" not in body
        assert "北京市朝阳区望京街道1号" not in body

    async def test_json_export_can_be_password_protected(self):
        """Test JSON export is encrypted when a password is provided."""
        from app.db import get_db_path

        db_path = await get_db_path()
        await init_database(db_path)

        await insert_messages(
            [
                UnifiedMessage(
                    id=0,
                    source=MessageSource.WECHAT_4X,
                    msg_svr_id=5401,
                    local_id=401,
                    msg_type=1,
                    timestamp=1704067200,
                    chat_id="encrypted_json_chat",
                    content="secret json export content",
                )
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export/json?encrypt_password=test-pass")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith(
            "application/vnd.lifevault.encrypted+json"
        )
        assert "messages_all.lvenc" in response.headers["content-disposition"]
        assert b"secret json export content" not in response.content

        envelope, plaintext = _decrypt_export(response.content, "test-pass")
        payload = json.loads(plaintext.decode("utf-8"))
        assert envelope["format"] == "lifevault-encrypted-export-v1"
        assert envelope["payload_format"] == "json"
        assert any(
            message["content"] == "secret json export content"
            for message in payload["messages"]
        )

    async def test_csv_export_can_be_password_protected(self):
        """Test CSV export is encrypted when a password is provided."""
        from app.db import get_db_path

        db_path = await get_db_path()
        await init_database(db_path)

        await insert_messages(
            [
                UnifiedMessage(
                    id=0,
                    source=MessageSource.WECHAT_4X,
                    msg_svr_id=5402,
                    local_id=402,
                    msg_type=1,
                    timestamp=1704067200,
                    chat_id="encrypted_csv_chat",
                    content="secret csv export content",
                )
            ]
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export/csv?encrypt_password=test-pass")

        assert response.status_code == 200
        assert "messages_all.lvenc" in response.headers["content-disposition"]
        assert b"secret csv export content" not in response.content

        envelope, plaintext = _decrypt_export(response.content, "test-pass")
        csv_text = plaintext.decode("utf-8-sig")
        assert envelope["payload_format"] == "csv"
        assert "secret csv export content" in csv_text

    async def test_password_protected_export_rejects_empty_password(self):
        """Test encrypted exports require a non-empty password."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export/json?encrypt_password=")

        assert response.status_code == 400
        assert "must not be empty" in response.text

    async def test_password_protected_export_rejects_unsupported_formats(self):
        """Test password protection is limited to JSON and CSV exports."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export/html?encrypt_password=test-pass")

        assert response.status_code == 400
        assert "only supported for JSON and CSV" in response.text

    async def test_json_export_can_be_gpg_encrypted(self, monkeypatch):
        """Test JSON export can be encrypted for a GPG recipient."""
        from app.db import get_db_path
        from app.routers import export as export_router

        db_path = await get_db_path()
        await init_database(db_path)

        await insert_messages(
            [
                UnifiedMessage(
                    id=0,
                    source=MessageSource.WECHAT_4X,
                    msg_svr_id=5403,
                    local_id=403,
                    msg_type=1,
                    timestamp=1704067200,
                    chat_id="gpg_json_chat",
                    content="secret gpg json content",
                )
            ]
        )

        captured = {}

        def fake_run(command, input, capture_output, check):
            captured["command"] = command
            captured["input"] = input
            captured["capture_output"] = capture_output
            captured["check"] = check
            return SimpleNamespace(returncode=0, stdout=b"gpg-ciphertext", stderr=b"")

        monkeypatch.setattr(export_router.shutil, "which", lambda name: "gpg.exe")
        monkeypatch.setattr(export_router.subprocess, "run", fake_run)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export/json?gpg_recipient=alice@example.com")

        assert response.status_code == 200
        assert response.content == b"gpg-ciphertext"
        assert "messages_all.json.gpg" in response.headers["content-disposition"]
        assert "--recipient" in captured["command"]
        assert "alice@example.com" in captured["command"]
        assert b"secret gpg json content" in captured["input"]
        assert captured["capture_output"] is True
        assert captured["check"] is False

    async def test_csv_export_can_be_gpg_encrypted(self, monkeypatch):
        """Test CSV export can be encrypted for a GPG recipient."""
        from app.db import get_db_path
        from app.routers import export as export_router

        db_path = await get_db_path()
        await init_database(db_path)

        await insert_messages(
            [
                UnifiedMessage(
                    id=0,
                    source=MessageSource.WECHAT_4X,
                    msg_svr_id=5404,
                    local_id=404,
                    msg_type=1,
                    timestamp=1704067200,
                    chat_id="gpg_csv_chat",
                    content="secret gpg csv content",
                )
            ]
        )

        captured = {}

        def fake_run(command, input, capture_output, check):
            captured["input"] = input
            return SimpleNamespace(returncode=0, stdout=b"csv-gpg-ciphertext", stderr=b"")

        monkeypatch.setattr(export_router.shutil, "which", lambda name: "gpg.exe")
        monkeypatch.setattr(export_router.subprocess, "run", fake_run)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export/csv?gpg_recipient=alice@example.com")

        assert response.status_code == 200
        assert response.content == b"csv-gpg-ciphertext"
        assert "messages_all.csv.gpg" in response.headers["content-disposition"]
        assert b"secret gpg csv content" in captured["input"]

    async def test_gpg_export_rejects_empty_recipient(self):
        """Test GPG exports require a non-empty recipient."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export/json?gpg_recipient=")

        assert response.status_code == 400
        assert "gpg_recipient must not be empty" in response.text

    async def test_export_rejects_multiple_encryption_modes(self):
        """Test password and GPG encryption modes are mutually exclusive."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/export/json?encrypt_password=test-pass&gpg_recipient=alice@example.com"
            )

        assert response.status_code == 400
        assert "Choose either encrypt_password or gpg_recipient" in response.text

    async def test_gpg_export_reports_missing_executable(self, monkeypatch):
        """Test GPG exports report missing local gpg executable."""
        from app.db import get_db_path
        from app.routers import export as export_router

        db_path = await get_db_path()
        await init_database(db_path)

        monkeypatch.setattr(export_router.shutil, "which", lambda name: None)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/export/json?gpg_recipient=alice@example.com")

        assert response.status_code == 400
        assert "gpg executable was not found" in response.text
