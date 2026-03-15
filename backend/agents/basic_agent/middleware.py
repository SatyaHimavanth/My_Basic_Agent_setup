from __future__ import annotations

from langchain.agents.middleware import HumanInTheLoopMiddleware

from agents.core.config import AgentRuntimeSettings
from agents.core.middleware import build_default_middleware
from agents.utils.llms import get_fallback_llm
from agents.utils.llms import get_llm


def build_basic_middleware(settings: AgentRuntimeSettings) -> list:
    primary_model = get_llm()
    fallback_model = get_fallback_llm()

    middleware = build_default_middleware(
        primary_model=primary_model,
        fallback_model=fallback_model,
        settings=settings.middleware,
    )

    middleware.append(
        HumanInTheLoopMiddleware(
            interrupt_on={
                "get_weather": {
                    "allowed_decisions": ["approve", "edit", "reject"],
                    "description": (
                        "Weather lookup requires approval. Review the city before the dummy weather tool runs."
                    ),
                }
            },
            description_prefix="Pending approval",
        )
    )

    return middleware
