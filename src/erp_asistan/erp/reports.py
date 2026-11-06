import datetime
from collections import Counter

from erp_asistan.erp.errors import ErpError
from erp_asistan.odoo.client import OdooClient

__all__ = ["compare", "compare_sales", "period", "sales_summary", "summarize"]

_CONFIRMED = ["sale", "done"]
_TOP_N = 5


def period(date_from: str, date_to: str) -> tuple[datetime.date, datetime.date]:
    """Inclusive YYYY-MM-DD range as [start, end)."""
    try:
        start = datetime.date.fromisoformat(date_from)
        end = datetime.date.fromisoformat(date_to) + datetime.timedelta(days=1)
    except ValueError as e:
        raise ErpError("Tarihler YYYY-AA-GG biçiminde olmalı.") from e
    return start, end


def summarize(orders: list[dict], lines: list[dict]) -> dict:
    """orders: [{"customer", "untaxed", "total"}], lines: [{"product", "untaxed"}]."""
    if not orders:
        return {"order_count": 0, "total": 0, "untaxed": 0, "top_customers": [], "top_products": []}

    by_customer: Counter = Counter()
    for o in orders:
        by_customer[o["customer"]] += o["untaxed"]

    by_product: Counter = Counter()
    for l in lines:
        by_product[l["product"]] += l["untaxed"]

    return {
        "order_count": len(orders),
        "untaxed": round(sum(o["untaxed"] for o in orders), 2),
        "total": round(sum(o["total"] for o in orders), 2),
        "top_customers": [{"name": n, "untaxed": round(v, 2)} for n, v in by_customer.most_common(_TOP_N)],
        "top_products": [{"name": n, "untaxed": round(v, 2)} for n, v in by_product.most_common(_TOP_N)],
    }


def sales_summary(odoo: OdooClient, date_from: str, date_to: str) -> dict:
    """Confirmed sales between dates (inclusive, YYYY-MM-DD)."""
    start, end = period(date_from, date_to)
    domain = [
        ("state", "in", _CONFIRMED),
        ("date_order", ">=", start.isoformat()),
        ("date_order", "<", end.isoformat()),
    ]
    orders = odoo.search_read("sale.order", domain, ["id", "partner_id", "amount_untaxed", "amount_total"])
    if not orders:
        return summarize([], [])

    lines = odoo.search_read(
        "sale.order.line",
        [("order_id", "in", [o["id"] for o in orders]), ("display_type", "=", False)],
        ["product_id", "product_uom_qty", "price_subtotal"],
    )
    return summarize(
        [{"customer": o["partner_id"][1], "untaxed": o["amount_untaxed"], "total": o["amount_total"]} for o in orders],
        [{"product": l["product_id"][1], "untaxed": l["price_subtotal"]} for l in lines],
    )


def _pct(old: float, new: float) -> float | None:
    return round((new - old) / old * 100, 1) if old else None


def compare(first: dict, second: dict) -> dict:
    """Two period summaries side by side; deltas are computed here, not by the LLM."""
    return {
        "first": first,
        "second": second,
        "change": {
            "total": round(second["total"] - first["total"], 2),
            "total_pct": _pct(first["total"], second["total"]),
            "order_count": second["order_count"] - first["order_count"],
        },
    }


def compare_sales(odoo: OdooClient, first_from: str, first_to: str, second_from: str, second_to: str) -> dict:
    return compare(sales_summary(odoo, first_from, first_to), sales_summary(odoo, second_from, second_to))
