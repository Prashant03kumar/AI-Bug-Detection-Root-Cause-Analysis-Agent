"""Investigation tools registry for BugSleuth agent."""

from typing import Any, Dict, List
from langchain_core.tools import BaseTool

from app.tools.ast_source import get_function_source
from app.tools.call_graph import find_callees, find_callers
from app.tools.code_search import search_code
from app.tools.commit_diff import show_commit_diff
from app.tools.error_parser import parse_error
from app.tools.file_reader import read_file
from app.tools.git_blame import git_blame
from app.tools.log_search import search_logs
from app.tools.recent_commits import recent_commits
from app.tools.similar_bugs import find_similar_bugs

# List of all investigation tools available to the LangGraph agent and Gemini
ALL_TOOLS: List[BaseTool] = [
    parse_error,
    search_code,
    read_file,
    get_function_source,
    find_callers,
    find_callees,
    git_blame,
    recent_commits,
    show_commit_diff,
    search_logs,
    find_similar_bugs,
]

TOOL_DESCRIPTIONS: Dict[str, str] = {
    tool.name: tool.description or "" for tool in ALL_TOOLS
}

__all__ = [
    "ALL_TOOLS",
    "TOOL_DESCRIPTIONS",
    "parse_error",
    "search_code",
    "read_file",
    "get_function_source",
    "find_callers",
    "find_callees",
    "git_blame",
    "recent_commits",
    "show_commit_diff",
    "search_logs",
    "find_similar_bugs",
]
