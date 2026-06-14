"""Ollama 本地 embedding provider。

API: POST /api/embeddings { model, prompt }
返回 { embedding: [...] }
注意：Ollama 单次只能处理一条文本，需循环调用。
"""
from __future__ import annotations

import asyncio

import httpx

from app.ai.config import AIConfig
from app.ai.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingResult,
)


class OllamaEmbeddingProvider(EmbeddingProvider):
    DEFAULT_BASE_URL = "http://localhost:11434"
    MAX_CONCURRENCY = 4

    def __init__(self, config: AIConfig) -> None:
        super().__init__(config)
        if not config.embedding_model:
            raise EmbeddingProviderError(
                "LIFEVAULT_EMBEDDING_MODEL is required for Ollama embedding provider"
            )
        self._base_url = (config.embedding_base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Content-Type": "application/json"},
            timeout=config.request_timeout_seconds,
        )
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENCY)

    @property
    def name(self) -> str:
        return "ollama"

    async def _embed_single(self, text: str) -> EmbeddingResult:
        payload = {"model": self.config.embedding_model, "prompt": text}
        async with self._semaphore:
            try:
                response = await self._client.post("/api/embeddings", json=payload)
            except httpx.HTTPError as exc:
                raise EmbeddingProviderError(
                    f"Ollama embeddings request failed: {exc}"
                ) from exc

        if response.status_code >= 400:
            raise EmbeddingProviderError(
                f"Ollama embeddings API error {response.status_code}: {response.text[:200]}"
            )

        try:
            data = response.json()
            return EmbeddingResult(
                vector=data["embedding"],
                model=self.config.embedding_model,
            )
        except (KeyError, ValueError) as exc:
            raise EmbeddingProviderError(
                f"Ollama embeddings response invalid: {exc}"
            ) from exc

    async def embed_texts(self, texts: list[str]) -> list[EmbeddingResult]:
        if not texts:
            return []
        # 并发但限制并发数，避免压垮本地 Ollama
        return await asyncio.gather(*[self._embed_single(t) for t in texts])

    async def close(self) -> None:
        await self._client.aclose()
