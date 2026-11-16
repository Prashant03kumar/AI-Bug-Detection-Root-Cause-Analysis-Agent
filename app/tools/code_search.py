"""Code semantic search tool using Chroma code chunk index."""

from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.indexing.retriever import search_code_chunks
from app.logging_setup import get_logger
from app.tools.common import truncate_output

logger = get_logger("tools.code_search")


class SearchCodeArgs(BaseModel):
    """Input schema for search_code tool."""
    query: str = Field(..., description="Query string, symptom description, or function/symbol to search for")
    k: int = Field(default=5, description="Number of code chunks to return (default: 5)")


def search_code_impl(query: str, k: int = 5) -> str:
    """Execute code search and format matching chunks."""
    if not query or not query.strip():
        return "Error: Empty query provided for code search."

    results = search_code_chunks(query=query.strip(), k=k)
    if not results:
        return f"No code chunks matched query: '{query}'."

    output_lines = [f"Found {len(results)} matching code chunk(s):"]
    for i, r in enumerate(results, start=1):
        file_path = r.get("file_path", "unknown")
        sym = r.get("symbol_name", "unknown")
        kind = r.get("kind", "unknown")
        s_line = r.get("start_line", 1)
        e_line = r.get("end_line", 1)
        score = r.get("score", 0.0)
        snippet = r.get("text", "").strip()

        # Short snippet preview: keep up to 8 lines
        snippet_preview = "\n   ".join(snippet.splitlines()[:10])

        output_lines.append(
            f"\n{i}. [{score:.2f}] {file_path}::{sym} (lines {s_line}-{e_line}, {kind})\n"
            f"   Snippet:\n   {snippet_preview}"
        )

    return truncate_output("\n".join(output_lines))


@tool("search_code", args_schema=SearchCodeArgs)
def search_code(query: str, k: int = 5) -> str:
    """Search codebase for relevant functions, classes, or keywords using semantic vector retrieval.

    Args:
        query: Search string or error description.
        k: Maximum number of results (default 5).

    Returns:
        Formatted list of matching code chunks with files, symbols, line ranges, and previews.
    """
    try:
        return search_code_impl(query, k)
    except Exception as exc:
        logger.error("search_code failed: %s", exc)
        return f"Error executing code search: {exc}"
