"""Deals board normalization layer.

Implements repeated-header filtering, client code normalization, stage hierarchy
classification, sector normalization, closure probability validation, and numeric
deal value parsing for the Deals board.

Specification defined in NORMALIZATION_NOTES.md (§6, §7, §8) and PROJECT_PLAN.md §9.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

import pandas as pd

from app.data.normalize_work_orders import parse_messy_date, parse_messy_number

# ---------------------------------------------------------------------------
# Enums for Deals Controlled Vocabularies
# ---------------------------------------------------------------------------

class DealStatus(str, Enum):
    """Deal pipeline status."""
    WON = "Won"
    DEAD = "Dead"
    OPEN = "Open"
    ON_HOLD = "On Hold"
    UNKNOWN = "UNKNOWN"


class ClosureProbability(str, Enum):
    """Deal closure probability tier."""
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class DealStage(str, Enum):
    """16 stages of the sales funnel with alphanumeric progression."""
    # Active Pipeline (A - F)
    LEAD_GENERATED = "A. Lead Generated"
    SALES_QUALIFIED_LEADS = "B. Sales Qualified Leads"
    DEMO_DONE = "C. Demo Done"
    FEASIBILITY = "D. Feasibility"
    PROPOSAL_COMMERCIALS_SENT = "E. Proposal/Commercials Sent"
    NEGOTIATIONS = "F. Negotiations"

    # Won / Executing (G - K, Project Completed)
    PROJECT_WON = "G. Project Won"
    WORK_ORDER_RECEIVED = "H. Work Order Received"
    POC = "I. POC"
    INVOICE_SENT = "J. Invoice sent"
    AMOUNT_ACCRUED = "K. Amount Accrued"
    PROJECT_COMPLETED = "Project Completed"

    # Dormant / Lost (L - O)
    PROJECT_LOST = "L. Project Lost"
    PROJECTS_ON_HOLD = "M. Projects On Hold"
    NOT_RELEVANT_MOMENT = "N. Not relevant at the moment"
    NOT_RELEVANT_AT_ALL = "O. Not Relevant at all"

    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Header Filtering (Regression Protection)
# ---------------------------------------------------------------------------

def filter_clean_deals(df: pd.DataFrame) -> pd.DataFrame:
    """Filter out repeated embedded header rows from the raw Deals dataset.

    Specifically removes rows where `Deal Status == 'Deal Status'` or
    `Deal Stage == 'Deal Stage'` (indices 50 and 179 in raw data).
    Guarantees exactly 344 genuine records on the source dataset.
    """
    clean_df = df.copy()
    if "Deal Status" in clean_df.columns:
        clean_df = clean_df[clean_df["Deal Status"].astype(str).str.strip() != "Deal Status"]
    if "Deal Stage" in clean_df.columns:
        clean_df = clean_df[clean_df["Deal Stage"].astype(str).str.strip() != "Deal Stage"]
    if "Deal Name" in clean_df.columns:
        clean_df = clean_df[clean_df["Deal Name"].astype(str).str.strip() != "Deal Name"]
    return clean_df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Stage Hierarchy Classification (§7)
# ---------------------------------------------------------------------------

ACTIVE_PIPELINE_STAGES = {
    DealStage.LEAD_GENERATED.value,
    DealStage.SALES_QUALIFIED_LEADS.value,
    DealStage.DEMO_DONE.value,
    DealStage.FEASIBILITY.value,
    DealStage.PROPOSAL_COMMERCIALS_SENT.value,
    DealStage.NEGOTIATIONS.value,
}

WON_STAGES = {
    DealStage.PROJECT_WON.value,
    DealStage.WORK_ORDER_RECEIVED.value,
    DealStage.POC.value,
    DealStage.INVOICE_SENT.value,
    DealStage.AMOUNT_ACCRUED.value,
    DealStage.PROJECT_COMPLETED.value,
}

LOST_OR_DORMANT_STAGES = {
    DealStage.PROJECT_LOST.value,
    DealStage.PROJECTS_ON_HOLD.value,
    DealStage.NOT_RELEVANT_MOMENT.value,
    DealStage.NOT_RELEVANT_AT_ALL.value,
}

STAGE_ORDER_MAP = {
    DealStage.LEAD_GENERATED.value: 1,
    DealStage.SALES_QUALIFIED_LEADS.value: 2,
    DealStage.DEMO_DONE.value: 3,
    DealStage.FEASIBILITY.value: 4,
    DealStage.PROPOSAL_COMMERCIALS_SENT.value: 5,
    DealStage.NEGOTIATIONS.value: 6,
    DealStage.PROJECT_WON.value: 7,
    DealStage.WORK_ORDER_RECEIVED.value: 8,
    DealStage.POC.value: 9,
    DealStage.INVOICE_SENT.value: 10,
    DealStage.AMOUNT_ACCRUED.value: 11,
    DealStage.PROJECT_COMPLETED.value: 12,
    DealStage.PROJECT_LOST.value: 13,
    DealStage.PROJECTS_ON_HOLD.value: 14,
    DealStage.NOT_RELEVANT_MOMENT.value: 15,
    DealStage.NOT_RELEVANT_AT_ALL.value: 16,
}


def is_active_pipeline(stage: Any) -> bool:
    """Return True if the stage belongs to active sales pipeline (Stages A through F)."""
    if not stage or pd.isna(stage):
        return False
    return str(stage).strip() in ACTIVE_PIPELINE_STAGES


def is_won(stage: Any) -> bool:
    """Return True if the stage represents a won/executing deal (Stages G-K + Project Completed)."""
    if not stage or pd.isna(stage):
        return False
    return str(stage).strip() in WON_STAGES


def is_lost_or_dormant(stage: Any) -> bool:
    """Return True if the stage represents a lost or dormant deal (Stages L through O)."""
    if not stage or pd.isna(stage):
        return False
    return str(stage).strip() in LOST_OR_DORMANT_STAGES


def get_stage_order(stage: Any) -> int:
    """Return 1-16 progression order of the sales stage (99 if unknown)."""
    if not stage or pd.isna(stage):
        return 99
    return STAGE_ORDER_MAP.get(str(stage).strip(), 99)


# ---------------------------------------------------------------------------
# Sector Classification & Normalization (§8)
# ---------------------------------------------------------------------------

PROCUREMENT_CHANNELS = {"tender", "dsp"}

STANDARD_SECTORS = {
    "renewables": "Renewables",
    "mining": "Mining",
    "railways": "Railways",
    "powerline": "Powerline",
    "construction": "Construction",
    "manufacturing": "Manufacturing",
    "security and surveillance": "Security and Surveillance",
    "aviation": "Aviation",
    "others": "Others",
}


def is_procurement_channel(sector_val: Any) -> bool:
    """Return True if the sector value represents an operational/procurement channel (Tender, DSP)."""
    if not sector_val or pd.isna(sector_val):
        return False
    return str(sector_val).strip().lower() in PROCUREMENT_CHANNELS


def normalize_deal_sector(sector_val: Any) -> str | None:
    """Normalize Deals 'Sector/service' column.

    - Classifies 'Tender' as 'Others (Tender)'
    - Classifies 'DSP' as 'Others (DSP)'
    - Standardizes recognized industrial sectors
    - Returns None for missing values
    """
    if sector_val is None or pd.isna(sector_val):
        return None
    s = str(sector_val).strip()
    if not s or s.lower() in ("nan", "none", "null"):
        return None

    s_lower = s.lower()
    if s_lower == "tender":
        return "Others (Tender)"
    if s_lower == "dsp":
        return "Others (DSP)"

    return STANDARD_SECTORS.get(s_lower, s)


def match_sector_query(query: str) -> str | None:
    """Fuzzy/keyword matcher mapping conversational user query terms to standardized sectors."""
    q = query.lower()
    if any(k in q for k in ("energy", "solar", "wind", "renew")):
        return "Renewables"
    if any(k in q for k in ("mine", "mining", "quarry")):
        return "Mining"
    if any(k in q for k in ("rail", "railway", "train", "metro")):
        return "Railways"
    if any(k in q for k in ("power", "transmission", "grid", "powerline")):
        return "Powerline"
    if any(k in q for k in ("construction", "infra", "building")):
        return "Construction"
    if any(k in q for k in ("manufactur", "factory")):
        return "Manufacturing"
    if any(k in q for k in ("security", "surveillance")):
        return "Security and Surveillance"
    if any(k in q for k in ("aviation", "airport", "aircraft")):
        return "Aviation"
    return None


# ---------------------------------------------------------------------------
# Main Deals Normalization Function
# ---------------------------------------------------------------------------

def normalize_deals_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize raw Deals DataFrame according to NORMALIZATION_NOTES.md.

    - Drops duplicate header rows (asserts/guarantees 344 valid deals).
    - Preserves nulls across Close Date (A), Closure Probability, and Masked Deal value.
    - NEVER imputes missing Closure Probability (preserves 258 nulls for quality caveats).
    - Adds stage classifications: is_active_pipeline, is_won, is_lost_or_dormant, stage_order.
    - Isolates procurement channels (Tender, DSP) and provides normalized_sector.
    """
    clean_df = filter_clean_deals(df)
    norm_df = pd.DataFrame(index=clean_df.index)

    # 1. Deal Name (str | None, 2 rows null in data)
    col_name = "Deal Name"
    deal_name_col = col_name if col_name in clean_df.columns else ("item_name" if "item_name" in clean_df.columns else None)
    if deal_name_col is not None:
        norm_df[col_name] = clean_df[deal_name_col].apply(
            lambda x: str(x).strip() if pd.notna(x) and str(x).strip() not in ("", "nan", "None") else None
        )

    # 2. Owner code (str | None, 15 rows null)
    col_name = "Owner code"
    if col_name in clean_df.columns:
        norm_df[col_name] = clean_df[col_name].apply(
            lambda x: str(x).strip() if pd.notna(x) and str(x).strip() not in ("", "nan", "None") else None
        )

    # 3. Client Code (str, 100% non-null COMPANYxxx)
    col_name = "Client Code"
    if col_name in clean_df.columns:
        norm_df[col_name] = clean_df[col_name].astype(str).str.strip().str.upper()

    # 4. Deal Status (Enum: Won, Dead, Open, On Hold, UNKNOWN)
    col_name = "Deal Status"
    if col_name in clean_df.columns:
        def _clean_status(x: Any) -> str:
            if pd.isna(x) or str(x).strip() in ("", "nan", "None"):
                return DealStatus.UNKNOWN.value
            s = str(x).strip()
            for member in DealStatus:
                if member.value.lower() == s.lower():
                    return member.value
            return DealStatus.UNKNOWN.value
        norm_df[col_name] = clean_df[col_name].apply(_clean_status)

    # 5. Close Date (A) (date | None, 318 nulls, 26 dates - PRESERVE NULLS!)
    col_name = "Close Date (A)"
    if col_name in clean_df.columns:
        norm_df[col_name] = clean_df[col_name].apply(parse_messy_date)

    # 6. Closure Probability (Enum | None: High, Medium, Low, 258 nulls - NEVER IMPUTE!)
    col_name = "Closure Probability"
    if col_name in clean_df.columns:
        def _clean_prob(x: Any) -> str | None:
            if pd.isna(x) or str(x).strip() in ("", "nan", "None"):
                return None
            s = str(x).strip().capitalize()
            for p in ClosureProbability:
                if p.value.lower() == s.lower():
                    return p.value
            return None
        norm_df[col_name] = clean_df[col_name].apply(_clean_prob)

    # 7. Masked Deal value (float | None, 179 nulls, 165 positive floats)
    col_name = "Masked Deal value"
    if col_name in clean_df.columns:
        norm_df[col_name] = clean_df[col_name].apply(lambda x: parse_messy_number(x, allow_negative=False))

    # 8. Tentative Close Date (date | None, 74 nulls)
    col_name = "Tentative Close Date"
    if col_name in clean_df.columns:
        norm_df[col_name] = clean_df[col_name].apply(parse_messy_date)

    # 9. Deal Stage & Stage Classifications (§7)
    col_name = "Deal Stage"
    if col_name in clean_df.columns:
        norm_df[col_name] = clean_df[col_name].astype(str).str.strip()
        norm_df["is_active_pipeline"] = norm_df[col_name].apply(is_active_pipeline)
        norm_df["is_won"] = norm_df[col_name].apply(is_won)
        norm_df["is_lost_or_dormant"] = norm_df[col_name].apply(is_lost_or_dormant)
        norm_df["stage_order"] = norm_df[col_name].apply(get_stage_order)

    # 10. Product deal (Enum | None, 170 nulls)
    col_name = "Product deal"
    if col_name in clean_df.columns:
        norm_df[col_name] = clean_df[col_name].apply(
            lambda x: str(x).strip() if pd.notna(x) and str(x).strip() not in ("", "nan", "None") else None
        )

    # 11. Sector/service & Normalized Sector (§8)
    col_name = "Sector/service"
    if col_name in clean_df.columns:
        norm_df[col_name] = clean_df[col_name].apply(
            lambda x: str(x).strip() if pd.notna(x) and str(x).strip() not in ("", "nan", "None") else None
        )
        norm_df["is_procurement_channel"] = norm_df[col_name].apply(is_procurement_channel)
        norm_df["normalized_sector"] = norm_df[col_name].apply(normalize_deal_sector)
        norm_df["delivery_channel"] = norm_df[col_name].apply(
            lambda x: str(x).strip() if is_procurement_channel(x) else None
        )

    # 12. Created Date (date | None, 1 null row)
    col_name = "Created Date"
    if col_name in clean_df.columns:
        norm_df[col_name] = clean_df[col_name].apply(parse_messy_date)

    return norm_df

