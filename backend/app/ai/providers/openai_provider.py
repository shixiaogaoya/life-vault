"""OpenAI 兼容的 LLM provider（OpenAI、DeepSeek、Moonshot 等使用相同 API 形态）。

设计：
- 直接使用 httpx.AsyncClient 调用 REST API，避免引入 openai SDK（减少依赖）
- 兼容任何 OpenAI API 形态的服务（通过 base_url 配置）
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


class OpenAIProvider(LLMProvider):
    """OpenAI 兼容 API 的 provider"""

    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    def __init__(self, config: AIConfig) -> None:
        super().__init__(config)
        if not config.llm_api_key:
            raise LLMProviderError("LIFEVAULT_LLM_API_KEY is required for OpenAI provider")
        if not config.llm_model:
            raise LLMProviderError("LIFEVAULT_LLM_MODEL is required for OpenAI provider")
        self._base_url = (config.llm_base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {config.llm_api_key}",
                "Content-Type": "application/json",
            },
            timeout=config.request_timeout_seconds,
        )

    @property
    def name(self) -> str:
        return "openai"

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
            "temperature": temperature if temperature is not None else self.config.llm_temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.config.llm_max_tokens,
        }
        payload.update(kwargs)

        try:
            response = await self._client.post("/chat/completions", json=payload)
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"OpenAI request failed: {exc}") from exc

        if response.status_code >= 400:
            raise LLMProviderError(
                f"OpenAI API error {response.status_code}: {response.text[:200]}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMProviderError(f"OpenAI returned non-JSON response: {exc}") from exc

        try:
            choice = data["choices"][0]
            message = choice["message"]
            return ChatResponse(
                content=message.get("content", ""),
                model=data.get("model", self.config.llm_model),
                finish_reason=choice.get("finish_reason", ""),
                usage=data.get("usage", {}),
                raw=data,
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(f"OpenAI response missing required fields: {exc}") from exc

    async def close(self) -> None:
        await self._client.aclose()
