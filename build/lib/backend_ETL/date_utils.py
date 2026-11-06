"""Date parsing and normalization utility for Tally ERP replicated dates.

Normalizes varied Tally date representations (YYYYMMDD, YYYY-MM-DD, D-Mon-YYYY, DD/MM/YYYY)
strictly into Indian standard format DD-MM-YYYY (e.g. 01-04-2024), safely converting
sentinel/dummy values ('19000101', '00000000', '', '0-0-0', '1900-01-01') to None.
"""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta
from typing import Any

SENTINEL_DATES: frozenset[str] = frozenset(
    {
        "",
        "0",
        "00000000",
        "19000101",
        "0-0-0",
        "00-00-0000",
        "1900-01-01",
        "01-01-1900",
        "19000101T000000",
    }
)


def parse_tally_date(raw_text: Any) -> date | None:
    """Parses any raw Tally date into a native Python datetime.date object.

    Handles varied Tally representations:
    - YYYYMMDD (e.g. '20240401')
    - ISO YYYY-MM-DD (e.g. '2024-04-01')
    - D-Mon-YYYY or DD-Mon-YYYY (e.g. '1-Apr-2024', '15-AUG-1947')
    - DD/MM/YYYY or DD-MM-YYYY (e.g. '01/04/2024', '1/4/2024')
    - Timestamps (e.g. '2024-04-01T14:30:00' or '2024-04-01 00:00:00')

    Converts sentinel/dummy values ('19000101', '00000000', '', '0-0-0', '1900-01-01') to None.

    Args:
        raw_text: Raw date string, date instance, or None from Tally XML/JSON or Bronze table.

    Returns:
        A datetime.date instance, or None if input is empty, a sentinel, or invalid.
    """
    if raw_text is None:
        return None

    if isinstance(raw_text, datetime):
        return raw_text.date()

    if isinstance(raw_text, date):
        if raw_text.year == 1900 and raw_text.month == 1 and raw_text.day == 1:
            return None
        return raw_text

    val = str(raw_text).strip()
    if not val or val in SENTINEL_DATES:
        return None

    # Strip time component if present
    if "T" in val:
        val = val.split("T", 1)[0].strip()
    elif " " in val:
        val = val.split(" ", 1)[0].strip()

    if not val or val in SENTINEL_DATES:
        return None

    # Format 1: YYYYMMDD (e.g. '20240401')
    if re.match(r"^[12]\d{7}$", val):
        try:
            dt = datetime.strptime(val, "%Y%m%d").date()
            if dt.year == 1900 and dt.month == 1 and dt.day == 1:
                return None
            return dt
        except ValueError:
            return None

    # Format 2: ISO YYYY-MM-DD (e.g. '2024-04-01')
    if re.match(r"^[12]\d{3}-[01]\d-[0-3]\d$", val):
        try:
            dt = datetime.strptime(val, "%Y-%m-%d").date()
            if dt.year == 1900 and dt.month == 1 and dt.day == 1:
                return None
            return dt
        except ValueError:
            return None

    # Format 3: DD-Mon-YYYY or D-Mon-YYYY (e.g. '1-Apr-2024' or '01-Apr-2024')
    if re.match(r"^[0-3]?\d-[A-Za-z]{3}-[12]\d{3}$", val):
        try:
            dt = datetime.strptime(val, "%d-%b-%Y").date()
            return dt
        except ValueError:
            return None

    # Format 4: DD/MM/YYYY or DD-MM-YYYY (e.g. '01/04/2024' or '1/4/2024')
    normalized = val.replace("/", "-")
    if re.match(r"^[0-3]?\d-[0-1]?\d-[12]\d{3}$", normalized):
        try:
            parts = normalized.split("-")
            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
            if y == 1900 and m == 1 and d == 1:
                return None
            return date(year=y, month=m, day=d)
        except (ValueError, IndexError):
            return None

    # Fallback attempt for standard date formats
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(val, fmt).date()
            if dt.year == 1900 and dt.month == 1 and dt.day == 1:
                return None
            return dt
        except ValueError:
            pass

    return None


def parse_canonical_date(date_val: date | str) -> date:
    """Parses a date string (DD-MM-YYYY or YYYY-MM-DD) or returns date instance directly."""
    if isinstance(date_val, date):
        return date_val

    clean_str = str(date_val).strip()
    # Try ISO YYYY-MM-DD first
    try:
        return date.fromisoformat(clean_str)
    except ValueError:
        pass

    # Try DD-MM-YYYY
    parts = clean_str.replace("/", "-").split("-")
    if len(parts) == 3:
        try:
            return date(year=int(parts[2]), month=int(parts[1]), day=int(parts[0]))
        except ValueError:
            pass

    raise ValueError(f"Invalid canonical date format: '{date_val}'.")


def format_canonical_date(target_date: date | str | None) -> str:
    """Formats a datetime.date instance into standard Indian DD-MM-YYYY format (e.g. '15-10-2024')."""
    if target_date is None:
        return ""
    if isinstance(target_date, str):
        parsed = parse_canonical_date(target_date)
        return parsed.strftime("%d-%m-%Y")
    return target_date.strftime("%d-%m-%Y")


def format_sql_date(target_date: date | str | None) -> str | None:
    """Formats a date or string into ISO YYYY-MM-DD for native SQL queries."""
    if target_date is None:
        return None
    if isinstance(target_date, str):
        parsed = parse_canonical_date(target_date)
        return parsed.strftime("%Y-%m-%d")
    return target_date.strftime("%Y-%m-%d")


def get_indian_financial_year(reference_date: date | str) -> tuple[date, date]:
    """Returns the start and end dates of the Indian Financial Year (1st April to 31st March).

    Args:
        reference_date: A datetime.date object or DD-MM-YYYY date string.

    Returns:
        A tuple of (financial_year_start, financial_year_end).
    """
    if isinstance(reference_date, str):
        parsed_date = parse_canonical_date(reference_date)
    else:
        parsed_date = reference_date

    if parsed_date.month >= 4:
        start_year = parsed_date.year
        end_year = parsed_date.year + 1
    else:
        start_year = parsed_date.year - 1
        end_year = parsed_date.year

    financial_year_start = date(year=start_year, month=4, day=1)
    financial_year_end = date(year=end_year, month=3, day=31)
    return financial_year_start, financial_year_end


def format_ordinal_day(day_number: int) -> str:
    """Formats a calendar day number with its English ordinal suffix (e.g. 1st, 2nd, 3rd, 26th)."""
    if 11 <= (day_number % 100) <= 13:
        return f"{day_number}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(day_number % 10, "th")
    return f"{day_number}{suffix}"


def parse_date_flexible(candidate_date: date | str | None) -> date | None:
    """Safely parses a date from either datetime.date, ISO string (YYYY-MM-DD), or Indian format (DD-MM-YYYY)."""
    if candidate_date is None:
        return None
    if isinstance(candidate_date, date):
        return candidate_date

    clean_str = str(candidate_date).strip()
    if not clean_str:
        return None

    # 1. Try ISO YYYY-MM-DD
    try:
        return date.fromisoformat(clean_str)
    except ValueError:
        pass

    # 2. Try DD-MM-YYYY or DD/MM/YYYY
    normalized = clean_str.replace("/", "-")
    parts = normalized.split("-")
    if len(parts) == 3:
        try:
            return date(year=int(parts[2]), month=int(parts[1]), day=int(parts[0]))
        except ValueError:
            pass

    return None


def get_relative_period_bounds(
    period_preset: str,
    reference_date: date | None = None,
    custom_start: date | str | None = None,
    custom_end: date | str | None = None,
) -> tuple[tuple[date, date], tuple[date, date], str]:
    """Calculates the current period and comparison prior period date bounds.

    Supports the 5 default executive presets, Month-to-date default, and Custom date range:
    1. 'mtd' (Month to Date, e.g. '1st to 26th October')
    2. 'last_30_days' (Last 30 days)
    3. 'last_60_days' (Last 60 days)
    4. 'last_90_days' (Last 90 days)
    5. 'current_fy' (Current Financial Year)
    6. 'previous_fy' (Previous Financial Year)
    7. 'custom' (Custom date range between custom_start and custom_end)

    Also preserves backwards compatibility for 'qtd', 'ytd', and 'last_month'.

    Args:
        period_preset: Identifier for the period preset.
        reference_date: Anchor date. If omitted, defaults dynamically to today.
        custom_start: Optional start date for 'custom' preset.
        custom_end: Optional end date for 'custom' preset.

    Returns:
        A tuple of:
        ((current_start_date, current_end_date),
         (prior_start_date, prior_end_date),
         display_label)
    """
    anchor_date = reference_date or date.today()
    normalized_preset = period_preset.strip().lower()

    # ─── 1. Month to Date (MTD - Default) ────────────────────────────────────────
    if normalized_preset in ("mtd", "month_to_date"):
        current_start_date = date(year=anchor_date.year, month=anchor_date.month, day=1)
        current_end_date = anchor_date

        if anchor_date.month == 1:
            prior_year = anchor_date.year - 1
            prior_month = 12
        else:
            prior_year = anchor_date.year
            prior_month = anchor_date.month - 1

        prior_start_date = date(year=prior_year, month=prior_month, day=1)
        prior_month_max_day = calendar.monthrange(prior_year, prior_month)[1]
        prior_end_day = min(anchor_date.day, prior_month_max_day)
        prior_end_date = date(year=prior_year, month=prior_month, day=prior_end_day)

        if anchor_date.day == 1:
            display_label = f"1st {anchor_date.strftime('%B')}"
        else:
            display_label = f"1st to {format_ordinal_day(anchor_date.day)} {anchor_date.strftime('%B')}"

        return (current_start_date, current_end_date), (prior_start_date, prior_end_date), display_label

    # ─── 2. Last 30 Days ─────────────────────────────────────────────────────────
    elif normalized_preset in ("last_30_days", "30_days"):
        current_start_date = anchor_date - timedelta(days=29)
        current_end_date = anchor_date

        prior_start_date = anchor_date - timedelta(days=59)
        prior_end_date = anchor_date - timedelta(days=30)

        display_label = "Last 30 days"
        return (current_start_date, current_end_date), (prior_start_date, prior_end_date), display_label

    # ─── 3. Last 60 Days ─────────────────────────────────────────────────────────
    elif normalized_preset in ("last_60_days", "60_days"):
        current_start_date = anchor_date - timedelta(days=59)
        current_end_date = anchor_date

        prior_start_date = anchor_date - timedelta(days=119)
        prior_end_date = anchor_date - timedelta(days=60)

        display_label = "Last 60 days"
        return (current_start_date, current_end_date), (prior_start_date, prior_end_date), display_label

    # ─── 4. Last 90 Days ─────────────────────────────────────────────────────────
    elif normalized_preset in ("last_90_days", "90_days"):
        current_start_date = anchor_date - timedelta(days=89)
        current_end_date = anchor_date

        prior_start_date = anchor_date - timedelta(days=179)
        prior_end_date = anchor_date - timedelta(days=90)

        display_label = "Last 90 days"
        return (current_start_date, current_end_date), (prior_start_date, prior_end_date), display_label

    # ─── 5. Current Financial Year ───────────────────────────────────────────────
    elif normalized_preset in ("current_fy", "current_financial_year", "ytd", "year_to_date"):
        fy_start, _ = get_indian_financial_year(anchor_date)
        current_start_date = fy_start
        current_end_date = anchor_date

        days_offset = (anchor_date - current_start_date).days
        prior_fy_start = date(year=fy_start.year - 1, month=4, day=1)
        prior_start_date = prior_fy_start
        prior_end_date = prior_fy_start + timedelta(days=days_offset)

        fy_label_str = f"FY {fy_start.year}-{str(fy_start.year + 1)[2:]}"
        display_label = f"Current Financial Year ({fy_label_str})"
        return (current_start_date, current_end_date), (prior_start_date, prior_end_date), display_label

    # ─── 6. Previous Financial Year ──────────────────────────────────────────────
    elif normalized_preset in ("previous_fy", "prior_fy", "previous_financial_year"):
        fy_start, _ = get_indian_financial_year(anchor_date)
        current_start_date = date(year=fy_start.year - 1, month=4, day=1)
        current_end_date = date(year=fy_start.year, month=3, day=31)

        prior_start_date = date(year=fy_start.year - 2, month=4, day=1)
        prior_end_date = date(year=fy_start.year - 1, month=3, day=31)

        prev_fy_label_str = f"FY {fy_start.year - 1}-{str(fy_start.year)[2:]}"
        display_label = f"Previous Financial Year ({prev_fy_label_str})"
        return (current_start_date, current_end_date), (prior_start_date, prior_end_date), display_label

    # ─── 7. Custom Date Range ───────────────────────────────────────────────────
    elif normalized_preset in ("custom", "custom_range"):
        parsed_custom_start = parse_date_flexible(custom_start)
        parsed_custom_end = parse_date_flexible(custom_end)

        # Fallback to MTD bounds if custom dates are omitted or invalid
        if not parsed_custom_start or not parsed_custom_end:
            return get_relative_period_bounds("mtd", reference_date=anchor_date)

        # Ensure start precedes or equals end
        if parsed_custom_start > parsed_custom_end:
            parsed_custom_start, parsed_custom_end = parsed_custom_end, parsed_custom_start

        current_start_date = parsed_custom_start
        current_end_date = parsed_custom_end

        total_range_days = (current_end_date - current_start_date).days + 1
        prior_end_date = current_start_date - timedelta(days=1)
        prior_start_date = current_start_date - timedelta(days=total_range_days)

        if current_start_date.year == current_end_date.year:
            display_label = (
                f"{format_ordinal_day(current_start_date.day)} {current_start_date.strftime('%b')} to "
                f"{format_ordinal_day(current_end_date.day)} {current_end_date.strftime('%b %Y')}"
            )
        else:
            display_label = (
                f"{format_ordinal_day(current_start_date.day)} {current_start_date.strftime('%b %Y')} to "
                f"{format_ordinal_day(current_end_date.day)} {current_end_date.strftime('%b %Y')}"
            )

        return (current_start_date, current_end_date), (prior_start_date, prior_end_date), display_label

    # ─── Legacy Indian Quarter to Date (QTD) ────────────────────────────────────
    elif normalized_preset in ("qtd", "quarter_to_date"):
        if 4 <= anchor_date.month <= 6:
            quarter_start_month = 4
            prior_quarter_start_month = 1
            prior_quarter_year = anchor_date.year
        elif 7 <= anchor_date.month <= 9:
            quarter_start_month = 7
            prior_quarter_start_month = 4
            prior_quarter_year = anchor_date.year
        elif 10 <= anchor_date.month <= 12:
            quarter_start_month = 10
            prior_quarter_start_month = 7
            prior_quarter_year = anchor_date.year
        else:
            quarter_start_month = 1
            prior_quarter_start_month = 10
            prior_quarter_year = anchor_date.year - 1

        current_start_date = date(year=anchor_date.year, month=quarter_start_month, day=1)
        current_end_date = anchor_date

        days_offset = (anchor_date - current_start_date).days
        prior_start_date = date(year=prior_quarter_year, month=prior_quarter_start_month, day=1)
        prior_end_date = prior_start_date + timedelta(days=days_offset)

        display_label = f"QTD ({anchor_date.strftime('%b %Y')})"
        return (current_start_date, current_end_date), (prior_start_date, prior_end_date), display_label

    # ─── Legacy Last Month ──────────────────────────────────────────────────────
    elif normalized_preset in ("last_month",):
        if anchor_date.month == 1:
            curr_month_year = anchor_date.year - 1
            curr_month = 12
        else:
            curr_month_year = anchor_date.year
            curr_month = anchor_date.month - 1

        max_day = calendar.monthrange(curr_month_year, curr_month)[1]
        current_start_date = date(year=curr_month_year, month=curr_month, day=1)
        current_end_date = date(year=curr_month_year, month=curr_month, day=max_day)

        if curr_month == 1:
            prior_month_year = curr_month_year - 1
            prior_month = 12
        else:
            prior_month_year = curr_month_year
            prior_month = curr_month - 1

        prior_max_day = calendar.monthrange(prior_month_year, prior_month)[1]
        prior_start_date = date(year=prior_month_year, month=prior_month, day=1)
        prior_end_date = date(year=prior_month_year, month=prior_month, day=prior_max_day)

        display_label = f"{current_start_date.strftime('%B %Y')}"
        return (current_start_date, current_end_date), (prior_start_date, prior_end_date), display_label

    # Fallback to MTD
    return get_relative_period_bounds("mtd", reference_date=anchor_date)


def get_prior_period_label(
    period_preset: str,
    prior_start: date,
    prior_end: date,
    reference_date: date | None = None,
) -> str:
    """Returns a natural language label for the prior comparison period."""
    normalized_preset = period_preset.strip().lower()

    if normalized_preset in ("mtd", "month_to_date"):
        if prior_end.day == 1:
            return f"1st {prior_end.strftime('%B')}"
        return f"1st to {format_ordinal_day(prior_end.day)} {prior_end.strftime('%B')}"

    elif normalized_preset in ("last_30_days", "30_days"):
        return "prior 30 days"

    elif normalized_preset in ("last_60_days", "60_days"):
        return "prior 60 days"

    elif normalized_preset in ("last_90_days", "90_days"):
        return "prior 90 days"

    elif normalized_preset in ("current_fy", "current_financial_year", "ytd", "year_to_date"):
        fy_start, _ = get_indian_financial_year(reference_date or date.today())
        return f"prior FY (FY {fy_start.year - 1}-{str(fy_start.year)[2:]})"

    elif normalized_preset in ("previous_fy", "prior_fy", "previous_financial_year"):
        fy_start, _ = get_indian_financial_year(reference_date or date.today())
        return f"FY {fy_start.year - 2}-{str(fy_start.year - 1)[2:]}"

    elif normalized_preset in ("custom", "custom_range"):
        if prior_start.year == prior_end.year:
            return (
                f"{format_ordinal_day(prior_start.day)} {prior_start.strftime('%b')} to "
                f"{format_ordinal_day(prior_end.day)} {prior_end.strftime('%b %Y')}"
            )
        return (
            f"{format_ordinal_day(prior_start.day)} {prior_start.strftime('%b %Y')} to "
            f"{format_ordinal_day(prior_end.day)} {prior_end.strftime('%b %Y')}"
        )

    return f"{prior_start.day}–{prior_end.day} {prior_end.strftime('%B')}"


