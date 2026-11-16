"""Domain and schema models for BugSleuth."""

from typing import Any, Dict, List, Optional
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
