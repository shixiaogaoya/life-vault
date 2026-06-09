from datetime import datetime
from enum import Enum, IntEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MessageSource(str, Enum):
    """数据源标识"""
    WECHAT_4X = "wechat_4x"


class UnifiedMessageType(IntEnum):
    """统一消息类型枚举（基于 WeChat Type 字段）"""
    UNKNOWN = -1
    TEXT = 1
    IMAGE = 3
    AUDIO = 34
    VIDEO = 43
    BUSINESS_CARD = 42
    EMOJI = 47
    POSITION = 48
    APP_MESSAGE = 49
    VOIP = 50
    OPEN_IM_CARD = 66
    SYSTEM = 10000


class UnifiedMessage(BaseModel):
    """LifeVault 统一消息模型"""

    model_config = ConfigDict(use_enum_values=False, str_strip_whitespace=True)

    id: int
    source: MessageSource
    msg_svr_id: int
    local_id: int
    msg_type: int
    sub_type: int = 0
    timestamp: int = Field(gt=0)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    chat_id: str = Field(min_length=1)
    chat_name: str = ""
    sender_id: str = ""
    sender_name: str = ""
    is_sender: bool = False
    content: str = ""
    status: int = 0
    raw: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("chat_id")
    @classmethod
    def validate_chat_id_not_empty(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("chat_id must not be empty")
        return v

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 兼容的字典"""
        data = self.model_dump(mode="python")
        data["source"] = self.source.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """从字典创建 UnifiedMessage 实例"""
        return cls.model_validate(data)
