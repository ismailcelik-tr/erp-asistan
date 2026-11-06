"""LLM-facing tool layer over ERP domain services."""

import enum
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from erp_asistan.erp.backend import Erp
from erp_asistan.erp.errors import ErpError
from erp_asistan.erpnext.client import ErpNextError
from erp_asistan.odoo.client import OdooError

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


def _build(erp: Erp) -> list[_Tool]:
    R, W = Kind.READ, Kind.WRITE
    return [
        _Tool("find_partner", "Search customers/vendors by name.",
              {"name": _s("Full or partial name")}, ["name"], R, erp.find_partner),
        _Tool("find_products", "Search products by name or product code (e.g. M.U.CLV.00001); returns code, category, price and stock.",
              {"name": _s("Product name or code, full or partial")}, ["name"], R, erp.find_products),
        _Tool("get_low_stock", "List products with stock below a threshold.",
              {"threshold": _n("Stock threshold")}, ["threshold"], R, erp.get_low_stock),
        _Tool("list_open_invoices", "List unpaid customer invoices, optionally for one customer.",
              {"partner": _s("Customer name (optional)")}, [], R, erp.list_open_invoices),
        _Tool("find_orders", "List sales quotations/orders, optionally filtered by customer and state.",
              {"partner": _s("Customer name (optional)"),
               "state": {"type": "string", "enum": ["quotation", "order"],
                         "description": "quotation = not yet confirmed, order = confirmed (optional)"}},
              [], R, erp.find_orders),
        _Tool("sales_summary", "Confirmed sales totals, top customers and top products for a date range.",
              {"date_from": _s(_DATE), "date_to": _s(_DATE)}, ["date_from", "date_to"], R, erp.sales_summary),
        _Tool("compare_sales", "Compare confirmed sales of two periods; returns both summaries and the change.",
              {"first_from": _s(_DATE), "first_to": _s(_DATE), "second_from": _s(_DATE), "second_to": _s(_DATE)},
              ["first_from", "first_to", "second_from", "second_to"], R, erp.compare_sales),
        _Tool("create_partner", "Create a new customer/vendor company.",
              {"name": _s("Company name"), "city": _s("City"), "phone": _s("Phone"), "email": _s("Email")},
              ["name"], W, erp.create_partner),
        _Tool("update_product_price", "Change a product's sales price (TL, excluding VAT).",
              {"product": _s("Product name"), "price": _n("New price")}, ["product", "price"], W,
              erp.update_product_price),
        _Tool("create_quotation", "Create a sales quotation (draft order) for a customer.",
              {"partner": _s("Customer name"), "lines": _SALE_LINES}, ["partner", "lines"], W, erp.create_quotation),
        _Tool("confirm_order", "Confirm a quotation into a sales order.",
              {"order_ref": _s(f"Quotation reference, e.g. {erp.quote_example}")}, ["order_ref"], W,
              erp.confirm_order),
        _Tool("create_invoice", "Create and post the customer invoice of a confirmed sales order.",
              {"order_ref": _s(f"Sales order reference, e.g. {erp.order_example}")}, ["order_ref"], W,
              erp.create_invoice),
        _Tool("create_vendor_bill", "Create a draft vendor bill. Unknown vendors are created.",
              {"vendor": _s("Vendor company name"), "lines": _BILL_LINES, "date": _s(_DATE),
               "ref": _s("Vendor invoice number (optional)")},
              ["vendor", "lines", "date"], W, erp.create_vendor_bill),
    ]


class ToolRegistry:
    def __init__(self, erp: Erp) -> None:
        self._tools = {t.name: t for t in _build(erp)}

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
        except (ErpError, OdooError, ErpNextError) as e:
            return {"error": str(e)}
        except (TypeError, KeyError) as e:
            return {"error": f"Geçersiz parametre: {e}"}
