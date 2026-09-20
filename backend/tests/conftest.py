"""Pytest configuration and global fixtures for Skylark BI backend tests."""

from __future__ import annotations

import pytest

from app.config import settings
from app.monday_mcp.server import board_cache
from tests.fixtures.monday_stubs import (
    load_stub_deals,
    load_stub_deals_schema,
    load_stub_work_orders,
    load_stub_work_orders_schema,
)


@pytest.fixture(autouse=True)
def setup_offline_board_cache(request: pytest.FixtureRequest) -> None:
    """Pre-populates the MCP in-memory cache with stubbed items for normal offline unit tests.
    
    Skipped for live integration tests marked with '@pytest.mark.live'.
    """
    if "live" in request.keywords:
        return

    # For unit/integration tests outside test_monday_mcp, pre-seed cache so tools and endpoints
    # run deterministically and completely offline without requiring MONDAY_API_TOKEN.
    if "test_monday_mcp" not in request.node.nodeid:
        wo_id = settings.monday_work_orders_board_id or "5031416769"
        deals_id = settings.monday_deals_board_id or "5031416803"
        board_cache.set("work_orders", load_stub_work_orders())
        board_cache.set("deals", load_stub_deals())
        board_cache.set(f"schema_{wo_id}", load_stub_work_orders_schema())
        board_cache.set(f"schema_{deals_id}", load_stub_deals_schema())
