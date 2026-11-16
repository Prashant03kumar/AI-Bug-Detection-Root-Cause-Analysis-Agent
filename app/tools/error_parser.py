"""Error message and stack trace parser tool."""

import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.logging_setup import get_logger
from app.tools.common import truncate_output

logger = get_logger("tools.error_parser")


class ParseErrorArgs(BaseModel):
    """Input schema for parse_error tool."""
    text: str = Field(..., description="Raw error log, stack trace, or symptom description to parse")


def parse_error_impl(text: str) -> Dict[str, Any]:
    """Parse raw error text into structured components."""
    if not text or not text.strip():
        return {
            "error_type": "Unknown",
            "message": "Empty error text provided",
            "frames": [],
            "crash_frame": None,
            "candidate_keywords": [],
        }

    clean_text = text.strip()
    frames: List[Dict[str, Any]] = []
    error_type: Optional[str] = None
    message: Optional[str] = None

    # 1. Python Stack Trace Matching
    # e.g.: File ".../users.py", line 38, in get_user_notification_preference
    py_frame_pattern = re.compile(
        r'File\s+["\'](?P<file>.+?)["\'],\s+line\s+(?P<line>\d+)(?:,\s+in\s+(?P<func>[A-Za-z0-9_<>]+))?'
    )
    for match in py_frame_pattern.finditer(clean_text):
        f_path = match.group("file").replace("\\", "/")
        line_num = int(match.group("line"))
        func_name = match.group("func") or "<unknown>"
        frames.append({
            "file": f_path,
            "line": line_num,
            "function": func_name,
        })

    # 2. JS / Java Stack Trace Matching
    # e.g.: at UserService.getUser (users.js:42:15) or at com.shop.User.get(User.java:42)
    if not frames:
        js_frame_pattern = re.compile(
            r'at\s+(?:(?P<func>[A-Za-z0-9_$.<>]+)\s+\()?(?P<file>[A-Za-z0-9_./\\-]+\.[a-z]+):(?P<line>\d+)'
        )
        for match in js_frame_pattern.finditer(clean_text):
            f_path = match.group("file").replace("\\", "/")
            line_num = int(match.group("line"))
            func_name = match.group("func") or "<unknown>"
            frames.append({
                "file": f_path,
                "line": line_num,
                "function": func_name,
            })

    # 3. Extract Error Type and Message
    # Check for standard Python Exception lines e.g.: TypeError: 'NoneType' object is not subscriptable
    err_line_pattern = re.compile(
        r'^(?:[A-Za-z0-9_.]+\.)?([A-Za-z0-9_]*(?:Error|Exception|Mismatch|Leak|Anomaly|Rejection|Fault|Warning))(?::\s*(.*))?$',
        re.MULTILINE,
    )
    err_matches = list(err_line_pattern.finditer(clean_text))
    if err_matches:
        # Last error match is typically the terminal exception in chained tracebacks
        last_match = err_matches[-1]
        error_type = last_match.group(1).strip()
        message = (last_match.group(2) or "").strip()

    # If no explicit exception pattern, check for [ERROR] log prefix
    if not error_type:
        log_err_match = re.search(
            r'\[ERROR\]\s+(?:.*reproduced:\s+)?(?:([A-Za-z0-9_]+Error|[A-Za-z0-9_]+Mismatch|[A-Za-z0-9_]+Leak|[A-Za-z0-9_]+Anomaly|[A-Za-z0-9_]+Rejection):)?\s*(.*)',
            clean_text,
        )
        if log_err_match:
            error_type = log_err_match.group(1) or "ApplicationError"
            message = log_err_match.group(2).strip()

    # Fallback to generic summary line if still not identified
    if not error_type:
        first_line = clean_text.splitlines()[0]
        error_type = "SymptomDescription"
        message = first_line[:120]

    crash_frame = frames[-1] if frames else None

    # 4. Extract Candidate Keywords
    candidate_keywords: List[str] = []
    if error_type:
        candidate_keywords.append(error_type)
    for frame in frames:
        if frame["function"] not in ("<module>", "<unknown>"):
            candidate_keywords.append(frame["function"])
        file_name = Path(frame["file"]).name
        if file_name and file_name not in candidate_keywords:
            candidate_keywords.append(file_name)

    # Add keywords from message
    if message:
        words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", message)
        for w in words:
            if w not in candidate_keywords and w.lower() not in ("error", "exception", "traceback", "file", "line"):
                candidate_keywords.append(w)

    return {
        "error_type": error_type,
        "message": message or "",
        "frames": frames,
        "crash_frame": crash_frame,
        "candidate_keywords": candidate_keywords[:15],
    }


@tool("parse_error", args_schema=ParseErrorArgs)
def parse_error(text: str) -> str:
    """Parse an error log, stack trace, or symptom description into structured frames and keywords.

    Args:
        text: Raw error text or stack trace.

    Returns:
        JSON string containing error_type, message, frames, crash_frame, and candidate_keywords.
    """
    try:
        data = parse_error_impl(text)
        return truncate_output(json.dumps(data, indent=2))
    except Exception as exc:
        logger.error("parse_error encountered an error: %s", exc)
        return json.dumps({
            "error_type": "ParseErrorFailure",
            "message": str(exc),
            "frames": [],
            "crash_frame": None,
            "candidate_keywords": [],
        })
