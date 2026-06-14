"""Ollama 本地 LLM provider（隐私优先：数据不离开本机）。

文档参考：https://github.com/ollama/ollama/blob/main/docs/api.md
默认 API: http://localhost:11434/api/chat
"""
from __future__ import annotations

from typing import Any

import httpx

from app.ai.config import AIConfig
from app.ai.providers.base import (
    ChatMessage,
    ChatResponse,
    LLMProvider,
    LLMProviderError,
)


class OllamaProvider(LLMProvider):
    """Ollama 本地 provider（无需 API key）"""

    DEFAULT_BASE_URL = "http://localhost:11434"

    def __init__(self, config: AIConfig) -> None:
        super().__init__(config)
        if not config.llm_model:
            raise LLMProviderError("LIFEVAULT_LLM_MODEL is required for Ollama provider")
        self._base_url = (config.llm_base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Content-Type": "application/json"},
            timeout=config.request_timeout_seconds,
        )

    @property
    def name(self) -> str:
        return "ollama"

    async def chat_completion(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": self.config.llm_model,
            "messages": [m.to_dict() for m in messages],
            "stream": False,
            "options": {
                "temperature": temperature
                if temperature is not None
                else self.config.llm_temperature,
            },
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens
        elif self.config.llm_max_tokens:
            payload["options"]["num_predict"] = self.config.llm_max_tokens

        payload.update(kwargs)

        try:
            response = await self._client.post("/api/chat", json=payload)
        except httpx.HTTPError as exc:
            raise LLMProviderError(
                f"Ollama request failed (is the server running at {self._base_url}?): {exc}"
            ) from exc

        if response.status_code >= 400:
            raise LLMProviderError(
                f"Ollama API error {response.status_code}: {response.text[:200]}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMProviderError(
                f"Ollama returned non-JSON response: {exc}"
            ) from exc

        message = data.get("message") or {}
        return ChatResponse(
            content=message.get("content", ""),
            model=data.get("model", self.config.llm_model),
            finish_reason=data.get("done_reason", "stop" if data.get("done") else ""),
            usage={
                "prompt_eval_count": data.get("prompt_eval_count", 0),
                "eval_count": data.get("eval_count", 0),
            },
            raw=data,
        )

    async def close(self) -> None:
        await self._client.aclose()
