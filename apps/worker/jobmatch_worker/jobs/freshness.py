"""Job freshness rechecking and dead-link handling.

Jobs older than the staleness window are rechecked before they are
presented again in a new daily run. Definitive outcomes update the job
status; network failures produce ``unknown`` and always retain the last
known data. Only ``active`` jobs are eligible for new matching work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import httpx

JobStatus = Literal["active", "expired", "unavailable", "unknown"]

_STALE_AFTER_DAYS = 7
_BATCH_SIZE = 50
_MAX_REDIRECTS = 3
_RECHECK_TIMEOUT_SECONDS = 10.0

_ATS_EXPIRED_MARKERS = (
    '"status": "closed"',
    '"closed_at"',
    '"state": "closed"',
    '"state": "archived"',
)

_STALE_SELECT_SQL = """
select id, original_url
from public.jobs
where status = 'active'
  and last_checked_at < now() - make_interval(days => %s)
order by last_checked_at
limit %s
"""

_UPDATE_SQL = """
update public.jobs
set status = %s, last_checked_at = now(), last_seen_at = now()
where id = %s
"""

_MATCHABLE_SQL = """
select j.id
from public.job_search_run_jobs jrj
join public.jobs j on j.id = jrj.job_id
where jrj.search_run_id = %s
  and j.status = 'active'
order by j.first_seen_at
"""


@dataclass(frozen=True, slots=True)
class FreshnessOutcome:
    status: JobStatus
    reason: str


@dataclass(frozen=True, slots=True)
class RecheckSummary:
    rechecked_count: int
    updated: tuple[tuple[str, str, str], ...]
    unknown_ids: tuple[str, ...]


def has_expired_marker(body: str | None) -> bool:
    """Detect expired-job markers in known ATS payloads."""
    if not body:
        return False
    lowered = body.lower()
    return any(marker in lowered for marker in _ATS_EXPIRED_MARKERS)


def matchable_status(status: str) -> bool:
    """Only active jobs may be enqueued for new matching work."""
    return status == "active"


async def recheck_job_url(
    client: Any,
    url: str,
    *,
    prefer_head: bool = False,
    timeout_seconds: float = _RECHECK_TIMEOUT_SECONDS,
) -> FreshnessOutcome:
    """Recheck one canonical job URL with bounded redirects and timeout."""
    method = "HEAD" if prefer_head else "GET"
    try:
        response = await client.request(
            method,
            url,
            follow_redirects=True,
            max_redirects=_MAX_REDIRECTS,
            timeout=timeout_seconds,
        )
    except (httpx.TimeoutException, httpx.TransportError):
        return FreshnessOutcome(status="unknown", reason="network_error")
    if response.status_code in (404, 410):
        return FreshnessOutcome(status="unavailable", reason="not_found")
    if response.status_code != 200:
        return FreshnessOutcome(status="unknown", reason="http_status")
    if method == "HEAD":
        return FreshnessOutcome(status="active", reason="head_ok")
    if has_expired_marker(response.text):
        return FreshnessOutcome(status="expired", reason="ats_marker")
    return FreshnessOutcome(status="active", reason="page_ok")


async def recheck_stale_jobs(
    conn: Any,
    *,
    client: Any,
    stale_after_days: int = _STALE_AFTER_DAYS,
    batch_size: int = _BATCH_SIZE,
    prefer_head: bool = False,
) -> RecheckSummary:
    """Recheck active jobs not verified within the staleness window.

    Unknown outcomes leave the row untouched so the last known data is
    retained; jobs are never deleted by this recheck.
    """
    cursor = await conn.execute(
        _STALE_SELECT_SQL, (stale_after_days, batch_size)
    )
    rows = await cursor.fetchall()

    updated: list[tuple[str, str, str]] = []
    unknown_ids: list[str] = []
    for row in rows:
        outcome = await recheck_job_url(
            client, row["original_url"], prefer_head=prefer_head
        )
        if outcome.status == "unknown":
            unknown_ids.append(row["id"])
            continue
        await conn.execute(_UPDATE_SQL, (outcome.status, row["id"]))
        updated.append((row["id"], "active", outcome.status))

    return RecheckSummary(
        rechecked_count=len(rows),
        updated=tuple(updated),
        unknown_ids=tuple(unknown_ids),
    )


async def matchable_job_ids(conn: Any, *, run_id: str) -> tuple[str, ...]:
    """Return active job ids of a run that may be matched in new runs."""
    cursor = await conn.execute(_MATCHABLE_SQL, (run_id,))
    rows = await cursor.fetchall()
    return tuple(row["id"] for row in rows)


__all__ = [
    "FreshnessOutcome",
    "JobStatus",
    "RecheckSummary",
    "has_expired_marker",
    "matchable_job_ids",
    "matchable_status",
    "recheck_job_url",
    "recheck_stale_jobs",
]