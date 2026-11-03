import datetime

from erp_asistan.erp.errors import ErpError
from erp_asistan.erp.sales import resolve_order
from erp_asistan.odoo.client import OdooClient

__all__ = ["create_invoice", "list_open_invoices", "create_vendor_bill"]

_MOVE_FIELDS = [
    "id", "name", "partner_id", "invoice_date", "invoice_date_due",
    "amount_untaxed", "amount_total", "amount_residual", "state",
]
_UNPAID = ["not_paid", "partial"]


def _view(row: dict) -> dict:
    return {
        "id": row["id"],
        "ref": row["name"],
        "partner": row["partner_id"][1] if row["partner_id"] else None,
        "date": row["invoice_date"],
        "due": row["invoice_date_due"],
        "untaxed": row["amount_untaxed"],
        "total": row["amount_total"],
        "residual": row["amount_residual"],
        "state": row["state"],
    }


def _read_move(odoo: OdooClient, move_id: int) -> dict:
    [row] = odoo.search_read("account.move", [("id", "=", move_id)], _MOVE_FIELDS)
    return _view(row)


def create_invoice(odoo: OdooClient, order_ref: str) -> dict:
    order = resolve_order(odoo, order_ref)
    if order["state"] != "sale":
        raise ErpError(f"{order['name']} henüz onaylanmamış; önce siparişi onaylayın.")

    ctx = {"active_model": "sale.order", "active_ids": [order["id"]]}
    wizard_ids = odoo.call(
        "sale.advance.payment.inv", "create", vals_list=[{"advance_payment_method": "delivered"}], context=ctx
    )
    odoo.call("sale.advance.payment.inv", "create_invoices", ids=wizard_ids, context=ctx)

    [row] = odoo.search_read("sale.order", [("id", "=", order["id"])], ["invoice_ids"])
    move_id = max(row["invoice_ids"])
    odoo.call("account.move", "action_post", ids=[move_id])
    return _read_move(odoo, move_id)


def list_open_invoices(odoo: OdooClient, partner: str | None = None) -> dict:
    """Totals are computed here: the LLM must not do arithmetic."""
    domain = [("move_type", "=", "out_invoice"), ("state", "=", "posted"), ("payment_state", "in", _UNPAID)]
    if partner:
        domain.append(("partner_id.name", "ilike", partner))

    rows = odoo.search_read("account.move", domain, _MOVE_FIELDS, order="invoice_date_due asc")
    return {
        "count": len(rows),
        "total_residual": round(sum(r["amount_residual"] for r in rows), 2),
        "invoices": [_view(r) for r in rows],
    }


def create_vendor_bill(odoo: OdooClient, vendor: str, lines: list[dict], date: str, ref: str | None = None) -> dict:
    """lines: [{"description": str, "quantity": float, "price_unit": float}]. Unknown vendor is created."""
    try:
        datetime.date.fromisoformat(date)
    except ValueError as e:
        raise ErpError(f"Geçersiz tarih: {date} (YYYY-AA-GG bekleniyor).") from e

    partner_id = _vendor_id(odoo, vendor)
    # Product-less lines get no default tax; apply the company's purchase VAT explicitly.
    [company] = odoo.search_read("res.company", [], ["account_purchase_tax_id"], limit=1)
    taxes = [company["account_purchase_tax_id"][0]] if company["account_purchase_tax_id"] else []
    move_lines = [
        [0, 0, {
            "name": l["description"],
            "quantity": l["quantity"],
            "price_unit": l["price_unit"],
            "tax_ids": [[6, 0, taxes]],
        }]
        for l in lines
    ]
    vals = {"move_type": "in_invoice", "partner_id": partner_id, "invoice_date": date, "invoice_line_ids": move_lines}
    if ref:
        vals["ref"] = ref

    [move_id] = odoo.create("account.move", [vals])
    return _read_move(odoo, move_id)


def _vendor_id(odoo: OdooClient, name: str) -> int:
    rows = odoo.search_read("res.partner", [("name", "=ilike", name)], ["id"], limit=1)
    if rows:
        return rows[0]["id"]

    [pid] = odoo.create("res.partner", [{"name": name, "is_company": True}])
    return pid
