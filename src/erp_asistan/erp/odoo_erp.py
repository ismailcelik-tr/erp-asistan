"""Odoo implementation of the ERP contract."""

import base64

from erp_asistan.erp import company, invoices, partners, products, reports, sales
from erp_asistan.odoo.client import OdooClient

__all__ = ["OdooErp"]

_COMPANY_FIELDS = ["name", "street", "city", "zip", "phone", "email", "website"]
_SEED_ORDER_TIME = "10:00:00"


class OdooErp:
    quote_example = "S00012"
    order_example = "S00012"

    def __init__(self, client: OdooClient, url: str, db: str) -> None:
        self._c = client
        self._url = url.rstrip("/")
        self._db = db

    def company_info(self) -> dict:
        return company.company_info(self._c)

    def record_url(self, record_id: int | str) -> str:
        # ?db= is required: the server hosts more than one DB (demo + tests).
        return f"{self._url}/odoo/account.move/{record_id}?db={self._db}"

    def find_partner(self, name: str) -> list[dict]:
        return partners.find_partner(self._c, name)

    def find_products(self, name: str) -> list[dict]:
        return products.find_products(self._c, name)

    def get_low_stock(self, threshold: float) -> list[dict]:
        return products.get_low_stock(self._c, threshold)

    def list_open_invoices(self, partner: str | None = None) -> dict:
        return invoices.list_open_invoices(self._c, partner)

    def find_orders(self, partner: str | None = None, state: str | None = None) -> list[dict]:
        return sales.find_orders(self._c, partner, state)

    def sales_summary(self, date_from: str, date_to: str) -> dict:
        return reports.sales_summary(self._c, date_from, date_to)

    def compare_sales(self, first_from: str, first_to: str, second_from: str, second_to: str) -> dict:
        return reports.compare_sales(self._c, first_from, first_to, second_from, second_to)

    def create_partner(
        self, name: str, city: str | None = None, phone: str | None = None, email: str | None = None
    ) -> dict:
        return partners.create_partner(self._c, name, city, phone, email)

    def update_product_price(self, product: str, price: float) -> dict:
        return products.update_product_price(self._c, product, price)

    def create_quotation(self, partner: str, lines: list[dict]) -> dict:
        return sales.create_quotation(self._c, partner, lines)

    def confirm_order(self, order_ref: str) -> dict:
        return sales.confirm_order(self._c, order_ref)

    def create_invoice(self, order_ref: str) -> dict:
        return invoices.create_invoice(self._c, order_ref)

    def create_vendor_bill(self, vendor: str, lines: list[dict], date: str, ref: str | None = None) -> dict:
        return invoices.create_vendor_bill(self._c, vendor, lines, date, ref)

    def set_company(self, info: dict, logo: bytes | None) -> None:
        vals = {k: info[k] for k in _COMPANY_FIELDS if info.get(k)}
        if logo:
            vals["logo"] = base64.b64encode(logo).decode()

        [row] = self._c.search_read("res.company", [], ["id"], limit=1)
        self._c.write("res.company", [row["id"]], vals)

    def create_vendor(self, name: str, city: str | None = None) -> dict:
        return partners.create_partner(self._c, name, city=city)

    def create_product(
        self, name: str, price: float, cost: float = 0, code: str | None = None, category: str | None = None
    ) -> dict:
        return products.create_product(self._c, name, price, cost, code, category)

    def set_stock(self, product: str, quantity: float) -> None:
        products.set_stock(self._c, product, quantity)

    def seed_order(self, partner: str, lines: list[dict], date: str, invoice: bool) -> None:
        quote = sales.create_quotation(self._c, partner, lines)
        sales.confirm_order(self._c, quote["ref"])

        order = sales.resolve_order(self._c, quote["ref"])
        self._c.write("sale.order", [order["id"]], {"date_order": f"{date} {_SEED_ORDER_TIME}"})

        if invoice:
            invoices.create_invoice(self._c, quote["ref"])
