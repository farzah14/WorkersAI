import asyncio
import json
import logging

import pytest

from jobmatch_worker.metrics import (
    EventLogger,
    hash_identifier,
    redact,
    run_metrics,
)


class FakeCursor:
    def __init__(self, row):
        self._row = row

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def fetchone(self):
        return self._row


class FakeConnection:
    def __init__(self, rows):
        self._rows = rows

    async def execute(self, sql, params=()):
        return FakeCursor(self._rows.pop(0))


class SchemaAwareMetricsConnection(FakeConnection):
    async def execute(self, sql, params=()):
        normalized = " ".join(sql.split()).lower()
        if "from public.job_search_runs" in normalized and (
            "error_code" in normalized or "result_count" in normalized
        ):
            raise AssertionError("job_search_runs query used an undefined column")
        return await super().execute(sql, params)


@pytest.fixture
def caplog_events(caplog):
    caplog.set_level(logging.INFO, logger="jobmatch.events")
    return caplog


def last_event(caplog):
    for record in reversed(caplog.records):
        if record.name == "jobmatch.events":
            return json.loads(record.getMessage())
    return None


def test_log_never_contains_raw_cv_text_email_or_storage_paths(caplog_events):
    logger = EventLogger()
    logger.emit(
        "work_item_complete",
        work_item_id="11111111-1111-1111-1111-111111111111",
        run_id="22222222-2222-2222-2222-222222222222",
        user_id="33333333-3333-3333-3333-333333333333",
        status="success",
        counts={"discovered": 5, "duplicate": 2},
        extracted_text="John Doe worked at Acme since 2019 with AWS and Kubernetes.",
        email="john.doe@example.com",
        storage_path="33333333-3333-3333-3333-333333333333/cv.pdf",
        signed_url=(
            "https://supabase.example/storage/v1/object/sign/cvs/path/file.pdf"
            "?token=abc&X-Amz-Signature=deadbeef"
        ),
    )
    payload = json.dumps(last_event(caplog_events))
    assert "John Doe" not in payload
    assert "acme" not in payload.lower() or "aws" not in payload.lower()
    assert "john.doe@example.com" not in payload
    assert "/cv.pdf" not in payload
    assert "X-Amz-Signature" not in payload
    assert "deadbeef" not in payload
    assert "11111111-1111-1111-1111-111111111111" in payload
    assert '"discovered": 5' in payload
    assert '"status": "success"' in payload


def test_user_id_is_hashed_in_operational_logs(caplog_events):
    EventLogger().emit(
        "work_item_claimed",
        work_item_id="11111111-1111-1111-1111-111111111111",
        user_id="33333333-3333-3333-3333-333333333333",
    )
    payload = json.dumps(last_event(caplog_events))
    assert "33333333-3333-3333-3333-333333333333" not in payload
    assert hash_identifier("33333333-3333-3333-3333-333333333333") in payload


def test_hash_identifier_is_deterministic_and_truncated():
    user_id = "33333333-3333-3333-3333-333333333333"
    assert hash_identifier(user_id) == hash_identifier(user_id)
    assert len(hash_identifier(user_id)) == 16
    assert hash_identifier(user_id) != hash_identifier("44444444-4444-4444-4444-444444444444")


def test_redact_drops_sensitive_keys_recursively():
    payload = {
        "work_item_id": "11111111-1111-1111-1111-111111111111",
        "extracted_text": "secret cv body",
        "nested": {"storage_path": "user/cv.pdf", "ok": True},
        "items": [{"email": "a@b.c", "id": 1}],
    }
    safe = redact(payload)
    assert "extracted_text" not in safe
    assert "storage_path" not in safe["nested"]
    assert safe["nested"]["ok"] is True
    assert "email" not in safe["items"][0]
    assert safe["items"][0]["id"] == 1
    assert safe["work_item_id"] == payload["work_item_id"]


def test_emit_covers_queue_counters_connector_ai_and_scheduler_events(caplog_events):
    logger = EventLogger()
    logger.emit("work_item_claimed", work_item_id="11111111-1111-1111-1111-111111111111")
    logger.emit("work_item_failed", work_item_id="11111111-1111-1111-1111-111111111111", error="boom")
    logger.emit("run_counters", run_id="22222222-2222-2222-2222-222222222222", counts={"matched": 3, "failed": 1})
    logger.emit("connector_error", source="remotive", error="timeout", jobs_collected=0)
    logger.emit("ai_attempt", provider="nvidia", operation="match_job", status="success", latency_ms=421, fallback_from=None)
    logger.emit("ai_fallback", provider="ollama", operation="match_job", status="retryable_failure", fallback_from="nvidia")
    logger.emit("match_success", run_id="22222222-2222-2222-2222-222222222222", job_id="55555555-5555-5555-5555-555555555555", overall_score=84)
    logger.emit("export_completed", export_id="66666666-6666-6666-6666-666666666666", format="xlsx", status="completed")
    logger.emit("scheduler_run_created", run_id="22222222-2222-2222-2222-222222222222", daily_key="daily:user:profile:2026-08-17")

    events = [json.loads(r.getMessage()) for r in caplog_events.records if r.name == "jobmatch.events"]
    assert [e["event"] for e in events] == [
        "work_item_claimed",
        "work_item_failed",
        "run_counters",
        "connector_error",
        "ai_attempt",
        "ai_fallback",
        "match_success",
        "export_completed",
        "scheduler_run_created",
    ]
    assert all("ts" in e for e in events)
    assert events[1]["error"] == "boom"


def test_run_metrics_returns_counts_without_cv_text():
    run_row = {
        "id": "22222222-2222-2222-2222-222222222222",
        "status": "completed",
        "error_code": None,
        "discovered_count": 40,
        "normalized_count": 38,
        "duplicate_count": 2,
        "failed_count": 1,
        "created_at": "2026-08-17T00:00:00+00:00",
        "completed_at": "2026-08-17T00:05:00+00:00",
    }
    match_row = {"n": 36, "degraded": 2}
    ai_row = {"calls": 42, "fallbacks": 5}
    conn = FakeConnection([run_row, match_row, ai_row])

    metrics = asyncio.run(run_metrics(conn, run_row["id"]))

    assert metrics["run_id"] == run_row["id"]
    assert metrics["status"] == "completed"
    assert metrics["discovered"] == 40
    assert metrics["normalized"] == 38
    assert metrics["duplicates"] == 2
    assert metrics["failed"] == 1
    assert metrics["results"] == 36
    assert metrics["matched"] == 36
    assert metrics["semantic_degraded"] == 2
    assert metrics["ai_calls"] == 42
    assert metrics["ai_fallbacks"] == 5
    assert "extracted_text" not in metrics
    assert "storage_path" not in metrics


def test_run_metrics_raises_for_unknown_run():
    conn = FakeConnection([None])
    with pytest.raises(KeyError):
        asyncio.run(run_metrics(conn, "22222222-2222-2222-2222-222222222222"))


def test_run_metrics_uses_only_job_search_run_columns():
    run_row = {
        "id": "22222222-2222-2222-2222-222222222222",
        "status": "completed",
        "discovered_count": 0,
        "normalized_count": 0,
        "duplicate_count": 0,
        "failed_count": 0,
        "created_at": "2026-08-17T00:00:00+00:00",
        "completed_at": "2026-08-17T00:05:00+00:00",
    }
    conn = SchemaAwareMetricsConnection(
        [run_row, {"n": 0, "degraded": 0}, {"calls": 0, "fallbacks": 0}]
    )

    metrics = asyncio.run(run_metrics(conn, run_row["id"]))

    assert metrics["error_code"] is None
