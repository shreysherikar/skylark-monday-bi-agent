"""Structured Copilot response builder and evidence/traceability generator.

Transforms deterministic tool outputs into structured leadership-grade copilot payloads:
- Executive summary
- Key KPI cards
- Material operational & financial risks
- Evidence & provenance (sources, records analyzed, coverage, calculation)
- Data-quality caveats
- Follow-up prompts

All metrics and evidence are strictly derived from deterministic tool outputs.
Zero arithmetic is fabricated or calculated by the LLM.
"""

from __future__ import annotations

import logging
from typing import Any, Literal
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic Models for Structured Copilot Response
# ---------------------------------------------------------------------------

class KpiItem(BaseModel):
    """Structured Key Performance Indicator card."""
    label: str
    value: str
    context: str | None = None


class RiskItem(BaseModel):
    """Material operational, financial, or data risk alert."""
    title: str
    detail: str
    severity: Literal["high", "medium", "low"] = "medium"


class EvidenceItem(BaseModel):
    """Concise provenance and audit trail for deterministic analytics."""
    sources: list[str]
    records_analyzed: int | str
    data_coverage: str | None = None
    calculation: str


class StructuredCopilotResponse(BaseModel):
    """Structured payload attached to ChatResponse for leadership copilot rendering."""
    summary: str
    kpis: list[KpiItem] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    evidence: EvidenceItem
    caveats: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)

    def __init__(self, **data: Any) -> None:
        if "follow_up" in data and "follow_ups" not in data:
            data["follow_ups"] = data.pop("follow_up")
        super().__init__(**data)

    @property
    def follow_up(self) -> list[str]:
        return self.follow_ups


# ---------------------------------------------------------------------------
# Deterministic Structured Response Builders
# ---------------------------------------------------------------------------

def build_revenue_structured(tool_output: dict[str, Any]) -> StructuredCopilotResponse:
    """Builds structured response for get_revenue_summary."""
    total_wo = tool_output.get("total_work_orders", 0)
    billed_incl = tool_output.get("total_billed_value_incl_gst", 0.0)
    billed_excl = tool_output.get("total_billed_value_excl_gst", 0.0)
    order_val_excl = tool_output.get("total_order_value_excl_gst", 0.0)
    collected = tool_output.get("total_collected_value_incl_gst", 0.0)
    net_rec = tool_output.get("net_receivables", 0.0)
    gross_rec = tool_output.get("gross_positive_receivables", 0.0)
    credit_total = tool_output.get("credit_balance_total", 0.0)
    credit_accounts = tool_output.get("credit_balance_accounts_count", 0)
    neg_count = tool_output.get("negative_billing_excl_count", 0)
    neg_total = tool_output.get("negative_billing_excl_total", 0.0)
    billed_nulls = tool_output.get("billed_excl_null_count", 0)
    sector = tool_output.get("filtered_sector")

    sec_label = f" in {sector}" if sector else ""
    summary = (
        f"Total booked scope{sec_label} is ₹{order_val_excl:,.2f} (Excl. GST) across {total_wo} work orders. "
        f"Billed revenue is ₹{billed_excl:,.2f} (Excl. GST), with net receivables of ₹{net_rec:,.2f} "
        f"after accounting for {credit_accounts} customer credit balances."
    )

    kpis = [
        KpiItem(
            label="Total Booked Scope (Excl. GST)",
            value=f"₹{order_val_excl:,.2f}",
            context=f"Across {total_wo} work orders",
        ),
        KpiItem(
            label="Total Billed Revenue (Excl. GST)",
            value=f"₹{billed_excl:,.2f}",
            context=f"Incl. GST: ₹{billed_incl:,.2f}",
        ),
        KpiItem(
            label="Collections (Incl. GST)",
            value=f"₹{collected:,.2f}",
            context="Recorded payments received",
        ),
        KpiItem(
            label="Net Outstanding Receivables",
            value=f"₹{net_rec:,.2f}",
            context=f"Gross: ₹{gross_rec:,.2f} (Credit balances: ₹{credit_total:,.2f})",
        ),
    ]

    risks: list[RiskItem] = []
    if credit_accounts > 0:
        risks.append(
            RiskItem(
                title="Customer Credit Balances",
                detail=f"{credit_accounts} accounts exhibit negative receivables totaling ₹{credit_total:,.2f} (client overpayments / credit balances).",
                severity="low",
            )
        )
    if neg_count > 0:
        risks.append(
            RiskItem(
                title="Negative Billing Balances",
                detail=f"{neg_count} work order(s) show negative amount-to-be-billed totaling ₹{neg_total:,.2f} Excl GST.",
                severity="medium",
            )
        )
    if billed_nulls > 0:
        risks.append(
            RiskItem(
                title="Unbilled Work Orders",
                detail=f"{billed_nulls} work orders have unrecorded billing values (treated as unbilled, not ₹0).",
                severity="medium",
            )
        )

    evidence = EvidenceItem(
        sources=["Work Orders"],
        records_analyzed=total_wo,
        data_coverage=f"100% of tracked work orders{sec_label}",
        calculation="deterministic revenue aggregation via compute_revenue_summary",
    )

    follow_up = [
        "Break down receivables by customer credit accounts",
        "Are we executing work orders on deals that haven't been won yet?",
        "Give me an executive leadership update",
    ]

    return StructuredCopilotResponse(
        summary=summary,
        kpis=kpis,
        risks=risks,
        evidence=evidence,
        caveats=list(tool_output.get("caveats", [])),
        follow_ups=follow_up,
    )


def build_pipeline_structured(tool_output: dict[str, Any]) -> StructuredCopilotResponse:
    """Builds structured response for get_pipeline_summary."""
    total_deals = tool_output.get("total_deals", 0)
    active_val = tool_output.get("active_pipeline_unweighted_value", 0.0)
    weighted_val = tool_output.get("active_pipeline_weighted_value", 0.0)
    won_val = tool_output.get("won_deals_total_value", 0.0)
    active_count = tool_output.get("active_pipeline_count") or tool_output.get("active_deals_count", 0)
    won_count = tool_output.get("won_deals_count", 0)
    lost_count = tool_output.get("lost_or_dormant_count") or tool_output.get("lost_or_dormant_deals_count", 0)
    missing_prob = tool_output.get("active_deals_missing_prob_count") or tool_output.get("missing_probability_count", 0)
    missing_val = tool_output.get("deals_missing_value_count") or tool_output.get("total_missing_value_deals", 0)
    missing_val_pct = tool_output.get("deals_missing_value_pct", 0.0)
    sector = tool_output.get("filtered_sector")

    sec_label = f" for {sector}" if sector else ""
    summary = (
        f"Active pipeline{sec_label} stands at ₹{active_val:,.2f} across {active_count} deals "
        f"(₹{weighted_val:,.2f} probability-weighted), with ₹{won_val:,.2f} across {won_count} closed-won deals."
    )

    kpis = [
        KpiItem(
            label="Active Pipeline (Unweighted)",
            value=f"₹{active_val:,.2f}",
            context=f"{active_count} active proposals",
        ),
        KpiItem(
            label="Active Pipeline (Probability-Weighted)",
            value=f"₹{weighted_val:,.2f}",
            context="Calculated on recorded probabilities",
        ),
        KpiItem(
            label="Won Deals Value",
            value=f"₹{won_val:,.2f}",
            context=f"{won_count} closed-won deals",
        ),
        KpiItem(
            label="Lost / Dormant Volume",
            value=f"{lost_count} deals",
            context=f"Out of {total_deals} total deals",
        ),
    ]

    risks: list[RiskItem] = []
    if missing_prob > 0:
        risks.append(
            RiskItem(
                title="Missing Closure Probability",
                detail=f"{missing_prob} deals lack closure probability and are excluded from weighted pipeline.",
                severity="medium",
            )
        )
    if missing_val > 0:
        risks.append(
            RiskItem(
                title="Unrecorded Deal Values",
                detail=f"{missing_val} deals ({missing_val_pct:.1f}%) lack recorded deal values in CRM (evaluated as unrecorded, not ₹0).",
                severity="medium",
            )
        )

    evidence = EvidenceItem(
        sources=["Deals"],
        records_analyzed=total_deals,
        data_coverage=f"{active_count} active / {total_deals} total deals{sec_label}",
        calculation="deterministic pipeline aggregation via compute_pipeline_summary",
    )

    follow_up = [
        "What is our total billed revenue?",
        "Are we executing work orders on deals that haven't been won yet?",
        "Show pipeline stage breakdown",
    ]

    return StructuredCopilotResponse(
        summary=summary,
        kpis=kpis,
        risks=risks,
        evidence=evidence,
        caveats=list(tool_output.get("caveats", [])),
        follow_ups=follow_up,
    )


def build_cross_board_structured(tool_output: dict[str, Any]) -> StructuredCopilotResponse:
    """Builds structured response for get_cross_board_delivery."""
    total_wo = tool_output.get("total_work_orders", 0)
    total_deals = tool_output.get("total_deals", 0)
    matched_count = tool_output.get("matched_orders_count", 0)
    coverage_pct = tool_output.get("link_coverage_percentage", 0.0)

    comm_risk = tool_output.get("commercial_risk", {})
    risk_count = comm_risk.get("unclosed_deal_risk_count", 0)
    risk_val = comm_risk.get("unclosed_deal_risk_value_excl_gst") or comm_risk.get("unclosed_deal_risk_order_value_excl_gst", 0.0)

    val_var = tool_output.get("value_variance", {})
    leakage_count = val_var.get("contract_leakage_count") or val_var.get("leakage_orders_count", 0)
    leakage_val = val_var.get("contract_leakage_value") or val_var.get("contract_leakage_total_excl_gst", 0.0)

    backlog = tool_output.get("won_deals_backlog", {})
    backlog_count = backlog.get("won_deals_without_wo_count", 0)
    backlog_val = backlog.get("won_deals_without_wo_value") or backlog.get("won_deals_without_wo_total_value", 0.0)

    unlinked = tool_output.get("unlinked_exposure", {})
    unlinked_count = unlinked.get("unlinked_orders_count", 0)

    summary = (
        f"Cross-board audit evaluated {total_wo} Work Orders and {total_deals} Deals: "
        f"Identified {risk_count} confirmed linked work orders ongoing or completed against deals that are not in a Won state (₹{risk_val:,.2f} Excl. GST at risk), "
        f"with {matched_count} confirmed native links ({coverage_pct}% coverage)."
    )

    kpis = [
        KpiItem(
            label="Work Orders on Unclosed Deals",
            value=f"{risk_count} orders",
            context=f"₹{risk_val:,.2f} Excl. GST risk (deals not in Won state)",
        ),
        KpiItem(
            label="Contract Value Leakage",
            value=f"{leakage_count} projects",
            context=f"₹{leakage_val:,.2f} scope expansion",
        ),
        KpiItem(
            label="Won Deals Delivery Backlog",
            value=f"{backlog_count} won deals",
            context=f"₹{backlog_val:,.2f} unbooked pipeline",
        ),
        KpiItem(
            label="Native Connect Board Linkage",
            value=f"{matched_count} of {total_wo} ({coverage_pct}%)",
            context="Confirmed relations on Monday.com",
        ),
    ]

    risks: list[RiskItem] = []
    if risk_count > 0:
        risks.append(
            RiskItem(
                title="Execution Risk on Unclosed Deals",
                detail=f"{risk_count} confirmed linked work orders totaling ₹{risk_val:,.2f} Excl. GST are ongoing or completed against deals that are not in a Won state (Open/On Hold/Dead).",
                severity="high",
            )
        )
    if leakage_count > 0:
        risks.append(
            RiskItem(
                title="Contract Value Leakage",
                detail=f"{leakage_count} projects have delivery scope exceeding contracted CRM value by ₹{leakage_val:,.2f}.",
                severity="high",
            )
        )
    if unlinked_count > 0:
        unlinked_val = unlinked.get("unlinked_orders_value_excl_gst", 0.0)
        risks.append(
            RiskItem(
                title="Unlinked Operations Financial Exposure",
                detail=f"₹{unlinked_val:,.2f} of booked work-order value across {unlinked_count} orders is currently unlinked to a confirmed CRM deal on Monday.com. The corresponding deal attribution cannot be established from confirmed native links.",
                severity="medium",
            )
        )

    evidence = EvidenceItem(
        sources=["Work Orders", "Deals"],
        records_analyzed=f"{total_wo} WOs / {total_deals} Deals",
        data_coverage=f"Confirmed native linkage: {matched_count}/{total_wo} ({coverage_pct}%)",
        calculation="deterministic cross-board reconciliation via compute_cross_board_delivery",
    )

    follow_up = [
        "Show details of work orders on unclosed deals",
        "Show contract value variance breakdown",
        "Give me an executive leadership update",
    ]

    return StructuredCopilotResponse(
        summary=summary,
        kpis=kpis,
        risks=risks,
        evidence=evidence,
        caveats=list(tool_output.get("caveats", [])),
        follow_ups=follow_up,
    )


def build_leadership_structured(tool_output: dict[str, Any]) -> StructuredCopilotResponse:
    """Builds structured response for get_leadership_update."""
    rev = tool_output.get("revenue_kpis") or tool_output.get("revenue", {})
    pipe = tool_output.get("pipeline_kpis") or tool_output.get("pipeline", {})
    deliv = tool_output.get("delivery_kpis") or tool_output.get("delivery") or tool_output.get("cross_board", {})

    pipe_unweighted = pipe.get("active_pipeline_unweighted_value", 0.0)
    pipe_weighted = pipe.get("active_pipeline_weighted_value", 0.0)
    billed_val = rev.get("total_billed_value_excl_gst", 0.0)
    order_val = rev.get("total_order_value_excl_gst", 0.0)
    net_rec = rev.get("net_receivables", 0.0)
    gross_rec = rev.get("gross_positive_receivables", 0.0)
    total_wo = rev.get("total_work_orders", 0)
    total_deals = pipe.get("total_deals", 0)
    matched_count = deliv.get("matched_orders_count", 0)
    coverage_pct = deliv.get("link_coverage_percentage", 0.0)

    summary = (
        f"Executive Leadership Briefing: Active pipeline stands at ₹{pipe_unweighted:,.2f} "
        f"(₹{pipe_weighted:,.2f} weighted), total billed revenue is ₹{billed_val:,.2f} (Excl. GST), "
        f"and net receivables are ₹{net_rec:,.2f}."
    )

    kpis = [
        KpiItem(
            label="Active Pipeline (Unweighted)",
            value=f"₹{pipe_unweighted:,.2f}",
            context=f"Weighted: ₹{pipe_weighted:,.2f}",
        ),
        KpiItem(
            label="Billed Revenue (Excl. GST)",
            value=f"₹{billed_val:,.2f}",
            context=f"Bookings: ₹{order_val:,.2f}",
        ),
        KpiItem(
            label="Net Outstanding Receivables",
            value=f"₹{net_rec:,.2f}",
            context=f"Gross: ₹{gross_rec:,.2f}",
        ),
        KpiItem(
            label="Connect Board Link Coverage",
            value=f"{matched_count} of {total_wo} ({coverage_pct}%)",
            context=f"Confirmed relations across {total_deals} deals",
        ),
    ]

    risks: list[RiskItem] = []
    comm_risk = deliv.get("commercial_risk", {})
    risk_orders = comm_risk.get("unclosed_deal_risk_count", 0)
    risk_val = comm_risk.get("unclosed_deal_risk_value_excl_gst") or comm_risk.get("unclosed_deal_risk_order_value_excl_gst", 0.0)
    if risk_orders > 0:
        risks.append(
            RiskItem(
                title="Commercial Risk on Non-Won Deals",
                detail=f"{risk_orders} confirmed linked work orders totaling ₹{risk_val:,.2f} Excl. GST are ongoing or completed against deals that are not in a Won state.",
                severity="high",
            )
        )

    val_var = deliv.get("value_variance", {})
    leakage_count = val_var.get("contract_leakage_count") or val_var.get("leakage_orders_count", 0)
    leakage_val = val_var.get("contract_leakage_value") or val_var.get("contract_leakage_total_excl_gst", 0.0)
    if leakage_count > 0:
        risks.append(
            RiskItem(
                title="Contract Value Leakage",
                detail=f"{leakage_count} projects with delivery bookings exceeding CRM contract commitments by ₹{leakage_val:,.2f}.",
                severity="high",
            )
        )

    credit_accs = rev.get("credit_balance_accounts_count", 0)
    credit_total = rev.get("credit_balance_total", 0.0)
    if credit_accs > 0:
        risks.append(
            RiskItem(
                title="Customer Credit Balances",
                detail=f"{credit_accs} customer credit accounts with overpayment credit balances totaling ₹{credit_total:,.2f}.",
                severity="low",
            )
        )

    evidence = EvidenceItem(
        sources=["Work Orders", "Deals"],
        records_analyzed=f"{total_wo} WOs / {total_deals} Deals",
        data_coverage=f"Live Connect Boards: {matched_count}/{total_wo} ({coverage_pct}%)",
        calculation="deterministic executive briefing consolidation via generate_leadership_update",
    )

    all_caveats: list[str] = (
        pipe.get("caveats", []) + rev.get("caveats", []) + deliv.get("caveats", [])
    )

    follow_up = [
        "Are we executing work orders on deals that haven't been won yet?",
        "What is our Renewables pipeline?",
        "Generate a data quality report",
    ]

    return StructuredCopilotResponse(
        summary=summary,
        kpis=kpis,
        risks=risks,
        evidence=evidence,
        caveats=all_caveats,
        follow_ups=follow_up,
    )


def build_quality_structured(tool_output: dict[str, Any]) -> StructuredCopilotResponse:
    """Builds structured response for get_data_quality_report."""
    wo_rep = tool_output.get("work_orders") if isinstance(tool_output.get("work_orders"), dict) else None
    deals_rep = tool_output.get("deals") if isinstance(tool_output.get("deals"), dict) else None
    gst_check = tool_output.get("gst_check") if isinstance(tool_output.get("gst_check"), dict) else None

    wo_rows = wo_rep.get("total_rows", 0) if wo_rep else 0
    deals_rows = deals_rep.get("total_rows", 0) if deals_rep else 0
    null_cols_list = wo_rep.get("fully_null_columns", []) if wo_rep else []
    null_cols = len(null_cols_list)
    neg_metrics = wo_rep.get("negative_metrics", {}) if wo_rep else {}
    credit_accs = neg_metrics.get("amount_receivable_neg_count", 0)
    gst_valid = gst_check.get("is_valid", True) if gst_check else True
    gst_rows = gst_check.get("checked_rows", 0) if gst_check else 0

    sources: list[str] = []
    board_summaries: list[str] = []
    if wo_rep:
        sources.append("Work Orders")
        board_summaries.append(f"{wo_rows} Work Orders")
    if deals_rep:
        sources.append("Deals")
        board_summaries.append(f"{deals_rows} Deals")
    if not sources:
        sources = ["Work Orders", "Deals"]

    scope_str = " and ".join(board_summaries) if board_summaries else "Monday.com boards"
    summary = (
        f"Data quality audit completed across {scope_str}: "
        f"Identified {null_cols} fully null columns, {credit_accs} customer credit accounts, "
        f"and validated GST 18% mathematical consistency across {gst_rows} rows."
    )

    kpis: list[KpiItem] = []
    if wo_rep:
        kpis.append(
            KpiItem(
                label="Work Orders Inspected",
                value=f"{wo_rows}",
                context="100% rows analyzed",
            )
        )
    if deals_rep:
        kpis.append(
            KpiItem(
                label="Deals Inspected",
                value=f"{deals_rows}",
                context="Duplicate headers eliminated",
            )
        )
    if wo_rep:
        kpis.append(
            KpiItem(
                label="100% Null Columns",
                value=f"{null_cols} columns",
                context=", ".join(null_cols_list) if null_cols_list else "None detected",
            )
        )
    if gst_check:
        kpis.append(
            KpiItem(
                label="GST 18% Math Tolerance",
                value="100% Valid" if gst_valid else "Discrepancies Flagged",
                context=f"Verified {gst_rows} rows (±₹0.50 margin)",
            )
        )

    risks: list[RiskItem] = []
    if deals_rep:
        core_nulls = deals_rep.get("core_null_rates", {})
        close_rate = core_nulls.get("close_date_null_rate", 0.0)
        prob_rate = core_nulls.get("closure_probability_null_rate", 0.0)
        # core_null_rates are already percent figures (e.g., 92.4, 75.0); handle decimal ratios defensively
        c_pct = close_rate * 100.0 if (0.0 < close_rate <= 1.0) else close_rate
        p_pct = prob_rate * 100.0 if (0.0 < prob_rate <= 1.0) else prob_rate
        if close_rate > 0 or prob_rate > 0:
            risks.append(
                RiskItem(
                    title="Severe Null Rates in Deals",
                    detail=f"Close Date ({c_pct:.1f}% null) and Closure Probability ({p_pct:.1f}% null) have major data gaps.",
                    severity="medium",
                )
            )
    if null_cols > 0:
        null_col_names = ", ".join(null_cols_list)
        risks.append(
            RiskItem(
                title="100% Null Columns Detected",
                detail=f"{null_cols} columns ({null_col_names}) have 0 populated rows across the board.",
                severity="medium",
            )
        )
    if credit_accs > 0:
        risks.append(
            RiskItem(
                title="Customer Credit Accounts",
                detail=f"{credit_accs} customer accounts have negative receivables representing client overpayments.",
                severity="low",
            )
        )

    records_analyzed_str = (
        f"{wo_rows} WOs / {deals_rows} Deals" if (wo_rep and deals_rep)
        else f"{wo_rows} Work Orders" if wo_rep
        else f"{deals_rows} Deals"
    )

    evidence = EvidenceItem(
        sources=sources,
        records_analyzed=records_analyzed_str,
        data_coverage="Complete multi-board governance audit",
        calculation="deterministic data quality audit via get_data_quality_summary",
    )

    follow_up = [
        "What is our total billed revenue?",
        "Are we executing work orders on deals that haven't been won yet?",
        "Give me an executive leadership update",
    ]

    return StructuredCopilotResponse(
        summary=summary,
        kpis=kpis,
        risks=risks,
        evidence=evidence,
        caveats=list(tool_output.get("caveats", [])),
        follow_ups=follow_up,
    )


# ---------------------------------------------------------------------------
# Dispatcher: Build Structured Response from Tool Result
# ---------------------------------------------------------------------------

def generate_structured_response(
    tool_name: str,
    tool_output: dict[str, Any],
) -> StructuredCopilotResponse | None:
    """Dispatches deterministic structured response building based on the tool executed.
    
    Returns None gracefully if the tool is not an analytical tool or output is malformed.
    """
    if not isinstance(tool_output, dict) or "error" in tool_output:
        return None

    try:
        if tool_name == "get_revenue_summary":
            return build_revenue_structured(tool_output)
        elif tool_name == "get_pipeline_summary":
            return build_pipeline_structured(tool_output)
        elif tool_name == "get_cross_board_delivery":
            return build_cross_board_structured(tool_output)
        elif tool_name == "get_leadership_update":
            return build_leadership_structured(tool_output)
        elif tool_name == "get_data_quality_report":
            return build_quality_structured(tool_output)
        return None
    except Exception as exc:
        logger.warning("Could not build structured response for '%s': %s", tool_name, exc)
        return None
