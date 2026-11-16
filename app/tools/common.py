"""Common utilities, path sandboxing, and output formatting for investigation tools."""

import os
from pathlib import Path
from typing import Optional, Tuple

from app.config import get_settings
from app.logging_setup import get_logger

logger = get_logger("tools.common")

MAX_OUTPUT_CHARS: int = 3000


def truncate_output(text: str, max_chars: int = MAX_OUTPUT_CHARS) -> str:
    """Cap output string to prevent context explosion, appending a truncation marker."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars].rstrip()
    return f"{truncated}\n\n... [truncated - output exceeded {max_chars} chars]"


def resolve_sandboxed_path(
    file_path: str | Path,
    repo_path: Optional[str | Path] = None,
) -> Tuple[Path, str]:
    """Resolve and sandbox a file path strictly within the target repository boundary.

    Args:
        file_path: Relative or absolute path to a file.
        repo_path: Optional repository root path (defaults to settings.target_repo_path).

    Returns:
        Tuple of (resolved_absolute_path, relative_posix_path).

    Raises:
        PermissionError: If path escapes the repository boundary (e.g. via ../ traversal).
        FileNotFoundError: If the target file does not exist.
    """
    settings = get_settings()
    repo_root = Path(repo_path or settings.target_repo_path).resolve()

    raw_path_str = str(file_path).strip()
    # Normalize path
    target = Path(raw_path_str)
    if not target.is_absolute():
        resolved = (repo_root / target).resolve()
    else:
        resolved = target.resolve()

    # Sandboxing security check: target must be inside repo_root
    try:
        rel_posix = resolved.relative_to(repo_root).as_posix()
    except ValueError:
        msg = f"Security Error: Access denied. Path '{file_path}' escapes the repository root sandbox '{repo_root}'."
        logger.warning(msg)
        raise PermissionError(msg)

    if not resolved.is_file():
        msg = f"File not found: '{file_path}' (resolved: '{resolved}')."
        logger.warning(msg)
        raise FileNotFoundError(msg)

    return resolved, rel_posix
