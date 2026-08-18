import asyncio
import ipaddress
import json
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import ValidationError
from pytest_httpx import HTTPXMock

from jobmatch_worker.jobs.connectors.base import (
    SourceConfigError,
    SourceDataError,
    SourceError,
    SourceUnavailable,
)
from jobmatch_worker.jobs.connectors.career_page import CareerPageFetcher
from jobmatch_worker.jobs.connectors.greenhouse import GreenhouseConnector
from jobmatch_worker.jobs.connectors.lever import LeverConnector
from jobmatch_worker.jobs.connectors.pinning_transport import (
    NonPublicAddressError,
    PinnedHttpsTransport,
    is_public_address,
)
from jobmatch_worker.jobs.connectors.tavily import TavilyConnector
from jobmatch_worker.jobs.models import DiscoveredJob, DiscoveryCandidateUrl
from jobmatch_worker.jobs.query import SearchQuery

QUERY = SearchQuery("Data Engineer Jakarta Indonesia")

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/acme/jobs?content=true"

LEVER_URL = "https://api.lever.co/v0/postings/acme?mode=json"

TAVILY_URL = "https://api.tavily.com/search"

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
        "workplaceType": "hybrid",
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

TAVILY_BODY = {
    "results": [
        {
            "title": "Data Engineer at Acme",
            "url": "https://careers.acme.com/jobs/data-engineer",
            "content": "Join our data team in Jakarta.",
        },
        {
            "title": "Demo CTO",
            "url": "https://jobs.leverdemo.com/postings/cto",
            "content": "Synthetic demo posting.",
        },
        {
            "title": "Insecure copy",
            "url": "http://insecure.example.com/job",
            "content": "must be filtered out",
        },
        {"title": "Missing URL", "content": "must be filtered out"},
    ]
}


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


# --- Tavily Search connector ---


async def test_tavily_maps_results_to_candidates(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=TAVILY_URL, method="POST", json=TAVILY_BODY)
    connector = TavilyConnector(api_key="test-key", client=httpx.AsyncClient())

    candidates = await connector.search(QUERY)

    assert len(candidates) == 1
    assert isinstance(candidates[0], DiscoveryCandidateUrl)
    assert candidates[0].url == "https://careers.acme.com/jobs/data-engineer"
    assert candidates[0].title == "Data Engineer at Acme"
    assert candidates[0].snippet == "Join our data team in Jakarta."

    request = httpx_mock.get_requests()[-1]
    assert request.method == "POST"
    assert str(request.url) == TAVILY_URL
    body = json.loads(request.content)
    assert body["query"] == f"{QUERY.terms} jobs"
    assert body["topic"] == "general"
    assert body["search_depth"] == "basic"
    assert body["include_answer"] is False
    assert body["include_raw_content"] is False
    assert body["include_images"] is False
    assert body["api_key"] == "test-key"
    await connector.aclose()


async def test_tavily_filters_excluded_keywords_locally(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=TAVILY_URL,
        method="POST",
        json={
            "results": [
                {
                    "title": "Programmer",
                    "url": "https://careers.acme.com/jobs/programmer",
                    "content": "Build software.",
                },
                {
                    "title": "Data Engineer",
                    "url": "https://careers.acme.com/jobs/data-engineer",
                    "content": "Build data pipelines.",
                },
            ]
        },
    )
    connector = TavilyConnector(api_key="test-key", client=httpx.AsyncClient())

    candidates = await connector.search(
        SearchQuery("Data Engineer", negative_terms=("Programmer",))
    )

    assert len(candidates) == 1
    assert isinstance(candidates[0], DiscoveryCandidateUrl)
    assert candidates[0].title == "Data Engineer"
    await connector.aclose()


async def test_tavily_missing_api_key_is_config_error() -> None:
    connector = TavilyConnector(api_key="", client=httpx.AsyncClient())

    with pytest.raises(SourceConfigError) as excinfo:
        await connector.search(QUERY)

    assert excinfo.value.source_key == "tavily"
    await connector.aclose()


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (401, SourceConfigError),
        (403, SourceConfigError),
        (408, SourceUnavailable),
        (429, SourceUnavailable),
        (500, SourceUnavailable),
    ],
)
async def test_tavily_classifies_http_errors(
    httpx_mock: HTTPXMock,
    status_code: int,
    error_type: type[SourceError],
) -> None:
    httpx_mock.add_response(url=TAVILY_URL, method="POST", status_code=status_code)
    connector = TavilyConnector(
        api_key="test-key", client=httpx.AsyncClient(), retries=0
    )

    with pytest.raises(error_type) as excinfo:
        await connector.search(QUERY)

    assert excinfo.value.source_key == "tavily"
    assert "test-key" not in str(excinfo.value)
    await connector.aclose()


async def test_tavily_non_json_body_is_data_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=TAVILY_URL,
        method="POST",
        text="<html>gateway error</html>",
    )
    connector = TavilyConnector(api_key="test-key", client=httpx.AsyncClient())

    with pytest.raises(SourceDataError) as excinfo:
        await connector.search(QUERY)

    assert excinfo.value.source_key == "tavily"
    assert "test-key" not in str(excinfo.value)
    await connector.aclose()


async def test_tavily_unexpected_shape_is_data_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=TAVILY_URL,
        method="POST",
        json={"results": "oops"},
    )
    connector = TavilyConnector(api_key="test-key", client=httpx.AsyncClient())

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


async def test_greenhouse_rejects_oversized_posting_list(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=GREENHOUSE_URL, json={"jobs": [{} for _ in range(201)]})
    connector = GreenhouseConnector(board_token="acme", client=httpx.AsyncClient())

    with pytest.raises(SourceDataError, match="result limit"):
        await connector.search(QUERY)

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
    assert job.work_mode == "hybrid"
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


async def test_lever_demo_site_is_rejected() -> None:
    connector = LeverConnector(site_name="leverdemo", client=httpx.AsyncClient())

    with pytest.raises(SourceConfigError, match="demo"):
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


async def test_career_page_extracts_job_posting_metadata(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://careers.acme.com/robots.txt",
        text="User-agent: *\nAllow: /",
    )
    page = """
    <html><head>
      <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "JobPosting",
          "title": "Senior Data Engineer",
          "datePosted": "2026-08-18",
          "hiringOrganization": {"@type": "Organization", "name": "Acme Labs"},
          "jobLocation": {
            "@type": "Place",
            "address": {
              "addressLocality": "Jakarta",
              "addressRegion": "DKI Jakarta",
              "addressCountry": "ID"
            }
          },
          "jobLocationType": "TELECOMMUTE"
        }
      </script>
    </head><body><p>Build reliable data pipelines.</p></body></html>
    """
    httpx_mock.add_response(
        url="https://careers.acme.com/jobs/senior-data-engineer",
        html=page,
    )
    fetcher = CareerPageFetcher(client=httpx.AsyncClient(), resolver=_public_resolver)

    content = await fetcher.extract_content(
        "https://careers.acme.com/jobs/senior-data-engineer"
    )

    assert content.text == "Build reliable data pipelines."
    assert content.title == "Senior Data Engineer"
    assert content.company == "Acme Labs"
    assert content.location == "Jakarta, DKI Jakarta, ID"
    assert content.published_at == datetime(2026, 8, 18, tzinfo=UTC)
    assert content.work_mode == "remote"


async def test_career_page_extracts_meta_job_metadata(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://careers.acme.com/robots.txt",
        text="User-agent: *\nAllow: /",
    )
    page = """
    <html><head>
      <title>Online Coding Teacher Jobs at Algonova, Jakarta Pusat | Glints</title>
      <meta name="description" content="Apply for Online Coding Teacher at Algonova. Remote Jobs. Job Location: Jakarta Pusat">
      <meta property="article:published_time" content="2026-08-18T09:30:00Z">
    </head><body><p>Teach coding to students.</p></body></html>
    """
    httpx_mock.add_response(
        url="https://careers.acme.com/jobs/online-coding-teacher",
        html=page,
    )
    fetcher = CareerPageFetcher(client=httpx.AsyncClient(), resolver=_public_resolver)

    content = await fetcher.extract_content(
        "https://careers.acme.com/jobs/online-coding-teacher"
    )

    assert content.title == "Online Coding Teacher"
    assert content.company == "Algonova"
    assert content.location == "Jakarta Pusat"
    assert content.published_at == datetime(2026, 8, 18, 9, 30, tzinfo=UTC)
    assert content.work_mode == "remote"
    assert content.is_closed is False


async def test_career_page_marks_closed_meta_job(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://careers.acme.com/robots.txt",
        text="User-agent: *\nAllow: /",
    )
    httpx_mock.add_response(
        url="https://careers.acme.com/jobs/closed",
        html="""
        <html><head>
          <title>Data Engineer Jobs at Acme Labs (Closed) | Glints</title>
          <meta name="description" content="Apply for Data Engineer at Acme Labs. Remote Jobs.">
        </head><body><p>This job was closed.</p></body></html>
        """,
    )
    fetcher = CareerPageFetcher(client=httpx.AsyncClient(), resolver=_public_resolver)

    content = await fetcher.extract_content("https://careers.acme.com/jobs/closed")

    assert content.company == "Acme Labs"
    assert content.is_closed is True


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


async def test_career_page_enforces_absolute_fetch_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    client = httpx.AsyncClient()
    fetcher = CareerPageFetcher(
        client=client,
        resolver=_public_resolver,
        timeout=0.01,
    )

    async def slow_robots(_url: str) -> bool:
        await asyncio.sleep(0.05)
        return True

    async def unexpected_get(_url: str) -> httpx.Response:
        raise AssertionError("fetch should have timed out before the page request")

    monkeypatch.setattr(fetcher, "_robots_allowed", slow_robots)
    monkeypatch.setattr(fetcher, "_get", unexpected_get)
    try:
        with pytest.raises(SourceUnavailable, match="deadline"):
            await fetcher.extract_text("https://careers.acme.com/jobs/slow")
    finally:
        await client.aclose()


async def test_career_page_default_transport_has_connection_factory() -> None:
    fetcher = CareerPageFetcher(resolver=_public_resolver)
    transport = fetcher._client._transport  # type: ignore[attr-defined]
    assert callable(transport._connection_factory)
    await fetcher.aclose()


# --- Connector isolation ---


async def test_one_connector_500_does_not_prevent_another_from_returning(
    httpx_mock: HTTPXMock,
) -> None:
    httpx_mock.add_response(url=TAVILY_URL, method="POST", status_code=500)
    httpx_mock.add_response(url=TAVILY_URL, method="POST", status_code=500)
    httpx_mock.add_response(url=GREENHOUSE_URL, json=GREENHOUSE_BODY)

    tavily = TavilyConnector(api_key="test-key", client=httpx.AsyncClient())
    greenhouse = GreenhouseConnector(board_token="acme", client=httpx.AsyncClient())

    with pytest.raises(SourceUnavailable):
        await tavily.search(QUERY)

    jobs = await greenhouse.search(QUERY)
    assert len(jobs) == 1
    assert isinstance(jobs[0], DiscoveredJob)
    assert jobs[0].title == "Data Engineer"
    await tavily.aclose()
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
        self.wait_closed_called = False

    def write(self, data: bytes) -> None:
        self.written += data

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        self.wait_closed_called = True


@pytest.mark.parametrize(
    "address",
    [
        ipaddress.ip_address("fec0::1"),
        ipaddress.ip_address("ff02::1"),
        ipaddress.ip_address("224.0.0.1"),
    ],
)
def test_public_address_check_rejects_non_unicast(address: object) -> None:
    assert not is_public_address(address)  # type: ignore[arg-type]


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


async def test_pinned_transport_splits_large_declared_chunks() -> None:
    body = b"x" * 200_000

    async def factory(
        host: str, port: int, ssl_context: object, server_hostname: str | None
    ) -> tuple[_FakeReader, _FakeWriter]:
        return (
            _FakeReader(
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
    response = await transport.handle_async_request(
        httpx.Request("GET", "https://careers.acme.com/jobs/data-engineer")
    )

    chunks = [chunk async for chunk in response.aiter_raw()]
    assert b"".join(chunks) == body
    assert max(map(len, chunks)) <= 64 * 1024


async def test_pinned_transport_closes_writer_when_request_is_cancelled() -> None:
    blocked = asyncio.Event()
    writers: list[_FakeWriter] = []

    class _BlockingReader(_FakeReader):
        async def readuntil(self, _sep: bytes) -> bytes:
            await blocked.wait()
            return b""

    async def factory(
        host: str, port: int, ssl_context: object, server_hostname: str | None
    ) -> tuple[_BlockingReader, _FakeWriter]:
        writer = _FakeWriter()
        writers.append(writer)
        return _BlockingReader(b""), writer

    transport = PinnedHttpsTransport(
        resolver=_public_resolver, connection_factory=factory  # type: ignore[arg-type]
    )
    task = asyncio.create_task(
        transport.handle_async_request(
            httpx.Request("GET", "https://careers.acme.com/jobs/cancel")
        )
    )
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert writers[0].closed
    assert writers[0].wait_closed_called


async def test_pinned_transport_closes_factory_result_when_cancelled() -> None:
    started = asyncio.Event()
    writers: list[_FakeWriter] = []

    async def factory(
        host: str, port: int, ssl_context: object, server_hostname: str | None
    ) -> tuple[_FakeReader, _FakeWriter]:
        writer = _FakeWriter()
        writers.append(writer)
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            return _FakeReader(b""), writer
        raise AssertionError("factory should have been cancelled")

    transport = PinnedHttpsTransport(
        resolver=_public_resolver, connection_factory=factory  # type: ignore[arg-type]
    )
    task = asyncio.create_task(
        transport.handle_async_request(
            httpx.Request("GET", "https://careers.acme.com/jobs/factory-cancel")
        )
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert writers[0].closed
    assert writers[0].wait_closed_called


async def test_pinned_transport_preserves_connection_timeout() -> None:
    started = asyncio.Event()

    async def factory(
        host: str, port: int, ssl_context: object, server_hostname: str | None
    ) -> tuple[_FakeReader, _FakeWriter]:
        started.set()
        await asyncio.Event().wait()
        raise AssertionError("factory should have timed out")

    transport = PinnedHttpsTransport(
        resolver=_public_resolver,
        timeout=0.01,
        connection_factory=factory,  # type: ignore[arg-type]
    )
    task = asyncio.create_task(
        transport.handle_async_request(
            httpx.Request("GET", "https://careers.acme.com/jobs/timeout")
        )
    )
    await started.wait()
    with pytest.raises(httpx.ConnectError):
        await task


async def test_pinned_transport_rejects_non_rfc_chunk_size() -> None:
    async def factory(
        host: str, port: int, ssl_context: object, server_hostname: str | None
    ) -> tuple[_FakeReader, _FakeWriter]:
        return (
            _FakeReader(
                b"HTTP/1.1 200 OK\r\n"
                b"Transfer-Encoding: chunked\r\n"
                b"\r\n"
                b"+1\r\nx\r\n0\r\n\r\n"
            ),
            _FakeWriter(),
        )

    transport = PinnedHttpsTransport(
        resolver=_public_resolver, connection_factory=factory  # type: ignore[arg-type]
    )
    response = await transport.handle_async_request(
        httpx.Request("GET", "https://careers.acme.com/jobs/invalid-chunk")
    )
    with pytest.raises(httpx.ProtocolError, match="chunked encoding"):
        await response.aread()


async def test_pinned_transport_rejects_malformed_chunk_trailer() -> None:
    async def factory(
        host: str, port: int, ssl_context: object, server_hostname: str | None
    ) -> tuple[_FakeReader, _FakeWriter]:
        return (
            _FakeReader(
                b"HTTP/1.1 200 OK\r\n"
                b"Transfer-Encoding: chunked\r\n"
                b"\r\n"
                b"0\r\nnot-a-header\r\n\r\n"
            ),
            _FakeWriter(),
        )

    transport = PinnedHttpsTransport(
        resolver=_public_resolver, connection_factory=factory  # type: ignore[arg-type]
    )
    response = await transport.handle_async_request(
        httpx.Request("GET", "https://careers.acme.com/jobs/invalid-trailer")
    )
    with pytest.raises(httpx.ProtocolError, match="trailer"):
        await response.aread()


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


async def test_tavily_oversize_json_body_is_data_error(httpx_mock: HTTPXMock) -> None:
    oversized = {
        "results": [
            {
                "title": "x",
                "url": "https://a.example/x",
                "content": "y" * (5 * 1024 * 1024),
            }
        ]
    }
    httpx_mock.add_response(url=TAVILY_URL, method="POST", json=oversized)
    connector = TavilyConnector(api_key="test-key", client=httpx.AsyncClient())

    with pytest.raises(SourceDataError) as excinfo:
        await connector.search(QUERY)
    assert "size" in str(excinfo.value)
    await connector.aclose()
