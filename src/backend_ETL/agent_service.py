"""O3 Conversational AI Agent Service powered by Ollama and Deterministic Analytics.

Supports local Ollama LLMs (e.g. qwen2.5:7b, llama3.2:3b) with tool calling and
includes an autonomous deterministic intent fallback ensuring 100% reliability
even before Ollama is launched or during model downloads.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Generator
from datetime import date, datetime, timedelta
from typing import Any

import ollama

from backend_ETL.agent_tools import AGENT_TOOL_DEFINITIONS, AgentTools
from backend_ETL.analytics_service import AnalyticsService
from backend_ETL.db import PostgresManager

log = logging.getLogger(__name__)

DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
DEFAULT_OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

class O3AgentService:
    """Manages conversational interactions for the single-thread Ask O3 panel."""

    def __init__(
        self,
        db: PostgresManager,
        model_name: str | None = None,
        host: str | None = None,
    ) -> None:
        self.db = db
        self.analytics_service = AnalyticsService(db)
        self.agent_tools = AgentTools(self.analytics_service)
        self.model_name = model_name or DEFAULT_OLLAMA_MODEL
        self.host = host or DEFAULT_OLLAMA_HOST

    def build_system_prompt(self, company_id: str) -> str:
        """Constructs a dynamic, per-request system prompt containing real calendar dates,
        the current Indian fiscal year, and the company's latest Tally sync anchor date,
        reinforced with zero-hallucination constraints and few-shot tool examples.
        """
        today = date.today()
        anchor_date = self.analytics_service.get_latest_anchor_date(company_id)
        anchor_str = anchor_date.strftime("%d-%b-%Y") if anchor_date else "Not yet synced"
        today_str = today.strftime("%A, %d-%b-%Y")
        fy_start_year = today.year if today.month >= 4 else today.year - 1
        fy_label = f"FY {fy_start_year}-{str(fy_start_year + 1)[-2:]}"

        return (
            "You are O3, an executive AI assistant for business owners analyzing their Tally ERP books.\n"
            "Your tone is professional, direct, concise, and helpful.\n"
            "Answer in 1 or 2 clear sentences. Always state exact amounts in Indian Rupees (₹ Cr, ₹ L) with period comparisons.\n"
            "\n"
            "TEMPORAL CONTEXT:\n"
            f"• Real-world Today: {today_str} ({fy_label})\n"
            f"• Latest Synced Transaction Date in Tally Books: {anchor_str}\n"
            "When user refers to 'this month', 'today', or 'this year', anchor relative queries to the Tally books context.\n"
            "\n"
            "CRITICAL CONSTRAINTS (ZERO HALLUCINATION RULE):\n"
            "1. You possess NO financial data or party balances in your memory.\n"
            "2. You MUST invoke a tool for any financial, party, or voucher question.\n"
            "3. Never guess, invent, or estimate any figure.\n"
            "4. If no tool returns data or the record is missing, state clearly that it was not found.\n"
            "5. For party balances: 'Who owes me/us money?' MUST call get_party_balances_summary(filter_type='owed_to_me'). 'Who do I/we owe money to?' MUST call get_party_balances_summary(filter_type='i_owe'). Never reverse them.\n"
            "\n"
            "FEW-SHOT TOOL CALL EXAMPLES:\n"
            '- User: "How much did we sell this month?" -> Call get_sales_summary(start_date="2024-10-01", end_date="2024-10-31")\n'
            '- User: "Sales for the last 15 days" -> Call get_sales_summary(start_date="2024-10-01", end_date="2024-10-15")\n'
            '- User: "Collections in the past 7 days" -> Call get_collections_summary(start_date="2024-10-09", end_date="2024-10-15")\n'
            '- User: "Purchases for the last 30 days" -> Call get_purchases_summary(start_date="2024-09-16", end_date="2024-10-15")\n'
            '- User: "Who owes me money?" -> Call get_party_balances_summary(filter_type="owed_to_me")\n'
            '- User: "Who do I owe money to?" -> Call get_party_balances_summary(filter_type="i_owe")\n'
            '- User: "Show party balances" -> Call get_party_balances_summary(filter_type="all")\n'
            '- User: "How much does Vardhman Packaging owe us?" -> Call get_party_summary(party_name="Vardhman Packaging")\n'
            '- User: "Show details of voucher 1024" -> Call get_voucher_details(voucher_identifier="1024")\n'
            '- User: "Is bill INV-101 paid?" -> Call get_bill_payment_status(bill_identifier="INV-101")\n'
            '- User: "Which invoices are overdue?" -> Call get_unpaid_invoices_summary(limit=5)\n'
            '- User: "Top 5 items I have largest stock of" -> Call get_inventory_summary(query_type="largest_stock", limit=5)\n'
            '- User: "Top 3 items with lowest stock" -> Call get_inventory_summary(query_type="lowest_stock", limit=3)\n'
            '- User: "Which items are out of stock?" -> Call get_inventory_summary(query_type="out_of_stock")\n'
            '- User: "How much Polyethylene do we have in stock?" -> Call get_inventory_summary(query_type="specific_item", item_name="Polyethylene")\n'
        )

    def get_conversation_history(
        self,
        user_id: str,
        company_id: str,
        limit: int = 15,
    ) -> list[dict[str, Any]]:
        """Returns the single-thread message history for this user and company."""
        return self.db.list_chat_messages(
            user_id=user_id,
            company_id=company_id,
            limit=limit,
        )

    def clear_conversation(self, user_id: str, company_id: str) -> None:
        """Clears the single conversation thread for this user and company."""
        self.db.clear_chat_messages(user_id=user_id, company_id=company_id)

    def process_chat_message(
        self,
        user_id: str,
        company_id: str,
        user_query: str,
    ) -> str:
        """Processes a user prompt, executes analytics tools, and returns the assistant response.

        Guarantees response generation by trying Ollama first, falling back cleanly
        to local deterministic analytics routing if Ollama is unreachable.
        """
        cleaned_user_query = user_query.strip()
        if not cleaned_user_query:
            return "Please enter a question about your sales, collections, receivables, or purchases."

        # 1. Save user message to database
        self.db.save_chat_message(
            user_id=user_id,
            company_id=company_id,
            role="user",
            content=cleaned_user_query,
        )

        # 2. Retrieve last 4 messages for sliding context window
        recent_history = self.get_conversation_history(user_id, company_id, limit=4)

        # 3. Attempt processing via Ollama with function calling
        assistant_reply: str | None = None
        try:
            assistant_reply = self._chat_via_ollama(
                company_id=company_id,
                user_query=cleaned_user_query,
                history=recent_history,
            )
        except Exception as ollama_error:
            log.info("Ollama chat invocation not available (%s); using deterministic analytics router.", ollama_error)
            assistant_reply = None

        # 4. Fallback to deterministic intent matching if Ollama was not available or gave empty response
        if not assistant_reply or not assistant_reply.strip():
            assistant_reply = self._deterministic_fallback_router(
                company_id=company_id,
                query=cleaned_user_query,
            )

        # 5. Save assistant reply to single-thread history
        self.db.save_chat_message(
            user_id=user_id,
            company_id=company_id,
            role="assistant",
            content=assistant_reply,
        )

        return assistant_reply

    def stream_chat_tokens(
        self,
        user_id: str,
        company_id: str,
        user_query: str,
    ) -> Generator[str, None, None]:
        """Yields response tokens sequentially for smooth typing effect in UI."""
        full_response = self.process_chat_message(
            user_id=user_id,
            company_id=company_id,
            user_query=user_query,
        )

        # Split into words for incremental typing stream
        words = full_response.split(" ")
        for i, word in enumerate(words):
            separator = " " if i < len(words) - 1 else ""
            yield word + separator

    def _chat_via_ollama(
        self,
        company_id: str,
        user_query: str,
        history: list[dict[str, Any]],
    ) -> str | None:
        """Invokes Ollama API with tools and anti-hallucination parameters."""
        # 1. Build dynamic system prompt with live date context and few-shot patterns
        system_prompt = self.build_system_prompt(company_id)

        formatted_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt}
        ]
        for msg in history:
            formatted_messages.append({"role": msg["role"], "content": msg["content"]})

        # 2. Inject temporal context envelope adjacent to the user query
        today = date.today()
        anchor_date = self.analytics_service.get_latest_anchor_date(company_id)
        anchor_str = anchor_date.strftime("%d-%b-%Y") if anchor_date else "Not yet synced"
        fy_start_year = today.year if today.month >= 4 else today.year - 1
        fy_label = f"FY {fy_start_year}-{str(fy_start_year + 1)[-2:]}"
        temporal_envelope = f"[System Context: Today is {today.strftime('%d-%b-%Y')} ({fy_label}) | Tally Books Synced As Of: {anchor_str}]\n"

        # Append current user prompt if not already present in history
        if not history or history[-1].get("content") != user_query:
            formatted_messages.append({"role": "user", "content": f"{temporal_envelope}{user_query}"})
        
        log.info(formatted_messages)
        client = ollama.Client(host=self.host, timeout=25.0)
        response = client.chat(
            model=self.model_name,
            messages=formatted_messages,
            tools=AGENT_TOOL_DEFINITIONS,
            think=True,
        )

        message = response.get("message") or {}
        tool_calls = message.get("tool_calls") or []

        if tool_calls:
            # Execute requested tool
            for call in tool_calls:
                func = call.get("function") or {}
                fn_name = func.get("name")
                fn_args = func.get("arguments") or {}

                # Anti-hallucination polarity and cross-tool guards for small LLMs
                q_lower = user_query.lower()

                # 1. Normalize common suffix aliases
                if fn_name == "get_voucher_details_summary":
                    fn_name = "get_voucher_details"
                elif fn_name == "get_bill_payment_status_summary":
                    fn_name = "get_bill_payment_status"

                # 2. Cross-Tool Redirections (Opposite flows & misclassifications)
                # Inflow vs. Outflow (Sales vs. Purchases)
                if fn_name == "get_sales_summary" and any(k in q_lower for k in ("purchase", "procurement", "bought", "vendor", "expenses")):
                    fn_name = "get_purchases_summary"
                elif fn_name == "get_purchases_summary" and any(k in q_lower for k in ("sales", "sold", "revenue", "turnover", "invoiced")):
                    fn_name = "get_sales_summary"

                # Receivables vs. Payables (What we owe vs. what is owed to us)
                elif fn_name == "get_receivables_summary" and any(k in q_lower for k in ("payable", "payables", "i owe", "we owe", "what do i owe", "vendor dues")):
                    fn_name = "get_party_balances_summary"
                    fn_args["filter_type"] = "i_owe"

                # Pronoun Hallucination Guard (e.g. model calls get_party_summary with "me" or "us")
                elif fn_name == "get_party_summary":
                    party_arg = str(fn_args.get("party_name", "")).strip().lower()
                    if party_arg in ("me", "us", "myself", "we", "company", "everyone", "all"):
                        fn_name = "get_party_balances_summary"
                        if any(k in q_lower for k in ("who owes me", "who owes us", "owed to me", "owe me")):
                            fn_args["filter_type"] = "owed_to_me"
                        elif any(k in q_lower for k in ("who do i owe", "who do we owe", "i owe")):
                            fn_args["filter_type"] = "i_owe"
                        else:
                            fn_args["filter_type"] = "all"

                # Bill payment status vs. unpaid invoices list disambiguation
                if fn_name in ("get_unpaid_invoices_summary", "get_voucher_details"):
                    if any(k in q_lower for k in ("is bill", "is invoice", "has bill", "has invoice", "been paid", "been settled", "cleared?", "paid?")):
                        bill_match = re.search(r"(?:bill|invoice|voucher)?\s*(?:#\s*)?([a-zA-Z0-9_\-\/]+)\s+(?:been\s+)?(?:paid|cleared|settled)", user_query, re.IGNORECASE)
                        if bill_match:
                            candidate_b = bill_match.group(1).strip()
                            if candidate_b.lower() not in ("it", "this", "that", "all", "the", "invoice", "bill"):
                                fn_name = "get_bill_payment_status"
                                fn_args["bill_identifier"] = candidate_b
                elif fn_name == "get_bill_payment_status":
                    bill_arg = str(fn_args.get("bill_identifier", "")).strip().lower()
                    if bill_arg in ("paid", "unpaid", "pending", "all", "overdue", "bills", "invoices", ""):
                        fn_name = "get_unpaid_invoices_summary"

                # 3. Argument / Polarity Normalization
                if fn_name == "get_party_balances_summary":
                    if any(k in q_lower for k in ("who owes me", "who owes us", "owed to me", "owe me", "owes me")):
                        fn_args["filter_type"] = "owed_to_me"
                    elif any(k in q_lower for k in ("who do i owe", "who do we owe", "what i owe", "what do i owe", "i owe", "we owe")):
                        fn_args["filter_type"] = "i_owe"
                    elif any(k in q_lower for k in ("all balances", "both", "debtors and creditors", "party balances")):
                        fn_args["filter_type"] = "all"

                elif fn_name == "get_inventory_summary":
                    if any(k in q_lower for k in ("out of stock", "zero stock", "no stock", "nil stock")):
                        fn_args["query_type"] = "out_of_stock"
                    elif any(k in q_lower for k in ("lowest stock", "least stock", "low stock", "minimum stock", "lowest inventory")):
                        fn_args["query_type"] = "lowest_stock"
                    elif any(k in q_lower for k in ("largest stock", "highest stock", "most stock", "maximum stock", "biggest stock")):
                        fn_args["query_type"] = "largest_stock"
                    elif any(k in q_lower for k in ("inventory summary", "stock summary", "total stock", "total inventory", "valuation", "status")):
                        fn_args["query_type"] = "summary"
                    elif fn_args.get("item_name"):
                        fn_args["query_type"] = "specific_item"

                # 4. Chronology Inversion Guard
                s_date = fn_args.get("start_date")
                e_date = fn_args.get("end_date")
                if s_date and e_date and str(s_date) > str(e_date):
                    fn_args["start_date"], fn_args["end_date"] = e_date, s_date

                result_str = self._execute_tool(company_id, fn_name, fn_args)
                if result_str:
                    return result_str

        # Zero-hallucination safeguard: if model attempted to answer a financial/analytical
        # query without calling a tool, reject the hallucination and fallback to deterministic router.
        log.info("Ollama did not invoke any tool for query [%s]; falling back to deterministic router.", user_query)
        return None

    def _execute_tool(
        self,
        company_id: str,
        tool_name: str,
        tool_arguments: dict[str, Any],
    ) -> str | None:
        """Dispatches tool execution to the deterministic AgentTools instance."""
        log.info(
            "O3AgentService._execute_tool: Invoking [%s] for company [%s] with args: %s",
            tool_name,
            company_id,
            tool_arguments,
        )
        start_date = tool_arguments.get("start_date")
        end_date = tool_arguments.get("end_date")
        period_preset = tool_arguments.get("period_preset")

        result: str | None = None
        if tool_name == "get_collections_summary":
            result = self.agent_tools.get_collections_summary(
                company_id,
                start_date=start_date,
                end_date=end_date,
                period_preset=period_preset,
            )
        elif tool_name == "get_sales_summary":
            result = self.agent_tools.get_sales_summary(
                company_id,
                start_date=start_date,
                end_date=end_date,
                period_preset=period_preset,
            )
        elif tool_name == "get_receivables_summary":
            result = self.agent_tools.get_receivables_summary(company_id)
        elif tool_name == "get_purchases_summary":
            result = self.agent_tools.get_purchases_summary(
                company_id,
                start_date=start_date,
                end_date=end_date,
                period_preset=period_preset,
            )
        elif tool_name == "get_slowest_paying_customers_summary":
            lookback = int(tool_arguments.get("lookback_days", 365))
            result = self.agent_tools.get_slowest_paying_customers_summary(company_id, lookback_days=lookback)
        elif tool_name == "get_unpaid_invoices_summary":
            limit = int(tool_arguments.get("limit", 5))
            result = self.agent_tools.get_unpaid_invoices_summary(company_id, limit=limit)
        elif tool_name in ("get_voucher_details", "get_voucher_details_summary"):
            voucher_id = str(tool_arguments.get("voucher_identifier") or "")
            result = self.agent_tools.get_voucher_details_summary(company_id, voucher_identifier=voucher_id)
        elif tool_name == "get_party_summary":
            party = str(tool_arguments.get("party_name") or "")
            result = self.agent_tools.get_party_summary(company_id, party_name=party)
        elif tool_name == "get_party_balances_summary":
            f_type = str(tool_arguments.get("filter_type") or "all")
            limit = int(tool_arguments.get("limit") or 5)
            result = self.agent_tools.get_party_balances_summary(company_id, filter_type=f_type, limit=limit)
        elif tool_name in ("get_bill_payment_status", "get_bill_payment_status_summary"):
            bill_id = str(tool_arguments.get("bill_identifier") or "")
            result = self.agent_tools.get_bill_payment_status_summary(company_id, bill_identifier=bill_id)
        elif tool_name == "get_inventory_summary":
            q_type = str(tool_arguments.get("query_type") or "largest_stock")
            limit = int(tool_arguments.get("limit") or 5)
            item_name = tool_arguments.get("item_name")
            result = self.agent_tools.get_inventory_summary(
                company_id,
                query_type=q_type,
                limit=limit,
                item_name=item_name,
            )

        log.info(
            "O3AgentService._execute_tool: [%s] completed (chars=%d)",
            tool_name,
            len(result) if result else 0,
        )
        return result

    def _deterministic_fallback_router(self, company_id: str, query: str) -> str:
        """Rules-based intent matching to route queries directly to analytics tools.

        Guarantees that prompts from the UI chips like 'How were collections this month?'
        or 'Sales of the last 15 days' work instantly and deterministically.
        """
        log.info("O3AgentService._deterministic_fallback_router: Routing query: %s", query)
        lowered = query.lower()

        # Check for arbitrary "last X days" or "past X days"
        last_x_match = re.search(r"(?:last|past)\s+(\d+)\s+days?", lowered)
        custom_days = int(last_x_match.group(1)) if last_x_match else None

        anchor = self.analytics_service.get_latest_anchor_date(company_id) or date.today()
        start_d: str | None = None
        end_d: str | None = None
        if custom_days is not None and custom_days > 0:
            start_d = (anchor - timedelta(days=custom_days - 1)).strftime("%Y-%m-%d")
            end_d = anchor.strftime("%Y-%m-%d")

        # Check for explicit date ranges: e.g. "from 2024-10-01 to 2024-10-15" or "between 01-10-2024 and 15-10-2024"
        if not start_d:
            range_match = re.search(
                r"(?:from|between)\s+([0-9]{2,4}[-/][0-9]{1,2}[-/][0-9]{2,4})\s+(?:to|and)\s+([0-9]{2,4}[-/][0-9]{1,2}[-/][0-9]{2,4})",
                lowered,
            )
            if range_match:
                start_d = range_match.group(1).strip()
                end_d = range_match.group(2).strip()

        # 1. Bill Payment / Settlement Status (e.g. 'Is bill INV-101 paid?', 'Has invoice INV-101 been settled?', 'Payment status of INV-101')
        top_x_stock_match = re.search(r"(?:top|first)\s+(\d+)", lowered)
        stock_limit = int(top_x_stock_match.group(1)) if top_x_stock_match else 5

        # Check for out of stock queries (e.g. "List all the items that are out of stock", "which items are out of stock", "zero stock")
        if any(k in lowered for k in ("out of stock", "zero stock", "no stock", "nil stock", "stockout", "out-of-stock", "without stock")):
            return self.agent_tools.get_inventory_summary(company_id, query_type="out_of_stock", limit=stock_limit if top_x_stock_match else 50)

        # Check for lowest non-zero stock queries (e.g. "top 5 items with lowest stock", "lowest stock", "least inventory", "low on stock")
        if any(k in lowered for k in ("lowest stock", "least stock", "low stock", "minimum stock", "lowest inventory", "least inventory", "low on stock", "bottom stock", "smallest stock")):
            return self.agent_tools.get_inventory_summary(company_id, query_type="lowest_stock", limit=stock_limit)

        # Check for largest stock queries (e.g. "top 5 items I have the largest stock of", "highest stock", "most stock", "maximum stock")
        if any(k in lowered for k in ("largest stock", "highest stock", "most stock", "maximum stock", "biggest stock", "largest inventory", "highest inventory", "most inventory", "top stock", "maximum inventory", "more stock")):
            return self.agent_tools.get_inventory_summary(company_id, query_type="largest_stock", limit=stock_limit)

        # Check for specific product stock query (e.g. "how much stock of HDPE do we have", "stock of Polyethylene")
        specific_stock_match = re.search(
            r"(?:how much stock of|stock of|inventory of|how much|quantity of)\s+([a-zA-Z0-9\s\.\-_&]+?)(?:\s+in stock|\s+do we have|\s+available|\?|$)",
            query,
            re.IGNORECASE,
        )
        if specific_stock_match and ("stock" in lowered or "inventory" in lowered):
            candidate_item = specific_stock_match.group(1).strip()
            if candidate_item.lower() not in ("it", "items", "goods", "materials", "products", "all", "everything", "the company", "we", "i", "the"):
                return self.agent_tools.get_inventory_summary(company_id, query_type="specific_item", item_name=candidate_item)

        # Check for general inventory overview / summary (e.g. "inventory summary", "stock summary", "total stock", "current inventory")
        if any(k in lowered for k in ("inventory summary", "stock summary", "total inventory", "total stock", "inventory status", "stock status", "current inventory", "all inventory", "current stock")):
            return self.agent_tools.get_inventory_summary(company_id, query_type="summary")

        bill_status_match = re.search(
            r"(?:is|has)\s+(?:the\s+)?(?:bill|invoice|voucher)?\s*(?:#\s*)?([a-zA-Z0-9_\-\/]+)\s+(?:been\s+)?(?:paid|cleared|settled|due)",
            query,
            re.IGNORECASE,
        )
        if not bill_status_match:
            bill_status_match = re.search(
                r"(?:payment\s+status|settlement\s+status|status)\s+of\s+(?:bill|invoice|voucher)?\s*(?:#\s*)?([a-zA-Z0-9_\-\/]+)",
                query,
                re.IGNORECASE,
            )
        if not bill_status_match:
            bill_status_match = re.search(
                r"(?:check\s+if|check)\s+(?:bill|invoice)?\s*(?:#\s*)?([a-zA-Z0-9_\-\/]+)\s+is\s+(?:paid|cleared|settled)",
                query,
                re.IGNORECASE,
            )
        if bill_status_match:
            extracted_bill = bill_status_match.group(1).strip()
            if extracted_bill.lower() not in ("it", "this", "that", "all", "the", "everything"):
                return self.agent_tools.get_bill_payment_status_summary(company_id, bill_identifier=extracted_bill)

        # 2. Granular Voucher Details (e.g. 'Show voucher 1024', 'Details of invoice INV-01')
        vch_match = re.search(
            r"(?:details\s+(?:of|for)\s+)?(?:voucher|invoice|bill)\s+(?:details\s+(?:for|of)\s+)?(?:#\s*)?([a-zA-Z0-9_\-]+)",
            query,
            re.IGNORECASE,
        )
        if not vch_match:
            vch_match = re.search(r"\b(vch-[a-zA-Z0-9_\-]+|inv-[a-zA-Z0-9_\-]+)\b", query, re.IGNORECASE)
        if vch_match and not any(w in lowered for w in ("unpaid", "pending", "overdue", "open invoices", "which invoices")):
            extracted_vch = vch_match.group(1).strip()
            if extracted_vch.lower() not in ("summary", "details", "list", "types", "counts", "this", "all"):
                return self.agent_tools.get_voucher_details_summary(company_id, voucher_identifier=extracted_vch)

        # 2. General Party Balances Overview (e.g. 'Who owes me money?', 'Who do I owe?')
        if any(k in lowered for k in ("who owes me", "who owes us", "owed to me", "owe me", "owes me")):
            return self.agent_tools.get_party_balances_summary(company_id, filter_type="owed_to_me")
        if any(k in lowered for k in ("who do i owe", "who do we owe", "what i owe", "what do i owe", "i owe", "we owe")):
            return self.agent_tools.get_party_balances_summary(company_id, filter_type="i_owe")
        if any(k in lowered for k in ("party balances", "party balance", "debtors and creditors", "who owes", "all balances", "amount owed")):
            return self.agent_tools.get_party_balances_summary(company_id, filter_type="all")

        # 3. Specific Party Ledger & Balance Summary (e.g. 'How much does Vardhman Packaging owe us', 'Balance of Apex')
        party_match = re.search(
            r"(?:how much does|balance of|outstanding (?:of|for)|ledger of|status of|party summary (?:of|for)|due from)\s+([a-zA-Z0-9\s\.\-_&]+?)(?:\s+owe|\?|$)",
            query,
            re.IGNORECASE,
        )
        if party_match:
            party_candidate = party_match.group(1).strip()
            if party_candidate.lower() not in ("me", "us", "the company", "everyone", "all"):
                return self.agent_tools.get_party_summary(company_id, party_name=party_candidate)

        if "balance" in lowered or "outstanding" in lowered or "ledger" in lowered:
            alt_match = re.search(r"([a-zA-Z0-9\s\.\-_&]+?)(?:'s|\s+)\s*(?:balance|outstanding|ledger)", query, re.IGNORECASE)
            if alt_match:
                party_candidate = alt_match.group(1).strip()
                if party_candidate.lower() not in ("cash", "bank", "total", "customer", "vendor", "supplier", "my", "our"):
                    return self.agent_tools.get_party_summary(company_id, party_name=party_candidate)

        # 4. Slowest paying customer (DSO)
        if any(k in lowered for k in ("slowest", "slow", "pays me", "dso", "payment delay")):
            return self.agent_tools.get_slowest_paying_customers_summary(company_id)

        # 5. Unpaid / overdue invoices
        if any(k in lowered for k in ("unpaid", "overdue", "pending bills", "open invoices", "which invoices")):
            return self.agent_tools.get_unpaid_invoices_summary(company_id)

        # 6. Collections
        if any(k in lowered for k in ("collection", "collected", "received", "receipt")):
            if start_d and end_d:
                return self.agent_tools.get_collections_summary(company_id, start_date=start_d, end_date=end_d)
            period = "mtd"
            if "week" in lowered:
                period = "mtd"
            elif "quarter" in lowered:
                period = "qtd"
            elif "year" in lowered:
                period = "ytd"
            return self.agent_tools.get_collections_summary(company_id, period_preset=period)

        # 7. Sales
        if any(k in lowered for k in ("sales", "sale", "revenue", "invoiced", "turnover")):
            if start_d and end_d:
                return self.agent_tools.get_sales_summary(company_id, start_date=start_d, end_date=end_d)
            period = "mtd"
            if "week" in lowered:
                period = "mtd"
            elif "quarter" in lowered:
                period = "qtd"
            elif "year" in lowered:
                period = "ytd"
            return self.agent_tools.get_sales_summary(company_id, period_preset=period)

        # 8. Purchases / Vendors
        if any(k in lowered for k in ("purchase", "vendor", "creditor", "procurement", "bought")):
            if start_d and end_d:
                return self.agent_tools.get_purchases_summary(company_id, start_date=start_d, end_date=end_d)
            return self.agent_tools.get_purchases_summary(company_id)

        # 9. Receivables / Debtors
        if any(k in lowered for k in ("receivable", "debtor", "due from")):
            return self.agent_tools.get_receivables_summary(company_id)

        # 10. If custom days or date range was asked without explicit type (e.g. "last 15 days"), default to sales
        if start_d and end_d:
            return self.agent_tools.get_sales_summary(company_id, start_date=start_d, end_date=end_d)

        # Fallback greeting
        return (
            "I'm O3. You can ask me about collections, sales, receivables, "
            "purchases, current inventory & stock, specific vouchers, party balances, which invoices are unpaid, or who pays you the slowest."
        )
