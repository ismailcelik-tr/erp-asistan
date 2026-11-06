"""Quotations, sales orders, customer invoices and vendor bills."""

import datetime

from erp_asistan.erp.errors import ErpError
from erp_asistan.erpnext import catalog
from erp_asistan.erpnext.client import ErpNextClient

__all__ = [
    "confirm_order",
    "create_invoice",
    "create_quotation",
    "create_vendor_bill",
    "find_orders",
    "list_open_invoices",
]

_SUBMITTED = 1  # docstatus
_SEARCH_LIMIT = 20
_QUOTE_VALID_DAYS = 30
# Submitted but not yet turned into a sales order: Odoo's "draft/sent" quotation.
_OPEN_QUOTATION = ["Open", "Replied"]
_VAT_RATE = 20
_VAT_LABEL = f"KDV %{_VAT_RATE}"
_SALES_VAT = "Hesaplanan KDV"
_PURCHASE_VAT = "İndirilecek KDV"
_ORDER_FIELDS = ["name", "customer_name", "grand_total", "transaction_date"]
_INVOICE_FIELDS = ["name", "customer_name", "posting_date", "due_date", "net_total", "grand_total",
                   "outstanding_amount", "status"]
_MAKE_ORDER = "erpnext.selling.doctype.quotation.quotation.make_sales_order"
_MAKE_INVOICE = "erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice"


def _today() -> str:
    return datetime.date.today().isoformat()


def _vat_account(c: ErpNextClient, account_name: str) -> str:
    [row] = c.get_list("Account", ["name"], filters=[["account_name", "=", account_name], ["is_group", "=", 0]], limit=1)
    return row["name"]


def _sales_taxes(c: ErpNextClient) -> list[dict]:
    return [{"charge_type": "On Net Total", "account_head": _vat_account(c, _SALES_VAT),
             "rate": _VAT_RATE, "description": _VAT_LABEL}]


def _purchase_taxes(c: ErpNextClient) -> list[dict]:
    return [{"category": "Total", "add_deduct_tax": "Add", "charge_type": "On Net Total",
             "account_head": _vat_account(c, _PURCHASE_VAT), "rate": _VAT_RATE, "description": _VAT_LABEL}]


def _submitted(c: ErpNextClient, doctype: str, ref: str) -> str | None:
    rows = c.get_list(doctype, ["name"], filters=[["name", "=", ref], ["docstatus", "=", _SUBMITTED]], limit=1)
    return rows[0]["name"] if rows else None


def _order_of(c: ErpNextClient, quotation: str) -> str | None:
    rows = c.get_list(
        "Sales Order", ["name"],
        filters=[["Sales Order Item", "prevdoc_docname", "=", quotation], ["docstatus", "=", _SUBMITTED]], limit=1,
    )
    return rows[0]["name"] if rows else None


def create_quotation(c: ErpNextClient, partner: str, lines: list[dict], date: str | None = None) -> dict:
    """lines: [{"product": str, "quantity": float}]. date (YYYY-MM-DD) backdates seed data."""
    customer = catalog.resolve_partner(c, partner)
    codes = [catalog.resolve_product(c, l["product"])["id"] for l in lines]
    prices = catalog.item_prices(c, codes)
    valid_till = datetime.date.today() + datetime.timedelta(days=_QUOTE_VALID_DAYS)

    quote = c.submit({
        "doctype": "Quotation", "quotation_to": "Customer", "party_name": customer["id"],
        "transaction_date": date or _today(),
        # Counted from today: an expired quotation cannot become an order.
        "valid_till": valid_till.isoformat(),
        "items": [{"item_code": code, "qty": l["quantity"], "rate": prices.get(code, 0)} for code, l in zip(codes, lines)],
        "taxes": _sales_taxes(c),
    })
    return {"ref": quote["name"], "partner": customer["name"], "total": quote["grand_total"]}


def confirm_order(c: ErpNextClient, order_ref: str, date: str | None = None) -> dict:
    quote = _submitted(c, "Quotation", order_ref)
    if quote is None:
        raise ErpError(f"'{order_ref}' adında teklif bulunamadı.")
    if _order_of(c, quote):
        raise ErpError(f"{quote} zaten siparişe dönüştürülmüş.")

    when = date or _today()
    doc = c.call(_MAKE_ORDER, source_name=quote)
    doc.update({"transaction_date": when, "delivery_date": when})
    for item in doc["items"]:
        item["delivery_date"] = when

    order = c.submit(doc)
    return {"ref": order["name"], "quotation": quote, "state": "order", "total": order["grand_total"]}


def _sales_order(c: ErpNextClient, ref: str) -> str:
    """ref may be the order itself or the quotation it came from."""
    order = _submitted(c, "Sales Order", ref)
    if order:
        return order

    quote = _submitted(c, "Quotation", ref)
    if quote is None:
        raise ErpError(f"'{ref}' adında sipariş/teklif bulunamadı.")

    order = _order_of(c, quote)
    if order is None:
        raise ErpError(f"{quote} henüz onaylanmamış; önce teklifi onaylayın.")
    return order


def _invoice_view(row: dict) -> dict:
    return {
        "id": row["name"],
        "ref": row["name"],
        "partner": row.get("customer_name") or row.get("supplier_name"),
        "date": row["posting_date"],
        "due": row["due_date"],
        "untaxed": row["net_total"],
        "total": row["grand_total"],
        "residual": row["outstanding_amount"],
        "state": row["status"],
    }


def create_invoice(c: ErpNextClient, order_ref: str) -> dict:
    doc = c.call(_MAKE_INVOICE, source_name=_sales_order(c, order_ref))
    return _invoice_view(c.submit(doc))


def list_open_invoices(c: ErpNextClient, partner: str | None = None) -> dict:
    """Totals are computed here: the LLM must not do arithmetic."""
    filters = [["docstatus", "=", _SUBMITTED], ["outstanding_amount", ">", 0], ["is_return", "=", 0]]
    if partner:
        filters.append(["customer_name", "like", f"%{partner}%"])

    rows = c.get_list("Sales Invoice", _INVOICE_FIELDS, filters=filters, order_by="due_date asc")
    return {
        "count": len(rows),
        "total_residual": round(sum(r["outstanding_amount"] for r in rows), 2),
        "invoices": [_invoice_view(r) for r in rows],
    }


def _order_view(row: dict, state: str) -> dict:
    return {"ref": row["name"], "partner": row["customer_name"], "state": state,
            "total": row["grand_total"], "date": str(row["transaction_date"])[:10]}


def find_orders(c: ErpNextClient, partner: str | None = None, state: str | None = None) -> list[dict]:
    """state: "quotation" (not yet an order) or "order" (sales order); anything else: both."""
    customer = catalog.resolve_partner(c, partner)["id"] if partner else None
    rows = []

    if state != "order":
        filters = [["docstatus", "=", _SUBMITTED], ["status", "in", _OPEN_QUOTATION]]
        if customer:
            filters.append(["party_name", "=", customer])
        quotes = c.get_list("Quotation", _ORDER_FIELDS, filters=filters, limit=_SEARCH_LIMIT,
                            order_by="transaction_date desc")
        rows += [_order_view(r, "quotation") for r in quotes]

    if state != "quotation":
        filters = [["docstatus", "=", _SUBMITTED]]
        if customer:
            filters.append(["customer", "=", customer])
        orders = c.get_list("Sales Order", _ORDER_FIELDS, filters=filters, limit=_SEARCH_LIMIT,
                            order_by="transaction_date desc")
        rows += [_order_view(r, "order") for r in orders]

    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows[:_SEARCH_LIMIT]


def _expense_account(c: ErpNextClient) -> str:
    return c.get_list("Company", ["default_expense_account"], limit=1)[0]["default_expense_account"]


def _supplier(c: ErpNextClient, name: str) -> str:
    rows = c.get_list("Supplier", ["name"], filters=[["supplier_name", "=", name]], limit=1)
    if rows:
        return rows[0]["name"]
    return catalog.create_vendor(c, name)["id"]


def create_vendor_bill(c: ErpNextClient, vendor: str, lines: list[dict], date: str, ref: str | None = None) -> dict:
    """lines: [{"description": str, "quantity": float, "price_unit": float}]. Unknown vendor is created. Stays draft."""
    try:
        datetime.date.fromisoformat(date)
    except ValueError as e:
        raise ErpError(f"Geçersiz tarih: {date} (YYYY-AA-GG bekleniyor).") from e

    # Lines without an item have no default expense account.
    expense = _expense_account(c)
    doc = {
        "doctype": "Purchase Invoice", "supplier": _supplier(c, vendor),
        "posting_date": date, "set_posting_time": 1, "bill_date": date, "due_date": date,
        "items": [
            {"item_name": l["description"], "description": l["description"], "qty": l["quantity"],
             "rate": l["price_unit"], "uom": catalog.UOM, "conversion_factor": 1, "expense_account": expense}
            for l in lines
        ],
        "taxes": _purchase_taxes(c),
    }
    if ref:
        doc["bill_no"] = ref

    bill = c.insert(doc)
    return _invoice_view(bill | {"supplier_name": vendor})
