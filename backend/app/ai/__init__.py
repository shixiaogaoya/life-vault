"""LifeVault AI module — optional LLM/embedding integration.

隐私设计原则：
- AI 默认未配置（disabled），用户需在 UI 或环境变量中显式启用
- 云端 provider（OpenAI、Anthropic）会在状态接口明确告知数据流向外部
- 本地 provider（Ollama）所有数据保留在本机
- API Key 存于本地配置文件，不上传任何服务器
"""
from app.ai.config import AIConfig, load_ai_config
from app.ai.registry import (
    AIDisabledError,
    AIProviderNotConfiguredError,
    apply_config,
    embedding_provider_factory,
    get_config,
    get_status,
    llm_provider_factory,
    reset_config,
)

__all__ = [
    "AIConfig",
    "load_ai_config",
    "AIDisabledError",
    "AIProviderNotConfiguredError",
    "apply_config",
    "embedding_provider_factory",
    "get_config",
    "get_status",
    "llm_provider_factory",
    "reset_config",
]
