"""Unit tests for pure Python AnalyticsService and financial KPI math."""

from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime
from typing import Any

import pytest

from backend_ETL.analytics_service import AnalyticsService
from backend_ETL.canonical_schema import CANONICAL_DDL_STATEMENTS
from backend_ETL.db import PostgresManager
from backend_ETL.schema import PG_DDL_STATEMENTS


class _SQLiteCursorAdapter:
    def __init__(self, raw_cur: sqlite3.Cursor) -> None:
        self._cur = raw_cur

    @staticmethod
    def _translate(sql: str) -> str:
        if "DROP CONSTRAINT" in sql.upper():
            return "SELECT 1"
        s = sql.replace("%s", "?")
        s = s.replace("BIGSERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
        s = s.replace("TIMESTAMPTZ DEFAULT NOW()", "TEXT DEFAULT CURRENT_TIMESTAMP")
        s = s.replace("TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP", "TEXT DEFAULT CURRENT_TIMESTAMP")
        s = s.replace("TIMESTAMPTZ", "TEXT")
        s = s.replace("NOW()", "CURRENT_TIMESTAMP")
        s = s.replace("CREATE OR REPLACE VIEW", "CREATE VIEW IF NOT EXISTS")
        # Strip regex CHECK constraints for SQLite compatibility
        s = re.sub(r"CHECK\s*\([^)]*~[^)]*\)", "", s)
        return s

    @staticmethod
    def _adapt_params(params: tuple[Any, ...] | list[Any]) -> tuple[Any, ...]:
        return tuple(
            p.isoformat() if isinstance(p, (date, datetime)) else p
            for p in params
        )

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        return self._cur.execute(self._translate(sql), self._adapt_params(params))

    def executemany(self, sql: str, seq_params: list[tuple[Any, ...]]) -> Any:
        return self._cur.executemany(
            self._translate(sql), [self._adapt_params(p) for p in seq_params]
        )

    def fetchone(self) -> Any:
        return self._cur.fetchone()

    def fetchall(self) -> list[Any]:
        return self._cur.fetchall()

    def close(self) -> None:
        self._cur.close()


class _SQLiteConnAdapter:
    def __init__(self, raw_conn: sqlite3.Connection) -> None:
        self._conn = raw_conn
        self._conn.row_factory = sqlite3.Row

    def cursor(self) -> _SQLiteCursorAdapter:
        return _SQLiteCursorAdapter(self._conn.cursor())

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()


@pytest.fixture()
def analytics_test_db() -> PostgresManager:
    raw_conn = sqlite3.connect(":memory:", check_same_thread=False)
    compat_conn = _SQLiteConnAdapter(raw_conn)
    db = PostgresManager(conn_factory=lambda: compat_conn, use_pool=False)

    with db.connection() as conn:
        cur = conn.cursor()
        for stmt in PG_DDL_STATEMENTS:
            cur.execute(stmt)
        for stmt in CANONICAL_DDL_STATEMENTS:
            cur.execute(stmt)

        # Seed Company
        cur.execute(
            """
            INSERT INTO canonical_companies (company_id, name, books_from, starting_from)
            VALUES ('comp-shree-1', 'Shree Polychem', '2024-04-01', '2024-04-01')
            """
        )

        # Seed Accounts
        cur.execute(
            """
            INSERT INTO canonical_accounts (account_id, company_id, name, classification_role)
            VALUES 
            ('acc-cust-1', 'comp-shree-1', 'Vardhman Packaging', 'customer'),
            ('acc-cust-2', 'comp-shree-1', 'Apex Polymers', 'customer'),
            ('acc-bank-1', 'comp-shree-1', 'HDFC Bank Account', 'bank'),
            ('acc-supp-1', 'comp-shree-1', 'Reliance Industries', 'supplier')
            """
        )

        # Seed Active Vouchers
        cur.execute(
            """
            INSERT INTO canonical_vouchers (voucher_id, company_id, date, kind, base_type, party_ref, lifecycle)
            VALUES 
            ('vch-sale-1', 'comp-shree-1', '2024-10-10', 'Tax Invoice', 'Sales', 'acc-cust-1', 'active'),
            ('vch-sale-2', 'comp-shree-1', '2024-10-12', 'Tax Invoice', 'Sales', 'acc-cust-2', 'active'),
            ('vch-rcpt-1', 'comp-shree-1', '2024-10-14', 'Receipt', 'Receipt', 'acc-cust-1', 'active'),
            ('vch-pur-1', 'comp-shree-1', '2024-10-08', 'Purchase', 'Purchase', 'acc-supp-1', 'active')
            """
        )

        # Seed Daily Movements (18.4 Lakhs Sales, 14.2 Lakhs Collections, 15.1 Lakhs Purchases in Oct)
        cur.execute(
            """
            INSERT INTO canonical_daily_movements (company_id, date, base_type, account_role, is_debit, total_amount, voucher_count)
            VALUES 
            ('comp-shree-1', '2024-10-10', 'Sales', 'customer', 1, 1000000.0, 1),
            ('comp-shree-1', '2024-10-12', 'Sales', 'customer', 1, 840000.0, 1),
            ('comp-shree-1', '2024-10-14', 'Receipt', 'bank', 1, 1420000.0, 1),
            ('comp-shree-1', '2024-10-08', 'Purchase', 'supplier', 0, 1510000.0, 1),
            -- Prior period comparison: 01-09-2024 to 15-09-2024
            ('comp-shree-1', '2024-09-05', 'Sales', 'customer', 1, 1559322.0, 1),
            ('comp-shree-1', '2024-09-06', 'Receipt', 'bank', 1, 1302752.0, 1),
            ('comp-shree-1', '2024-09-07', 'Purchase', 'supplier', 0, 1606382.0, 1)
            """
        )

        # Seed Bill Events (for DSO & Overdue Invoices)
        cur.execute(
            """
            INSERT INTO canonical_bill_events (voucher_ref, company_id, party_ref, bill_ref, kind, due_date, amount)
            VALUES 
            ('vch-sale-1', 'comp-shree-1', 'acc-cust-1', 'INV-101', 'new', '2024-10-15', 100000.0),
            ('vch-rcpt-1', 'comp-shree-1', 'acc-cust-1', 'INV-101', 'agst', NULL, 100000.0),
            ('vch-sale-2', 'comp-shree-1', 'acc-cust-2', 'INV-102', 'new', '2024-10-01', 250000.0)
            """
        )
        cur.close()

    return db


class TestAnalyticsService:
    def test_get_sync_status(self, analytics_test_db: PostgresManager) -> None:
        service = AnalyticsService(analytics_test_db)
        status = service.get_sync_status("comp-shree-1")
        assert status["company_name"] == "Shree Polychem"
        assert "14 Oct" in status["books_updated_label"]

    def test_executive_overview_mtd(self, analytics_test_db: PostgresManager) -> None:
        service = AnalyticsService(analytics_test_db)
        # Anchor at 15-10-2024
        overview = service.get_executive_overview(
            company_id="comp-shree-1",
            period_preset="mtd",
            reference_date=date(2024, 10, 15),
            user_display_name="Manoj",
        )

        assert overview["company_name"] == "Shree Polychem"
        assert overview["period_label"] == "1st to 15th October"
        assert overview["prior_period_label"] == "1st to 15th September"
        assert "Good morning, Manoj." == overview["greeting_title"]

        # Sales: 10,00,000 + 8,40,000 = 18,40,000 (₹ 18.40 L)
        sales_kpi = overview["kpis"]["sales"]
        assert sales_kpi["raw_value"] == 1840000.0
        assert sales_kpi["formatted_value"] == "₹ 18.40 L"

        # Collections: 14,20,000 (₹ 14.20 L)
        coll_kpi = overview["kpis"]["collections"]
        assert coll_kpi["raw_value"] == 1420000.0
        assert coll_kpi["formatted_value"] == "₹ 14.20 L"

        # Purchases: 15,10,000 (₹ 15.10 L)
        purch_kpi = overview["kpis"]["purchases"]
        assert purch_kpi["raw_value"] == 1510000.0
        assert purch_kpi["formatted_value"] == "₹ 15.10 L"

    def test_executive_overview_last_30_days(self, analytics_test_db: PostgresManager) -> None:
        service = AnalyticsService(analytics_test_db)
        overview = service.get_executive_overview(
            company_id="comp-shree-1",
            period_preset="last_30_days",
            reference_date=date(2024, 10, 15),
        )
        assert overview["period_label"] == "Last 30 days"
        assert overview["prior_period_label"] == "prior 30 days"
        assert overview["kpis"]["sales"]["raw_value"] == 1840000.0

    def test_executive_overview_custom_range(self, analytics_test_db: PostgresManager) -> None:
        service = AnalyticsService(analytics_test_db)
        overview = service.get_executive_overview(
            company_id="comp-shree-1",
            period_preset="custom",
            custom_start="2024-10-01",
            custom_end="2024-10-15",
        )
        assert "1st Oct to 15th Oct 2024" in overview["period_label"]
        assert overview["kpis"]["sales"]["raw_value"] == 1840000.0

    def test_slowest_paying_customers(self, analytics_test_db: PostgresManager) -> None:
        service = AnalyticsService(analytics_test_db)
        result = service.get_slowest_paying_customers("comp-shree-1")
        assert "slowest_customer" in result
        assert "narrative_response" in result
        assert "Vardhman Packaging" in result["narrative_response"]

    def test_unpaid_invoices(self, analytics_test_db: PostgresManager) -> None:
        service = AnalyticsService(analytics_test_db)
        unpaid = service.get_unpaid_invoices("comp-shree-1", reference_date=date(2024, 10, 15))
        # INV-102 has remaining balance 250,000, due 01-10-2024 (14 days overdue)
        assert len(unpaid) == 1
        assert unpaid[0]["bill_ref"] == "INV-102"
        assert unpaid[0]["party_name"] == "Apex Polymers"
        assert unpaid[0]["outstanding_amount"] == 250000.0
        assert unpaid[0]["days_overdue"] == 14
