#!/usr/bin/env python3
"""Offline Deal-to-Work-Order Matching Script.

Generates a deterministic mapping between Work Orders and Deals using multi-feature resolution:
- Deal Name (exact case-insensitive match)
- Normalized Customer/Client Code (WOCOMPANY_xxx -> COMPANYxxx)
- Sector alignment
- Personnel alignment (BD/KAM Personnel code vs Owner code)
- Deal Status and Stage (Won / Work Order Received priority)
- Date proximity (Work Order Date of PO/LOI vs Deal Close Date (A) or Created Date)

Assigns every Work Order to one of three confidence tiers:
- MATCHED_HIGH
- MATCHED_FUZZY
- UNMATCHED

Outputs a mapping CSV to be used during Monday.com board setup to populate
a native "Connect Boards" relation column.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np


def normalize_client_code(cust_code: Any) -> Optional[str]:
    """Normalizes WO customer code to standard deal client code format."""
    if cust_code is None or pd.isna(cust_code):
        return None
    s = str(cust_code).strip()
    return s.replace("WOCOMPANY_", "COMPANY").replace("WOCOMPANY", "COMPANY")


def load_and_preprocess_boards(
    wo_path: Path | str, deals_path: Path | str
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Loads and preprocesses both source boards."""
    # Work Orders: Excel Row 1 is empty, Row 2 is headers -> header=1
    wo_df = pd.read_excel(wo_path, header=1)
    
    # Deals: Excel Row 1 is headers. Filter out duplicate header rows (e.g. row 50, 179)
    deals_df = pd.read_excel(deals_path)
    deals_df = deals_df[deals_df["Deal Status"] != "Deal Status"].copy()
    deals_df = deals_df.reset_index(drop=True)
    deals_df["deal_row_id"] = deals_df.index + 1  # 1-indexed logical record ID

    return wo_df, deals_df


def score_candidate(wo_row: pd.Series, deal_row: pd.Series) -> Tuple[float, List[str]]:
    """Calculates match score and rationale between a Work Order and a Deal candidate."""
    score = 0.0
    reasons: List[str] = []

    w_name = str(wo_row["Deal name masked"]).strip().lower() if pd.notna(wo_row["Deal name masked"]) else ""
    d_name = str(deal_row["Deal Name"]).strip().lower() if pd.notna(deal_row["Deal Name"]) else ""

    w_client = normalize_client_code(wo_row.get("Customer Name Code"))
    d_client = str(deal_row["Client Code"]).strip() if pd.notna(deal_row["Client Code"]) else ""

    w_sector = str(wo_row["Sector"]).strip().lower() if pd.notna(wo_row["Sector"]) else ""
    d_sector = str(deal_row["Sector/service"]).strip().lower() if pd.notna(deal_row["Sector/service"]) else ""

    w_owner = str(wo_row["BD/KAM Personnel code"]).strip() if pd.notna(wo_row["BD/KAM Personnel code"]) else ""
    d_owner = str(deal_row["Owner code"]).strip() if pd.notna(deal_row["Owner code"]) else ""

    d_status = str(deal_row["Deal Status"]).strip() if pd.notna(deal_row["Deal Status"]) else ""
    d_stage = str(deal_row["Deal Stage"]).strip() if pd.notna(deal_row["Deal Stage"]) else ""

    # 1. Deal Name
    if w_name and d_name and w_name == d_name:
        score += 35.0
        reasons.append("Exact Deal Name")
    elif not w_name:
        return 0.0, ["Missing WO Deal Name"]

    # 2. Client Code
    if w_client and d_client and w_client == d_client:
        score += 40.0
        reasons.append("Exact Client Code")

    # 3. Sector
    if w_sector and d_sector:
        if w_sector == d_sector:
            score += 25.0
            reasons.append("Matching Sector")
        elif d_sector in ["tender", "dsp", "others"]:
            score += 10.0
            reasons.append(f"Related Sector ({d_sector})")
        else:
            score -= 30.0
            reasons.append("Conflicting Sector")

    # 4. Personnel / Owner
    if w_owner and d_owner and w_owner == d_owner:
        score += 20.0
        reasons.append("Matching Owner")

    # 5. Status & Stage
    if d_status == "Won":
        score += 20.0
        reasons.append("Status: Won")
    elif any(term in d_stage.lower() for term in ["work order received", "project won", "project completed"]):
        score += 15.0
        reasons.append(f"Won Stage ({d_stage})")
    elif d_status == "Open":
        score += 5.0
        reasons.append("Status: Open")
    elif d_status == "Dead":
        score -= 35.0
        reasons.append("Dead Deal Status")

    # 6. Date Proximity (PO date vs close/created date)
    w_po_date = pd.to_datetime(wo_row["Date of PO/LOI"]) if pd.notna(wo_row["Date of PO/LOI"]) else None
    d_close = pd.to_datetime(deal_row["Close Date (A)"]) if pd.notna(deal_row["Close Date (A)"]) else None
    d_created = pd.to_datetime(deal_row["Created Date"]) if pd.notna(deal_row["Created Date"]) else None

    ref_date = d_close if d_close is not None else d_created
    if w_po_date is not None and ref_date is not None:
        diff_days = abs((w_po_date - ref_date).days)
        if diff_days <= 30:
            score += 25.0
            reasons.append(f"Date within {diff_days}d")
        elif diff_days <= 60:
            score += 18.0
            reasons.append(f"Date within {diff_days}d")
        elif diff_days <= 120:
            score += 10.0
            reasons.append(f"Date within {diff_days}d")
        elif diff_days <= 180:
            score += 5.0
            reasons.append(f"Date within {diff_days}d")
        elif diff_days > 365:
            score -= 20.0
            reasons.append(f"Date distant ({diff_days}d)")

    return score, reasons


def match_work_order_to_deals(
    wo_row: pd.Series, deals_df: pd.DataFrame
) -> Dict[str, Any]:
    """Finds the best matching deal for a single work order."""
    w_serial = str(wo_row["Serial #"]).strip()
    w_name = str(wo_row["Deal name masked"]).strip() if pd.notna(wo_row["Deal name masked"]) else ""
    w_cust = str(wo_row["Customer Name Code"]).strip() if pd.notna(wo_row["Customer Name Code"]) else ""
    w_client = normalize_client_code(w_cust)
    w_sector = str(wo_row["Sector"]).strip() if pd.notna(wo_row["Sector"]) else ""
    w_owner = str(wo_row["BD/KAM Personnel code"]).strip() if pd.notna(wo_row["BD/KAM Personnel code"]) else ""
    w_po_date = str(wo_row["Date of PO/LOI"])[:10] if pd.notna(wo_row["Date of PO/LOI"]) else ""

    base_record: Dict[str, Any] = {
        "wo_serial": w_serial,
        "wo_deal_name": w_name,
        "wo_customer_code": w_cust,
        "wo_normalized_client": w_client,
        "wo_sector": w_sector,
        "wo_owner": w_owner,
        "wo_po_date": w_po_date,
        "matched_deal_row_id": None,
        "matched_deal_name": None,
        "matched_client_code": None,
        "matched_deal_sector": None,
        "matched_deal_owner": None,
        "matched_deal_status": None,
        "matched_deal_date": None,
        "confidence_tier": "UNMATCHED",
        "match_score": 0.0,
        "match_notes": "",
    }

    if not w_name or w_name.lower() in ["nan", "none", ""]:
        base_record["match_notes"] = "Work Order missing deal name"
        return base_record

    candidates = deals_df[deals_df["Deal Name"].astype(str).str.lower() == w_name.lower()]
    if len(candidates) == 0:
        base_record["match_notes"] = f"Deal name '{w_name}' does not exist in Deals board"
        return base_record

    scored_cands: List[Tuple[float, pd.Series, List[str]]] = []
    for _, deal in candidates.iterrows():
        s, r = score_candidate(wo_row, deal)
        scored_cands.append((s, deal, r))

    scored_cands.sort(key=lambda x: x[0], reverse=True)
    best_score, best_deal, best_reasons = scored_cands[0]
    runner_up_score = scored_cands[1][0] if len(scored_cands) > 1 else -999.0
    margin = best_score - runner_up_score

    # Check for Exact Client Code Match
    d_client = str(best_deal["Client Code"]).strip() if pd.notna(best_deal["Client Code"]) else ""
    has_exact_client = bool(w_client and d_client and w_client == d_client)

    # Determine confidence tier
    tier = "UNMATCHED"
    note = ""

    if has_exact_client and best_score >= 70.0:
        tier = "MATCHED_HIGH"
        note = f"Exact Deal Name & Client Code match ({best_score:.0f} pts): {'; '.join(best_reasons)}"
    elif best_score >= 85.0 and margin >= 20.0:
        tier = "MATCHED_HIGH"
        note = f"High confidence composite match ({best_score:.0f} pts, margin {margin:.0f}): {'; '.join(best_reasons)}"
    elif best_score >= 60.0 and (len(candidates) == 1 or margin >= 15.0):
        tier = "MATCHED_FUZZY"
        note = f"Fuzzy composite match ({best_score:.0f} pts, margin {margin:.0f}): {'; '.join(best_reasons)}"
    elif best_score >= 50.0 and len(candidates) == 1 and best_deal["Deal Status"] == "Won":
        tier = "MATCHED_FUZZY"
        note = f"Fuzzy unique won match ({best_score:.0f} pts): {'; '.join(best_reasons)}"
    else:
        tier = "UNMATCHED"
        if best_score < 40.0:
            note = f"Below confidence threshold (best score {best_score:.0f}): {'; '.join(best_reasons)}"
        else:
            note = f"Ambiguous multiple candidates (best score {best_score:.0f}, runner-up {runner_up_score:.0f}, margin {margin:.0f})"

    base_record["confidence_tier"] = tier
    base_record["match_score"] = best_score
    base_record["match_notes"] = note

    if tier != "UNMATCHED":
        base_record["matched_deal_row_id"] = int(best_deal["deal_row_id"])
        base_record["matched_deal_name"] = best_deal["Deal Name"]
        base_record["matched_client_code"] = best_deal["Client Code"]
        base_record["matched_deal_sector"] = best_deal["Sector/service"]
        base_record["matched_deal_owner"] = best_deal["Owner code"]
        base_record["matched_deal_status"] = best_deal["Deal Status"]
        deal_date = best_deal["Close Date (A)"] if pd.notna(best_deal["Close Date (A)"]) else best_deal["Created Date"]
        base_record["matched_deal_date"] = str(deal_date)[:10] if pd.notna(deal_date) else ""

    return base_record


def build_deal_links(
    wo_path: Path | str, deals_path: Path | str, output_csv: Path | str
) -> pd.DataFrame:
    """Executes matching across all work orders and writes results to CSV."""
    wo_df, deals_df = load_and_preprocess_boards(wo_path, deals_path)
    records = [match_work_order_to_deals(row, deals_df) for _, row in wo_df.iterrows()]
    res_df = pd.DataFrame(records)
    
    # Save CSV
    out_path = Path(output_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    res_df.to_csv(out_path, index=False)
    return res_df


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    wo_file = base_dir / "Work_Order_Tracker Data.xlsx"
    deals_file = base_dir / "Deal funnel Data.xlsx"
    out_file = base_dir / "scripts" / "deal_wo_links.csv"

    print(f"Loading Work Orders: {wo_file}")
    print(f"Loading Deals: {deals_file}")
    links_df = build_deal_links(wo_file, deals_file, out_file)
    print(f"Successfully generated mapping file: {out_file}")
    print("\nConfidence Tier Summary:")
    print(links_df["confidence_tier"].value_counts())
