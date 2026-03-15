# Backend Agents

This backend contains a reusable agent framework under [agents](./agents). The goal is to make new agents easy to build without repeating model setup, checkpointing, middleware wiring, logging, and filesystem configuration each time.

## Structure

- `agents/core/`
  Shared building blocks such as config, middleware factories, guardrails, checkpointing, and the common `build_agent(...)` factory.
- `agents/utils/`
  Shared helpers for logging and model initialization.
- `agents/research_agent/`
  A concrete example agent built on top of the shared foundation.

## How To Build A Custom Agent

Create a new folder inside `agents/`, for example `agents/support_agent/`, and keep the same shape as `research_agent`:

- `prompts.py`
  Define the system prompt for the agent.
- `tools.py`
  Add the tools that agent can call.
- `middleware.py`
  Compose shared middleware from `agents/core/middleware.py` and add any agent-specific middleware.
- `agent.py`
  Build the final agent with `agents.core.factory.build_agent(...)`.
- `config.py`
  Optional agent-specific settings if the agent needs custom limits or behavior.

## Recommended Build Flow

1. Reuse shared models from `agents/utils/llms.py`.
2. Reuse shared middleware from `agents/core/middleware.py`.
3. Reuse shared runtime settings from `agents/core/config.py`.
4. Call `build_agent(...)` from `agents/core/factory.py`.
5. Expose a single constructor such as `create_support_agent()`.

## Minimal Example

```python
from agents.core.config import get_runtime_settings
from agents.core.factory import build_agent
from agents.core.middleware import build_default_middleware
from agents.utils.llms import get_fallback_llm, get_llm

from agents.support_agent.prompts import SYSTEM_PROMPT
from agents.support_agent.tools import search_docs


def create_support_agent():
    settings = get_runtime_settings()
    model = get_llm()

    middleware = build_default_middleware(
        primary_model=model,
        fallback_model=get_fallback_llm(),
        settings=settings.middleware,
    )

    return build_agent(
        model=model,
        tools=[search_docs],
        system_prompt=SYSTEM_PROMPT,
        middleware=middleware,
        settings=settings,
    )
```

## Notes

- Daily logs are written to `backend/logs/`.
- Research-style file saving is already handled safely with virtual filesystem paths.
- If an agent needs custom storage behavior, add it in that agent's `middleware.py` rather than changing shared defaults first.
- `agents/research_agent/` is the best reference implementation for future agents.
