from __future__ import annotations

import os

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


BACKEND_DIR = Path(__file__).resolve().parents[2]


@dataclass(slots=True, frozen=True)
class PathSettings:
    backend_dir: Path = BACKEND_DIR
    logs_dir: Path = BACKEND_DIR / "logs"
    research_dir: Path = BACKEND_DIR / "research"


@dataclass(slots=True, frozen=True)
class MemorySettings:
    memory_type: str = os.getenv("AGENT_MEMORY_TYPE", "postgres").strip().lower()
    postgres_url: str = os.getenv("PG_MEMORY_DB_URL", "").strip()

    @property
    def use_postgres(self) -> bool:
        return self.memory_type == "postgres" and bool(self.postgres_url)


@dataclass(slots=True, frozen=True)
class MiddlewareSettings:
    model_retry_max_retries: int = 3
    tool_retry_max_retries: int = 3
    retry_backoff_factor: float = 2.0
    retry_initial_delay: float = 1.0
    context_edit_trigger_tokens: int = 100_000
    context_edit_keep_tool_uses: int = 3
    summarization_trigger_tokens: int = 4_000
    summarization_keep_messages: int = 20
    save_reports_to_filesystem: bool = True
    enable_todo_middleware: bool = True


@dataclass(slots=True, frozen=True)
class AgentRuntimeSettings:
    paths: PathSettings = PathSettings()
    memory: MemorySettings = MemorySettings()
    middleware: MiddlewareSettings = MiddlewareSettings()


def get_runtime_settings() -> AgentRuntimeSettings:
    return AgentRuntimeSettings()
