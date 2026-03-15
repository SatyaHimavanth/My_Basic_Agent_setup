from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ResearchAgentSettings:
    web_search_max_results: int = 3
    arxiv_max_results: int = 5
    semantic_scholar_max_results: int = 5


def get_research_agent_settings() -> ResearchAgentSettings:
    return ResearchAgentSettings()
