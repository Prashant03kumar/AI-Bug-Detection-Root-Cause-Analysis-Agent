"""Tool to inspect recent git commit history on repository or file level."""

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.config import get_settings
from app.logging_setup import get_logger
from app.tools.common import resolve_sandboxed_path, truncate_output

logger = get_logger("tools.recent_commits")


class RecentCommitsArgs(BaseModel):
    """Input schema for recent_commits tool."""
    file: Optional[str] = Field(default=None, description="Optional relative file path to restrict commit log to")
    n: int = Field(default=10, description="Maximum number of commits to retrieve (default: 10)")
    since_days: Optional[int] = Field(default=None, description="Optional filter to only commits in the last N days")


def recent_commits_impl(
    file: Optional[str] = None,
    n: int = 10,
    since_days: Optional[int] = None,
) -> str:
    """Retrieve recent commits with authors, timestamps, and touched files."""
    settings = get_settings()
    repo_root = Path(settings.target_repo_path).resolve()

    cmd = [
        "git",
        "log",
        f"-n{max(1, min(n, 50))}",
        "--format=commit %H%nAuthor: %an <%ae>%nDate:   %ad%nSubject: %s",
        "--name-status",
        "--date=iso",
    ]

    if since_days is not None:
        cmd.append(f"--since={since_days}.days")

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
        return f"Error retrieving commit history: {err.stderr.strip() or str(err)}"
    except Exception as exc:
        return f"Error running git log: {exc}"

    output = res.stdout.strip()
    if not output:
        target_str = f" for '{file}'" if file else ""
        return f"No commits found{target_str}."

    return truncate_output(output)


@tool("recent_commits", args_schema=RecentCommitsArgs)
def recent_commits(
    file: Optional[str] = None,
    n: int = 10,
    since_days: Optional[int] = None,
) -> str:
    """View recent git commits, authors, commit messages, and touched files across repository or for a specific file.

    Args:
        file: Optional relative path to filter commits for a single file.
        n: Number of commits to show (default: 10).
        since_days: Optional number of days to look back.

    Returns:
        Formatted git log showing recent commits and changed files.
    """
    try:
        return recent_commits_impl(file, n, since_days)
    except Exception as exc:
        logger.error("recent_commits failed: %s", exc)
        return f"Error retrieving recent commits: {exc}"
