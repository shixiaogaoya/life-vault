"""AI 路由集成测试 — 使用 mock LLM/embedding provider 避免真实 API 调用。"""
from __future__ import annotations

import os
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.ai.embeddings.base import EmbeddingProvider, EmbeddingResult
from app.ai.providers.base import ChatMessage, ChatResponse, LLMProvider
from app.db import init_database, insert_messages
from app.main import app
from app.models.message import MessageSource, UnifiedMessage


class MockLLMProvider(LLMProvider):
    """记录调用、返回固定回答的 mock LLM"""

    def __init__(self, config, response_text: str = "Mock answer") -> None:
        super().__init__(config)
        self._response_text = response_text
        self.calls: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return "mock"

    async def chat_completion(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        self.calls.append(
            {
                "messages": [(m.role, m.content[:50]) for m in messages],
                "temperature": temperature,
            }
        )
        return ChatResponse(content=self._response_text, model="mock-model")


class MockEmbeddingProvider(EmbeddingProvider):
    """返回基于文本长度/内容简单向量的 mock embedding"""

    def __init__(self, config, dimensions: int = 4) -> None:
        super().__init__(config)
        self._dimensions = dimensions
        self.calls: list[str] = []

    @property
    def name(self) -> str:
        return "mock"

    async def embed_texts(self, texts: list[str]) -> list[EmbeddingResult]:
        self.calls.extend(texts)
        results = []
        for text in texts:
            # 简单基于内容的向量：每个字符的 ASCII 码 mod 维度
            vec = [0.0] * self._dimensions
            for ch in text:
                vec[ord(ch) % self._dimensions] += 1.0
            # 归一化由 vector_store 处理
            results.append(EmbeddingResult(vector=vec, model="mock-embedding"))
        return results


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """每个测试前清除 AI 相关环境变量"""
    for key in list(os.environ.keys()):
        if key.startswith("LIFEVAULT_LLM_") or key.startswith("LIFEVAULT_EMBEDDING_") or key == "LIFEVAULT_VECTOR_DB_PATH":
            monkeypatch.delenv(key, raising=False)
    # 强制使用临时 vector db
    import tempfile
    monkeypatch.setenv("LIFEVAULT_VECTOR_DB_PATH", os.path.join(tempfile.gettempdir(), "test_vectors.db"))
    # 清除可能存在的 vectors.db 文件
    vpath = os.environ.get("LIFEVAULT_VECTOR_DB_PATH")
    if vpath and os.path.exists(vpath):
        os.remove(vpath)
    # 重置 registry 缓存
    from app.ai.registry import reload_config
    reload_config()


@pytest_asyncio.fixture
async def setup_messages(tmp_path):
    """初始化数据库并插入测试消息（使用当前时间戳，便于摘要测试匹配当前时间段）"""
    db_path = tmp_path / "test_ai.db"
    os.environ["LIFEVAULT_DB_PATH"] = str(db_path)
    await init_database(str(db_path))

    from datetime import datetime
    now_ts = int(datetime.now().timestamp())

    messages = [
        UnifiedMessage(
            id=0,
            source=MessageSource.WECHAT_4X,
            msg_svr_id=100 + i,
            local_id=i,
            msg_type=1,
            timestamp=now_ts - i * 3600,  # 最近 10 小时
            chat_id="chat_main",
            chat_name="主聊天",
            sender_name="Alice" if i % 2 else "Bob",
            content=f"Hello world message number {i} about Python",
        )
        for i in range(10)
    ]
    await insert_messages(messages)
    return db_path


@pytest.mark.asyncio
class TestAIStatusEndpoint:
    async def test_status_returns_disabled_by_default(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/ai/status")

        assert response.status_code == 200
        data = response.json()
        assert data["llm_enabled"] is False
        assert data["embedding_enabled"] is False
        assert data["llm_provider"] == "disabled"
        assert "index_progress" in data

    async def test_status_reflects_enabled_providers(self, monkeypatch):
        monkeypatch.setenv("LIFEVAULT_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("LIFEVAULT_LLM_MODEL", "llama3.2")
        from app.ai.registry import reload_config
        reload_config()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/ai/status")

        assert response.status_code == 200
        data = response.json()
        assert data["llm_enabled"] is True
        assert data["llm_provider"] == "ollama"
        assert data["is_local_only"] is True


@pytest.mark.asyncio
class TestAIChatEndpoint:
    async def test_chat_returns_503_when_disabled(self, setup_messages):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/ai/chat",
                json={"query": "Hello"},
            )

        assert response.status_code == 503

    async def test_chat_validates_empty_query(self, monkeypatch, setup_messages):
        # 即使 AI 启用，空 query 也应被 Pydantic 拒绝
        monkeypatch.setenv("LIFEVAULT_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("LIFEVAULT_LLM_MODEL", "llama3.2")
        from app.ai.registry import reload_config
        reload_config()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/ai/chat",
                json={"query": ""},
            )

        assert response.status_code == 422

    async def test_chat_works_with_mocks(
        self, monkeypatch, setup_messages
    ):
        # 启用 AI 并替换工厂函数
        monkeypatch.setenv("LIFEVAULT_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("LIFEVAULT_LLM_MODEL", "llama3.2")
        monkeypatch.setenv("LIFEVAULT_EMBEDDING_PROVIDER", "ollama")
        monkeypatch.setenv("LIFEVAULT_EMBEDDING_MODEL", "nomic-embed-text")
        monkeypatch.setenv("LIFEVAULT_EMBEDDING_DIMENSIONS", "4")
        from app.ai.registry import reload_config
        cfg = reload_config()

        mock_llm = MockLLMProvider(cfg, response_text="This is a mock answer")
        mock_embedding = MockEmbeddingProvider(cfg, dimensions=4)

        # 用 monkeypatch 替换工厂函数（在 router 模块内）
        from app.routers import ai as ai_router
        monkeypatch.setattr(ai_router, "llm_provider_factory", lambda: mock_llm)
        monkeypatch.setattr(ai_router, "embedding_provider_factory", lambda: mock_embedding)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # 先建立索引（让向量库有数据）
            await client.post("/api/ai/index")
            # 等任务完成
            import asyncio
            for _ in range(20):
                await asyncio.sleep(0.1)
                status_resp = await client.get("/api/ai/index/status")
                if status_resp.json()["status"] in ("completed", "failed"):
                    break

            response = await client.post(
                "/api/ai/chat",
                json={"query": "Python", "top_k": 3},
            )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["answer"] == "This is a mock answer"
        assert isinstance(data["citations"], list)
        assert len(data["citations"]) <= 3
        assert all("message_id" in c for c in data["citations"])


@pytest.mark.asyncio
class TestAISummaryEndpoint:
    async def test_summary_returns_503_when_disabled(self, setup_messages):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/ai/summary",
                json={"period": "day"},
            )

        assert response.status_code == 503

    async def test_summary_validates_period(self, monkeypatch, setup_messages):
        monkeypatch.setenv("LIFEVAULT_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("LIFEVAULT_LLM_MODEL", "llama3.2")
        from app.ai.registry import reload_config
        reload_config()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/ai/summary",
                json={"period": "year"},
            )

        assert response.status_code == 400

    async def test_summary_works_with_mock(self, monkeypatch, setup_messages):
        monkeypatch.setenv("LIFEVAULT_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("LIFEVAULT_LLM_MODEL", "llama3.2")
        from app.ai.registry import reload_config
        cfg = reload_config()

        mock_llm = MockLLMProvider(cfg, response_text="今天讨论了 Python 编程")
        from app.routers import ai as ai_router
        monkeypatch.setattr(ai_router, "llm_provider_factory", lambda: mock_llm)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/ai/summary",
                json={"period": "month"},
            )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["summary"] == "今天讨论了 Python 编程"
        assert data["period"] == "month"
        assert data["message_count"] >= 0
        assert data["model"] == "mock-model"


@pytest.mark.asyncio
class TestAIIndexEndpoint:
    async def test_index_returns_503_when_disabled(self, setup_messages):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/api/ai/index")

        assert response.status_code == 503

    async def test_index_status_returns_idle_initially(self):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/ai/index/status")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("idle", "pending", "running", "completed", "failed")
