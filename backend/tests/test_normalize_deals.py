"""Tests for Deals board normalization logic.

All tests utilize genuine records from `Deal funnel Data.xlsx` to verify:
- Regression guard: exactly 344 valid rows, 0 duplicate header rows.
- Funnel stage classifications (is_active_pipeline, is_won, is_lost_or_dormant).
- Sector normalization and procurement channel isolation (Tender, DSP).
- Severe null preservation for Closure Probability (75%), Deal Value (52%), Close Date (92%).
- One real null Deal Status row ('Tanjiro', COMPANY038) mapped to UNKNOWN.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pandas as pd
import pytest

from app.data.normalize_deals import (
    match_sector_query,
    normalize_deals_df,
)

DEALS_DATA_PATH = Path(__file__).resolve().parent.parent.parent / "Deal funnel Data.xlsx"


@pytest.fixture(scope="module")
def raw_deals_df() -> pd.DataFrame:
    """Load raw Deals DataFrame from Excel (includes 2 embedded header rows) with keep_default_na=False."""
    assert DEALS_DATA_PATH.exists(), f"Deals data file not found at {DEALS_DATA_PATH}"
    return pd.read_excel(DEALS_DATA_PATH, keep_default_na=False)


@pytest.fixture(scope="module")
def normalized_deals_df(raw_deals_df: pd.DataFrame) -> pd.DataFrame:
    """Load normalized Deals DataFrame."""
    return normalize_deals_df(raw_deals_df)


# ---------------------------------------------------------------------------
# 1. Header Contamination Regression Test (Mandated)
# ---------------------------------------------------------------------------

def test_regression_deals_header_contamination(raw_deals_df: pd.DataFrame, normalized_deals_df: pd.DataFrame) -> None:
    """Regression test: deals_df has exactly 344 rows and 0 duplicate header rows.

    The raw Excel file has 347 rows (headers + 346 rows), where rows 50 and 179
    are duplicate headers ('Deal Status' == 'Deal Status'). This test guarantees
    this bug can never silently reappear.
    """
    # Verify raw file actually contains the duplicate header rows
    raw_header_rows = raw_deals_df[raw_deals_df["Deal Status"] == "Deal Status"]
    assert len(raw_header_rows) == 2

    # Assert normalized deals has exactly 344 rows
    assert len(normalized_deals_df) == 344

    # Assert zero residual duplicate header rows exist
    assert not (normalized_deals_df["Deal Status"] == "Deal Status").any()
    assert not (normalized_deals_df["Deal Stage"] == "Deal Stage").any()
    assert not (normalized_deals_df["Deal Name"] == "Deal Name").any()


# ---------------------------------------------------------------------------
# 2. Stage Classification (§7)
# ---------------------------------------------------------------------------

def test_stage_classification_active_pipeline(normalized_deals_df: pd.DataFrame) -> None:
    """Verify at least one real deal in active pipeline bucket (Stages A through F)."""
    active_deals = normalized_deals_df[normalized_deals_df["is_active_pipeline"]]
    assert len(active_deals) == 142  # 74 + 14 + 9 + 4 + 28 + 13

    # Check a specific real active deal: Row 0 has 'B. Sales Qualified Leads'
    row_0 = normalized_deals_df.iloc[0]
    assert row_0["Deal Stage"] == "B. Sales Qualified Leads"
    assert bool(row_0["is_active_pipeline"]) is True
    assert bool(row_0["is_won"]) is False
    assert bool(row_0["is_lost_or_dormant"]) is False
    assert row_0["stage_order"] == 2


def test_stage_classification_won(normalized_deals_df: pd.DataFrame) -> None:
    """Verify at least one real deal in won bucket (Stages G-K + Project Completed)."""
    won_deals = normalized_deals_df[normalized_deals_df["is_won"]]
    assert len(won_deals) == 103  # 27 + 46 + 3 + 6 + 2 + 19

    # Find a real deal with Stage 'G. Project Won'
    sample_won = normalized_deals_df[normalized_deals_df["Deal Stage"] == "G. Project Won"].iloc[0]
    assert bool(sample_won["is_won"]) is True
    assert bool(sample_won["is_active_pipeline"]) is False
    assert bool(sample_won["is_lost_or_dormant"]) is False
    assert sample_won["stage_order"] == 7

    # Find a real deal with Stage 'Project Completed'
    sample_completed = normalized_deals_df[normalized_deals_df["Deal Stage"] == "Project Completed"].iloc[0]
    assert bool(sample_completed["is_won"]) is True
    assert bool(sample_completed["is_active_pipeline"]) is False
    assert bool(sample_completed["is_lost_or_dormant"]) is False
    assert sample_completed["stage_order"] == 12


def test_stage_classification_lost_or_dormant(normalized_deals_df: pd.DataFrame) -> None:
    """Verify at least one real deal in lost/dormant bucket (Stages L through O)."""
    dormant_deals = normalized_deals_df[normalized_deals_df["is_lost_or_dormant"]]
    assert len(dormant_deals) == 99  # 42 + 20 + 19 + 18

    # Find a real deal with Stage 'L. Project Lost'
    sample_lost = normalized_deals_df[normalized_deals_df["Deal Stage"] == "L. Project Lost"].iloc[0]
    assert bool(sample_lost["is_lost_or_dormant"]) is True
    assert bool(sample_lost["is_active_pipeline"]) is False
    assert bool(sample_lost["is_won"]) is False
    assert sample_lost["stage_order"] == 13


def test_all_deals_classified_into_exactly_one_bucket(normalized_deals_df: pd.DataFrame) -> None:
    """Assert all 344 deals fall into exactly one stage classification bucket."""
    active_count = normalized_deals_df["is_active_pipeline"].sum()
    won_count = normalized_deals_df["is_won"].sum()
    dormant_count = normalized_deals_df["is_lost_or_dormant"].sum()

    assert active_count + won_count + dormant_count == 344


# ---------------------------------------------------------------------------
# 3. Sector & Procurement Channel Normalization (§8)
# ---------------------------------------------------------------------------

def test_procurement_channels_isolated(normalized_deals_df: pd.DataFrame) -> None:
    """Tender (5 rows) and DSP (7 rows) isolated as procurement channels."""
    procurement_deals = normalized_deals_df[normalized_deals_df["is_procurement_channel"]]
    assert len(procurement_deals) == 12

    # Check Tender rows
    tenders = normalized_deals_df[normalized_deals_df["Sector/service"] == "Tender"]
    assert len(tenders) == 5
    assert (tenders["is_procurement_channel"] == True).all()
    assert (tenders["normalized_sector"] == "Others (Tender)").all()

    # Check DSP rows
    dsps = normalized_deals_df[normalized_deals_df["Sector/service"] == "DSP"]
    assert len(dsps) == 7
    assert (dsps["is_procurement_channel"] == True).all()
    assert (dsps["normalized_sector"] == "Others (DSP)").all()


def test_standard_sectors_preserved(normalized_deals_df: pd.DataFrame) -> None:
    """Standard industrial sectors retain clean names without being flagged as procurement channels."""
    renewables = normalized_deals_df[normalized_deals_df["Sector/service"] == "Renewables"]
    assert len(renewables) == 111
    assert (renewables["is_procurement_channel"] == False).all()
    assert (renewables["normalized_sector"] == "Renewables").all()

    mining = normalized_deals_df[normalized_deals_df["Sector/service"] == "Mining"]
    assert len(mining) == 106
    assert (mining["is_procurement_channel"] == False).all()


def test_match_sector_query() -> None:
    """Fuzzy/keyword query mapper maps conversational terms to sectors."""
    assert match_sector_query("what is our energy sector pipeline?") == "Renewables"
    assert match_sector_query("show me revenue from mines") == "Mining"
    assert match_sector_query("trains and rail deals") == "Railways"
    assert match_sector_query("transmission power grid") == "Powerline"
    assert match_sector_query("unrelated text") is None


# ---------------------------------------------------------------------------
# 4. Severe Null Rate Preservation (Must NEVER Default or Drop)
# ---------------------------------------------------------------------------

def test_closure_probability_null_preservation(normalized_deals_df: pd.DataFrame) -> None:
    """Closure Probability has 258 nulls (75.0%) and must NEVER be defaulted to Medium/Low."""
    col = "Closure Probability"
    null_count = normalized_deals_df[col].isna().sum()
    assert null_count == 258

    # Non-null values must be High, Medium, Low
    non_null_vals = set(normalized_deals_df[col].dropna().unique())
    assert non_null_vals == {"High", "Medium", "Low"}


def test_masked_deal_value_null_preservation(normalized_deals_df: pd.DataFrame) -> None:
    """Masked Deal value has 179 nulls (52.0%) and 165 positive values."""
    col = "Masked Deal value"
    null_count = normalized_deals_df[col].isna().sum()
    assert null_count == 179

    non_nulls = normalized_deals_df[col].dropna()
    assert len(non_nulls) == 165
    assert (non_nulls > 0).all()
    assert pytest.approx(non_nulls.min(), 0.01) == 51440.30


def test_close_date_null_preservation(normalized_deals_df: pd.DataFrame) -> None:
    """Close Date (A) has 318 nulls (92.4%) and exactly 26 valid dates."""
    col = "Close Date (A)"
    null_count = normalized_deals_df[col].isna().sum()
    assert null_count == 318

    valid_dates = normalized_deals_df[col].dropna()
    assert len(valid_dates) == 26
    assert all(isinstance(d, datetime.date) for d in valid_dates)


# ---------------------------------------------------------------------------
# 5. Null Fallback for Single Missing Deal Status Row
# ---------------------------------------------------------------------------

def test_single_null_deal_status_mapped_to_unknown(normalized_deals_df: pd.DataFrame) -> None:
    """The 1 real row where Deal Status was null ('Tanjiro', COMPANY038) is mapped to UNKNOWN."""
    tanjiro_row = normalized_deals_df[
        (normalized_deals_df["Deal Name"] == "Tanjiro") &
        (normalized_deals_df["Client Code"] == "COMPANY038")
    ].iloc[0]
    assert tanjiro_row["Deal Status"] == "UNKNOWN"

