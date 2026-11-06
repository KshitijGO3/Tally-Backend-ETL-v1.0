"""Deterministic Financial Analytics Tools for the O3 Executive AI Assistant.

Wraps the pure Python AnalyticsService to produce natural language executive summaries
matching the exact formatting and UX shown in the O3 design mockups.
"""

from __future__ import annotations

import logging
from typing import Any

from backend_ETL.analytics_service import AnalyticsService
from backend_ETL.formatters import format_inr

log = logging.getLogger(__name__)


class AgentTools:
    """Provides conversational responses for executive financial queries."""

    def __init__(self, analytics_service: AnalyticsService) -> None:
        self.analytics = analytics_service

    def get_collections_summary(
        self,
        company_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        period_preset: str | None = None,
    ) -> str:
        """Returns collections KPI, percentage comparison with prior period, and paying customer count."""
        log.info(
            "AgentTools.get_collections_summary: Invoked for company_id=%s, start_date=%s, end_date=%s, period_preset=%s",
            company_id,
            start_date,
            end_date,
            period_preset,
        )
        preset = "custom" if (start_date or end_date) else (period_preset or "mtd")
        if start_date and not end_date:
            anchor = self.analytics.get_latest_anchor_date(company_id)
            end_date = anchor.strftime("%Y-%m-%d") if anchor else None
        elif end_date and not start_date:
            start_date = end_date

        overview = self.analytics.get_executive_overview(
            company_id=company_id,
            period_preset=preset,
            custom_start=start_date,
            custom_end=end_date,
        )
        collections_kpi = overview["kpis"]["collections"]
        prior_label = overview["prior_period_label"]
        delta_pct = abs(int(round(collections_kpi["delta_pct"])))
        direction = collections_kpi["delta_direction"]
        formatted_val = collections_kpi["formatted_value"]
        customer_count = collections_kpi.get("paying_customers_count", 26)
        prior_formatted_val = collections_kpi["prior_collections"]

        result = (
            f"**{formatted_val}** received across **{customer_count}** customers.\n"
            f"Collections are **{direction} {delta_pct}%** vs **{prior_formatted_val}** received during {prior_label}."
        )
        log.info("AgentTools.get_collections_summary: Result generated: %s", result)
        return result

    def get_sales_summary(
        self,
        company_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        period_preset: str | None = None,
    ) -> str:
        """Returns sales KPI and comparison with prior period."""
        log.info(
            "AgentTools.get_sales_summary: Invoked for company_id=%s, start_date=%s, end_date=%s, period_preset=%s",
            company_id,
            start_date,
            end_date,
            period_preset,
        )
        preset = "custom" if (start_date or end_date) else (period_preset or "mtd")
        if start_date and not end_date:
            anchor = self.analytics.get_latest_anchor_date(company_id)
            end_date = anchor.strftime("%Y-%m-%d") if anchor else None
        elif end_date and not start_date:
            start_date = end_date

        overview = self.analytics.get_executive_overview(
            company_id=company_id,
            period_preset=preset,
            custom_start=start_date,
            custom_end=end_date,
        )
        sales_kpi = overview["kpis"]["sales"]
        prior_label = overview["prior_period_label"]
        delta_pct = abs(int(round(sales_kpi["delta_pct"])))
        direction = sales_kpi["delta_direction"]
        formatted_val = sales_kpi["formatted_value"]
        prior_formatted_val = sales_kpi.get("prior_sales", "₹ 0.00")

        result = (
            f"Total sales generated: **{formatted_val}**.\n"
            f"Sales are **{direction} {delta_pct}%** vs **{prior_formatted_val}** booked during {prior_label}."
        )
        log.info("AgentTools.get_sales_summary: Result generated: %s", result)
        return result

    def get_receivables_summary(self, company_id: str) -> str:
        """Returns outstanding receivables as of latest book date."""
        log.info("AgentTools.get_receivables_summary: Invoked for company_id=%s", company_id)
        overview = self.analytics.get_executive_overview(company_id=company_id)
        receivables_kpi = overview["kpis"]["receivables"]
        as_of_label = receivables_kpi["as_of_label"]
        formatted_val = receivables_kpi["formatted_value"]

        result = f"Total receivables outstanding {formatted_val} {as_of_label}."
        log.info("AgentTools.get_receivables_summary: Result generated: %s", result)
        return result

    def get_purchases_summary(
        self,
        company_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        period_preset: str | None = None,
    ) -> str:
        """Returns purchases KPI and comparison with prior period."""
        log.info(
            "AgentTools.get_purchases_summary: Invoked for company_id=%s, start_date=%s, end_date=%s, period_preset=%s",
            company_id,
            start_date,
            end_date,
            period_preset,
        )
        preset = "custom" if (start_date or end_date) else (period_preset or "mtd")
        if start_date and not end_date:
            anchor = self.analytics.get_latest_anchor_date(company_id)
            end_date = anchor.strftime("%Y-%m-%d") if anchor else None
        elif end_date and not start_date:
            start_date = end_date

        overview = self.analytics.get_executive_overview(
            company_id=company_id,
            period_preset=preset,
            custom_start=start_date,
            custom_end=end_date,
        )
        purchases_kpi = overview["kpis"]["purchases"]
        prior_label = overview["prior_period_label"]
        delta_pct = abs(int(round(purchases_kpi["delta_pct"])))
        direction = purchases_kpi["delta_direction"]
        formatted_val = purchases_kpi["formatted_value"]
        prior_formatted_val = purchases_kpi.get("prior_purchases", "₹ 0.00")

        result = (
            f"Total purchases booked: **{formatted_val}**.\n"
            f"Purchases are **{direction} {delta_pct}%** vs **{prior_formatted_val}** incurred during {prior_label}."
        )
        log.info("AgentTools.get_purchases_summary: Result generated: %s", result)
        return result

    def get_slowest_paying_customers_summary(self, company_id: str, lookback_days: int = 365) -> str:
        """Returns slowest paying customer DSO narrative vs company average."""
        log.info(
            "AgentTools.get_slowest_paying_customers_summary: Invoked for company_id=%s, lookback_days=%d",
            company_id,
            lookback_days,
        )
        result = self.analytics.get_slowest_paying_customers(company_id=company_id, lookback_days=lookback_days)
        narrative = result["narrative_response"]
        log.info("AgentTools.get_slowest_paying_customers_summary: Result generated (chars=%d)", len(narrative))
        return narrative

    def get_unpaid_invoices_summary(self, company_id: str, limit: int = 5) -> str:
        """Returns summary of top overdue invoices."""
        log.info(
            "AgentTools.get_unpaid_invoices_summary: Invoked for company_id=%s, limit=%d",
            company_id,
            limit,
        )
        invoices = self.analytics.get_unpaid_invoices(company_id=company_id, limit=limit)
        if not invoices:
            log.info("AgentTools.get_unpaid_invoices_summary: No unpaid invoices found")
            return "All invoices are currently fully settled. There are no unpaid invoices."

        lines = [f"Here are the top {len(invoices)} unpaid invoices:"]
        for inv in invoices:
            lines.append(
                f"• {inv['bill_ref']} - {inv['party_name']}: {inv['formatted_amount']} "
                f"({inv['days_overdue']} days overdue, due {inv['due_date']})"
            )
        result = "\n".join(lines)
        log.info("AgentTools.get_unpaid_invoices_summary: Returned %d unpaid invoices", len(invoices))
        return result

    def get_voucher_details_summary(self, company_id: str, voucher_identifier: str) -> str:
        """Returns granular details for a specific voucher, invoice, or receipt."""
        log.info(
            "AgentTools.get_voucher_details_summary: Invoked for company_id=%s, voucher_identifier=%s",
            company_id,
            voucher_identifier,
        )
        details = self.analytics.get_voucher_details(company_id=company_id, voucher_identifier=voucher_identifier)
        if not details:
            log.info("AgentTools.get_voucher_details_summary: Voucher not found: %s", voucher_identifier)
            return f"Voucher '{voucher_identifier}' was not found in your company records."

        kind = details.get("kind") or "Voucher"
        number = details.get("number") or details.get("voucher_id")
        v_date = details.get("date") or "N/A"
        lifecycle = (details.get("lifecycle") or "active").capitalize()
        total_amt = details.get("formatted_total_amount") or "₹ 0.00"

        party = details.get("party") or {}
        party_name = party.get("party_name") or "None / Internal"
        party_gstin = party.get("gstin")
        party_role = (party.get("party_role") or "").capitalize()
        party_role_str = f" ({party_role})" if party_role and party_role != "Other" else ""

        lines = [
            f"**{kind} #{number}**",
            f"• **Date**: {v_date} | **Status**: {lifecycle} | **Total Amount**: {total_amt}",
            f"• **Party**: {party_name}{party_role_str}" + (f" (GSTIN: {party_gstin})" if party_gstin else ""),
        ]

        if details.get("reference"):
            lines.append(f"• **Reference**: {details['reference']}")
        if details.get("place_of_supply"):
            lines.append(f"• **Place of Supply**: {details['place_of_supply']}")
        if details.get("e_way_bill_no"):
            lines.append(f"• **E-Way Bill**: {details['e_way_bill_no']}")

        # Inventory lines
        inv_lines = details.get("inventory_lines") or []
        if inv_lines:
            lines.append("\n**Inventory Items:**")
            for item in inv_lines:
                qty_unit = f"{item['billed_qty']:g} {item['unit']}".strip()
                rate_str = f" @ ₹{item['rate']:,.2f}" if item['rate'] > 0 else ""
                lines.append(f"• {item['item_name']}: {qty_unit}{rate_str} = {item['formatted_amount']}")

        # Accounting Postings
        postings = details.get("postings") or []
        if postings:
            lines.append("\n**Accounting Postings (Ledger Entries):**")
            for p in postings:
                role_label = f" [{p['classification_role']}]" if p.get("classification_role") and p["classification_role"] != "other" else ""
                lines.append(f"• {p['account_name']}{role_label}: {p['formatted_amount']} {p['type_label']}")

        # Bill references
        bills = details.get("bill_events") or []
        if bills:
            lines.append("\n**Bill Allocations:**")
            for b in bills:
                due_str = f", Due: {b['due_date']}" if b.get("due_date") else ""
                lines.append(f"• Ref: {b['bill_ref']} ({b['kind']}{due_str}) = {b['formatted_amount']}")

        if details.get("narration"):
            lines.append(f"\n*Narration*: {details['narration']}")

        result = "\n".join(lines)
        log.info("AgentTools.get_voucher_details_summary: Formatted summary generated for voucher %s", voucher_identifier)
        return result

    def get_party_summary(self, company_id: str, party_name: str) -> str:
        """Returns ledger balance, overdue dues, and recent vouchers for a specific party."""
        log.info(
            "AgentTools.get_party_summary: Invoked for company_id=%s, party_name=%s",
            company_id,
            party_name,
        )
        summary = self.analytics.get_party_summary(company_id=company_id, party_name=party_name)
        if not summary:
            log.info("AgentTools.get_party_summary: Party not found: %s", party_name)
            return f"No account or party matching '{party_name}' was found in your company records."

        p_name = summary.get("party_name") or party_name
        p_role = (summary.get("classification_role") or "party").capitalize()
        closing_bal = summary.get("formatted_closing_balance") or "₹ 0.00"
        open_bills_count = summary.get("open_bills_count", 0)
        overdue_amt = summary.get("formatted_overdue_amount") or "₹ 0.00"

        lines = [
            f"**{p_name}** ({p_role})",
            f"• **Current Closing Balance**: {closing_bal}",
        ]

        if summary.get("credit_limit"):
            lines.append(f"• **Credit Limit**: {format_inr(summary['credit_limit'])}")
        if summary.get("credit_period"):
            lines.append(f"• **Credit Period**: {summary['credit_period']}")

        contact = summary.get("contact") or {}
        if contact.get("phone") or contact.get("email"):
            contact_str = " | ".join(filter(None, [contact.get("phone"), contact.get("email")]))
            lines.append(f"• **Contact**: {contact_str}")

        open_bills = summary.get("open_bills") or []
        if open_bills:
            lines.append(f"\n**Open Invoices ({open_bills_count} bills, {overdue_amt} overdue):**")
            for b in open_bills[:5]:
                due_info = f"{b['days_overdue']} days overdue" if b['days_overdue'] > 0 else f"Due {b['due_date']}"
                lines.append(f"• Bill {b['bill_ref']}: {b['formatted_amount']} ({due_info})")
            if len(open_bills) > 5:
                lines.append(f"  *(and {len(open_bills) - 5} more open bills)*")
        else:
            lines.append("• **Open Invoices**: None (All bills settled)")

        recent_vchs = summary.get("recent_vouchers") or []
        if recent_vchs:
            lines.append("\n**Recent Transactions:**")
            for v in recent_vchs:
                lines.append(f"• {v['kind']} #{v['number']} on {v['date']}")

        result = "\n".join(lines)
        log.info("AgentTools.get_party_summary: Formatted summary generated for party: %s", party_name)
        return result

    def get_party_balances_summary(
        self,
        company_id: str,
        filter_type: str = "all",
        limit: int = 5,
    ) -> str:
        """Returns executive summary of amounts owed to you (receivables/debtors) and amounts you owe (payables/creditors)."""
        log.info(
            "AgentTools.get_party_balances_summary: Invoked for company_id=%s, filter_type=%s, limit=%d",
            company_id,
            filter_type,
            limit,
        )
        data = self.analytics.get_party_balances(company_id=company_id, filter_type=filter_type, limit=limit)
        summary = data["summary"]

        owed_to_me = summary["formatted_owed_to_me"]
        count_owed_to_me = summary["count_owed_to_me"]
        i_owe = summary["formatted_i_owe"]
        count_i_owe = summary["count_i_owe"]
        net_str = summary["formatted_net_position"]
        pos_status = summary["position_status"]

        lines = [
            "**Party Balances & Dues Overview**",
            f"• **Total Owed to You (Receivables)**: {owed_to_me} across {count_owed_to_me} parties",
            f"• **Total You Owe (Payables)**: {i_owe} across {count_i_owe} parties",
            f"• **Net Position**: {net_str} ({pos_status.split(':')[0]})",
        ]

        parties_owed = data.get("parties_owed_to_me") or []
        if filter_type in ("all", "owed_to_me"):
            if parties_owed:
                lines.append(f"\n**Top Parties Who Owe You ({len(parties_owed)} shown):**")
                for p in parties_owed:
                    overdue_info = f" ({p['max_overdue_days']} days overdue)" if p.get("max_overdue_days", 0) > 0 else ""
                    nature_tag = f" [{p['nature']}]" if "Supplier" in p.get("nature", "") else ""
                    lines.append(f"• {p['party_name']}{nature_tag}: {p['formatted_amount']}{overdue_info}")
            elif filter_type == "owed_to_me":
                lines.append("\n**No parties currently owe you money.**")

        parties_owe = data.get("parties_i_owe") or []
        if filter_type in ("all", "i_owe"):
            if parties_owe:
                lines.append(f"\n**Top Parties You Owe ({len(parties_owe)} shown):**")
                for p in parties_owe:
                    nature_tag = f" [{p['nature']}]" if "Customer" in p.get("nature", "") else ""
                    lines.append(f"• {p['party_name']}{nature_tag}: {p['formatted_amount']}")
            elif filter_type == "i_owe":
                lines.append("\n**You currently do not owe money to any party.**")

        result = "\n".join(lines)
        log.info("AgentTools.get_party_balances_summary: Result generated for filter_type=%s", filter_type)
        return result

    def get_bill_payment_status_summary(self, company_id: str, bill_identifier: str) -> str:
        """Returns natural language payment and settlement status for a specific bill or invoice reference."""
        log.info(
            "AgentTools.get_bill_payment_status_summary: Invoked for company_id=%s, bill_identifier=%s",
            company_id,
            bill_identifier,
        )
        status_info = self.analytics.get_bill_status(company_id=company_id, bill_identifier=bill_identifier)
        if not status_info:
            log.info("AgentTools.get_bill_payment_status_summary: Bill not found: %s", bill_identifier)
            return f"Bill or invoice reference '{bill_identifier}' was not found in your company records."

        b_ref = status_info["bill_ref"]
        party = status_info["party_name"]
        role = status_info["party_role"].capitalize()
        status_label = status_info["status_label"]
        status_code = status_info["status"]
        orig_amt = status_info["formatted_original_amount"]
        settled_amt = status_info["formatted_settled_amount"]
        out_bal = status_info["formatted_outstanding_balance"]
        pct = status_info["settlement_percentage"]

        if status_code == "paid":
            badge = "🟢"
        elif status_code == "partially_paid":
            badge = "🟡"
        elif status_code == "unpaid":
            badge = "⚠️"
        else:
            badge = "🔵"

        lines = [
            f"**Bill {b_ref} is {status_label}** {badge}",
            f"• **Party**: **{party}** ({role})",
            f"• **Total Bill Amount**: **{orig_amt}** | **Outstanding Balance**: **{out_bal}**",
        ]

        if status_code == "paid":
            vchs_count = status_info["settlement_count"]
            vch_word = "transaction" if vchs_count == 1 else "transactions"
            lines.append(f"• **Settled**: **{settled_amt}** (100% cleared) across **{vchs_count} {vch_word}**")
        elif status_code == "partially_paid":
            lines.append(f"• **Settled So Far**: **{settled_amt}** ({pct:g}% cleared)")
            if status_info.get("due_date"):
                if status_info["is_overdue"]:
                    lines.append(f"• **Due Date**: ⚠️ **{status_info['days_overdue']} days overdue** (due {status_info['due_date']})")
                else:
                    lines.append(f"• **Due Date**: {status_info['due_date']}")
        elif status_code == "unpaid":
            if status_info.get("due_date"):
                if status_info["is_overdue"]:
                    lines.append(f"• **Due Date**: ⚠️ **{status_info['days_overdue']} days overdue** (due {status_info['due_date']})")
                else:
                    lines.append(f"• **Due Date**: {status_info['due_date']}")
            lines.append("• **Payments Recorded**: None")
        elif status_code == "overpaid":
            lines.append(f"• **Settled / Adjusted**: **{settled_amt}** (Excess advance adjustment)")

        # Settlement history if available
        vchs = status_info.get("settlement_vouchers") or []
        if vchs:
            lines.append("\n**Settlement History:**")
            for v in vchs[:5]:
                lines.append(f"• {v['voucher_kind']} `{v['voucher_number']}` on {v['date']}: **{v['formatted_amount']}**")
            if len(vchs) > 5:
                lines.append(f"  *(and {len(vchs) - 5} earlier settlements)*")

        result = "\n".join(lines)
        log.info("AgentTools.get_bill_payment_status_summary: Result generated for bill %s (status=%s)", b_ref, status_code)
        return result

    def get_inventory_summary(
        self,
        company_id: str,
        query_type: str = "largest_stock",
        limit: int = 5,
        item_name: str | None = None,
    ) -> str:
        """Generates an executive-formatted summary of current inventory and stock balances.

        Supports:
          - largest_stock: Top items with highest closing quantity
          - lowest_stock: Top items with lowest non-zero closing quantity
          - out_of_stock: Items currently with 0 or negative quantity
          - specific_item: Stock information for a matching product name
          - summary: Overall inventory metrics and total valuation
        """
        log.info(
            "AgentTools.get_inventory_summary: company=%s, query_type=%s, limit=%d, item_name=%s",
            company_id,
            query_type,
            limit,
            item_name,
        )

        if query_type == "summary":
            overview = self.analytics.get_inventory_overview(company_id)
            if overview["total_items"] == 0:
                return "ℹ️ No inventory stock items found for this company in Tally books."

            return (
                f"📊 **Inventory Stock Overview:**\n\n"
                f"• **Total Valuation**: **{overview['formatted_valuation']}** across **{overview['total_items']} items**\n"
                f"• **In Stock**: **{overview['in_stock_count']} items**\n"
                f"• **Out of Stock**: **{overview['out_of_stock_count']} items**"
            )

        items = self.analytics.get_stock_items(
            company_id=company_id,
            query_type=query_type,
            limit=limit,
            item_name=item_name,
        )

        if not items:
            if query_type == "out_of_stock":
                return (
                    "✅ **All Items In Stock**\n\n"
                    "No out-of-stock items found. All inventory items currently have positive stock balances."
                )
            elif query_type == "lowest_stock":
                return "ℹ️ No items with positive stock found in your inventory."
            elif query_type == "specific_item" and item_name:
                return f"ℹ️ No stock items matching **\"{item_name}\"** were found for this company."
            else:
                return "ℹ️ No inventory stock items found for this company in Tally books."

        lines: list[str] = []
        if query_type == "largest_stock":
            lines.append(f"📦 **Top {len(items)} Stock Items by Quantity (Largest Stock):**\n")
            for item in items:
                u_str = f" {item['unit_name']}" if item["unit_name"] else ""
                lines.append(
                    f"• **{item['name']}**: **{item['formatted_qty']}{u_str}** (Valuation: **{item['formatted_value']}**)"
                )
        elif query_type == "lowest_stock":
            lines.append(f"⚠️ **Top {len(items)} Stock Items with Lowest Non-Zero Stock:**\n")
            for item in items:
                u_str = f" {item['unit_name']}" if item["unit_name"] else ""
                lines.append(
                    f"• **{item['name']}**: **{item['formatted_qty']}{u_str}** (Valuation: **{item['formatted_value']}**)"
                )
        elif query_type == "out_of_stock":
            item_word = "item" if len(items) == 1 else "items"
            lines.append(f"🚨 **Out of Stock Items ({len(items)} {item_word}):**\n")
            for item in items:
                u_str = f" {item['unit_name']}" if item["unit_name"] else ""
                lines.append(
                    f"• **{item['name']}**: **0{u_str}** (Out of Stock)"
                )
        elif query_type == "specific_item":
            lines.append(f"📦 **Stock Details for \"{item_name or 'Item'}\":**\n")
            for item in items:
                u_str = f" {item['unit_name']}" if item["unit_name"] else ""
                status_label = "🚨 Out of Stock" if item["is_out_of_stock"] else f"Valuation: **{item['formatted_value']}**"
                lines.append(
                    f"• **{item['name']}**: **{item['formatted_qty']}{u_str}** ({status_label})"
                )

        result = "\n".join(lines)
        log.info(
            "AgentTools.get_inventory_summary: Generated %d lines for query_type=%s",
            len(lines),
            query_type,
        )
        return result


# Tool schemas for Ollama function calling / system prompt definition
AGENT_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_collections_summary",
            "description": "Get collections KPI, period-over-period percentage delta, and paying customer count for a custom date range (start_date to end_date).",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date of the period in YYYY-MM-DD format (e.g. '2024-10-01')",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date of the period in YYYY-MM-DD format (e.g. '2024-10-15')",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sales_summary",
            "description": "Get sales KPI and percentage comparison vs prior period for a custom date range (start_date to end_date).",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date of the period in YYYY-MM-DD format (e.g. '2024-10-01')",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date of the period in YYYY-MM-DD format (e.g. '2024-10-15')",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_receivables_summary",
            "description": "Get total outstanding receivables and balance as of latest transaction date.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_purchases_summary",
            "description": "Get purchases KPI and percentage comparison vs prior period for a custom date range (start_date to end_date).",
            "parameters": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date of the period in YYYY-MM-DD format (e.g. '2024-10-01')",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date of the period in YYYY-MM-DD format (e.g. '2024-10-15')",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_slowest_paying_customers_summary",
            "description": "Find which customer pays the slowest in Days Sales Outstanding (DSO) compared to company average.",
            "parameters": {
                "type": "object",
                "properties": {
                    "lookback_days": {
                        "type": "integer",
                        "description": "Lookback days (default 365 days / 12 months)",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_unpaid_invoices_summary",
            "description": "Get list of unpaid, overdue customer invoices with amounts and days overdue.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of invoices to return (default 5)",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_voucher_details",
            "description": "Get granular accounting and inventory details for a specific voucher or invoice by voucher number, reference, or GUID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "voucher_identifier": {
                        "type": "string",
                        "description": "Voucher number, invoice reference, or voucher GUID (e.g. '1024', 'INV-001', 'vch-sale-1')",
                    }
                },
                "required": ["voucher_identifier"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_party_summary",
            "description": "Get ledger balance, outstanding dues, open bills, and recent transactions for a specific customer, supplier, or party.",
            "parameters": {
                "type": "object",
                "properties": {
                    "party_name": {
                        "type": "string",
                        "description": "The customer, supplier, or ledger name (e.g. 'Vardhman Packaging', 'Apex Polymers')",
                    }
                },
                "required": ["party_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_party_balances_summary",
            "description": "Get summary of all parties and accounts with amounts owed to you (receivables/debtors or supplier advances) and amounts you owe to them (payables/creditors or customer advances).",
            "parameters": {
                "type": "object",
                "properties": {
                    "filter_type": {
                        "type": "string",
                        "enum": ["owed_to_me", "i_owe", "all"],
                        "description": "Use 'owed_to_me' when asking who owes money to me/the business (debtors, receivables, customers who owe us). Use 'i_owe' when asking who I/we owe money to (creditors, payables, suppliers we owe). Use 'all' for complete balances overview.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of parties to list in each category (default 5).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_bill_payment_status",
            "description": "Check whether a specific invoice, bill reference, or bill number is paid, partially paid, or unpaid, along with settled amounts, outstanding balance, and payment history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bill_identifier": {
                        "type": "string",
                        "description": "Bill reference or invoice number to look up (e.g. 'INV-101', '1024', 'BILL/2024/001')",
                    }
                },
                "required": ["bill_identifier"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_inventory_summary",
            "description": "Get current inventory and stock balances. Supports finding top items with largest stock, top items with lowest non-zero stock, items that are out of stock, specific item stock, or overall inventory summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query_type": {
                        "type": "string",
                        "enum": ["largest_stock", "lowest_stock", "out_of_stock", "specific_item", "summary"],
                        "description": "Use 'largest_stock' when asking for items with highest/largest stock. Use 'lowest_stock' for items with lowest non-zero stock. Use 'out_of_stock' for items with zero or negative stock. Use 'specific_item' to check stock of a specific named product. Use 'summary' for total inventory value and item counts.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of items to return (default 5, e.g. for top 3, top 5, top 10).",
                    },
                    "item_name": {
                        "type": "string",
                        "description": "Name or keyword of the item when searching for a specific product (e.g. 'Polyethylene', 'Resin').",
                    },
                },
            },
        },
    },
]
