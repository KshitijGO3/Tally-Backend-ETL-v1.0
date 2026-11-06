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

from backend_ETL.canonical_transformer import CanonicalTransformer
from backend_ETL.config import ETLConfig
from backend_ETL.date_utils import parse_canonical_date, parse_tally_date
from backend_ETL.db import PostgresManager

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


def build_upsert_query(
    table: str,
    columns: tuple[str, ...],
    conflict_target: str | tuple[str, ...] | None,
) -> str:
    """Constructs an idempotent PostgreSQL INSERT ... ON CONFLICT DO UPDATE query."""
    cols_csv = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    if not conflict_target:
        return f"INSERT INTO {table} ({cols_csv}) VALUES ({placeholders})"

    conflicts = (conflict_target,) if isinstance(conflict_target, str) else conflict_target
    conflict_csv = ", ".join(conflicts)
    update_cols = [c for c in columns if c not in conflicts]
    if update_cols:
        update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
        return (
            f"INSERT INTO {table} ({cols_csv}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT ({conflict_csv}) DO UPDATE SET {update_set}"
        )
    return (
        f"INSERT INTO {table} ({cols_csv}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT ({conflict_csv}) DO NOTHING"
    )


def try_acquire_company_lock(cur: Any, company_id: str) -> bool:
    """Attempts to acquire a non-blocking transaction-level PostgreSQL advisory lock."""
    try:
        cur.execute(
            "SELECT pg_try_advisory_xact_lock(hashtext('canonical_elt_' || %s)::bigint) AS locked",
            (company_id,),
        )
        row = cur.fetchone()
        if row:
            val = row["locked"] if isinstance(row, dict) else row[0]
            return bool(val)
        return True
    except Exception as e:
        log.debug("Advisory lock check skipped/unsupported (%s); proceeding with execution", e)
        return True


def get_cursor(cur: Any, company_id: str, entity: str) -> int:
    """Reads current sync watermark alter_id from canonical_sync_cursors."""
    cur.execute(
        "SELECT cursor_value FROM canonical_sync_cursors WHERE company_id = %s AND entity = %s",
        (company_id, entity),
    )
    row = cur.fetchone()
    if not row:
        return 0
    try:
        val = row["cursor_value"] if isinstance(row, dict) else row[0]
        return int(val or 0)
    except (ValueError, TypeError):
        return 0


def set_cursor(cur: Any, company_id: str, entity: str, cursor_value: int) -> None:
    """Updates sync watermark alter_id in canonical_sync_cursors."""
    cur.execute(
        """
        INSERT INTO canonical_sync_cursors (company_id, entity, cursor_value, extraction_time)
        VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (company_id, entity) DO UPDATE
        SET cursor_value = EXCLUDED.cursor_value, extraction_time = CURRENT_TIMESTAMP
        """,
        (company_id, entity, str(cursor_value)),
    )


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
        with self.db.connection() as conn:
            cur = conn.cursor()
            if company_id:
                cur.execute(
                    "SELECT * FROM companies WHERE guid = %s",
                    (company_id,),
                )
            else:
                cur.execute("SELECT * FROM companies ORDER BY guid")
            raw_companies = [dict(r) for r in cur.fetchall()]
            cur.close()

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
            with self.db.connection() as conn:
                cur = conn.cursor()
                if not try_acquire_company_lock(cur, c_guid):
                    log.info(
                        "Company '%s' (%s) ETL is already active in another worker; skipping.",
                        comp.get("name"),
                        c_guid,
                    )
                    cur.close()
                    continue

                try:
                    c_counts = self._process_company(cur, comp)
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
                finally:
                    cur.close()

        return {
            "status": "ok",
            "companies_processed": len(processed_companies),
            "company_ids": processed_companies,
            "counts": dict(total_counts),
        }

    def _process_company(self, cur: Any, comp: dict[str, Any]) -> dict[str, int]:
        """Transforms Bronze data for a single company into Silver canonical tables."""
        company_id = comp["guid"]
        counts: dict[str, int] = defaultdict(int)

        # ── Step A: Build in-memory reference lookups and parent maps ─────────
        cur.execute(
            "SELECT guid, name, parent FROM groups WHERE company_id = %s",
            (company_id,),
        )
        group_rows = [dict(r) for r in cur.fetchall()]
        group_lookup = {r["name"]: r["guid"] for r in group_rows if r.get("name")}
        group_parent_map = {r["name"]: r.get("parent") for r in group_rows if r.get("name")}

        cur.execute(
            "SELECT guid, name FROM ledgers WHERE company_id = %s",
            (company_id,),
        )
        account_lookup = {
            r["name"]: r["guid"] for r in (dict(x) for x in cur.fetchall()) if r.get("name")
        }

        cur.execute(
            "SELECT guid, name FROM stock_items WHERE company_id = %s",
            (company_id,),
        )
        item_lookup = {
            r["name"]: r["guid"] for r in (dict(x) for x in cur.fetchall()) if r.get("name")
        }

        cur.execute(
            "SELECT guid, name FROM godowns WHERE company_id = %s",
            (company_id,),
        )
        godown_lookup = {
            r["name"]: r["guid"] for r in (dict(x) for x in cur.fetchall()) if r.get("name")
        }

        cur.execute(
            "SELECT guid, name FROM units WHERE company_id = %s",
            (company_id,),
        )
        unit_lookup = {
            r["name"]: r["guid"] for r in (dict(x) for x in cur.fetchall()) if r.get("name")
        }

        cur.execute(
            "SELECT guid, name FROM cost_centres WHERE company_id = %s",
            (company_id,),
        )
        cost_centre_lookup = {
            r["name"]: r["guid"] for r in (dict(x) for x in cur.fetchall()) if r.get("name")
        }

        cur.execute(
            "SELECT guid, name FROM cost_categories WHERE company_id = %s",
            (company_id,),
        )
        cost_category_lookup = {
            r["name"]: r["guid"] for r in (dict(x) for x in cur.fetchall()) if r.get("name")
        }

        cur.execute(
            "SELECT name, parent FROM voucher_types WHERE company_id = %s",
            (company_id,),
        )
        voucher_type_parent_map = {
            r["name"]: r.get("parent") for r in (dict(x) for x in cur.fetchall()) if r.get("name")
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
        self._upsert_rows(cur, "canonical_companies", [c_trans])
        counts["companies"] += 1

        # ── Step C: Master Tables (Incremental via alter_id) ─────────────────
        books_from_norm = parse_tally_date(comp.get("books_from"))

        # 1. Groups
        counts["groups"] += self._sync_simple_master(
            cur,
            company_id,
            "groups",
            "canonical_account_groups",
            transformer.transform_group,
        )

        # 2. Ledgers (Decoupled to Accounts, Contacts, Party Identifiers, Opening Balances)
        counts["ledgers"] += self._sync_ledgers(cur, company_id, transformer, books_from_norm)

        # 3. Voucher Types
        counts["voucher_types"] += self._sync_simple_master(
            cur,
            company_id,
            "voucher_types",
            "canonical_voucher_types",
            transformer.transform_voucher_type,
        )

        # 4. Stock Groups
        counts["stock_groups"] += self._sync_simple_master(
            cur,
            company_id,
            "stock_groups",
            "canonical_stock_groups",
            transformer.transform_stock_group,
        )

        # 5. Stock Categories
        counts["stock_categories"] += self._sync_simple_master(
            cur,
            company_id,
            "stock_categories",
            "canonical_stock_categories",
            transformer.transform_stock_category,
        )

        # 6. Stock Items
        counts["stock_items"] += self._sync_simple_master(
            cur,
            company_id,
            "stock_items",
            "canonical_stock_items",
            transformer.transform_stock_item,
        )

        # 7. Godowns
        counts["godowns"] += self._sync_simple_master(
            cur,
            company_id,
            "godowns",
            "canonical_godowns",
            transformer.transform_godown,
        )

        # 8. Units
        counts["units"] += self._sync_simple_master(
            cur,
            company_id,
            "units",
            "canonical_units",
            transformer.transform_unit,
        )

        # 9. Cost Categories
        counts["cost_categories"] += self._sync_simple_master(
            cur,
            company_id,
            "cost_categories",
            "canonical_cost_categories",
            transformer.transform_cost_category,
        )

        # 10. Cost Centres
        counts["cost_centres"] += self._sync_simple_master(
            cur,
            company_id,
            "cost_centres",
            "canonical_cost_centres",
            transformer.transform_cost_centre,
        )

        # 11. Currencies
        counts["currencies"] += self._sync_simple_master(
            cur,
            company_id,
            "currencies",
            "canonical_currencies",
            transformer.transform_currency,
        )

        # 12. Employee Groups
        counts["employee_groups"] += self._sync_simple_master(
            cur,
            company_id,
            "employee_groups",
            "canonical_employee_groups",
            transformer.transform_employee_group,
        )

        # 13. Employees
        counts["employees"] += self._sync_simple_master(
            cur,
            company_id,
            "employees",
            "canonical_employees",
            transformer.transform_employee,
        )

        # 14. Attendance Types
        counts["attendance_types"] += self._sync_simple_master(
            cur,
            company_id,
            "attendance_types",
            "canonical_attendance_types",
            transformer.transform_attendance_type,
        )

        # ── Step D: Transactions (Vouchers and Decoupled Children) ───────────
        vouchers_synced = self._sync_vouchers(cur, company_id, transformer)
        counts["vouchers"] += vouchers_synced

        # ── Step E: Daily Aggregate Table Rollup (Pure Python) ───────────────
        counts["daily_movements"] += self._update_daily_movements(cur, company_id)

        return counts

    def _sync_simple_master(
        self,
        cur: Any,
        company_id: str,
        source_table: str,
        target_table: str,
        transform_fn: Any,
    ) -> int:
        """Transforms and upserts incremental master records."""
        last_cursor = get_cursor(cur, company_id, source_table)
        cur.execute(
            f"SELECT * FROM {source_table} "
            "WHERE company_id = %s AND alter_id > %s ORDER BY alter_id ASC",
            (company_id, last_cursor),
        )
        rows = [dict(r) for r in cur.fetchall()]
        if not rows:
            return 0

        transformed = [transform_fn(r) for r in rows]
        self._upsert_rows(cur, target_table, transformed)
        max_alter = max(int(r.get("alter_id") or 0) for r in rows)
        set_cursor(cur, company_id, source_table, max_alter)
        return len(rows)

    def _sync_ledgers(
        self,
        cur: Any,
        company_id: str,
        transformer: CanonicalTransformer,
        books_from_norm: date | str | None,
    ) -> int:
        """Syncs ledgers into accounts, contacts, identifiers, and opening balances."""
        last_cursor = get_cursor(cur, company_id, "ledgers")
        cur.execute(
            "SELECT * FROM ledgers WHERE company_id = %s AND alter_id > %s ORDER BY alter_id ASC",
            (company_id, last_cursor),
        )
        rows = [dict(r) for r in cur.fetchall()]
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

        self._upsert_rows(cur, "canonical_accounts", accounts)
        if contacts:
            self._upsert_rows(cur, "canonical_account_contacts", contacts)
        if party_ids:
            self._upsert_rows(cur, "canonical_party_identifiers", party_ids)
        if opening_bals:
            self._upsert_rows(cur, "canonical_opening_balances", opening_bals)

        max_alter = max(int(r.get("alter_id") or 0) for r in rows)
        set_cursor(cur, company_id, "ledgers", max_alter)
        return len(rows)

    def _sync_vouchers(
        self,
        cur: Any,
        company_id: str,
        transformer: CanonicalTransformer,
    ) -> int:
        """Batches vouchers and transforms postings, bill events, inventory,
        and cost allocations.
        """
        last_cursor = get_cursor(cur, company_id, "vouchers")
        cur.execute(
            """
            SELECT * FROM vouchers
            WHERE company_id = %s AND alter_id > %s
            ORDER BY alter_id ASC
            LIMIT %s
            """,
            (company_id, last_cursor, self.cfg.max_batch_vouchers),
        )
        vch_rows = [dict(r) for r in cur.fetchall()]
        if not vch_rows:
            return 0

        vch_guids = [v["guid"] for v in vch_rows]
        placeholders = ", ".join(["%s"] * len(vch_guids))
        guid_params = tuple(vch_guids)

        # Query all child rows in batch
        cur.execute(
            f"SELECT * FROM ledger_entries "
            f"WHERE voucher_guid IN ({placeholders}) ORDER BY id ASC",
            guid_params,
        )
        le_by_vch: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in cur.fetchall():
            d = dict(r)
            le_by_vch[d["voucher_guid"]].append(d)

        cur.execute(
            f"SELECT * FROM inventory_entries "
            f"WHERE voucher_guid IN ({placeholders}) ORDER BY id ASC",
            guid_params,
        )
        ie_by_vch: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in cur.fetchall():
            d = dict(r)
            ie_by_vch[d["voucher_guid"]].append(d)

        cur.execute(
            f"SELECT * FROM cost_centre_allocations "
            f"WHERE voucher_guid IN ({placeholders}) ORDER BY id ASC",
            guid_params,
        )
        cca_by_vch: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in cur.fetchall():
            d = dict(r)
            cca_by_vch[d["voucher_guid"]].append(d)

        cur.execute(
            f"SELECT * FROM attendance_entries "
            f"WHERE voucher_guid IN ({placeholders}) ORDER BY id ASC",
            guid_params,
        )
        ae_by_vch: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in cur.fetchall():
            d = dict(r)
            ae_by_vch[d["voucher_guid"]].append(d)

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
        self._upsert_rows(cur, "canonical_vouchers", transformed_vouchers)

        # 2. Clean previous child lines for these vouchers (atomic child replacement)
        cur.execute(
            f"DELETE FROM canonical_postings WHERE voucher_ref IN ({placeholders})",
            guid_params,
        )
        cur.execute(
            f"DELETE FROM canonical_bill_events WHERE voucher_ref IN ({placeholders})",
            guid_params,
        )
        cur.execute(
            f"DELETE FROM canonical_inventory_lines WHERE voucher_guid IN ({placeholders})",
            guid_params,
        )
        cur.execute(
            f"DELETE FROM canonical_cost_allocations WHERE voucher_ref IN ({placeholders})",
            guid_params,
        )
        cur.execute(
            f"DELETE FROM canonical_attendance_entries WHERE voucher_guid IN ({placeholders})",
            guid_params,
        )

        # 3. Insert fresh transformed child rows
        if all_postings:
            self._upsert_rows(cur, "canonical_postings", all_postings)
        if all_bill_events:
            self._upsert_rows(cur, "canonical_bill_events", all_bill_events)
        if all_inv_lines:
            self._upsert_rows(cur, "canonical_inventory_lines", all_inv_lines)
        if all_cost_allocs:
            self._upsert_rows(cur, "canonical_cost_allocations", all_cost_allocs)
        if all_att_entries:
            self._upsert_rows(cur, "canonical_attendance_entries", all_att_entries)

        # 4. Advance cursor
        max_alter = max(int(v.get("alter_id") or 0) for v in vch_rows)
        set_cursor(cur, company_id, "vouchers", max_alter)
        return len(vch_rows)

    def _upsert_rows(
        self,
        cur: Any,
        table_name: str,
        rows: Sequence[dict[str, Any]],
    ) -> None:
        """Executes a parameterized bulk upsert/insert using table specifications."""
        if not rows:
            return

        spec = CANONICAL_TABLE_SPECS[table_name]
        columns: tuple[str, ...] = spec["columns"]
        conflict = spec.get("conflict")

        sql = build_upsert_query(table_name, columns, conflict)
        param_tuples = [tuple(r.get(c) for c in columns) for r in rows]
        log.debug(sql)
        log.debug(param_tuples)
        cur.executemany(sql, param_tuples)

    def _update_daily_movements(
        self,
        cur: Any,
        company_id: str,
        affected_dates: set[date | str] | None = None,
    ) -> int:
        """Aggregates active voucher postings by day, base voucher type, account role, and debit/credit.

        Idempotently updates canonical_daily_movements in pure Python without DB triggers or procedures.
        """
        # Fetch account classification roles for the company
        cur.execute(
            "SELECT account_id, classification_role FROM canonical_accounts WHERE company_id = %s",
            (company_id,),
        )
        account_role_mapping = {
            r["account_id"]: (r.get("classification_role") or "other")
            for r in (dict(x) for x in cur.fetchall())
            if r.get("account_id")
        }

        # Query active vouchers and postings
        if affected_dates:
            date_list = sorted(list(affected_dates))
            placeholders = ", ".join(["%s"] * len(date_list))
            query_sql = f"""
                SELECT v.voucher_id, v.date, v.base_type, p.account_ref, p.amount, p.source_deemed_positive
                FROM canonical_vouchers v
                JOIN canonical_postings p ON v.voucher_id = p.voucher_ref
                WHERE v.company_id = %s AND v.lifecycle = 'active' AND v.date IN ({placeholders})
            """
            query_parameters: tuple[Any, ...] = (company_id, *date_list)
        else:
            query_sql = """
                SELECT v.voucher_id, v.date, v.base_type, p.account_ref, p.amount, p.source_deemed_positive
                FROM canonical_vouchers v
                JOIN canonical_postings p ON v.voucher_id = p.voucher_ref
                WHERE v.company_id = %s AND v.lifecycle = 'active'
            """
            query_parameters = (company_id,)

        cur.execute(query_sql, query_parameters)
        posting_records = [dict(r) for r in cur.fetchall()]

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
        if affected_dates:
            date_list = sorted(list(affected_dates))
            delete_placeholders = ", ".join(["%s"] * len(date_list))
            cur.execute(
                f"DELETE FROM canonical_daily_movements WHERE company_id = %s AND date IN ({delete_placeholders})",
                (company_id, *date_list),
            )
        else:
            cur.execute(
                "DELETE FROM canonical_daily_movements WHERE company_id = %s",
                (company_id,),
            )

        daily_movement_rows: list[dict[str, Any]] = []
        for (v_date, base_type, account_role, is_debit), aggregate_data in grouped_aggregates.items():
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
            self._upsert_rows(cur, "canonical_daily_movements", daily_movement_rows)

        return len(daily_movement_rows)
