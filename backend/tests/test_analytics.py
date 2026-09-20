"""Tests for data quality reporting and GST sanity check.

Verifies:
- The Excl-vs-Incl GST relationship (Incl ≈ Excl × 1.18) as a sanity check
  flagged in the quality report, NOT an enforced hard rule.
- Identification of the four 100% null columns in Work Orders.
- Severe null rate metrics for Deals (Closure Probability, Masked Deal value).
- Caveat text generation for agent injection (§9).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.data.analytics import (
    compute_cross_board_delivery,
    compute_pipeline_summary,
    compute_revenue_summary,
    generate_leadership_update,
    get_data_quality_summary,
)
from app.data.normalize_deals import normalize_deals_df
from app.data.normalize_work_orders import normalize_work_orders_df
from app.data.quality_report import check_gst_relationship, generate_quality_report, quality_report

WO_PATH = Path(__file__).resolve().parent.parent.parent / "Work_Order_Tracker Data.xlsx"
DEALS_PATH = Path(__file__).resolve().parent.parent.parent / "Deal funnel Data.xlsx"


@pytest.fixture(scope="module")
def normalized_data():
    raw_wo = pd.read_excel(WO_PATH, header=1, keep_default_na=False)
    norm_wo = normalize_work_orders_df(raw_wo)

    raw_deals = pd.read_excel(DEALS_PATH, keep_default_na=False)
    norm_deals = normalize_deals_df(raw_deals)

    return norm_wo, norm_deals


def test_gst_relationship_on_real_data(normalized_data) -> None:
    """Real Work Orders data conforms to 18% GST sanity check."""
    norm_wo, _ = normalized_data
    gst_res = check_gst_relationship(norm_wo, tolerance=0.5)

    # In real data, all valid rows match within 50 paise
    assert gst_res["is_valid"] is True
    assert gst_res["checked_rows"] == 175  # 1 row is null in Excl
    assert gst_res["discrepancy_count"] == 0


def test_gst_relationship_as_advisory_check_not_enforced() -> None:
    """Sanity check flags discrepancies as advisory warnings without crashing or dropping rows."""
    sample_data = pd.DataFrame({
        "Serial #": ["SDPLDEAL-999"],
        "Amount in Rupees (Excl of GST) (Masked)": [100000.0],
        # Corrupt Incl amount (e.g. 10% GST instead of 18%)
        "Amount in Rupees (Incl of GST) (Masked)": [110000.0],
    })

    # check_gst_relationship should flag it but not raise an exception
    gst_res = check_gst_relationship(sample_data, tolerance=0.5)
    assert gst_res["is_valid"] is False
    assert gst_res["discrepancy_count"] == 1
    assert gst_res["discrepancies"][0]["serial"] == "SDPLDEAL-999"
    assert pytest.approx(gst_res["discrepancies"][0]["diff"], 0.01) == 8000.0


def test_quality_report_wo_metrics(normalized_data) -> None:
    """Work Orders quality report detects the 4 fully null columns and negative counts."""
    norm_wo, _ = normalized_data
    rep = quality_report(norm_wo, "Work Orders")

    assert rep["total_rows"] == 176
    assert len(rep["fully_null_columns"]) == 4
    assert set(rep["fully_null_columns"]) == {
        "Expected Billing Month",
        "Actual Collection Month",
        "Collection status",
        "Collection Date",
    }

    neg = rep["negative_metrics"]
    assert neg["amount_to_be_billed_excl_neg_count"] == 6
    assert neg["amount_to_be_billed_incl_neg_count"] == 6
    assert neg["amount_receivable_neg_count"] == 11
    assert neg["balance_in_quantity_neg_count"] == 2

    # Verify Billing Status 148 nulls are captured in quality null counts
    assert rep["null_counts"]["Billing Status"] == 148

    # Verify invoice status breakdown: 54 NOT_BILLED, 10 UNKNOWN_WITH_BILLING
    inv_metrics = rep["invoice_status_metrics"]
    assert inv_metrics["not_billed_count"] == 54
    assert inv_metrics["unknown_with_billing_count"] == 10


def test_quality_report_deals_metrics(normalized_data) -> None:
    """Deals quality report captures severe null rates for probability, value, and close date."""
    _, norm_deals = normalized_data
    rep = quality_report(norm_deals, "Deals")

    assert rep["total_rows"] == 344
    null_rates = rep["core_null_rates"]
    assert pytest.approx(null_rates["closure_probability_null_rate"], 0.1) == 75.0
    assert pytest.approx(null_rates["deal_value_null_rate"], 0.1) == 52.0
    assert pytest.approx(null_rates["close_date_null_rate"], 0.1) == 92.4


def test_caveat_generation(normalized_data) -> None:
    """Comprehensive quality report generates narrative caveats matching §9."""
    norm_wo, norm_deals = normalized_data
    report = generate_quality_report(norm_wo, norm_deals)

    caveats = report["caveats"]
    assert "75% of deals do not have a closure probability" in caveats["weighted_pipeline"]
    assert "Deal value is unrecorded for 179 of 344 deals (52.0%)" in caveats["deal_values_missing"]
    assert "6 work orders have negative billing balances" in caveats["receivables_negative"]
    assert "11 accounts show net credit balances" in caveats["receivables_negative"]
    assert "The columns 'Expected Billing Month'" in caveats["empty_columns"]
    assert "unknown_with_billing" in caveats
    assert "10 work orders" in caveats["unknown_with_billing"]
    assert "UNKNOWN_WITH_BILLING" in caveats["unknown_with_billing"]


def test_quality_caveats_are_computed_from_data_not_hardcoded(normalized_data) -> None:
    """Regression: caveat sentences must be derived from the DataFrames, not frozen literals.

    Trimming the Deals board must change the reported totals/percentages in the caveat text.
    """
    norm_wo, norm_deals = normalized_data

    full = generate_quality_report(norm_wo, norm_deals)
    trimmed_deals = norm_deals.iloc[:-10].reset_index(drop=True)
    trimmed = generate_quality_report(norm_wo, trimmed_deals)

    full_total = len(norm_deals)
    trimmed_total = len(trimmed_deals)

    # Machine-readable metrics must track the actual row count.
    assert full["caveat_metrics"]["deal_values_missing"]["total_deals"] == full_total
    assert trimmed["caveat_metrics"]["deal_values_missing"]["total_deals"] == trimmed_total
    assert full["caveat_metrics"]["weighted_pipeline"]["total_deals"] == full_total
    assert trimmed["caveat_metrics"]["weighted_pipeline"]["total_deals"] == trimmed_total

    # ...and so must the narrative caveat text.
    assert f"of {full_total} deals" in full["caveats"]["deal_values_missing"]
    assert f"of {trimmed_total} deals" in trimmed["caveats"]["deal_values_missing"]
    assert full["caveats"]["deal_values_missing"] != trimmed["caveats"]["deal_values_missing"]

    # Counts must equal a direct recomputation from the source frame.
    expected_missing = int(norm_deals["Masked Deal value"].isna().sum())
    assert full["caveat_metrics"]["deal_values_missing"]["missing_value_count"] == expected_missing

    expected_prob_nulls = int(norm_deals["Closure Probability"].isna().sum())
    assert full["caveat_metrics"]["weighted_pipeline"]["probability_null_count"] == expected_prob_nulls

    expected_credit_accounts = int((norm_wo["Amount Receivable (Masked)"] < 0).sum())
    assert (
        full["caveat_metrics"]["receivables_negative"]["credit_balance_accounts"]
        == expected_credit_accounts
    )
    expected_neg_billing = int(
        (norm_wo["Amount to be billed in Rs. (Exl. of GST) (Masked)"] < 0).sum()
    )
    assert (
        full["caveat_metrics"]["receivables_negative"]["negative_billing_count"]
        == expected_neg_billing
    )


# ---------------------------------------------------------------------------
# Analytics Engine Unit Tests
# ---------------------------------------------------------------------------

def test_compute_pipeline_summary(normalized_data) -> None:
    """Verifies deterministic pipeline calculations across unweighted, weighted, and filtered views."""
    _, norm_deals = normalized_data
    summary = compute_pipeline_summary(norm_deals)

    assert summary["total_deals"] == 344
    assert summary["active_pipeline_count"] > 0
    assert summary["won_deals_count"] > 0
    assert summary["active_pipeline_unweighted_value"] > 0
    assert summary["active_pipeline_weighted_value"] > 0
    assert summary["won_deals_total_value"] > 0

    # Probability weighting must be less than or equal to unweighted active pipeline
    assert summary["active_pipeline_weighted_value"] < summary["active_pipeline_unweighted_value"]

    # Verify sector filter
    renewables_summary = compute_pipeline_summary(norm_deals, sector="Renewables")
    assert renewables_summary["filtered_sector"] == "Renewables"
    assert renewables_summary["total_deals"] < 344
    assert renewables_summary["total_deals"] > 0

    # Verify stage filter
    won_summary = compute_pipeline_summary(norm_deals, stage="won")
    assert won_summary["total_deals"] == summary["won_deals_count"]

    # Verify caveats attached
    assert any("Closure probability is unset" in c for c in summary["caveats"])
    assert any("Deal value is unrecorded" in c for c in summary["caveats"])


def test_compute_revenue_billed_incl_gst_regression(normalized_data) -> None:
    """Regression: `Billed Value in Rupees (Incl of GST.) (Masked)` contains a period inside
    the parentheses. Omitting that period in the lookup previously made the column unresolvable,
    silently reporting total_billed_value_incl_gst as ₹0 for every query."""
    norm_wo, _ = normalized_data
    rev = compute_revenue_summary(norm_wo)

    assert rev["total_billed_value_incl_gst"] > 0, (
        "Billed-value-incl-GST regressed to zero: the source column name contains a period "
        "'(Incl of GST.)' that must match the normalized DataFrame exactly."
    )
    assert rev["total_billed_value_incl_gst"] > rev["total_billed_value_excl_gst"]

    # The source board guarantees Incl == Excl * 1.18 (18% GST) for billed values.
    assert pytest.approx(rev["total_billed_value_incl_gst"], rel=0.01) == pytest.approx(
        rev["total_billed_value_excl_gst"] * 1.18, rel=0.01
    )


def test_compute_revenue_summary(normalized_data) -> None:
    """Verifies deterministic revenue aggregations and negative credit balance accounting."""
    norm_wo, _ = normalized_data
    rev = compute_revenue_summary(norm_wo)

    assert rev["total_work_orders"] == 176
    assert rev["total_order_value_excl_gst"] > 0
    assert rev["total_order_value_incl_gst"] > rev["total_order_value_excl_gst"]
    assert rev["total_billed_value_excl_gst"] > 0
    assert rev["total_collected_value_incl_gst"] > 0

    # Net vs Gross receivables accounting for 11 credit balance accounts
    assert rev["credit_balance_accounts_count"] == 11
    assert rev["credit_balance_total"] < 0
    assert rev["gross_positive_receivables"] > rev["net_receivables"]
    assert pytest.approx(rev["gross_positive_receivables"] + rev["credit_balance_total"], 0.01) == rev["net_receivables"]

    # Negative billing adjustments accounting for 6 rows
    assert rev["negative_billing_excl_count"] == 6
    assert rev["negative_billing_excl_total"] < 0

    # Status breakdown checks
    assert rev["invoice_status_breakdown"]["NOT_BILLED"] == 54
    assert rev["invoice_status_breakdown"]["UNKNOWN_WITH_BILLING"] == 10

    # Sector filter check
    mining_rev = compute_revenue_summary(norm_wo, sector="Mining")
    assert mining_rev["filtered_sector"] == "Mining"
    assert mining_rev["total_work_orders"] < 176
    assert mining_rev["total_work_orders"] > 0

    # Verify caveats attached
    assert any("Credit balances detected" in c for c in rev["caveats"])
    assert any("Negative billing balances" in c for c in rev["caveats"])


def test_cross_board_join_and_delivery(normalized_data) -> None:
    """Verifies dynamic live cross-board join metrics without hardcoding link counts."""
    norm_wo, norm_deals = normalized_data
    
    # Simulate a few live items with board_relation links
    simulated_wo_items = [
        {"Serial #": "SDPLDEAL-159", "Linked Deal__linked_ids": ["2862901859"]},
        {"Serial #": "SDPLDEAL-160", "Linked Deal__linked_ids": ["2862901859"]},
        {"Serial #": "SDPLDEAL-001", "Linked Deal__linked_ids": []},
    ]

    delivery = compute_cross_board_delivery(
        norm_wo, norm_deals, wo_items=simulated_wo_items
    )

    assert delivery["total_work_orders"] == 176
    assert delivery["total_deals"] == 344
    assert delivery["matched_orders_count"] == 2
    assert delivery["unmatched_orders_count"] == 174
    assert pytest.approx(delivery["link_coverage_percentage"], 0.1) == round(2 / 176 * 100, 1)

    # Dynamic caveats must reflect the exact dynamic counts
    assert any("2 of 176 work orders" in c for c in delivery["caveats"])
    assert "commercial_risk" in delivery
    assert "value_variance" in delivery
    assert "won_deals_backlog" in delivery
    assert "unlinked_exposure" in delivery


def test_cross_board_commercial_risk_and_variance(normalized_data) -> None:
    """Verifies commercial risk, value variance, and won-deal backlog calculations."""
    norm_wo, norm_deals = normalized_data
    res = compute_cross_board_delivery(norm_wo, norm_deals, view="unclosed_deal_risk")

    assert res["total_work_orders"] == 176
    assert res["total_deals"] == 344
    assert res["view"] == "unclosed_deal_risk"
    assert "commercial_risk" in res
    assert "value_variance" in res
    assert "won_deals_backlog" in res
    assert res["commercial_risk"]["unclosed_deal_risk_count"] >= 0
    assert res["won_deals_backlog"]["total_won_deals"] == 103
    assert res["won_deals_backlog"]["won_deals_without_wo_count"] >= 0
    assert res["unlinked_exposure"]["unlinked_orders_count"] > 0


def test_generate_leadership_update(normalized_data) -> None:
    """Verifies executive leadership update briefing formatting and KPI inclusion."""
    norm_wo, norm_deals = normalized_data
    briefing = generate_leadership_update(norm_wo, norm_deals, period="Weekly Update")

    assert briefing["period"] == "Weekly Update"
    md = briefing["markdown_briefing"]
    assert "# Skylark Drones — Leadership Executive Briefing (Weekly Update)" in md
    assert "Executive Summary & Core KPIs" in md
    assert "Active Pipeline" in md
    assert "Net Outstanding Receivables" in md
    assert "Critical Data Quality & Bookkeeping Alerts" in md
    assert "⚠️" in md


def test_get_data_quality_summary(normalized_data) -> None:
    """Verifies data quality wrapper returns both boards when requested."""
    norm_wo, norm_deals = normalized_data
    q_summary = get_data_quality_summary(norm_wo_df=norm_wo, norm_deals_df=norm_deals, board_name="both")

    assert "work_orders" in q_summary
    assert "deals" in q_summary
    assert "gst_check" in q_summary
    assert q_summary["work_orders"]["total_rows"] == 176
    assert q_summary["deals"]["total_rows"] == 344


def test_pipeline_temporal_filtering_historical_and_empty_quarter(normalized_data) -> None:
    """Verifies temporal filtering applies anchor rules and handles empty quarters with nearest benchmarks."""
    from datetime import date
    _, norm_deals = normalized_data

    # Q4 FY25-26: Jan 1, 2026 to Mar 31, 2026 (has historical deals)
    q4_res = compute_pipeline_summary(norm_deals, period="Q4 FY25-26")
    assert q4_res["period"] == "Q4 FY25-26"
    assert q4_res["is_empty_period"] is False
    assert q4_res["total_deals"] > 0
    assert q4_res["total_deals"] < 344
    assert q4_res["anchor_stats"]["close_date_count"] > 0 or q4_res["anchor_stats"]["tentative_fallback_count"] > 0

    # Current Quarter on Sept 20, 2026: Q2 FY26-27 (empty period trap)
    ref_date = date(2026, 9, 20)
    current_q_res = compute_pipeline_summary(norm_deals, period="this quarter", reference_date=ref_date)
    assert current_q_res["is_empty_period"] is True
    assert current_q_res["total_deals"] == 0
    assert current_q_res["active_pipeline_unweighted_value"] == 0.0
    assert current_q_res["won_deals_total_value"] == 0.0
    assert current_q_res["empty_period_explanation"] is not None
    assert "Q2 FY26-27" in current_q_res["period"]
    assert len(current_q_res["nearest_quarters_data"]) > 0
    # Nearest quarters data includes FY25-26 quarters with activity
    quarters = [q["quarter"] for q in current_q_res["nearest_quarters_data"]]
    assert any("FY25-26" in q for q in quarters)


def test_pipeline_win_rate_and_owner_rankings(normalized_data) -> None:
    """Verifies win rate calculation Won/(Won+Dead) and owner ranking by won value."""
    _, norm_deals = normalized_data
    summary = compute_pipeline_summary(norm_deals)

    assert "win_rate_percentage" in summary
    assert "win_rate_sample_size" in summary
    # Win rate = Won / (Won + Dead)
    expected_decided = summary["won_deals_count"] + summary["lost_or_dormant_count"]
    assert summary["win_rate_sample_size"] == expected_decided
    expected_win_rate = round(summary["won_deals_count"] / expected_decided * 100.0, 1)
    assert summary["win_rate_percentage"] == expected_win_rate

    # Owner breakdown
    assert "owner_breakdown" in summary
    owners = summary["owner_breakdown"]
    assert len(owners) > 0
    # Ranked by won value descending
    for i in range(len(owners) - 1):
        assert owners[i]["won_value"] >= owners[i + 1]["won_value"]
    # Top owner is OWNER_003
    assert owners[0]["owner_code"] == "OWNER_003"
    assert owners[0]["won_deals"] > 0


def test_revenue_temporal_filtering_and_bookings_label(normalized_data) -> None:
    """Verifies Work Orders time slicing uses Date of PO/LOI, labels as Bookings, and detects empty quarters."""
    from datetime import date
    norm_wo, _ = normalized_data

    # Q1 FY25-26 has known bookings
    q1_res = compute_revenue_summary(norm_wo, period="Q1 FY25-26")
    assert q1_res["period"] == "Q1 FY25-26"
    assert q1_res["is_empty_period"] is False
    assert q1_res["total_work_orders"] > 0
    assert q1_res["period_bookings_excl_gst"] > 0
    assert q1_res["metric_labels"]["order_value"] == "Bookings (by PO date)"

    # Refusal notice for DSO / aging
    assert "dso_refusal_reason" in q1_res
    assert "100% null" in q1_res["dso_refusal_reason"]

    # Current quarter (empty)
    ref_date = date(2026, 9, 20)
    current_q_res = compute_revenue_summary(norm_wo, period="this quarter", reference_date=ref_date)
    assert current_q_res["is_empty_period"] is True
    assert current_q_res["total_work_orders"] == 0
    assert current_q_res["period_bookings_excl_gst"] == 0.0
    assert len(current_q_res["nearest_quarters_data"]) > 0

    # BD/KAM Owner breakdown
    assert "owner_breakdown" in q1_res
    owners = q1_res["owner_breakdown"]
    assert len(owners) > 0
    for i in range(len(owners) - 1):
        assert owners[i]["total_booked_excl_gst"] >= owners[i + 1]["total_booked_excl_gst"]


def test_energy_sector_aggregation_renewables_and_powerline(normalized_data) -> None:
    """Verifies sector='Energy' aggregates Renewables + Powerline and returns sub-breakdowns."""
    norm_wo, norm_deals = normalized_data

    # Deals pipeline for Energy
    energy_pipe = compute_pipeline_summary(norm_deals, sector="Energy")
    renewables_pipe = compute_pipeline_summary(norm_deals, sector="Renewables")
    powerline_pipe = compute_pipeline_summary(norm_deals, sector="Powerline")

    assert energy_pipe["total_deals"] == renewables_pipe["total_deals"] + powerline_pipe["total_deals"]
    assert energy_pipe["won_deals_count"] == renewables_pipe["won_deals_count"] + powerline_pipe["won_deals_count"]
    assert pytest.approx(energy_pipe["won_deals_total_value"], 0.01) == renewables_pipe["won_deals_total_value"] + powerline_pipe["won_deals_total_value"]
    assert energy_pipe["energy_breakdown"] is not None
    assert "Renewables" in energy_pipe["energy_breakdown"]
    assert "Powerline" in energy_pipe["energy_breakdown"]

    # Work orders for Energy
    energy_rev = compute_revenue_summary(norm_wo, sector="Energy")
    renewables_rev = compute_revenue_summary(norm_wo, sector="Renewables")
    powerline_rev = compute_revenue_summary(norm_wo, sector="Powerline")

    assert energy_rev["total_work_orders"] == renewables_rev["total_work_orders"] + powerline_rev["total_work_orders"]
    assert energy_rev["energy_breakdown"] is not None


def test_leadership_update_with_empty_quarter(normalized_data) -> None:
    """Verifies leadership update displays timeline callout and nearest quarter tables for empty periods."""
    from datetime import date
    norm_wo, norm_deals = normalized_data
    ref_date = date(2026, 9, 20)

    briefing = generate_leadership_update(norm_wo, norm_deals, period="this quarter", reference_date=ref_date)
    assert briefing["is_empty_period"] is True
    md = briefing["markdown_briefing"]
    assert "Timeline Notice" in md
    assert "Nearest Historical Quarters" in md
    assert "Win Rate" in md
    assert "OWNER_003" in md


