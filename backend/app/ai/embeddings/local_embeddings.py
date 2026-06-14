"""本地 embedding provider（基于 sentence-transformers，可选依赖）。

设计要点：
- sentence-transformers 是可选依赖，未安装时构造 provider 抛 EmbeddingProviderError
- 默认模型：BAAI/bge-small-zh-v1.5（中文友好，体积小，~95MB）
- 首次加载会下载模型（除非已缓存）
"""
from __future__ import annotations

import threading
from typing import Any

from app.ai.config import AIConfig
from app.ai.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingResult,
)


DEFAULT_LOCAL_MODEL = "BAAI/bge-small-zh-v1.5"


class LocalEmbeddingProvider(EmbeddingProvider):
    """本地 sentence-transformers embedding provider"""

    _model_lock = threading.Lock()

    def __init__(self, config: AIConfig) -> None:
        super().__init__(config)
        self._resolved_model = config.embedding_model or DEFAULT_LOCAL_MODEL
        self._model: Any = None  # 延迟加载

    @property
    def name(self) -> str:
        return "local"

    @property
    def model(self) -> str:
        return self._resolved_model

    def _ensure_model(self) -> None:
        """延迟加载 sentence-transformers 模型（线程安全）"""
        if self._model is not None:
            return

        with self._model_lock:
            if self._model is not None:
                return

            try:
                # 延迟 import 避免未安装时整个 ai 模块失败
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise EmbeddingProviderError(
                    "sentence-transformers is not installed. "
                    "Install with: pip install sentence-transformers"
                ) from exc

            try:
                self._model = SentenceTransformer(self._resolved_model)
            except Exception as exc:
                raise EmbeddingProviderError(
                    f"Failed to load local embedding model '{self._resolved_model}': {exc}"
                ) from exc

    async def embed_texts(self, texts: list[str]) -> list[EmbeddingResult]:
        if not texts:
            return []

        self._ensure_model()

        # sentence-transformers 是同步 API，但在 asyncio 上下文中调用通常很快
        # 对于大批量可以考虑用 run_in_executor，但这里保持简单
        try:
            vectors = self._model.encode(texts, convert_to_numpy=True)
        except Exception as exc:
            raise EmbeddingProviderError(
                f"Local embedding inference failed: {exc}"
            ) from exc

        return [
            EmbeddingResult(
                vector=vec.tolist(),
                model=self._resolved_model,
            )
            for vec in vectors
        ]

    async def close(self) -> None:
        # 释放模型引用，便于 GC
        self._model = None
