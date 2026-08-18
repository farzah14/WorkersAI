from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from jobmatch_worker.handlers.discovery import _build_sources
from jobmatch_worker.jobs.connectors.base import SourceUnavailable
from jobmatch_worker.jobs.models import DiscoveredJob, DiscoveryCandidateUrl


class _Cursor:
    def __init__(self, row: dict[str, Any] | None) -> None:
        self._row = row

    async def fetchone(self) -> dict[str, Any] | None:
        return self._row


class _Connection:
    def __init__(self, run_row: dict[str, Any]) -> None:
        self.run_row = run_row
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self._job_number = 0

    async def execute(self, query: str, params: tuple[Any, ...] = ()) -> _Cursor:
        self.executed.append((query, params))
        lowered = query.lower()
        if "from public.job_search_runs" in lowered:
            return _Cursor(self.run_row)
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
            greenhouse_board_token="",
            lever_site_name="",
        )
    )

    assert set(sources) == {"tavily", "greenhouse", "lever"}
    assert sources["tavily"].source_key == "tavily"

    for source in sources.values():
        await source.aclose()  # type: ignore[attr-defined]


def _job(*, source_key: str, url: str, title: str) -> DiscoveredJob:
    return DiscoveredJob(
        source_name=source_key,
        source_key=source_key,
        title=title,
        company="Acme",
        location="Jakarta",
        description=f"Description for {title}",
        original_url=url,
    )


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
    assert any(params[0] == "partial" for params in run_updates)
    final_update = next(params for params in run_updates if params[0] == "partial")
    assert final_update[1:5] == (5, 4, 1, 1)

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
    assert len(provenance) == 5
    assert {params[3] for params in provenance} == {"greenhouse", "tavily"}

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

    async def fetch_page(_url: str) -> str:
        return "Backend Engineer\nBuild reliable services."

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
    assert job_insert[2] == "Unknown"
    assert job_insert[11] == "Backend Engineer\nBuild reliable services."


@pytest.mark.asyncio
async def test_discovery_run_is_failed_when_no_source_yields_jobs() -> None:
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
        "lever": _Connector("lever", []),
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
    assert final_update[1:5] == (0, 0, 0, 1)


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

    async def fetch_page(_url: str) -> str:
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
