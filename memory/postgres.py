from .checkpointer import CheckpointerFabric
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.postgres.base import MIGRATIONS as BASE_MIGRATIONS
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool


_MIGRATIONS = [
    m.replace("CREATE INDEX CONCURRENTLY IF NOT EXISTS", "CREATE INDEX IF NOT EXISTS")
    if "CREATE INDEX CONCURRENTLY" in m
    else m
    for m in BASE_MIGRATIONS
]


class FixedAsyncPostgresSaver(AsyncPostgresSaver):
    MIGRATIONS = _MIGRATIONS


class AsyncPostgresCheckpointerFactory(CheckpointerFabric):
    async def get_checkpointer(self, db_uri: str, **kwargs):
        conn = await AsyncConnection.connect(
            db_uri, autocommit=True, row_factory=dict_row
        )
        async with conn:
            async with conn.cursor() as cur:
                await cur.execute(_MIGRATIONS[0])
                results = await cur.execute(
                    "SELECT v FROM checkpoint_migrations ORDER BY v DESC LIMIT 1"
                )
                row = await results.fetchone()
                version = row["v"] if row else -1
                for v, migration in enumerate(
                    _MIGRATIONS[version + 1:], start=version + 1
                ):
                    await cur.execute(migration)
                    await cur.execute(
                        "INSERT INTO checkpoint_migrations (v) VALUES (%s)", (v,)
                    )

        pool = AsyncConnectionPool(db_uri, open=False, timeout=3, reconnect_timeout=3)
        await pool.open()
        checkpointer = FixedAsyncPostgresSaver(pool)
        return checkpointer
