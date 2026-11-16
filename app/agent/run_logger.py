"""Investigation run artifact logging for BugSleuth."""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, Optional
import uuid

from app.logging_setup import get_logger
from app.models import RootCauseReport

logger = get_logger("agent.run_logger")


def save_investigation_run(
    bug_input: str,
    report: RootCauseReport,
    steps_taken: Optional[list] = None,
    token_usage: Optional[Dict[str, int]] = None,
    latency_seconds: float = 0.0,
    runs_dir: Path | str = "runs",
) -> Path:
    """Save an immutable execution artifact of an investigation run to runs/ directory.

    Args:
        bug_input: The raw error text or failure description investigated.
        report: Final RootCauseReport object.
        steps_taken: Sequence of actions or tool calls taken.
        token_usage: Dictionary tracking prompt, completion, and total tokens.
        latency_seconds: Total execution duration in seconds.
        runs_dir: Destination directory for run logs.

    Returns:
        Path to the saved JSON artifact.
    """
    storage = Path(runs_dir).resolve()
    storage.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc)
    ts_str = timestamp.strftime("%Y%m%d_%H%M%S")
    run_id = str(uuid.uuid4())[:8]
    filename = f"{ts_str}_{run_id}.json"
    dest_file = storage / filename

    run_record = {
        "run_id": run_id,
        "timestamp_utc": timestamp.isoformat(),
        "latency_seconds": round(latency_seconds, 2),
        "token_usage": token_usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "input": {
            "bug_text": bug_input,
            "character_count": len(bug_input),
        },
        "steps_count": len(steps_taken or report.steps_taken or []),
        "steps": steps_taken or report.steps_taken or [],
        "report": report.model_dump(),
        "grounded": report.grounded,
        "fix_verified": report.fix_verified,
        "confidence": report.confidence,
    }

    try:
        dest_file.write_text(json.dumps(run_record, indent=2), encoding="utf-8")
        logger.info("Saved investigation run log to %s (id: %s)", dest_file, run_id)
    except Exception as exc:
        logger.warning("Failed to save run log to %s: %s", dest_file, exc)

    return dest_file
