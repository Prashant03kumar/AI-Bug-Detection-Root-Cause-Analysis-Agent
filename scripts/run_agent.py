"""CLI script to run the LangGraph bug investigation agent."""

import argparse
import json
import sys
from pathlib import Path

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.graph import stream_investigation
from app.config import get_settings

DATA_BUGS_DIR = PROJECT_ROOT / "data" / "bugs"


def normalize_bug_id(raw_bug: str) -> str:
    """Normalize user input like 'bug_03' or 'bug-3' to 'BUG-03'."""
    clean = raw_bug.strip().upper().replace("_", "-")
    if not clean.startswith("BUG-"):
        clean = f"BUG-{clean}"
    parts = clean.split("-")
    if len(parts) == 2 and parts[1].isdigit():
        clean = f"BUG-{int(parts[1]):02d}"
    return clean


def main() -> int:
    parser = argparse.ArgumentParser(description="BugSleuth Autonomous Investigation Agent")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--bug",
        type=str,
        help="Bug ID to investigate (e.g. 'BUG-01', 'bug_03')",
    )
    group.add_argument(
        "--text",
        type=str,
        help="Raw error message, stack trace, or bug description string",
    )
    args = parser.parse_args()

    if args.bug:
        norm_id = normalize_bug_id(args.bug)
        error_file = DATA_BUGS_DIR / norm_id / "error.txt"
        if not error_file.is_file():
            print(f"ERROR: Bug directory or error file not found at: {error_file}", file=sys.stderr)
            return 1
        input_text = error_file.read_text(encoding="utf-8")
        target_label = norm_id
    else:
        input_text = args.text
        target_label = "Direct Input"

    print("=" * 70)
    print(f" BugSleuth Autonomous Investigation: {target_label}")
    print("=" * 70)
    print(f"Input Preview (first 250 chars):\n{input_text[:250].strip()}...\n")
    print("Beginning agent reasoning and tool execution trace...\n" + "-" * 70)

    final_report = None
    step_num = 1

    try:
        for event in stream_investigation(input_text):
            etype = event["event"]
            if etype == "parsed_error":
                pe = event["data"]
                print(f"[Parsed Error] Type: {pe.get('error_type')} | Crash Site: {pe.get('crash_frame')}")
            elif etype == "thought":
                print(f"\n[Thought {step_num}]:\n{event['content'].strip()}")
                step_num += 1
            elif etype == "tool_call":
                t_args = json.dumps(event['args'])
                print(f"\n[Tool Call] -> {event['tool']}({t_args})")
            elif etype == "tool_result":
                short_res = event['result'].replace("\n", " ")
                print(f"[Tool Result] <- {event['tool']}: {short_res}")
            elif etype == "hypothesis":
                print(f"\n[Hypothesis]:\n{event['data'].strip()}")
            elif etype == "final_report":
                final_report = event["report"]

        print("-" * 70)
        if not final_report:
            print("\nERROR: Investigation concluded without generating a final report.")
            return 1

        print("\n" + "=" * 70)
        print(" FINAL ROOT CAUSE ANALYSIS REPORT")
        print("=" * 70)
        print(f"Summary             : {final_report.summary}")
        print(f"Root Cause          : {final_report.root_cause}")
        print(f"Bug Type            : {final_report.bug_type}")
        print(f"Location            : {final_report.file}::{final_report.function} (lines {final_report.line_start}-{final_report.line_end})")
        print(f"Introducing Commit  : {final_report.introducing_commit}")
        print(f"Confidence          : {final_report.confidence:.2f} ({final_report.confidence_reasoning})")
        print(f"Grounded (Verified) : {'YES' if final_report.grounded else 'NO'}")
        if final_report.validation_notes:
            print(f"Validation Notes    : {'; '.join(final_report.validation_notes)}")
        print("\nSuggested Fix:")
        print(final_report.suggested_fix)

        if final_report.evidence:
            print(f"\nGathered Evidence ({len(final_report.evidence)} items):")
            for i, ev in enumerate(final_report.evidence, start=1):
                print(f"  {i}. [{ev.kind}] {ev.source}: {ev.why_relevant}")

        print("\n" + "=" * 70)
        print(" REPORT JSON DUMP:")
        print("=" * 70)
        print(json.dumps(final_report.model_dump(), indent=2))
        return 0

    except Exception as exc:
        print(f"\nFATAL: Agent execution failed: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
