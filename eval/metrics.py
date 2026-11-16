"""Evaluation metrics and LLM-judge scoring utilities for BugSleuth."""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.llm import get_llm
from app.logging_setup import get_logger
from app.models import RootCauseReport

logger = get_logger("eval.metrics")

JUDGE_PROMPT_TEMPLATE = """You are a strict senior software engineering judge evaluating an AI agent's root cause analysis.

GROUND TRUTH ROOT CAUSE:
{ground_truth}

AGENT'S REPORTED ROOT CAUSE:
{agent_cause}

TASK:
Compare the agent's reported root cause to the ground truth root cause.
Assess whether the agent identified the EXACT underlying failure mechanism, or merely a superficial symptom, or was incorrect.

SCORING CRITERIA (Strict):
- 1.0: Exact match. The agent accurately identified the root cause mechanism, the failure trigger, and the specific flawed logic.
- 0.8: Strong match. The agent identified the correct root cause mechanism with minor differences in wording or focus.
- 0.5: Partial match. The agent identified the affected subsystem or symptom, but misidentified or omitted the exact mechanism.
- 0.2: Weak match. Tangentially relevant or primarily describes symptoms without the root cause.
- 0.0: Incorrect, fabricated, or entirely ungrounded.

Respond ONLY with valid JSON in the exact format below, with no markdown code fences:
{{"score": <number between 0.0 and 1.0>, "justification": "<one concise sentence explaining the score>"}}
"""


def normalize_path(path_str: Optional[str]) -> str:
    """Normalize file path for uniform comparison (e.g. forward slashes, strip leading demo_repo/)."""
    if not path_str:
        return ""
    clean = str(path_str).replace("\\", "/").strip().lstrip("./")
    if clean.startswith("demo_repo/"):
        clean = clean[len("demo_repo/"):]
    return clean


def normalize_function(func_str: Optional[str]) -> str:
    """Normalize function or method name (e.g. remove ClassName. prefix if comparing method)."""
    if not func_str:
        return ""
    clean = str(func_str).strip()
    if "." in clean:
        clean = clean.split(".")[-1]
    return clean


def check_file_correct(reported_file: Optional[str], gt_file: str) -> bool:
    """Check if reported file matches ground truth file."""
    rf = normalize_path(reported_file)
    gf = normalize_path(gt_file)
    if not rf or not gf:
        return False
    return rf == gf or rf.endswith(gf) or gf.endswith(rf)


def check_function_correct(reported_func: Optional[str], gt_func: str) -> bool:
    """Check if reported function matches ground truth function."""
    rf = normalize_function(reported_func)
    gf = normalize_function(gt_func)
    if not rf or not gf:
        return False
    return rf.lower() == gf.lower()


def check_line_overlap(line_start: Optional[int], line_end: Optional[int], gt_range: List[int]) -> bool:
    """Check if reported [line_start, line_end] overlaps with ground truth [gt_start, gt_end]."""
    if line_start is None or line_end is None or not gt_range or len(gt_range) < 2:
        return False
    gt_start, gt_end = gt_range[0], gt_range[1]
    # Ensure start <= end
    r_start, r_end = min(line_start, line_end), max(line_start, line_end)
    g_start, g_end = min(gt_start, gt_end), max(gt_start, gt_end)
    return max(r_start, g_start) <= min(r_end, g_end)


def check_commit_correct(reported_commit: Optional[str], gt_commit: str) -> bool:
    """Check if reported commit hash matches ground truth commit hash (full or prefix)."""
    if not reported_commit or not gt_commit:
        return False
    rc = str(reported_commit).strip().lower()
    gc = str(gt_commit).strip().lower()
    # Accept 7+ prefix or full match
    if rc == gc:
        return True
    if len(rc) >= 7 and gc.startswith(rc):
        return True
    if len(gc) >= 7 and rc.startswith(gc):
        return True
    return False


def check_bug_type_correct(reported_type: Optional[str], gt_type: str) -> bool:
    """Check if reported bug type category matches ground truth."""
    if not reported_type or not gt_type:
        return False
    rt = str(reported_type).strip().lower().replace("-", "_").replace(" ", "_")
    gt = str(gt_type).strip().lower().replace("-", "_").replace(" ", "_")
    return rt == gt


def score_root_cause_semantic(reported_cause: str, gt_summary: str) -> Tuple[float, str]:
    """Use Gemini as strict LLM-judge to compare reported root cause with ground truth."""
    if not reported_cause or not reported_cause.strip():
        return 0.0, "Empty root cause provided."

    prompt = JUDGE_PROMPT_TEMPLATE.format(
        ground_truth=gt_summary,
        agent_cause=reported_cause,
    )

    try:
        llm = get_llm(temperature=0.0)
        response = llm.invoke(prompt)
        text = response.content
        if isinstance(text, list):
            text = " ".join(t.get("text", "") if isinstance(t, dict) else str(t) for t in text)
        text = text.strip()

        # Parse JSON from response
        # Clean potential markdown fences
        clean_json = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        clean_json = re.sub(r"\s*```$", "", clean_json, flags=re.MULTILINE).strip()
        parsed = json.loads(clean_json)

        score = float(parsed.get("score", 0.0))
        justification = str(parsed.get("justification", "No justification provided."))
        # Clamp to 0.0 - 1.0
        score = max(0.0, min(1.0, score))
        return score, justification
    except Exception as exc:
        logger.warning("LLM judge evaluation failed (%s). Falling back to basic token overlap.", exc)
        # Fallback heuristic: token set overlap
        gt_words = set(re.findall(r"\w+", gt_summary.lower()))
        rep_words = set(re.findall(r"\w+", reported_cause.lower()))
        overlap = len(gt_words & rep_words) / max(len(gt_words), 1)
        return round(overlap, 2), f"Fallback token overlap ({round(overlap, 2)}): {exc}"


def evaluate_report(report: RootCauseReport, gt: Dict[str, Any]) -> Dict[str, Any]:
    """Score a RootCauseReport against ground truth entry."""
    file_match = check_file_correct(report.file, gt.get("root_cause_file", ""))
    func_match = check_function_correct(report.function, gt.get("root_cause_function", ""))
    line_match = check_line_overlap(report.line_start, report.line_end, gt.get("line_range", []))
    commit_match = check_commit_correct(report.introducing_commit, gt.get("introducing_commit_hash", ""))
    type_match = check_bug_type_correct(report.bug_type, gt.get("bug_type", ""))

    semantic_score, justification = score_root_cause_semantic(
        report.root_cause,
        gt.get("root_cause_summary", ""),
    )

    return {
        "file_correct": file_match,
        "function_correct": func_match,
        "line_overlap": line_match,
        "commit_correct": commit_match,
        "bug_type_correct": type_match,
        "cause_semantic_score": semantic_score,
        "semantic_justification": justification,
        "grounded": bool(report.grounded),
        "confidence": float(report.confidence),
        "validation_notes": report.validation_notes,
    }
