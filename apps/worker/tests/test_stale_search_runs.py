import pytest

from jobmatch_worker.main import _reap_stale_search_runs


class FakeCursor:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    async def fetchall(self):
        return self.rows

    async def fetchone(self):
        return self.rows[0] if self.rows else None


class FakeConnection:
    def __init__(self, stale_runs: list[dict], match_counts: dict[str, int]):
        self.stale_runs = stale_runs
        self.match_counts = match_counts
        self.executed: list[tuple[str, tuple]] = []

    async def execute(self, query: str, params: tuple = ()):
        self.executed.append((query, params))
        normalized = query.strip().lower()
        if "from public.job_search_runs" in normalized:
            return FakeCursor(self.stale_runs)
        if "from public.job_matches" in normalized:
            run_id = params[0]
            count = self.match_counts.get(run_id, 0)
            return FakeCursor([{"count": count}])
        return FakeCursor([])


@pytest.mark.asyncio
async def test_reap_stale_search_runs_with_zero_matches_marks_failed():
    conn = FakeConnection(
        stale_runs=[{"id": "run-stale-1"}],
        match_counts={"run-stale-1": 0},
    )
    reaped = await _reap_stale_search_runs(conn)
    assert reaped == 1

    updates = [
        params for query, params in conn.executed if "update public.job_search_runs" in query.lower()
    ]
    assert len(updates) == 1
    status, run_id = updates[0]
    assert status == "failed"
    assert run_id == "run-stale-1"


@pytest.mark.asyncio
async def test_reap_stale_search_runs_with_matches_marks_partial():
    conn = FakeConnection(
        stale_runs=[{"id": "run-stale-2"}],
        match_counts={"run-stale-2": 3},
    )
    reaped = await _reap_stale_search_runs(conn)
    assert reaped == 1

    updates = [
        params for query, params in conn.executed if "update public.job_search_runs" in query.lower()
    ]
    assert len(updates) == 1
    status, run_id = updates[0]
    assert status == "partial"
    assert run_id == "run-stale-2"


@pytest.mark.asyncio
async def test_reap_stale_search_runs_empty():
    conn = FakeConnection(
        stale_runs=[],
        match_counts={},
    )
    reaped = await _reap_stale_search_runs(conn)
    assert reaped == 0
    updates = [
        params for query, params in conn.executed if "update public.job_search_runs" in query.lower()
    ]
    assert len(updates) == 0
