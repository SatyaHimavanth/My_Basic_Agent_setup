from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver

from agents.core.config import MemorySettings
from agents.utils.logging import get_logger


logger = get_logger(__name__)


def build_checkpointer(memory_settings: MemorySettings):
    if memory_settings.use_postgres:
        try:
            import psycopg
            from langgraph.checkpoint.postgres import PostgresSaver

            connection = psycopg.connect(memory_settings.postgres_url)
            connection.autocommit = True
            checkpointer = PostgresSaver(connection)
            checkpointer.setup()
            logger.info("Using Postgres checkpointer.")
            return checkpointer
        except Exception:
            logger.exception("Failed to initialize Postgres checkpointer. Falling back to in-memory.")

    logger.info("Using in-memory checkpointer.")
    return InMemorySaver()
