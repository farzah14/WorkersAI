from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from jobmatch_worker.ai.base import AiResult

PROFILE_JSON = {
    "name": "Rina",
    "current_role": "Data Engineer",
    "seniority": "mid",
    "target_roles": ["Data Engineer"],
    "skills": ["Python", "SQL"],
    "experience_years": 4.0,
    "languages": ["Bahasa Indonesia"],
    "education": ["BSc Computer Science"],
}

REQUIREMENTS_JSON = {
    "requirements": [
        {
            "category": "skill",
            "value": "Python",
            "criticality": "must",
            "evidence": "Python required",
        }
    ]
}

EXPLANATION_JSON = {
    "explanation": "Strong match on Python.",
    "recommendations": ["Keep building Python projects"],
}


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
        *,
        run_row: dict[str, Any] | None,
        profile_row: dict[str, Any] | None,
        job_row: dict[str, Any] | None,
        pending: int = 0,
        failed: int = 0,
        match_run_ids: list[str] | None = None,
    ) -> None:
        self.run_row = run_row
        self.profile_row = profile_row
        self.job_row = job_row
        self.pending = pending
        self.failed = failed
        self.match_run_ids = match_run_ids or []
        self.executed: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, query: str, params: tuple[Any, ...] = ()) -> _Cursor:
        self.executed.append((query, params))
        lowered = query.lower()
        if "from public.job_search_runs" in lowered:
            return _Cursor(self.run_row)
        if "from public.candidate_profiles" in lowered:
            return _Cursor(self.profile_row)
        if "from public.jobs" in lowered:
            return _Cursor(self.job_row)
        if "from public.job_search_run_jobs" in lowered:
            return _RowsCursor(
                [{"search_run_id": run_id} for run_id in self.match_run_ids]
            )
        if "from public.work_items" in lowered:
            if "status in ('queued', 'processing')" in lowered:
                return _Cursor({"pending": self.pending})
            return _Cursor({"failed": self.failed})
        return _Cursor(None)

    async def rollback(self) -> None:
        return None


class _FakeRouter:
    async def generate_structured(
        self, *, system: str, user: str, schema: dict[str, Any]
    ) -> AiResult:
        if "untrusted" in system:
            return AiResult(provider="fake", model="fake", data=REQUIREMENTS_JSON, latency_ms=1)
        return AiResult(provider="fake", model="fake", data=EXPLANATION_JSON, latency_ms=1)


def _settings(**overrides: Any) -> SimpleNamespace:
    values: dict[str, Any] = {
        "max_attempts": 3,
        "ollama_embed_model": "",
        "ollama_api_key": "",
        "ollama_base_url": "https://ollama.com/api",
        "ai_provider_order": "nvidia",
        "ai_timeout_seconds": 1.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_match_job_handler_completes_run_when_all_items_terminal() -> None:
    from jobmatch_worker.handlers.matching import handle_match_job

    connection = _Connection(
        run_row={"user_id": "user-1", "candidate_profile_id": "prof-1", "locations": ["Jakarta"]},
        profile_row={"profile": PROFILE_JSON, "confirmed_at": "2026-08-16T00:00:00Z"},
        job_row={"description": "Python required"},
        pending=0,
        failed=0,
    )

    await handle_match_job(
        connection,
        {"id": "item-1", "payload": {"search_run_id": "run-1", "job_id": "job-1"}},
        _settings(),
        router=_FakeRouter(),
    )

    upserts = [
        params
        for query, params in connection.executed
        if "insert into public.job_matches" in query.lower()
    ]
    assert len(upserts) == 1
    assert upserts[0][1] == "run-1"

    run_updates = [
        params
        for query, params in connection.executed
        if "update public.job_search_runs" in query.lower()
    ]
    assert run_updates == [("completed", 0, "run-1")]

    completed_items = [
        params
        for query, params in connection.executed
        if "update public.work_items" in query.lower() and "completed" in query.lower()
    ]
    assert completed_items == [("item-1",)]


@pytest.mark.asyncio
async def test_match_job_handler_marks_run_partial_when_sibling_failed() -> None:
    from jobmatch_worker.handlers.matching import handle_match_job

    connection = _Connection(
        run_row={"user_id": "user-1", "candidate_profile_id": "prof-1", "locations": []},
        profile_row={"profile": PROFILE_JSON, "confirmed_at": "2026-08-16T00:00:00Z"},
        job_row={"description": "Python required"},
        pending=0,
        failed=1,
    )

    await handle_match_job(
        connection,
        {"id": "item-2", "payload": {"search_run_id": "run-2", "job_id": "job-2"}},
        _settings(),
        router=_FakeRouter(),
    )

    run_updates = [
        params
        for query, params in connection.executed
        if "update public.job_search_runs" in query.lower()
    ]
    assert run_updates == [("partial", 1, "run-2")]


@pytest.mark.asyncio
async def test_match_job_handler_keeps_run_pending_when_siblings_remain() -> None:
    from jobmatch_worker.handlers.matching import handle_match_job

    connection = _Connection(
        run_row={"user_id": "user-1", "candidate_profile_id": "prof-1", "locations": []},
        profile_row={"profile": PROFILE_JSON, "confirmed_at": "2026-08-16T00:00:00Z"},
        job_row={"description": "Python required"},
        pending=3,
        failed=0,
    )

    await handle_match_job(
        connection,
        {"id": "item-3", "payload": {"search_run_id": "run-3", "job_id": "job-3"}},
        _settings(),
        router=_FakeRouter(),
    )

    run_updates = [
        params
        for query, params in connection.executed
        if "update public.job_search_runs" in query.lower()
    ]
    assert run_updates == []


@pytest.mark.asyncio
async def test_match_job_handler_fails_without_confirmed_profile() -> None:
    from jobmatch_worker.handlers.matching import handle_match_job

    connection = _Connection(
        run_row={"user_id": "user-1", "candidate_profile_id": "prof-1", "locations": []},
        profile_row=None,
        job_row={"description": "Python required"},
    )

    await handle_match_job(
        connection,
        {"id": "item-4", "payload": {"search_run_id": "run-4", "job_id": "job-4"}},
        _settings(),
        router=_FakeRouter(),
    )

    failed_items = [
        params
        for query, params in connection.executed
        if "update public.work_items" in query.lower() and "failed" in query.lower()
    ]
    assert failed_items == [("candidate profile not confirmed", "item-4")]
    match_upserts = [
        query for query, _params in connection.executed if "insert into public.job_matches" in query.lower()
    ]
    assert match_upserts == []


@pytest.mark.asyncio
async def test_extract_job_requirements_handler_persists_cache() -> None:
    from jobmatch_worker.handlers.matching import handle_extract_job_requirements

    connection = _Connection(
        run_row=None,
        profile_row=None,
        job_row={"description": "Python required"},
    )

    await handle_extract_job_requirements(
        connection,
        {"id": "item-5", "payload": {"job_id": "job-5", "description_hash": "h5"}},
        _settings(),
        router=_FakeRouter(),
    )

    inserts = [
        params
        for query, params in connection.executed
        if "insert into public.job_requirements" in query.lower()
    ]
    assert len(inserts) == 1
    assert inserts[0][0] == "job-5"
    assert inserts[0][1] == "h5"

    completed_items = [
        params
        for query, params in connection.executed
        if "update public.work_items" in query.lower() and "completed" in query.lower()
    ]
    assert completed_items == [("item-5",)]


@pytest.mark.asyncio
async def test_extract_job_requirements_enqueues_matches_for_related_runs() -> None:
    from psycopg.types.json import Jsonb

    from jobmatch_worker.handlers.matching import handle_extract_job_requirements

    connection = _Connection(
        run_row=None,
        profile_row=None,
        job_row={"description": "Python required"},
        match_run_ids=["run-5", "run-6"],
    )

    await handle_extract_job_requirements(
        connection,
        {"id": "item-6", "payload": {"job_id": "job-6", "description_hash": "h6"}},
        _settings(),
        router=_FakeRouter(),
    )

    match_items = [
        params
        for query, params in connection.executed
        if "insert into public.work_items" in query.lower()
        and params[0] == "match_job"
    ]
    assert len(match_items) == 2
    assert {params[1] for params in match_items} == {
        "match_job:run-5:job-6:h6",
        "match_job:run-6:job-6:h6",
    }
    payloads = [params[2] for params in match_items]
    assert all(isinstance(payload, Jsonb) for payload in payloads)
    assert {payload.obj["search_run_id"] for payload in payloads} == {"run-5", "run-6"}
    assert {payload.obj["job_id"] for payload in payloads} == {"job-6"}
