from __future__ import annotations

from agents.basic_agent.middleware import build_basic_middleware
from agents.basic_agent.prompts import SYSTEM_PROMPT
from agents.basic_agent.tools import TOOLS
from agents.core.config import get_runtime_settings
from agents.core.factory import build_agent
from agents.utils.llms import get_llm
from agents.utils.logging import get_logger


logger = get_logger(__name__)


def create_basic_agent():
    settings = get_runtime_settings()
    model = get_llm()

    logger.info("Building basic agent.")
    agent = build_agent(
        model=model,
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
        middleware=build_basic_middleware(settings),
        settings=settings,
    )
    logger.info("Basic agent built successfully.")
    return agent
