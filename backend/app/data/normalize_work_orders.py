"""Work Orders normalization layer.

Implements typed schemas, messy number parsing, free-text quantity extraction,
date parsing, and status vocabulary normalization for the Work Orders board.

Specification defined in NORMALIZATION_NOTES.md and PROJECT_PLAN.md §9.
"""

from __future__ import annotations

import datetime
import math
import re
from enum import Enum
from typing import Any, NamedTuple

import pandas as pd

# ---------------------------------------------------------------------------
# Enums for Work Orders Controlled Vocabularies
# ---------------------------------------------------------------------------

class NatureOfWork(str, Enum):
    """Controlled vocabulary for Nature of Work."""
    ONE_TIME_PROJECT = "One time Project"
    PROOF_OF_CONCEPT = "Proof of Concept"
    ANNUAL_RATE_CONTRACT = "Annual Rate Contract"
    MONTHLY_CONTRACT = "Monthly Contract"
    UNKNOWN = "UNKNOWN"


class ExecutionStatus(str, Enum):
    """Operational fulfillment status (orthogonal to billing)."""
    COMPLETED = "Completed"
    ONGOING = "Ongoing"
    EXECUTED_UNTIL_CURRENT_MONTH = "Executed until current month"
    NOT_STARTED = "Not Started"
    PAUSE_STRUCK = "Pause / struck"
    PARTIAL_COMPLETED = "Partial Completed"
    DETAILS_PENDING = "Details pending from Client"
    UNKNOWN = "UNKNOWN"


class DocumentType(str, Enum):
    """Legal document type backing the work order."""
    PURCHASE_ORDER = "Purchase Order"
    EMAIL_CONFIRMATION = "Email Confirmation"
    LOA_LOI = "LOA/LOI"
    UNKNOWN = "UNKNOWN"


class WOSector(str, Enum):
    """Industrial sector in Work Orders."""
    MINING = "Mining"
    RENEWABLES = "Renewables"
    RAILWAYS = "Railways"
    POWERLINE = "Powerline"
    OTHERS = "Others"
    CONSTRUCTION = "Construction"
    UNKNOWN = "UNKNOWN"


class PlatformDeliverable(str, Enum):
    """Skylark software platforms included in deliverables."""
    NONE = "NONE"
    SPECTRA = "SPECTRA"
    DMO = "DMO"
    SPECTRA_DMO = "SPECTRA + DMO"


class InvoiceStatus(str, Enum):
    """Billing execution stage."""
    FULLY_BILLED = "Fully Billed"
    PARTIALLY_BILLED = "Partially Billed"
    NOT_BILLED_YET = "Not billed yet"
    BILLED_VISIT_7 = "Billed- Visit 7"
    BILLED_VISIT_3 = "Billed- Visit 3"
    STUCK = "Stuck"
    NOT_BILLED = "NOT_BILLED"
    UNKNOWN_WITH_BILLING = "UNKNOWN_WITH_BILLING"
    UNKNOWN = "UNKNOWN"


class WOStatusBilled(str, Enum):
    """Administrative ERP account closure status."""
    CLOSED = "Closed"
    OPEN = "Open"
    UNKNOWN = "UNKNOWN"


class BillingStatus(str, Enum):
    """Billing exception handling status."""
    UPDATE_REQUIRED = "Update Required"
    NOT_BILLABLE = "Not Billable"
    PARTIALLY_BILLED = "Partially Billed"
    BILLED = "BILLED"
    STUCK = "Stuck"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Structured Return Types
# ---------------------------------------------------------------------------

class ParsedQuantity(NamedTuple):
    """Structured result of parsing free-text PO quantity string."""
    value: float | None
    unit: str | None
    raw: str
    is_qualitative: bool


# ---------------------------------------------------------------------------
# Core Parsing & Normalization Helpers (§9)
# ---------------------------------------------------------------------------

def parse_messy_number(value: Any, allow_negative: bool = True) -> float | None:
    """Strip currency symbols, commas, and formatting from numeric tokens.

    Preserves negative values when allow_negative=True (crucial for overbilled
    orders, receivables credit balances, and quantity balances).
    Returns None for blank or unparseable values (never silently coerces to 0.0).
    """
    if value is None or pd.isna(value):
        return None

    if isinstance(value, (int, float)):
        if math.isnan(value):
            return None
        val_float = float(value)
        if not allow_negative and val_float < 0:
            return None
        return val_float

    s = str(value).strip()
    if not s or s.lower() in ("nan", "none", "null", "na", "-", ""):
        return None

    # Handle accounting parenthetical negative format: (1,234.56) -> -1234.56
    is_paren_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_paren_negative = True
        s = s[1:-1].strip()

    # Normalize unicode minus sign (−) to ASCII hyphen (-)
    s = s.replace("−", "-")

    # Remove currency symbols and formatting
    s = re.sub(r"[₹$,]|\brs\.?|\binr\b", "", s, flags=re.IGNORECASE).strip()

    try:
        num = float(s)
        if is_paren_negative:
            num = -abs(num)
        if not allow_negative and num < 0:
            return None
        return num
    except ValueError:
        return None


def parse_messy_date(value: Any) -> datetime.date | None:
    """Parse various datetime representations into a standard python datetime.date.

    Handles pandas Timestamps, Python datetime/date, Excel serial dates, and
    ISO / date strings. Returns None for blanks; never defaults to today.
    """
    if value is None or pd.isna(value):
        return None

    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        return value.date()

    if isinstance(value, datetime.datetime):
        return value.date()

    if isinstance(value, datetime.date):
        return value

    # Excel serial number handling
    if isinstance(value, (int, float)):
        if math.isnan(value):
            return None
        try:
            return (datetime.datetime(1899, 12, 30) + datetime.timedelta(days=float(value))).date()  # noqa: DTZ001 - Excel epoch is intentionally naive
        except (OverflowError, ValueError):
            return None

    s = str(value).strip()
    if not s or s.lower() in ("nan", "none", "null", "na", "nat", "-"):
        return None

    try:
        parsed = pd.to_datetime(s)
        if pd.isna(parsed):
            return None
        return parsed.date()
    except (ValueError, TypeError, OverflowError):
        return None


def normalize_client_code(cust_code: Any) -> str | None:
    """Normalize client/customer codes across boards.

    Converts WO format ('WOCOMPANY_001') to standardized format ('COMPANY001').
    Leaves existing 'COMPANYxxx' untouched.
    """
    if cust_code is None or pd.isna(cust_code):
        return None
    s = str(cust_code).strip()
    if not s or s.lower() in ("nan", "none", "null"):
        return None

    # Replace prefix WOCOMPANY_ or WOCOMPANY with COMPANY
    if s.upper().startswith("WOCOMPANY_"):
        return "COMPANY" + s[10:].strip()
    if s.upper().startswith("WOCOMPANY"):
        return "COMPANY" + s[9:].strip()
    return s.upper()


def normalize_month_name(month_val: Any) -> str | None:
    """Normalize month abbreviations and strings to full English month names."""
    if month_val is None or pd.isna(month_val):
        return None
    s = str(month_val).strip()
    if not s or s.lower() in ("nan", "none", "null", "-"):
        return None

    mapping = {
        "jan": "January", "january": "January",
        "feb": "February", "february": "February",
        "mar": "March", "march": "March",
        "apr": "April", "april": "April",
        "may": "May",
        "jun": "June", "june": "June",
        "jul": "July", "july": "July",
        "aug": "August", "august": "August",
        "sep": "September", "sept": "September", "september": "September",
        "oct": "October", "october": "October",
        "nov": "November", "november": "November",
        "dec": "December", "december": "December",
    }
    return mapping.get(s.lower(), s)


def parse_po_quantity(value: Any) -> ParsedQuantity:
    """Parse free-text 'Quantities as per PO' mixing numbers, attached units, and text.

    Specification:
    1. Pure numbers & comma numbers ('4', '3000', '1,310.850', '59.33')
    2. Number + unit with space ('5360 HA', '10.5 KM', '1415 Acres', '7000 images')
    3. Number + attached unit ('115HA', '40MW', '45days', '415Acers', '2057 Acr')
    4. Qualitative / non-numeric ('L/s', 'Rate based on MW slabs', 'NA . Verbal confirmation for 59 km')
    5. Nulls -> ParsedQuantity(None, None, '', False)
    """
    if value is None or pd.isna(value):
        return ParsedQuantity(value=None, unit=None, raw="", is_qualitative=False)

    s = str(value).strip()
    if not s or s.lower() in ("nan", "none", "null"):
        return ParsedQuantity(value=None, unit=None, raw="", is_qualitative=False)

    # Pure qualitative descriptions
    if s in ("L/s", "Rate based on MW slabs"):
        return ParsedQuantity(value=None, unit=s, raw=s, is_qualitative=True)

    # Special mixed case: 'NA . Verbal confirmation for 59 km'
    m_verbal = re.search(r"(\d+(?:\.\d+)?)\s*(km|KM)", s, re.IGNORECASE)
    if "Verbal confirmation" in s and m_verbal:
        return ParsedQuantity(value=float(m_verbal.group(1)), unit="KM", raw=s, is_qualitative=True)

    # Quarter pattern: e.g. '3 Quarter (Till Dec)'
    m_quarter = re.match(r"^(\d+)\s+Quarter", s, re.IGNORECASE)
    if m_quarter:
        return ParsedQuantity(value=float(m_quarter.group(1)), unit="Quarter", raw=s, is_qualitative=False)

    # Pure numeric (including comma separated)
    clean_num = s.replace(",", "")
    try:
        num = float(clean_num)
        return ParsedQuantity(value=num, unit=None, raw=s, is_qualitative=False)
    except ValueError:
        pass

    # Regex matching: digits with decimals/commas, optional space, then unit letters
    m = re.match(r"^([\d,]+(?:\.\d+)?)\s*([A-Za-z/]+(?:\s+[A-Za-z]+)?.*)$", s)
    if m:
        num_str = m.group(1).replace(",", "")
        unit_str = m.group(2).strip()
        try:
            num = float(num_str)
        except ValueError:
            return ParsedQuantity(value=None, unit=unit_str, raw=s, is_qualitative=True)

        # Unit normalization mapping
        u_lower = unit_str.lower()
        if u_lower in ("ha",):
            norm_unit = "HA"
        elif u_lower in ("acres", "acers", "acr"):
            norm_unit = "Acres"
        elif u_lower in ("km",):
            norm_unit = "KM"
        elif u_lower in ("rkm",):
            norm_unit = "RKM"
        elif u_lower in ("mw",):
            norm_unit = "MW"
        elif u_lower in ("days", "day"):
            norm_unit = "days"
        elif u_lower in ("months", "month"):
            norm_unit = "months"
        elif u_lower in ("towers", "tower"):
            norm_unit = "towers"
        elif u_lower in ("pillars", "pillar"):
            norm_unit = "pillars"
        elif u_lower in ("images", "image"):
            norm_unit = "images"
        elif u_lower in ("sites", "site"):
            norm_unit = "sites"
        elif u_lower in ("rooftops", "rooftop"):
            norm_unit = "rooftops"
        elif u_lower in ("mines", "mine"):
            norm_unit = "mines"
        elif u_lower in ("subscriptions", "subscription"):
            norm_unit = "subscriptions"
        elif u_lower in ("location", "locations"):
            norm_unit = "locations"
        elif u_lower in ("units", "unit"):
            norm_unit = "units"
        elif u_lower in ("au",):
            norm_unit = "AU"
        else:
            norm_unit = unit_str

        return ParsedQuantity(value=num, unit=norm_unit, raw=s, is_qualitative=False)

    return ParsedQuantity(value=None, unit=s, raw=s, is_qualitative=True)


def normalize_invoice_status(status_val: Any, billed_val_excl: Any = None) -> str:
    """Normalize Invoice Status with conditional split for nulls (§3, §9).

    - If Invoice Status is non-null: normalize to standard enum.
    - If Invoice Status is null/blank AND Billed Value (Excl GST) <= 0 or null -> NOT_BILLED
    - If Invoice Status is null/blank AND Billed Value (Excl GST) > 0 -> UNKNOWN_WITH_BILLING
    """
    if status_val is not None and not pd.isna(status_val):
        s = str(status_val).strip()
        if s and s.lower() not in ("nan", "none", "null"):
            for member in InvoiceStatus:
                if member.value.lower() == s.lower():
                    return member.value
            return InvoiceStatus.UNKNOWN.value

    # When Invoice Status is null: check billed value (Excl GST)
    billed_float = parse_messy_number(billed_val_excl, allow_negative=True)
    if billed_float is not None and billed_float > 0:
        return InvoiceStatus.UNKNOWN_WITH_BILLING.value
    return InvoiceStatus.NOT_BILLED.value


def normalize_status(value: Any, column_name: str, billed_val_excl: Any = None) -> str | None:
    """Normalize status fields into controlled vocabularies with UNKNOWN fallback.

    Ensures the 4 status columns remain strictly orthogonal.
    Preserves Billing Status nulls as None (does not invent status for unused field).
    """
    col_lower = column_name.lower()

    if "invoice status" in col_lower:
        return normalize_invoice_status(value, billed_val_excl)

    if "billing status" in col_lower:
        if value is None or pd.isna(value):
            return None
        s = str(value).strip()
        if not s or s.lower() in ("nan", "none", "null"):
            return None
        # Handle 'BIlled' casing typo
        if s.lower() == "billed":
            return BillingStatus.BILLED.value
        for member in BillingStatus:
            if member.value.lower() == s.lower():
                return member.value
        return BillingStatus.UNKNOWN.value

    if value is None or pd.isna(value):
        return "UNKNOWN"

    s = str(value).strip()
    if not s or s.lower() in ("nan", "none", "null"):
        return "UNKNOWN"

    if "execution" in col_lower:
        for exec_member in ExecutionStatus:
            if exec_member.value.lower() == s.lower():
                return exec_member.value
        return ExecutionStatus.UNKNOWN.value

    if "wo status" in col_lower:
        for wo_member in WOStatusBilled:
            if wo_member.value.lower() == s.lower():
                return wo_member.value
        return WOStatusBilled.UNKNOWN.value

    if "nature of work" in col_lower:
        for nature_member in NatureOfWork:
            if nature_member.value.lower() == s.lower():
                return nature_member.value
        return NatureOfWork.UNKNOWN.value

    if "document type" in col_lower:
        for doc_member in DocumentType:
            if doc_member.value.lower() == s.lower():
                return doc_member.value
        return DocumentType.UNKNOWN.value

    return s


# ---------------------------------------------------------------------------
# Main DataFrame Normalization Function
# ---------------------------------------------------------------------------

def normalize_work_orders_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize raw Work Orders DataFrame according to NORMALIZATION_NOTES.md.

    - Processes exactly 176 records.
    - Preserves legitimate negative numbers across all 4 negative-bearing columns.
    - Preserves all 4 fully-null columns in the schema.
    - Parses all dates to ISO datetime.date objects.
    - Extracts structured quantities (po_quantity_value, po_quantity_unit, etc.).
    - Normalizes client codes into 'client_code_normalized'.
    - Maps status fields to orthogonal controlled vocabularies.
    """
    working_df = df.copy()
    if working_df.shape[1] > 0 and working_df.iloc[0].isna().all():
        working_df = working_df.iloc[1:].reset_index(drop=True)
    if "Serial #" not in working_df.columns and "Deal name masked" not in working_df.columns:
        working_df.columns = working_df.iloc[0]
        working_df = working_df.iloc[1:].reset_index(drop=True)

    norm_df = pd.DataFrame(index=working_df.index)

    # 1. Deal name masked
    col_name = "Deal name masked"
    deal_src_col = col_name if col_name in working_df.columns else ("item_name" if "item_name" in working_df.columns else None)
    if deal_src_col is not None:
        norm_df[col_name] = working_df[deal_src_col].apply(
            lambda x: str(x).strip() if pd.notna(x) and str(x).strip().lower() not in ("", "nan", "none", "null", "unnamed", "unnamed item") else None
        )

    # 2. Customer Name Code & normalized code
    col_name = "Customer Name Code"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].astype(str).str.strip()
        norm_df["client_code_normalized"] = norm_df[col_name].apply(normalize_client_code)

    # 3. Serial # (Primary Key)
    col_name = "Serial #"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].astype(str).str.strip()

    # 4. Nature of Work (Enum)
    col_name = "Nature of Work"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(lambda x: normalize_status(x, "Nature of Work"))

    # 5. Last executed month of recurring project
    col_name = "Last executed month of recurring project"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(normalize_month_name)

    # 6. Execution Status (Enum)
    col_name = "Execution Status"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(lambda x: normalize_status(x, "Execution Status"))

    # 7. Data Delivery Date
    col_name = "Data Delivery Date"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(parse_messy_date)

    # 8. Date of PO/LOI
    col_name = "Date of PO/LOI"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(parse_messy_date)

    # 9. Document Type (Enum)
    col_name = "Document Type"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(lambda x: normalize_status(x, "Document Type"))

    # 10. Probable Start Date
    col_name = "Probable Start Date"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(parse_messy_date)

    # 11. Probable End Date
    col_name = "Probable End Date"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(parse_messy_date)

    # 12. BD/KAM Personnel code
    col_name = "BD/KAM Personnel code"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(
            lambda x: str(x).strip() if pd.notna(x) and str(x).strip() not in ("", "nan", "None") else None
        )

    # 13. Sector
    col_name = "Sector"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].astype(str).str.strip()

    # 14. Type of Work
    col_name = "Type of Work"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].astype(str).str.strip()

    # 15. Skylark software platform deliverable (Enum, 12 nulls imputed as NONE)
    col_name = "Is any Skylark software platform part of the client deliverables in this deal?"
    if col_name in working_df.columns:
        def _clean_platform(x: Any) -> str:
            if pd.isna(x) or str(x).strip() in ("", "nan", "None"):
                return PlatformDeliverable.NONE.value
            s = str(x).strip()
            for p in PlatformDeliverable:
                if p.value.lower() == s.lower():
                    return p.value
            return PlatformDeliverable.NONE.value
        norm_df[col_name] = working_df[col_name].apply(_clean_platform)

    # 16. Last invoice date
    col_name = "Last invoice date"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(parse_messy_date)

    # 17. latest invoice no.
    col_name = "latest invoice no."
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(
            lambda x: str(x).strip() if pd.notna(x) and str(x).strip() not in ("", "nan", "None") else None
        )

    # 18. Amount in Rupees (Excl of GST) (Masked) - 1 null, 6 zeros, 169 positive
    col_name = "Amount in Rupees (Excl of GST) (Masked)"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(lambda x: parse_messy_number(x, allow_negative=True))

    # 19. Amount in Rupees (Incl of GST) (Masked) - 100% non-null float
    col_name = "Amount in Rupees (Incl of GST) (Masked)"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(lambda x: parse_messy_number(x, allow_negative=True) or 0.0)

    # 20. Billed Value in Rupees (Excl of GST.) (Masked) - 63 nulls, 0 zeros (preserve None!)
    col_name = "Billed Value in Rupees (Excl of GST.) (Masked)"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(lambda x: parse_messy_number(x, allow_negative=True))

    # 21. Billed Value in Rupees (Incl of GST.) (Masked) - 63 zeros, 0 nulls
    col_name = "Billed Value in Rupees (Incl of GST.) (Masked)"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(lambda x: parse_messy_number(x, allow_negative=True) or 0.0)

    # 22. Collected Amount in Rupees (Incl of GST.) (Masked) - 98 nulls, 0 zeros (preserve None!)
    col_name = "Collected Amount in Rupees (Incl of GST.) (Masked)"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(lambda x: parse_messy_number(x, allow_negative=True))

    # 23. Amount to be billed in Rs. (Exl. of GST) (Masked) - PRESERVE 6 NEGATIVES!
    col_name = "Amount to be billed in Rs. (Exl. of GST) (Masked)"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(lambda x: parse_messy_number(x, allow_negative=True))

    # 24. Amount to be billed in Rs. (Incl. of GST) (Masked) - PRESERVE 6 NEGATIVES!
    col_name = "Amount to be billed in Rs. (Incl. of GST) (Masked)"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(lambda x: parse_messy_number(x, allow_negative=True))

    # 25. Amount Receivable (Masked) - PRESERVE 11 NEGATIVES!
    col_name = "Amount Receivable (Masked)"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(lambda x: parse_messy_number(x, allow_negative=True))

    # 26. AR Priority account (bool: True if 'Priority', else False)
    col_name = "AR Priority account"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(
            lambda x: str(x).strip().lower() == "priority" if pd.notna(x) else False
        )

    # 27. Quantity by Ops (float | None)
    col_name = "Quantity by Ops"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(lambda x: parse_messy_number(x, allow_negative=True))

    # 28. Quantities as per PO (free text parser)
    col_name = "Quantities as per PO"
    if col_name in working_df.columns:
        parsed_po = working_df[col_name].apply(parse_po_quantity)
        norm_df[col_name] = working_df[col_name].apply(
            lambda x: str(x).strip() if pd.notna(x) and str(x).strip() not in ("", "nan", "None") else None
        )
        norm_df["po_quantity_value"] = parsed_po.apply(lambda p: p.value)
        norm_df["po_quantity_unit"] = parsed_po.apply(lambda p: p.unit)
        norm_df["po_quantity_is_qualitative"] = parsed_po.apply(lambda p: p.is_qualitative)
        norm_df["po_quantity_raw"] = parsed_po.apply(lambda p: p.raw)

    # 29. Quantity billed (till date) (float | None)
    col_name = "Quantity billed (till date)"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(lambda x: parse_messy_number(x, allow_negative=True))

    # 30. Balance in quantity - PRESERVE 2 NEGATIVES (-0.01, -1309.85)!
    col_name = "Balance in quantity"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(lambda x: parse_messy_number(x, allow_negative=True))

    # 31. Invoice Status (Conditional split: NOT_BILLED vs UNKNOWN_WITH_BILLING)
    col_name = "Invoice Status"
    billed_col = "Billed Value in Rupees (Excl of GST.) (Masked)"
    if col_name in working_df.columns:
        norm_df[col_name] = [
            normalize_invoice_status(
                working_df.at[i, col_name] if col_name in working_df.columns else None,
                working_df.at[i, billed_col] if billed_col in working_df.columns else None,
            )
            for i in working_df.index
        ]

    # 32. Expected Billing Month (100% NULL - PRESERVED IN SCHEMA)
    col_name = "Expected Billing Month"
    norm_df[col_name] = None if col_name not in working_df.columns else working_df[col_name].apply(
        lambda x: None if pd.isna(x) or str(x).strip() in ("", "nan", "None", "null") else str(x)
    )

    # 33. Actual Billing Month
    col_name = "Actual Billing Month"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(normalize_month_name)

    # 34. Actual Collection Month (100% NULL - PRESERVED IN SCHEMA)
    col_name = "Actual Collection Month"
    norm_df[col_name] = None if col_name not in working_df.columns else working_df[col_name].apply(
        lambda x: None if pd.isna(x) or str(x).strip() in ("", "nan", "None", "null") else str(x)
    )

    # 35. WO Status (billed) (Enum)
    col_name = "WO Status (billed)"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(lambda x: normalize_status(x, "WO Status (billed)"))

    # 36. Collection status (100% NULL - PRESERVED IN SCHEMA)
    col_name = "Collection status"
    norm_df[col_name] = None if col_name not in working_df.columns else working_df[col_name].apply(
        lambda x: None if pd.isna(x) or str(x).strip() in ("", "nan", "None", "null") else str(x)
    )

    # 37. Collection Date (100% NULL - PRESERVED IN SCHEMA)
    col_name = "Collection Date"
    norm_df[col_name] = None if col_name not in working_df.columns else working_df[col_name].apply(
        lambda x: None if pd.isna(x) or str(x).strip() in ("", "nan", "None", "null") else str(x)
    )

    # 38. Billing Status (Enum with typo fix BIlled -> BILLED; 148 nulls preserved as None)
    col_name = "Billing Status"
    if col_name in working_df.columns:
        norm_df[col_name] = working_df[col_name].apply(lambda x: normalize_status(x, "Billing Status"))

    # 39. Linked Deal (Board relation from Monday Connect Boards)
    for link_col in ["Linked Deal", "Linked Deal__linked_ids"]:
        if link_col in working_df.columns:
            norm_df[link_col] = working_df[link_col]

    return norm_df

