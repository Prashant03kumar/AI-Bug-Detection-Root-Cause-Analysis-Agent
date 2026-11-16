"""Request and response models for the BugSleuth FastAPI backend."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class InvestigateOptions(BaseModel):
    """Optional tuning parameters for the investigation agent."""

    max_steps: Optional[int] = Field(
        default=None,
        ge=1,
        le=50,
        description="Override maximum reasoning steps",
    )
    repo_path: Optional[str] = Field(
        default=None,
        description="Override target repository path to analyze",
    )


class InvestigateRequest(BaseModel):
    """Payload for POST /investigate endpoint."""

    bug_text: str = Field(
        ...,
        min_length=5,
        description="Error message, stack trace, or failure description to investigate",
    )
    options: Optional[InvestigateOptions] = Field(
        default=None,
        description="Optional investigation tuning options",
    )


class IndexStatusResponse(BaseModel):
    """Response model for GET /index/status."""

    status: Literal["idle", "indexing", "completed", "failed"] = Field(
        ..., description="Current indexer state"
    )
    code_chunks_count: int = Field(default=0, description="Total indexed code chunks")
    tickets_count: int = Field(default=0, description="Total indexed historical tickets")
    target_repo: str = Field(..., description="Target repository path analyzed")
    last_rebuilt: Optional[str] = Field(default=None, description="ISO timestamp of last reindex")
    last_summary: Optional[Dict[str, Any]] = Field(
        default=None, description="Detailed statistics from last rebuild"
    )
    error: Optional[str] = Field(default=None, description="Error message if indexing failed")


class RebuildIndexResponse(BaseModel):
    """Response model for POST /index/rebuild."""

    status: str = Field(..., description="Status of rebuild request: started or already_in_progress")
    message: str = Field(..., description="Descriptive status message")


class HealthResponse(BaseModel):
    """Response model for GET /health."""

    status: Literal["ok", "degraded"] = Field(..., description="Overall service operational health")
    checks: Dict[str, Any] = Field(..., description="Detailed status breakdown of components")
    timestamp: str = Field(..., description="ISO 8601 server timestamp")


class SampleBugItem(BaseModel):
    """Metadata and raw text for a sample test bug."""

    id: str = Field(..., description="Sample bug directory identifier")
    title: str = Field(..., description="Brief symptom title or first error line")
    error_text: str = Field(..., description="Content of error.txt")
    log_snippet: Optional[str] = Field(
        default=None, description="Snippet or full content of app.log"
    )


class SampleBugsResponse(BaseModel):
    """Response model for GET /bugs."""

    bugs: List[SampleBugItem] = Field(
        default_factory=list, description="List of available sample bugs"
    )
