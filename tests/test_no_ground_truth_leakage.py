"""Test that no ground-truth answers or bug-specific identifiers are leaked into the app/ directory."""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = PROJECT_ROOT / "app"
GROUND_TRUTH_FILE = PROJECT_ROOT / "eval" / "ground_truth.json"


def test_no_ground_truth_leakage():
    """Verify that app/ contains zero hardcoded ground truth commits, summaries, fixes, or bug IDs."""
    assert GROUND_TRUTH_FILE.is_file(), f"Ground truth file missing: {GROUND_TRUTH_FILE}"
    gt_data = json.loads(GROUND_TRUTH_FILE.read_text(encoding="utf-8"))

    # Collect forbidden tokens
    forbidden_tokens = set()
    for bug_id, bug_info in gt_data.items():
        # Bug ID
        forbidden_tokens.add(bug_id.upper())
        forbidden_tokens.add(bug_id.lower())
        # Commit hash and short hash
        commit = bug_info.get("introducing_commit_hash", "")
        if commit:
            forbidden_tokens.add(commit.lower())
            forbidden_tokens.add(commit[:7].lower())
        # Substantive summary fragments (> 20 chars)
        summary = bug_info.get("root_cause_summary", "")
        if len(summary) > 20:
            forbidden_tokens.add(summary.strip())
        # Fix description
        fix = bug_info.get("fix_description", "")
        if len(fix) > 20:
            forbidden_tokens.add(fix.strip())

    # Scan all Python files in app/
    app_py_files = list(APP_DIR.rglob("*.py"))
    assert len(app_py_files) > 0, "No python files found in app/"

    leaks = []
    for py_file in app_py_files:
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        content_lower = content.lower()
        for token in forbidden_tokens:
            if token.lower() in content_lower:
                leaks.append(f"{py_file.relative_to(PROJECT_ROOT)}: contains forbidden ground-truth token '{token[:30]}...'")

    assert not leaks, f"Found ground truth leaks in app/ code:\n" + "\n".join(leaks)
