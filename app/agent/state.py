"""LangGraph state representation for the BugSleuth agent."""

from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from app.models import Evidence, RootCauseReport


class Hypothesis(TypedDict):
    """An investigation hypothesis formed by the agent."""

    hypothesis: str
    status: Literal["unverified", "confirmed", "rejected"]
    supporting_evidence: List[str]
    contradicting_evidence: List[str]


class AgentState(TypedDict):
    """State tracked throughout the LangGraph agent investigation workflow."""

    bug_input: str
    parsed_error: Dict[str, Any]
    messages: Annotated[List[BaseMessage], add_messages]
    hypotheses: List[Dict[str, Any]]
    evidence: List[Evidence]
    step_count: int
    tool_call_history: List[str]
    token_usage: Dict[str, int]
    open_questions: List[str]
    final_report: Optional[RootCauseReport]
