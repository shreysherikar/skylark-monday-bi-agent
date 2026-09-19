"""Monday.com GraphQL API client for dynamic board querying.

Enforces strictly read-only access at the code level:
- No mutation methods exist or are exposed.
- All query strings are defensively checked to block any mutation keyword.
- Provides custom exceptions for auth, rate limits, missing boards, and mutation attempts.
"""

from __future__ import annotations

import logging
import re
from typing import Any, cast

import requests

from app.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class MondayAPIError(Exception):
    """Base exception for all Monday.com API errors."""


class MondayAuthenticationError(MondayAPIError):
    """Raised when authentication fails (missing/invalid token, 401, 403)."""


class MondayBoardNotFoundError(MondayAPIError):
    """Raised when a requested board ID does not exist or is inaccessible."""


class MondayRateLimitError(MondayAPIError):
    """Raised when the API rate limit or complexity budget is exceeded (HTTP 429)."""


class ReadOnlyViolationError(MondayAPIError):
    """Raised when any mutation query is attempted."""


# ---------------------------------------------------------------------------
# Client Implementation
# ---------------------------------------------------------------------------

class MondayClient:
    """Thin, strictly read-only GraphQL client for Monday.com API v2."""

    MUTATION_PATTERN = re.compile(r"\bmutation\b", re.IGNORECASE)

    def __init__(
        self,
        api_token: str | None = None,
        api_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_token = api_token if api_token is not None else settings.monday_api_token
        self.api_url = api_url or settings.monday_api_url
        self.api_version = "2024-10"
        self.timeout = timeout
        self.request_count = 0

    def _validate_read_only(self, query: str) -> None:
        """Enforces that the query does not contain mutation operations."""
        if self.MUTATION_PATTERN.search(query):
            raise ReadOnlyViolationError(
                "Mutations are strictly prohibited: MondayClient is read-only."
            )

    def execute_query(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a read-only GraphQL query against Monday.com.
        
        Args:
            query: The GraphQL query string (must not contain mutations).
            variables: Optional variables mapping.
            
        Returns:
            The 'data' dictionary from the GraphQL response.
            
        Raises:
            ReadOnlyViolationError: If a mutation is detected.
            MondayAuthenticationError: If token is missing, invalid, or unauthorized.
            MondayRateLimitError: If HTTP 429 or complexity limit is hit.
            MondayBoardNotFoundError: If a board cannot be found.
            MondayAPIError: For other HTTP or GraphQL errors.
        """
        self._validate_read_only(query)

        if not self.api_token or not self.api_token.strip():
            raise MondayAuthenticationError("Monday API token is missing or not configured.")

        headers = {
            "Authorization": self.api_token.strip(),
            "API-Version": self.api_version,
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "query": query,
            "variables": variables or {},
        }

        try:
            self.request_count += 1
            response = requests.post(
                self.api_url,
                json=cast("Any", payload),
                headers=headers,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise MondayAPIError(f"Network error connecting to Monday.com: {exc}") from exc

        # Handle HTTP status errors
        if response.status_code in (401, 403):
            raise MondayAuthenticationError(
                f"Authentication failed ({response.status_code}): {response.text}"
            )
        if response.status_code == 429:
            raise MondayRateLimitError(
                f"Monday.com API rate limit exceeded (HTTP 429): {response.text}"
            )
        if response.status_code == 404:
            raise MondayBoardNotFoundError(
                f"Monday.com API endpoint or board not found (HTTP 404): {response.text}"
            )
        if response.status_code >= 400:
            raise MondayAPIError(
                f"Monday.com API HTTP error {response.status_code}: {response.text}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise MondayAPIError(f"Malformed JSON from Monday.com API: {response.text}") from exc

        # Handle GraphQL-level errors
        if body.get("errors"):
            error_list = body["errors"]
            first_msg = error_list[0].get("message", "") if isinstance(error_list, list) else str(error_list)
            first_lower = first_msg.lower()

            if "not authenticated" in first_lower or "unauthorized" in first_lower:
                raise MondayAuthenticationError(f"Monday API authentication error: {first_msg}")
            if "complexity" in first_lower or "budget exhausted" in first_lower:
                raise MondayRateLimitError(f"Monday API complexity limit exceeded: {first_msg}")
            if "not found" in first_lower or "invalid board" in first_lower:
                raise MondayBoardNotFoundError(f"Monday API board not found: {first_msg}")

            raise MondayAPIError(f"Monday API GraphQL error: {first_msg}")

        return cast("dict[str, Any]", body.get("data", {}))

    def fetch_board_metadata(self, board_id: str) -> dict[str, Any]:
        """Fetch board schema metadata (name, description, columns)."""
        query = """
        query GetBoardMetadata($boardId: [ID!]) {
            boards(ids: $boardId) {
                id
                name
                description
                items_count
                columns {
                    id
                    title
                    type
                    description
                    settings_str
                }
            }
        }
        """
        data = self.execute_query(query, variables={"boardId": [str(board_id)]})
        boards = data.get("boards", [])
        if not boards:
            raise MondayBoardNotFoundError(f"Board with ID '{board_id}' was not found.")
        return cast("dict[str, Any]", boards[0])

    def fetch_board_items(self, board_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch all items from a board using cursor-based pagination.
        
        Extracts item ID, name, and column values, including linked items from BoardRelationValue.
        """
        query = """
        query GetBoardItems($boardId: [ID!], $cursor: String, $limit: Int!) {
            boards(ids: $boardId) {
                id
                name
                items_page(limit: $limit, cursor: $cursor) {
                    cursor
                    items {
                        id
                        name
                        group {
                            id
                            title
                        }
                        column_values {
                            id
                            type
                            text
                            value
                            ... on BoardRelationValue {
                                linked_item_ids
                            }
                        }
                    }
                }
            }
        }
        """
        items: list[dict[str, Any]] = []
        cursor: str | None = None

        while True:
            variables: dict[str, Any] = {
                "boardId": [str(board_id)],
                "limit": limit,
            }
            if cursor:
                variables["cursor"] = cursor

            data = self.execute_query(query, variables=variables)
            boards = data.get("boards", [])
            if not boards:
                raise MondayBoardNotFoundError(f"Board with ID '{board_id}' was not found.")

            page = boards[0].get("items_page", {})
            page_items = page.get("items", [])
            items.extend(page_items)

            cursor = page.get("cursor")
            if not cursor or len(page_items) == 0:
                break

        return items

