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


class RootCauseAnalysis(BaseModel):
    """Structured output report produced by the agent."""

    root_cause: str = Field(..., description="Explanation of why the bug occurred")
    file_path: Optional[str] = Field(default=None, description="Primary offending file")
    line_number: Optional[int] = Field(default=None, description="Primary offending line number")
    evidence: List[str] = Field(
        default_factory=list,
        description="Evidence supporting hypothesis (code, commits, logs)",
    )
    suggested_fix: str = Field(..., description="Code snippet or description of the fix")
    confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0",
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
