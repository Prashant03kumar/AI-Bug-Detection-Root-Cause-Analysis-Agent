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


class VerifyFixRequest(BaseModel):
    """Payload for POST /verify_fix."""

    patch: str = Field(..., min_length=10, description="Unified diff patch content")
    repo_path: Optional[str] = Field(
        default=None, description="Target repository path override"
    )
    bug_hint: Optional[str] = Field(
        default=None, description="Optional bug identifier or scenario hint"
    )


class VerifyFixResponse(BaseModel):
    """Response model for POST /verify_fix."""

    patch_applied: bool = Field(..., description="Whether git apply succeeded")
    fix_verified: bool = Field(..., description="Whether tests passed cleanly in sandbox")
    test_output: str = Field(..., description="Captured test runner output")
    execution_time_seconds: float = Field(..., description="Sandbox execution duration in seconds")
    error_message: Optional[str] = Field(default=None, description="Error details if verification failed")


class CloneRepoRequest(BaseModel):
    """Payload for POST /repo/clone."""

    repo_url: str = Field(..., min_length=8, description="Git clone URL (HTTPS/SSH)")
    workspace_dir: Optional[str] = Field(
        default="./workspace", description="Local workspace destination directory"
    )


class CloneRepoResponse(BaseModel):
    """Response model for POST /repo/clone."""

    status: str = Field(..., description="Clone result: success or error")
    cloned_path: str = Field(..., description="Local path to cloned repository")
    message: str = Field(..., description="Status description")

