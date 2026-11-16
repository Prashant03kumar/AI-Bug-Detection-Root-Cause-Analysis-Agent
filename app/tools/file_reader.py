"""Sandboxed source file reader tool."""

from pathlib import Path
from typing import Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.logging_setup import get_logger
from app.tools.common import resolve_sandboxed_path, truncate_output

logger = get_logger("tools.file_reader")


class ReadFileArgs(BaseModel):
    """Input schema for read_file tool."""
    path: str = Field(..., description="Relative path to file within the target repository")
    start_line: Optional[int] = Field(default=None, description="Starting line number (1-indexed)")
    end_line: Optional[int] = Field(default=None, description="Ending line number (inclusive)")
    target_line: Optional[int] = Field(default=None, description="Center line to read around if start/end omitted")
    window: int = Field(default=30, description="Window size (+- lines around target_line, default: 30)")


def read_file_impl(
    path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    target_line: Optional[int] = None,
    window: int = 30,
) -> str:
    """Read numbered lines from a repository file within sandbox boundaries."""
    try:
        abs_path, rel_path = resolve_sandboxed_path(path)
    except Exception as exc:
        return f"Error: {exc}"

    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as exc:
        return f"Error reading file '{rel_path}': {exc}"

    total_lines = len(lines)
    if total_lines == 0:
        return f"File '{rel_path}' is empty."

    # Determine line window
    if start_line is not None and end_line is not None:
        s = max(1, start_line)
        e = min(total_lines, end_line)
    elif target_line is not None:
        s = max(1, target_line - window)
        e = min(total_lines, target_line + window)
    elif start_line is not None:
        s = max(1, start_line)
        e = min(total_lines, s + (window * 2))
    else:
        # Default first 60 lines
        s = 1
        e = min(total_lines, 60)

    if s > total_lines:
        return f"Error: Requested start line {s} exceeds total lines ({total_lines}) in '{rel_path}'."
    if s > e:
        s, e = e, s

    numbered_lines = []
    max_num_width = len(str(e))
    for line_num in range(s, e + 1):
        content = lines[line_num - 1].rstrip("\r\n")
        num_str = str(line_num).rjust(max_num_width)
        numbered_lines.append(f"{num_str} | {content}")

    header = f"File: {rel_path} (lines {s}-{e} of {total_lines}):\n"
    full_output = header + "\n".join(numbered_lines)
    return truncate_output(full_output)


@tool("read_file", args_schema=ReadFileArgs)
def read_file(
    path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    target_line: Optional[int] = None,
    window: int = 30,
) -> str:
    """Read lines of code from a file with line numbers. Strictly sandboxed to target repository.

    Args:
        path: Path to target file (e.g. 'shopapp/users.py').
        start_line: First line to read (optional).
        end_line: Last line to read (optional).
        target_line: Center line to display +- window around (optional).
        window: Number of context lines around target_line (default: 30).

    Returns:
        Numbered lines of source code or an error message.
    """
    try:
        return read_file_impl(path, start_line, end_line, target_line, window)
    except Exception as exc:
        logger.error("read_file encountered unexpected error: %s", exc)
        return f"Error: Unexpected failure reading file: {exc}"
