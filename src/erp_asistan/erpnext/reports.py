"""Sales summaries over submitted sales orders."""

import datetime

from erp_asistan.erp.reports import compare, period, summarize
from erp_asistan.erpnext.client import ErpNextClient

__all__ = ["compare_sales", "sales_summary"]

_SUBMITTED = 1


def sales_summary(c: ErpNextClient, date_from: str, date_to: str) -> dict:
    """Submitted sales orders between dates (inclusive, YYYY-MM-DD)."""
    start, end = period(date_from, date_to)
    last = end - datetime.timedelta(days=1)
    orders = c.get_list(
        "Sales Order", ["name", "customer_name", "net_total", "grand_total"],
        filters=[["docstatus", "=", _SUBMITTED], ["transaction_date", "between", [start.isoformat(), last.isoformat()]]],
    )
    if not orders:
        return summarize([], [])

    lines = c.get_list(
        "Sales Order Item", ["item_name", "net_amount"],
        filters=[["parent", "in", [o["name"] for o in orders]]], parent="Sales Order",
    )
    return summarize(
        [{"customer": o["customer_name"], "untaxed": o["net_total"], "total": o["grand_total"]} for o in orders],
        [{"product": l["item_name"], "untaxed": l["net_amount"]} for l in lines],
    )


def compare_sales(c: ErpNextClient, first_from: str, first_to: str, second_from: str, second_to: str) -> dict:
    return compare(sales_summary(c, first_from, first_to), sales_summary(c, second_from, second_to))
