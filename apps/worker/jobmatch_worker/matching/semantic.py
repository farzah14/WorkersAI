"""Optional cloud embedding similarity with deterministic lexical fallback.

Embeddings are an internal matching helper, routed through 9Router OpenAI-compatible
embeddings endpoint. When no ``NINEROUTER_EMBED_MODEL`` is configured or the
cloud embedding request fails, matching degrades to token-set similarity
and records ``degraded=True`` in the match result.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field

import httpx

from jobmatch_worker.ai.ninerouter import NINEROUTER_DEFAULT_BASE_URL

MAX_INPUT_CHARS = 512
EMBED_PATH = "embeddings"
EMBED_TIMEOUT_SECONDS = 10.0

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalize_for_semantic(text: str) -> str:
    """Lowercase alphanumeric tokens joined by spaces, capped in length."""
    tokens = _TOKEN_RE.findall(text.casefold())
    return " ".join(tokens)[:MAX_INPUT_CHARS]


def token_similarity(left: str, right: str) -> float:
    """Jaccard similarity over normalized lowercase alphanumeric tokens."""
    left_tokens = set(_TOKEN_RE.findall(left.casefold()))
    right_tokens = set(_TOKEN_RE.findall(right.casefold()))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Cosine similarity normalized to the unit range (0..1)."""
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return max(0.0, dot / (left_norm * right_norm))


class EmbeddingClient:
    """9Router / OpenAI-compatible embedding client; never used for generative calls."""

    def __init__(
        self,
        *,
        api_key: str = "",
        model: str,
        base_url: str = NINEROUTER_DEFAULT_BASE_URL,
        client: httpx.AsyncClient | None = None,
        timeout: float = EMBED_TIMEOUT_SECONDS,
        embed_path: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client if client is not None else httpx.AsyncClient(timeout=timeout)
        if embed_path is not None:
            self._embed_path = embed_path
        elif self._base_url.endswith("/api"):
            self._embed_path = "embed"
        else:
            self._embed_path = "embeddings"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        response = await self._client.post(
            f"{self._base_url}/{self._embed_path.lstrip('/')}",
            json={
                "model": self._model,
                "input": [normalize_for_semantic(text) for text in texts],
            },
            headers=headers if headers else None,
        )
        response.raise_for_status()
        data = response.json()
        if "data" in data and isinstance(data["data"], list):
            return [item["embedding"] for item in data["data"]]
        if "embeddings" in data and isinstance(data["embeddings"], list):
            return data["embeddings"]
        raise ValueError("Unexpected embeddings response shape")

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


@dataclass
class SemanticMatchResult:
    scores: dict[str, float] = field(default_factory=dict)
    degraded: bool = True


class SemanticMatcher:
    """Scores requirement values against candidate statements semantically.

    Degrades to deterministic token similarity (with ``degraded=True``)
    when no embedding client is configured or the cloud service fails.
    """

    def __init__(self, client: EmbeddingClient | None) -> None:
        self._client = client

    async def match(
        self,
        *,
        candidate_statements: list[str],
        requirement_values: list[str],
    ) -> SemanticMatchResult:
        if self._client is None:
            return self._lexical(candidate_statements, requirement_values)
        try:
            vectors = await self._client.embed(candidate_statements + requirement_values)
        except Exception:  # noqa: BLE001 - any embedding failure degrades deterministically
            return self._lexical(candidate_statements, requirement_values)
        if len(vectors) != len(candidate_statements) + len(requirement_values):
            return self._lexical(candidate_statements, requirement_values)
        candidate_vectors = vectors[: len(candidate_statements)]
        requirement_vectors = vectors[len(candidate_statements) :]
        scores = {
            value: max(
                cosine_similarity(req_vec, cand_vec)
                for cand_vec in candidate_vectors
            )
            for value, req_vec in zip(requirement_values, requirement_vectors, strict=True)
        }
        return SemanticMatchResult(scores=scores, degraded=False)

    def _lexical(
        self,
        candidate_statements: list[str],
        requirement_values: list[str],
    ) -> SemanticMatchResult:
        scores = {
            value: max(token_similarity(value, statement) for statement in candidate_statements)
            for value in requirement_values
        }
        return SemanticMatchResult(scores=scores, degraded=True)


__all__ = [
    "EMBED_PATH",
    "EMBED_TIMEOUT_SECONDS",
    "MAX_INPUT_CHARS",
    "EmbeddingClient",
    "SemanticMatchResult",
    "SemanticMatcher",
    "cosine_similarity",
    "normalize_for_semantic",
    "token_similarity",
]