"""FastAPI application exposing authenticated, query-parameterized CRUD and batch endpoints."""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend_ETL.agent_service import O3AgentService
from backend_ETL.analytics_service import AnalyticsService
from backend_ETL.auth_deps import get_current_authenticated_user
from backend_ETL.canonical_runner import CanonicalPollerRunner
from backend_ETL.config import BackendConfig, load_backend_config
from backend_ETL.date_utils import parse_date_flexible
from backend_ETL.db import PostgresManager
from backend_ETL.schemas import (
    ChatMessageRequest,
    ChildEntriesBatchRequest,
    ClientCreateRequest,
    CompanyBatchRequest,
    CompanyPayload,
    MasterBatchRequest,
    UserLoginRequest,
    UserRegisterRequest,
    VoucherBatchRequest,
    VoucherSingleRequest,
)
from backend_ETL.security import (
    create_jwt_access_token,
    hash_user_password,
    verify_user_password,
)

log = logging.getLogger(__name__)

AuthHeader = Annotated[str | None, Header(alias="Authorization")]


def _extract_bearer_token(authorization: str | None) -> str:
    """Extracts the raw token from an Authorization: Bearer <token> header."""
    if not authorization:
        log.warning("Authentication rejected: missing Authorization header")
        raise HTTPException(status_code=403, detail="Missing Authorization Bearer token")
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        log.warning("Authentication rejected: invalid Bearer header format")
        raise HTTPException(status_code=403, detail="Invalid Authorization Bearer header format")
    return parts[1].strip()


def create_app(
    db: PostgresManager | None = None,
    start_poller: bool | None = None,
    config: BackendConfig | None = None,
) -> FastAPI:
    """Creates and configures the FastAPI application."""
    cfg = config or load_backend_config()
    if db is None:
        db = PostgresManager(dsn=cfg.get_dsn(), use_pool=False)
        should_start_poller = True if start_poller is None else start_poller
    else:
        should_start_poller = False if start_poller is None else start_poller

    manager: PostgresManager = db
    runner = CanonicalPollerRunner(db=manager, cfg=cfg.etl)
    analytics_service = AnalyticsService(db=manager)
    agent_service = O3AgentService(
        db=manager,
        model_name=cfg.ollama_model,
        host=cfg.ollama_host,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if should_start_poller and runner.cfg.enabled and runner.cfg.execution_mode == "polling":
            runner.start()
        yield
        if should_start_poller:
            runner.stop()

    app = FastAPI(
        title="Tally Replication Backend API",
        version="1.0.0",
        description="Authenticated PostgreSQL CRUD and batch replication API for Tally tables.",
        lifespan=lifespan,
    )
    app.state.db = manager
    app.state.canonical_runner = runner

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next: Any) -> Any:
        start_time = time.perf_counter()
        client_host = request.client.host if request.client else "unknown"
        method = request.method
        url_path = request.url.path
        query = str(request.url.query)
        full_path = f"{url_path}?{query}" if query else url_path

        try:
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            if response.status_code >= 400:
                log.warning(
                    "HTTP %d %s %s from %s (took %.2fms)",
                    response.status_code,
                    method,
                    full_path,
                    client_host,
                    elapsed_ms,
                )
            else:
                log.info(
                    "HTTP %d %s %s from %s (took %.2fms)",
                    response.status_code,
                    method,
                    full_path,
                    client_host,
                    elapsed_ms,
                )
            return response
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            log.error(
                "Unhandled exception on %s %s from %s (took %.2fms): %s",
                method,
                full_path,
                client_host,
                elapsed_ms,
                e,
                exc_info=True,
            )
            raise

    def require_token_and_client(
        authorization: str | None,
        client_id: str,
        require_registered_client: bool = True,
    ) -> str:
        """Verifies Bearer token matches client_id (and optionally that client is registered)."""
        raw_token = _extract_bearer_token(authorization)
        token_info = manager.verify_bearer_token(raw_token)
        if not token_info or token_info["client_id"] != client_id:
            log.warning(
                "Auth rejected: Bearer token client '%s' != requested client_id '%s'",
                token_info.get("client_id") if token_info else "<none>",
                client_id,
            )
            raise HTTPException(
                status_code=403,
                detail="Forbidden: Bearer token and client_id do not match",
            )
        if require_registered_client and not manager.get_client(client_id):
            log.warning(
                "Auth rejected: client_id '%s' is not registered in clients table", client_id
            )
            raise HTTPException(
                status_code=403,
                detail="Forbidden: Client must be created via POST /api/v1/clients first",
            )
        return client_id

    def require_three_way_match(
        authorization: str | None,
        client_id: str,
        company_guid: str,
    ) -> None:
        """Enforces that Bearer Token, client_id, and company_guid all match (or raises 403)."""
        require_token_and_client(authorization, client_id, require_registered_client=True)
        if not manager.verify_client_company_access(client_id, company_guid):
            log.warning(
                "3-Way match failed: client_id '%s' has no access to company_id '%s'",
                client_id,
                company_guid,
            )
            raise HTTPException(
                status_code=403,
                detail="Forbidden: client_id does not have access to the specified company_id",
            )

    # ─── Health & Replication Watermarks ─────────────────────────────────────────

    @app.get("/health")
    def health() -> dict[str, str]:
        try:
            ok = manager.check_health()
        except Exception as e:
            log.error("Health check database error: %s", e)
            raise HTTPException(status_code=503, detail=f"Database unavailable: {e}") from e
        return {"status": "ok" if ok else "degraded"}

    # ─── Human Authentication & User Onboarding Endpoints ───────────────────────

    @app.post("/api/v1/auth/register")
    def register_organization_and_owner(
        registration_payload: UserRegisterRequest,
    ) -> dict[str, Any]:
        """Registers a new organization client and creates its initial owner user account."""
        normalized_user_email = registration_payload.email.strip().lower()

        # Check if an account already exists with this email address
        existing_user_record = manager.get_user_by_email(normalized_user_email)
        if existing_user_record is not None:
            raise HTTPException(
                status_code=400,
                detail="An account with this email address already exists. Please log in.",
            )

        # Check if organization was already pre-registered by Tally Sync via contact_email
        existing_client = manager.get_client_by_contact_email(normalized_user_email)
        if existing_client is not None:
            effective_client_id = existing_client.client_id
            client_org_name = existing_client.client_name or registration_payload.client_name.strip()
            log.info(
                "Linking user '%s' to existing Tally-synced organization '%s' (%s)",
                normalized_user_email,
                client_org_name,
                effective_client_id,
            )
        else:
            # 1. Create client organization record if not pre-seeded by Tally Sync
            effective_client_id = str(uuid.uuid4())
            manager.create_client(
                client_id=effective_client_id,
                client_name=registration_payload.client_name.strip(),
                contact_email=normalized_user_email,
            )

        # 2. Hash password with Argon2id one-way algorithm
        salted_password_hash: str = hash_user_password(registration_payload.password)

        # 3. Create the owner user record
        created_user_account = manager.create_user(
            client_id=effective_client_id,
            email=normalized_user_email,
            password_hash=salted_password_hash,
            full_name=registration_payload.full_name.strip(),
            role="owner",
        )

        # 4. Automatically link user to any pre-synced company GUIDs of this client
        synced_companies = manager.list_client_company_guids(effective_client_id)
        for comp_guid in synced_companies:
            manager.link_user_to_company(created_user_account["user_id"], comp_guid)

        # 5. Issue initial JWT access token for immediate session login
        jwt_access_token_string: str = create_jwt_access_token(
            token_payload_claims={
                "user_id": created_user_account["user_id"],
                "client_id": created_user_account["client_id"],
                "email": created_user_account["email"],
                "full_name": created_user_account["full_name"],
                "role": created_user_account["role"],
            }
        )

        log.info(
            "Registered new organization '%s' with owner '%s'",
            registration_payload.client_name,
            normalized_user_email,
        )
        return {
            "status": "ok",
            "access_token": jwt_access_token_string,
            "token_type": "bearer",
            "user": created_user_account,
        }

    @app.post("/api/v1/auth/login")
    def login_user(
        login_credentials: UserLoginRequest,
    ) -> dict[str, Any]:
        """Authenticates a user using email and password, returning a signed JWT access token."""
        normalized_login_email = login_credentials.email.strip().lower()
        user_record = manager.get_user_by_email(normalized_login_email)

        if not user_record:
            # Check if this email was registered during Tally Sync but password not yet created
            existing_client = manager.get_client_by_contact_email(normalized_login_email)
            if existing_client is not None:
                log.info(
                    "Email '%s' belongs to Tally-synced client '%s' but user password not set yet",
                    normalized_login_email,
                    existing_client.client_name,
                )
                raise HTTPException(
                    status_code=403,
                    detail=(
                        f"Tally Sync has synced books for '{existing_client.client_name}', "
                        "but your dashboard password has not been set yet. "
                        "Please use the 'Set Password / Activate' tab to activate your access."
                    ),
                )
            log.warning("Login failed: email '%s' not found", normalized_login_email)
            raise HTTPException(status_code=401, detail="Invalid email or password.")

        is_password_valid: bool = verify_user_password(
            plain_text_password_candidate=login_credentials.password,
            hashed_password_from_database=user_record.password_hash,
        )
        if not is_password_valid:
            log.warning("Login failed: password mismatch for '%s'", normalized_login_email)
            raise HTTPException(status_code=401, detail="Invalid email or password.")

        if not user_record.is_active:
            log.warning("Login rejected: deactivated user '%s'", normalized_login_email)
            raise HTTPException(
                status_code=403,
                detail="User account is deactivated. Please contact support.",
            )

        # Update last login timestamp
        manager.update_user_last_login(user_record.user_id)

        # Fetch accessible companies
        accessible_companies_list = manager.list_user_companies(user_record.user_id)

        jwt_access_token_string: str = create_jwt_access_token(
            token_payload_claims={
                "user_id": user_record.user_id,
                "client_id": user_record.client_id,
                "email": user_record.email,
                "full_name": user_record.full_name,
                "role": user_record.role,
            }
        )

        log.info("Successful login for user '%s' (%s)", user_record.full_name, normalized_login_email)
        return {
            "status": "ok",
            "access_token": jwt_access_token_string,
            "token_type": "bearer",
            "user": {
                "user_id": user_record.user_id,
                "client_id": user_record.client_id,
                "email": user_record.email,
                "full_name": user_record.full_name,
                "role": user_record.role,
                "accessible_companies": accessible_companies_list,
            },
        }

    @app.get("/api/v1/auth/me")
    def get_current_user_profile(
        current_authenticated_user: Annotated[dict[str, Any], Depends(get_current_authenticated_user)],
    ) -> dict[str, Any]:
        """Returns the profile and accessible company GUIDs for the currently authenticated user."""
        current_user_id: str = current_authenticated_user["user_id"]
        accessible_companies = manager.list_user_companies(current_user_id)
        return {
            "user": {
                **current_authenticated_user,
                "accessible_companies": accessible_companies,
            }
        }

    @app.get("/api/v1/watermarks")
    def get_watermarks(
        client_id: Annotated[str, Query(description="Client ID")],
        company_id: Annotated[str, Query(description="Company GUID")],
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        require_three_way_match(authorization, client_id, company_id)
        return {
            "client_id": client_id,
            "company_id": company_id,
            "tables": manager.get_company_watermarks(company_id),
        }

    # ─── Client Onboarding CRUD ──────────────────────────────────────────────────

    @app.post("/api/v1/clients")
    def register_client(
        payload: ClientCreateRequest,
        client_id: Annotated[
            str | None,
            Query(description="Optional Client ID (auto-generated if omitted)"),
        ] = None,
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        raw_token = _extract_bearer_token(authorization)
        token_info = manager.verify_bearer_token(raw_token)
        if not token_info:
            log.warning("Client registration failed: invalid or deactivated token")
            raise HTTPException(
                status_code=403,
                detail="Forbidden: Invalid or inactive Bearer token",
            )

        bound_client_id = token_info.get("client_id")
        if bound_client_id is not None:
            effective_client_id = client_id or bound_client_id
            if effective_client_id != bound_client_id:
                log.warning(
                    "Client registration failed: client_id '%s' != token bound client '%s'",
                    effective_client_id,
                    bound_client_id,
                )
                raise HTTPException(
                    status_code=403,
                    detail="Forbidden: Bearer token and client_id do not match",
                )
        else:
            # First-time onboarding with unassigned token!
            effective_client_id = (client_id or "").strip() or str(uuid.uuid4())
            manager.bind_token_to_client(raw_token, effective_client_id)
            log.info("Bound unassigned token to new client_id='%s'", effective_client_id)

        client_record = manager.create_client(
            client_id=effective_client_id,
            client_name=payload.client_name,
            contact_email=payload.contact_email,
            tally_version=payload.tally_version,
        )
        log.info(
            "Client successfully registered: client_id='%s', name='%s'",
            effective_client_id,
            payload.client_name,
        )
        return {"status": "ok", "data": client_record}

    @app.get("/api/v1/clients")
    def get_client_info(
        client_id: Annotated[str, Query(description="Client ID")],
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        require_token_and_client(authorization, client_id, require_registered_client=True)
        client_record = manager.get_client(client_id)
        company_guids = manager.list_client_company_guids(client_id)
        return {
            "data": {
                **(client_record.to_dict() if client_record else {}),
                "company_guids": company_guids,
            }
        }

    # ─── Companies CRUD ──────────────────────────────────────────────────────────

    @app.post("/api/v1/companies/batch")
    def upsert_companies_batch(
        payload: CompanyBatchRequest,
        client_id: Annotated[str, Query(description="Client ID")],
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        require_token_and_client(authorization, client_id, require_registered_client=True)
        rows = [r.model_dump() for r in payload.rows]
        try:
            count = manager.upsert_companies(rows, client_id=client_id)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e
        return {"status": "ok", "upserted_count": count}

    @app.post("/api/v1/companies")
    def create_or_upsert_company(
        payload: CompanyPayload,
        client_id: Annotated[str, Query(description="Client ID")],
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        require_token_and_client(authorization, client_id, require_registered_client=True)
        try:
            count = manager.upsert_companies([payload.model_dump()], client_id=client_id)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e
        return {"status": "ok", "upserted_count": count, "guid": payload.guid}

    @app.get("/api/v1/companies")
    def get_companies(
        client_id: Annotated[str, Query(description="Client ID")],
        guid: Annotated[str | None, Query(description="Optional company GUID")] = None,
        name: Annotated[str | None, Query(description="Optional company Name")] = None,
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        require_token_and_client(authorization, client_id, require_registered_client=True)
        if guid or name:
            comp = manager.get_company(guid=guid, name=name)
            if not comp:
                raise HTTPException(status_code=404, detail="Company not found")
            if not manager.verify_client_company_access(client_id, comp.guid):
                raise HTTPException(
                    status_code=403,
                    detail="Forbidden: client_id does not have access to this company",
                )
            return {"data": comp.to_dict()}
        return {"data": [c.to_dict() for c in manager.list_companies(client_id=client_id)]}

    @app.put("/api/v1/companies")
    def update_company(
        payload: dict[str, Any],
        client_id: Annotated[str, Query(description="Client ID")],
        guid: Annotated[str, Query(description="Company GUID to update")],
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        require_three_way_match(authorization, client_id, guid)
        existing = manager.get_company(guid=guid)
        if not existing:
            raise HTTPException(status_code=404, detail="Company not found")
        merged = {**existing.to_dict(), **payload, "guid": guid}
        manager.upsert_companies([merged], client_id=client_id)
        return {"status": "ok", "guid": guid}

    @app.delete("/api/v1/companies")
    def delete_company(
        client_id: Annotated[str, Query(description="Client ID")],
        guid: Annotated[str, Query(description="Company GUID to delete")],
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        require_three_way_match(authorization, client_id, guid)
        deleted = manager.delete_company(guid)
        if not deleted:
            raise HTTPException(status_code=404, detail="Company not found")
        return {"status": "ok", "deleted": True, "guid": guid}

    # ─── Master Tables CRUD (14 Tables) ──────────────────────────────────────────

    @app.post("/api/v1/masters/batch")
    def upsert_masters_batch(
        payload: MasterBatchRequest,
        client_id: Annotated[str, Query(description="Client ID")],
        company_id: Annotated[str, Query(description="Company GUID")],
        table_name: Annotated[str, Query(description="Target master table name")],
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        require_three_way_match(authorization, client_id, company_id)
        try:
            count = manager.upsert_master_rows(table_name, company_id, payload.rows)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except KeyError as e:
            raise HTTPException(
                status_code=422, detail=f"Missing required field in row: {e}"
            ) from e
        return {"status": "ok", "table_name": table_name, "upserted_count": count}

    @app.post("/api/v1/masters")
    def create_or_upsert_master(
        row: dict[str, Any],
        client_id: Annotated[str, Query(description="Client ID")],
        company_id: Annotated[str, Query(description="Company GUID")],
        table_name: Annotated[str, Query(description="Target master table name")],
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        require_three_way_match(authorization, client_id, company_id)
        try:
            count = manager.upsert_master_rows(table_name, company_id, [row])
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except KeyError as e:
            raise HTTPException(
                status_code=422, detail=f"Missing required field in row: {e}"
            ) from e
        return {
            "status": "ok",
            "table_name": table_name,
            "upserted_count": count,
            "guid": row.get("guid"),
        }

    @app.get("/api/v1/masters")
    def get_masters(
        client_id: Annotated[str, Query(description="Client ID")],
        company_id: Annotated[str, Query(description="Company GUID")],
        table_name: Annotated[str, Query(description="Target master table name")],
        guid: Annotated[str | None, Query(description="Optional record GUID")] = None,
        min_alter_id: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=5000)] = 500,
        offset: Annotated[int, Query(ge=0)] = 0,
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        require_three_way_match(authorization, client_id, company_id)
        try:
            if guid is not None:
                record = manager.get_master_row(table_name, company_id, guid)
                if not record:
                    raise HTTPException(status_code=404, detail="Master record not found")
                return {"data": record.to_dict()}
            rows = [
                r.to_dict()
                for r in manager.list_master_rows(
                    table_name=table_name,
                    company_id=company_id,
                    min_alter_id=min_alter_id,
                    limit=limit,
                    offset=offset,
                )
            ]
            return {"data": rows, "count": len(rows)}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.put("/api/v1/masters")
    def update_master(
        payload: dict[str, Any],
        client_id: Annotated[str, Query(description="Client ID")],
        company_id: Annotated[str, Query(description="Company GUID")],
        table_name: Annotated[str, Query(description="Target master table name")],
        guid: Annotated[str, Query(description="Record GUID to update")],
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        require_three_way_match(authorization, client_id, company_id)
        try:
            existing = manager.get_master_row(table_name, company_id, guid)
            if not existing:
                raise HTTPException(status_code=404, detail="Master record not found")
            merged = {**existing.to_dict(), **payload, "guid": guid, "company_id": company_id}
            manager.upsert_master_rows(table_name, company_id, [merged])
            return {"status": "ok", "table_name": table_name, "guid": guid}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @app.delete("/api/v1/masters")
    def delete_master(
        client_id: Annotated[str, Query(description="Client ID")],
        company_id: Annotated[str, Query(description="Company GUID")],
        table_name: Annotated[str, Query(description="Target master table name")],
        guid: Annotated[str, Query(description="Record GUID to delete")],
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        require_three_way_match(authorization, client_id, company_id)
        try:
            deleted = manager.delete_master_row(table_name, company_id, guid)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if not deleted:
            raise HTTPException(status_code=404, detail="Master record not found")
        return {"status": "ok", "deleted": True, "table_name": table_name, "guid": guid}

    # ─── Vouchers & Child Entries CRUD ───────────────────────────────────────────

    @app.post("/api/v1/vouchers/batch")
    def upsert_vouchers_batch(
        payload: VoucherBatchRequest,
        client_id: Annotated[str, Query(description="Client ID")],
        company_id: Annotated[str, Query(description="Company GUID")],
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        require_three_way_match(authorization, client_id, company_id)
        try:
            count = manager.upsert_vouchers_with_entries(
                company_id=company_id,
                headers=payload.headers,
                ledger_entries=payload.ledger_entries,
                inventory_entries=payload.inventory_entries,
                cost_centre_allocations=payload.cost_centre_allocations,
                attendance_entries=payload.attendance_entries,
            )
        except KeyError as e:
            raise HTTPException(
                status_code=422, detail=f"Missing required voucher field: {e}"
            ) from e
        return {"status": "ok", "upserted_count": count}

    @app.post("/api/v1/vouchers")
    def create_or_upsert_voucher(
        payload: VoucherSingleRequest,
        client_id: Annotated[str, Query(description="Client ID")],
        company_id: Annotated[str, Query(description="Company GUID")],
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        require_three_way_match(authorization, client_id, company_id)
        try:
            guid = str(payload.header["guid"])
            le = [{**r, "voucher_guid": guid} for r in payload.ledger_entries]
            ie = [{**r, "voucher_guid": guid} for r in payload.inventory_entries]
            cca = [{**r, "voucher_guid": guid} for r in payload.cost_centre_allocations]
            ae = [{**r, "voucher_guid": guid} for r in payload.attendance_entries]
            count = manager.upsert_vouchers_with_entries(
                company_id=company_id,
                headers=[payload.header],
                ledger_entries=le,
                inventory_entries=ie,
                cost_centre_allocations=cca,
                attendance_entries=ae,
            )
        except KeyError as e:
            raise HTTPException(
                status_code=422, detail=f"Missing required voucher field: {e}"
            ) from e
        return {"status": "ok", "upserted_count": count, "guid": guid}

    @app.get("/api/v1/vouchers")
    def get_vouchers(
        client_id: Annotated[str, Query(description="Client ID")],
        company_id: Annotated[str, Query(description="Company GUID")],
        guid: Annotated[str | None, Query(description="Optional voucher GUID")] = None,
        from_date: Annotated[str | None, Query()] = None,
        to_date: Annotated[str | None, Query()] = None,
        voucher_type_name: Annotated[str | None, Query()] = None,
        min_alter_id: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=5000)] = 500,
        offset: Annotated[int, Query(ge=0)] = 0,
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        require_three_way_match(authorization, client_id, company_id)
        if guid is not None:
            voucher = manager.get_voucher_with_entries(company_id=company_id, guid=guid)
            if not voucher:
                raise HTTPException(status_code=404, detail="Voucher not found")
            return {"data": voucher}
        rows = [
            v.to_dict()
            for v in manager.list_vouchers(
                company_id=company_id,
                from_date=from_date,
                to_date=to_date,
                voucher_type_name=voucher_type_name,
                min_alter_id=min_alter_id,
                limit=limit,
                offset=offset,
            )
        ]
        return {"data": rows, "count": len(rows)}

    @app.put("/api/v1/vouchers")
    def update_voucher(
        payload: VoucherSingleRequest,
        client_id: Annotated[str, Query(description="Client ID")],
        company_id: Annotated[str, Query(description="Company GUID")],
        guid: Annotated[str, Query(description="Voucher GUID to update")],
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        require_three_way_match(authorization, client_id, company_id)
        existing = manager.get_voucher_with_entries(company_id=company_id, guid=guid)
        if not existing:
            raise HTTPException(status_code=404, detail="Voucher not found")
        merged_header = {**existing, **payload.header, "guid": guid, "company_id": company_id}
        le = [{**r, "voucher_guid": guid} for r in payload.ledger_entries]
        ie = [{**r, "voucher_guid": guid} for r in payload.inventory_entries]
        cca = [{**r, "voucher_guid": guid} for r in payload.cost_centre_allocations]
        ae = [{**r, "voucher_guid": guid} for r in payload.attendance_entries]
        manager.upsert_vouchers_with_entries(
            company_id=company_id,
            headers=[merged_header],
            ledger_entries=le,
            inventory_entries=ie,
            cost_centre_allocations=cca,
            attendance_entries=ae,
        )
        return {"status": "ok", "guid": guid}

    @app.delete("/api/v1/vouchers")
    def delete_voucher(
        client_id: Annotated[str, Query(description="Client ID")],
        company_id: Annotated[str, Query(description="Company GUID")],
        guid: Annotated[str, Query(description="Voucher GUID to delete")],
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        require_three_way_match(authorization, client_id, company_id)
        deleted = manager.delete_voucher(company_id=company_id, guid=guid)
        if not deleted:
            raise HTTPException(status_code=404, detail="Voucher not found")
        return {"status": "ok", "deleted": True, "guid": guid}

    # ─── Direct Child Entry Endpoints ────────────────────────────────────────────

    def _verify_voucher_access(
        authorization: str | None, client_id: str, voucher_guid: str
    ) -> None:
        require_token_and_client(authorization, client_id, require_registered_client=True)
        company_guid = manager.get_voucher_company_guid(voucher_guid)
        if not company_guid or not manager.verify_client_company_access(client_id, company_guid):
            log.warning(
                "Access rejected: client_id '%s' has no access to voucher '%s' (company: '%s')",
                client_id,
                voucher_guid,
                company_guid or "<unknown>",
            )
            raise HTTPException(
                status_code=403,
                detail="Forbidden: client_id does not have access to this voucher",
            )

    @app.get("/api/v1/voucher-entries")
    def get_voucher_entries(
        client_id: Annotated[str, Query(description="Client ID")],
        voucher_guid: Annotated[str, Query(description="Parent voucher GUID")],
        child_table: Annotated[str, Query(description="Child table name")],
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        _verify_voucher_access(authorization, client_id, voucher_guid)
        try:
            rows = [
                e.to_dict()
                for e in manager.list_child_entries(voucher_guid=voucher_guid, child_table=child_table)
            ]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return {"data": rows, "count": len(rows)}

    @app.put("/api/v1/voucher-entries")
    def replace_voucher_entries(
        payload: ChildEntriesBatchRequest,
        client_id: Annotated[str, Query(description="Client ID")],
        voucher_guid: Annotated[str, Query(description="Parent voucher GUID")],
        child_table: Annotated[str, Query(description="Child table name")],
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        _verify_voucher_access(authorization, client_id, voucher_guid)
        try:
            count = manager.replace_child_entries(
                voucher_guid=voucher_guid,
                child_table=child_table,
                rows=payload.rows,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return {
            "status": "ok",
            "voucher_guid": voucher_guid,
            "child_table": child_table,
            "replaced_count": count,
        }

    @app.delete("/api/v1/voucher-entries")
    def delete_voucher_entries(
        client_id: Annotated[str, Query(description="Client ID")],
        voucher_guid: Annotated[str, Query(description="Parent voucher GUID")],
        child_table: Annotated[str, Query(description="Child table name")],
        entry_id: Annotated[int | None, Query(description="Optional child row ID")] = None,
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        _verify_voucher_access(authorization, client_id, voucher_guid)
        try:
            deleted_count = manager.delete_child_entries(
                voucher_guid=voucher_guid,
                child_table=child_table,
                entry_id=entry_id,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return {
            "status": "ok",
            "voucher_guid": voucher_guid,
            "child_table": child_table,
            "deleted_count": deleted_count,
        }

    # ─── Canonical Domain Model Transformation Trigger ───────────────────────────

    @app.post("/api/v1/canonical/transform")
    def trigger_canonical_transform(
        client_id: Annotated[str, Query(description="Client ID")],
        company_id: Annotated[
            str | None, Query(description="Optional specific Company GUID")
        ] = None,
        authorization: AuthHeader = None,
    ) -> dict[str, Any]:
        """Manually triggers canonical transformation for mapped companies."""
        require_token_and_client(authorization, client_id, require_registered_client=True)

        if company_id:
            if not manager.verify_client_company_access(client_id, company_id):
                raise HTTPException(
                    status_code=403,
                    detail=(
                        f"Forbidden: Client '{client_id}' does not have "
                        f"access to company '{company_id}'"
                    ),
                )
            target_companies = [company_id]
        else:
            target_companies = manager.list_client_company_guids(client_id)

        runner_inst: CanonicalPollerRunner = app.state.canonical_runner
        total_processed = 0
        all_counts: dict[str, int] = defaultdict(int)
        processed_guids: list[str] = []

        for c_id in target_companies:
            res = runner_inst.run_once(company_id=c_id)
            total_processed += res.get("companies_processed", 0)
            processed_guids.extend(res.get("company_ids", []))
            for k, v in res.get("counts", {}).items():
                all_counts[k] += v

        return {
            "status": "ok",
            "client_id": client_id,
            "companies_processed": total_processed,
            "company_ids": processed_guids,
            "counts": dict(all_counts),
        }

    # ─── Analytics & Executive KPI Endpoints ─────────────────────────────────────

    @app.get("/api/v1/analytics/overview")
    def get_analytics_overview(
        current_authenticated_user: Annotated[dict[str, Any], Depends(get_current_authenticated_user)],
        company_id: Annotated[str | None, Query(description="Company GUID")] = None,
        period: Annotated[
            str,
            Query(description="Period preset: mtd, last_30_days, last_60_days, last_90_days, current_fy, previous_fy, custom"),
        ] = "mtd",
        start_date: Annotated[str | None, Query(description="Custom start date (YYYY-MM-DD or DD-MM-YYYY)")] = None,
        end_date: Annotated[str | None, Query(description="Custom end date (YYYY-MM-DD or DD-MM-YYYY)")] = None,
        reference_date: Annotated[str | None, Query(description="Optional anchor reference date")] = None,
    ) -> dict[str, Any]:
        """Returns the 4 Executive KPIs with period comparisons and greeting."""
        target_company_id = company_id
        if not target_company_id:
            user_companies = manager.list_user_company_guids(current_authenticated_user["user_id"])
            if user_companies:
                target_company_id = user_companies[0]
            else:
                target_company_id = manager.get_any_canonical_company_id() or target_company_id

        if not target_company_id:
            log.warning(
                "analytics/overview: no company resolved (user_id=%s, requested=%s); canonical_companies is empty or user has no linked companies",
                current_authenticated_user.get("user_id"),
                company_id,
            )
            raise HTTPException(status_code=404, detail="No active company found for analytics overview.")
        log.info(
            "analytics/overview: user_id=%s company_id=%s (requested=%s) period=%s",
            current_authenticated_user.get("user_id"),
            target_company_id,
            company_id,
            period,
        )

        parsed_ref_date = parse_date_flexible(reference_date) if reference_date else None
        parsed_custom_start = parse_date_flexible(start_date) if start_date else None
        parsed_custom_end = parse_date_flexible(end_date) if end_date else None

        user_name = current_authenticated_user.get("full_name") or "Manoj"
        first_name = user_name.split()[0] if user_name else "Manoj"
        try:
            result = analytics_service.get_executive_overview(
                company_id=target_company_id,
                period_preset=period,
                user_display_name=first_name,
                reference_date=parsed_ref_date,
                custom_start=parsed_custom_start,
                custom_end=parsed_custom_end,
            )
        except Exception:
            log.exception("analytics/overview failed for company_id=%s period=%s", target_company_id, period)
            raise
        kpi_raw = {k: v.get("raw_value") for k, v in result.get("kpis", {}).items()}
        if not any(kpi_raw.values()):
            log.warning(
                "analytics/overview: all KPIs are zero for company_id=%s period=%s %s -- no data in range, or company_id has no canonical rows",
                target_company_id,
                period,
                kpi_raw,
            )
        else:
            log.info("analytics/overview: company_id=%s KPIs=%s", target_company_id, kpi_raw)
        return result

    @app.get("/api/v1/analytics/aging")
    def get_analytics_aging(
        current_authenticated_user: Annotated[dict[str, Any], Depends(get_current_authenticated_user)],
        company_id: Annotated[str | None, Query(description="Company GUID")] = None,
        limit: Annotated[int, Query(description="Max records to return")] = 5,
    ) -> dict[str, Any]:
        """Returns slowest paying customers and DSO benchmarks."""
        target_company_id = company_id
        if not target_company_id:
            user_companies = manager.list_user_company_guids(current_authenticated_user["user_id"])
            target_company_id = user_companies[0] if user_companies else None
            if not target_company_id:
                target_company_id = manager.get_any_canonical_company_id() or target_company_id

        if not target_company_id:
            raise HTTPException(status_code=404, detail="No active company found.")

        return analytics_service.get_slowest_paying_customers(
            company_id=target_company_id,
            limit=limit,
        )

    @app.get("/api/v1/analytics/unpaid")
    def get_analytics_unpaid(
        current_authenticated_user: Annotated[dict[str, Any], Depends(get_current_authenticated_user)],
        company_id: Annotated[str | None, Query(description="Company GUID")] = None,
        limit: Annotated[int, Query(description="Max open invoices")] = 10,
    ) -> list[dict[str, Any]]:
        """Returns unpaid and overdue customer invoices."""
        target_company_id = company_id
        if not target_company_id:
            user_companies = manager.list_user_company_guids(current_authenticated_user["user_id"])
            target_company_id = user_companies[0] if user_companies else None
            if not target_company_id:
                target_company_id = manager.get_any_canonical_company_id() or target_company_id

        if not target_company_id:
            raise HTTPException(status_code=404, detail="No active company found.")

        return analytics_service.get_unpaid_invoices(
            company_id=target_company_id,
            limit=limit,
        )

    @app.get("/api/v1/analytics/inventory")
    def get_analytics_inventory(
        current_authenticated_user: Annotated[dict[str, Any], Depends(get_current_authenticated_user)],
        company_id: Annotated[str | None, Query(description="Company GUID")] = None,
        limit: Annotated[int, Query(description="Max items per list", ge=1, le=50)] = 5,
    ) -> dict[str, Any]:
        """Returns inventory KPIs plus largest, lowest and out-of-stock item lists."""
        target_company_id = company_id
        if not target_company_id:
            user_companies = manager.list_user_company_guids(current_authenticated_user["user_id"])
            target_company_id = user_companies[0] if user_companies else None
            if not target_company_id:
                target_company_id = manager.get_any_canonical_company_id() or target_company_id

        if not target_company_id:
            raise HTTPException(status_code=404, detail="No active company found.")

        details = analytics_service.get_inventory_details(company_id=target_company_id, limit=limit)
        if not details["overview"]["total_items"]:
            log.warning("analytics/inventory: no stock items for company_id=%s (canonical_stock_items empty for it)", target_company_id)
        else:
            log.info("analytics/inventory: company_id=%s overview=%s", target_company_id, details["overview"])
        return details

    @app.get("/api/v1/analytics/kpi-details")
    def get_analytics_kpi_details(
        current_authenticated_user: Annotated[dict[str, Any], Depends(get_current_authenticated_user)],
        kpi: Annotated[str, Query(description="KPI card: sales, collections, purchases or receivables")],
        company_id: Annotated[str | None, Query(description="Company GUID")] = None,
        period: Annotated[str, Query(description="Period preset (same values as /analytics/overview)")] = "mtd",
        start_date: Annotated[str | None, Query(description="Custom start date (YYYY-MM-DD or DD-MM-YYYY)")] = None,
        end_date: Annotated[str | None, Query(description="Custom end date (YYYY-MM-DD or DD-MM-YYYY)")] = None,
        reference_date: Annotated[str | None, Query(description="Optional anchor reference date")] = None,
        limit: Annotated[int, Query(description="Max rows per ranked list", ge=1, le=25)] = 5,
    ) -> dict[str, Any]:
        """Returns the key metrics, trend and ranked lists behind one KPI card (for its popup)."""
        if kpi.strip().lower() not in analytics_service.KPI_DETAIL_KEYS:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown kpi '{kpi}'. Expected one of: {', '.join(analytics_service.KPI_DETAIL_KEYS)}",
            )

        target_company_id = company_id
        if not target_company_id:
            user_companies = manager.list_user_company_guids(current_authenticated_user["user_id"])
            target_company_id = user_companies[0] if user_companies else None
            if not target_company_id:
                target_company_id = manager.get_any_canonical_company_id() or target_company_id

        if not target_company_id:
            raise HTTPException(status_code=404, detail="No active company found.")

        try:
            details = analytics_service.get_kpi_details(
                company_id=target_company_id,
                kpi=kpi,
                period_preset=period,
                reference_date=parse_date_flexible(reference_date) if reference_date else None,
                custom_start=parse_date_flexible(start_date) if start_date else None,
                custom_end=parse_date_flexible(end_date) if end_date else None,
                limit=limit,
            )
        except Exception:
            log.exception("analytics/kpi-details failed: company_id=%s kpi=%s period=%s", target_company_id, kpi, period)
            raise
        log.info(
            "analytics/kpi-details: company_id=%s kpi=%s period=%s headline=%s metrics=%d sections=%s",
            target_company_id,
            kpi,
            period,
            details["headline"]["formatted_value"],
            len(details["metrics"]),
            {s["title"]: len(s["rows"]) for s in details["sections"]},
        )
        return details

    @app.get("/api/v1/analytics/sync-status")
    def get_analytics_sync_status(
        current_authenticated_user: Annotated[dict[str, Any], Depends(get_current_authenticated_user)],
        company_id: Annotated[str | None, Query(description="Company GUID")] = None,
    ) -> dict[str, Any]:
        """Returns the latest transaction sync status of company books."""
        target_company_id = company_id
        if not target_company_id:
            user_companies = manager.list_user_company_guids(current_authenticated_user["user_id"])
            target_company_id = user_companies[0] if user_companies else None
            if not target_company_id:
                target_company_id = manager.get_any_canonical_company_id() or target_company_id

        if not target_company_id:
            raise HTTPException(status_code=404, detail="No active company found.")

        return analytics_service.get_sync_status(target_company_id)

    # ─── Ask O3 AI Assistant Endpoints ──────────────────────────────────────────

    @app.get("/api/v1/agent/messages")
    def get_chat_history(
        current_authenticated_user: Annotated[dict[str, Any], Depends(get_current_authenticated_user)],
        company_id: Annotated[str | None, Query(description="Company GUID")] = None,
    ) -> dict[str, Any]:
        """Returns the message history for the single Ask O3 chat thread."""
        target_company_id = company_id
        if not target_company_id:
            user_companies = manager.list_user_company_guids(current_authenticated_user["user_id"])
            target_company_id = user_companies[0] if user_companies else "default"

        messages = agent_service.get_conversation_history(
            user_id=current_authenticated_user["user_id"],
            company_id=target_company_id,
        )
        return {"company_id": target_company_id, "messages": messages}

    @app.post("/api/v1/agent/chat")
    def send_chat_message(
        chat_request: ChatMessageRequest,
        current_authenticated_user: Annotated[dict[str, Any], Depends(get_current_authenticated_user)],
    ) -> dict[str, Any]:
        """Sends a question to O3 and receives a conversational response."""
        target_company_id = chat_request.company_id
        if not target_company_id:
            user_companies = manager.list_user_company_guids(current_authenticated_user["user_id"])
            target_company_id = user_companies[0] if user_companies else "default"

        assistant_response = agent_service.process_chat_message(
            user_id=current_authenticated_user["user_id"],
            company_id=target_company_id,
            user_query=chat_request.message,
        )

        return {
            "status": "ok",
            "role": "assistant",
            "content": assistant_response,
            "company_id": target_company_id,
        }

    @app.delete("/api/v1/agent/messages")
    def clear_chat_history(
        current_authenticated_user: Annotated[dict[str, Any], Depends(get_current_authenticated_user)],
        company_id: Annotated[str | None, Query(description="Company GUID")] = None,
    ) -> dict[str, str]:
        """Clears the single chat thread for the current company."""
        target_company_id = company_id
        if not target_company_id:
            user_companies = manager.list_user_company_guids(current_authenticated_user["user_id"])
            target_company_id = user_companies[0] if user_companies else "default"

        agent_service.clear_conversation(
            user_id=current_authenticated_user["user_id"],
            company_id=target_company_id,
        )
        return {"status": "ok", "message": "Conversation cleared."}

    # ─── Static Frontend Assets & Template Endpoints ────────────────────────────

    frontend_dir = Path(__file__).resolve().parent.parent / "frontend_dashboard"
    if frontend_dir.exists():
        static_dir = frontend_dir / "static"
        if static_dir.exists():
            app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", response_class=HTMLResponse)
        def serve_root():
            dashboard_file = frontend_dir / "templates" / "dashboard.html"
            if dashboard_file.exists():
                return HTMLResponse(content=dashboard_file.read_text(encoding="utf-8"))
            return HTMLResponse(content="<h1>O3 Executive Dashboard</h1>")

        @app.get("/login", response_class=HTMLResponse)
        def serve_login():
            login_file = frontend_dir / "templates" / "login.html"
            if login_file.exists():
                return HTMLResponse(content=login_file.read_text(encoding="utf-8"))
            return HTMLResponse(content="<h1>O3 Login</h1>")

        @app.get("/dashboard", response_class=HTMLResponse)
        def serve_dashboard():
            dashboard_file = frontend_dir / "templates" / "dashboard.html"
            if dashboard_file.exists():
                return HTMLResponse(content=dashboard_file.read_text(encoding="utf-8"))
            return HTMLResponse(content="<h1>O3 Dashboard</h1>")

    return app
