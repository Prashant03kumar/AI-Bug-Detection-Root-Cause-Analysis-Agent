"""Comprehensive test suite for investigation tools."""

import json
from pathlib import Path
import pytest

from app.tools import (
    ALL_TOOLS,
    TOOL_DESCRIPTIONS,
    find_callees,
    find_callers,
    get_function_source,
    git_blame,
    parse_error,
    read_file,
    recent_commits,
    search_code,
    search_logs,
    show_commit_diff,
)
from app.tools.common import resolve_sandboxed_path
from app.tools.error_parser import parse_error_impl
from app.tools.file_reader import read_file_impl

DATA_BUGS_DIR = Path("data") / "bugs"


def test_tool_registry():
    """Verify all 11 tools are registered with schemas and descriptions."""
    assert len(ALL_TOOLS) == 11
    assert len(TOOL_DESCRIPTIONS) == 11
    for tool_instance in ALL_TOOLS:
        assert tool_instance.name in TOOL_DESCRIPTIONS
        assert len(tool_instance.description) > 10


def test_sandbox_escape_attempts():
    """Verify paths attempting directory traversal outside target repo are rejected."""
    traversal_paths = [
        "../../.env",
        "../.env",
        "../../PROJECT_CONTEXT.md",
        "/etc/passwd",
        "C:\\Windows\\System32\\drivers\\etc\\hosts",
    ]

    for bad_path in traversal_paths:
        # direct helper should raise PermissionError
        with pytest.raises(PermissionError):
            resolve_sandboxed_path(bad_path)

        # tool functions should return readable error strings rather than crashing
        read_res = read_file.invoke({"path": bad_path})
        assert "Error:" in read_res or "Security Error:" in read_res

        src_res = get_function_source.invoke({"file": bad_path, "symbol": "foo"})
        assert "Error:" in src_res

        blame_res = git_blame.invoke({"file": bad_path})
        assert "Error:" in blame_res

        recent_res = recent_commits.invoke({"file": bad_path})
        assert "Error:" in recent_res

        diff_res = show_commit_diff.invoke({"commit_hash": "HEAD", "file": bad_path})
        assert "Error:" in diff_res


def test_parse_error_all_10_bugs():
    """Verify parse_error parses all 10 real bug error files properly."""
    bug_dirs = sorted([d for d in DATA_BUGS_DIR.iterdir() if d.is_dir() and d.name.startswith("BUG-")])
    assert len(bug_dirs) == 10

    for bdir in bug_dirs:
        err_file = bdir / "error.txt"
        assert err_file.is_file()
        text = err_file.read_text(encoding="utf-8")

        res = parse_error_impl(text)
        assert res["error_type"] is not None and len(res["error_type"]) > 0
        assert isinstance(res["frames"], list)
        assert len(res["candidate_keywords"]) > 0

        # Also test via LangChain tool invoke
        tool_res = parse_error.invoke({"text": text})
        data = json.loads(tool_res)
        assert data["error_type"] == res["error_type"]


def test_read_file_valid():
    """Verify read_file loads numbered source code from demo_repo."""
    res = read_file.invoke({"path": "shopapp/users.py", "start_line": 1, "end_line": 15})
    assert "File: shopapp/users.py" in res
    assert "1 |" in res
    assert "def get_user" in res


def test_get_function_source():
    """Verify get_function_source extracts exact AST function lines."""
    res = get_function_source.invoke({
        "file": "shopapp/inventory.py",
        "symbol": "check_and_reserve_stock",
    })
    assert "Symbol: check_and_reserve_stock" in res
    assert "def check_and_reserve_stock" in res
    assert "stock > quantity" in res or "stock >= quantity" in res


def test_call_graph():
    """Verify find_callers and find_callees report cross-module relationships."""
    callees_out = find_callees.invoke({"symbol": "place_order"})
    assert "assemble_order_items" in callees_out or "check_and_reserve_stock" in callees_out

    callers_out = find_callers.invoke({"symbol": "assemble_order_items"})
    assert "place_order" in callers_out


def test_git_blame():
    """Verify git_blame returns commit hashes and author names."""
    res = git_blame.invoke({
        "file": "shopapp/users.py",
        "start_line": 35,
        "end_line": 38,
    })
    assert "Git Blame for shopapp/users.py" in res
    assert "Asha" in res or "Ravi" in res


def test_recent_commits():
    """Verify recent_commits returns git log entries."""
    res = recent_commits.invoke({"n": 5})
    assert "Author:" in res
    assert "Subject:" in res


def test_show_commit_diff():
    """Verify show_commit_diff produces diff content."""
    res = show_commit_diff.invoke({"commit_hash": "HEAD"})
    assert "commit" in res.lower()
    assert "diff --git" in res


def test_search_logs():
    """Verify search_logs finds entries in app.log."""
    res = search_logs.invoke({"query": "BUG-01"})
    assert "Executing Scenario BUG-01" in res or "BUG-01 reproduced" in res
