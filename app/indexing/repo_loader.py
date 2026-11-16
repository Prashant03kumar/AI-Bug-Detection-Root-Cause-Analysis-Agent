"""Utilities for managing user-supplied local and remote git repositories."""

import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlparse

from app.logging_setup import get_logger

logger = get_logger("indexing.repo_loader")


def sanitize_repo_name(url_or_path: str) -> str:
    """Derive a safe folder name from a git URL or path."""
    parsed = urlparse(url_or_path)
    path_part = parsed.path.rstrip("/")
    if path_part.endswith(".git"):
        path_part = path_part[:-4]
    name = Path(path_part).name or "cloned_repo"
    # Ensure safe alphanumeric plus hyphens/underscores
    safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    return safe_name or "target_repo"


def validate_repo_path(path: Path | str) -> Path:
    """Validate that a local repository directory exists and is accessible.

    Args:
        path: Path string or Path object to check.

    Returns:
        Resolved Path object.

    Raises:
        FileNotFoundError: If path does not exist.
        NotADirectoryError: If path is not a directory.
    """
    resolved = Path(path).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Repository directory does not exist: {resolved}")
    if not resolved.is_dir():
        raise NotADirectoryError(f"Repository path is not a directory: {resolved}")
    return resolved


def clone_github_repo(
    repo_url: str,
    workspace_dir: Path | str = "./workspace",
    depth: int = 1,
    timeout_seconds: int = 120,
) -> Path:
    """Safely clone a remote GitHub repository into the local workspace.

    Args:
        repo_url: GitHub HTTPS or SSH URL.
        workspace_dir: Local destination workspace directory.
        depth: Git shallow clone depth (default 1 for speed and safety).
        timeout_seconds: Timeout for git clone subprocess.

    Returns:
        Path to the cloned repository.

    Raises:
        ValueError: If repository URL is invalid or unsafe.
        RuntimeError: If git clone fails.
    """
    clean_url = repo_url.strip()
    # Basic URL security validation to prevent flag injection
    if clean_url.startswith("-") or ";" in clean_url or "&" in clean_url or "|" in clean_url:
        raise ValueError(f"Invalid or unsafe repository URL: '{clean_url}'")

    if not (
        clean_url.startswith("https://")
        or clean_url.startswith("http://")
        or clean_url.startswith("git@")
    ):
        raise ValueError("Repository URL must be a valid HTTPS, HTTP, or SSH Git URL.")

    target_workspace = Path(workspace_dir).resolve()
    target_workspace.mkdir(parents=True, exist_ok=True)

    folder_name = sanitize_repo_name(clean_url)
    dest_path = target_workspace / folder_name

    if dest_path.is_dir():
        logger.info("Repository '%s' already exists at %s. Using existing copy.", folder_name, dest_path)
        return dest_path

    cmd = ["git", "clone", f"--depth={depth}", clean_url, str(dest_path)]
    logger.info("Cloning repository into %s: %s", dest_path, clean_url)

    try:
        env = os.environ.copy()
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
        )
        if res.returncode != 0:
            err_msg = res.stderr.strip() or res.stdout.strip()
            raise RuntimeError(f"git clone failed with code {res.returncode}: {err_msg}")

        logger.info("Successfully cloned repository to %s", dest_path)
        return dest_path

    except subprocess.TimeoutExpired:
        raise RuntimeError(f"git clone timed out after {timeout_seconds} seconds.")
