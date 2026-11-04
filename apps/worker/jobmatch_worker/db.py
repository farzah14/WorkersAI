from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from jobmatch_worker.config import Settings


async def create_pool(settings: Settings) -> AsyncConnectionPool:
    pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        open=False,
        min_size=1,
        max_size=4,
        max_idle=60.0,
        max_lifetime=300.0,
        check=AsyncConnectionPool.check_connection,
        kwargs={
            "row_factory": dict_row,
            "keepalives": 1,
            "keepalives_idle": 15,
            "keepalives_interval": 5,
            "keepalives_count": 3,
            "tcp_user_timeout": 30000,
        },
    )
    await pool.open(wait=True)
    return pool