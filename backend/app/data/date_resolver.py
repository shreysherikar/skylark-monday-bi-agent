"""Deterministic business date-range resolver for Indian Fiscal Year and Calendar periods.

Resolves conversational time expressions ("this quarter", "last quarter", "Q4 FY25-26",
"this month", "FY25-26") into precise ISO date bounds (start_date, end_date) using Indian
Fiscal Year conventions (April 1 to March 31) in Indian Standard Time (IST, UTC+05:30).

No LLM date hallucination: all calendar calculations are performed deterministically.
"""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from typing import Any

# Indian Standard Time (UTC+05:30)
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def get_current_ist_date() -> datetime.date:
    """Returns today's date in Indian Standard Time."""
    return datetime.datetime.now(IST).date()


@dataclass(frozen=True)
class DateRangeResult:
    """Structured date boundary specification for analytics filters."""
    start_date: datetime.date | None
    end_date: datetime.date | None
    period_label: str
    fiscal_year: str | None
    quarter_number: int | None
    is_all_time: bool
    assumption_note: str

    def __getitem__(self, item: str) -> Any:
        try:
            return getattr(self, item)
        except AttributeError:
            raise KeyError(item) from None

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)


def get_indian_fy_for_date(dt: datetime.date) -> tuple[str, int, datetime.date, datetime.date]:
    """Returns (fiscal_year_str, quarter_num, quarter_start_date, quarter_end_date) for a given date.

    Indian Fiscal Year:
    - Q1: Apr 1 - Jun 30 (FY{y}-{y+1})
    - Q2: Jul 1 - Sep 30 (FY{y}-{y+1})
    - Q3: Oct 1 - Dec 31 (FY{y}-{y+1})
    - Q4: Jan 1 - Mar 31 (FY{y-1}-{y})
    """
    y = dt.year
    m = dt.month

    if m in (4, 5, 6):
        fy_str = f"FY{str(y)[-2:]}-{str(y + 1)[-2:]}"
        return fy_str, 1, datetime.date(y, 4, 1), datetime.date(y, 6, 30)
    elif m in (7, 8, 9):
        fy_str = f"FY{str(y)[-2:]}-{str(y + 1)[-2:]}"
        return fy_str, 2, datetime.date(y, 7, 1), datetime.date(y, 9, 30)
    elif m in (10, 11, 12):
        fy_str = f"FY{str(y)[-2:]}-{str(y + 1)[-2:]}"
        return fy_str, 3, datetime.date(y, 10, 1), datetime.date(y, 12, 31)
    else:  # m in (1, 2, 3)
        fy_str = f"FY{str(y - 1)[-2:]}-{str(y)[-2:]}"
        # Leap year check for March 31 / Feb 28-29
        return fy_str, 4, datetime.date(y, 1, 1), datetime.date(y, 3, 31)


def parse_explicit_fy_quarter(fy_str: str, q_num: int) -> tuple[datetime.date, datetime.date]:
    """Computes exact start and end dates for a named Indian FY quarter.

    E.g. fy_str="FY25-26", q_num=4 -> (2026-01-01, 2026-03-31)
    E.g. fy_str="FY25-26", q_1 -> (2025-04-01, 2025-06-30)
    """
    m_fy = re.search(r"FY\s*(\d{2,4})[-/](\d{2,4})", fy_str, re.IGNORECASE)
    if not m_fy:
        raise ValueError(f"Invalid fiscal year string: {fy_str}")

    y1_raw = int(m_fy.group(1))
    start_year = 2000 + y1_raw if y1_raw < 100 else y1_raw

    if q_num == 1:
        return datetime.date(start_year, 4, 1), datetime.date(start_year, 6, 30)
    elif q_num == 2:
        return datetime.date(start_year, 7, 1), datetime.date(start_year, 9, 30)
    elif q_num == 3:
        return datetime.date(start_year, 10, 1), datetime.date(start_year, 12, 31)
    elif q_num == 4:
        end_year = start_year + 1
        return datetime.date(end_year, 1, 1), datetime.date(end_year, 3, 31)
    else:
        raise ValueError(f"Invalid quarter number: {q_num}. Must be 1-4.")


def parse_explicit_fy(fy_str: str) -> tuple[datetime.date, datetime.date]:
    """Computes full April 1 to March 31 bounds for a named Indian FY.

    E.g. "FY25-26" -> (2025-04-01, 2026-03-31)
    """
    m_fy = re.search(r"FY\s*(\d{2,4})[-/](\d{2,4})", fy_str, re.IGNORECASE)
    if not m_fy:
        raise ValueError(f"Invalid fiscal year string: {fy_str}")
    y1_raw = int(m_fy.group(1))
    start_year = 2000 + y1_raw if y1_raw < 100 else y1_raw
    return datetime.date(start_year, 4, 1), datetime.date(start_year + 1, 3, 31)


MONTH_NAMES: dict[str, int] = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9, "sept": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def resolve_date_range(
    period_str: str | None,
    reference_date: datetime.date | None = None,
) -> DateRangeResult:
    """Resolves conversational or explicit period strings into exact ISO date ranges.

    Defaults to Indian Fiscal Year conventions (April 1 to March 31) evaluated in IST.
    """
    ref_date = reference_date or get_current_ist_date()

    if not period_str or not period_str.strip():
        return DateRangeResult(
            start_date=None,
            end_date=None,
            period_label="All-Time",
            fiscal_year=None,
            quarter_number=None,
            is_all_time=True,
            assumption_note="Evaluated across all recorded board dates (All-Time).",
        )

    clean = period_str.strip().lower()

    # 1. Check All-time explicitly
    if clean in ("all time", "all-time", "all", "cumulative", "lifetime"):
        return DateRangeResult(
            start_date=None,
            end_date=None,
            period_label="All-Time",
            fiscal_year=None,
            quarter_number=None,
            is_all_time=True,
            assumption_note="Evaluated across all recorded board dates (All-Time).",
        )

    # 2. Check "this quarter" / "current quarter"
    if clean in ("this quarter", "current quarter", "this q", "current q", "this quarter's"):
        fy, q, q_start, q_end = get_indian_fy_for_date(ref_date)
        return DateRangeResult(
            start_date=q_start,
            end_date=q_end,
            period_label=f"Q{q} {fy}",
            fiscal_year=fy,
            quarter_number=q,
            is_all_time=False,
            assumption_note=(
                f"Defaulted to Indian Fiscal Year Q{q} {fy} ({q_start.strftime('%b %d, %Y')} "
                f"to {q_end.strftime('%b %d, %Y')}). If you prefer Calendar Quarter or All-Time, specify your preference."
            ),
        )

    # 3. Check "last quarter" / "previous quarter"
    if clean in ("last quarter", "previous quarter", "prev quarter", "last q"):
        # Roll back by setting date to 15 days before current quarter start
        fy, q, q_start, _ = get_indian_fy_for_date(ref_date)
        prev_date = q_start - datetime.timedelta(days=15)
        prev_fy, prev_q, prev_start, prev_end = get_indian_fy_for_date(prev_date)
        return DateRangeResult(
            start_date=prev_start,
            end_date=prev_end,
            period_label=f"Q{prev_q} {prev_fy}",
            fiscal_year=prev_fy,
            quarter_number=prev_q,
            is_all_time=False,
            assumption_note=(
                f"Defaulted to Indian Fiscal Year Q{prev_q} {prev_fy} ({prev_start.strftime('%b %d, %Y')} "
                f"to {prev_end.strftime('%b %d, %Y')})."
            ),
        )

    # 4. Check "next quarter"
    if clean in ("next quarter", "next q"):
        fy, q, _, q_end = get_indian_fy_for_date(ref_date)
        next_date = q_end + datetime.timedelta(days=15)
        next_fy, next_q, next_start, next_end = get_indian_fy_for_date(next_date)
        return DateRangeResult(
            start_date=next_start,
            end_date=next_end,
            period_label=f"Q{next_q} {next_fy}",
            fiscal_year=next_fy,
            quarter_number=next_q,
            is_all_time=False,
            assumption_note=(
                f"Defaulted to Indian Fiscal Year Q{next_q} {next_fy} ({next_start.strftime('%b %d, %Y')} "
                f"to {next_end.strftime('%b %d, %Y')})."
            ),
        )

    # 5. Explicit Quarter with Named Fiscal Year: e.g. "Q4 FY25-26", "Q1 FY26-27", "FY25-26 Q4"
    m_explicit_q = re.search(r"Q([1-4])\s*(?:of\s*)?(FY\s*\d{2,4}[-/]\d{2,4})", clean, re.IGNORECASE)
    if not m_explicit_q:
        m_explicit_q = re.search(r"(FY\s*\d{2,4}[-/]\d{2,4})\s*Q([1-4])", clean, re.IGNORECASE)
        if m_explicit_q:
            fy_part = m_explicit_q.group(1).upper().replace(" ", "")
            q_num = int(m_explicit_q.group(2))
        else:
            fy_part, q_num = None, None
    else:
        q_num = int(m_explicit_q.group(1))
        fy_part = m_explicit_q.group(2).upper().replace(" ", "")

    if fy_part and q_num:
        s_date, e_date = parse_explicit_fy_quarter(fy_part, q_num)
        return DateRangeResult(
            start_date=s_date,
            end_date=e_date,
            period_label=f"Q{q_num} {fy_part}",
            fiscal_year=fy_part,
            quarter_number=q_num,
            is_all_time=False,
            assumption_note=f"Filtered for Indian Fiscal Year Q{q_num} {fy_part} ({s_date} to {e_date}).",
        )

    # 6. Bare Quarter (e.g. "Q1", "Q2", "Q3", "Q4") without explicit FY
    # Default to the most recent historical or current occurrence of that quarter in Indian FY
    m_bare_q = re.match(r"^q([1-4])$", clean)
    if m_bare_q:
        bare_q = int(m_bare_q.group(1))
        cur_fy, cur_q, _, _ = get_indian_fy_for_date(ref_date)
        # If bare_q <= cur_q, it falls in cur_fy; if bare_q > cur_q, it refers to the most recent one (previous FY)
        if bare_q <= cur_q:
            target_fy = cur_fy
        else:
            # Previous FY: e.g. FY26-27 -> FY25-26
            m_curr_yr = re.search(r"FY(\d{2})-(\d{2})", cur_fy)
            if m_curr_yr:
                y1 = int(m_curr_yr.group(1)) - 1
                y2 = int(m_curr_yr.group(2)) - 1
                target_fy = f"FY{y1:02d}-{y2:02d}"
            else:
                target_fy = cur_fy

        s_date, e_date = parse_explicit_fy_quarter(target_fy, bare_q)
        return DateRangeResult(
            start_date=s_date,
            end_date=e_date,
            period_label=f"Q{bare_q} {target_fy}",
            fiscal_year=target_fy,
            quarter_number=bare_q,
            is_all_time=False,
            assumption_note=(
                f"Assumed most recent Indian Fiscal Year occurrence for bare 'Q{bare_q}': "
                f"Q{bare_q} {target_fy} ({s_date} to {e_date})."
            ),
        )

    # 7. Explicit Fiscal Year: e.g. "FY25-26", "FY 2025-2026", "current fy", "this fy"
    if clean in ("this fy", "current fy", "this fiscal year", "current fiscal year"):
        cur_fy, _, _, _ = get_indian_fy_for_date(ref_date)
        s_date, e_date = parse_explicit_fy(cur_fy)
        return DateRangeResult(
            start_date=s_date,
            end_date=e_date,
            period_label=cur_fy,
            fiscal_year=cur_fy,
            quarter_number=None,
            is_all_time=False,
            assumption_note=f"Filtered for Indian Fiscal Year {cur_fy} (April 1 to March 31).",
        )

    m_full_fy = re.match(r"^(?:in\s+)?(fy\s*\d{2,4}[-/]\d{2,4})$", clean)
    if m_full_fy:
        fy_name = m_full_fy.group(1).upper().replace(" ", "")
        s_date, e_date = parse_explicit_fy(fy_name)
        return DateRangeResult(
            start_date=s_date,
            end_date=e_date,
            period_label=fy_name,
            fiscal_year=fy_name,
            quarter_number=None,
            is_all_time=False,
            assumption_note=f"Filtered for Indian Fiscal Year {fy_name} ({s_date} to {e_date}).",
        )

    # 8. Relative Month: "this month", "last month"
    if clean in ("this month", "current month"):
        y, m = ref_date.year, ref_date.month
        # Month start & end
        s_date = datetime.date(y, m, 1)
        next_m_date = datetime.date(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1)
        e_date = next_m_date - datetime.timedelta(days=1)
        return DateRangeResult(
            start_date=s_date,
            end_date=e_date,
            period_label=s_date.strftime("%B %Y"),
            fiscal_year=get_indian_fy_for_date(s_date)[0],
            quarter_number=None,
            is_all_time=False,
            assumption_note=f"Filtered for {s_date.strftime('%B %Y')} ({s_date} to {e_date}).",
        )

    if clean in ("last month", "previous month"):
        first_of_this = datetime.date(ref_date.year, ref_date.month, 1)
        last_of_prev = first_of_this - datetime.timedelta(days=1)
        first_of_prev = datetime.date(last_of_prev.year, last_of_prev.month, 1)
        return DateRangeResult(
            start_date=first_of_prev,
            end_date=last_of_prev,
            period_label=first_of_prev.strftime("%B %Y"),
            fiscal_year=get_indian_fy_for_date(first_of_prev)[0],
            quarter_number=None,
            is_all_time=False,
            assumption_note=f"Filtered for {first_of_prev.strftime('%B %Y')} ({first_of_prev} to {last_of_prev}).",
        )

    # 9. Bare Month Name (e.g. "july", "august")
    for m_term, m_idx in MONTH_NAMES.items():
        if re.search(r"\b" + m_term + r"\b", clean):
            # Target most recent occurrence of this month on or before ref_date
            y = ref_date.year if m_idx <= ref_date.month else ref_date.year - 1
            s_date = datetime.date(y, m_idx, 1)
            next_m_date = datetime.date(y + (1 if m_idx == 12 else 0), 1 if m_idx == 12 else m_idx + 1, 1)
            e_date = next_m_date - datetime.timedelta(days=1)
            return DateRangeResult(
                start_date=s_date,
                end_date=e_date,
                period_label=s_date.strftime("%B %Y"),
                fiscal_year=get_indian_fy_for_date(s_date)[0],
                quarter_number=None,
                is_all_time=False,
                assumption_note=f"Assumed most recent occurrence for bare '{m_term.capitalize()}': {s_date.strftime('%B %Y')}.",
            )

    # 10. Fallback: unparseable period -> treat as all-time with note
    return DateRangeResult(
        start_date=None,
        end_date=None,
        period_label=period_str,
        fiscal_year=None,
        quarter_number=None,
        is_all_time=True,
        assumption_note=(
            f"Could not deterministically parse period '{period_str}'. "
            "Evaluated across all recorded board dates (All-Time)."
        ),
    )
