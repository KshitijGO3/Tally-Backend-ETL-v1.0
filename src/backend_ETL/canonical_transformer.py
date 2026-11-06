"""Pure Python Transformation Engine for Tally Replicated to Canonical Domain Model.

Encapsulates date normalization to native SQL date objects (datetime.date), name-to-GUID resolution,
PII quarantining, multi-level group hierarchy traversal, ledger role classification,
and bill-event decoupling.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from backend_ETL.date_utils import parse_tally_date

log = logging.getLogger(__name__)


def walk_group_hierarchy(
    start_group: str | None,
    group_parent_map: dict[str, str | None],
) -> list[str]:
    """Walks upwards through the Tally group hierarchy until reaching the root parent.

    Termination Rules:
    1. Parent is None, empty, or whitespace.
    2. Group name == Parent name (Tally root convention, e.g. Primary -> Primary).
    3. Cyclical reference detected (visited set guards against infinite loops).

    Args:
        start_group: The starting group name.
        group_parent_map: Dictionary mapping child group name to parent group name.

    Returns:
        List of group names traversed from start_group up to the root ancestor.
    """
    if not start_group:
        return []

    chain: list[str] = []
    curr = start_group.strip()
    visited: set[str] = set()

    while curr and curr not in visited:
        chain.append(curr)
        visited.add(curr)
        parent = group_parent_map.get(curr)
        if not parent or not str(parent).strip():
            break
        parent = str(parent).strip()
        # Termination condition: group name = parent name (Tally self-referential root)
        if parent.lower() == curr.lower():
            break
        curr = parent

    return chain


def infer_ledger_role(
    direct_group: str | None,
    group_parent_map: dict[str, str | None],
) -> str:
    """Classifies a ledger into customer/supplier/bank/cash/tax/expense/income/other
    by walking upwards through all layers of the group tree until reaching the root.

    Args:
        direct_group: The immediate parent group of the ledger.
        group_parent_map: Dictionary mapping group names to their parent group names.

    Returns:
        Classification role string ('customer', 'supplier', 'bank', 'cash', 'tax',
        'expense', 'income', or 'other').
    """
    if not direct_group:
        return "other"

    chain = walk_group_hierarchy(direct_group, group_parent_map)
    for g_name in chain:
        g = g_name.lower()
        if "sundry debtors" in g or "debtor" in g:
            return "customer"
        if "sundry creditors" in g or "creditor" in g:
            return "supplier"
        if any(k in g for k in ("bank accounts", "bank occ", "bank od")):
            return "bank"
        if "cash-in-hand" in g or "cash" in g:
            return "cash"
        if "duties & taxes" in g or "tax" in g:
            return "tax"
        if any(k in g for k in ("direct expenses", "indirect expenses", "expense")):
            return "expense"
        if any(k in g for k in ("sales accounts", "direct incomes", "indirect incomes", "income")):
            return "income"

    return "other"


def resolve_ref(name: str | None, lookup: dict[str, str]) -> str | None:
    """Resolves name to GUID via exact (company_id, name) lookup, falling back to name."""
    if not name:
        return None
    cleaned = str(name).strip()
    return lookup.get(cleaned, cleaned)


PRIMARY_VOUCHER_TYPES: tuple[str, ...] = (
    "Sales",
    "Purchase",
    "Receipt",
    "Payment",
    "Credit Note",
    "Debit Note",
    "Journal",
    "Contra",
    "Attendance",
    "Payroll",
    "Stock Journal",
    "Physical Stock",
    "Delivery Note",
    "Receipt Note",
    "Rejections In",
    "Rejections Out",
    "Material In",
    "Material Out",
    "Memorandum",
    "Reversing Journal",
)

_PRIMARY_VT_LOWER_MAP: dict[str, str] = {vt.lower(): vt for vt in PRIMARY_VOUCHER_TYPES}


def walk_voucher_type_hierarchy(
    start_type: str | None,
    voucher_type_parent_map: dict[str, str | None] | None,
) -> str:
    """Climbs the voucher type hierarchy in Python memory to resolve custom voucher types
    to primary Tally types (e.g. 'Tax Invoice' -> 'Sales', 'Cash Receipt' -> 'Receipt').

    Termination Rules:
    1. Direct match with a primary Tally voucher type (case-insensitive).
    2. Parent is None, empty, or whitespace.
    3. Cyclical reference detected (visited set guards against loops).
    4. Heuristic keyword fallback (e.g. contains 'sales' or 'receipt').

    Args:
        start_type: The starting voucher type name.
        voucher_type_parent_map: Dictionary mapping custom voucher type name to parent voucher type name.

    Returns:
        Canonical primary voucher type string (e.g. 'Sales', 'Receipt', etc.) or cleaned start_type.
    """
    if not start_type:
        return "Unknown"

    cleaned_start = start_type.strip()
    if not cleaned_start:
        return "Unknown"

    vt_map = voucher_type_parent_map or {}
    curr = cleaned_start
    visited: set[str] = set()

    while curr and curr not in visited:
        curr_lower = curr.lower()
        if curr_lower in _PRIMARY_VT_LOWER_MAP:
            return _PRIMARY_VT_LOWER_MAP[curr_lower]

        visited.add(curr)
        parent = vt_map.get(curr)
        if not parent or not str(parent).strip():
            break
        parent_cleaned = str(parent).strip()
        if parent_cleaned.lower() == curr.lower():
            break
        curr = parent_cleaned

    # Keyword heuristics fallback if primary type not directly named in tree
    lowered = cleaned_start.lower()
    if "credit note" in lowered:
        return "Credit Note"
    if "debit note" in lowered:
        return "Debit Note"
    if "sales" in lowered or "sale" in lowered or "invoice" in lowered:
        return "Sales"
    if "receipt" in lowered:
        return "Receipt"
    if "purchase" in lowered:
        return "Purchase"
    if "payment" in lowered:
        return "Payment"
    if "contra" in lowered:
        return "Contra"
    if "journal" in lowered:
        return "Journal"

    return cleaned_start


class CanonicalTransformer:
    """Transforms raw Bronze record dictionaries into cleaned Canonical Silver dictionaries."""

    def __init__(
        self,
        company_id: str,
        account_lookup: dict[str, str] | None = None,
        group_lookup: dict[str, str] | None = None,
        group_parent_map: dict[str, str | None] | None = None,
        item_lookup: dict[str, str] | None = None,
        godown_lookup: dict[str, str] | None = None,
        unit_lookup: dict[str, str] | None = None,
        cost_centre_lookup: dict[str, str] | None = None,
        cost_category_lookup: dict[str, str] | None = None,
        voucher_type_parent_map: dict[str, str | None] | None = None,
        voucher_base_type_lookup: dict[str, str] | None = None,
    ) -> None:
        self.company_id = company_id
        self.account_lookup = account_lookup or {}
        self.group_lookup = group_lookup or {}
        self.group_parent_map = group_parent_map or {}
        self.item_lookup = item_lookup or {}
        self.godown_lookup = godown_lookup or {}
        self.unit_lookup = unit_lookup or {}
        self.cost_centre_lookup = cost_centre_lookup or {}
        self.cost_category_lookup = cost_category_lookup or {}
        self.voucher_type_parent_map = voucher_type_parent_map or {}
        self.voucher_base_type_lookup = voucher_base_type_lookup or {}

    def transform_company(self, row: dict[str, Any]) -> dict[str, Any]:
        """Maps raw companies -> canonical_companies with native SQL date objects (datetime.date)."""
        return {
            "company_id": row["guid"],
            "name": row.get("name") or "",
            "books_from": parse_tally_date(row.get("books_from")),
            "starting_from": parse_tally_date(row.get("starting_from")),
            "company_number": row.get("company_number"),
            "books_to": parse_tally_date(row.get("ending_at")),
            "company_gstin": row.get("gstin"),
            "source_master_id": row.get("master_id") or 0,
            "source_alter_id": row.get("alter_id") or 0,
        }

    def transform_group(self, row: dict[str, Any]) -> dict[str, Any]:
        """Maps raw groups -> canonical_account_groups with resolved parent GUID and parent chain.
        """
        group_name = row.get("name") or ""
        parent_name = row.get("parent")
        chain = walk_group_hierarchy(group_name, self.group_parent_map)
        parent_chain_str = " > ".join(reversed(chain)) if chain else None

        return {
            "accountgroup_id": row["guid"],
            "company_id": self.company_id,
            "name": group_name,
            "parent_ref": resolve_ref(parent_name, self.group_lookup),
            "parent_chain": parent_chain_str,
            "nature": row.get("nature"),
            "primary_group": row.get("primary_group"),
            "is_revenue": bool(row.get("is_revenue")),
            "is_deemed_positive": bool(row.get("is_deemed_positive")),
            "affects_gross_profit": bool(row.get("affects_gross_profit")),
            "source_master_id": row.get("master_id") or 0,
            "source_alter_id": row.get("alter_id") or 0,
        }

    def transform_ledger(
        self,
        row: dict[str, Any],
        books_from_date: date | str | None = None,
    ) -> dict[str, Any]:
        """Splits raw ledgers into Account, AccountContact (PII), PartyIdentifier,
        and OpeningBalance.
        """
        ledger_id = row["guid"]
        parent_name = row.get("parent")
        role = infer_ledger_role(parent_name, self.group_parent_map)

        account = {
            "account_id": ledger_id,
            "company_id": self.company_id,
            "name": row.get("name") or "",
            "group_ref": resolve_ref(parent_name, self.group_lookup),
            "aliases": row.get("alias"),
            "credit_limit": row.get("credit_limit"),
            "credit_period_raw": row.get("credit_period"),
            "bill_wise": bool(row.get("is_bill_wise_on")),
            "cost_centres_on": bool(row.get("is_cost_centres_on")),
            "currency": row.get("currency_name"),
            "reported_closing": row.get("closing_balance"),
            "gst_reg_type": row.get("gst_registration_type"),
            "tax_classification": row.get("tax_classification"),
            "classification_role": role,
            "source_master_id": row.get("master_id") or 0,
            "source_alter_id": row.get("alter_id") or 0,
        }

        # Quarantined PII Contact Record
        contact = None
        if any(
            row.get(k)
            for k in ("mailing_name", "address", "pan_number", "email", "phone", "mobile")
        ):
            contact = {
                "account_ref": ledger_id,
                "contact_mailing_name": row.get("mailing_name"),
                "contact_address": row.get("addrdess"),
                "contact_state_name": row.get("state_name"),
                "contact_country_name": row.get("country_name"),
                "contact_pincode": row.get("pincode"),
                "contact_email": row.get("email"),
                "contact_phone": row.get("phone"),
                "contact_mobile": row.get("mobile"),
                "party_pan": row.get("pan_number"),
            }

        # Party Identifier (GSTIN)
        party_id = None
        raw_gstin = (row.get("gstin") or "").strip()
        if raw_gstin:
            party_id = {
                "party_ref": ledger_id,
                "id_type": "gstin",
                "value": raw_gstin,
                "confidence": "OBSERVED",
                "source": "tally_ledger_master",
            }

        # Baseline Opening Balance (as-of books_from date)
        op_bal = {
            "account_ref": ledger_id,
            "company_id": self.company_id,
            "amount": row.get("opening_balance") or 0.0,
            "as_of": books_from_date if isinstance(books_from_date, date) else parse_tally_date(books_from_date),
        }

        return {
            "account": account,
            "contact": contact,
            "party_identifier": party_id,
            "opening_balance": op_bal,
        }

    def transform_voucher_type(self, row: dict[str, Any]) -> dict[str, Any]:
        """Maps raw voucher_types -> canonical_voucher_types including resolved base_type."""
        voucher_type_name = row.get("name") or ""
        parent_voucher_type = row.get("parent")
        resolved_base_type = walk_voucher_type_hierarchy(
            parent_voucher_type or voucher_type_name,
            self.voucher_type_parent_map,
        )
        return {
            "vouchertype_id": row["guid"],
            "company_id": self.company_id,
            "name": voucher_type_name,
            "parent_kind": parent_voucher_type,
            "base_type": resolved_base_type,
            "numbering_method": row.get("numbering_method"),
            "is_active": bool(row.get("is_active", True)),
            "affects_stock": bool(row.get("affects_stock", False)),
            "prevent_duplicates": bool(row.get("prevent_duplicates", False)),
            "source_master_id": row.get("master_id") or 0,
            "source_alter_id": row.get("alter_id") or 0,
        }

    def transform_stock_group(self, row: dict[str, Any]) -> dict[str, Any]:
        """Maps raw stock_groups -> canonical_stock_groups."""
        return {
            "stockgroup_id": row["guid"],
            "company_id": self.company_id,
            "name": row.get("name") or "",
            "parent_ref": row.get("parent"),
            "source_master_id": row.get("master_id") or 0,
            "source_alter_id": row.get("alter_id") or 0,
        }

    def transform_stock_category(self, row: dict[str, Any]) -> dict[str, Any]:
        """Maps raw stock_categories -> canonical_stock_categories."""
        return {
            "stockcategory_id": row["guid"],
            "company_id": self.company_id,
            "name": row.get("name") or "",
            "parent_ref": row.get("parent"),
            "source_master_id": row.get("master_id") or 0,
            "source_alter_id": row.get("alter_id") or 0,
        }

    def transform_stock_item(self, row: dict[str, Any]) -> dict[str, Any]:
        """Maps raw stock_items -> canonical_stock_items."""
        return {
            "stockitem_id": row["guid"],
            "company_id": self.company_id,
            "name": row.get("name") or "",
            "parent_ref": row.get("parent"),
            "category": row.get("category"),
            "base_units": row.get("base_units"),
            "alternate_units": row.get("alternate_units"),
            "hsn_code": row.get("hsn_code"),
            "gst_applicable": row.get("gst_applicable"),
            "gst_type_of_supply": row.get("gst_type_of_supply"),
            "tax_rate": row.get("tax_rate"),
            "costing_method": row.get("costing_method"),
            "valuation_method": row.get("valuation_method"),
            "opening_qty": row.get("opening_balance"),
            "opening_rate": row.get("opening_rate"),
            "opening_value": row.get("opening_value"),
            "closing_qty": row.get("closing_balance"),
            "closing_value": row.get("closing_value"),
            "source_master_id": row.get("master_id") or 0,
            "source_alter_id": row.get("alter_id") or 0,
        }

    def transform_godown(self, row: dict[str, Any]) -> dict[str, Any]:
        """Maps raw godowns -> canonical_godowns."""
        return {
            "godown_id": row["guid"],
            "company_id": self.company_id,
            "name": row.get("name") or "",
            "parent_ref": row.get("parent"),
            "address": row.get("address"),
            "has_no_space": bool(row.get("has_no_space")),
            "has_no_stock": bool(row.get("has_no_stock")),
            "source_master_id": row.get("master_id") or 0,
            "source_alter_id": row.get("alter_id") or 0,
        }

    def transform_unit(self, row: dict[str, Any]) -> dict[str, Any]:
        """Maps raw units -> canonical_units."""
        return {
            "unit_id": row["guid"],
            "company_id": self.company_id,
            "name": row.get("name") or "",
            "original_name": row.get("original_name"),
            "base_units": row.get("base_units"),
            "is_simple_unit": bool(row.get("is_simple_unit", True)),
            "decimal_places": row.get("decimal_places") or 0,
            "conversion": row.get("conversion"),
            "source_master_id": row.get("master_id") or 0,
            "source_alter_id": row.get("alter_id") or 0,
        }

    def transform_cost_category(self, row: dict[str, Any]) -> dict[str, Any]:
        """Maps raw cost_categories -> canonical_cost_categories."""
        return {
            "costcategory_id": row["guid"],
            "company_id": self.company_id,
            "name": row.get("name") or "",
            "allocate_revenue": bool(row.get("allocate_revenue", True)),
            "allocate_non_revenue": bool(row.get("allocate_non_revenue", False)),
            "source_master_id": row.get("master_id") or 0,
            "source_alter_id": row.get("alter_id") or 0,
        }

    def transform_cost_centre(self, row: dict[str, Any]) -> dict[str, Any]:
        """Maps raw cost_centres -> canonical_cost_centres."""
        return {
            "costcentre_id": row["guid"],
            "company_id": self.company_id,
            "name": row.get("name") or "",
            "parent_ref": row.get("parent"),
            "category": row.get("category"),
            "revenue_le_for_op_bal": bool(row.get("revenue_le_for_op_bal")),
            "email_id": row.get("email_id"),
            "source_master_id": row.get("master_id") or 0,
            "source_alter_id": row.get("alter_id") or 0,
        }

    def transform_currency(self, row: dict[str, Any]) -> dict[str, Any]:
        """Maps raw currencies -> canonical_currencies."""
        return {
            "currency_id": row["guid"],
            "company_id": self.company_id,
            "name": row.get("name") or "",
            "mailing_name": row.get("mailing_name"),
            "original_name": row.get("original_name"),
            "expanded_symbol": row.get("expanded_symbol"),
            "decimal_symbol": row.get("decimal_symbol") or ".",
            "decimal_places": row.get("decimal_places") or 2,
            "source_master_id": row.get("master_id") or 0,
            "source_alter_id": row.get("alter_id") or 0,
        }

    def transform_employee_group(self, row: dict[str, Any]) -> dict[str, Any]:
        """Maps raw employee_groups -> canonical_employee_groups."""
        return {
            "employeegroup_id": row["guid"],
            "company_id": self.company_id,
            "name": row.get("name") or "",
            "parent_ref": row.get("parent"),
            "category": row.get("category"),
            "source_master_id": row.get("master_id") or 0,
            "source_alter_id": row.get("alter_id") or 0,
        }

    def transform_employee(self, row: dict[str, Any]) -> dict[str, Any]:
        """Maps raw employees -> canonical_employees with native SQL date objects (datetime.date) and PII."""
        return {
            "employee_id": row["guid"],
            "company_id": self.company_id,
            "name": row.get("name") or "",
            "parent_ref": row.get("parent"),
            "category": row.get("category"),
            "date_of_joining": parse_tally_date(row.get("date_of_joining")),
            "deactivation_date": parse_tally_date(row.get("deactivation_date")),
            "designation": row.get("designation"),
            "function_role": row.get("function_role"),
            "location": row.get("location"),
            "gender": row.get("gender"),
            "blood_group": row.get("blood_group"),
            "pan_number": row.get("pan_number"),
            "aadhar_number": row.get("aadhar_number"),
            "pf_number": row.get("pf_number"),
            "uan": row.get("uan"),
            "esi_number": row.get("esi_number"),
            "bank_name": row.get("bank_name"),
            "bank_account_number": row.get("bank_account_number"),
            "ifsc_code": row.get("ifsc_code"),
            "email": row.get("email"),
            "mobile": row.get("mobile"),
            "source_master_id": row.get("master_id") or 0,
            "source_alter_id": row.get("alter_id") or 0,
        }

    def transform_attendance_type(self, row: dict[str, Any]) -> dict[str, Any]:
        """Maps raw attendance_types -> canonical_attendance_types."""
        return {
            "attendancetype_id": row["guid"],
            "company_id": self.company_id,
            "name": row.get("name") or "",
            "parent_ref": row.get("parent"),
            "attendance_production_type": row.get("attendance_production_type"),
            "attendance_period": row.get("attendance_period"),
            "base_units": row.get("base_units"),
            "source_master_id": row.get("master_id") or 0,
            "source_alter_id": row.get("alter_id") or 0,
        }

    def transform_voucher(self, row: dict[str, Any]) -> dict[str, Any]:
        """Maps raw vouchers -> canonical_vouchers with native SQL date objects (datetime.date) and base_type."""
        party_name = row.get("party_ledger_name")
        is_cancelled = bool(row.get("is_cancelled"))
        voucher_kind = row.get("voucher_type_name") or ""
        resolved_base_type = self.voucher_base_type_lookup.get(
            voucher_kind
        ) or walk_voucher_type_hierarchy(voucher_kind, self.voucher_type_parent_map)

        return {
            "voucher_id": row["guid"],
            "company_id": self.company_id,
            "date": parse_tally_date(row.get("date")),
            "kind": voucher_kind,
            "base_type": resolved_base_type,
            "number": row.get("voucher_number") or "",
            "narration": row.get("narration"),
            "reference": row.get("reference"),
            "party_ref": resolve_ref(party_name, self.account_lookup),
            "lifecycle": "cancelled" if is_cancelled else "active",
            "is_optional": bool(row.get("is_optional")),
            "is_invoice": bool(row.get("is_invoice")),
            "persisted_view": row.get("persisted_view"),
            "effective_date": parse_tally_date(row.get("effective_date")),
            "reference_date": parse_tally_date(row.get("reference_date")),
            "place_of_supply": row.get("place_of_supply"),
            "party_gstin_doc": row.get("party_gstin"),
            "ship_to": row.get("consignee_name"),
            "irn": row.get("irn"),
            "eway_bill_no": row.get("eway_bill_no"),
            "source_master_id": row.get("master_id") or 0,
            "source_alter_id": row.get("alter_id") or 0,
        }

    def transform_ledger_entries(
        self,
        rows: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Decouples ledger_entries into canonical_postings and canonical_bill_events."""
        postings: list[dict[str, Any]] = []
        bill_events: list[dict[str, Any]] = []

        bill_type_map = {
            "New Ref": "new",
            "Agst Ref": "agst",
            "On Account": "on_account",
            "Advance": "advance",
        }

        for idx, row in enumerate(rows, start=1):
            ledger_name = row.get("ledger_name")
            account_id = resolve_ref(ledger_name, self.account_lookup)

            # 1. Posting leg (general ledger order preserved)
            postings.append(
                {
                    "voucher_ref": row["voucher_guid"],
                    "line_ordinal": idx,
                    "account_ref": account_id or ledger_name or "Unknown Account",
                    "amount": float(row.get("amount") or 0.0),
                    "source_deemed_positive": bool(row.get("is_deemed_positive")),
                }
            )

            # 2. Bill Event (Decoupled settlement allocation)
            bill_ref = row.get("bill_ref")
            raw_bill_type = row.get("bill_type")
            if bill_ref or raw_bill_type:
                bill_events.append(
                    {
                        "voucher_ref": row["voucher_guid"],
                        "company_id": self.company_id,
                        "party_ref": account_id or ledger_name or "Unknown Party",
                        "bill_ref": str(bill_ref or "").strip(),
                        "kind": bill_type_map.get(raw_bill_type, "unspecified"),
                        "due_date": parse_tally_date(row.get("bill_due_date")),
                        "credit_period_raw": row.get("bill_credit_period"),
                        "amount": float(row.get("bill_amount") or row.get("amount") or 0.0),
                    }
                )

        return postings, bill_events

    def transform_inventory_entries(
        self,
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Maps inventory_entries -> canonical_inventory_lines."""
        lines: list[dict[str, Any]] = []
        for row in rows:
            item_name = row.get("stock_item_name")
            godown_name = row.get("godown_name")
            unit_name = row.get("unit")
            lines.append(
                {
                    "voucher_guid": row["voucher_guid"],
                    "item_ref": resolve_ref(item_name, self.item_lookup)
                    or item_name
                    or "Unknown Item",
                    "billed_qty": float(row.get("billed_qty") or 0.0),
                    "actual_qty": float(row.get("actual_qty") or 0.0),
                    "rate": float(row.get("rate") or 0.0),
                    "amount": float(row.get("amount") or 0.0),
                    "godown_ref": resolve_ref(godown_name, self.godown_lookup),
                    "batch_ref": row.get("batch_name"),
                    "unit_ref": resolve_ref(unit_name, self.unit_lookup),
                }
            )
        return lines

    def transform_cost_allocations(
        self,
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Maps cost_centre_allocations -> canonical_cost_allocations."""
        allocations: list[dict[str, Any]] = []
        for idx, row in enumerate(rows, start=1):
            ledger_name = row.get("ledger_name")
            cat_name = row.get("cost_category")
            centre_name = row.get("cost_centre_name")
            allocations.append(
                {
                    "voucher_ref": row["voucher_guid"],
                    "line_ordinal": idx,
                    "account_ref": resolve_ref(ledger_name, self.account_lookup)
                    or ledger_name
                    or "Unknown Account",
                    "cost_category_ref": resolve_ref(cat_name, self.cost_category_lookup),
                    "cost_centre_ref": resolve_ref(centre_name, self.cost_centre_lookup)
                    or centre_name
                    or "Unknown Centre",
                    "amount": float(row.get("amount") or 0.0),
                    "source_deemed_positive": bool(row.get("is_deemed_positive")),
                }
            )
        return allocations

    def transform_attendance_entries(
        self,
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Maps attendance_entries -> canonical_attendance_entries."""
        entries: list[dict[str, Any]] = []
        for row in rows:
            entries.append(
                {
                    "voucher_guid": row["voucher_guid"],
                    "employee_name": row.get("employee_name") or "",
                    "attendance_type": row.get("attendance_type") or "",
                    "value": float(row.get("value")) if row.get("value") is not None else None,
                    "time_value": float(row.get("time_value"))
                    if row.get("time_value") is not None
                    else None,
                }
            )
        return entries
