"""Historical bug ticket similarity search tool."""

from typing import Any, Dict, List
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.indexing.retriever import search_tickets
from app.logging_setup import get_logger
from app.tools.common import truncate_output

logger = get_logger("tools.similar_bugs")


class FindSimilarBugsArgs(BaseModel):
    """Input schema for find_similar_bugs tool."""
    description: str = Field(..., description="Bug description, error message, or symptom to find similar past tickets for")
    k: int = Field(default=3, description="Number of past tickets to retrieve (default: 3)")


def find_similar_bugs_impl(description: str, k: int = 3) -> str:
    """Query Chroma bug_tickets collection for historically resolved issues similar to description."""
    if not description or not description.strip():
        return "Error: Empty description provided for similar bugs search."

    results = search_tickets(query=description.strip(), k=k)
    if not results:
        return f"No similar historical tickets found for: '{description[:80]}'."

    lines = [f"Found {len(results)} similar past bug ticket(s):"]
    for i, t in enumerate(results, start=1):
        tid = t.get("ticket_id", "unknown")
        title = t.get("title", "")
        score = t.get("score", 0.0)
        touched = ", ".join(t.get("files_touched", [])) or "None"
        raw_text = t.get("text", "")

        lines.append(
            f"\n{i}. [{score:.2f}] {tid}: {title}\n"
            f"   Files touched: {touched}\n"
            f"   Details:\n   {raw_text.strip()}"
        )

    return truncate_output("\n".join(lines))


@tool("find_similar_bugs", args_schema=FindSimilarBugsArgs)
def find_similar_bugs(description: str, k: int = 3) -> str:
    """Retrieve historically resolved bug tickets similar to current error symptoms to inspect previous fixes.

    Args:
        description: Description of the bug, symptoms, or error message.
        k: Maximum number of tickets to return (default: 3).

    Returns:
        Formatted past bug tickets with descriptions, resolutions, and files modified.
    """
    try:
        return find_similar_bugs_impl(description, k)
    except Exception as exc:
        logger.error("find_similar_bugs failed: %s", exc)
        return f"Error retrieving similar bugs: {exc}"
