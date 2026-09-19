"""Unit tests for offline Work-Order-to-Deal matching logic.

Tests real rows from Work_Order_Tracker Data.xlsx and Deal funnel Data.xlsx
verifying that records land in the expected confidence tiers:
- MATCHED_HIGH
- MATCHED_FUZZY
- UNMATCHED
"""

from pathlib import Path
import pytest
import pandas as pd
import sys

# Add repo root to sys.path to import scripts.build_deal_links
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root))

from scripts.build_deal_links import (
    load_and_preprocess_boards,
    match_work_order_to_deals,
    normalize_client_code,
    score_candidate,
)


@pytest.fixture(scope="module")
def loaded_boards() -> tuple[pd.DataFrame, pd.DataFrame]:
    wo_path = repo_root / "Work_Order_Tracker Data.xlsx"
    deals_path = repo_root / "Deal funnel Data.xlsx"
    return load_and_preprocess_boards(wo_path, deals_path)


def test_normalize_client_code() -> None:
    """Verifies that WO customer code prefixes are stripped cleanly."""
    assert normalize_client_code("WOCOMPANY_002") == "COMPANY002"
    assert normalize_client_code("WOCOMPANY_038") == "COMPANY038"
    assert normalize_client_code("COMPANY100") == "COMPANY100"
    assert normalize_client_code(None) is None


def test_matched_high_exact_identity(loaded_boards: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """Verifies MATCHED_HIGH for SDPLDEAL-101 (Appa) with exact client code match."""
    wo_df, deals_df = loaded_boards
    appa_row = wo_df[wo_df["Serial #"] == "SDPLDEAL-101"].iloc[0]
    result = match_work_order_to_deals(appa_row, deals_df)

    assert result["confidence_tier"] == "MATCHED_HIGH"
    assert result["wo_deal_name"] == "Appa"
    assert result["matched_client_code"] == "COMPANY038"
    assert result["matched_deal_name"] == "Appa"
    assert "Exact Deal Name & Client Code match" in result["match_notes"]


def test_matched_high_composite(loaded_boards: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """Verifies MATCHED_HIGH for records with strong composite alignment and clear margin."""
    wo_df, deals_df = loaded_boards
    
    # SDPLDEAL-099 (Goku)
    goku_row = wo_df[wo_df["Serial #"] == "SDPLDEAL-099"].iloc[0]
    res_goku = match_work_order_to_deals(goku_row, deals_df)
    assert res_goku["confidence_tier"] == "MATCHED_HIGH"
    assert res_goku["matched_deal_name"] == "Goku"

    # SDPLDEAL-109 (Rafiki)
    rafiki_row = wo_df[wo_df["Serial #"] == "SDPLDEAL-109"].iloc[0]
    res_rafiki = match_work_order_to_deals(rafiki_row, deals_df)
    assert res_rafiki["confidence_tier"] == "MATCHED_HIGH"
    assert res_rafiki["matched_deal_name"] == "Rafiki"


def test_matched_fuzzy_single_candidate(loaded_boards: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """Verifies MATCHED_FUZZY for records with single candidates or related sectors."""
    wo_df, deals_df = loaded_boards

    # SDPLDEAL-060 (Powerpuff Girls) - single candidate in sector with Won status
    ppg_row = wo_df[wo_df["Serial #"] == "SDPLDEAL-060"].iloc[0]
    result = match_work_order_to_deals(ppg_row, deals_df)
    assert result["confidence_tier"] == "MATCHED_FUZZY"
    assert result["matched_deal_name"] == "Powerpuff Girls"

    # SDPLDEAL-085 (Luffy) - single candidate with related sector (Tender)
    luffy_row = wo_df[wo_df["Serial #"] == "SDPLDEAL-085"].iloc[0]
    res_luffy = match_work_order_to_deals(luffy_row, deals_df)
    assert res_luffy["confidence_tier"] == "MATCHED_FUZZY"
    assert res_luffy["matched_deal_name"] == "Luffy"


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
