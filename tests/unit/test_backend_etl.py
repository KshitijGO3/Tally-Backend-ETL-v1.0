"""Unit and API tests for src/backend_ETL PostgreSQL schema, security, and CRUD API."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend_ETL.api import create_app
from backend_ETL.config import BackendConfig, load_backend_config
from backend_ETL.db import PostgresManager, build_insert_sql, build_upsert_sql
from backend_ETL.main import parse_args, run_cli_command
from backend_ETL.schema import (
    CHILD_TABLE_SPECS,
    COMPANY_SPEC,
    MASTER_TABLE_SPECS,
    PG_DDL_STATEMENTS,
    VOUCHER_SPEC,
)
from tally_core.db import DBManager


class _SQLiteCompatCursor:
    """Adapter cursor translating PostgreSQL %s placeholders and DDL for SQLite testing."""

    def __init__(self, raw_cursor: sqlite3.Cursor) -> None:
        self._cur = raw_cursor

    @staticmethod
    def _translate_sql(sql: str) -> str:
        translated = sql.replace("%s", "?")
        translated = translated.replace(
            "BIGSERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT"
        )
        translated = translated.replace(
            "CREATE OR REPLACE VIEW VoucherType",
            "CREATE VIEW IF NOT EXISTS VoucherType",
        )
        return translated

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        return self._cur.execute(self._translate_sql(sql), params)

    def executemany(self, sql: str, seq_of_params: list[tuple[Any, ...]]) -> Any:
        return self._cur.executemany(self._translate_sql(sql), seq_of_params)

    def fetchone(self) -> Any:
        return self._cur.fetchone()

    def fetchall(self) -> list[Any]:
        return self._cur.fetchall()

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount

    def close(self) -> None:
        self._cur.close()


class _SQLiteCompatConnection:
    """Connection wrapper around sqlite3.Connection providing dict rows and %s compatibility."""

    def __init__(self, raw_conn: sqlite3.Connection) -> None:
        self._conn = raw_conn
        self._conn.row_factory = sqlite3.Row

    def cursor(self) -> _SQLiteCompatCursor:
        return _SQLiteCompatCursor(self._conn.cursor())

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()


@pytest.fixture()
def pg_manager() -> PostgresManager:
    raw_conn = sqlite3.connect(":memory:", check_same_thread=False)
    compat_conn = _SQLiteCompatConnection(raw_conn)
    manager = PostgresManager(conn_factory=lambda: compat_conn, use_pool=False)
    manager.bootstrap()
    return manager


@pytest.fixture()
def client(pg_manager: PostgresManager) -> TestClient:
    app = create_app(db=pg_manager)
    return TestClient(app)


@pytest.fixture()
def onboarded_auth(pg_manager: PostgresManager, client: TestClient) -> dict[str, str]:
    """Issues a CLI token, registers the client via API, and creates a mapped company."""
    issued = pg_manager.issue_token_for_client(description="Primary Test Client")
    client_id = issued["client_id"]
    headers = {"Authorization": f"Bearer {issued['token']}"}

    reg_res = client.post(
        "/api/v1/clients",
        params={"client_id": client_id},
        headers=headers,
        json={"client_name": "Bhrama Enterprises Client", "contact_email": "ops@bhrama.com"},
    )
    assert reg_res.status_code == 200

    company_guid = "comp-guid-bhrama"
    comp_res = client.post(
        "/api/v1/companies",
        params={"client_id": client_id},
        headers=headers,
        json={
            "guid": company_guid,
            "name": "Bhrama Enterprises",
            "books_from": "2025-04-01",
            "starting_from": "2025-04-01",
            "gstin": "27AABCU9603R1ZM",
            "master_id": 1,
            "alter_id": 10,
        },
    )
    assert comp_res.status_code == 200
    return {
        "client_id": client_id,
        "token": issued["token"],
        "company_guid": company_guid,
    }


def test_schema_parity_with_sqlite_core_tables():
    """Verify all 20 core tables in backend_ETL match the column definitions of tally_core.db."""
    sqlite_db = DBManager(":memory:")
    sqlite_db.bootstrap()
    cur = sqlite_db._conn.cursor()

    all_specs = [
        COMPANY_SPEC,
        *MASTER_TABLE_SPECS.values(),
        VOUCHER_SPEC,
        *CHILD_TABLE_SPECS.values(),
    ]
    assert len(all_specs) == 20

    for spec in all_specs:
        cur.execute(f"PRAGMA table_info({spec.name})")
        # Exclude client-side SQLite tracking column 'is_replicated'
        sqlite_cols = [row[1] for row in cur.fetchall() if row[1] != "is_replicated"]
        if spec.name in CHILD_TABLE_SPECS:
            assert sqlite_cols == ["id", *spec.columns], f"Mismatch on child table {spec.name}"
        else:
            assert sqlite_cols == list(spec.columns), f"Mismatch on table {spec.name}"

    sqlite_db.close()


def test_postgres_sql_builders():
    upsert_sql = build_upsert_sql(COMPANY_SPEC)
    assert "INSERT INTO companies" in upsert_sql
    assert "ON CONFLICT (guid) DO UPDATE SET" in upsert_sql
    assert "%s" in upsert_sql

    insert_sql = build_insert_sql(CHILD_TABLE_SPECS["ledger_entries"])
    assert "INSERT INTO ledger_entries" in insert_sql
    assert "%s" in insert_sql
    assert any("BIGSERIAL PRIMARY KEY" in stmt for stmt in PG_DDL_STATEMENTS)


def test_backend_config_dsn(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("POSTGRES_HOST", "db.internal")
    monkeypatch.setenv("POSTGRES_PORT", "5433")
    monkeypatch.setenv("POSTGRES_USER", "tally_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "secret")
    monkeypatch.setenv("POSTGRES_DB", "tally_prod")
    cfg: BackendConfig = load_backend_config()
    assert cfg.get_dsn() == "postgresql://tally_user:secret@db.internal:5433/tally_prod"


def test_cli_token_lifecycle_and_one_token_per_client(
    pg_manager: PostgresManager, capsys: pytest.CaptureFixture[str]
):
    args_create = parse_args(
        ["--create-token", "--client-id", "cli-client-01", "--description", "Main"]
    )
    assert run_cli_command(pg_manager, args_create) == 0
    out = capsys.readouterr().out
    assert "Client ID : cli-client-01" in out
    assert "API Token : trs_" in out

    # One token can only be assigned to one client
    with pytest.raises(ValueError, match="already has a token assigned"):
        pg_manager.issue_token_for_client(client_id="cli-client-01")

    # Rotate token via CLI
    args_rotate = parse_args(["--rotate-token", "--client-id", "cli-client-01"])
    assert run_cli_command(pg_manager, args_rotate) == 0
    rotate_out = capsys.readouterr().out
    new_token = [
        line.split(":", 1)[1].strip()
        for line in rotate_out.splitlines()
        if line.startswith("New Token")
    ][0]
    assert pg_manager.verify_bearer_token(new_token) == {"client_id": "cli-client-01"}

    # Revoke token via CLI
    args_revoke = parse_args(["--revoke-token", "--client-id", "cli-client-01"])
    assert run_cli_command(pg_manager, args_revoke) == 0
    assert pg_manager.verify_bearer_token(new_token) is None


def test_security_onboarding_order_and_three_way_403_enforcement(
    pg_manager: PostgresManager, client: TestClient
):
    # 1. Missing Authorization header -> 403
    no_auth = client.get("/api/v1/companies", params={"client_id": "any"})
    assert no_auth.status_code == 403

    # 2. Issue token for Client A
    issued_a = pg_manager.issue_token_for_client(client_id="client-a")
    headers_a = {"Authorization": f"Bearer {issued_a['token']}"}

    # 3. Attempting company creation BEFORE POST /api/v1/clients -> 403
    premature_comp = client.post(
        "/api/v1/companies",
        params={"client_id": "client-a"},
        headers=headers_a,
        json={"guid": "comp-a", "name": "Company A"},
    )
    assert premature_comp.status_code == 403
    assert "Client must be created" in premature_comp.json()["detail"]

    # 4. Token A used with wrong client_id -> 403
    wrong_client = client.post(
        "/api/v1/clients",
        params={"client_id": "client-b"},
        headers=headers_a,
        json={"client_name": "Spoofed Client"},
    )
    assert wrong_client.status_code == 403

    # 5. Register Client A and create Company A
    assert (
        client.post(
            "/api/v1/clients",
            params={"client_id": "client-a"},
            headers=headers_a,
            json={"client_name": "Client A"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/companies",
            params={"client_id": "client-a"},
            headers=headers_a,
            json={"guid": "comp-a", "name": "Company A"},
        ).status_code
        == 200
    )

    # 6. Issue token and register Client B
    issued_b = pg_manager.issue_token_for_client(client_id="client-b")
    headers_b = {"Authorization": f"Bearer {issued_b['token']}"}
    assert (
        client.post(
            "/api/v1/clients",
            params={"client_id": "client-b"},
            headers=headers_b,
            json={"client_name": "Client B"},
        ).status_code
        == 200
    )

    # 7. Client B attempting to access or overwrite Client A's company/masters/vouchers -> 403
    assert (
        client.get(
            "/api/v1/companies",
            params={"client_id": "client-b", "guid": "comp-a"},
            headers=headers_b,
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/companies",
            params={"client_id": "client-b"},
            headers=headers_b,
            json={"guid": "comp-a", "name": "Hijack Company A"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/masters/batch",
            params={"client_id": "client-b", "company_id": "comp-a", "table_name": "ledgers"},
            headers=headers_b,
            json={"rows": [{"guid": "ldg-1", "name": "Cash"}]},
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/v1/watermarks",
            params={"client_id": "client-b", "company_id": "comp-a"},
            headers=headers_b,
        ).status_code
        == 403
    )


def test_health_and_companies_crud_query_params(
    client: TestClient, onboarded_auth: dict[str, str]
):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}

    client_id = onboarded_auth["client_id"]
    comp_guid = onboarded_auth["company_guid"]
    headers = {"Authorization": f"Bearer {onboarded_auth['token']}"}

    # Check client info endpoint includes mapped company_guids
    info_res = client.get("/api/v1/clients", params={"client_id": client_id}, headers=headers)
    assert info_res.status_code == 200
    assert comp_guid in info_res.json()["data"]["company_guids"]

    # Get by guid query param
    get_res = client.get(
        "/api/v1/companies",
        params={"client_id": client_id, "guid": comp_guid},
        headers=headers,
    )
    assert get_res.status_code == 200
    assert get_res.json()["data"]["name"] == "Bhrama Enterprises"

    # Update via query param
    put_res = client.put(
        "/api/v1/companies",
        params={"client_id": client_id, "guid": comp_guid},
        headers=headers,
        json={"alter_id": 25, "company_number": "10001"},
    )
    assert put_res.status_code == 200

    updated = client.get(
        "/api/v1/companies",
        params={"client_id": client_id, "guid": comp_guid},
        headers=headers,
    ).json()["data"]
    assert updated["alter_id"] == 25
    assert updated["company_number"] == "10001"

    # Delete via query param
    del_res = client.delete(
        "/api/v1/companies",
        params={"client_id": client_id, "guid": comp_guid},
        headers=headers,
    )
    assert del_res.status_code == 200
    assert (
        client.get(
            "/api/v1/companies",
            params={"client_id": client_id, "guid": comp_guid},
            headers=headers,
        ).status_code
        == 404
    )


def test_all_14_master_tables_crud_query_params(
    client: TestClient, onboarded_auth: dict[str, str]
):
    client_id = onboarded_auth["client_id"]
    company_id = onboarded_auth["company_guid"]
    headers = {"Authorization": f"Bearer {onboarded_auth['token']}"}

    for idx, table_name in enumerate(MASTER_TABLE_SPECS, start=1):
        guid = f"{table_name}-guid-1"
        batch_res = client.post(
            "/api/v1/masters/batch",
            params={"client_id": client_id, "company_id": company_id, "table_name": table_name},
            headers=headers,
            json={
                "rows": [
                    {
                        "guid": guid,
                        "name": f"Sample {table_name}",
                        "master_id": idx,
                        "alter_id": idx * 10,
                    }
                ]
            },
        )
        assert batch_res.status_code == 200, f"Failed batch upsert on {table_name}"
        assert batch_res.json()["upserted_count"] == 1

        # Fetch single record via query params
        single_res = client.get(
            "/api/v1/masters",
            params={
                "client_id": client_id,
                "company_id": company_id,
                "table_name": table_name,
                "guid": guid,
            },
            headers=headers,
        )
        assert single_res.status_code == 200
        assert single_res.json()["data"]["name"] == f"Sample {table_name}"

        # Update via query params
        put_res = client.put(
            "/api/v1/masters",
            params={
                "client_id": client_id,
                "company_id": company_id,
                "table_name": table_name,
                "guid": guid,
            },
            headers=headers,
            json={"name": f"Updated {table_name}", "alter_id": idx * 20},
        )
        assert put_res.status_code == 200

        # List with min_alter_id filter
        list_res = client.get(
            "/api/v1/masters",
            params={
                "client_id": client_id,
                "company_id": company_id,
                "table_name": table_name,
                "min_alter_id": idx * 20,
            },
            headers=headers,
        )
        assert list_res.status_code == 200
        assert list_res.json()["count"] == 1
        assert list_res.json()["data"][0]["name"] == f"Updated {table_name}"

    # Verify watermarks endpoint across all tables
    wm_res = client.get(
        "/api/v1/watermarks",
        params={"client_id": client_id, "company_id": company_id},
        headers=headers,
    )
    assert wm_res.status_code == 200
    tables_wm = wm_res.json()["tables"]
    assert tables_wm["ledgers"]["row_count"] == 1
    assert tables_wm["stock_items"]["row_count"] == 1

    # Delete a master record via query params
    del_res = client.delete(
        "/api/v1/masters",
        params={
            "client_id": client_id,
            "company_id": company_id,
            "table_name": "ledgers",
            "guid": "ledgers-guid-1",
        },
        headers=headers,
    )
    assert del_res.status_code == 200
    assert (
        client.get(
            "/api/v1/masters",
            params={
                "client_id": client_id,
                "company_id": company_id,
                "table_name": "ledgers",
                "guid": "ledgers-guid-1",
            },
            headers=headers,
        ).status_code
        == 404
    )


def test_vouchers_and_child_entries_crud_query_params(
    client: TestClient, onboarded_auth: dict[str, str]
):
    client_id = onboarded_auth["client_id"]
    company_id = onboarded_auth["company_guid"]
    headers = {"Authorization": f"Bearer {onboarded_auth['token']}"}
    vch_guid = "vch-sales-001"

    batch_payload = {
        "headers": [
            {
                "guid": vch_guid,
                "date": "2026-04-01",
                "voucher_type_name": "Sales",
                "voucher_number": "INV-001",
                "party_ledger_name": "Amar Enterprises",
                "is_invoice": True,
                "master_id": 101,
                "alter_id": 500,
            }
        ],
        "ledger_entries": [
            {
                "voucher_guid": vch_guid,
                "ledger_name": "Amar Enterprises",
                "amount": "-250000.00",
                "is_deemed_positive": True,
                "bill_ref": "INV-001",
                "bill_type": "New Ref",
                "bill_amount": "-250000.00",
            },
            {
                "voucher_guid": vch_guid,
                "ledger_name": "Sales",
                "amount": "250000.00",
                "is_deemed_positive": False,
            },
        ],
        "inventory_entries": [
            {
                "voucher_guid": vch_guid,
                "stock_item_name": "Laptop Pro",
                "billed_qty": "5",
                "actual_qty": "5",
                "rate": "50000.00",
                "amount": "250000.00",
                "unit": "Nos",
            }
        ],
        "cost_centre_allocations": [
            {
                "voucher_guid": vch_guid,
                "ledger_name": "Sales",
                "cost_category": "Primary Cost Category",
                "cost_centre_name": "Mumbai Branch",
                "amount": "250000.00",
                "is_deemed_positive": False,
            }
        ],
        "attendance_entries": [
            {
                "voucher_guid": vch_guid,
                "employee_name": "Rahul Sharma",
                "attendance_type": "Present",
                "value": "1",
            }
        ],
    }

    res = client.post(
        "/api/v1/vouchers/batch",
        params={"client_id": client_id, "company_id": company_id},
        headers=headers,
        json=batch_payload,
    )
    assert res.status_code == 200
    assert res.json()["upserted_count"] == 1

    # Fetch voucher with nested child entries via query params
    detail_res = client.get(
        "/api/v1/vouchers",
        params={"client_id": client_id, "company_id": company_id, "guid": vch_guid},
        headers=headers,
    )
    assert detail_res.status_code == 200
    vch_data = detail_res.json()["data"]
    assert vch_data["voucher_number"] == "INV-001"
    assert len(vch_data["ledger_entries"]) == 2
    assert len(vch_data["inventory_entries"]) == 1
    assert len(vch_data["cost_centre_allocations"]) == 1
    assert len(vch_data["attendance_entries"]) == 1

    # Direct child table query via /api/v1/voucher-entries
    le_res = client.get(
        "/api/v1/voucher-entries",
        params={
            "client_id": client_id,
            "voucher_guid": vch_guid,
            "child_table": "ledger_entries",
        },
        headers=headers,
    )
    assert le_res.status_code == 200
    assert le_res.json()["count"] == 2

    # Replace child entries via PUT /api/v1/voucher-entries
    replace_res = client.put(
        "/api/v1/voucher-entries",
        params={
            "client_id": client_id,
            "voucher_guid": vch_guid,
            "child_table": "ledger_entries",
        },
        headers=headers,
        json={
            "rows": [
                {
                    "ledger_name": "Amar Enterprises",
                    "amount": "-300000.00",
                    "is_deemed_positive": True,
                }
            ]
        },
    )
    assert replace_res.status_code == 200
    assert replace_res.json()["replaced_count"] == 1

    # Delete voucher and verify child entries are cleaned up (so voucher is no longer accessible)
    del_res = client.delete(
        "/api/v1/vouchers",
        params={"client_id": client_id, "company_id": company_id, "guid": vch_guid},
        headers=headers,
    )
    assert del_res.status_code == 200
    assert (
        client.get(
            "/api/v1/vouchers",
            params={"client_id": client_id, "company_id": company_id, "guid": vch_guid},
            headers=headers,
        ).status_code
        == 404
    )


def test_backend_etl_logging_setup(tmp_path: Any) -> None:
    """Verifies backend_ETL.logging_setup creates rotating file logs with the expected format."""
    from backend_ETL.logging_setup import get_default_log_dir, setup_logging

    log_dir = tmp_path / "logs"
    setup_logging(process_name="backend_unit_test", log_dir=log_dir, level="DEBUG")

    test_logger = logging.getLogger("backend_unit_test.sub")
    test_logger.info("Informational test entry")
    test_logger.warning("Warning test entry")

    log_file = log_dir / "backend_unit_test.log"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "Informational test entry" in content
    assert "Warning test entry" in content
    assert "backend_unit_test.sub" in content

    # Verify default log dir resolution
    default_dir = get_default_log_dir()
    assert default_dir is not None


def test_unassigned_token_creation_and_first_time_onboarding(
    pg_manager: PostgresManager, client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    """Tests the onboarding flow: admin creates unassigned token, client self-onboards."""
    # 1. Admin generates an unassigned token via CLI (no --client-id provided)
    args = parse_args(["--create-token", "--description", "Pending Client Onboarding"])
    assert run_cli_command(pg_manager, args) == 0
    cli_out = capsys.readouterr().out
    assert "<Unassigned - will be bound on first client registration>" in cli_out
    token = [
        line.split(":", 1)[1].strip()
        for line in cli_out.splitlines()
        if line.startswith("API Token")
    ][0]

    # Verify token exists in database but has no client_id yet
    token_status = pg_manager.verify_bearer_token(token)
    assert token_status is not None
    assert token_status["client_id"] is None

    # 2. Client onboards by calling POST /api/v1/clients with their unused token
    headers = {"Authorization": f"Bearer {token}"}
    reg_res = client.post(
        "/api/v1/clients",
        headers=headers,
        json={"client_name": "Acme Innovations Ltd", "contact_email": "admin@acme.com"},
    )
    assert reg_res.status_code == 200
    data = reg_res.json()["data"]
    assigned_client_id = data["client_id"]
    assert assigned_client_id is not None
    assert data["client_name"] == "Acme Innovations Ltd"

    # 3. Token is now permanently locked and bound to assigned_client_id
    token_status_after = pg_manager.verify_bearer_token(token)
    assert token_status_after is not None
    assert token_status_after["client_id"] == assigned_client_id

    # 4. Attempting to onboard another client with the same token is rejected
    second_reg = client.post(
        "/api/v1/clients",
        params={"client_id": "different-client-id"},
        headers=headers,
        json={"client_name": "Imposter Corp"},
    )
    assert second_reg.status_code == 403

    # 5. The onboarded client can now successfully manage companies
    comp_res = client.post(
        "/api/v1/companies",
        params={"client_id": assigned_client_id},
        headers=headers,
        json={"guid": "comp-acme-01", "name": "Acme Innovations Primary"},
    )
    assert comp_res.status_code == 200


def test_request_logging_middleware_and_security_audit(
    client: TestClient, onboarded_auth: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    """Verifies that requests and 403 authorization rejections are logged appropriately."""
    import logging

    with caplog.at_level(logging.INFO):
        # Health check produces INFO log
        h_res = client.get("/health")
        assert h_res.status_code == 200
        assert any("HTTP 200 GET /health" in r.message for r in caplog.records)

    caplog.clear()

    with caplog.at_level(logging.WARNING):
        # Invalid client_id produces 403 WARNING log
        bad_res = client.get(
            "/api/v1/companies",
            params={"client_id": "non-existent-client"},
            headers={"Authorization": f"Bearer {onboarded_auth['token']}"},
        )
        assert bad_res.status_code == 403
        assert any("Auth rejected" in r.message or "HTTP 403" in r.message for r in caplog.records)

