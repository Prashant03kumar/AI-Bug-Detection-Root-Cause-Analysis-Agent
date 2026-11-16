"""Baseline experiment: Evaluate raw Gemini performance without tools or RAG."""

import argparse
import datetime
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.llm import get_llm
from app.logging_setup import get_logger
from app.models import RootCauseReport
from eval.metrics import evaluate_report
from eval.run_eval import compute_aggregate_metrics, estimate_tokens, normalize_bug_id, render_markdown_report

logger = get_logger("eval.baseline")

DATA_BUGS_DIR = PROJECT_ROOT / "data" / "bugs"
GROUND_TRUTH_PATH = PROJECT_ROOT / "eval" / "ground_truth.json"
RESULTS_DIR = PROJECT_ROOT / "eval" / "results"

BASELINE_SYSTEM_PROMPT = """You are an AI code debugging assistant.
You are given ONLY the raw error message, stack trace, or symptom description of a bug in an e-commerce application.
You do NOT have access to any external tools, file reading, code search, git repositories, or logs.

Based solely on your general knowledge and the provided error text, deduce:
1. The likely root cause
2. The offending file and function
3. The estimated line range
4. The likely introducing commit hash (if discernible from traceback, else leave null)
5. The bug type category
6. A proposed fix
7. Your confidence score (0.0 - 1.0) and reasoning

Be honest and calibrated: if you cannot determine the file or root cause with certainty, state so and lower your confidence score.
"""


def run_single_baseline(bug_id: str, gt_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Execute raw Gemini model without tools or RAG on a single bug."""
    norm_id = normalize_bug_id(bug_id)
    error_file = DATA_BUGS_DIR / norm_id / "error.txt"

    if not error_file.is_file():
        raise FileNotFoundError(f"Error file missing for {norm_id} at {error_file}")

    error_text = error_file.read_text(encoding="utf-8")
    start_time = time.time()
    error_msg = None
    report: Optional[RootCauseReport] = None

    try:
        llm = get_llm(temperature=0.1)
        structured_llm = llm.with_structured_output(RootCauseReport)
        prompt = f"{BASELINE_SYSTEM_PROMPT}\n\nERROR INPUT:\n{error_text}"
        res = structured_llm.invoke(prompt)
        if isinstance(res, RootCauseReport):
            report = res
        elif isinstance(res, dict):
            report = RootCauseReport(**res)
        else:
            raise ValueError(f"Unexpected baseline response type: {type(res)}")
    except Exception as exc:
        logger.exception("Baseline inference failed for %s: %s", norm_id, exc)
        error_msg = str(exc)

    elapsed_time = round(time.time() - start_time, 2)

    if report is None:
        report = RootCauseReport(
            summary=f"Baseline failed to diagnose: {error_msg}",
            root_cause="Baseline execution error",
            bug_type="unknown",
            file="unknown",
            function="unknown",
            line_start=0,
            line_end=0,
            confidence=0.0,
            confidence_reasoning="Model call failed.",
            steps_taken=["raw_prompt_without_tools"],
            open_questions=[error_msg or "Unknown error"],
            grounded=False,
            validation_notes=["Baseline executed without tool grounding."],
        )
    else:
        # Baseline has no tool grounding validation, mark as ungrounded by definition
        report.grounded = False
        report.validation_notes = ["Baseline prediction generated purely without tool or repository grounding."]

    total_text = error_text + report.summary + report.root_cause
    tokens_used = estimate_tokens(total_text)

    scores = evaluate_report(report, gt_entry)

    return {
        "bug_id": norm_id,
        "latency_sec": elapsed_time,
        "steps_used": 1,
        "tokens_used": tokens_used,
        "error": error_msg,
        "report": report.model_dump(),
        "scores": scores,
    }


def main():
    parser = argparse.ArgumentParser(description="BugSleuth Baseline Evaluation (No RAG / No Tools)")
    parser.add_argument("--bugs", type=str, default="all", help="Comma-separated bug IDs or 'all'")
    parser.add_argument("--runs", type=int, default=1, help="Repetitions per bug (default: 1)")
    parser.add_argument("--output-dir", type=str, default=str(RESULTS_DIR), help="Output directory")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not GROUND_TRUTH_PATH.is_file():
        print(f"Error: Ground truth file missing at {GROUND_TRUTH_PATH}", file=sys.stderr)
        return 1

    gt_data = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))

    if args.bugs.lower() == "all":
        target_ids = sorted(gt_data.keys())
    else:
        target_ids = [normalize_bug_id(b.strip()) for b in args.bugs.split(",") if b.strip()]

    print("=" * 70)
    print(" BugSleuth Baseline Experiment: No Tools / No RAG")
    print("=" * 70)
    print(f"Evaluating {len(target_ids)} bug scenario(s): {', '.join(target_ids)}\n")

    all_runs: List[Dict[str, Any]] = []

    for bug_id in target_ids:
        if bug_id not in gt_data:
            continue
        print(f"Running baseline on {bug_id}...", end=" ", flush=True)
        run_res = run_single_baseline(bug_id, gt_data[bug_id])
        all_runs.append(run_res)

        sc = run_res["scores"]
        lat = run_res["latency_sec"]
        status = "OK" if sc["file_correct"] and sc["cause_semantic_score"] >= 0.7 else "FAIL"
        print(f"[{status}] ({lat}s) -> File: {sc['file_correct']} | Commit: {sc['commit_correct']} | Semantic: {sc['cause_semantic_score']:.2f}")

        time.sleep(1.5)

    summary = compute_aggregate_metrics(all_runs)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"baseline_{timestamp}.json"
    latest_json_path = out_dir / "baseline_latest.json"
    md_path = out_dir / f"baseline_{timestamp}.md"
    latest_md_path = out_dir / "baseline_latest.md"

    payload = {
        "timestamp": timestamp,
        "type": "baseline_no_rag",
        "summary": summary,
        "runs": all_runs,
    }

    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    latest_json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md_content = render_markdown_report(summary, all_runs, title="BugSleuth Baseline Evaluation (No RAG / No Tools)")
    md_path.write_text(md_content, encoding="utf-8")
    latest_md_path.write_text(md_content, encoding="utf-8")

    print("\n" + "=" * 70)
    print(" BASELINE EVALUATION SUMMARY")
    print("=" * 70)
    print(f"File Localization Accuracy : {summary.get('file_accuracy', 0.0) * 100:.1f}%")
    print(f"Function Accuracy          : {summary.get('function_accuracy', 0.0) * 100:.1f}%")
    print(f"Introducing Commit Accuracy: {summary.get('commit_accuracy', 0.0) * 100:.1f}%")
    print(f"Average Semantic Score     : {summary.get('avg_semantic_score', 0.0) * 100:.1f}%")
    print(f"Fact Grounding Rate        : {summary.get('grounded_accuracy', 0.0) * 100:.1f}%")
    print(f"Average Latency            : {summary.get('avg_latency_sec', 0.0)}s")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
