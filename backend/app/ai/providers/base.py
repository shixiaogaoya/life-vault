"""LLM provider 抽象基类与共享数据类型。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.ai.config import AIConfig


class LLMProviderError(RuntimeError):
    """LLM provider 调用失败"""


@dataclass
class ChatMessage:
    """统一的聊天消息表示"""

    role: str  # "system" | "user" | "assistant"
    content: str

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class ChatResponse:
    """统一的聊天响应表示"""

    content: str
    model: str = ""
    finish_reason: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


class LLMProvider(ABC):
    """LLM provider 抽象基类

    所有方法都是 async 的，子类需要实现 chat_completion。
    具体子类应通过 DI 接收 AIConfig，避免全局状态。
    """

    def __init__(self, config: AIConfig) -> None:
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """provider 唯一标识（用于日志和状态展示）"""

    @property
    def model(self) -> str:
        return self.config.llm_model

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """执行聊天补全

        参数：
            messages: 对话历史（system/user/assistant）
            temperature: 0.0-2.0，覆盖配置默认值
            max_tokens: 覆盖配置默认值

        返回：ChatResponse
        抛出：LLMProviderError
        """

    async def close(self) -> None:
        """清理资源（如 HTTP client）"""
        return None
