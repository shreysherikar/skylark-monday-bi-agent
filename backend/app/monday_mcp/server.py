"""MCP server exposing read-only Monday.com tools (get_work_orders, get_deals, get_board_schema).

Implements:
- 5-minute in-memory TTL caching layer to prevent excessive API requests.
- Defensive filtering in get_deals() to drop any header-contaminated rows and log warnings.
- Defensive filtering in get_work_orders() to ensure phantom sum rows never leak through.
- Schema introspection so consumers can map columns dynamically.
- Official Python MCP SDK server exposure.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, cast

from mcp.server.mcpserver import MCPServer

from app.config import settings
from app.monday_mcp.client import MondayBoardNotFoundError, MondayClient
from app.monday_mcp.schema import get_board_schema as introspect_schema
from app.monday_mcp.schema import map_item_to_schema

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-Memory TTL Cache
# ---------------------------------------------------------------------------

class TTLCache:
    """Thread-safe in-memory cache with time-to-live expiration."""

    def __init__(self, default_ttl_seconds: int = 300) -> None:
        self.default_ttl = default_ttl_seconds
        self._cache: dict[str, tuple[Any, float]] = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any | None:
        """Retrieve value if key exists and has not expired."""
        with self._lock:
            if key in self._cache:
                val, expiry = self._cache[key]
                if time.time() < expiry:
                    self.hits += 1
                    return val
                else:
                    del self._cache[key]
            self.misses += 1
            return None

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Store value with expiration timestamp."""
        with self._lock:
            ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
            expiry = time.time() + ttl
            self._cache[key] = (value, expiry)

    def clear(self) -> None:
        """Clear all cached entries and reset metrics."""
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0

    def invalidate(self, key: str) -> None:
        """Remove a specific key from cache."""
        with self._lock:
            self._cache.pop(key, None)


# Global board cache instance (5-minute TTL per §3)
board_cache = TTLCache(default_ttl_seconds=settings.board_cache_ttl_seconds)


# ---------------------------------------------------------------------------
# Defensive Check Helpers
# ---------------------------------------------------------------------------

def is_header_contaminated_deal(item: dict[str, Any]) -> tuple[bool, str | None, str | None]:
    """Check if any column value matches its column title (e.g. Deal Status == 'Deal Status').
    
    Returns:
        (is_contaminated, column_title, matched_value)
    """
    key_status_columns = [
        "Deal Status",
        "Closure Probability",
        "Deal Stage",
        "Product deal",
        "Sector/service",
        "Client Code",
        "Owner code",
    ]
    for col in key_status_columns:
        val = item.get(col)
        if val is not None and isinstance(val, str) and val.strip().lower() == col.strip().lower():
            return True, col, val

    # General check: any column value matching its own column title
    for col_title, val in item.items():
        if col_title in ("item_id", "item_name", "group_id", "group_title"):
            continue
        if val is not None and isinstance(val, str) and val.strip().lower() == col_title.strip().lower():
            return True, col_title, val

    return False, None, None


def is_phantom_sum_row(item: dict[str, Any]) -> bool:
    """Check if an item matches the phantom total/sum row pattern from the source spreadsheet."""
    name = str(item.get("item_name", "")).strip().lower()
    serial = str(item.get("Serial #", "")).strip().lower()
    return name in {"total", "sum", "grand total"} or serial in {"total", "sum", "grand total"}


# ---------------------------------------------------------------------------
# Core Data Fetching Functions (Python API & Tool Implementation)
# ---------------------------------------------------------------------------

def get_work_orders(
    force_refresh: bool = False,
    client: MondayClient | None = None,
) -> list[dict[str, Any]]:
    """Fetch all Work Orders from Monday.com with 5-minute TTL caching.
    
    Maps column IDs to column titles, resolves linked deal item IDs, and drops
    phantom total/sum rows.
    """
    cache_key = "work_orders"
    if not force_refresh:
        cached = board_cache.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for work orders board.")
            return cast("list[dict[str, Any]]", cached)

    m_client = client or MondayClient()
    board_id = settings.monday_work_orders_board_id
    if not board_id:
        raise MondayBoardNotFoundError("MONDAY_WORK_ORDERS_BOARD_ID is not configured.")

    schema = introspect_schema(board_id, client=m_client)
    raw_items = m_client.fetch_board_items(board_id)

    cleaned_items: list[dict[str, Any]] = []
    for raw in raw_items:
        mapped = map_item_to_schema(raw, schema)
        if is_phantom_sum_row(mapped):
            logger.warning(
                "Dropping phantom sum row on Work Orders board: item ID %s ('%s')",
                mapped.get("item_id"),
                mapped.get("item_name"),
            )
            continue
        cleaned_items.append(mapped)

    board_cache.set(cache_key, cleaned_items)
    return cleaned_items


def get_deals(
    force_refresh: bool = False,
    client: MondayClient | None = None,
) -> list[dict[str, Any]]:
    """Fetch all Deals from Monday.com with 5-minute TTL caching.
    
    Applies defensive filtering to drop any row where column value matches the
    column title (e.g. Deal Status == 'Deal Status'), logging a warning if encountered.
    """
    cache_key = "deals"
    if not force_refresh:
        cached = board_cache.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for deals board.")
            return cast("list[dict[str, Any]]", cached)

    m_client = client or MondayClient()
    board_id = settings.monday_deals_board_id
    if not board_id:
        raise MondayBoardNotFoundError("MONDAY_DEALS_BOARD_ID is not configured.")

    schema = introspect_schema(board_id, client=m_client)
    raw_items = m_client.fetch_board_items(board_id)

    cleaned_items: list[dict[str, Any]] = []
    for raw in raw_items:
        mapped = map_item_to_schema(raw, schema)
        contaminated, col_name, col_val = is_header_contaminated_deal(mapped)
        if contaminated:
            logger.warning(
                "Dropping header-contaminated deal item ID %s ('%s'): column '%s' matches header value '%s'",
                mapped.get("item_id"),
                mapped.get("item_name"),
                col_name,
                col_val,
            )
            continue
        cleaned_items.append(mapped)

    board_cache.set(cache_key, cleaned_items)
    return cleaned_items


def get_schema(
    board_id: str | None = None,
    board_type: str | None = None,
    force_refresh: bool = False,
    client: MondayClient | None = None,
) -> dict[str, Any]:
    """Introspect schema for a Monday.com board with 5-minute TTL caching.
    
    Args:
        board_id: Explicit board ID.
        board_type: Named board identifier ('work_orders' or 'deals').
        force_refresh: If True, bypass cache.
        client: Optional MondayClient instance.
    """
    target_id = board_id
    if not target_id and board_type:
        norm_type = board_type.strip().lower()
        if norm_type in ("work_orders", "work_order", "wo"):
            target_id = settings.monday_work_orders_board_id or "5031416769"
        elif norm_type in ("deals", "deal"):
            target_id = settings.monday_deals_board_id or "5031416803"

    if not target_id:
        raise MondayBoardNotFoundError(
            "Must provide either a valid board_id or board_type ('work_orders' | 'deals')."
        )

    cache_key = f"schema_{target_id}"
    if not force_refresh:
        cached = board_cache.get(cache_key)
        if cached is not None:
            return cast("dict[str, Any]", cached)

    m_client = client or MondayClient()
    schema_model = introspect_schema(target_id, client=m_client)
    schema_dict = schema_model.model_dump()
    board_cache.set(cache_key, schema_dict)
    return schema_dict


# Python backwards-compatibility alias
get_board_schema = get_schema


# ---------------------------------------------------------------------------
# MCP Server Registration
# ---------------------------------------------------------------------------

mcp_server = MCPServer("skylark-monday-mcp")


@mcp_server.tool(
    name="get_work_orders",
    description="Fetch all Work Orders with columns mapped by title and linked deals resolved.",
)
def _mcp_get_work_orders(force_refresh: bool = False) -> list[dict[str, Any]]:
    """MCP tool wrapper for get_work_orders."""
    return get_work_orders(force_refresh=force_refresh)


@mcp_server.tool(
    name="get_deals",
    description="Fetch all Deals with columns mapped by title and header contamination filtered.",
)
def _mcp_get_deals(force_refresh: bool = False) -> list[dict[str, Any]]:
    """MCP tool wrapper for get_deals."""
    return get_deals(force_refresh=force_refresh)


@mcp_server.tool(
    name="get_schema",
    description="Introspect column titles, IDs, and types for a board (use board_type='work_orders' or 'deals').",
)
def _mcp_get_schema(
    board_id: str | None = None,
    board_type: str | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """MCP tool wrapper for get_schema."""
    return get_schema(board_id=board_id, board_type=board_type, force_refresh=force_refresh)


# ---------------------------------------------------------------------------
# MCP Resources (Read-Only)
# ---------------------------------------------------------------------------

@mcp_server.resource("monday://work_orders", description="Raw mapped Work Orders from Monday.com")
def _mcp_resource_work_orders() -> str:
    """Read-only MCP resource for Work Orders dataset."""
    import json
    return json.dumps(get_work_orders())


@mcp_server.resource("monday://deals", description="Raw mapped Deals from Monday.com")
def _mcp_resource_deals() -> str:
    """Read-only MCP resource for Deals dataset."""
    import json
    return json.dumps(get_deals())


@mcp_server.resource("monday://schema/{board_type}", description="Board schema metadata from Monday.com")
def _mcp_resource_schema(board_type: str) -> str:
    """Read-only MCP resource for board schema."""
    import json
    return json.dumps(get_schema(board_type=board_type))


if __name__ == "__main__":
    mcp_server.run()

