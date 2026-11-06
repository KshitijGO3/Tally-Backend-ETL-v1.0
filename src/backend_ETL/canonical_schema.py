"""Canonical Domain Model Schema DDL definitions for PostgreSQL (Silver Layer).

Defines the 26 Canonical Objects according to O3_Tally_to_Canonical_MASTER_REFERENCE.xlsx
sheets '02 Canonical Model' and '03 Field Mapping'. Enforces standard SQL DATE types
for chronological indexing and high-performance range queries.
"""

from __future__ import annotations

CANONICAL_DDL_STATEMENTS: list[str] = [
    # ─── 1. Canonical Master Tables ──────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS canonical_companies (
        company_id          TEXT PRIMARY KEY,
        name                TEXT NOT NULL,
        books_from          DATE,
        starting_from       DATE,
        company_number      TEXT,
        books_to            DATE,
        company_gstin       VARCHAR(15),
        source_master_id    INTEGER NOT NULL DEFAULT 0,
        source_alter_id     INTEGER NOT NULL DEFAULT 0,
        warehouse_synced_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_comp_name ON canonical_companies(name);",
    """
    CREATE TABLE IF NOT EXISTS canonical_account_groups (
        accountgroup_id     TEXT PRIMARY KEY,
        company_id          TEXT NOT NULL REFERENCES canonical_companies(company_id) ON DELETE CASCADE,
        name                TEXT NOT NULL,
        parent_ref          TEXT,
        parent_chain        TEXT,
        nature              VARCHAR(30),
        primary_group       TEXT,
        is_revenue          BOOLEAN DEFAULT FALSE,
        is_deemed_positive  BOOLEAN DEFAULT FALSE,
        affects_gross_profit BOOLEAN DEFAULT FALSE,
        source_master_id    INTEGER NOT NULL DEFAULT 0,
        source_alter_id     INTEGER NOT NULL DEFAULT 0,
        warehouse_synced_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_ag_company ON canonical_account_groups(company_id);",
    "CREATE INDEX IF NOT EXISTS idx_c_ag_name ON canonical_account_groups(company_id, name);",
    """
    CREATE TABLE IF NOT EXISTS canonical_accounts (
        account_id          TEXT PRIMARY KEY,
        company_id          TEXT NOT NULL REFERENCES canonical_companies(company_id) ON DELETE CASCADE,
        name                TEXT NOT NULL,
        group_ref           TEXT,
        aliases             TEXT,
        credit_limit        NUMERIC(18, 4),
        credit_period_raw   TEXT,
        bill_wise           BOOLEAN DEFAULT FALSE,
        cost_centres_on     BOOLEAN DEFAULT FALSE,
        currency            TEXT,
        reported_closing    NUMERIC(18, 4),
        gst_reg_type        TEXT,
        tax_classification  TEXT,
        classification_role VARCHAR(30) DEFAULT 'other',
        source_master_id    INTEGER NOT NULL DEFAULT 0,
        source_alter_id     INTEGER NOT NULL DEFAULT 0,
        warehouse_synced_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_acc_company ON canonical_accounts(company_id);",
    "CREATE INDEX IF NOT EXISTS idx_c_acc_name ON canonical_accounts(company_id, name);",
    "CREATE INDEX IF NOT EXISTS idx_c_acc_role ON canonical_accounts(company_id, classification_role);",
    """
    CREATE TABLE IF NOT EXISTS canonical_account_contacts (
        account_ref         TEXT PRIMARY KEY REFERENCES canonical_accounts(account_id) ON DELETE CASCADE,
        contact_mailing_name TEXT,
        contact_address     TEXT,
        contact_state_name  TEXT,
        contact_country_name TEXT,
        contact_pincode     VARCHAR(20),
        contact_email       TEXT,
        contact_phone       TEXT,
        contact_mobile      TEXT,
        party_pan           VARCHAR(30)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS canonical_party_identifiers (
        id                  BIGSERIAL PRIMARY KEY,
        party_ref           TEXT NOT NULL REFERENCES canonical_accounts(account_id) ON DELETE CASCADE,
        id_type             VARCHAR(30) NOT NULL,
        value               TEXT NOT NULL,
        confidence          VARCHAR(30) DEFAULT 'OBSERVED',
        source              TEXT,
        UNIQUE (party_ref, id_type, value)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_pi_party ON canonical_party_identifiers(party_ref);",
    """
    CREATE TABLE IF NOT EXISTS canonical_voucher_types (
        vouchertype_id      TEXT PRIMARY KEY,
        company_id          TEXT NOT NULL REFERENCES canonical_companies(company_id) ON DELETE CASCADE,
        name                TEXT NOT NULL,
        parent_kind         TEXT,
        base_type           VARCHAR(50),
        numbering_method    TEXT,
        is_active           BOOLEAN DEFAULT TRUE,
        affects_stock       BOOLEAN DEFAULT FALSE,
        prevent_duplicates  BOOLEAN DEFAULT FALSE,
        source_master_id    INTEGER NOT NULL DEFAULT 0,
        source_alter_id     INTEGER NOT NULL DEFAULT 0,
        warehouse_synced_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_vt_company ON canonical_voucher_types(company_id);",
    """
    CREATE TABLE IF NOT EXISTS canonical_stock_groups (
        stockgroup_id       TEXT PRIMARY KEY,
        company_id          TEXT NOT NULL REFERENCES canonical_companies(company_id) ON DELETE CASCADE,
        name                TEXT NOT NULL,
        parent_ref          TEXT,
        source_master_id    INTEGER NOT NULL DEFAULT 0,
        source_alter_id     INTEGER NOT NULL DEFAULT 0,
        warehouse_synced_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_sg_company ON canonical_stock_groups(company_id);",
    """
    CREATE TABLE IF NOT EXISTS canonical_stock_categories (
        stockcategory_id    TEXT PRIMARY KEY,
        company_id          TEXT NOT NULL REFERENCES canonical_companies(company_id) ON DELETE CASCADE,
        name                TEXT NOT NULL,
        parent_ref          TEXT,
        source_master_id    INTEGER NOT NULL DEFAULT 0,
        source_alter_id     INTEGER NOT NULL DEFAULT 0,
        warehouse_synced_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_sc_company ON canonical_stock_categories(company_id);",
    """
    CREATE TABLE IF NOT EXISTS canonical_stock_items (
        stockitem_id        TEXT PRIMARY KEY,
        company_id          TEXT NOT NULL REFERENCES canonical_companies(company_id) ON DELETE CASCADE,
        name                TEXT NOT NULL,
        parent_ref          TEXT,
        category            TEXT,
        base_units          TEXT,
        alternate_units     TEXT,
        hsn_code            TEXT,
        gst_applicable      TEXT,
        gst_type_of_supply  TEXT,
        tax_rate            NUMERIC(8, 4),
        costing_method      TEXT,
        valuation_method    TEXT,
        opening_qty         NUMERIC(18, 4),
        opening_rate        NUMERIC(18, 4),
        opening_value       NUMERIC(18, 4),
        closing_qty         NUMERIC(18, 4),
        closing_value       NUMERIC(18, 4),
        source_master_id    INTEGER NOT NULL DEFAULT 0,
        source_alter_id     INTEGER NOT NULL DEFAULT 0,
        warehouse_synced_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_si_company ON canonical_stock_items(company_id);",
    "CREATE INDEX IF NOT EXISTS idx_c_si_name ON canonical_stock_items(company_id, name);",
    """
    CREATE TABLE IF NOT EXISTS canonical_godowns (
        godown_id           TEXT PRIMARY KEY,
        company_id          TEXT NOT NULL REFERENCES canonical_companies(company_id) ON DELETE CASCADE,
        name                TEXT NOT NULL,
        parent_ref          TEXT,
        address             TEXT,
        has_no_space        BOOLEAN DEFAULT FALSE,
        has_no_stock        BOOLEAN DEFAULT FALSE,
        source_master_id    INTEGER NOT NULL DEFAULT 0,
        source_alter_id     INTEGER NOT NULL DEFAULT 0,
        warehouse_synced_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_godown_company ON canonical_godowns(company_id);",
    """
    CREATE TABLE IF NOT EXISTS canonical_units (
        unit_id             TEXT PRIMARY KEY,
        company_id          TEXT NOT NULL REFERENCES canonical_companies(company_id) ON DELETE CASCADE,
        name                TEXT NOT NULL,
        original_name       TEXT,
        base_units          TEXT,
        is_simple_unit      BOOLEAN DEFAULT TRUE,
        decimal_places      INTEGER DEFAULT 0,
        conversion          NUMERIC(18, 6),
        source_master_id    INTEGER NOT NULL DEFAULT 0,
        source_alter_id     INTEGER NOT NULL DEFAULT 0,
        warehouse_synced_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_unit_company ON canonical_units(company_id);",
    """
    CREATE TABLE IF NOT EXISTS canonical_cost_categories (
        costcategory_id     TEXT PRIMARY KEY,
        company_id          TEXT NOT NULL REFERENCES canonical_companies(company_id) ON DELETE CASCADE,
        name                TEXT NOT NULL,
        allocate_revenue    BOOLEAN DEFAULT TRUE,
        allocate_non_revenue BOOLEAN DEFAULT FALSE,
        source_master_id    INTEGER NOT NULL DEFAULT 0,
        source_alter_id     INTEGER NOT NULL DEFAULT 0,
        warehouse_synced_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_ccat_company ON canonical_cost_categories(company_id);",
    """
    CREATE TABLE IF NOT EXISTS canonical_cost_centres (
        costcentre_id       TEXT PRIMARY KEY,
        company_id          TEXT NOT NULL REFERENCES canonical_companies(company_id) ON DELETE CASCADE,
        name                TEXT NOT NULL,
        parent_ref          TEXT,
        category            TEXT,
        revenue_le_for_op_bal BOOLEAN DEFAULT FALSE,
        email_id            TEXT,
        source_master_id    INTEGER NOT NULL DEFAULT 0,
        source_alter_id     INTEGER NOT NULL DEFAULT 0,
        warehouse_synced_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_cc_company ON canonical_cost_centres(company_id);",
    """
    CREATE TABLE IF NOT EXISTS canonical_currencies (
        currency_id         TEXT PRIMARY KEY,
        company_id          TEXT NOT NULL REFERENCES canonical_companies(company_id) ON DELETE CASCADE,
        name                TEXT NOT NULL,
        mailing_name        TEXT,
        original_name       TEXT,
        expanded_symbol     TEXT,
        decimal_symbol      VARCHAR(10),
        decimal_places      INTEGER DEFAULT 2,
        source_master_id    INTEGER NOT NULL DEFAULT 0,
        source_alter_id     INTEGER NOT NULL DEFAULT 0,
        warehouse_synced_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_curr_company ON canonical_currencies(company_id);",
    """
    CREATE TABLE IF NOT EXISTS canonical_employee_groups (
        employeegroup_id    TEXT PRIMARY KEY,
        company_id          TEXT NOT NULL REFERENCES canonical_companies(company_id) ON DELETE CASCADE,
        name                TEXT NOT NULL,
        parent_ref          TEXT,
        category            TEXT,
        source_master_id    INTEGER NOT NULL DEFAULT 0,
        source_alter_id     INTEGER NOT NULL DEFAULT 0,
        warehouse_synced_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS canonical_employees (
        employee_id         TEXT PRIMARY KEY,
        company_id          TEXT NOT NULL REFERENCES canonical_companies(company_id) ON DELETE CASCADE,
        name                TEXT NOT NULL,
        parent_ref          TEXT,
        category            TEXT,
        date_of_joining     DATE,
        deactivation_date   DATE,
        designation         TEXT,
        function_role       TEXT,
        location            TEXT,
        gender              VARCHAR(20),
        blood_group         VARCHAR(10),
        pan_number          VARCHAR(10),
        aadhar_number       VARCHAR(20),
        pf_number           TEXT,
        uan                 VARCHAR(20),
        esi_number          TEXT,
        bank_name           TEXT,
        bank_account_number TEXT,
        ifsc_code           VARCHAR(20),
        email               TEXT,
        mobile              TEXT,
        source_master_id    INTEGER NOT NULL DEFAULT 0,
        source_alter_id     INTEGER NOT NULL DEFAULT 0,
        warehouse_synced_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_emp_company ON canonical_employees(company_id);",
    """
    CREATE TABLE IF NOT EXISTS canonical_attendance_types (
        attendancetype_id   TEXT PRIMARY KEY,
        company_id          TEXT NOT NULL REFERENCES canonical_companies(company_id) ON DELETE CASCADE,
        name                TEXT NOT NULL,
        parent_ref          TEXT,
        attendance_production_type TEXT,
        attendance_period   TEXT,
        base_units          TEXT,
        source_master_id    INTEGER NOT NULL DEFAULT 0,
        source_alter_id     INTEGER NOT NULL DEFAULT 0,
        warehouse_synced_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    # ─── 2. Canonical Transaction Tables ─────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS canonical_vouchers (
        voucher_id          TEXT PRIMARY KEY,
        company_id          TEXT NOT NULL REFERENCES canonical_companies(company_id) ON DELETE CASCADE,
        date                DATE NOT NULL,
        kind                TEXT NOT NULL,
        base_type           VARCHAR(50),
        number              TEXT,
        narration           TEXT,
        reference           TEXT,
        party_ref           TEXT,
        lifecycle           VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (lifecycle IN ('active', 'cancelled')),
        is_optional         BOOLEAN DEFAULT FALSE,
        is_invoice          BOOLEAN DEFAULT FALSE,
        persisted_view      TEXT,
        effective_date      DATE,
        reference_date      DATE,
        place_of_supply     TEXT,
        party_gstin_doc     VARCHAR(15),
        ship_to             TEXT,
        irn                 TEXT,
        eway_bill_no        TEXT,
        source_master_id    INTEGER NOT NULL DEFAULT 0,
        source_alter_id     INTEGER NOT NULL DEFAULT 0,
        warehouse_synced_at TIMESTAMPTZ DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_vch_company ON canonical_vouchers(company_id);",
    "CREATE INDEX IF NOT EXISTS idx_c_vch_date ON canonical_vouchers(company_id, date);",
    "CREATE INDEX IF NOT EXISTS idx_c_vch_party ON canonical_vouchers(company_id, party_ref);",
    "CREATE INDEX IF NOT EXISTS idx_c_vch_alter ON canonical_vouchers(company_id, source_alter_id);",
    "CREATE INDEX IF NOT EXISTS idx_c_vch_base_type ON canonical_vouchers(company_id, base_type);",
    """
    CREATE TABLE IF NOT EXISTS canonical_postings (
        id                  BIGSERIAL PRIMARY KEY,
        voucher_ref         TEXT NOT NULL REFERENCES canonical_vouchers(voucher_id) ON DELETE CASCADE,
        line_ordinal        INTEGER NOT NULL,
        account_ref         TEXT NOT NULL,
        amount              NUMERIC(18, 4) NOT NULL,
        source_deemed_positive BOOLEAN DEFAULT FALSE,
        UNIQUE (voucher_ref, line_ordinal)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_post_voucher ON canonical_postings(voucher_ref);",
    "CREATE INDEX IF NOT EXISTS idx_c_post_account ON canonical_postings(account_ref);",
    """
    CREATE TABLE IF NOT EXISTS canonical_bill_events (
        id                  BIGSERIAL PRIMARY KEY,
        voucher_ref         TEXT NOT NULL REFERENCES canonical_vouchers(voucher_id) ON DELETE CASCADE,
        company_id          TEXT NOT NULL REFERENCES canonical_companies(company_id) ON DELETE CASCADE,
        party_ref           TEXT NOT NULL,
        bill_ref            TEXT NOT NULL,
        kind                VARCHAR(30) NOT NULL CHECK (kind IN ('new', 'agst', 'on_account', 'advance', 'unspecified')),
        due_date            DATE,
        credit_period_raw   TEXT,
        amount              NUMERIC(18, 4) NOT NULL
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_be_voucher ON canonical_bill_events(voucher_ref);",
    "CREATE INDEX IF NOT EXISTS idx_c_be_party ON canonical_bill_events(company_id, party_ref);",
    "CREATE INDEX IF NOT EXISTS idx_c_be_bill ON canonical_bill_events(company_id, bill_ref);",
    """
    CREATE TABLE IF NOT EXISTS canonical_inventory_lines (
        id                  BIGSERIAL PRIMARY KEY,
        voucher_guid        TEXT NOT NULL REFERENCES canonical_vouchers(voucher_id) ON DELETE CASCADE,
        item_ref            TEXT NOT NULL,
        billed_qty          NUMERIC(18, 4) NOT NULL,
        actual_qty          NUMERIC(18, 4) NOT NULL,
        rate                NUMERIC(18, 4) NOT NULL,
        amount              NUMERIC(18, 4) NOT NULL,
        godown_ref          TEXT,
        batch_ref           TEXT,
        unit_ref            TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_il_voucher ON canonical_inventory_lines(voucher_guid);",
    "CREATE INDEX IF NOT EXISTS idx_c_il_item ON canonical_inventory_lines(item_ref);",
    """
    CREATE TABLE IF NOT EXISTS canonical_cost_allocations (
        id                  BIGSERIAL PRIMARY KEY,
        voucher_ref         TEXT NOT NULL REFERENCES canonical_vouchers(voucher_id) ON DELETE CASCADE,
        line_ordinal        INTEGER NOT NULL,
        account_ref         TEXT NOT NULL,
        cost_category_ref   TEXT,
        cost_centre_ref     TEXT NOT NULL,
        amount              NUMERIC(18, 4) NOT NULL,
        source_deemed_positive BOOLEAN DEFAULT FALSE
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_ca_voucher ON canonical_cost_allocations(voucher_ref);",
    """
    CREATE TABLE IF NOT EXISTS canonical_attendance_entries (
        id                  BIGSERIAL PRIMARY KEY,
        voucher_guid        TEXT NOT NULL REFERENCES canonical_vouchers(voucher_id) ON DELETE CASCADE,
        employee_name       TEXT NOT NULL,
        attendance_type     TEXT NOT NULL,
        value               NUMERIC(18, 4),
        time_value          NUMERIC(18, 4)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_ae_voucher ON canonical_attendance_entries(voucher_guid);",
    # ─── 3. Baseline, Quality & Sync Tables ──────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS canonical_opening_balances (
        account_ref         TEXT PRIMARY KEY REFERENCES canonical_accounts(account_id) ON DELETE CASCADE,
        company_id          TEXT NOT NULL REFERENCES canonical_companies(company_id) ON DELETE CASCADE,
        amount              NUMERIC(18, 4) NOT NULL,
        as_of               DATE
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_ob_company ON canonical_opening_balances(company_id);",
    """
    CREATE TABLE IF NOT EXISTS canonical_sync_cursors (
        company_id          TEXT NOT NULL REFERENCES canonical_companies(company_id) ON DELETE CASCADE,
        entity              TEXT NOT NULL,
        cursor_value        TEXT NOT NULL,
        extraction_time     TIMESTAMPTZ DEFAULT NOW(),
        PRIMARY KEY (company_id, entity)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS canonical_reconciliation_issues (
        id                  BIGSERIAL PRIMARY KEY,
        company_id          TEXT NOT NULL REFERENCES canonical_companies(company_id) ON DELETE CASCADE,
        entity_type         VARCHAR(50) NOT NULL,
        entity_name         TEXT NOT NULL,
        tally_value         NUMERIC(18, 4),
        warehouse_value     NUMERIC(18, 4),
        variance            NUMERIC(18, 4),
        detected_at         TIMESTAMPTZ DEFAULT NOW(),
        resolved            BOOLEAN DEFAULT FALSE
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_recon_company ON canonical_reconciliation_issues(company_id);",
    # ─── 4. Daily Analytical Summary Tables ──────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS canonical_daily_movements (
        company_id          TEXT NOT NULL REFERENCES canonical_companies(company_id) ON DELETE CASCADE,
        date                DATE NOT NULL,
        base_type           VARCHAR(50) NOT NULL,
        account_role        VARCHAR(50) NOT NULL,
        is_debit            BOOLEAN NOT NULL,
        total_amount        NUMERIC(18, 4) NOT NULL DEFAULT 0,
        voucher_count       INTEGER NOT NULL DEFAULT 0,
        updated_at          TIMESTAMPTZ DEFAULT NOW(),
        PRIMARY KEY (company_id, date, base_type, account_role, is_debit)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_c_dm_comp_date ON canonical_daily_movements(company_id, date);",
    "CREATE INDEX IF NOT EXISTS idx_c_dm_comp_base ON canonical_daily_movements(company_id, base_type);",
]
