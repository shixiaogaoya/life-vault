"""Embedding provider 抽象与具体实现。"""
from app.ai.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingResult,
)

__all__ = [
    "EmbeddingProvider",
    "EmbeddingProviderError",
    "EmbeddingResult",
]
