"""AI provider 注册表 — 根据 AIConfig 选择并构造 LLM/Embedding provider。

公共 API：
- llm_provider_factory(): 工厂函数，返回 LLMProvider 实例（若禁用则抛 AIDisabledError）
- embedding_provider_factory(): 工厂函数，返回 EmbeddingProvider 实例
- get_status(): 返回当前 AI 模块的状态字典
"""
from __future__ import annotations

from functools import lru_cache
from typing import Callable

from app.ai.config import AIConfig, clear_ai_config, load_ai_config, save_ai_config
from app.ai.embeddings.base import EmbeddingProvider, EmbeddingProviderError
from app.ai.embeddings.local_embeddings import LocalEmbeddingProvider
from app.ai.embeddings.ollama_embeddings import OllamaEmbeddingProvider
from app.ai.embeddings.openai_embeddings import OpenAIEmbeddingProvider
from app.ai.providers.anthropic_provider import AnthropicProvider
from app.ai.providers.base import LLMProvider, LLMProviderError
from app.ai.providers.ollama_provider import OllamaProvider
from app.ai.providers.openai_provider import OpenAIProvider


class AIDisabledError(RuntimeError):
    """AI 模块未启用"""


class AIProviderNotConfiguredError(RuntimeError):
    """provider 配置不完整"""


# provider 名称 -> 工厂函数
_LLM_PROVIDERS: dict[str, Callable[[AIConfig], LLMProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
}

_EMBEDDING_PROVIDERS: dict[str, Callable[[AIConfig], EmbeddingProvider]] = {
    "openai": OpenAIEmbeddingProvider,
    "ollama": OllamaEmbeddingProvider,
    "local": LocalEmbeddingProvider,
}


@lru_cache(maxsize=1)
def _cached_config() -> AIConfig:
    """启动时一次性加载配置（避免每次请求读环境变量）"""
    return load_ai_config()


def reload_config() -> AIConfig:
    """强制重新加载配置（用于测试或运行时切换 provider）"""
    _cached_config.cache_clear()
    return _cached_config()


def apply_config(updates: dict) -> AIConfig:
    """保存用户配置到文件并立即生效（清缓存 + 返回新配置）。

    供 /api/ai/config PUT 调用：写入 ai_config.json 后清 lru_cache，
    下次 get_config() 拿到新值，无需重启服务。
    """
    save_ai_config(updates)
    return reload_config()


def reset_config() -> AIConfig:
    """删除配置文件，恢复到环境变量 / 默认值"""
    clear_ai_config()
    return reload_config()


def get_config() -> AIConfig:
    """获取当前 AI 配置（缓存）"""
    return _cached_config()


def llm_provider_factory(config: AIConfig | None = None) -> LLMProvider:
    """构造 LLM provider 实例

    参数：
        config: 可选，默认从环境变量加载

    抛出：
        AIDisabledError: AI 模块未启用
        AIProviderNotConfiguredError: provider 配置不完整
    """
    cfg = config or get_config()

    if not cfg.llm_enabled:
        raise AIDisabledError(
            "AI module is disabled. Set LIFEVAULT_LLM_PROVIDER and LIFEVAULT_LLM_MODEL to enable."
        )

    factory = _LLM_PROVIDERS.get(cfg.llm_provider)
    if factory is None:
        raise AIProviderNotConfiguredError(
            f"Unknown LLM provider: {cfg.llm_provider}. "
            f"Supported: {sorted(_LLM_PROVIDERS.keys())}"
        )

    try:
        return factory(cfg)
    except LLMProviderError as exc:
        raise AIProviderNotConfiguredError(str(exc)) from exc


def embedding_provider_factory(config: AIConfig | None = None) -> EmbeddingProvider:
    """构造 embedding provider 实例

    抛出：
        AIDisabledError: embedding 模块未启用
        AIProviderNotConfiguredError: provider 配置不完整
    """
    cfg = config or get_config()

    if not cfg.embedding_enabled:
        raise AIDisabledError(
            "Embedding module is disabled. Set LIFEVAULT_EMBEDDING_PROVIDER and "
            "LIFEVAULT_EMBEDDING_MODEL to enable."
        )

    factory = _EMBEDDING_PROVIDERS.get(cfg.embedding_provider)
    if factory is None:
        raise AIProviderNotConfiguredError(
            f"Unknown embedding provider: {cfg.embedding_provider}. "
            f"Supported: {sorted(_EMBEDDING_PROVIDERS.keys())}"
        )

    try:
        return factory(cfg)
    except EmbeddingProviderError as exc:
        raise AIProviderNotConfiguredError(str(exc)) from exc


def get_status() -> dict:
    """返回 AI 模块的对外状态信息（不包含敏感字段）"""
    cfg = get_config()
    return cfg.to_public_dict()
