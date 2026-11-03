from erp_asistan.erp._lookup import resolve, search
from erp_asistan.odoo.client import OdooClient

__all__ = [
    "find_products",
    "resolve_product",
    "create_product",
    "set_stock",
    "get_low_stock",
    "update_product_price",
]

_FIELDS = ["id", "name", "default_code", "categ_id", "list_price", "qty_available"]
_SEARCH_LIMIT = 20


def _view(row: dict) -> dict:
    return {
        "id": row["id"],
        "code": row["default_code"] or None,
        "name": row["name"],
        "category": row["categ_id"][1].split(" / ")[-1] if row["categ_id"] else None,
        "price": row["list_price"],
        "stock": row["qty_available"],
    }


def find_products(odoo: OdooClient, name: str) -> list[dict]:
    rows = search(odoo, "product.product", name, _FIELDS, _SEARCH_LIMIT, code_field="default_code")
    return [_view(r) for r in rows]


def resolve_product(odoo: OdooClient, name: str) -> dict:
    return resolve(odoo, "product.product", name, "ürün", code_field="default_code")


def create_product(
    odoo: OdooClient,
    name: str,
    price: float,
    cost: float = 0,
    code: str | None = None,
    category: str | None = None,
) -> dict:
    vals = {
        "name": name,
        "list_price": price,
        "standard_price": cost,
        "type": "consu",
        "is_storable": True,
        "invoice_policy": "order",
    }
    if code:
        vals["default_code"] = code
    if category:
        vals["categ_id"] = _category_id(odoo, category)

    odoo.create("product.template", [vals])
    return resolve_product(odoo, name)


def _category_id(odoo: OdooClient, name: str) -> int:
    rows = odoo.search_read("product.category", [("name", "=", name)], ["id"], limit=1)
    if rows:
        return rows[0]["id"]

    [cid] = odoo.create("product.category", [{"name": name}])
    return cid


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
