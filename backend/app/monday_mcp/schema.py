"""Monday.com board schema introspection and column type mappings.

Allows agent and data layers to reason about column titles and structure dynamically
rather than depending solely on volatile column IDs.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from app.monday_mcp.client import MondayClient

logger = logging.getLogger(__name__)


class BoardColumn(BaseModel):
    """Schema definition for a single Monday.com board column."""

    id: str
    title: str
    type: str
    description: str | None = None
    settings: dict[str, Any] | None = None


class BoardSchema(BaseModel):
    """Full schema definition for a Monday.com board."""

    board_id: str
    board_name: str
    description: str | None = None
    items_count: int | None = None
    columns: list[BoardColumn]
    column_by_id: dict[str, BoardColumn] = Field(default_factory=dict)
    column_by_title: dict[str, BoardColumn] = Field(default_factory=dict)

    def model_post_init(self, __context: Any, /) -> None:
        """Populate fast lookup mappings after initialization."""
        for col in self.columns:
            self.column_by_id[col.id] = col
            self.column_by_title[col.title] = col
            # Also map lowercase/stripped version for lenient lookups
            normalized = col.title.strip().lower()
            if normalized not in self.column_by_title:
                self.column_by_title[normalized] = col

    def get_column_id(self, title: str) -> str | None:
        """Lookup column ID by exact or case-insensitive title."""
        if title in self.column_by_title:
            return self.column_by_title[title].id
        norm = title.strip().lower()
        if norm in self.column_by_title:
            return self.column_by_title[norm].id
        return None

    def get_column_title(self, col_id: str) -> str | None:
        """Lookup column title by column ID."""
        if col_id in self.column_by_id:
            return self.column_by_id[col_id].title
        return None


def get_board_schema(
    board_id: str,
    client: MondayClient | None = None,
) -> BoardSchema:
    """Introspect a Monday.com board and return its structured schema.
    
    Args:
        board_id: The Monday.com board ID.
        client: Optional MondayClient instance (creates a default one if omitted).
        
    Returns:
        BoardSchema instance with columns and lookup dictionaries.
    """
    m_client = client or MondayClient()
    meta = m_client.fetch_board_metadata(board_id)

    parsed_columns: list[BoardColumn] = []
    for raw_col in meta.get("columns", []):
        settings_dict = None
        settings_str = raw_col.get("settings_str")
        if settings_str:
            try:
                settings_dict = json.loads(settings_str)
            except (ValueError, TypeError):
                settings_dict = None

        parsed_columns.append(
            BoardColumn(
                id=raw_col["id"],
                title=raw_col["title"],
                type=raw_col["type"],
                description=raw_col.get("description"),
                settings=settings_dict,
            )
        )

    return BoardSchema(
        board_id=str(meta.get("id", board_id)),
        board_name=meta.get("name", ""),
        description=meta.get("description"),
        items_count=meta.get("items_count"),
        columns=parsed_columns,
    )


def map_item_to_schema(item: dict[str, Any], schema: BoardSchema) -> dict[str, Any]:
    """Transform raw GraphQL item dict into a friendly dict keyed by column titles.
    
    Preserves linked_item_ids for BoardRelationValue columns.
    Treats Monday default placeholders like 'Unnamed' as None for item_name and Name columns.
    """
    raw_name = item.get("name")
    if raw_name is not None and str(raw_name).strip().lower() in ("unnamed", "unnamed item", "null", "none", ""):
        clean_name = None
    else:
        clean_name = raw_name

    mapped: dict[str, Any] = {
        "item_id": item.get("id"),
        "item_name": clean_name,
    }
    group = item.get("group")
    if group:
        mapped["group_id"] = group.get("id")
        mapped["group_title"] = group.get("title")

    for cv in item.get("column_values", []):
        col_id = cv.get("id")
        col_title = schema.get_column_title(col_id) or col_id
        
        # If it has linked_item_ids, expose them directly
        linked_ids = cv.get("linked_item_ids")
        if linked_ids is not None:
            mapped[col_title] = [str(lid) for lid in linked_ids]
            # Also keep a dedicated entry for linked_item_ids
            mapped[f"{col_title}__linked_ids"] = [str(lid) for lid in linked_ids]
        else:
            txt = cv.get("text")
            if col_title.lower() in ("name", "deal name", "deal name masked") and txt and txt.strip().lower() in ("unnamed", "unnamed item"):
                mapped[col_title] = None
            else:
                mapped[col_title] = txt

    return mapped

