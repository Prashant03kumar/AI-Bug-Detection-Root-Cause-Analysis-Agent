"""Post-hoc validation of agent root-cause reports against repository ground truth."""

import ast
import subprocess
from pathlib import Path
from typing import Optional

from app.config import get_settings
from app.logging_setup import get_logger
from app.models import RootCauseReport

logger = get_logger("agent.validate")


def validate_function_in_ast(file_path: Path, function_name: str) -> bool:
    """Check if function or method exists in Python file AST."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))

        target = function_name.strip()
        if "." in target:
            class_name, method_name = target.split(".", 1)
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
                            return True
            return False

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target:
                return True
            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == target:
                        return True
        return False
    except Exception:
        return False


def validate_commit_in_git(repo_root: Path, commit_hash: str, file_rel: str) -> tuple[bool, str]:
    """Verify that a commit hash exists and modified the specified file."""
    clean_hash = commit_hash.strip()
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--verify", f"{clean_hash}^{{commit}}"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            return False, f"Commit hash '{clean_hash}' does not exist in git history."

        # Verify commit touched the file
        res_files = subprocess.run(
            ["git", "show", "--name-only", "--format=", clean_hash],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        touched = [f.strip().replace("\\", "/") for f in res_files.stdout.splitlines() if f.strip()]
        norm_file = file_rel.replace("\\", "/")
        if norm_file not in touched:
            return True, f"Warning: Commit '{clean_hash[:7]}' exists but touched {touched} rather than '{norm_file}' directly."
        return True, f"Commit '{clean_hash[:7]}' verified in git history."

    except Exception as exc:
        return False, f"Git execution error verifying commit '{clean_hash}': {exc}"


def validate_report(
    report: RootCauseReport,
    repo_path: Optional[Path | str] = None,
) -> RootCauseReport:
    """Validate RootCauseReport against actual repository ground truth.

    Checks:
    1. Offending file exists in target repo.
    2. Line range is within file bounds.
    3. Function/method exists in file AST.
    4. Introducing commit exists in git history.

    Sets report.grounded = True/False and appends notes. Automatically lowers
    confidence if validation fails.
    """
    settings = get_settings()
    repo_root = Path(repo_path or settings.target_repo_path).resolve()

    notes: list[str] = []
    all_passed = True

    # 1. File existence
    target_file = (repo_root / report.file).resolve()
    if not target_file.is_file():
        notes.append(f"Validation Error: File '{report.file}' not found in repository.")
        all_passed = False
        total_lines = 0
    else:
        try:
            with open(target_file, "r", encoding="utf-8") as f:
                total_lines = len(f.readlines())
        except Exception:
            total_lines = 0

    # 2. Line range check
    if target_file.is_file():
        if not (1 <= report.line_start <= report.line_end <= max(total_lines, 1)):
            notes.append(
                f"Validation Error: Line range [{report.line_start}, {report.line_end}] "
                f"is invalid for file with {total_lines} lines."
            )
            all_passed = False
        else:
            notes.append(f"Line range [{report.line_start}, {report.line_end}] verified within bounds ({total_lines} lines).")

    # 3. Function existence
    if target_file.is_file() and report.function:
        if not validate_function_in_ast(target_file, report.function):
            notes.append(
                f"Validation Error: Function '{report.function}' was not found in AST of '{report.file}'."
            )
            all_passed = False
        else:
            notes.append(f"Function '{report.function}' confirmed in AST.")

    # 4. Commit hash check
    if report.introducing_commit and report.introducing_commit.strip():
        commit_valid, commit_msg = validate_commit_in_git(
            repo_root, report.introducing_commit, report.file
        )
        notes.append(commit_msg)
        if not commit_valid:
            all_passed = False
    else:
        notes.append("Introducing commit was not specified.")

    report.grounded = all_passed
    report.validation_notes = notes

    # Automatically lower confidence if validation failed
    if not all_passed:
        original_conf = report.confidence
        report.confidence = min(report.confidence, 0.40)
        report.confidence_reasoning += (
            f" [Automated validation failed grounding checks; confidence adjusted from {original_conf:.2f} to {report.confidence:.2f}]"
        )
        logger.warning(
            "Report grounding validation FAILED. Lowered confidence from %.2f to %.2f. Notes: %s",
            original_conf,
            report.confidence,
            notes,
        )
    else:
        logger.info("Report grounding validation PASSED. Notes: %s", notes)

    return report
