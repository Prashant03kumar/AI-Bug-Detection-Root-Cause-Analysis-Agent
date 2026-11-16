"""FastAPI application for BugSleuth autonomous bug detection and root-cause analysis."""

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
from typing import Any, Dict, Generator, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from app.agent.fix_verifier import verify_fix_in_temp_repo
from app.agent.graph import investigate_bug, stream_investigation
from app.api.models import (
    CloneRepoRequest,
    CloneRepoResponse,
    HealthResponse,
    IndexStatusResponse,
    InvestigateOptions,
    InvestigateRequest,
    RebuildIndexResponse,
    SampleBugItem,
    SampleBugsResponse,
    VerifyFixRequest,
    VerifyFixResponse,
)
from app.config import Settings, get_settings
from app.indexing.indexer import (
    CODE_COLLECTION_NAME,
    TICKETS_COLLECTION_NAME,
    build_code_index,
    build_ticket_index,
    get_chroma_client,
)
from app.indexing.repo_loader import clone_github_repo
from app.logging_setup import get_logger
from app.models import RootCauseReport

logger = get_logger("api.main")


class InMemoryRateLimiter:
    """Sliding-window in-memory rate limiter per client IP."""

    def __init__(self, max_requests: int = 60, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, client_ip: str) -> bool:
        """Check whether the client IP has exceeded the allowed request window."""
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            active_requests = [t for t in self._history[client_ip] if t > cutoff]
            if len(active_requests) >= self.max_requests:
                self._history[client_ip] = active_requests
                return False
            active_requests.append(now)
            self._history[client_ip] = active_requests
            return True


class IndexingStateManager:
    """Thread-safe state manager for asynchronous index rebuilding."""

    def __init__(self):
        self._lock = threading.Lock()
        self.status: str = "idle"  # idle | indexing | completed | failed
        self.last_rebuilt: Optional[str] = None
        self.last_summary: Optional[Dict[str, Any]] = None
        self.last_error: Optional[str] = None

    def start_indexing(self) -> bool:
        """Attempt to transition into indexing state. Returns False if already busy."""
        with self._lock:
            if self.status == "indexing":
                return False
            self.status = "indexing"
            self.last_error = None
            return True

    def mark_completed(self, summary: Dict[str, Any]) -> None:
        """Transition into completed state with summary metrics."""
        with self._lock:
            self.status = "completed"
            self.last_rebuilt = datetime.now(timezone.utc).isoformat()
            self.last_summary = summary
            self.last_error = None

    def mark_failed(self, error: str) -> None:
        """Transition into failed state with error message."""
        with self._lock:
            self.status = "failed"
            self.last_error = error

    def get_status(self, settings: Settings) -> IndexStatusResponse:
        """Query Chroma and return current status snapshot."""
        code_chunks_count = 0
        tickets_count = 0

        storage_dir = Path(settings.chroma_dir).resolve()
        if storage_dir.exists():
            try:
                client = get_chroma_client(storage_dir)
                try:
                    c1 = client.get_collection(name=CODE_COLLECTION_NAME)
                    code_chunks_count = c1.count()
                except Exception:
                    pass
                try:
                    c2 = client.get_collection(name=TICKETS_COLLECTION_NAME)
                    tickets_count = c2.count()
                except Exception:
                    pass
            except Exception as exc:
                logger.warning("Error querying Chroma collections for status: %s", exc)

        with self._lock:
            return IndexStatusResponse(
                status=self.status,  # type: ignore[arg-type]
                code_chunks_count=code_chunks_count,
                tickets_count=tickets_count,
                target_repo=settings.target_repo_path,
                last_rebuilt=self.last_rebuilt,
                last_summary=self.last_summary,
                error=self.last_error,
            )


# Initialize shared application state
rate_limiter = InMemoryRateLimiter(max_requests=60, window_seconds=60.0)
index_state_manager = IndexingStateManager()

app = FastAPI(
    title="BugSleuth API",
    description="Autonomous AI Bug Detection & Root-Cause Analysis API powered by LangGraph and Gemini",
    version="1.0.0",
)

# Enable CORS for local development (UI, dev servers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limiting_middleware(request: Request, call_next):
    """Enforce basic per-IP rate limiting while allowing monitoring routes."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    path = request.url.path

    # Bypass rate limiting on monitoring, documentation, and read-only status routes
    exempt_paths = {"/health", "/index/status", "/bugs", "/docs", "/openapi.json", "/redoc"}
    if path not in exempt_paths:
        if not rate_limiter.is_allowed(client_ip):
            logger.warning("Rate limit exceeded for client %s on %s", client_ip, path)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Maximum 60 requests per minute allowed."},
            )

    response = await call_next(request)
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return clean JSON error details for Pydantic validation failures."""
    logger.warning("Validation error on %s: %s", request.url.path, exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Return clean JSON response for unhandled server exceptions."""
    logger.error("Unhandled error processing %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Internal server error: {str(exc)}"},
    )


def _execute_rebuild_task(settings: Settings) -> None:
    """Synchronous worker function executed in background for index rebuilding."""
    logger.info("Starting background re-indexing task for repo: %s", settings.target_repo_path)
    try:
        code_summary = build_code_index(settings=settings, incremental=False)
        ticket_summary = build_ticket_index(settings=settings)
        combined_summary = {
            "code_index": code_summary,
            "ticket_index": ticket_summary,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        index_state_manager.mark_completed(combined_summary)
        logger.info("Background re-indexing completed successfully.")
    except Exception as exc:
        logger.error("Background re-indexing failed: %s", exc, exc_info=True)
        index_state_manager.mark_failed(str(exc))


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Comprehensive health check verifying Gemini API key, repository, and index state."""
    settings = get_settings()
    now_iso = datetime.now(timezone.utc).isoformat()

    has_api_key = bool(settings.google_api_key and settings.google_api_key.strip())
    repo_path = Path(settings.target_repo_path).resolve()
    repo_exists = repo_path.is_dir()
    chroma_path = Path(settings.chroma_dir).resolve()
    chroma_dir_exists = chroma_path.is_dir()

    code_chunks_count = 0
    tickets_count = 0
    if chroma_dir_exists:
        try:
            client = get_chroma_client(chroma_path)
            try:
                code_chunks_count = client.get_collection(CODE_COLLECTION_NAME).count()
            except Exception:
                pass
            try:
                tickets_count = client.get_collection(TICKETS_COLLECTION_NAME).count()
            except Exception:
                pass
        except Exception as exc:
            logger.warning("Could not inspect Chroma collections during health check: %s", exc)

    checks = {
        "google_api_key_configured": has_api_key,
        "target_repo_exists": repo_exists,
        "target_repo_path": str(repo_path),
        "chroma_dir_exists": chroma_dir_exists,
        "code_chunks_count": code_chunks_count,
        "tickets_count": tickets_count,
        "llm_model": settings.llm_model,
        "embedding_provider": settings.embedding_provider,
    }

    is_healthy = has_api_key and repo_exists and (code_chunks_count > 0)
    health_status: str = "ok" if is_healthy else "degraded"

    if not has_api_key:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=HealthResponse(status="degraded", checks=checks, timestamp=now_iso).model_dump(),
        )  # type: ignore[return-value]

    return HealthResponse(status=health_status, checks=checks, timestamp=now_iso)  # type: ignore[arg-type]


@app.get("/bugs", response_model=SampleBugsResponse)
def list_sample_bugs() -> SampleBugsResponse:
    """Dynamically scan data/bugs directory and return available sample bug scenarios."""
    bugs_dir = Path("data") / "bugs"
    sample_bugs: List[SampleBugItem] = []

    if bugs_dir.is_dir():
        for item in sorted(bugs_dir.iterdir(), key=lambda p: p.name):
            if item.is_dir():
                err_path = item / "error.txt"
                log_path = item / "app.log"
                err_text = err_path.read_text(encoding="utf-8") if err_path.is_file() else ""
                log_text = log_path.read_text(encoding="utf-8") if log_path.is_file() else None

                # Derive descriptive title from the first non-traceback line
                title = item.name
                for line in err_text.splitlines():
                    cleaned = line.strip()
                    if cleaned and not cleaned.startswith("Traceback") and not cleaned.startswith("File"):
                        title = f"{item.name}: {cleaned[:80]}"
                        break

                sample_bugs.append(
                    SampleBugItem(
                        id=item.name,
                        title=title,
                        error_text=err_text,
                        log_snippet=log_text[:2500] if log_text else None,
                    )
                )

    return SampleBugsResponse(bugs=sample_bugs)


@app.get("/index/status", response_model=IndexStatusResponse)
def get_index_status() -> IndexStatusResponse:
    """Return current indexing status, collection counts, and last rebuild summary."""
    settings = get_settings()
    return index_state_manager.get_status(settings)


@app.post("/index/rebuild", response_model=RebuildIndexResponse)
def trigger_index_rebuild(background_tasks: BackgroundTasks) -> RebuildIndexResponse:
    """Trigger an asynchronous full re-indexing of repository code and historical tickets."""
    settings = get_settings()
    started = index_state_manager.start_indexing()
    if not started:
        return RebuildIndexResponse(
            status="already_in_progress",
            message="An index rebuild task is currently already running.",
        )

    background_tasks.add_task(_execute_rebuild_task, settings)
    return RebuildIndexResponse(
        status="started",
        message="Index rebuild task has been scheduled in the background.",
    )


@app.post("/investigate", response_model=RootCauseReport)
async def investigate_endpoint(request: InvestigateRequest) -> RootCauseReport:
    """Synchronously execute the LangGraph investigation workflow and return the structured report."""
    settings = get_settings()
    if request.options:
        overrides: Dict[str, Any] = {}
        if request.options.max_steps is not None:
            overrides["max_agent_steps"] = request.options.max_steps
        if request.options.repo_path is not None:
            overrides["target_repo_path"] = request.options.repo_path
        if overrides:
            settings = settings.model_copy(update=overrides)

    try:
        # Run investigation in a worker thread so the async event loop is not blocked
        report = await asyncio.to_thread(investigate_bug, request.bug_text, settings=settings)
        return report
    except Exception as exc:
        logger.error("Investigation failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Investigation workflow failed: {str(exc)}",
        )


@app.get("/investigate/stream")
def stream_investigate_endpoint(
    bug_text: str = Query(..., min_length=5, description="Bug error text to investigate"),
    max_steps: Optional[int] = Query(default=None, ge=1, le=50, description="Max reasoning steps"),
    repo_path: Optional[str] = Query(default=None, description="Target repo path override"),
) -> StreamingResponse:
    """Stream Server-Sent Events (SSE) representing real-time steps and the final report."""
    settings = get_settings()
    overrides: Dict[str, Any] = {}
    if max_steps is not None:
        overrides["max_agent_steps"] = max_steps
    if repo_path is not None:
        overrides["target_repo_path"] = repo_path
    if overrides:
        settings = settings.model_copy(update=overrides)

    def event_generator() -> Generator[str, None, None]:
        try:
            logger.info("Starting SSE investigation stream for %d chars input", len(bug_text))
            for step_event in stream_investigation(bug_text, settings=settings):
                # Ensure model objects in final_report event are properly serialized
                if step_event.get("event") == "final_report" and hasattr(step_event.get("report"), "model_dump"):
                    serialized = dict(step_event)
                    serialized["report"] = step_event["report"].model_dump()
                    payload = json.dumps(serialized)
                else:
                    payload = json.dumps(step_event)

                yield f"data: {payload}\n\n"

            # Emit final completion marker
            yield f"data: {json.dumps({'event': 'completed'})}\n\n"
        except Exception as exc:
            logger.error("SSE stream error during investigation: %s", exc, exc_info=True)
            err_payload = json.dumps({"event": "error", "message": str(exc)})
            yield f"data: {err_payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/verify_fix", response_model=VerifyFixResponse)
async def verify_fix_endpoint(request: VerifyFixRequest) -> VerifyFixResponse:
    """Verify a suggested unified diff patch in an isolated temporary clone."""
    settings = get_settings()
    target_repo = request.repo_path or settings.target_repo_path

    try:
        result = await asyncio.to_thread(
            verify_fix_in_temp_repo,
            target_repo,
            request.patch,
            bug_hint=request.bug_hint,
        )
        return VerifyFixResponse(
            patch_applied=result.patch_applied,
            fix_verified=result.fix_verified,
            test_output=result.test_output,
            execution_time_seconds=result.execution_time_seconds,
            error_message=result.error_message,
        )
    except Exception as exc:
        logger.error("Fix verification failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Auto-fix verification failed: {str(exc)}",
        )


@app.post("/repo/clone", response_model=CloneRepoResponse)
async def clone_repo_endpoint(request: CloneRepoRequest) -> CloneRepoResponse:
    """Safely clone a remote GitHub repository into the local workspace."""
    try:
        dest_path = await asyncio.to_thread(
            clone_github_repo,
            request.repo_url,
            workspace_dir=request.workspace_dir or "./workspace",
        )
        return CloneRepoResponse(
            status="success",
            cloned_path=str(dest_path),
            message=f"Repository cloned successfully into {dest_path}",
        )
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as exc:
        logger.error("Clone failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

