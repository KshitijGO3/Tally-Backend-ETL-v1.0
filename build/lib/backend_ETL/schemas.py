"""Pydantic request and response schemas for the PostgreSQL backend CRUD API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ClientCreateRequest(BaseModel):
    """Payload to register/activate a client."""

    client_name: str
    contact_email: str | None = None


class CompanyPayload(BaseModel):
    """Company record payload."""

    guid: str
    name: str
    books_from: str | None = None
    starting_from: str | None = None
    company_number: str | None = None
    ending_at: str | None = None
    gstin: str | None = None
    master_id: int = 0
    alter_id: int = 0
    synced_at: str | None = None


class CompanyBatchRequest(BaseModel):
    """Batch upsert payload for companies."""

    rows: list[CompanyPayload] = Field(default_factory=list)


class MasterBatchRequest(BaseModel):
    """Batch upsert payload for any of the 14 master tables."""

    rows: list[dict[str, Any]] = Field(default_factory=list)


class VoucherBatchRequest(BaseModel):
    """Atomic batch upsert payload for vouchers and their 4 child entry tables."""

    headers: list[dict[str, Any]] = Field(default_factory=list)
    ledger_entries: list[dict[str, Any]] = Field(default_factory=list)
    inventory_entries: list[dict[str, Any]] = Field(default_factory=list)
    cost_centre_allocations: list[dict[str, Any]] = Field(default_factory=list)
    attendance_entries: list[dict[str, Any]] = Field(default_factory=list)


class VoucherSingleRequest(BaseModel):
    """Single voucher upsert payload with optional nested child entry lists."""

    header: dict[str, Any]
    ledger_entries: list[dict[str, Any]] = Field(default_factory=list)
    inventory_entries: list[dict[str, Any]] = Field(default_factory=list)
    cost_centre_allocations: list[dict[str, Any]] = Field(default_factory=list)
    attendance_entries: list[dict[str, Any]] = Field(default_factory=list)


class ChildEntriesBatchRequest(BaseModel):
    """Batch replacement payload for a voucher's child entry table."""

    rows: list[dict[str, Any]] = Field(default_factory=list)


# ─── Human User Authentication & Onboarding Models ──────────────────────────────


class UserRegisterRequest(BaseModel):
    """Registration payload for a new organization and owner account."""

    client_name: str
    full_name: str
    email: str
    password: str


class UserLoginRequest(BaseModel):
    """Login payload for an existing user account."""

    email: str
    password: str


class ChatMessageRequest(BaseModel):
    """Payload to submit a message to the single ongoing 'Ask O3' conversation."""

    company_id: str | None = None
    company_name: str | None = None
    message: str

