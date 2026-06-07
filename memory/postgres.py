from .checkpointer import CheckpointerFabric
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool


class AsyncPostgresCheckpointerFactory(CheckpointerFabric):
    async def get_checkpointer(self, db_uri: str, **kwargs):
        pool = AsyncConnectionPool(db_uri, open=False)
        await pool.open()
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        return checkpointer
