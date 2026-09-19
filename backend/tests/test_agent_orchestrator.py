"""Unit and integration tests for Groq AgentOrchestrator."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from app.agent.orchestrator import AgentOrchestrator
from app.agent.tools import get_groq_tools
from app.config import settings


def test_orchestrator_uses_configured_groq_model() -> None:
    """Verifies that orchestrator uses the configured settings.groq_model, not a hardcoded model."""
    orchestrator = AgentOrchestrator()
    assert orchestrator.model == settings.groq_model


def test_clarification_path_bypasses_llm_call() -> None:
    """Ambiguous query immediately returns clarification without invoking Groq API."""
    mock_client = MagicMock()
    orchestrator = AgentOrchestrator(client=mock_client)

    resp = orchestrator.ask("How are deals looking recently?")
    assert resp.needs_clarification is True
    assert "recently" in resp.response.lower() or "clarify" in resp.response.lower()
    assert len(resp.tools_used) == 0
    # LLM must NOT be called on ambiguous query
    mock_client.chat.completions.create.assert_not_called()


def test_missing_groq_api_key_raises_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing GROQ_API_KEY raises a descriptive ValueError."""
    monkeypatch.setattr(settings, "groq_api_key", "")
    orchestrator = AgentOrchestrator(client=None)

    with pytest.raises(ValueError, match="GROQ_API_KEY is not configured"):
        _ = orchestrator.client


def test_get_groq_tools_schema() -> None:
    """Verifies that get_groq_tools returns valid OpenAI/Groq function schemas."""
    tools = get_groq_tools()
    assert len(tools) == 6
    for t in tools:
        assert t["type"] == "function"
        assert "name" in t["function"]
        assert "description" in t["function"]
        assert "parameters" in t["function"]
        assert t["function"]["parameters"]["type"] == "object"


def test_groq_multi_turn_tool_use_loop() -> None:
    """Verifies multi-turn tool execution loop with mocked Groq SDK."""
    mock_client = MagicMock()

    # Turn 1: Model calls get_revenue_summary
    mock_tc = MagicMock()
    mock_tc.id = "call_groq_rev_1"
    mock_tc.function.name = "get_revenue_summary"
    mock_tc.function.arguments = json.dumps({"sector": "Mining"})

    msg1 = MagicMock()
    msg1.content = None
    msg1.tool_calls = [mock_tc]

    turn1_response = MagicMock()
    turn1_response.choices = [MagicMock(message=msg1)]

    # Turn 2: Model returns final text with answer
    msg2 = MagicMock()
    msg2.content = "The total revenue for Mining is ₹1,000,000 with 5 work orders."
    msg2.tool_calls = None

    turn2_response = MagicMock()
    turn2_response.choices = [MagicMock(message=msg2)]

    mock_client.chat.completions.create.side_effect = [turn1_response, turn2_response]

    orchestrator = AgentOrchestrator(client=mock_client)
    res = orchestrator.ask("What is our revenue in Mining?")

    assert res.needs_clarification is False
    assert "get_revenue_summary" in res.tools_used
    assert "total revenue for Mining" in res.response
    assert mock_client.chat.completions.create.call_count == 2


def test_currency_sanitization_helper() -> None:
    """Regression test: verifies that sanitize_currency_symbols replaces '$' with '₹' and 'USD' with 'INR'."""
    from app.agent.orchestrator import sanitize_currency_symbols

    raw_text = (
        "Active Pipeline: $28,138,196.33 ($ 16.6M weighted)\n"
        "Won revenue: $5,000.00 USD total."
    )
    sanitized = sanitize_currency_symbols(raw_text)

    assert "$28" not in sanitized
    assert "$ 16" not in sanitized
    assert "$5" not in sanitized
    assert "₹28,138,196.33" in sanitized
    assert "₹16.6M" in sanitized
    assert "₹5,000.00" in sanitized
    assert "INR" in sanitized
    assert "USD" not in sanitized


def _make_groq_bad_request(detail: str):
    """Builds a real groq.BadRequestError so `except BadRequestError` matches."""
    import httpx
    from groq import BadRequestError

    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(400, request=request, json={"error": {"message": detail}})
    return BadRequestError(detail, response=response, body=None)


TOOL_VALIDATION_DETAIL = (
    "tool call validation failed: parameters for tool get_revenue_summary did not match "
    "schema: errors: [`/sector`: expected string, but got null]"
)


def test_invalid_tool_call_is_retried_then_succeeds() -> None:
    """Regression: an invalid tool call must be retried rather than surfaced as a 500.

    Groq returns HTTP 400 `tool_use_failed` when the model emits `null` for an optional
    non-nullable argument. That previously made
    "What is our total outstanding receivables?" fail outright.
    """
    mock_client = MagicMock()

    err = _make_groq_bad_request(TOOL_VALIDATION_DETAIL)

    msg = MagicMock()
    msg.content = "Total outstanding receivables are ₹36,291,748.87."
    msg.tool_calls = None
    ok_response = MagicMock()
    ok_response.choices = [MagicMock(message=msg)]

    mock_client.chat.completions.create.side_effect = [err, ok_response]

    orchestrator = AgentOrchestrator(client=mock_client)
    res = orchestrator.ask("What is our total outstanding receivables?")

    assert res.needs_clarification is False
    assert "36,291,748" in res.response
    assert mock_client.chat.completions.create.call_count == 2


def test_persistent_invalid_tool_call_raises_agent_llm_error() -> None:
    """When retries are exhausted the orchestrator raises AgentLLMError (mapped to 503)."""
    from app.agent.orchestrator import AgentLLMError

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = _make_groq_bad_request(
        TOOL_VALIDATION_DETAIL
    )

    orchestrator = AgentOrchestrator(client=mock_client)

    with pytest.raises(AgentLLMError):
        orchestrator.ask("What is our total outstanding receivables?")

    # One retry after the initial failure.
    assert mock_client.chat.completions.create.call_count == 2


def test_provider_outage_raises_agent_llm_error() -> None:
    """A generic provider failure becomes a controlled AgentLLMError, never a raw exception."""
    from app.agent.orchestrator import AgentLLMError

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = ConnectionError("network unreachable")

    orchestrator = AgentOrchestrator(client=mock_client)

    with pytest.raises(AgentLLMError):
        orchestrator.ask("How is our pipeline looking in Renewables?")


def test_system_prompt_mandates_inr_currency() -> None:
    """Verifies that SYSTEM_PROMPT explicitly mandates INR (₹) and strictly forbids dollar ($)."""
    from app.agent.orchestrator import SYSTEM_PROMPT

    assert "Indian Rupees" in SYSTEM_PROMPT
    assert "₹" in SYSTEM_PROMPT
    assert "$" in SYSTEM_PROMPT
    assert "CURRENCY FORMATTING" in SYSTEM_PROMPT


def test_regression_preventing_dollar_mislabeling_in_llm_response() -> None:
    """Regression test: when LLM output mistakenly includes '$' for monetary values, orchestrator normalizes it to '₹'."""
    mock_client = MagicMock()

    # Model returns text containing accidental $ symbols for INR data
    msg = MagicMock()
    msg.content = (
        "**Renewables Pipeline Snapshot**:\n"
        "- Unweighted Value: $28,138,196.33\n"
        "- Weighted Value: $16,638,239.27\n"
        "- Won Deal Value: $16,846,373.37\n"
    )
    msg.tool_calls = None

    resp = MagicMock()
    resp.choices = [MagicMock(message=msg)]
    mock_client.chat.completions.create.return_value = resp

    orchestrator = AgentOrchestrator(client=mock_client)
    res = orchestrator.ask("How is our deal pipeline looking in Renewables?")

    assert "$" not in res.response
    assert "₹28,138,196.33" in res.response
    assert "₹16,638,239.27" in res.response
    assert "₹16,846,373.37" in res.response



