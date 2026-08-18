"""Base contracts and error taxonomy for job discovery connectors.

Error taxonomy mirrors the AI adapter layer (``ai/base.py``):

- ``SourceUnavailable``: transient source failure (timeout, transport
  error, HTTP 408/429/3xx/5xx) - safe to retry or fall back to another
  source;
- ``SourceConfigError``: permanent configuration problem (missing API key,
  wrong scheme, rejected credentials);
- ``SourceDataError``: permanent rejection - unusable response payload or
  a security/policy refusal (non-public address, robots denial, oversize
  body, non-HTML content).

Error messages are built by this package and never include raw page text,
search snippets, or API keys.
"""

import asyncio
import json
import re
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx
from bs4 import BeautifulSoup

from jobmatch_worker.jobs.models import DiscoveredJob, DiscoveryCandidateUrl
from jobmatch_worker.jobs.query import SearchQuery

_RETRYABLE_STATUSES = frozenset({408, 429})
_JSON_MAX_BYTES = 4 * 1024 * 1024


class SourceError(Exception):
    """Base class for connector failures, carrying the failing source key."""

    def __init__(self, source_key: str, message: str) -> None:
        super().__init__(f"{source_key}: {message}")
        self.source_key = source_key
        self.message = message


class SourceUnavailable(SourceError):
    """Transient source failure; safe to retry or fall back to other sources."""


class SourceConfigError(SourceError):
    """Permanent configuration problem that requires operator action."""


class SourceDataError(SourceError):
    """Permanent rejection: unusable response, security or policy refusal."""


class SourceConnector(Protocol):
    """Uniform interface for discovery connectors.

    Connectors return fully normalized jobs (Greenhouse/Lever) or candidate
    URLs that still need a career-page fetch (web search). A connector
    must raise only ``SourceError`` subclasses and never be affected by
    another connector's failure.
    """

    source_key: str

    async def search(
        self, query: SearchQuery
    ) -> list[DiscoveredJob | DiscoveryCandidateUrl]: ...


async def get_json_with_retry(
    client: httpx.AsyncClient,
    *,
    url: str,
    source_key: str,
    timeout: float,
    params: dict[str, str | int] | None = None,
    headers: dict[str, str] | None = None,
    retries: int = 1,
    retry_delay: float = 0.05,
) -> httpx.Response:
    """GET JSON with bounded retries, error classification, and a body cap.

    Retryable conditions (timeout, transport error, HTTP 408/429/3xx/5xx)
    are retried at most ``retries`` times before raising
    ``SourceUnavailable``. Other HTTP 4xx responses are permanent
    ``SourceConfigError``. The response body is streamed and capped at
    4 MiB; oversized bodies raise ``SourceDataError``. Callers must parse
    the returned body with ``parse_json``.
    """
    last_error: SourceUnavailable | None = None
    for attempt in range(retries + 1):
        request = client.build_request("GET", url, params=params, headers=headers)
        response: httpx.Response | None = None
        try:
            response = await client.send(request, stream=True)
            status = response.status_code
            if status in _RETRYABLE_STATUSES or 300 <= status < 400 or status >= 500:
                last_error = SourceUnavailable(source_key, f"HTTP {status}")
            elif 400 <= status < 500:
                raise SourceConfigError(source_key, f"HTTP {status}")
            else:
                body = await _read_capped_body(source_key, response, _JSON_MAX_BYTES)
                return httpx.Response(
                    status_code=status,
                    headers=response.headers,
                    content=body,
                    request=request,
                )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_error = SourceUnavailable(
                source_key, f"transport error: {type(exc).__name__}"
            )
        finally:
            if response is not None:
                await response.aclose()
        if attempt < retries:
            await asyncio.sleep(retry_delay)
    assert last_error is not None
    raise last_error


async def post_json_with_retry(
    client: httpx.AsyncClient,
    *,
    url: str,
    source_key: str,
    json_body: dict[str, Any],
    timeout: float,
    headers: dict[str, str] | None = None,
    retries: int = 1,
    retry_delay: float = 0.05,
) -> httpx.Response:
    """POST JSON with the same bounded retry and body-cap policy as GET."""
    last_error: SourceUnavailable | None = None
    for attempt in range(retries + 1):
        request = client.build_request("POST", url, headers=headers, json=json_body)
        response: httpx.Response | None = None
        try:
            response = await client.send(request, stream=True)
            status = response.status_code
            if status in _RETRYABLE_STATUSES or 300 <= status < 400 or status >= 500:
                last_error = SourceUnavailable(source_key, f"HTTP {status}")
            elif 400 <= status < 500:
                raise SourceConfigError(source_key, f"HTTP {status}")
            else:
                body = await _read_capped_body(source_key, response, _JSON_MAX_BYTES)
                return httpx.Response(
                    status_code=status,
                    headers=response.headers,
                    content=body,
                    request=request,
                )
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_error = SourceUnavailable(
                source_key, f"transport error: {type(exc).__name__}"
            )
        finally:
            if response is not None:
                await response.aclose()
        if attempt < retries:
            await asyncio.sleep(retry_delay)
    assert last_error is not None
    raise last_error


async def _read_capped_body(
    source_key: str, response: httpx.Response, limit: int
) -> bytes:
    content_length = response.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > limit:
        raise SourceDataError(source_key, "response body exceeds size cap")
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if total > limit:
            raise SourceDataError(source_key, "response body exceeds size cap")
        chunks.append(chunk)
    return b"".join(chunks)


def parse_json(source_key: str, response: httpx.Response) -> Any:
    """Parse a JSON response body, mapping malformed bodies to data errors."""
    try:
        return response.json()
    except json.JSONDecodeError as exc:
        raise SourceDataError(source_key, "non-JSON response") from exc


def clean_optional_str(value: object) -> str | None:
    """Return a stripped non-empty string, or None for empty/missing values."""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def strip_html_to_text(markup: object) -> str:
    """Strip tags and non-content elements from untrusted HTML fragments.

    Scripts, styles, forms, and other non-content elements are removed
    before the visible text is extracted.
    """
    if not isinstance(markup, str) or not markup.strip():
        return ""
    soup = BeautifulSoup(markup, "html.parser")
    for tag in soup.find_all(["script", "style", "form", "noscript", "iframe", "svg"]):
        tag.decompose()
    return collapse_whitespace(soup.get_text(separator="\n"))


def collapse_whitespace(text: str) -> str:
    """Collapse runs of horizontal whitespace and drop blank lines."""
    lines = [re.sub(r"[ \t\x0b\x0c]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def parse_iso_datetime(value: object) -> datetime | None:
    """Parse an ISO-8601 timestamp (as returned by Greenhouse), or None."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def parse_ms_epoch(value: object) -> datetime | None:
    """Parse a millisecond epoch timestamp (as returned by Lever), or None."""
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


__all__ = [
    "SourceConfigError",
    "SourceConnector",
    "SourceDataError",
    "SourceError",
    "SourceUnavailable",
    "clean_optional_str",
    "collapse_whitespace",
    "get_json_with_retry",
    "parse_iso_datetime",
    "parse_json",
    "parse_ms_epoch",
    "post_json_with_retry",
    "strip_html_to_text",
]
