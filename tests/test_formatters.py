"""Unit tests for Indian currency and numeric formatters."""

from backend_ETL.formatters import format_inr, format_inr_full, format_percentage


class TestIndianFormatters:
    def test_format_inr_crores(self) -> None:
        assert format_inr(18_420_000) == "₹ 1.84 Cr"
        assert format_inr(21_000_000) == "₹ 2.10 Cr"
        assert format_inr(-18_420_000) == "-₹ 1.84 Cr"

    def test_format_inr_lakhs(self) -> None:
        assert format_inr(4_520_000) == "₹ 45.20 L"
        assert format_inr(100_000) == "₹ 1.00 L"
        assert format_inr(-4_520_000) == "-₹ 45.20 L"

    def test_format_inr_thousands(self) -> None:
        assert format_inr(12_500) == "₹ 12.50 K"
        assert format_inr(1_000) == "₹ 1.00 K"

    def test_format_inr_sub_thousand(self) -> None:
        assert format_inr(450.5) == "₹ 450.50"
        assert format_inr(0) == "₹ 0.00"
        assert format_inr(None) == "₹ 0.00"

    def test_format_inr_full_indian_commas(self) -> None:
        assert format_inr_full(18420500.5) == "₹ 1,84,20,500.50"
        assert format_inr_full(4520000) == "₹ 45,20,000.00"
        assert format_inr_full(1234) == "₹ 1,234.00"
        assert format_inr_full(500) == "₹ 500.00"
        assert format_inr_full(-18420500) == "-₹ 1,84,20,500.00"

    def test_format_percentage(self) -> None:
        assert format_percentage(12.4) == "+12.4%"
        assert format_percentage(-5.1) == "-5.1%"
        assert format_percentage(0.0) == "0.0%"
        assert format_percentage(None) == "0.0%"
