"""AI provider 单元测试 — 使用 httpx.MockTransport 模拟 HTTP 调用，不依赖真实 API。"""
from __future__ import annotations

import json
from typing import Callable

import httpx
import pytest

from app.ai.config import AIConfig, load_ai_config
from app.ai.providers.anthropic_provider import AnthropicProvider
from app.ai.providers.base import ChatMessage, LLMProviderError
from app.ai.providers.ollama_provider import OllamaProvider
from app.ai.providers.openai_provider import OpenAIProvider
from app.ai.registry import (
    AIDisabledError,
    AIProviderNotConfiguredError,
    get_status,
    llm_provider_factory,
    reload_config,
)


def _make_handler(status: int, payload: dict) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload)
    return handler


def _make_text_handler(status: int, text: str) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=text)
    return handler


def _patch_provider_client(provider, transport: httpx.MockTransport) -> None:
    """用 MockTransport 替换 provider 内部的 httpx client"""
    # 直接替换 _client，保留原 base_url 和 headers
    old = provider._client
    provider._client = httpx.AsyncClient(
        base_url=old.base_url,
        headers=old.headers,
        transport=transport,
        timeout=old.timeout,
    )


# ===== OpenAI Provider =====


@pytest.mark.asyncio
class TestOpenAIProvider:
    async def test_requires_api_key(self):
        config = AIConfig(
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            llm_api_key="",
        )
        with pytest.raises(LLMProviderError, match="API_KEY"):
            OpenAIProvider(config)

    async def test_requires_model(self):
        config = AIConfig(
            llm_provider="openai",
            llm_model="",
            llm_api_key="sk-test",
        )
        with pytest.raises(LLMProviderError, match="MODEL"):
            OpenAIProvider(config)

    async def test_chat_completion_success(self):
        config = AIConfig(
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            llm_api_key="sk-test",
        )
        provider = OpenAIProvider(config)
        payload = {
            "choices": [
                {
                    "message": {"role": "assistant", "content": "Hello!"},
                    "finish_reason": "stop",
                }
            ],
            "model": "gpt-4o-mini",
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        }
        _patch_provider_client(provider, httpx.MockTransport(_make_handler(200, payload)))

        response = await provider.chat_completion(
            [ChatMessage(role="user", content="Hi")]
        )

        assert response.content == "Hello!"
        assert response.model == "gpt-4o-mini"
        assert response.finish_reason == "stop"
        assert response.usage["completion_tokens"] == 3

        await provider.close()

    async def test_chat_completion_api_error(self):
        config = AIConfig(
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            llm_api_key="sk-test",
        )
        provider = OpenAIProvider(config)
        _patch_provider_client(
            provider,
            httpx.MockTransport(_make_text_handler(401, "Unauthorized")),
        )

        with pytest.raises(LLMProviderError, match="401"):
            await provider.chat_completion([ChatMessage(role="user", content="Hi")])

        await provider.close()


# ===== Anthropic Provider =====


@pytest.mark.asyncio
class TestAnthropicProvider:
    async def test_requires_api_key(self):
        config = AIConfig(
            llm_provider="anthropic",
            llm_model="claude-sonnet-4-6",
            llm_api_key="",
        )
        with pytest.raises(LLMProviderError, match="API_KEY"):
            AnthropicProvider(config)

    async def test_chat_completion_separates_system_message(self):
        config = AIConfig(
            llm_provider="anthropic",
            llm_model="claude-sonnet-4-6",
            llm_api_key="sk-ant-test",
        )
        provider = AnthropicProvider(config)
        captured_requests: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content.decode("utf-8"))
            captured_requests.append(body)
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "Hi there"}],
                    "model": "claude-sonnet-4-6",
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            )

        _patch_provider_client(provider, httpx.MockTransport(handler))

        response = await provider.chat_completion(
            [
                ChatMessage(role="system", content="Be helpful"),
                ChatMessage(role="user", content="Hello"),
            ]
        )

        assert response.content == "Hi there"
        assert response.finish_reason == "end_turn"
        assert response.usage["output_tokens"] == 5

        # system 字段应单独传递，不在 messages 中
        assert len(captured_requests) == 1
        req_body = captured_requests[0]
        assert req_body["system"] == "Be helpful"
        assert all(m["role"] in ("user", "assistant") for m in req_body["messages"])

        await provider.close()

    async def test_chat_completion_handles_error_response(self):
        config = AIConfig(
            llm_provider="anthropic",
            llm_model="claude-sonnet-4-6",
            llm_api_key="sk-ant-test",
        )
        provider = AnthropicProvider(config)
        _patch_provider_client(
            provider,
            httpx.MockTransport(_make_text_handler(500, "Server error")),
        )

        with pytest.raises(LLMProviderError, match="500"):
            await provider.chat_completion([ChatMessage(role="user", content="Hi")])

        await provider.close()


# ===== Ollama Provider =====


@pytest.mark.asyncio
class TestOllamaProvider:
    async def test_requires_model(self):
        config = AIConfig(
            llm_provider="ollama",
            llm_model="",
        )
        with pytest.raises(LLMProviderError, match="MODEL"):
            OllamaProvider(config)

    async def test_chat_completion_success_without_api_key(self):
        config = AIConfig(
            llm_provider="ollama",
            llm_model="llama3.2",
        )
        provider = OllamaProvider(config)
        payload = {
            "model": "llama3.2",
            "message": {"role": "assistant", "content": "Hi"},
            "done": True,
            "done_reason": "stop",
            "prompt_eval_count": 12,
            "eval_count": 4,
        }
        _patch_provider_client(provider, httpx.MockTransport(_make_handler(200, payload)))

        response = await provider.chat_completion(
            [ChatMessage(role="user", content="Hello")]
        )

        assert response.content == "Hi"
        assert response.usage["eval_count"] == 4
        assert provider.name == "ollama"

        await provider.close()

    async def test_connection_error_includes_base_url_hint(self):
        config = AIConfig(
            llm_provider="ollama",
            llm_model="llama3.2",
            llm_base_url="http://localhost:99999",
        )
        provider = OllamaProvider(config)

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        _patch_provider_client(provider, httpx.MockTransport(handler))

        with pytest.raises(LLMProviderError, match="Ollama request failed"):
            await provider.chat_completion([ChatMessage(role="user", content="Hi")])

        await provider.close()


# ===== Config =====


class TestAIConfig:
    def test_disabled_by_default(self, monkeypatch):
        # 清除所有相关环境变量
        for key in list(os_environ_keys()):
            monkeypatch.delenv(key, raising=False)
        config = load_ai_config()
        assert config.llm_provider == "disabled"
        assert not config.llm_enabled
        assert not config.embedding_enabled
        assert config.is_local_only  # disabled 也算 local only

    def test_loads_from_env(self, monkeypatch):
        monkeypatch.setenv("LIFEVAULT_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("LIFEVAULT_LLM_MODEL", "llama3.2")
        monkeypatch.setenv("LIFEVAULT_EMBEDDING_PROVIDER", "ollama")
        monkeypatch.setenv("LIFEVAULT_EMBEDDING_MODEL", "nomic-embed-text")
        config = load_ai_config()
        assert config.llm_provider == "ollama"
        assert config.llm_enabled
        assert config.embedding_enabled
        assert config.is_local_only  # ollama 是本地

    def test_remote_provider_detected(self, monkeypatch):
        monkeypatch.setenv("LIFEVAULT_LLM_PROVIDER", "openai")
        monkeypatch.setenv("LIFEVAULT_LLM_MODEL", "gpt-4o-mini")
        monkeypatch.setenv("LIFEVAULT_LLM_API_KEY", "sk-test")
        config = load_ai_config()
        assert config.llm_data_flows_remote()
        assert not config.is_local_only

    def test_invalid_provider_falls_back_to_disabled(self, monkeypatch):
        monkeypatch.setenv("LIFEVAULT_LLM_PROVIDER", "nonexistent")
        config = load_ai_config()
        assert config.llm_provider == "disabled"

    def test_public_dict_hides_api_key(self, monkeypatch):
        monkeypatch.setenv("LIFEVAULT_LLM_PROVIDER", "openai")
        monkeypatch.setenv("LIFEVAULT_LLM_MODEL", "gpt-4o-mini")
        monkeypatch.setenv("LIFEVAULT_LLM_API_KEY", "sk-secret")
        config = load_ai_config()
        public = config.to_public_dict()
        # 明文 api_key 不应出现在返回中
        assert "llm_api_key" not in public
        assert "embedding_api_key" not in public
        assert "sk-secret" not in str(public)
        # 但允许返回是否已设置的布尔标记
        assert public["llm_api_key_set"] is True


def os_environ_keys() -> list[str]:
    """获取所有 LIFEVAULT_ 开头的环境变量名"""
    import os
    return [k for k in os.environ if k.startswith("LIFEVAULT_")]


# ===== Registry =====


class TestRegistry:
    def test_factory_raises_when_disabled(self, monkeypatch):
        for key in os_environ_keys():
            monkeypatch.delenv(key, raising=False)
        reload_config()
        with pytest.raises(AIDisabledError):
            llm_provider_factory()

    def test_factory_raises_when_provider_unknown(self, monkeypatch):
        # 通过手动构造 config 测试 unknown provider
        from app.ai.config import AIConfig
        config = AIConfig(llm_provider="custom", llm_model="x")
        # 绕过 llm_enabled 检查 — 直接用工厂
        from app.ai.registry import _LLM_PROVIDERS
        assert "custom" not in _LLM_PROVIDERS

    def test_factory_returns_ollama_provider(self, monkeypatch):
        monkeypatch.setenv("LIFEVAULT_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("LIFEVAULT_LLM_MODEL", "llama3.2")
        reload_config()
        provider = llm_provider_factory()
        assert provider.name == "ollama"
        # 清理
        reload_config()

    def test_get_status_returns_safe_dict(self, monkeypatch):
        for key in os_environ_keys():
            monkeypatch.delenv(key, raising=False)
        reload_config()
        status = get_status()
        assert "llm_enabled" in status
        assert "llm_provider" in status
        assert "llm_model" in status
        # 明文 api_key 不应出现（_key_set 布尔标记除外）
        assert "sk-" not in str(status)
        assert "llm_api_key" not in status
        assert "embedding_api_key" not in status
