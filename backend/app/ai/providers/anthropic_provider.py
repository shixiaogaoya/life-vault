"""Anthropic Claude LLM provider（Messages API）。

文档参考：https://docs.anthropic.com/en/api/messages
- system 字段单独传，不在 messages 数组中
- 必须显式 anthropic-version header
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


class AnthropicProvider(LLMProvider):
    """Anthropic Messages API provider"""

    DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
    DEFAULT_VERSION = "2023-06-01"

    def __init__(self, config: AIConfig) -> None:
        super().__init__(config)
        if not config.llm_api_key:
            raise LLMProviderError(
                "LIFEVAULT_LLM_API_KEY is required for Anthropic provider"
            )
        if not config.llm_model:
            raise LLMProviderError(
                "LIFEVAULT_LLM_MODEL is required for Anthropic provider"
            )
        self._base_url = (config.llm_base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "x-api-key": config.llm_api_key,
                "anthropic-version": self.DEFAULT_VERSION,
                "Content-Type": "application/json",
            },
            timeout=config.request_timeout_seconds,
        )

    @property
    def name(self) -> str:
        return "anthropic"

    async def chat_completion(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        # Anthropic: system 单独传，messages 中只允许 user/assistant
        system_parts = [m.content for m in messages if m.role == "system"]
        api_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]

        payload: dict[str, Any] = {
            "model": self.config.llm_model,
            "messages": api_messages,
            "max_tokens": max_tokens if max_tokens is not None else self.config.llm_max_tokens,
            "temperature": temperature if temperature is not None else self.config.llm_temperature,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        payload.update(kwargs)

        try:
            response = await self._client.post("/messages", json=payload)
        except httpx.HTTPError as exc:
            raise LLMProviderError(f"Anthropic request failed: {exc}") from exc

        if response.status_code >= 400:
            raise LLMProviderError(
                f"Anthropic API error {response.status_code}: {response.text[:200]}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMProviderError(
                f"Anthropic returned non-JSON response: {exc}"
            ) from exc

        try:
            content_blocks = data.get("content", [])
            text_parts = [
                block.get("text", "")
                for block in content_blocks
                if isinstance(block, dict) and block.get("type") == "text"
            ]
            return ChatResponse(
                content="".join(text_parts),
                model=data.get("model", self.config.llm_model),
                finish_reason=data.get("stop_reason", ""),
                usage=data.get("usage", {}),
                raw=data,
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMProviderError(
                f"Anthropic response missing required fields: {exc}"
            ) from exc

    async def close(self) -> None:
        await self._client.aclose()
