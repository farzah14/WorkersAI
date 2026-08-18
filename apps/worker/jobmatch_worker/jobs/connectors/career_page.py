"""SSRF-safe career-page fetcher that extracts visible job text.

Security model for every fetched URL (including redirect targets):

- HTTPS scheme only; URLs with embedded credentials are rejected;
- DNS is resolved exactly once per hop and every connection is pinned to
  a validated public address by ``PinnedHttpsTransport`` (private,
  loopback, link-local, reserved, and NAT64 addresses are rejected);
- ``urllib.robotparser`` policy is honored before each fetch;
- response headers are capped at 64 KiB and bodies are streamed and
  capped at 2 MiB;
- only ``text/html`` content is accepted;
- scripts, styles, and forms are stripped before visible text is
  extracted.

JavaScript is never executed and forms are never submitted in the MVP.
"""

import asyncio
import ipaddress
import json
import re
import socket
import urllib.parse
import urllib.robotparser
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from jobmatch_worker.jobs.connectors.base import (
    SourceConfigError,
    SourceDataError,
    SourceUnavailable,
    clean_optional_str,
    collapse_whitespace,
    parse_iso_datetime,
)
from jobmatch_worker.jobs.connectors.pinning_transport import (
    NoDnsError,
    NonPublicAddressError,
    PinnedHttpsTransport,
    is_public_address,
)
from jobmatch_worker.jobs.models import WorkMode

CareerPageResolver = Callable[
    [str], Awaitable[Sequence[ipaddress.IPv4Address | ipaddress.IPv6Address]]
]


@dataclass(frozen=True, slots=True)
class CareerPageContent:
    """Visible job-page text plus conservative structured metadata."""

    text: str
    title: str | None = None
    company: str | None = None
    location: str | None = None
    published_at: datetime | None = None
    work_mode: WorkMode | None = None
    is_closed: bool = False


@dataclass(frozen=True, slots=True)
class _JobPostingMetadata:
    title: str | None = None
    company: str | None = None
    location: str | None = None
    published_at: datetime | None = None
    work_mode: WorkMode | None = None
    is_closed: bool = False


_MAX_REDIRECTS = 3
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_ROBOTS_MAX_BYTES = 512 * 1024


async def _default_resolver(
    host: str,
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    infos = await asyncio.to_thread(
        socket.getaddrinfo, host, 443, proto=socket.IPPROTO_TCP
    )
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if isinstance(address, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
            addresses.append(address)
    return addresses


class CareerPageFetcher:
    """Fetch a permitted job page and return its visible text."""

    source_key = "career_page"
    max_bytes = 2 * 1024 * 1024
    timeout_seconds = 10.0
    user_agent = "jobmatch-worker/0.1"

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        resolver: CareerPageResolver | None = None,
        timeout: float = timeout_seconds,
        max_bytes: int = max_bytes,
        user_agent: str = user_agent,
        connection_factory: Callable | None = None,
    ) -> None:
        self._timeout = timeout
        self._max_bytes = max_bytes
        self._user_agent = user_agent
        self._resolver = resolver if resolver is not None else _default_resolver
        self._owns_client = client is None
        if client is not None:
            self._client = client
        else:
            transport = PinnedHttpsTransport(
                resolver=self._resolver,
                timeout=timeout,
                connection_factory=connection_factory,  # type: ignore[arg-type]
            )
            self._client = httpx.AsyncClient(
                timeout=timeout, follow_redirects=False, transport=transport
            )
        self._client.headers["User-Agent"] = user_agent

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def extract_text(self, url: str) -> str:
        return (await self.extract_content(url)).text

    async def extract_content(self, url: str) -> CareerPageContent:
        try:
            async with asyncio.timeout(self._timeout):
                return await self._extract_content(url)
        except TimeoutError as exc:
            raise SourceUnavailable(self.source_key, "request deadline exceeded") from exc

    async def _extract_content(self, url: str) -> CareerPageContent:
        current = url
        for _ in range(_MAX_REDIRECTS + 1):
            await self._validate_url(current)
            await self._assert_public_host(current)
            if not await self._robots_allowed(current):
                raise SourceDataError(
                    self.source_key, f"robots.txt disallows fetching {current}"
                )
            response = await self._get(current)
            if response.status_code in _REDIRECT_STATUSES:
                location = response.headers.get("location")
                await response.aclose()
                if not location:
                    raise SourceDataError(
                        self.source_key, "redirect without a Location header"
                    )
                current = urllib.parse.urljoin(current, location)
                continue
            try:
                self._assert_html(response)
                body = await self._read_capped(response)
                return _extract_page_content(body, source_key=self.source_key)
            finally:
                await response.aclose()
        raise SourceDataError(self.source_key, "too many redirects")

    async def _validate_url(self, url: str) -> None:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https":
            raise SourceConfigError(self.source_key, "only https URLs are allowed")
        if not parsed.netloc or not parsed.hostname:
            raise SourceDataError(self.source_key, "URL has no host")
        if parsed.username or parsed.password:
            raise SourceConfigError(self.source_key, "URL must not embed credentials")

    async def _assert_public_host(self, url: str) -> None:
        host = urllib.parse.urlsplit(url).hostname
        if not host:
            raise SourceDataError(self.source_key, "URL has no host")
        try:
            addresses = list(await self._resolver(host))
        except socket.gaierror as exc:
            raise SourceDataError(self.source_key, f"no DNS records for {host}") from exc
        if not addresses:
            raise SourceDataError(self.source_key, f"no DNS records for {host}")
        for address in addresses:
            if not is_public_address(address):
                raise SourceDataError(
                    self.source_key,
                    f"{host} resolves to non-public address {address}",
                )

    async def _robots_allowed(self, url: str) -> bool:
        parsed = urllib.parse.urlsplit(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        request = self._client.build_request("GET", robots_url)
        try:
            response = await self._client.send(request, stream=True)
        except (httpx.TimeoutException, httpx.TransportError):
            return True
        try:
            if response.status_code == 404:
                return True
            if response.status_code != 200:
                return True
            body = await self._read_capped(response, max_bytes=_ROBOTS_MAX_BYTES)
        finally:
            await response.aclose()
        parser = urllib.robotparser.RobotFileParser()
        parser.set_url(robots_url)
        try:
            lines = body.decode("utf-8", errors="replace").splitlines()
            parser.parse(lines)
            return parser.can_fetch("*", url)
        except Exception:  # noqa: BLE001 - malformed robots.txt fails open
            return True

    async def _get(self, url: str) -> httpx.Response:
        request = self._client.build_request("GET", url)
        try:
            response = await self._client.send(request, stream=True)
        except (NoDnsError, NonPublicAddressError) as exc:
            raise SourceDataError(self.source_key, str(exc)) from exc
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise SourceUnavailable(
                self.source_key, f"transport error: {type(exc).__name__}"
            ) from exc
        status = response.status_code
        if status in (408, 429) or status >= 500:
            await response.aclose()
            raise SourceUnavailable(self.source_key, f"HTTP {status}")
        if status >= 400:
            await response.aclose()
            raise SourceDataError(self.source_key, f"HTTP {status}")
        return response

    def _assert_html(self, response: httpx.Response) -> None:
        media_type = response.headers.get("content-type", "").split(";")[0].strip().casefold()
        if media_type != "text/html":
            raise SourceDataError(
                self.source_key, f"unsupported content type: {media_type or 'none'}"
            )

    async def _read_capped(
        self, response: httpx.Response, *, max_bytes: int | None = None
    ) -> bytes:
        limit = max_bytes if max_bytes is not None else self._max_bytes
        content_length = response.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > limit:
            raise SourceDataError(self.source_key, "response body exceeds size cap")
        chunks: list[bytes] = []
        total = 0
        try:
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > limit:
                    raise SourceDataError(self.source_key, "response body exceeds size cap")
                chunks.append(chunk)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise SourceUnavailable(
                self.source_key, f"transport error: {type(exc).__name__}"
            ) from exc
        return b"".join(chunks)


def _visible_text(body: bytes, *, source_key: str) -> str:
    soup = BeautifulSoup(body, "html.parser")
    for tag in soup.find_all(
        ["script", "style", "form", "noscript", "iframe", "svg", "header", "footer", "nav"]
    ):
        tag.decompose()
    text = collapse_whitespace(soup.get_text(separator="\n"))
    if not text:
        raise SourceDataError(source_key, "no visible text found")
    return text


def _extract_page_content(body: bytes, *, source_key: str) -> CareerPageContent:
    soup = BeautifulSoup(body, "html.parser")
    metadata = _extract_job_posting_metadata(soup)
    return CareerPageContent(
        text=_visible_text(body, source_key=source_key),
        title=metadata.title,
        company=metadata.company,
        location=metadata.location,
        published_at=metadata.published_at,
        work_mode=metadata.work_mode,
        is_closed=metadata.is_closed,
    )


def _extract_job_posting_metadata(soup: BeautifulSoup) -> _JobPostingMetadata:
    is_closed = _is_closed_page(soup)
    for node in _iter_job_posting_nodes(soup):
        return _JobPostingMetadata(
            title=clean_optional_str(node.get("title")),
            company=_organization_name(node.get("hiringOrganization")),
            location=_job_location(node.get("jobLocation")),
            published_at=parse_iso_datetime(node.get("datePosted")),
            work_mode=_work_mode(node.get("jobLocationType"))
            or _work_mode(node.get("workplaceType")),
            is_closed=is_closed,
        )
    return _extract_meta_job_metadata(soup, is_closed=is_closed)


def _extract_meta_job_metadata(
    soup: BeautifulSoup, *, is_closed: bool
) -> _JobPostingMetadata:
    description = _meta_content(soup, "name", "description") or ""
    page_title = _meta_content(soup, "property", "og:title") or ""
    if not page_title and soup.title is not None:
        page_title = collapse_whitespace(soup.title.get_text(" "))

    title: str | None = None
    company: str | None = None
    location: str | None = None
    summary_match = re.search(
        r"\bapply\s+for\s+(?P<title>.+?)\s+at\s+(?P<company>[^.]+)\.",
        description,
        flags=re.IGNORECASE,
    )
    if summary_match:
        title = clean_optional_str(summary_match.group("title"))
        company = clean_optional_str(summary_match.group("company"))
    else:
        title_match = re.search(
            r"^(?P<title>.+?)\s+jobs?\s+at\s+(?P<company>[^,|()]+)"
            r"(?:,\s*(?P<location>[^|()]+))?",
            page_title,
            flags=re.IGNORECASE,
        )
        if title_match:
            title = clean_optional_str(title_match.group("title"))
            company = clean_optional_str(title_match.group("company"))
            location = clean_optional_str(title_match.group("location"))

    location_match = re.search(
        r"\bjob\s+location\s*:\s*(?P<location>[^.;|]+)",
        description,
        flags=re.IGNORECASE,
    )
    if location_match:
        location = clean_optional_str(location_match.group("location"))

    return _JobPostingMetadata(
        title=title,
        company=company,
        location=location,
        published_at=_meta_published_at(soup),
        work_mode=_work_mode_from_text(f"{page_title} {description}"),
        is_closed=is_closed,
    )


def _meta_content(soup: BeautifulSoup, attribute: str, value: str) -> str | None:
    for tag in soup.find_all("meta"):
        if str(tag.get(attribute, "")).casefold() != value.casefold():
            continue
        return clean_optional_str(tag.get("content"))
    return None


def _meta_published_at(soup: BeautifulSoup) -> datetime | None:
    for attribute, value in (
        ("property", "article:published_time"),
        ("name", "datePosted"),
        ("name", "datePublished"),
    ):
        parsed = parse_iso_datetime(_meta_content(soup, attribute, value))
        if parsed is not None:
            return parsed
    time_tag = soup.find("time", attrs={"datetime": True})
    if time_tag is not None:
        return parse_iso_datetime(time_tag.get("datetime"))
    return None


def _work_mode_from_text(value: str) -> WorkMode | None:
    normalized = value.casefold()
    if re.search(r"\bremote\b|\bwork\s+from\s+home\b", normalized):
        return "remote"
    if re.search(r"\bhybrid\b", normalized):
        return "hybrid"
    if re.search(r"\bon[- ]site\b|\bonsite\b", normalized):
        return "on-site"
    return None


def _is_closed_page(soup: BeautifulSoup) -> bool:
    title = soup.title.get_text(" ") if soup.title is not None else ""
    visible = soup.get_text(" ")
    normalized = collapse_whitespace(f"{title} {visible}").casefold()
    return any(
        marker in normalized
        for marker in ("this job was closed", "(closed)", "job is closed", "position has been filled")
    )


def _iter_job_posting_nodes(soup: BeautifulSoup) -> list[dict[str, object]]:
    nodes: list[dict[str, object]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        try:
            payload = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        for candidate in candidates:
            if isinstance(candidate, dict) and isinstance(candidate.get("@graph"), list):
                candidates.extend(candidate["@graph"])
            elif isinstance(candidate, dict):
                node_type = candidate.get("@type")
                types = node_type if isinstance(node_type, list) else [node_type]
                if "JobPosting" in types:
                    nodes.append(candidate)
    return nodes


def _organization_name(value: object) -> str | None:
    if isinstance(value, dict):
        return clean_optional_str(value.get("name"))
    return clean_optional_str(value)


def _job_location(value: object) -> str | None:
    locations = value if isinstance(value, list) else [value]
    for location in locations:
        if not isinstance(location, dict):
            continue
        address = location.get("address")
        if isinstance(address, dict):
            parts: list[str] = []
            for key in ("streetAddress", "addressLocality", "addressRegion", "addressCountry"):
                part = address.get(key)
                if isinstance(part, dict):
                    part = part.get("name")
                cleaned = clean_optional_str(part)
                if cleaned and cleaned not in parts:
                    parts.append(cleaned)
            if parts:
                return ", ".join(parts)
        place_name = clean_optional_str(location.get("name"))
        if place_name:
            return place_name
    return None


def _work_mode(value: object) -> WorkMode | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold().replace("_", "-")
    if normalized in {"telecommute", "remote"}:
        return "remote"
    if normalized == "hybrid":
        return "hybrid"
    if normalized in {"onsite", "on-site", "on site"}:
        return "on-site"
    return None


__all__ = ["CareerPageContent", "CareerPageFetcher", "CareerPageResolver"]
