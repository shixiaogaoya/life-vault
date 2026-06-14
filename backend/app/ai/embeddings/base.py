"""Embedding provider 抽象基类与共享数据类型。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.ai.config import AIConfig


class EmbeddingProviderError(RuntimeError):
    """Embedding provider 调用失败"""


@dataclass
class EmbeddingResult:
    """单条 embedding 结果"""

    vector: list[float]
    model: str = ""
    dimensions: int = 0

    def __post_init__(self) -> None:
        if not self.dimensions:
            self.dimensions = len(self.vector)


class EmbeddingProvider(ABC):
    """Embedding provider 抽象基类"""

    def __init__(self, config: AIConfig) -> None:
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """provider 唯一标识"""

    @property
    def model(self) -> str:
        return self.config.embedding_model

    @property
    def dimensions(self) -> int:
        return self.config.embedding_dimensions

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[EmbeddingResult]:
        """批量生成 embedding（保持输入顺序）

        参数：
            texts: 待向量化的文本列表

        返回：等长 EmbeddingResult 列表
        抛出：EmbeddingProviderError
        """

    async def embed_text(self, text: str) -> EmbeddingResult:
        """单条便捷封装"""
        results = await self.embed_texts([text])
        return results[0]

    async def close(self) -> None:
        return None
