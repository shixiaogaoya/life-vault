"""AI 模块配置：支持运行时配置文件 + 环境变量双通道。

加载优先级（高 → 低）：
1. 运行时配置文件（JSON，由 UI 写入，路径见 config_file_path()）
2. 环境变量（LIFEVAULT_LLM_* / LIFEVAULT_EMBEDDING_*）
3. 默认值（disabled）

这样：
- 桌面端 / Docker 用户可在前端 UI 直接填 URL + API Key，无需重启
- 命令行 / CI 用户仍可用环境变量（运维友好）
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SUPPORTED_LLM_PROVIDERS = ("disabled", "openai", "anthropic", "ollama")
SUPPORTED_EMBEDDING_PROVIDERS = ("disabled", "openai", "ollama", "local")

# 配置文件名（与数据库同目录）
CONFIG_FILENAME = "ai_config.json"

# 敏感字段：GET 时不回显明文，PUT 时空串表示清除
SENSITIVE_FIELDS = ("llm_api_key", "embedding_api_key")


@dataclass(frozen=True)
class AIConfig:
    """AI 模块运行时配置（不可变，每次加载新建实例）"""

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

    # 配置来源标记（"file" / "env" / "default"），便于调试
    source: str = "default"

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
        """对外暴露的状态信息（隐藏 API key 明文）"""
        return {
            "llm_enabled": self.llm_enabled,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "llm_base_url": self.llm_base_url,
            "llm_data_flows_remote": self.llm_data_flows_remote(),
            "embedding_enabled": self.embedding_enabled,
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
            "embedding_base_url": self.embedding_base_url,
            "is_local_only": self.is_local_only,
            "source": self.source,
            # 是否已配置 api_key（不返回明文，仅布尔）
            "llm_api_key_set": bool(self.llm_api_key),
            "embedding_api_key_set": bool(self.embedding_api_key),
        }


def config_file_path() -> Path:
    """运行时配置文件路径。

    约定（与桌面端 paths.ts 一致）：
    - 优先用环境变量 LIFEVAULT_CONFIG_DIR（桌面端注入 userData 目录）
    - 回退到环境变量 LIFEVAULT_DB_PATH 的父目录（Docker 部署：/data）
    - 最后回退到 ~/.lifevault/
    """
    config_dir = os.getenv("LIFEVAULT_CONFIG_DIR")
    if config_dir:
        return Path(config_dir).expanduser() / CONFIG_FILENAME

    db_path = os.getenv("LIFEVAULT_DB_PATH")
    if db_path:
        return Path(db_path).expanduser().parent / CONFIG_FILENAME

    return Path("~/.lifevault").expanduser() / CONFIG_FILENAME


def _load_from_file() -> dict[str, Any] | None:
    """从 JSON 配置文件加载（不存在或损坏则返回 None）"""
    try:
        path = config_file_path()
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


def _env_int(name: str, default: int) -> int:
    raw = _env(name, str(default))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    raw = _env(name, str(default))
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _coerce_str(value: Any, allowed: tuple[str, ...], default: str) -> str:
    """把任意值转成小写字符串，不在 allowed 集合则用 default"""
    if value is None:
        return default
    text = str(value).strip().lower()
    return text if text in allowed else default


def _coerce_number(value: Any, default: float | int, is_int: bool) -> float | int:
    if value is None:
        return default
    try:
        return int(value) if is_int else float(value)
    except (TypeError, ValueError):
        return default


def _has_any_env() -> bool:
    """检测是否设置了任何 AI 相关环境变量"""
    return any(
        os.getenv(name)
        for name in (
            "LIFEVAULT_LLM_PROVIDER",
            "LIFEVAULT_LLM_MODEL",
            "LIFEVAULT_EMBEDDING_PROVIDER",
            "LIFEVAULT_EMBEDDING_MODEL",
        )
    )


def load_ai_config() -> AIConfig:
    """加载配置：文件 > 环境变量 > 默认值。

    文件配置存在时，文件中的每个字段覆盖环境变量；文件中缺省的字段
    回退到环境变量。这样用户在 UI 部分填写（如只填 LLM 不填 embedding）
    也能正确工作。
    """
    file_data = _load_from_file()

    def pick(file_key: str, env_key: str, default: str = "") -> str:
        """文件值优先；文件中该字段空则用环境变量"""
        if file_data and file_data.get(file_key) not in (None, ""):
            return str(file_data[file_key]).strip()
        return _env(env_key, default)

    llm_provider = _coerce_str(
        pick("llm_provider", "LIFEVAULT_LLM_PROVIDER", "disabled"),
        SUPPORTED_LLM_PROVIDERS,
        "disabled",
    )
    embedding_provider = _coerce_str(
        pick("embedding_provider", "LIFEVAULT_EMBEDDING_PROVIDER", "disabled"),
        SUPPORTED_EMBEDDING_PROVIDERS,
        "disabled",
    )

    source = "file" if file_data else ("env" if _has_any_env() else "default")

    return AIConfig(
        llm_provider=llm_provider,
        llm_model=pick("llm_model", "LIFEVAULT_LLM_MODEL"),
        llm_api_key=pick("llm_api_key", "LIFEVAULT_LLM_API_KEY"),
        llm_base_url=pick("llm_base_url", "LIFEVAULT_LLM_BASE_URL"),
        llm_max_tokens=int(
            _coerce_number(
                file_data.get("llm_max_tokens") if file_data else None,
                _env_int("LIFEVAULT_LLM_MAX_TOKENS", 1024),
                is_int=True,
            )
        ),
        llm_temperature=float(
            _coerce_number(
                file_data.get("llm_temperature") if file_data else None,
                _env_float("LIFEVAULT_LLM_TEMPERATURE", 0.7),
                is_int=False,
            )
        ),
        embedding_provider=embedding_provider,
        embedding_model=pick("embedding_model", "LIFEVAULT_EMBEDDING_MODEL"),
        embedding_api_key=pick("embedding_api_key", "LIFEVAULT_EMBEDDING_API_KEY"),
        embedding_base_url=pick("embedding_base_url", "LIFEVAULT_EMBEDDING_BASE_URL"),
        embedding_dimensions=int(
            _coerce_number(
                file_data.get("embedding_dimensions") if file_data else None,
                _env_int("LIFEVAULT_EMBEDDING_DIMENSIONS", 768),
                is_int=True,
            )
        ),
        request_timeout_seconds=float(
            _coerce_number(
                file_data.get("request_timeout_seconds") if file_data else None,
                _env_float("LIFEVAULT_AI_TIMEOUT", 60.0),
                is_int=False,
            )
        ),
        source=source,
    )


def save_ai_config(updates: dict[str, Any]) -> AIConfig:
    """把用户从 UI 提交的配置增量写入 JSON 文件，返回新配置。

    - updates 中 None 的字段会被忽略（不覆盖已有值）
    - api_key 传空串视为「清除」，传非空串视为「更新」
    - 其他字段传空串视为「留空保留原值」
    - 写入后立即清缓存，下次 get_config() 拿到新值
    """
    path = config_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, Any] = {}
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(existing, dict):
                existing = {}
        except (json.JSONDecodeError, OSError):
            existing = {}

    ALLOWED_KEYS = {
        "llm_provider",
        "llm_model",
        "llm_api_key",
        "llm_base_url",
        "llm_max_tokens",
        "llm_temperature",
        "embedding_provider",
        "embedding_model",
        "embedding_api_key",
        "embedding_base_url",
        "embedding_dimensions",
        "request_timeout_seconds",
    }
    for key, value in updates.items():
        if key not in ALLOWED_KEYS:
            continue
        if value is None:
            continue
        # 非敏感字段传空串 → 跳过（保留原值）；敏感字段传空串 → 清除
        if isinstance(value, str) and value == "" and key not in SENSITIVE_FIELDS:
            continue
        existing[key] = value

    path.write_text(
        json.dumps(existing, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return load_ai_config()


def clear_ai_config() -> None:
    """删除配置文件（恢复到环境变量 / 默认值）"""
    path = config_file_path()
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
