from typing import Any

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

CLAIM_SQL = """
with candidate as (
  select id
  from public.work_items
  where status = 'queued' and available_at <= now()
  order by created_at
  for update skip locked
  limit 1
)
update public.work_items w
set status='processing', locked_at=now(), locked_by=%(worker_id)s, attempts=attempts+1
from candidate
where w.id=candidate.id
returning w.*;
"""


def retry_delay_seconds(attempt: int) -> int:
    return min(300, 5 * (2 ** max(0, attempt - 1)))


async def claim_next_item(pool: AsyncConnectionPool, worker_id: str) -> dict[str, Any] | None:
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(CLAIM_SQL, {"worker_id": worker_id})
        row = await cur.fetchone()
        return dict(row) if row else None


async def complete_item(conn: AsyncConnection[Any], item_id: str) -> None:
    await conn.execute(
        """
        update public.work_items
        set status = 'completed', locked_at = null, locked_by = null,
            last_error = null, completed_at = now()
        where id = %s
        """,
        (item_id,),
    )


async def retry_item(conn: AsyncConnection[Any], item_id: str, error: str, attempt: int) -> None:
    await conn.execute(
        """
        update public.work_items
        set status = 'queued', locked_at = null, locked_by = null,
            last_error = %s, available_at = now() + make_interval(secs => %s)
        where id = %s
        """,
        (error, retry_delay_seconds(attempt), item_id),
    )


async def fail_item(conn: AsyncConnection[Any], item_id: str, error: str) -> None:
    await conn.execute(
        """
        update public.work_items
        set status = 'failed', locked_at = null, locked_by = null, last_error = %s
        where id = %s
        """,
        (error, item_id),
    )