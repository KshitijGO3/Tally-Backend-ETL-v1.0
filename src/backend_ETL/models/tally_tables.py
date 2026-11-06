"""Bronze Tally replication tables: companies, masters, vouchers and child entries."""

from __future__ import annotations

import datetime as dt  # noqa: F401
import decimal  # noqa: F401

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend_ETL.models.base import Base


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (Index("idx_comp_alter_id", "alter_id"),)

    guid: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    books_from: Mapped[str | None] = mapped_column(Text)
    starting_from: Mapped[str | None] = mapped_column(Text)
    company_number: Mapped[str | None] = mapped_column(Text)
    ending_at: Mapped[str | None] = mapped_column(Text)
    gstin: Mapped[str | None] = mapped_column(Text)
    master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    synced_at: Mapped[str | None] = mapped_column(Text)


class Currency(Base):
    __tablename__ = "currencies"
    __table_args__ = (
        Index("idx_curr_company", "company_id"),
        Index("idx_curr_alter_id", "alter_id"),
    )

    guid: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    mailing_name: Mapped[str | None] = mapped_column(Text)
    original_name: Mapped[str | None] = mapped_column(Text)
    expanded_symbol: Mapped[str | None] = mapped_column(Text)
    decimal_symbol: Mapped[str | None] = mapped_column(Text)
    decimal_places: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("2"))
    master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    synced_at: Mapped[str | None] = mapped_column(Text)


class Group(Base):
    __tablename__ = "groups"
    __table_args__ = (
        Index("idx_group_company", "company_id"),
        Index("idx_group_master_id", "master_id"),
        Index("idx_group_alter_id", "alter_id"),
    )

    guid: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent: Mapped[str | None] = mapped_column(Text)
    nature: Mapped[str | None] = mapped_column(Text)
    primary_group: Mapped[str | None] = mapped_column(Text)
    is_revenue: Mapped[int | None] = mapped_column(Integer)
    is_deemed_positive: Mapped[int | None] = mapped_column(Integer)
    affects_gross_profit: Mapped[int | None] = mapped_column(Integer)
    master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    synced_at: Mapped[str | None] = mapped_column(Text)


class CostCategory(Base):
    __tablename__ = "cost_categories"
    __table_args__ = (
        Index("idx_ccat_company", "company_id"),
        Index("idx_ccat_alter_id", "alter_id"),
    )

    guid: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    allocate_revenue: Mapped[int | None] = mapped_column(Integer)
    allocate_non_revenue: Mapped[int | None] = mapped_column(Integer)
    master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    synced_at: Mapped[str | None] = mapped_column(Text)


class CostCentre(Base):
    __tablename__ = "cost_centres"
    __table_args__ = (
        Index("idx_cc_company", "company_id"),
        Index("idx_cc_alter_id", "alter_id"),
    )

    guid: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    revenue_le_for_op_bal: Mapped[int | None] = mapped_column(Integer)
    email_id: Mapped[str | None] = mapped_column(Text)
    master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    synced_at: Mapped[str | None] = mapped_column(Text)


class EmployeeGroup(Base):
    __tablename__ = "employee_groups"
    __table_args__ = (
        Index("idx_empg_company", "company_id"),
        Index("idx_empg_alter_id", "alter_id"),
    )

    guid: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    synced_at: Mapped[str | None] = mapped_column(Text)


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (
        Index("idx_emp_company", "company_id"),
        Index("idx_emp_alter_id", "alter_id"),
    )

    guid: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    employee_id: Mapped[str | None] = mapped_column(Text)
    date_of_joining: Mapped[str | None] = mapped_column(Text)
    deactivation_date: Mapped[str | None] = mapped_column(Text)
    designation: Mapped[str | None] = mapped_column(Text)
    function_role: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    gender: Mapped[str | None] = mapped_column(Text)
    blood_group: Mapped[str | None] = mapped_column(Text)
    pan_number: Mapped[str | None] = mapped_column(Text)
    aadhar_number: Mapped[str | None] = mapped_column(Text)
    pf_number: Mapped[str | None] = mapped_column(Text)
    uan: Mapped[str | None] = mapped_column(Text)
    esi_number: Mapped[str | None] = mapped_column(Text)
    bank_name: Mapped[str | None] = mapped_column(Text)
    bank_account_number: Mapped[str | None] = mapped_column(Text)
    ifsc_code: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    mobile: Mapped[str | None] = mapped_column(Text)
    master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    synced_at: Mapped[str | None] = mapped_column(Text)


class AttendanceType(Base):
    __tablename__ = "attendance_types"
    __table_args__ = (
        Index("idx_at_company", "company_id"),
        Index("idx_at_alter_id", "alter_id"),
    )

    guid: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent: Mapped[str | None] = mapped_column(Text)
    attendance_production_type: Mapped[str | None] = mapped_column(Text)
    attendance_period: Mapped[str | None] = mapped_column(Text)
    base_units: Mapped[str | None] = mapped_column(Text)
    master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    synced_at: Mapped[str | None] = mapped_column(Text)


class StockCategory(Base):
    __tablename__ = "stock_categories"
    __table_args__ = (
        Index("idx_scat_company", "company_id"),
        Index("idx_scat_alter_id", "alter_id"),
    )

    guid: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent: Mapped[str | None] = mapped_column(Text)
    master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    synced_at: Mapped[str | None] = mapped_column(Text)


class StockGroup(Base):
    __tablename__ = "stock_groups"
    __table_args__ = (
        Index("idx_sg_company", "company_id"),
        Index("idx_sg_master_id", "master_id"),
        Index("idx_sg_alter_id", "alter_id"),
    )

    guid: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent: Mapped[str | None] = mapped_column(Text)
    master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    synced_at: Mapped[str | None] = mapped_column(Text)


class Unit(Base):
    __tablename__ = "units"
    __table_args__ = (
        Index("idx_unit_master_id", "master_id"),
        Index("idx_unit_alter_id", "alter_id"),
    )

    guid: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    original_name: Mapped[str | None] = mapped_column(Text)
    base_units: Mapped[str | None] = mapped_column(Text)
    is_simple_unit: Mapped[int | None] = mapped_column(Integer)
    decimal_places: Mapped[int | None] = mapped_column(Integer)
    conversion: Mapped[str | None] = mapped_column(Text)
    master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    synced_at: Mapped[str | None] = mapped_column(Text)


class Godown(Base):
    __tablename__ = "godowns"
    __table_args__ = (
        Index("idx_godown_master_id", "master_id"),
        Index("idx_godown_alter_id", "alter_id"),
    )

    guid: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    has_no_space: Mapped[int | None] = mapped_column(Integer)
    has_no_stock: Mapped[int | None] = mapped_column(Integer)
    master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    synced_at: Mapped[str | None] = mapped_column(Text)


class VoucherType(Base):
    __tablename__ = "voucher_types"
    __table_args__ = (
        Index("idx_vt_company", "company_id"),
        Index("idx_vt_name", "company_id", "name"),
        Index("idx_vt_alter_id", "alter_id"),
    )

    guid: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent: Mapped[str | None] = mapped_column(Text)
    numbering_method: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[int | None] = mapped_column(Integer)
    affects_stock: Mapped[int | None] = mapped_column(Integer)
    prevent_duplicates: Mapped[int | None] = mapped_column(Integer)
    master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    synced_at: Mapped[str | None] = mapped_column(Text)


class Ledger(Base):
    __tablename__ = "ledgers"
    __table_args__ = (
        Index("idx_ledger_company", "company_id"),
        Index("idx_ledger_master_id", "master_id"),
        Index("idx_ledger_alter_id", "alter_id"),
    )

    guid: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent: Mapped[str | None] = mapped_column(Text)
    alias: Mapped[str | None] = mapped_column(Text)
    mailing_name: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    state_name: Mapped[str | None] = mapped_column(Text)
    country_name: Mapped[str | None] = mapped_column(Text)
    pincode: Mapped[str | None] = mapped_column(Text)
    pan_number: Mapped[str | None] = mapped_column(Text)
    gstin: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    mobile: Mapped[str | None] = mapped_column(Text)
    credit_limit: Mapped[str | None] = mapped_column(Text)
    credit_period: Mapped[str | None] = mapped_column(Text)
    is_bill_wise_on: Mapped[int | None] = mapped_column(Integer)
    is_cost_centres_on: Mapped[int | None] = mapped_column(Integer)
    currency_name: Mapped[str | None] = mapped_column(Text)
    opening_balance: Mapped[str | None] = mapped_column(Text)
    closing_balance: Mapped[str | None] = mapped_column(Text)
    gst_registration_type: Mapped[str | None] = mapped_column(Text)
    tax_classification: Mapped[str | None] = mapped_column(Text)
    master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    synced_at: Mapped[str | None] = mapped_column(Text)


class StockItem(Base):
    __tablename__ = "stock_items"
    __table_args__ = (
        Index("idx_si_company", "company_id"),
        Index("idx_si_master_id", "master_id"),
        Index("idx_si_alter_id", "alter_id"),
    )

    guid: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    base_units: Mapped[str | None] = mapped_column(Text)
    alternate_units: Mapped[str | None] = mapped_column(Text)
    hsn_code: Mapped[str | None] = mapped_column(Text)
    gst_applicable: Mapped[str | None] = mapped_column(Text)
    gst_type_of_supply: Mapped[str | None] = mapped_column(Text)
    tax_rate: Mapped[str | None] = mapped_column(Text)
    costing_method: Mapped[str | None] = mapped_column(Text)
    valuation_method: Mapped[str | None] = mapped_column(Text)
    opening_balance: Mapped[str | None] = mapped_column(Text)
    opening_rate: Mapped[str | None] = mapped_column(Text)
    opening_value: Mapped[str | None] = mapped_column(Text)
    closing_balance: Mapped[str | None] = mapped_column(Text)
    closing_value: Mapped[str | None] = mapped_column(Text)
    master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    synced_at: Mapped[str | None] = mapped_column(Text)


class Voucher(Base):
    __tablename__ = "vouchers"
    __table_args__ = (
        Index("idx_vch_company", "company_id"),
        Index("idx_vch_date", "company_id", "date"),
        Index("idx_vch_master_id", "master_id"),
        Index("idx_vch_alter_id", "alter_id"),
        Index("idx_vch_type", "company_id", "voucher_type_name"),
    )

    guid: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[str] = mapped_column(Text, nullable=False)
    voucher_type_name: Mapped[str] = mapped_column(Text, nullable=False)
    voucher_number: Mapped[str | None] = mapped_column(Text)
    narration: Mapped[str | None] = mapped_column(Text)
    reference: Mapped[str | None] = mapped_column(Text)
    party_ledger_name: Mapped[str | None] = mapped_column(Text)
    is_cancelled: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_optional: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_invoice: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    persisted_view: Mapped[str | None] = mapped_column(Text)
    effective_date: Mapped[str | None] = mapped_column(Text)
    reference_date: Mapped[str | None] = mapped_column(Text)
    place_of_supply: Mapped[str | None] = mapped_column(Text)
    party_gstin: Mapped[str | None] = mapped_column(Text)
    consignee_name: Mapped[str | None] = mapped_column(Text)
    irn: Mapped[str | None] = mapped_column(Text)
    eway_bill_no: Mapped[str | None] = mapped_column(Text)
    master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    synced_at: Mapped[str | None] = mapped_column(Text)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        Index("idx_le_voucher", "voucher_guid"),
        Index("idx_le_ledger", "ledger_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    voucher_guid: Mapped[str] = mapped_column(
        Text, ForeignKey("vouchers.guid", ondelete="CASCADE"), nullable=False
    )
    ledger_name: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[str] = mapped_column(Text, nullable=False)
    is_deemed_positive: Mapped[int | None] = mapped_column(Integer)
    bill_ref: Mapped[str | None] = mapped_column(Text)
    bill_type: Mapped[str | None] = mapped_column(Text)
    bill_due_date: Mapped[str | None] = mapped_column(Text)
    bill_credit_period: Mapped[str | None] = mapped_column(Text)
    bill_amount: Mapped[str | None] = mapped_column(Text)


class CostCentreAllocation(Base):
    __tablename__ = "cost_centre_allocations"
    __table_args__ = (
        Index("idx_cca_voucher", "voucher_guid"),
        Index("idx_cca_cc", "cost_centre_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    voucher_guid: Mapped[str] = mapped_column(
        Text, ForeignKey("vouchers.guid", ondelete="CASCADE"), nullable=False
    )
    ledger_name: Mapped[str] = mapped_column(Text, nullable=False)
    cost_category: Mapped[str | None] = mapped_column(Text)
    cost_centre_name: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[str] = mapped_column(Text, nullable=False)
    is_deemed_positive: Mapped[int | None] = mapped_column(Integer)


class InventoryEntry(Base):
    __tablename__ = "inventory_entries"
    __table_args__ = (
        Index("idx_ie_voucher", "voucher_guid"),
        Index("idx_ie_item", "stock_item_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    voucher_guid: Mapped[str] = mapped_column(
        Text, ForeignKey("vouchers.guid", ondelete="CASCADE"), nullable=False
    )
    stock_item_name: Mapped[str] = mapped_column(Text, nullable=False)
    billed_qty: Mapped[str | None] = mapped_column(Text)
    actual_qty: Mapped[str | None] = mapped_column(Text)
    rate: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[str | None] = mapped_column(Text)
    godown_name: Mapped[str | None] = mapped_column(Text)
    batch_name: Mapped[str | None] = mapped_column(Text)
    unit: Mapped[str | None] = mapped_column(Text)


class AttendanceEntry(Base):
    __tablename__ = "attendance_entries"
    __table_args__ = (
        Index("idx_ae_voucher", "voucher_guid"),
        Index("idx_ae_emp", "employee_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    voucher_guid: Mapped[str] = mapped_column(
        Text, ForeignKey("vouchers.guid", ondelete="CASCADE"), nullable=False
    )
    employee_name: Mapped[str] = mapped_column(Text, nullable=False)
    attendance_type: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[str | None] = mapped_column(Text)
    time_value: Mapped[str | None] = mapped_column(Text)
