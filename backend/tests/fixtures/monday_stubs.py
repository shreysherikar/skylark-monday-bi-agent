"""Offline stub fixtures for Monday.com datasets and schemas.

Allows unit and integration tests to run 100% offline without live Monday.com credentials.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parent


def load_stub_work_orders() -> list[dict[str, Any]]:
    """Loads 176 mapped work orders from offline stub fixture."""
    path = FIXTURES_DIR / "work_orders_stub.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_stub_deals() -> list[dict[str, Any]]:
    """Loads 344 mapped deals from offline stub fixture."""
    path = FIXTURES_DIR / "deals_stub.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_stub_work_orders_schema() -> dict[str, Any]:
    """Loads work orders board schema metadata from offline stub fixture."""
    path = FIXTURES_DIR / "work_orders_schema_stub.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_stub_deals_schema() -> dict[str, Any]:
    """Loads deals board schema metadata from offline stub fixture."""
    path = FIXTURES_DIR / "deals_schema_stub.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
