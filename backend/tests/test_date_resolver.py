"""Unit tests for deterministic Indian Fiscal Year date resolver."""

from __future__ import annotations

import datetime

from app.data.date_resolver import (
    get_indian_fy_for_date,
    resolve_date_range,
)


def test_indian_fy_quarter_calculation() -> None:
    # September 20, 2026 -> Q2 FY26-27
    fy, q, s, e = get_indian_fy_for_date(datetime.date(2026, 9, 20))
    assert fy == "FY26-27"
    assert q == 2
    assert s == datetime.date(2026, 7, 1)
    assert e == datetime.date(2026, 9, 30)

    # May 15, 2026 -> Q1 FY26-27
    fy, q, s, e = get_indian_fy_for_date(datetime.date(2026, 5, 15))
    assert fy == "FY26-27"
    assert q == 1
    assert s == datetime.date(2026, 4, 1)
    assert e == datetime.date(2026, 6, 30)

    # November 10, 2025 -> Q3 FY25-26
    fy, q, s, e = get_indian_fy_for_date(datetime.date(2025, 11, 10))
    assert fy == "FY25-26"
    assert q == 3
    assert s == datetime.date(2025, 10, 1)
    assert e == datetime.date(2025, 12, 31)

    # January 15, 2026 (Jan-Mar rollover) -> Q4 FY25-26
    fy, q, s, e = get_indian_fy_for_date(datetime.date(2026, 1, 15))
    assert fy == "FY25-26"
    assert q == 4
    assert s == datetime.date(2026, 1, 1)
    assert e == datetime.date(2026, 3, 31)


def test_resolve_this_quarter_current_date() -> None:
    ref = datetime.date(2026, 9, 20)
    res = resolve_date_range("this quarter", reference_date=ref)
    assert res.start_date == datetime.date(2026, 7, 1)
    assert res.end_date == datetime.date(2026, 9, 30)
    assert res.period_label == "Q2 FY26-27"
    assert res.is_all_time is False
    assert "Indian Fiscal Year Q2 FY26-27" in res.assumption_note


def test_resolve_last_quarter() -> None:
    # From Sept 20, 2026 (Q2 FY26-27), last quarter is Q1 FY26-27 (Apr-Jun 2026)
    ref = datetime.date(2026, 9, 20)
    res = resolve_date_range("last quarter", reference_date=ref)
    assert res.start_date == datetime.date(2026, 4, 1)
    assert res.end_date == datetime.date(2026, 6, 30)
    assert res.period_label == "Q1 FY26-27"

    # From May 10, 2026 (Q1 FY26-27), last quarter is Q4 FY25-26 (Jan-Mar 2026)
    ref_may = datetime.date(2026, 5, 10)
    res_may = resolve_date_range("last quarter", reference_date=ref_may)
    assert res_may.start_date == datetime.date(2026, 1, 1)
    assert res_may.end_date == datetime.date(2026, 3, 31)
    assert res_may.period_label == "Q4 FY25-26"


def test_resolve_explicit_fy_quarter() -> None:
    res = resolve_date_range("Q4 FY25-26")
    assert res.start_date == datetime.date(2026, 1, 1)
    assert res.end_date == datetime.date(2026, 3, 31)
    assert res.period_label == "Q4 FY25-26"

    res_q1 = resolve_date_range("FY25-26 Q1")
    assert res_q1.start_date == datetime.date(2025, 4, 1)
    assert res_q1.end_date == datetime.date(2025, 6, 30)


def test_resolve_bare_quarter() -> None:
    ref = datetime.date(2026, 9, 20)  # Q2 FY26-27
    # Bare Q4 -> most recent Q4 was in FY25-26 (Jan-Mar 2026)
    res_q4 = resolve_date_range("Q4", reference_date=ref)
    assert res_q4.start_date == datetime.date(2026, 1, 1)
    assert res_q4.end_date == datetime.date(2026, 3, 31)
    assert res_q4.period_label == "Q4 FY25-26"

    # Bare Q1 -> in current FY26-27 (Apr-Jun 2026)
    res_q1 = resolve_date_range("Q1", reference_date=ref)
    assert res_q1.start_date == datetime.date(2026, 4, 1)
    assert res_q1.end_date == datetime.date(2026, 6, 30)
    assert res_q1.period_label == "Q1 FY26-27"


def test_resolve_bare_month() -> None:
    ref = datetime.date(2026, 9, 20)
    # Bare "July" on Sept 2026 -> July 2026
    res_jul = resolve_date_range("July", reference_date=ref)
    assert res_jul.start_date == datetime.date(2026, 7, 1)
    assert res_jul.end_date == datetime.date(2026, 7, 31)

    # Bare "December" on Sept 2026 -> Dec 2025 (most recent occurrence)
    res_dec = resolve_date_range("December", reference_date=ref)
    assert res_dec.start_date == datetime.date(2025, 12, 1)
    assert res_dec.end_date == datetime.date(2025, 12, 31)


def test_resolve_full_fy() -> None:
    res = resolve_date_range("FY25-26")
    assert res.start_date == datetime.date(2025, 4, 1)
    assert res.end_date == datetime.date(2026, 3, 31)
    assert res.period_label == "FY25-26"


def test_resolve_all_time_and_none() -> None:
    res_none = resolve_date_range(None)
    assert res_none.is_all_time is True
    assert res_none.start_date is None
    assert res_none.end_date is None

    res_all = resolve_date_range("All-Time")
    assert res_all.is_all_time is True
    assert res_all.start_date is None
