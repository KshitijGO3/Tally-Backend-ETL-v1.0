"""Unit tests for CanonicalTransformer and hierarchy walking."""

from datetime import date
from backend_ETL.canonical_transformer import (
    CanonicalTransformer,
    infer_ledger_role,
    resolve_ref,
    walk_group_hierarchy,
)


class TestGroupHierarchyWalking:
    def test_multi_level_walking(self) -> None:
        # Hierarchy: North Region Debtors -> Domestic Debtors -> Sundry Debtors -> Sundry Debtors
        group_parent_map = {
            "North Region Debtors": "Domestic Debtors",
            "Domestic Debtors": "Sundry Debtors",
            "Sundry Debtors": "Sundry Debtors",  # Tally root: group name = parent name
        }
        chain = walk_group_hierarchy("North Region Debtors", group_parent_map)
        assert chain == ["North Region Debtors", "Domestic Debtors", "Sundry Debtors"]

    def test_root_self_reference_cycle_terminates(self) -> None:
        # Tally convention: root group points to itself (Primary -> Primary)
        group_parent_map = {"Primary": "Primary"}
        chain = walk_group_hierarchy("Primary", group_parent_map)
        assert chain == ["Primary"]

    def test_arbitrary_cycle_terminated_by_visited_guard(self) -> None:
        # Unhealthy cycle: A -> B -> C -> A
        group_parent_map = {
            "Group A": "Group B",
            "Group B": "Group C",
            "Group C": "Group A",
        }
        chain = walk_group_hierarchy("Group A", group_parent_map)
        assert chain == ["Group A", "Group B", "Group C"]

    def test_missing_or_empty_parent_terminates(self) -> None:
        # Parent exists in map as empty/None
        assert walk_group_hierarchy("Child", {"Child": ""}) == ["Child"]
        assert walk_group_hierarchy("Child", {"Child": None}) == ["Child"]

        # Parent named but not registered in map as a key
        assert walk_group_hierarchy("Child", {"Child": "NonExistent"}) == ["Child", "NonExistent"]

        assert walk_group_hierarchy("", {}) == []
        assert walk_group_hierarchy(None, {}) == []


class TestInferLedgerRole:
    def test_nested_debtor_and_creditor_roles(self) -> None:
        group_parent_map = {
            "Delhi Debtors": "North Debtors",
            "North Debtors": "Domestic Debtors",
            "Domestic Debtors": "Sundry Debtors",
            "Sundry Debtors": "Sundry Debtors",
            "Mumbai Creditors": "West Creditors",
            "West Creditors": "Sundry Creditors",
            "Sundry Creditors": "Sundry Creditors",
            "HDFC Current": "Bank Accounts",
            "Bank Accounts": "Current Assets",
            "Petty Cash": "Cash-in-Hand",
            "GST Input": "Duties & Taxes",
            "Office Rent": "Indirect Expenses",
            "Software Sales": "Sales Accounts",
        }

        assert infer_ledger_role("Delhi Debtors", group_parent_map) == "customer"
        assert infer_ledger_role("Mumbai Creditors", group_parent_map) == "supplier"
        assert infer_ledger_role("HDFC Current", group_parent_map) == "bank"
        assert infer_ledger_role("Petty Cash", group_parent_map) == "cash"
        assert infer_ledger_role("GST Input", group_parent_map) == "tax"
        assert infer_ledger_role("Office Rent", group_parent_map) == "expense"
        assert infer_ledger_role("Software Sales", group_parent_map) == "income"
        assert infer_ledger_role("Miscellaneous Capital", group_parent_map) == "other"
        assert infer_ledger_role(None, group_parent_map) == "other"


class TestCanonicalTransformer:
    def test_transform_company(self) -> None:
        transformer = CanonicalTransformer(company_id="comp-123")
        raw = {
            "guid": "comp-123",
            "name": "Acme Corp",
            "books_from": "20240401",
            "starting_from": "1-Apr-2024",
            "company_number": "1001",
            "ending_at": "31/03/2025",
            "gstin": "27AABCU9603R1ZM",
            "master_id": 1,
            "alter_id": 10,
        }
        res = transformer.transform_company(raw)
        assert res["company_id"] == "comp-123"
        assert res["name"] == "Acme Corp"
        assert res["books_from"] == date(2024, 4, 1)
        assert res["starting_from"] == date(2024, 4, 1)
        assert res["books_to"] == date(2025, 3, 31)
        assert res["company_gstin"] == "27AABCU9603R1ZM"

    def test_transform_group_and_parent_chain(self) -> None:
        group_parent_map = {
            "North Region": "Domestic Debtors",
            "Domestic Debtors": "Sundry Debtors",
            "Sundry Debtors": "Sundry Debtors",
        }
        group_lookup = {
            "Domestic Debtors": "guid-dom-debtors",
        }
        transformer = CanonicalTransformer(
            company_id="comp-123",
            group_lookup=group_lookup,
            group_parent_map=group_parent_map,
        )
        raw = {
            "guid": "guid-north-region",
            "name": "North Region",
            "parent": "Domestic Debtors",
            "nature": "Assets",
            "primary_group": "Sundry Debtors",
            "is_revenue": False,
            "is_deemed_positive": True,
            "affects_gross_profit": False,
            "master_id": 5,
            "alter_id": 15,
        }
        res = transformer.transform_group(raw)
        assert res["accountgroup_id"] == "guid-north-region"
        assert res["parent_ref"] == "guid-dom-debtors"
        assert res["parent_chain"] == "Sundry Debtors > Domestic Debtors > North Region"

    def test_transform_ledger_decoupling(self) -> None:
        group_parent_map = {
            "Local Clients": "Sundry Debtors",
            "Sundry Debtors": "Sundry Debtors",
        }
        transformer = CanonicalTransformer(
            company_id="comp-123",
            group_parent_map=group_parent_map,
        )
        raw_ledger = {
            "guid": "led-cust-001",
            "name": "Tata Motors Ltd",
            "parent": "Local Clients",
            "alias": "TATA",
            "credit_limit": 500000.0,
            "credit_period": "30 Days",
            "is_bill_wise_on": 1,
            "is_cost_centres_on": 0,
            "currency_name": "INR",
            "closing_balance": 125000.0,
            "gst_registration_type": "Regular",
            "tax_classification": "Taxable",
            "mailing_name": "Tata Motors Limited",
            "address": "Bombay House, 24 Homi Mody Street",
            "state_name": "Maharashtra",
            "country_name": "India",
            "pincode": "400001",
            "email": "finance@tatamotors.com",
            "phone": "022-66658282",
            "mobile": "9820012345",
            "pan_number": "AAACT2727Q",
            "gstin": "27AAACT2727Q1ZW",
            "opening_balance": 50000.0,
        }
        res = transformer.transform_ledger(raw_ledger, books_from_date="01-04-2024")

        # 1. Account
        account = res["account"]
        assert account["account_id"] == "led-cust-001"
        assert account["classification_role"] == "customer"  # Inferred through ancestor
        assert account["credit_limit"] == 500000.0
        assert account["bill_wise"] is True

        # 2. Contact PII
        contact = res["contact"]
        assert contact is not None
        assert contact["account_ref"] == "led-cust-001"
        assert contact["party_pan"] == "AAACT2727Q"
        assert contact["contact_email"] == "finance@tatamotors.com"

        # 3. Party Identifier
        party_id = res["party_identifier"]
        assert party_id is not None
        assert party_id["id_type"] == "gstin"
        assert party_id["value"] == "27AAACT2727Q1ZW"

        # 4. Opening Balance
        op_bal = res["opening_balance"]
        assert op_bal["account_ref"] == "led-cust-001"
        assert op_bal["amount"] == 50000.0
        assert op_bal["as_of"] == date(2024, 4, 1)

    def test_transform_voucher_and_postings_bill_events(self) -> None:
        account_lookup = {"Tata Motors Ltd": "guid-tata", "Sales Account": "guid-sales"}
        transformer = CanonicalTransformer(
            company_id="comp-123",
            account_lookup=account_lookup,
        )

        raw_vch = {
            "guid": "vch-inv-101",
            "date": "20240415",
            "voucher_type_name": "Sales",
            "voucher_number": "INV-001",
            "narration": "Sale of automotive parts",
            "party_ledger_name": "Tata Motors Ltd",
            "is_cancelled": 0,
            "is_invoice": 1,
            "effective_date": "2024-04-15",
            "party_gstin": "27AAACT2727Q1ZW",
        }
        vch = transformer.transform_voucher(raw_vch)
        assert vch["voucher_id"] == "vch-inv-101"
        assert vch["date"] == date(2024, 4, 15)
        assert vch["effective_date"] == date(2024, 4, 15)
        assert vch["party_ref"] == "guid-tata"  # Resolved by lookup
        assert vch["lifecycle"] == "active"
        assert vch["is_invoice"] is True

        raw_entries = [
            {
                "voucher_guid": "vch-inv-101",
                "ledger_name": "Tata Motors Ltd",
                "amount": -118000.0,
                "is_deemed_positive": 1,
                "bill_ref": "INV-001",
                "bill_type": "New Ref",
                "bill_due_date": "15-May-2024",
                "bill_credit_period": "30 Days",
                "bill_amount": -118000.0,
            },
            {
                "voucher_guid": "vch-inv-101",
                "ledger_name": "Sales Account",
                "amount": 100000.0,
                "is_deemed_positive": 0,
                "bill_ref": None,
                "bill_type": None,
            },
        ]
        postings, bill_events = transformer.transform_ledger_entries(raw_entries)

        # Postings count = 2
        assert len(postings) == 2
        assert postings[0]["line_ordinal"] == 1
        assert postings[0]["account_ref"] == "guid-tata"
        assert postings[0]["amount"] == -118000.0
        assert postings[1]["line_ordinal"] == 2
        assert postings[1]["account_ref"] == "guid-sales"

        # Bill Events decoupled = 1
        assert len(bill_events) == 1
        assert bill_events[0]["bill_ref"] == "INV-001"
        assert bill_events[0]["kind"] == "new"
        assert bill_events[0]["due_date"] == date(2024, 5, 15)
        assert bill_events[0]["party_ref"] == "guid-tata"

    def test_resolve_ref_fallback(self) -> None:
        lookup = {"Known Ledger": "guid-known"}
        assert resolve_ref("Known Ledger", lookup) == "guid-known"
        assert resolve_ref("Historical Unknown Ledger", lookup) == "Historical Unknown Ledger"
        assert resolve_ref(None, lookup) is None

    def test_voucher_type_hierarchy_and_base_type(self) -> None:
        from backend_ETL.canonical_transformer import walk_voucher_type_hierarchy

        vt_parent_map = {
            "GST Sales": "Domestic Sales",
            "Domestic Sales": "Sales",
            "Special Receipt": "Receipt",
            "Unknown Custom": "Weird Parent",
        }
        assert walk_voucher_type_hierarchy("GST Sales", vt_parent_map) == "Sales"
        assert walk_voucher_type_hierarchy("Special Receipt", vt_parent_map) == "Receipt"
        # Keyword heuristic fallback for unknown parent with sales in name
        assert walk_voucher_type_hierarchy("Retail Sales Counter", {}) == "Sales"
        assert walk_voucher_type_hierarchy("Unknown Custom", vt_parent_map) == "Unknown Custom"

        transformer = CanonicalTransformer(
            company_id="comp-1",
            voucher_type_parent_map=vt_parent_map,
        )
        raw_vt = {
            "guid": "vt-1",
            "name": "GST Sales",
            "parent": "Domestic Sales",
        }
        transformed_vt = transformer.transform_voucher_type(raw_vt)
        assert transformed_vt["base_type"] == "Sales"

        raw_vch = {
            "guid": "vch-1",
            "voucher_type_name": "GST Sales",
            "date": "20241015",
        }
        transformed_vch = transformer.transform_voucher(raw_vch)
        assert transformed_vch["base_type"] == "Sales"

