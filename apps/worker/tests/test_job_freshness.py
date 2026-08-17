"""Tests for job freshness rechecking and dead-link handling."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from jobmatch_worker.jobs.dedupe import upsert_jobs
from jobmatch_worker.jobs.freshness import (
    FreshnessOutcome,
    RecheckSummary,
    has_expired_marker,
    matchable_job_ids,
    matchable_status,
    recheck_job_url,
    recheck_stale_jobs,
)


class FakeHttpClient:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses
        self.requests: list[tuple[str, str, dict[str, Any]]] = []

    async def request(self, method: str, url: str, **kwargs: Any) -> Any:
        self.requests.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def make_response(status_code: int, text: str = "") -> httpx.Response:
    return httpx.Response(status_code, text=text)


class FakeConnection:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self._rows_index = 0

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    async def execute(
        self, sql: str, params: tuple[Any, ...] | None = None
    ) -> FakeConnection:
        self.executed.append((sql, params or ()))
        self._rows_index = 0
        return self

    async def fetchall(self) -> list[dict[str, Any]]:
        rows = self.rows[self._rows_index :]
        self._rows_index = len(self.rows)
        return rows

    async def fetchone(self) -> dict[str, Any] | None:
        if self._rows_index >= len(self.rows):
            return None
        row = self.rows[self._rows_index]
        self._rows_index += 1
        return row


def job_row(job_id: str, url: str) -> dict[str, Any]:
    return {"id": job_id, "original_url": url}


class TestExpiredMarkers:
    def test_greenhouse_closed_status_is_expired(self) -> None:
        assert has_expired_marker('{"id": 1, "status": "closed"}') is True

    def test_greenhouse_closed_at_is_expired(self) -> None:
        assert has_expired_marker('{"closed_at": "2026-08-01T00:00:00Z"}') is True

    def test_lever_closed_state_is_expired(self) -> None:
        assert has_expired_marker('{"state": "closed"}') is True

    def test_lever_archived_state_is_expired(self) -> None:
        assert has_expired_marker('{"state": "archived"}') is True

    def test_open_ats_payload_is_not_expired(self) -> None:
        assert has_expired_marker('{"status": "open", "state": "published"}') is False

    def test_plain_html_is_not_expired(self) -> None:
        assert has_expired_marker("<html><h1>Data Engineer</h1></html>") is False

    def test_empty_body_is_not_expired(self) -> None:
        assert has_expired_marker("") is False


class TestRecheckJobUrl:
    async def recheck(
        self, responses: list[Any], **kwargs: Any
    ) -> tuple[FreshnessOutcome, FakeHttpClient]:
        client = FakeHttpClient(responses)
        outcome = await recheck_job_url(client, "https://boards.example/jobs/1", **kwargs)  # type: ignore[arg-type]
        return outcome, client

    @pytest.mark.asyncio
    async def test_get_200_page_is_active(self) -> None:
        outcome, _ = await self.recheck([make_response(200, "Engineer wanted")])
        assert outcome.status == "active"
        assert outcome.reason == "page_ok"

    @pytest.mark.asyncio
    async def test_get_404_is_unavailable(self) -> None:
        outcome, _ = await self.recheck([make_response(404)])
        assert outcome.status == "unavailable"
        assert outcome.reason == "not_found"

    @pytest.mark.asyncio
    async def test_get_410_is_unavailable(self) -> None:
        outcome, _ = await self.recheck([make_response(410)])
        assert outcome.status == "unavailable"

    @pytest.mark.asyncio
    async def test_closed_ats_payload_is_expired(self) -> None:
        outcome, _ = await self.recheck(
            [make_response(200, '{"status": "closed"}')]
        )
        assert outcome.status == "expired"
        assert outcome.reason == "ats_marker"

    @pytest.mark.asyncio
    async def test_timeout_is_unknown(self) -> None:
        outcome, _ = await self.recheck(
            [httpx.TimeoutException("timed out")]
        )
        assert outcome.status == "unknown"
        assert outcome.reason == "network_error"

    @pytest.mark.asyncio
    async def test_transport_error_is_unknown(self) -> None:
        outcome, _ = await self.recheck(
            [httpx.ConnectError("connection refused")]
        )
        assert outcome.status == "unknown"

    @pytest.mark.asyncio
    async def test_head_200_is_active_without_body(self) -> None:
        outcome, client = await self.recheck(
            [make_response(200)], prefer_head=True
        )
        assert outcome.status == "active"
        assert outcome.reason == "head_ok"
        assert client.requests[0][0] == "HEAD"

    @pytest.mark.asyncio
    async def test_head_404_is_unavailable(self) -> None:
        outcome, client = await self.recheck(
            [make_response(404)], prefer_head=True
        )
        assert outcome.status == "unavailable"
        assert client.requests[0][0] == "HEAD"

    @pytest.mark.asyncio
    async def test_server_error_is_unknown(self) -> None:
        outcome, _ = await self.recheck([make_response(503)])
        assert outcome.status == "unknown"
        assert outcome.reason == "http_status"

    @pytest.mark.asyncio
    async def test_redirects_are_bounded_and_timeout_is_applied(self) -> None:
        _, client = await self.recheck([make_response(200, "ok")])
        _method, _url, kwargs = client.requests[0]
        assert kwargs["follow_redirects"] is True
        assert kwargs["max_redirects"] == 3
        assert kwargs["timeout"] > 0


class TestRecheckStaleJobs:
    @pytest.mark.asyncio
    async def test_selects_only_stale_active_jobs(self) -> None:
        conn = FakeConnection()
        conn.set_rows([job_row("job-1", "https://x.example/1")])
        client = FakeHttpClient([make_response(404)])

        await recheck_stale_jobs(conn, client=client)  # type: ignore[arg-type]

        select_sql, params = conn.executed[0]
        assert "status = 'active'" in select_sql
        assert "last_checked_at <" in select_sql
        assert params[0] == 7

    @pytest.mark.asyncio
    async def test_updates_unavailable_outcome(self) -> None:
        conn = FakeConnection()
        conn.set_rows([job_row("job-1", "https://x.example/1")])
        client = FakeHttpClient([make_response(404)])

        summary = await recheck_stale_jobs(conn, client=client)  # type: ignore[arg-type]

        assert isinstance(summary, RecheckSummary)
        assert summary.rechecked_count == 1
        assert summary.updated == (("job-1", "active", "unavailable"),)
        update_sql, params = conn.executed[1]
        assert "update public.jobs" in update_sql
        assert params[0] == "unavailable"
        assert params[1] == "job-1"

    @pytest.mark.asyncio
    async def test_updates_expired_outcome(self) -> None:
        conn = FakeConnection()
        conn.set_rows([job_row("job-1", "https://x.example/1")])
        client = FakeHttpClient([make_response(200, '{"status": "closed"}')])

        summary = await recheck_stale_jobs(conn, client=client)  # type: ignore[arg-type]

        assert summary.updated == (("job-1", "active", "expired"),)

    @pytest.mark.asyncio
    async def test_unknown_keeps_last_known_data_and_is_not_deleted(self) -> None:
        conn = FakeConnection()
        conn.set_rows([job_row("job-1", "https://x.example/1")])
        client = FakeHttpClient([httpx.TimeoutException("timed out")])

        summary = await recheck_stale_jobs(conn, client=client)  # type: ignore[arg-type]

        assert summary.rechecked_count == 1
        assert summary.updated == ()
        assert summary.unknown_ids == ("job-1",)
        assert len(conn.executed) == 1
        assert "delete" not in conn.executed[0][0].lower()

    @pytest.mark.asyncio
    async def test_recheck_updates_last_checked_at_only_for_outcomes(self) -> None:
        conn = FakeConnection()
        conn.set_rows(
            [
                job_row("job-1", "https://x.example/1"),
                job_row("job-2", "https://x.example/2"),
            ]
        )
        client = FakeHttpClient(
            [make_response(200, "still open"), httpx.TimeoutException("timed out")]
        )

        summary = await recheck_stale_jobs(conn, client=client)  # type: ignore[arg-type]

        assert summary.rechecked_count == 2
        assert summary.updated == (("job-1", "active", "active"),)
        assert summary.unknown_ids == ("job-2",)
        assert len(conn.executed) == 2


class TestMatchableJobs:
    def test_only_active_is_matchable(self) -> None:
        assert matchable_status("active") is True
        assert matchable_status("expired") is False
        assert matchable_status("unavailable") is False
        assert matchable_status("unknown") is False

    @pytest.mark.asyncio
    async def test_matchable_job_ids_excludes_unavailable(self) -> None:
        conn = FakeConnection()
        conn.set_rows([{"id": "job-1"}, {"id": "job-2"}])

        ids = await matchable_job_ids(conn, run_id="run-1")  # type: ignore[arg-type]

        assert ids == ("job-1", "job-2")
        sql, params = conn.executed[0]
        assert "job_search_run_jobs" in sql
        assert "status = 'active'" in sql
        assert params == ("run-1",)


class TestRediscovery:
    @pytest.mark.asyncio
    async def test_upsert_rediscovery_resets_status_to_active(self) -> None:
        conn = FakeConnection()
        conn.set_rows([{"id": "job-1", "inserted": False}])
        from test_job_dedupe import make_normalized

        jobs = [make_normalized(original_url="https://x.example/1")]

        await upsert_jobs(conn, search_run_id="run-1", jobs=jobs)

        insert_sql, _params = conn.executed[0]
        assert "status = 'active'" in insert_sql