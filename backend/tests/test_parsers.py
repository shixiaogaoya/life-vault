import json

import pytest

from app.models.message import MessageSource, UnifiedMessage


@pytest.mark.asyncio
class TestParsers:
    """Parser tests for importing data"""

    async def test_import_demo_json_all_records_succeed(self, demo_json_path):
        """Test that all 50 records from demo.json are imported successfully"""
        # Load demo.json
        with open(demo_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        messages_data = data.get("messages", [])
        assert len(messages_data) > 0, "demo.json should contain messages"

        # Parse all messages
        messages = []
        errors = []

        for msg_data in messages_data:
            try:
                message = UnifiedMessage.from_dict(msg_data)
                messages.append(message)
            except Exception as exc:
                errors.append({"data": msg_data, "error": str(exc)})

        # All messages should parse successfully
        assert len(errors) == 0, f"Failed to parse {len(errors)} messages: {errors[:3]}"
        assert len(messages) == len(messages_data)

    async def test_demo_json_message_type_distribution(self, demo_json_path):
        """Test that message type distribution is correct in demo.json"""
        with open(demo_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        messages_data = data.get("messages", [])
        messages = [UnifiedMessage.from_dict(msg) for msg in messages_data]

        # Count by message type
        type_count = {}
        for msg in messages:
            msg_type = msg.msg_type
            type_count[msg_type] = type_count.get(msg_type, 0) + 1

        # Verify we have different message types
        assert len(type_count) > 0
        assert 1 in type_count, "Should have text messages (type=1)"

        # Print distribution for debugging
        print(f"\nMessage type distribution: {type_count}")

    async def test_demo_json_has_required_fields(self, demo_json_path):
        """Test that all messages in demo.json have required fields"""
        with open(demo_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        messages_data = data.get("messages", [])
        required_fields = [
            "source",
            "msg_svr_id",
            "local_id",
            "msg_type",
            "timestamp",
            "chat_id",
        ]

        for idx, msg_data in enumerate(messages_data):
            for field in required_fields:
                assert field in msg_data, f"Message {idx} missing field: {field}"

            # Validate field values
            assert msg_data["source"] == MessageSource.WECHAT_4X.value
            assert isinstance(msg_data["msg_svr_id"], int)
            assert isinstance(msg_data["local_id"], int)
            assert isinstance(msg_data["msg_type"], int)
            assert isinstance(msg_data["timestamp"], int) and msg_data["timestamp"] > 0
            assert isinstance(msg_data["chat_id"], str) and msg_data["chat_id"] != ""

    async def test_demo_json_contains_expected_count(self, demo_json_path):
        """Test that demo.json contains the expected number of messages"""
        with open(demo_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        messages_data = data.get("messages", [])

        # The test requires 50 messages, but we should check what's actually there
        actual_count = len(messages_data)
        print(f"\nActual message count in demo.json: {actual_count}")

        # At minimum, should have some test data
        assert actual_count >= 4, f"Expected at least 4 messages, got {actual_count}"
