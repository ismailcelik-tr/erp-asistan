import datetime
from collections import Counter

from erp_asistan.erp.errors import ErpError
from erp_asistan.odoo.client import OdooClient

__all__ = ["compare_sales", "sales_summary"]

_CONFIRMED = ["sale", "done"]
_TOP_N = 5


def sales_summary(odoo: OdooClient, date_from: str, date_to: str) -> dict:
    """Confirmed sales between dates (inclusive, YYYY-MM-DD)."""
    try:
        start = datetime.date.fromisoformat(date_from)
        end = datetime.date.fromisoformat(date_to) + datetime.timedelta(days=1)
    except ValueError as e:
        raise ErpError("Tarihler YYYY-AA-GG biçiminde olmalı.") from e

    domain = [
        ("state", "in", _CONFIRMED),
        ("date_order", ">=", start.isoformat()),
        ("date_order", "<", end.isoformat()),
    ]
    orders = odoo.search_read("sale.order", domain, ["id", "partner_id", "amount_untaxed", "amount_total"])
    if not orders:
        return {"order_count": 0, "total": 0, "untaxed": 0, "top_customers": [], "top_products": []}

    lines = odoo.search_read(
        "sale.order.line",
        [("order_id", "in", [o["id"] for o in orders]), ("display_type", "=", False)],
        ["product_id", "product_uom_qty", "price_subtotal"],
    )

    by_customer: Counter = Counter()
    for o in orders:
        by_customer[o["partner_id"][1]] += o["amount_untaxed"]

    by_product: Counter = Counter()
    for l in lines:
        by_product[l["product_id"][1]] += l["price_subtotal"]

    return {
        "order_count": len(orders),
        "untaxed": round(sum(o["amount_untaxed"] for o in orders), 2),
        "total": round(sum(o["amount_total"] for o in orders), 2),
        "top_customers": [{"name": n, "untaxed": round(v, 2)} for n, v in by_customer.most_common(_TOP_N)],
        "top_products": [{"name": n, "untaxed": round(v, 2)} for n, v in by_product.most_common(_TOP_N)],
    }


def _pct(old: float, new: float) -> float | None:
    return round((new - old) / old * 100, 1) if old else None


def compare_sales(odoo: OdooClient, first_from: str, first_to: str, second_from: str, second_to: str) -> dict:
    """Two periods side by side; deltas are computed here, not by the LLM."""
    first = sales_summary(odoo, first_from, first_to)
    second = sales_summary(odoo, second_from, second_to)
    return {
        "first": first,
        "second": second,
        "change": {
            "total": round(second["total"] - first["total"], 2),
            "total_pct": _pct(first["total"], second["total"]),
            "order_count": second["order_count"] - first["order_count"],
        },
    }
