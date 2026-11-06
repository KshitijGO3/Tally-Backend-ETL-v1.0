"""Unit tests for Tally date parsing and native SQL date normalization."""

from datetime import date
from backend_ETL.date_utils import (
    format_canonical_date,
    format_sql_date,
    parse_canonical_date,
    parse_tally_date,
)


class TestParseTallyDate:
    def test_yyyymmdd_format(self) -> None:
        assert parse_tally_date("20240401") == date(2024, 4, 1)
        assert parse_tally_date("20231231") == date(2023, 12, 31)
        assert parse_tally_date("19950815") == date(1995, 8, 15)

    def test_iso_format(self) -> None:
        assert parse_tally_date("2024-04-01") == date(2024, 4, 1)
        assert parse_tally_date("2024-04-01T00:00:00") == date(2024, 4, 1)
        assert parse_tally_date("2024-04-01 14:30:00") == date(2024, 4, 1)

    def test_d_mon_yyyy_format(self) -> None:
        assert parse_tally_date("1-Apr-2024") == date(2024, 4, 1)
        assert parse_tally_date("01-Apr-2024") == date(2024, 4, 1)
        assert parse_tally_date("15-AUG-1947") == date(1947, 8, 15)
        assert parse_tally_date("31-Dec-2023") == date(2023, 12, 31)

    def test_dd_mm_yyyy_format(self) -> None:
        assert parse_tally_date("01/04/2024") == date(2024, 4, 1)
        assert parse_tally_date("1/4/2024") == date(2024, 4, 1)
        assert parse_tally_date("31-12-2023") == date(2023, 12, 31)

    def test_sql_and_canonical_formatters(self) -> None:
        d = date(2024, 4, 1)
        assert format_sql_date(d) == "2024-04-01"
        assert format_canonical_date(d) == "01-04-2024"
        assert parse_canonical_date("2024-04-01") == d
        assert parse_canonical_date("01-04-2024") == d
        assert parse_canonical_date(d) == d

    def test_sentinel_dummy_dates_return_none(self) -> None:
        assert parse_tally_date("19000101") is None
        assert parse_tally_date("1900-01-01") is None
        assert parse_tally_date("00000000") is None
        assert parse_tally_date("0-0-0") is None
        assert parse_tally_date("00-00-0000") is None
        assert parse_tally_date("0") is None
        assert parse_tally_date("") is None
        assert parse_tally_date("   ") is None
        assert parse_tally_date(None) is None

    def test_invalid_dates_return_none(self) -> None:
        assert parse_tally_date("invalid_date") is None
        assert parse_tally_date("2024-02-31") is None  # Invalid calendar day
        assert parse_tally_date("32-01-2024") is None  # Day 32
        assert parse_tally_date("01-13-2024") is None  # Month 13


class TestIndianFinancialYearAndPeriods:
    def test_indian_financial_year_in_april(self) -> None:
        from datetime import date
        from backend_ETL.date_utils import get_indian_financial_year

        # Date in FY 2024-25
        fy_start, fy_end = get_indian_financial_year(date(2024, 4, 15))
        assert fy_start == date(2024, 4, 1)
        assert fy_end == date(2025, 3, 31)

    def test_indian_financial_year_in_january(self) -> None:
        from datetime import date
        from backend_ETL.date_utils import get_indian_financial_year

        # January 2025 is still FY 2024-25
        fy_start, fy_end = get_indian_financial_year(date(2025, 1, 10))
        assert fy_start == date(2024, 4, 1)
        assert fy_end == date(2025, 3, 31)

    def test_relative_period_bounds_mtd(self) -> None:
        from datetime import date
        from backend_ETL.date_utils import get_relative_period_bounds, get_prior_period_label

        ref = date(2024, 10, 15)
        curr, prior, label = get_relative_period_bounds("mtd", reference_date=ref)
        assert curr == (date(2024, 10, 1), date(2024, 10, 15))
        assert prior == (date(2024, 9, 1), date(2024, 9, 15))
        assert label == "1st to 15th October"
        prior_label = get_prior_period_label("mtd", prior[0], prior[1], reference_date=ref)
        assert prior_label == "1st to 15th September"

    def test_relative_period_bounds_mtd_anchored_today(self) -> None:
        from datetime import date
        from backend_ETL.date_utils import get_relative_period_bounds, format_ordinal_day

        today = date.today()
        curr, prior, label = get_relative_period_bounds("mtd")
        assert curr[0] == date(today.year, today.month, 1)
        assert curr[1] == today
        expected_label = (
            f"1st {today.strftime('%B')}"
            if today.day == 1
            else f"1st to {format_ordinal_day(today.day)} {today.strftime('%B')}"
        )
        assert label == expected_label

    def test_relative_period_bounds_last_30_days(self) -> None:
        from datetime import date
        from backend_ETL.date_utils import get_relative_period_bounds, get_prior_period_label

        ref = date(2024, 10, 26)
        curr, prior, label = get_relative_period_bounds("last_30_days", reference_date=ref)
        assert curr == (date(2024, 9, 27), date(2024, 10, 26))
        assert prior == (date(2024, 8, 28), date(2024, 9, 26))
        assert label == "Last 30 days"
        assert get_prior_period_label("last_30_days", prior[0], prior[1]) == "prior 30 days"

    def test_relative_period_bounds_last_60_days(self) -> None:
        from datetime import date
        from backend_ETL.date_utils import get_relative_period_bounds, get_prior_period_label

        ref = date(2024, 10, 26)
        curr, prior, label = get_relative_period_bounds("last_60_days", reference_date=ref)
        assert curr == (date(2024, 8, 28), date(2024, 10, 26))
        assert label == "Last 60 days"
        assert get_prior_period_label("last_60_days", prior[0], prior[1]) == "prior 60 days"

    def test_relative_period_bounds_last_90_days(self) -> None:
        from datetime import date
        from backend_ETL.date_utils import get_relative_period_bounds, get_prior_period_label

        ref = date(2024, 10, 26)
        curr, prior, label = get_relative_period_bounds("last_90_days", reference_date=ref)
        assert curr == (date(2024, 7, 29), date(2024, 10, 26))
        assert label == "Last 90 days"
        assert get_prior_period_label("last_90_days", prior[0], prior[1]) == "prior 90 days"

    def test_relative_period_bounds_financial_years(self) -> None:
        from datetime import date
        from backend_ETL.date_utils import get_relative_period_bounds

        ref = date(2024, 10, 26)
        curr, prior, label = get_relative_period_bounds("current_fy", reference_date=ref)
        assert curr == (date(2024, 4, 1), date(2024, 10, 26))
        assert prior == (date(2023, 4, 1), date(2023, 10, 26))
        assert "Current Financial Year (FY 2024-25)" in label

        curr_prev, prior_prev, label_prev = get_relative_period_bounds("previous_fy", reference_date=ref)
        assert curr_prev == (date(2023, 4, 1), date(2024, 3, 31))
        assert prior_prev == (date(2022, 4, 1), date(2023, 3, 31))
        assert "Previous Financial Year (FY 2023-24)" in label_prev

    def test_relative_period_bounds_custom(self) -> None:
        from datetime import date
        from backend_ETL.date_utils import get_relative_period_bounds, get_prior_period_label

        curr, prior, label = get_relative_period_bounds(
            "custom",
            custom_start="2024-10-01",
            custom_end="2024-10-15",
        )
        assert curr == (date(2024, 10, 1), date(2024, 10, 15))
        assert prior == (date(2024, 9, 16), date(2024, 9, 30))
        assert "1st Oct to 15th Oct 2024" in label
        prior_label = get_prior_period_label("custom", prior[0], prior[1])
        assert "16th Sep to 30th Sep 2024" in prior_label


