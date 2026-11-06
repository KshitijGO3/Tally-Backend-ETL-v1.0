"""Integration tests for Analytics, Ask O3 Agent, and Frontend endpoints."""

from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend_ETL.api import create_app
from backend_ETL.canonical_schema import CANONICAL_DDL_STATEMENTS
from backend_ETL.config import BackendConfig
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
        s = re.sub(r"TIMESTAMPTZ\s+NOT\s+NULL\s+DEFAULT\s+(NOW\(\)|CURRENT_TIMESTAMP)", "TEXT DEFAULT CURRENT_TIMESTAMP", s, flags=re.IGNORECASE)
        s = re.sub(r"TIMESTAMPTZ\s+DEFAULT\s+(NOW\(\)|CURRENT_TIMESTAMP)", "TEXT DEFAULT CURRENT_TIMESTAMP", s, flags=re.IGNORECASE)
        s = s.replace("TIMESTAMPTZ DEFAULT NOW()", "TEXT DEFAULT CURRENT_TIMESTAMP")
        s = s.replace("TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP", "TEXT DEFAULT CURRENT_TIMESTAMP")
        s = s.replace("TIMESTAMPTZ", "TEXT")
        s = s.replace("NOW()", "CURRENT_TIMESTAMP")
        s = s.replace("CREATE OR REPLACE VIEW", "CREATE VIEW IF NOT EXISTS")
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

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount

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
def client() -> TestClient:
    raw_conn = sqlite3.connect(":memory:", check_same_thread=False)
    compat_conn = _SQLiteConnAdapter(raw_conn)
    db = PostgresManager(conn_factory=lambda: compat_conn, use_pool=False)

    with db.connection() as conn:
        cur = conn.cursor()
        for stmt in PG_DDL_STATEMENTS:
            cur.execute(stmt)
        for stmt in CANONICAL_DDL_STATEMENTS:
            cur.execute(stmt)

        # Seed company
        cur.execute(
            """
            INSERT INTO canonical_companies (company_id, name, books_from)
            VALUES ('comp-shree-1', 'Shree Polychem', '2024-04-01')
            """
        )
        today = date.today()
        d_today_10 = today.replace(day=10).strftime("%Y-%m-%d")
        d_today_14 = today.replace(day=14).strftime("%Y-%m-%d")
        d_today_08 = today.replace(day=8).strftime("%Y-%m-%d")
        d_today_recent = today.replace(day=min(today.day, 15)).strftime("%Y-%m-%d")

        cur.execute(
            """
            INSERT INTO canonical_vouchers (voucher_id, company_id, date, kind, base_type, lifecycle)
            VALUES ('vch-recent', 'comp-shree-1', %s, 'Receipt', 'Receipt', 'active')
            """,
            (d_today_recent,),
        )
        cur.execute(
            """
            INSERT INTO canonical_daily_movements (company_id, date, base_type, account_role, is_debit, total_amount, voucher_count)
            VALUES 
            ('comp-shree-1', %s, 'Sales', 'customer', 1, 1840000.0, 1),
            ('comp-shree-1', %s, 'Receipt', 'bank', 1, 1420000.0, 1),
            ('comp-shree-1', %s, 'Purchase', 'supplier', 0, 1510000.0, 1)
            """,
            (d_today_10, d_today_14, d_today_08),
        )
        cur.close()

    cfg = BackendConfig()
    cfg.etl.enabled = False  # Disable background thread during testing
    app = create_app(db=db, start_poller=False, config=cfg)
    return TestClient(app)


class TestFullApiFlow:
    def test_frontend_routes_serve_html(self, client: TestClient) -> None:
        login_res = client.get("/login")
        assert login_res.status_code == 200
        assert "Welcome to O3" in login_res.text

        dash_res = client.get("/dashboard")
        assert dash_res.status_code == 200
        assert "Ask O3" in dash_res.text

        root_res = client.get("/")
        assert root_res.status_code == 200
        assert "Ask O3" in root_res.text

    def test_auth_and_analytics_flow(self, client: TestClient) -> None:
        # 1. Register
        reg_res = client.post(
            "/api/v1/auth/register",
            json={
                "client_name": "Shree Polychem Org",
                "full_name": "Manoj Kumar",
                "email": "manoj@shree.com",
                "password": "Password@123",
            },
        )
        assert reg_res.status_code == 200
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Get Profile
        me_res = client.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["user"]["email"] == "manoj@shree.com"

        # 3. Overview Analytics (Default MTD)
        overview_res = client.get(
            "/api/v1/analytics/overview?period=mtd&company_id=comp-shree-1",
            headers=headers,
        )
        assert overview_res.status_code == 200
        data = overview_res.json()
        assert data["company_name"] == "Shree Polychem"
        assert "Good morning, Manoj." in data["greeting_title"]
        assert "₹ 18.40 L" in data["kpis"]["sales"]["formatted_value"]

        # 3b. Overview Analytics (Custom Range)
        today = date.today()
        custom_start_str = today.replace(day=1).strftime("%Y-%m-%d")
        custom_end_str = today.strftime("%Y-%m-%d")
        custom_res = client.get(
            f"/api/v1/analytics/overview?period=custom&company_id=comp-shree-1&start_date={custom_start_str}&end_date={custom_end_str}",
            headers=headers,
        )
        assert custom_res.status_code == 200
        assert "₹ 18.40 L" in custom_res.json()["kpis"]["sales"]["formatted_value"]

        # 4. Sync Status
        sync_res = client.get(
            "/api/v1/analytics/sync-status?company_id=comp-shree-1",
            headers=headers,
        )
        assert sync_res.status_code == 200
        assert "Books updated to 15 Oct" in sync_res.json()["books_updated_label"]

        # 5. Ask O3 Chat
        chat_res = client.post(
            "/api/v1/agent/chat",
            json={
                "company_id": "comp-shree-1",
                "message": "How were collections this month?",
            },
            headers=headers,
        )
        assert chat_res.status_code == 200
        assert "Collections are" in chat_res.json()["content"]

        # 6. Retrieve History
        hist_res = client.get(
            "/api/v1/agent/messages?company_id=comp-shree-1",
            headers=headers,
        )
        assert hist_res.status_code == 200
        messages = hist_res.json()["messages"]
        assert len(messages) >= 2

        # 7. Clear Conversation
        del_res = client.delete(
            "/api/v1/agent/messages?company_id=comp-shree-1",
            headers=headers,
        )
        assert del_res.status_code == 200

        hist_after = client.get(
            "/api/v1/agent/messages?company_id=comp-shree-1",
            headers=headers,
        )
        assert len(hist_after.json()["messages"]) == 0

    def test_tally_sync_preseeded_email_activation_flow(self, client: TestClient) -> None:
        """Verifies real-world flow where Tally Sync registers email first, and user activates on dashboard."""
        # 1. Simulate Tally Sync creating the client with contact_email and mapping company
        db: PostgresManager = client.app.state.db
        with db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO clients (client_id, client_name, contact_email, created_at, updated_at)
                VALUES ('client-preseed-1', 'Shree Polychem Preseeded', 'owner@polychem.com', '2024-04-01T00:00:00Z', '2024-04-01T00:00:00Z')
                """
            )
            cur.execute(
                """
                INSERT INTO client_companies (client_id, company_guid, created_at)
                VALUES ('client-preseed-1', 'comp-shree-1', '2024-04-01T00:00:00Z')
                """
            )
            cur.close()

        # 2. User tries to sign in without setting a password first -> gets guided 403 message
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": "owner@polychem.com", "password": "AnyPassword"},
        )
        assert login_res.status_code == 403
        assert "Tally Sync has synced books" in login_res.json()["detail"]
        assert "password has not been set yet" in login_res.json()["detail"]

        # 3. User uses 'Set Password / Activate' -> seamlessly links to preseeded client and companies
        activate_res = client.post(
            "/api/v1/auth/register",
            json={
                "client_name": "Shree Polychem Preseeded",
                "full_name": "Manoj Owner",
                "email": "owner@polychem.com",
                "password": "SecurePassword@123",
            },
        )
        assert activate_res.status_code == 200
        token = activate_res.json()["access_token"]
        user_info = activate_res.json()["user"]
        # Verify the user is bound to the Tally Sync client, NOT a new orphan client
        assert user_info["client_id"] == "client-preseed-1"

        # 4. User immediately accesses the dashboard with inherited company access
        headers = {"Authorization": f"Bearer {token}"}
        me_res = client.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        accessible = me_res.json()["user"]["accessible_companies"]
        assert any((c["company_id"] if isinstance(c, dict) else c) == "comp-shree-1" for c in accessible)

        # 5. User immediately gets analytics for their synced company
        overview_res = client.get("/api/v1/analytics/overview?period=mtd", headers=headers)
        assert overview_res.status_code == 200
        assert overview_res.json()["company_name"] == "Shree Polychem"

    def test_multi_company_accessible_list_with_names(self, client: TestClient) -> None:
        """Verifies that a user with multiple companies gets all companies with company_id and company_name in /api/v1/auth/me."""
        db: PostgresManager = client.app.state.db
        with db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO canonical_companies (company_id, name, books_from)
                VALUES 
                    ('comp-alpha-1', 'Alpha Chemicals Ltd', '2024-04-01'),
                    ('comp-beta-2', 'Beta Petrochem Pvt Ltd', '2024-04-01'),
                    ('comp-gamma-3', 'Gamma Solvents Corp', '2024-04-01')
                """
            )
            cur.execute(
                """
                INSERT INTO clients (client_id, client_name, contact_email, created_at, updated_at)
                VALUES ('client-multi-3', 'Alpha Group', 'admin@alphagroup.com', '2024-04-01T00:00:00Z', '2024-04-01T00:00:00Z')
                """
            )
            for cid in ["comp-alpha-1", "comp-beta-2", "comp-gamma-3"]:
                cur.execute(
                    """
                    INSERT INTO client_companies (client_id, company_guid, created_at)
                    VALUES ('client-multi-3', %s, '2024-04-01T00:00:00Z')
                    """,
                    (cid,),
                )
            cur.close()

        # Register user for client-multi-3
        reg_res = client.post(
            "/api/v1/auth/register",
            json={
                "client_name": "Alpha Group",
                "full_name": "Alpha Admin",
                "email": "admin@alphagroup.com",
                "password": "SecurePassword@123",
            },
        )
        assert reg_res.status_code == 200
        token = reg_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Check /api/v1/auth/me returns all 3 companies with IDs and names
        me_res = client.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        accessible = me_res.json()["user"]["accessible_companies"]
        assert len(accessible) == 3

        expected_map = {
            "comp-alpha-1": "Alpha Chemicals Ltd",
            "comp-beta-2": "Beta Petrochem Pvt Ltd",
            "comp-gamma-3": "Gamma Solvents Corp",
        }
        for item in accessible:
            assert item["company_id"] in expected_map
            assert item["company_name"] == expected_map[item["company_id"]]

