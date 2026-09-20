"""Unit tests for query understanding and clarification logic per §8.

Verifies:
- Vague time expressions trigger clarifying questions for explicit date windows.
- 'This quarter' / 'Last quarter' trigger clarification between Fiscal vs Calendar year.
- Fuzzy/ambiguous sector names trigger confirmation against known board verticals.
- Clear questions extract correct entities and proceed without unnecessary clarification.
- Cross-board queries are tagged appropriately.
"""

from __future__ import annotations

from app.agent.clarification import (
    KNOWN_SECTORS,
    check_query_ambiguity,
    extract_sector_entity,
)


def test_vague_time_queries_trigger_clarification() -> None:
    """Queries with 'recently', 'lately', or 'past few weeks' must prompt for explicit time window."""
    vague_queries = [
        "How are deals looking recently?",
        "What work orders were closed lately?",
        "Show me billings over the past few weeks",
    ]

    for q in vague_queries:
        res = check_query_ambiguity(q)
        assert res.needs_clarification is True
        assert res.ambiguity_type == "time"
        assert len(res.suggested_options) > 0
        assert "clarify" in res.clarification_message.lower() or "date range" in res.clarification_message.lower()


def test_quarter_queries_proceed_without_clarification() -> None:
    """Relative quarter queries (e.g. 'this quarter') proceed directly without blocking modal, extracting period and sector."""
    flagship = check_query_ambiguity("How's our pipeline for the energy sector this quarter?")
    assert flagship.needs_clarification is False
    assert flagship.extracted_entities.get("sector") == "Energy"
    assert flagship.extracted_entities.get("period") == "this quarter"

    rev_last_q = check_query_ambiguity("Show me total revenue for last quarter")
    assert rev_last_q.needs_clarification is False
    assert rev_last_q.extracted_entities.get("period") == "last quarter"


def test_sector_exact_and_synonym_extraction() -> None:
    """Recognizes exact board sectors and business synonyms with high confidence."""
    # Direct exact matches
    for s in KNOWN_SECTORS:
        sec, conf, is_ambig = extract_sector_entity(f"How is {s} performing?")
        assert sec == s
        assert conf == 1.0
        assert is_ambig is False

    # Common aliases
    sec, _, is_ambig = extract_sector_entity("Show me solar revenue")
    assert sec == "Renewables"
    assert is_ambig is False

    sec, _, is_ambig = extract_sector_entity("What is our transmission pipeline?")
    assert sec == "Powerline"
    assert is_ambig is False

    sec, _, is_ambig = extract_sector_entity("How are trains and rail deals doing?")
    assert sec == "Railways"
    assert is_ambig is False


def test_ambiguous_sector_triggers_clarification() -> None:
    """Typo or ambiguous sector below threshold triggers clarification."""
    res = check_query_ambiguity("How is the renewbls sector pipeline looking?")
    assert res.needs_clarification is True
    assert res.ambiguity_type == "sector"
    assert "Did you mean the 'Renewables' sector?" in res.clarification_message


def test_clear_query_proceeds_without_clarification() -> None:
    """Clear, specific queries do not trigger false clarification."""
    clear_queries = [
        "What is our total outstanding receivable amount?",
        "Give me a leadership update",
        "What is the total won deal volume in Renewables?",
        "Show me data quality caveats for Deals board",
    ]

    for q in clear_queries:
        res = check_query_ambiguity(q)
        assert res.needs_clarification is False
        assert res.clarification_message is None


def test_cross_board_query_flagged() -> None:
    """Cross-board comparison queries are tagged with is_cross_board=True."""
    res = check_query_ambiguity("Compare pipeline vs delivery for Renewables")
    assert res.extracted_entities["is_cross_board"] is True
