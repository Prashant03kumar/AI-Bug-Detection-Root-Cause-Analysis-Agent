"""Git blame inspection tool for tracing authors, commits, and timestamps of code lines."""

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.config import get_settings
from app.logging_setup import get_logger
from app.tools.common import resolve_sandboxed_path, truncate_output

logger = get_logger("tools.git_blame")


class GitBlameArgs(BaseModel):
    """Input schema for git_blame tool."""
    file: str = Field(..., description="File path relative to repository (e.g. 'shopapp/users.py')")
    start_line: Optional[int] = Field(default=None, description="Starting line number (1-indexed)")
    end_line: Optional[int] = Field(default=None, description="Ending line number (inclusive)")


def git_blame_impl(
    file: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> str:
    """Run git blame on a sandboxed file, grouping adjacent lines by introducing commit."""
    try:
        abs_path, rel_path = resolve_sandboxed_path(file)
    except Exception as exc:
        return f"Error: {exc}"

    settings = get_settings()
    repo_root = Path(settings.target_repo_path).resolve()

    cmd = ["git", "blame", "--line-porcelain"]
    if start_line is not None and end_line is not None:
        cmd.extend(["-L", f"{start_line},{end_line}"])
    elif start_line is not None:
        cmd.extend(["-L", f"{start_line},{start_line + 30}"])

    cmd.append(rel_path)

    try:
        res = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as err:
        return f"Error executing git blame: {err.stderr.strip() or str(err)}"
    except Exception as exc:
        return f"Error running git blame: {exc}"

    porcelain_output = res.stdout
    if not porcelain_output.strip():
        return f"No git blame data returned for '{rel_path}'."

    # Parse porcelain blame lines
    groups: List[Dict[str, Any]] = []
    current_entry: Dict[str, Any] = {}

    for line in porcelain_output.splitlines():
        if not line:
            continue
        if not current_entry and re_match_hash(line):
            parts = line.split()
            current_entry["commit"] = parts[0]
            current_entry["line_num"] = int(parts[2])
        elif line.startswith("author "):
            current_entry["author"] = line[7:].strip()
        elif line.startswith("author-time "):
            ts = int(line[12:].strip())
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            current_entry["date"] = dt.strftime("%Y-%m-%d %H:%M:%S")
        elif line.startswith("summary "):
            current_entry["summary"] = line[8:].strip()
        elif line.startswith("\t"):
            code = line[1:]
            current_entry["code"] = code

            # Append or merge into line groups
            if groups and groups[-1]["commit"] == current_entry["commit"] and groups[-1]["end_line"] == current_entry["line_num"] - 1:
                groups[-1]["end_line"] = current_entry["line_num"]
                groups[-1]["lines"].append((current_entry["line_num"], code))
            else:
                groups.append({
                    "commit": current_entry["commit"],
                    "author": current_entry.get("author", "Unknown"),
                    "date": current_entry.get("date", "Unknown"),
                    "summary": current_entry.get("summary", ""),
                    "start_line": current_entry["line_num"],
                    "end_line": current_entry["line_num"],
                    "lines": [(current_entry["line_num"], code)],
                })
            current_entry = {}

    output_lines = [f"Git Blame for {rel_path}:"]
    for g in groups:
        short_hash = g["commit"][:7]
        line_range_str = f"Lines {g['start_line']}-{g['end_line']}" if g["start_line"] != g["end_line"] else f"Line {g['start_line']}"
        output_lines.append(
            f"\n[{short_hash}] {g['author']} ({g['date']}) \"{g['summary']}\" | {line_range_str}:"
        )
        for num, code in g["lines"][:15]:
            output_lines.append(f"  {num:4d} | {code}")
        if len(g["lines"]) > 15:
            output_lines.append(f"  ... ({len(g['lines']) - 15} more lines in this commit group)")

    return truncate_output("\n".join(output_lines))


def re_match_hash(line: str) -> bool:
    """Check if line starts with a 40-character hex commit hash."""
    parts = line.split()
    return len(parts) >= 3 and len(parts[0]) == 40 and all(c in "0123456789abcdef" for c in parts[0].lower())


@tool("git_blame", args_schema=GitBlameArgs)
def git_blame(
    file: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
) -> str:
    """Inspect line-by-line revision history of a file to identify who last modified code and which commit introduced changes.

    Args:
        file: Relative path to target file (e.g. 'shopapp/users.py').
        start_line: Optional starting line number.
        end_line: Optional ending line number.

    Returns:
        Structured git blame output showing commits, authors, dates, messages, and code lines.
    """
    try:
        return git_blame_impl(file, start_line, end_line)
    except Exception as exc:
        logger.error("git_blame failed: %s", exc)
        return f"Error executing git blame: {exc}"
