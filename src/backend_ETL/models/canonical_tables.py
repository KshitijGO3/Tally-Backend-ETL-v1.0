"""Canonical (silver layer) domain model tables."""

from __future__ import annotations

import datetime as dt  # noqa: F401
import decimal  # noqa: F401

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend_ETL.models.base import Base


class CanonicalCompany(Base):
    __tablename__ = "canonical_companies"
    __table_args__ = (Index("idx_c_comp_name", "name"),)

    company_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    books_from: Mapped[dt.date | None] = mapped_column(Date)
    starting_from: Mapped[dt.date | None] = mapped_column(Date)
    company_number: Mapped[str | None] = mapped_column(Text)
    books_to: Mapped[dt.date | None] = mapped_column(Date)
    company_gstin: Mapped[str | None] = mapped_column(String(15))
    source_master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    source_alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    warehouse_synced_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class CanonicalAccountGroup(Base):
    __tablename__ = "canonical_account_groups"
    __table_args__ = (
        Index("idx_c_ag_company", "company_id"),
        Index("idx_c_ag_name", "company_id", "name"),
    )

    accountgroup_id: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_companies.company_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_ref: Mapped[str | None] = mapped_column(Text)
    parent_chain: Mapped[str | None] = mapped_column(Text)
    nature: Mapped[str | None] = mapped_column(String(30))
    primary_group: Mapped[str | None] = mapped_column(Text)
    is_revenue: Mapped[bool | None] = mapped_column(Boolean, server_default=text("FALSE"))
    is_deemed_positive: Mapped[bool | None] = mapped_column(Boolean, server_default=text("FALSE"))
    affects_gross_profit: Mapped[bool | None] = mapped_column(Boolean, server_default=text("FALSE"))
    source_master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    source_alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    warehouse_synced_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class CanonicalAccount(Base):
    __tablename__ = "canonical_accounts"
    __table_args__ = (
        Index("idx_c_acc_company", "company_id"),
        Index("idx_c_acc_name", "company_id", "name"),
        Index("idx_c_acc_role", "company_id", "classification_role"),
    )

    account_id: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_companies.company_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    group_ref: Mapped[str | None] = mapped_column(Text)
    aliases: Mapped[str | None] = mapped_column(Text)
    credit_limit: Mapped[decimal.Decimal | None] = mapped_column(Numeric(18, 4))
    credit_period_raw: Mapped[str | None] = mapped_column(Text)
    bill_wise: Mapped[bool | None] = mapped_column(Boolean, server_default=text("FALSE"))
    cost_centres_on: Mapped[bool | None] = mapped_column(Boolean, server_default=text("FALSE"))
    currency: Mapped[str | None] = mapped_column(Text)
    reported_closing: Mapped[decimal.Decimal | None] = mapped_column(Numeric(18, 4))
    gst_reg_type: Mapped[str | None] = mapped_column(Text)
    tax_classification: Mapped[str | None] = mapped_column(Text)
    classification_role: Mapped[str | None] = mapped_column(
        String(30), server_default=text("'other'")
    )
    source_master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    source_alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    warehouse_synced_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class CanonicalAccountContact(Base):
    __tablename__ = "canonical_account_contacts"

    account_ref: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_accounts.account_id", ondelete="CASCADE"), primary_key=True
    )
    contact_mailing_name: Mapped[str | None] = mapped_column(Text)
    contact_address: Mapped[str | None] = mapped_column(Text)
    contact_state_name: Mapped[str | None] = mapped_column(Text)
    contact_country_name: Mapped[str | None] = mapped_column(Text)
    contact_pincode: Mapped[str | None] = mapped_column(String(20))
    contact_email: Mapped[str | None] = mapped_column(Text)
    contact_phone: Mapped[str | None] = mapped_column(Text)
    contact_mobile: Mapped[str | None] = mapped_column(Text)
    party_pan: Mapped[str | None] = mapped_column(String(30))


class CanonicalPartyIdentifier(Base):
    __tablename__ = "canonical_party_identifiers"
    __table_args__ = (
        UniqueConstraint("party_ref", "id_type", "value"),
        Index("idx_c_pi_party", "party_ref"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    party_ref: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_accounts.account_id", ondelete="CASCADE"), nullable=False
    )
    id_type: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str | None] = mapped_column(String(30), server_default=text("'OBSERVED'"))
    source: Mapped[str | None] = mapped_column(Text)


class CanonicalVoucherType(Base):
    __tablename__ = "canonical_voucher_types"
    __table_args__ = (Index("idx_c_vt_company", "company_id"),)

    vouchertype_id: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_companies.company_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_kind: Mapped[str | None] = mapped_column(Text)
    base_type: Mapped[str | None] = mapped_column(String(50))
    numbering_method: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool | None] = mapped_column(Boolean, server_default=text("TRUE"))
    affects_stock: Mapped[bool | None] = mapped_column(Boolean, server_default=text("FALSE"))
    prevent_duplicates: Mapped[bool | None] = mapped_column(Boolean, server_default=text("FALSE"))
    source_master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    source_alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    warehouse_synced_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class CanonicalStockGroup(Base):
    __tablename__ = "canonical_stock_groups"
    __table_args__ = (Index("idx_c_sg_company", "company_id"),)

    stockgroup_id: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_companies.company_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_ref: Mapped[str | None] = mapped_column(Text)
    source_master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    source_alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    warehouse_synced_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class CanonicalStockCategory(Base):
    __tablename__ = "canonical_stock_categories"
    __table_args__ = (Index("idx_c_sc_company", "company_id"),)

    stockcategory_id: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_companies.company_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_ref: Mapped[str | None] = mapped_column(Text)
    source_master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    source_alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    warehouse_synced_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class CanonicalStockItem(Base):
    __tablename__ = "canonical_stock_items"
    __table_args__ = (
        Index("idx_c_si_company", "company_id"),
        Index("idx_c_si_name", "company_id", "name"),
    )

    stockitem_id: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_companies.company_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_ref: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    base_units: Mapped[str | None] = mapped_column(Text)
    alternate_units: Mapped[str | None] = mapped_column(Text)
    hsn_code: Mapped[str | None] = mapped_column(Text)
    gst_applicable: Mapped[str | None] = mapped_column(Text)
    gst_type_of_supply: Mapped[str | None] = mapped_column(Text)
    tax_rate: Mapped[decimal.Decimal | None] = mapped_column(Numeric(8, 4))
    costing_method: Mapped[str | None] = mapped_column(Text)
    valuation_method: Mapped[str | None] = mapped_column(Text)
    opening_qty: Mapped[decimal.Decimal | None] = mapped_column(Numeric(18, 4))
    opening_rate: Mapped[decimal.Decimal | None] = mapped_column(Numeric(18, 4))
    opening_value: Mapped[decimal.Decimal | None] = mapped_column(Numeric(18, 4))
    closing_qty: Mapped[decimal.Decimal | None] = mapped_column(Numeric(18, 4))
    closing_value: Mapped[decimal.Decimal | None] = mapped_column(Numeric(18, 4))
    source_master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    source_alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    warehouse_synced_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class CanonicalGodown(Base):
    __tablename__ = "canonical_godowns"
    __table_args__ = (Index("idx_c_godown_company", "company_id"),)

    godown_id: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_companies.company_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_ref: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    has_no_space: Mapped[bool | None] = mapped_column(Boolean, server_default=text("FALSE"))
    has_no_stock: Mapped[bool | None] = mapped_column(Boolean, server_default=text("FALSE"))
    source_master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    source_alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    warehouse_synced_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class CanonicalUnit(Base):
    __tablename__ = "canonical_units"
    __table_args__ = (Index("idx_c_unit_company", "company_id"),)

    unit_id: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_companies.company_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    original_name: Mapped[str | None] = mapped_column(Text)
    base_units: Mapped[str | None] = mapped_column(Text)
    is_simple_unit: Mapped[bool | None] = mapped_column(Boolean, server_default=text("TRUE"))
    decimal_places: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    conversion: Mapped[decimal.Decimal | None] = mapped_column(Numeric(18, 6))
    source_master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    source_alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    warehouse_synced_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class CanonicalCostCategory(Base):
    __tablename__ = "canonical_cost_categories"
    __table_args__ = (Index("idx_c_ccat_company", "company_id"),)

    costcategory_id: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_companies.company_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    allocate_revenue: Mapped[bool | None] = mapped_column(Boolean, server_default=text("TRUE"))
    allocate_non_revenue: Mapped[bool | None] = mapped_column(Boolean, server_default=text("FALSE"))
    source_master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    source_alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    warehouse_synced_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class CanonicalCostCentre(Base):
    __tablename__ = "canonical_cost_centres"
    __table_args__ = (Index("idx_c_cc_company", "company_id"),)

    costcentre_id: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_companies.company_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_ref: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    revenue_le_for_op_bal: Mapped[bool | None] = mapped_column(
        Boolean, server_default=text("FALSE")
    )
    email_id: Mapped[str | None] = mapped_column(Text)
    source_master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    source_alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    warehouse_synced_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class CanonicalCurrency(Base):
    __tablename__ = "canonical_currencies"
    __table_args__ = (Index("idx_c_curr_company", "company_id"),)

    currency_id: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_companies.company_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    mailing_name: Mapped[str | None] = mapped_column(Text)
    original_name: Mapped[str | None] = mapped_column(Text)
    expanded_symbol: Mapped[str | None] = mapped_column(Text)
    decimal_symbol: Mapped[str | None] = mapped_column(String(10))
    decimal_places: Mapped[int | None] = mapped_column(Integer, server_default=text("2"))
    source_master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    source_alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    warehouse_synced_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class CanonicalEmployeeGroup(Base):
    __tablename__ = "canonical_employee_groups"

    employeegroup_id: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_companies.company_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_ref: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    source_master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    source_alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    warehouse_synced_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class CanonicalEmployee(Base):
    __tablename__ = "canonical_employees"
    __table_args__ = (Index("idx_c_emp_company", "company_id"),)

    employee_id: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_companies.company_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_ref: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    date_of_joining: Mapped[dt.date | None] = mapped_column(Date)
    deactivation_date: Mapped[dt.date | None] = mapped_column(Date)
    designation: Mapped[str | None] = mapped_column(Text)
    function_role: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    gender: Mapped[str | None] = mapped_column(String(20))
    blood_group: Mapped[str | None] = mapped_column(String(10))
    pan_number: Mapped[str | None] = mapped_column(String(10))
    aadhar_number: Mapped[str | None] = mapped_column(String(20))
    pf_number: Mapped[str | None] = mapped_column(Text)
    uan: Mapped[str | None] = mapped_column(String(20))
    esi_number: Mapped[str | None] = mapped_column(Text)
    bank_name: Mapped[str | None] = mapped_column(Text)
    bank_account_number: Mapped[str | None] = mapped_column(Text)
    ifsc_code: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(Text)
    mobile: Mapped[str | None] = mapped_column(Text)
    source_master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    source_alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    warehouse_synced_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class CanonicalAttendanceType(Base):
    __tablename__ = "canonical_attendance_types"

    attendancetype_id: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_companies.company_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    parent_ref: Mapped[str | None] = mapped_column(Text)
    attendance_production_type: Mapped[str | None] = mapped_column(Text)
    attendance_period: Mapped[str | None] = mapped_column(Text)
    base_units: Mapped[str | None] = mapped_column(Text)
    source_master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    source_alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    warehouse_synced_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class CanonicalVoucher(Base):
    __tablename__ = "canonical_vouchers"
    __table_args__ = (
        CheckConstraint(
            "lifecycle IN ('active', 'cancelled')", name="canonical_vouchers_lifecycle_check"
        ),
        Index("idx_c_vch_company", "company_id"),
        Index("idx_c_vch_date", "company_id", "date"),
        Index("idx_c_vch_party", "company_id", "party_ref"),
        Index("idx_c_vch_alter", "company_id", "source_alter_id"),
        Index("idx_c_vch_base_type", "company_id", "base_type"),
    )

    voucher_id: Mapped[str] = mapped_column(Text, primary_key=True)
    company_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_companies.company_id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    base_type: Mapped[str | None] = mapped_column(String(50))
    number: Mapped[str | None] = mapped_column(Text)
    narration: Mapped[str | None] = mapped_column(Text)
    reference: Mapped[str | None] = mapped_column(Text)
    party_ref: Mapped[str | None] = mapped_column(Text)
    lifecycle: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'active'")
    )
    is_optional: Mapped[bool | None] = mapped_column(Boolean, server_default=text("FALSE"))
    is_invoice: Mapped[bool | None] = mapped_column(Boolean, server_default=text("FALSE"))
    persisted_view: Mapped[str | None] = mapped_column(Text)
    effective_date: Mapped[dt.date | None] = mapped_column(Date)
    reference_date: Mapped[dt.date | None] = mapped_column(Date)
    place_of_supply: Mapped[str | None] = mapped_column(Text)
    party_gstin_doc: Mapped[str | None] = mapped_column(String(15))
    ship_to: Mapped[str | None] = mapped_column(Text)
    irn: Mapped[str | None] = mapped_column(Text)
    eway_bill_no: Mapped[str | None] = mapped_column(Text)
    source_master_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    source_alter_id: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    warehouse_synced_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class CanonicalPosting(Base):
    __tablename__ = "canonical_postings"
    __table_args__ = (
        UniqueConstraint("voucher_ref", "line_ordinal"),
        Index("idx_c_post_voucher", "voucher_ref"),
        Index("idx_c_post_account", "account_ref"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    voucher_ref: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_vouchers.voucher_id", ondelete="CASCADE"), nullable=False
    )
    line_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    account_ref: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    source_deemed_positive: Mapped[bool | None] = mapped_column(
        Boolean, server_default=text("FALSE")
    )


class CanonicalBillEvent(Base):
    __tablename__ = "canonical_bill_events"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('new', 'agst', 'on_account', 'advance', 'unspecified')",
            name="canonical_bill_events_kind_check",
        ),
        Index("idx_c_be_voucher", "voucher_ref"),
        Index("idx_c_be_party", "company_id", "party_ref"),
        Index("idx_c_be_bill", "company_id", "bill_ref"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    voucher_ref: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_vouchers.voucher_id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_companies.company_id", ondelete="CASCADE"), nullable=False
    )
    party_ref: Mapped[str] = mapped_column(Text, nullable=False)
    bill_ref: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    due_date: Mapped[dt.date | None] = mapped_column(Date)
    credit_period_raw: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 4), nullable=False)


class CanonicalInventoryLine(Base):
    __tablename__ = "canonical_inventory_lines"
    __table_args__ = (
        Index("idx_c_il_voucher", "voucher_guid"),
        Index("idx_c_il_item", "item_ref"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    voucher_guid: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_vouchers.voucher_id", ondelete="CASCADE"), nullable=False
    )
    item_ref: Mapped[str] = mapped_column(Text, nullable=False)
    billed_qty: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    actual_qty: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    rate: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    amount: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    godown_ref: Mapped[str | None] = mapped_column(Text)
    batch_ref: Mapped[str | None] = mapped_column(Text)
    unit_ref: Mapped[str | None] = mapped_column(Text)


class CanonicalCostAllocation(Base):
    __tablename__ = "canonical_cost_allocations"
    __table_args__ = (Index("idx_c_ca_voucher", "voucher_ref"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    voucher_ref: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_vouchers.voucher_id", ondelete="CASCADE"), nullable=False
    )
    line_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    account_ref: Mapped[str] = mapped_column(Text, nullable=False)
    cost_category_ref: Mapped[str | None] = mapped_column(Text)
    cost_centre_ref: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    source_deemed_positive: Mapped[bool | None] = mapped_column(
        Boolean, server_default=text("FALSE")
    )


class CanonicalAttendanceEntry(Base):
    __tablename__ = "canonical_attendance_entries"
    __table_args__ = (Index("idx_c_ae_voucher", "voucher_guid"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    voucher_guid: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_vouchers.voucher_id", ondelete="CASCADE"), nullable=False
    )
    employee_name: Mapped[str] = mapped_column(Text, nullable=False)
    attendance_type: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[decimal.Decimal | None] = mapped_column(Numeric(18, 4))
    time_value: Mapped[decimal.Decimal | None] = mapped_column(Numeric(18, 4))


class CanonicalOpeningBalance(Base):
    __tablename__ = "canonical_opening_balances"
    __table_args__ = (Index("idx_c_ob_company", "company_id"),)

    account_ref: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_accounts.account_id", ondelete="CASCADE"), primary_key=True
    )
    company_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_companies.company_id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[decimal.Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    as_of: Mapped[dt.date | None] = mapped_column(Date)


class CanonicalSyncCursor(Base):
    __tablename__ = "canonical_sync_cursors"

    company_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_companies.company_id", ondelete="CASCADE"), primary_key=True
    )
    entity: Mapped[str] = mapped_column(Text, primary_key=True)
    cursor_value: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_time: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )


class CanonicalReconciliationIssue(Base):
    __tablename__ = "canonical_reconciliation_issues"
    __table_args__ = (Index("idx_c_recon_company", "company_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    company_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_companies.company_id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_name: Mapped[str] = mapped_column(Text, nullable=False)
    tally_value: Mapped[decimal.Decimal | None] = mapped_column(Numeric(18, 4))
    warehouse_value: Mapped[decimal.Decimal | None] = mapped_column(Numeric(18, 4))
    variance: Mapped[decimal.Decimal | None] = mapped_column(Numeric(18, 4))
    detected_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
    resolved: Mapped[bool | None] = mapped_column(Boolean, server_default=text("FALSE"))


class CanonicalDailyMovement(Base):
    __tablename__ = "canonical_daily_movements"
    __table_args__ = (
        Index("idx_c_dm_comp_date", "company_id", "date"),
        Index("idx_c_dm_comp_base", "company_id", "base_type"),
    )

    company_id: Mapped[str] = mapped_column(
        Text, ForeignKey("canonical_companies.company_id", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    base_type: Mapped[str] = mapped_column(String(50), primary_key=True)
    account_role: Mapped[str] = mapped_column(String(50), primary_key=True)
    is_debit: Mapped[bool] = mapped_column(Boolean, primary_key=True)
    total_amount: Mapped[decimal.Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, server_default=text("0")
    )
    voucher_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    updated_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()")
    )
