"""PostgreSQL DDL and declarative table metadata for the 20 core Tally tables."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TableSpec:
    """Column specification for a core table."""

    name: str
    columns: tuple[str, ...]
    bool_columns: frozenset[str] = frozenset()
    int_columns: frozenset[str] = frozenset()
    str_columns: frozenset[str] = frozenset()


PG_DDL_STATEMENTS: list[str] = [
    # ─── Security, Clients & Multi-Tenant Mapping ────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS clients (
        client_id       TEXT    PRIMARY KEY,
        client_name     TEXT    NOT NULL,
        contact_email   TEXT,
        is_active       INTEGER NOT NULL DEFAULT 1,
        created_at      TEXT    NOT NULL,
        updated_at      TEXT    NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS api_tokens (
        token_id        BIGSERIAL PRIMARY KEY,
        client_id       TEXT      UNIQUE,
        token_hash      TEXT      NOT NULL UNIQUE,
        token_prefix    TEXT      NOT NULL,
        description     TEXT,
        is_active       INTEGER   NOT NULL DEFAULT 1,
        created_at      TEXT      NOT NULL,
        last_used_at    TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_api_tokens_hash ON api_tokens(token_hash);",
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id         TEXT    PRIMARY KEY,
        client_id       TEXT    NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
        email           TEXT    NOT NULL UNIQUE,
        password_hash   TEXT    NOT NULL,
        full_name       TEXT    NOT NULL,
        role            TEXT    NOT NULL DEFAULT 'viewer',
        is_active       INTEGER NOT NULL DEFAULT 1,
        created_at      TEXT    NOT NULL,
        updated_at      TEXT    NOT NULL,
        last_login_at   TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);",
    "CREATE INDEX IF NOT EXISTS idx_users_client ON users(client_id);",
    # ─── Company & Structural Masters ────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS companies (
        guid                TEXT    PRIMARY KEY,
        name                TEXT    NOT NULL UNIQUE,
        books_from          TEXT,
        starting_from       TEXT,
        company_number      TEXT,
        ending_at           TEXT,
        gstin               TEXT,
        master_id           INTEGER NOT NULL DEFAULT 0,
        alter_id            INTEGER NOT NULL DEFAULT 0,
        synced_at           TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_comp_alter_id ON companies(alter_id);",
    """
    CREATE TABLE IF NOT EXISTS client_companies (
        id              BIGSERIAL PRIMARY KEY,
        client_id       TEXT      NOT NULL REFERENCES clients(client_id) ON DELETE CASCADE,
        company_guid    TEXT      NOT NULL REFERENCES companies(guid) ON DELETE CASCADE,
        created_at      TEXT      NOT NULL,
        UNIQUE (client_id, company_guid)
    );
    """,
    (
        "CREATE INDEX IF NOT EXISTS idx_client_comp_lookup "
        "ON client_companies(client_id, company_guid);"
    ),
    "CREATE INDEX IF NOT EXISTS idx_client_comp_guid ON client_companies(company_guid);",
    """
    CREATE TABLE IF NOT EXISTS currencies (
        guid                TEXT    PRIMARY KEY,
        company_id          TEXT    NOT NULL,
        name                TEXT    NOT NULL,
        mailing_name        TEXT,
        original_name       TEXT,
        expanded_symbol     TEXT,
        decimal_symbol      TEXT,
        decimal_places      INTEGER NOT NULL DEFAULT 2,
        master_id           INTEGER NOT NULL DEFAULT 0,
        alter_id            INTEGER NOT NULL DEFAULT 0,
        synced_at           TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_curr_company ON currencies(company_id);",
    "CREATE INDEX IF NOT EXISTS idx_curr_alter_id ON currencies(alter_id);",
    """
    CREATE TABLE IF NOT EXISTS groups (
        guid                 TEXT    PRIMARY KEY,
        company_id           TEXT    NOT NULL,
        name                 TEXT    NOT NULL,
        parent               TEXT,
        nature               TEXT,
        primary_group        TEXT,
        is_revenue           INTEGER,
        is_deemed_positive   INTEGER,
        affects_gross_profit INTEGER,
        master_id            INTEGER NOT NULL DEFAULT 0,
        alter_id             INTEGER NOT NULL DEFAULT 0,
        synced_at            TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_group_company ON groups(company_id);",
    "CREATE INDEX IF NOT EXISTS idx_group_master_id ON groups(master_id);",
    "CREATE INDEX IF NOT EXISTS idx_group_alter_id ON groups(alter_id);",
    """
    CREATE TABLE IF NOT EXISTS cost_categories (
        guid                 TEXT    PRIMARY KEY,
        company_id           TEXT    NOT NULL,
        name                 TEXT    NOT NULL,
        allocate_revenue     INTEGER,
        allocate_non_revenue INTEGER,
        master_id            INTEGER NOT NULL DEFAULT 0,
        alter_id             INTEGER NOT NULL DEFAULT 0,
        synced_at            TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_ccat_company ON cost_categories(company_id);",
    "CREATE INDEX IF NOT EXISTS idx_ccat_alter_id ON cost_categories(alter_id);",
    """
    CREATE TABLE IF NOT EXISTS cost_centres (
        guid                  TEXT    PRIMARY KEY,
        company_id            TEXT    NOT NULL,
        name                  TEXT    NOT NULL,
        parent                TEXT,
        category              TEXT,
        revenue_le_for_op_bal INTEGER,
        email_id              TEXT,
        master_id             INTEGER NOT NULL DEFAULT 0,
        alter_id              INTEGER NOT NULL DEFAULT 0,
        synced_at             TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_cc_company ON cost_centres(company_id);",
    "CREATE INDEX IF NOT EXISTS idx_cc_alter_id ON cost_centres(alter_id);",
    """
    CREATE TABLE IF NOT EXISTS employee_groups (
        guid                TEXT    PRIMARY KEY,
        company_id          TEXT    NOT NULL,
        name                TEXT    NOT NULL,
        parent              TEXT,
        category            TEXT,
        master_id           INTEGER NOT NULL DEFAULT 0,
        alter_id            INTEGER NOT NULL DEFAULT 0,
        synced_at           TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_empg_company ON employee_groups(company_id);",
    "CREATE INDEX IF NOT EXISTS idx_empg_alter_id ON employee_groups(alter_id);",
    """
    CREATE TABLE IF NOT EXISTS employees (
        guid                TEXT    PRIMARY KEY,
        company_id          TEXT    NOT NULL,
        name                TEXT    NOT NULL,
        parent              TEXT,
        category            TEXT,
        employee_id         TEXT,
        date_of_joining     TEXT,
        deactivation_date   TEXT,
        designation         TEXT,
        function_role       TEXT,
        location            TEXT,
        gender              TEXT,
        blood_group         TEXT,
        pan_number          TEXT,
        aadhar_number       TEXT,
        pf_number           TEXT,
        uan                 TEXT,
        esi_number          TEXT,
        bank_name           TEXT,
        bank_account_number TEXT,
        ifsc_code           TEXT,
        email               TEXT,
        mobile              TEXT,
        master_id           INTEGER NOT NULL DEFAULT 0,
        alter_id            INTEGER NOT NULL DEFAULT 0,
        synced_at           TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_emp_company ON employees(company_id);",
    "CREATE INDEX IF NOT EXISTS idx_emp_alter_id ON employees(alter_id);",
    """
    CREATE TABLE IF NOT EXISTS attendance_types (
        guid                       TEXT    PRIMARY KEY,
        company_id                 TEXT    NOT NULL,
        name                       TEXT    NOT NULL,
        parent                     TEXT,
        attendance_production_type TEXT,
        attendance_period          TEXT,
        base_units                 TEXT,
        master_id                  INTEGER NOT NULL DEFAULT 0,
        alter_id                   INTEGER NOT NULL DEFAULT 0,
        synced_at                  TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_at_company ON attendance_types(company_id);",
    "CREATE INDEX IF NOT EXISTS idx_at_alter_id ON attendance_types(alter_id);",
    """
    CREATE TABLE IF NOT EXISTS stock_categories (
        guid                TEXT    PRIMARY KEY,
        company_id          TEXT    NOT NULL,
        name                TEXT    NOT NULL,
        parent              TEXT,
        master_id           INTEGER NOT NULL DEFAULT 0,
        alter_id            INTEGER NOT NULL DEFAULT 0,
        synced_at           TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_scat_company ON stock_categories(company_id);",
    "CREATE INDEX IF NOT EXISTS idx_scat_alter_id ON stock_categories(alter_id);",
    """
    CREATE TABLE IF NOT EXISTS stock_groups (
        guid                TEXT    PRIMARY KEY,
        company_id          TEXT    NOT NULL,
        name                TEXT    NOT NULL,
        parent              TEXT,
        master_id           INTEGER NOT NULL DEFAULT 0,
        alter_id            INTEGER NOT NULL DEFAULT 0,
        synced_at           TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_sg_company ON stock_groups(company_id);",
    "CREATE INDEX IF NOT EXISTS idx_sg_master_id ON stock_groups(master_id);",
    "CREATE INDEX IF NOT EXISTS idx_sg_alter_id ON stock_groups(alter_id);",
    """
    CREATE TABLE IF NOT EXISTS units (
        guid                TEXT    PRIMARY KEY,
        company_id          TEXT    NOT NULL,
        name                TEXT    NOT NULL,
        original_name       TEXT,
        base_units          TEXT,
        is_simple_unit      INTEGER,
        decimal_places      INTEGER,
        conversion          TEXT,
        master_id           INTEGER NOT NULL DEFAULT 0,
        alter_id            INTEGER NOT NULL DEFAULT 0,
        synced_at           TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_unit_master_id ON units(master_id);",
    "CREATE INDEX IF NOT EXISTS idx_unit_alter_id ON units(alter_id);",
    """
    CREATE TABLE IF NOT EXISTS godowns (
        guid                TEXT    PRIMARY KEY,
        company_id          TEXT    NOT NULL,
        name                TEXT    NOT NULL,
        parent              TEXT,
        address             TEXT,
        has_no_space        INTEGER,
        has_no_stock        INTEGER,
        master_id           INTEGER NOT NULL DEFAULT 0,
        alter_id            INTEGER NOT NULL DEFAULT 0,
        synced_at           TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_godown_master_id ON godowns(master_id);",
    "CREATE INDEX IF NOT EXISTS idx_godown_alter_id ON godowns(alter_id);",
    """
    CREATE TABLE IF NOT EXISTS voucher_types (
        guid                TEXT    PRIMARY KEY,
        company_id          TEXT    NOT NULL,
        name                TEXT    NOT NULL,
        parent              TEXT,
        numbering_method    TEXT,
        is_active           INTEGER,
        affects_stock       INTEGER,
        prevent_duplicates  INTEGER,
        master_id           INTEGER NOT NULL DEFAULT 0,
        alter_id            INTEGER NOT NULL DEFAULT 0,
        synced_at           TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_vt_company ON voucher_types(company_id);",
    "CREATE INDEX IF NOT EXISTS idx_vt_name ON voucher_types(company_id, name);",
    "CREATE INDEX IF NOT EXISTS idx_vt_alter_id ON voucher_types(alter_id);",
    "CREATE OR REPLACE VIEW VoucherType AS SELECT * FROM voucher_types;",
    """
    CREATE TABLE IF NOT EXISTS ledgers (
        guid                  TEXT    PRIMARY KEY,
        company_id            TEXT    NOT NULL,
        name                  TEXT    NOT NULL,
        parent                TEXT,
        alias                 TEXT,
        mailing_name          TEXT,
        address               TEXT,
        state_name            TEXT,
        country_name          TEXT,
        pincode               TEXT,
        pan_number            TEXT,
        gstin                 TEXT,
        email                 TEXT,
        phone                 TEXT,
        mobile                TEXT,
        credit_limit          TEXT,
        credit_period         TEXT,
        is_bill_wise_on       INTEGER,
        is_cost_centres_on    INTEGER,
        currency_name         TEXT,
        opening_balance       TEXT,
        closing_balance       TEXT,
        gst_registration_type TEXT,
        tax_classification    TEXT,
        master_id             INTEGER NOT NULL DEFAULT 0,
        alter_id              INTEGER NOT NULL DEFAULT 0,
        synced_at             TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_ledger_company ON ledgers(company_id);",
    "CREATE INDEX IF NOT EXISTS idx_ledger_master_id ON ledgers(master_id);",
    "CREATE INDEX IF NOT EXISTS idx_ledger_alter_id ON ledgers(alter_id);",
    """
    CREATE TABLE IF NOT EXISTS stock_items (
        guid                TEXT    PRIMARY KEY,
        company_id          TEXT    NOT NULL,
        name                TEXT    NOT NULL,
        parent              TEXT,
        category            TEXT,
        base_units          TEXT,
        alternate_units     TEXT,
        hsn_code            TEXT,
        gst_applicable      TEXT,
        gst_type_of_supply  TEXT,
        tax_rate            TEXT,
        costing_method      TEXT,
        valuation_method    TEXT,
        opening_balance     TEXT,
        opening_rate        TEXT,
        opening_value       TEXT,
        closing_balance     TEXT,
        closing_value       TEXT,
        master_id           INTEGER NOT NULL DEFAULT 0,
        alter_id            INTEGER NOT NULL DEFAULT 0,
        synced_at           TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_si_company ON stock_items(company_id);",
    "CREATE INDEX IF NOT EXISTS idx_si_master_id ON stock_items(master_id);",
    "CREATE INDEX IF NOT EXISTS idx_si_alter_id ON stock_items(alter_id);",
    # ─── Transaction Fact Tables ─────────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS vouchers (
        guid                TEXT    PRIMARY KEY,
        company_id          TEXT    NOT NULL,
        date                TEXT    NOT NULL,
        voucher_type_name   TEXT    NOT NULL,
        voucher_number      TEXT,
        narration           TEXT,
        reference           TEXT,
        party_ledger_name   TEXT,
        is_cancelled        INTEGER NOT NULL DEFAULT 0,
        is_optional         INTEGER NOT NULL DEFAULT 0,
        is_invoice          INTEGER NOT NULL DEFAULT 0,
        persisted_view      TEXT,
        effective_date      TEXT,
        reference_date      TEXT,
        place_of_supply     TEXT,
        party_gstin         TEXT,
        consignee_name      TEXT,
        irn                 TEXT,
        eway_bill_no        TEXT,
        master_id           INTEGER NOT NULL DEFAULT 0,
        alter_id            INTEGER NOT NULL DEFAULT 0,
        synced_at           TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_vch_company ON vouchers(company_id);",
    "CREATE INDEX IF NOT EXISTS idx_vch_date ON vouchers(company_id, date);",
    "CREATE INDEX IF NOT EXISTS idx_vch_master_id ON vouchers(master_id);",
    "CREATE INDEX IF NOT EXISTS idx_vch_alter_id ON vouchers(alter_id);",
    "CREATE INDEX IF NOT EXISTS idx_vch_type ON vouchers(company_id, voucher_type_name);",
    """
    CREATE TABLE IF NOT EXISTS ledger_entries (
        id                  BIGSERIAL PRIMARY KEY,
        voucher_guid        TEXT      NOT NULL REFERENCES vouchers(guid) ON DELETE CASCADE,
        ledger_name         TEXT      NOT NULL,
        amount              TEXT      NOT NULL,
        is_deemed_positive  INTEGER,
        bill_ref            TEXT,
        bill_type           TEXT,
        bill_due_date       TEXT,
        bill_credit_period  TEXT,
        bill_amount         TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_le_voucher ON ledger_entries(voucher_guid);",
    "CREATE INDEX IF NOT EXISTS idx_le_ledger ON ledger_entries(ledger_name);",
    """
    CREATE TABLE IF NOT EXISTS cost_centre_allocations (
        id                  BIGSERIAL PRIMARY KEY,
        voucher_guid        TEXT      NOT NULL REFERENCES vouchers(guid) ON DELETE CASCADE,
        ledger_name         TEXT      NOT NULL,
        cost_category       TEXT,
        cost_centre_name    TEXT      NOT NULL,
        amount              TEXT      NOT NULL,
        is_deemed_positive  INTEGER
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_cca_voucher ON cost_centre_allocations(voucher_guid);",
    "CREATE INDEX IF NOT EXISTS idx_cca_cc ON cost_centre_allocations(cost_centre_name);",
    """
    CREATE TABLE IF NOT EXISTS inventory_entries (
        id                  BIGSERIAL PRIMARY KEY,
        voucher_guid        TEXT      NOT NULL REFERENCES vouchers(guid) ON DELETE CASCADE,
        stock_item_name     TEXT      NOT NULL,
        billed_qty          TEXT,
        actual_qty          TEXT,
        rate                TEXT,
        amount              TEXT,
        godown_name         TEXT,
        batch_name          TEXT,
        unit                TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_ie_voucher ON inventory_entries(voucher_guid);",
    "CREATE INDEX IF NOT EXISTS idx_ie_item ON inventory_entries(stock_item_name);",
    """
    CREATE TABLE IF NOT EXISTS attendance_entries (
        id                  BIGSERIAL PRIMARY KEY,
        voucher_guid        TEXT      NOT NULL REFERENCES vouchers(guid) ON DELETE CASCADE,
        employee_name       TEXT      NOT NULL,
        attendance_type     TEXT      NOT NULL,
        value               TEXT,
        time_value          TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_ae_voucher ON attendance_entries(voucher_guid);",
    "CREATE INDEX IF NOT EXISTS idx_ae_emp ON attendance_entries(employee_name);",
    """
    CREATE TABLE IF NOT EXISTS user_companies (
        id              BIGSERIAL PRIMARY KEY,
        user_id         TEXT      NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        company_guid    TEXT      NOT NULL REFERENCES companies(guid) ON DELETE CASCADE,
        created_at      TEXT      NOT NULL,
        UNIQUE (user_id, company_guid)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_user_companies_lookup ON user_companies(user_id, company_guid);",
    """
    CREATE TABLE IF NOT EXISTS chat_messages (
        id              BIGSERIAL PRIMARY KEY,
        user_id         TEXT      NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
        company_id      TEXT      NOT NULL REFERENCES companies(guid) ON DELETE CASCADE,
        role            TEXT      NOT NULL,
        content         TEXT      NOT NULL,
        tool_called     TEXT,
        created_at      TEXT      NOT NULL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_chat_messages_lookup ON chat_messages(user_id, company_id, created_at);",
]


COMPANY_SPEC = TableSpec(
    name="companies",
    columns=(
        "guid",
        "name",
        "books_from",
        "starting_from",
        "company_number",
        "ending_at",
        "gstin",
        "master_id",
        "alter_id",
        "synced_at",
    ),
    int_columns=frozenset({"master_id", "alter_id"}),
    str_columns=frozenset({"books_from", "starting_from", "ending_at"}),
)


MASTER_TABLE_SPECS: dict[str, TableSpec] = {
    "currencies": TableSpec(
        name="currencies",
        columns=(
            "guid",
            "company_id",
            "name",
            "mailing_name",
            "original_name",
            "expanded_symbol",
            "decimal_symbol",
            "decimal_places",
            "master_id",
            "alter_id",
            "synced_at",
        ),
        int_columns=frozenset({"decimal_places", "master_id", "alter_id"}),
    ),
    "groups": TableSpec(
        name="groups",
        columns=(
            "guid",
            "company_id",
            "name",
            "parent",
            "nature",
            "primary_group",
            "is_revenue",
            "is_deemed_positive",
            "affects_gross_profit",
            "master_id",
            "alter_id",
            "synced_at",
        ),
        bool_columns=frozenset({"is_revenue", "is_deemed_positive", "affects_gross_profit"}),
        int_columns=frozenset({"master_id", "alter_id"}),
    ),
    "cost_categories": TableSpec(
        name="cost_categories",
        columns=(
            "guid",
            "company_id",
            "name",
            "allocate_revenue",
            "allocate_non_revenue",
            "master_id",
            "alter_id",
            "synced_at",
        ),
        bool_columns=frozenset({"allocate_revenue", "allocate_non_revenue"}),
        int_columns=frozenset({"master_id", "alter_id"}),
    ),
    "cost_centres": TableSpec(
        name="cost_centres",
        columns=(
            "guid",
            "company_id",
            "name",
            "parent",
            "category",
            "revenue_le_for_op_bal",
            "email_id",
            "master_id",
            "alter_id",
            "synced_at",
        ),
        bool_columns=frozenset({"revenue_le_for_op_bal"}),
        int_columns=frozenset({"master_id", "alter_id"}),
    ),
    "employee_groups": TableSpec(
        name="employee_groups",
        columns=(
            "guid",
            "company_id",
            "name",
            "parent",
            "category",
            "master_id",
            "alter_id",
            "synced_at",
        ),
        int_columns=frozenset({"master_id", "alter_id"}),
    ),
    "employees": TableSpec(
        name="employees",
        columns=(
            "guid",
            "company_id",
            "name",
            "parent",
            "category",
            "employee_id",
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
            "master_id",
            "alter_id",
            "synced_at",
        ),
        int_columns=frozenset({"master_id", "alter_id"}),
        str_columns=frozenset({"date_of_joining", "deactivation_date"}),
    ),
    "attendance_types": TableSpec(
        name="attendance_types",
        columns=(
            "guid",
            "company_id",
            "name",
            "parent",
            "attendance_production_type",
            "attendance_period",
            "base_units",
            "master_id",
            "alter_id",
            "synced_at",
        ),
        int_columns=frozenset({"master_id", "alter_id"}),
    ),
    "stock_categories": TableSpec(
        name="stock_categories",
        columns=(
            "guid",
            "company_id",
            "name",
            "parent",
            "master_id",
            "alter_id",
            "synced_at",
        ),
        int_columns=frozenset({"master_id", "alter_id"}),
    ),
    "stock_groups": TableSpec(
        name="stock_groups",
        columns=(
            "guid",
            "company_id",
            "name",
            "parent",
            "master_id",
            "alter_id",
            "synced_at",
        ),
        int_columns=frozenset({"master_id", "alter_id"}),
    ),
    "units": TableSpec(
        name="units",
        columns=(
            "guid",
            "company_id",
            "name",
            "original_name",
            "base_units",
            "is_simple_unit",
            "decimal_places",
            "conversion",
            "master_id",
            "alter_id",
            "synced_at",
        ),
        bool_columns=frozenset({"is_simple_unit"}),
        int_columns=frozenset({"decimal_places", "master_id", "alter_id"}),
        str_columns=frozenset({"conversion"}),
    ),
    "godowns": TableSpec(
        name="godowns",
        columns=(
            "guid",
            "company_id",
            "name",
            "parent",
            "address",
            "has_no_space",
            "has_no_stock",
            "master_id",
            "alter_id",
            "synced_at",
        ),
        bool_columns=frozenset({"has_no_space", "has_no_stock"}),
        int_columns=frozenset({"master_id", "alter_id"}),
    ),
    "voucher_types": TableSpec(
        name="voucher_types",
        columns=(
            "guid",
            "company_id",
            "name",
            "parent",
            "numbering_method",
            "is_active",
            "affects_stock",
            "prevent_duplicates",
            "master_id",
            "alter_id",
            "synced_at",
        ),
        bool_columns=frozenset({"is_active", "affects_stock", "prevent_duplicates"}),
        int_columns=frozenset({"master_id", "alter_id"}),
    ),
    "ledgers": TableSpec(
        name="ledgers",
        columns=(
            "guid",
            "company_id",
            "name",
            "parent",
            "alias",
            "mailing_name",
            "address",
            "state_name",
            "country_name",
            "pincode",
            "pan_number",
            "gstin",
            "email",
            "phone",
            "mobile",
            "credit_limit",
            "credit_period",
            "is_bill_wise_on",
            "is_cost_centres_on",
            "currency_name",
            "opening_balance",
            "closing_balance",
            "gst_registration_type",
            "tax_classification",
            "master_id",
            "alter_id",
            "synced_at",
        ),
        bool_columns=frozenset({"is_bill_wise_on", "is_cost_centres_on"}),
        int_columns=frozenset({"master_id", "alter_id"}),
        str_columns=frozenset({"credit_limit", "opening_balance", "closing_balance"}),
    ),
    "stock_items": TableSpec(
        name="stock_items",
        columns=(
            "guid",
            "company_id",
            "name",
            "parent",
            "category",
            "base_units",
            "alternate_units",
            "hsn_code",
            "gst_applicable",
            "gst_type_of_supply",
            "tax_rate",
            "costing_method",
            "valuation_method",
            "opening_balance",
            "opening_rate",
            "opening_value",
            "closing_balance",
            "closing_value",
            "master_id",
            "alter_id",
            "synced_at",
        ),
        int_columns=frozenset({"master_id", "alter_id"}),
        str_columns=frozenset(
            {
                "tax_rate",
                "opening_balance",
                "opening_rate",
                "opening_value",
                "closing_balance",
                "closing_value",
            }
        ),
    ),
}


VOUCHER_SPEC = TableSpec(
    name="vouchers",
    columns=(
        "guid",
        "company_id",
        "date",
        "voucher_type_name",
        "voucher_number",
        "narration",
        "reference",
        "party_ledger_name",
        "is_cancelled",
        "is_optional",
        "is_invoice",
        "persisted_view",
        "effective_date",
        "reference_date",
        "place_of_supply",
        "party_gstin",
        "consignee_name",
        "irn",
        "eway_bill_no",
        "master_id",
        "alter_id",
        "synced_at",
    ),
    bool_columns=frozenset({"is_cancelled", "is_optional", "is_invoice"}),
    int_columns=frozenset({"master_id", "alter_id"}),
    str_columns=frozenset({"date", "effective_date", "reference_date"}),
)


CHILD_TABLE_SPECS: dict[str, TableSpec] = {
    "ledger_entries": TableSpec(
        name="ledger_entries",
        columns=(
            "voucher_guid",
            "ledger_name",
            "amount",
            "is_deemed_positive",
            "bill_ref",
            "bill_type",
            "bill_due_date",
            "bill_credit_period",
            "bill_amount",
        ),
        bool_columns=frozenset({"is_deemed_positive"}),
        str_columns=frozenset({"amount", "bill_amount"}),
    ),
    "cost_centre_allocations": TableSpec(
        name="cost_centre_allocations",
        columns=(
            "voucher_guid",
            "ledger_name",
            "cost_category",
            "cost_centre_name",
            "amount",
            "is_deemed_positive",
        ),
        bool_columns=frozenset({"is_deemed_positive"}),
        str_columns=frozenset({"amount"}),
    ),
    "inventory_entries": TableSpec(
        name="inventory_entries",
        columns=(
            "voucher_guid",
            "stock_item_name",
            "billed_qty",
            "actual_qty",
            "rate",
            "amount",
            "godown_name",
            "batch_name",
            "unit",
        ),
        str_columns=frozenset({"billed_qty", "actual_qty", "rate", "amount"}),
    ),
    "attendance_entries": TableSpec(
        name="attendance_entries",
        columns=(
            "voucher_guid",
            "employee_name",
            "attendance_type",
            "value",
            "time_value",
        ),
        str_columns=frozenset({"value"}),
    ),
}
