"""
Tavily web search wrapper.

Single public function
──────────────────────
    run_tavily_search(query) -> list[dict]

Each returned dict has:
    url     : str   — source URL
    title   : str   — page title
    content : str   — snippet / extracted text from the page
    score   : float — Tavily relevance score (0–1)
"""

import logging

from tavily import TavilyClient

from config.config import TAVILY_API_KEY, TAVILY_MAX_RESULTS, TAVILY_SEARCH_DEPTH

logger = logging.getLogger(__name__)

# Module-level client — initialised once, reused for every search call.
_client = TavilyClient(api_key=TAVILY_API_KEY)


def run_tavily_search(query: str) -> list[dict]:
    """Run a single Tavily web search and return normalised results.

    Args:
        query: The search string to submit to Tavily.

    Returns:
        A list of result dicts, each containing:
            url, title, content, score.
        Returns an empty list on any error so callers can continue safely.
    """
    logger.debug("Tavily search: %r (depth=%s, max=%d)", query, TAVILY_SEARCH_DEPTH, TAVILY_MAX_RESULTS)

    try:
        response = _client.search(
            query=query,
            search_depth=TAVILY_SEARCH_DEPTH,
            max_results=TAVILY_MAX_RESULTS,
        )

        results: list[dict] = [
            {
                "url":     hit.get("url", ""),
                "title":   hit.get("title", ""),
                "content": hit.get("content", ""),
                "score":   hit.get("score", 0.0),
            }
            for hit in response.get("results", [])
        ]

        logger.debug("Tavily search returned %d results for %r", len(results), query)
        return results

    except Exception as exc:
        logger.error("Tavily search failed for query %r: %s", query, exc)
        return []
