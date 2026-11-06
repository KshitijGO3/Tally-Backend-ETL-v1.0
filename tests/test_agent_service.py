"""Unit tests for AgentTools and O3AgentService conversational engine."""

from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime
from typing import Any

import pytest

from backend_ETL.agent_service import O3AgentService
from backend_ETL.agent_tools import AgentTools
from backend_ETL.analytics_service import AnalyticsService
from backend_ETL.canonical_schema import CANONICAL_DDL_STATEMENTS
from backend_ETL.db import PostgresManager
from backend_ETL.schema import PG_DDL_STATEMENTS


class _SQLiteCursorAdapter:
    def __init__(self, raw_cur: sqlite3.Cursor) -> None:
        self._cur = raw_cur

    @staticmethod
    def _translate(sql: str) -> str:
        if "DROP CONSTRAINT" in sql.upper():
            return "SELECT 1"
        s = sql.replace("%s", "?")
        s = s.replace("BIGSERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
        s = re.sub(r"TIMESTAMPTZ\s+NOT\s+NULL\s+DEFAULT\s+(NOW\(\)|CURRENT_TIMESTAMP)", "TEXT DEFAULT CURRENT_TIMESTAMP", s, flags=re.IGNORECASE)
        s = re.sub(r"TIMESTAMPTZ\s+DEFAULT\s+(NOW\(\)|CURRENT_TIMESTAMP)", "TEXT DEFAULT CURRENT_TIMESTAMP", s, flags=re.IGNORECASE)
        s = s.replace("TIMESTAMPTZ DEFAULT NOW()", "TEXT DEFAULT CURRENT_TIMESTAMP")
        s = s.replace("TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP", "TEXT DEFAULT CURRENT_TIMESTAMP")
        s = s.replace("TIMESTAMPTZ", "TEXT")
        s = s.replace("NOW()", "CURRENT_TIMESTAMP")
        s = s.replace("CREATE OR REPLACE VIEW", "CREATE VIEW IF NOT EXISTS")
        s = re.sub(r"CHECK\s*\([^)]*~[^)]*\)", "", s)
        return s

    @staticmethod
    def _adapt_params(params: tuple[Any, ...] | list[Any]) -> tuple[Any, ...]:
        return tuple(
            p.isoformat() if isinstance(p, (date, datetime)) else p
            for p in params
        )

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        return self._cur.execute(self._translate(sql), self._adapt_params(params))

    def executemany(self, sql: str, seq_params: list[tuple[Any, ...]]) -> Any:
        return self._cur.executemany(
            self._translate(sql), [self._adapt_params(p) for p in seq_params]
        )

    def fetchone(self) -> Any:
        return self._cur.fetchone()

    def fetchall(self) -> list[Any]:
        return self._cur.fetchall()

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount

    def close(self) -> None:
        self._cur.close()


class _SQLiteConnAdapter:
    def __init__(self, raw_conn: sqlite3.Connection) -> None:
        self._conn = raw_conn
        self._conn.row_factory = sqlite3.Row

    def cursor(self) -> _SQLiteCursorAdapter:
        return _SQLiteCursorAdapter(self._conn.cursor())

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()


@pytest.fixture()
def agent_test_db() -> PostgresManager:
    raw_conn = sqlite3.connect(":memory:", check_same_thread=False)
    compat_conn = _SQLiteConnAdapter(raw_conn)
    db = PostgresManager(conn_factory=lambda: compat_conn, use_pool=False)

    with db.connection() as conn:
        cur = conn.cursor()
        for stmt in PG_DDL_STATEMENTS:
            cur.execute(stmt)
        for stmt in CANONICAL_DDL_STATEMENTS:
            cur.execute(stmt)

        # Seed Client and User
        cur.execute(
            """
            INSERT INTO clients (client_id, client_name, contact_email, created_at, updated_at)
            VALUES ('client-shree', 'Shree Polychem', 'manoj@shreepolychem.com', '2024-04-01T00:00:00Z', '2024-04-01T00:00:00Z')
            """
        )
        cur.execute(
            """
            INSERT INTO users (user_id, client_id, email, password_hash, full_name, role, created_at, updated_at)
            VALUES ('usr-manoj', 'client-shree', 'manoj@shreepolychem.com', 'dummy_hash', 'Manoj Kumar', 'owner', '2024-04-01T00:00:00Z', '2024-04-01T00:00:00Z')
            """
        )
        cur.execute(
            """
            INSERT INTO canonical_companies (company_id, name, books_from)
            VALUES ('comp-shree-1', 'Shree Polychem', '2024-04-01')
            """
        )
        today = date.today()
        d_today_10 = today.replace(day=10).strftime("%Y-%m-%d")
        d_today_14 = today.replace(day=14).strftime("%Y-%m-%d")
        d_today_recent = today.replace(day=min(today.day, 15)).strftime("%Y-%m-%d")

        if today.month == 1:
            prior_year = today.year - 1
            prior_month = 12
        else:
            prior_year = today.year
            prior_month = today.month - 1
        d_prior_05 = date(prior_year, prior_month, 5).strftime("%Y-%m-%d")
        d_prior_06 = date(prior_year, prior_month, 6).strftime("%Y-%m-%d")

        # Seed Accounts
        cur.execute(
            """
            INSERT INTO canonical_accounts (account_id, company_id, name, classification_role, reported_closing, credit_limit, credit_period_raw)
            VALUES 
            ('acc-cust-1', 'comp-shree-1', 'Vardhman Packaging', 'customer', 1180000.0, 2000000.0, '30 Days'),
            ('acc-cust-adv', 'comp-shree-1', 'Apex Polymers', 'customer', -200000.0, NULL, NULL),
            ('acc-supp-1', 'comp-shree-1', 'Reliance Industries', 'supplier', -1510000.0, NULL, '30 Days'),
            ('acc-supp-adv', 'comp-shree-1', 'Indian Oil Corp', 'supplier', 350000.0, NULL, NULL),
            ('acc-sales-1', 'comp-shree-1', 'Sales Domestic', 'sales', 0.0, NULL, NULL),
            ('acc-tax-1', 'comp-shree-1', 'Output IGST 18%', 'tax', 0.0, NULL, NULL)
            """
        )
        cur.execute(
            """
            INSERT INTO canonical_account_contacts (account_ref, contact_email, contact_phone, party_pan)
            VALUES 
            ('acc-cust-1', 'sales@vardhman.com', '+91-9876543210', 'AABCV1234F'),
            ('acc-cust-adv', 'orders@apexpolymers.com', '+91-9876543211', 'AABCA1234F'),
            ('acc-supp-1', 'billing@ril.com', '+91-9876543212', 'AABCR1234F'),
            ('acc-supp-adv', 'commercial@iocl.com', '+91-9876543213', 'AABCI1234F')
            """
        )

        # Seed Stock Item
        cur.execute(
            """
            INSERT INTO canonical_stock_items (stockitem_id, company_id, name, base_units)
            VALUES ('item-poly-1', 'comp-shree-1', 'Polymer Granules LDPE', 'KGS')
            """
        )

        # Seed Detailed Voucher (INV-101)
        cur.execute(
            """
            INSERT INTO canonical_vouchers (voucher_id, company_id, date, kind, base_type, number, reference, narration, party_ref, lifecycle, is_invoice, place_of_supply, party_gstin_doc)
            VALUES 
            ('vch-inv-101', 'comp-shree-1', '2024-10-15', 'Tax Invoice', 'Sales', 'INV-101', 'PO-9988', 'Goods delivered to plant', 'acc-cust-1', 'active', 1, '27 Maharashtra', '27AABCV1234F1Z1')
            """
        )
        # Postings for INV-101
        cur.execute(
            """
            INSERT INTO canonical_postings (voucher_ref, line_ordinal, account_ref, amount, source_deemed_positive)
            VALUES 
            ('vch-inv-101', 1, 'acc-cust-1', 1180000.0, 1),
            ('vch-inv-101', 2, 'acc-sales-1', 1000000.0, 0),
            ('vch-inv-101', 3, 'acc-tax-1', 180000.0, 0)
            """
        )
        # Inventory line for INV-101
        cur.execute(
            """
            INSERT INTO canonical_inventory_lines (voucher_guid, item_ref, billed_qty, actual_qty, rate, amount, unit_ref)
            VALUES 
            ('vch-inv-101', 'item-poly-1', 500.0, 500.0, 2000.0, 1000000.0, 'KGS')
            """
        )
        # Bill event for INV-101
        cur.execute(
            """
            INSERT INTO canonical_bill_events (voucher_ref, company_id, party_ref, bill_ref, kind, due_date, credit_period_raw, amount)
            VALUES 
            ('vch-inv-101', 'comp-shree-1', 'acc-cust-1', 'INV-101', 'new', '2024-11-14', '30 Days', 1180000.0)
            """
        )

        # Seed Quadrant 2: Customer Advance (Apex Polymers paid 2.0 Lakhs in advance)
        cur.execute(
            """
            INSERT INTO canonical_vouchers (voucher_id, company_id, date, kind, base_type, number, party_ref, lifecycle)
            VALUES ('vch-apex-adv', 'comp-shree-1', '2024-10-14', 'Receipt', 'Receipt', 'RCPT-501', 'acc-cust-adv', 'active')
            """
        )
        cur.execute(
            """
            INSERT INTO canonical_bill_events (voucher_ref, company_id, party_ref, bill_ref, kind, due_date, amount)
            VALUES ('vch-apex-adv', 'comp-shree-1', 'acc-cust-adv', 'ADV-APEX-1', 'advance', NULL, 200000.0)
            """
        )

        # Seed Quadrant 3: Supplier Payable (Reliance Industries purchase 15.1 Lakhs)
        cur.execute(
            """
            INSERT INTO canonical_vouchers (voucher_id, company_id, date, kind, base_type, number, party_ref, lifecycle)
            VALUES ('vch-ril-pur', 'comp-shree-1', '2024-10-08', 'Purchase', 'Purchase', 'PUR-801', 'acc-supp-1', 'active')
            """
        )
        cur.execute(
            """
            INSERT INTO canonical_bill_events (voucher_ref, company_id, party_ref, bill_ref, kind, due_date, amount)
            VALUES ('vch-ril-pur', 'comp-shree-1', 'acc-supp-1', 'RIL-INV-99', 'new', '2024-11-08', 1510000.0)
            """
        )

        # Seed Quadrant 4: Supplier Advance (Indian Oil Corp paid 3.5 Lakhs in advance)
        cur.execute(
            """
            INSERT INTO canonical_vouchers (voucher_id, company_id, date, kind, base_type, number, party_ref, lifecycle)
            VALUES ('vch-iocl-adv', 'comp-shree-1', '2024-10-12', 'Payment', 'Payment', 'PAY-301', 'acc-supp-adv', 'active')
            """
        )
        cur.execute(
            """
            INSERT INTO canonical_bill_events (voucher_ref, company_id, party_ref, bill_ref, kind, due_date, amount)
            VALUES ('vch-iocl-adv', 'comp-shree-1', 'acc-supp-adv', 'IOCL-ADV-1', 'advance', NULL, 350000.0)
            """
        )

        # Seed Company 2 for multi-tenant isolation verification
        cur.execute(
            """
            INSERT INTO canonical_companies (company_id, name, books_from)
            VALUES ('comp-other-2', 'Competitor Pvt Ltd', '2024-04-01')
            """
        )
        cur.execute(
            """
            INSERT INTO canonical_vouchers (voucher_id, company_id, date, kind, base_type, number, lifecycle)
            VALUES ('vch-comp2-secret', 'comp-other-2', '2024-10-15', 'Tax Invoice', 'Sales', 'SECRET-999', 'active')
            """
        )

        cur.execute(
            """
            INSERT INTO canonical_vouchers (voucher_id, company_id, date, kind, base_type, lifecycle)
            VALUES ('vch-recent', 'comp-shree-1', %s, 'Receipt', 'Receipt', 'active')
            """,
            (d_today_recent,),
        )

        # Seed Daily movements
        cur.execute(
            """
            INSERT INTO canonical_daily_movements (company_id, date, base_type, account_role, is_debit, total_amount, voucher_count)
            VALUES 
            ('comp-shree-1', %s, 'Sales', 'customer', 1, 1840000.0, 1),
            ('comp-shree-1', %s, 'Receipt', 'bank', 1, 1420000.0, 1),
            ('comp-shree-1', %s, 'Sales', 'customer', 1, 1559322.0, 1),
            ('comp-shree-1', %s, 'Receipt', 'bank', 1, 1302752.0, 1)
            """,
            (d_today_10, d_today_14, d_prior_05, d_prior_06),
        )
        cur.close()

    return db


class TestAgentService:
    def test_agent_tools_summary_generation(self, agent_test_db: PostgresManager) -> None:
        analytics = AnalyticsService(agent_test_db)
        tools = AgentTools(analytics)

        coll_summary = tools.get_collections_summary("comp-shree-1", period_preset="mtd")
        assert "Collections are" in coll_summary
        assert "up" in coll_summary
        assert "₹ 14.20 L" in coll_summary
        assert "₹ 13.03 L" in coll_summary

        sales_summary = tools.get_sales_summary("comp-shree-1", period_preset="mtd")
        assert "Sales are" in sales_summary
        assert "up" in sales_summary
        assert "₹ 18.40 L" in sales_summary
        assert "₹ 15.59 L" in sales_summary

    def test_deterministic_router_collections_prompt(self, agent_test_db: PostgresManager) -> None:
        agent = O3AgentService(agent_test_db)
        reply = agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="How were collections this month?",
        )
        assert "Collections are" in reply
        assert "₹ 14.20 L" in reply

        # Verify message was persisted into single chat thread
        history = agent.get_conversation_history("usr-manoj", "comp-shree-1")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "How were collections this month?"
        assert history[1]["role"] == "assistant"
        assert "Collections are" in history[1]["content"]

    def test_deterministic_router_slowest_payer(self, agent_test_db: PostgresManager) -> None:
        agent = O3AgentService(agent_test_db)
        reply = agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="Who pays me the slowest?",
        )
        assert "Vardhman Packaging" in reply
        assert "days" in reply

    def test_clear_conversation(self, agent_test_db: PostgresManager) -> None:
        agent = O3AgentService(agent_test_db)
        agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="How were sales this week?",
        )
        history = agent.get_conversation_history("usr-manoj", "comp-shree-1")
        assert len(history) >= 2

        agent.clear_conversation("usr-manoj", "comp-shree-1")
        history_after = agent.get_conversation_history("usr-manoj", "comp-shree-1")
        assert len(history_after) == 0

    def test_get_voucher_details_with_joins_and_multi_tenant_guard(self, agent_test_db: PostgresManager) -> None:
        analytics = AnalyticsService(agent_test_db)
        tools = AgentTools(analytics)

        # 1. Query by voucher number
        vch = analytics.get_voucher_details("comp-shree-1", "INV-101")
        assert vch is not None
        assert vch["number"] == "INV-101"
        assert vch["kind"] == "Tax Invoice"
        assert vch["base_type"] == "Sales"
        assert vch["party"]["party_name"] == "Vardhman Packaging"
        assert vch["party"]["gstin"] == "27AABCV1234F1Z1"

        # Check inventory lines join
        assert len(vch["inventory_lines"]) == 1
        inv = vch["inventory_lines"][0]
        assert inv["item_name"] == "Polymer Granules LDPE"
        assert inv["billed_qty"] == 500.0
        assert inv["rate"] == 2000.0
        assert inv["amount"] == 1000000.0

        # Check postings join
        assert len(vch["postings"]) == 3
        debit_postings = [p for p in vch["postings"] if p["is_debit"]]
        assert len(debit_postings) == 1
        assert debit_postings[0]["account_name"] == "Vardhman Packaging"
        assert debit_postings[0]["amount"] == 1180000.0

        # Check bill events join
        assert len(vch["bill_events"]) == 1
        assert vch["bill_events"][0]["bill_ref"] == "INV-101"
        assert vch["bill_events"][0]["amount"] == 1180000.0

        # 2. Multi-tenant isolation: comp-other-2 cannot access comp-shree-1's voucher
        isolated = analytics.get_voucher_details("comp-other-2", "INV-101")
        assert isolated is None

        # 3. comp-shree-1 cannot access comp-other-2's secret voucher
        secret_leak = analytics.get_voucher_details("comp-shree-1", "SECRET-999")
        assert secret_leak is None

        # 4. Formatted summary from AgentTools
        summary = tools.get_voucher_details_summary("comp-shree-1", "INV-101")
        assert "**Tax Invoice #INV-101**" in summary
        assert "Vardhman Packaging" in summary
        assert "Polymer Granules LDPE" in summary
        assert "Sales Domestic" in summary
        assert "Ref: INV-101" in summary

    def test_get_party_summary_and_multi_tenant_guard(self, agent_test_db: PostgresManager) -> None:
        analytics = AnalyticsService(agent_test_db)
        tools = AgentTools(analytics)

        # 1. Query party by name
        party_info = analytics.get_party_summary("comp-shree-1", "Vardhman Packaging")
        assert party_info is not None
        assert party_info["party_name"] == "Vardhman Packaging"
        assert party_info["classification_role"] == "customer"
        assert party_info["closing_balance"] == 1180000.0
        assert party_info["contact"]["email"] == "sales@vardhman.com"
        assert party_info["contact"]["phone"] == "+91-9876543210"
        assert len(party_info["open_bills"]) >= 1
        assert party_info["open_bills"][0]["bill_ref"] == "INV-101"

        # 2. Multi-tenant isolation: comp-other-2 cannot view comp-shree-1's party
        isolated = analytics.get_party_summary("comp-other-2", "Vardhman Packaging")
        assert isolated is None

        # 3. Formatted summary from AgentTools
        summary = tools.get_party_summary("comp-shree-1", "Vardhman")
        assert "**Vardhman Packaging** (Customer)" in summary
        assert "Bill INV-101" in summary

    def test_deterministic_router_voucher_lookup(self, agent_test_db: PostgresManager) -> None:
        agent = O3AgentService(agent_test_db)

        # Natural language query matching voucher
        reply = agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="Show details of voucher INV-101",
        )
        assert "Tax Invoice #INV-101" in reply
        assert "Polymer Granules LDPE" in reply
        assert "Vardhman Packaging" in reply

        # Query using voucher guid
        reply_guid = agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="Inspect voucher vch-inv-101",
        )
        assert "Tax Invoice #INV-101" in reply_guid

    def test_deterministic_router_party_summary(self, agent_test_db: PostgresManager) -> None:
        agent = O3AgentService(agent_test_db)

        # Natural language query matching party
        reply = agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="How much does Vardhman Packaging owe us?",
        )
        assert "Vardhman Packaging" in reply
        assert "Current Closing Balance" in reply
        assert "Bill INV-101" in reply

        reply_balance = agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="Balance of Vardhman Packaging",
        )
        assert "Vardhman Packaging" in reply_balance

    def test_dynamic_system_prompt_and_anti_hallucination_guardrails(self, agent_test_db: PostgresManager) -> None:
        agent = O3AgentService(agent_test_db)
        prompt = agent.build_system_prompt("comp-shree-1")

        # 1. Contains dynamic temporal anchor
        today = date.today()
        today_str = today.strftime("%d-%b-%Y")
        assert today_str in prompt
        assert "FY " in prompt
        assert "TEMPORAL CONTEXT" in prompt
        assert "Latest Synced Transaction Date in Tally Books" in prompt

        # 2. Contains anti-hallucination negative constraints
        assert "ZERO HALLUCINATION RULE" in prompt
        assert "You possess NO financial data or party balances in your memory" in prompt
        assert "Never guess, invent, or estimate any figure" in prompt

        # 3. Contains few-shot examples
        assert "FEW-SHOT TOOL CALL EXAMPLES" in prompt
        assert "get_party_balances_summary" in prompt
        assert "get_voucher_details" in prompt

    def test_party_balances_four_quadrants_and_multi_tenant(self, agent_test_db: PostgresManager) -> None:
        analytics = AnalyticsService(agent_test_db)
        tools = AgentTools(analytics)

        # 1. Fetch all party balances for comp-shree-1
        data = analytics.get_party_balances("comp-shree-1", filter_type="all")
        summary = data["summary"]

        # Quadrant 1: Customer Receivable (Vardhman Packaging Dr 11.80 L)
        # Quadrant 4: Supplier Advance (Indian Oil Corp Dr 3.50 L)
        # Total Owed to Me = 11.80 L + 3.50 L = 15.30 L
        assert summary["total_owed_to_me"] == 1530000.0
        assert summary["count_owed_to_me"] == 2
        owed_names = [p["party_name"] for p in data["parties_owed_to_me"]]
        assert "Vardhman Packaging" in owed_names
        assert "Indian Oil Corp" in owed_names

        # Check natures
        iocl_entry = next(p for p in data["parties_owed_to_me"] if p["party_name"] == "Indian Oil Corp")
        assert "Supplier Advance" in iocl_entry["nature"]
        vardhman_entry = next(p for p in data["parties_owed_to_me"] if p["party_name"] == "Vardhman Packaging")
        assert "Customer Receivable" in vardhman_entry["nature"]

        # Quadrant 2: Customer Advance (Apex Polymers Cr 2.00 L)
        # Quadrant 3: Supplier Payable (Reliance Industries Cr 15.10 L)
        # Total I Owe = 15.10 L + 2.00 L = 17.10 L
        assert summary["total_i_owe"] == 1710000.0
        assert summary["count_i_owe"] == 2
        owe_names = [p["party_name"] for p in data["parties_i_owe"]]
        assert "Reliance Industries" in owe_names
        assert "Apex Polymers" in owe_names

        apex_entry = next(p for p in data["parties_i_owe"] if p["party_name"] == "Apex Polymers")
        assert "Customer Advance" in apex_entry["nature"]
        ril_entry = next(p for p in data["parties_i_owe"] if p["party_name"] == "Reliance Industries")
        assert "Supplier Payable" in ril_entry["nature"]

        # Net Position = 15.30 L - 17.10 L = -1.80 L (Net Payable)
        assert summary["net_position"] == -180000.0
        assert "Net Payable" in summary["position_status"]

        # 2. Multi-tenant isolation: comp-other-2 has no access to comp-shree-1
        data_other = analytics.get_party_balances("comp-other-2", filter_type="all")
        assert data_other["summary"]["count_owed_to_me"] == 0
        assert data_other["summary"]["count_i_owe"] == 0

        # 3. Formatted natural language summary
        summary_text = tools.get_party_balances_summary("comp-shree-1", filter_type="all")
        assert "**Party Balances & Dues Overview**" in summary_text
        assert "Vardhman Packaging" in summary_text
        assert "Indian Oil Corp [Supplier Advance / Debit Note]" in summary_text
        assert "Apex Polymers [Customer Advance / Credit Note]" in summary_text
        assert "Reliance Industries" in summary_text

    def test_deterministic_router_party_balances(self, agent_test_db: PostgresManager) -> None:
        agent = O3AgentService(agent_test_db)

        # "Who owes me money?"
        reply_owed = agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="Who owes me money?",
        )
        assert "Party Balances & Dues Overview" in reply_owed
        assert "Vardhman Packaging" in reply_owed
        assert "Indian Oil Corp" in reply_owed

        # "Who do I owe?"
        reply_i_owe = agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="Who do I owe money to?",
        )
        assert "Party Balances & Dues Overview" in reply_i_owe
        assert "Reliance Industries" in reply_i_owe
        assert "Apex Polymers" in reply_i_owe

        # "Show party balances"
        reply_all = agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="Show party balances",
        )
        assert "Total Owed to You" in reply_all
        assert "Total You Owe" in reply_all

    def test_agent_tools_custom_date_ranges(self, agent_test_db: PostgresManager) -> None:
        analytics = AnalyticsService(agent_test_db)
        tools = AgentTools(analytics)

        # 1. Custom date range for sales
        sales_summary = tools.get_sales_summary(
            "comp-shree-1",
            start_date="2024-10-01",
            end_date="2024-10-15",
        )
        assert "Sales are" in sales_summary
        assert "Total sales generated" in sales_summary

        # 2. Custom date range for collections
        coll_summary = tools.get_collections_summary(
            "comp-shree-1",
            start_date="2024-10-01",
            end_date="2024-10-15",
        )
        assert "Collections are" in coll_summary

        # 3. Custom date range for purchases
        pur_summary = tools.get_purchases_summary(
            "comp-shree-1",
            start_date="2024-10-01",
            end_date="2024-10-15",
        )
        assert "Purchases are" in pur_summary

    def test_deterministic_router_arbitrary_x_days(self, agent_test_db: PostgresManager) -> None:
        agent = O3AgentService(agent_test_db)

        # "Tell me sales of the last 15 days"
        reply_sales_15 = agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="Tell me my sales of the last 15 days",
        )
        assert "Sales are" in reply_sales_15
        assert "Total sales generated" in reply_sales_15

        # "Collections of the past 7 days"
        reply_coll_7 = agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="How were collections of the past 7 days?",
        )
        assert "Collections are" in reply_coll_7

        # "Purchases of the last 45 days"
        reply_pur_45 = agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="Tell me purchases of the last 45 days",
        )
        assert "Purchases are" in reply_pur_45

        # Explicit date range: "Sales from 2024-10-01 to 2024-10-15"
        reply_range = agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="Sales from 2024-10-01 to 2024-10-15",
        )
        assert "Sales are" in reply_range

    def test_tool_definitions_schemas_expose_start_and_end_dates(self) -> None:
        from backend_ETL.agent_tools import AGENT_TOOL_DEFINITIONS

        tool_map = {t["function"]["name"]: t["function"] for t in AGENT_TOOL_DEFINITIONS}

        for fn_name in ("get_sales_summary", "get_collections_summary", "get_purchases_summary"):
            assert fn_name in tool_map
            props = tool_map[fn_name]["parameters"]["properties"]
            # Must NOT expose period_preset to AI
            assert "period_preset" not in props
            # Must expose start_date and end_date
            assert "start_date" in props
            assert "end_date" in props
            assert props["start_date"]["type"] == "string"
            assert props["end_date"]["type"] == "string"

    def test_ai_tooling_functions_logging_emits_logs(
        self,
        agent_test_db: PostgresManager,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        import logging

        caplog.set_level(logging.INFO)
        agent = O3AgentService(agent_test_db)

        # Trigger tool via router
        agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="Sales of the last 10 days",
        )

        # Verify logs were emitted
        log_messages = [record.message for record in caplog.records]
        assert any("AgentTools.get_sales_summary: Invoked" in m for m in log_messages)
        assert any("AgentTools.get_sales_summary: Result generated" in m for m in log_messages)

        # Directly invoke another tool and verify logging
        caplog.clear()
        agent.agent_tools.get_party_balances_summary("comp-shree-1", filter_type="all")
        assert any("AgentTools.get_party_balances_summary: Invoked" in r.message for r in caplog.records)
        assert any("AgentTools.get_party_balances_summary: Result generated" in r.message for r in caplog.records)

    @staticmethod
    def _seed_bill_status_fixtures(db: PostgresManager) -> None:
        with db.connection() as conn:
            cur = conn.cursor()
            # Seed Fully Paid Bill (INV-PAID-200)
            cur.execute(
                """
                INSERT INTO canonical_vouchers (voucher_id, company_id, date, kind, base_type, number, party_ref, lifecycle)
                VALUES 
                ('vch-inv-paid', 'comp-shree-1', '2024-09-01', 'Tax Invoice', 'Sales', 'INV-PAID-200', 'acc-cust-1', 'active'),
                ('vch-rcpt-paid', 'comp-shree-1', '2024-09-20', 'Receipt', 'Receipt', 'RCPT-200', 'acc-cust-1', 'active')
                """
            )
            cur.execute(
                """
                INSERT INTO canonical_bill_events (voucher_ref, company_id, party_ref, bill_ref, kind, due_date, amount)
                VALUES 
                ('vch-inv-paid', 'comp-shree-1', 'acc-cust-1', 'INV-PAID-200', 'new', '2024-10-01', 500000.0),
                ('vch-rcpt-paid', 'comp-shree-1', 'acc-cust-1', 'INV-PAID-200', 'agst', NULL, 500000.0)
                """
            )

            # Seed Partially Paid Bill (INV-PARTIAL-300)
            cur.execute(
                """
                INSERT INTO canonical_vouchers (voucher_id, company_id, date, kind, base_type, number, party_ref, lifecycle)
                VALUES 
                ('vch-inv-part', 'comp-shree-1', '2024-10-01', 'Tax Invoice', 'Sales', 'INV-PARTIAL-300', 'acc-cust-1', 'active'),
                ('vch-rcpt-part', 'comp-shree-1', '2024-10-10', 'Receipt', 'Receipt', 'RCPT-300', 'acc-cust-1', 'active')
                """
            )
            cur.execute(
                """
                INSERT INTO canonical_bill_events (voucher_ref, company_id, party_ref, bill_ref, kind, due_date, amount)
                VALUES 
                ('vch-inv-part', 'comp-shree-1', 'acc-cust-1', 'INV-PARTIAL-300', 'new', '2024-10-31', 1000000.0),
                ('vch-rcpt-part', 'comp-shree-1', 'acc-cust-1', 'INV-PARTIAL-300', 'agst', NULL, 400000.0)
                """
            )
            cur.close()

    def test_get_bill_status_analytics_direct(self, agent_test_db: PostgresManager) -> None:
        self._seed_bill_status_fixtures(agent_test_db)
        analytics = AnalyticsService(agent_test_db)

        # 1. Fully Paid Bill (INV-PAID-200)
        paid_status = analytics.get_bill_status("comp-shree-1", "INV-PAID-200")
        assert paid_status is not None
        assert paid_status["bill_ref"] == "INV-PAID-200"
        assert paid_status["party_name"] == "Vardhman Packaging"
        assert paid_status["status"] == "paid"
        assert paid_status["status_label"] == "Fully Paid (Settled)"
        assert paid_status["original_amount"] == 500000.0
        assert paid_status["settled_amount"] == 500000.0
        assert paid_status["outstanding_balance"] == 0.0
        assert paid_status["settlement_percentage"] == 100.0
        assert len(paid_status["settlement_vouchers"]) == 1
        assert paid_status["settlement_vouchers"][0]["voucher_number"] == "RCPT-200"

        # 2. Partially Paid Bill (INV-PARTIAL-300)
        part_status = analytics.get_bill_status("comp-shree-1", "INV-PARTIAL-300")
        assert part_status is not None
        assert part_status["status"] == "partially_paid"
        assert part_status["status_label"] == "Partially Paid"
        assert part_status["original_amount"] == 1000000.0
        assert part_status["settled_amount"] == 400000.0
        assert part_status["outstanding_balance"] == 600000.0
        assert part_status["settlement_percentage"] == 40.0
        assert len(part_status["settlement_vouchers"]) == 1
        assert part_status["settlement_vouchers"][0]["voucher_number"] == "RCPT-300"

        # 3. Unpaid Bill (INV-101)
        unpaid_status = analytics.get_bill_status("comp-shree-1", "INV-101")
        assert unpaid_status is not None
        assert unpaid_status["status"] == "unpaid"
        assert unpaid_status["status_label"] == "Unpaid (Pending)"
        assert unpaid_status["original_amount"] == 1180000.0
        assert unpaid_status["settled_amount"] == 0.0
        assert unpaid_status["outstanding_balance"] == 1180000.0
        assert unpaid_status["settlement_percentage"] == 0.0
        assert len(unpaid_status["settlement_vouchers"]) == 0

        # 4. Non-existent bill
        missing = analytics.get_bill_status("comp-shree-1", "NON-EXISTENT-BILL-999")
        assert missing is None

    def test_get_bill_payment_status_summary_agent_tools(self, agent_test_db: PostgresManager) -> None:
        self._seed_bill_status_fixtures(agent_test_db)
        analytics = AnalyticsService(agent_test_db)
        tools = AgentTools(analytics)

        # 1. Paid summary
        paid_text = tools.get_bill_payment_status_summary("comp-shree-1", "INV-PAID-200")
        assert "**Bill INV-PAID-200 is Fully Paid (Settled)** 🟢" in paid_text
        assert "Vardhman Packaging" in paid_text
        assert "**Total Bill Amount**: **₹ 5.00 L**" in paid_text
        assert "**Outstanding Balance**: **₹ 0.00**" in paid_text
        assert "**Settled**: **₹ 5.00 L** (100% cleared)" in paid_text
        assert "Receipt `RCPT-200`" in paid_text

        # 2. Partially paid summary
        part_text = tools.get_bill_payment_status_summary("comp-shree-1", "INV-PARTIAL-300")
        assert "**Bill INV-PARTIAL-300 is Partially Paid** 🟡" in part_text
        assert "**Total Bill Amount**: **₹ 10.00 L**" in part_text
        assert "**Outstanding Balance**: **₹ 6.00 L**" in part_text
        assert "**Settled So Far**: **₹ 4.00 L** (40% cleared)" in part_text
        assert "Receipt `RCPT-300`" in part_text

        # 3. Unpaid summary
        unpaid_text = tools.get_bill_payment_status_summary("comp-shree-1", "INV-101")
        assert "**Bill INV-101 is Unpaid (Pending)** ⚠️" in unpaid_text
        assert "**Total Bill Amount**: **₹ 11.80 L**" in unpaid_text
        assert "**Outstanding Balance**: **₹ 11.80 L**" in unpaid_text
        assert "**Payments Recorded**: None" in unpaid_text

        # 4. Missing bill
        missing_text = tools.get_bill_payment_status_summary("comp-shree-1", "UNKNOWN-BILL")
        assert "not found" in missing_text

    def test_get_bill_payment_status_multi_tenant_guard(self, agent_test_db: PostgresManager) -> None:
        self._seed_bill_status_fixtures(agent_test_db)
        analytics = AnalyticsService(agent_test_db)
        tools = AgentTools(analytics)

        # Company 2 cannot access Company 1's bills
        c2_bill = analytics.get_bill_status("comp-other-2", "INV-PAID-200")
        assert c2_bill is None

        c2_summary = tools.get_bill_payment_status_summary("comp-other-2", "INV-PAID-200")
        assert "not found in your company records" in c2_summary

    def test_deterministic_router_bill_payment_status(self, agent_test_db: PostgresManager) -> None:
        self._seed_bill_status_fixtures(agent_test_db)
        agent = O3AgentService(agent_test_db)

        # Query 1: "Is bill INV-PAID-200 paid?"
        reply_paid = agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="Is bill INV-PAID-200 paid?",
        )
        assert "Fully Paid (Settled)" in reply_paid
        assert "₹ 5.00 L" in reply_paid

        # Query 2: "Is invoice INV-101 paid?"
        reply_unpaid = agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="Is invoice INV-101 paid?",
        )
        assert "Unpaid (Pending)" in reply_unpaid
        assert "₹ 11.80 L" in reply_unpaid

        # Query 3: "Payment status of INV-PARTIAL-300"
        reply_part = agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="Payment status of INV-PARTIAL-300",
        )
        assert "Partially Paid" in reply_part
        assert "₹ 4.00 L" in reply_part

        # Query 4: "Has invoice INV-PAID-200 been settled?"
        reply_settled = agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="Has invoice INV-PAID-200 been settled?",
        )
        assert "Fully Paid (Settled)" in reply_settled

    def test_bill_payment_status_tool_definition_schema(self) -> None:
        from backend_ETL.agent_tools import AGENT_TOOL_DEFINITIONS

        tool_map = {t["function"]["name"]: t["function"] for t in AGENT_TOOL_DEFINITIONS}
        assert "get_bill_payment_status" in tool_map

        bill_fn = tool_map["get_bill_payment_status"]
        assert "bill_identifier" in bill_fn["parameters"]["properties"]
        assert "bill_identifier" in bill_fn["parameters"]["required"]

    def test_bill_payment_status_logging(
        self,
        agent_test_db: PostgresManager,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        import logging

        caplog.set_level(logging.INFO)
        agent = O3AgentService(agent_test_db)

        caplog.clear()
        agent.agent_tools.get_bill_payment_status_summary("comp-shree-1", "INV-101")
        assert any("AgentTools.get_bill_payment_status_summary: Invoked" in r.message for r in caplog.records)
        assert any("AgentTools.get_bill_payment_status_summary: Result generated" in r.message for r in caplog.records)

    def _seed_inventory_fixtures(self, db: PostgresManager) -> None:
        """Seeds canonical_units and canonical_stock_items for inventory intelligence tests."""
        with db.connection() as conn:
            cur = conn.cursor()
            # Units
            cur.execute(
                """
                INSERT INTO canonical_units (unit_id, company_id, name, original_name, decimal_places)
                VALUES 
                    ('u-kgs', 'comp-shree-1', 'Kgs', 'Kilograms', 2),
                    ('u-nos', 'comp-shree-1', 'Nos', 'Pieces', 0)
                """
            )
            # Stock Items
            cur.execute(
                """
                INSERT INTO canonical_stock_items (
                    stockitem_id, company_id, name, base_units, closing_qty, closing_value
                ) VALUES 
                    ('si-1', 'comp-shree-1', 'HDPE Granules Grade A', 'Kgs', 12500.0, 1125000.0),
                    ('si-2', 'comp-shree-1', 'LLDPE Film Grade', 'Kgs', 8200.0, 738000.0),
                    ('si-3', 'comp-shree-1', 'Masterbatch Black', 'Kgs', 1200.0, 180000.0),
                    ('si-4', 'comp-shree-1', 'Titanium Dioxide Pigment', 'Kgs', 15.0, 45000.0),
                    ('si-5', 'comp-shree-1', 'Stearic Acid Flakes', 'Kgs', 25.0, 22500.0),
                    ('si-6', 'comp-shree-1', 'Plastic Storage Crates', 'Nos', 400.0, 160000.0),
                    ('si-zero-1', 'comp-shree-1', 'EVA Polymer 18%', 'Kgs', 0.0, 0.0),
                    ('si-zero-2', 'comp-shree-1', 'Calcium Carbonate Filler', 'Kgs', 0.0, 0.0)
                """
            )
            cur.close()

    def test_inventory_largest_stock(self, agent_test_db: PostgresManager) -> None:
        self._seed_inventory_fixtures(agent_test_db)
        tools = AgentTools(AnalyticsService(agent_test_db))

        res = tools.get_inventory_summary("comp-shree-1", query_type="largest_stock", limit=3)
        assert "Top 3 Stock Items by Quantity" in res
        assert "HDPE Granules Grade A" in res
        assert "12,500" in res
        assert "LLDPE Film Grade" in res
        assert "8,200" in res
        assert "Masterbatch Black" in res

        # Titanium Dioxide (15 Kgs) should not be in the top 3 largest
        assert "Titanium Dioxide Pigment" not in res

    def test_inventory_lowest_stock_strictly_non_zero(self, agent_test_db: PostgresManager) -> None:
        self._seed_inventory_fixtures(agent_test_db)
        tools = AgentTools(AnalyticsService(agent_test_db))

        res = tools.get_inventory_summary("comp-shree-1", query_type="lowest_stock", limit=3)
        assert "Lowest Non-Zero Stock" in res
        # #1 lowest non-zero is Titanium Dioxide (15)
        assert "Titanium Dioxide Pigment" in res
        assert "15 Kgs" in res or "15.00 Kgs" in res
        # #2 is Stearic Acid Flakes (25)
        assert "Stearic Acid Flakes" in res
        assert "25 Kgs" in res or "25.00 Kgs" in res
        # #3 is Plastic Storage Crates (400)
        assert "Plastic Storage Crates" in res

        # CRITICAL: Zero-stock items must NOT appear in lowest stock!
        assert "EVA Polymer 18%" not in res
        assert "Calcium Carbonate Filler" not in res

    def test_inventory_out_of_stock(self, agent_test_db: PostgresManager) -> None:
        self._seed_inventory_fixtures(agent_test_db)
        tools = AgentTools(AnalyticsService(agent_test_db))

        res = tools.get_inventory_summary("comp-shree-1", query_type="out_of_stock")
        assert "Out of Stock Items" in res
        assert "EVA Polymer 18%" in res
        assert "Calcium Carbonate Filler" in res
        assert "**0 Kgs** (Out of Stock)" in res

        # Positive items must NOT be listed
        assert "HDPE Granules Grade A" not in res
        assert "Titanium Dioxide Pigment" not in res

    def test_inventory_out_of_stock_none_found(self, agent_test_db: PostgresManager) -> None:
        tools = AgentTools(AnalyticsService(agent_test_db))
        # Empty company has no items out of stock
        res = tools.get_inventory_summary("comp-empty", query_type="out_of_stock")
        assert "All Items In Stock" in res

    def test_inventory_specific_item_search(self, agent_test_db: PostgresManager) -> None:
        self._seed_inventory_fixtures(agent_test_db)
        tools = AgentTools(AnalyticsService(agent_test_db))

        res = tools.get_inventory_summary("comp-shree-1", query_type="specific_item", item_name="HDPE")
        assert "HDPE Granules Grade A" in res
        assert "12,500" in res

        missing_res = tools.get_inventory_summary("comp-shree-1", query_type="specific_item", item_name="NonExistentItem")
        assert "No stock items matching" in missing_res

    def test_inventory_deterministic_router_intents(self, agent_test_db: PostgresManager) -> None:
        self._seed_inventory_fixtures(agent_test_db)
        agent = O3AgentService(agent_test_db)

        # 1. "tell me the top 3 items I have the largest stock of"
        q1 = agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="tell me the top 3 items I have the largest stock of",
        )
        assert "Top 3 Stock Items by Quantity" in q1
        assert "HDPE Granules Grade A" in q1

        # 2. "tell me the top 2 items I have the lowest stock of"
        q2 = agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="tell me the top 2 items I have the lowest stock of",
        )
        assert "Lowest Non-Zero Stock" in q2
        assert "Titanium Dioxide Pigment" in q2
        assert "EVA Polymer 18%" not in q2  # Zero stock excluded

        # 3. "List all the items that are out of stock"
        q3 = agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="List all the items that are out of stock",
        )
        assert "Out of Stock Items" in q3
        assert "EVA Polymer 18%" in q3
        assert "Calcium Carbonate Filler" in q3

        # 4. "How much stock of Masterbatch do we have?"
        q4 = agent.process_chat_message(
            user_id="usr-manoj",
            company_id="comp-shree-1",
            user_query="How much stock of Masterbatch do we have?",
        )
        assert "Masterbatch Black" in q4
        assert "1,200" in q4

    def test_inventory_tool_definition_schema(self) -> None:
        from backend_ETL.agent_tools import AGENT_TOOL_DEFINITIONS

        tool_map = {t["function"]["name"]: t["function"] for t in AGENT_TOOL_DEFINITIONS}
        assert "get_inventory_summary" in tool_map

        inv_fn = tool_map["get_inventory_summary"]
        props = inv_fn["parameters"]["properties"]
        assert "query_type" in props
        assert "limit" in props
        assert "item_name" in props
        assert "largest_stock" in props["query_type"]["enum"]
        assert "lowest_stock" in props["query_type"]["enum"]
        assert "out_of_stock" in props["query_type"]["enum"]

    def test_inventory_logging(
        self,
        agent_test_db: PostgresManager,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        import logging

        self._seed_inventory_fixtures(agent_test_db)
        caplog.set_level(logging.INFO)
        tools = AgentTools(AnalyticsService(agent_test_db))

        caplog.clear()
        tools.get_inventory_summary("comp-shree-1", query_type="largest_stock", limit=5)
        assert any("AgentTools.get_inventory_summary:" in r.message for r in caplog.records)
        assert any("AnalyticsService.get_stock_items:" in r.message for r in caplog.records)
