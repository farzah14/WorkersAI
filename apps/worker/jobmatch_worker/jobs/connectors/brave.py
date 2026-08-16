"""Brave Search API connector producing candidate URLs.

Search-engine snippets are search-result summaries, not job descriptions:
they are mapped to ``DiscoveryCandidateUrl`` metadata only and are never
promoted to full job descriptions. The API key stays server-side.
"""

from typing import Any

import httpx
from pydantic import ValidationError

from jobmatch_worker.jobs.connectors.base import (
    SourceConfigError,
    SourceDataError,
    clean_optional_str,
    get_json_with_retry,
    parse_json,
)
from jobmatch_worker.jobs.models import DiscoveredJob, DiscoveryCandidateUrl
from jobmatch_worker.jobs.query import SearchQuery

BRAVE_SEARCH_API_URL = "https://api.search.brave.com/res/v1/web/search"
BRAVE_MAX_COUNT = 20
BRAVE_DEFAULT_COUNT = 10
BRAVE_SAFE_SEARCH = "moderate"


class BraveConnector:
    """Search-engine connector using the official Brave Search API.

    One query is sent at a time, ``count`` is capped at 20, and safe search
    is set to ``moderate`` (appropriate for normal web search).
    """

    source_key = "brave"

    def __init__(
        self,
        *,
        api_key: str,
        client: httpx.AsyncClient | None = None,
        timeout: float = 15.0,
        count: int = BRAVE_DEFAULT_COUNT,
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
                self.source_key, "BRAVE_SEARCH_API_KEY is not configured"
            )
        if self._count > BRAVE_MAX_COUNT:
            raise SourceConfigError(
                self.source_key, f"count must not exceed {BRAVE_MAX_COUNT}"
            )

        terms = [query.terms]
        terms.extend(
            f'-"{term}"' if " " in term else f"-{term}"
            for term in query.negative_terms
        )
        response = await get_json_with_retry(
            self._client,
            url=BRAVE_SEARCH_API_URL,
            params={"q": " ".join(terms), "count": self._count, "safesearch": BRAVE_SAFE_SEARCH},
            headers={
                "X-Subscription-Token": self._api_key,
                "Accept": "application/json",
            },
            timeout=self._timeout,
            source_key=self.source_key,
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
                candidates.append(
                    DiscoveryCandidateUrl(
                        url=url,
                        title=clean_optional_str(result.get("title")),
                        snippet=clean_optional_str(result.get("description")),
                    )
                )
            except ValidationError:
                continue
        return candidates


def _extract_results(source_key: str, body: Any) -> list[dict[str, Any]]:
    if not isinstance(body, dict):
        raise SourceDataError(source_key, "unexpected response shape")
    web = body.get("web")
    results = web.get("results") if isinstance(web, dict) else None
    if not isinstance(results, list):
        raise SourceDataError(source_key, "unexpected response shape")
    return [result for result in results if isinstance(result, dict)]


__all__ = ["BraveConnector"]