import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
import jsonschema


@dataclass(frozen=True)
class AiResult:
    provider: str
    model: str
    data: dict[str, Any]
    latency_ms: int


class AiProvider(Protocol):
    name: str

    async def generate_structured(self, *, system: str, user: str, schema: dict[str, Any]) -> AiResult: ...


class RetryableAiError(Exception):
    """Transient provider or transport failure; safe to retry or fall back."""


class PermanentAiError(Exception):
    """Configuration or input error; retrying will not help."""


class StructuredOutputError(RetryableAiError):
    """Provider returned invalid JSON or schema-invalid output."""


def parse_structured_content(content: str, schema: dict[str, Any]) -> dict[str, Any]:
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise StructuredOutputError(f"provider returned invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise StructuredOutputError("provider output is not a JSON object")
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as exc:
        raise StructuredOutputError(f"provider output failed schema validation: {exc.message}") from exc
    return data


def extract_message_content(
    body: dict[str, Any],
    *,
    provider: str,
    getter: Callable[[dict[str, Any]], Any],
) -> str:
    """Extract the provider-specific message content with defensive shape checks.

    A body carrying a provider ``error`` field, a missing/empty ``choices`` or
    ``message``, or a missing/None content value is treated as a retryable
    structured-output failure instead of leaking raw KeyError/IndexError/TypeError.
    """
    if "error" in body:
        raise StructuredOutputError(f"{provider} returned an error field in the body")
    try:
        content = getter(body)
    except (KeyError, IndexError, TypeError) as exc:
        raise StructuredOutputError(
            f"{provider} returned an unexpected response shape: {type(exc).__name__}"
        ) from exc
    if not isinstance(content, str) or not content.strip():
        raise StructuredOutputError(f"{provider} returned empty or non-string message content")
    return content


class HttpAiProvider:
    """Base for HTTP chat-completion providers with bounded timeout and error mapping."""

    name: str = ""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._owns_client = client is None
        self._client = client if client is not None else httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _post_json(
        self,
        path: str,
        *,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            response = await self._client.post(url, json=payload, headers=headers, timeout=self.timeout)
        except httpx.TimeoutException as exc:
            raise RetryableAiError(f"{self.name} request timed out") from exc
        except httpx.TransportError as exc:
            raise RetryableAiError(f"{self.name} transport error: {type(exc).__name__}") from exc
        if response.status_code in (408, 429) or 300 <= response.status_code < 400 or response.status_code >= 500:
            raise RetryableAiError(f"{self.name} HTTP {response.status_code}")
        if 400 <= response.status_code < 500:
            raise PermanentAiError(f"{self.name} HTTP {response.status_code}")
        response.raise_for_status()
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise StructuredOutputError(f"{self.name} returned a non-JSON body") from exc


__all__ = [
    "AiProvider",
    "AiResult",
    "HttpAiProvider",
    "PermanentAiError",
    "RetryableAiError",
    "StructuredOutputError",
    "extract_message_content",
    "parse_structured_content",
]