from __future__ import annotations

from agents.core.config import get_runtime_settings
from agents.core.factory import build_agent
from agents.research_agent.middleware import build_research_middleware
from agents.research_agent.prompts import SYSTEM_PROMPT
from agents.research_agent.tools import arxiv_search
from agents.research_agent.tools import read_arxiv_pdf
from agents.research_agent.tools import semantic_scholar_search
from agents.utils.llms import get_llm
from agents.utils.logging import get_logger


logger = get_logger(__name__)


def create_research_agent():
    settings = get_runtime_settings()
    settings.paths.research_dir.mkdir(parents=True, exist_ok=True)
    model = get_llm()

    logger.info("Building research agent.")
    agent = build_agent(
        model=model,
        tools=[arxiv_search, read_arxiv_pdf, semantic_scholar_search],
        system_prompt=SYSTEM_PROMPT,
        middleware=build_research_middleware(settings),
        settings=settings,
    )
    logger.info("Research agent built successfully.")
    return agent


if __name__ == "__main__":
    agent = create_research_agent()
    messages = {
        "messages": [
            {
                "role": "user",
                "content": "Can you save the research once again? I do not see the file in my directory. Return the absolute path as well.",
            }
        ]
    }
    config = {"configurable": {"thread_id": "thread_1"}}
    for chunk in agent.stream(input=messages, config=config, stream_mode="updates"):
        print(chunk)
