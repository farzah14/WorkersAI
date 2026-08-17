"""Scheduler that creates one idempotent daily discovery run per profile/day.

The scheduler runs as a separate process on the same VPS as the worker.
PostgreSQL is the durable coordination layer: run creation is guarded by the
partial unique index on ``job_search_runs.idempotency_key``, so concurrent or
repeated scheduler invocations for the same UTC day cannot duplicate work.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from jobmatch_worker.config import Settings
from jobmatch_worker.db import create_pool
from jobmatch_worker.queue import enqueue_item

JAKARTA_UTC_OFFSET = timedelta(hours=7)

PROFILE_SELECT_SQL = """
select sp.user_id, sp.id as search_profile_id, sp.candidate_profile_id,
       (cp.id is not null and cv.id is not null) as has_confirmed_active_cv
from public.search_profiles sp
left join public.candidate_profiles cp
  on cp.id = sp.candidate_profile_id
 and cp.user_id = sp.user_id
 and cp.confirmed_at is not null
left join public.cvs cv
  on cv.id = cp.cv_id
 and cv.user_id = cp.user_id
 and cv.is_active
 and cv.extraction_status = 'extracted'
where sp.daily_enabled
  and sp.is_current
"""

RUN_INSERT_SQL = """
insert into public.job_search_runs
  (user_id, search_profile_id, candidate_profile_id, trigger, idempotency_key)
values (%s, %s, %s, 'daily', %s)
on conflict (idempotency_key) do nothing
returning id
"""

@dataclass(frozen=True, slots=True)
class DailyRunResult:
    day: date | None
    created: tuple[dict[str, Any], ...]
    skipped: tuple[dict[str, Any], ...]


def daily_key(user_id: str, search_profile_id: str, day: date) -> str:
    return f"daily:{user_id}:{search_profile_id}:{day.isoformat()}"


def daily_target_day(now_utc: datetime, hour_jakarta: int) -> date | None:
    """Return the Jakarta local day whose run window has opened, or None.

    MVP scheduling uses a single configurable Jakarta hour for every user;
    there are no per-user arbitrary time zones in the MVP.
    """
    if not 0 <= hour_jakarta <= 23:
        raise ValueError("hour_jakarta must be between 0 and 23")
    jakarta_now = now_utc + JAKARTA_UTC_OFFSET
    if jakarta_now.hour < hour_jakarta:
        return None
    return jakarta_now.date()


async def schedule_daily_runs(
    conn: AsyncConnection[Any],
    settings: Settings,
    *,
    now_utc: datetime | None = None,
) -> DailyRunResult:
    """Create missing daily discovery runs for daily-enabled profiles.

    Returns created run rows and profiles skipped with a reason. Runs that
    already exist for the day (same idempotency key) are no-ops.
    """
    now = now_utc or datetime.now(UTC)
    day = daily_target_day(now, settings.daily_discovery_hour_jakarta)
    if day is None:
        return DailyRunResult(day=None, created=(), skipped=())

    cursor = await conn.execute(PROFILE_SELECT_SQL)
    profiles = await cursor.fetchall()

    created: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for row in profiles:
        user_id = row["user_id"]
        search_profile_id = row["search_profile_id"]
        candidate_profile_id = row["candidate_profile_id"]
        if not row["has_confirmed_active_cv"]:
            skipped.append(
                {
                    "user_id": user_id,
                    "search_profile_id": search_profile_id,
                    "reason": "no_confirmed_active_cv",
                }
            )
            continue

        run_cursor = await conn.execute(
            RUN_INSERT_SQL,
            (
                user_id,
                search_profile_id,
                candidate_profile_id,
                daily_key(user_id, search_profile_id, day),
            ),
        )
        run = await run_cursor.fetchone()
        if run is None:
            continue
        await enqueue_item(
            conn,
            kind="discover_jobs",
            dedupe_key=f"discover_jobs:{run['id']}",
            payload={
                "search_run_id": run["id"],
                "search_profile_id": run["search_profile_id"],
                "candidate_profile_id": run["candidate_profile_id"],
                "user_id": run["user_id"],
            },
        )
        created.append(dict(run))

    return DailyRunResult(
        day=day, created=tuple(created), skipped=tuple(skipped)
    )


async def scheduler_loop(settings: Settings) -> None:
    pool: AsyncConnectionPool = await create_pool(settings)
    try:
        while True:
            try:
                async with pool.connection() as conn, conn.cursor(
                    row_factory=dict_row
                ):
                    result = await schedule_daily_runs(conn, settings)
                    print(
                        {
                            "event": "scheduler_run",
                            "day": (
                                result.day.isoformat()
                                if result.day is not None
                                else None
                            ),
                            "created_runs": len(result.created),
                            "skipped_profiles": len(result.skipped),
                        }
                    )
            except Exception:  # noqa: BLE001 - one failed sweep must not kill the scheduler
                print(
                    {
                        "event": "scheduler_error",
                        "error": "scheduler sweep failed",
                    }
                )
                await asyncio.sleep(settings.scheduler_interval_minutes * 60)
                continue
            await asyncio.sleep(settings.scheduler_interval_minutes * 60)
    finally:
        await pool.close()


async def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    await scheduler_loop(settings)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())


__all__ = [
    "DailyRunResult",
    "daily_key",
    "daily_target_day",
    "schedule_daily_runs",
    "scheduler_loop",
]
