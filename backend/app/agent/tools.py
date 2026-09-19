"""Agent tool definitions and dispatcher for Anthropic Claude.

Exposes deterministic analytics functions as structured Claude tool schemas.
All data fetching routes strictly through the read-only Monday MCP tools:
- get_work_orders()
- get_deals()
- get_board_schema()

No calculations are performed by the LLM. The LLM selects tools and passes
structured arguments; deterministic Python functions execute all arithmetic.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

import pandas as pd

from app.config import settings
from app.data.analytics import (
    compute_cross_board_delivery,
    compute_pipeline_summary,
    compute_revenue_summary,
    generate_leadership_update,
    get_data_quality_summary,
)
from app.data.normalize_deals import normalize_deals_df
from app.data.normalize_work_orders import normalize_work_orders_df
from app.monday_mcp.client import MondayAPIError
from app.monday_mcp.server import get_board_schema as mcp_get_board_schema
from app.monday_mcp.server import get_deals, get_work_orders

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Claude Tool Schemas
# ---------------------------------------------------------------------------

AGENT_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_pipeline_summary",
        "description": (
            "Retrieve deterministic pipeline health metrics for deals tracked on Monday.com. "
            "Returns active pipeline value (unweighted and probability-weighted), won deals volume, "
            "stage breakdown, and sector breakdown. Automatically includes caveats for unrecorded values and probabilities."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sector": {
                    "type": ["string", "null"],
                    "description": "Optional sector filter (e.g., 'Renewables', 'Powerline', 'Mining', 'Railways', 'Tender', 'DSP', 'Others'). Omit or null when no sector filter is wanted.",
                },
                "stage": {
                    "type": ["string", "null"],
                    "description": "Optional stage category filter ('active', 'won', 'lost'). Omit or null when no stage filter is wanted.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_revenue_summary",
        "description": (
            "Retrieve deterministic revenue, billing, and collection metrics from Work Orders on Monday.com. "
            "Returns total booking value, billed value (Excl/Incl GST), collected amounts, and net vs gross "
            "receivables. Isolates credit balances (overpayments) and negative billing adjustments."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sector": {
                    "type": ["string", "null"],
                    "description": "Optional sector filter (e.g., 'Renewables', 'Powerline', 'Mining', 'Railways'). Omit or null when no sector filter is wanted.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_cross_board_delivery",
        "description": (
            "Retrieve delivery and fulfillment alignment across linked Work Orders and Deals using live "
            "Monday.com Connect Boards relationships. Dynamically reports live link coverage and execution status."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sector": {
                    "type": ["string", "null"],
                    "description": "Optional sector filter. Omit or null when no sector filter is wanted.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_leadership_update",
        "description": (
            "Generate a comprehensive executive leadership update briefing covering revenue KPIs, "
            "pipeline velocity, cross-board delivery fulfillment, and critical data-integrity caveats."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "period": {
                    "type": ["string", "null"],
                    "description": "Optional period descriptor (e.g., 'This Week', 'Monthly', 'Q4 FY25-26'). Omit or null when no period is specified.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_data_quality_report",
        "description": (
            "Inspect data health, severe null rates across critical columns, UNKNOWN status counts, "
            "credit balance accounts, and GST sanity checks for Work Orders and/or Deals boards."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "board_name": {
                    "type": ["string", "null"],
                    "enum": ["work_orders", "deals", "both", None],
                    "description": "Which board to inspect ('work_orders', 'deals', or 'both'). Default is 'both'.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_board_schema",
        "description": (
            "Introspect column structures, titles, and IDs for Monday.com boards to inspect schema definition."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "board_type": {
                    "type": "string",
                    "enum": ["work_orders", "deals"],
                    "description": "Target board identifier ('work_orders' or 'deals').",
                },
            },
            "required": ["board_type"],
        },
    },
]


# ---------------------------------------------------------------------------
# Data Caching & Normalization Helpers for Tool Execution
# ---------------------------------------------------------------------------

def _find_data_file(filename: str) -> Path | None:
    """Locates a master data Excel file across multiple relative directory depths."""
    for base in [
        Path.cwd(),
        Path.cwd().parent,
        Path(__file__).resolve().parent,
        Path(__file__).resolve().parents[2],
        Path(__file__).resolve().parents[3],
    ]:
        candidate = base / filename
        if candidate.exists():
            return candidate
    return None


def _get_fallback_board_schema(board_type: str) -> dict[str, Any]:
    """Provides an offline static schema definition when live Monday API is unreachable."""
    if board_type == "deals":
        return {
            "board_id": settings.monday_deals_board_id or "5031416803",
            "board_name": "Deal Funnel",
            "description": "Offline schema fallback for Deal Funnel",
            "columns": [
                {"id": "name", "title": "Deal Name", "type": "name"},
                {"id": "deal_status", "title": "Deal Status", "type": "status"},
                {"id": "closure_prob", "title": "Closure Probability", "type": "numeric"},
                {"id": "deal_stage", "title": "Deal Stage", "type": "status"},
                {"id": "client_code", "title": "Client Code", "type": "text"},
                {"id": "deal_value", "title": "Deal Value", "type": "numeric"},
                {"id": "sector", "title": "Sector", "type": "status"},
            ],
        }
    return {
        "board_id": settings.monday_work_orders_board_id or "5031416769",
        "board_name": "Work Orders Tracker",
        "description": "Offline schema fallback for Work Orders",
        "columns": [
            {"id": "name", "title": "Serial #", "type": "name"},
            {"id": "customer_code", "title": "Customer Name Code", "type": "text"},
            {"id": "execution_status", "title": "Execution Status", "type": "status"},
            {"id": "expected_revenue", "title": "Expected Revenue (Excl. GST)", "type": "numeric"},
            {"id": "billed_value", "title": "Billed (Excl. GST)", "type": "numeric"},
            {"id": "payment_received", "title": "Payment Received", "type": "numeric"},
            {"id": "linked_deal", "title": "Linked Deal", "type": "board_relation"},
        ],
    }


def _load_normalized_work_orders() -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Fetches raw work orders from Monday MCP tool and returns normalized DataFrame + raw items.

    Gracefully falls back to the master Excel dataset if Monday API credentials are not
    configured or Monday API is unreachable.
    """
    try:
        raw_items = get_work_orders()
        df_raw = pd.DataFrame(raw_items)
        # Ensure item_id is retained
        if "item_id" in df_raw.columns:
            df_raw["item_id"] = df_raw["item_id"].astype(str)
        norm_df = normalize_work_orders_df(df_raw)
        if "item_id" in df_raw.columns:
            norm_df["item_id"] = df_raw["item_id"].values
        return norm_df, raw_items
    except (MondayAPIError, Exception) as exc:
        logger.warning(
            "Could not fetch live work orders from Monday (%s); loading offline master snapshot.", exc
        )
        file_path = _find_data_file("Work_Order_Tracker Data.xlsx")
        if file_path and file_path.exists():
            df_excel = pd.read_excel(file_path, header=1, keep_default_na=False)
            norm_df = normalize_work_orders_df(df_excel)
            raw_items = cast("list[dict[str, Any]]", df_excel.to_dict(orient="records"))
            return norm_df, raw_items
        raise


def _load_normalized_deals() -> pd.DataFrame:
    """Fetches raw deals from Monday MCP tool and returns normalized DataFrame.

    Gracefully falls back to the master Excel dataset if Monday API credentials are not
    configured or Monday API is unreachable.
    """
    try:
        raw_items = get_deals()
        df_raw = pd.DataFrame(raw_items)
        if "item_id" in df_raw.columns:
            df_raw["item_id"] = df_raw["item_id"].astype(str)
        norm_df = normalize_deals_df(df_raw)
        if "item_id" in df_raw.columns:
            norm_df["item_id"] = df_raw["item_id"].values
        return norm_df
    except (MondayAPIError, Exception) as exc:
        logger.warning(
            "Could not fetch live deals from Monday (%s); loading offline master snapshot.", exc
        )
        file_path = _find_data_file("Deal funnel Data.xlsx")
        if file_path and file_path.exists():
            df_excel = pd.read_excel(file_path, keep_default_na=False)
            norm_df = normalize_deals_df(df_excel)
            return norm_df
        raise


# ---------------------------------------------------------------------------
# Tool Dispatcher
# ---------------------------------------------------------------------------

def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Executes a requested tool deterministically and returns structured results.

    Defensively normalizes arguments: LLM tool calls may legitimately emit `null`
    for optional parameters (the JSON schemas allow `["string", "null"]`), so any
    None value is coerced to the tool's documented default instead of crashing.
    """
    args = dict(arguments or {})
    logger.info("Executing tool '%s' with arguments: %s", name, args)

    def _opt_str(key: str) -> str | None:
        """Returns a stripped string value, or None when absent/null/blank."""
        value = args.get(key)
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    if name == "get_pipeline_summary":
        deals_df = _load_normalized_deals()
        return compute_pipeline_summary(
            deals_df,
            sector=_opt_str("sector"),
            stage=_opt_str("stage"),
        )

    elif name == "get_revenue_summary":
        wo_df, _ = _load_normalized_work_orders()
        return compute_revenue_summary(wo_df, sector=_opt_str("sector"))

    elif name == "get_cross_board_delivery":
        wo_df, wo_items = _load_normalized_work_orders()
        deals_df = _load_normalized_deals()
        return compute_cross_board_delivery(
            wo_df, deals_df, wo_items=wo_items, sector=_opt_str("sector")
        )

    elif name == "get_leadership_update":
        wo_df, wo_items = _load_normalized_work_orders()
        deals_df = _load_normalized_deals()
        return generate_leadership_update(
            wo_df, deals_df, wo_items=wo_items, period=_opt_str("period")
        )

    elif name == "get_data_quality_report":
        board = (_opt_str("board_name") or "both").lower()
        if board not in ("work_orders", "work_order", "wo", "deals", "deal", "both"):
            board = "both"
        report_wo_df: pd.DataFrame | None
        report_wo_items: list[dict[str, Any]] | None
        report_deals_df: pd.DataFrame | None
        if board in ("work_orders", "work_order", "wo", "both"):
            report_wo_df, report_wo_items = _load_normalized_work_orders()
        else:
            report_wo_df, report_wo_items = None, None
        if board in ("deals", "deal", "both"):
            report_deals_df = _load_normalized_deals()
        else:
            report_deals_df = None
        return get_data_quality_summary(
            norm_wo_df=report_wo_df,
            norm_deals_df=report_deals_df,
            board_name=board,
            wo_items=report_wo_items,
        )

    elif name == "get_board_schema":
        b_type = _opt_str("board_type") or "work_orders"
        try:
            return mcp_get_board_schema(board_type=b_type)
        except (MondayAPIError, Exception) as exc:
            logger.warning(
                "Could not introspect live Monday board schema (%s); using offline static schema.", exc
            )
            return _get_fallback_board_schema(b_type)

    else:
        raise ValueError(f"Unknown tool requested: '{name}'")


def get_groq_tools() -> list[dict[str, Any]]:
    """Converts AGENT_TOOLS to Groq/OpenAI compatible function-calling schemas."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }
        for tool in AGENT_TOOLS
    ]

