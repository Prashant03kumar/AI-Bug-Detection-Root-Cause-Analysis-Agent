"""Evaluate whether git_blame accurately attributes the introducing commit across all 10 bugs."""

import json
import re
import sys
from pathlib import Path

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.tools import git_blame

GROUND_TRUTH_FILE = PROJECT_ROOT / "eval" / "ground_truth.json"


def main() -> int:
    print("=" * 68)
    print(" BugSleuth Blame Accuracy Verification (Ground Truth vs Git Blame)")
    print("=" * 68)

    if not GROUND_TRUTH_FILE.is_file():
        print(f"ERROR: Ground truth file not found at {GROUND_TRUTH_FILE}")
        return 1

    with open(GROUND_TRUTH_FILE, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    total_bugs = len(ground_truth)
    matched_count = 0

    for bug_id in sorted(ground_truth.keys()):
        gt = ground_truth[bug_id]
        file_path = gt["root_cause_file"]
        func_name = gt["root_cause_function"]
        s_line, e_line = gt["line_range"]
        expected_hash = gt["introducing_commit_hash"]
        short_expected = expected_hash[:7].lower()

        # Execute git_blame tool
        blame_text = git_blame.invoke({
            "file": file_path,
            "start_line": s_line,
            "end_line": e_line,
        })

        # Extract all commit hashes returned by blame
        blamed_hashes = [h.lower() for h in re.findall(r"\[([0-9a-f]{7,40})\]", blame_text)]

        # Check if introducing commit is present in blamed line group
        is_match = any(h.startswith(short_expected) or short_expected.startswith(h) for h in blamed_hashes)

        if is_match:
            matched_count += 1
            status = "MATCH"
            msg = f"Found commit {short_expected} in {file_path}::{func_name} (lines {s_line}-{e_line})"
        else:
            status = "MISS "
            msg = f"Expected {short_expected}, blamed: {blamed_hashes} in {file_path}::{func_name}"

        print(f"  [{status}] {bug_id:7s}: {msg}")

    print("\n" + "=" * 68)
    print(f" Blame Accuracy Score: {matched_count}/{total_bugs} ({matched_count / total_bugs * 100:.1f}%)")
    print("=" * 68)

    if matched_count >= 8:
        print(f"PASS: Blame accuracy {matched_count}/{total_bugs} meets or exceeds required 8/10 threshold!\n")
        return 0
    else:
        print(f"FAIL: Blame accuracy {matched_count}/{total_bugs} is below required threshold (8/10).\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
