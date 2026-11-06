"""Autonomous Background Poller and Manual Execution Runner for Canonical ETL.

Implements pure polling mode and manual execution mode for transforming
Bronze replicated tables into the Silver Canonical Domain Model in PostgreSQL.
Uses non-blocking PostgreSQL transaction-level advisory locks to prevent overlapping runs.
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import BigInteger, cast, delete, func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from backend_ETL.canonical_transformer import CanonicalTransformer
from backend_ETL.config import ETLConfig
from backend_ETL.date_utils import parse_canonical_date, parse_tally_date
from backend_ETL.db import PostgresManager, _bulk_upsert
from backend_ETL.models import CANONICAL_MODELS, MASTER_MODELS
from backend_ETL.models.canonical_tables import (
    CanonicalAccount,
    CanonicalAttendanceEntry,
    CanonicalBillEvent,
    CanonicalCostAllocation,
    CanonicalDailyMovement,
    CanonicalInventoryLine,
    CanonicalPosting,
    CanonicalSyncCursor,
    CanonicalVoucher,
)
from backend_ETL.models.tally_tables import (
    AttendanceEntry,
    Company,
    CostCategory,
    CostCentre,
    CostCentreAllocation,
    Godown,
    Group,
    InventoryEntry,
    Ledger,
    LedgerEntry,
    StockItem,
    Unit,
    Voucher,
    VoucherType,
)

log = logging.getLogger(__name__)


# ─── Canonical Table Column & Conflict Specifications ───────────────────────────

CANONICAL_TABLE_SPECS: dict[str, dict[str, Any]] = {
    "canonical_companies": {
        "columns": (
            "company_id",
            "name",
            "books_from",
            "starting_from",
            "company_number",
            "books_to",
            "company_gstin",
            "source_master_id",
            "source_alter_id",
        ),
        "conflict": "company_id",
    },
    "canonical_account_groups": {
        "columns": (
            "accountgroup_id",
            "company_id",
            "name",
            "parent_ref",
            "parent_chain",
            "nature",
            "primary_group",
            "is_revenue",
            "is_deemed_positive",
            "affects_gross_profit",
            "source_master_id",
            "source_alter_id",
        ),
        "conflict": "accountgroup_id",
    },
    "canonical_accounts": {
        "columns": (
            "account_id",
            "company_id",
            "name",
            "group_ref",
            "aliases",
            "credit_limit",
            "credit_period_raw",
            "bill_wise",
            "cost_centres_on",
            "currency",
            "reported_closing",
            "gst_reg_type",
            "tax_classification",
            "classification_role",
            "source_master_id",
            "source_alter_id",
        ),
        "conflict": "account_id",
    },
    "canonical_account_contacts": {
        "columns": (
            "account_ref",
            "contact_mailing_name",
            "contact_address",
            "contact_state_name",
            "contact_country_name",
            "contact_pincode",
            "contact_email",
            "contact_phone",
            "contact_mobile",
            "party_pan",
        ),
        "conflict": "account_ref",
    },
    "canonical_party_identifiers": {
        "columns": ("party_ref", "id_type", "value", "confidence", "source"),
        "conflict": ("party_ref", "id_type", "value"),
    },
    "canonical_voucher_types": {
        "columns": (
            "vouchertype_id",
            "company_id",
            "name",
            "parent_kind",
            "base_type",
            "numbering_method",
            "is_active",
            "affects_stock",
            "prevent_duplicates",
            "source_master_id",
            "source_alter_id",
        ),
        "conflict": "vouchertype_id",
    },
    "canonical_stock_groups": {
        "columns": (
            "stockgroup_id",
            "company_id",
            "name",
            "parent_ref",
            "source_master_id",
            "source_alter_id",
        ),
        "conflict": "stockgroup_id",
    },
    "canonical_stock_categories": {
        "columns": (
            "stockcategory_id",
            "company_id",
            "name",
            "parent_ref",
            "source_master_id",
            "source_alter_id",
        ),
        "conflict": "stockcategory_id",
    },
    "canonical_stock_items": {
        "columns": (
            "stockitem_id",
            "company_id",
            "name",
            "parent_ref",
            "category",
            "base_units",
            "alternate_units",
            "hsn_code",
            "gst_applicable",
            "gst_type_of_supply",
            "tax_rate",
            "costing_method",
            "valuation_method",
            "opening_qty",
            "opening_rate",
            "opening_value",
            "closing_qty",
            "closing_value",
            "source_master_id",
            "source_alter_id",
        ),
        "conflict": "stockitem_id",
    },
    "canonical_godowns": {
        "columns": (
            "godown_id",
            "company_id",
            "name",
            "parent_ref",
            "address",
            "has_no_space",
            "has_no_stock",
            "source_master_id",
            "source_alter_id",
        ),
        "conflict": "godown_id",
    },
    "canonical_units": {
        "columns": (
            "unit_id",
            "company_id",
            "name",
            "original_name",
            "base_units",
            "is_simple_unit",
            "decimal_places",
            "conversion",
            "source_master_id",
            "source_alter_id",
        ),
        "conflict": "unit_id",
    },
    "canonical_cost_categories": {
        "columns": (
            "costcategory_id",
            "company_id",
            "name",
            "allocate_revenue",
            "allocate_non_revenue",
            "source_master_id",
            "source_alter_id",
        ),
        "conflict": "costcategory_id",
    },
    "canonical_cost_centres": {
        "columns": (
            "costcentre_id",
            "company_id",
            "name",
            "parent_ref",
            "category",
            "revenue_le_for_op_bal",
            "email_id",
            "source_master_id",
            "source_alter_id",
        ),
        "conflict": "costcentre_id",
    },
    "canonical_currencies": {
        "columns": (
            "currency_id",
            "company_id",
            "name",
            "mailing_name",
            "original_name",
            "expanded_symbol",
            "decimal_symbol",
            "decimal_places",
            "source_master_id",
            "source_alter_id",
        ),
        "conflict": "currency_id",
    },
    "canonical_employee_groups": {
        "columns": (
            "employeegroup_id",
            "company_id",
            "name",
            "parent_ref",
            "category",
            "source_master_id",
            "source_alter_id",
        ),
        "conflict": "employeegroup_id",
    },
    "canonical_employees": {
        "columns": (
            "employee_id",
            "company_id",
            "name",
            "parent_ref",
            "category",
            "date_of_joining",
            "deactivation_date",
            "designation",
            "function_role",
            "location",
            "gender",
            "blood_group",
            "pan_number",
            "aadhar_number",
            "pf_number",
            "uan",
            "esi_number",
            "bank_name",
            "bank_account_number",
            "ifsc_code",
            "email",
            "mobile",
            "source_master_id",
            "source_alter_id",
        ),
        "conflict": "employee_id",
    },
    "canonical_attendance_types": {
        "columns": (
            "attendancetype_id",
            "company_id",
            "name",
            "parent_ref",
            "attendance_production_type",
            "attendance_period",
            "base_units",
            "source_master_id",
            "source_alter_id",
        ),
        "conflict": "attendancetype_id",
    },
    "canonical_opening_balances": {
        "columns": ("account_ref", "company_id", "amount", "as_of"),
        "conflict": "account_ref",
    },
    "canonical_vouchers": {
        "columns": (
            "voucher_id",
            "company_id",
            "date",
            "kind",
            "base_type",
            "number",
            "narration",
            "reference",
            "party_ref",
            "lifecycle",
            "is_optional",
            "is_invoice",
            "persisted_view",
            "effective_date",
            "reference_date",
            "place_of_supply",
            "party_gstin_doc",
            "ship_to",
            "irn",
            "eway_bill_no",
            "source_master_id",
            "source_alter_id",
        ),
        "conflict": "voucher_id",
    },
    "canonical_postings": {
        "columns": (
            "voucher_ref",
            "line_ordinal",
            "account_ref",
            "amount",
            "source_deemed_positive",
        ),
        "conflict": ("voucher_ref", "line_ordinal"),
    },
    "canonical_bill_events": {
        "columns": (
            "voucher_ref",
            "company_id",
            "party_ref",
            "bill_ref",
            "kind",
            "due_date",
            "credit_period_raw",
            "amount",
        ),
        "conflict": None,
    },
    "canonical_inventory_lines": {
        "columns": (
            "voucher_guid",
            "item_ref",
            "billed_qty",
            "actual_qty",
            "rate",
            "amount",
            "godown_ref",
            "batch_ref",
            "unit_ref",
        ),
        "conflict": None,
    },
    "canonical_cost_allocations": {
        "columns": (
            "voucher_ref",
            "line_ordinal",
            "account_ref",
            "cost_category_ref",
            "cost_centre_ref",
            "amount",
            "source_deemed_positive",
        ),
        "conflict": None,
    },
    "canonical_attendance_entries": {
        "columns": (
            "voucher_guid",
            "employee_name",
            "attendance_type",
            "value",
            "time_value",
        ),
        "conflict": None,
    },
    "canonical_daily_movements": {
        "columns": (
            "company_id",
            "date",
            "base_type",
            "account_role",
            "is_debit",
            "total_amount",
            "voucher_count",
        ),
        "conflict": ("company_id", "date", "base_type", "account_role", "is_debit"),
    },
}


def try_acquire_company_lock(s: Session, company_id: str) -> bool:
    """Attempts to acquire a non-blocking transaction-level PostgreSQL advisory lock."""
    try:
        locked = s.scalar(
            select(
                func.pg_try_advisory_xact_lock(
                    cast(func.hashtext(f"canonical_elt_{company_id}"), BigInteger)
                )
            )
        )
        return True if locked is None else bool(locked)
    except Exception as e:
        log.debug("Advisory lock check skipped/unsupported (%s); proceeding with execution", e)
        return True


def get_cursor(s: Session, company_id: str, entity: str) -> int:
    """Reads current sync watermark alter_id from canonical_sync_cursors."""
    val = s.scalars(
        select(CanonicalSyncCursor.cursor_value).where(
            CanonicalSyncCursor.company_id == company_id, CanonicalSyncCursor.entity == entity
        )
    ).first()
    try:
        return int(val or 0)
    except (ValueError, TypeError):
        return 0


def set_cursor(s: Session, company_id: str, entity: str, cursor_value: int) -> None:
    """Updates sync watermark alter_id in canonical_sync_cursors."""
    stmt = pg_insert(CanonicalSyncCursor).values(
        company_id=company_id,
        entity=entity,
        cursor_value=str(cursor_value),
        extraction_time=func.current_timestamp(),
    )
    s.execute(
        stmt.on_conflict_do_update(
            index_elements=["company_id", "entity"],
            set_={
                "cursor_value": stmt.excluded.cursor_value,
                "extraction_time": func.current_timestamp(),
            },
        )
    )


def _name_guid_lookup(s: Session, model: Any, company_id: str) -> dict[str, str]:
    """Maps bronze master name -> guid for one company."""
    rows = s.execute(select(model.name, model.guid).where(model.company_id == company_id)).all()
    return {r.name: r.guid for r in rows if r.name}


def _fetch_rows(
    s: Session, model: Any, *conditions: Any, order_by: Any = None, limit: int | None = None
) -> list[dict[str, Any]]:
    """Plain dict rows (like SELECT *) from a model's table, without building ORM objects."""
    stmt = select(model.__table__).where(*conditions)
    if order_by is not None:
        stmt = stmt.order_by(order_by)
    if limit is not None:
        stmt = stmt.limit(limit)
    return [dict(r) for r in s.execute(stmt).mappings()]


class CanonicalPollerRunner:
    """Autonomous Poller & Manual Executor for Canonical Domain Model Transformation."""

    def __init__(self, db: PostgresManager, cfg: ETLConfig | None = None) -> None:
        self.db = db
        self.cfg = cfg or ETLConfig()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Starts background poller if enabled and in polling mode."""
        if not self.cfg.enabled:
            log.info("Canonical ETL runner is disabled by config.")
            return
        if self.cfg.execution_mode != "polling":
            log.info(
                "Canonical ETL execution mode is '%s'; background poller not started.",
                self.cfg.execution_mode,
            )
            return
        if self._thread is not None and self._thread.is_alive():
            log.warning("Canonical ETL background poller is already running.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="canonical_etl_poller",
            daemon=True,
        )
        self._thread.start()
        log.info(
            "Started Canonical ETL poller (polling every %ds).",
            self.cfg.polling_interval_seconds,
        )

    def stop(self, timeout: float = 10.0) -> None:
        """Signals background poller to stop and waits for completion."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
            log.info("Canonical ETL poller stopped.")

    def _run_loop(self) -> None:
        """Continuous polling loop executed by background daemon thread."""
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as e:
                log.error("Unhandled error in Canonical ETL polling cycle: %s", e, exc_info=True)
            self._stop_event.wait(self.cfg.polling_interval_seconds)

    def run_once(self, company_id: str | None = None) -> dict[str, Any]:
        """Executes a single end-to-end transformation cycle.

        Args:
            company_id: Optional company GUID. If None, processes all companies in Bronze.

        Returns:
            Dictionary containing processing summary and record counts.
        """
        processed_companies: list[str] = []
        total_counts: dict[str, int] = defaultdict(int)

        # 1. Discover target companies
        with self.db.session() as s:
            company_stmt = select(Company).order_by(Company.guid)
            if company_id:
                company_stmt = select(Company).where(Company.guid == company_id)
            raw_companies = [c.to_dict() for c in s.scalars(company_stmt)]

        if not raw_companies:
            log.debug("No companies found in Bronze staging layer.")
            return {
                "status": "ok",
                "companies_processed": 0,
                "company_ids": [],
                "counts": dict(total_counts),
            }

        # 2. Process each company under a transaction-level advisory lock
        for comp in raw_companies:
            c_guid = comp["guid"]
            with self.db.session() as s:
                if not try_acquire_company_lock(s, c_guid):
                    log.info(
                        "Company '%s' (%s) ETL is already active in another worker; skipping.",
                        comp.get("name"),
                        c_guid,
                    )
                    continue

                try:
                    c_counts = self._process_company(s, comp)
                    for k, v in c_counts.items():
                        total_counts[k] += v
                    processed_companies.append(c_guid)
                except Exception as e:
                    log.error(
                        "Error transforming company '%s' (%s): %s",
                        comp.get("name"),
                        c_guid,
                        e,
                        exc_info=True,
                    )
                    raise

        return {
            "status": "ok",
            "companies_processed": len(processed_companies),
            "company_ids": processed_companies,
            "counts": dict(total_counts),
        }

    def _process_company(self, s: Session, comp: dict[str, Any]) -> dict[str, int]:
        """Transforms Bronze data for a single company into Silver canonical tables."""
        company_id = comp["guid"]
        counts: dict[str, int] = defaultdict(int)

        # ── Step A: Build in-memory reference lookups and parent maps ─────────
        group_rows = [
            dict(r)
            for r in s.execute(
                select(Group.guid, Group.name, Group.parent).where(Group.company_id == company_id)
            ).mappings()
        ]
        group_lookup = {r["name"]: r["guid"] for r in group_rows if r.get("name")}
        group_parent_map = {r["name"]: r.get("parent") for r in group_rows if r.get("name")}

        account_lookup = _name_guid_lookup(s, Ledger, company_id)
        item_lookup = _name_guid_lookup(s, StockItem, company_id)
        godown_lookup = _name_guid_lookup(s, Godown, company_id)
        unit_lookup = _name_guid_lookup(s, Unit, company_id)
        cost_centre_lookup = _name_guid_lookup(s, CostCentre, company_id)
        cost_category_lookup = _name_guid_lookup(s, CostCategory, company_id)

        voucher_type_parent_map = {
            r.name: r.parent
            for r in s.execute(
                select(VoucherType.name, VoucherType.parent).where(
                    VoucherType.company_id == company_id
                )
            ).all()
            if r.name
        }

        transformer = CanonicalTransformer(
            company_id=company_id,
            account_lookup=account_lookup,
            group_lookup=group_lookup,
            group_parent_map=group_parent_map,
            item_lookup=item_lookup,
            godown_lookup=godown_lookup,
            unit_lookup=unit_lookup,
            cost_centre_lookup=cost_centre_lookup,
            cost_category_lookup=cost_category_lookup,
            voucher_type_parent_map=voucher_type_parent_map,
        )

        # ── Step B: Canonical Company Record ─────────────────────────────────
        c_trans = transformer.transform_company(comp)
        self._upsert_rows(s, "canonical_companies", [c_trans])
        counts["companies"] += 1

        # ── Step C: Master Tables (Incremental via alter_id) ─────────────────
        books_from_norm = parse_tally_date(comp.get("books_from"))

        # 1. Groups
        counts["groups"] += self._sync_simple_master(
            s,
            company_id,
            "groups",
            "canonical_account_groups",
            transformer.transform_group,
        )

        # 2. Ledgers (Decoupled to Accounts, Contacts, Party Identifiers, Opening Balances)
        counts["ledgers"] += self._sync_ledgers(s, company_id, transformer, books_from_norm)

        # 3. Voucher Types
        counts["voucher_types"] += self._sync_simple_master(
            s,
            company_id,
            "voucher_types",
            "canonical_voucher_types",
            transformer.transform_voucher_type,
        )

        # 4. Stock Groups
        counts["stock_groups"] += self._sync_simple_master(
            s,
            company_id,
            "stock_groups",
            "canonical_stock_groups",
            transformer.transform_stock_group,
        )

        # 5. Stock Categories
        counts["stock_categories"] += self._sync_simple_master(
            s,
            company_id,
            "stock_categories",
            "canonical_stock_categories",
            transformer.transform_stock_category,
        )

        # 6. Stock Items
        counts["stock_items"] += self._sync_simple_master(
            s,
            company_id,
            "stock_items",
            "canonical_stock_items",
            transformer.transform_stock_item,
        )

        # 7. Godowns
        counts["godowns"] += self._sync_simple_master(
            s,
            company_id,
            "godowns",
            "canonical_godowns",
            transformer.transform_godown,
        )

        # 8. Units
        counts["units"] += self._sync_simple_master(
            s,
            company_id,
            "units",
            "canonical_units",
            transformer.transform_unit,
        )

        # 9. Cost Categories
        counts["cost_categories"] += self._sync_simple_master(
            s,
            company_id,
            "cost_categories",
            "canonical_cost_categories",
            transformer.transform_cost_category,
        )

        # 10. Cost Centres
        counts["cost_centres"] += self._sync_simple_master(
            s,
            company_id,
            "cost_centres",
            "canonical_cost_centres",
            transformer.transform_cost_centre,
        )

        # 11. Currencies
        counts["currencies"] += self._sync_simple_master(
            s,
            company_id,
            "currencies",
            "canonical_currencies",
            transformer.transform_currency,
        )

        # 12. Employee Groups
        counts["employee_groups"] += self._sync_simple_master(
            s,
            company_id,
            "employee_groups",
            "canonical_employee_groups",
            transformer.transform_employee_group,
        )

        # 13. Employees
        counts["employees"] += self._sync_simple_master(
            s,
            company_id,
            "employees",
            "canonical_employees",
            transformer.transform_employee,
        )

        # 14. Attendance Types
        counts["attendance_types"] += self._sync_simple_master(
            s,
            company_id,
            "attendance_types",
            "canonical_attendance_types",
            transformer.transform_attendance_type,
        )

        # ── Step D: Transactions (Vouchers and Decoupled Children) ───────────
        vouchers_synced = self._sync_vouchers(s, company_id, transformer)
        counts["vouchers"] += vouchers_synced

        # ── Step E: Daily Aggregate Table Rollup (Pure Python) ───────────────
        counts["daily_movements"] += self._update_daily_movements(s, company_id)

        return counts

    def _sync_simple_master(
        self,
        s: Session,
        company_id: str,
        source_table: str,
        target_table: str,
        transform_fn: Any,
    ) -> int:
        """Transforms and upserts incremental master records."""
        last_cursor = get_cursor(s, company_id, source_table)
        model: Any = MASTER_MODELS[source_table]
        rows = _fetch_rows(
            s,
            model,
            model.company_id == company_id,
            model.alter_id > last_cursor,
            order_by=model.alter_id.asc(),
        )
        if not rows:
            return 0

        transformed = [transform_fn(r) for r in rows]
        self._upsert_rows(s, target_table, transformed)
        max_alter = max(int(r.get("alter_id") or 0) for r in rows)
        set_cursor(s, company_id, source_table, max_alter)
        return len(rows)

    def _sync_ledgers(
        self,
        s: Session,
        company_id: str,
        transformer: CanonicalTransformer,
        books_from_norm: date | str | None,
    ) -> int:
        """Syncs ledgers into accounts, contacts, identifiers, and opening balances."""
        last_cursor = get_cursor(s, company_id, "ledgers")
        rows = _fetch_rows(
            s,
            Ledger,
            Ledger.company_id == company_id,
            Ledger.alter_id > last_cursor,
            order_by=Ledger.alter_id.asc(),
        )
        if not rows:
            return 0

        accounts: list[dict[str, Any]] = []
        contacts: list[dict[str, Any]] = []
        party_ids: list[dict[str, Any]] = []
        opening_bals: list[dict[str, Any]] = []

        for r in rows:
            res = transformer.transform_ledger(r, books_from_date=books_from_norm)
            accounts.append(res["account"])
            if res.get("contact"):
                contacts.append(res["contact"])
            if res.get("party_identifier"):
                party_ids.append(res["party_identifier"])
            if res.get("opening_balance"):
                opening_bals.append(res["opening_balance"])

        self._upsert_rows(s, "canonical_accounts", accounts)
        if contacts:
            self._upsert_rows(s, "canonical_account_contacts", contacts)
        if party_ids:
            self._upsert_rows(s, "canonical_party_identifiers", party_ids)
        if opening_bals:
            self._upsert_rows(s, "canonical_opening_balances", opening_bals)

        max_alter = max(int(r.get("alter_id") or 0) for r in rows)
        set_cursor(s, company_id, "ledgers", max_alter)
        return len(rows)

    def _sync_vouchers(
        self,
        s: Session,
        company_id: str,
        transformer: CanonicalTransformer,
    ) -> int:
        """Batches vouchers and transforms postings, bill events, inventory,
        and cost allocations.
        """
        last_cursor = get_cursor(s, company_id, "vouchers")
        vch_rows = _fetch_rows(
            s,
            Voucher,
            Voucher.company_id == company_id,
            Voucher.alter_id > last_cursor,
            order_by=Voucher.alter_id.asc(),
            limit=self.cfg.max_batch_vouchers,
        )
        if not vch_rows:
            return 0

        vch_guids = [v["guid"] for v in vch_rows]

        def children_by_voucher(model: Any) -> dict[str, list[dict[str, Any]]]:
            grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for d in _fetch_rows(
                s, model, model.voucher_guid.in_(vch_guids), order_by=model.id.asc()
            ):
                grouped[d["voucher_guid"]].append(d)
            return grouped

        # Query all child rows in batch
        le_by_vch = children_by_voucher(LedgerEntry)
        ie_by_vch = children_by_voucher(InventoryEntry)
        cca_by_vch = children_by_voucher(CostCentreAllocation)
        ae_by_vch = children_by_voucher(AttendanceEntry)

        # Transform voucher parents and children
        transformed_vouchers: list[dict[str, Any]] = []
        all_postings: list[dict[str, Any]] = []
        all_bill_events: list[dict[str, Any]] = []
        all_inv_lines: list[dict[str, Any]] = []
        all_cost_allocs: list[dict[str, Any]] = []
        all_att_entries: list[dict[str, Any]] = []

        for v in vch_rows:
            v_guid = v["guid"]
            transformed_vouchers.append(transformer.transform_voucher(v))

            le_rows = le_by_vch.get(v_guid, [])
            posts, bills = transformer.transform_ledger_entries(le_rows)
            all_postings.extend(posts)
            all_bill_events.extend(bills)

            ie_rows = ie_by_vch.get(v_guid, [])
            all_inv_lines.extend(transformer.transform_inventory_entries(ie_rows))

            cca_rows = cca_by_vch.get(v_guid, [])
            all_cost_allocs.extend(transformer.transform_cost_allocations(cca_rows))

            ae_rows = ae_by_vch.get(v_guid, [])
            all_att_entries.extend(transformer.transform_attendance_entries(ae_rows))

        # 1. Upsert vouchers
        self._upsert_rows(s, "canonical_vouchers", transformed_vouchers)

        # 2. Clean previous child lines for these vouchers (atomic child replacement)
        s.execute(delete(CanonicalPosting).where(CanonicalPosting.voucher_ref.in_(vch_guids)))
        s.execute(delete(CanonicalBillEvent).where(CanonicalBillEvent.voucher_ref.in_(vch_guids)))
        s.execute(
            delete(CanonicalInventoryLine).where(CanonicalInventoryLine.voucher_guid.in_(vch_guids))
        )
        s.execute(
            delete(CanonicalCostAllocation).where(
                CanonicalCostAllocation.voucher_ref.in_(vch_guids)
            )
        )
        s.execute(
            delete(CanonicalAttendanceEntry).where(
                CanonicalAttendanceEntry.voucher_guid.in_(vch_guids)
            )
        )

        # 3. Insert fresh transformed child rows
        if all_postings:
            self._upsert_rows(s, "canonical_postings", all_postings)
        if all_bill_events:
            self._upsert_rows(s, "canonical_bill_events", all_bill_events)
        if all_inv_lines:
            self._upsert_rows(s, "canonical_inventory_lines", all_inv_lines)
        if all_cost_allocs:
            self._upsert_rows(s, "canonical_cost_allocations", all_cost_allocs)
        if all_att_entries:
            self._upsert_rows(s, "canonical_attendance_entries", all_att_entries)

        # 4. Advance cursor
        max_alter = max(int(v.get("alter_id") or 0) for v in vch_rows)
        set_cursor(s, company_id, "vouchers", max_alter)
        return len(vch_rows)

    def _upsert_rows(
        self,
        s: Session,
        table_name: str,
        rows: Sequence[dict[str, Any]],
    ) -> None:
        """Bulk upsert (or plain insert when the spec has no conflict key) from the table spec."""
        if not rows:
            return

        spec = CANONICAL_TABLE_SPECS[table_name]
        columns: tuple[str, ...] = spec["columns"]
        conflict = spec.get("conflict")
        model = CANONICAL_MODELS[table_name]
        clean_rows = [{c: r.get(c) for c in columns} for r in rows]

        if not conflict:
            s.execute(insert(model), clean_rows)
            return
        conflict_cols = [conflict] if isinstance(conflict, str) else list(conflict)
        _bulk_upsert(s, model, clean_rows, conflict_cols)

    def _update_daily_movements(
        self,
        s: Session,
        company_id: str,
        affected_dates: set[date | str] | None = None,
    ) -> int:
        """Aggregates active voucher postings by day, base voucher type, account role, and debit/credit.

        Idempotently updates canonical_daily_movements in pure Python without DB triggers or procedures.
        """
        # Fetch account classification roles for the company
        account_role_mapping = {
            r.account_id: (r.classification_role or "other")
            for r in s.execute(
                select(CanonicalAccount.account_id, CanonicalAccount.classification_role).where(
                    CanonicalAccount.company_id == company_id
                )
            ).all()
            if r.account_id
        }

        # Query active vouchers and postings
        v, p = CanonicalVoucher, CanonicalPosting
        posting_stmt = (
            select(
                v.voucher_id, v.date, v.base_type, p.account_ref, p.amount, p.source_deemed_positive
            )
            .select_from(v)
            .join(p, v.voucher_id == p.voucher_ref)
            .where(v.company_id == company_id, v.lifecycle == "active")
        )
        date_list = sorted(list(affected_dates)) if affected_dates else []
        if date_list:
            posting_stmt = posting_stmt.where(v.date.in_(date_list))
        posting_records = [dict(r) for r in s.execute(posting_stmt).mappings()]

        # Pure Python aggregation: group by (date, base_type, account_role, is_debit)
        grouped_aggregates: dict[tuple[date, str, str, bool], dict[str, Any]] = defaultdict(
            lambda: {"total_amount": 0.0, "voucher_ids": set()}
        )

        for posting in posting_records:
            voucher_date = posting.get("date")
            if isinstance(voucher_date, str):
                voucher_date = parse_canonical_date(voucher_date)
            if not voucher_date:
                continue
            base_type = posting.get("base_type") or "Unknown"
            account_ref = posting.get("account_ref")
            account_role = account_role_mapping.get(account_ref, "other")
            posting_amount = float(posting.get("amount") or 0.0)
            deemed_positive = bool(posting.get("source_deemed_positive"))
            # In Tally double entry: negative amount indicates debit (deemed positive)
            is_debit = (posting_amount < 0) or deemed_positive
            absolute_posting_amount = abs(posting_amount)

            aggregation_key = (voucher_date, base_type, account_role, is_debit)
            grouped_aggregates[aggregation_key]["total_amount"] += absolute_posting_amount
            grouped_aggregates[aggregation_key]["voucher_ids"].add(posting["voucher_id"])

        # Delete existing rows before inserting freshly calculated rollups
        delete_stmt = delete(CanonicalDailyMovement).where(
            CanonicalDailyMovement.company_id == company_id
        )
        if date_list:
            delete_stmt = delete_stmt.where(CanonicalDailyMovement.date.in_(date_list))
        s.execute(delete_stmt)

        daily_movement_rows: list[dict[str, Any]] = []
        for (
            v_date,
            base_type,
            account_role,
            is_debit,
        ), aggregate_data in grouped_aggregates.items():
            daily_movement_rows.append(
                {
                    "company_id": company_id,
                    "date": v_date,
                    "base_type": base_type,
                    "account_role": account_role,
                    "is_debit": is_debit,
                    "total_amount": round(aggregate_data["total_amount"], 4),
                    "voucher_count": len(aggregate_data["voucher_ids"]),
                }
            )

        if daily_movement_rows:
            self._upsert_rows(s, "canonical_daily_movements", daily_movement_rows)

        return len(daily_movement_rows)
