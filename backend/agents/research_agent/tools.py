from __future__ import annotations

from io import BytesIO
from typing import Literal

def web_search(
    search_query: str,
    max_results: int = 3,
    time: Literal["d", "w", "m", "y"] = "y",
    source: Literal["text", "news"] = "text",
) -> str:
    """Search the web for current information."""

    from langchain_community.tools import DuckDuckGoSearchResults
    from langchain_community.utilities import DuckDuckGoSearchAPIWrapper

    wrapper = DuckDuckGoSearchAPIWrapper(time=time, max_results=max_results)
    search = DuckDuckGoSearchResults(api_wrapper=wrapper, source=source, output_format="json")
    return search.invoke(search_query)


def arxiv_search(query: str, max_results: int = 5) -> list[dict]:
    """Search ArXiv for academic papers."""

    import arxiv

    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    )

    papers = []
    for result in search.results():
        papers.append(
            {
                "title": result.title,
                "authors": [author.name for author in result.authors],
                "published": str(result.published.date()),
                "summary": result.summary,
                "pdf_url": result.pdf_url,
                "entry_id": result.entry_id,
            }
        )

    return papers


def read_arxiv_pdf(pdf_url: str) -> str:
    """Download an ArXiv PDF and extract a text preview."""

    import requests

    from pypdf import PdfReader

    response = requests.get(pdf_url, timeout=30)
    response.raise_for_status()

    reader = PdfReader(BytesIO(response.content))
    text = "".join(page.extract_text() or "" for page in reader.pages)
    return text[:20_000]


def semantic_scholar_search(query: str, max_results: int = 5) -> list[dict]:
    """Search Semantic Scholar for papers."""

    from semanticscholar import SemanticScholar

    scholar = SemanticScholar()
    results = scholar.search_paper(query, limit=max_results)

    papers = []
    for paper in results:
        papers.append(
            {
                "title": paper.title,
                "authors": [author.name for author in paper.authors] if paper.authors else [],
                "year": paper.year,
                "abstract": paper.abstract,
                "citation_count": paper.citationCount,
                "paper_id": paper.paperId,
                "url": paper.url,
            }
        )

    return papers
