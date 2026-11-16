"""Git commit diff inspection tool."""

import subprocess
from pathlib import Path
from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.config import get_settings
from app.logging_setup import get_logger
from app.tools.common import resolve_sandboxed_path, truncate_output

logger = get_logger("tools.commit_diff")


class ShowCommitDiffArgs(BaseModel):
    """Input schema for show_commit_diff tool."""
    commit_hash: str = Field(..., description="Commit SHA or branch tag to inspect (e.g. '1f3a4df')")
    file: Optional[str] = Field(default=None, description="Optional relative file path to restrict diff to")


def show_commit_diff_impl(commit_hash: str, file: Optional[str] = None) -> str:
    """Retrieve full git diff of a specific commit."""
    clean_hash = commit_hash.strip()
    if not clean_hash:
        return "Error: Empty commit hash provided."

    settings = get_settings()
    repo_root = Path(settings.target_repo_path).resolve()

    cmd = ["git", "show", "--stat", "--patch", clean_hash]
    if file:
        try:
            _, rel_path = resolve_sandboxed_path(file)
            cmd.extend(["--", rel_path])
        except Exception as exc:
            return f"Error: {exc}"

    try:
        res = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as err:
        return f"Error retrieving commit diff for '{clean_hash}': {err.stderr.strip() or str(err)}"
    except Exception as exc:
        return f"Error running git show: {exc}"

    output = res.stdout.strip()
    if not output:
        return f"No diff content found for commit '{clean_hash}'."

    return truncate_output(output)


@tool("show_commit_diff", args_schema=ShowCommitDiffArgs)
def show_commit_diff(commit_hash: str, file: Optional[str] = None) -> str:
    """Show the code changes introduced by a specific git commit hash, optionally filtered to a single file.

    Args:
        commit_hash: Git commit hash or reference.
        file: Optional relative file path to view only its diff in this commit.

    Returns:
        Unified git diff and commit metadata.
    """
    try:
        return show_commit_diff_impl(commit_hash, file)
    except Exception as exc:
        logger.error("show_commit_diff failed: %s", exc)
        return f"Error showing commit diff: {exc}"
