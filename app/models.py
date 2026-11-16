"""Domain and schema models for BugSleuth."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class BugReportInput(BaseModel):
    """Input payload representing a bug report, error log, or stack trace."""

    title: Optional[str] = Field(default=None, description="Short summary or title of the bug")
    raw_input: str = Field(..., description="Raw error message, stack trace, or bug description")
    target_repo_path: Optional[str] = Field(
        default=None,
        description="Path to target repository to analyze",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context such as environment or reproduction steps",
    )


class Evidence(BaseModel):
    """Specific piece of supporting evidence gathered during investigation."""

    kind: Literal["code", "log", "commit", "ticket", "diff"] = Field(
        ..., description="Type of evidence"
    )
    source: str = Field(
        ..., description="Source reference e.g. 'shopapp/users.py:38' or commit hash"
    )
    snippet: str = Field(..., description="Excerpt or code snippet")
    why_relevant: str = Field(..., description="Explanation of why this supports the hypothesis")


class RootCauseReport(BaseModel):
    """Structured final investigation report produced by the agent."""

    summary: str = Field(..., description="High-level summary of the bug and failure mode")
    root_cause: str = Field(
        ..., description="In-depth explanation of the underlying root cause mechanism"
    )
    bug_type: str = Field(
        ...,
        description="Classification category e.g. none_undefined_access, off_by_one, wrong_operator",
    )
    file: str = Field(..., description="Offending file relative path in repository")
    function: str = Field(..., description="Offending function or method name")
    line_start: int = Field(..., ge=1, description="Starting line number of root cause")
    line_end: int = Field(..., ge=1, description="Ending line number of root cause")
    introducing_commit: Optional[str] = Field(
        default=None,
        description="Commit hash that introduced the bug, if identified",
    )
    evidence: List[Evidence] = Field(
        default_factory=list,
        description="List of evidence supporting this conclusion",
    )
    suggested_fix: str = Field(
        ..., description="Recommended fix explanation and optional unified-diff patch"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0"
    )
    confidence_reasoning: str = Field(
        ..., description="Justification for the confidence score"
    )
    steps_taken: List[str] = Field(
        default_factory=list,
        description="Chronological log of investigative steps taken",
    )
    open_questions: List[str] = Field(
        default_factory=list,
        description="Unresolved ambiguities or caveats",
    )
    grounded: bool = Field(
        default=False,
        description="Whether the report passed automated post-hoc validation",
    )
    validation_notes: List[str] = Field(
        default_factory=list,
        description="Automated validation findings",
    )
    fix_verified: Optional[bool] = Field(
        default=None,
        description="Whether the suggested fix was verified in an isolated sandbox clone",
    )
    fix_verification_output: Optional[str] = Field(
        default=None,
        description="Execution output from verifying the suggested fix patch",
    )


class CodeChunk(BaseModel):
    """Pydantic model representing an AST-indexed code segment."""

    id: str = Field(..., description="Unique chunk identifier")
    text: str = Field(..., description="Embedded code representation with header")
    file_path: str = Field(..., description="Relative file path from repository root")
    symbol_name: str = Field(..., description="Symbol identifier e.g. Class.method or function")
    kind: Literal["function", "method", "class", "module", "window"] = Field(
        ..., description="AST chunk classification"
    )
    start_line: int = Field(..., ge=1, description="Starting line in source file")
    end_line: int = Field(..., ge=1, description="Ending line in source file")
    is_test: bool = Field(default=False, description="Whether this chunk belongs to test code")
    imports_used: List[str] = Field(
        default_factory=list, description="List of module-level imports referenced in chunk"
    )
    calls_made: List[str] = Field(
        default_factory=list, description="Function/method calls made inside this chunk"
    )


class TicketChunk(BaseModel):
    """Representation of an indexed historical bug ticket."""

    id: str = Field(..., description="Ticket identifier e.g. TICK-101")
    title: str = Field(..., description="Ticket title")
    description: str = Field(..., description="Bug description and symptoms")
    resolution: str = Field(..., description="Fix or resolution explanation")
    files_touched: List[str] = Field(
        default_factory=list, description="Files modified in fix"
    )
    text: str = Field(..., description="Formatted text for embedding")
