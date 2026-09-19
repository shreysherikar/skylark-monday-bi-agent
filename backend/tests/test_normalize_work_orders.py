"""Tests for Work Orders normalization logic.

All tests utilize genuine values from `Work_Order_Tracker Data.xlsx` to verify:
- Negative value preservation across all 4 negative-bearing columns.
- Schema retention of the four 100% null columns.
- Free-text PO quantity parser across 10+ real documented string patterns.
- Controlled vocabularies, status orthogonality, and date/month parsing.
- Full 176-row DataFrame normalization.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pandas as pd
import pytest

from app.data.normalize_work_orders import (
    normalize_client_code,
    normalize_month_name,
    normalize_status,
    normalize_work_orders_df,
    parse_messy_date,
    parse_messy_number,
    parse_po_quantity,
)

DATA_PATH = Path(__file__).resolve().parent.parent.parent / "Work_Order_Tracker Data.xlsx"


@pytest.fixture(scope="module")
def raw_wo_df() -> pd.DataFrame:
    """Load raw Work Orders DataFrame from Excel (skipping the empty top row) with keep_default_na=False."""
    assert DATA_PATH.exists(), f"Work Orders data file not found at {DATA_PATH}"
    return pd.read_excel(DATA_PATH, header=1, keep_default_na=False)


@pytest.fixture(scope="module")
def normalized_wo_df(raw_wo_df: pd.DataFrame) -> pd.DataFrame:
    """Load normalized Work Orders DataFrame."""
    return normalize_work_orders_df(raw_wo_df)


# ---------------------------------------------------------------------------
# 1. Dataset Integrity & Row Count
# ---------------------------------------------------------------------------

def test_work_orders_row_count(normalized_wo_df: pd.DataFrame) -> None:
    """Assert exactly 176 data rows are produced from raw Work Orders."""
    assert len(normalized_wo_df) == 176
    assert normalized_wo_df["Serial #"].nunique() == 176


# ---------------------------------------------------------------------------
# 2. Schema Retention of the Four Fully-Null Columns
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("col", [
    "Expected Billing Month",
    "Actual Collection Month",
    "Collection status",
    "Collection Date",
])
def test_fully_null_columns_preserved_in_schema(normalized_wo_df: pd.DataFrame, col: str) -> None:
    """The four fully-null columns must be preserved in schema and contain 100% nulls."""
    assert col in normalized_wo_df.columns, f"Column '{col}' was omitted from schema"
    assert normalized_wo_df[col].isna().sum() == 176, f"Column '{col}' expected 176 nulls, got non-null values"


# ---------------------------------------------------------------------------
# 3. Legitimate Negative Values (Must NOT be Clamped to Zero or Dropped)
# ---------------------------------------------------------------------------

def test_amount_to_be_billed_excl_negatives(normalized_wo_df: pd.DataFrame) -> None:
    """Amount to be billed (Excl of GST) must preserve 6 negative rows with min −₹82,907.30."""
    col = "Amount to be billed in Rs. (Exl. of GST) (Masked)"
    neg_rows = normalized_wo_df[normalized_wo_df[col] < 0]
    assert len(neg_rows) == 6
    assert pytest.approx(neg_rows[col].min(), 0.01) == -82907.30

    # Specific real row check: SDPLDEAL-004
    deal_004 = normalized_wo_df[normalized_wo_df["Serial #"] == "SDPLDEAL-004"].iloc[0]
    assert pytest.approx(deal_004[col], 0.01) == -82907.30


def test_amount_to_be_billed_incl_negatives(normalized_wo_df: pd.DataFrame) -> None:
    """Amount to be billed (Incl of GST) must preserve 6 negative rows with min −₹97,830.61."""
    col = "Amount to be billed in Rs. (Incl. of GST) (Masked)"
    neg_rows = normalized_wo_df[normalized_wo_df[col] < 0]
    assert len(neg_rows) == 6
    assert pytest.approx(neg_rows[col].min(), 0.01) == -97830.61

    # Specific real row check: SDPLDEAL-004
    deal_004 = normalized_wo_df[normalized_wo_df["Serial #"] == "SDPLDEAL-004"].iloc[0]
    assert pytest.approx(deal_004[col], 0.01) == -97830.61


def test_amount_receivable_negatives(normalized_wo_df: pd.DataFrame) -> None:
    """Amount Receivable must preserve 11 negative rows with min −₹160.24 (credit balances)."""
    col = "Amount Receivable (Masked)"
    neg_rows = normalized_wo_df[normalized_wo_df[col] < 0]
    assert len(neg_rows) == 11
    assert pytest.approx(neg_rows[col].min(), 0.01) == -160.24

    # Specific real row check: SDPLDEAL-019
    deal_019 = normalized_wo_df[normalized_wo_df["Serial #"] == "SDPLDEAL-019"].iloc[0]
    assert pytest.approx(deal_019[col], 0.01) == -160.24


def test_balance_in_quantity_negatives(normalized_wo_df: pd.DataFrame) -> None:
    """Balance in quantity must preserve 2 negative values (-0.01 and -1309.85)."""
    col = "Balance in quantity"
    neg_rows = normalized_wo_df[normalized_wo_df[col] < 0]
    assert len(neg_rows) == 2

    # SDPLDEAL-048 has -0.01, SDPLDEAL-072 has -1309.85
    deal_048 = normalized_wo_df[normalized_wo_df["Serial #"] == "SDPLDEAL-048"].iloc[0]
    assert pytest.approx(deal_048[col], 0.001) == -0.01

    deal_072 = normalized_wo_df[normalized_wo_df["Serial #"] == "SDPLDEAL-072"].iloc[0]
    assert pytest.approx(deal_072[col], 0.01) == -1309.85


# ---------------------------------------------------------------------------
# 4. Quantity Parser Against Real Documented String Variants (§4)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw_str,expected_val,expected_unit,expected_qual", [
    # Pure numeric
    ("4", 4.0, None, False),
    ("3000", 3000.0, None, False),
    ("59.33", 59.33, None, False),
    # Comma-formatted numbers
    ("1,310.850", 1310.85, None, False),
    ("4,875,000.000", 4875000.0, None, False),
    # Standard units with space
    ("5360 HA", 5360.0, "HA", False),
    ("10.5 KM", 10.5, "KM", False),
    ("1415 Acres", 1415.0, "Acres", False),
    ("7000 images", 7000.0, "images", False),
    ("1250 towers", 1250.0, "towers", False),
    ("45 days", 45.0, "days", False),
    ("18 Months", 18.0, "months", False),
    ("3 subscriptions", 3.0, "subscriptions", False),
    ("4 Sites", 4.0, "sites", False),
    # Attached units
    ("115HA", 115.0, "HA", False),
    ("40MW", 40.0, "MW", False),
    ("45days", 45.0, "days", False),
    ("415Acers", 415.0, "Acres", False),
    ("2057 Acr", 2057.0, "Acres", False),
    # Quarter pattern
    ("3 Quarter (Till Dec)", 3.0, "Quarter", False),
    # Qualitative / non-numeric
    ("L/s", None, "L/s", True),
    ("Rate based on MW slabs", None, "Rate based on MW slabs", True),
    ("NA . Verbal confirmation for 59 km", 59.0, "KM", True),
])
def test_quantity_parser_real_variants(
    raw_str: str,
    expected_val: float | None,
    expected_unit: str | None,
    expected_qual: bool,
) -> None:
    """Test parse_po_quantity against 20+ real variants from Quantities as per PO."""
    res = parse_po_quantity(raw_str)
    if expected_val is not None:
        assert res.value is not None
        assert pytest.approx(res.value, 0.001) == expected_val
    else:
        assert res.value is None

    assert res.unit == expected_unit
    assert res.is_qualitative == expected_qual


def test_quantity_parser_null() -> None:
    """Test parse_po_quantity on null/blank input."""
    res = parse_po_quantity(None)
    assert res.value is None
    assert res.unit is None
    assert res.is_qualitative is False


# ---------------------------------------------------------------------------
# 5. Column-by-Column Real Data Rules
# ---------------------------------------------------------------------------

def test_client_code_normalization() -> None:
    """Test client code normalization on real WO client codes."""
    assert normalize_client_code("WOCOMPANY_002") == "COMPANY002"
    assert normalize_client_code("WOCOMPANY_038") == "COMPANY038"
    assert normalize_client_code("COMPANY100") == "COMPANY100"
    assert normalize_client_code(None) is None


def test_deal_name_masked_null_preserved(normalized_wo_df: pd.DataFrame) -> None:
    """Deal name masked has 1 real null row (SDPLDEAL-189) which must be None."""
    row = normalized_wo_df[normalized_wo_df["Serial #"] == "SDPLDEAL-189"].iloc[0]
    assert row["Deal name masked"] is None or pd.isna(row["Deal name masked"])

    valid_row = normalized_wo_df[normalized_wo_df["Serial #"] == "SDPLDEAL-075"].iloc[0]
    assert valid_row["Deal name masked"] == "Scooby-Doo"


def test_date_parsing_real_values(normalized_wo_df: pd.DataFrame) -> None:
    """Date of PO/LOI and Data Delivery Date parsed into datetime.date."""
    # SDPLDEAL-075 Date of PO/LOI: 2025-10-29
    deal_075 = normalized_wo_df[normalized_wo_df["Serial #"] == "SDPLDEAL-075"].iloc[0]
    assert deal_075["Date of PO/LOI"] == datetime.date(2025, 10, 29)
    assert deal_075["Data Delivery Date"] == datetime.date(2025, 9, 27)

    # 1 row with NaT PO date (SDPLDEAL-178)
    deal_178 = normalized_wo_df[normalized_wo_df["Serial #"] == "SDPLDEAL-178"].iloc[0]
    assert deal_178["Date of PO/LOI"] is None or pd.isna(deal_178["Date of PO/LOI"])


def test_month_normalization() -> None:
    """Month abbreviations normalized to full English month names."""
    assert normalize_month_name("Dec") == "December"
    assert normalize_month_name("June") == "June"
    assert normalize_month_name("November") == "November"
    assert normalize_month_name(None) is None


def test_status_vocabularies_and_orthogonality(normalized_wo_df: pd.DataFrame) -> None:
    """Verify orthogonal status dimensions and valid enum mappings."""
    # Execution status
    exec_statuses = set(normalized_wo_df["Execution Status"].unique())
    assert "Completed" in exec_statuses
    assert "Ongoing" in exec_statuses
    assert "Executed until current month" in exec_statuses
    assert "UNKNOWN" in exec_statuses

    # Invoice status
    inv_statuses = set(normalized_wo_df["Invoice Status"].unique())
    assert "Fully Billed" in inv_statuses
    assert "Partially Billed" in inv_statuses
    assert "Not billed yet" in inv_statuses
    assert "NOT_BILLED" in inv_statuses
    assert "UNKNOWN_WITH_BILLING" in inv_statuses

    # WO Status (billed)
    wo_statuses = set(normalized_wo_df["WO Status (billed)"].unique())
    assert wo_statuses.issubset({"Closed", "Open", "UNKNOWN"})

    # Billing status (including BIlled -> BILLED typo fix, and 148 nulls as None)
    billing_statuses = set(normalized_wo_df["Billing Status"].dropna().unique())
    assert "BILLED" in billing_statuses
    assert "BIlled" not in billing_statuses
    assert "UNKNOWN" not in billing_statuses
    assert normalized_wo_df["Billing Status"].isna().sum() == 148


def test_invoice_status_conditional_split(normalized_wo_df: pd.DataFrame) -> None:
    """Assert conditional split: 54 rows map to NOT_BILLED, 10 rows map to UNKNOWN_WITH_BILLING."""
    col = "Invoice Status"
    not_billed = normalized_wo_df[normalized_wo_df[col] == "NOT_BILLED"]
    unknown_billing = normalized_wo_df[normalized_wo_df[col] == "UNKNOWN_WITH_BILLING"]

    assert len(not_billed) == 54
    assert len(unknown_billing) == 10

    # Test specific real row: SDPLDEAL-002 has billed value > 0 and null invoice status -> UNKNOWN_WITH_BILLING
    deal_002 = normalized_wo_df[normalized_wo_df["Serial #"] == "SDPLDEAL-002"].iloc[0]
    assert deal_002[col] == "UNKNOWN_WITH_BILLING"
    assert deal_002["Billed Value in Rupees (Excl of GST.) (Masked)"] > 0

    # Test specific real row: SDPLDEAL-075 has no billed value and null invoice status -> NOT_BILLED
    deal_075 = normalized_wo_df[normalized_wo_df["Serial #"] == "SDPLDEAL-075"].iloc[0]
    assert deal_075[col] == "NOT_BILLED"


def test_platform_deliverables(normalized_wo_df: pd.DataFrame) -> None:
    """Skylark platform column maps 12 nulls to NONE."""
    platforms = set(normalized_wo_df["Is any Skylark software platform part of the client deliverables in this deal?"].unique())
    assert platforms == {"NONE", "SPECTRA", "DMO", "SPECTRA + DMO"}
    # Verify no nulls exist
    assert normalized_wo_df["Is any Skylark software platform part of the client deliverables in this deal?"].isna().sum() == 0


def test_ar_priority_account(normalized_wo_df: pd.DataFrame) -> None:
    """AR Priority account mapped to boolean: exactly 10 True rows."""
    col = "AR Priority account"
    assert normalized_wo_df[col].dtype == bool
    assert normalized_wo_df[col].sum() == 10


def test_unbilled_and_uncollected_null_preservation(normalized_wo_df: pd.DataFrame) -> None:
    """Billed Value (Excl) has 63 nulls (not 0); Collected Amount has 98 nulls (not 0)."""
    excl_billed = "Billed Value in Rupees (Excl of GST.) (Masked)"
    collected = "Collected Amount in Rupees (Incl of GST.) (Masked)"

    assert normalized_wo_df[excl_billed].isna().sum() == 63
    assert (normalized_wo_df[excl_billed] == 0).sum() == 0

    assert normalized_wo_df[collected].isna().sum() == 98
    assert (normalized_wo_df[collected] == 0).sum() == 0


def test_parse_messy_number_edge_cases() -> None:
    """Test parse_messy_number with currency, comma, accounting parentheses, and negative clamping."""
    assert parse_messy_number("₹ 1,234.50") == 1234.50
    assert parse_messy_number("Rs. 50,000") == 50000.0
    assert parse_messy_number("(1,500.25)") == -1500.25
    assert parse_messy_number("−82,907.30") == -82907.30
    assert parse_messy_number("-500", allow_negative=False) is None
    assert parse_messy_number("invalid_text") is None
    assert parse_messy_number("-") is None
    assert parse_messy_number(None) is None


def test_parse_messy_date_edge_cases() -> None:
    """Test parse_messy_date with strings, Timestamps, Excel serials, and invalid blanks."""
    assert parse_messy_date("2025-10-29") == datetime.date(2025, 10, 29)
    assert parse_messy_date(pd.Timestamp("2025-10-29")) == datetime.date(2025, 10, 29)
    assert parse_messy_date(datetime.datetime(2025, 10, 29, 12, 0)) == datetime.date(2025, 10, 29)  # noqa: DTZ001 - naive datetime is intentional test input
    # Excel serial 45594 corresponds to 2024-10-29
    assert parse_messy_date(45594) == datetime.date(2024, 10, 29)
    assert parse_messy_date("invalid_date") is None
    assert parse_messy_date(None) is None


def test_normalize_status_fallbacks() -> None:
    """Test normalize_status unknown handling across dimensions."""
    assert normalize_status("completely_unknown_status", "Execution Status") == "UNKNOWN"
    assert normalize_status("weird_doc", "Document Type") == "UNKNOWN"
    assert normalize_status("random_nature", "Nature of Work") == "UNKNOWN"
    assert normalize_status(None, "Execution Status") == "UNKNOWN"
    assert normalize_status("weird_invoice", "Invoice Status") == "UNKNOWN"
    assert normalize_status("", "Invoice Status") == "NOT_BILLED"
    assert normalize_status("", "Invoice Status", billed_val_excl=5000) == "UNKNOWN_WITH_BILLING"
    assert normalize_status(None, "Billing Status") is None


def test_keep_default_na_false_preserves_literal_na(normalized_wo_df: pd.DataFrame) -> None:
    """Regression test: keep_default_na=False preserves literal 'NA' strings in Quantities as per PO."""
    na_serials = ["SDPLDEAL-063", "SDPLDEAL-078", "SDPLDEAL-079", "SDPLDEAL-133"]
    for serial in na_serials:
        row = normalized_wo_df[normalized_wo_df["Serial #"] == serial].iloc[0]
        assert row["po_quantity_raw"] == "NA"
        assert bool(row["po_quantity_is_qualitative"]) is True
        assert row["po_quantity_unit"] == "NA"
        assert pd.isna(row["po_quantity_value"])


def test_sdpldeal_189_unnamed_placeholder_treated_as_null(normalized_wo_df: pd.DataFrame) -> None:
    """Regression test: Monday's 'Unnamed' placeholder or blank for SDPLDEAL-189 is treated as null."""
    row = normalized_wo_df[normalized_wo_df["Serial #"] == "SDPLDEAL-189"].iloc[0]
    assert pd.isna(row["Deal name masked"]) or row["Deal name masked"] is None

    # Explicitly test that passing 'Unnamed' or 'Unnamed Item' normalizes to None
    test_df = pd.DataFrame({
        "Serial #": ["SDPLDEAL-998", "SDPLDEAL-999"],
        "Deal name masked": ["Unnamed", "Unnamed Item"],
        "Customer Name Code": ["WOCOMPANY_001", "WOCOMPANY_001"],
    })
    res = normalize_work_orders_df(test_df)
    assert pd.isna(res.loc[0, "Deal name masked"]) or res.loc[0, "Deal name masked"] is None
    assert pd.isna(res.loc[1, "Deal name masked"]) or res.loc[1, "Deal name masked"] is None


