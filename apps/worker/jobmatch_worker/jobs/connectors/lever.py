"""Lever public postings connector.

Fetches published postings from the public Lever Postings API
(``/v0/postings/{site}?mode=json``) and maps hosted URL, text description,
and the location/team/commitment categories into ``DiscoveredJob``. The
site name is the company's public Lever slug; Lever does not expose a
company name in this endpoint, so the site name is used as the company.
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
    parse_json,
    parse_ms_epoch,
    strip_html_to_text,
)
from jobmatch_worker.jobs.models import (
    DiscoveredJob,
    DiscoveryCandidateUrl,
    EmploymentType,
    WorkMode,
)
from jobmatch_worker.jobs.query import SearchQuery

LEVER_API_URL = "https://api.lever.co/v0/postings/{site}"

_COMMITMENT_MAP: dict[str, EmploymentType] = {
    "full-time": "full-time",
    "full time": "full-time",
    "part-time": "part-time",
    "part time": "part-time",
    "contract": "contract",
    "contractor": "contract",
    "temporary": "temporary",
    "temp": "temporary",
    "internship": "internship",
    "intern": "internship",
    "apprenticeship": "apprenticeship",
    "volunteer": "volunteer",
    "volunteering": "volunteer",
    "freelance": "freelance",
    "freelancer": "freelance",
}

_WORK_MODE_MAP: dict[str, WorkMode] = {
    "remote": "remote",
    "hybrid": "hybrid",
    "on-site": "on-site",
    "onsite": "on-site",
    "on site": "on-site",
}
_BLOCKED_SITE_NAMES = frozenset({"leverdemo"})


class LeverConnector:
    """Public Lever postings connector mapping published jobs."""

    source_key = "lever"

    def __init__(
        self,
        *,
        site_name: str,
        client: httpx.AsyncClient | None = None,
        timeout: float = 15.0,
        retries: int = 1,
    ) -> None:
        self._site_name = site_name
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
        if not self._site_name:
            raise SourceConfigError(self.source_key, "LEVER_SITE_NAME is not configured")
        if self._site_name.strip().casefold() in _BLOCKED_SITE_NAMES:
            raise SourceConfigError(self.source_key, "demo Lever site is not allowed")
        response = await get_json_with_retry(
            self._client,
            url=LEVER_API_URL.format(site=self._site_name),
            params={"mode": "json"},
            headers={"Accept": "application/json"},
            timeout=self._timeout,
            source_key=self.source_key,
            retries=self._retries,
        )
        body = parse_json(self.source_key, response)
        if not isinstance(body, list):
            raise SourceDataError(self.source_key, "unexpected response shape")

        result: list[DiscoveredJob | DiscoveryCandidateUrl] = []
        for posting in body:
            discovered = _map_posting(self.source_key, self._site_name, posting)
            if discovered is not None:
                result.append(discovered)
        return result


def _map_posting(
    source_key: str, site_name: str, posting: Any
) -> DiscoveredJob | None:
    if not isinstance(posting, dict):
        return None
    title = posting.get("text")
    original_url = posting.get("hostedUrl")
    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(original_url, str) or not original_url.strip():
        return None
    if not _is_https_url(original_url):
        return None
    categories = posting.get("categories")
    if not isinstance(categories, dict):
        categories = {}
    team = categories.get("team")
    description = clean_optional_str(posting.get("descriptionPlain")) or strip_html_to_text(
        posting.get("description")
    )
    if isinstance(team, str) and team.strip():
        description = f"{description}\nTeam: {team.strip()}".strip() if description else team.strip()
    if not description:
        description = title.strip()
    try:
        return DiscoveredJob(
            source_name="Lever",
            source_key=source_key,
            title=title,
            company=site_name,
            location=clean_optional_str(categories.get("location")),
            work_mode=_map_work_mode(posting.get("workplaceType")),
            employment_type=_map_commitment(categories.get("commitment")),
            description=description,
            original_url=original_url,
            published_at=parse_ms_epoch(posting.get("createdAt")),
        )
    except ValidationError:
        return None


def _map_commitment(value: object) -> EmploymentType | None:
    if not isinstance(value, str):
        return None
    return _COMMITMENT_MAP.get(value.strip().casefold())


def _map_work_mode(value: object) -> WorkMode | None:
    if not isinstance(value, str):
        return None
    return _WORK_MODE_MAP.get(value.strip().casefold())


def _is_https_url(value: str) -> bool:
    parsed = urllib.parse.urlsplit(value)
    return (
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and parsed.username is None
        and parsed.password is None
    )


__all__ = [
    "_BLOCKED_SITE_NAMES",
    "_COMMITMENT_MAP",
    "_WORK_MODE_MAP",
    "LeverConnector",
    "_map_commitment",
    "_map_work_mode",
]
