"""Tests for CanonicalPollerRunner, ETL configuration, and Canonical Domain Model pipeline."""

from __future__ import annotations

from datetime import date, datetime
import os
import re
import sqlite3
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend_ETL.api import create_app
from backend_ETL.canonical_runner import (
    CanonicalPollerRunner,
    build_upsert_query,
)
from backend_ETL.canonical_schema import CANONICAL_DDL_STATEMENTS
from backend_ETL.config import ETLConfig, load_backend_config
from backend_ETL.db import PostgresManager
from backend_ETL.schema import PG_DDL_STATEMENTS

# ─── SQLite Test Adapter ─────────────────────────────────────────────────────────


class _RunnerSQLiteCursor:
    """Translates PostgreSQL DDL & queries for in-memory SQLite testing."""

    def __init__(self, raw_cur: sqlite3.Cursor) -> None:
        self._cur = raw_cur

    @staticmethod
    def _translate_sql(sql: str) -> str:
        if "DROP CONSTRAINT" in sql.upper():
            return "SELECT 1"
        s = sql.replace("%s", "?")
        s = s.replace("BIGSERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
        s = s.replace("TIMESTAMPTZ DEFAULT NOW()", "TEXT DEFAULT CURRENT_TIMESTAMP")
        s = s.replace("TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP", "TEXT DEFAULT CURRENT_TIMESTAMP")
        s = s.replace("TIMESTAMPTZ", "TEXT")
        s = s.replace("NOW()", "CURRENT_TIMESTAMP")
        s = s.replace("CREATE OR REPLACE VIEW", "CREATE VIEW IF NOT EXISTS")
        # Strip regex CHECK constraints since SQLite doesn't natively support '~' operator
        s = re.sub(r"CHECK\s*\([^)]*~[^)]*\)", "", s)
        return s

    @staticmethod
    def _adapt_params(params: tuple[Any, ...] | list[Any]) -> tuple[Any, ...]:
        return tuple(
            p.isoformat() if isinstance(p, (date, datetime)) else p
            for p in params
        )

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        return self._cur.execute(self._translate_sql(sql), self._adapt_params(params))

    def executemany(self, sql: str, seq_of_params: list[tuple[Any, ...]]) -> Any:
        return self._cur.executemany(
            self._translate_sql(sql), [self._adapt_params(p) for p in seq_of_params]
        )

    def fetchone(self) -> Any:
        return self._cur.fetchone()

    def fetchall(self) -> list[Any]:
        return self._cur.fetchall()

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount

    def close(self) -> None:
        self._cur.close()


class _RunnerSQLiteConn:
    def __init__(self, raw_conn: sqlite3.Connection) -> None:
        self._conn = raw_conn
        self._conn.row_factory = sqlite3.Row

    def cursor(self) -> _RunnerSQLiteCursor:
        return _RunnerSQLiteCursor(self._conn.cursor())

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()


@pytest.fixture()
def in_memory_db() -> PostgresManager:
    raw_conn = sqlite3.connect(":memory:", check_same_thread=False)
    compat_conn = _RunnerSQLiteConn(raw_conn)
    db = PostgresManager(conn_factory=lambda: compat_conn, use_pool=False)
    # Bootstrap Bronze and Canonical tables into SQLite
    with db.connection() as conn:
        cur = conn.cursor()
        for stmt in PG_DDL_STATEMENTS:
            cur.execute(stmt)
        for stmt in CANONICAL_DDL_STATEMENTS:
            cur.execute(stmt)
        cur.close()
    return db


# ─── 1. Configuration Unit Tests ────────────────────────────────────────────────


def test_etl_config_defaults():
    cfg = ETLConfig()
    assert cfg.enabled is True
    assert cfg.execution_mode == "polling"
    assert cfg.polling_interval_seconds == 30
    assert cfg.max_batch_vouchers == 2000


def test_etl_config_env_overrides():
    env = {
        "BACKEND_ETL_ENABLED": "false",
        "BACKEND_ETL_EXECUTION_MODE": "manual",
        "BACKEND_ETL_POLLING_INTERVAL_SECONDS": "60",
        "BACKEND_ETL_MAX_BATCH_VOUCHERS": "500",
    }
    with patch.dict(os.environ, env):
        bcfg = load_backend_config()
        assert bcfg.etl.enabled is False
        assert bcfg.etl.execution_mode == "manual"
        assert bcfg.etl.polling_interval_seconds == 60
        assert bcfg.etl.max_batch_vouchers == 500


# ─── 2. Query Builder Unit Tests ────────────────────────────────────────────────


def test_build_upsert_query_single_conflict():
    sql = build_upsert_query(
        "canonical_companies",
        ("company_id", "name", "books_from"),
        conflict_target="company_id",
    )
    assert "INSERT INTO canonical_companies (company_id, name, books_from)" in sql
    assert (
        "ON CONFLICT (company_id) DO UPDATE SET "
        "name = EXCLUDED.name, books_from = EXCLUDED.books_from"
    ) in sql


def test_build_upsert_query_multi_column_conflict():
    sql = build_upsert_query(
        "canonical_party_identifiers",
        ("party_ref", "id_type", "value", "confidence", "source"),
        conflict_target=("party_ref", "id_type", "value"),
    )
    assert "ON CONFLICT (party_ref, id_type, value) DO UPDATE SET" in sql
    assert "confidence = EXCLUDED.confidence" in sql
    assert "source = EXCLUDED.source" in sql


def test_build_upsert_query_no_conflict():
    sql = build_upsert_query(
        "canonical_bill_events",
        ("voucher_ref", "company_id", "amount"),
        conflict_target=None,
    )
    assert "ON CONFLICT" not in sql
    assert "INSERT INTO canonical_bill_events" in sql


# ─── 3. Poller Lifecycle Unit Tests ─────────────────────────────────────────────


def test_poller_start_stop_lifecycle(in_memory_db: PostgresManager):
    cfg = ETLConfig(enabled=True, execution_mode="polling", polling_interval_seconds=10)
    runner = CanonicalPollerRunner(db=in_memory_db, cfg=cfg)

    assert runner._thread is None
    runner.start()
    assert runner._thread is not None
    assert runner._thread.is_alive()

    # Calling start again should not start a second thread
    old_thread = runner._thread
    runner.start()
    assert runner._thread is old_thread

    runner.stop(timeout=2.0)
    assert runner._thread is None


def test_poller_does_not_start_when_disabled_or_manual(in_memory_db: PostgresManager):
    # Disabled
    runner_disabled = CanonicalPollerRunner(
        db=in_memory_db,
        cfg=ETLConfig(enabled=False, execution_mode="polling"),
    )
    runner_disabled.start()
    assert runner_disabled._thread is None

    # Manual mode
    runner_manual = CanonicalPollerRunner(
        db=in_memory_db,
        cfg=ETLConfig(enabled=True, execution_mode="manual"),
    )
    runner_manual.start()
    assert runner_manual._thread is None


# ─── 4. End-to-End Pipeline Transformation Test ────────────────────────────────


def test_end_to_end_canonical_transformation(in_memory_db: PostgresManager):
    company_id = "comp-guid-001"

    # Seed Bronze tables with sample data
    with in_memory_db.connection() as conn:
        cur = conn.cursor()
        # 1. Company
        cur.execute(
            """
            INSERT INTO companies (
                guid, name, books_from, starting_from, ending_at, gstin, alter_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                company_id,
                "Apex Tech Solutions",
                "20240401",
                "20240401",
                "20250331",
                "27AABCU9603R1ZM",
                10,
            ),
        )

        # 2. Groups (Multi-level)
        cur.execute(
            """
            INSERT INTO groups (guid, company_id, name, parent, alter_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            ("grp-01", company_id, "Current Assets", "Primary", 101),
        )
        cur.execute(
            """
            INSERT INTO groups (guid, company_id, name, parent, alter_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            ("grp-02", company_id, "Sundry Debtors", "Current Assets", 102),
        )

        # 3. Ledgers (with PII and GSTIN)
        cur.execute(
            """
            INSERT INTO ledgers (
                guid, company_id, name, parent, opening_balance, closing_balance,
                gst_registration_type, tax_classification, alter_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                "led-01",
                company_id,
                "Acme Corporation",
                "Sundry Debtors",
                "50000.00",
                "75000.00",
                "Regular",
                "Taxable",
                201,
            ),
        )
        cur.execute(
            """
            INSERT INTO ledgers (
                guid, company_id, name, parent, opening_balance, closing_balance, alter_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            ("led-02", company_id, "Sales Account", "Sales Accounts", "0.00", "200000.00", 202),
        )

        # 4. Voucher with ledger entries and inventory entries
        cur.execute(
            """
            INSERT INTO vouchers (
                guid, company_id, date, voucher_type_name, voucher_number, party_ledger_name,
                is_cancelled, alter_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            ("vch-001", company_id, "20240515", "Sales", "INV-1001", "Acme Corporation", 0, 301),
        )
        cur.execute(
            """
            INSERT INTO ledger_entries (
                voucher_guid, ledger_name, amount, is_deemed_positive,
                bill_ref, bill_type, bill_due_date, bill_amount
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                "vch-001",
                "Acme Corporation",
                "-25000.00",
                1,
                "INV-1001",
                "New Ref",
                "20240615",
                "-25000.00",
            ),
        )
        cur.execute(
            """
            INSERT INTO ledger_entries (
                voucher_guid, ledger_name, amount, is_deemed_positive
            ) VALUES (%s, %s, %s, %s)
            """,
            ("vch-001", "Sales Account", "25000.00", 0),
        )
        cur.execute(
            """
            INSERT INTO inventory_entries (
                voucher_guid, stock_item_name, billed_qty, actual_qty, rate, amount
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """,
            ("vch-001", "Widget Pro", "5", "5", "5000.00", "25000.00"),
        )
        cur.close()

    runner = CanonicalPollerRunner(db=in_memory_db, cfg=ETLConfig())
    res = runner.run_once(company_id=company_id)

    assert res["status"] == "ok"
    assert res["companies_processed"] == 1
    assert company_id in res["company_ids"]
    assert res["counts"]["companies"] == 1
    assert res["counts"]["groups"] == 2
    assert res["counts"]["ledgers"] == 2
    assert res["counts"]["vouchers"] == 1

    # Verify Silver Canonical records
    with in_memory_db.connection() as conn:
        cur = conn.cursor()

        # Company check: date normalized to SQL DATE (ISO YYYY-MM-DD or date object)
        cur.execute("SELECT * FROM canonical_companies WHERE company_id = %s", (company_id,))
        c = dict(cur.fetchone())
        assert c["name"] == "Apex Tech Solutions"
        assert c["books_from"] in ("2024-04-01", date(2024, 4, 1))
        assert c["books_to"] in ("2025-03-31", date(2025, 3, 31))

        # Account groups check: parent chain populated
        cur.execute("SELECT * FROM canonical_account_groups WHERE accountgroup_id = 'grp-02'")
        g = dict(cur.fetchone())
        assert g["name"] == "Sundry Debtors"
        assert g["parent_ref"] == "grp-01"
        assert "Current Assets > Sundry Debtors" in g["parent_chain"]

        # Accounts check: role classified as customer
        cur.execute("SELECT * FROM canonical_accounts WHERE account_id = 'led-01'")
        acc = dict(cur.fetchone())
        assert acc["name"] == "Acme Corporation"
        assert acc["classification_role"] == "customer"
        assert acc["group_ref"] == "grp-02"

        # Opening balance check: books_from populated as as_of
        cur.execute("SELECT * FROM canonical_opening_balances WHERE account_ref = 'led-01'")
        ob = dict(cur.fetchone())
        assert ob["as_of"] in ("2024-04-01", date(2024, 4, 1))
        assert float(ob["amount"]) == 50000.0

        # Voucher check: date normalized to SQL DATE
        cur.execute("SELECT * FROM canonical_vouchers WHERE voucher_id = 'vch-001'")
        vch = dict(cur.fetchone())
        assert vch["date"] in ("2024-05-15", date(2024, 5, 15))
        assert vch["party_ref"] == "led-01"  # Resolved name to GUID
        assert vch["lifecycle"] == "active"

        # Postings check: 2 decoupled postings
        cur.execute(
            "SELECT * FROM canonical_postings "
            "WHERE voucher_ref = 'vch-001' ORDER BY line_ordinal ASC"
        )
        posts = [dict(p) for p in cur.fetchall()]
        assert len(posts) == 2
        assert posts[0]["account_ref"] == "led-01"
        assert posts[0]["line_ordinal"] == 1
        assert posts[1]["account_ref"] == "led-02"

        # Bill events check: decoupled bill event
        cur.execute("SELECT * FROM canonical_bill_events WHERE voucher_ref = 'vch-001'")
        bills = [dict(b) for b in cur.fetchall()]
        assert len(bills) == 1
        assert bills[0]["bill_ref"] == "INV-1001"
        assert bills[0]["kind"] == "new"
        assert bills[0]["due_date"] in ("2024-06-15", date(2024, 6, 15))

        # Inventory lines check
        cur.execute("SELECT * FROM canonical_inventory_lines WHERE voucher_guid = 'vch-001'")
        invs = [dict(i) for i in cur.fetchall()]
        assert len(invs) == 1
        assert invs[0]["item_ref"] == "Widget Pro"
        assert float(invs[0]["amount"]) == 25000.0

        # Sync cursors check: watermarks recorded
        cur.execute(
            "SELECT entity, cursor_value FROM canonical_sync_cursors WHERE company_id = %s",
            (company_id,),
        )
        cursors = {r["entity"]: r["cursor_value"] for r in (dict(x) for x in cur.fetchall())}
        assert cursors["groups"] == "102"
        assert cursors["ledgers"] == "202"
        assert cursors["vouchers"] == "301"

        cur.close()

    # Second run should find 0 delta (idempotent watermark skipping)
    res2 = runner.run_once(company_id=company_id)
    assert res2["counts"].get("groups", 0) == 0
    assert res2["counts"].get("ledgers", 0) == 0
    assert res2["counts"].get("vouchers", 0) == 0


# ─── 5. API Multi-Tenant Security Tests ─────────────────────────────────────────


def test_api_canonical_transform_endpoint_security(in_memory_db: PostgresManager):
    app = create_app(db=in_memory_db, start_poller=False)
    client = TestClient(app)

    # Issue token for client A
    issued_a = in_memory_db.issue_token_for_client(description="Client A")
    token_a = issued_a["token"]
    cid_a = issued_a["client_id"]
    in_memory_db.create_client(cid_a, "Client Alpha")

    # Issue token for client B
    issued_b = in_memory_db.issue_token_for_client(description="Client B")
    token_b = issued_b["token"]
    cid_b = issued_b["client_id"]
    in_memory_db.create_client(cid_b, "Client Beta")

    # Map company 1 to client A
    with in_memory_db.connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO companies (guid, name, books_from) "
            "VALUES ('comp-A', 'Alpha Ltd', '20240401')"
        )
        cur.close()
    in_memory_db.map_client_to_companies(cid_a, ["comp-A"])

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 1. Reject without token (403)
    resp = client.post(f"/api/v1/canonical/transform?client_id={cid_a}")
    assert resp.status_code == 403

    # 2. Reject client B attempting to transform client A's company (403)
    resp_cross = client.post(
        f"/api/v1/canonical/transform?client_id={cid_b}&company_id=comp-A",
        headers=headers_b,
    )
    assert resp_cross.status_code == 403
    assert "Forbidden" in resp_cross.json()["detail"]

    # 3. Allow client A to transform own company (200)
    resp_ok = client.post(
        f"/api/v1/canonical/transform?client_id={cid_a}&company_id=comp-A",
        headers=headers_a,
    )
    assert resp_ok.status_code == 200
    data = resp_ok.json()
    assert data["status"] == "ok"
    assert data["client_id"] == cid_a
    assert "comp-A" in data["company_ids"]
