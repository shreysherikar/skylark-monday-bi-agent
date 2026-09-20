"""Deterministic query understanding and ambiguity clarification decision tree.

Implements explicit decision tree logic per §8 of PROJECT_PLAN.md:
1. Entity & Intent Extraction (Sectors, Timeframes, Deal Stages, Cross-board joins).
2. Ambiguity Checks:
   - Unspecified or vague time periods ("recently", "lately", "these past months").
   - Near-boundary relative time periods ("this quarter", "last quarter") prompting for fiscal/calendar definition.
   - Sector name ambiguity (fuzzy match below confidence threshold or unmapped industry vertical).
   - Cross-board join disclosures.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any

from app.data.date_resolver import get_current_ist_date, get_indian_fy_for_date

KNOWN_SECTORS: list[str] = [
    "Renewables",
    "Powerline",
    "Energy",
    "Mining",
    "Railways",
    "Tender",
    "DSP",
    "Others",
]

# Common aliases and synonyms mapping to standard board sectors
SECTOR_SYNONYMS: dict[str, str] = {
    "renewables": "Renewables",
    "renewable": "Renewables",
    "solar": "Renewables",
    "wind": "Renewables",
    "energy": "Energy",
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
    "others": "Others",
    "other": "Others",
}

VAGUE_TIME_PATTERNS: list[re.Pattern] = [
    re.compile(r"\brecently\b", re.IGNORECASE),
    re.compile(r"\blately\b", re.IGNORECASE),
    re.compile(r"\bpast few (?:days|weeks|months)\b", re.IGNORECASE),
    re.compile(r"\bover time\b", re.IGNORECASE),
]

QUARTER_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bthis quarter\b", re.IGNORECASE),
    re.compile(r"\blast quarter\b", re.IGNORECASE),
    re.compile(r"\bnext quarter\b", re.IGNORECASE),
    re.compile(r"\bcurrent quarter\b", re.IGNORECASE),
]


@dataclass
class ClarificationResult:
    """Result of ambiguity analysis on a user query."""
    needs_clarification: bool
    clarification_message: str | None = None
    suggested_options: list[str] = field(default_factory=list)
    ambiguity_type: str | None = None  # 'time', 'sector', 'stage', or None
    extracted_entities: dict[str, Any] = field(default_factory=dict)


COMMON_BUSINESS_TERMS = {
    "receivable", "receivables", "revenue", "pipeline", "collection",
    "collections", "order", "orders", "billed", "unbilled", "tracker",
    "status", "deal", "deals", "update", "summary", "total",
    "amount", "health", "metrics", "work", "looking", "doing", "perform",
}


def extract_sector_entity(query: str) -> tuple[str | None, float | None, bool]:
    """Extracts sector from query with confidence score.
    
    Returns:
        (resolved_sector, confidence, is_ambiguous)
    """
    q_lower = query.lower()

    # 1. Exact match against known sectors or direct synonyms
    for term, mapped in SECTOR_SYNONYMS.items():
        pattern = r"\b" + re.escape(term) + r"\b"
        if re.search(pattern, q_lower):
            return mapped, 1.0, False

    # 2. Look for sector typos (ignoring common business vocabulary)
    words = re.findall(r"\b[a-zA-Z]{4,}\b", q_lower)
    best_match: str | None = None
    best_score = 0.0

    for word in words:
        if word in COMMON_BUSINESS_TERMS:
            continue
        for known in KNOWN_SECTORS:
            ratio = difflib.SequenceMatcher(None, word, known.lower()).ratio()
            if ratio > best_score:
                best_score = ratio
                best_match = known

    if best_match and best_score >= 0.75:
        # Typo or close candidate below exact match -> requires clarification
        return best_match, best_score, True

    return None, 0.0, False


def check_query_ambiguity(query: str) -> ClarificationResult:
    """Evaluates query through the ambiguity decision tree per §8.
    
    Rules:
    1. Vague timeframes ('recently', 'lately') require clarification of the specific date window.
    2. 'This quarter' / 'Last quarter' triggers clarification regarding Fiscal Year (e.g. Q4 FY25-26) vs Calendar Year.
    3. Ambiguous sector names or typos trigger confirmation against known board verticals.
    4. Cross-board queries are tagged so match coverage can be surfaced.
    """
    cleaned = query.strip()
    entities: dict[str, Any] = {}

    # Check cross-board intent
    is_cross_board = any(
        phrase in cleaned.lower()
        for phrase in [
            "pipeline vs delivery",
            "pipeline vs execution",
            "pipeline versus delivery",
            "cross-board",
            "delivery vs pipeline",
            "fulfillment vs pipeline",
            "deals and work orders",
        ]
    )
    entities["is_cross_board"] = is_cross_board

    # 1. Check for vague relative timeframes
    for pattern in VAGUE_TIME_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            vague_phrase = match.group(0)
            cur_d = get_current_ist_date()
            cur_fy, cur_q, _, _ = get_indian_fy_for_date(cur_d)
            return ClarificationResult(
                needs_clarification=True,
                ambiguity_type="time",
                clarification_message=(
                    f"You mentioned '{vague_phrase}'. To provide precise figures, could you clarify the date range? "
                    "For example: last 30 days, last 90 days, or full fiscal year?"
                ),
                suggested_options=["Last 30 days", "Last 90 days", f"Current {cur_fy} Q{cur_q}", f"Full {cur_fy}", "All time"],
                extracted_entities=entities,
            )

    # 2. Extract quarter timeframe (defaults deterministically to Indian FY in IST without blocking modal)
    for pattern in QUARTER_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            entities["period"] = match.group(0).lower()
            break

    # 3. Check for sector mentions and ambiguity
    sector, _conf, is_ambiguous = extract_sector_entity(cleaned)
    if sector:
        entities["sector"] = sector
        if is_ambiguous:
            return ClarificationResult(
                needs_clarification=True,
                ambiguity_type="sector",
                clarification_message=(
                    f"Did you mean the '{sector}' sector? The system tracks: "
                    f"{', '.join(KNOWN_SECTORS)}."
                ),
                suggested_options=[sector, "Renewables", "Powerline", "Energy", "Mining", "Railways", "All Sectors"],
                extracted_entities=entities,
            )

    # No clarification needed — query is specific or general enough to proceed
    return ClarificationResult(
        needs_clarification=False,
        extracted_entities=entities,
    )
