"""Auto-fix patch verification in an isolated temporary repository sandbox."""

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import List, Optional, Tuple

from app.logging_setup import get_logger

logger = get_logger("agent.fix_verifier")


@dataclass
class FixVerificationResult:
    """Outcome of attempting to apply and verify a patch in a temp clone."""

    patch_applied: bool
    fix_verified: bool
    test_output: str
    command_executed: str
    execution_time_seconds: float
    error_message: Optional[str] = None


def extract_diff_patch(text: str) -> Optional[str]:
    """Extract unified diff patch text from code blocks or raw patch strings.

    Args:
        text: Free-form text or suggested fix description.

    Returns:
        Unified diff patch string, or None if no valid diff is found.
    """
    if not text:
        return None

    # 1. Match fenced ```diff ... ``` blocks
    fenced_match = re.search(r"```(?:diff|patch)?\s*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
    if fenced_match:
        candidate = fenced_match.group(1).strip()
        if ("--- " in candidate or "diff --git" in candidate) and "@@ " in candidate:
            return candidate + "\n"

    # 2. Match raw diff starting with 'diff --git' or '--- '
    diff_start = -1
    for marker in ("diff --git ", "--- a/", "--- "):
        pos = text.find(marker)
        if pos != -1 and (diff_start == -1 or pos < diff_start):
            diff_start = pos

    if diff_start != -1:
        candidate = text[diff_start:].strip()
        # Truncate if closing backticks follow
        if "```" in candidate:
            candidate = candidate.split("```")[0].strip()
        if "@@ " in candidate:
            return candidate + "\n"

    return None


def apply_patch_to_repo(repo_dir: Path, patch_content: str) -> Tuple[bool, str]:
    """Apply a unified diff patch to a repository using git apply.

    Args:
        repo_dir: Path to cloned target repository.
        patch_content: Unified diff patch text.

    Returns:
        Tuple of (success, log_message).
    """
    patch_file = repo_dir / "_sleuth_patch.diff"
    patch_file.write_text(patch_content, encoding="utf-8")

    # Strategy 1: standard git apply with whitespace tolerance
    cmd_base = ["git", "apply", "--ignore-whitespace", "--whitespace=nowarn"]
    res = subprocess.run(
        cmd_base + ["_sleuth_patch.diff"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
    )
    if res.returncode == 0:
        patch_file.unlink(missing_ok=True)
        return True, "Patch applied cleanly with git apply."

    # Strategy 2: git apply with -p0 (for non-prefixed paths)
    res_p0 = subprocess.run(
        cmd_base + ["-p0", "_sleuth_patch.diff"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
    )
    if res_p0.returncode == 0:
        patch_file.unlink(missing_ok=True)
        return True, "Patch applied cleanly with git apply -p0."

    # Strategy 3: git apply with -p1
    res_p1 = subprocess.run(
        cmd_base + ["-p1", "_sleuth_patch.diff"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
    )
    if res_p1.returncode == 0:
        patch_file.unlink(missing_ok=True)
        return True, "Patch applied cleanly with git apply -p1."

    patch_file.unlink(missing_ok=True)
    err = res.stderr or res.stdout or res_p1.stderr
    return False, f"git apply failed: {err.strip()}"


def verify_fix_in_temp_repo(
    repo_path: Path | str,
    patch_content: str,
    test_command: Optional[List[str] | str] = None,
    bug_hint: Optional[str] = None,
    timeout_seconds: int = 40,
) -> FixVerificationResult:
    """Copy target repository to isolated temp dir, apply patch, and run test verification.

    Args:
        repo_path: Path to target repository.
        patch_content: Unified diff patch.
        test_command: Optional explicit test command line.
        bug_hint: Optional scenario identifier for scenario runners.
        timeout_seconds: Timeout for test execution.

    Returns:
        FixVerificationResult detailing application and verification state.
    """
    start_time = time.time()
    source_repo = Path(repo_path).resolve()
    if not source_repo.is_dir():
        return FixVerificationResult(
            patch_applied=False,
            fix_verified=False,
            test_output="",
            command_executed="none",
            execution_time_seconds=0.0,
            error_message=f"Target repository not found: {source_repo}",
        )

    # Create isolated temp sandbox
    temp_dir = tempfile.mkdtemp(prefix="bugsleuth_fix_")
    sandbox_repo = Path(temp_dir) / "repo"

    try:
        # Copy repository into temp sandbox
        shutil.copytree(source_repo, sandbox_repo, symlinks=False)

        # Apply patch
        applied, apply_msg = apply_patch_to_repo(sandbox_repo, patch_content)
        if not applied:
            return FixVerificationResult(
                patch_applied=False,
                fix_verified=False,
                test_output=apply_msg,
                command_executed="git apply",
                execution_time_seconds=round(time.time() - start_time, 2),
                error_message=apply_msg,
            )

        # Determine verification command
        exec_cmd: List[str]
        if test_command:
            exec_cmd = test_command if isinstance(test_command, list) else test_command.split()
        elif (sandbox_repo / "run_scenarios.py").is_file() and bug_hint:
            exec_cmd = [sys.executable, "run_scenarios.py", "--bug", bug_hint]
        elif (sandbox_repo / "run_scenarios.py").is_file():
            exec_cmd = [sys.executable, "run_scenarios.py"]
        elif (sandbox_repo / "tests").is_dir():
            exec_cmd = [sys.executable, "-m", "pytest", "tests"]
        else:
            exec_cmd = [sys.executable, "-m", "unittest", "discover"]

        cmd_str = " ".join(exec_cmd)
        logger.info("Executing verification command in sandbox: %s", cmd_str)

        # Run test inside sandbox with timeout and clean environment
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        res = subprocess.run(
            exec_cmd,
            cwd=str(sandbox_repo),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
        )

        test_out = (res.stdout + "\n" + res.stderr).strip()
        elapsed = round(time.time() - start_time, 2)

        # Assess verification outcome
        # If scenario runner output says "[PASS]" or "0/1 failures reproduced", it's verified
        is_verified = False
        if res.returncode == 0:
            is_verified = True
        elif "[PASS]" in test_out and "0/1 failures reproduced" in test_out:
            is_verified = True
        elif "[PASS]" in test_out and "[FAIL]" not in test_out:
            is_verified = True

        return FixVerificationResult(
            patch_applied=True,
            fix_verified=is_verified,
            test_output=test_out[:3000],
            command_executed=cmd_str,
            execution_time_seconds=elapsed,
            error_message=None if is_verified else "Test execution failed or bug still reproduced.",
        )

    except subprocess.TimeoutExpired:
        return FixVerificationResult(
            patch_applied=True,
            fix_verified=False,
            test_output=f"Verification timed out after {timeout_seconds}s",
            command_executed=cmd_str if "cmd_str" in locals() else "unknown",
            execution_time_seconds=round(time.time() - start_time, 2),
            error_message="Execution timeout",
        )
    except Exception as exc:
        return FixVerificationResult(
            patch_applied=False,
            fix_verified=False,
            test_output=str(exc),
            command_executed="unknown",
            execution_time_seconds=round(time.time() - start_time, 2),
            error_message=str(exc),
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
