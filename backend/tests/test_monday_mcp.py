"""Integration and unit tests for Monday.com MCP server and client.

Verifies:
- Read-only enforcement at code level (blocking mutations, no mutation methods).
- Live Work Orders board has 176 items (and NO phantom sum row).
- Live Deals board has 344 items (test_deals_item_count asserts 344, duplicate headers eliminated).
- Exactly 15 Work Orders have populated Linked Deal relations with resolvable Deal IDs.
- In-memory 5-minute TTL cache prevents secondary API calls.
- Schema introspection on both boards.
- Robust error handling: bad token, nonexistent board, rate limit (HTTP 429), and complexity budget.
- Defensive filter in get_deals drops header contamination rows and logs warnings.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest

from app.config import settings
from app.monday_mcp.client import (
    MondayAuthenticationError,
    MondayBoardNotFoundError,
    MondayClient,
    MondayRateLimitError,
    ReadOnlyViolationError,
)
from app.monday_mcp.schema import BoardSchema
from app.monday_mcp.server import (
    board_cache,
    get_board_schema,
    get_deals,
    get_work_orders,
    is_header_contaminated_deal,
    is_phantom_sum_row,
    mcp_server,
)

require_monday_token = pytest.mark.skipif(
    not settings.monday_api_token,
    reason="MONDAY_API_TOKEN is not configured in environment; skipping live board test",
)


# ---------------------------------------------------------------------------
# 1. Read-Only Code-Level Enforcement
# ---------------------------------------------------------------------------

def test_read_only_enforcement_blocks_mutations() -> None:
    """Verify that MondayClient has no mutation methods and blocks mutation queries."""
    client = MondayClient(api_token="dummy_token")

    # 1. No mutation methods exposed on the client class
    forbidden_method_prefixes = ["create_", "delete_", "update_", "change_", "archive_"]
    for attr in dir(client):
        for prefix in forbidden_method_prefixes:
            assert not attr.startswith(prefix), f"Client exposes forbidden mutation method '{attr}'"
    assert not hasattr(client, "execute_mutation")

    # 2. execute_query defensively rejects any mutation syntax before network dispatch
    mutation_queries = [
        "mutation { delete_item(item_id: \"123\") { id } }",
        "MUTATION CreateBoard { create_board(board_name: \"test\") { id } }",
        "mutation ChangeValue { change_simple_column_value(item_id: \"1\", column_id: \"col\", value: \"val\") { id } }",
    ]
    for q in mutation_queries:
        with pytest.raises(ReadOnlyViolationError, match="Mutations are strictly prohibited"):
            client.execute_query(q)


# ---------------------------------------------------------------------------
# 2. Live Board Item Counts & Phantom Sum Assertion
# ---------------------------------------------------------------------------

@require_monday_token
def test_work_orders_item_count_and_no_phantom_sum() -> None:
    """Verify that get_work_orders returns 176 items and no phantom sum row is present."""
    items = get_work_orders(force_refresh=True)

    # 1. Exactly 176 work orders
    assert len(items) == 176, f"Expected 176 Work Order items, got {len(items)}"

    # 2. Explicitly assert the phantom sum row from the source CSV is NOT present as a board item
    for item in items:
        name = str(item.get("item_name", "")).strip().lower()
        serial = str(item.get("Serial #", "")).strip().lower()
        assert name not in {"total", "sum", "grand total"}, f"Found phantom sum row by name: {item}"
        assert serial not in {"total", "sum", "grand total"}, f"Found phantom sum row by serial: {item}"
        assert not is_phantom_sum_row(item)


@require_monday_token
def test_deals_item_count() -> None:
    """Verify that get_deals returns exactly 344 items (header rows permanently deleted)."""
    items = get_deals(force_refresh=True)

    # Enforce exactly 344 valid deal items
    assert len(items) == 344, f"Expected 344 Deals items, got {len(items)}"

    # Assert no item contains duplicate header strings
    for item in items:
        contaminated, col, val = is_header_contaminated_deal(item)
        assert not contaminated, f"Found header-contaminated deal in live items: {col}='{val}'"


# ---------------------------------------------------------------------------
# 3. Connect Boards Linked Deals Verification
# ---------------------------------------------------------------------------

@require_monday_token
def test_connect_boards_linked_deals() -> None:
    """Verify that exactly 15 Work Orders have a populated Linked Deal relation."""
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

    # Check known fuzzy/ambiguous links are resolved
    serials_linked = {item.get("Serial #"): item.get("Linked Deal") for item in linked_items}
    assert "SDPLDEAL-159" in serials_linked
    assert "SDPLDEAL-160" in serials_linked
    assert "SDPLDEAL-186" in serials_linked
    assert "SDPLDEAL-149" in serials_linked

    # The 3 Timon items link to deal item 2862901859
    assert serials_linked["SDPLDEAL-159"] == ["2862901859"]
    assert serials_linked["SDPLDEAL-160"] == ["2862901859"]
    assert serials_linked["SDPLDEAL-186"] == ["2862901859"]

    # Sakura links to deal item 2862901981
    assert serials_linked["SDPLDEAL-149"] == ["2862901981"]


# ---------------------------------------------------------------------------
# 4. In-Memory 5-Minute TTL Cache Verification
# ---------------------------------------------------------------------------

@require_monday_token
def test_ttl_cache_hit_prevents_api_calls() -> None:
    """Verify calling get_work_orders twice within 5 minutes returns cached data with 0 API calls."""
    board_cache.clear()
    client = MondayClient()

    initial_requests = client.request_count

    # 1. First call populates cache
    first_result = get_work_orders(client=client)
    first_call_requests = client.request_count - initial_requests
    assert first_call_requests > 0, "First call must fetch from API"
    assert len(first_result) == 176

    # 2. Second call must hit cache without any new API calls
    mid_requests = client.request_count
    second_result = get_work_orders(client=client)
    second_call_requests = client.request_count - mid_requests

    assert second_call_requests == 0, f"Cache missed! Expected 0 requests, got {second_call_requests}"
    assert len(second_result) == len(first_result)
    assert first_result == second_result


# ---------------------------------------------------------------------------
# 5. Schema Introspection Verification
# ---------------------------------------------------------------------------

@require_monday_token
def test_get_board_schema_introspection() -> None:
    """Verify board schema introspection returns column titles, IDs, and types."""
    wo_schema = get_board_schema(board_type="work_orders", force_refresh=True)
    assert isinstance(wo_schema, dict)
    assert "columns" in wo_schema
    assert wo_schema["board_id"] == settings.monday_work_orders_board_id

    # Check key columns exist
    titles = [c["title"] for c in wo_schema["columns"]]
    assert "Serial #" in titles
    assert "Customer Name Code" in titles
    assert "Linked Deal" in titles
    assert "Execution Status" in titles

    deals_schema = get_board_schema(board_type="deals", force_refresh=True)
    assert isinstance(deals_schema, dict)
    assert deals_schema["board_id"] == settings.monday_deals_board_id

    deal_titles = [c["title"] for c in deals_schema["columns"]]
    assert "Deal Status" in deal_titles
    assert "Closure Probability" in deal_titles
    assert "Deal Stage" in deal_titles
    assert "Client Code" in deal_titles


# ---------------------------------------------------------------------------
# 6. Error Handling Tests
# ---------------------------------------------------------------------------

def test_bad_token_raises_informative_error() -> None:
    """Verify that an invalid API token raises MondayAuthenticationError."""
    bad_client = MondayClient(api_token="invalid_token_xyz")
    with pytest.raises(MondayAuthenticationError):
        bad_client.fetch_board_items(settings.monday_work_orders_board_id)


@require_monday_token
def test_bad_board_id_raises_informative_error() -> None:
    """Verify that querying a nonexistent board ID raises MondayBoardNotFoundError."""
    client = MondayClient()
    with pytest.raises(MondayBoardNotFoundError):
        client.fetch_board_items("999999999999999999")


def test_rate_limit_http_429_handled_gracefully() -> None:
    """Verify HTTP 429 responses raise MondayRateLimitError."""
    client = MondayClient(api_token="test_token")

    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = "Too Many Requests"

    with patch("requests.post", return_value=mock_resp), pytest.raises(
        MondayRateLimitError, match="rate limit exceeded"
    ):
        client.execute_query("{ me { id } }")


def test_complexity_budget_exhausted_handled_gracefully() -> None:
    """Verify GraphQL complexity budget errors raise MondayRateLimitError."""
    client = MondayClient(api_token="test_token")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "errors": [{"message": "Complexity budget exhausted: maximum complexity exceeded"}]
    }

    with patch("requests.post", return_value=mock_resp), pytest.raises(
        MondayRateLimitError, match="complexity limit exceeded"
    ):
        client.execute_query("{ me { id } }")


# ---------------------------------------------------------------------------
# 7. Defensive Filtering in get_deals
# ---------------------------------------------------------------------------

def test_defensive_filter_drops_header_contaminated_items(caplog: pytest.LogCaptureFixture) -> None:
    """Verify get_deals defensively drops any item matching column header names and logs a warning."""
    mock_schema = BoardSchema(
        board_id="123",
        board_name="Test Deals",
        columns=[
            {"id": "col_status", "title": "Deal Status", "type": "status"},
            {"id": "col_client", "title": "Client Code", "type": "text"},
        ],
    )
    mock_raw_items = [
        {
            "id": "1",
            "name": "Legitimate Deal 1",
            "column_values": [
                {"id": "col_status", "text": "Won", "value": None},
                {"id": "col_client", "client": "COMP1", "value": None},
            ],
        },
        {
            "id": "999",
            "name": "Header Row Deal",
            "column_values": [
                {"id": "col_status", "text": "Deal Status", "value": None},
                {"id": "col_client", "client": "Client Code", "value": None},
            ],
        },
        {
            "id": "2",
            "name": "Legitimate Deal 2",
            "column_values": [
                {"id": "col_status", "text": "Lost", "value": None},
                {"id": "col_client", "client": "COMP2", "value": None},
            ],
        },
    ]

    mock_client = MagicMock()
    mock_client.fetch_board_items.return_value = mock_raw_items

    with (
        patch("app.monday_mcp.server.introspect_schema", return_value=mock_schema),
        patch.object(settings, "monday_deals_board_id", "123"),
    ):
        board_cache.clear()
        with caplog.at_level(logging.WARNING):
            deals = get_deals(force_refresh=True, client=mock_client)

        # Assert only the 2 legitimate deals were returned
        assert len(deals) == 2
        deal_ids = [d["item_id"] for d in deals]
        assert "1" in deal_ids
        assert "2" in deal_ids
        assert "999" not in deal_ids

        # Assert warning was logged
        assert any("Dropping header-contaminated deal" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# 8. MCP Server Tools List
# ---------------------------------------------------------------------------

def test_mcp_server_registered_tools() -> None:
    """Verify that mcp_server exposes get_work_orders, get_deals, and get_board_schema."""
    import asyncio

    async def _check() -> None:
        tools = await mcp_server.list_tools()
        tool_names = [t.name for t in tools]
        assert "get_work_orders" in tool_names
        assert "get_deals" in tool_names
        assert "get_board_schema" in tool_names

    asyncio.run(_check())

