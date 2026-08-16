from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from jobmatch_worker.matching.semantic import (
    MAX_INPUT_CHARS,
    EmbeddingClient,
    SemanticMatcher,
    cosine_similarity,
    normalize_for_semantic,
    token_similarity,
)


def test_cosine_similarity_is_normalized_to_unit_range() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(0.0)
    assert cosine_similarity([1.0, 1.0], [1.0, 0.0]) == pytest.approx(2**-0.5)


def test_token_similarity_is_jaccard() -> None:
    assert token_similarity("python data engineering", "python data") == pytest.approx(2 / 3)
    assert token_similarity("python sql", "aws") == 0.0
    assert token_similarity("python sql", "SQL python") == 1.0
    assert token_similarity("python", "") == 0.0


def test_normalize_for_semantic_lowercases_and_strips_punctuation() -> None:
    assert normalize_for_semantic("Python & SQL — Jakarta!") == "python sql jakarta"


def test_normalize_for_semantic_caps_input_length() -> None:
    long_text = "python " * 1000
    assert len(normalize_for_semantic(long_text)) <= MAX_INPUT_CHARS


class _FakeEmbeddingClient:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [
            [1.0, 0.0] if "python" in text else ([0.0, 1.0] if "aws" in text else [2.0, 0.0])
            for text in texts
        ]

    async def aclose(self) -> None:
        return None


class _BrokenEmbeddingClient:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise httpx.ConnectError("embedding service unavailable")

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_matcher_without_embed_model_uses_lexical_path() -> None:
    matcher = SemanticMatcher(client=None)
    result = await matcher.match(
        candidate_statements=["python"],
        requirement_values=["python", "aws"],
    )
    assert result.degraded is True
    assert result.scores["python"] == 1.0
    assert result.scores["aws"] == 0.0


@pytest.mark.asyncio
async def test_matcher_uses_embeddings_when_configured() -> None:
    matcher = SemanticMatcher(client=_FakeEmbeddingClient())
    result = await matcher.match(
        candidate_statements=["python"],
        requirement_values=["python", "aws"],
    )
    assert result.degraded is False
    assert result.scores["python"] == pytest.approx(1.0)
    assert result.scores["aws"] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_matcher_takes_best_similarity_across_statements() -> None:
    matcher = SemanticMatcher(client=_FakeEmbeddingClient())
    result = await matcher.match(
        candidate_statements=["python", "aws"],
        requirement_values=["cloud"],
    )
    assert result.scores["cloud"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_matcher_falls_back_when_embedding_unavailable() -> None:
    matcher = SemanticMatcher(client=_BrokenEmbeddingClient())
    result = await matcher.match(
        candidate_statements=["python"],
        requirement_values=["python", "aws"],
    )
    assert result.degraded is True
    assert result.scores["python"] == 1.0
    assert result.scores["aws"] == 0.0


@pytest.mark.asyncio
async def test_embedding_client_sends_batched_authorized_request(httpx_mock: Any) -> None:
    httpx_mock.add_response(
        json={"embeddings": [[1.0, 0.0], [0.0, 1.0]]},
    )
    client = EmbeddingClient(
        api_key="okey",
        model="embed-model",
        base_url="https://ollama.com/api",
        client=httpx.AsyncClient(),
    )
    vectors = await client.embed(["python", "AWS!"])
    request = httpx_mock.get_requests()[-1]
    payload = json.loads(request.content)
    assert str(request.url) == "https://ollama.com/api/embed"
    assert request.headers["Authorization"] == "Bearer okey"
    assert payload["model"] == "embed-model"
    assert payload["input"] == ["python", "aws"]
    assert len(vectors) == 2