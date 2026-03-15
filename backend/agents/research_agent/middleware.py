from __future__ import annotations

from agents.core.config import AgentRuntimeSettings
from agents.core.middleware import build_default_middleware
from agents.core.middleware import build_filesystem_middleware
from agents.core.middleware import build_subagent_middleware
from agents.utils.llms import get_fallback_llm
from agents.utils.llms import get_llm

from agents.research_agent.tools import web_search


def build_research_middleware(settings: AgentRuntimeSettings) -> list:
    primary_model = get_llm()
    fallback_model = get_fallback_llm()

    middleware = build_default_middleware(
        primary_model=primary_model,
        fallback_model=fallback_model,
        settings=settings.middleware,
    )

    filesystem_prompt = """
You have access to a filesystem.

Always save research results to disk.

Rules:
- Save final reports as markdown files
- Use filename format: research_<topic>.md
- Store files relative to the current research workspace root only
- Do not use absolute paths like /research/... or C:/...
- Use write_file with relative paths such as research_topic.md
- Overwrite existing files if needed
""".strip()

    if settings.middleware.save_reports_to_filesystem:
        middleware.append(
            build_filesystem_middleware(
                root_dir=settings.paths.research_dir,
                system_prompt=filesystem_prompt,
            )
        )

    middleware.append(
        build_subagent_middleware(
            root_dir=settings.paths.research_dir,
            subagents=[
                {
                    "name": "Websurfer",
                    "description": "Finds and reads information from the web.",
                    "system_prompt": (
                        "You search the web and read webpages to extract factual information. "
                        "Always read links returned by search results. Save required info in the provided backend."
                    ),
                    "model": primary_model,
                    "tools": [web_search],
                }
            ],
        )
    )

    return middleware
