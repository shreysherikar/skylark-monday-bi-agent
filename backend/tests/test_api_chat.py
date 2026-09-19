"""Integration tests for FastAPI endpoints (/health, /, /api/chat)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.agent.orchestrator import AgentResponse
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    """Verifies /health returns 200 with operational status."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "environment" in data


def test_root_endpoint(client: TestClient) -> None:
    """Verifies / returns 200 with API metadata."""
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "online"
    assert "name" in data


def test_chat_empty_message_rejected(client: TestClient) -> None:
    """Empty message in /api/chat returns 400 Bad Request."""
    resp = client.post("/api/chat", json={"message": "   "})
    assert resp.status_code == 400
    assert "cannot be empty" in resp.json()["detail"]


def test_chat_clarification_response(client: TestClient) -> None:
    """Ambiguous query returns 200 with needs_clarification=True and suggested options."""
    resp = client.post(
        "/api/chat",
        json={"message": "How is pipeline looking recently?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["needs_clarification"] is True
    assert len(data["suggested_options"]) > 0
    assert "recently" in data["response"].lower() or "clarify" in data["response"].lower()


def test_chat_successful_agent_flow(client: TestClient) -> None:
    """Successful agent query returns response text, tools used, and surfaced caveats."""
    mock_agent_response = AgentResponse(
        response="Total unweighted pipeline in Renewables is ₹50,000,000.",
        tools_used=["get_pipeline_summary"],
        caveats=["75% of deals lack Closure Probability."],
        needs_clarification=False,
    )

    with patch("app.main.AgentOrchestrator") as MockOrchestrator:
        mock_instance = MagicMock()
        mock_instance.ask.return_value = mock_agent_response
        MockOrchestrator.return_value = mock_instance

        resp = client.post(
            "/api/chat",
            json={"message": "What is the pipeline in Renewables?"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["response"] == mock_agent_response.response
        assert data["tools_used"] == ["get_pipeline_summary"]
        assert len(data["caveats"]) == 1
        assert data["needs_clarification"] is False


def test_chat_llm_failure_returns_503(client: TestClient) -> None:
    """Regression: an LLM provider failure must surface as 503, not a raw 500."""
    from app.agent.orchestrator import AgentLLMError

    with patch("app.main.AgentOrchestrator") as MockOrchestrator:
        mock_instance = MagicMock()
        mock_instance.ask.side_effect = AgentLLMError("The reasoning engine is unavailable.")
        MockOrchestrator.return_value = mock_instance

        resp = client.post(
            "/api/chat",
            json={"message": "What is our total outstanding receivables?"},
        )

    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"].lower()


def test_chat_monday_failure_returns_503(client: TestClient) -> None:
    """A Monday.com API failure must surface as 503, not a raw 500."""
    from app.monday_mcp.client import MondayAuthenticationError

    with patch("app.main.AgentOrchestrator") as MockOrchestrator:
        mock_instance = MagicMock()
        mock_instance.ask.side_effect = MondayAuthenticationError("Authentication failed (401)")
        MockOrchestrator.return_value = mock_instance

        resp = client.post("/api/chat", json={"message": "How is our pipeline?"})

    assert resp.status_code == 503
    assert "monday" in resp.json()["detail"].lower()


@pytest.mark.parametrize("endpoint", ["/api/overview", "/api/quality"])
def test_metric_endpoints_return_503_on_monday_failure(client: TestClient, endpoint: str) -> None:
    """Regression: /api/overview and /api/quality returned raw 500s when Monday was down."""
    from app.monday_mcp.client import MondayAuthenticationError

    with patch(
        "app.agent.tools._load_normalized_deals",
        side_effect=MondayAuthenticationError("Authentication failed (401)"),
    ):
        resp = client.get(endpoint)

    assert resp.status_code == 503, f"{endpoint} should degrade to 503, got {resp.status_code}"
    assert "monday" in resp.json()["detail"].lower()


def test_chat_internal_error_handling(client: TestClient) -> None:
    """Unhandled exceptions in orchestrator return 500 Internal Server Error."""
    with patch("app.main.AgentOrchestrator") as MockOrchestrator:
        mock_instance = MagicMock()
        mock_instance.ask.side_effect = RuntimeError("Simulated internal error")
        MockOrchestrator.return_value = mock_instance

        resp = client.post(
            "/api/chat",
            json={"message": "What is our revenue?"},
        )
        assert resp.status_code == 500
        assert "Simulated internal error" in resp.json()["detail"]


def test_overview_endpoint(client: TestClient) -> None:
    """Verifies /api/overview returns deterministic pipeline, revenue, and delivery metrics."""
    resp = client.get("/api/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert "pipeline" in data
    assert "revenue" in data
    assert "delivery" in data
    assert data["revenue"]["total_work_orders"] == 176
    assert data["pipeline"]["total_deals"] == 344


def test_quality_endpoint(client: TestClient) -> None:
    """Verifies /api/quality returns data quality audit metrics."""
    resp = client.get("/api/quality")
    assert resp.status_code == 200
    data = resp.json()
    assert "work_orders" in data
    assert "deals" in data
    assert data["work_orders"]["total_rows"] == 176
    assert data["deals"]["total_rows"] == 344

