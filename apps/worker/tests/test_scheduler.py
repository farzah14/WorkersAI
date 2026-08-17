from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import pytest

from jobmatch_worker.config import Settings
from jobmatch_worker.scheduler import (
    DailyRunResult,
    daily_key,
    daily_target_day,
    schedule_daily_runs,
)

PROFILE_SELECT_MARKER = "from public.search_profiles"
RUN_INSERT_MARKER = "insert into public.job_search_runs"
WORK_INSERT_MARKER = "insert into public.work_items"


class FakeCursor:
    def __init__(self, rows: list[dict[str, Any]] | None) -> None:
        self._rows = rows or []
        self._index = 0

    async def fetchone(self) -> dict[str, Any] | None:
        if self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        self._index += 1
        return row

    async def fetchall(self) -> list[dict[str, Any]]:
        rows = self._rows
        self._index = len(rows)
        return rows


@dataclass
class FakeConnection:
    profiles: list[dict[str, Any]]
    seen_run_keys: set[str] = field(default_factory=set)
    inserted_runs: list[dict[str, Any]] = field(default_factory=list)
    enqueued: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)
    _next_run: int = 0

    async def execute(
        self, sql: str, params: tuple[Any, ...] | None = None
    ) -> FakeCursor:
        if PROFILE_SELECT_MARKER in sql and sql.lstrip().startswith("select"):
            return FakeCursor(self.profiles)
        if sql.lstrip().startswith(RUN_INSERT_MARKER):
            idempotency_key = params[-1]
            if idempotency_key in self.seen_run_keys:
                return FakeCursor(None)
            self.seen_run_keys.add(idempotency_key)
            self._next_run += 1
            row = {
                "id": f"run-{self._next_run}",
                "user_id": params[0],
                "search_profile_id": params[1],
                "candidate_profile_id": params[2],
                "trigger": "daily",
                "idempotency_key": idempotency_key,
            }
            self.inserted_runs.append(row)
            return FakeCursor([row])
        if sql.lstrip().startswith(WORK_INSERT_MARKER):
            self.enqueued.append((params[0], params[1], params[2]))
            return FakeCursor(None)
        raise AssertionError(f"unexpected sql: {sql}")


def make_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("SUPABASE_URL", "http://localhost:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")
    monkeypatch.setenv("OLLAMA_API_KEY", "ollama-key")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2")
    return Settings(_env_file=None)


def profile(
    user_id: str,
    search_profile_id: str,
    candidate_profile_id: str,
    confirmed: bool = True,
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "search_profile_id": search_profile_id,
        "candidate_profile_id": candidate_profile_id,
        "has_confirmed_active_cv": confirmed,
    }


def test_daily_key_has_deterministic_shape() -> None:
    assert (
        daily_key("u-1", "p-1", date(2026, 8, 17))
        == "daily:u-1:p-1:2026-08-17"
    )


def test_daily_target_day_before_window_is_none() -> None:
    now = datetime(2026, 8, 16, 23, 59, tzinfo=UTC)
    assert daily_target_day(now, hour_jakarta=7) is None


def test_daily_target_day_opens_at_jakarta_hour() -> None:
    now = datetime(2026, 8, 17, 0, 0, tzinfo=UTC)
    assert daily_target_day(now, hour_jakarta=7) == date(2026, 8, 17)


async def test_two_daily_profiles_create_two_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = FakeConnection(
        profiles=[
            profile("u-1", "p-1", "c-1"),
            profile("u-2", "p-2", "c-2"),
        ]
    )
    settings = make_settings(monkeypatch)
    now = datetime(2026, 8, 17, 0, 0, tzinfo=UTC)

    result = await schedule_daily_runs(conn, settings, now_utc=now)  # type: ignore[arg-type]

    assert isinstance(result, DailyRunResult)
    assert result.day == date(2026, 8, 17)
    assert len(result.created) == 2
    assert result.skipped == ()
    assert {r["search_profile_id"] for r in result.created} == {"p-1", "p-2"}
    assert len(conn.inserted_runs) == 2
    assert all(r["trigger"] == "daily" for r in conn.inserted_runs)
    assert all(r["idempotency_key"] for r in conn.inserted_runs)
    assert len(conn.enqueued) == 2
    assert all(kind == "discover_jobs" for kind, _, _ in conn.enqueued)
    assert all(
        dedupe_key == f"discover_jobs:{r['id']}"
        for (_, dedupe_key, _), r in zip(conn.enqueued, conn.inserted_runs, strict=True)
    )


async def test_second_invocation_same_utc_day_creates_no_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = FakeConnection(
        profiles=[
            profile("u-1", "p-1", "c-1"),
            profile("u-2", "p-2", "c-2"),
        ]
    )
    settings = make_settings(monkeypatch)
    now = datetime(2026, 8, 17, 0, 0, tzinfo=UTC)

    first = await schedule_daily_runs(conn, settings, now_utc=now)  # type: ignore[arg-type]
    assert len(first.created) == 2
    enqueued_before = len(conn.enqueued)

    second = await schedule_daily_runs(conn, settings, now_utc=now)  # type: ignore[arg-type]
    assert second.day == date(2026, 8, 17)
    assert second.created == ()
    assert second.skipped == ()
    assert len(conn.inserted_runs) == 2
    assert len(conn.enqueued) == enqueued_before


async def test_profiles_without_confirmed_cv_are_skipped_with_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = FakeConnection(
        profiles=[
            profile("u-1", "p-1", "c-1", confirmed=True),
            profile("u-2", "p-2", "c-2", confirmed=False),
        ]
    )
    settings = make_settings(monkeypatch)
    now = datetime(2026, 8, 17, 0, 0, tzinfo=UTC)

    result = await schedule_daily_runs(conn, settings, now_utc=now)  # type: ignore[arg-type]

    assert len(result.created) == 1
    assert result.created[0]["search_profile_id"] == "p-1"
    assert result.skipped == (
        {"user_id": "u-2", "search_profile_id": "p-2", "reason": "no_confirmed_active_cv"},
    )
    assert len(conn.enqueued) == 1


async def test_window_not_open_creates_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn = FakeConnection(
        profiles=[profile("u-1", "p-1", "c-1")],
    )
    settings = make_settings(monkeypatch)
    now = datetime(2026, 8, 16, 23, 59, tzinfo=UTC)

    result = await schedule_daily_runs(conn, settings, now_utc=now)  # type: ignore[arg-type]

    assert result.day is None
    assert result.created == ()
    assert result.skipped == ()
    assert conn.inserted_runs == []
    assert conn.enqueued == []
