"""Manual investigation toolchain demo for a selected bug scenario."""

import json
import re
import sys
from pathlib import Path

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.tools import git_blame, parse_error, read_file, show_commit_diff

DATA_DIR = PROJECT_ROOT / "data"


def main():
    print("=" * 70)
    print(" BugSleuth Investigation Toolchain Demo (BUG-01)")
    print("=" * 70)

    bug_id = "BUG-01"
    error_file = DATA_DIR / "bugs" / bug_id / "error.txt"
    raw_error = error_file.read_text(encoding="utf-8")

    print("\n--- [Step 1] parse_error tool invocation ---")
    parsed_json = parse_error.invoke({"text": raw_error})
    parsed = json.loads(parsed_json)
    print(f"Error Type  : {parsed['error_type']}")
    print(f"Message     : {parsed['message']}")
    print(f"Crash Frame : {parsed['crash_frame']}")
    print(f"Keywords    : {parsed['candidate_keywords']}")

    crash_frame = parsed["crash_frame"]
    if not crash_frame:
        print("ERROR: No crash frame identified in traceback.")
        return 1

    file_path = crash_frame["file"]
    line_num = crash_frame["line"]

    print(f"\n--- [Step 2] read_file around crash line ({file_path}:{line_num}) ---")
    code_snippet = read_file.invoke({
        "path": file_path,
        "target_line": line_num,
        "window": 6,
    })
    print(code_snippet)

    print(f"\n--- [Step 3] git_blame on crash line {line_num} in {file_path} ---")
    blame_out = git_blame.invoke({
        "file": file_path,
        "start_line": line_num,
        "end_line": line_num,
    })
    print(blame_out)

    # Extract suspect commit hash from blame output
    hash_match = re.search(r"\[([0-9a-f]{7,40})\]", blame_out)
    blamed_hash = hash_match.group(1) if hash_match else "HEAD"

    print(f"\n--- [Step 4] show_commit_diff for introducing commit ({blamed_hash}) ---")
    diff_out = show_commit_diff.invoke({
        "commit_hash": blamed_hash,
        "file": file_path,
    })
    print(diff_out)

    print("\n" + "=" * 70)
    print("Investigation chain completed successfully!")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
