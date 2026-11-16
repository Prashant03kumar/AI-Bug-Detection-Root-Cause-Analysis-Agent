"""Verification script for BugSleuth Phase 2 Ground Truth data.

Verifies that for every bug in eval/ground_truth.json:
1. Target file exists in demo_repo.
2. Target function exists in that file.
3. Line range is valid and contained within the file.
4. Introducing commit hash exists in demo_repo git history.
5. Introducing commit actually touched that file.
"""

import ast
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMO_REPO = PROJECT_ROOT / "demo_repo"
EVAL_DIR = PROJECT_ROOT / "eval"
GROUND_TRUTH_FILE = EVAL_DIR / "ground_truth.json"


def function_exists_in_file(filepath: Path, func_name: str) -> bool:
    """Verify function or method definition exists in Python source file via AST."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == func_name:
                    return True
        return False
    except Exception:
        return False


def run_git(args: list[str]) -> tuple[int, str]:
    """Execute git command within demo_repo."""
    res = subprocess.run(
        ["git"] + args,
        cwd=str(DEMO_REPO),
        capture_output=True,
        text=True,
    )
    return res.returncode, res.stdout.strip()


def verify_entry(bug_id: str, data: dict) -> tuple[bool, str]:
    """Validate a single ground truth record."""
    file_rel = data.get("root_cause_file")
    func_name = data.get("root_cause_function")
    line_range = data.get("line_range")
    commit_hash = data.get("introducing_commit_hash")

    if not file_rel or not func_name or not line_range or not commit_hash:
        return False, "Missing required ground truth keys"

    # 1. File exists
    target_file = DEMO_REPO / file_rel
    if not target_file.is_file():
        return False, f"File not found: {file_rel}"

    # 2. Function exists
    if not function_exists_in_file(target_file, func_name):
        return False, f"Function '{func_name}' not found in {file_rel}"

    # 3. Line range validity
    with open(target_file, "r", encoding="utf-8") as f:
        total_lines = len(f.readlines())

    start_line, end_line = line_range
    if not (1 <= start_line <= end_line <= total_lines):
        return False, f"Invalid line range [{start_line}, {end_line}] for {file_rel} ({total_lines} lines)"

    # 4. Commit hash exists in git history
    rc, out = run_git(["rev-parse", "--verify", f"{commit_hash}^{{commit}}"])
    if rc != 0:
        return False, f"Commit hash {commit_hash} does not exist in demo_repo git history"

    # 5. Commit actually touched that file
    rc, touched_out = run_git(["show", "--name-only", "--format=", commit_hash])
    if rc != 0:
        return False, f"Unable to inspect files touched by commit {commit_hash}"

    touched_files = [f.strip().replace("\\", "/") for f in touched_out.splitlines() if f.strip()]
    normalized_target = file_rel.replace("\\", "/")
    if normalized_target not in touched_files:
        return (
            False,
            f"Commit {commit_hash[:7]} touched {touched_files}, which does not include {normalized_target}",
        )

    return True, f"{file_rel}::{func_name} (lines {start_line}-{end_line}, commit {commit_hash[:7]})"


def main() -> int:
    print("=" * 65)
    print(" BugSleuth Phase 2: Ground Truth Verification")
    print("=" * 65)

    if not GROUND_TRUTH_FILE.is_file():
        print(f"FAIL: Ground truth file not found at {GROUND_TRUTH_FILE}")
        return 1

    with open(GROUND_TRUTH_FILE, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    all_passed = True
    print(f"\nVerifying {len(ground_truth)} ground truth entries...\n")

    for bug_id in sorted(ground_truth.keys()):
        data = ground_truth[bug_id]
        passed, msg = verify_entry(bug_id, data)
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {bug_id:7s}: {msg}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 65)
    if all_passed and len(ground_truth) == 10:
        print("PASS: All 10 ground-truth entries verified successfully!")
        print("=" * 65 + "\n")
        return 0
    else:
        print(f"FAIL: Verification failed or unexpected entry count ({len(ground_truth)}/10)")
        print("=" * 65 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
