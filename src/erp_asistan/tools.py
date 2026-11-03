"""LLM-facing tool layer over ERP domain services."""

import enum
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from erp_asistan.erp import invoices, partners, products, reports, sales
from erp_asistan.erp.errors import ErpError
from erp_asistan.odoo.client import OdooClient, OdooError

__all__ = ["Kind", "ToolRegistry"]


class Kind(enum.Enum):
    READ = "read"
    WRITE = "write"


@dataclass(frozen=True)
class _Tool:
    name: str
    description: str
    params: dict
    required: list[str]
    kind: Kind
    fn: Callable[..., Any]


def _s(desc: str) -> dict:
    return {"type": "string", "description": desc}


def _n(desc: str) -> dict:
    return {"type": "number", "description": desc}


_DATE = "Date as YYYY-MM-DD"
_SALE_LINES = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {"product": _s("Product name"), "quantity": _n("Quantity")},
        "required": ["product", "quantity"],
    },
}
_BILL_LINES = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "description": _s("Line description"),
            "quantity": _n("Quantity"),
            "price_unit": _n("Unit price excluding VAT"),
        },
        "required": ["description", "quantity", "price_unit"],
    },
}


def _build(odoo: OdooClient) -> list[_Tool]:
    R, W = Kind.READ, Kind.WRITE
    return [
        _Tool("find_partner", "Search customers/vendors by name.",
              {"name": _s("Full or partial name")}, ["name"], R,
              lambda name: partners.find_partner(odoo, name)),
        _Tool("find_products", "Search products by name; returns price and stock.",
              {"name": _s("Full or partial product name")}, ["name"], R,
              lambda name: products.find_products(odoo, name)),
        _Tool("get_low_stock", "List products with stock below a threshold.",
              {"threshold": _n("Stock threshold")}, ["threshold"], R,
              lambda threshold: products.get_low_stock(odoo, threshold)),
        _Tool("list_open_invoices", "List unpaid customer invoices, optionally for one customer.",
              {"partner": _s("Customer name (optional)")}, [], R,
              lambda partner=None: invoices.list_open_invoices(odoo, partner)),
        _Tool("sales_summary", "Confirmed sales totals, top customers and top products for a date range.",
              {"date_from": _s(_DATE), "date_to": _s(_DATE)}, ["date_from", "date_to"], R,
              lambda date_from, date_to: reports.sales_summary(odoo, date_from, date_to)),
        _Tool("create_partner", "Create a new customer/vendor company.",
              {"name": _s("Company name"), "city": _s("City"), "phone": _s("Phone"), "email": _s("Email")},
              ["name"], W,
              lambda name, city=None, phone=None, email=None: partners.create_partner(odoo, name, city, phone, email)),
        _Tool("update_product_price", "Change a product's sales price (TL, excluding VAT).",
              {"product": _s("Product name"), "price": _n("New price")}, ["product", "price"], W,
              lambda product, price: products.update_product_price(odoo, product, price)),
        _Tool("create_quotation", "Create a sales quotation (draft order) for a customer.",
              {"partner": _s("Customer name"), "lines": _SALE_LINES}, ["partner", "lines"], W,
              lambda partner, lines: sales.create_quotation(odoo, partner, lines)),
        _Tool("confirm_order", "Confirm a quotation into a sales order.",
              {"order_ref": _s("Quotation reference, e.g. S00012")}, ["order_ref"], W,
              lambda order_ref: sales.confirm_order(odoo, order_ref)),
        _Tool("create_invoice", "Create and post the customer invoice of a confirmed sales order.",
              {"order_ref": _s("Sales order reference, e.g. S00012")}, ["order_ref"], W,
              lambda order_ref: invoices.create_invoice(odoo, order_ref)),
        _Tool("create_vendor_bill", "Create a draft vendor bill. Unknown vendors are created.",
              {"vendor": _s("Vendor company name"), "lines": _BILL_LINES, "date": _s(_DATE),
               "ref": _s("Vendor invoice number (optional)")},
              ["vendor", "lines", "date"], W,
              lambda vendor, lines, date, ref=None: invoices.create_vendor_bill(odoo, vendor, lines, date, ref)),
    ]


class ToolRegistry:
    def __init__(self, odoo: OdooClient) -> None:
        self._tools = {t.name: t for t in _build(odoo)}

    def schemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": {"type": "object", "properties": t.params, "required": t.required},
                },
            }
            for t in self._tools.values()
        ]

    def kind(self, name: str) -> Kind:
        tool = self._tools.get(name)
        # Unknown tools are treated as writes so they never run unapproved.
        return tool.kind if tool else Kind.WRITE

    def run(self, name: str, args: dict) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            return {"error": f"Bilinmeyen araç: {name}"}

        try:
            return tool.fn(**args)
        except (ErpError, OdooError) as e:
            return {"error": str(e)}
        except (TypeError, KeyError) as e:
            return {"error": f"Geçersiz parametre: {e}"}
