"""Unit tests for offline Work-Order-to-Deal matching logic.

Tests real rows from Work_Order_Tracker Data.xlsx and Deal funnel Data.xlsx
verifying that records land in the expected confidence tiers:
- MATCHED_HIGH
- MATCHED_FUZZY
- UNMATCHED
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

# Add repo root to sys.path to import scripts.build_deal_links
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

from scripts.build_deal_links import (
    load_and_preprocess_boards,
    match_work_order_to_deals,
    normalize_client_code,
)


@pytest.fixture(scope="module")
def loaded_boards() -> tuple[pd.DataFrame, pd.DataFrame]:
    wo_path = repo_root / "Work_Order_Tracker Data.xlsx"
    deals_path = repo_root / "Deal funnel Data.xlsx"
    return load_and_preprocess_boards(wo_path, deals_path)


def test_normalize_client_code() -> None:
    """Verifies that WO customer code prefixes are stripped cleanly for informational metadata."""
    assert normalize_client_code("WOCOMPANY_002") == "COMPANY002"
    assert normalize_client_code("WOCOMPANY_038") == "COMPANY038"
    assert normalize_client_code("COMPANY100") == "COMPANY100"
    assert normalize_client_code(None) is None


def test_matched_high_composite(loaded_boards: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """Verifies MATCHED_HIGH for records with strong multi-feature composite alignment and clear margin."""
    wo_df, deals_df = loaded_boards
    
    # SDPLDEAL-099 (Goku) - Exact name, matching sector (Railways), matching owner, status Open
    goku_row = wo_df[wo_df["Serial #"] == "SDPLDEAL-099"].iloc[0]
    res_goku = match_work_order_to_deals(goku_row, deals_df)
    assert res_goku["confidence_tier"] == "MATCHED_HIGH"
    assert res_goku["matched_deal_name"] == "Goku"

    # SDPLDEAL-109 (Rafiki) - Exact name, matching sector (Renewables), status Won
    rafiki_row = wo_df[wo_df["Serial #"] == "SDPLDEAL-109"].iloc[0]
    res_rafiki = match_work_order_to_deals(rafiki_row, deals_df)
    assert res_rafiki["confidence_tier"] == "MATCHED_HIGH"
    assert res_rafiki["matched_deal_name"] == "Rafiki"

    # SDPLDEAL-149 (Sakura) - Exact name, matching sector (Renewables), matching owner (OWNER_003), close date (19d)
    sakura_row = wo_df[wo_df["Serial #"] == "SDPLDEAL-149"].iloc[0]
    res_sakura = match_work_order_to_deals(sakura_row, deals_df)
    assert res_sakura["confidence_tier"] == "MATCHED_HIGH"
    assert res_sakura["matched_deal_name"] == "Sakura"
    assert res_sakura["matched_deal_row_id"] == 28

    # SDPLDEAL-050 (Timon) - Exact name, matching owner (OWNER_003), status Won
    timon_row = wo_df[wo_df["Serial #"] == "SDPLDEAL-050"].iloc[0]
    res_timon = match_work_order_to_deals(timon_row, deals_df)
    assert res_timon["confidence_tier"] == "MATCHED_HIGH"
    assert res_timon["matched_deal_name"] == "Timon"


def test_matched_fuzzy_records(loaded_boards: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """Verifies MATCHED_FUZZY for records with moderate composite scores or related sectors."""
    wo_df, deals_df = loaded_boards

    # SDPLDEAL-101 (Appa) - Related sector (Others), status Won
    appa_row = wo_df[wo_df["Serial #"] == "SDPLDEAL-101"].iloc[0]
    res_appa = match_work_order_to_deals(appa_row, deals_df)
    assert res_appa["confidence_tier"] == "MATCHED_FUZZY"
    assert res_appa["matched_deal_name"] == "Appa"

    # SDPLDEAL-004 (SpongeBob) - Fuzzy composite match
    sb_row = wo_df[wo_df["Serial #"] == "SDPLDEAL-004"].iloc[0]
    res_sb = match_work_order_to_deals(sb_row, deals_df)
    assert res_sb["confidence_tier"] == "MATCHED_FUZZY"
    assert res_sb["matched_deal_name"] == "SpongeBob"


def test_unmatched_missing_in_deals_board(loaded_boards: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """Verifies UNMATCHED for deal names that do not exist anywhere in Deals."""
    wo_df, deals_df = loaded_boards

    # SDPLDEAL-178 (Whale), SDPLDEAL-156 (Golden fish), SDPLDEAL-181 (Turtle), SDPLDEAL-150 (Dolphin)
    for serial in ["SDPLDEAL-178", "SDPLDEAL-156", "SDPLDEAL-181", "SDPLDEAL-150"]:
        row = wo_df[wo_df["Serial #"] == serial].iloc[0]
        result = match_work_order_to_deals(row, deals_df)
        assert result["confidence_tier"] == "UNMATCHED"
        assert "does not exist in Deals board" in result["match_notes"]
        assert result["matched_deal_row_id"] is None


def test_unmatched_conflicting_or_dead_deal(loaded_boards: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """Verifies UNMATCHED for records with Dead deal status and conflicting sectors."""
    wo_df, deals_df = loaded_boards

    # SDPLDEAL-005 (Edward Elric) - Renewables in WO, but Powerline + Dead in Deals
    edward_row = wo_df[wo_df["Serial #"] == "SDPLDEAL-005"].iloc[0]
    result = match_work_order_to_deals(edward_row, deals_df)
    assert result["confidence_tier"] == "UNMATCHED"
    assert "Below confidence threshold" in result["match_notes"]
    assert result["matched_deal_row_id"] is None


def test_unmatched_ambiguous_duplicates(loaded_boards: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """Verifies UNMATCHED for records where multiple candidates have tied or near-tied scores."""
    wo_df, deals_df = loaded_boards

    # SDPLDEAL-075 (Scooby-Doo) - two tied Scooby-Doo deals in Deals board
    scooby_row = wo_df[wo_df["Serial #"] == "SDPLDEAL-075"].iloc[0]
    result = match_work_order_to_deals(scooby_row, deals_df)
    assert result["confidence_tier"] == "UNMATCHED"
    assert "Ambiguous multiple candidates" in result["match_notes"]
    assert result["matched_deal_row_id"] is None


def test_overall_matching_counts(loaded_boards: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """Verifies that running matching across all 176 Work Orders yields exactly 176 results with no client code bias."""
    wo_df, deals_df = loaded_boards
    results = [match_work_order_to_deals(row, deals_df) for _, row in wo_df.iterrows()]
    res_df = pd.DataFrame(results)

    assert len(res_df) == 176
    counts = res_df["confidence_tier"].value_counts().to_dict()
    assert counts.get("MATCHED_HIGH") == 16
    assert counts.get("MATCHED_FUZZY") == 8
    assert counts.get("UNMATCHED") == 152
    assert sum(counts.values()) == 176
