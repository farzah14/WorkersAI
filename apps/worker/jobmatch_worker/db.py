from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from jobmatch_worker.config import Settings


async def create_pool(settings: Settings) -> AsyncConnectionPool:
    pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        open=False,
        min_size=1,
        max_size=4,
        kwargs={"row_factory": dict_row},
    )
    await pool.open(wait=True)
    return pool