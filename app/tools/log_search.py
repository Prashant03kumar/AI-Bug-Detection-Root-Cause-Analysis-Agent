"""Application log search and analysis tool."""

import re
from pathlib import Path
from typing import List, Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.logging_setup import get_logger
from app.tools.common import truncate_output

logger = get_logger("tools.log_search")


class SearchLogsArgs(BaseModel):
    """Input schema for search_logs tool."""
    query: str = Field(..., description="Keywords or regex pattern to search for in application logs")
    around_time: Optional[str] = Field(default=None, description="Optional time string (e.g. '19:40' or '2026-11-16') to match near")
    level: Optional[str] = Field(default=None, description="Optional log level filter (e.g. 'ERROR', 'WARN', 'INFO')")
    max_lines: int = Field(default=40, description="Maximum number of log lines to return (default: 40)")


def search_logs_impl(
    query: str,
    around_time: Optional[str] = None,
    level: Optional[str] = None,
    max_lines: int = 40,
    log_file_override: Optional[Path] = None,
) -> str:
    """Scan application log files for matching entries, error levels, or temporal context."""
    if not query or not query.strip():
        return "Error: Empty query provided for log search."

    log_path = log_file_override or (Path("data") / "logs" / "app.log")
    if not log_path.is_file():
        # Fallback to general bugsleuth log
        alt_path = Path("data") / "bugsleuth.log"
        if alt_path.is_file():
            log_path = alt_path
        else:
            return f"Error: Log file not found at '{log_path}'."

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as exc:
        return f"Error reading log file '{log_path}': {exc}"

    if not lines:
        return f"Log file '{log_path}' is empty."

    # Build regex or case-insensitive search
    query_str = query.strip()
    try:
        pattern = re.compile(query_str, re.IGNORECASE)
    except re.error:
        pattern = re.compile(re.escape(query_str), re.IGNORECASE)

    level_filter = f"[{level.upper()}]" if level else None
    matched_lines: List[str] = []

    for line in lines:
        stripped = line.rstrip("\r\n")
        # Level check
        if level_filter and level_filter not in stripped.upper():
            continue
        # Time check
        if around_time and around_time not in stripped:
            continue
        # Query check
        if pattern.search(stripped):
            matched_lines.append(stripped)
            if len(matched_lines) >= max_lines:
                break

    if not matched_lines:
        filter_msg = f" (Level: {level}, Time: {around_time})" if (level or around_time) else ""
        return f"No log entries matched query '{query}'{filter_msg} in '{log_path}'."

    header = f"Found {len(matched_lines)} log line(s) matching '{query}' in {log_path}:\n"
    return truncate_output(header + "\n".join(matched_lines))


@tool("search_logs", args_schema=SearchLogsArgs)
def search_logs(
    query: str,
    around_time: Optional[str] = None,
    level: Optional[str] = None,
    max_lines: int = 40,
) -> str:
    """Grep application logs for errors, transaction IDs, stack traces, or operational events.

    Args:
        query: Search keyword, error name, or regex pattern.
        around_time: Optional timestamp or time fragment to narrow context.
        level: Optional log level filter ('ERROR', 'WARN', 'INFO').
        max_lines: Maximum log lines to return (default: 40).

    Returns:
        Matched lines from application log files.
    """
    try:
        return search_logs_impl(query, around_time, level, max_lines)
    except Exception as exc:
        logger.error("search_logs failed: %s", exc)
        return f"Error searching logs: {exc}"
