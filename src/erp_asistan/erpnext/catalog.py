"""Customers, suppliers, items, prices and stock."""

from collections import Counter

from erp_asistan.erpnext.client import ErpNextClient
from erp_asistan.erpnext.lookup import resolve, search

__all__ = [
    "UOM",
    "create_partner",
    "create_product",
    "create_vendor",
    "find_partner",
    "find_products",
    "get_low_stock",
    "item_prices",
    "resolve_partner",
    "resolve_product",
    "set_stock",
    "update_product_price",
]

UOM = "Nos"
_PARTNER_LIMIT = 10
_PRODUCT_LIMIT = 20
_PRICE_LIST = "Standard Selling"
_DEFAULT_ITEM_GROUP = "Products"
_ROOT_ITEM_GROUP = "All Item Groups"
_WAREHOUSE = "Stores"
_OPENING_ACCOUNT = "Temporary Opening"
_COMPANY_TYPE = "Company"
_ADDRESS_TYPE = "Billing"
_PARTIES = [("Customer", "customer_name"), ("Supplier", "supplier_name")]
_ITEM_FIELDS = ["name", "item_code", "item_name", "item_group"]


def find_partner(c: ErpNextClient, name: str) -> list[dict]:
    rows = []
    for doctype, field in _PARTIES:
        for r in search(c, doctype, field, name, ["name", field], _PARTNER_LIMIT):
            rows.append({"id": r["name"], "name": r[field], "type": doctype.lower(), "city": _city(c, r["name"])})
    return rows[:_PARTNER_LIMIT]


def _city(c: ErpNextClient, party: str) -> str | None:
    rows = c.get_list("Address", ["city"], filters=[["Dynamic Link", "link_name", "=", party]], limit=1)
    return rows[0]["city"] if rows else None


def resolve_partner(c: ErpNextClient, name: str) -> dict:
    return resolve(c, "Customer", "customer_name", name, "cari")


def create_partner(
    c: ErpNextClient, name: str, city: str | None = None, phone: str | None = None, email: str | None = None
) -> dict:
    doc = c.insert({"doctype": "Customer", "customer_name": name, "customer_type": _COMPANY_TYPE})
    _link_details(c, "Customer", doc["name"], name, city, phone, email)
    return {"id": doc["name"], "name": name}


def create_vendor(c: ErpNextClient, name: str, city: str | None = None) -> dict:
    doc = c.insert({"doctype": "Supplier", "supplier_name": name, "supplier_type": _COMPANY_TYPE})
    _link_details(c, "Supplier", doc["name"], name, city, None, None)
    return {"id": doc["name"], "name": name}


def _link_details(
    c: ErpNextClient, doctype: str, party: str, title: str, city: str | None, phone: str | None, email: str | None
) -> None:
    """ERPNext keeps city in Address and phone/email in Contact, linked to the party."""
    links = [{"link_doctype": doctype, "link_name": party}]
    if city:
        c.insert({
            "doctype": "Address", "address_title": title, "address_type": _ADDRESS_TYPE,
            "address_line1": city, "city": city, "country": _country(c), "links": links,
        })
    if phone or email:
        c.insert({
            "doctype": "Contact", "first_name": title, "links": links,
            "email_ids": [{"email_id": email, "is_primary": 1}] if email else [],
            "phone_nos": [{"phone": phone, "is_primary_phone": 1}] if phone else [],
        })


def _country(c: ErpNextClient) -> str:
    return c.get_list("Company", ["country"], limit=1)[0]["country"]


def item_prices(c: ErpNextClient, codes: list[str]) -> dict[str, float]:
    rows = c.get_list(
        "Item Price", ["item_code", "price_list_rate"],
        filters=[["price_list", "=", _PRICE_LIST], ["item_code", "in", codes]],
    )
    return {r["item_code"]: r["price_list_rate"] for r in rows}


def _stocks(c: ErpNextClient, codes: list[str]) -> Counter:
    totals: Counter = Counter()
    for r in c.get_list("Bin", ["item_code", "actual_qty"], filters=[["item_code", "in", codes]]):
        totals[r["item_code"]] += r["actual_qty"]
    return totals


def _views(c: ErpNextClient, rows: list[dict]) -> list[dict]:
    codes = [r["name"] for r in rows]
    if not codes:
        return []

    prices, stocks = item_prices(c, codes), _stocks(c, codes)
    return [
        {
            "id": r["name"],
            # Items without a product code use their name as item_code.
            "code": r["item_code"] if r["item_code"] != r["item_name"] else None,
            "name": r["item_name"],
            "category": r["item_group"],
            "price": prices.get(r["name"], 0),
            "stock": stocks[r["name"]],
        }
        for r in rows
    ]


def find_products(c: ErpNextClient, name: str) -> list[dict]:
    rows = search(c, "Item", "item_name", name, _ITEM_FIELDS, _PRODUCT_LIMIT, code_field="item_code")
    return _views(c, rows)


def resolve_product(c: ErpNextClient, name: str) -> dict:
    return resolve(c, "Item", "item_name", name, "ürün", code_field="item_code")


def create_product(
    c: ErpNextClient, name: str, price: float, cost: float = 0, code: str | None = None, category: str | None = None
) -> dict:
    item_code = code or name
    c.insert({
        "doctype": "Item", "item_code": item_code, "item_name": name,
        "item_group": _item_group(c, category) if category else _DEFAULT_ITEM_GROUP,
        "stock_uom": UOM, "is_stock_item": 1, "valuation_rate": cost,
    })
    c.insert({"doctype": "Item Price", "item_code": item_code, "price_list": _PRICE_LIST, "price_list_rate": price})
    return resolve_product(c, item_code)


def _item_group(c: ErpNextClient, name: str) -> str:
    if c.get_list("Item Group", ["name"], filters=[["name", "=", name]], limit=1):
        return name

    c.insert({"doctype": "Item Group", "item_group_name": name, "parent_item_group": _ROOT_ITEM_GROUP})
    return name


def _warehouse(c: ErpNextClient) -> str:
    [row] = c.get_list("Warehouse", ["name"], filters=[["warehouse_name", "=", _WAREHOUSE], ["is_group", "=", 0]], limit=1)
    return row["name"]


def _account(c: ErpNextClient, account_name: str) -> str:
    [row] = c.get_list("Account", ["name"], filters=[["account_name", "=", account_name], ["is_group", "=", 0]], limit=1)
    return row["name"]


def set_stock(c: ErpNextClient, product: str, quantity: float) -> None:
    code = resolve_product(c, product)["id"]
    rate = c.get_doc("Item", code)["valuation_rate"]
    row = {"item_code": code, "warehouse": _warehouse(c), "qty": quantity, "valuation_rate": rate}
    if not rate:
        row["allow_zero_valuation_rate"] = 1

    doc = {"doctype": "Stock Reconciliation", "purpose": "Stock Reconciliation", "items": [row]}
    # An item's first stock entry is an opening entry: ERPNext requires an asset-type difference account.
    if not c.get_list("Bin", ["name"], filters=[["item_code", "=", code]], limit=1):
        doc |= {"purpose": "Opening Stock", "expense_account": _account(c, _OPENING_ACCOUNT)}

    c.submit(doc)


def get_low_stock(c: ErpNextClient, threshold: float) -> list[dict]:
    rows = c.get_list("Item", _ITEM_FIELDS, filters=[["is_stock_item", "=", 1], ["disabled", "=", 0]])
    low = [p for p in _views(c, rows) if p["stock"] < threshold]
    return sorted(low, key=lambda p: p["stock"])


def update_product_price(c: ErpNextClient, product: str, price: float) -> dict:
    p = resolve_product(c, product)
    [row] = c.get_list(
        "Item Price", ["name", "price_list_rate"],
        filters=[["item_code", "=", p["id"]], ["price_list", "=", _PRICE_LIST]], limit=1,
    )
    c.set_value("Item Price", row["name"], {"price_list_rate": price})
    return {"name": p["name"], "old_price": row["price_list_rate"], "new_price": price}
