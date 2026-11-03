from erp_asistan.erp._lookup import resolve
from erp_asistan.erp.partners import resolve_partner
from erp_asistan.erp.products import resolve_product
from erp_asistan.odoo.client import OdooClient

__all__ = ["create_quotation", "confirm_order", "resolve_order"]

_ORDER_FIELDS = ["id", "name", "state", "amount_total", "partner_id"]


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
