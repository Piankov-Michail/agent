from abc import ABC, abstractmethod
from typing import Any


class CheckpointerFabric(ABC):
    @abstractmethod
    async def get_checkpointer(self, **kwargs) -> Any:
        pass


async def create_checkpointer(db_uri: str, **kwargs) -> Any:
    if db_uri.startswith("postgresql://") or db_uri.startswith("postgres://"):
        from .postgres import AsyncPostgresCheckpointerFactory
        try:
            return await AsyncPostgresCheckpointerFactory().get_checkpointer(db_uri=db_uri, **kwargs)
        except Exception as e:
            from langgraph.checkpoint.memory import MemorySaver
            print(f"Warning: Postgres checkpointer failed ({e}), using MemorySaver")
            return MemorySaver()
    raise ValueError(f"Unsupported DB URI scheme in: {db_uri}")
