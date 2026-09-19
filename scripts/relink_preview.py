#!/usr/bin/env python3
"""Read-only preview script comparing current Monday.com links vs proposed Deal item IDs.

STRICTLY READ-ONLY:
- Does NOT execute any GraphQL mutations.
- Queries current Work Order items and their 'Linked Deal' relation column.
- Queries Deals board items to map deal_row_id to Monday Deal item IDs.
- Compares current links against proposed links from scripts/deal_wo_links.csv.
- Specifically highlights Sakura and Timon resolutions.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
import requests
from dotenv import load_dotenv

# Load environment
base_dir = Path(__file__).resolve().parent.parent
load_dotenv(base_dir / ".env")

API_TOKEN = os.getenv("MONDAY_API_TOKEN")
WO_BOARD_ID = os.getenv("MONDAY_WORK_ORDERS_BOARD_ID")
DEALS_BOARD_ID = os.getenv("MONDAY_DEALS_BOARD_ID")

if not API_TOKEN or not WO_BOARD_ID or not DEALS_BOARD_ID:
    print("Error: Missing MONDAY_API_TOKEN, MONDAY_WORK_ORDERS_BOARD_ID, or MONDAY_DEALS_BOARD_ID in .env")
    sys.exit(1)

HEADERS = {
    "Authorization": API_TOKEN,
    "API-Version": "2024-10",
    "Content-Type": "application/json",
}
API_URL = "https://api.monday.com/v2"


def run_query(query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Executes a read-only GraphQL query against Monday.com."""
    # Strict safety check: block any mutation attempt
    if "mutation" in query.lower():
        raise ValueError("Mutations are strictly forbidden in relink_preview.py")
    
    resp = requests.post(
        API_URL,
        json={"query": query, "variables": variables or {}},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "errors" in payload:
        raise RuntimeError(f"GraphQL error: {payload['errors']}")
    return payload.get("data", {})


def fetch_all_deals() -> List[Dict[str, Any]]:
    """Fetches all Deal board items in order to map 1-indexed row IDs to Deal item IDs."""
    query = """
    query GetAllDeals($boardId: [ID!], $cursor: String) {
        boards(ids: $boardId) {
            items_page(limit: 100, cursor: $cursor) {
                cursor
                items {
                    id
                    name
                    column_values {
                        id
                        text
                    }
                }
            }
        }
    }
    """
    items: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    while True:
        data = run_query(query, {"boardId": [DEALS_BOARD_ID], "cursor": cursor})
        page = data["boards"][0]["items_page"]
        items.extend(page["items"])
        cursor = page.get("cursor")
        if not cursor or len(page["items"]) == 0:
            break
    return items


def fetch_all_work_orders() -> List[Dict[str, Any]]:
    """Fetches all Work Orders items along with Serial # and Linked Deal relations."""
    query = """
    query GetAllWO($boardId: [ID!], $cursor: String) {
        boards(ids: $boardId) {
            items_page(limit: 100, cursor: $cursor) {
                cursor
                items {
                    id
                    name
                    column_values {
                        id
                        type
                        text
                        ... on BoardRelationValue {
                            linked_item_ids
                        }
                    }
                }
            }
        }
    }
    """
    items: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    while True:
        data = run_query(query, {"boardId": [WO_BOARD_ID], "cursor": cursor})
        page = data["boards"][0]["items_page"]
        items.extend(page["items"])
        cursor = page.get("cursor")
        if not cursor or len(page["items"]) == 0:
            break
    return items


def main() -> None:
    print("=" * 80)
    print("MONDAY WORK ORDERS <-> DEALS RELINK PREVIEW (STRICTLY READ-ONLY)")
    print("=" * 80)

    # 1. Load CSV links
    csv_path = base_dir / "scripts" / "deal_wo_links.csv"
    if not csv_path.exists():
        print(f"Error: {csv_path} not found. Run scripts/build_deal_links.py first.")
        sys.exit(1)

    links_df = pd.read_csv(csv_path, keep_default_na=False)
    print(f"\nLoaded {len(links_df)} rows from {csv_path.name}")
    tier_counts = links_df["confidence_tier"].value_counts().to_dict()
    print(f"  Confidence tiers: MATCHED_HIGH: {tier_counts.get('MATCHED_HIGH', 0)}, "
          f"MATCHED_FUZZY: {tier_counts.get('MATCHED_FUZZY', 0)}, "
          f"UNMATCHED: {tier_counts.get('UNMATCHED', 0)}")

    # 2. Fetch Deals from Monday
    print(f"\nFetching Deals from board {DEALS_BOARD_ID}...")
    deal_items = fetch_all_deals()
    print(f"  Fetched {len(deal_items)} deals from live Monday board")
    # deal_row_id is 1-indexed matching the 344 clean items sequentially
    deal_row_to_item: Dict[int, Dict[str, Any]] = {
        i + 1: item for i, item in enumerate(deal_items)
    }
    deal_item_by_id: Dict[str, Dict[str, Any]] = {
        str(item["id"]): item for item in deal_items
    }

    # 3. Fetch Work Orders from Monday
    print(f"\nFetching Work Orders from board {WO_BOARD_ID}...")
    wo_items = fetch_all_work_orders()
    print(f"  Fetched {len(wo_items)} work orders from live Monday board")

    # Map serial to Monday WO item
    wo_by_serial: Dict[str, Dict[str, Any]] = {}
    for it in wo_items:
        serial = None
        linked_ids: List[str] = []
        for cv in it.get("column_values", []):
            if cv.get("id") == "text_mm7bd0x2":  # Serial # column
                serial = cv.get("text", "").strip()
            if cv.get("type") == "board_relation":
                linked_ids = [str(x) for x in cv.get("linked_item_ids", [])]
        if serial:
            wo_by_serial[serial] = {
                "item_id": it["id"],
                "name": it["name"],
                "current_linked_ids": linked_ids,
            }

    # 4. Compare current vs proposed links
    preview_rows: List[Dict[str, Any]] = []

    for _, row in links_df.iterrows():
        serial = row["wo_serial"]
        wo_name = row["wo_deal_name"]
        tier = row["confidence_tier"]
        row_id_val = row["matched_deal_row_id"]

        current_info = wo_by_serial.get(serial, {})
        current_linked_ids = current_info.get("current_linked_ids", [])
        current_id_str = current_linked_ids[0] if current_linked_ids else None
        current_deal_name = None
        if current_id_str and current_id_str in deal_item_by_id:
            current_deal_name = deal_item_by_id[current_id_str]["name"]

        proposed_id_str = None
        proposed_deal_name = None
        if tier != "UNMATCHED" and row_id_val != "" and pd.notna(row_id_val):
            row_id = int(float(row_id_val))
            deal_item = deal_row_to_item.get(row_id)
            if deal_item:
                proposed_id_str = str(deal_item["id"])
                proposed_deal_name = deal_item["name"]

        # Classification of action
        if not current_id_str and not proposed_id_str:
            action = "STAYS_UNLINKED"
        elif not current_id_str and proposed_id_str:
            action = "NEW_LINK"
        elif current_id_str and not proposed_id_str:
            action = "UNLINK"
        elif current_id_str == proposed_id_str:
            action = "UNCHANGED"
        else:
            action = "CHANGED_LINK"

        preview_rows.append({
            "serial": serial,
            "wo_name": wo_name,
            "tier": tier,
            "current_id": current_id_str,
            "current_name": current_deal_name,
            "proposed_id": proposed_id_str,
            "proposed_name": proposed_deal_name,
            "action": action,
            "score": row["match_score"],
            "notes": row["match_notes"],
        })

    preview_df = pd.DataFrame(preview_rows)

    # 5. Print Summary Statistics
    action_counts = preview_df["action"].value_counts().to_dict()
    print("\n" + "=" * 80)
    print("SUMMARY OF LINK ACTIONS")
    print("=" * 80)
    print(f"  Total Work Orders:          {len(preview_df)}")
    print(f"  Currently Linked on Monday: {sum(preview_df['current_id'].notna())}")
    print(f"  Proposed Linked (High+Fuzzy): {sum(preview_df['proposed_id'].notna())}")
    print(f"    - Unchanged Links:        {action_counts.get('UNCHANGED', 0)}")
    print(f"    - New Links:              {action_counts.get('NEW_LINK', 0)}")
    print(f"    - Changed Links:          {action_counts.get('CHANGED_LINK', 0)}")
    print(f"    - Unlinked (Ambiguous/NA):{action_counts.get('UNLINK', 0)}")
    print(f"    - Stays Unlinked:         {action_counts.get('STAYS_UNLINKED', 0)}")

    # 6. Detail of Changed Links
    changed = preview_df[preview_df["action"] == "CHANGED_LINK"]
    if len(changed) > 0:
        print("\n" + "=" * 80)
        print("CHANGED LINKS (Current Deal ID != Proposed Deal ID)")
        print("=" * 80)
        for _, r in changed.iterrows():
            print(f"  {r['serial']} ({r['wo_name']}):")
            print(f"    Current:  Item ID {r['current_id']} ('{r['current_name']}')")
            print(f"    Proposed: Item ID {r['proposed_id']} ('{r['proposed_name']}') [{r['tier']}]")
            print(f"    Reason:   {r['notes']}")

    # 7. Detail of New Links
    new_links = preview_df[preview_df["action"] == "NEW_LINK"]
    if len(new_links) > 0:
        print("\n" + "=" * 80)
        print(f"NEW LINKS ({len(new_links)} work orders newly linked)")
        print("=" * 80)
        for _, r in new_links.iterrows():
            print(f"  {r['serial']} ({r['wo_name']}) -> Proposed: Item ID {r['proposed_id']} ('{r['proposed_name']}') [{r['tier']}] ({r['score']} pts)")

    # 8. Detail of Unlinked (previously linked on Monday, now UNMATCHED)
    unlinks = preview_df[preview_df["action"] == "UNLINK"]
    if len(unlinks) > 0:
        print("\n" + "=" * 80)
        print(f"UNLINKED ({len(unlinks)} work orders to be unlinked due to ambiguous candidates)")
        print("=" * 80)
        for _, r in unlinks.iterrows():
            print(f"  {r['serial']} ({r['wo_name']}):")
            print(f"    Currently Linked to: Item ID {r['current_id']} ('{r['current_name']}')")
            print(f"    Proposed Action:     UNLINK [{r['tier']}]")
            print(f"    Reason:              {r['notes']}")

    # 9. Focus Inspection: Sakura and Timon
    print("\n" + "=" * 80)
    print("FOCUS INSPECTION: SAKURA & TIMON RESOLUTIONS")
    print("=" * 80)
    focus_serials = [
        "SDPLDEAL-149",  # Sakura
        "SDPLDEAL-050",  # Timon
        "SDPLDEAL-081",  # Timon
        "SDPLDEAL-082",  # Timon
        "SDPLDEAL-125",  # Timon
        "SDPLDEAL-159",  # Timon
        "SDPLDEAL-160",  # Timon
        "SDPLDEAL-186",  # Timon
    ]
    focus_df = preview_df[preview_df["serial"].isin(focus_serials)].sort_values("serial")
    print(f"{'Serial':<14} {'WO Name':<10} {'Tier':<14} {'Current Deal ID':<18} {'Proposed Deal ID':<18} {'Action':<14}")
    print("-" * 90)
    for _, r in focus_df.iterrows():
        c_id = str(r['current_id']) if r['current_id'] else "None"
        p_id = str(r['proposed_id']) if r['proposed_id'] else "None"
        print(f"{r['serial']:<14} {r['wo_name']:<10} {r['tier']:<14} {c_id:<18} {p_id:<18} {r['action']:<14}")

    print("\nConfirmation: STRICTLY READ-ONLY execution. Zero Monday mutations performed.")


if __name__ == "__main__":
    main()
