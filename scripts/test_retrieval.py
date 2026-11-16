"""Verification script testing retrieval hit rate for all 10 bug scenarios."""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.indexing.retriever import search_code_chunks

DATA_DIR = PROJECT_ROOT / "data"
EVAL_DIR = PROJECT_ROOT / "eval"
GROUND_TRUTH_FILE = EVAL_DIR / "ground_truth.json"


def construct_search_query(raw_error_text: str) -> str:
    """Preprocess error text and stack traces into an optimized retrieval query."""
    lines = raw_error_text.strip().splitlines()

    # Extract function names from traceback frames: in <function_name>
    functions_in_trace = re.findall(r"in\s+([A-Za-z_][A-Za-z0-9_]*)", raw_error_text)
    # Ignore runner wrapper functions
    ignored_funcs = {"scenario_bug_01", "scenario_bug_02", "scenario_bug_03", "scenario_bug_04",
                     "scenario_bug_05", "scenario_bug_06", "scenario_bug_07", "scenario_bug_08",
                     "scenario_bug_09", "scenario_bug_10", "main", "<module>"}
    filtered_funcs = [fn for fn in functions_in_trace if fn not in ignored_funcs]

    # Extract python file paths mentioned
    file_matches = re.findall(r"([A-Za-z0-9_./\\-]+\.py)", raw_error_text)
    filtered_files = [
        Path(f).name for f in file_matches if "run_scenarios" not in f
    ]

    # Extract exception or error message line
    error_summary_lines = []
    for line in lines:
        cleaned = line.strip()
        if any(keyword in cleaned for keyword in ["Error:", "Exception:", "[ERROR]", "Traceback", "Mismatch", "Leak", "Anomaly", "Rejection"]):
            # Strip timestamp and logger prefix if present
            cleaned_line = re.sub(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+\[\w+\]\s+\[.*?\]\s+", "", cleaned)
            error_summary_lines.append(cleaned_line)

    query_tokens = []
    if filtered_funcs:
        # Prioritize innermost function in stack
        query_tokens.extend(filtered_funcs)
    if filtered_files:
        query_tokens.extend(set(filtered_files))
    if error_summary_lines:
        query_tokens.append(" ".join(error_summary_lines))

    if not query_tokens:
        return raw_error_text[:200]

    return " ".join(query_tokens)


def evaluate_retrieval() -> Tuple[int, int, List[Dict[str, str]]]:
    """Evaluate retrieval accuracy against all 10 ground truth entries."""
    if not GROUND_TRUTH_FILE.is_file():
        raise FileNotFoundError(f"Ground truth file not found at: {GROUND_TRUTH_FILE}")

    with open(GROUND_TRUTH_FILE, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    total_bugs = len(ground_truth)
    hits = 0
    details: List[Dict[str, str]] = []

    print("=" * 65)
    print(f" Testing Retrieval Accuracy on {total_bugs} Bug Scenarios (Top-5)")
    print("=" * 65)

    for bug_id in sorted(ground_truth.keys()):
        gt = ground_truth[bug_id]
        expected_file = gt["root_cause_file"].replace("\\", "/")
        expected_func = gt["root_cause_function"]

        error_file = DATA_DIR / "bugs" / bug_id / "error.txt"
        if not error_file.is_file():
            print(f"  [MISS] {bug_id}: error.txt not found")
            details.append({"bug_id": bug_id, "status": "MISS", "rank": "N/A", "reason": "Missing error.txt"})
            continue

        raw_error = error_file.read_text(encoding="utf-8")
        query = construct_search_query(raw_error)

        top_chunks = search_code_chunks(query=query, k=5)

        # Check if expected file and function are present in top_chunks
        found_rank = None
        for rank, chunk in enumerate(top_chunks, start=1):
            chunk_file_norm = chunk["file_path"].replace("\\", "/")
            chunk_symbol = chunk["symbol_name"]

            # Match on file and function name
            if chunk_file_norm == expected_file:
                if chunk_symbol == expected_func or chunk_symbol.endswith(f".{expected_func}"):
                    found_rank = rank
                    break

        if found_rank is not None:
            hits += 1
            status = "HIT"
            msg = f"Rank {found_rank} -> {expected_file}::{expected_func}"
        else:
            status = "MISS"
            top_found = [f"{c['file_path']}::{c['symbol_name']}" for c in top_chunks[:2]]
            msg = f"Expected {expected_file}::{expected_func} | Top returned: {top_found}"

        print(f"  [{status}] {bug_id:7s}: {msg}")
        details.append({
            "bug_id": bug_id,
            "status": status,
            "rank": str(found_rank) if found_rank else "None",
            "target": f"{expected_file}::{expected_func}",
        })

    return hits, total_bugs, details


def main() -> int:
    try:
        hits, total, _ = evaluate_retrieval()
        rate = (hits / total) * 100 if total > 0 else 0.0
        print("\n" + "=" * 65)
        print(f" Retrieval Evaluation Summary: {hits}/{total} Hits ({rate:.1f}%)")
        print("=" * 65)

        if hits >= 7:
            print(f"PASS: Hit rate {hits}/{total} exceeds the >= 7/10 requirement!\n")
            return 0
        else:
            print(f"FAIL: Hit rate {hits}/{total} is below required threshold (>= 7/10).\n")
            return 1
    except Exception as exc:
        print(f"\nERROR: Retrieval evaluation failed: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
