from erp_asistan.erp._lookup import resolve
from erp_asistan.erp.partners import resolve_partner
from erp_asistan.erp.products import resolve_product
from erp_asistan.odoo.client import OdooClient

__all__ = ["create_quotation", "confirm_order", "find_orders", "resolve_order"]

_ORDER_FIELDS = ["id", "name", "state", "amount_total", "partner_id", "date_order"]
_STATES = {"quotation": ["draft", "sent"], "order": ["sale"]}
_SEARCH_LIMIT = 20


def resolve_order(odoo: OdooClient, ref: str) -> dict:
    o = resolve(odoo, "sale.order", ref, "sipariş/teklif")
    [row] = odoo.search_read("sale.order", [("id", "=", o["id"])], _ORDER_FIELDS)
    return row


def create_quotation(odoo: OdooClient, partner: str, lines: list[dict]) -> dict:
    """lines: [{"product": str, "quantity": float}]"""
    pid = resolve_partner(odoo, partner)["id"]
    order_lines = [
        [0, 0, {"product_id": resolve_product(odoo, l["product"])["id"], "product_uom_qty": l["quantity"]}]
        for l in lines
    ]

    [oid] = odoo.create("sale.order", [{"partner_id": pid, "order_line": order_lines}])

    [row] = odoo.search_read("sale.order", [("id", "=", oid)], _ORDER_FIELDS)
    return {"ref": row["name"], "partner": row["partner_id"][1], "total": row["amount_total"]}


def confirm_order(odoo: OdooClient, order_ref: str) -> dict:
    order = resolve_order(odoo, order_ref)
    odoo.call("sale.order", "action_confirm", ids=[order["id"]])

    order = resolve_order(odoo, order_ref)
    return {"ref": order["name"], "state": order["state"], "total": order["amount_total"]}


def find_orders(odoo: OdooClient, partner: str | None = None, state: str | None = None) -> list[dict]:
    """state: "quotation" (not yet confirmed) or "order" (confirmed)."""
    domain = []
    if partner:
        domain.append(("partner_id", "=", resolve_partner(odoo, partner)["id"]))
    if state in _STATES:
        domain.append(("state", "in", _STATES[state]))

    rows = odoo.search_read("sale.order", domain, _ORDER_FIELDS, limit=_SEARCH_LIMIT, order="date_order desc")
    return [
        {"ref": r["name"], "partner": r["partner_id"][1], "state": r["state"], "total": r["amount_total"],
         "date": r["date_order"][:10]}
        for r in rows
    ]
