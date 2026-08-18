"""Tavily Search API connector producing candidate job URLs."""

import re
import urllib.parse
from typing import Any

import httpx
from pydantic import ValidationError

from jobmatch_worker.jobs.connectors.base import (
    SourceConfigError,
    SourceDataError,
    clean_optional_str,
    parse_json,
    post_json_with_retry,
)
from jobmatch_worker.jobs.models import DiscoveredJob, DiscoveryCandidateUrl
from jobmatch_worker.jobs.query import SearchQuery

TAVILY_API_URL = "https://api.tavily.com/search"
TAVILY_MAX_COUNT = 20
TAVILY_DEFAULT_COUNT = 10
TAVILY_SEARCH_DEPTH = "basic"
_JOB_QUERY_MARKERS = ("job", "jobs", "career", "careers", "vacancy", "hiring")
_DEMO_HOST_MARKERS = ("leverdemo", "example.com", "example.org", "example.net")
_DEMO_TITLE_MARKERS = ("synthetic demo", "test posting")


class TavilyConnector:
    """Search connector using Tavily's documented web search endpoint."""

    source_key = "tavily"

    def __init__(
        self,
        *,
        api_key: str,
        client: httpx.AsyncClient | None = None,
        timeout: float = 15.0,
        count: int = TAVILY_DEFAULT_COUNT,
        retries: int = 1,
    ) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._count = count
        self._retries = retries
        self._owns_client = client is None
        self._client = client if client is not None else httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def search(
        self, query: SearchQuery
    ) -> list[DiscoveredJob | DiscoveryCandidateUrl]:
        if not self._api_key:
            raise SourceConfigError(
                self.source_key, "TAVILY_API_KEY is not configured"
            )
        if not 1 <= self._count <= TAVILY_MAX_COUNT:
            raise SourceConfigError(
                self.source_key, f"count must be between 1 and {TAVILY_MAX_COUNT}"
            )

        response = await post_json_with_retry(
            self._client,
            url=TAVILY_API_URL,
            source_key=self.source_key,
            json_body={
                "api_key": self._api_key,
                "query": _job_query_terms(query),
                "topic": "general",
                "search_depth": TAVILY_SEARCH_DEPTH,
                "max_results": self._count,
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
            },
            timeout=self._timeout,
            headers={"Accept": "application/json"},
            retries=self._retries,
        )
        body = parse_json(self.source_key, response)
        results = _extract_results(self.source_key, body)

        candidates: list[DiscoveredJob | DiscoveryCandidateUrl] = []
        for result in results:
            url = result.get("url")
            if not isinstance(url, str) or not url.strip():
                continue
            try:
                title = clean_optional_str(result.get("title"))
                if not _is_allowed_job_result(url, title):
                    continue
                snippet = clean_optional_str(result.get("content"))
                if _contains_excluded_keyword(title, snippet, query.negative_terms):
                    continue
                candidates.append(
                    DiscoveryCandidateUrl(
                        url=url,
                        title=title,
                        snippet=snippet,
                    )
                )
            except ValidationError:
                continue
        return candidates


def _extract_results(source_key: str, body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise SourceDataError(source_key, "unexpected response shape")
    results = body.get("results")
    if not isinstance(results, list):
        raise SourceDataError(source_key, "unexpected response shape")
    if len(results) > TAVILY_MAX_COUNT:
        raise SourceDataError(source_key, "source result limit exceeded")
    return [result for result in results if isinstance(result, dict)]


def _job_query_terms(query: SearchQuery) -> str:
    terms = query.terms.strip()
    if not any(marker in terms.casefold().split() for marker in _JOB_QUERY_MARKERS):
        terms = f"{terms} jobs"
    exclusions = [
        f'-"{keyword.replace(chr(34), "").strip()}"'
        for keyword in query.negative_terms
        if keyword.strip()
    ]
    return " ".join([terms, *exclusions])


def _is_allowed_job_result(url: str, title: str | None) -> bool:
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").casefold()
    title_text = (title or "").casefold()
    if any(marker in host for marker in _DEMO_HOST_MARKERS):
        return False
    if any(marker in title_text for marker in _DEMO_TITLE_MARKERS):
        return False
    return parsed.scheme == "https" and bool(host)


def _contains_excluded_keyword(
    title: str | None, snippet: str | None, keywords: tuple[str, ...]
) -> bool:
    haystack = " ".join(value for value in (title, snippet) if value).casefold()
    for keyword in keywords:
        normalized = keyword.strip().strip('"').casefold()
        if normalized and re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", haystack):
            return True
    return False


__all__ = ["TavilyConnector"]
