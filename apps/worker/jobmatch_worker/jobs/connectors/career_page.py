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
import socket
import urllib.parse
import urllib.robotparser
from collections.abc import Awaitable, Callable, Sequence

import httpx
from bs4 import BeautifulSoup

from jobmatch_worker.jobs.connectors.base import (
    SourceConfigError,
    SourceDataError,
    SourceUnavailable,
    collapse_whitespace,
)
from jobmatch_worker.jobs.connectors.pinning_transport import (
    NoDnsError,
    NonPublicAddressError,
    PinnedHttpsTransport,
    is_public_address,
)

CareerPageResolver = Callable[
    [str], Awaitable[Sequence[ipaddress.IPv4Address | ipaddress.IPv6Address]]
]

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
                return _visible_text(body, source_key=self.source_key)
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


__all__ = ["CareerPageFetcher", "CareerPageResolver"]