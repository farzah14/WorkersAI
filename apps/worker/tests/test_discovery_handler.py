from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from jobmatch_worker.handlers.discovery import _build_sources
from jobmatch_worker.jobs.connectors.base import (
    SourceConfigError,
    SourceDataError,
    SourceUnavailable,
)
from jobmatch_worker.jobs.connectors.career_page import CareerPageContent
from jobmatch_worker.jobs.models import DiscoveredJob, DiscoveryCandidateUrl
from jobmatch_worker.matching.cache_key import requirements_cache_key


class _Cursor:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self._row = row

    async def fetchone(self) -> dict[str, Any] | None:
        return self._row


class _RowsCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    async def fetchall(self) -> list[dict[str, Any]]:
        return self._rows


class _Connection:
    def __init__(
        self,
        run_row: dict[str, Any],
        *,
        cached_job_hashes: dict[str, str] | None = None,
    ) -> None:
        self.run_row = run_row
        self.cached_job_hashes = cached_job_hashes or {}
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self._job_number = 0

    async def execute(self, query: str, params: tuple[Any, ...] = ()) -> _Cursor:
        self.executed.append((query, params))
        lowered = query.lower()
        if "from public.job_search_runs" in lowered:
            return _Cursor(self.run_row)
        if "from public.job_requirements" in lowered:
            job_ids = {str(job_id) for job_id in params[0]} if params else set()
            return _RowsCursor(
                [
                    {"job_id": job_id, "description_hash": description_hash}
                    for job_id, description_hash in self.cached_job_hashes.items()
                    if job_id in job_ids
                ]
            )
        if "insert into public.jobs" in lowered:
            self._job_number += 1
            return _Cursor({"id": f"job-{self._job_number}", "inserted": True})
        return _Cursor(None)

    async def rollback(self) -> None:
        return None


class _Connector:
    def __init__(self, source_key: str, result: list[DiscoveredJob] | Exception) -> None:
        self.source_key = source_key
        self._result = result

    async def search(self, _query: Any) -> list[DiscoveredJob | DiscoveryCandidateUrl]:
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


@pytest.mark.asyncio
async def test_build_sources_uses_tavily_for_web_search() -> None:
    sources = _build_sources(
        SimpleNamespace(
            tavily_api_key="tavily-key",
            greenhouse_board_token="leverdemo",
            lever_site_name="leverdemo",
        )
    )

    assert set(sources) == {"tavily", "greenhouse", "lever"}
    assert sources["greenhouse"].source_key == "greenhouse"
    assert sources["lever"].source_key == "lever"

    for source in sources.values():
        await source.aclose()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_build_sources_targets_recent_trusted_indonesia_jobs() -> None:
    sources = _build_sources(
        SimpleNamespace(
            tavily_api_key="tavily-key",
            greenhouse_board_token="",
            lever_site_name="",
            indonesia_trusted_job_domains="careers.example.id",
        ),
        region="indonesia",
    )

    tavily = sources["tavily"]
    assert tavily._time_range == "month"  # type: ignore[attr-defined]
    assert tavily._country == "indonesia"  # type: ignore[attr-defined]
    assert "glints.com" in tavily._include_domains  # type: ignore[attr-defined]
    assert "careers.example.id" in tavily._include_domains  # type: ignore[attr-defined]

    for source in sources.values():
        await source.aclose()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_tavily_candidate_requires_real_job_metadata() -> None:
    from jobmatch_worker.handlers.discovery import _candidate_to_job

    candidate = DiscoveryCandidateUrl(
        url="https://careers.acme.com/jobs/data-engineer",
        title="Data Engineer",
    )

    async def fetch_page(_url: str) -> CareerPageContent:
        return CareerPageContent(text="Build data pipelines.")

    with pytest.raises(SourceDataError, match="company metadata"):
        await _candidate_to_job(candidate, fetch_page, "tavily")


@pytest.mark.asyncio
async def test_tavily_candidate_uses_job_page_metadata() -> None:
    from datetime import UTC, datetime

    from jobmatch_worker.handlers.discovery import _candidate_to_job

    candidate = DiscoveryCandidateUrl(
        url="https://careers.acme.com/jobs/data-engineer",
        title="Search result title",
    )

    async def fetch_page(_url: str) -> CareerPageContent:
        return CareerPageContent(
            text="Build data pipelines.",
            title="Data Engineer",
            company="Acme Labs",
            location="Jakarta",
            published_at=datetime(2026, 8, 18, tzinfo=UTC),
            work_mode="hybrid",
        )

    job = await _candidate_to_job(candidate, fetch_page, "tavily")

    assert job is not None
    assert job.title == "Data Engineer"
    assert job.company == "Acme Labs"
    assert job.location == "Jakarta"
    assert job.published_at == datetime(2026, 8, 18, tzinfo=UTC)
    assert job.work_mode == "hybrid"


@pytest.mark.asyncio
async def test_tavily_candidate_rejects_closed_job_page() -> None:
    from jobmatch_worker.handlers.discovery import _candidate_to_job

    candidate = DiscoveryCandidateUrl(
        url="https://careers.acme.com/jobs/closed",
        title="Closed job",
    )

    async def fetch_page(_url: str) -> CareerPageContent:
        return CareerPageContent(
            text="This job was closed.",
            title="Closed job",
            company="Acme Labs",
            is_closed=True,
        )

    with pytest.raises(SourceDataError, match="closed"):
        await _candidate_to_job(candidate, fetch_page, "tavily")


@pytest.mark.asyncio
async def test_indonesia_candidate_requires_a_specific_job_page() -> None:
    from jobmatch_worker.handlers.discovery import _candidate_to_job

    candidate = DiscoveryCandidateUrl(
        url="https://glints.com/id/opportunities/jobs",
        title="Data jobs in Indonesia",
    )

    async def fetch_page(_url: str) -> CareerPageContent:
        return CareerPageContent(
            text="Browse current jobs in Indonesia.",
            title="Data jobs in Indonesia",
            company="Glints",
            location="Indonesia",
            is_job_posting=False,
        )

    with pytest.raises(SourceDataError, match="specific job"):
        await _candidate_to_job(
            candidate,
            fetch_page,
            "tavily",
            require_specific=True,
        )


def _job(
    *,
    source_key: str,
    url: str,
    title: str,
    company: str = "Acme",
    location: str | None = "Jakarta",
    country: str | None = None,
    work_mode: str | None = None,
    published_at: datetime | None = None,
) -> DiscoveredJob:
    return DiscoveredJob(
        source_name=source_key,
        source_key=source_key,
        title=title,
        company=company,
        location=location,
        country=country,
        work_mode=work_mode,
        description=f"Description for {title}",
        original_url=url,
        published_at=published_at or datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_indonesia_candidate_rejects_untrusted_domain_without_fetch() -> None:
    from jobmatch_worker.handlers.discovery import handle_discover_jobs

    run_row = {
        "id": "run-untrusted",
        "status": "queued",
        "region": "indonesia",
        "target_roles": ["Data Engineer"],
        "locations": ["Jakarta"],
        "work_modes": [],
        "excluded_keywords": [],
    }
    candidate = DiscoveryCandidateUrl(
        url="https://unknown.example/jobs/data-engineer",
        title="Data Engineer Jakarta",
    )
    fetch_count = 0

    async def fetch_page(_url: str) -> CareerPageContent:
        nonlocal fetch_count
        fetch_count += 1
        return CareerPageContent(
            text="Location: Jakarta, Indonesia",
            title="Data Engineer",
            company="Acme",
            location="Jakarta",
        )

    connection = _Connection(run_row)
    await handle_discover_jobs(
        connection,
        {"id": "item-untrusted", "payload": {"search_run_id": "run-untrusted"}},
        SimpleNamespace(
            max_attempts=3,
            requirement_extraction_enabled=False,
            indonesia_trusted_job_domains="",
        ),
        connectors={"tavily": _Connector("tavily", [candidate])},
        fetch_page=fetch_page,
    )

    assert fetch_count == 0
    assert not any("insert into public.jobs" in query.lower() for query, _ in connection.executed)


@pytest.mark.asyncio
async def test_indonesia_candidate_rejects_non_job_content_without_fetch() -> None:
    from jobmatch_worker.handlers.discovery import handle_discover_jobs

    run_row = {
        "id": "run-content-page",
        "status": "queued",
        "region": "indonesia",
        "target_roles": ["Information Technology Specialist"],
        "locations": ["Jakarta"],
        "work_modes": [],
        "excluded_keywords": [],
    }
    candidate = DiscoveryCandidateUrl(
        url="https://id.jobstreet.com/career-advice/role/information-technology-specialist/salary",
        title="Information Technology Specialist Salary in ID",
    )
    fetch_count = 0

    async def fetch_page(_url: str) -> CareerPageContent:
        nonlocal fetch_count
        fetch_count += 1
        raise AssertionError("non-job content must be rejected before fetching")

    connection = _Connection(run_row)
    await handle_discover_jobs(
        connection,
        {"id": "item-content-page", "payload": {"search_run_id": "run-content-page"}},
        SimpleNamespace(
            max_attempts=3,
            requirement_extraction_enabled=False,
            indonesia_trusted_job_domains="",
        ),
        connectors={"tavily": _Connector("tavily", [candidate])},
        fetch_page=fetch_page,
    )

    assert fetch_count == 0
    assert not any("insert into public.jobs" in query.lower() for query, _ in connection.executed)


@pytest.mark.asyncio
async def test_indonesia_filters_foreign_jobs_and_ranks_before_five_job_limit() -> None:
    from jobmatch_worker.handlers.discovery import handle_discover_jobs

    run_row = {
        "id": "run-ranked",
        "status": "queued",
        "region": "indonesia",
        "target_roles": ["Data Engineer"],
        "locations": ["Jakarta"],
        "work_modes": ["hybrid"],
        "excluded_keywords": [],
    }
    jobs = [
        _job(source_key="greenhouse", url="https://jobs.example/marketing", title="Marketing Manager", company="Marketing Co"),
        _job(source_key="greenhouse", url="https://jobs.example/foreign", title="Data Engineer", company="Foreign Co", location="Singapore", country="Singapore"),
        _job(source_key="greenhouse", url="https://jobs.example/surabaya", title="Data Engineer", company="Surabaya Co", location="Surabaya"),
        _job(source_key="greenhouse", url="https://jobs.example/jakarta-1", title="Data Engineer I", company="Jakarta One", work_mode="hybrid"),
        _job(source_key="greenhouse", url="https://jobs.example/jakarta-2", title="Data Engineer II", company="Jakarta Two", work_mode="hybrid"),
        _job(source_key="greenhouse", url="https://jobs.example/jakarta-3", title="Analytics Engineer", company="Analytics Co", work_mode="hybrid"),
        _job(source_key="greenhouse", url="https://jobs.example/jakarta-4", title="Platform Engineer", company="Platform Co", work_mode="hybrid"),
    ]
    connection = _Connection(run_row)

    await handle_discover_jobs(
        connection,
        {"id": "item-ranked", "payload": {"search_run_id": "run-ranked"}},
        SimpleNamespace(max_attempts=3, requirement_extraction_enabled=False),
        connectors={"greenhouse": _Connector("greenhouse", jobs)},
    )

    inserted_titles = [
        params[1]
        for query, params in connection.executed
        if "insert into public.jobs" in query.lower()
    ]
    assert inserted_titles == [
        "Data Engineer I",
        "Data Engineer II",
        "Analytics Engineer",
        "Platform Engineer",
        "Data Engineer",
    ]
    assert "Marketing Manager" not in inserted_titles


@pytest.mark.asyncio
async def test_global_discovery_keeps_foreign_job_behavior() -> None:
    from jobmatch_worker.handlers.discovery import handle_discover_jobs

    run_row = {
        "id": "run-global-foreign",
        "status": "queued",
        "region": "global",
        "target_roles": ["Data Engineer"],
        "locations": [],
        "work_modes": [],
        "excluded_keywords": [],
    }
    connection = _Connection(run_row)
    await handle_discover_jobs(
        connection,
        {"id": "item-global-foreign", "payload": {"search_run_id": "run-global-foreign"}},
        SimpleNamespace(max_attempts=3, requirement_extraction_enabled=False),
        connectors={
            "greenhouse": _Connector(
                "greenhouse",
                [_job(source_key="greenhouse", url="https://jobs.example/sg", title="Data Engineer", location="Singapore", country="Singapore")],
            )
        },
    )

    assert any("insert into public.jobs" in query.lower() for query, _ in connection.executed)


@pytest.mark.asyncio
@pytest.mark.parametrize("region", ["indonesia", "global"])
async def test_discovery_enforces_thirty_day_publication_window(region: str) -> None:
    from jobmatch_worker.handlers.discovery import handle_discover_jobs

    now = datetime.now(UTC)
    run_row = {
        "id": f"run-thirty-day-{region}",
        "status": "queued",
        "region": region,
        "target_roles": ["Data Engineer"],
        "locations": ["Jakarta"] if region == "indonesia" else [],
        "work_modes": [],
        "excluded_keywords": [],
    }
    jobs = [
        _job(
            source_key="greenhouse",
            url="https://boards.greenhouse.io/acme/jobs/recent",
            title="Recent Job",
            published_at=now - timedelta(days=1),
        ),
        _job(
            source_key="greenhouse",
            url="https://boards.greenhouse.io/acme/jobs/boundary",
            title="Exactly Thirty Days",
            published_at=now - timedelta(days=30),
        ),
        _job(
            source_key="greenhouse",
            url="https://boards.greenhouse.io/acme/jobs/old",
            title="Old Job",
            published_at=now - timedelta(days=31),
        ),
        _job(
            source_key="greenhouse",
            url="https://boards.greenhouse.io/acme/jobs/future",
            title="Future Job",
            published_at=now + timedelta(days=1),
        ),
        DiscoveredJob(
            source_name="greenhouse",
            source_key="greenhouse",
            title="Undated Job",
            company="Acme",
            location="Jakarta",
            description="Description for Undated Job",
            original_url="https://boards.greenhouse.io/acme/jobs/undated",
            published_at=None,
        ),
    ]
    connection = _Connection(run_row)

    await handle_discover_jobs(
        connection,
        {
            "id": f"item-thirty-day-{region}",
            "payload": {"search_run_id": f"run-thirty-day-{region}"},
        },
        SimpleNamespace(max_attempts=3, requirement_extraction_enabled=False),
        connectors={"greenhouse": _Connector("greenhouse", jobs)},
    )

    inserted_titles = [
        params[1]
        for query, params in connection.executed
        if "insert into public.jobs" in query.lower()
    ]
    assert inserted_titles == ["Recent Job", "Exactly Thirty Days"]


@pytest.mark.asyncio
async def test_indonesia_zero_valid_jobs_completes_when_sources_succeed() -> None:
    from jobmatch_worker.handlers.discovery import handle_discover_jobs

    run_row = {
        "id": "run-zero-valid",
        "status": "queued",
        "region": "indonesia",
        "target_roles": ["Data Engineer"],
        "locations": [],
        "work_modes": [],
        "excluded_keywords": [],
    }
    connection = _Connection(run_row)
    await handle_discover_jobs(
        connection,
        {"id": "item-zero-valid", "payload": {"search_run_id": "run-zero-valid"}},
        SimpleNamespace(max_attempts=3, requirement_extraction_enabled=False),
        connectors={"greenhouse": _Connector("greenhouse", [])},
    )

    statuses = [
        params[0]
        for query, params in connection.executed
        if "update public.job_search_runs" in query.lower() and params
    ]
    assert statuses[-1] == "completed"


@pytest.mark.asyncio
async def test_zero_valid_jobs_is_partial_when_one_source_succeeds() -> None:
    from jobmatch_worker.handlers.discovery import handle_discover_jobs

    run_row = {
        "id": "run-zero-partial",
        "status": "queued",
        "region": "indonesia",
        "target_roles": ["Data Engineer"],
        "locations": [],
        "work_modes": [],
        "excluded_keywords": [],
    }
    connection = _Connection(run_row)

    await handle_discover_jobs(
        connection,
        {"id": "item-zero-partial", "payload": {"search_run_id": "run-zero-partial"}},
        SimpleNamespace(max_attempts=3, requirement_extraction_enabled=False),
        connectors={
            "tavily": _Connector("tavily", []),
            "greenhouse": _Connector(
                "greenhouse", SourceConfigError("greenhouse", "not configured")
            ),
        },
    )

    statuses = [
        params[0]
        for query, params in connection.executed
        if "update public.job_search_runs" in query.lower() and params
    ]
    assert statuses[-1] == "partial"


@pytest.mark.asyncio
async def test_indonesia_verifies_at_most_twenty_trusted_web_candidates() -> None:
    from jobmatch_worker.handlers.discovery import handle_discover_jobs

    run_row = {
        "id": "run-candidate-cap",
        "status": "queued",
        "region": "indonesia",
        "target_roles": ["Data Engineer"],
        "locations": ["Jakarta"],
        "work_modes": [],
        "excluded_keywords": [],
    }
    candidates = [
        DiscoveryCandidateUrl(
            url=f"https://glints.com/id/opportunities/jobs/data-engineer/{index}",
            title=f"Data Engineer {index}",
        )
        for index in range(25)
    ]
    fetched: list[str] = []

    async def fetch_page(url: str) -> CareerPageContent:
        fetched.append(url)
        return CareerPageContent(
            text="Location: Jakarta, Indonesia",
            title="Data Engineer",
            company="Acme",
            location="Jakarta",
        )

    connection = _Connection(run_row)
    await handle_discover_jobs(
        connection,
        {"id": "item-candidate-cap", "payload": {"search_run_id": "run-candidate-cap"}},
        SimpleNamespace(max_attempts=3, requirement_extraction_enabled=False),
        connectors={"tavily": _Connector("tavily", candidates)},
        fetch_page=fetch_page,
    )

    assert len(fetched) == 20


@pytest.mark.asyncio
async def test_indonesia_deadline_preserves_jobs_verified_before_timeout() -> None:
    from jobmatch_worker.handlers.discovery import _run_source
    from jobmatch_worker.jobs.query import SearchQuery

    candidates = [
        DiscoveryCandidateUrl(
            url="https://glints.com/id/jobs/fast",
            title="Data Engineer Jakarta",
        ),
        DiscoveryCandidateUrl(
            url="https://glints.com/id/jobs/slow",
            title="Data Engineer Jakarta",
        ),
    ]

    async def fetch_page(url: str) -> CareerPageContent:
        if url.endswith("/slow"):
            await asyncio.sleep(0.2)
        return CareerPageContent(
            text="Location: Jakarta, Indonesia",
            title="Data Engineer",
            company="Acme",
            location="Jakarta",
            is_job_posting=True,
        )

    outcome = await _run_source(
        "tavily",
        _Connector("tavily", candidates),
        [SearchQuery("Data Engineer Jakarta Indonesia")],
        fetch_page,
        asyncio.Semaphore(1),
        candidate_limit=20,
        require_specific=True,
        trusted_domains=frozenset(),
        roles=("Data Engineer",),
        locations=("Jakarta",),
        deadline_seconds=0.05,
    )

    assert [job.title for job in outcome.jobs] == ["Data Engineer"]
    assert outcome.status == "failed"
    assert outcome.retryable is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("requirement_extraction_enabled", "expected_requirement_items"),
    [(False, 0), (True, 4)],
)
async def test_discovery_run_keeps_successful_sources_when_one_fails(
    requirement_extraction_enabled: bool,
    expected_requirement_items: int,
) -> None:
    from jobmatch_worker.handlers.discovery import handle_discover_jobs

    run_row = {
        "id": "run-1",
        "status": "queued",
        "region": "indonesia",
        "target_roles": ["Data Engineer"],
        "locations": [],
        "work_modes": [],
        "excluded_keywords": [],
    }
    duplicate_url = "https://jobs.example.com/data-engineer?utm_source=tracker"
    connectors = {
        "greenhouse": _Connector(
            "greenhouse",
            [
                _job(
                    source_key="greenhouse",
                    url="https://jobs.example.com/data-engineer",
                    title="Data Engineer",
                ),
                _job(
                    source_key="greenhouse",
                    url="https://jobs.example.com/platform-engineer",
                    title="Platform Engineer",
                ),
                _job(
                    source_key="greenhouse",
                    url="https://jobs.example.com/analytics-engineer",
                    title="Analytics Engineer",
                ),
            ],
        ),
        "lever": _Connector("lever", SourceUnavailable("lever", "timeout")),
        "tavily": _Connector(
            "tavily",
            [
                _job(source_key="tavily", url=duplicate_url, title="Data Engineer"),
                _job(
                    source_key="tavily",
                    url="https://jobs.example.com/ml-engineer",
                    title="ML Engineer",
                ),
            ],
        ),
    }
    connection = _Connection(run_row)

    await handle_discover_jobs(
        connection,
        {"id": "item-1", "payload": {"search_run_id": "run-1"}},
        SimpleNamespace(
            max_attempts=3,
            requirement_extraction_enabled=requirement_extraction_enabled,
        ),
        connectors=connectors,
    )

    run_updates = [
        params
        for query, params in connection.executed
        if "update public.job_search_runs" in query.lower()
    ]
    expected_status = "processing" if requirement_extraction_enabled else "partial"
    assert any(params[0] == expected_status for params in run_updates)
    final_update = next(params for params in run_updates if params[0] == expected_status)
    assert final_update[1:5] == (7, 4, 1, 1)

    job_inserts = [
        (query, params)
        for query, params in connection.executed
        if "insert into public.jobs" in query.lower()
    ]
    assert len(job_inserts) == 4

    provenance = [
        params
        for query, params in connection.executed
        if "insert into public.job_provenance" in query.lower()
    ]
    source_keys = [params[3] for params in provenance]
    assert len(provenance) == 5
    assert source_keys.count("greenhouse") == 3
    assert source_keys.count("tavily") == 2
    assert {params[0] for params in provenance if params[3] in {"greenhouse", "tavily"}}
    duplicate_job_ids = {
        params[0]
        for params in provenance
        if params[5] == "https://jobs.example.com/data-engineer"
    }
    assert len(duplicate_job_ids) == 1
    duplicate_sources = {
        params[3]
        for params in provenance
        if params[5] == "https://jobs.example.com/data-engineer"
    }
    assert duplicate_sources == {"greenhouse", "tavily"}

    requirement_items = [
        params
        for query, params in connection.executed
        if "insert into public.work_items" in query.lower()
        and params[0] == "extract_job_requirements"
    ]
    assert len(requirement_items) == expected_requirement_items

    failed_source_updates = [
        params
        for query, params in connection.executed
        if "update public.job_sources" in query.lower() and "unavailable" in params
    ]
    assert len(failed_source_updates) == 1

    completed_items = [
        params
        for query, params in connection.executed
        if "update public.work_items" in query.lower()
        and "completed" in query.lower()
    ]
    assert completed_items == [("item-1",)]


@pytest.mark.asyncio
async def test_discovery_run_persists_at_most_five_distinct_jobs() -> None:
    from jobmatch_worker.handlers.discovery import handle_discover_jobs

    run_row = {
        "id": "run-limited",
        "status": "queued",
        "region": "global",
        "target_roles": ["Engineer"],
        "locations": [],
        "work_modes": [],
        "excluded_keywords": [],
    }
    jobs = [
        _job(
            source_key="greenhouse",
            url=f"https://jobs.example.com/engineer-{number}",
            title=f"Engineer {number}",
        )
        for number in range(1, 8)
    ]
    connection = _Connection(run_row)

    await handle_discover_jobs(
        connection,
        {"id": "item-limited", "payload": {"search_run_id": "run-limited"}},
        SimpleNamespace(requirement_extraction_enabled=True, max_attempts=3),
        connectors={"greenhouse": _Connector("greenhouse", jobs)},
    )

    job_inserts = [
        params
        for query, params in connection.executed
        if "insert into public.jobs" in query.lower()
    ]
    provenance = [
        params
        for query, params in connection.executed
        if "insert into public.job_provenance" in query.lower()
    ]
    requirement_items = [
        params
        for query, params in connection.executed
        if "insert into public.work_items" in query.lower()
        and params[0] == "extract_job_requirements"
    ]
    run_updates = [
        params
        for query, params in connection.executed
        if "update public.job_search_runs" in query.lower()
    ]
    final_update = next(params for params in run_updates if params[0] == "processing")

    assert [params[1] for params in job_inserts] == [
        f"Engineer {number}" for number in range(1, 6)
    ]
    assert len(provenance) == 5
    assert len(requirement_items) == 5
    assert final_update[1:5] == (7, 5, 0, 0)


@pytest.mark.asyncio
async def test_discovery_enqueues_match_for_cached_requirements() -> None:
    from jobmatch_worker.handlers.discovery import handle_discover_jobs

    run_row = {
        "id": "run-cached",
        "status": "queued",
        "region": "indonesia",
        "target_roles": ["Data Engineer"],
        "locations": [],
        "work_modes": [],
        "excluded_keywords": [],
    }
    connection = _Connection(
        run_row,
        cached_job_hashes={
            "job-1": requirements_cache_key("Description for Data Engineer")
        },
    )

    await handle_discover_jobs(
        connection,
        {"id": "item-cached", "payload": {"search_run_id": "run-cached"}},
        SimpleNamespace(requirement_extraction_enabled=True, max_attempts=3),
        connectors={
            "greenhouse": _Connector(
                "greenhouse",
                [
                    _job(
                        source_key="greenhouse",
                        url="https://jobs.example.com/cached",
                        title="Data Engineer",
                    )
                ],
            )
        },
    )

    match_items = [
        params
        for query, params in connection.executed
        if "insert into public.work_items" in query.lower() and params[0] == "match_job"
    ]
    assert len(match_items) == 1
    assert match_items[0][2].obj["search_run_id"] == "run-cached"
    assert match_items[0][2].obj["job_id"] == "job-1"


@pytest.mark.asyncio
async def test_search_candidates_become_jobs_with_search_provenance() -> None:
    from jobmatch_worker.handlers.discovery import handle_discover_jobs

    run_row = {
        "id": "run-2",
        "status": "queued",
        "region": "global",
        "target_roles": ["Backend Engineer"],
        "locations": [],
        "work_modes": [],
        "excluded_keywords": [],
    }
    candidate = DiscoveryCandidateUrl(
        url="https://careers.example.com/jobs/backend",
        title="Backend Engineer",
    )
    connection = _Connection(run_row)

    async def fetch_page(_url: str) -> CareerPageContent:
        return CareerPageContent(
            text="Backend Engineer\nBuild reliable services.",
            title="Backend Engineer",
            company="Acme Labs",
            location="Jakarta",
            published_at=datetime.now(UTC),
            is_job_posting=True,
        )

    await handle_discover_jobs(
        connection,
        {"id": "item-2", "payload": {"search_run_id": "run-2"}},
        None,
        connectors={"tavily": _Connector("tavily", [candidate])},
        fetch_page=fetch_page,
    )

    provenance = [
        params
        for query, params in connection.executed
        if "insert into public.job_provenance" in query.lower()
    ]
    assert len(provenance) == 1
    assert provenance[0][2:4] == ("search", "tavily")

    job_insert = next(
        params
        for query, params in connection.executed
        if "insert into public.jobs" in query.lower()
    )
    assert job_insert[1] == "Backend Engineer"
    assert job_insert[2] == "Acme Labs"
    assert job_insert[11] == "Backend Engineer\nBuild reliable services."


@pytest.mark.asyncio
async def test_discovery_run_is_failed_when_every_source_fails() -> None:
    from jobmatch_worker.handlers.discovery import handle_discover_jobs

    run_row = {
        "id": "run-3",
        "status": "queued",
        "region": "indonesia",
        "target_roles": ["Data Engineer"],
        "locations": [],
        "work_modes": [],
        "excluded_keywords": [],
    }
    connection = _Connection(run_row)
    connectors = {
        "greenhouse": _Connector(
            "greenhouse", SourceUnavailable("greenhouse", "timeout")
        ),
        "lever": _Connector("lever", SourceConfigError("lever", "not configured")),
    }

    await handle_discover_jobs(
        connection,
        {"id": "item-3", "attempts": 3, "payload": {"search_run_id": "run-3"}},
        None,
        connectors=connectors,
    )

    run_updates = [
        params
        for query, params in connection.executed
        if "update public.job_search_runs" in query.lower()
    ]
    final_update = next(params for params in run_updates if params[0] == "failed")
    assert final_update[1:5] == (0, 0, 0, 2)


@pytest.mark.asyncio
async def test_transient_source_failure_retries_the_work_item() -> None:
    from jobmatch_worker.handlers.discovery import handle_discover_jobs

    run_row = {
        "id": "run-4",
        "status": "queued",
        "region": "global",
        "target_roles": ["Data Engineer"],
        "locations": [],
        "work_modes": [],
        "excluded_keywords": [],
    }
    connection = _Connection(run_row)

    await handle_discover_jobs(
        connection,
        {"id": "item-4", "attempts": 1, "payload": {"search_run_id": "run-4"}},
        SimpleNamespace(max_attempts=3),
        connectors={
            "lever": _Connector("lever", SourceUnavailable("lever", "timeout"))
        },
    )

    retry_updates = [
        params
        for query, params in connection.executed
        if "set status = 'queued'" in query.lower()
    ]
    assert retry_updates
    assert retry_updates[-1][-1] == "item-4"


@pytest.mark.asyncio
async def test_candidate_fetch_failure_is_recorded_as_source_failure() -> None:
    from jobmatch_worker.handlers.discovery import handle_discover_jobs

    run_row = {
        "id": "run-5",
        "status": "queued",
        "region": "global",
        "target_roles": ["Backend Engineer"],
        "locations": [],
        "work_modes": [],
        "excluded_keywords": [],
    }
    candidate = DiscoveryCandidateUrl(url="https://careers.example.com/jobs/backend")
    connection = _Connection(run_row)

    async def fetch_page(_url: str) -> CareerPageContent:
        raise SourceUnavailable("career_page", "timeout")

    await handle_discover_jobs(
        connection,
        {"id": "item-5", "payload": {"search_run_id": "run-5"}},
        None,
        connectors={"tavily": _Connector("tavily", [candidate])},
        fetch_page=fetch_page,
    )

    source_updates = [
        params
        for query, params in connection.executed
        if "update public.job_sources" in query.lower()
    ]
    assert any(params[0] == "failed" and params[2] == "candidate_fetch" for params in source_updates)


@pytest.mark.asyncio
async def test_unexpected_source_failure_does_not_discard_other_sources() -> None:
    from jobmatch_worker.handlers.discovery import handle_discover_jobs

    run_row = {
        "id": "run-6",
        "status": "queued",
        "region": "global",
        "target_roles": ["Data Engineer"],
        "locations": [],
        "work_modes": [],
        "excluded_keywords": [],
    }
    connection = _Connection(run_row)

    await handle_discover_jobs(
        connection,
        {"id": "item-6", "payload": {"search_run_id": "run-6"}},
        None,
        connectors={
            "greenhouse": _Connector(
                "greenhouse",
                [_job(source_key="greenhouse", url="https://x.example/1", title="Data Engineer")],
            ),
            "lever": _Connector("lever", RuntimeError("connector bug")),
        },
    )

    job_inserts = [
        query for query, _params in connection.executed if "insert into public.jobs" in query.lower()
    ]
    assert len(job_inserts) == 1
    source_updates = [
        params
        for query, params in connection.executed
        if "update public.job_sources" in query.lower()
    ]
    assert any(params[0] == "failed" and params[2] == "source_error" for params in source_updates)
    run_updates = [
        params
        for query, params in connection.executed
        if "update public.job_search_runs" in query.lower()
    ]
    assert any(params[0] == "partial" for params in run_updates)
