"""AI 模块配置：从环境变量加载，默认禁用。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


SUPPORTED_LLM_PROVIDERS = ("disabled", "openai", "anthropic", "ollama")
SUPPORTED_EMBEDDING_PROVIDERS = ("disabled", "openai", "ollama", "local")


@dataclass(frozen=True)
class AIConfig:
    """AI 模块运行时配置（不可变，启动时一次性读取）"""

    llm_provider: str = "disabled"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_max_tokens: int = 1024
    llm_temperature: float = 0.7

    embedding_provider: str = "disabled"
    embedding_model: str = ""
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_dimensions: int = 768

    request_timeout_seconds: float = 60.0

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider != "disabled" and bool(self.llm_model)

    @property
    def embedding_enabled(self) -> bool:
        return self.embedding_provider != "disabled" and bool(self.embedding_model)

    @property
    def is_local_only(self) -> bool:
        """是否仅使用本地 provider（隐私模式）"""
        local_set = {"disabled", "ollama", "local"}
        return self.llm_provider in local_set and self.embedding_provider in local_set

    def llm_data_flows_remote(self) -> bool:
        """LLM 是否将数据发送到外部（用于 UI 警告）"""
        return self.llm_enabled and self.llm_provider in ("openai", "anthropic")

    def to_public_dict(self) -> dict[str, Any]:
        """对外暴露的状态信息（隐藏 API key）"""
        return {
            "llm_enabled": self.llm_enabled,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "llm_data_flows_remote": self.llm_data_flows_remote(),
            "embedding_enabled": self.embedding_enabled,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
            "is_local_only": self.is_local_only,
        }


def _get(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


def _get_int(name: str, default: int) -> int:
    raw = _get(name, str(default))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _get_float(name: str, default: float) -> float:
    raw = _get(name, str(default))
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def load_ai_config() -> AIConfig:
    """从环境变量加载 AI 配置"""
    llm_provider = _get("LIFEVAULT_LLM_PROVIDER", "disabled").lower()
    if llm_provider not in SUPPORTED_LLM_PROVIDERS:
        llm_provider = "disabled"

    embedding_provider = _get("LIFEVAULT_EMBEDDING_PROVIDER", "disabled").lower()
    if embedding_provider not in SUPPORTED_EMBEDDING_PROVIDERS:
        embedding_provider = "disabled"

    return AIConfig(
        llm_provider=llm_provider,
        llm_model=_get("LIFEVAULT_LLM_MODEL"),
        llm_api_key=_get("LIFEVAULT_LLM_API_KEY"),
        llm_base_url=_get("LIFEVAULT_LLM_BASE_URL"),
        llm_max_tokens=_get_int("LIFEVAULT_LLM_MAX_TOKENS", 1024),
        llm_temperature=_get_float("LIFEVAULT_LLM_TEMPERATURE", 0.7),
        embedding_provider=embedding_provider,
        embedding_model=_get("LIFEVAULT_EMBEDDING_MODEL"),
        embedding_api_key=_get("LIFEVAULT_EMBEDDING_API_KEY"),
        embedding_base_url=_get("LIFEVAULT_EMBEDDING_BASE_URL"),
        embedding_dimensions=_get_int("LIFEVAULT_EMBEDDING_DIMENSIONS", 768),
        request_timeout_seconds=_get_float("LIFEVAULT_AI_TIMEOUT", 60.0),
    )
