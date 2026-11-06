"""PostgreSQL storage, security, and CRUD manager for the 20 core Tally tables."""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from backend_ETL.canonical_schema import CANONICAL_DDL_STATEMENTS
from backend_ETL.schema import (
    CHILD_TABLE_SPECS,
    COMPANY_SPEC,
    MASTER_TABLE_SPECS,
    PG_DDL_STATEMENTS,
    VOUCHER_SPEC,
    TableSpec,
)

log = logging.getLogger(__name__)


def _bool_to_int(val: Any, default: int | None = None) -> int | None:
    if val is None:
        return default
    return 1 if bool(val) else 0


def _hash_token(raw_token: str) -> str:
    """Computes SHA-256 hex digest of a plaintext Bearer token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _extract_row_tuple(
    spec: TableSpec,
    row: dict[str, Any],
    company_id: str | None = None,
    now_utc: str = "",
) -> tuple[Any, ...]:
    """Converts a dictionary record into an ordered parameter tuple matching spec.columns."""
    values: list[Any] = []
    for col in spec.columns:
        if col == "company_id" and company_id is not None:
            values.append(company_id)
            continue

        raw = row.get(col)
        if col == "guid" and not raw and spec.name == "voucher_types" and company_id:
            raw = f"{company_id}-{row['name']}"

        if col == "synced_at":
            values.append(raw if raw is not None else now_utc)
        elif col in spec.bool_columns:
            default_bool = 0 if spec.name == "vouchers" else None
            values.append(_bool_to_int(raw, default=default_bool))
        elif col in spec.int_columns:
            if col in ("master_id", "alter_id"):
                values.append(int(raw or 0))
            elif col == "decimal_places" and spec.name == "currencies":
                values.append(int(raw if raw is not None else 2))
            else:
                values.append(int(raw) if raw is not None else None)
        elif col in spec.str_columns:
            values.append(str(raw) if raw is not None else None)
        else:
            values.append(raw)
    return tuple(values)


def build_upsert_sql(spec: TableSpec, conflict_col: str = "guid") -> str:
    """Builds an idempotent PostgreSQL INSERT ... ON CONFLICT DO UPDATE statement."""
    cols_csv = ", ".join(spec.columns)
    placeholders = ", ".join(["%s"] * len(spec.columns))
    update_cols = [c for c in spec.columns if c != conflict_col]
    update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
    return (
        f"INSERT INTO {spec.name} ({cols_csv}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT ({conflict_col}) DO UPDATE SET {update_set}"
    )


def build_insert_sql(spec: TableSpec) -> str:
    """Builds a parameterized PostgreSQL INSERT statement for child tables."""
    cols_csv = ", ".join(spec.columns)
    placeholders = ", ".join(["%s"] * len(spec.columns))
    return f"INSERT INTO {spec.name} ({cols_csv}) VALUES ({placeholders})"


class PostgresManager:
    """Data access layer for the PostgreSQL replicated backend."""

    def __init__(
        self,
        dsn: str = "",
        conn_factory: Callable[[], Any] | None = None,
        use_pool: bool = True,
    ) -> None:
        self.dsn = dsn
        self._conn_factory = conn_factory
        self._pool: Any = None

        if self._conn_factory is None and self.dsn and use_pool:
            try:
                self._pool = ConnectionPool(
                    conninfo=self.dsn,
                    min_size=1,
                    max_size=10,
                    kwargs={"row_factory": dict_row},
                    open=True,
                )
            except Exception as e:
                log.error(
                    "ConnectionPool not initialized for %s (%s: %s); falling back to direct connect",
                    self.safe_dsn(),
                    type(e).__name__,
                    e,
                )
                self._pool = None
            else:
                log.info("ConnectionPool initialised for %s", self.safe_dsn())

    def safe_dsn(self) -> str:
        """Returns the DSN with the password masked, safe for logging."""
        return re.sub(r"(://[^:/@]+:)[^@]*@", r"\1***@", self.dsn or "<none>")

    # Tables the dashboard APIs read from, in pipeline order (raw -> canonical)
    _DIAGNOSTIC_TABLES = (
        "companies",
        "vouchers",
        "canonical_companies",
        "canonical_accounts",
        "canonical_vouchers",
        "canonical_daily_movements",
        "canonical_bill_events",
        "canonical_stock_items",
        "canonical_inventory_lines",
    )

    def diagnose_data(self) -> dict[str, Any]:
        """Logs DB connectivity and per-table row counts to locate where the data pipeline is empty."""
        report: dict[str, Any] = {"dsn": self.safe_dsn(), "connected": False, "tables": {}}
        log.info("DIAGNOSE: checking database %s", report["dsn"])
        try:
            with self.connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT current_database() AS db, current_user AS usr, version() AS ver")
                info = dict(cur.fetchone())
                report["connected"] = True
                report.update(info)
                log.info("DIAGNOSE: connected db=%s user=%s (%s)", info["db"], info["usr"], info["ver"])
                cur.close()
        except Exception as e:
            log.error("DIAGNOSE: cannot connect to database %s: %s: %s", report["dsn"], type(e).__name__, e)
            report["error"] = f"{type(e).__name__}: {e}"
            return report

        for table in self._DIAGNOSTIC_TABLES:
            try:
                with self.connection() as conn:
                    cur = conn.cursor()
                    cur.execute(f"SELECT COUNT(*) AS n FROM {table}")
                    count = int(dict(cur.fetchone())["n"])
                    cur.close()
                report["tables"][table] = count
                (log.info if count else log.warning)("DIAGNOSE: %-28s %d rows", table, count)
            except Exception as e:
                report["tables"][table] = f"ERROR {type(e).__name__}"
                log.error("DIAGNOSE: %-28s query failed: %s: %s", table, type(e).__name__, e)
        return report

    @contextmanager
    def connection(self) -> Iterator[Any]:
        """Yields a database connection with transaction management."""
        if self._conn_factory is not None:
            conn = self._conn_factory()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            return

        if self._pool is not None:
            with self._pool.connection() as conn:
                yield conn
            return

        with psycopg.connect(self.dsn, row_factory=dict_row) as conn:
            yield conn

    def close(self) -> None:
        """Closes the connection pool if active."""
        if self._pool is not None:
            log.info("Closing database connection pool")
            self._pool.close()
            self._pool = None

    def check_health(self) -> bool:
        """Verifies PostgreSQL connectivity."""
        try:
            with self.connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT 1 AS ok")
                row = cur.fetchone()
                cur.close()
                return bool(row)
        except Exception as e:
            log.error("PostgreSQL health check failed: %s", e)
            raise

    def bootstrap_canonical(self) -> None:
        """Creates all 26 canonical domain model tables and sync cursor registry."""
        log.info(
            "Bootstrapping Canonical schema (%d DDL statements)...", len(CANONICAL_DDL_STATEMENTS)
        )
        with self.connection() as conn:
            cur = conn.cursor()
            for stmt in CANONICAL_DDL_STATEMENTS:
                cur.execute(stmt)
            cur.close()
        log.info("Canonical schema bootstrap completed successfully.")

    def bootstrap(self, include_canonical: bool = False) -> None:
        """Creates all security, core, and canonical tables, indexes, and views in PostgreSQL."""
        log.info("Bootstrapping PostgreSQL schema (%d DDL statements)...", len(PG_DDL_STATEMENTS))
        with self.connection() as conn:
            cur = conn.cursor()
            for stmt in PG_DDL_STATEMENTS:
                cur.execute(stmt)
            cur.close()
        log.info("PostgreSQL schema bootstrap completed successfully.")
        if include_canonical:
            self.bootstrap_canonical()

    # ─── Security: CLI Token Provisioning & Client Onboarding ────────────────────

    def issue_token_for_client(
        self,
        client_id: str | None = None,
        description: str | None = None,
        unassigned: bool = False,
    ) -> dict[str, str | None]:
        """Generates a unique API token.

        If unassigned is True, creates a token with client_id = NULL for onboarding.
        If client_id is not specified and unassigned is False, generates a random UUID client_id.
        """
        if unassigned:
            clean_client_id = None
        else:
            clean_client_id = (client_id or "").strip() or str(uuid.uuid4())

        raw_token = f"trs_{secrets.token_urlsafe(32)}"
        token_hash = _hash_token(raw_token)
        token_prefix = raw_token[:10]
        now_utc = datetime.now(UTC).isoformat()

        with self.connection() as conn:
            cur = conn.cursor()
            if clean_client_id is not None:
                cur.execute(
                    "SELECT client_id FROM api_tokens WHERE client_id = %s LIMIT 1",
                    (clean_client_id,),
                )
                if cur.fetchone():
                    cur.close()
                    raise ValueError(
                        f"Client '{clean_client_id}' already has a token assigned. "
                        "Use --rotate-token instead."
                    )

            cur.execute(
                """
                INSERT INTO api_tokens (
                    client_id, token_hash, token_prefix, description, is_active, created_at
                ) VALUES (%s, %s, %s, %s, 1, %s)
                """,
                (clean_client_id, token_hash, token_prefix, description, now_utc),
            )
            cur.close()

        log.info(
            "Issued API token (prefix='%s...', client_id=%s, description=%s)",
            token_prefix,
            clean_client_id or "<unassigned>",
            description,
        )
        return {
            "client_id": clean_client_id,
            "token": raw_token,
            "token_prefix": token_prefix,
        }

    def bind_token_to_client(self, token: str, client_id: str) -> bool:
        """Binds an unassigned token to a newly onboarded client_id."""
        token_hash = _hash_token(token)
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT token_id FROM api_tokens WHERE client_id = %s LIMIT 1",
                (client_id,),
            )
            if cur.fetchone():
                cur.close()
                raise ValueError(f"Client '{client_id}' already has a token assigned")

            cur.execute(
                "UPDATE api_tokens SET client_id = %s WHERE token_hash = %s AND client_id IS NULL",
                (client_id, token_hash),
            )
            bound = bool(cur.rowcount > 0)
            cur.close()

        if bound:
            log.info("Bound unassigned token to client_id='%s'", client_id)
        else:
            log.warning("Failed to bind token: either token not found or already assigned")
        return bound

    def rotate_token(self, client_id: str) -> dict[str, str]:
        """Rotates the Bearer token for an existing client_id."""
        raw_token = f"trs_{secrets.token_urlsafe(32)}"
        token_hash = _hash_token(raw_token)
        token_prefix = raw_token[:10]
        now_utc = datetime.now(UTC).isoformat()

        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE api_tokens
                SET token_hash = %s, token_prefix = %s, is_active = 1, created_at = %s
                WHERE client_id = %s
                """,
                (token_hash, token_prefix, now_utc, client_id),
            )
            updated = bool(cur.rowcount > 0)
            cur.close()

        if not updated:
            raise ValueError(f"No token record found for client_id '{client_id}'")

        log.info("Rotated token for client_id='%s' (new prefix='%s...')", client_id, token_prefix)
        return {
            "client_id": client_id,
            "token": raw_token,
            "token_prefix": token_prefix,
        }

    def revoke_token(self, client_id: str) -> bool:
        """Deactivates the Bearer token for a client_id."""
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE api_tokens SET is_active = 0 WHERE client_id = %s",
                (client_id,),
            )
            revoked = bool(cur.rowcount > 0)
            cur.close()
            if revoked:
                log.info("Revoked token for client_id='%s'", client_id)
            else:
                log.warning("Revoke failed: client_id='%s' not found", client_id)
            return revoked

    def verify_bearer_token(self, raw_token: str) -> dict[str, Any] | None:
        """Validates a Bearer token and returns its metadata if active."""
        if not raw_token:
            return None
        # TODO: Delete later
        log.info(raw_token)
        token_hash = _hash_token(raw_token)
        # TODO: Delete later
        log.info(token_hash)
        now_utc = datetime.now(UTC).isoformat()

        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT client_id, is_active FROM api_tokens WHERE token_hash = %s LIMIT 1",
                (token_hash,),
            )
            row = cur.fetchone()
            if not row:
                cur.close()
                log.warning("Bearer token verification failed: token hash not found")
                return None

            data = dict(row)
            if not int(data.get("is_active") or 0):
                cur.close()
                log.warning("Bearer token verification failed: token is deactivated")
                return None

            cur.execute(
                "UPDATE api_tokens SET last_used_at = %s WHERE token_hash = %s",
                (now_utc, token_hash),
            )
            cur.close()
            client_id = str(data["client_id"]) if data.get("client_id") is not None else None
            return {"client_id": client_id}

    def create_client(
        self, client_id: str, client_name: str, contact_email: str | None = None
    ) -> dict[str, Any]:
        """Creates or updates a registered client record in the clients table."""
        now_utc = datetime.now(UTC).isoformat()
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO clients (
                    client_id, client_name, contact_email, is_active, created_at, updated_at
                ) VALUES (%s, %s, %s, 1, %s, %s)
                ON CONFLICT (client_id) DO UPDATE SET
                    client_name = EXCLUDED.client_name,
                    contact_email = EXCLUDED.contact_email,
                    is_active = 1,
                    updated_at = EXCLUDED.updated_at
                """,
                (client_id, client_name, contact_email, now_utc, now_utc),
            )
            cur.close()
        log.info("Registered client: client_id='%s', client_name='%s'", client_id, client_name)
        return {
            "client_id": client_id,
            "client_name": client_name,
            "contact_email": contact_email,
            "is_active": 1,
        }

    def get_client(self, client_id: str) -> dict[str, Any] | None:
        """Retrieves an active registered client from the clients table."""
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM clients WHERE client_id = %s AND is_active = 1 LIMIT 1",
                (client_id,),
            )
            row = cur.fetchone()
            cur.close()
            return dict(row) if row else None

    def get_client_by_contact_email(self, contact_email: str) -> dict[str, Any] | None:
        """Retrieves an active client record matching the provided contact email (case-insensitive)."""
        if not contact_email or not contact_email.strip():
            return None
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM clients WHERE LOWER(contact_email) = LOWER(%s) AND is_active = 1 ORDER BY created_at DESC LIMIT 1",
                (contact_email.strip(),),
            )
            row = cur.fetchone()
            cur.close()
            return dict(row) if row else None

    def list_client_company_guids(self, client_id: str) -> list[str]:
        """Returns all company GUIDs mapped to the given client_id."""
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT company_guid FROM client_companies "
                "WHERE client_id = %s ORDER BY company_guid ASC",
                (client_id,),
            )
            guids = [str(dict(r)["company_guid"]) for r in cur.fetchall()]
            cur.close()
            return guids

    def map_client_to_companies(self, client_id: str, company_guids: list[str]) -> None:
        """Maps company GUIDs to client_id after verifying no other client owns them."""
        if not company_guids:
            return
        now_utc = datetime.now(UTC).isoformat()
        with self.connection() as conn:
            cur = conn.cursor()
            for c_guid in company_guids:
                cur.execute(
                    "SELECT client_id FROM client_companies WHERE company_guid = %s LIMIT 1",
                    (c_guid,),
                )
                existing = cur.fetchone()
                if existing and str(dict(existing)["client_id"]) != client_id:
                    cur.close()
                    log.warning(
                        "Company mapping rejected: company_guid='%s' is already mapped to '%s'",
                        c_guid,
                        dict(existing)["client_id"],
                    )
                    raise PermissionError(
                        f"Company GUID '{c_guid}' is already mapped to another client"
                    )

            for c_guid in company_guids:
                cur.execute(
                    """
                    INSERT INTO client_companies (client_id, company_guid, created_at)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (client_id, company_guid) DO NOTHING
                    """,
                    (client_id, c_guid, now_utc),
                )
            cur.close()
        log.info(
            "Mapped client_id='%s' to %d company GUIDs: %s",
            client_id,
            len(company_guids),
            company_guids,
        )

    def verify_client_company_access(self, client_id: str, company_guid: str) -> bool:
        """Verifies that client_id is registered and mapped to company_guid."""
        if not client_id or not company_guid:
            log.warning("Access check failed: empty client_id or company_guid")
            return False
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT 1
                FROM client_companies cc
                JOIN clients c ON c.client_id = cc.client_id
                WHERE cc.client_id = %s AND cc.company_guid = %s AND c.is_active = 1
                LIMIT 1
                """,
                (client_id, company_guid),
            )
            ok = cur.fetchone() is not None
            cur.close()
            if not ok:
                log.warning(
                    "Access check failed: client_id='%s' does NOT have access to company_id='%s'",
                    client_id,
                    company_guid,
                )
            return ok

    # ─── User Accounts, Roles & Chat Stream Management ──────────────────────────

    def create_user(
        self,
        client_id: str,
        email: str,
        password_hash: str,
        full_name: str,
        role: str = "viewer",
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Creates a new human user record under an organization client."""
        assigned_user_id = (user_id or "").strip() or str(uuid.uuid4())
        normalized_email = email.strip().lower()
        now_utc = datetime.now(UTC).isoformat()

        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO users (
                    user_id, client_id, email, password_hash, full_name, role, is_active, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s)
                """,
                (
                    assigned_user_id,
                    client_id,
                    normalized_email,
                    password_hash,
                    full_name.strip(),
                    role.strip(),
                    now_utc,
                    now_utc,
                ),
            )
            cur.close()

        log.info(
            "Created user account: user_id='%s', email='%s', role='%s', client_id='%s'",
            assigned_user_id,
            normalized_email,
            role,
            client_id,
        )
        return {
            "user_id": assigned_user_id,
            "client_id": client_id,
            "email": normalized_email,
            "full_name": full_name.strip(),
            "role": role.strip(),
            "is_active": 1,
            "created_at": now_utc,
        }

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        """Retrieves a user record by email address."""
        normalized_email = email.strip().lower()
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM users WHERE email = %s LIMIT 1",
                (normalized_email,),
            )
            row = cur.fetchone()
            cur.close()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        """Retrieves a user record by user_id."""
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM users WHERE user_id = %s LIMIT 1",
                (user_id,),
            )
            row = cur.fetchone()
            cur.close()
            return dict(row) if row else None

    def update_user_last_login(self, user_id: str) -> None:
        """Updates last_login_at timestamp for the user."""
        now_utc = datetime.now(UTC).isoformat()
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET last_login_at = %s, updated_at = %s WHERE user_id = %s",
                (now_utc, now_utc, user_id),
            )
            cur.close()

    def link_user_to_company(self, user_id: str, company_guid: str) -> None:
        """Grants fine-grained company access to a user."""
        now_utc = datetime.now(UTC).isoformat()
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO user_companies (user_id, company_guid, created_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, company_guid) DO NOTHING
                """,
                (user_id, company_guid, now_utc),
            )
            cur.close()

    def list_user_company_guids(self, user_id: str) -> list[str]:
        """Lists accessible company GUIDs for a user (combining explicit user links and client company mappings)."""
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT company_guid FROM user_companies WHERE user_id = %s ORDER BY company_guid",
                (user_id,),
            )
            explicit_guids = [str(dict(r)["company_guid"]) for r in cur.fetchall()]
            if explicit_guids:
                cur.close()
                return explicit_guids

            cur.execute(
                """
                SELECT cc.company_guid
                FROM client_companies cc
                JOIN users u ON u.client_id = cc.client_id
                WHERE u.user_id = %s
                ORDER BY cc.company_guid
                """,
                (user_id,),
            )
            inherited_guids = [str(dict(r)["company_guid"]) for r in cur.fetchall()]
            cur.close()
            return inherited_guids

    def list_user_companies(self, user_id: str) -> list[dict[str, str]]:
        """Lists accessible companies with their IDs and names for a user."""
        guids = self.list_user_company_guids(user_id)
        if not guids:
            return []

        with self.connection() as conn:
            cur = conn.cursor()
            placeholders = ", ".join(["%s"] * len(guids))
            cur.execute(
                f"SELECT company_id, name FROM canonical_companies WHERE company_id IN ({placeholders})",
                tuple(guids),
            )
            canonical_map = {str(dict(r)["company_id"]): str(dict(r)["name"]) for r in cur.fetchall()}
            cur.close()

        return [
            {"company_id": g, "company_name": canonical_map.get(g, g)}
            for g in guids
        ]

    def save_chat_message(
        self,
        user_id: str,
        company_id: str,
        role: str,
        content: str,
        tool_called: str | None = None,
    ) -> dict[str, Any]:
        """Appends a new turn to the single ongoing conversation stream for this user and company."""
        now_utc = datetime.now(UTC).isoformat()
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO chat_messages (user_id, company_id, role, content, tool_called, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (user_id, company_id, role.strip(), content.strip(), tool_called, now_utc),
            )
            cur.close()
        return {
            "user_id": user_id,
            "company_id": company_id,
            "role": role,
            "content": content,
            "tool_called": tool_called,
            "created_at": now_utc,
        }

    def list_chat_messages(
        self,
        user_id: str,
        company_id: str,
        limit: int = 50,
        ascending: bool = True,
    ) -> list[dict[str, Any]]:
        """Retrieves messages from the single persistent chat stream."""
        order_direction = "ASC" if ascending else "DESC"
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT role, content, tool_called, created_at
                FROM (
                    SELECT * FROM chat_messages
                    WHERE user_id = %s AND company_id = %s
                    ORDER BY id DESC
                    LIMIT %s
                ) recent_turns
                ORDER BY id {order_direction}
                """,
                (user_id, company_id, limit),
            )
            messages = [dict(r) for r in cur.fetchall()]
            cur.close()
            return messages

    def clear_chat_messages(self, user_id: str, company_id: str) -> int:
        """Clears all turns from the chat stream for this user and company."""
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM chat_messages WHERE user_id = %s AND company_id = %s",
                (user_id, company_id),
            )
            deleted_count = cur.rowcount
            cur.close()
        log.info("Cleared %d chat messages for user_id='%s', company_id='%s'", deleted_count, user_id, company_id)
        return deleted_count

    def get_voucher_company_guid(self, voucher_guid: str) -> str | None:
        """Looks up the owning company_id (company GUID) for a voucher_guid."""
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT company_id FROM vouchers WHERE guid = %s LIMIT 1",
                (voucher_guid,),
            )
            row = cur.fetchone()
            cur.close()
            return str(dict(row)["company_id"]) if row else None

    # ─── Companies CRUD ──────────────────────────────────────────────────────────

    def upsert_companies(self, rows: list[dict[str, Any]], client_id: str | None = None) -> int:
        """Bulk upserts company records on guid conflict and maps them to client_id."""
        if not rows:
            return 0
        now_utc = datetime.now(UTC).isoformat()
        company_guids = [str(r["guid"]) for r in rows]

        if client_id is not None:
            with self.connection() as conn:
                cur = conn.cursor()
                for c_guid in company_guids:
                    cur.execute(
                        "SELECT client_id FROM client_companies WHERE company_guid = %s LIMIT 1",
                        (c_guid,),
                    )
                    existing = cur.fetchone()
                    if existing and str(dict(existing)["client_id"]) != client_id:
                        cur.close()
                        raise PermissionError(
                            f"Company GUID '{c_guid}' is already mapped to another client"
                        )
                cur.close()

        sql = build_upsert_sql(COMPANY_SPEC, conflict_col="guid")
        params = [_extract_row_tuple(COMPANY_SPEC, r, now_utc=now_utc) for r in rows]
        with self.connection() as conn:
            cur = conn.cursor()
            cur.executemany(sql, params)
            cur.close()

        if client_id is not None:
            self.map_client_to_companies(client_id, company_guids)

        log.info(
            "Upserted %d companies into PostgreSQL (client_id=%s)",
            len(rows),
            client_id or "<none>",
        )
        return len(rows)

    def list_companies(self, client_id: str | None = None) -> list[dict[str, Any]]:
        """Lists companies (scoped to client_id when provided)."""
        with self.connection() as conn:
            cur = conn.cursor()
            if client_id is not None:
                cur.execute(
                    """
                    SELECT comp.*
                    FROM companies comp
                    JOIN client_companies cc ON cc.company_guid = comp.guid
                    WHERE cc.client_id = %s
                    ORDER BY comp.name ASC
                    """,
                    (client_id,),
                )
            else:
                cur.execute("SELECT * FROM companies ORDER BY name ASC")
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            return rows

    def get_company(
        self, guid: str | None = None, name: str | None = None
    ) -> dict[str, Any] | None:
        """Fetches a company by guid or name."""
        if not guid and not name:
            return None
        with self.connection() as conn:
            cur = conn.cursor()
            if guid and name:
                cur.execute(
                    "SELECT * FROM companies WHERE guid = %s AND name = %s LIMIT 1",
                    (guid, name),
                )
            elif guid:
                cur.execute("SELECT * FROM companies WHERE guid = %s LIMIT 1", (guid,))
            else:
                cur.execute("SELECT * FROM companies WHERE name = %s LIMIT 1", (name,))
            row = cur.fetchone()
            cur.close()
            return dict(row) if row else None

    def delete_company(self, guid: str) -> bool:
        """Deletes a company by guid and removes its client mapping."""
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM client_companies WHERE company_guid = %s", (guid,))
            cur.execute("DELETE FROM companies WHERE guid = %s", (guid,))
            deleted = bool(cur.rowcount > 0)
            cur.close()
            log.info("Deleted company guid='%s' (success=%s)", guid, deleted)
            return deleted

    # ─── Master Tables CRUD (14 Tables) ──────────────────────────────────────────

    @staticmethod
    def _get_master_spec(table_name: str) -> TableSpec:
        if table_name not in MASTER_TABLE_SPECS:
            raise ValueError(f"Unsupported master table: '{table_name}'")
        return MASTER_TABLE_SPECS[table_name]

    def upsert_master_rows(
        self, table_name: str, company_id: str, rows: list[dict[str, Any]]
    ) -> int:
        """Bulk upserts rows into any of the 14 master tables on guid conflict."""
        spec = self._get_master_spec(table_name)
        if not rows:
            return 0
        now_utc = datetime.now(UTC).isoformat()
        sql = build_upsert_sql(spec, conflict_col="guid")
        params = [_extract_row_tuple(spec, r, company_id=company_id, now_utc=now_utc) for r in rows]
        with self.connection() as conn:
            cur = conn.cursor()
            cur.executemany(sql, params)
            cur.close()
        log.info(
            "Upserted %d master records into '%s' for company_id='%s'",
            len(rows),
            table_name,
            company_id,
        )
        return len(rows)

    def list_master_rows(
        self,
        table_name: str,
        company_id: str,
        min_alter_id: int = 0,
        limit: int = 500,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Lists master records for a company with optional alter_id watermark filter."""
        spec = self._get_master_spec(table_name)
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT * FROM {spec.name} "
                f"WHERE company_id = %s AND alter_id >= %s "
                f"ORDER BY alter_id ASC, name ASC LIMIT %s OFFSET %s",
                (company_id, min_alter_id, limit, offset),
            )
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            return rows

    def get_master_row(self, table_name: str, company_id: str, guid: str) -> dict[str, Any] | None:
        """Fetches a single master record by company_id and guid."""
        spec = self._get_master_spec(table_name)
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT * FROM {spec.name} WHERE company_id = %s AND guid = %s LIMIT 1",
                (company_id, guid),
            )
            row = cur.fetchone()
            cur.close()
            return dict(row) if row else None

    def delete_master_row(self, table_name: str, company_id: str, guid: str) -> bool:
        """Deletes a single master record by company_id and guid."""
        spec = self._get_master_spec(table_name)
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"DELETE FROM {spec.name} WHERE company_id = %s AND guid = %s",
                (company_id, guid),
            )
            deleted = bool(cur.rowcount > 0)
            cur.close()
            log.info(
                "Deleted master record from '%s' for company_id='%s', guid='%s' (success=%s)",
                table_name,
                company_id,
                guid,
                deleted,
            )
            return deleted

    # ─── Vouchers & Child Entries CRUD ───────────────────────────────────────────

    def upsert_vouchers_with_entries(
        self,
        company_id: str,
        headers: list[dict[str, Any]],
        ledger_entries: list[dict[str, Any]] | None = None,
        inventory_entries: list[dict[str, Any]] | None = None,
        cost_centre_allocations: list[dict[str, Any]] | None = None,
        attendance_entries: list[dict[str, Any]] | None = None,
    ) -> int:
        """Atomically upserts voucher headers and replaces their child line items."""
        if not headers:
            return 0
        now_utc = datetime.now(UTC).isoformat()
        header_sql = build_upsert_sql(VOUCHER_SPEC, conflict_col="guid")
        header_params = [
            _extract_row_tuple(VOUCHER_SPEC, h, company_id=company_id, now_utc=now_utc)
            for h in headers
        ]
        guids = [(h["guid"],) for h in headers if h.get("guid")]

        child_batches: list[tuple[TableSpec, list[dict[str, Any]] | None]] = [
            (CHILD_TABLE_SPECS["ledger_entries"], ledger_entries),
            (CHILD_TABLE_SPECS["cost_centre_allocations"], cost_centre_allocations),
            (CHILD_TABLE_SPECS["inventory_entries"], inventory_entries),
            (CHILD_TABLE_SPECS["attendance_entries"], attendance_entries),
        ]

        with self.connection() as conn:
            cur = conn.cursor()
            try:
                cur.executemany(header_sql, header_params)

                if guids:
                    for child_name in CHILD_TABLE_SPECS:
                        cur.executemany(
                            f"DELETE FROM {child_name} WHERE voucher_guid = %s",
                            guids,
                        )

                for child_spec, child_rows in child_batches:
                    if child_rows:
                        child_sql = build_insert_sql(child_spec)
                        child_params = [_extract_row_tuple(child_spec, r) for r in child_rows]
                        cur.executemany(child_sql, child_params)
            finally:
                cur.close()

        log.info(
            "Atomically upserted %d vouchers for company_id='%s' "
            "(line items: ledger=%d, cost=%d, inv=%d, att=%d)",
            len(headers),
            company_id,
            len(ledger_entries or []),
            len(cost_centre_allocations or []),
            len(inventory_entries or []),
            len(attendance_entries or []),
        )
        return len(headers)

    def list_vouchers(
        self,
        company_id: str,
        from_date: str | None = None,
        to_date: str | None = None,
        voucher_type_name: str | None = None,
        min_alter_id: int = 0,
        limit: int = 500,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Lists voucher headers with optional date, voucher_type, and alter_id filters."""
        clauses = ["company_id = %s", "alter_id >= %s"]
        params: list[Any] = [company_id, min_alter_id]

        if from_date:
            clauses.append("date >= %s")
            params.append(from_date)
        if to_date:
            clauses.append("date <= %s")
            params.append(to_date)
        if voucher_type_name:
            clauses.append("voucher_type_name = %s")
            params.append(voucher_type_name)

        params.extend([limit, offset])
        where_sql = " AND ".join(clauses)

        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT * FROM vouchers WHERE {where_sql} "
                f"ORDER BY date ASC, alter_id ASC LIMIT %s OFFSET %s",
                tuple(params),
            )
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            return rows

    def get_voucher_with_entries(self, company_id: str, guid: str) -> dict[str, Any] | None:
        """Retrieves a voucher header along with all 4 child entry collections."""
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM vouchers WHERE company_id = %s AND guid = %s LIMIT 1",
                (company_id, guid),
            )
            row = cur.fetchone()
            if not row:
                cur.close()
                return None

            result = dict(row)
            for child_name in CHILD_TABLE_SPECS:
                cur.execute(
                    f"SELECT * FROM {child_name} WHERE voucher_guid = %s ORDER BY id ASC",
                    (guid,),
                )
                result[child_name] = [dict(r) for r in cur.fetchall()]
            cur.close()
            return result

    def delete_voucher(self, company_id: str, guid: str) -> bool:
        """Deletes a voucher header and its child entries."""
        with self.connection() as conn:
            cur = conn.cursor()
            for child_name in CHILD_TABLE_SPECS:
                cur.execute(f"DELETE FROM {child_name} WHERE voucher_guid = %s", (guid,))
            cur.execute(
                "DELETE FROM vouchers WHERE company_id = %s AND guid = %s",
                (company_id, guid),
            )
            deleted = bool(cur.rowcount > 0)
            cur.close()
            log.info(
                "Deleted voucher guid='%s' for company_id='%s' (success=%s)",
                guid,
                company_id,
                deleted,
            )
            return deleted

    # ─── Direct Child Entry Table CRUD (4 Tables) ────────────────────────────────

    @staticmethod
    def _get_child_spec(child_table: str) -> TableSpec:
        if child_table not in CHILD_TABLE_SPECS:
            raise ValueError(f"Unsupported child table: '{child_table}'")
        return CHILD_TABLE_SPECS[child_table]

    def list_child_entries(self, voucher_guid: str, child_table: str) -> list[dict[str, Any]]:
        """Lists child entries for a voucher from the specified child_table."""
        spec = self._get_child_spec(child_table)
        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT * FROM {spec.name} WHERE voucher_guid = %s ORDER BY id ASC",
                (voucher_guid,),
            )
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()
            return rows

    def replace_child_entries(
        self, voucher_guid: str, child_table: str, rows: list[dict[str, Any]]
    ) -> int:
        """Replaces all child entries for voucher_guid in child_table."""
        spec = self._get_child_spec(child_table)
        enriched = [{**r, "voucher_guid": voucher_guid} for r in rows]
        params = [_extract_row_tuple(spec, r) for r in enriched]
        insert_sql = build_insert_sql(spec)

        with self.connection() as conn:
            cur = conn.cursor()
            cur.execute(f"DELETE FROM {spec.name} WHERE voucher_guid = %s", (voucher_guid,))
            if params:
                cur.executemany(insert_sql, params)
            cur.close()
        log.info(
            "Replaced %d entries in child table '%s' for voucher_guid='%s'",
            len(rows),
            child_table,
            voucher_guid,
        )
        return len(rows)

    def delete_child_entries(
        self, voucher_guid: str, child_table: str, entry_id: int | None = None
    ) -> int:
        """Deletes child entries for voucher_guid (or a specific entry_id if provided)."""
        spec = self._get_child_spec(child_table)
        with self.connection() as conn:
            cur = conn.cursor()
            if entry_id is not None:
                cur.execute(
                    f"DELETE FROM {spec.name} WHERE voucher_guid = %s AND id = %s",
                    (voucher_guid, entry_id),
                )
            else:
                cur.execute(
                    f"DELETE FROM {spec.name} WHERE voucher_guid = %s",
                    (voucher_guid,),
                )
            deleted_count = int(cur.rowcount or 0)
            cur.close()
            log.info(
                "Deleted %d entries from child table '%s' for voucher_guid='%s' (entry_id=%s)",
                deleted_count,
                child_table,
                voucher_guid,
                entry_id,
            )
            return deleted_count

    # ─── Replication Watermarks ──────────────────────────────────────────────────

    def get_company_watermarks(self, company_id: str) -> dict[str, dict[str, int]]:
        """Returns row counts and max master_id / alter_id watermarks across all company tables."""
        watermarks: dict[str, dict[str, int]] = {}
        scoped_tables = [*MASTER_TABLE_SPECS.keys(), "vouchers"]

        with self.connection() as conn:
            cur = conn.cursor()
            for table_name in scoped_tables:
                cur.execute(
                    f"SELECT COUNT(*) AS row_count, "
                    f"COALESCE(MAX(master_id), 0) AS max_master_id, "
                    f"COALESCE(MAX(alter_id), 0) AS max_alter_id "
                    f"FROM {table_name} WHERE company_id = %s",
                    (company_id,),
                )
                row = dict(cur.fetchone() or {})
                watermarks[table_name] = {
                    "row_count": int(row.get("row_count") or 0),
                    "max_master_id": int(row.get("max_master_id") or 0),
                    "max_alter_id": int(row.get("max_alter_id") or 0),
                }
            cur.close()
        return watermarks
