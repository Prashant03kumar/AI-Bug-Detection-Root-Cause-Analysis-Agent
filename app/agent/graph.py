"""LangGraph investigation agent with tool execution, verification, and structured reporting."""

import json
import os
import re
import time
from typing import Any, Dict, Generator, List, Literal, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from app.agent.fix_verifier import extract_diff_patch, verify_fix_in_temp_repo
from app.agent.prompts import (
    HYPOTHESIS_PROMPT,
    INVESTIGATION_SYSTEM_PROMPT,
    REPORT_PROMPT,
    VERIFICATION_PROMPT,
)
from app.agent.run_logger import save_investigation_run
from app.agent.state import AgentState
from app.agent.validate import validate_report
from app.config import Settings, get_settings
from app.llm import get_llm
from app.logging_setup import get_logger
from app.models import Evidence, RootCauseReport
from app.tools import ALL_TOOLS
from app.tools.error_parser import parse_error_impl

logger = get_logger("agent.graph")

TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}
_TOOL_EXECUTION_CACHE: Dict[str, str] = {}


def record_evidence(tool_name: str, args: Dict[str, Any], result: str, state_evidence: List[Evidence]) -> None:
    """Extract and append structured Evidence objects from tool execution results."""
    clean_result = result[:1200]
    if "Error:" in result or "not found" in result.lower() and len(result) < 150:
        return

    if tool_name in ("read_file", "get_function_source"):
        source = f"{args.get('path') or args.get('file')}:{args.get('start_line') or args.get('target_line') or args.get('symbol')}"
        state_evidence.append(
            Evidence(
                kind="code",
                source=source,
                snippet=clean_result[:400],
                why_relevant=f"Observed code implementation in {source}",
            )
        )
    elif tool_name == "git_blame":
        source = f"git_blame({args.get('file')})"
        state_evidence.append(
            Evidence(
                kind="commit",
                source=source,
                snippet=clean_result[:400],
                why_relevant="Identified author and commit revisions modifying critical lines",
            )
        )
    elif tool_name == "show_commit_diff":
        source = f"commit_diff({args.get('commit_hash')})"
        state_evidence.append(
            Evidence(
                kind="diff",
                source=source,
                snippet=clean_result[:400],
                why_relevant="Inspected code diff introduced by suspect commit",
            )
        )
    elif tool_name == "search_logs":
        source = f"app.log query '{args.get('query')}'"
        state_evidence.append(
            Evidence(
                kind="log",
                source=source,
                snippet=clean_result[:400],
                why_relevant="Runtime log occurrences correlating with failure symptoms",
            )
        )
    elif tool_name == "find_similar_bugs":
        source = "historical bug tickets"
        state_evidence.append(
            Evidence(
                kind="ticket",
                source=source,
                snippet=clean_result[:400],
                why_relevant="Historical resolution pattern for similar symptoms",
            )
        )


def node_parse_input(state: AgentState) -> Dict[str, Any]:
    """Parse raw bug input into structured components and initialize message history."""
    raw_input = state["bug_input"]
    logger.info("Starting investigation of bug input (%d chars)", len(raw_input))
    parsed = parse_error_impl(raw_input)

    crash_summary = f"Error Type: {parsed['error_type']}\nMessage: {parsed['message']}"
    if parsed.get("crash_frame"):
        cf = parsed["crash_frame"]
        crash_summary += f"\nCrash Site: {cf['file']}:{cf['line']} in {cf['function']}"

    initial_prompt = (
        f"Investigate the following reported bug and locate its root cause:\n\n"
        f"```\n{raw_input}\n```\n\n"
        f"Parsed Error Analysis:\n{crash_summary}\n\n"
        f"Candidate Keywords: {', '.join(parsed['candidate_keywords'])}\n\n"
        f"Begin by locating and reading the relevant code files."
    )

    messages = [
        SystemMessage(content=INVESTIGATION_SYSTEM_PROMPT),
        HumanMessage(content=initial_prompt),
    ]

    return {
        "parsed_error": parsed,
        "messages": messages,
        "step_count": 0,
        "tool_call_history": [],
        "evidence": [],
        "hypotheses": [],
    }


def create_investigate_node(settings: Settings, llm_override: Optional[Any] = None):
    """Factory creating the investigation node with bound tools and limit handling."""
    llm = llm_override or get_llm(settings=settings)
    llm_with_tools = llm.bind_tools(ALL_TOOLS)
    max_steps = settings.max_agent_steps

    def node_investigate(state: AgentState) -> Dict[str, Any]:
        cur_step = state["step_count"] + 1
        logger.info("Investigation step %d / %d", cur_step, max_steps)

        if cur_step >= max_steps:
            logger.warning("Reached maximum agent step limit (%d). Forcing conclusion.", max_steps)
            warning_msg = AIMessage(
                content="I have reached the maximum investigative step limit. Synthesizing findings based on currently gathered evidence."
            )
            return {
                "step_count": cur_step,
                "messages": [warning_msg],
            }

        response = llm_with_tools.invoke(state["messages"])
        return {
            "step_count": cur_step,
            "messages": [response],
        }

    return node_investigate


def node_tools(state: AgentState) -> Dict[str, Any]:
    """Execute tool calls with loop detection and error resilience."""
    messages = state["messages"]
    last_msg = messages[-1]
    tool_messages: List[ToolMessage] = []
    call_history = list(state.get("tool_call_history", []))
    evidence_list = list(state.get("evidence", []))

    if not isinstance(last_msg, AIMessage) or not last_msg.tool_calls:
        return {"tool_call_history": call_history}

    for tc in last_msg.tool_calls:
        t_name = tc.get("name")
        t_args = tc.get("args", {})
        t_id = tc.get("id") or f"call_{t_name}"

        # Loop / Duplicate Call Detection and in-run caching
        call_sig = f"{t_name}:{json.dumps(t_args, sort_keys=True)}"
        call_count = call_history.count(call_sig)

        logger.info("Executing tool: %s with args: %s (call count: %d)", t_name, t_args, call_count)

        if call_count >= 2:
            res_str = (
                f"Loop Warning: Tool '{t_name}' was already executed twice with identical arguments {t_args}. "
                f"Please analyze the previous output or examine upstream callers/callees instead."
            )
        elif call_sig in _TOOL_EXECUTION_CACHE:
            logger.info("Using cached tool execution result for %s", call_sig)
            res_str = _TOOL_EXECUTION_CACHE[call_sig]
            record_evidence(t_name, t_args, res_str, evidence_list)
        else:
            tool_fn = TOOLS_BY_NAME.get(t_name)
            if not tool_fn:
                res_str = f"Error: Tool '{t_name}' does not exist in registry."
            else:
                try:
                    res_str = str(tool_fn.invoke(t_args))
                    _TOOL_EXECUTION_CACHE[call_sig] = res_str
                except Exception as exc:
                    logger.error("Error running tool %s: %s", t_name, exc)
                    res_str = f"Error executing {t_name}: {exc}"

            record_evidence(t_name, t_args, res_str, evidence_list)

        call_history.append(call_sig)
        tool_messages.append(ToolMessage(tool_call_id=t_id, content=res_str, name=t_name))

    return {
        "messages": tool_messages,
        "tool_call_history": call_history,
        "evidence": evidence_list,
    }


def route_after_investigate(state: AgentState) -> Literal["tools", "hypothesize", "report"]:
    """Determine next step: execute tools, formulate hypothesis, or conclude."""
    settings = get_settings()
    if state["step_count"] >= settings.max_agent_steps:
        return "report"

    messages = state["messages"]
    if not messages:
        return "hypothesize"

    last_msg = messages[-1]
    if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
        return "tools"

    return "hypothesize"


def create_hypothesize_node(settings: Settings, llm_override: Optional[Any] = None):
    """Factory creating hypothesis generation node."""
    llm = llm_override or get_llm(settings=settings)

    def node_hypothesize(state: AgentState) -> Dict[str, Any]:
        logger.info("Formulating root cause hypothesis...")
        err_summary = json.dumps(state["parsed_error"], indent=2)
        prompt = HYPOTHESIS_PROMPT.format(error_summary=err_summary)

        context_messages = list(state["messages"]) + [HumanMessage(content=prompt)]
        resp = llm.invoke(context_messages)

        hypo_text = resp.content if hasattr(resp, "content") else str(resp)
        new_hypotheses = list(state.get("hypotheses", []))
        new_hypotheses.append({
            "hypothesis": str(hypo_text),
            "status": "unverified",
            "supporting_evidence": [e.source for e in state.get("evidence", [])],
        })

        return {
            "hypotheses": new_hypotheses,
            "messages": [resp],
        }

    return node_hypothesize


def create_verify_node(settings: Settings, llm_override: Optional[Any] = None):
    """Factory creating hypothesis verification node."""
    llm = llm_override or get_llm(settings=settings)

    def node_verify(state: AgentState) -> Dict[str, Any]:
        logger.info("Verifying leading hypothesis...")
        hypos = state.get("hypotheses", [])
        leading_hypo = hypos[-1]["hypothesis"] if hypos else "No hypothesis generated yet."
        evidence_summary = "\n".join([f"- [{e.kind}] {e.source}: {e.why_relevant}" for e in state.get("evidence", [])]) or "None"

        prompt = VERIFICATION_PROMPT.format(
            hypothesis=leading_hypo,
            evidence_summary=evidence_summary,
        )

        resp = llm.invoke(list(state["messages"]) + [HumanMessage(content=prompt)])
        content = resp.content if hasattr(resp, "content") else str(resp)

        # Update hypothesis status
        if hypos:
            is_confirmed = "confirm" in str(content).lower() or "verified" in str(content).lower()
            hypos[-1]["status"] = "confirmed" if is_confirmed else "rejected"

        return {
            "hypotheses": hypos,
            "messages": [resp],
        }

    return node_verify


def route_after_verification(state: AgentState) -> Literal["investigate", "report"]:
    """Decide whether to gather more evidence or finalize the report."""
    settings = get_settings()
    if state["step_count"] >= settings.max_agent_steps - 2:
        return "report"

    hypos = state.get("hypotheses", [])
    if hypos and hypos[-1]["status"] == "confirmed":
        return "report"

    # If unconfirmed and budget remains, run one more investigation pass
    if state["step_count"] < 8:
        return "investigate"
    return "report"


def create_report_node(settings: Settings, llm_override: Optional[Any] = None):
    """Factory creating report generation node with forced structured output."""
    llm = llm_override or get_llm(settings=settings)
    structured_llm = llm.with_structured_output(RootCauseReport)

    def node_report(state: AgentState) -> Dict[str, Any]:
        logger.info("Synthesizing final RootCauseReport...")
        evidence_list = state.get("evidence", [])
        evidence_txt = "\n".join([
            f"Evidence {i+1} [{e.kind}]: {e.source}\nSnippet: {e.snippet}\nWhy: {e.why_relevant}\n"
            for i, e in enumerate(evidence_list)
        ])

        history_summary = "\n".join(state.get("tool_call_history", []))

        prompt = (
            f"{REPORT_PROMPT}\n\n"
            f"Parsed Error:\n{json.dumps(state['parsed_error'], indent=2)}\n\n"
            f"Gathered Evidence:\n{evidence_txt or 'None'}\n\n"
            f"Tool Execution History:\n{history_summary or 'None'}\n"
        )

        try:
            raw_report = structured_llm.invoke(
                list(state["messages"]) + [HumanMessage(content=prompt)]
            )
            if not isinstance(raw_report, RootCauseReport):
                # Fallback conversion if dict returned
                raw_report = RootCauseReport(**raw_report)
        except Exception as exc:
            logger.error("Structured output parsing failed: %s. Constructing emergency report.", exc)
            raw_report = RootCauseReport(
                summary=f"Investigation failed to parse structured output: {exc}",
                root_cause="Automated structured synthesis failed; check logs.",
                bug_type="unknown",
                file="unknown",
                function="unknown",
                line_start=1,
                line_end=1,
                confidence=0.1,
                confidence_reasoning="Emergency fallback due to LLM synthesis exception.",
                suggested_fix="Inspect raw trace.",
            )

        # Post-hoc validation against repo ground truth
        validated = validate_report(raw_report, repo_path=settings.target_repo_path)
        return {"final_report": validated}

    return node_report


def build_investigation_graph(
    settings: Optional[Settings] = None,
    llm_override: Optional[Any] = None,
) -> Any:
    """Construct and compile the LangGraph agent investigation workflow."""
    cfg = settings or get_settings()

    builder = StateGraph(AgentState)

    # Nodes
    builder.add_node("parse_input", node_parse_input)
    builder.add_node("investigate", create_investigate_node(cfg, llm_override))
    builder.add_node("tools", node_tools)
    builder.add_node("hypothesize", create_hypothesize_node(cfg, llm_override))
    builder.add_node("verify", create_verify_node(cfg, llm_override))
    builder.add_node("report", create_report_node(cfg, llm_override))

    # Edges
    builder.add_edge(START, "parse_input")
    builder.add_edge("parse_input", "investigate")

    builder.add_conditional_edges(
        "investigate",
        route_after_investigate,
        {
            "tools": "tools",
            "hypothesize": "hypothesize",
            "report": "report",
        },
    )

    builder.add_edge("tools", "investigate")
    builder.add_edge("hypothesize", "verify")

    builder.add_conditional_edges(
        "verify",
        route_after_verification,
        {
            "investigate": "investigate",
            "report": "report",
        },
    )

    builder.add_edge("report", END)

    return builder.compile()


def investigate_bug(
    text: str,
    settings: Optional[Settings] = None,
    llm_override: Optional[Any] = None,
) -> RootCauseReport:
    """Synchronously execute the full LangGraph bug investigation workflow."""
    start_time = time.time()
    cfg = settings or get_settings()
    graph = build_investigation_graph(cfg, llm_override=llm_override)

    initial_state: AgentState = {
        "bug_input": text,
        "parsed_error": {},
        "messages": [],
        "hypotheses": [],
        "evidence": [],
        "step_count": 0,
        "tool_call_history": [],
        "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "open_questions": [],
        "final_report": None,
    }

    final_state = graph.invoke(initial_state)
    report = final_state.get("final_report")
    if not report:
        raise RuntimeError("Investigation concluded without generating a final report.")

    # Auto-fix patch verification
    patch = extract_diff_patch(report.suggested_fix)
    if patch:
        logger.info("Extracted unified diff patch. Initiating auto-fix verification in sandbox...")
        bug_match = re.search(r"BUG-\d+", text, re.IGNORECASE)
        bug_hint = bug_match.group(0).upper() if bug_match else None
        ver_res = verify_fix_in_temp_repo(cfg.target_repo_path, patch, bug_hint=bug_hint)
        report.fix_verified = ver_res.fix_verified
        report.fix_verification_output = ver_res.test_output[:1200]
        logger.info("Auto-fix verification result: verified=%s", report.fix_verified)

    # Save immutable run log to runs/
    elapsed = time.time() - start_time
    save_investigation_run(
        bug_input=text,
        report=report,
        steps_taken=report.steps_taken or [f"Step {i+1}" for i in range(final_state.get("step_count", 0))],
        token_usage=final_state.get("token_usage"),
        latency_seconds=elapsed,
    )

    return report


def stream_investigation(
    text: str,
    settings: Optional[Settings] = None,
    llm_override: Optional[Any] = None,
) -> Generator[Dict[str, Any], None, None]:
    """Stream step events during investigation for real-time visualization."""
    stream_start = time.time()
    cfg = settings or get_settings()
    graph = build_investigation_graph(cfg, llm_override=llm_override)

    initial_state: AgentState = {
        "bug_input": text,
        "parsed_error": {},
        "messages": [],
        "hypotheses": [],
        "evidence": [],
        "step_count": 0,
        "tool_call_history": [],
        "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "open_questions": [],
        "final_report": None,
    }

    for event in graph.stream(initial_state, stream_mode="updates"):
        for node_name, node_update in event.items():
            if node_name == "parse_input":
                yield {
                    "event": "parsed_error",
                    "data": node_update.get("parsed_error", {}),
                }
            elif node_name == "investigate":
                msgs = node_update.get("messages", [])
                if msgs:
                    last = msgs[-1]
                    if getattr(last, "tool_calls", None):
                        for tc in last.tool_calls:
                            yield {
                                "event": "tool_call",
                                "tool": tc.get("name"),
                                "args": tc.get("args"),
                            }
                    elif getattr(last, "content", None):
                        yield {
                            "event": "thought",
                            "content": str(last.content),
                        }
            elif node_name == "tools":
                msgs = node_update.get("messages", [])
                for tm in msgs:
                    yield {
                        "event": "tool_result",
                        "tool": getattr(tm, "name", "tool"),
                        "result": str(tm.content)[:250] + ("..." if len(str(tm.content)) > 250 else ""),
                    }
            elif node_name == "hypothesize":
                hypos = node_update.get("hypotheses", [])
                if hypos:
                    yield {
                        "event": "hypothesis",
                        "data": hypos[-1]["hypothesis"][:300],
                    }
            elif node_name == "report":
                rep = node_update.get("final_report")
                if rep:
                    patch = extract_diff_patch(rep.suggested_fix)
                    if patch:
                        bug_match = re.search(r"BUG-\d+", text, re.IGNORECASE)
                        bug_hint = bug_match.group(0).upper() if bug_match else None
                        ver_res = verify_fix_in_temp_repo(cfg.target_repo_path, patch, bug_hint=bug_hint)
                        rep.fix_verified = ver_res.fix_verified
                        rep.fix_verification_output = ver_res.test_output[:1200]
                    save_investigation_run(
                        bug_input=text,
                        report=rep,
                        steps_taken=rep.steps_taken,
                        latency_seconds=time.time() - stream_start,
                    )
                yield {
                    "event": "final_report",
                    "report": rep,
                }
