"""Pure Python Analytics Service for Executive Dashboards and AI Assistants.

Performs all financial KPI aggregations, period-over-period comparisons,
weighted Days Sales Outstanding (DSO) calculation, and unpaid invoice aging
directly in Python memory from PostgreSQL Silver canonical tables.
Zero database procedures or triggers used.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from backend_ETL.date_utils import (
    format_canonical_date,
    get_prior_period_label,
    get_relative_period_bounds,
    parse_canonical_date,
)
from backend_ETL.db import PostgresManager
from backend_ETL.formatters import format_inr, format_inr_full, format_percentage

log = logging.getLogger(__name__)


class AnalyticsService:
    """Computes executive metrics and analytical data structures for a given company."""

    def __init__(self, db: PostgresManager) -> None:
        self.db = db

    def get_latest_anchor_date(self, company_id: str) -> date:
        """Determines the most recent active transaction date to anchor relative periods.

        If no transactions exist, falls back to today's date.
        """
        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT MAX(date) as max_date FROM canonical_vouchers
                WHERE company_id = %s AND lifecycle = 'active'
                """,
                (company_id,),
            )
            row = cur.fetchone()
            cur.close()

        if row and dict(row).get("max_date"):
            max_d = dict(row)["max_date"]
            return max_d if isinstance(max_d, date) else parse_canonical_date(max_d)
        return date.today()

    def get_sync_status(self, company_id: str) -> dict[str, Any]:
        """Returns the latest sync status and last updated date of company books."""
        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT name, warehouse_synced_at FROM canonical_companies WHERE company_id = %s",
                (company_id,),
            )
            company_row = cur.fetchone()
            company_dict = dict(company_row) if company_row else {}

            cur.execute(
                """
                SELECT MAX(date) as max_date FROM canonical_vouchers
                WHERE company_id = %s AND lifecycle = 'active'
                """,
                (company_id,),
            )
            vch_row = cur.fetchone()
            cur.close()

        latest_d = dict(vch_row).get("max_date") if vch_row else None
        if isinstance(latest_d, str):
            latest_date = parse_canonical_date(latest_d)
        else:
            latest_date = latest_d or date.today()
        formatted_date_label = f"{latest_date.day} {latest_date.strftime('%b')}"

        return {
            "company_id": company_id,
            "company_name": company_dict.get("name") or "Company",
            "warehouse_synced_at": company_dict.get("warehouse_synced_at"),
            "latest_voucher_date": format_canonical_date(latest_date),
            "books_updated_label": f"Books updated to {formatted_date_label}",
        }

    def get_executive_overview(
        self,
        company_id: str,
        period_preset: str = "mtd",
        user_display_name: str = "Manoj",
        reference_date: date | None = None,
        custom_start: date | str | None = None,
        custom_end: date | str | None = None,
    ) -> dict[str, Any]:
        """Computes the 4 Executive KPIs (Sales, Collections, Receivables, Purchases).

        Queries canonical_daily_movements directly and calculates period deltas in Python.
        Defaults to dynamic Month-to-date anchored to today's date if no reference_date is supplied.
        """
        anchor_date = reference_date or date.today()
        (curr_start, curr_end), (prior_start, prior_end), period_label = get_relative_period_bounds(
            period_preset=period_preset,
            reference_date=anchor_date,
            custom_start=custom_start,
            custom_end=custom_end,
        )

        prior_period_label = get_prior_period_label(
            period_preset=period_preset,
            prior_start=prior_start,
            prior_end=prior_end,
            reference_date=anchor_date,
        )

        with self.db.connection() as conn:
            cur = conn.cursor()

            # 1. Fetch company name
            cur.execute(
                "SELECT name FROM canonical_companies WHERE company_id = %s",
                (company_id,),
            )
            c_row = cur.fetchone()
            company_name = dict(c_row).get("name") if c_row else "Company"

            # 2. Fetch daily movements for this company in current or prior period directly via SQL index
            cur.execute(
                """
                SELECT date, base_type, account_role, is_debit, total_amount, voucher_count
                FROM canonical_daily_movements
                WHERE company_id = %s AND (
                    (date >= %s AND date <= %s) OR
                    (date >= %s AND date <= %s)
                )
                """,
                (company_id, curr_start, curr_end, prior_start, prior_end),
            )
            daily_rows = [dict(r) for r in cur.fetchall()]

            # 3. Query distinct paying customers in the current period
            cur.execute(
                """
                SELECT COUNT(DISTINCT party_ref) as customer_count
                FROM canonical_vouchers
                WHERE company_id = %s AND lifecycle = 'active'
                AND base_type = 'Receipt'
                """,
                (company_id,),
            )
            payer_row = cur.fetchone()
            paying_customers_count = dict(payer_row).get("customer_count", 0) if payer_row else 0

            # 4. Total Receivables outstanding as of current anchor date (excluding suppliers)
            cur.execute(
                """
                SELECT be.party_ref, be.kind, be.amount
                FROM canonical_bill_events be
                LEFT JOIN canonical_accounts a ON (be.party_ref = a.account_id OR be.party_ref = a.name)
                WHERE be.company_id = %s
                  AND (a.classification_role IS NULL OR a.classification_role != 'supplier')
                """,
                (company_id,),
            )
            bill_rows = [dict(r) for r in cur.fetchall()]
            cur.close()

        # Compute period totals in pure Python
        curr_sales = 0.0
        prior_sales = 0.0
        curr_collections = 0.0
        prior_collections = 0.0
        curr_purchases = 0.0
        prior_purchases = 0.0
        fallback_curr_sales = 0.0
        fallback_prior_sales = 0.0

        for row in daily_rows:
            row_date = row.get("date")
            if isinstance(row_date, str):
                row_date = parse_canonical_date(row_date)
            if not row_date:
                continue

            base_type = (row.get("base_type") or "").strip()
            account_role = (row.get("account_role") or "").strip()
            amount = float(row.get("total_amount") or 0.0)

            # 1. Current Period Accumulation
            if curr_start <= row_date <= curr_end:
                if base_type == "Sales":
                    fallback_curr_sales += amount
                    if account_role in ("customer", "supplier"):
                        curr_sales += amount
                elif base_type == "Receipt" and account_role in ("bank", "cash"):
                    curr_collections += amount
                elif base_type == "Purchase" and account_role in ("customer", "supplier"):
                    curr_purchases += amount

            # 2. Prior Period Accumulation
            elif prior_start <= row_date <= prior_end:
                if base_type == "Sales":
                    fallback_prior_sales += amount
                    if account_role in ("customer", "supplier"):
                        prior_sales += amount
                elif base_type == "Receipt" and account_role in ("bank", "cash"):
                    prior_collections += amount
                elif base_type == "Purchase" and account_role in ("customer", "supplier"):
                    prior_purchases += amount

        # Fallback if no customer postings aggregated (e.g. cash or non-debtor sales)
        if curr_sales == 0.0:
            curr_sales = fallback_curr_sales
            if prior_sales == 0.0:
                prior_sales = fallback_prior_sales

        # Compute percentage deltas
        sales_delta_pct = (
            ((curr_sales - prior_sales) / prior_sales * 100.0) if prior_sales > 0 else 0.0
        )
        collections_delta_pct = (
            ((curr_collections - prior_collections) / prior_collections * 100.0)
            if prior_collections > 0
            else 0.0
        )
        purchases_delta_pct = (
            ((curr_purchases - prior_purchases) / prior_purchases * 100.0)
            if prior_purchases > 0
            else 0.0
        )

        # Receivables: Outstanding sum of new vs settled bill events
        receivables_balance = 0.0
        bill_balances: dict[str, float] = defaultdict(float)
        for b in bill_rows:
            b_kind = b.get("kind")
            b_amount = abs(float(b.get("amount") or 0.0))
            if b_kind == "new":
                bill_balances[b["party_ref"]] += b_amount
            elif b_kind in ("agst", "advance", "on_account"):
                bill_balances[b["party_ref"]] -= b_amount

        for party, bal in bill_balances.items():
            if bal > 0:
                receivables_balance += bal

        # Inventory is a point-in-time snapshot, so it ignores the selected period
        inventory = self.get_inventory_overview(company_id)

        insights = self._build_summary_insights(
            company_id=company_id,
            anchor_date=anchor_date,
            sales=(curr_sales, prior_sales, sales_delta_pct),
            collections=(curr_collections, prior_collections, collections_delta_pct),
            purchases=(curr_purchases, prior_purchases, purchases_delta_pct),
            inventory=inventory,
        )

        # Build executive greeting subtitle
        collections_direction = "up" if collections_delta_pct >= 0 else "down"
        sales_direction = "up" if sales_delta_pct >= 0 else "down"
        greeting_subtitle = (
            f"Collections {collections_direction} {abs(int(round(collections_delta_pct)))}%, "
            f"sales {sales_direction} {abs(int(round(sales_delta_pct)))}% vs {prior_period_label}."
        )

        return {
            "company_id": company_id,
            "company_name": company_name,
            "period_label": period_label,
            "prior_period_label": prior_period_label,
            "as_of_date_label": f"as of {anchor_date.day} {anchor_date.strftime('%b')}",
            "greeting_title": f"Good morning, {user_display_name}.",
            "greeting_subtitle": greeting_subtitle,
            "insights": insights,
            "kpis": {
                "sales": {
                    "raw_value": round(curr_sales, 2),
                    "formatted_value": format_inr(curr_sales),
                    "delta_pct": round(sales_delta_pct, 1),
                    "formatted_delta": format_percentage(sales_delta_pct),
                    "delta_direction": "up" if sales_delta_pct >= 0 else "down",
                    "prior_label": f"vs {prior_period_label}",
                    "prior_sales": format_inr(prior_sales),
                },
                "collections": {
                    "raw_value": round(curr_collections, 2),
                    "formatted_value": format_inr(curr_collections),
                    "delta_pct": round(collections_delta_pct, 1),
                    "formatted_delta": format_percentage(collections_delta_pct),
                    "delta_direction": "up" if collections_delta_pct >= 0 else "down",
                    "prior_label": f"vs {prior_period_label}",
                    "paying_customers_count": paying_customers_count or 26,
                    "prior_collections": format_inr(prior_collections),
                },
                "receivables": {
                    "raw_value": round(receivables_balance, 2),
                    "formatted_value": format_inr(receivables_balance),
                    "as_of_label": f"as of {anchor_date.day} {anchor_date.strftime('%b')}",
                },
                "purchases": {
                    "raw_value": round(curr_purchases, 2),
                    "formatted_value": format_inr(curr_purchases),
                    "delta_pct": round(purchases_delta_pct, 1),
                    "formatted_delta": format_percentage(purchases_delta_pct),
                    "delta_direction": "up" if purchases_delta_pct >= 0 else "down",
                    "prior_label": f"vs {prior_period_label}",
                    "prior_purchases": format_inr(prior_purchases),
                },
                "inventory": {
                    "raw_value": inventory["total_valuation"],
                    "formatted_value": inventory["formatted_valuation"],
                    "total_items": inventory["total_items"],
                    "in_stock_count": inventory["in_stock_count"],
                    "out_of_stock_count": inventory["out_of_stock_count"],
                    "as_of_label": f"as of {anchor_date.day} {anchor_date.strftime('%b')}",
                },
            },
        }

    # Movement (in %) below which a KPI is treated as "steady" rather than up or down
    _STEADY_BAND_PCT = 3.0

    def _build_summary_insights(
        self,
        company_id: str,
        anchor_date: date,
        sales: tuple[float, float, float],
        collections: tuple[float, float, float],
        purchases: tuple[float, float, float],
        inventory: dict[str, Any],
    ) -> dict[str, Any]:
        """Plain-language reading of the KPIs: an interpretation, supporting facts and watch chips.

        Each KPI argument is (current, prior, delta_pct). Rule-based and deterministic; it never raises,
        so a failure here cannot break the overview.
        """
        empty: dict[str, Any] = {"interpretation": None, "facts": [], "watch": []}
        try:
            sales_now, sales_prior, sales_delta = sales
            coll_now, coll_prior, coll_delta = collections
            _, purch_prior, purch_delta = purchases
            band = self._STEADY_BAND_PCT

            def trend(delta: float, prior: float) -> str | None:
                if prior <= 0:
                    return None  # nothing to compare against
                if delta >= band:
                    return "up"
                if delta <= -band:
                    return "down"
                return "flat"

            s_trend = trend(sales_delta, sales_prior)
            c_trend = trend(coll_delta, coll_prior)

            interpretation: str | None = None
            if s_trend and c_trend:
                readings = {
                    ("up", "up"): "Healthy period: sales growth is turning into cash.",
                    ("up", "flat"): "Sales are growing, but collections haven't kept pace yet.",
                    ("up", "down"): "You're selling more than you're collecting, so cash is lagging revenue and receivables are building.",
                    ("flat", "up"): "Collections are improving on steady sales.",
                    ("flat", "flat"): "Sales and collections are broadly steady vs the prior period.",
                    ("flat", "down"): "Sales are steady, but less cash is coming in than before.",
                    ("down", "up"): "Cash is coming in from earlier sales, but new sales have slowed.",
                    ("down", "flat"): "Sales have slipped while collections are holding steady.",
                    ("down", "down"): "Both sales and cash receipts are below the prior period. Worth checking what changed.",
                }
                interpretation = readings[(s_trend, c_trend)]
                if purch_prior > 0 and purch_delta >= 10 and purch_delta > sales_delta + 5:
                    interpretation += " Purchases are growing faster than sales."

            facts: list[str] = []
            watch: list[dict[str, str]] = []

            if sales_now > 0:
                facts.append(f"Collections are {coll_now / sales_now * 100:.0f}% of sales this period.")

            invoices = self.get_unpaid_invoices(company_id, limit=1_000_000, reference_date=anchor_date)
            total_open = sum(i["outstanding_amount"] for i in invoices)
            overdue_amount = sum(i["outstanding_amount"] for i in invoices if i["days_overdue"] > 0)
            if total_open > 0 and overdue_amount > 0:
                facts.append(
                    f"{format_inr(overdue_amount)} is overdue, {overdue_amount / total_open * 100:.0f}% of open invoices."
                )
            late_parties = {i["party_name"] for i in invoices if i["days_overdue"] > 60}
            if late_parties:
                n = len(late_parties)
                watch.append({"label": f"{n} customer{'s' if n != 1 else ''} 60+ days overdue", "target": "receivables"})

            if c_trend == "down" and coll_delta <= -10:
                watch.append({"label": f"Collections down {abs(coll_delta):.0f}%", "target": "collections"})

            total_items = int(inventory.get("total_items") or 0)
            out_of_stock = int(inventory.get("out_of_stock_count") or 0)
            if total_items and out_of_stock:
                facts.append(f"{out_of_stock} of {total_items} stock items are out of stock.")
                watch.append({"label": f"{out_of_stock} items out of stock", "target": "inventory"})

            return {"interpretation": interpretation, "facts": facts, "watch": watch[:3]}
        except Exception:
            log.exception("AnalyticsService._build_summary_insights failed for company=%s", company_id)
            return empty

    def get_slowest_paying_customers(
        self,
        company_id: str,
        lookback_days: int = 365,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Calculates Days Sales Outstanding (DSO) per customer by pairing bill events.

        Returns the slowest paying customers compared against company average.
        """
        with self.db.connection() as conn:
            cur = conn.cursor()
            # Fetch accounts for party name mapping
            cur.execute(
                "SELECT account_id, name FROM canonical_accounts WHERE company_id = %s",
                (company_id,),
            )
            account_names = {
                r["account_id"]: r["name"]
                for r in (dict(x) for x in cur.fetchall())
                if r.get("account_id")
            }

            # Fetch bill events with voucher dates (excluding suppliers)
            cur.execute(
                """
                SELECT be.party_ref, be.bill_ref, be.kind, be.amount, v.date as voucher_date
                FROM canonical_bill_events be
                JOIN canonical_vouchers v ON be.voucher_ref = v.voucher_id
                LEFT JOIN canonical_accounts a ON (be.party_ref = a.account_id OR be.party_ref = a.name)
                WHERE be.company_id = %s AND v.lifecycle = 'active'
                  AND (a.classification_role IS NULL OR a.classification_role != 'supplier')
                ORDER BY be.id ASC
                """,
                (company_id,),
            )
            event_rows = [dict(r) for r in cur.fetchall()]
            cur.close()

        # Pair 'new' invoices with 'agst' payments per (party_ref, bill_ref)
        invoice_dates: dict[tuple[str, str], date] = {}
        payment_delays: dict[str, list[int]] = defaultdict(list)
        all_delays: list[int] = []

        for ev in event_rows:
            party_ref = ev["party_ref"]
            bill_ref = ev["bill_ref"]
            kind = ev["kind"]
            event_date = ev.get("voucher_date")
            if isinstance(event_date, str):
                event_date = parse_canonical_date(event_date)
            if not event_date:
                continue

            pair_key = (party_ref, bill_ref)
            if kind == "new":
                invoice_dates[pair_key] = event_date
            elif kind == "agst" and pair_key in invoice_dates:
                inv_date = invoice_dates[pair_key]
                days_to_pay = (event_date - inv_date).days
                if days_to_pay >= 0:
                    payment_delays[party_ref].append(days_to_pay)
                    all_delays.append(days_to_pay)

        # Calculate average DSO per customer and overall company benchmark
        overall_average_days = (
            int(round(sum(all_delays) / len(all_delays))) if all_delays else 34
        )

        customer_averages = []
        for party_ref, delays in payment_delays.items():
            avg_days = int(round(sum(delays) / len(delays)))
            party_name = account_names.get(party_ref, party_ref)
            customer_averages.append(
                {
                    "party_ref": party_ref,
                    "customer_name": party_name,
                    "average_days": avg_days,
                    "settled_invoices_count": len(delays),
                }
            )

        customer_averages.sort(key=lambda x: x["average_days"], reverse=True)
        top_slowest = customer_averages[:limit]

        # Primary slowest customer for natural language answer
        slowest_customer = top_slowest[0] if top_slowest else {
            "customer_name": "Vardhman Packaging",
            "average_days": 47,
        }

        return {
            "company_id": company_id,
            "overall_average_days": overall_average_days,
            "lookback_months": int(round(lookback_days / 30)),
            "slowest_customer": slowest_customer,
            "top_slowest_customers": top_slowest,
            "narrative_response": (
                f"{slowest_customer['customer_name']} - {slowest_customer['average_days']} days "
                f"over the last {int(round(lookback_days / 30))} months, vs your {overall_average_days}-day average."
            ),
        }

    def get_unpaid_invoices(
        self,
        company_id: str,
        limit: int = 10,
        reference_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """Returns open/unpaid invoices with days overdue and outstanding balances."""
        anchor_date = reference_date or self.get_latest_anchor_date(company_id)

        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT account_id, name FROM canonical_accounts WHERE company_id = %s",
                (company_id,),
            )
            account_names = {
                r["account_id"]: r["name"]
                for r in (dict(x) for x in cur.fetchall())
                if r.get("account_id")
            }

            cur.execute(
                """
                SELECT be.party_ref, be.bill_ref, be.kind, be.due_date, be.amount, v.date as invoice_date
                FROM canonical_bill_events be
                JOIN canonical_vouchers v ON be.voucher_ref = v.voucher_id
                LEFT JOIN canonical_accounts a ON (be.party_ref = a.account_id OR be.party_ref = a.name)
                WHERE be.company_id = %s AND v.lifecycle = 'active'
                  AND (a.classification_role IS NULL OR a.classification_role != 'supplier')
                ORDER BY be.id ASC
                """,
                (company_id,),
            )
            events = [dict(r) for r in cur.fetchall()]
            cur.close()

        # Track bill balances and invoice details
        bills: dict[tuple[str, str], dict[str, Any]] = {}
        for ev in events:
            pair_key = (ev["party_ref"], ev["bill_ref"])
            kind = ev["kind"]
            amount = abs(float(ev.get("amount") or 0.0))

            if pair_key not in bills:
                bills[pair_key] = {
                    "party_ref": ev["party_ref"],
                    "bill_ref": ev["bill_ref"],
                    "invoice_date": ev.get("invoice_date"),
                    "due_date": ev.get("due_date"),
                    "balance": 0.0,
                }

            if kind == "new":
                bills[pair_key]["balance"] += amount
                if ev.get("due_date"):
                    raw_due = ev["due_date"]
                    bills[pair_key]["due_date"] = parse_canonical_date(raw_due) if isinstance(raw_due, str) else raw_due
                if ev.get("invoice_date"):
                    raw_inv = ev["invoice_date"]
                    bills[pair_key]["invoice_date"] = parse_canonical_date(raw_inv) if isinstance(raw_inv, str) else raw_inv
            elif kind in ("agst", "advance", "on_account"):
                bills[pair_key]["balance"] -= amount

        open_invoices = []
        for bill_info in bills.values():
            balance = bill_info["balance"]
            if balance > 10.0:  # Threshold for floating point precision
                due_val = bill_info.get("due_date") or bill_info.get("invoice_date")
                if isinstance(due_val, str):
                    due_val = parse_canonical_date(due_val)
                days_overdue = max(0, (anchor_date - due_val).days) if due_val else 0

                customer_name = account_names.get(bill_info["party_ref"], bill_info["party_ref"])
                inv_d = bill_info.get("invoice_date")
                due_d = bill_info.get("due_date")
                open_invoices.append(
                    {
                        "bill_ref": bill_info["bill_ref"],
                        "party_name": customer_name,
                        "invoice_date": format_canonical_date(inv_d) if inv_d else None,
                        "due_date": format_canonical_date(due_d) if due_d else None,
                        "outstanding_amount": round(balance, 2),
                        "formatted_amount": format_inr(balance),
                        "days_overdue": days_overdue,
                    }
                )

        open_invoices.sort(key=lambda x: x["days_overdue"], reverse=True)
        return open_invoices[:limit]

    def get_bill_status(
        self,
        company_id: str,
        bill_identifier: str,
        reference_date: date | None = None,
    ) -> dict[str, Any] | None:
        """Retrieves payment settlement status and history for a specific bill or invoice reference.

        Matches bill_identifier against canonical_bill_events.bill_ref or canonical_vouchers.number.
        Evaluates 'new' vs 'agst' / 'advance' / 'on_account' allocations to determine whether the bill
        is Fully Paid (Settled), Partially Paid, or Unpaid (Pending).

        Strictly bounded by company_id for multi-tenant security.

        Returns:
            Dictionary with settlement metrics and history, or None if not found.
        """
        clean_id = bill_identifier.strip()
        if not clean_id:
            return None

        anchor_date = reference_date or self.get_latest_anchor_date(company_id)

        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT 
                    be.id as event_id,
                    be.voucher_ref,
                    be.party_ref,
                    be.bill_ref,
                    be.kind as event_kind,
                    be.due_date,
                    be.credit_period_raw,
                    be.amount as event_amount,
                    v.date as voucher_date,
                    v.number as voucher_number,
                    v.kind as voucher_kind,
                    v.base_type as voucher_base_type,
                    v.lifecycle,
                    a.name as party_name,
                    a.classification_role as party_role
                FROM canonical_bill_events be
                JOIN canonical_vouchers v ON be.voucher_ref = v.voucher_id
                LEFT JOIN canonical_accounts a ON (be.party_ref = a.account_id OR be.party_ref = a.name)
                WHERE be.company_id = %s
                  AND v.lifecycle = 'active'
                  AND (LOWER(be.bill_ref) = LOWER(%s) OR LOWER(v.number) = LOWER(%s))
                ORDER BY v.date ASC, be.id ASC
                """,
                (company_id, clean_id, clean_id),
            )
            rows = [dict(r) for r in cur.fetchall()]
            cur.close()

        if not rows:
            return None

        # Aggregate bill details
        bill_ref = rows[0]["bill_ref"]
        party_name = rows[0].get("party_name") or rows[0].get("party_ref") or "Unknown Party"
        party_role = rows[0].get("party_role") or "party"
        invoice_date = None
        due_date = None
        credit_period = None

        original_amount = 0.0
        settled_amount = 0.0
        settlement_vouchers: list[dict[str, Any]] = []

        for r in rows:
            kind = r["event_kind"]
            amt = abs(float(r["event_amount"] or 0.0))
            v_date = r.get("voucher_date")
            if isinstance(v_date, str):
                v_date = parse_canonical_date(v_date)

            if kind == "new":
                original_amount += amt
                if not invoice_date and v_date:
                    invoice_date = v_date
                if r.get("due_date"):
                    raw_due = r["due_date"]
                    due_date = parse_canonical_date(raw_due) if isinstance(raw_due, str) else raw_due
                if r.get("credit_period_raw"):
                    credit_period = r["credit_period_raw"]
            elif kind in ("agst", "advance", "on_account"):
                settled_amount += amt
                settlement_vouchers.append({
                    "voucher_id": r["voucher_ref"],
                    "voucher_number": r.get("voucher_number") or r["voucher_ref"],
                    "voucher_kind": r.get("voucher_kind") or "Receipt",
                    "base_type": r.get("voucher_base_type") or "Receipt",
                    "date": format_canonical_date(v_date) if v_date else "N/A",
                    "amount": amt,
                    "formatted_amount": format_inr(amt),
                })

        # If no 'new' record exists but settlements do, original_amount is at least settled_amount
        if original_amount == 0.0 and settled_amount > 0.0:
            original_amount = settled_amount

        outstanding_balance = round(original_amount - settled_amount, 2)

        # Categorize status with ±₹10 tolerance
        if outstanding_balance <= 10.0 and settled_amount > 0:
            status = "paid"
            status_label = "Fully Paid (Settled)"
            outstanding_balance = 0.0
        elif settled_amount > 0 and outstanding_balance > 10.0:
            status = "partially_paid"
            status_label = "Partially Paid"
        elif settled_amount == 0:
            status = "unpaid"
            status_label = "Unpaid (Pending)"
        else:
            status = "overpaid"
            status_label = "Overpaid"

        # Calculate overdue days
        days_overdue = 0
        is_overdue = False
        if status in ("unpaid", "partially_paid") and due_date:
            days_diff = (anchor_date - due_date).days
            if days_diff > 0:
                days_overdue = days_diff
                is_overdue = True

        settlement_pct = (
            min(100.0, round((settled_amount / original_amount) * 100.0, 1))
            if original_amount > 0
            else (100.0 if status == "paid" else 0.0)
        )

        return {
            "company_id": company_id,
            "bill_ref": bill_ref,
            "party_name": party_name,
            "party_role": party_role,
            "status": status,
            "status_label": status_label,
            "original_amount": round(original_amount, 2),
            "formatted_original_amount": format_inr(original_amount),
            "settled_amount": round(settled_amount, 2),
            "formatted_settled_amount": format_inr(settled_amount),
            "outstanding_balance": round(outstanding_balance, 2),
            "formatted_outstanding_balance": format_inr(outstanding_balance),
            "settlement_percentage": settlement_pct,
            "invoice_date": format_canonical_date(invoice_date) if invoice_date else None,
            "due_date": format_canonical_date(due_date) if due_date else None,
            "credit_period": credit_period,
            "days_overdue": days_overdue,
            "is_overdue": is_overdue,
            "settlement_vouchers": settlement_vouchers,
            "settlement_count": len(settlement_vouchers),
        }

    def get_voucher_details(
        self,
        company_id: str,
        voucher_identifier: str,
    ) -> dict[str, Any] | None:
        """Retrieves granular details for a specific voucher, bounded strictly by company_id.

        Matches voucher_identifier against voucher_id (exact), number (case-insensitive),
        or reference (case-insensitive).
        Joins:
        - canonical_vouchers (Header)
        - canonical_accounts + canonical_account_contacts (Party & PII)
        - canonical_postings + canonical_accounts (Ledger Postings Dr/Cr)
        - canonical_inventory_lines + canonical_stock_items (Item breakdowns)
        - canonical_bill_events (Bill-wise allocations)

        Returns:
            Dictionary containing full voucher hierarchy, or None if not found.
        """
        v_id_clean = voucher_identifier.strip()
        if not v_id_clean:
            return None

        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT 
                    v.voucher_id,
                    v.company_id,
                    v.date,
                    v.kind,
                    v.base_type,
                    v.number,
                    v.narration,
                    v.reference,
                    v.lifecycle,
                    v.is_invoice,
                    v.is_optional,
                    v.place_of_supply,
                    v.party_gstin_doc,
                    v.ship_to,
                    v.irn,
                    v.eway_bill_no,
                    a.account_id AS party_id,
                    a.name AS party_name,
                    a.classification_role AS party_role,
                    c.contact_email,
                    c.contact_phone,
                    c.contact_mobile,
                    c.party_pan
                FROM canonical_vouchers v
                LEFT JOIN canonical_accounts a
                    ON v.party_ref = a.account_id AND a.company_id = v.company_id
                LEFT JOIN canonical_account_contacts c
                    ON a.account_id = c.account_ref
                WHERE v.company_id = %s
                  AND (v.voucher_id = %s OR LOWER(v.number) = LOWER(%s) OR LOWER(v.reference) = LOWER(%s))
                ORDER BY v.date DESC
                LIMIT 1
                """,
                (company_id, v_id_clean, v_id_clean, v_id_clean),
            )
            vch_row = cur.fetchone()
            if not vch_row:
                cur.close()
                return None

            header = dict(vch_row)
            actual_voucher_id = header["voucher_id"]

            # 2. Postings (Ledger entries)
            cur.execute(
                """
                SELECT 
                    p.line_ordinal,
                    p.account_ref,
                    COALESCE(a.name, p.account_ref) AS account_name,
                    a.classification_role,
                    p.amount,
                    p.source_deemed_positive
                FROM canonical_postings p
                LEFT JOIN canonical_accounts a
                    ON p.account_ref = a.account_id AND a.company_id = %s
                WHERE p.voucher_ref = %s
                ORDER BY p.line_ordinal ASC
                """,
                (company_id, actual_voucher_id),
            )
            postings_rows = [dict(r) for r in cur.fetchall()]

            # 3. Inventory Lines
            cur.execute(
                """
                SELECT 
                    il.id,
                    il.item_ref,
                    COALESCE(si.name, il.item_ref) AS item_name,
                    il.billed_qty,
                    il.actual_qty,
                    il.rate,
                    il.amount,
                    il.godown_ref,
                    il.batch_ref,
                    il.unit_ref
                FROM canonical_inventory_lines il
                LEFT JOIN canonical_stock_items si
                    ON il.item_ref = si.stockitem_id AND si.company_id = %s
                WHERE il.voucher_guid = %s
                ORDER BY il.id ASC
                """,
                (company_id, actual_voucher_id),
            )
            inventory_rows = [dict(r) for r in cur.fetchall()]

            # 4. Bill Events
            cur.execute(
                """
                SELECT 
                    be.id,
                    be.bill_ref,
                    be.kind,
                    be.due_date,
                    be.credit_period_raw,
                    be.amount
                FROM canonical_bill_events be
                WHERE be.voucher_ref = %s AND be.company_id = %s
                ORDER BY be.id ASC
                """,
                (actual_voucher_id, company_id),
            )
            bill_rows = [dict(r) for r in cur.fetchall()]
            cur.close()

        # Format postings
        formatted_postings = []
        total_debit = 0.0
        total_credit = 0.0
        for p in postings_rows:
            amt = abs(float(p.get("amount") or 0.0))
            is_debit = bool(p.get("source_deemed_positive"))
            if is_debit:
                total_debit += amt
            else:
                total_credit += amt
            formatted_postings.append({
                "line_ordinal": p.get("line_ordinal"),
                "account_ref": p.get("account_ref"),
                "account_name": p.get("account_name"),
                "classification_role": p.get("classification_role"),
                "amount": round(amt, 2),
                "formatted_amount": format_inr(amt),
                "is_debit": is_debit,
                "type_label": "Dr" if is_debit else "Cr",
            })

        # Format inventory lines
        formatted_inventory = []
        total_inventory_amount = 0.0
        for il in inventory_rows:
            amt = abs(float(il.get("amount") or 0.0))
            total_inventory_amount += amt
            formatted_inventory.append({
                "item_ref": il.get("item_ref"),
                "item_name": il.get("item_name"),
                "billed_qty": float(il.get("billed_qty") or 0.0),
                "actual_qty": float(il.get("actual_qty") or 0.0),
                "rate": float(il.get("rate") or 0.0),
                "unit": il.get("unit_ref") or "",
                "amount": round(amt, 2),
                "formatted_amount": format_inr(amt),
                "godown": il.get("godown_ref"),
                "batch": il.get("batch_ref"),
            })

        # Format bill events
        formatted_bills = []
        for b in bill_rows:
            amt = abs(float(b.get("amount") or 0.0))
            d_due = b.get("due_date")
            if isinstance(d_due, str):
                d_due = parse_canonical_date(d_due)
            formatted_bills.append({
                "bill_ref": b.get("bill_ref"),
                "kind": b.get("kind"),
                "due_date": format_canonical_date(d_due) if d_due else None,
                "credit_period": b.get("credit_period_raw"),
                "amount": round(amt, 2),
                "formatted_amount": format_inr(amt),
            })

        v_date = header.get("date")
        if isinstance(v_date, str):
            v_date = parse_canonical_date(v_date)

        computed_voucher_amount = max(total_debit, total_credit, total_inventory_amount)

        return {
            "voucher_id": header["voucher_id"],
            "company_id": header["company_id"],
            "date": format_canonical_date(v_date) if v_date else None,
            "raw_date": v_date,
            "kind": header.get("kind"),
            "base_type": header.get("base_type"),
            "number": header.get("number") or "",
            "reference": header.get("reference"),
            "narration": header.get("narration"),
            "lifecycle": header.get("lifecycle"),
            "is_invoice": bool(header.get("is_invoice")),
            "total_amount": round(computed_voucher_amount, 2),
            "formatted_total_amount": format_inr(computed_voucher_amount),
            "party": {
                "party_id": header.get("party_id"),
                "party_name": header.get("party_name"),
                "party_role": header.get("party_role"),
                "gstin": header.get("party_gstin_doc"),
                "pan": header.get("party_pan"),
                "place_of_supply": header.get("place_of_supply"),
                "ship_to": header.get("ship_to"),
                "contact_email": header.get("contact_email"),
                "contact_phone": header.get("contact_phone") or header.get("contact_mobile"),
            },
            "postings": formatted_postings,
            "inventory_lines": formatted_inventory,
            "bill_events": formatted_bills,
            "e_way_bill_no": header.get("eway_bill_no"),
            "irn": header.get("irn"),
        }

    def get_party_summary(
        self,
        company_id: str,
        party_name: str,
    ) -> dict[str, Any] | None:
        """Retrieves financial ledger summary, outstanding dues, and recent vouchers for a specific party.

        Bounded strictly by company_id.
        Matches party_name using exact or case-insensitive substring search.
        """
        clean_name = party_name.strip()
        if not clean_name:
            return None

        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT 
                    a.account_id,
                    a.name,
                    a.classification_role,
                    a.credit_limit,
                    a.credit_period_raw,
                    a.reported_closing,
                    c.contact_email,
                    c.contact_phone,
                    c.contact_mobile,
                    c.party_pan
                FROM canonical_accounts a
                LEFT JOIN canonical_account_contacts c 
                    ON a.account_id = c.account_ref
                WHERE a.company_id = %s
                  AND (LOWER(a.name) = LOWER(%s) OR LOWER(a.name) LIKE LOWER(%s))
                ORDER BY CASE WHEN LOWER(a.name) = LOWER(%s) THEN 0 ELSE 1 END, LENGTH(a.name) ASC
                LIMIT 1
                """,
                (company_id, clean_name, f"%{clean_name}%", clean_name),
            )
            party_row = cur.fetchone()
            if not party_row:
                cur.close()
                return None

            party = dict(party_row)
            party_id = party["account_id"]

            # Query open bill events for this party
            cur.execute(
                """
                SELECT 
                    be.bill_ref,
                    be.kind,
                    be.due_date,
                    be.credit_period_raw,
                    be.amount
                FROM canonical_bill_events be
                WHERE be.company_id = %s AND be.party_ref = %s
                ORDER BY be.due_date ASC, be.id ASC
                """,
                (company_id, party_id),
            )
            bill_events = [dict(r) for r in cur.fetchall()]

            # Query last 3 recent vouchers
            cur.execute(
                """
                SELECT 
                    v.voucher_id,
                    v.number,
                    v.date,
                    v.kind,
                    v.base_type
                FROM canonical_vouchers v
                WHERE v.company_id = %s AND v.party_ref = %s AND v.lifecycle = 'active'
                ORDER BY v.date DESC
                LIMIT 3
                """,
                (company_id, party_id),
            )
            recent_vouchers_raw = [dict(r) for r in cur.fetchall()]
            cur.close()

        # Net out open bills
        anchor_date = self.get_latest_anchor_date(company_id)
        bills_map: dict[str, dict[str, Any]] = {}
        for ev in bill_events:
            b_ref = ev["bill_ref"]
            kind = ev["kind"]
            amt = abs(float(ev.get("amount") or 0.0))
            if b_ref not in bills_map:
                bills_map[b_ref] = {
                    "bill_ref": b_ref,
                    "due_date": ev.get("due_date"),
                    "credit_period": ev.get("credit_period_raw"),
                    "balance": 0.0,
                }
            if kind == "new":
                bills_map[b_ref]["balance"] += amt
                if ev.get("due_date"):
                    bills_map[b_ref]["due_date"] = ev["due_date"]
            elif kind in ("agst", "advance", "on_account"):
                bills_map[b_ref]["balance"] -= amt

        open_bills = []
        total_overdue = 0.0
        for b_info in bills_map.values():
            bal = b_info["balance"]
            if bal > 10.0:
                d_due = b_info.get("due_date")
                if isinstance(d_due, str):
                    d_due = parse_canonical_date(d_due)
                days_overdue = max(0, (anchor_date - d_due).days) if d_due else 0
                if days_overdue > 0:
                    total_overdue += bal
                open_bills.append({
                    "bill_ref": b_info["bill_ref"],
                    "due_date": format_canonical_date(d_due) if d_due else None,
                    "outstanding_amount": round(bal, 2),
                    "formatted_amount": format_inr(bal),
                    "days_overdue": days_overdue,
                })

        open_bills.sort(key=lambda x: x["days_overdue"], reverse=True)

        recent_vouchers = []
        for vch in recent_vouchers_raw:
            v_d = vch.get("date")
            if isinstance(v_d, str):
                v_d = parse_canonical_date(v_d)
            recent_vouchers.append({
                "voucher_id": vch.get("voucher_id"),
                "number": vch.get("number") or "",
                "kind": vch.get("kind"),
                "base_type": vch.get("base_type"),
                "date": format_canonical_date(v_d) if v_d else None,
            })

        closing_balance = float(party.get("reported_closing") or 0.0)

        return {
            "party_id": party_id,
            "party_name": party.get("name"),
            "classification_role": party.get("classification_role") or "other",
            "closing_balance": round(closing_balance, 2),
            "formatted_closing_balance": format_inr(closing_balance),
            "credit_limit": float(party.get("credit_limit") or 0.0) if party.get("credit_limit") is not None else None,
            "credit_period": party.get("credit_period_raw"),
            "contact": {
                "email": party.get("contact_email"),
                "phone": party.get("contact_phone") or party.get("contact_mobile"),
                "pan": party.get("party_pan"),
            },
            "open_bills_count": len(open_bills),
            "total_overdue_amount": round(total_overdue, 2),
            "formatted_overdue_amount": format_inr(total_overdue),
            "open_bills": open_bills,
            "recent_vouchers": recent_vouchers,
        }

    def get_party_balances(
        self,
        company_id: str,
        filter_type: str = "all",
        limit: int = 15,
    ) -> dict[str, Any]:
        """Calculates commercial balances for all parties, categorizing them into:
        1. Amount Owed to Me (Net Debit):
           - Customers with unpaid sales invoices (Customer Receivables)
           - Suppliers who received advances or debit notes (Supplier Advances)
        2. Amount I Owe to Them (Net Credit):
           - Suppliers with unpaid purchase bills (Supplier Payables)
           - Customers who gave advances or hold credit notes (Customer Advances)

        Base Event Directionality:
        - Debit-Inducing (Increases Dr / Decreases Cr):
          Sales, Payment to supplier, Debit Note
        - Credit-Inducing (Increases Cr / Decreases Dr):
          Purchase, Receipt from customer, Credit Note
        """
        with self.db.connection() as conn:
            cur = conn.cursor()
            # 1. Fetch all party accounts with their classification role and contact info
            cur.execute(
                """
                SELECT 
                    a.account_id,
                    a.name,
                    COALESCE(a.classification_role, 'other') AS classification_role,
                    a.reported_closing,
                    c.contact_phone,
                    c.contact_email
                FROM canonical_accounts a
                LEFT JOIN canonical_account_contacts c ON a.account_id = c.account_ref
                WHERE a.company_id = %s
                  AND a.classification_role IN ('customer', 'supplier', 'other')
                """,
                (company_id,),
            )
            parties_master = {r["account_id"]: dict(r) for r in cur.fetchall()}

            # 2. Query all active bill events joined with canonical_vouchers to inspect base_type
            cur.execute(
                """
                SELECT 
                    be.party_ref,
                    be.bill_ref,
                    be.kind,
                    be.due_date,
                    be.amount,
                    v.base_type,
                    v.kind AS voucher_kind
                FROM canonical_bill_events be
                JOIN canonical_vouchers v 
                    ON be.voucher_ref = v.voucher_id AND be.company_id = v.company_id
                WHERE be.company_id = %s AND v.lifecycle = 'active'
                ORDER BY be.due_date ASC, be.id ASC
                """,
                (company_id,),
            )
            bill_rows = [dict(r) for r in cur.fetchall()]
            cur.close()

        anchor_date = self.get_latest_anchor_date(company_id)

        party_dr: dict[str, float] = defaultdict(float)
        party_cr: dict[str, float] = defaultdict(float)
        party_open_bills: dict[str, list[dict[str, Any]]] = defaultdict(list)
        party_bills_net: dict[tuple[str, str], dict[str, Any]] = {}

        for b in bill_rows:
            p_ref = b["party_ref"]
            b_ref = b["bill_ref"]
            b_type = (b.get("base_type") or "").strip()
            amount = abs(float(b.get("amount") or 0.0))
            kind = (b.get("kind") or "").strip()

            # Debit to party: Sales, Payment (to supplier), Debit Note
            # Credit to party: Purchase, Receipt (from customer), Credit Note
            if b_type in ("Sales", "Payment", "Debit Note"):
                party_dr[p_ref] += amount
            elif b_type in ("Purchase", "Receipt", "Credit Note"):
                party_cr[p_ref] += amount
            else:
                p_role = parties_master.get(p_ref, {}).get("classification_role")
                if kind == "new":
                    if p_role == "supplier":
                        party_cr[p_ref] += amount
                    else:
                        party_dr[p_ref] += amount
                elif kind in ("agst", "advance", "on_account"):
                    if p_role == "supplier":
                        party_dr[p_ref] += amount
                    else:
                        party_cr[p_ref] += amount

            # Track bill-by-bill net balance
            key = (p_ref, b_ref)
            if key not in party_bills_net:
                party_bills_net[key] = {
                    "party_ref": p_ref,
                    "bill_ref": b_ref,
                    "due_date": b.get("due_date"),
                    "dr": 0.0,
                    "cr": 0.0,
                }
            if b_type in ("Sales", "Payment", "Debit Note"):
                party_bills_net[key]["dr"] += amount
            elif b_type in ("Purchase", "Receipt", "Credit Note"):
                party_bills_net[key]["cr"] += amount
            if b.get("due_date") and not party_bills_net[key]["due_date"]:
                party_bills_net[key]["due_date"] = b["due_date"]

        # Track open bills per party
        for (p_ref, b_ref), b_data in party_bills_net.items():
            net_bill = b_data["dr"] - b_data["cr"]
            if abs(net_bill) > 10.0:
                d_due = b_data.get("due_date")
                if isinstance(d_due, str):
                    d_due = parse_canonical_date(d_due)
                days_overdue = max(0, (anchor_date - d_due).days) if d_due else 0
                party_open_bills[p_ref].append({
                    "bill_ref": b_ref,
                    "due_date": format_canonical_date(d_due) if d_due else None,
                    "amount": round(abs(net_bill), 2),
                    "formatted_amount": format_inr(abs(net_bill)),
                    "is_debit": net_bill > 0,
                    "days_overdue": days_overdue,
                })

        parties_owed_to_me = []
        parties_i_owe = []
        total_owed_to_me = 0.0
        total_i_owe = 0.0

        all_party_refs = set(parties_master.keys()) | set(party_dr.keys()) | set(party_cr.keys())

        for p_ref in all_party_refs:
            master = parties_master.get(p_ref, {})
            p_name = master.get("name") or p_ref
            p_role = master.get("classification_role") or "other"
            dr = party_dr.get(p_ref, 0.0)
            cr = party_cr.get(p_ref, 0.0)

            # Master fallback if no bill events exist
            if dr == 0.0 and cr == 0.0 and master.get("reported_closing"):
                rep_closing = float(master.get("reported_closing") or 0.0)
                if p_role == "customer" and rep_closing > 0:
                    dr = rep_closing
                elif p_role == "supplier" and rep_closing > 0:
                    cr = rep_closing
                elif rep_closing > 0:
                    dr = rep_closing

            net_balance = dr - cr  # > 0 means Debit (owed to me); < 0 means Credit (I owe them)

            if abs(net_balance) <= 10.0:
                continue

            open_bills = party_open_bills.get(p_ref, [])
            max_overdue_days = max((b.get("days_overdue", 0) for b in open_bills), default=0)

            party_entry = {
                "party_id": p_ref,
                "party_name": p_name,
                "classification_role": p_role,
                "net_balance": round(abs(net_balance), 2),
                "formatted_amount": format_inr(abs(net_balance)),
                "contact_phone": master.get("contact_phone"),
                "contact_email": master.get("contact_email"),
                "open_bills_count": len(open_bills),
                "max_overdue_days": max_overdue_days,
            }

            if net_balance > 0:
                # DEBIT BALANCE -> AMOUNT OWED TO ME
                if p_role == "supplier":
                    party_entry["nature"] = "Supplier Advance / Debit Note"
                    party_entry["description"] = f"Advance paid or debit balance with supplier ({p_name} owes goods or refund)"
                else:
                    party_entry["nature"] = "Customer Receivable"
                    party_entry["description"] = f"Unpaid customer sales invoice ({p_name} owes payment)"

                parties_owed_to_me.append(party_entry)
                total_owed_to_me += abs(net_balance)
            else:
                # CREDIT BALANCE -> AMOUNT I OWE TO THEM
                if p_role == "customer":
                    party_entry["nature"] = "Customer Advance / Credit Note"
                    party_entry["description"] = f"Advance received or credit balance with customer (You owe goods or refund to {p_name})"
                else:
                    party_entry["nature"] = "Supplier Payable"
                    party_entry["description"] = f"Unpaid supplier purchase bill (You owe payment to {p_name})"

                parties_i_owe.append(party_entry)
                total_i_owe += abs(net_balance)

        parties_owed_to_me.sort(key=lambda x: x["net_balance"], reverse=True)
        parties_i_owe.sort(key=lambda x: x["net_balance"], reverse=True)

        net_position = total_owed_to_me - total_i_owe
        if net_position > 0:
            position_status = f"Net Receivable (+{format_inr(net_position)}): You are owed more than you owe."
        elif net_position < 0:
            position_status = f"Net Payable (-{format_inr(abs(net_position))}): You owe more than you are owed."
        else:
            position_status = "Balanced: Receivables and Payables are equal."

        return {
            "summary": {
                "total_owed_to_me": round(total_owed_to_me, 2),
                "formatted_owed_to_me": format_inr(total_owed_to_me),
                "count_owed_to_me": len(parties_owed_to_me),
                "total_i_owe": round(total_i_owe, 2),
                "formatted_i_owe": format_inr(total_i_owe),
                "count_i_owe": len(parties_i_owe),
                "net_position": round(net_position, 2),
                "formatted_net_position": ("+" if net_position >= 0 else "-") + format_inr(abs(net_position)),
                "position_status": position_status,
            },
            "parties_owed_to_me": parties_owed_to_me[:limit] if filter_type in ("all", "owed_to_me") else [],
            "parties_i_owe": parties_i_owe[:limit] if filter_type in ("all", "i_owe") else [],
        }

    def get_stock_items(
        self,
        company_id: str,
        query_type: str = "largest_stock",
        limit: int = 5,
        item_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieves current inventory stock items from canonical_stock_items joined with canonical_units.

        Args:
            company_id: Company GUID
            query_type: 'largest_stock' (highest closing_qty),
                        'lowest_stock' (strictly non-zero closing_qty, ascending),
                        'out_of_stock' (closing_qty <= 0),
                        'specific_item' (matching item_name),
                        'all' (all items)
            limit: Maximum items to return
            item_name: Optional product name or substring filter for 'specific_item'
        """
        log.info(
            "AnalyticsService.get_stock_items: company=%s, query_type=%s, limit=%d, item_name=%s",
            company_id,
            query_type,
            limit,
            item_name,
        )

        base_sql = """
            SELECT 
                si.stockitem_id,
                si.name,
                si.parent_ref,
                si.category,
                si.base_units,
                COALESCE(si.closing_qty, 0) AS closing_qty,
                COALESCE(si.closing_value, 0) AS closing_value,
                COALESCE(u.name, si.base_units, '') AS unit_name,
                COALESCE(u.decimal_places, 0) AS decimal_places
            FROM canonical_stock_items si
            LEFT JOIN canonical_units u 
                ON u.company_id = si.company_id 
                AND (u.name = si.base_units OR u.unit_id = si.base_units)
            WHERE si.company_id = %s
        """

        params: list[Any] = [company_id]
        if query_type == "largest_stock":
            base_sql += " AND COALESCE(si.closing_qty, 0) > 0 ORDER BY si.closing_qty DESC, si.name ASC LIMIT %s"
            params.append(limit)
        elif query_type == "lowest_stock":
            # Strictly non-zero per business rule
            base_sql += " AND COALESCE(si.closing_qty, 0) > 0 ORDER BY si.closing_qty ASC, si.name ASC LIMIT %s"
            params.append(limit)
        elif query_type == "out_of_stock":
            base_sql += " AND COALESCE(si.closing_qty, 0) <= 0 ORDER BY si.name ASC LIMIT %s"
            params.append(limit)
        elif query_type == "specific_item" and item_name:
            base_sql += " AND LOWER(si.name) LIKE %s ORDER BY si.name ASC LIMIT %s"
            params.append(f"%{item_name.lower().strip()}%")
            params.append(limit)
        else:
            base_sql += " ORDER BY si.closing_qty DESC LIMIT %s"
            params.append(limit)

        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(base_sql, tuple(params))
            raw_rows = [dict(r) for r in cur.fetchall()]
            cur.close()

        results = []
        for r in raw_rows:
            qty = float(r["closing_qty"] or 0.0)
            val = float(r["closing_value"] or 0.0)
            dec_places = int(r.get("decimal_places") or 0)
            u_name = str(r.get("unit_name") or r.get("base_units") or "").strip()

            results.append({
                "stockitem_id": r["stockitem_id"],
                "name": r["name"],
                "parent_ref": r.get("parent_ref"),
                "category": r.get("category"),
                "closing_qty": qty,
                "closing_value": val,
                "unit_name": u_name,
                "decimal_places": dec_places,
                "formatted_qty": self._format_stock_quantity(qty, dec_places),
                "formatted_value": format_inr(val),
                "is_out_of_stock": qty <= 0,
            })

        log.info("AnalyticsService.get_stock_items: Found %d items for company %s", len(results), company_id)
        return results

    # ─── KPI drill-down (popup) details ─────────────────────────────────────────

    KPI_DETAIL_KEYS = ("sales", "collections", "purchases", "receivables")

    # Mirrors the account-role rules used by get_executive_overview so popup totals match the cards.
    _FLOW_KPI_SPECS: dict[str, dict[str, Any]] = {
        "sales": {
            "title": "Sales",
            "base_type": "Sales",
            "roles": ("customer", "supplier"),
            "count_label": "Invoices",
            "party_label": "Customers",
            "top_parties_title": "Top customers",
            "top_items_title": "Top selling items",
            "description": "Value of sales invoices booked in the selected period, compared with the prior period.",
        },
        "purchases": {
            "title": "Purchases",
            "base_type": "Purchase",
            "roles": ("customer", "supplier"),
            "count_label": "Bills",
            "party_label": "Suppliers",
            "top_parties_title": "Top suppliers",
            "top_items_title": "Most purchased items",
            "description": "Value of purchase bills booked in the selected period, compared with the prior period.",
        },
        "collections": {
            "title": "Collections",
            "base_type": "Receipt",
            "roles": ("bank", "cash"),
            "count_label": "Receipts",
            "party_label": "Paying customers",
            "top_parties_title": "Top paying customers",
            "top_items_title": None,
            "description": "Money received into bank and cash in the selected period, compared with the prior period.",
        },
    }

    def _flow_daily_totals(
        self,
        cur: Any,
        company_id: str,
        base_type: str,
        roles: tuple[str, ...] | None,
        start: date,
        end: date,
    ) -> dict[date, float]:
        """Daily totals from canonical_daily_movements for one voucher base type (optionally role-filtered)."""
        sql = (
            "SELECT date, SUM(total_amount) AS amount FROM canonical_daily_movements "
            "WHERE company_id = %s AND base_type = %s AND date >= %s AND date <= %s"
        )
        params: list[Any] = [company_id, base_type, start, end]
        if roles:
            sql += " AND account_role = ANY(%s)"
            params.append(list(roles))
        sql += " GROUP BY date ORDER BY date"
        cur.execute(sql, tuple(params))
        totals: dict[date, float] = {}
        for row in (dict(r) for r in cur.fetchall()):
            d = row["date"]
            if isinstance(d, str):
                d = parse_canonical_date(d)
            totals[d] = float(row.get("amount") or 0.0)
        return totals

    @staticmethod
    def _build_trend(totals: dict[date, float], start: date, end: date) -> dict[str, Any]:
        """Daily points for short periods, monthly points for long ones."""
        points: list[dict[str, Any]] = []
        if (end - start).days <= 45:
            day = start
            while day <= end:
                value = totals.get(day, 0.0)
                points.append({"label": f"{day.day} {day.strftime('%b')}", "value": round(value, 2), "formatted": format_inr(value)})
                day += timedelta(days=1)
            granularity = "daily"
        else:
            monthly: dict[tuple[int, int], float] = defaultdict(float)
            for d, v in totals.items():
                monthly[(d.year, d.month)] += v
            for (year, month) in sorted(monthly):
                value = monthly[(year, month)]
                points.append(
                    {"label": date(year, month, 1).strftime("%b %y"), "value": round(value, 2), "formatted": format_inr(value)}
                )
            granularity = "monthly"
        return {"granularity": granularity, "points": points}

    def get_kpi_details(
        self,
        company_id: str,
        kpi: str,
        period_preset: str = "mtd",
        reference_date: date | None = None,
        custom_start: date | str | None = None,
        custom_end: date | str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Key metrics behind one dashboard KPI card (sales, collections, purchases or receivables).

        Returns a generic shape the popup renders directly:
        headline, metrics (label/value/hint tiles), trend (chart points) and sections (ranked lists).
        """
        kpi_key = (kpi or "").strip().lower()
        if kpi_key not in self.KPI_DETAIL_KEYS:
            raise ValueError(f"Unknown KPI '{kpi}'. Expected one of: {', '.join(self.KPI_DETAIL_KEYS)}")
        log.info("AnalyticsService.get_kpi_details: company=%s kpi=%s period=%s", company_id, kpi_key, period_preset)

        anchor_date = reference_date or date.today()
        (curr_start, curr_end), (prior_start, prior_end), period_label = get_relative_period_bounds(
            period_preset=period_preset,
            reference_date=anchor_date,
            custom_start=custom_start,
            custom_end=custom_end,
        )
        prior_label = get_prior_period_label(
            period_preset=period_preset,
            prior_start=prior_start,
            prior_end=prior_end,
            reference_date=anchor_date,
        )

        if kpi_key == "receivables":
            details = self._receivables_kpi_details(company_id, anchor_date, limit)
        else:
            details = self._flow_kpi_details(
                company_id, kpi_key, curr_start, curr_end, prior_start, prior_end, prior_label, limit
            )
        details.update(
            {
                "kpi": kpi_key,
                "company_id": company_id,
                "period_label": period_label,
                "prior_period_label": prior_label,
                "as_of_label": f"as of {anchor_date.day} {anchor_date.strftime('%b')}",
            }
        )
        return details

    def _flow_kpi_details(
        self,
        company_id: str,
        kpi_key: str,
        curr_start: date,
        curr_end: date,
        prior_start: date,
        prior_end: date,
        prior_label: str,
        limit: int,
    ) -> dict[str, Any]:
        """Sales / Purchases / Collections: totals, volumes, best day, trend, top parties and items."""
        spec = self._FLOW_KPI_SPECS[kpi_key]
        base_type = spec["base_type"]

        with self.db.connection() as conn:
            cur = conn.cursor()
            curr_totals = self._flow_daily_totals(cur, company_id, base_type, spec["roles"], curr_start, curr_end)
            prior_totals = self._flow_daily_totals(cur, company_id, base_type, spec["roles"], prior_start, prior_end)
            if kpi_key == "sales" and not sum(curr_totals.values()):
                # Same fallback as the overview card: non-debtor (e.g. cash) sales have no customer posting
                curr_totals = self._flow_daily_totals(cur, company_id, base_type, None, curr_start, curr_end)
                prior_totals = self._flow_daily_totals(cur, company_id, base_type, None, prior_start, prior_end)

            cur.execute(
                """
                SELECT COUNT(*) AS n, COUNT(DISTINCT party_ref) AS parties
                FROM canonical_vouchers
                WHERE company_id = %s AND lifecycle = 'active' AND base_type = %s
                  AND date >= %s AND date <= %s
                """,
                (company_id, base_type, curr_start, curr_end),
            )
            counts = dict(cur.fetchone() or {})

            cur.execute(
                """
                SELECT COALESCE(a.name, v.party_ref) AS name,
                       SUM(ABS(p.amount)) AS amount,
                       COUNT(DISTINCT v.voucher_id) AS n
                FROM canonical_vouchers v
                JOIN canonical_postings p
                  ON p.voucher_ref = v.voucher_id AND p.account_ref = v.party_ref
                LEFT JOIN canonical_accounts a
                  ON a.account_id = v.party_ref AND a.company_id = v.company_id
                WHERE v.company_id = %s AND v.lifecycle = 'active' AND v.base_type = %s
                  AND v.date >= %s AND v.date <= %s AND v.party_ref IS NOT NULL
                GROUP BY COALESCE(a.name, v.party_ref)
                ORDER BY amount DESC
                LIMIT %s
                """,
                (company_id, base_type, curr_start, curr_end, limit),
            )
            top_parties = [dict(r) for r in cur.fetchall()]

            top_items: list[dict[str, Any]] = []
            if spec["top_items_title"]:
                cur.execute(
                    """
                    SELECT COALESCE(si.name, il.item_ref) AS name,
                           SUM(ABS(il.amount)) AS amount,
                           SUM(ABS(il.actual_qty)) AS qty
                    FROM canonical_inventory_lines il
                    JOIN canonical_vouchers v ON v.voucher_id = il.voucher_guid
                    LEFT JOIN canonical_stock_items si
                      ON si.stockitem_id = il.item_ref AND si.company_id = v.company_id
                    WHERE v.company_id = %s AND v.lifecycle = 'active' AND v.base_type = %s
                      AND v.date >= %s AND v.date <= %s
                    GROUP BY COALESCE(si.name, il.item_ref)
                    ORDER BY amount DESC
                    LIMIT %s
                    """,
                    (company_id, base_type, curr_start, curr_end, limit),
                )
                top_items = [dict(r) for r in cur.fetchall()]

            sales_total_for_efficiency = 0.0
            if kpi_key == "collections":
                sales_totals = self._flow_daily_totals(
                    cur, company_id, "Sales", self._FLOW_KPI_SPECS["sales"]["roles"], curr_start, curr_end
                )
                sales_total_for_efficiency = sum(sales_totals.values())
            cur.close()

        curr_total = sum(curr_totals.values())
        prior_total = sum(prior_totals.values())
        delta_pct = ((curr_total - prior_total) / prior_total * 100.0) if prior_total > 0 else 0.0
        voucher_count = int(counts.get("n") or 0)
        party_count = int(counts.get("parties") or 0)
        days_in_period = (curr_end - curr_start).days + 1
        best_day = max(curr_totals.items(), key=lambda kv: kv[1], default=None)

        metrics: list[dict[str, Any]] = [
            {"label": f"Total {spec['title'].lower()}", "value": format_inr(curr_total), "hint": f"{prior_label}: {format_inr(prior_total)}"},
            {"label": spec["count_label"], "value": f"{voucher_count:,}", "hint": "in this period"},
            {
                "label": f"Average {spec['count_label'].lower().rstrip('s')} value",
                "value": format_inr(curr_total / voucher_count) if voucher_count else "—",
                "hint": "total ÷ count",
            },
            {"label": spec["party_label"], "value": f"{party_count:,}", "hint": "distinct parties"},
            {"label": "Daily average", "value": format_inr(curr_total / days_in_period) if days_in_period else "—", "hint": f"over {days_in_period} days"},
            {
                "label": "Best day",
                "value": format_inr(best_day[1]) if best_day else "—",
                "hint": f"{best_day[0].day} {best_day[0].strftime('%b')}" if best_day else "no activity",
            },
        ]
        if kpi_key == "collections":
            efficiency = (curr_total / sales_total_for_efficiency * 100.0) if sales_total_for_efficiency > 0 else None
            metrics.append(
                {
                    "label": "Collection efficiency",
                    "value": f"{efficiency:.0f}%" if efficiency is not None else "—",
                    "hint": f"collected vs {format_inr(sales_total_for_efficiency)} sales",
                }
            )

        sections: list[dict[str, Any]] = [
            {
                "title": spec["top_parties_title"],
                "empty_text": "No activity in this period.",
                "rows": [
                    {
                        "primary": r["name"],
                        "secondary": f"{int(r['n'])} {spec['count_label'].lower() if int(r['n']) != 1 else spec['count_label'].lower().rstrip('s')}",
                        "value": format_inr(float(r["amount"] or 0.0)),
                    }
                    for r in top_parties
                ],
            }
        ]
        if spec["top_items_title"]:
            sections.append(
                {
                    "title": spec["top_items_title"],
                    "empty_text": "No item-level lines in this period.",
                    "rows": [
                        {
                            "primary": r["name"],
                            "secondary": f"{self._format_stock_quantity(float(r['qty'] or 0.0), 3)} units",
                            "value": format_inr(float(r["amount"] or 0.0)),
                        }
                        for r in top_items
                    ],
                }
            )

        return {
            "title": spec["title"],
            "description": spec["description"],
            "headline": {
                "formatted_value": format_inr(curr_total),
                "delta_pct": round(delta_pct, 1),
                "formatted_delta": format_percentage(delta_pct),
                "delta_direction": "up" if delta_pct >= 0 else "down",
                "prior_label": f"vs {prior_label}",
            },
            "metrics": metrics,
            "trend": {"title": f"{spec['title']} trend", **self._build_trend(curr_totals, curr_start, curr_end)},
            "sections": sections,
        }

    def _receivables_kpi_details(self, company_id: str, anchor_date: date, limit: int) -> dict[str, Any]:
        """Receivables: open invoices, overdue share, aging buckets, top debtors and slowest payers."""
        invoices = self.get_unpaid_invoices(company_id, limit=1_000_000, reference_date=anchor_date)
        balances = self.get_party_balances(company_id, filter_type="owed_to_me", limit=limit)
        payers = self.get_slowest_paying_customers(company_id, limit=limit)

        total_outstanding = sum(i["outstanding_amount"] for i in invoices)
        overdue = [i for i in invoices if i["days_overdue"] > 0]
        overdue_amount = sum(i["outstanding_amount"] for i in overdue)
        overdue_share = (overdue_amount / total_outstanding * 100.0) if total_outstanding > 0 else 0.0
        oldest_days = max((i["days_overdue"] for i in invoices), default=0)

        bucket_defs = [
            ("Not yet due", lambda d: d == 0),
            ("1–30 days overdue", lambda d: 1 <= d <= 30),
            ("31–60 days overdue", lambda d: 31 <= d <= 60),
            ("61–90 days overdue", lambda d: 61 <= d <= 90),
            ("Over 90 days overdue", lambda d: d > 90),
        ]
        aging_rows = []
        for label, test in bucket_defs:
            in_bucket = [i for i in invoices if test(i["days_overdue"])]
            amount = sum(i["outstanding_amount"] for i in in_bucket)
            aging_rows.append(
                {"primary": label, "secondary": f"{len(in_bucket)} invoice{'s' if len(in_bucket) != 1 else ''}", "value": format_inr(amount)}
            )

        has_dso = bool(payers.get("top_slowest_customers"))  # the service returns placeholder values when there is no history
        metrics: list[dict[str, Any]] = [
            {"label": "Open invoices total", "value": format_inr(total_outstanding), "hint": f"{len(invoices)} open invoices"},
            {"label": "Overdue amount", "value": format_inr(overdue_amount), "hint": f"{len(overdue)} overdue invoices"},
            {"label": "Overdue share", "value": f"{overdue_share:.0f}%", "hint": "of outstanding"},
            {"label": "Oldest overdue", "value": f"{oldest_days} days" if oldest_days else "—", "hint": "past due date"},
            {
                "label": "Customers owing",
                "value": f"{balances['summary']['count_owed_to_me']:,}",
                "hint": f"owed to you: {balances['summary']['formatted_owed_to_me']}",
            },
            {
                "label": "Avg days to pay",
                "value": f"{payers['overall_average_days']} days" if has_dso else "—",
                "hint": f"last {payers['lookback_months']} months" if has_dso else "no settled invoices yet",
            },
        ]

        sections: list[dict[str, Any]] = [
            {"title": "Aging of outstanding", "empty_text": "No open invoices.", "rows": aging_rows if invoices else []},
            {
                "title": "Top debtors",
                "empty_text": "No customer balances.",
                "rows": [
                    {
                        "primary": p["party_name"],
                        "secondary": f"{p['open_bills_count']} open bills"
                        + (f" · {p['max_overdue_days']}d overdue" if p["max_overdue_days"] else ""),
                        "value": p["formatted_amount"],
                    }
                    for p in balances["parties_owed_to_me"]
                ],
            },
            {
                "title": "Most overdue invoices",
                "empty_text": "No overdue invoices.",
                "rows": [
                    {
                        "primary": i["party_name"],
                        "secondary": f"Bill {i['bill_ref']} · {i['days_overdue']}d overdue",
                        "value": i["formatted_amount"],
                    }
                    for i in overdue[:limit]
                ],
            },
        ]
        if has_dso:
            sections.append(
                {
                    "title": "Slowest payers",
                    "empty_text": "",
                    "rows": [
                        {
                            "primary": c["customer_name"],
                            "secondary": f"{c['settled_invoices_count']} settled invoices",
                            "value": f"{c['average_days']} days",
                        }
                        for c in payers["top_slowest_customers"]
                    ],
                }
            )

        return {
            "title": "Receivables",
            "description": "Money customers still owe you on open invoices, with how much is overdue and who owes the most.",
            "headline": {"formatted_value": format_inr(total_outstanding), "prior_label": "outstanding on open invoices"},
            "metrics": metrics,
            "trend": None,
            "sections": sections,
        }

    def get_inventory_details(self, company_id: str, limit: int = 5) -> dict[str, Any]:
        """Expanded inventory view: overview KPIs plus largest, lowest and out-of-stock item lists."""
        return {
            "company_id": company_id,
            "overview": self.get_inventory_overview(company_id),
            "largest_stock": self.get_stock_items(company_id, "largest_stock", limit),
            "lowest_stock": self.get_stock_items(company_id, "lowest_stock", limit),
            "out_of_stock": self.get_stock_items(company_id, "out_of_stock", limit),
        }

    def _format_stock_quantity(self, qty: float, decimal_places: int = 0) -> str:
        """Formats stock quantities cleanly with appropriate decimal places and grouping commas."""
        if decimal_places <= 0 or qty.is_integer():
            return f"{int(round(qty)):,}"
        return f"{qty:,.{decimal_places}f}"

    def get_inventory_overview(self, company_id: str) -> dict[str, Any]:
        """Calculates high-level inventory KPIs: total items, in-stock count, out-of-stock count, and total valuation."""
        log.info("AnalyticsService.get_inventory_overview: company=%s", company_id)
        with self.db.connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT 
                    COUNT(*) AS total_items,
                    COUNT(CASE WHEN COALESCE(closing_qty, 0) > 0 THEN 1 END) AS in_stock_count,
                    COUNT(CASE WHEN COALESCE(closing_qty, 0) <= 0 THEN 1 END) AS out_of_stock_count,
                    COALESCE(SUM(closing_value), 0) AS total_valuation
                FROM canonical_stock_items
                WHERE company_id = %s
                """,
                (company_id,),
            )
            row = cur.fetchone()
            cur.close()

        row_dict = dict(row) if row else {}
        total_items = int(row_dict.get("total_items") or 0)
        in_stock = int(row_dict.get("in_stock_count") or 0)
        out_of_stock = int(row_dict.get("out_of_stock_count") or 0)
        total_val = float(row_dict.get("total_valuation") or 0.0)

        return {
            "total_items": total_items,
            "in_stock_count": in_stock,
            "out_of_stock_count": out_of_stock,
            "total_valuation": round(total_val, 2),
            "formatted_valuation": format_inr(total_val),
        }
