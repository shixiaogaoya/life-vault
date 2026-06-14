"""Embedding provider 与向量存储的单元测试。"""
from __future__ import annotations

import json
from typing import Callable

import httpx
import pytest

from app.ai.config import AIConfig
from app.ai.embeddings.base import EmbeddingProviderError
from app.ai.embeddings.local_embeddings import LocalEmbeddingProvider
from app.ai.embeddings.ollama_embeddings import OllamaEmbeddingProvider
from app.ai.embeddings.openai_embeddings import OpenAIEmbeddingProvider
from app.ai.vector_store import VectorStore, _normalize, _unpack_vector, _pack_vector, cosine_similarity


def _patch_client(provider, transport: httpx.MockTransport) -> None:
    old = provider._client
    provider._client = httpx.AsyncClient(
        base_url=old.base_url,
        headers=old.headers,
        transport=transport,
        timeout=old.timeout,
    )


# ===== OpenAI Embeddings =====


@pytest.mark.asyncio
class TestOpenAIEmbeddingProvider:
    async def test_requires_api_key(self):
        config = AIConfig(embedding_provider="openai", embedding_model="text-embedding-3-small")
        with pytest.raises(EmbeddingProviderError, match="API_KEY"):
            OpenAIEmbeddingProvider(config)

    async def test_embed_texts_returns_normalized_results(self):
        config = AIConfig(
            embedding_provider="openai",
            embedding_model="text-embedding-3-small",
            embedding_api_key="sk-test",
            embedding_dimensions=4,
        )
        provider = OpenAIEmbeddingProvider(config)

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content.decode("utf-8"))
            return httpx.Response(
                200,
                json={
                    "model": body["model"],
                    "data": [
                        {"index": i, "embedding": [0.1, 0.2, 0.3, 0.4]}
                        for i in range(len(body["input"]))
                    ],
                },
            )

        _patch_client(provider, httpx.MockTransport(handler))
        results = await provider.embed_texts(["Hello", "World"])

        assert len(results) == 2
        assert results[0].vector == [0.1, 0.2, 0.3, 0.4]
        assert results[0].dimensions == 4
        assert results[1].vector == [0.1, 0.2, 0.3, 0.4]

        await provider.close()

    async def test_handles_empty_input(self):
        config = AIConfig(
            embedding_provider="openai",
            embedding_model="text-embedding-3-small",
            embedding_api_key="sk-test",
        )
        provider = OpenAIEmbeddingProvider(config)
        results = await provider.embed_texts([])
        assert results == []
        await provider.close()


# ===== Ollama Embeddings =====


@pytest.mark.asyncio
class TestOllamaEmbeddingProvider:
    async def test_requires_model(self):
        config = AIConfig(embedding_provider="ollama", embedding_model="")
        with pytest.raises(EmbeddingProviderError, match="MODEL"):
            OllamaEmbeddingProvider(config)

    async def test_embed_texts_sequential_calls(self):
        config = AIConfig(
            embedding_provider="ollama",
            embedding_model="nomic-embed-text",
            embedding_dimensions=3,
        )
        provider = OllamaEmbeddingProvider(config)

        call_count = {"value": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["value"] += 1
            body = json.loads(request.content.decode("utf-8"))
            # 返回固定向量但与 prompt 长度相关（验证输入）
            return httpx.Response(
                200,
                json={"embedding": [0.1 * len(body["prompt"]), 0.2, 0.3]},
            )

        _patch_client(provider, httpx.MockTransport(handler))
        results = await provider.embed_texts(["a", "bb", "ccc"])

        assert len(results) == 3
        assert call_count["value"] == 3
        assert results[0].vector[0] == pytest.approx(0.1)  # "a" len=1
        assert results[2].vector[0] == pytest.approx(0.3)  # "ccc" len=3

        await provider.close()


# ===== Local Embeddings =====


class TestLocalEmbeddingProvider:
    def test_default_model_when_unspecified(self):
        config = AIConfig(embedding_provider="local", embedding_model="")
        provider = LocalEmbeddingProvider(config)
        assert provider.model == "BAAI/bge-small-zh-v1.5"

    def test_uses_configured_model(self):
        config = AIConfig(embedding_provider="local", embedding_model="custom-model")
        provider = LocalEmbeddingProvider(config)
        assert provider.model == "custom-model"

    def test_raises_when_sentence_transformers_not_installed(self, monkeypatch):
        # 强制 import 失败
        import sys
        # 移除可能已安装的模块
        for mod in list(sys.modules.keys()):
            if mod.startswith("sentence_transformers"):
                del sys.modules[mod]
        # 让后续 import 失败
        original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def fake_import(name, *args, **kwargs):
            if name == "sentence_transformers" or name.startswith("sentence_transformers."):
                raise ImportError("simulated missing dependency")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)

        config = AIConfig(embedding_provider="local", embedding_model="test-model")
        provider = LocalEmbeddingProvider(config)

        with pytest.raises(EmbeddingProviderError, match="sentence-transformers"):
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                provider.embed_texts(["test"])
            ) if False else provider._ensure_model()


# ===== Vector Store =====


@pytest.mark.asyncio
class TestVectorStore:
    async def test_init_schema_creates_tables(self, tmp_path):
        store = VectorStore(str(tmp_path / "vectors.db"), dimensions=4)
        await store.init_schema()

        import aiosqlite
        async with aiosqlite.connect(store.db_path) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='message_vectors'"
            )
            row = await cursor.fetchone()
            await cursor.close()

        assert row is not None
        assert row[0] == "message_vectors"

    async def test_upsert_and_search(self, tmp_path):
        store = VectorStore(str(tmp_path / "vectors.db"), dimensions=3)
        await store.init_schema()

        # 向量 [1, 0, 0] 和 query [0.9, 0.1, 0] 相似度高
        await store.upsert(
            message_id=1,
            chunk_text="Hello",
            vector=[1.0, 0.0, 0.0],
            chat_id="c1",
            timestamp=1700000000,
            model="test",
        )
        await store.upsert(
            message_id=2,
            chunk_text="World",
            vector=[0.0, 1.0, 0.0],
            chat_id="c2",
            timestamp=1700000100,
            model="test",
        )

        hits = await store.search([0.9, 0.1, 0.0], top_k=2)

        assert len(hits) == 2
        assert hits[0].message_id == 1  # 应该最相似
        assert hits[0].score > hits[1].score
        assert hits[0].chat_id == "c1"

    async def test_search_with_chat_filter(self, tmp_path):
        store = VectorStore(str(tmp_path / "vectors.db"), dimensions=3)
        await store.init_schema()

        await store.upsert(1, "A", [1.0, 0.0, 0.0], chat_id="chat_x")
        await store.upsert(2, "B", [1.0, 0.0, 0.0], chat_id="chat_y")

        hits = await store.search([1.0, 0.0, 0.0], top_k=10, chat_id="chat_x")
        assert len(hits) == 1
        assert hits[0].message_id == 1

    async def test_upsert_replaces_on_conflict(self, tmp_path):
        store = VectorStore(str(tmp_path / "vectors.db"), dimensions=3)
        await store.init_schema()

        await store.upsert(1, "v1", [1.0, 0.0, 0.0])
        await store.upsert(1, "v2", [0.0, 1.0, 0.0])  # 同 message_id+chunk_index=0

        assert await store.count() == 1

    async def test_dimension_validation(self, tmp_path):
        store = VectorStore(str(tmp_path / "vectors.db"), dimensions=3)
        await store.init_schema()

        with pytest.raises(ValueError, match="dimension"):
            await store.upsert(1, "x", [1.0, 2.0])  # 只有 2 维

    async def test_batch_upsert(self, tmp_path):
        store = VectorStore(str(tmp_path / "vectors.db"), dimensions=3)
        await store.init_schema()

        records = [
            {"message_id": i, "chunk_text": f"msg{i}", "vector": [1.0, 0.0, 0.0]}
            for i in range(5)
        ]
        inserted = await store.batch_upsert(records)
        assert inserted == 5
        assert await store.count() == 5

    async def test_delete_by_message(self, tmp_path):
        store = VectorStore(str(tmp_path / "vectors.db"), dimensions=3)
        await store.init_schema()
        await store.upsert(1, "a", [1.0, 0.0, 0.0])
        await store.upsert(2, "b", [1.0, 0.0, 0.0])

        deleted = await store.delete_by_message(1)
        assert deleted == 1
        assert await store.count() == 1

    async def test_list_message_ids(self, tmp_path):
        store = VectorStore(str(tmp_path / "vectors.db"), dimensions=3)
        await store.init_schema()
        await store.upsert(10, "a", [1.0, 0.0, 0.0])
        await store.upsert(20, "b", [1.0, 0.0, 0.0])

        ids = await store.list_message_ids()
        assert ids == {10, 20}

    async def test_empty_query_returns_empty(self, tmp_path):
        store = VectorStore(str(tmp_path / "vectors.db"), dimensions=3)
        await store.init_schema()
        await store.upsert(1, "a", [1.0, 0.0, 0.0])

        hits = await store.search([], top_k=5)
        assert hits == []


# ===== Vector utilities =====


class TestVectorUtilities:
    def test_pack_unpack_round_trip(self):
        original = [1.5, -2.5, 3.14, 0.0]
        packed = _pack_vector(original)
        unpacked = _unpack_vector(packed)
        assert unpacked == pytest.approx(original, abs=1e-5)

    def test_normalize_zero_vector(self):
        assert _normalize([0.0, 0.0]) == [0.0, 0.0]

    def test_normalize_unit_vector(self):
        result = _normalize([3.0, 4.0])
        # 应归一化到模 1
        import math
        norm = math.sqrt(sum(v * v for v in result))
        assert norm == pytest.approx(1.0, abs=1e-6)

    def test_cosine_similarity_orthogonal(self):
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_cosine_similarity_identical(self):
        assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)

    def test_cosine_similarity_different_lengths(self):
        assert cosine_similarity([1.0], [1.0, 1.0]) == 0.0
