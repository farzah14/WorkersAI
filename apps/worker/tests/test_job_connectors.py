import asyncio
import ipaddress
import urllib.parse
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import ValidationError
from pytest_httpx import HTTPXMock

from jobmatch_worker.jobs.connectors.base import (
    SourceConfigError,
    SourceDataError,
    SourceUnavailable,
)
from jobmatch_worker.jobs.connectors.brave import BraveConnector
from jobmatch_worker.jobs.connectors.career_page import CareerPageFetcher
from jobmatch_worker.jobs.connectors.greenhouse import GreenhouseConnector
from jobmatch_worker.jobs.connectors.lever import LeverConnector
from jobmatch_worker.jobs.connectors.pinning_transport import (
    NonPublicAddressError,
    PinnedHttpsTransport,
)
from jobmatch_worker.jobs.models import DiscoveredJob, DiscoveryCandidateUrl
from jobmatch_worker.jobs.query import SearchQuery

QUERY = SearchQuery("Data Engineer Jakarta Indonesia")

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
BRAVE_URL_ENCODED = (
    BRAVE_URL
    + "?"
    + urllib.parse.urlencode(
        {"q": "Data Engineer Jakarta Indonesia", "count": 10, "safesearch": "moderate"}
    )
)

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true"

LEVER_URL = "https://api.lever.co/v0/postings/acme?mode=json"

BRAVE_BODY = {
    "web": {
        "results": [
            {
                "title": "Data Engineer at Acme",
                "url": "https://careers.acme.com/jobs/data-engineer",
                "description": "Join our data team in Jakarta.",
            },
            {
                "title": "Insecure copy",
                "url": "http://insecure.example.com/job",
                "description": "must be filtered out",
            },
            {"title": "Missing URL", "url": "", "description": "must be filtered out"},
        ]
    }
}

GREENHOUSE_BODY = {
    "jobs": [
        {
            "id": 4034187003,
            "title": "Data Engineer",
            "updated_at": "2026-08-01T10:00:00.000Z",
            "location": {"name": "Jakarta, Indonesia"},
            "absolute_url": "https://boards.greenhouse.io/acme/jobs/4034187003",
            "content": "<p>Build data pipelines.</p><script>alert('nope')</script>",
        }
    ]
}

LEVER_BODY = [
    {
        "id": "abc123",
        "text": "Data Engineer",
        "hostedUrl": "https://jobs.lever.co/acme/abc123",
        "categories": {
            "location": "Jakarta",
            "commitment": "Full-time",
            "team": "Engineering",
        },
        "createdAt": 1783000000000,
        "descriptionPlain": "Build reliable data pipelines.",
    },
    {
        "id": "def456",
        "text": "Data Analyst",
        "hostedUrl": "https://jobs.lever.co/acme/def456",
        "categories": {"commitment": "Fellowship"},
        "createdAt": 1783000001000,
    },
]


async def _public_resolver(
    host: str,
) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    return [ipaddress.ip_address("93.184.216.34")]


# --- DiscoveryCandidateUrl model ---


def test_discovery_candidate_url_accepts_url_with_optional_fields() -> None:
    candidate = DiscoveryCandidateUrl(
        url="https://careers.acme.com/jobs/data-engineer",
        title="Data Engineer at Acme",
        snippet="Join our data team.",
    )
    assert candidate.url == "https://careers.acme.com/jobs/data-engineer"
    assert candidate.title == "Data Engineer at Acme"
    assert candidate.snippet == "Join our data team."


def test_discovery_candidate_url_defaults_title_and_snippet() -> None:
    candidate = DiscoveryCandidateUrl(url="https://careers.acme.com/jobs/1")
    assert candidate.title is None
    assert candidate.snippet is None


@pytest.mark.parametrize(
    "url",
    [
        "http://careers.acme.com/jobs/1",
        "https://",
        "https://user:pass@careers.acme.com/jobs/1",
        "ftp://careers.acme.com/jobs/1",
    ],
)
def test_discovery_candidate_url_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(ValidationError):
        DiscoveryCandidateUrl(url=url)


# --- Error taxonomy ---


def test_source_errors_carry_source_key_and_never_raw_payload() -> None:
    error = SourceUnavailable("brave", "HTTP 500")
    assert error.source_key == "brave"
    assert "brave: HTTP 500" in str(error)


# --- Brave Search connector ---


async def test_brave_maps_results_to_candidates(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=BRAVE_URL_ENCODED, json=BRAVE_BODY)
    connector = BraveConnector(api_key="test-key", client=httpx.AsyncClient())

    candidates = await connector.search(QUERY)

    assert isinstance(candidates, list)
    assert len(candidates) == 1
    assert isinstance(candidates[0], DiscoveryCandidateUrl)
    assert candidates[0].url == "https://careers.acme.com/jobs/data-engineer"
    assert candidates[0].title == "Data Engineer at Acme"
    assert candidates[0].snippet == "Join our data team in Jakarta."

    request = httpx_mock.get_requests()[-1]
    assert request.url.params["q"] == "Data Engineer Jakarta Indonesia"
    assert request.url.params["count"] == "10"
    assert request.url.params["safesearch"] == "moderate"
    assert request.headers["x-subscription-token"] == "test-key"
    await connector.aclose()


async def test_brave_500_raises_source_unavailable(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=BRAVE_URL_ENCODED, status_code=500)
    httpx_mock.add_response(url=BRAVE_URL_ENCODED, status_code=500)
    connector = BraveConnector(api_key="test-key", client=httpx.AsyncClient())

    with pytest.raises(SourceUnavailable) as excinfo:
        await connector.search(QUERY)
    assert excinfo.value.source_key == "brave"
    await connector.aclose()


async def test_brave_401_is_config_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=BRAVE_URL_ENCODED, status_code=401)
    connector = BraveConnector(api_key="bad-key", client=httpx.AsyncClient())

    with pytest.raises(SourceConfigError) as excinfo:
        await connector.search(QUERY)
    assert excinfo.value.source_key == "brave"
    await connector.aclose()


async def test_brave_missing_api_key_is_config_error() -> None:
    connector = BraveConnector(api_key="", client=httpx.AsyncClient())
    with pytest.raises(SourceConfigError):
        await connector.search(QUERY)


async def test_brave_non_json_body_is_data_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=BRAVE_URL_ENCODED, text="<html>gateway error</html>")
    connector = BraveConnector(api_key="test-key", client=httpx.AsyncClient())

    with pytest.raises(SourceDataError) as excinfo:
        await connector.search(QUERY)
    assert excinfo.value.source_key == "brave"
    await connector.aclose()


async def test_brave_unexpected_shape_is_data_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=BRAVE_URL_ENCODED, json={"web": {"results": "oops"}})
    connector = BraveConnector(api_key="test-key", client=httpx.AsyncClient())

    with pytest.raises(SourceDataError):
        await connector.search(QUERY)
    await connector.aclose()


# --- Greenhouse connector ---


async def test_greenhouse_maps_board_jobs(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=GREENHOUSE_URL, json=GREENHOUSE_BODY)
    connector = GreenhouseConnector(board_token="acme", client=httpx.AsyncClient())

    jobs = await connector.search(QUERY)

    assert len(jobs) == 1
    job = jobs[0]
    assert isinstance(job, DiscoveredJob)
    assert job.source_key == "greenhouse"
    assert job.title == "Data Engineer"
    assert job.company == "acme"
    assert job.location == "Jakarta, Indonesia"
    assert job.original_url == "https://boards.greenhouse.io/acme/jobs/4034187003"
    assert "Build data pipelines." in job.description
    assert "alert" not in job.description
    assert job.published_at == datetime(2026, 8, 1, 10, 0, tzinfo=UTC)
    assert job.work_mode is None
    assert job.employment_type is None
    await connector.aclose()


async def test_greenhouse_skips_incomplete_jobs(httpx_mock: HTTPXMock) -> None:
    body = {
        "jobs": [
            GREENHOUSE_BODY["jobs"][0],
            {"id": 1, "title": "No URL", "updated_at": "2026-08-01T00:00:00.000Z"},
            {"id": 2, "absolute_url": "https://boards.greenhouse.io/acme/jobs/2"},
            {
                "id": 3,
                "title": "Insecure",
                "absolute_url": "http://boards.greenhouse.io/acme/jobs/3",
            },
        ]
    }
    httpx_mock.add_response(url=GREENHOUSE_URL, json=body)
    connector = GreenhouseConnector(board_token="acme", client=httpx.AsyncClient())

    jobs = await connector.search(QUERY)

    assert len(jobs) == 1
    assert jobs[0].title == "Data Engineer"
    await connector.aclose()


async def test_greenhouse_500_raises_source_unavailable(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=GREENHOUSE_URL, status_code=500)
    httpx_mock.add_response(url=GREENHOUSE_URL, status_code=500)
    connector = GreenhouseConnector(board_token="acme", client=httpx.AsyncClient())

    with pytest.raises(SourceUnavailable) as excinfo:
        await connector.search(QUERY)
    assert excinfo.value.source_key == "greenhouse"
    await connector.aclose()


async def test_greenhouse_missing_token_is_config_error() -> None:
    connector = GreenhouseConnector(board_token="", client=httpx.AsyncClient())
    with pytest.raises(SourceConfigError):
        await connector.search(QUERY)


async def test_greenhouse_unexpected_body_is_data_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=GREENHOUSE_URL, json={"bogus": True})
    connector = GreenhouseConnector(board_token="acme", client=httpx.AsyncClient())

    with pytest.raises(SourceDataError):
        await connector.search(QUERY)
    await connector.aclose()


# --- Lever connector ---


async def test_lever_maps_postings(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=LEVER_URL, json=LEVER_BODY)
    connector = LeverConnector(site_name="acme", client=httpx.AsyncClient())

    jobs = await connector.search(QUERY)

    assert len(jobs) == 2
    job = jobs[0]
    assert isinstance(job, DiscoveredJob)
    assert job.source_key == "lever"
    assert job.title == "Data Engineer"
    assert job.company == "acme"
    assert job.original_url == "https://jobs.lever.co/acme/abc123"
    assert job.location == "Jakarta"
    assert job.employment_type == "full-time"
    assert "Build reliable data pipelines." in job.description
    assert "Engineering" in job.description
    assert job.published_at == datetime.fromtimestamp(1783000000, tz=UTC)

    analyst = jobs[1]
    assert analyst.title == "Data Analyst"
    assert analyst.location is None
    assert analyst.employment_type is None
    await connector.aclose()


async def test_lever_500_raises_source_unavailable(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=LEVER_URL, status_code=500)
    httpx_mock.add_response(url=LEVER_URL, status_code=500)
    connector = LeverConnector(site_name="acme", client=httpx.AsyncClient())

    with pytest.raises(SourceUnavailable) as excinfo:
        await connector.search(QUERY)
    assert excinfo.value.source_key == "lever"
    await connector.aclose()


async def test_lever_missing_site_name_is_config_error() -> None:
    connector = LeverConnector(site_name="", client=httpx.AsyncClient())
    with pytest.raises(SourceConfigError):
        await connector.search(QUERY)


# --- Career page fetcher ---


async def test_career_page_requires_https_scheme() -> None:
    fetcher = CareerPageFetcher(
        client=httpx.AsyncClient(),
        resolver=_public_resolver,
    )
    with pytest.raises(SourceConfigError):
        await fetcher.extract_text("http://careers.acme.com/jobs/1")


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.5", "192.168.1.10", "169.254.169.254", "::1", "fe80::1"],
)
async def test_career_page_rejects_private_resolution(address: str) -> None:
    async def resolver(
        host: str,
    ) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        return [ipaddress.ip_address(address)]

    fetcher = CareerPageFetcher(client=httpx.AsyncClient(), resolver=resolver)

    with pytest.raises(SourceDataError):
        await fetcher.extract_text("https://internal.corp.example/jobs/1")


async def test_career_page_robots_denial(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://careers.acme.com/robots.txt",
        text="User-agent: *\nDisallow: /jobs/",
    )
    fetcher = CareerPageFetcher(
        client=httpx.AsyncClient(),
        resolver=_public_resolver,
    )

    with pytest.raises(SourceDataError) as excinfo:
        await fetcher.extract_text("https://careers.acme.com/jobs/data-engineer")
    assert "robots" in str(excinfo.value)
    requested = [str(request.url) for request in httpx_mock.get_requests()]
    assert requested == ["https://careers.acme.com/robots.txt"]


async def test_career_page_strips_scripts_styles_and_forms(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://careers.acme.com/robots.txt",
        text="User-agent: *\nAllow: /",
    )
    page = """
    <html><head><title>Jobs</title>
    <script>var secret = "s3cret-script";</script>
    <style>body { color: red; }</style></head>
    <body>
      <form action="/apply"><input name="secret-field"></form>
      <nav>Nav links</nav>
      <p>Data Engineer needed in Jakarta.</p>
      <p>Apply now.</p>
    </body></html>
    """
    httpx_mock.add_response(
        url="https://careers.acme.com/jobs/data-engineer",
        html=page,
    )
    fetcher = CareerPageFetcher(
        client=httpx.AsyncClient(),
        resolver=_public_resolver,
    )

    text = await fetcher.extract_text("https://careers.acme.com/jobs/data-engineer")

    assert "Data Engineer needed in Jakarta." in text
    assert "Apply now." in text
    assert "s3cret-script" not in text
    assert "secret-field" not in text
    assert "Nav links" not in text


async def test_career_page_rejects_oversize_body(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://careers.acme.com/robots.txt",
        text="User-agent: *\nAllow: /",
    )
    httpx_mock.add_response(
        url="https://careers.acme.com/jobs/big",
        html="<p>big</p>",
        headers={"content-length": str(3 * 1024 * 1024)},
    )
    fetcher = CareerPageFetcher(
        client=httpx.AsyncClient(),
        resolver=_public_resolver,
    )

    with pytest.raises(SourceDataError) as excinfo:
        await fetcher.extract_text("https://careers.acme.com/jobs/big")
    assert "size" in str(excinfo.value)


async def test_career_page_rejects_non_html_content_type(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://careers.acme.com/robots.txt",
        text="User-agent: *\nAllow: /",
    )
    httpx_mock.add_response(
        url="https://careers.acme.com/resume.pdf",
        headers={"content-type": "application/pdf"},
        content=b"%PDF-1.4 fake",
    )
    fetcher = CareerPageFetcher(
        client=httpx.AsyncClient(),
        resolver=_public_resolver,
    )

    with pytest.raises(SourceDataError) as excinfo:
        await fetcher.extract_text("https://careers.acme.com/resume.pdf")
    assert "content type" in str(excinfo.value)


# --- Connector isolation ---


async def test_one_connector_500_does_not_prevent_another_from_returning(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(url=BRAVE_URL_ENCODED, status_code=500)
    httpx_mock.add_response(url=BRAVE_URL_ENCODED, status_code=500)
    httpx_mock.add_response(url=GREENHOUSE_URL, json=GREENHOUSE_BODY)

    brave = BraveConnector(api_key="test-key", client=httpx.AsyncClient())
    greenhouse = GreenhouseConnector(board_token="acme", client=httpx.AsyncClient())

    with pytest.raises(SourceUnavailable):
        await brave.search(QUERY)

    jobs = await greenhouse.search(QUERY)
    assert len(jobs) == 1
    assert isinstance(jobs[0], DiscoveredJob)
    assert jobs[0].title == "Data Engineer"
    await brave.aclose()
    await greenhouse.aclose()


# --- Pinned HTTPS transport (DNS rebinding protection) ---


class _FakeReader:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    async def readuntil(self, sep: bytes) -> bytes:
        index = self._data.find(sep, self._pos)
        if index == -1:
            raise asyncio.IncompleteReadError(self._data[self._pos:], len(sep))
        end = index + len(sep)
        chunk = self._data[self._pos:end]
        self._pos = end
        return chunk

    async def read(self, n: int = -1) -> bytes:
        if n < 0:
            chunk = self._data[self._pos:]
            self._pos = len(self._data)
        else:
            chunk = self._data[self._pos : self._pos + n]
            self._pos += len(chunk)
        return chunk


class _TrickleReader:
    """Simulates a socket that only buffers a few bytes per read call."""

    def __init__(self, data: bytes, step: int = 7) -> None:
        self._data = data
        self._pos = 0
        self._step = step

    async def readuntil(self, sep: bytes) -> bytes:
        index = self._data.find(sep, self._pos)
        if index == -1:
            raise asyncio.IncompleteReadError(self._data[self._pos:], len(sep))
        end = index + len(sep)
        chunk = self._data[self._pos:end]
        self._pos = end
        return chunk

    async def read(self, n: int = -1) -> bytes:
        if n < 0:
            chunk = self._data[self._pos:]
            self._pos = len(self._data)
        else:
            take = min(n, self._step)
            chunk = self._data[self._pos : self._pos + take]
            self._pos += len(chunk)
        return chunk


class _FakeWriter:
    def __init__(self) -> None:
        self.written = b""
        self.closed = False

    def write(self, data: bytes) -> None:
        self.written += data

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


async def test_pinned_transport_connects_to_validated_ip_only() -> None:
    connected: list[tuple[str, str | None]] = []

    async def factory(
        host: str, port: int, ssl_context: object, server_hostname: str | None
    ) -> tuple[_FakeReader, _FakeWriter]:
        connected.append((host, server_hostname))
        body = b"hello"
        return (
            _FakeReader(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/html\r\n"
                b"Content-Length: 5\r\n"
                b"\r\n"
                + body
            ),
            _FakeWriter(),
        )

    transport = PinnedHttpsTransport(
        resolver=_public_resolver, connection_factory=factory  # type: ignore[arg-type]
    )
    client = httpx.AsyncClient(transport=transport)

    response = await client.get("https://careers.acme.com/jobs/data-engineer")

    assert connected == [("93.184.216.34", "careers.acme.com")]
    assert response.status_code == 200
    assert (await response.aread()) == b"hello"
    await client.aclose()


async def test_pinned_transport_rejects_private_address_without_connecting() -> None:
    async def resolver(
        host: str,
    ) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        return [ipaddress.ip_address("10.0.0.5")]

    async def factory(
        host: str, port: int, ssl_context: object, server_hostname: str | None
    ) -> tuple[_FakeReader, _FakeWriter]:
        pytest.fail("must never connect to an unvalidated address")

    transport = PinnedHttpsTransport(
        resolver=resolver, connection_factory=factory  # type: ignore[arg-type]
    )

    with pytest.raises(NonPublicAddressError):
        await transport.handle_async_request(
            httpx.Request("GET", "https://internal.corp.example/jobs/1")
        )


async def test_pinned_transport_rejects_nat64_embedded_private_address() -> None:
    async def resolver(
        host: str,
    ) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        return [ipaddress.ip_address("64:ff9b::a00:1")]

    async def factory(
        host: str, port: int, ssl_context: object, server_hostname: str | None
    ) -> tuple[_FakeReader, _FakeWriter]:
        pytest.fail("must never connect to a NAT64 address")

    transport = PinnedHttpsTransport(
        resolver=resolver, connection_factory=factory  # type: ignore[arg-type]
    )

    with pytest.raises(NonPublicAddressError):
        await transport.handle_async_request(
            httpx.Request("GET", "https://nat64.example.test/jobs/1")
        )


async def test_pinned_transport_accepts_public_ipv6() -> None:
    connected: list[str] = []

    async def resolver(
        host: str,
    ) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        return [ipaddress.ip_address("2606:4700::1111")]

    async def factory(
        host: str, port: int, ssl_context: object, server_hostname: str | None
    ) -> tuple[_FakeReader, _FakeWriter]:
        connected.append(host)
        return (
            _FakeReader(b"HTTP/1.1 204 No Content\r\nContent-Length: 0\r\n\r\n"),
            _FakeWriter(),
        )

    transport = PinnedHttpsTransport(
        resolver=resolver, connection_factory=factory  # type: ignore[arg-type]
    )
    client = httpx.AsyncClient(transport=transport)

    response = await client.get("https://v6.example.test/jobs/1")

    assert connected == ["2606:4700::1111"]
    assert response.status_code == 204
    await client.aclose()


async def test_pinned_transport_decodes_chunked_body() -> None:
    async def factory(
        host: str, port: int, ssl_context: object, server_hostname: str | None
    ) -> tuple[_FakeReader, _FakeWriter]:
        return (
            _FakeReader(
                b"HTTP/1.1 200 OK\r\n"
                b"Transfer-Encoding: chunked\r\n"
                b"\r\n"
                b"5\r\nhello\r\n"
                b"6\r\n world\r\n"
                b"0\r\n\r\n"
            ),
            _FakeWriter(),
        )

    transport = PinnedHttpsTransport(
        resolver=_public_resolver, connection_factory=factory  # type: ignore[arg-type]
    )
    client = httpx.AsyncClient(transport=transport)

    response = await client.get("https://careers.acme.com/jobs/data-engineer")

    assert (await response.aread()) == b"hello world"
    await client.aclose()


async def test_pinned_transport_decodes_large_chunk_across_partial_reads() -> None:
    body = b"x" * 300_000

    async def factory(
        host: str, port: int, ssl_context: object, server_hostname: str | None
    ) -> tuple[_TrickleReader, _FakeWriter]:
        return (
            _TrickleReader(
                b"HTTP/1.1 200 OK\r\n"
                b"Transfer-Encoding: chunked\r\n"
                b"\r\n"
                + f"{len(body):x}\r\n".encode()
                + body
                + b"\r\n0\r\n\r\n"
            ),
            _FakeWriter(),
        )

    transport = PinnedHttpsTransport(
        resolver=_public_resolver, connection_factory=factory  # type: ignore[arg-type]
    )
    client = httpx.AsyncClient(transport=transport)

    response = await client.get("https://careers.acme.com/jobs/data-engineer")

    assert (await response.aread()) == body
    await client.aclose()


async def test_pinned_transport_rejects_oversized_header_block() -> None:
    async def factory(
        host: str, port: int, ssl_context: object, server_hostname: str | None
    ) -> tuple[_FakeReader, _FakeWriter]:
        return (
            _FakeReader(
                b"HTTP/1.1 200 OK\r\n" + b"X-Big: " + b"a" * 100_000 + b"\r\n\r\n"
            ),
            _FakeWriter(),
        )

    transport = PinnedHttpsTransport(
        resolver=_public_resolver, connection_factory=factory  # type: ignore[arg-type]
    )
    client = httpx.AsyncClient(transport=transport)

    with pytest.raises(httpx.ProtocolError):
        await client.get("https://careers.acme.com/jobs/data-engineer")
    await client.aclose()


async def test_career_page_fetches_through_pinned_transport_by_default() -> None:
    connected: list[tuple[str, str | None]] = []
    responses = [
        b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n",
        (
            b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n"
            b"Content-Length: 67\r\n\r\n"
            b"<html><body><p>Data Engineer needed in Jakarta.</p></body></html>"
        ),
    ]

    async def factory(
        host: str, port: int, ssl_context: object, server_hostname: str | None
    ) -> tuple[_FakeReader, _FakeWriter]:
        connected.append((host, server_hostname))
        return _FakeReader(responses.pop(0)), _FakeWriter()

    fetcher = CareerPageFetcher(
        resolver=_public_resolver,
        timeout=5.0,
        connection_factory=factory,  # type: ignore[arg-type]
    )

    text = await fetcher.extract_text("https://careers.acme.com/jobs/data-engineer")

    assert "Data Engineer needed in Jakarta." in text
    assert connected == [
        ("93.184.216.34", "careers.acme.com"),
        ("93.184.216.34", "careers.acme.com"),
    ]
    await fetcher.aclose()


async def test_career_page_rejects_nat64_resolution() -> None:
    async def resolver(
        host: str,
    ) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        return [ipaddress.ip_address("64:ff9b::a00:1")]

    fetcher = CareerPageFetcher(
        client=httpx.AsyncClient(), resolver=resolver  # type: ignore[arg-type]
    )

    with pytest.raises(SourceDataError):
        await fetcher.extract_text("https://nat64.example.test/jobs/1")


async def test_career_page_rejects_redirect_to_http(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://careers.acme.com/robots.txt",
        text="User-agent: *\nAllow: /",
    )
    httpx_mock.add_response(
        url="https://careers.acme.com/jobs/1",
        status_code=302,
        headers={"location": "http://careers.acme.com/jobs/2"},
    )
    fetcher = CareerPageFetcher(
        client=httpx.AsyncClient(),
        resolver=_public_resolver,
    )

    with pytest.raises(SourceConfigError):
        await fetcher.extract_text("https://careers.acme.com/jobs/1")


async def test_career_page_rejects_redirect_to_private_host(
    httpx_mock: HTTPXMock,
) -> None:
    async def resolver(
        host: str,
    ) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        if host == "internal.corp.example":
            return [ipaddress.ip_address("10.0.0.5")]
        return [ipaddress.ip_address("93.184.216.34")]

    httpx_mock.add_response(
        url="https://careers.acme.com/robots.txt",
        text="User-agent: *\nAllow: /",
    )
    httpx_mock.add_response(
        url="https://careers.acme.com/jobs/1",
        status_code=302,
        headers={"location": "https://internal.corp.example/jobs/2"},
    )
    fetcher = CareerPageFetcher(
        client=httpx.AsyncClient(),
        resolver=resolver,  # type: ignore[arg-type]
    )

    with pytest.raises(SourceDataError):
        await fetcher.extract_text("https://careers.acme.com/jobs/1")


async def test_career_page_rejects_redirect_without_location(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(
        url="https://careers.acme.com/robots.txt",
        text="User-agent: *\nAllow: /",
    )
    httpx_mock.add_response(
        url="https://careers.acme.com/jobs/1",
        status_code=302,
        headers={},
    )
    fetcher = CareerPageFetcher(
        client=httpx.AsyncClient(),
        resolver=_public_resolver,
    )

    with pytest.raises(SourceDataError):
        await fetcher.extract_text("https://careers.acme.com/jobs/1")


async def test_career_page_rejects_excessive_redirects(httpx_mock: HTTPXMock) -> None:
    for _ in range(4):
        httpx_mock.add_response(
            url="https://careers.acme.com/robots.txt",
            text="User-agent: *\nAllow: /",
        )
    for i in range(1, 5):
        httpx_mock.add_response(
            url=f"https://careers.acme.com/jobs/{i}",
            status_code=302,
            headers={"location": f"https://careers.acme.com/jobs/{i + 1}"},
        )
    fetcher = CareerPageFetcher(
        client=httpx.AsyncClient(),
        resolver=_public_resolver,
    )

    with pytest.raises(SourceDataError) as excinfo:
        await fetcher.extract_text("https://careers.acme.com/jobs/1")
    assert "redirect" in str(excinfo.value)


async def test_career_page_rejects_oversize_robots_txt(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://careers.acme.com/robots.txt",
        text="User-agent: *\nAllow: /" + "x" * (600 * 1024),
        headers={"content-length": str(600 * 1024)},
    )
    fetcher = CareerPageFetcher(
        client=httpx.AsyncClient(),
        resolver=_public_resolver,
    )

    with pytest.raises(SourceDataError) as excinfo:
        await fetcher.extract_text("https://careers.acme.com/jobs/data-engineer")
    assert "size" in str(excinfo.value)


async def test_no_dns_error_is_classified_as_data_error() -> None:
    async def resolver(
        host: str,
    ) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        return []

    fetcher = CareerPageFetcher(
        client=httpx.AsyncClient(),
        resolver=resolver,  # type: ignore[arg-type]
    )

    with pytest.raises(SourceDataError):
        await fetcher.extract_text("https://nowhere.example.test/jobs/1")


# --- Credential-bearing source URLs ---


async def test_greenhouse_skips_credentials_url(httpx_mock: HTTPXMock) -> None:
    body = {
        "jobs": [
            GREENHOUSE_BODY["jobs"][0],
            {
                "id": 9,
                "title": "Embedded credentials",
                "absolute_url": "https://user:pass@boards.greenhouse.io/acme/jobs/9",
            },
        ]
    }
    httpx_mock.add_response(url=GREENHOUSE_URL, json=body)
    connector = GreenhouseConnector(board_token="acme", client=httpx.AsyncClient())

    jobs = await connector.search(QUERY)

    assert len(jobs) == 1
    assert jobs[0].title == "Data Engineer"
    await connector.aclose()


async def test_lever_skips_credentials_url(httpx_mock: HTTPXMock) -> None:
    body = [
        LEVER_BODY[0],
        {
            "id": "creds123",
            "text": "Embedded credentials",
            "hostedUrl": "https://user:pass@jobs.lever.co/acme/creds123",
            "createdAt": 1783000002000,
        },
    ]
    httpx_mock.add_response(url=LEVER_URL, json=body)
    connector = LeverConnector(site_name="acme", client=httpx.AsyncClient())

    jobs = await connector.search(QUERY)

    assert len(jobs) == 1
    assert jobs[0].title == "Data Engineer"
    await connector.aclose()


# --- API JSON body cap ---


async def test_brave_oversize_json_body_is_data_error(httpx_mock: HTTPXMock) -> None:
    oversized = {
        "web": {
            "results": [
                {
                    "title": "x",
                    "url": "https://a.example/x",
                    "description": "y" * (5 * 1024 * 1024),
                }
            ]
        }
    }
    httpx_mock.add_response(url=BRAVE_URL_ENCODED, json=oversized)
    connector = BraveConnector(api_key="test-key", client=httpx.AsyncClient())

    with pytest.raises(SourceDataError) as excinfo:
        await connector.search(QUERY)
    assert "size" in str(excinfo.value)
    await connector.aclose()
