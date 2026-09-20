"""Unit and integration tests for structured copilot responses and evidence traceability."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.agent.structured_response import (
    EvidenceItem,
    KpiItem,
    RiskItem,
    StructuredCopilotResponse,
    build_cross_board_structured,
    build_leadership_structured,
    build_pipeline_structured,
    build_quality_structured,
    build_revenue_structured,
    generate_structured_response,
)
from app.main import app


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def sample_revenue_output() -> dict[str, Any]:
    return {
        "total_work_orders": 176,
        "total_order_value_excl_gst": 16182186.0,
        "total_order_value_incl_gst": 19094979.48,
        "total_billed_value_excl_gst": 8806297.0,
        "total_billed_value_incl_gst": 10391430.46,
        "total_collected_value_incl_gst": 6500000.0,
        "net_receivables": 1618218.6,
        "gross_positive_receivables": 2000000.0,
        "credit_balance_total": -381781.4,
        "credit_balance_accounts_count": 3,
        "negative_billing_excl_count": 2,
        "negative_billing_excl_total": -50000.0,
        "caveats": [
            "3 credit balance accounts offset net receivables by ₹3.82 L.",
            "2 line items contain negative billing totalling -₹50.00 K.",
        ],
    }


@pytest.fixture
def sample_pipeline_output() -> dict[str, Any]:
    return {
        "total_deals": 344,
        "active_pipeline_count": 120,
        "won_deals_count": 85,
        "lost_or_dormant_count": 139,
        "active_pipeline_unweighted_value": 45000000.0,
        "active_pipeline_weighted_value": 22500000.0,
        "won_deals_total_value": 31000000.0,
        "total_recorded_value": 76000000.0,
        "deals_missing_value_count": 42,
        "deals_missing_value_pct": 12.2,
        "active_deals_missing_prob_count": 15,
        "caveats": [
            "42 deals (12.2%) lack recorded deal values.",
            "15 active deals lack closure probabilities.",
        ],
    }


@pytest.fixture
def sample_cross_board_output() -> dict[str, Any]:
    return {
        "total_work_orders": 176,
        "total_deals": 344,
        "matched_orders_count": 131,
        "unmatched_orders_count": 45,
        "link_coverage_percentage": 74.4,
        "completed_and_won_count": 80,
        "completed_with_open_deal_count": 12,
        "ongoing_or_pending_count": 39,
        "total_matched_order_value_excl_gst": 12500000.0,
        "total_matched_billed_value_excl_gst": 7100000.0,
        "commercial_risk": {
            "unclosed_deal_risk_count": 12,
            "high_risk_orders_count": 5,
            "unclosed_deal_risk_value_excl_gst": 2400000.0,
            "unclosed_deal_risk_billed_excl_gst": 1100000.0,
            "risk_orders": [
                {
                    "wo_serial": "WO-101",
                    "deal_name": "Solar Inspection Deal",
                    "deal_status": "Negotiation",
                    "deal_stage": "Stage 4",
                    "wo_execution_status": "Completed",
                    "wo_amount_excl_gst": 500000.0,
                    "wo_billed_excl_gst": 300000.0,
                    "risk_severity": "high",
                    "risk_reason": "Order completed while deal is still in Negotiation",
                }
            ],
        },
        "value_variance": {
            "matched_deals_with_value_count": 110,
            "contract_leakage_count": 8,
            "contract_leakage_value": 750000.0,
            "scope_expansion_count": 14,
            "scope_expansion_value": 1200000.0,
            "aligned_count": 88,
            "unrecorded_deal_value_count": 21,
        },
        "unlinked_exposure": {
            "unlinked_orders_count": 45,
            "unlinked_orders_value_excl_gst": 3682186.0,
            "unlinked_orders_billed_excl_gst": 1706297.0,
        },
        "caveats": [
            "45 work orders (25.6%) are unlinked to deals.",
            "12 work orders executed against unclosed deals.",
        ],
    }


# ---------------------------------------------------------------------------
# Unit Tests for Builders
# ---------------------------------------------------------------------------

def test_build_revenue_structured(sample_revenue_output: dict[str, Any]) -> None:
    """Revenue builder returns typed response with correct KPIs, risks, and evidence."""
    resp = build_revenue_structured(sample_revenue_output)

    assert isinstance(resp, StructuredCopilotResponse)
    assert "16,182,186.00" in resp.summary or "8,806,297.00" in resp.summary
    assert len(resp.kpis) >= 4

    # Check KPI labels
    labels = [k.label for k in resp.kpis]
    assert "Total Booked Scope (Excl. GST)" in labels
    assert "Total Billed Revenue (Excl. GST)" in labels
    assert "Net Outstanding Receivables" in labels

    # Check evidence traceability
    assert resp.evidence.sources == ["Work Orders"]
    assert resp.evidence.records_analyzed == 176
    assert resp.evidence.data_coverage is not None
    assert "compute_revenue_summary" in resp.evidence.calculation

    # Check risks (negative billing and credit accounts)
    risk_titles = [r.title for r in resp.risks]
    assert any("Customer Credit Balances" in t for t in risk_titles)
    assert any("Negative Billing" in t for t in risk_titles)

    # Check caveats and follow-ups
    assert len(resp.caveats) == 2
    assert len(resp.follow_ups) >= 2


def test_build_pipeline_structured(sample_pipeline_output: dict[str, Any]) -> None:
    """Pipeline builder returns typed response with probability and deal metrics."""
    resp = build_pipeline_structured(sample_pipeline_output)

    assert isinstance(resp, StructuredCopilotResponse)
    assert len(resp.kpis) >= 4
    labels = [k.label for k in resp.kpis]
    assert "Active Pipeline (Unweighted)" in labels
    assert "Active Pipeline (Probability-Weighted)" in labels
    assert "Won Deals Value" in labels
    assert "Lost / Dormant Volume" in labels

    # Evidence
    assert resp.evidence.sources == ["Deals"]
    assert resp.evidence.records_analyzed == 344
    assert "compute_pipeline_summary" in resp.evidence.calculation

    # Risks
    assert any("Missing Closure Probability" in r.title for r in resp.risks)
    assert any("Unrecorded Deal Values" in r.title for r in resp.risks)
    assert len(resp.follow_ups) >= 2


def test_build_cross_board_structured(sample_cross_board_output: dict[str, Any]) -> None:
    """Cross-board builder returns commercial risk, contract leakage, and linkage metrics."""
    resp = build_cross_board_structured(sample_cross_board_output)

    assert isinstance(resp, StructuredCopilotResponse)
    assert len(resp.kpis) >= 4

    labels = [k.label for k in resp.kpis]
    assert "Work Orders on Unclosed Deals" in labels
    assert "Contract Value Leakage" in labels
    assert "Native Connect Board Linkage" in labels

    # Check critical risk flag
    high_risks = [r for r in resp.risks if r.severity == "high"]
    assert len(high_risks) >= 1
    assert any("Execution Risk on Unclosed Deals" in r.title for r in high_risks)

    # Check evidence spans both boards
    assert "Work Orders" in resp.evidence.sources
    assert "Deals" in resp.evidence.sources
    assert "176 WOs / 344 Deals" in str(resp.evidence.records_analyzed)
    assert len(resp.follow_ups) >= 2


def test_build_leadership_structured(
    sample_pipeline_output: dict[str, Any],
    sample_revenue_output: dict[str, Any],
    sample_cross_board_output: dict[str, Any],
) -> None:
    """Leadership builder consolidates pipeline, revenue, and cross-board metrics."""
    tool_output = {
        "pipeline_kpis": sample_pipeline_output,
        "revenue_kpis": sample_revenue_output,
        "delivery_kpis": sample_cross_board_output,
    }
    resp = build_leadership_structured(tool_output)

    assert isinstance(resp, StructuredCopilotResponse)
    assert "Leadership Briefing" in resp.summary
    assert len(resp.kpis) >= 4

    labels = [k.label for k in resp.kpis]
    assert "Active Pipeline (Unweighted)" in labels
    assert "Billed Revenue (Excl. GST)" in labels
    assert "Net Outstanding Receivables" in labels
    assert "Connect Board Link Coverage" in labels

    assert "Work Orders" in resp.evidence.sources
    assert "Deals" in resp.evidence.sources
    assert len(resp.risks) >= 1


def test_build_quality_structured() -> None:
    """Data quality builder summarizes null rates, schema integrity, and negative metrics."""
    tool_output = {
        "work_orders": {
            "total_rows": 176,
            "fully_null_columns": ["col_extra_1", "col_extra_2"],
            "negative_metrics": {
                "amount_receivable_neg_count": 3,
                "amount_to_be_billed_excl_neg_count": 2,
            },
        },
        "deals": {
            "total_rows": 344,
            "core_null_rates": {
                "deal_value_null_rate": 0.122,
                "closure_probability_null_rate": 0.15,
            },
        },
        "caveats": {
            "negative_billing": "2 work orders contain negative billing",
            "missing_values": "42 deals lack value",
        },
    }
    resp = build_quality_structured(tool_output)

    assert isinstance(resp, StructuredCopilotResponse)
    assert len(resp.kpis) >= 3
    assert len(resp.risks) >= 1
    assert "Work Orders" in resp.evidence.sources
    assert "Deals" in resp.evidence.sources


def test_build_quality_structured_live_percentages() -> None:
    """Regression test for Point 1 & 6: core_null_rates must display as 92.4% / 75.0% and list all 4 null columns."""
    tool_output = {
        "work_orders": {
            "total_rows": 176,
            "fully_null_columns": [
                "Expected Billing Month",
                "Actual Collection Month",
                "Collection status",
                "Collection Date",
            ],
            "negative_metrics": {"amount_receivable_neg_count": 11},
        },
        "deals": {
            "total_rows": 344,
            "core_null_rates": {
                "close_date_null_rate": 92.44,
                "closure_probability_null_rate": 75.0,
                "deal_value_null_rate": 52.03,
            },
        },
    }
    resp = build_quality_structured(tool_output)
    null_risk = [r for r in resp.risks if "Severe Null Rates in Deals" in r.title][0]
    assert "Close Date (92.4% null)" in null_risk.detail
    assert "Closure Probability (75.0% null)" in null_risk.detail
    assert "9244" not in null_risk.detail
    assert "7500" not in null_risk.detail

    # Check Point 6: All 4 columns must be listed
    col_risk = [r for r in resp.risks if "100% Null Columns Detected" in r.title][0]
    assert "4 columns (Expected Billing Month, Actual Collection Month, Collection status, Collection Date)" in col_risk.detail


# ---------------------------------------------------------------------------
# Dispatcher & Resilience Tests
# ---------------------------------------------------------------------------

def test_generate_structured_response_success(sample_revenue_output: dict[str, Any]) -> None:
    """generate_structured_response returns StructuredCopilotResponse instance."""
    result = generate_structured_response("get_revenue_summary", sample_revenue_output)

    assert result is not None
    assert isinstance(result, StructuredCopilotResponse)
    assert result.evidence.sources == ["Work Orders"]
    assert len(result.kpis) >= 3

    # model_dump produces the dict representation needed by the API
    as_dict = result.model_dump()
    assert "summary" in as_dict
    assert "kpis" in as_dict
    assert "risks" in as_dict
    assert "evidence" in as_dict
    assert "caveats" in as_dict
    assert "follow_ups" in as_dict


def test_generate_structured_response_unknown_tool() -> None:
    """Unknown tool name gracefully returns None."""
    assert generate_structured_response("unknown_tool", {"foo": "bar"}) is None


def test_generate_structured_response_invalid_payloads() -> None:
    """Non-dict or error payloads gracefully return None without raising."""
    assert generate_structured_response("get_revenue_summary", "some string") is None  # type: ignore[arg-type]
    assert generate_structured_response("get_revenue_summary", None) is None  # type: ignore[arg-type]
    assert generate_structured_response("get_revenue_summary", {"error": "Something failed"}) is None


def test_backward_compatibility_follow_up_alias() -> None:
    """StructuredCopilotResponse allows accessing follow_up or follow_ups seamlessly."""
    evidence = EvidenceItem(
        sources=["Work Orders"],
        records_analyzed=176,
        data_coverage="100%",
        calculation="test",
    )
    # Instantiate with follow_ups
    resp1 = StructuredCopilotResponse(
        summary="Test summary",
        kpis=[KpiItem(label="Test", value="100")],
        risks=[RiskItem(title="Risk", detail="Details", severity="low")],
        evidence=evidence,
        follow_ups=["Follow up 1"],
    )
    assert resp1.follow_ups == ["Follow up 1"]
    assert resp1.follow_up == ["Follow up 1"]

    # Instantiate with follow_up
    resp2 = StructuredCopilotResponse(
        summary="Test summary",
        evidence=evidence,
        follow_up=["Follow up 2"],
    )
    assert resp2.follow_ups == ["Follow up 2"]
    assert resp2.follow_up == ["Follow up 2"]


# ---------------------------------------------------------------------------
# End-to-End API Integration Tests
# ---------------------------------------------------------------------------

def test_api_chat_includes_structured_response(client: TestClient) -> None:
    """The /api/chat endpoint returns structured response when an analytics tool runs."""
    from app.agent.orchestrator import AgentResponse

    mock_agent_response = AgentResponse(
        response="Total order value is ₹1.62 Cr with ₹88.06 L billed.",
        tools_used=["get_revenue_summary"],
        caveats=["3 credit accounts offset receivables."],
        needs_clarification=False,
        suggested_options=[],
        structured={
            "summary": "Total tracked order book is ₹1.62 Cr.",
            "kpis": [{"label": "Total Order Value", "value": "₹1.62 Cr", "context": "excl. GST"}],
            "risks": [{"title": "Collection Gap", "detail": "₹16.18 L pending", "severity": "medium"}],
            "evidence": {
                "sources": ["Work Orders"],
                "records_analyzed": 176,
                "data_coverage": "100% of tracked work orders",
                "calculation": "deterministic revenue aggregation via compute_revenue_summary",
            },
            "caveats": ["3 credit accounts offset receivables."],
            "follow_ups": ["Break down receivables by customer credit accounts"],
        },
    )

    with patch(
        "app.main.AgentOrchestrator.ask",
        return_value=mock_agent_response,
    ):
        resp = client.post("/api/chat", json={"message": "What is our revenue?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "structured" in data
        assert data["structured"] is not None
        assert data["structured"]["summary"] == "Total tracked order book is ₹1.62 Cr."
        assert len(data["structured"]["kpis"]) == 1
        assert data["structured"]["kpis"][0]["label"] == "Total Order Value"
        assert data["structured"]["evidence"]["sources"] == ["Work Orders"]
        assert "follow_ups" in data["structured"]


def test_api_chat_structured_is_none_on_clarification(client: TestClient) -> None:
    """When the query requires clarification (no tool run), structured must be None."""
    from app.agent.orchestrator import AgentResponse

    mock_agent_response = AgentResponse(
        response="Would you like to analyze Revenue or Pipeline?",
        tools_used=[],
        caveats=[],
        needs_clarification=True,
        suggested_options=["Analyze Revenue Summary", "Analyze Pipeline"],
        structured=None,
    )

    with patch("app.main.AgentOrchestrator.ask", return_value=mock_agent_response):
        resp = client.post("/api/chat", json={"message": "hello"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["structured"] is None
        assert data["needs_clarification"] is True
