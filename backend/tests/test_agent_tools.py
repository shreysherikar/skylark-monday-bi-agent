"""Unit tests for agent tool definitions and tool execution dispatcher."""

from __future__ import annotations

import pytest

from app.agent.tools import AGENT_TOOLS, execute_tool


def test_optional_tool_parameters_accept_null() -> None:
    """Regression: the model can legitimately emit `null` for an optional parameter.

    Groq rejects a tool call that passes null to a non-nullable field with a 400
    `tool_use_failed` error. This previously turned the query
    "What is our total outstanding receivables?" into an HTTP 500.
    Optional parameters therefore must be declared nullable.
    """
    optional_params = {
        "get_pipeline_summary": ["sector", "stage"],
        "get_revenue_summary": ["sector"],
        "get_cross_board_delivery": ["sector"],
        "get_leadership_update": ["period"],
        "get_data_quality_report": ["board_name"],
    }

    tools_by_name = {t["name"]: t for t in AGENT_TOOLS}
    for tool_name, params in optional_params.items():
        schema = tools_by_name[tool_name]["input_schema"]
        for param in params:
            declared_type = schema["properties"][param]["type"]
            assert isinstance(declared_type, list), (
                f"{tool_name}.{param} must be nullable, got {declared_type!r}"
            )
            assert "null" in declared_type, (
                f"{tool_name}.{param} must allow null (Groq rejects null for non-nullable fields)"
            )


def test_groq_tool_schemas_preserve_nullable_types() -> None:
    """The Groq-facing conversion must not drop the nullable type declarations."""
    from app.agent.tools import get_groq_tools

    groq_tools = {t["function"]["name"]: t["function"] for t in get_groq_tools()}
    revenue_schema = groq_tools["get_revenue_summary"]["parameters"]
    assert "null" in revenue_schema["properties"]["sector"]["type"]


def test_execute_tool_tolerates_null_optional_arguments() -> None:
    """The dispatcher must coerce explicit nulls to defaults instead of crashing."""
    # Unknown-tool guard still works with null-heavy payloads.
    with pytest.raises(ValueError, match="Unknown tool requested"):
        execute_tool("non_existent_tool", {"sector": None})

    # Null board_name falls back to the documented 'both' default. This path only reads
    # module-level helpers, so patch them to avoid a live Monday.com dependency.
    from unittest.mock import patch

    with patch("app.agent.tools._load_normalized_work_orders", return_value=(None, None)), patch(
        "app.agent.tools._load_normalized_deals", return_value=None
    ):
        result = execute_tool("get_data_quality_report", {"board_name": None})
    assert isinstance(result, dict)


def test_agent_tool_schemas() -> None:
    """Verifies all agent tool schemas comply with Anthropic tool specifications."""
    expected_tools = {
        "get_pipeline_summary",
        "get_revenue_summary",
        "get_cross_board_delivery",
        "get_leadership_update",
        "get_data_quality_report",
        "get_board_schema",
    }

    tool_names = {t["name"] for t in AGENT_TOOLS}
    assert expected_tools.issubset(tool_names)

    for tool in AGENT_TOOLS:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"
        assert "properties" in tool["input_schema"]


def test_execute_pipeline_summary_tool() -> None:
    """Verifies get_pipeline_summary executes deterministically via tool dispatcher."""
    res = execute_tool("get_pipeline_summary", {"sector": "Renewables"})
    assert res["filtered_sector"] == "Renewables"
    assert res["total_deals"] > 0
    assert "active_pipeline_unweighted_value" in res
    assert "caveats" in res


def test_execute_revenue_summary_tool() -> None:
    """Verifies get_revenue_summary executes deterministically via tool dispatcher."""
    res = execute_tool("get_revenue_summary", {})
    assert res["total_work_orders"] == 176
    assert res["credit_balance_accounts_count"] == 11
    assert "net_receivables" in res
    assert "caveats" in res


def test_execute_cross_board_delivery_tool() -> None:
    """Verifies get_cross_board_delivery returns dynamic live coverage."""
    res = execute_tool("get_cross_board_delivery", {})
    assert res["total_work_orders"] == 176
    assert res["total_deals"] == 344
    assert "link_coverage_percentage" in res
    assert "caveats" in res
    assert "commercial_risk" in res
    assert "value_variance" in res
    assert "won_deals_backlog" in res


def test_execute_cross_board_delivery_tool_with_view() -> None:
    """Verifies get_cross_board_delivery executes with view parameter."""
    res = execute_tool("get_cross_board_delivery", {"view": "unclosed_deal_risk"})
    assert res["view"] == "unclosed_deal_risk"
    assert "risk_orders" in res["commercial_risk"]
    assert res["commercial_risk"]["unclosed_deal_risk_count"] >= 0


def test_execute_leadership_update_tool() -> None:
    """Verifies get_leadership_update returns structured executive briefing."""
    res = execute_tool("get_leadership_update", {"period": "Monthly Review"})
    assert res["period"] == "Monthly Review"
    assert "markdown_briefing" in res
    assert "Skylark Drones" in res["markdown_briefing"]


def test_execute_data_quality_report_tool() -> None:
    """Verifies get_data_quality_report returns report metrics."""
    res = execute_tool("get_data_quality_report", {"board_name": "both"})
    assert "work_orders" in res
    assert "deals" in res


def test_execute_board_schema_tool() -> None:
    """Verifies get_board_schema returns schema metadata."""
    res = execute_tool("get_board_schema", {"board_type": "work_orders"})
    assert "board_id" in res
    assert "columns" in res


def test_execute_unknown_tool_raises_error() -> None:
    """Unknown tool name raises ValueError."""
    with pytest.raises(ValueError, match="Unknown tool requested"):
        execute_tool("non_existent_tool", {})
