"""Live integration tests for Monday.com MCP server and client against real boards.

These tests are isolated from normal CI and require MONDAY_API_TOKEN and network connectivity.
Run explicitly with:
    python -m pytest -m live
"""

from __future__ import annotations

import pytest

from app.config import settings
from app.monday_mcp.client import MondayClient
from app.monday_mcp.server import (
    board_cache,
    get_deals,
    get_schema,
    get_work_orders,
    is_header_contaminated_deal,
    is_phantom_sum_row,
)

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not settings.monday_api_token,
        reason="MONDAY_API_TOKEN is not configured; skipping live board verification",
    ),
]


def test_live_work_orders_item_count_and_no_phantom_sum() -> None:
    """Verify live Work Orders board returns 176 items and no phantom sum row is present."""
    board_cache.clear()
    items = get_work_orders(force_refresh=True)

    # 1. Exactly 176 work orders
    assert len(items) == 176, f"Expected 176 Work Order items, got {len(items)}"

    # 2. Explicitly assert the phantom sum row from source is NOT present as a board item
    for item in items:
        name = str(item.get("item_name", "")).strip().lower()
        serial = str(item.get("Serial #", "")).strip().lower()
        assert name not in {"total", "sum", "grand total"}, f"Found phantom sum row by name: {item}"
        assert serial not in {"total", "sum", "grand total"}, f"Found phantom sum row by serial: {item}"
        assert not is_phantom_sum_row(item)


def test_live_deals_item_count() -> None:
    """Verify live Deals board returns exactly 344 items (header rows permanently deleted)."""
    board_cache.clear()
    items = get_deals(force_refresh=True)

    # Enforce exactly 344 valid deal items
    assert len(items) == 344, f"Expected 344 Deals items, got {len(items)}"

    # Assert no item contains duplicate header strings
    for item in items:
        contaminated, col, val = is_header_contaminated_deal(item)
        assert not contaminated, f"Found header-contaminated deal in live items: {col}='{val}'"


def test_live_connect_boards_linked_deals() -> None:
    """Verify live board has exactly 15 Work Orders with populated Linked Deal relation."""
    items = get_work_orders(force_refresh=False)

    linked_items = [
        item for item in items
        if item.get("Linked Deal") and len(item["Linked Deal"]) > 0
    ]

    # Exactly 15 work orders have a populated Linked Deal relation
    assert len(linked_items) == 15, f"Expected 15 linked work orders, found {len(linked_items)}"

    # Verify each linked relation contains valid string deal item IDs
    for item in linked_items:
        deal_ids = item.get("Linked Deal")
        assert isinstance(deal_ids, list)
        assert len(deal_ids) >= 1
        for did in deal_ids:
            assert isinstance(did, str)
            assert did.isdigit(), f"Deal ID '{did}' should be a numeric string"

    serials_linked = {item.get("Serial #"): item.get("Linked Deal") for item in linked_items}
    assert "SDPLDEAL-159" in serials_linked
    assert "SDPLDEAL-160" in serials_linked
    assert "SDPLDEAL-186" in serials_linked
    assert "SDPLDEAL-149" in serials_linked


def test_live_ttl_cache_hit_prevents_api_calls() -> None:
    """Verify calling get_work_orders twice within 5 minutes returns cached data with 0 API calls."""
    board_cache.clear()
    client = MondayClient()

    initial_requests = client.request_count

    first_result = get_work_orders(client=client)
    first_call_requests = client.request_count - initial_requests
    assert first_call_requests > 0, "First call must fetch from API"
    assert len(first_result) == 176

    mid_requests = client.request_count
    second_result = get_work_orders(client=client)
    second_call_requests = client.request_count - mid_requests

    assert second_call_requests == 0, f"Cache missed! Expected 0 requests, got {second_call_requests}"
    assert len(second_result) == len(first_result)
    assert first_result == second_result


def test_live_get_board_schema_introspection() -> None:
    """Verify live board schema introspection returns column titles, IDs, and types."""
    wo_schema = get_schema(board_type="work_orders", force_refresh=True)
    assert isinstance(wo_schema, dict)
    assert "columns" in wo_schema
    assert wo_schema["board_id"] == settings.monday_work_orders_board_id

    titles = [c["title"] for c in wo_schema["columns"]]
    assert "Serial #" in titles
    assert "Customer Name Code" in titles
    assert "Linked Deal" in titles
    assert "Execution Status" in titles

    deals_schema = get_schema(board_type="deals", force_refresh=True)
    assert isinstance(deals_schema, dict)
    assert deals_schema["board_id"] == settings.monday_deals_board_id

    deal_titles = [c["title"] for c in deals_schema["columns"]]
    assert "Deal Status" in deal_titles
    assert "Closure Probability" in deal_titles
    assert "Deal Stage" in deal_titles
    assert "Client Code" in deal_titles
