"""Deterministic business intelligence and analytics functions for Skylark Drones.

All financial and pipeline calculations are performed deterministically in Python
with strict accounting of nulls, negative balances, and data quality caveats per §3, §8, and §9.

Key rules:
- Cross-board joins dynamically inspect live Monday Connect Boards links from `get_work_orders()`.
- Actual link coverage is always reported dynamically (never hardcoded).
- Legitimate negative values (receivables credit balances, negative billing amounts)
  are preserved and explicitly reported alongside net/gross totals.
- Relevant data-quality caveats from quality_report.py are automatically attached to every summary.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pandas as pd

from app.data.quality_report import check_gst_relationship, generate_quality_report, quality_report

# Probability weighting mapping for Closure Probability
CLOSURE_PROBABILITY_WEIGHTS: dict[str, float] = {
    "high": 0.8,
    "medium": 0.5,
    "low": 0.2,
}

# Common sector synonyms and aliases mapping to canonical board sectors
SECTOR_SYNONYMS: dict[str, str] = {
    "renewables": "Renewables",
    "renewable": "Renewables",
    "solar": "Renewables",
    "wind": "Renewables",
    "energy": "Renewables",
    "green energy": "Renewables",
    "powerline": "Powerline",
    "powerlines": "Powerline",
    "power": "Powerline",
    "transmission": "Powerline",
    "utilities": "Powerline",
    "mining": "Mining",
    "mines": "Mining",
    "coal": "Mining",
    "minerals": "Mining",
    "railways": "Railways",
    "railway": "Railways",
    "rail": "Railways",
    "trains": "Railways",
    "tender": "Tender",
    "tenders": "Tender",
    "dsp": "DSP",
    "construction": "Construction",
    "others": "Others",
    "other": "Others",
}


def resolve_sector_synonym(sector: str | None) -> str | None:
    """Resolves sector aliases and synonyms to official board sector names."""
    if not sector or not sector.strip():
        return None
    clean = sector.strip().lower()
    return SECTOR_SYNONYMS.get(clean, sector.strip())



# ---------------------------------------------------------------------------
# Cross-Board Dynamic Join Helper
# ---------------------------------------------------------------------------

def join_work_orders_to_deals(
    norm_wo_df: pd.DataFrame,
    norm_deals_df: pd.DataFrame,
    wo_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Dynamically joins Work Orders to Deals using live Monday Connect Boards relationships.
    
    Inspects live `Linked Deal` / `Linked Deal__linked_ids` column on Work Order items.
    Reports actual live link coverage dynamically without hardcoded numbers.
    """
    total_wo = len(norm_wo_df)
    total_deals = len(norm_deals_df)

    # Build deal lookup index by item_id (string) and by 1-indexed row id
    deals_by_id: dict[str, dict[str, Any]] = {}
    for join_idx, join_row in norm_deals_df.iterrows():
        item_id = str(join_row.get("item_id", "")) if pd.notna(join_row.get("item_id")) else ""
        deal_dict: dict[str, Any] = dict(cast("dict[Any, Any]", join_row.to_dict()))
        deal_dict["deal_row_index"] = int(cast("Any", join_idx)) + 1
        if item_id:
            deals_by_id[item_id] = deal_dict
        # Also index by deal row id as fallback if items share index
        deals_by_id[str(int(cast("Any", join_idx)) + 1)] = deal_dict

    # Extract linked deal item IDs from wo_items or norm_wo_df
    # wo_items gives direct access to 'Linked Deal__linked_ids'
    linked_pairs: list[dict[str, Any]] = []
    unlinked_wo_serials: list[str] = []

    # Map serial to wo_items if provided
    wo_item_map: dict[str, dict[str, Any]] = {}
    if wo_items:
        for it in wo_items:
            serial = it.get("Serial #") or it.get("item_name")
            if serial:
                wo_item_map[str(serial).strip()] = it

    for _, wo_row in norm_wo_df.iterrows():
        serial = str(wo_row.get("Serial #", "")).strip()
        linked_ids: list[str] = []

        # 1. Try from wo_items dict
        if serial in wo_item_map:
            raw_ids = (
                wo_item_map[serial].get("Linked Deal__linked_ids")
                or wo_item_map[serial].get("Linked Deal")
            )
            if isinstance(raw_ids, list):
                linked_ids = [str(x) for x in raw_ids if x]
            elif raw_ids and str(raw_ids).strip() not in ("", "none", "nan", "[]"):
                linked_ids = [str(raw_ids).strip()]

        # 2. Try from norm_wo_df column if present (defensively avoid numpy/pandas array truth errors)
        if not linked_ids:
            for col in ["Linked Deal__linked_ids", "Linked Deal"]:
                if col in wo_row:
                    val = wo_row[col]
                    if val is not None:
                        if isinstance(val, (list, tuple)):
                            linked_ids = [str(x) for x in val if x]
                        elif not (pd.isna(val) if not hasattr(val, "__len__") else len(val) == 0):
                            s_val = str(val).strip()
                            if s_val not in ("", "none", "nan", "[]"):
                                linked_ids = [s_val]
                    if linked_ids:
                        break

        if linked_ids:
            target_id = linked_ids[0]
            matched_deal = deals_by_id.get(target_id)
            deal_nm = matched_deal.get("Deal Name") or matched_deal.get("item_name") if matched_deal else None
            wo_deal_nm = wo_row.get("Deal name masked") or wo_row.get("Deal Name") or wo_row.get("item_name")
            linked_pairs.append({
                "wo_serial": serial,
                "wo_deal_name": deal_nm or wo_deal_nm,
                "wo_customer_code": wo_row.get("Customer Name Code"),
                "wo_sector": wo_row.get("Sector"),
                "wo_owner": wo_row.get("BD/KAM Personnel code"),
                "wo_execution_status": wo_row.get("Execution Status"),
                "wo_invoice_status": wo_row.get("Invoice Status"),
                "wo_nature_of_work": wo_row.get("Nature of Work"),
                "wo_start_date": wo_row.get("Probable Start Date"),
                "wo_po_date": wo_row.get("Date of PO/LOI"),
                "wo_amount_excl_gst": wo_row.get("Amount in Rupees (Excl of GST) (Masked)"),
                "wo_billed_excl_gst": wo_row.get("Billed Value in Rupees (Excl of GST.) (Masked)"),
                "wo_receivable": wo_row.get("Amount Receivable (Masked)"),
                "deal_item_id": target_id,
                "deal_name": deal_nm,
                "deal_status": matched_deal.get("Deal Status") if matched_deal else None,
                "deal_stage": matched_deal.get("Deal Stage") if matched_deal else None,
                "deal_sector": matched_deal.get("Sector/service") if matched_deal else None,
                "deal_value": matched_deal.get("Masked Deal value") if matched_deal else None,
                "deal_owner": matched_deal.get("Owner code") if matched_deal else None,
                "deal_close_date": matched_deal.get("Close Date (A)") if matched_deal else None,
            })
        else:
            unlinked_wo_serials.append(serial)

    # Offline fallback: only if wo_items was NOT provided (e.g. offline unit testing on Excel),
    # load links from scripts/deal_wo_links.csv if available.
    if not linked_pairs and wo_items is None:
        for base in [Path.cwd(), Path.cwd().parent, Path(__file__).resolve().parents[3]]:
            csv_candidate = base / "scripts" / "deal_wo_links.csv"
            if csv_candidate.exists():
                try:
                    link_csv_df = pd.read_csv(csv_candidate)
                    matched_rows = link_csv_df[link_csv_df["confidence_tier"].isin(["MATCHED_HIGH", "MATCHED_FUZZY"])]
                    csv_link_map: dict[str, str] = {}
                    for _, lrow in matched_rows.iterrows():
                        if pd.notna(lrow.get("matched_deal_row_id")):
                            csv_link_map[str(lrow["wo_serial"]).strip()] = str(int(float(lrow["matched_deal_row_id"])))
                    if csv_link_map:
                        linked_pairs = []
                        unlinked_wo_serials = []
                        for _, wo_row in norm_wo_df.iterrows():
                            serial = str(wo_row.get("Serial #", "")).strip()
                            if serial in csv_link_map:
                                deal_row_str = csv_link_map[serial]
                                matched_deal = deals_by_id.get(deal_row_str)
                                deal_nm = matched_deal.get("Deal Name") or matched_deal.get("item_name") if matched_deal else None
                                wo_deal_nm = wo_row.get("Deal name masked") or wo_row.get("Deal Name") or wo_row.get("item_name")
                                linked_pairs.append({
                                    "wo_serial": serial,
                                    "wo_deal_name": deal_nm or wo_deal_nm,
                                    "wo_customer_code": wo_row.get("Customer Name Code"),
                                    "wo_sector": wo_row.get("Sector"),
                                    "wo_owner": wo_row.get("BD/KAM Personnel code"),
                                    "wo_execution_status": wo_row.get("Execution Status"),
                                    "wo_invoice_status": wo_row.get("Invoice Status"),
                                    "wo_nature_of_work": wo_row.get("Nature of Work"),
                                    "wo_start_date": wo_row.get("Probable Start Date"),
                                    "wo_po_date": wo_row.get("Date of PO/LOI"),
                                    "wo_amount_excl_gst": wo_row.get("Amount in Rupees (Excl of GST) (Masked)"),
                                    "wo_billed_excl_gst": wo_row.get("Billed Value in Rupees (Excl of GST.) (Masked)"),
                                    "wo_receivable": wo_row.get("Amount Receivable (Masked)"),
                                    "deal_item_id": deal_row_str,
                                    "deal_name": deal_nm,
                                    "deal_status": matched_deal.get("Deal Status") if matched_deal else None,
                                    "deal_stage": matched_deal.get("Deal Stage") if matched_deal else None,
                                    "deal_sector": matched_deal.get("Sector/service") if matched_deal else None,
                                    "deal_value": matched_deal.get("Masked Deal value") if matched_deal else None,
                                    "deal_owner": matched_deal.get("Owner code") if matched_deal else None,
                                    "deal_close_date": matched_deal.get("Close Date (A)") if matched_deal else None,
                                })
                            else:
                                unlinked_wo_serials.append(serial)
                    break
                except Exception:
                    pass

    linked_count = len(linked_pairs)
    unlinked_count = len(unlinked_wo_serials)
    coverage_pct = (linked_count / total_wo * 100.0) if total_wo > 0 else 0.0

    caveats = [
        (
            f"Cross-board join coverage: {linked_count} of {total_wo} work orders "
            f"({coverage_pct:.1f}%) are currently linked to a tracked deal on Monday.com."
        ),
        f"{unlinked_count} work orders remain unlinked. Cross-board metrics reflect matched records only.",
    ]

    return {
        "total_work_orders": total_wo,
        "total_deals": total_deals,
        "linked_work_orders_count": linked_count,
        "unlinked_work_orders_count": unlinked_count,
        "link_coverage_percentage": round(coverage_pct, 1),
        "linked_pairs": linked_pairs,
        "unlinked_serials": unlinked_wo_serials,
        "caveats": caveats,
    }


# ---------------------------------------------------------------------------
# Pipeline Analytics
# ---------------------------------------------------------------------------

def compute_pipeline_summary(
    norm_deals_df: pd.DataFrame,
    sector: str | None = None,
    stage: str | None = None,
) -> dict[str, Any]:
    """Computes deterministic pipeline health, weighted pipeline, and stage metrics.
    
    Applies filters if requested and dynamically injects relevant quality caveats.
    """
    df = norm_deals_df.copy()

    # Sector filtering (case-insensitive with synonym resolution)
    resolved_sector = resolve_sector_synonym(sector)
    if resolved_sector:
        s_norm = resolved_sector.lower()
        df = df[df["Sector/service"].astype(str).str.lower() == s_norm]

    # Stage category filtering
    if stage and stage.strip():
        st_norm = stage.strip().lower()
        if st_norm in ("active", "active pipeline", "pipeline", "open"):
            df = df[df["is_active_pipeline"] == True]
        elif st_norm in ("won", "closed won", "project won"):
            df = df[df["is_won"] == True]
        elif st_norm in ("lost", "dormant", "dead"):
            df = df[df["is_lost_or_dormant"] == True]

    total_deals = len(df)
    val_col = "Masked Deal value"

    # Pipeline categories
    active_df = df[df["is_active_pipeline"] == True]
    won_df = df[df["is_won"] == True]
    lost_df = df[df["is_lost_or_dormant"] == True]

    active_count = len(active_df)
    won_count = len(won_df)
    lost_count = len(lost_df)

    # Values (accounting for nulls)
    active_val_unweighted = active_df[val_col].dropna().sum()
    won_val = won_df[val_col].dropna().sum()
    total_val_all = df[val_col].dropna().sum()

    # Deals with missing value
    total_missing_val = int(df[val_col].isna().sum())
    missing_val_pct = (total_missing_val / total_deals * 100.0) if total_deals > 0 else 0.0

    # Weighted pipeline calculation (active pipeline only)
    # Using closure probability weights: High=0.8, Medium=0.5, Low=0.2
    prob_col = "Closure Probability"
    active_with_prob_df = active_df[active_df[prob_col].notna() & active_df[val_col].notna()]
    
    weighted_pipeline_val = 0.0
    weighted_count = 0
    for _, r in active_with_prob_df.iterrows():
        p_str = str(r[prob_col]).strip().lower()
        weight = CLOSURE_PROBABILITY_WEIGHTS.get(p_str, 0.0)
        weighted_pipeline_val += float(r[val_col]) * weight
        weighted_count += 1

    active_missing_prob = int(active_df[prob_col].isna().sum())
    active_missing_prob_pct = (
        (active_missing_prob / active_count * 100.0) if active_count > 0 else 0.0
    )

    # Breakdown by Deal Stage
    stage_breakdown: dict[str, dict[str, Any]] = {}
    for st_name, grp in df.groupby("Deal Stage", dropna=False):
        st_label = str(st_name) if pd.notna(st_name) else "Unspecified"
        stage_breakdown[st_label] = {
            "count": len(grp),
            "total_value": round(grp[val_col].dropna().sum(), 2),
            "missing_value_count": int(grp[val_col].isna().sum()),
        }

    # Breakdown by Sector
    sector_breakdown: dict[str, dict[str, Any]] = {}
    for sec_name, grp in df.groupby("Sector/service", dropna=False):
        sec_label = str(sec_name) if pd.notna(sec_name) else "Unspecified"
        sector_breakdown[sec_label] = {
            "total_deals": len(grp),
            "active_deals": int(grp["is_active_pipeline"].sum()),
            "won_deals": int(grp["is_won"].sum()),
            "active_value": round(grp[grp["is_active_pipeline"] == True][val_col].dropna().sum(), 2),
            "won_value": round(grp[grp["is_won"] == True][val_col].dropna().sum(), 2),
        }

    # Data Quality Caveats
    caveats: list[str] = []
    if missing_val_pct > 0:
        caveats.append(
            f"Deal value is unrecorded for {total_missing_val} of {total_deals} deals ({missing_val_pct:.1f}%). "
            f"Pipeline totals reflect only deals with recorded financial values."
        )
    if active_missing_prob > 0:
        caveats.append(
            f"Closure probability is unset for {active_missing_prob} of {active_count} active deals ({active_missing_prob_pct:.1f}%). "
            f"Weighted pipeline (₹{weighted_pipeline_val:,.2f}) reflects only the {weighted_count} active deals with both value and probability recorded."
        )

    return {
        "filtered_sector": sector,
        "filtered_stage": stage,
        "total_deals": total_deals,
        "active_pipeline_count": active_count,
        "won_deals_count": won_count,
        "lost_or_dormant_count": lost_count,
        "active_pipeline_unweighted_value": round(active_val_unweighted, 2),
        "active_pipeline_weighted_value": round(weighted_pipeline_val, 2),
        "won_deals_total_value": round(won_val, 2),
        "total_recorded_value": round(total_val_all, 2),
        "deals_missing_value_count": total_missing_val,
        "deals_missing_value_pct": round(missing_val_pct, 1),
        "active_deals_missing_prob_count": active_missing_prob,
        "stage_breakdown": stage_breakdown,
        "sector_breakdown": sector_breakdown,
        "caveats": caveats,
    }


# ---------------------------------------------------------------------------
# Revenue & Collections Analytics
# ---------------------------------------------------------------------------

def compute_revenue_summary(
    norm_wo_df: pd.DataFrame,
    sector: str | None = None,
) -> dict[str, Any]:
    """Computes deterministic revenue, billing, and accounts receivable metrics.
    
    Crucially preserves and isolates negative values (credit balances, negative billing balances)
    without clamping them to zero.
    """
    df = norm_wo_df.copy()

    # Sector filtering (case-insensitive with synonym resolution)
    resolved_sector = resolve_sector_synonym(sector)
    if resolved_sector:
        s_norm = resolved_sector.lower()
        df = df[df["Sector"].astype(str).str.lower() == s_norm]

    total_orders = len(df)

    # Monetary columns
    amt_excl_col = "Amount in Rupees (Excl of GST) (Masked)"
    amt_incl_col = "Amount in Rupees (Incl of GST) (Masked)"
    billed_excl_col = "Billed Value in Rupees (Excl of GST.) (Masked)"
    # NOTE: the source board column literally contains the abbreviation period
    # ("... (Incl of GST.) (Masked)"). Omitting the dot silently yields 0.0 and was a
    # real regression (total_billed_value_incl_gst always reported ₹0). Do not "tidy" this.
    billed_incl_col = "Billed Value in Rupees (Incl of GST.) (Masked)"
    collected_incl_col = "Collected Amount in Rupees (Incl of GST.) (Masked)"
    receivable_col = "Amount Receivable (Masked)"
    amt_to_bill_excl_col = "Amount to be billed in Rs. (Exl. of GST) (Masked)"
    amt_to_bill_incl_col = "Amount to be billed in Rs. (Incl. of GST) (Masked)"

    total_order_val_excl = df[amt_excl_col].dropna().sum() if amt_excl_col in df.columns else 0.0
    total_order_val_incl = df[amt_incl_col].dropna().sum() if amt_incl_col in df.columns else 0.0
    total_billed_excl = df[billed_excl_col].dropna().sum() if billed_excl_col in df.columns else 0.0
    total_billed_incl = df[billed_incl_col].dropna().sum() if billed_incl_col in df.columns else 0.0
    total_collected_incl = df[collected_incl_col].dropna().sum() if collected_incl_col in df.columns else 0.0

    # Receivables breakdown (positive vs negative credit balances)
    receivable_series = df[receivable_col].dropna() if receivable_col in df.columns else pd.Series(dtype=float)
    net_receivable = receivable_series.sum()
    gross_positive_receivable = receivable_series[receivable_series > 0].sum()
    credit_balance_total = receivable_series[receivable_series < 0].sum()
    credit_balance_accounts = int((receivable_series < 0).sum())

    # Amount to be billed negative values
    to_bill_excl_series = df[amt_to_bill_excl_col].dropna() if amt_to_bill_excl_col in df.columns else pd.Series(dtype=float)
    to_bill_incl_series = df[amt_to_bill_incl_col].dropna() if amt_to_bill_incl_col in df.columns else pd.Series(dtype=float)
    neg_to_bill_excl_count = int((to_bill_excl_series < 0).sum())
    neg_to_bill_excl_total = to_bill_excl_series[to_bill_excl_series < 0].sum()
    neg_to_bill_incl_total = to_bill_incl_series[to_bill_incl_series < 0].sum()

    # Null counts in monetary fields (Blank != 0)
    billed_excl_nulls = int(df[billed_excl_col].isna().sum()) if billed_excl_col in df.columns else 0
    collected_nulls = int(df[collected_incl_col].isna().sum()) if collected_incl_col in df.columns else 0

    # Invoice Status breakdown
    invoice_status_breakdown: dict[str, int] = {}
    if "Invoice Status" in df.columns:
        inv_counts = df["Invoice Status"].value_counts().to_dict()
        invoice_status_breakdown = {str(k): int(v) for k, v in inv_counts.items()}

    # Execution Status breakdown
    execution_status_breakdown: dict[str, int] = {}
    if "Execution Status" in df.columns:
        exec_counts = df["Execution Status"].value_counts().to_dict()
        execution_status_breakdown = {str(k): int(v) for k, v in exec_counts.items()}

    # Sector breakdown
    sector_breakdown: dict[str, dict[str, Any]] = {}
    if "Sector" in df.columns:
        for sec_name, grp in df.groupby("Sector", dropna=False):
            sec_label = str(sec_name) if pd.notna(sec_name) else "Unspecified"
            sector_breakdown[sec_label] = {
                "orders_count": len(grp),
                "total_order_val_excl": round(grp[amt_excl_col].dropna().sum(), 2) if amt_excl_col in grp else 0.0,
                "billed_val_excl": round(grp[billed_excl_col].dropna().sum(), 2) if billed_excl_col in grp else 0.0,
                "collected_val_incl": round(grp[collected_incl_col].dropna().sum(), 2) if collected_incl_col in grp else 0.0,
                "net_receivable": round(grp[receivable_col].dropna().sum(), 2) if receivable_col in grp else 0.0,
            }

    # Data Quality Caveats
    caveats: list[str] = []
    if credit_balance_accounts > 0:
        caveats.append(
            f"Credit balances detected: {credit_balance_accounts} account(s) show net credit balances / overpayments "
            f"totaling ₹{abs(credit_balance_total):,.2f}. Gross positive receivables are ₹{gross_positive_receivable:,.2f} "
            f"(Net: ₹{net_receivable:,.2f})."
        )
    if neg_to_bill_excl_count > 0:
        caveats.append(
            f"Negative billing balances: {neg_to_bill_excl_count} work order(s) show negative amount-to-be-billed "
            f"totaling ₹{neg_to_bill_excl_total:,.2f} Excl GST (₹{neg_to_bill_incl_total:,.2f} Incl GST), "
            f"representing execution adjustments."
        )
    if billed_excl_nulls > 0 or collected_nulls > 0:
        caveats.append(
            f"Unbilled/Uncollected null tracking: {billed_excl_nulls} orders have null billed values and {collected_nulls} have null collected amounts. "
            f"These blanks are treated as unrecorded values rather than zero and should not be interpreted as confirmed outstanding balances without additional billing/collection information."
        )
    if invoice_status_breakdown.get("UNKNOWN_WITH_BILLING", 0) > 0:
        unk_b_count = invoice_status_breakdown["UNKNOWN_WITH_BILLING"]
        caveats.append(
            f"Bookkeeping integrity flag: {unk_b_count} work order(s) have positive billed value but an unset invoice status (UNKNOWN_WITH_BILLING)."
        )

    return {
        "filtered_sector": sector,
        "total_work_orders": total_orders,
        "total_order_value_excl_gst": round(total_order_val_excl, 2),
        "total_order_value_incl_gst": round(total_order_val_incl, 2),
        "total_billed_value_excl_gst": round(total_billed_excl, 2),
        "total_billed_value_incl_gst": round(total_billed_incl, 2),
        "total_collected_value_incl_gst": round(total_collected_incl, 2),
        "net_receivables": round(net_receivable, 2),
        "gross_positive_receivables": round(gross_positive_receivable, 2),
        "credit_balance_total": round(credit_balance_total, 2),
        "credit_balance_accounts_count": credit_balance_accounts,
        "negative_billing_excl_count": neg_to_bill_excl_count,
        "negative_billing_excl_total": round(neg_to_bill_excl_total, 2),
        "invoice_status_breakdown": invoice_status_breakdown,
        "execution_status_breakdown": execution_status_breakdown,
        "sector_breakdown": sector_breakdown,
        "caveats": caveats,
    }


# ---------------------------------------------------------------------------
# Cross-Board Delivery Analytics
# ---------------------------------------------------------------------------

def compute_cross_board_delivery(
    norm_wo_df: pd.DataFrame,
    norm_deals_df: pd.DataFrame,
    wo_items: list[dict[str, Any]] | None = None,
    sector: str | None = None,
    view: str | None = None,
) -> dict[str, Any]:
    """Computes cross-board delivery and fulfillment alignment for matched Work Orders & Deals.
    
    Performs deterministic calculations for:
    - Live Connect Boards link coverage (never assumes hardcoded counts)
    - Commercial Risk Audit (work orders active or completed on unclosed Deals)
    - Contract Value Variance (Deal Value contracted vs WO Booked vs Billed)
    - Won Deals Execution Backlog (Won deals without linked Work Orders)
    - Unlinked Work Orders Financial Exposure (unattributed operations)
    - Cross-department Owner and Sector Alignment
    """
    join_res = join_work_orders_to_deals(norm_wo_df, norm_deals_df, wo_items=wo_items)
    pairs = list(join_res["linked_pairs"])

    resolved_sector = resolve_sector_synonym(sector)
    if resolved_sector:
        s_norm = resolved_sector.lower()
        pairs = [p for p in pairs if str(p.get("wo_sector", "")).lower() == s_norm or str(p.get("deal_sector", "")).lower() == s_norm]

    total_matched = len(pairs)

    # 1. Fulfillment & Status Breakdown
    completed_and_won = 0
    completed_open_deal = 0
    ongoing_or_not_started = 0
    total_matched_order_value = 0.0
    total_matched_billed_value = 0.0
    total_matched_deal_value = 0.0
    matched_deals_with_value_count = 0

    # 2. Commercial Risk Tracking
    unclosed_risk_pairs: list[dict[str, Any]] = []
    unclosed_risk_value = 0.0
    unclosed_risk_billed = 0.0
    high_risk_count = 0

    # 3. Value Variance Tracking
    contract_leakage_value = 0.0
    scope_expansion_value = 0.0
    leakage_count = 0
    expansion_count = 0
    aligned_count = 0
    unrecorded_deal_value_count = 0

    # 4. Alignment Tracking
    owner_matches = 0
    owner_comparable = 0
    sector_matches = 0
    sector_comparable = 0

    for p in pairs:
        e_stat = str(p.get("wo_execution_status", "")).strip()
        e_stat_lower = e_stat.lower()
        d_stat = str(p.get("deal_status", "")).strip()
        d_stat_lower = d_stat.lower()
        d_stage = str(p.get("deal_stage", "")).strip()

        amt = p.get("wo_amount_excl_gst")
        billed = p.get("wo_billed_excl_gst")
        deal_val = p.get("deal_value")

        amt_f = float(amt) if (amt is not None and pd.notna(amt)) else 0.0
        billed_f = float(billed) if (billed is not None and pd.notna(billed)) else 0.0

        if amt is not None and pd.notna(amt):
            total_matched_order_value += amt_f
        if billed is not None and pd.notna(billed):
            total_matched_billed_value += billed_f

        # Fulfillment classification
        if e_stat_lower == "completed" and d_stat_lower == "won":
            completed_and_won += 1
        elif e_stat_lower == "completed" and d_stat_lower != "won":
            completed_open_deal += 1
        else:
            ongoing_or_not_started += 1

        # Commercial Risk Audit (Orders executing on unclosed deals)
        is_won = (d_stat_lower == "won")
        p["is_commercial_risk"] = not is_won
        if not is_won:
            if e_stat_lower in ("completed", "ongoing"):
                severity = "HIGH"
                high_risk_count += 1
                reason = f"Operations {e_stat} on non-won deal ({d_stat or 'No Status'} - {d_stage or 'No Stage'})"
            elif e_stat_lower in ("executed until current month", "partial completed"):
                severity = "MEDIUM"
                reason = f"Active execution ({e_stat}) on open deal ({d_stat or 'Open'})"
            else:
                severity = "LOW"
                reason = f"Work order queued ({e_stat}) on pending deal"

            p["risk_severity"] = severity
            p["risk_reason"] = reason
            unclosed_risk_pairs.append({
                "wo_serial": p["wo_serial"],
                "deal_name": p["deal_name"] or p["wo_deal_name"],
                "deal_status": p["deal_status"],
                "deal_stage": p["deal_stage"],
                "wo_execution_status": p["wo_execution_status"],
                "wo_amount_excl_gst": round(amt_f, 2),
                "wo_billed_excl_gst": round(billed_f, 2),
                "risk_severity": severity,
                "risk_reason": reason,
            })
            unclosed_risk_value += amt_f
            unclosed_risk_billed += billed_f
        else:
            p["risk_severity"] = "NONE"
            p["risk_reason"] = "Deal won"

        # Value Variance Analysis
        if deal_val is not None and pd.notna(deal_val):
            deal_val_f = float(deal_val)
            total_matched_deal_value += deal_val_f
            matched_deals_with_value_count += 1

            if amt is not None and pd.notna(amt):
                variance = round(deal_val_f - amt_f, 2)
                var_pct = round((variance / deal_val_f * 100.0), 1) if deal_val_f > 0 else 0.0

                if variance > (0.05 * deal_val_f):
                    cat = "Contract Leakage / Under-booked"
                    leakage_count += 1
                    contract_leakage_value += variance
                elif variance < -(0.05 * deal_val_f):
                    cat = "Scope Expansion / Over-delivered"
                    expansion_count += 1
                    scope_expansion_value += abs(variance)
                else:
                    cat = "Aligned"
                    aligned_count += 1

                p["variance_deal_vs_wo"] = variance
                p["variance_percentage"] = var_pct
                p["variance_category"] = cat
            else:
                p["variance_deal_vs_wo"] = None
                p["variance_percentage"] = None
                p["variance_category"] = "Unrecorded Work Order Value"
        else:
            unrecorded_deal_value_count += 1
            p["variance_deal_vs_wo"] = None
            p["variance_percentage"] = None
            p["variance_category"] = "Unrecorded Deal Value"

        # Owner and Sector Alignment
        wo_own = str(p.get("wo_owner") or "").strip()
        deal_own = str(p.get("deal_owner") or "").strip()
        if wo_own and deal_own and wo_own.lower() not in ("none", "nan") and deal_own.lower() not in ("none", "nan"):
            owner_comparable += 1
            if wo_own.lower() == deal_own.lower():
                owner_matches += 1

        wo_sec = resolve_sector_synonym(p.get("wo_sector"))
        deal_sec = resolve_sector_synonym(p.get("deal_sector"))
        if wo_sec and deal_sec:
            sector_comparable += 1
            if wo_sec.lower() == deal_sec.lower():
                sector_matches += 1

    # Sort risk orders with HIGH severity first, then by order value descending
    unclosed_risk_pairs.sort(key=lambda x: (0 if x["risk_severity"] == "HIGH" else (1 if x["risk_severity"] == "MEDIUM" else 2), -x["wo_amount_excl_gst"]))

    # 5. Won Deals Without Work Orders
    linked_deal_ids = {str(p["deal_item_id"]).strip() for p in join_res["linked_pairs"] if p.get("deal_item_id")}
    won_mask = norm_deals_df["is_won"] if "is_won" in norm_deals_df.columns else (norm_deals_df["Deal Status"].str.lower() == "won")
    won_df = norm_deals_df[won_mask]
    total_won_deals = len(won_df)

    won_deals_without_wo_list: list[dict[str, Any]] = []
    won_deals_without_wo_val = 0.0
    won_deals_with_wo_cnt = 0

    for idx, drow in won_df.iterrows():
        item_id = str(drow.get("item_id", "")).strip()
        row_id_str = str(int(cast("Any", idx)) + 1)
        is_linked = (item_id in linked_deal_ids) or (row_id_str in linked_deal_ids)

        if is_linked:
            won_deals_with_wo_cnt += 1
        else:
            dv = drow.get("Masked Deal value")
            dv_f = float(dv) if (dv is not None and pd.notna(dv)) else 0.0
            won_deals_without_wo_val += dv_f
            won_deals_without_wo_list.append({
                "deal_item_id": item_id or row_id_str,
                "deal_name": drow.get("Deal Name") or drow.get("item_name"),
                "client_code": drow.get("Client Code"),
                "sector": drow.get("normalized_sector") or drow.get("Sector/service"),
                "deal_value": round(dv_f, 2) if dv_f > 0 else None,
                "close_date": str(drow.get("Close Date (A)")) if pd.notna(drow.get("Close Date (A)")) else None,
            })

    won_deals_without_wo_cnt = total_won_deals - won_deals_with_wo_cnt

    # 6. Unlinked Work Orders Exposure
    unlinked_serials_set = set(join_res["unlinked_serials"])
    unlinked_wo_df = norm_wo_df[norm_wo_df["Serial #"].isin(unlinked_serials_set)]
    unlinked_order_col = "Amount in Rupees (Excl of GST) (Masked)"
    unlinked_billed_col = "Billed Value in Rupees (Excl of GST.) (Masked)"
    unlinked_val_excl = float(unlinked_wo_df[unlinked_order_col].dropna().sum()) if unlinked_order_col in unlinked_wo_df else 0.0
    unlinked_billed_excl = float(unlinked_wo_df[unlinked_billed_col].dropna().sum()) if unlinked_billed_col in unlinked_wo_df else 0.0

    # 7. Construct Dynamic Caveats
    coverage_pct = join_res["link_coverage_percentage"]
    caveats = [
        (
            f"Cross-board join coverage: {join_res['linked_work_orders_count']} of {join_res['total_work_orders']} work orders "
            f"({coverage_pct:.1f}%) are currently linked via native Monday Connect Boards."
        ),
    ]
    if len(unclosed_risk_pairs) > 0:
        caveats.append(
            f"Commercial Risk Alert: {len(unclosed_risk_pairs)} confirmed linked work order(s) totaling ₹{unclosed_risk_value:,.2f} Excl GST "
            f"are ongoing or completed against deals that are not in a Won state ({high_risk_count} with Completed or Ongoing status)."
        )
    if won_deals_without_wo_cnt > 0:
        caveats.append(
            f"Execution Backlog: {won_deals_without_wo_cnt} won deal(s) totaling ₹{won_deals_without_wo_val:,.2f} pipeline value "
            f"have no linked Work Order recorded."
        )
    caveats.append(
        f"Unlinked Work Orders Exposure: {len(unlinked_serials_set)} unlinked work orders represent ₹{unlinked_val_excl:,.2f} "
        f"of booked work-order value currently unlinked to a confirmed CRM deal on Monday.com. The corresponding deal attribution cannot be established from the confirmed native links."
    )

    return {
        # Core original fields (strictly preserved for backwards compatibility)
        "filtered_sector": sector,
        "total_work_orders": join_res["total_work_orders"],
        "total_deals": join_res["total_deals"],
        "matched_orders_count": total_matched,
        "unmatched_orders_count": join_res["unlinked_work_orders_count"],
        "link_coverage_percentage": coverage_pct,
        "completed_and_won_count": completed_and_won,
        "completed_with_open_deal_count": completed_open_deal,
        "ongoing_or_pending_count": ongoing_or_not_started,
        "total_matched_order_value_excl_gst": round(total_matched_order_value, 2),
        "total_matched_billed_value_excl_gst": round(total_matched_billed_value, 2),
        "matched_sample": pairs[:10],
        "caveats": caveats,

        # Enhanced Founder-Level Intelligence Fields
        "total_matched_deal_value_excl_gst": round(total_matched_deal_value, 2),
        "commercial_risk": {
            "unclosed_deal_risk_count": len(unclosed_risk_pairs),
            "high_risk_orders_count": high_risk_count,
            "unclosed_deal_risk_value_excl_gst": round(unclosed_risk_value, 2),
            "unclosed_deal_risk_billed_excl_gst": round(unclosed_risk_billed, 2),
            "risk_orders": unclosed_risk_pairs,
        },
        "value_variance": {
            "matched_deals_with_value_count": matched_deals_with_value_count,
            "contract_leakage_count": leakage_count,
            "contract_leakage_value": round(contract_leakage_value, 2),
            "scope_expansion_count": expansion_count,
            "scope_expansion_value": round(scope_expansion_value, 2),
            "aligned_count": aligned_count,
            "unrecorded_deal_value_count": unrecorded_deal_value_count,
        },
        "won_deals_backlog": {
            "total_won_deals": total_won_deals,
            "won_deals_with_wo_count": won_deals_with_wo_cnt,
            "won_deals_without_wo_count": won_deals_without_wo_cnt,
            "won_deals_without_wo_value": round(won_deals_without_wo_val, 2),
            "sample_won_deals_without_wo": won_deals_without_wo_list[:10],
        },
        "unlinked_exposure": {
            "unlinked_orders_count": len(unlinked_serials_set),
            "unlinked_orders_value_excl_gst": round(unlinked_val_excl, 2),
            "unlinked_orders_billed_excl_gst": round(unlinked_billed_excl, 2),
        },
        "alignment": {
            "owner_match_rate_pct": round((owner_matches / owner_comparable * 100.0), 1) if owner_comparable > 0 else 0.0,
            "owner_matches": owner_matches,
            "owner_comparable_count": owner_comparable,
            "sector_match_rate_pct": round((sector_matches / sector_comparable * 100.0), 1) if sector_comparable > 0 else 0.0,
            "sector_matches": sector_matches,
            "sector_comparable_count": sector_comparable,
        },
        "view": view or "summary",
        "linked_items": pairs,
    }


# ---------------------------------------------------------------------------
# Leadership Update Briefing Generator (§10)
# ---------------------------------------------------------------------------

def generate_leadership_update(
    norm_wo_df: pd.DataFrame,
    norm_deals_df: pd.DataFrame,
    wo_items: list[dict[str, Any]] | None = None,
    period: str | None = None,
) -> dict[str, Any]:
    """Generates an executive-ready leadership update briefing in structured markdown.
    
    Includes core KPIs, revenue health, deal pipeline, cross-board alignment,
    and prominent data-integrity caveats per §10.
    """
    rev = compute_revenue_summary(norm_wo_df)
    pipe = compute_pipeline_summary(norm_deals_df)
    delivery = compute_cross_board_delivery(norm_wo_df, norm_deals_df, wo_items=wo_items)

    p_title = period.strip() if period and period.strip() else "Current Period"

    # Format briefing markdown
    md = []
    md.append(f"# Skylark Drones — Leadership Executive Briefing ({p_title})\n")
    
    md.append("## 1. Executive Summary & Core KPIs")
    md.append(f"- **Active Pipeline (Unweighted)**: ₹{pipe['active_pipeline_unweighted_value']:,.2f} across {pipe['active_pipeline_count']} deals")
    md.append(f"- **Active Pipeline (Probability-Weighted)**: ₹{pipe['active_pipeline_weighted_value']:,.2f}")
    md.append(f"- **Won Deals Value**: ₹{pipe['won_deals_total_value']:,.2f} across {pipe['won_deals_count']} deals")
    md.append(f"- **Total Work Order Bookings (Excl. GST)**: ₹{rev['total_order_value_excl_gst']:,.2f} ({rev['total_work_orders']} orders)")
    md.append(f"- **Total Billed Value (Excl. GST)**: ₹{rev['total_billed_value_excl_gst']:,.2f}")
    md.append(f"- **Total Collected (Incl. GST)**: ₹{rev['total_collected_value_incl_gst']:,.2f}")
    md.append(f"- **Net Outstanding Receivables**: ₹{rev['net_receivables']:,.2f} (Gross: ₹{rev['gross_positive_receivables']:,.2f})")
    md.append("")

    md.append("## 2. Revenue & Delivery Health")
    md.append(f"- **Execution Status Breakdown**: {', '.join(f'{k}: {v}' for k, v in rev['execution_status_breakdown'].items())}")
    md.append(f"- **Billing Breakdown**: {', '.join(f'{k}: {v}' for k, v in rev['invoice_status_breakdown'].items())}")
    md.append("")

    md.append("## 3. Cross-Board Alignment (Work Orders ↔ Deals)")
    md.append(f"- **Live Connect Boards Coverage**: {delivery['matched_orders_count']} of {delivery['total_work_orders']} work orders ({delivery['link_coverage_percentage']}%) are linked to tracked deals on Monday.com.")
    md.append(f"- **Completed & Won Fulfillment**: {delivery['completed_and_won_count']} orders completed with Won deal status.")
    md.append("")

    md.append("## 4. Critical Data Quality & Bookkeeping Alerts")
    for c in rev["caveats"]:
        md.append(f"- ⚠️ **Billing / Receivables**: {c}")
    for c in pipe["caveats"]:
        md.append(f"- ⚠️ **Pipeline**: {c}")
    for c in delivery["caveats"]:
        md.append(f"- ⚠️ **Linkage**: {c}")

    markdown_text = "\n".join(md)

    return {
        "period": p_title,
        "revenue_kpis": rev,
        "pipeline_kpis": pipe,
        "delivery_kpis": delivery,
        "markdown_briefing": markdown_text,
    }


# ---------------------------------------------------------------------------
# Data Quality Report Tool Wrapper
# ---------------------------------------------------------------------------

def get_data_quality_summary(
    norm_wo_df: pd.DataFrame | None = None,
    norm_deals_df: pd.DataFrame | None = None,
    board_name: str = "both",
    wo_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Retrieves structured data quality metrics and narrative caveats from quality_report.py.

    When both frames are supplied the cross-board narrative caveats and their underlying
    machine-readable counts (`caveat_metrics`) are included, so consumers (agent and UI)
    never have to hardcode data-quality numbers. Live Connect Boards coverage is measured
    dynamically whenever raw ``wo_items`` are provided.
    """
    result: dict[str, Any] = {}
    target = board_name.strip().lower()

    if target in ("work_orders", "work_order", "wo", "both") and norm_wo_df is not None:
        result["work_orders"] = quality_report(norm_wo_df, "Work Orders")
        result["gst_check"] = check_gst_relationship(norm_wo_df)

    if target in ("deals", "deal", "both") and norm_deals_df is not None:
        result["deals"] = quality_report(norm_deals_df, "Deals")

    # Cross-board narrative caveats + derived metrics (dynamically computed, never hardcoded)
    if norm_wo_df is not None and norm_deals_df is not None:
        join_summary: dict[str, int] | None = None
        if wo_items is not None:
            live_join = join_work_orders_to_deals(norm_wo_df, norm_deals_df, wo_items=wo_items)
            join_summary = {
                "matched_count": live_join["linked_work_orders_count"],
                "unmatched_work_orders": live_join["unlinked_work_orders_count"],
                "unmatched_deals": max(len(norm_deals_df) - live_join["linked_work_orders_count"], 0),
            }
        cross_board = generate_quality_report(
            norm_wo_df, norm_deals_df, join_summary=join_summary
        )
        result["caveats"] = cross_board["caveats"]
        result["caveat_metrics"] = cross_board["caveat_metrics"]

    return result
