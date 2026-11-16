"""AST-based call graph tools to inspect callers and callees across the repository."""

import ast
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.config import get_settings
from app.indexing.chunker import IGNORED_DIRS, extract_calls
from app.logging_setup import get_logger
from app.tools.common import truncate_output

logger = get_logger("tools.call_graph")

# In-memory call graph cache: repo_path -> (callers_map, callees_map)
_CALL_GRAPH_CACHE: Dict[str, Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]] = {}


class SymbolArg(BaseModel):
    """Input schema for call graph tools."""
    symbol: str = Field(..., description="Function or method name to query (e.g. 'check_and_reserve_stock')")


def build_repo_call_graph(repo_path: Path) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    """Scan all Python files in the repository to build callers and callees mappings."""
    callers_map: Dict[str, Set[str]] = {}
    callees_map: Dict[str, Set[str]] = {}

    for py_file in repo_path.rglob("*.py"):
        rel_parts = py_file.relative_to(repo_path).parts
        if any(part in IGNORED_DIRS or part.startswith(".") for part in rel_parts):
            continue

        try:
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()
            tree = ast.parse(content, filename=str(py_file))
        except Exception:
            continue

        rel_path = py_file.relative_to(repo_path).as_posix()

        # Walk functions and methods
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                caller_name = f"{rel_path}::{node.name}"
                callees = extract_calls(node)
                callees_map[node.name] = set(callees)
                callees_map[caller_name] = set(callees)

                for target in callees:
                    callers_map.setdefault(target, set()).add(caller_name)
                    # Also map bare function name
                    short_target = target.split(".")[-1]
                    callers_map.setdefault(short_target, set()).add(caller_name)

            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_symbol = f"{node.name}.{item.name}"
                        caller_name = f"{rel_path}::{method_symbol}"
                        callees = extract_calls(item)
                        callees_map[item.name] = set(callees)
                        callees_map[method_symbol] = set(callees)
                        callees_map[caller_name] = set(callees)

                        for target in callees:
                            callers_map.setdefault(target, set()).add(caller_name)
                            short_target = target.split(".")[-1]
                            callers_map.setdefault(short_target, set()).add(caller_name)

    return callers_map, callees_map


def get_call_graph() -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    """Retrieve or build cached repository call graph."""
    global _CALL_GRAPH_CACHE
    repo_root = Path(get_settings().target_repo_path).resolve()
    repo_key = str(repo_root)

    if repo_key not in _CALL_GRAPH_CACHE:
        logger.info("Building AST call graph for %s...", repo_key)
        _CALL_GRAPH_CACHE[repo_key] = build_repo_call_graph(repo_root)

    return _CALL_GRAPH_CACHE[repo_key]


def find_callers_impl(symbol: str) -> str:
    """Find all functions and methods calling the specified symbol."""
    sym = symbol.strip()
    if not sym:
        return "Error: Empty symbol provided."

    callers_map, _ = get_call_graph()
    matching_callers = callers_map.get(sym, set())

    # Check bare symbol name if qualified symbol passed
    if not matching_callers and "." in sym:
        short_sym = sym.split(".")[-1]
        matching_callers = callers_map.get(short_sym, set())

    if not matching_callers:
        return f"No callers found in repository for symbol '{symbol}'."

    sorted_callers = sorted(list(matching_callers))
    lines = [f"Found {len(sorted_callers)} caller(s) of '{symbol}':"]
    for i, c in enumerate(sorted_callers, start=1):
        lines.append(f"  {i}. {c}")

    return truncate_output("\n".join(lines))


def find_callees_impl(symbol: str) -> str:
    """Find all functions and methods called by the specified symbol."""
    sym = symbol.strip()
    if not sym:
        return "Error: Empty symbol provided."

    _, callees_map = get_call_graph()
    matching_callees = callees_map.get(sym, set())

    if not matching_callees and "." in sym:
        short_sym = sym.split(".")[-1]
        matching_callees = callees_map.get(short_sym, set())

    if not matching_callees:
        return f"No callees found in repository called by '{symbol}'."

    sorted_callees = sorted(list(matching_callees))
    lines = [f"Symbol '{symbol}' calls {len(sorted_callees)} function(s)/method(s):"]
    for i, c in enumerate(sorted_callees, start=1):
        lines.append(f"  {i}. {c}")

    return truncate_output("\n".join(lines))


@tool("find_callers", args_schema=SymbolArg)
def find_callers(symbol: str) -> str:
    """Find all functions and methods across the codebase that call the specified symbol.

    Args:
        symbol: Function or method name to inspect (e.g. 'check_and_reserve_stock').

    Returns:
        List of calling functions/methods and their file paths.
    """
    try:
        return find_callers_impl(symbol)
    except Exception as exc:
        logger.error("find_callers failed: %s", exc)
        return f"Error finding callers: {exc}"


@tool("find_callees", args_schema=SymbolArg)
def find_callees(symbol: str) -> str:
    """Find all functions and methods invoked inside the body of the specified symbol.

    Args:
        symbol: Function or method name to inspect (e.g. 'place_order').

    Returns:
        List of functions and methods called by this symbol.
    """
    try:
        return find_callees_impl(symbol)
    except Exception as exc:
        logger.error("find_callees failed: %s", exc)
        return f"Error finding callees: {exc}"
