"""ERPNext implementation of the ERP contract."""

from urllib.parse import quote

from erp_asistan.erpnext import catalog, reports, sales
from erp_asistan.erpnext.client import ErpNextClient

__all__ = ["ErpNextErp"]

_LOGO_NAME = "logo.png"


class ErpNextErp:
    quote_example = "SAL-QTN-2026-00012"
    order_example = "SAL-ORD-2026-00012"

    def __init__(self, client: ErpNextClient) -> None:
        self._c = client

    def company_info(self) -> dict:
        [row] = self._c.get_list("Company", ["company_name", "company_logo"], limit=1)
        logo = self._c.file(row["company_logo"]) if row["company_logo"] else None
        return {"name": row["company_name"], "city": None, "logo": logo}

    def record_url(self, record_id: int | str) -> str:
        return f"{self._c.url}/app/purchase-invoice/{quote(str(record_id))}"

    def find_partner(self, name: str) -> list[dict]:
        return catalog.find_partner(self._c, name)

    def find_products(self, name: str) -> list[dict]:
        return catalog.find_products(self._c, name)

    def get_low_stock(self, threshold: float) -> list[dict]:
        return catalog.get_low_stock(self._c, threshold)

    def list_open_invoices(self, partner: str | None = None) -> dict:
        return sales.list_open_invoices(self._c, partner)

    def find_orders(self, partner: str | None = None, state: str | None = None) -> list[dict]:
        return sales.find_orders(self._c, partner, state)

    def sales_summary(self, date_from: str, date_to: str) -> dict:
        return reports.sales_summary(self._c, date_from, date_to)

    def compare_sales(self, first_from: str, first_to: str, second_from: str, second_to: str) -> dict:
        return reports.compare_sales(self._c, first_from, first_to, second_from, second_to)

    def create_partner(
        self, name: str, city: str | None = None, phone: str | None = None, email: str | None = None
    ) -> dict:
        return catalog.create_partner(self._c, name, city, phone, email)

    def update_product_price(self, product: str, price: float) -> dict:
        return catalog.update_product_price(self._c, product, price)

    def create_quotation(self, partner: str, lines: list[dict]) -> dict:
        return sales.create_quotation(self._c, partner, lines)

    def confirm_order(self, order_ref: str) -> dict:
        return sales.confirm_order(self._c, order_ref)

    def create_invoice(self, order_ref: str) -> dict:
        return sales.create_invoice(self._c, order_ref)

    def create_vendor_bill(self, vendor: str, lines: list[dict], date: str, ref: str | None = None) -> dict:
        return sales.create_vendor_bill(self._c, vendor, lines, date, ref)

    def set_company(self, info: dict, logo: bytes | None) -> None:
        """Name is set by setup_erpnext.py: renaming a Company in ERPNext rewrites every linked record."""
        if not logo:
            return

        [row] = self._c.get_list("Company", ["name"], limit=1)
        url = self._c.upload(_LOGO_NAME, logo, "Company", row["name"], "company_logo")
        self._c.set_value("Company", row["name"], {"company_logo": url})

    def create_vendor(self, name: str, city: str | None = None) -> dict:
        return catalog.create_vendor(self._c, name, city)

    def create_product(
        self, name: str, price: float, cost: float = 0, code: str | None = None, category: str | None = None
    ) -> dict:
        return catalog.create_product(self._c, name, price, cost, code, category)

    def set_stock(self, product: str, quantity: float) -> None:
        catalog.set_stock(self._c, product, quantity)

    def seed_order(self, partner: str, lines: list[dict], date: str, invoice: bool) -> None:
        quote_ = sales.create_quotation(self._c, partner, lines, date=date)
        order = sales.confirm_order(self._c, quote_["ref"], date=date)
        if invoice:
            sales.create_invoice(self._c, order["ref"])
