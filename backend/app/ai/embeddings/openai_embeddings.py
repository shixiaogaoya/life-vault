"""OpenAI 兼容的 embedding provider。

API: POST /v1/embeddings { model, input: [str, ...] }
返回 { data: [{ embedding: [...] }, ...] }
"""
from __future__ import annotations

from typing import Any

import httpx

from app.ai.config import AIConfig
from app.ai.embeddings.base import (
    EmbeddingProvider,
    EmbeddingProviderError,
    EmbeddingResult,
)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    MAX_BATCH_SIZE = 100  # OpenAI 限制

    def __init__(self, config: AIConfig) -> None:
        super().__init__(config)
        if not config.embedding_api_key:
            raise EmbeddingProviderError(
                "LIFEVAULT_EMBEDDING_API_KEY is required for OpenAI embedding provider"
            )
        if not config.embedding_model:
            raise EmbeddingProviderError(
                "LIFEVAULT_EMBEDDING_MODEL is required for OpenAI embedding provider"
            )
        self._base_url = (config.embedding_base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {config.embedding_api_key}",
                "Content-Type": "application/json",
            },
            timeout=config.request_timeout_seconds,
        )

    @property
    def name(self) -> str:
        return "openai"

    async def embed_texts(self, texts: list[str]) -> list[EmbeddingResult]:
        if not texts:
            return []

        results: list[EmbeddingResult] = []
        for i in range(0, len(texts), self.MAX_BATCH_SIZE):
            batch = texts[i : i + self.MAX_BATCH_SIZE]
            payload = {"model": self.config.embedding_model, "input": batch}
            try:
                response = await self._client.post("/embeddings", json=payload)
            except httpx.HTTPError as exc:
                raise EmbeddingProviderError(
                    f"OpenAI embeddings request failed: {exc}"
                ) from exc

            if response.status_code >= 400:
                raise EmbeddingProviderError(
                    f"OpenAI embeddings API error {response.status_code}: {response.text[:200]}"
                )

            try:
                data = response.json()
                data_items = data["data"]
                # 按 index 排序确保顺序
                data_items.sort(key=lambda item: item.get("index", 0))
                for item in data_items:
                    results.append(
                        EmbeddingResult(
                            vector=item["embedding"],
                            model=data.get("model", self.config.embedding_model),
                        )
                    )
            except (KeyError, TypeError, ValueError) as exc:
                raise EmbeddingProviderError(
                    f"OpenAI embeddings response invalid: {exc}"
                ) from exc

        return results

    async def close(self) -> None:
        await self._client.aclose()
