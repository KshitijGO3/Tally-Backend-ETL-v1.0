"""Indian Numbering and Currency Formatters for Executive Dashboards.

Formats numeric values into standard Indian denominations (Crores, Lakhs, Thousands)
and standard full Indian comma-grouped representations (e.g. ₹ 1,84,20,500.00).
"""

from __future__ import annotations


def format_inr(amount: float | int | None) -> str:
    """Formats an amount into a compact Indian executive currency string.

    Examples:
        18,420,000.00 -> '₹ 1.84 Cr'
        4,520,000.00  -> '₹ 45.20 L'
        12,500.00     -> '₹ 12.50 K'
        450.00        -> '₹ 450.00'
        -1,842,000.00 -> '-₹ 18.42 L'

    Args:
        amount: Float or integer numeric amount, or None.

    Returns:
        Formatted Indian Rupee string with denomination suffix.
    """
    if amount is None:
        return "₹ 0.00"

    numeric_value = float(amount)
    sign_prefix = "-₹ " if numeric_value < 0 else "₹ "
    absolute_value = abs(numeric_value)

    if absolute_value >= 10_000_000:  # 1 Crore = 100 Lakhs
        return f"{sign_prefix}{absolute_value / 10_000_000:.2f} Cr"
    elif absolute_value >= 100_000:    # 1 Lakh = 100 Thousands
        return f"{sign_prefix}{absolute_value / 100_000:.2f} L"
    elif absolute_value >= 1_000:      # 1 Thousand
        return f"{sign_prefix}{absolute_value / 1_000:.2f} K"
    else:
        return f"{sign_prefix}{absolute_value:.2f}"


def format_inr_full(amount: float | int | None) -> str:
    """Formats an amount into a full comma-separated Indian currency string.

    Conforms to Indian numbering system (3 digits on the right, then groups of 2):
    e.g. 18420500.00 -> '₹ 1,84,20,500.00'

    Args:
        amount: Float or integer numeric amount.

    Returns:
        Fully formatted Indian Rupee string with exact commas and 2 decimals.
    """
    if amount is None:
        return "₹ 0.00"

    numeric_value = float(amount)
    sign_prefix = "-₹ " if numeric_value < 0 else "₹ "
    absolute_value = abs(numeric_value)

    formatted_decimal_string = f"{absolute_value:.2f}"
    integer_part, decimal_part = formatted_decimal_string.split(".")

    if len(integer_part) <= 3:
        grouped_integer = integer_part
    else:
        last_three_digits = integer_part[-3:]
        remaining_digits = integer_part[:-3]
        two_digit_chunks = []
        while remaining_digits:
            two_digit_chunks.append(remaining_digits[-2:])
            remaining_digits = remaining_digits[:-2]
        two_digit_chunks.reverse()
        grouped_integer = ",".join(two_digit_chunks) + "," + last_three_digits

    return f"{sign_prefix}{grouped_integer}.{decimal_part}"


def format_percentage(percentage_delta: float | None) -> str:
    """Formats a percentage delta with explicit +/- sign.

    Examples:
        12.4  -> '+12.4%'
        -5.1  -> '-5.1%'
        0.0   -> '0.0%'
        None  -> '0.0%'
    """
    if percentage_delta is None:
        return "0.0%"
    sign = "+" if percentage_delta > 0 else ""
    return f"{sign}{percentage_delta:.1f}%"
