from __future__ import annotations

from collections.abc import Iterable

from langchain.agents import create_agent

from agents.core.checkpointing import build_checkpointer
from agents.core.config import AgentRuntimeSettings


def build_agent(
    *,
    model,
    tools: Iterable,
    system_prompt: str,
    middleware: Iterable,
    settings: AgentRuntimeSettings,
):
    checkpointer = build_checkpointer(settings.memory)
    return create_agent(
        model=model,
        tools=list(tools),
        system_prompt=system_prompt,
        middleware=list(middleware),
        checkpointer=checkpointer,
    )
