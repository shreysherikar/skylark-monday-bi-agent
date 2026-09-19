"""Data quality audit and caveat generation layer.

Computes null rates, unparseable field counts, unknown status counts, negative value
metrics, GST reconciliation checks, and caveat messages for agent responses.

Specification defined in NORMALIZATION_NOTES.md (§9) and PROJECT_PLAN.md (§9).
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def check_gst_relationship(wo_df: pd.DataFrame, tolerance: float = 0.5) -> dict[str, Any]:
    """Verify the sanity check relationship: Incl ≈ Excl * 1.18.

    This is an advisory sanity check flagged in the quality report, NOT an enforced
    hard rule (rows are never dropped or mutated due to GST discrepancy).
    """
    excl_col = "Amount in Rupees (Excl of GST) (Masked)"
    incl_col = "Amount in Rupees (Incl of GST) (Masked)"

    if excl_col not in wo_df.columns or incl_col not in wo_df.columns:
        return {
            "is_valid": True,
            "checked_rows": 0,
            "discrepancy_count": 0,
            "discrepancies": [],
            "notes": "GST columns not present in DataFrame",
        }

    valid_mask = wo_df[excl_col].notna() & wo_df[incl_col].notna()
    checked_df = wo_df[valid_mask]

    diff = (checked_df[incl_col] - (checked_df[excl_col] * 1.18)).abs()
    mismatches = checked_df[diff > tolerance]

    discrepancies = []
    for idx, row in mismatches.iterrows():
        discrepancies.append({
            "serial": row.get("Serial #", f"row_{idx}"),
            "excl": row[excl_col],
            "incl": row[incl_col],
            "expected_incl": round(row[excl_col] * 1.18, 2),
            "diff": round(diff.loc[idx], 2),  # type: ignore[call-overload]
        })

    return {
        "is_valid": len(discrepancies) == 0,
        "checked_rows": len(checked_df),
        "discrepancy_count": len(discrepancies),
        "discrepancies": discrepancies,
        "notes": (
            f"Verified {len(checked_df)} rows against 18% GST (tolerance ±{tolerance}). "
            f"{len(discrepancies)} discrepancy(ies) detected."
        ),
    }


def quality_report(df: pd.DataFrame, board_name: str) -> dict[str, Any]:
    """Generate a data quality report for an individual board (Work Orders or Deals)."""
    total_rows = len(df)
    null_counts: dict[str, int] = {}
    null_rates: dict[str, float] = {}

    for col in df.columns:
        n_null = int(df[col].isna().sum())
        null_counts[col] = n_null
        null_rates[col] = round((n_null / total_rows * 100), 2) if total_rows > 0 else 0.0

    report: dict[str, Any] = {
        "board_name": board_name,
        "total_rows": total_rows,
        "null_counts": null_counts,
        "null_rates": null_rates,
    }

    if "work" in board_name.lower():
        # Check the 4 fully-null columns
        empty_cols = ["Expected Billing Month", "Actual Collection Month", "Collection status", "Collection Date"]
        report["fully_null_columns"] = [c for c in empty_cols if c in df.columns and null_counts.get(c, 0) == total_rows]

        # Check negative value columns
        excl_to_bill = "Amount to be billed in Rs. (Exl. of GST) (Masked)"
        incl_to_bill = "Amount to be billed in Rs. (Incl. of GST) (Masked)"
        ar_col = "Amount Receivable (Masked)"
        bal_qty = "Balance in quantity"

        report["negative_metrics"] = {
            "amount_to_be_billed_excl_neg_count": int((df[excl_to_bill] < 0).sum()) if excl_to_bill in df.columns else 0,
            "amount_to_be_billed_incl_neg_count": int((df[incl_to_bill] < 0).sum()) if incl_to_bill in df.columns else 0,
            "amount_receivable_neg_count": int((df[ar_col] < 0).sum()) if ar_col in df.columns else 0,
            "balance_in_quantity_neg_count": int((df[bal_qty] < 0).sum()) if bal_qty in df.columns else 0,
        }

        # Check invoice status breakdown including UNKNOWN_WITH_BILLING
        inv_col = "Invoice Status"
        if inv_col in df.columns:
            report["invoice_status_metrics"] = {
                "not_billed_count": int((df[inv_col] == "NOT_BILLED").sum()),
                "unknown_with_billing_count": int((df[inv_col] == "UNKNOWN_WITH_BILLING").sum()),
            }

        # Check GST sanity
        report["gst_check"] = check_gst_relationship(df)

    elif "deal" in board_name.lower():
        # Check core Deals null rates
        prob_col = "Closure Probability"
        val_col = "Masked Deal value"
        date_col = "Close Date (A)"

        report["core_null_rates"] = {
            "closure_probability_null_rate": null_rates.get(prob_col, 0.0),
            "deal_value_null_rate": null_rates.get(val_col, 0.0),
            "close_date_null_rate": null_rates.get(date_col, 0.0),
        }

    return report


def generate_quality_report(
    wo_df: pd.DataFrame,
    deals_df: pd.DataFrame,
    links_df: pd.DataFrame | None = None,
    join_summary: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Generate comprehensive cross-board quality metrics and narrative caveat triggers (§9).

    Args:
        wo_df: Normalized Work Orders DataFrame.
        deals_df: Normalized Deals DataFrame.
        links_df: Optional offline match-mapping CSV (``Confidence Tier`` schema).
        join_summary: Optional live join counts (``matched_count``,
            ``unmatched_work_orders``, ``unmatched_deals``). Takes precedence over
            ``links_df`` so runtime caveats always reflect the live board state.
    """
    wo_rep = quality_report(wo_df, "Work Orders")
    deals_rep = quality_report(deals_df, "Deals")

    # Calculate caveat-specific aggregations (all values derived from the live DataFrames)
    total_deals = len(deals_df)
    total_wo = len(wo_df)

    # 1. Weighted pipeline / missing-probability caveat values
    val_col = "Masked Deal value"
    prob_col = "Closure Probability"
    total_pipeline = float(deals_df[val_col].dropna().sum()) if val_col in deals_df.columns else 0.0
    if prob_col in deals_df.columns:
        prob_null_count = int(deals_df[prob_col].isna().sum())
        deals_with_prob = int(deals_df[prob_col].notna().sum())
    else:
        prob_null_count = total_deals
        deals_with_prob = 0
    prob_null_pct = (prob_null_count / total_deals * 100.0) if total_deals > 0 else 0.0

    # 2. Missing deal-value caveat values
    if val_col in deals_df.columns:
        missing_val_count = int(deals_df[val_col].isna().sum())
    else:
        missing_val_count = total_deals
    missing_val_pct = (missing_val_count / total_deals * 100.0) if total_deals > 0 else 0.0

    with_prob_mask = deals_df[prob_col].notna() if prob_col in deals_df.columns else pd.Series(False, index=deals_df.index)
    valued_with_prob = float(deals_df[with_prob_mask & deals_df[val_col].notna()][val_col].sum()) if val_col in deals_df.columns else 0.0

    # 3. Negative receivables & overbilling caveat values
    excl_to_bill = "Amount to be billed in Rs. (Exl. of GST) (Masked)"
    ar_col = "Amount Receivable (Masked)"
    if excl_to_bill in wo_df.columns:
        neg_billing_mask = wo_df[excl_to_bill] < 0
        neg_billing_count = int(neg_billing_mask.sum())
        overbilled_amt = float(wo_df[neg_billing_mask][excl_to_bill].abs().sum())
    else:
        neg_billing_count = 0
        overbilled_amt = 0.0
    if ar_col in wo_df.columns:
        credit_bal_mask = wo_df[ar_col] < 0
        credit_accounts = int(credit_bal_mask.sum())
        credit_bal_amt = float(wo_df[credit_bal_mask][ar_col].abs().sum())
    else:
        credit_accounts = 0
        credit_bal_amt = 0.0

    # 4. Cross-board join counts (live join summary takes precedence over the offline CSV)
    if join_summary:
        matched_count = int(join_summary.get("matched_count", 0))
        unmatched_wo = int(join_summary.get("unmatched_work_orders", total_wo))
        unmatched_deals = int(join_summary.get("unmatched_deals", total_deals))
    elif links_df is not None:
        matched_count = len(links_df[links_df["Confidence Tier"].isin(["MATCHED_HIGH", "MATCHED_FUZZY"])])
        unmatched_wo = len(links_df[links_df["Confidence Tier"] == "UNMATCHED"])
        unmatched_deals = total_deals - matched_count
    else:
        matched_count = 0
        unmatched_wo = total_wo
        unmatched_deals = total_deals

    # 4. UNKNOWN_WITH_BILLING metrics
    inv_col = "Invoice Status"
    billed_excl = "Billed Value in Rupees (Excl of GST.) (Masked)"
    unknown_billing_mask = (wo_df[inv_col] == "UNKNOWN_WITH_BILLING") if inv_col in wo_df.columns else pd.Series(False, index=wo_df.index)
    unknown_billing_count = int(unknown_billing_mask.sum())
    unknown_billing_amt = float(wo_df[unknown_billing_mask][billed_excl].dropna().sum()) if billed_excl in wo_df.columns else 0.0

    caveats = {
        "weighted_pipeline": (
            f"Note: {prob_null_pct:.0f}% of deals do not have a closure probability assigned "
            f"({prob_null_count} of {total_deals}). "
            f"Weighted pipeline is calculated solely on the {deals_with_prob} deals with probability set, "
            f"representing ₹{valued_with_prob:,.2f} of ₹{total_pipeline:,.2f} total recorded pipeline."
        ),
        "deal_values_missing": (
            f"Note: Deal value is unrecorded for {missing_val_count} of {total_deals} deals ({missing_val_pct:.1f}%). "
            f"Actual pipeline is likely significantly higher."
        ),
        "cross_board_join": (
            f"Data quality caveat: Work orders and deals lack an explicit foreign key. "
            f"Analysis reflects {matched_count} matched records; "
            f"unlinked work orders ({unmatched_wo}) and deals ({unmatched_deals}) are reported separately."
        ),
        "receivables_negative": (
            f"{neg_billing_count} work orders have negative billing balances (billed value exceeds contract value by ₹{overbilled_amt:,.2f}), "
            f"and {credit_accounts} accounts show net credit balances in receivables (totaling ₹{credit_bal_amt:,.2f})."
        ),
        "empty_columns": (
            "The columns 'Expected Billing Month', 'Actual Collection Month', "
            "'Collection status', and 'Collection Date' contain no recorded data in the source board."
        ),
        "unknown_with_billing": (
            f"Bookkeeping integrity flag: {unknown_billing_count} work orders have recorded billing "
            f"totaling ₹{unknown_billing_amt:,.2f} (Excl GST) but missing Invoice Status "
            f"(classified as UNKNOWN_WITH_BILLING). These require financial audit reconciliation."
        ),
    }

    return {
        "work_orders": wo_rep,
        "deals": deals_rep,
        "caveats": caveats,
        "caveat_metrics": {
            "weighted_pipeline": {
                "probability_null_count": prob_null_count,
                "probability_null_pct": round(prob_null_pct, 1),
                "deals_with_probability": deals_with_prob,
                "total_deals": total_deals,
                "recorded_pipeline_value": round(total_pipeline, 2),
                "value_with_probability": round(valued_with_prob, 2),
            },
            "deal_values_missing": {
                "missing_value_count": missing_val_count,
                "total_deals": total_deals,
                "missing_value_pct": round(missing_val_pct, 1),
            },
            "receivables_negative": {
                "negative_billing_count": neg_billing_count,
                "overbilled_total": round(overbilled_amt, 2),
                "credit_balance_accounts": credit_accounts,
                "credit_balance_total": round(credit_bal_amt, 2),
            },
            "cross_board_join": {
                "matched_count": matched_count,
                "unmatched_work_orders": unmatched_wo,
                "unmatched_deals": unmatched_deals,
            },
            "unknown_with_billing": {
                "count": unknown_billing_count,
                "billed_value_excl_gst": round(unknown_billing_amt, 2),
            },
        },
    }

