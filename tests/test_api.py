"""Tests for FastAPI backend endpoints using FastAPI TestClient with mocked agent."""

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from app.api.main import app, rate_limiter
from app.models import Evidence, RootCauseReport

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Ensure rate limiter records are cleared before each test."""
    rate_limiter._history.clear()


def test_health_endpoint():
    """Verify /health returns operational checks and status."""
    response = client.get("/health")
    assert response.status_code in (200, 503)
    data = response.json()
    assert "status" in data
    assert "checks" in data
    assert "google_api_key_configured" in data["checks"]
    assert "target_repo_exists" in data["checks"]


def test_list_bugs_endpoint():
    """Verify /bugs discovers and returns sample bug scenarios from data/bugs."""
    response = client.get("/bugs")
    assert response.status_code == 200
    data = response.json()
    assert "bugs" in data
    assert isinstance(data["bugs"], list)
    if data["bugs"]:
        first = data["bugs"][0]
        assert "id" in first
        assert "title" in first
        assert "error_text" in first


def test_index_status_endpoint():
    """Verify /index/status returns collection counts and repository path."""
    response = client.get("/index/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "code_chunks_count" in data
    assert "tickets_count" in data
    assert "target_repo" in data


def test_trigger_index_rebuild():
    """Verify POST /index/rebuild triggers background re-indexing task."""
    with patch("app.api.main.build_code_index") as mock_code_idx, patch(
        "app.api.main.build_ticket_index"
    ) as mock_ticket_idx:
        mock_code_idx.return_value = {"files_indexed": 5, "chunks_embedded": 20}
        mock_ticket_idx.return_value = {"tickets_indexed": 10}

        response = client.post("/index/rebuild")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("started", "already_in_progress")
        assert "message" in data


def test_investigate_endpoint_success():
    """Verify POST /investigate returns structured RootCauseReport."""
    dummy_report = RootCauseReport(
        summary="Test error explanation",
        root_cause="A mock null reference was observed during execution.",
        bug_type="null_reference",
        file="shopapp/mock_module.py",
        function="mock_function",
        line_start=10,
        line_end=15,
        introducing_commit="aabbcc112233",
        evidence=[
            Evidence(
                kind="code",
                source="shopapp/mock_module.py:12",
                snippet="mock code",
                why_relevant="Mock observation",
            )
        ],
        suggested_fix="Check if variable is not None before access.",
        confidence=0.95,
        confidence_reasoning="High confidence from unit test trace.",
        steps_taken=["Parsed error", "Located crash frame", "Formed hypothesis"],
        open_questions=[],
        grounded=True,
        validation_notes=["Passed AST validation"],
    )

    with patch("app.api.main.investigate_bug", return_value=dummy_report):
        payload = {
            "bug_text": "TypeError: 'NoneType' object is not subscriptable at line 12",
            "options": {"max_steps": 8},
        }
        response = client.post("/investigate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["summary"] == "Test error explanation"
        assert data["file"] == "shopapp/mock_module.py"
        assert data["function"] == "mock_function"
        assert data["confidence"] == 0.95
        assert data["grounded"] is True


def test_investigate_endpoint_validation_error():
    """Verify POST /investigate returns 422 on invalid/empty bug_text."""
    response = client.post("/investigate", json={"bug_text": "err"})
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


def test_investigate_stream_endpoint():
    """Verify GET /investigate/stream streams Server-Sent Events."""
    mock_events = [
        {"event": "parsed_error", "data": {"error_type": "TypeError", "message": "None error"}},
        {"event": "thought", "content": "Analyzing repository AST..."},
        {"event": "tool_call", "tool": "read_file", "args": {"path": "shopapp/mock_module.py"}},
        {
            "event": "final_report",
            "report": RootCauseReport(
                summary="Streamed test summary",
                root_cause="Streamed root cause",
                bug_type="mock_bug",
                file="shopapp/mock.py",
                function="test_fn",
                line_start=1,
                line_end=5,
                suggested_fix="Fix mock issue",
                confidence=1.0,
                confidence_reasoning="Confirmed",
                grounded=True,
            ),
        },
    ]

    with patch("app.api.main.stream_investigation", return_value=iter(mock_events)):
        response = client.get(
            "/investigate/stream",
            params={"bug_text": "Sample error message with sufficient length"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = response.text
        assert "data: " in body
        assert "parsed_error" in body
        assert "final_report" in body
        assert "completed" in body


def test_rate_limiting_enforcement():
    """Verify in-memory rate limiter returns 429 when request threshold is exceeded."""
    # Temporarily set rate limit to 3 requests
    original_max = rate_limiter.max_requests
    rate_limiter.max_requests = 3
    try:
        # First 3 requests should pass validation
        for _ in range(3):
            res = client.post("/investigate", json={"bug_text": "abc"})
            assert res.status_code == 422  # Handled before rate limit blocks

        # 4th request must be blocked by rate limiting middleware with 429
        blocked_res = client.post("/investigate", json={"bug_text": "abc"})
        assert blocked_res.status_code == 429
        assert "Rate limit exceeded" in blocked_res.json()["detail"]
    finally:
        rate_limiter.max_requests = original_max
