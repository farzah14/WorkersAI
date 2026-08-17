from typing import Any, Self

from psycopg.rows import dict_row

import jobmatch_worker.main as worker_main
from jobmatch_worker.main import _fetch_work_item_status


class StatusCursor:
    def __init__(self) -> None:
        self.query: str | None = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def execute(self, query: str, params: tuple[str]) -> None:
        self.query = query
        if "error_code" in query or "last_error" in query:
            raise AssertionError("work_items status query used a nonexistent error column")

    async def fetchone(self) -> dict[str, str]:
        return {"status": "completed"}


class StatusConnection:
    def __init__(self) -> None:
        self.cursor_instance = StatusCursor()

    def cursor(self, *, row_factory: Any) -> StatusCursor:
        assert row_factory is dict_row
        return self.cursor_instance


class EventCollector:
    def __init__(self) -> None:
        self.event: str | None = None
        self.fields: dict[str, Any] | None = None

    def emit(self, event: str, **fields: Any) -> None:
        self.event = event
        self.fields = fields


async def test_work_item_status_reads_only_columns_defined_by_work_items_schema() -> None:
    conn = StatusConnection()

    status = await _fetch_work_item_status(conn, "work-item-id")  # type: ignore[arg-type]

    assert status == {"status": "completed"}
    assert conn.cursor_instance.query is not None
    assert "select status from public.work_items" in " ".join(
        conn.cursor_instance.query.split()
    ).lower()


async def test_run_counter_event_forwards_metrics_without_duplicate_run_id(monkeypatch: Any) -> None:
    async def fake_run_metrics(_conn: Any, run_id: str) -> dict[str, Any]:
        return {"run_id": run_id, "status": "completed"}

    monkeypatch.setattr(worker_main, "run_metrics", fake_run_metrics)
    events = EventCollector()

    await worker_main._emit_run_counters(events, object(), "run-1")  # type: ignore[arg-type]

    assert events.event == "run_counters"
    assert events.fields == {"run_id": "run-1", "status": "completed"}
