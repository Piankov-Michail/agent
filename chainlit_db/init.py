import asyncpg

from chainlit_db.schema import CHAINLIT_SCHEMA_SQL


def _to_asyncpg_dsn(dsn: str) -> str:
    """Convert a SQLAlchemy DSN (``postgresql+asyncpg://``) to an asyncpg DSN (``postgresql://``)."""
    return dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


async def init_chainlit_database(dsn: str) -> None:
    """Create all required Chainlit tables if they do not already exist.

    Args:
        dsn: SQLAlchemy connection string
             (``postgresql+asyncpg://user:pass@host:5432/db``).
    """
    conn = await asyncpg.connect(_to_asyncpg_dsn(dsn))
    try:
        for stmt in CHAINLIT_SCHEMA_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    await conn.execute(stmt + ";")
                except Exception:
                    pass  # skip migration statements that fail (e.g. column already JSONB)
    finally:
        await conn.close()
