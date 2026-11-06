"""PostgreSQL storage, security, and CRUD manager for the 20 core Tally tables."""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, delete, func, insert, literal, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, aliased

from backend_ETL.database import make_engine, make_session_factory
from backend_ETL.models import CHILD_MODELS, MASTER_MODELS, Base
from backend_ETL.models.app_tables import (
    ApiToken,
    ChatMessage,
    Client,
    ClientCompany,
    User,
    UserCompany,
)
from backend_ETL.models.canonical_tables import CanonicalCompany
from backend_ETL.models.tally_tables import Company, Voucher
from backend_ETL.schema import (
    CHILD_TABLE_SPECS,
    COMPANY_SPEC,
    MASTER_TABLE_SPECS,
    VOUCHER_SPEC,
    TableSpec,
)

log = logging.getLogger(__name__)


def _bool_to_int(val: Any, default: int | None = None) -> int | None:
    if val is None:
        return default
    return 1 if bool(val) else 0


def _rowcount(result: Any) -> int:
    """Rows matched/affected by an UPDATE or DELETE executed through a Session."""
    return int(result.rowcount or 0)


def _hash_token(raw_token: str) -> str:
    """Computes SHA-256 hex digest of a plaintext Bearer token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _clean_row(
    spec: TableSpec,
    row: dict[str, Any],
    company_id: str | None = None,
    now_utc: str = "",
) -> dict[str, Any]:
    """Coerces a record into {column: value} for every column in spec.columns."""
    values: dict[str, Any] = {}
    for col in spec.columns:
        if col == "company_id" and company_id is not None:
            values[col] = company_id
            continue

        raw = row.get(col)
        if col == "guid" and not raw and spec.name == "voucher_types" and company_id:
            raw = f"{company_id}-{row['name']}"

        if col == "synced_at":
            values[col] = raw if raw is not None else now_utc
        elif col in spec.bool_columns:
            default_bool = 0 if spec.name == "vouchers" else None
            values[col] = _bool_to_int(raw, default=default_bool)
        elif col in spec.int_columns:
            if col in ("master_id", "alter_id"):
                values[col] = int(raw or 0)
            elif col == "decimal_places" and spec.name == "currencies":
                values[col] = int(raw if raw is not None else 2)
            else:
                values[col] = int(raw) if raw is not None else None
        elif col in spec.str_columns:
            values[col] = str(raw) if raw is not None else None
        else:
            values[col] = raw
    return values


def _bulk_upsert(
    s: Session, model: Any, rows: list[dict[str, Any]], conflict_cols: list[str]
) -> None:
    """Idempotent INSERT ... ON CONFLICT DO UPDATE. Every row must have the same keys."""
    if not rows:
        return
    stmt = pg_insert(model)
    update_cols = {k: stmt.excluded[k] for k in rows[0] if k not in conflict_cols}
    if update_cols:
        stmt = stmt.on_conflict_do_update(index_elements=conflict_cols, set_=update_cols)
    else:
        stmt = stmt.on_conflict_do_nothing(index_elements=conflict_cols)
    s.execute(stmt, rows)


class PostgresManager:
    """Data access layer for the PostgreSQL replicated backend."""

    def __init__(
        self,
        dsn: str = "",
        use_pool: bool = True,
        engine: Engine | None = None,
    ) -> None:
        self.dsn = dsn

        # SQLAlchemy engine (lazy: no connection is opened until first use)
        self.engine: Engine | None = engine
        if self.engine is None and self.dsn:
            self.engine = make_engine(self.dsn, use_pool=use_pool)
        self._session_factory = make_session_factory(self.engine) if self.engine else None

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
            with self.session() as s:
                info = dict(
                    s.execute(
                        select(
                            func.current_database().label("db"),
                            func.current_user().label("usr"),
                            func.version().label("ver"),
                        )
                    )
                    .one()
                    ._mapping
                )
                report["connected"] = True
                report.update(info)
                log.info("DIAGNOSE: connected db=%s user=%s (%s)", info["db"], info["usr"], info["ver"])
        except Exception as e:
            log.error("DIAGNOSE: cannot connect to database %s: %s: %s", report["dsn"], type(e).__name__, e)
            report["error"] = f"{type(e).__name__}: {e}"
            return report

        for table in self._DIAGNOSTIC_TABLES:
            try:
                with self.session() as s:
                    count = int(
                        s.scalar(select(func.count()).select_from(Base.metadata.tables[table])) or 0
                    )
                report["tables"][table] = count
                (log.info if count else log.warning)("DIAGNOSE: %-28s %d rows", table, count)
            except Exception as e:
                report["tables"][table] = f"ERROR {type(e).__name__}"
                log.error("DIAGNOSE: %-28s query failed: %s: %s", table, type(e).__name__, e)
        return report

    @contextmanager
    def session(self) -> Iterator[Session]:
        """One transaction: commits on success, rolls back on exception."""
        if self._session_factory is None:
            raise RuntimeError("No SQLAlchemy engine configured (provide dsn or engine)")
        with self._session_factory.begin() as s:
            yield s

    def close(self) -> None:
        """Disposes the SQLAlchemy engine and its connection pool."""
        if self.engine is not None:
            log.info("Disposing database engine")
            self.engine.dispose()

    def check_health(self) -> bool:
        """Verifies PostgreSQL connectivity."""
        try:
            with self.session() as s:
                return bool(s.execute(select(literal(1).label("ok"))).first())
        except Exception as e:
            log.error("PostgreSQL health check failed: %s", e)
            raise

    def _create_tables(self, canonical: bool) -> None:
        """Creates missing tables (and their indexes) from the SQLAlchemy models."""
        if self.engine is None:
            raise RuntimeError("No SQLAlchemy engine configured (provide dsn or engine)")
        tables = [
            tbl
            for name, tbl in Base.metadata.tables.items()
            if name.startswith("canonical_") == canonical
        ]
        Base.metadata.create_all(self.engine, tables=tables)

    def bootstrap_canonical(self) -> None:
        """Creates all 27 canonical domain model tables and sync cursor registry."""
        log.info("Bootstrapping Canonical schema from models...")
        self._create_tables(canonical=True)
        log.info("Canonical schema bootstrap completed successfully.")

    def bootstrap(self, include_canonical: bool = False) -> None:
        """Creates all security, core, and canonical tables, indexes, and views in PostgreSQL."""
        log.info("Bootstrapping PostgreSQL schema from models...")
        self._create_tables(canonical=False)
        with self.session() as s:  # create_all does not manage views
            s.execute(text("CREATE OR REPLACE VIEW VoucherType AS SELECT * FROM voucher_types"))
            s.execute(text("ALTER TABLE clients ADD COLUMN IF NOT EXISTS tally_version TEXT"))
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

        with self.session() as s:
            if clean_client_id is not None:
                existing = s.scalars(
                    select(ApiToken.client_id).where(ApiToken.client_id == clean_client_id).limit(1)
                ).first()
                if existing is not None:
                    raise ValueError(
                        f"Client '{clean_client_id}' already has a token assigned. "
                        "Use --rotate-token instead."
                    )

            s.add(
                ApiToken(
                    client_id=clean_client_id,
                    token_hash=token_hash,
                    token_prefix=token_prefix,
                    description=description,
                    is_active=1,
                    created_at=now_utc,
                )
            )

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
        with self.session() as s:
            existing = s.scalars(
                select(ApiToken.token_id).where(ApiToken.client_id == client_id).limit(1)
            ).first()
            if existing is not None:
                raise ValueError(f"Client '{client_id}' already has a token assigned")

            result = s.execute(
                update(ApiToken)
                .where(ApiToken.token_hash == token_hash, ApiToken.client_id.is_(None))
                .values(client_id=client_id)
            )
            bound = _rowcount(result) > 0

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

        with self.session() as s:
            result = s.execute(
                update(ApiToken)
                .where(ApiToken.client_id == client_id)
                .values(
                    token_hash=token_hash,
                    token_prefix=token_prefix,
                    is_active=1,
                    created_at=now_utc,
                )
            )
            updated = _rowcount(result) > 0

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
        with self.session() as s:
            result = s.execute(
                update(ApiToken).where(ApiToken.client_id == client_id).values(is_active=0)
            )
            revoked = _rowcount(result) > 0
        if revoked:
            log.info("Revoked token for client_id='%s'", client_id)
        else:
            log.warning("Revoke failed: client_id='%s' not found", client_id)
        return revoked

    def verify_bearer_token(self, raw_token: str) -> dict[str, Any] | None:
        """Validates a Bearer token and returns its metadata if active."""
        if not raw_token:
            return None
        token_hash = _hash_token(raw_token)
        now_utc = datetime.now(UTC).isoformat()

        with self.session() as s:
            row = s.execute(
                select(ApiToken.client_id, ApiToken.is_active)
                .where(ApiToken.token_hash == token_hash)
                .limit(1)
            ).first()
            if not row:
                log.warning("Bearer token verification failed: token hash not found")
                return None

            if not int(row.is_active or 0):
                log.warning("Bearer token verification failed: token is deactivated")
                return None

            s.execute(
                update(ApiToken).where(ApiToken.token_hash == token_hash).values(last_used_at=now_utc)
            )
            client_id = str(row.client_id) if row.client_id is not None else None
            return {"client_id": client_id}

    def create_client(
        self,
        client_id: str,
        client_name: str,
        contact_email: str | None = None,
        tally_version: str | None = None,
    ) -> dict[str, Any]:
        """Creates or updates a registered client record in the clients table."""
        now_utc = datetime.now(UTC).isoformat()
        stmt = pg_insert(Client).values(
            client_id=client_id,
            client_name=client_name,
            contact_email=contact_email,
            tally_version=tally_version,
            is_active=1,
            created_at=now_utc,
            updated_at=now_utc,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["client_id"],
            set_={
                "client_name": stmt.excluded.client_name,
                "contact_email": stmt.excluded.contact_email,
                "is_active": 1,
                "updated_at": stmt.excluded.updated_at,
                "tally_version": func.coalesce(stmt.excluded.tally_version, Client.tally_version),
            },
        )
        with self.session() as s:
            s.execute(stmt)
        log.info("Registered client: client_id='%s', client_name='%s'", client_id, client_name)
        return {
            "client_id": client_id,
            "client_name": client_name,
            "contact_email": contact_email,
            "tally_version": tally_version,
            "is_active": 1,
        }

    def get_client(self, client_id: str) -> Client | None:
        """Retrieves an active registered client from the clients table."""
        with self.session() as s:
            return s.scalars(
                select(Client).where(Client.client_id == client_id, Client.is_active == 1).limit(1)
            ).first()

    def get_client_by_contact_email(self, contact_email: str) -> Client | None:
        """Retrieves an active client record matching the provided contact email (case-insensitive)."""
        if not contact_email or not contact_email.strip():
            return None
        with self.session() as s:
            return s.scalars(
                select(Client)
                .where(
                    func.lower(Client.contact_email) == func.lower(contact_email.strip()),
                    Client.is_active == 1,
                )
                .order_by(Client.created_at.desc())
                .limit(1)
            ).first()

    def list_client_company_guids(self, client_id: str) -> list[str]:
        """Returns all company GUIDs mapped to the given client_id."""
        with self.session() as s:
            guids = s.scalars(
                select(ClientCompany.company_guid)
                .where(ClientCompany.client_id == client_id)
                .order_by(ClientCompany.company_guid.asc())
            ).all()
            return [str(g) for g in guids]

    def map_client_to_companies(self, client_id: str, company_guids: list[str]) -> None:
        """Maps company GUIDs to client_id after verifying no other client owns them."""
        if not company_guids:
            return
        now_utc = datetime.now(UTC).isoformat()
        with self.session() as s:
            for c_guid in company_guids:
                owner = s.scalars(
                    select(ClientCompany.client_id)
                    .where(ClientCompany.company_guid == c_guid)
                    .limit(1)
                ).first()
                if owner is not None and str(owner) != client_id:
                    log.warning(
                        "Company mapping rejected: company_guid='%s' is already mapped to '%s'",
                        c_guid,
                        owner,
                    )
                    raise PermissionError(
                        f"Company GUID '{c_guid}' is already mapped to another client"
                    )

            for c_guid in company_guids:
                s.execute(
                    pg_insert(ClientCompany)
                    .values(client_id=client_id, company_guid=c_guid, created_at=now_utc)
                    .on_conflict_do_nothing(index_elements=["client_id", "company_guid"])
                )
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
        with self.session() as s:
            ok = (
                s.execute(
                    select(literal(1))
                    .select_from(ClientCompany)
                    .join(Client, Client.client_id == ClientCompany.client_id)
                    .where(
                        ClientCompany.client_id == client_id,
                        ClientCompany.company_guid == company_guid,
                        Client.is_active == 1,
                    )
                    .limit(1)
                ).first()
                is not None
            )
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

        with self.session() as s:
            s.add(
                User(
                    user_id=assigned_user_id,
                    client_id=client_id,
                    email=normalized_email,
                    password_hash=password_hash,
                    full_name=full_name.strip(),
                    role=role.strip(),
                    is_active=1,
                    created_at=now_utc,
                    updated_at=now_utc,
                )
            )

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

    def get_user_by_email(self, email: str) -> User | None:
        """Retrieves a user record by email address."""
        normalized_email = email.strip().lower()
        with self.session() as s:
            return s.scalars(select(User).where(User.email == normalized_email).limit(1)).first()

    def get_user_by_id(self, user_id: str) -> User | None:
        """Retrieves a user record by user_id."""
        with self.session() as s:
            return s.scalars(select(User).where(User.user_id == user_id).limit(1)).first()

    def update_user_last_login(self, user_id: str) -> None:
        """Updates last_login_at timestamp for the user."""
        now_utc = datetime.now(UTC).isoformat()
        with self.session() as s:
            s.execute(
                update(User)
                .where(User.user_id == user_id)
                .values(last_login_at=now_utc, updated_at=now_utc)
            )

    def link_user_to_company(self, user_id: str, company_guid: str) -> None:
        """Grants fine-grained company access to a user."""
        now_utc = datetime.now(UTC).isoformat()
        with self.session() as s:
            s.execute(
                pg_insert(UserCompany)
                .values(user_id=user_id, company_guid=company_guid, created_at=now_utc)
                .on_conflict_do_nothing(index_elements=["user_id", "company_guid"])
            )

    def list_user_company_guids(self, user_id: str) -> list[str]:
        """Lists accessible company GUIDs for a user (combining explicit user links and client company mappings)."""
        with self.session() as s:
            explicit_guids = [
                str(g)
                for g in s.scalars(
                    select(UserCompany.company_guid)
                    .where(UserCompany.user_id == user_id)
                    .order_by(UserCompany.company_guid)
                ).all()
            ]
            if explicit_guids:
                return explicit_guids

            return [
                str(g)
                for g in s.scalars(
                    select(ClientCompany.company_guid)
                    .join(User, User.client_id == ClientCompany.client_id)
                    .where(User.user_id == user_id)
                    .order_by(ClientCompany.company_guid)
                ).all()
            ]

    def list_user_companies(self, user_id: str) -> list[dict[str, str]]:
        """Lists accessible companies with their IDs and names for a user."""
        guids = self.list_user_company_guids(user_id)
        if not guids:
            return []

        with self.session() as s:
            rows = s.execute(
                select(CanonicalCompany.company_id, CanonicalCompany.name).where(
                    CanonicalCompany.company_id.in_(guids)
                )
            ).all()
            canonical_map = {str(r.company_id): str(r.name) for r in rows}

        return [{"company_id": g, "company_name": canonical_map.get(g, g)} for g in guids]

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
        with self.session() as s:
            s.add(
                ChatMessage(
                    user_id=user_id,
                    company_id=company_id,
                    role=role.strip(),
                    content=content.strip(),
                    tool_called=tool_called,
                    created_at=now_utc,
                )
            )
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
        recent = (
            select(ChatMessage)
            .where(ChatMessage.user_id == user_id, ChatMessage.company_id == company_id)
            .order_by(ChatMessage.id.desc())
            .limit(limit)
            .subquery()
        )
        turn = aliased(ChatMessage, recent)
        with self.session() as s:
            rows = s.execute(
                select(turn.role, turn.content, turn.tool_called, turn.created_at).order_by(
                    turn.id.asc() if ascending else turn.id.desc()
                )
            ).mappings()
            return [dict(r) for r in rows]

    def clear_chat_messages(self, user_id: str, company_id: str) -> int:
        """Clears all turns from the chat stream for this user and company."""
        with self.session() as s:
            result = s.execute(
                delete(ChatMessage).where(
                    ChatMessage.user_id == user_id, ChatMessage.company_id == company_id
                )
            )
            deleted_count = _rowcount(result)
        log.info(
            "Cleared %d chat messages for user_id='%s', company_id='%s'",
            deleted_count,
            user_id,
            company_id,
        )
        return deleted_count

    def get_voucher_company_guid(self, voucher_guid: str) -> str | None:
        """Looks up the owning company_id (company GUID) for a voucher_guid."""
        with self.session() as s:
            company_id = s.scalars(
                select(Voucher.company_id).where(Voucher.guid == voucher_guid).limit(1)
            ).first()
            return str(company_id) if company_id is not None else None

    def get_any_canonical_company_id(self) -> str | None:
        """First canonical company id (unordered); the dashboards' fallback company (bug B04)."""
        with self.session() as s:
            company_id = s.scalars(select(CanonicalCompany.company_id).limit(1)).first()
            return str(company_id) if company_id is not None else None

    # ─── Companies CRUD ──────────────────────────────────────────────────────────

    def upsert_companies(self, rows: list[dict[str, Any]], client_id: str | None = None) -> int:
        """Bulk upserts company records on guid conflict and maps them to client_id."""
        if not rows:
            return 0
        now_utc = datetime.now(UTC).isoformat()
        company_guids = [str(r["guid"]) for r in rows]

        if client_id is not None:
            with self.session() as s:
                for c_guid in company_guids:
                    owner = s.scalars(
                        select(ClientCompany.client_id)
                        .where(ClientCompany.company_guid == c_guid)
                        .limit(1)
                    ).first()
                    if owner is not None and str(owner) != client_id:
                        raise PermissionError(
                            f"Company GUID '{c_guid}' is already mapped to another client"
                        )

        clean_rows = [_clean_row(COMPANY_SPEC, r, now_utc=now_utc) for r in rows]
        with self.session() as s:
            _bulk_upsert(s, Company, clean_rows, ["guid"])

        if client_id is not None:
            self.map_client_to_companies(client_id, company_guids)

        log.info(
            "Upserted %d companies into PostgreSQL (client_id=%s)",
            len(rows),
            client_id or "<none>",
        )
        return len(rows)

    def list_companies(self, client_id: str | None = None) -> list[Company]:
        """Lists companies (scoped to client_id when provided)."""
        stmt = select(Company)
        if client_id is not None:
            stmt = stmt.join(ClientCompany, ClientCompany.company_guid == Company.guid).where(
                ClientCompany.client_id == client_id
            )
        with self.session() as s:
            return list(s.scalars(stmt.order_by(Company.name.asc())).all())

    def get_company(self, guid: str | None = None, name: str | None = None) -> Company | None:
        """Fetches a company by guid or name."""
        if not guid and not name:
            return None
        stmt = select(Company)
        if guid:
            stmt = stmt.where(Company.guid == guid)
        if name:
            stmt = stmt.where(Company.name == name)
        with self.session() as s:
            return s.scalars(stmt.limit(1)).first()

    def delete_company(self, guid: str) -> bool:
        """Deletes a company by guid and removes its client mapping."""
        with self.session() as s:
            s.execute(delete(ClientCompany).where(ClientCompany.company_guid == guid))
            result = s.execute(delete(Company).where(Company.guid == guid))
            deleted = _rowcount(result) > 0
        log.info("Deleted company guid='%s' (success=%s)", guid, deleted)
        return deleted

    # ─── Master Tables CRUD (14 Tables) ──────────────────────────────────────────

    @staticmethod
    def _get_master_spec(table_name: str) -> TableSpec:
        if table_name not in MASTER_TABLE_SPECS:
            raise ValueError(f"Unsupported master table: '{table_name}'")
        return MASTER_TABLE_SPECS[table_name]

    @staticmethod
    def _get_master_model(table_name: str) -> Any:
        if table_name not in MASTER_MODELS:
            raise ValueError(f"Unsupported master table: '{table_name}'")
        return MASTER_MODELS[table_name]

    def upsert_master_rows(
        self, table_name: str, company_id: str, rows: list[dict[str, Any]]
    ) -> int:
        """Bulk upserts rows into any of the 14 master tables on guid conflict."""
        spec = self._get_master_spec(table_name)
        model = self._get_master_model(table_name)
        if not rows:
            return 0
        now_utc = datetime.now(UTC).isoformat()
        clean_rows = [_clean_row(spec, r, company_id=company_id, now_utc=now_utc) for r in rows]
        with self.session() as s:
            _bulk_upsert(s, model, clean_rows, ["guid"])
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
    ) -> list[Any]:
        """Lists master records for a company with optional alter_id watermark filter."""
        model = self._get_master_model(table_name)
        stmt = (
            select(model)
            .where(model.company_id == company_id, model.alter_id >= min_alter_id)
            .order_by(model.alter_id.asc(), model.name.asc())
            .limit(limit)
            .offset(offset)
        )
        with self.session() as s:
            return list(s.scalars(stmt).all())

    def get_master_row(self, table_name: str, company_id: str, guid: str) -> Any | None:
        """Fetches a single master record by company_id and guid."""
        model = self._get_master_model(table_name)
        with self.session() as s:
            return s.scalars(
                select(model).where(model.company_id == company_id, model.guid == guid).limit(1)
            ).first()

    def delete_master_row(self, table_name: str, company_id: str, guid: str) -> bool:
        """Deletes a single master record by company_id and guid."""
        model = self._get_master_model(table_name)
        with self.session() as s:
            result = s.execute(
                delete(model).where(model.company_id == company_id, model.guid == guid)
            )
            deleted = _rowcount(result) > 0
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
        header_rows = [
            _clean_row(VOUCHER_SPEC, h, company_id=company_id, now_utc=now_utc) for h in headers
        ]
        guids = [h["guid"] for h in headers if h.get("guid")]

        child_batches: list[tuple[str, list[dict[str, Any]] | None]] = [
            ("ledger_entries", ledger_entries),
            ("cost_centre_allocations", cost_centre_allocations),
            ("inventory_entries", inventory_entries),
            ("attendance_entries", attendance_entries),
        ]

        with self.session() as s:
            _bulk_upsert(s, Voucher, header_rows, ["guid"])

            if guids:
                for child_name in CHILD_TABLE_SPECS:
                    child_model: Any = CHILD_MODELS[child_name]
                    s.execute(delete(child_model).where(child_model.voucher_guid.in_(guids)))

            for child_name, child_rows in child_batches:
                if child_rows:
                    child_spec = CHILD_TABLE_SPECS[child_name]
                    s.execute(
                        insert(CHILD_MODELS[child_name]),
                        [_clean_row(child_spec, r) for r in child_rows],
                    )

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
    ) -> list[Voucher]:
        """Lists voucher headers with optional date, voucher_type, and alter_id filters."""
        stmt = select(Voucher).where(Voucher.company_id == company_id, Voucher.alter_id >= min_alter_id)
        if from_date:
            stmt = stmt.where(Voucher.date >= from_date)
        if to_date:
            stmt = stmt.where(Voucher.date <= to_date)
        if voucher_type_name:
            stmt = stmt.where(Voucher.voucher_type_name == voucher_type_name)
        stmt = stmt.order_by(Voucher.date.asc(), Voucher.alter_id.asc()).limit(limit).offset(offset)
        with self.session() as s:
            return list(s.scalars(stmt).all())

    def get_voucher_with_entries(self, company_id: str, guid: str) -> dict[str, Any] | None:
        """Retrieves a voucher header along with all 4 child entry collections."""
        with self.session() as s:
            voucher = s.scalars(
                select(Voucher).where(Voucher.company_id == company_id, Voucher.guid == guid).limit(1)
            ).first()
            if voucher is None:
                return None

            result = voucher.to_dict()
            for child_name in CHILD_TABLE_SPECS:
                child_model: Any = CHILD_MODELS[child_name]
                children = s.scalars(
                    select(child_model)
                    .where(child_model.voucher_guid == guid)
                    .order_by(child_model.id.asc())
                ).all()
                result[child_name] = [c.to_dict() for c in children]
            return result

    def delete_voucher(self, company_id: str, guid: str) -> bool:
        """Deletes a voucher header and its child entries."""
        with self.session() as s:
            for child_name in CHILD_TABLE_SPECS:
                child_model: Any = CHILD_MODELS[child_name]
                s.execute(delete(child_model).where(child_model.voucher_guid == guid))
            result = s.execute(
                delete(Voucher).where(Voucher.company_id == company_id, Voucher.guid == guid)
            )
            deleted = _rowcount(result) > 0
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

    def list_child_entries(self, voucher_guid: str, child_table: str) -> list[Any]:
        """Lists child entries for a voucher from the specified child_table."""
        self._get_child_spec(child_table)
        model: Any = CHILD_MODELS[child_table]
        with self.session() as s:
            return list(
                s.scalars(
                    select(model).where(model.voucher_guid == voucher_guid).order_by(model.id.asc())
                ).all()
            )

    def replace_child_entries(
        self, voucher_guid: str, child_table: str, rows: list[dict[str, Any]]
    ) -> int:
        """Replaces all child entries for voucher_guid in child_table."""
        spec = self._get_child_spec(child_table)
        model: Any = CHILD_MODELS[child_table]
        clean_rows = [_clean_row(spec, {**r, "voucher_guid": voucher_guid}) for r in rows]

        with self.session() as s:
            s.execute(delete(model).where(model.voucher_guid == voucher_guid))
            if clean_rows:
                s.execute(insert(model), clean_rows)
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
        self._get_child_spec(child_table)
        model: Any = CHILD_MODELS[child_table]
        stmt = delete(model).where(model.voucher_guid == voucher_guid)
        if entry_id is not None:
            stmt = stmt.where(model.id == entry_id)
        with self.session() as s:
            deleted_count = _rowcount(s.execute(stmt))
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
        scoped_models: dict[str, Any] = {**MASTER_MODELS, "vouchers": Voucher}

        with self.session() as s:
            for table_name, model in scoped_models.items():
                row = s.execute(
                    select(
                        func.count().label("row_count"),
                        func.coalesce(func.max(model.master_id), 0).label("max_master_id"),
                        func.coalesce(func.max(model.alter_id), 0).label("max_alter_id"),
                    ).where(model.company_id == company_id)
                ).one()
                watermarks[table_name] = {
                    "row_count": int(row.row_count or 0),
                    "max_master_id": int(row.max_master_id or 0),
                    "max_alter_id": int(row.max_alter_id or 0),
                }
        return watermarks
