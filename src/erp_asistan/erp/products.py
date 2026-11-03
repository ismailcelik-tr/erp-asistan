from erp_asistan.erp._lookup import resolve
from erp_asistan.odoo.client import OdooClient

__all__ = [
    "find_products",
    "resolve_product",
    "create_product",
    "set_stock",
    "get_low_stock",
    "update_product_price",
]

_FIELDS = ["id", "name", "list_price", "qty_available"]
_SEARCH_LIMIT = 20


def _view(row: dict) -> dict:
    return {"id": row["id"], "name": row["name"], "price": row["list_price"], "stock": row["qty_available"]}


def find_products(odoo: OdooClient, name: str) -> list[dict]:
    rows = odoo.search_read("product.product", [("name", "ilike", name)], _FIELDS, limit=_SEARCH_LIMIT)
    return [_view(r) for r in rows]


def resolve_product(odoo: OdooClient, name: str) -> dict:
    return resolve(odoo, "product.product", name, "ürün")


def create_product(odoo: OdooClient, name: str, price: float, cost: float = 0) -> dict:
    vals = {
        "name": name,
        "list_price": price,
        "standard_price": cost,
        "type": "consu",
        "is_storable": True,
        "invoice_policy": "order",
    }
    odoo.create("product.template", [vals])
    return resolve_product(odoo, name)


def set_stock(odoo: OdooClient, product: str, quantity: float) -> None:
    pid = resolve_product(odoo, product)["id"]
    [wh] = odoo.search_read("stock.warehouse", [], ["lot_stock_id"], limit=1)
    ctx = {"inventory_mode": True}

    quant_ids = odoo.call(
        "stock.quant",
        "create",
        vals_list=[{"product_id": pid, "location_id": wh["lot_stock_id"][0], "inventory_quantity": quantity}],
        context=ctx,
    )
    odoo.call("stock.quant", "action_apply_inventory", ids=quant_ids, context=ctx)


def get_low_stock(odoo: OdooClient, threshold: float) -> list[dict]:
    domain = [("is_storable", "=", True), ("qty_available", "<", threshold)]
    rows = odoo.search_read("product.product", domain, _FIELDS)

    # qty_available is computed, not stored: SQL can't order by it.
    return sorted((_view(r) for r in rows), key=lambda p: p["stock"])


def update_product_price(odoo: OdooClient, product: str, price: float) -> dict:
    p = resolve_product(odoo, product)
    [row] = odoo.search_read("product.product", [("id", "=", p["id"])], ["list_price"])
    odoo.write("product.product", [p["id"]], {"list_price": price})
    return {"name": p["name"], "old_price": row["list_price"], "new_price": price}
