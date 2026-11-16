"""Comparison utility to benchmark and diff two BugSleuth evaluation results."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def load_result_json(path_str: str) -> Dict[str, Any]:
    p = Path(path_str)
    if not p.is_file():
        raise FileNotFoundError(f"Result file not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def format_delta_pct(val_a: float, val_b: float) -> str:
    diff = (val_b - val_a) * 100
    sign = "+" if diff > 0 else ""
    return f"{sign}{diff:.1f}%"


def format_delta_num(val_a: float, val_b: float, unit: str = "") -> str:
    diff = val_b - val_a
    sign = "+" if diff > 0 else ""
    return f"{sign}{diff:.2f}{unit}"


def compare_runs(path_a: str, path_b: str, md_out: str = None) -> str:
    data_a = load_result_json(path_a)
    data_b = load_result_json(path_b)

    label_a = data_a.get("type", Path(path_a).stem)
    label_b = data_b.get("type", Path(path_b).stem)
    sum_a = data_a.get("summary", {})
    sum_b = data_b.get("summary", {})

    runs_a = {r["bug_id"]: r for r in data_a.get("runs", [])}
    runs_b = {r["bug_id"]: r for r in data_b.get("runs", [])}
    all_bugs = sorted(set(runs_a.keys()) | set(runs_b.keys()))

    lines = []
    lines.append(f"# Evaluation Comparison: `{label_a}` vs `{label_b}`")
    lines.append(f"- **Source A:** `{path_a}`")
    lines.append(f"- **Source B:** `{path_b}`\n")

    lines.append("## 1. Aggregate Benchmark Comparison\n")
    lines.append("| Metric | Source A | Source B | Delta |")
    lines.append("| :--- | :---: | :---: | :---: |")

    metrics_pct = [
        ("File Localization Accuracy", "file_accuracy"),
        ("Function Identification", "function_accuracy"),
        ("Line Range Overlap", "line_overlap_accuracy"),
        ("Introducing Commit Match", "commit_accuracy"),
        ("Bug Type Classification", "bug_type_accuracy"),
        ("Fact Grounding Rate", "grounded_accuracy"),
        ("LLM-Judge Semantic Quality", "avg_semantic_score"),
    ]

    for label, key in metrics_pct:
        v_a = float(sum_a.get(key, 0.0))
        v_b = float(sum_b.get(key, 0.0))
        delta = format_delta_pct(v_a, v_b)
        lines.append(f"| **{label}** | {v_a * 100:.1f}% | {v_b * 100:.1f}% | **{delta}** |")

    # Latency and Steps
    lat_a = float(sum_a.get("avg_latency_sec", 0.0))
    lat_b = float(sum_b.get("avg_latency_sec", 0.0))
    lines.append(f"| **Avg Latency** | {lat_a:.2f}s | {lat_b:.2f}s | {format_delta_num(lat_a, lat_b, 's')} |")

    steps_a = float(sum_a.get("avg_steps", 0.0))
    steps_b = float(sum_b.get("avg_steps", 0.0))
    lines.append(f"| **Avg Steps** | {steps_a:.1f} | {steps_b:.1f} | {format_delta_num(steps_a, steps_b)} |")

    lines.append("\n## 2. Granular Bug-by-Bug Comparison\n")
    lines.append("| Bug ID | File Match (A -> B) | Commit Match (A -> B) | Semantic Score (A -> B) | Status |")
    lines.append("| :--- | :---: | :---: | :---: | :---: |")

    improved = 0
    regressed = 0
    unchanged = 0

    for b in all_bugs:
        r_a = runs_a.get(b, {})
        r_b = runs_b.get(b, {})
        sc_a = r_a.get("scores", {})
        sc_b = r_b.get("scores", {})

        f_a = sc_a.get("file_correct", False)
        f_b = sc_b.get("file_correct", False)
        f_str = f"{'YES' if f_a else 'NO'} -> {'YES' if f_b else 'NO'}"

        c_a = sc_a.get("commit_correct", False)
        c_b = sc_b.get("commit_correct", False)
        c_str = f"{'YES' if c_a else 'NO'} -> {'YES' if c_b else 'NO'}"

        s_a = float(sc_a.get("cause_semantic_score", 0.0))
        s_b = float(sc_b.get("cause_semantic_score", 0.0))
        s_str = f"{s_a:.2f} -> {s_b:.2f}"

        # Status heuristic
        score_diff = (1 if f_b else 0) + (1 if c_b else 0) + s_b - ((1 if f_a else 0) + (1 if c_a else 0) + s_a)
        if score_diff > 0.2:
            status = "**IMPROVED**"
            improved += 1
        elif score_diff < -0.2:
            status = "**REGRESSED**"
            regressed += 1
        else:
            status = "Unchanged"
            unchanged += 1

        lines.append(f"| **{b}** | `{f_str}` | `{c_str}` | `{s_str}` | {status} |")

    lines.append(f"\n**Summary of Deltas:** Improved: `{improved}` | Regressed: `{regressed}` | Unchanged: `{unchanged}`\n")

    report_text = "\n".join(lines)
    if md_out:
        Path(md_out).write_text(report_text, encoding="utf-8")

    return report_text


def main():
    parser = argparse.ArgumentParser(description="Compare two BugSleuth evaluation results")
    parser.add_argument("file_a", type=str, help="Path to first evaluation result JSON (e.g. baseline)")
    parser.add_argument("file_b", type=str, help="Path to second evaluation result JSON (e.g. agent)")
    parser.add_argument("--markdown-out", type=str, default=None, help="Optional output path for markdown comparison")
    args = parser.parse_args()

    try:
        report = compare_runs(args.file_a, args.file_b, args.markdown_out)
        print(report)
        return 0
    except Exception as exc:
        print(f"Error comparing runs: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
