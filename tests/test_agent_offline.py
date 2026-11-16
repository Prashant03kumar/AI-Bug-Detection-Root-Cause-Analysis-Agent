"""Offline unit tests for LangGraph investigation agent using a scripted mock LLM."""

from typing import Any, List, Optional
import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.agent.graph import build_investigation_graph, investigate_bug
from app.config import Settings
from app.models import Evidence, RootCauseReport


class ScriptedMockChatModel(BaseChatModel):
    """Deterministic scripted mock LLM that returns pre-configured responses in sequence."""

    responses: List[Any]
    call_index: int = 0

    def __init__(self, responses: List[Any], **kwargs):
        super().__init__(responses=responses, call_index=0, **kwargs)

    @property
    def _llm_type(self) -> str:
        return "scripted-mock"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult:
        if self.call_index < len(self.responses):
            resp = self.responses[self.call_index]
            self.call_index += 1
        else:
            resp = self.responses[-1]

        if isinstance(resp, BaseMessage):
            generation = ChatGeneration(message=resp)
        elif isinstance(resp, str):
            generation = ChatGeneration(message=AIMessage(content=resp))
        else:
            generation = ChatGeneration(message=AIMessage(content=str(resp)))

        return ChatResult(generations=[generation])

    def bind_tools(self, tools: Any, **kwargs: Any) -> Any:
        """Mock implementation of bind_tools returning self."""
        return self

    def with_structured_output(self, schema: Any, **kwargs: Any):
        """Mock implementation of with_structured_output."""
        parent_self = self

        class MockStructuredRunnable:
            def invoke(self, input_msgs: Any, **inner_kwargs: Any) -> RootCauseReport:
                return RootCauseReport(
                    summary="Mock investigation summary",
                    root_cause="Identified flaw in mock test",
                    bug_type="none_undefined_access",
                    file="shopapp/users.py",
                    function="get_user_notification_preference",
                    line_start=35,
                    line_end=38,
                    introducing_commit="1f3a4dfcbb5999cded20e5f972896788de55604d",
                    evidence=[
                        Evidence(
                            kind="code",
                            source="shopapp/users.py:38",
                            snippet="user['preferences'][channel]",
                            why_relevant="Direct subscript without null-check",
                        )
                    ],
                    suggested_fix="Restore null check on preferences",
                    confidence=0.95,
                    confidence_reasoning="Confirmed via mock blame and AST inspection",
                    steps_taken=["parse_input", "read_file", "git_blame"],
                    open_questions=[],
                )

        return MockStructuredRunnable()


def test_agent_graph_offline_execution():
    """Verify full graph state transitions offline from parse_input to report."""
    test_settings = Settings(
        google_api_key="mock-key",
        target_repo_path="./demo_repo",
        max_agent_steps=6,
    )

    # 1: tool call to read_file
    # 2: thought concluding investigation
    # 3: hypothesis formulation
    # 4: verification confirmation
    scripted_responses = [
        AIMessage(
            content="",
            tool_calls=[{
                "name": "read_file",
                "args": {"path": "shopapp/users.py", "start_line": 30, "end_line": 40},
                "id": "call_1",
            }],
        ),
        AIMessage(content="I have read shopapp/users.py and identified the line causing the error."),
        AIMessage(content="Hypothesis: preferences is None, raising TypeError on direct indexing."),
        AIMessage(content="Verified: git_blame confirms commit 1f3a4df introduced this line."),
    ]

    mock_llm = ScriptedMockChatModel(responses=scripted_responses)
    graph = build_investigation_graph(settings=test_settings, llm_override=mock_llm)

    state = graph.invoke({
        "bug_input": "TypeError: 'NoneType' object is not subscriptable in shopapp/users.py:38",
        "parsed_error": {},
        "messages": [],
        "hypotheses": [],
        "evidence": [],
        "step_count": 0,
        "tool_call_history": [],
        "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "open_questions": [],
        "final_report": None,
    })

    report = state.get("final_report")
    assert report is not None
    assert report.file == "shopapp/users.py"
    assert report.function == "get_user_notification_preference"
    assert report.grounded is True
    assert report.confidence > 0.8
    assert len(report.validation_notes) > 0


def test_agent_step_limit_enforcement():
    """Verify agent cleanly terminates and reports if max_agent_steps is reached."""
    # Settings with max_agent_steps = 3
    test_settings = Settings(
        google_api_key="mock-key",
        target_repo_path="./demo_repo",
        max_agent_steps=3,
    )

    # Endless tool calls loop
    infinite_tool_calls = [
        AIMessage(
            content="",
            tool_calls=[{
                "name": "read_file",
                "args": {"path": "shopapp/users.py", "start_line": 1, "end_line": 5},
                "id": "call_loop",
            }],
        )
    ] * 10

    mock_llm = ScriptedMockChatModel(responses=infinite_tool_calls)
    report = investigate_bug(
        text="TypeError in test loop",
        settings=test_settings,
        llm_override=mock_llm,
    )

    assert report is not None
    assert report.grounded is True
