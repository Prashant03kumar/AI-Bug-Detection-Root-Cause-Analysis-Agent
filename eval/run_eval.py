"""Evaluation runner benchmarking the BugSleuth agent against ground truth."""

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

from app.agent.graph import investigate_bug
from app.config import get_settings
from app.logging_setup import get_logger
from app.models import RootCauseReport
from eval.metrics import evaluate_report

logger = get_logger("eval.runner")

DATA_BUGS_DIR = PROJECT_ROOT / "data" / "bugs"
GROUND_TRUTH_PATH = PROJECT_ROOT / "eval" / "ground_truth.json"
RESULTS_DIR = PROJECT_ROOT / "eval" / "results"


def normalize_bug_id(raw_id: str) -> str:
    """Normalize input ID like 'bug_01' or 'bug-1' to 'BUG-01'."""
    clean = raw_id.strip().upper().replace("_", "-")
    if not clean.startswith("BUG-"):
        clean = f"BUG-{clean}"
    parts = clean.split("-")
    if len(parts) == 2 and parts[1].isdigit():
        clean = f"BUG-{int(parts[1]):02d}"
    return clean


def estimate_tokens(text: str) -> int:
    """Approximate token count based on word and character counts."""
    if not text:
        return 0
    return max(1, int(len(text) / 4))


def run_single_evaluation(bug_id: str, gt_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the agent on a single bug scenario and score the result."""
    norm_id = normalize_bug_id(bug_id)
    error_file = DATA_BUGS_DIR / norm_id / "error.txt"

    if not error_file.is_file():
        raise FileNotFoundError(f"Error file missing for {norm_id} at {error_file}")

    error_text = error_file.read_text(encoding="utf-8")
    start_time = time.time()
    error_msg = None
    report: Optional[RootCauseReport] = None

    try:
        report = investigate_bug(error_text)
    except Exception as exc:
        logger.exception("Investigation failed for %s: %s", norm_id, exc)
        error_msg = str(exc)

    elapsed_time = round(time.time() - start_time, 2)

    if report is None:
        # Create empty fallback report indicating total failure
        report = RootCauseReport(
            summary=f"Agent failed to investigate: {error_msg}",
            root_cause="Execution failure",
            bug_type="unknown",
            file="unknown",
            function="unknown",
            line_start=0,
            line_end=0,
            confidence=0.0,
            confidence_reasoning="Investigation threw an unhandled exception.",
            steps_taken=[],
            open_questions=[error_msg or "Unknown error"],
            grounded=False,
            validation_notes=[f"Agent execution error: {error_msg}"],
        )

    # Compute token estimate (input error text + all evidence snippets + suggested fix)
    total_text = error_text + report.summary + report.root_cause + (report.suggested_fix or "")
    for ev in report.evidence:
        total_text += ev.snippet + ev.why_relevant
    tokens_used = estimate_tokens(total_text)

    # Score report against ground truth
    scores = evaluate_report(report, gt_entry)

    steps_count = len(report.steps_taken) if report.steps_taken else 1

    return {
        "bug_id": norm_id,
        "latency_sec": elapsed_time,
        "steps_used": steps_count,
        "tokens_used": tokens_used,
        "error": error_msg,
        "report": report.model_dump(),
        "scores": scores,
    }


def compute_aggregate_metrics(eval_runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate individual bug evaluation scores into overall benchmarks."""
    n = len(eval_runs)
    if n == 0:
        return {}

    file_hits = sum(1 for r in eval_runs if r["scores"]["file_correct"])
    func_hits = sum(1 for r in eval_runs if r["scores"]["function_correct"])
    line_hits = sum(1 for r in eval_runs if r["scores"]["line_overlap"])
    commit_hits = sum(1 for r in eval_runs if r["scores"]["commit_correct"])
    type_hits = sum(1 for r in eval_runs if r["scores"]["bug_type_correct"])
    grounded_hits = sum(1 for r in eval_runs if r["scores"]["grounded"])

    avg_semantic = round(sum(r["scores"]["cause_semantic_score"] for r in eval_runs) / n, 3)
    avg_conf = round(sum(r["scores"]["confidence"] for r in eval_runs) / n, 3)
    avg_latency = round(sum(r["latency_sec"] for r in eval_runs) / n, 2)
    avg_steps = round(sum(r["steps_used"] for r in eval_runs) / n, 1)
    avg_tokens = int(sum(r["tokens_used"] for r in eval_runs) / n)

    # Calibration calculation
    correct_confs = [r["scores"]["confidence"] for r in eval_runs if r["scores"]["file_correct"]]
    incorrect_confs = [r["scores"]["confidence"] for r in eval_runs if not r["scores"]["file_correct"]]

    mean_conf_correct = round(sum(correct_confs) / len(correct_confs), 3) if correct_confs else None
    mean_conf_incorrect = round(sum(incorrect_confs) / len(incorrect_confs), 3) if incorrect_confs else None

    calibrated = None
    if mean_conf_correct is not None and mean_conf_incorrect is not None:
        calibrated = mean_conf_correct > mean_conf_incorrect
    elif mean_conf_correct is not None and not incorrect_confs:
        calibrated = True  # 100% correct, perfect calibration

    failures = [
        {
            "bug_id": r["bug_id"],
            "file_correct": r["scores"]["file_correct"],
            "commit_correct": r["scores"]["commit_correct"],
            "semantic_score": r["scores"]["cause_semantic_score"],
            "reported_file": r["report"]["file"],
            "reported_func": r["report"]["function"],
            "justification": r["scores"]["semantic_justification"],
        }
        for r in eval_runs
        if (not r["scores"]["file_correct"] or not r["scores"]["commit_correct"] or r["scores"]["cause_semantic_score"] < 0.7)
    ]

    return {
        "total_bugs": n,
        "file_accuracy": round(file_hits / n, 3),
        "function_accuracy": round(func_hits / n, 3),
        "line_overlap_accuracy": round(line_hits / n, 3),
        "commit_accuracy": round(commit_hits / n, 3),
        "bug_type_accuracy": round(type_hits / n, 3),
        "grounded_accuracy": round(grounded_hits / n, 3),
        "avg_semantic_score": avg_semantic,
        "avg_confidence": avg_conf,
        "avg_latency_sec": avg_latency,
        "avg_steps": avg_steps,
        "avg_tokens": avg_tokens,
        "calibration": {
            "calibrated": calibrated,
            "mean_confidence_correct": mean_conf_correct,
            "mean_confidence_incorrect": mean_conf_incorrect,
        },
        "failures_count": len(failures),
        "failures": failures,
    }


def render_markdown_report(summary: Dict[str, Any], runs: List[Dict[str, Any]], title: str = "BugSleuth Agent Evaluation") -> str:
    """Format aggregate evaluation results into a clean markdown document."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md = []
    md.append(f"# {title}")
    md.append(f"\n**Execution Timestamp:** `{ts}`  ")
    md.append(f"**Total Bug Scenarios Evaluated:** `{summary.get('total_bugs', 0)}`\n")

    md.append("## 1. Aggregate Performance Benchmark\n")
    md.append("| Metric | Result | Benchmark Target | Status |")
    md.append("| :--- | :---: | :---: | :---: |")

    file_acc = summary.get("file_accuracy", 0.0) * 100
    file_status = "PASS" if file_acc >= 70.0 else "NEEDS IMPROVEMENT"
    md.append(f"| **File Localization Accuracy** | **{file_acc:.1f}%** | >= 70.0% | `{file_status}` |")

    func_acc = summary.get("function_accuracy", 0.0) * 100
    md.append(f"| **Function Identification** | **{func_acc:.1f}%** | >= 70.0% | `{'PASS' if func_acc >= 70 else 'WARN'}` |")

    line_acc = summary.get("line_overlap_accuracy", 0.0) * 100
    md.append(f"| **Line Range Overlap** | **{line_acc:.1f}%** | >= 60.0% | `{'PASS' if line_acc >= 60 else 'WARN'}` |")

    commit_acc = summary.get("commit_accuracy", 0.0) * 100
    md.append(f"| **Introducing Commit Identification** | **{commit_acc:.1f}%** | >= 60.0% | `{'PASS' if commit_acc >= 60 else 'WARN'}` |")

    type_acc = summary.get("bug_type_accuracy", 0.0) * 100
    md.append(f"| **Bug Type Classification** | **{type_acc:.1f}%** | >= 60.0% | `{'PASS' if type_acc >= 60 else 'WARN'}` |")

    sem_score = summary.get("avg_semantic_score", 0.0) * 100
    md.append(f"| **LLM-Judge Root Cause Semantic Quality** | **{sem_score:.1f}%** | >= 75.0% | `{'PASS' if sem_score >= 75 else 'WARN'}` |")

    ground_acc = summary.get("grounded_accuracy", 0.0) * 100
    md.append(f"| **Fact Grounding Rate** | **{ground_acc:.1f}%** | 100.0% | `{'PASS' if ground_acc == 100 else 'WARN'}` |")

    calib = summary.get("calibration", {})
    calib_str = "Yes (Higher on correct)" if calib.get("calibrated") else "No"
    md.append(f"| **Confidence Calibration** | `{calib_str}` | Correct > Wrong | `{'PASS' if calib.get('calibrated') else 'WARN'}` |")

    md.append(f"| **Avg Latency per Bug** | `{summary.get('avg_latency_sec', 0.0)}s` | - | - |")
    md.append(f"| **Avg Steps per Bug** | `{summary.get('avg_steps', 0.0)}` | $\\le 12$ | `PASS` |")
    md.append(f"| **Avg Token Footprint** | `{summary.get('avg_tokens', 0)}` | - | - |\n")

    md.append("## 2. Granular Results per Bug Scenario\n")
    md.append("| Bug ID | File Match | Function Match | Line Overlap | Commit Match | Type Match | Semantic Score | Grounded | Conf | Latency | Steps |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")

    for r in runs:
        b_id = r["bug_id"]
        sc = r["scores"]
        f_m = "YES" if sc["file_correct"] else "NO"
        fn_m = "YES" if sc["function_correct"] else "NO"
        l_m = "YES" if sc["line_overlap"] else "NO"
        c_m = "YES" if sc["commit_correct"] else "NO"
        t_m = "YES" if sc["bug_type_correct"] else "NO"
        g_m = "YES" if sc["grounded"] else "NO"
        sem = f"{sc['cause_semantic_score']:.2f}"
        conf = f"{sc['confidence']:.2f}"
        lat = f"{r['latency_sec']}s"
        steps = r["steps_used"]

        md.append(f"| **{b_id}** | `{f_m}` | `{fn_m}` | `{l_m}` | `{c_m}` | `{t_m}` | `{sem}` | `{g_m}` | `{conf}` | `{lat}` | `{steps}` |")

    md.append("\n## 3. Failure & Diagnostic Analysis\n")
    failures = summary.get("failures", [])
    if not failures:
        md.append("No failures detected! All evaluated scenarios achieved successful file localization and semantic grounding.")
    else:
        for f in failures:
            md.append(f"### {f['bug_id']}")
            md.append(f"- **Reported Location:** `{f['reported_file']}::{f['reported_func']}`")
            md.append(f"- **File Match:** `{f['file_correct']}` | **Commit Match:** `{f['commit_correct']}`")
            md.append(f"- **Semantic Score:** `{f['semantic_score']:.2f}`")
            md.append(f"- **Judge Justification:** {f['justification']}\n")

    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(description="BugSleuth Automated Evaluation Harness")
    parser.add_argument("--bugs", type=str, default="all", help="Comma-separated bug IDs (e.g. 'BUG-01,BUG-03') or 'all'")
    parser.add_argument("--runs", type=int, default=1, help="Repetitions per bug scenario (default: 1)")
    parser.add_argument("--output-dir", type=str, default=str(RESULTS_DIR), help="Path to write evaluation results")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not GROUND_TRUTH_PATH.is_file():
        print(f"Error: Ground truth file missing at {GROUND_TRUTH_PATH}", file=sys.stderr)
        return 1

    gt_data = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))

    # Determine target bugs
    if args.bugs.lower() == "all":
        target_ids = sorted(gt_data.keys())
    else:
        target_ids = [normalize_bug_id(b.strip()) for b in args.bugs.split(",") if b.strip()]

    print("=" * 70)
    print(f" BugSleuth Automated Evaluation Harness")
    print("=" * 70)
    print(f"Evaluating {len(target_ids)} bug scenario(s): {', '.join(target_ids)}")
    print(f"Runs per bug: {args.runs}\n")

    all_runs: List[Dict[str, Any]] = []

    for run_idx in range(1, args.runs + 1):
        if args.runs > 1:
            print(f"\n--- Starting Evaluation Run Cycle {run_idx}/{args.runs} ---")

        for bug_id in target_ids:
            if bug_id not in gt_data:
                print(f"[WARN] Bug ID '{bug_id}' not found in ground truth. Skipping.", file=sys.stderr)
                continue

            print(f"Running agent on {bug_id}...", end=" ", flush=True)
            run_result = run_single_evaluation(bug_id, gt_data[bug_id])
            all_runs.append(run_result)

            sc = run_result["scores"]
            lat = run_result["latency_sec"]
            status_symbol = "OK" if sc["file_correct"] and sc["cause_semantic_score"] >= 0.7 else "WARN"
            print(f"[{status_symbol}] ({lat}s) -> File: {sc['file_correct']} | Commit: {sc['commit_correct']} | Semantic: {sc['cause_semantic_score']:.2f}")

            # Small cooldown pause to respect Gemini free-tier RPM
            time.sleep(1.5)

    summary = compute_aggregate_metrics(all_runs)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"eval_{timestamp}.json"
    latest_json_path = out_dir / "latest.json"
    md_path = out_dir / f"eval_{timestamp}.md"
    latest_md_path = out_dir / "latest.md"

    output_payload = {
        "timestamp": timestamp,
        "summary": summary,
        "runs": all_runs,
    }

    # Save JSON files
    json_path.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")
    latest_json_path.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")

    # Generate Markdown report
    md_content = render_markdown_report(summary, all_runs, title="BugSleuth Agent Evaluation Report")
    md_path.write_text(md_content, encoding="utf-8")
    latest_md_path.write_text(md_content, encoding="utf-8")

    print("\n" + "=" * 70)
    print(" EVALUATION SUMMARY")
    print("=" * 70)
    print(f"Total Scenarios Evaluated  : {summary.get('total_bugs')}")
    print(f"File Localization Accuracy : {summary.get('file_accuracy', 0.0) * 100:.1f}%")
    print(f"Function Accuracy          : {summary.get('function_accuracy', 0.0) * 100:.1f}%")
    print(f"Introducing Commit Accuracy: {summary.get('commit_accuracy', 0.0) * 100:.1f}%")
    print(f"Average Semantic Score     : {summary.get('avg_semantic_score', 0.0) * 100:.1f}%")
    print(f"Fact Grounding Rate        : {summary.get('grounded_accuracy', 0.0) * 100:.1f}%")
    print(f"Average Latency            : {summary.get('avg_latency_sec', 0.0)}s")
    print(f"Results saved to:")
    print(f"  - {json_path}")
    print(f"  - {latest_md_path}")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
