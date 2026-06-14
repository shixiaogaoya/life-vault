"""LifeVault AI module — optional LLM/embedding integration.

隐私设计原则：
- 整个 AI 子系统默认禁用，必须显式配置环境变量 LIFEVAULT_LLM_PROVIDER 才启用
- 云端 provider（OpenAI、Anthropic）会在状态接口明确告知数据流向外部
- 本地 provider（Ollama）所有数据保留在本机
"""
from app.ai.config import AIConfig, load_ai_config
from app.ai.registry import (
    AIDisabledError,
    AIProviderNotConfiguredError,
    embedding_provider_factory,
    get_status,
    llm_provider_factory,
)

__all__ = [
    "AIConfig",
    "load_ai_config",
    "AIDisabledError",
    "AIProviderNotConfiguredError",
    "embedding_provider_factory",
    "get_status",
    "llm_provider_factory",
]
