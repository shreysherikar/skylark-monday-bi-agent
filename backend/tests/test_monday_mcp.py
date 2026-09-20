"""Unit tests for Monday.com MCP server, client, pagination, caching, and read-only security.

Runs 100% offline without requiring MONDAY_API_TOKEN or live network connectivity.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import time
from unittest.mock import MagicMock, patch

import pytest

from app.config import settings
from app.monday_mcp.client import (
    MondayAPIError,
    MondayAuthenticationError,
    MondayBoardNotFoundError,
    MondayClient,
    MondayRateLimitError,
    ReadOnlyViolationError,
)
from app.monday_mcp.schema import BoardSchema, get_board_schema as introspect_schema
from app.monday_mcp.server import (
    TTLCache,
    get_board_schema,
    get_deals,
    get_schema,
    get_work_orders,
    is_header_contaminated_deal,
    is_phantom_sum_row,
    mcp_server,
)


# ---------------------------------------------------------------------------
# 1. MCP Server Initialization & Public Tool Surface
# ---------------------------------------------------------------------------

def test_mcp_server_initialization() -> None:
    """Verify MCP server is properly named and initialized."""
    assert mcp_server.name == "skylark-monday-mcp"


def test_mcp_server_tool_surface_is_minimal_and_non_duplicative() -> None:
    """Verify MCP tool surface exposes exactly: get_work_orders, get_deals, get_schema.

    get_board_schema must NOT be registered as a duplicate MCP tool.
    """
    tools = asyncio.run(mcp_server.list_tools())
    tool_names = sorted(t.name for t in tools)
    assert tool_names == ["get_deals", "get_schema", "get_work_orders"]


def test_get_board_schema_compatibility_alias() -> None:
    """Verify get_board_schema exists as a direct Python alias for get_schema."""
    assert get_board_schema is get_schema


def test_mcp_server_resources_registered() -> None:
    """Verify read-only MCP resources are registered for work orders, deals, and schema."""
    resources = asyncio.run(mcp_server.list_resources())
    uris = {str(r.uri) for r in resources}
    assert "monday://work_orders" in uris
    assert "monday://deals" in uris


# ---------------------------------------------------------------------------
# 2. Read-Only Code-Level Enforcement & Mutation Defense
# ---------------------------------------------------------------------------

def test_read_only_enforcement_blocks_mutations() -> None:
    """Verify that MondayClient has no mutation methods and blocks mutation queries."""
    client = MondayClient(api_token="dummy_token")

    forbidden_method_prefixes = ["create_", "delete_", "update_", "change_", "archive_"]
    for attr in dir(client):
        for prefix in forbidden_method_prefixes:
            assert not attr.startswith(prefix), f"Client exposes forbidden mutation method '{attr}'"
    assert not hasattr(client, "execute_mutation")

    mutation_queries = [
        "mutation { delete_item(item_id: \"123\") { id } }",
        "MUTATION CreateBoard { create_board(board_name: \"test\") { id } }",
        "mutation ChangeValue { change_simple_column_value(item_id: \"1\", column_id: \"col\", value: \"val\") { id } }",
        "\n  mutation {\n    archive_item(item_id: \"123\") { id }\n  }",
        "# comment\nmutation { duplicate_group(board_id: 1, group_id: \"g\") { id } }",
    ]
    for q in mutation_queries:
        with pytest.raises(ReadOnlyViolationError, match="Mutations are strictly prohibited"):
            client.execute_query(q)


def test_mutation_rejection_happens_before_network_transmission() -> None:
    """Verify mutation queries are rejected before any network request is sent."""
    client = MondayClient(api_token="test_token")

    with patch("requests.post") as mock_post:
        with pytest.raises(ReadOnlyViolationError):
            client.execute_query("mutation { delete_item(id: 1) { id } }")
        mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# 3. GraphQL Pagination
# ---------------------------------------------------------------------------

def test_pagination_multiple_pages_and_cursor_progression() -> None:
    """Verify cursor progression and item aggregation across multiple pages."""
    client = MondayClient(api_token="test_token")

    page1_resp = {
        "boards": [
            {
                "id": "100",
                "items_page": {
                    "cursor": "cursor_page_2",
                    "items": [{"id": "item_1", "name": "Item 1", "column_values": []}],
                },
            }
        ]
    }
    page2_resp = {
        "boards": [
            {
                "id": "100",
                "items_page": {
                    "cursor": None,
                    "items": [{"id": "item_2", "name": "Item 2", "column_values": []}],
                },
            }
        ]
    }

    with patch.object(client, "execute_query", side_effect=[page1_resp, page2_resp]) as mock_exec:
        items = client.fetch_board_items("100", limit=1)

        assert len(items) == 2
        assert [it["id"] for it in items] == ["item_1", "item_2"]
        assert mock_exec.call_count == 2

        # Verify cursor was passed in the second query
        second_call_variables = mock_exec.call_args_list[1][1]["variables"]
        assert second_call_variables["cursor"] == "cursor_page_2"


def test_pagination_termination_on_empty_page() -> None:
    """Verify pagination cleanly terminates if a page returns empty items even with a cursor."""
    client = MondayClient(api_token="test_token")

    page1_resp = {
        "boards": [
            {
                "id": "100",
                "items_page": {
                    "cursor": "stray_cursor",
                    "items": [],
                },
            }
        ]
    }

    with patch.object(client, "execute_query", return_value=page1_resp):
        items = client.fetch_board_items("100")
        assert items == []


def test_pagination_empty_board() -> None:
    """Verify an empty board returns an empty list without error."""
    client = MondayClient(api_token="test_token")

    empty_resp = {
        "boards": [
            {
                "id": "100",
                "items_page": {
                    "cursor": None,
                    "items": [],
                },
            }
        ]
    }

    with patch.object(client, "execute_query", return_value=empty_resp):
        items = client.fetch_board_items("100")
        assert items == []


def test_pagination_api_failure_midway_propagates_error() -> None:
    """Verify an API failure during pagination raises immediately rather than returning partial data."""
    client = MondayClient(api_token="test_token")

    page1_resp = {
        "boards": [
            {
                "id": "100",
                "items_page": {
                    "cursor": "cursor_2",
                    "items": [{"id": "1", "name": "Item 1", "column_values": []}],
                },
            }
        ]
    }

    with patch.object(client, "execute_query", side_effect=[page1_resp, MondayRateLimitError("Rate limit exceeded")]):
        with pytest.raises(MondayRateLimitError):
            client.fetch_board_items("100")


# ---------------------------------------------------------------------------
# 4. Dynamic Schema Introspection
# ---------------------------------------------------------------------------

def test_schema_introspection_model_and_lookups() -> None:
    """Verify BoardSchema parsing, settings extraction, and title/ID lookups."""
    mock_meta = {
        "id": "500",
        "name": "Test Board",
        "description": "Board for testing",
        "items_count": 42,
        "columns": [
            {"id": "col_name", "title": "Deal Name", "type": "name", "settings_str": "{}"},
            {"id": "col_status", "title": "Deal Status", "type": "status", "settings_str": '{"labels":{"1":"Won"}}'},
            {"id": "col_numeric", "title": "Contract Value", "type": "numbers", "settings_str": None},
        ],
    }

    mock_client = MagicMock()
    mock_client.fetch_board_metadata.return_value = mock_meta

    schema = introspect_schema("500", client=mock_client)
    assert schema.board_id == "500"
    assert schema.board_name == "Test Board"
    assert len(schema.columns) == 3

    # Exact title lookup
    assert schema.get_column_id("Deal Status") == "col_status"
    # Case-insensitive title lookup
    assert schema.get_column_id("deal status") == "col_status"
    assert schema.get_column_id("contract value") == "col_numeric"
    # Column ID to title lookup
    assert schema.get_column_title("col_status") == "Deal Status"
    assert schema.get_column_title("nonexistent") is None


# ---------------------------------------------------------------------------
# 5. In-Memory TTL Cache & Concurrent Behavior
# ---------------------------------------------------------------------------

def test_ttl_cache_expiration_and_hit_miss_counters() -> None:
    """Verify TTL cache expiration, hits, misses, clear, and invalidate."""
    cache = TTLCache(default_ttl_seconds=1)

    assert cache.get("key1") is None
    assert cache.misses == 1

    cache.set("key1", "val1", ttl_seconds=1)
    assert cache.get("key1") == "val1"
    assert cache.hits == 1

    # Wait for expiry
    time.sleep(1.05)
    assert cache.get("key1") is None
    assert cache.misses == 2

    # Invalidate
    cache.set("key2", "val2")
    cache.invalidate("key2")
    assert cache.get("key2") is None

    # Clear
    cache.set("key3", "val3")
    cache.clear()
    assert cache.hits == 0
    assert cache.misses == 0
    assert cache.get("key3") is None


def test_ttl_cache_thread_safe_concurrent_access() -> None:
    """Verify TTLCache safe operation under concurrent multi-threaded reads and writes."""
    cache = TTLCache(default_ttl_seconds=60)

    def worker(thread_idx: int) -> None:
        for i in range(50):
            key = f"key_{thread_idx}_{i % 5}"
            cache.set(key, f"value_{thread_idx}_{i}")
            val = cache.get(key)
            assert val is not None or cache.get(key) is None

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, idx) for idx in range(8)]
        for f in futures:
            f.result()

    assert cache.hits + cache.misses > 0


# ---------------------------------------------------------------------------
# 6. Defensive Filtering (Headers & Phantom Sums)
# ---------------------------------------------------------------------------

def test_phantom_sum_detection() -> None:
    """Verify phantom sum rows are accurately identified."""
    assert is_phantom_sum_row({"item_name": "Total", "Serial #": "SDPL-001"}) is True
    assert is_phantom_sum_row({"item_name": "Grand Total"}) is True
    assert is_phantom_sum_row({"Serial #": "sum"}) is True
    assert is_phantom_sum_row({"item_name": "Legitimate Project", "Serial #": "SDPLDEAL-100"}) is False


def test_header_contamination_detection() -> None:
    """Verify header contamination rows are accurately identified."""
    contam_item = {
        "item_name": "Header Row",
        "Deal Status": "Deal Status",
        "Client Code": "Client Code",
    }
    is_contam, col, val = is_header_contaminated_deal(contam_item)
    assert is_contam is True
    assert col == "Deal Status"

    valid_item = {
        "item_name": "Legitimate Deal",
        "Deal Status": "Won",
        "Client Code": "COMPANY123",
    }
    is_contam, _, _ = is_header_contaminated_deal(valid_item)
    assert is_contam is False


# ---------------------------------------------------------------------------
# 7. Error Handling & API Failure Responses
# ---------------------------------------------------------------------------

def test_bad_token_raises_authentication_error() -> None:
    """Verify invalid or missing token raises MondayAuthenticationError."""
    bad_client = MondayClient(api_token="")
    with pytest.raises(MondayAuthenticationError, match="missing or not configured"):
        bad_client.execute_query("{ me { id } }")


def test_nonexistent_board_raises_not_found_error() -> None:
    """Verify 404 response raises MondayBoardNotFoundError."""
    client = MondayClient(api_token="token")
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_resp.text = "Board not found"

    with patch("requests.post", return_value=mock_resp), pytest.raises(MondayBoardNotFoundError):
        client.execute_query("{ boards(ids: [999]) { id } }")


def test_rate_limit_http_429_handled_gracefully() -> None:
    """Verify HTTP 429 raises MondayRateLimitError."""
    client = MondayClient(api_token="token")
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.text = "Rate limit exceeded"

    with patch("requests.post", return_value=mock_resp), pytest.raises(MondayRateLimitError):
        client.execute_query("{ me { id } }")


def test_complexity_budget_exhausted_raises_rate_limit_error() -> None:
    """Verify complexity budget exhausted GraphQL error raises MondayRateLimitError."""
    client = MondayClient(api_token="token")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "errors": [{"message": "Complexity budget exhausted: maximum complexity exceeded"}]
    }

    with patch("requests.post", return_value=mock_resp), pytest.raises(MondayRateLimitError):
        client.execute_query("{ me { id } }")


def test_malformed_json_raises_monday_api_error() -> None:
    """Verify malformed JSON response raises MondayAPIError."""
    client = MondayClient(api_token="token")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("Invalid JSON")
    mock_resp.text = "<html>502 Bad Gateway</html>"

    with patch("requests.post", return_value=mock_resp), pytest.raises(MondayAPIError, match="Malformed JSON"):
        client.execute_query("{ me { id } }")


def test_network_connection_error_raises_monday_api_error() -> None:
    """Verify network connection exception raises MondayAPIError."""
    import requests

    client = MondayClient(api_token="token")
    with patch("requests.post", side_effect=requests.ConnectionError("Failed to connect")):
        with pytest.raises(MondayAPIError, match="Network error"):
            client.execute_query("{ me { id } }")


def test_missing_board_id_configuration_raises_error() -> None:
    """Verify missing board ID configuration raises MondayBoardNotFoundError."""
    with patch.object(settings, "monday_work_orders_board_id", None):
        with pytest.raises(MondayBoardNotFoundError, match="MONDAY_WORK_ORDERS_BOARD_ID is not configured"):
            get_work_orders(force_refresh=True)

    with patch.object(settings, "monday_deals_board_id", None):
        with pytest.raises(MondayBoardNotFoundError, match="MONDAY_DEALS_BOARD_ID is not configured"):
            get_deals(force_refresh=True)


# ---------------------------------------------------------------------------
# 8. MCP Protocol Tool Invocation
# ---------------------------------------------------------------------------

def test_mcp_server_call_tool_get_schema() -> None:
    """Verify calling get_schema via MCP server protocol returns structured content."""
    mock_schema = BoardSchema(
        board_id="123",
        board_name="Test Deals",
        columns=[{"id": "col_1", "title": "Deal Name", "type": "name"}],
    )

    with patch("app.monday_mcp.server.introspect_schema", return_value=mock_schema):
        res = asyncio.run(
            mcp_server.call_tool("get_schema", {"board_type": "deals", "force_refresh": True})
        )
        assert res.is_error is False
        assert res.structured_content is not None
        assert res.structured_content["board_id"] == "123"
