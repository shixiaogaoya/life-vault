import pytest
from pydantic import ValidationError

from app.models.message import MessageSource, UnifiedMessage


class TestUnifiedMessage:
    """UnifiedMessage model tests"""

    def test_create_valid_message(self):
        """Test creating a valid UnifiedMessage"""
        message = UnifiedMessage(
            id=1,
            source=MessageSource.WECHAT_4X,
            msg_svr_id=1001,
            local_id=1,
            msg_type=1,
            sub_type=0,
            timestamp=1704067200,
            chat_id="user_a",
            chat_name="User A",
            sender_id="wxid_user_a",
            sender_name="User A",
            is_sender=False,
            content="Hello",
            status=3,
            raw={},
            metadata={},
        )

        assert message.id == 1
        assert message.source == MessageSource.WECHAT_4X
        assert message.msg_svr_id == 1001
        assert message.local_id == 1
        assert message.msg_type == 1
        assert message.chat_id == "user_a"
        assert message.content == "Hello"
        assert message.is_sender is False

    def test_missing_required_field_raises_validation_error(self):
        """Test that missing required fields raise ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            UnifiedMessage(
                id=1,
                source=MessageSource.WECHAT_4X,
                msg_svr_id=1001,
                local_id=1,
                msg_type=1,
                timestamp=1704067200,
                # chat_id is missing
            )

        errors = exc_info.value.errors()
        assert len(errors) > 0
        assert any(error["loc"] == ("chat_id",) for error in errors)

    def test_empty_chat_id_raises_validation_error(self):
        """Test that empty chat_id raises ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            UnifiedMessage(
                id=1,
                source=MessageSource.WECHAT_4X,
                msg_svr_id=1001,
                local_id=1,
                msg_type=1,
                timestamp=1704067200,
                chat_id="",  # Empty chat_id
            )

        errors = exc_info.value.errors()
        assert any("chat_id" in str(error) for error in errors)

    def test_invalid_timestamp_raises_validation_error(self):
        """Test that invalid timestamp (≤0) raises ValidationError"""
        with pytest.raises(ValidationError):
            UnifiedMessage(
                id=1,
                source=MessageSource.WECHAT_4X,
                msg_svr_id=1001,
                local_id=1,
                msg_type=1,
                timestamp=0,  # Invalid timestamp
                chat_id="user_a",
            )

    def test_to_dict_serialization(self):
        """Test to_dict method serializes correctly"""
        message = UnifiedMessage(
            id=1,
            source=MessageSource.WECHAT_4X,
            msg_svr_id=1001,
            local_id=1,
            msg_type=1,
            timestamp=1704067200,
            chat_id="user_a",
            content="Test",
        )

        data = message.to_dict()
        assert isinstance(data, dict)
        assert data["id"] == 1
        assert data["source"] == "wechat_4x"
        assert data["msg_svr_id"] == 1001
        assert data["chat_id"] == "user_a"
        assert data["content"] == "Test"

    def test_from_dict_deserialization(self):
        """Test from_dict method deserializes correctly"""
        data = {
            "id": 1,
            "source": "wechat_4x",
            "msg_svr_id": 1001,
            "local_id": 1,
            "msg_type": 1,
            "sub_type": 0,
            "timestamp": 1704067200,
            "created_at": "2024-01-01T08:00:00",
            "updated_at": "2024-01-01T08:00:00",
            "chat_id": "user_a",
            "chat_name": "User A",
            "sender_id": "wxid_user_a",
            "sender_name": "User A",
            "is_sender": False,
            "content": "Test",
            "status": 3,
            "raw": {},
            "metadata": {},
        }

        message = UnifiedMessage.from_dict(data)
        assert message.id == 1
        assert message.source == MessageSource.WECHAT_4X
        assert message.msg_svr_id == 1001
        assert message.chat_id == "user_a"
        assert message.content == "Test"
