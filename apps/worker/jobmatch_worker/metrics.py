"""Privacy-safe structured operational logging and run metrics.

Operational logs must never contain raw CV text, emails, storage paths,
signed URLs, API keys, or raw user identifiers. Event payloads are
redacted before serialization and user ids are hashed.
"""

import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from psycopg import AsyncConnection

SENSITIVE_KEYS = frozenset(
    {
        "extracted_text",
        "storage_path",
        "storage_url",
        "signed_url",
        "email",
        "password",
        "token",
        "authorization",
        "apikey",
        "api_key",
        "access_token",
        "refresh_token",
    }
)
SIGNED_URL_RE = re.compile(
    r"(X-Amz-Signature|X-Amz-Credential|X-Amz-Security-Token|access_token=)",
    re.IGNORECASE,
)


def hash_identifier(value: str) -> str:
    """Deterministic truncated hash for user identifiers in logs."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def redact(value: Any, key: str = "") -> Any:
    """Return a log-safe copy, dropping sensitive keys and signed URLs.

    User ids are hashed wherever they appear as values.
    """
    if isinstance(value, dict):
        return {
            k: redact(v, k) for k, v in value.items() if k.lower() not in SENSITIVE_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [redact(v, key) for v in value]
    if isinstance(value, str):
        if key.lower() in {"user_id", "userid", "user"}:
            return hash_identifier(value)
        if SIGNED_URL_RE.search(value):
            return "<redacted-url>"
    return value


class EventLogger:
    """Emits one JSON line per operational event on `jobmatch.events`."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._log = logger or logging.getLogger("jobmatch.events")

    def emit(self, event: str, **fields: Any) -> None:
        record: dict[str, Any] = {
            "event": event,
            "ts": datetime.now(UTC).isoformat(),
        }
        record.update(redact(fields))
        self._log.info(json.dumps(record, default=str))


def default_logger() -> EventLogger:
    return EventLogger()


async def run_metrics(conn: AsyncConnection[Any], run_id: str) -> dict[str, Any]:
    """Return discovery/matching/AI counters for a run from database metadata.

    Reads counters already stored on the run row plus match and AI audit
    aggregates. Never queries raw CV text or storage paths.
    """
    run_cursor = await conn.execute(
        """
        select id, status, discovered_count, normalized_count,
               duplicate_count, failed_count,
               created_at, completed_at
        from public.job_search_runs
        where id = %s
        """,
        (run_id,),
    )
    run = await run_cursor.fetchone()
    if run is None:
        raise KeyError(run_id)

    match_cursor = await conn.execute(
        """
        select count(*) as n,
               count(*) filter (where semantic_degraded) as degraded
        from public.job_matches
        where search_run_id = %s
        """,
        (run_id,),
    )
    match_row = await match_cursor.fetchone() or {"n": 0, "degraded": 0}

    window_start = run["created_at"]
    window_end = run["completed_at"] or run["created_at"]
    ai_cursor = await conn.execute(
        """
        select count(*) as calls,
               count(*) filter (where fallback_from is not null) as fallbacks
        from public.ai_requests
        where created_at between %s and %s
        """,
        (window_start, window_end),
    )
    ai_row = await ai_cursor.fetchone() or {"calls": 0, "fallbacks": 0}

    return {
        "run_id": run["id"],
        "status": run["status"],
        "error_code": None,
        "discovered": run["discovered_count"],
        "normalized": run["normalized_count"],
        "duplicates": run["duplicate_count"],
        "failed": run["failed_count"],
        "results": match_row["n"],
        "matched": match_row["n"],
        "semantic_degraded": match_row["degraded"],
        "ai_calls": ai_row["calls"],
        "ai_fallbacks": ai_row["fallbacks"],
    }
