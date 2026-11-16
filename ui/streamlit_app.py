"""BugSleuth Streamlit User Interface.

Interactive web application for autonomous bug detection, live investigation
streaming via Server-Sent Events, and structured root-cause report presentation.
"""

from datetime import datetime, timezone
import json
import os
import time
from typing import Any, Dict, List, Optional
import requests
import streamlit as st

# Ensure local loopback requests bypass any external proxy
os.environ["NO_PROXY"] = "localhost,127.0.0.1"

# Shared requests session with trust_env=False to guarantee local connectivity
_session = requests.Session()
_session.trust_env = False

# Configure page layout and visual identity
st.set_page_config(
    page_title="BugSleuth - AI Root Cause Analysis",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for polished interface styling
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
        color: #1E88E5;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #546E7A;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8F9FA;
        border-radius: 8px;
        padding: 12px 16px;
        border: 1px solid #E0E0E0;
    }
    .badge-grounded {
        background-color: #E8F5E9;
        color: #2E7D32;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
    }
    .badge-ungrounded {
        background-color: #FFEBEE;
        color: #C62828;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
    }
    .step-box {
        font-family: monospace;
        background-color: #263238;
        color: #ECEFF1;
        padding: 8px 12px;
        border-radius: 6px;
        font-size: 0.88rem;
        margin-bottom: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize Session State
if "bug_input" not in st.session_state:
    st.session_state.bug_input = ""
if "selected_bug_id" not in st.session_state:
    st.session_state.selected_bug_id = ""
if "investigation_report" not in st.session_state:
    st.session_state.investigation_report = None
if "live_steps" not in st.session_state:
    st.session_state.live_steps = []
if "sample_bugs_cache" not in st.session_state:
    st.session_state.sample_bugs_cache = []


# Helper functions to query the backend API
def fetch_health(api_url: str) -> Optional[Dict[str, Any]]:
    """Query GET /health endpoint."""
    try:
        res = _session.get(f"{api_url}/health", timeout=3.0)
        return res.json()
    except Exception:
        return None


def fetch_index_status(api_url: str) -> Optional[Dict[str, Any]]:
    """Query GET /index/status endpoint."""
    try:
        res = _session.get(f"{api_url}/index/status", timeout=3.0)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None


def fetch_sample_bugs(api_url: str) -> List[Dict[str, Any]]:
    """Query GET /bugs endpoint."""
    try:
        res = _session.get(f"{api_url}/bugs", timeout=5.0)
        if res.status_code == 200:
            return res.json().get("bugs", [])
    except Exception:
        pass
    return []


def trigger_index_rebuild(api_url: str) -> Dict[str, Any]:
    """Trigger POST /index/rebuild endpoint."""
    try:
        res = _session.post(f"{api_url}/index/rebuild", timeout=5.0)
        return res.json()
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def build_markdown_report(report: Dict[str, Any]) -> str:
    """Format RootCauseReport dictionary into clean GitHub-flavored Markdown document."""
    lines = [
        f"# BugSleuth Root Cause Analysis Report",
        f"",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"**Confidence:** {report.get('confidence', 0.0) * 100:.1f}% ({report.get('confidence_reasoning', '')})",
        f"**Validation Grounded:** {'YES (Verified against repository AST & git)' if report.get('grounded') else 'NO (Unverified claims)'}",
        f"",
        f"---",
        f"",
        f"## 1. Summary & Classification",
        f"- **Summary:** {report.get('summary', 'N/A')}",
        f"- **Category:** `{report.get('bug_type', 'unknown')}`",
        f"- **Offending Location:** `{report.get('file', 'unknown')}:{report.get('line_start', '?')}-{report.get('line_end', '?')}`",
        f"- **Function / Symbol:** `{report.get('function', 'unknown')}`",
        f"- **Introducing Commit:** `{report.get('introducing_commit') or 'N/A'}`",
        f"",
        f"## 2. Root Cause Analysis",
        f"{report.get('root_cause', 'N/A')}",
        f"",
        f"## 3. Suggested Fix & Patch",
        f"{report.get('suggested_fix', 'N/A')}",
        f"",
        f"## 4. Supporting Evidence",
    ]

    for idx, ev in enumerate(report.get("evidence", []), 1):
        lines.append(f"### Evidence #{idx} ({ev.get('kind', 'code').upper()})")
        lines.append(f"- **Source:** `{ev.get('source', '')}`")
        lines.append(f"- **Relevance:** {ev.get('why_relevant', '')}")
        lines.append(f"```\n{ev.get('snippet', '')}\n```\n")

    if report.get("steps_taken"):
        lines.append(f"## 5. Investigation Trail")
        for s in report.get("steps_taken", []):
            lines.append(f"- {s}")
        lines.append("")

    if report.get("open_questions"):
        lines.append(f"## 6. Open Questions & Caveats")
        for q in report.get("open_questions", []):
            lines.append(f"- {q}")
        lines.append("")

    return "\n".join(lines)


# ==========================================
# SIDEBAR CONTROLS
# ==========================================
with st.sidebar:
    st.markdown("### 🔍 BugSleuth Controls")

    api_url = st.text_input(
        "API Base URL",
        value="http://127.0.0.1:8000",
        help="FastAPI backend host address",
    )

    # Health & Connectivity check
    health_data = fetch_health(api_url)
    if health_data and health_data.get("status") in ("ok", "degraded"):
        status_color = "🟢" if health_data.get("status") == "ok" else "🟡"
        st.caption(f"{status_color} **API Online** ({health_data.get('status').upper()})")
    else:
        st.error("🔴 **API Offline** (Run `python scripts/run_dev.py`)")

    st.markdown("---")

    # Index Status Section
    st.markdown("#### 📚 Code & Ticket Index")
    index_status = fetch_index_status(api_url)
    if index_status:
        st.write(f"**Target Repo:** `{index_status.get('target_repo', './demo_repo')}`")
        col_c1, col_c2 = st.columns(2)
        col_c1.metric("Code Chunks", index_status.get("code_chunks_count", 0))
        col_c2.metric("Tickets", index_status.get("tickets_count", 0))

        if index_status.get("status") == "indexing":
            st.info("⏳ Indexing in progress...")

        if st.button("🔄 Rebuild Index", use_container_width=True):
            res = trigger_index_rebuild(api_url)
            if res.get("status") == "started":
                with st.spinner("Rebuilding Chroma vector index..."):
                    # Poll for completion up to 25 seconds
                    for _ in range(25):
                        time.sleep(1.0)
                        st_check = fetch_index_status(api_url)
                        if st_check and st_check.get("status") in ("completed", "failed"):
                            break
                st.success("Index rebuild finished!")
                st.rerun()
            else:
                st.warning(res.get("message", "Could not start rebuild."))
    else:
        st.caption("Index information unavailable.")

    st.markdown("---")

    # Sample Bug Loader Section
    st.markdown("#### 🧪 Load Sample Bug Scenario")
    if not st.session_state.sample_bugs_cache and health_data:
        st.session_state.sample_bugs_cache = fetch_sample_bugs(api_url)

    sample_options = ["-- Select a sample scenario --"] + [
        f"{b['id']}: {b['title']}" for b in st.session_state.sample_bugs_cache
    ]

    selected_sample = st.selectbox(
        "Choose test scenario",
        options=sample_options,
        index=0,
        help="Pre-fills input with a known failure scenario from demo_repo",
    )

    if selected_sample != "-- Select a sample scenario --":
        bug_id = selected_sample.split(":")[0].strip()
        if st.session_state.selected_bug_id != bug_id:
            match = next((b for b in st.session_state.sample_bugs_cache if b["id"] == bug_id), None)
            if match:
                st.session_state.selected_bug_id = bug_id
                st.session_state.bug_input = match["error_text"]
                st.session_state.investigation_report = None
                st.session_state.live_steps = []
                st.rerun()

    st.markdown("---")

    # Reasoning parameters
    st.markdown("#### ⚙️ Agent Tuning")
    max_steps = st.slider(
        "Max Reasoning Steps",
        min_value=4,
        max_value=20,
        value=12,
        help="Hard ceiling on LangGraph investigation loop steps",
    )


# ==========================================
# MAIN INTERFACE
# ==========================================
st.markdown('<div class="main-title">🔍 BugSleuth: AI Root-Cause Analysis Agent</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">'
    "Autonomous engineering agent that inspects repository AST, git blame, diffs, application logs, "
    "and historical tickets to identify root causes and generate validated patches."
    "</div>",
    unsafe_allow_html=True,
)

# Text area for bug report input
user_input = st.text_area(
    "Enter Error Message, Stack Trace, or Failure Description:",
    value=st.session_state.bug_input,
    height=200,
    placeholder="Paste a Python traceback, error log snippet, or bug symptom description here...",
)
# Update session state on text modification
st.session_state.bug_input = user_input

col_btn1, col_btn2, _ = st.columns([2, 1, 5])
with col_btn1:
    investigate_clicked = st.button("🚀 Investigate Root Cause", type="primary", use_container_width=True)
with col_btn2:
    if st.button("🗑️ Clear", use_container_width=True):
        st.session_state.bug_input = ""
        st.session_state.selected_bug_id = ""
        st.session_state.investigation_report = None
        st.session_state.live_steps = []
        st.rerun()


# ==========================================
# STREAMING INVESTIGATION EXECUTION
# ==========================================
if investigate_clicked:
    if not user_input.strip() or len(user_input.strip()) < 5:
        st.warning("Please provide a valid bug description or stack trace (at least 5 characters).")
    else:
        st.session_state.live_steps = []
        st.session_state.investigation_report = None

        st.markdown("---")
        progress_container = st.container()

        with progress_container:
            with st.status("🕵️ Investigating bug in target codebase...", expanded=True) as status_box:
                steps_placeholder = st.empty()
                stream_url = f"{api_url}/investigate/stream"
                params = {"bug_text": user_input, "max_steps": max_steps}

                try:
                    with _session.get(stream_url, params=params, stream=True, timeout=300) as response:
                        if response.status_code != 200:
                            status_box.update(label="❌ Investigation API Error", state="error")
                            st.error(f"API returned status {response.status_code}: {response.text}")
                        else:
                            for line in response.iter_lines(decode_unicode=True):
                                if not line:
                                    continue
                                if line.startswith("data: "):
                                    payload_str = line[len("data: ") :].strip()
                                    try:
                                        payload = json.loads(payload_str)
                                    except Exception:
                                        continue

                                    event_type = payload.get("event")

                                    if event_type == "parsed_error":
                                        p = payload.get("data", {})
                                        cf = p.get("crash_frame")
                                        site = f" at `{cf['file']}:{cf['line']}` ({cf['function']})" if cf else ""
                                        st.session_state.live_steps.append(
                                            f"📄 **Parsed Symptom**: `{p.get('error_type')}`{site}"
                                        )

                                    elif event_type == "thought":
                                        content = payload.get("content", "").strip()
                                        if content:
                                            first_line = content.splitlines()[0][:140]
                                            st.session_state.live_steps.append(f"🧠 **Thought**: {first_line}")

                                    elif event_type == "tool_call":
                                        tool = payload.get("tool")
                                        args = payload.get("args", {})
                                        args_preview = ", ".join(f"{k}={v}" for k, v in args.items())[:100]
                                        st.session_state.live_steps.append(
                                            f"🛠️ **Executing Tool**: `{tool}({args_preview})`"
                                        )

                                    elif event_type == "tool_result":
                                        tool = payload.get("tool")
                                        res = payload.get("result", "")[:120].replace("\n", " ")
                                        st.session_state.live_steps.append(
                                            f"📋 **Tool Result** (`{tool}`): {res}..."
                                        )

                                    elif event_type == "hypothesis":
                                        hypo = payload.get("data", "")[:150]
                                        st.session_state.live_steps.append(f"💡 **Hypothesis Formed**: {hypo}...")

                                    elif event_type == "final_report":
                                        rep = payload.get("report")
                                        st.session_state.investigation_report = rep

                                    elif event_type == "error":
                                        status_box.update(label="❌ Error Encountered", state="error")
                                        st.error(f"Investigation error: {payload.get('message')}")
                                        break

                                    # Update UI live list
                                    rendered_steps = "\n\n".join(
                                        f"- {s}" for s in st.session_state.live_steps[-10:]
                                    )
                                    steps_placeholder.markdown(rendered_steps)

                            status_box.update(
                                label="✅ Root Cause Analysis Complete!",
                                state="complete",
                                expanded=False,
                            )
                except Exception as exc:
                    status_box.update(label="❌ Network or Execution Failure", state="error")
                    st.error(f"Failed to stream from API: {exc}")


# ==========================================
# FINAL REPORT PRESENTATION
# ==========================================
report = st.session_state.investigation_report

if report:
    st.markdown("---")
    st.markdown("### 📋 Root Cause Analysis Findings")

    # High-level summary banner
    st.info(f"**Diagnostic Summary:** {report.get('summary')}")

    # Metrics Row
    m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)

    confidence_val = float(report.get("confidence", 0.0))
    m_col1.metric("Confidence", f"{confidence_val * 100:.0f}%")

    file_val = report.get("file", "unknown")
    start_l = report.get("line_start", "?")
    end_l = report.get("line_end", "?")
    m_col2.metric("Offending Location", f"{file_val}:{start_l}-{end_l}")

    m_col3.metric("Offending Function", report.get("function", "unknown"))

    commit_val = report.get("introducing_commit")
    m_col4.metric("Introducing Commit", commit_val[:7] if commit_val else "N/A")

    is_grounded = bool(report.get("grounded", False))
    with m_col5:
        st.write("**Validation Badge**")
        if is_grounded:
            st.markdown('<span class="badge-grounded">✅ GROUNDED (PASS)</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="badge-ungrounded">⚠️ UNVERIFIED</span>', unsafe_allow_html=True)

    # Detailed Tabs
    tab_diag, tab_fix, tab_evid, tab_trail = st.tabs(
        ["🔍 Root Cause Diagnosis", "🛠️ Suggested Fix", "📦 Evidence Chain", "👣 Investigation Trail"]
    )

    with tab_diag:
        st.markdown("#### Detailed Root Cause Explanation")
        st.markdown(report.get("root_cause", "No detailed explanation available."))

        st.markdown("#### Classification & Confidence Reasoning")
        st.write(f"**Bug Category:** `{report.get('bug_type', 'unknown')}`")
        st.write(f"**Confidence Reasoning:** {report.get('confidence_reasoning', 'N/A')}")

        if report.get("validation_notes"):
            st.markdown("#### Automated Validation Findings")
            for note in report.get("validation_notes", []):
                st.write(f"- {note}")

    with tab_fix:
        st.markdown("#### Recommended Solution")
        st.markdown(report.get("suggested_fix", "No fix provided."))

        # If fix contains a unified diff codeblock, render syntax-highlighted diff
        fix_text = report.get("suggested_fix", "")
        if "```diff" in fix_text:
            try:
                diff_part = fix_text.split("```diff")[1].split("```")[0].strip()
                st.markdown("##### Unified Diff Patch")
                st.code(diff_part, language="diff")
            except Exception:
                pass
        elif "--- " in fix_text and "+++ " in fix_text:
            st.markdown("##### Unified Diff Patch")
            st.code(fix_text, language="diff")

    with tab_evid:
        evidence_list = report.get("evidence", [])
        if not evidence_list:
            st.write("No explicit evidence items logged.")
        else:
            e_kinds = {e.get("kind") for e in evidence_list}
            sub_tabs = st.tabs([f"📂 {k.upper()} ({sum(1 for e in evidence_list if e.get('kind') == k)})" for k in sorted(e_kinds)])

            for s_tab, kind in zip(sub_tabs, sorted(e_kinds)):
                with s_tab:
                    for ev in [e for e in evidence_list if e.get("kind") == kind]:
                        with st.expander(f"Source: {ev.get('source')}", expanded=True):
                            st.write(f"**Why Relevant:** {ev.get('why_relevant')}")
                            st.code(ev.get("snippet", ""), language="python" if kind in ("code", "diff") else None)

    with tab_trail:
        st.markdown("#### Chronological Investigative Actions")
        steps_list = report.get("steps_taken", [])
        if steps_list:
            for s in steps_list:
                st.write(f"- {s}")
        else:
            st.write("No steps recorded in final report.")

        open_q = report.get("open_questions", [])
        if open_q:
            st.markdown("#### Open Questions & Ambiguities")
            for q in open_q:
                st.write(f"- ❓ {q}")

    st.markdown("---")

    # Download action buttons
    d_col1, d_col2, _ = st.columns([2, 2, 4])
    with d_col1:
        json_report_str = json.dumps(report, indent=2)
        st.download_button(
            label="📥 Download Report (JSON)",
            data=json_report_str,
            file_name=f"bug_report_{report.get('file', 'unknown').replace('/', '_')}.json",
            mime="application/json",
            use_container_width=True,
        )

    with d_col2:
        md_report_str = build_markdown_report(report)
        st.download_button(
            label="📄 Download Report (Markdown)",
            data=md_report_str,
            file_name=f"bug_report_{report.get('file', 'unknown').replace('/', '_')}.md",
            mime="text/markdown",
            use_container_width=True,
        )
