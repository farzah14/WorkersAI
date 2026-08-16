"""Greenhouse public job-board connector.

Fetches published jobs from the public Greenhouse board API
(``/v1/boards/{board_token}/jobs?content=true``) and maps them to
``DiscoveredJob``. The board token is the company's public board slug;
Greenhouse does not expose a company name in this endpoint, so the token
is used as the company name.
"""

import urllib.parse
from typing import Any

import httpx
from pydantic import ValidationError

from jobmatch_worker.jobs.connectors.base import (
    SourceConfigError,
    SourceDataError,
    clean_optional_str,
    get_json_with_retry,
    parse_iso_datetime,
    parse_json,
    strip_html_to_text,
)
from jobmatch_worker.jobs.models import DiscoveredJob, DiscoveryCandidateUrl
from jobmatch_worker.jobs.query import SearchQuery

GREENHOUSE_API_URL = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
_MAX_MAPPED_JOBS = 200


class GreenhouseConnector:
    """Public Greenhouse board connector mapping published jobs."""

    source_key = "greenhouse"

    def __init__(
        self,
        *,
        board_token: str,
        client: httpx.AsyncClient | None = None,
        timeout: float = 15.0,
        retries: int = 1,
    ) -> None:
        self._board_token = board_token
        self._timeout = timeout
        self._retries = retries
        self._owns_client = client is None
        self._client = client if client is not None else httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def search(
        self, query: SearchQuery
    ) -> list[DiscoveredJob | DiscoveryCandidateUrl]:
        if not self._board_token:
            raise SourceConfigError(
                self.source_key, "GREENHOUSE_BOARD_TOKEN is not configured"
            )
        response = await get_json_with_retry(
            self._client,
            url=GREENHOUSE_API_URL.format(board_token=self._board_token),
            params={"content": "true"},
            headers={"Accept": "application/json"},
            timeout=self._timeout,
            source_key=self.source_key,
            retries=self._retries,
        )
        body = parse_json(self.source_key, response)
        jobs = body.get("jobs") if isinstance(body, dict) else None
        if not isinstance(jobs, list):
            raise SourceDataError(self.source_key, "unexpected response shape")
        if len(jobs) > _MAX_MAPPED_JOBS:
            raise SourceDataError(self.source_key, "source result limit exceeded")

        result: list[DiscoveredJob | DiscoveryCandidateUrl] = []
        for job in jobs:
            discovered = _map_job(self.source_key, self._board_token, job)
            if discovered is not None:
                result.append(discovered)
        return result


def _map_job(
    source_key: str, board_token: str, job: Any
) -> DiscoveredJob | None:
    if not isinstance(job, dict):
        return None
    title = job.get("title")
    original_url = job.get("absolute_url")
    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(original_url, str) or not original_url.strip():
        return None
    if not _is_https_url(original_url):
        return None
    location = job.get("location")
    location_name = location.get("name") if isinstance(location, dict) else None
    description = strip_html_to_text(job.get("content"))
    if not description:
        description = title.strip()
    try:
        return DiscoveredJob(
            source_name="Greenhouse",
            source_key=source_key,
            title=title,
            company=board_token,
            location=clean_optional_str(location_name),
            description=description,
            original_url=original_url,
            published_at=parse_iso_datetime(job.get("updated_at")),
        )
    except ValidationError:
        return None


def _is_https_url(value: str) -> bool:
    parsed = urllib.parse.urlsplit(value)
    return (
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and parsed.username is None
        and parsed.password is None
    )


__all__ = ["GreenhouseConnector"]
