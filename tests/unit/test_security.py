"""Unit and integration tests for human user authentication, Argon2id hashing, and JWT tokens."""

from __future__ import annotations

import sqlite3
from typing import Any
import pytest
from fastapi.testclient import TestClient

from backend_ETL.api import create_app
from backend_ETL.db import PostgresManager
from backend_ETL.schema import PG_DDL_STATEMENTS
from backend_ETL.security import (
    create_jwt_access_token,
    decode_jwt_access_token,
    hash_user_password,
    verify_user_password,
)


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
        translated = translated.replace("TIMESTAMPTZ DEFAULT NOW()", "TEXT DEFAULT CURRENT_TIMESTAMP")
        translated = translated.replace("TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP", "TEXT DEFAULT CURRENT_TIMESTAMP")
        translated = translated.replace("TIMESTAMPTZ", "TEXT")
        translated = translated.replace("NOW()", "CURRENT_TIMESTAMP")
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


class _SQLiteCompatConn:
    """Wrapper connection yielding SQLiteCompatCursor."""

    def __init__(self, raw_conn: sqlite3.Connection) -> None:
        self._conn = raw_conn

    def cursor(self) -> _SQLiteCompatCursor:
        return _SQLiteCompatCursor(self._conn.cursor())

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()


@pytest.fixture
def test_db_manager() -> PostgresManager:
    """Creates an in-memory SQLite database wrapped by PostgresManager for testing."""
    raw_sqlite_connection = sqlite3.connect(":memory:", check_same_thread=False)
    raw_sqlite_connection.row_factory = sqlite3.Row
    compat_connection = _SQLiteCompatConn(raw_sqlite_connection)

    db_manager_instance = PostgresManager(conn_factory=lambda: compat_connection)

    # Initialize schema tables
    with db_manager_instance.connection() as conn:
        cursor = conn.cursor()
        for statement in PG_DDL_STATEMENTS:
            cursor.execute(statement)
        cursor.close()

    return db_manager_instance


@pytest.fixture
def test_api_client(test_db_manager: PostgresManager) -> TestClient:
    """Creates a FastAPI test client bound to the test database."""
    fastapi_application = create_app(db=test_db_manager, start_poller=False)
    return TestClient(fastapi_application)


def test_argon2id_hashing_and_verification() -> None:
    """Verifies that Argon2id produces valid one-way hashes and verifies plain text correctly."""
    plain_password_string = "SecureP@ssword123!"

    # 1. Compute hash
    hashed_password = hash_user_password(plain_password_string)
    assert hashed_password.startswith("$argon2id$")
    assert hashed_password != plain_password_string

    # 2. Verify with correct password
    assert verify_user_password(plain_password_string, hashed_password) is True

    # 3. Verify with incorrect password
    assert verify_user_password("WrongPassword999", hashed_password) is False

    # 4. Verify with empty input
    assert verify_user_password("", hashed_password) is False


def test_jwt_creation_and_decoding() -> None:
    """Verifies JWT access token generation and claims decoding."""
    test_user_claims = {
        "user_id": "usr-uuid-100",
        "client_id": "clt-uuid-200",
        "email": "manoj@shreepolychem.com",
        "full_name": "Manoj Kumar",
        "role": "owner",
    }

    # 1. Issue access token
    encoded_token = create_jwt_access_token(test_user_claims)
    assert isinstance(encoded_token, str)
    assert len(encoded_token) > 20

    # 2. Decode claims
    decoded_claims = decode_jwt_access_token(encoded_token)
    assert decoded_claims["user_id"] == "usr-uuid-100"
    assert decoded_claims["client_id"] == "clt-uuid-200"
    assert decoded_claims["email"] == "manoj@shreepolychem.com"
    assert "exp" in decoded_claims
    assert "iat" in decoded_claims


def test_auth_registration_and_login_api_endpoints(test_api_client: TestClient) -> None:
    """Tests the full user onboarding, registration, and login API flow."""
    # 1. Register new organization & owner
    registration_response = test_api_client.post(
        "/api/v1/auth/register",
        json={
            "client_name": "Shree Polychem Pvt Ltd",
            "full_name": "Manoj Kumar",
            "email": "manoj@shreepolychem.com",
            "password": "SuperSecretPassword123!",
        },
    )
    assert registration_response.status_code == 200
    registration_data = registration_response.json()
    assert registration_data["status"] == "ok"
    assert "access_token" in registration_data
    assert registration_data["user"]["email"] == "manoj@shreepolychem.com"
    assert registration_data["user"]["role"] == "owner"

    # 2. Duplicate registration attempt should fail with 400 Bad Request
    duplicate_response = test_api_client.post(
        "/api/v1/auth/register",
        json={
            "client_name": "Duplicate Company",
            "full_name": "Another User",
            "email": "manoj@shreepolychem.com",
            "password": "AnotherPassword456!",
        },
    )
    assert duplicate_response.status_code == 400

    # 3. Successful login
    login_response = test_api_client.post(
        "/api/v1/auth/login",
        json={
            "email": "manoj@shreepolychem.com",
            "password": "SuperSecretPassword123!",
        },
    )
    assert login_response.status_code == 200
    login_data = login_response.json()
    assert login_data["status"] == "ok"
    jwt_token = login_data["access_token"]
    assert jwt_token

    # 4. Failed login with wrong password
    bad_login_response = test_api_client.post(
        "/api/v1/auth/login",
        json={
            "email": "manoj@shreepolychem.com",
            "password": "IncorrectPassword!",
        },
    )
    assert bad_login_response.status_code == 401

    # 5. Protected profile endpoint /api/v1/auth/me with Bearer token
    me_response = test_api_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {jwt_token}"},
    )
    assert me_response.status_code == 200
    me_data = me_response.json()
    assert me_data["user"]["email"] == "manoj@shreepolychem.com"
    assert me_data["user"]["full_name"] == "Manoj Kumar"

    # 6. Protected profile endpoint without token should return 401
    unauth_response = test_api_client.get("/api/v1/auth/me")
    assert unauth_response.status_code == 401
