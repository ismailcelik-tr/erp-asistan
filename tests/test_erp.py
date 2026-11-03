import datetime

import pytest

from erp_asistan.erp import invoices, partners, products, reports, sales
from erp_asistan.erp.errors import ErpError


@pytest.fixture
def customer(odoo, uniq):
    return partners.create_partner(odoo, name=f"Yılmaz Ltd {uniq}", city="İzmir")


@pytest.fixture
def product(odoo, uniq):
    p = products.create_product(odoo, name=f"Laptop {uniq}", price=25000)
    products.set_stock(odoo, p["name"], 4)
    return p


def test_find_partner(odoo, customer):
    rows = partners.find_partner(odoo, customer["name"][:-2])

    assert customer["name"] in [r["name"] for r in rows]


def test_resolve_ambiguous_partner_raises(odoo, uniq):
    partners.create_partner(odoo, name=f"Kaya {uniq} A")
    partners.create_partner(odoo, name=f"Kaya {uniq} B")

    with pytest.raises(ErpError, match="birden fazla"):
        partners.resolve_partner(odoo, f"Kaya {uniq}")


def test_low_stock_and_price_update(odoo, product):
    low = products.get_low_stock(odoo, threshold=5)
    assert product["name"] in [p["name"] for p in low]

    result = products.update_product_price(odoo, product["name"], 27500)
    assert (result["old_price"], result["new_price"]) == (25000, 27500)


def test_quotation_to_invoice_flow(odoo, customer, product):
    quote = sales.create_quotation(
        odoo, customer["name"], [{"product": product["name"], "quantity": 2}]
    )
    assert quote["total"] > 0

    order = sales.confirm_order(odoo, quote["ref"])
    assert order["state"] == "sale"

    inv = invoices.create_invoice(odoo, quote["ref"])
    assert inv["total"] == quote["total"]

    result = invoices.list_open_invoices(odoo, customer["name"])
    assert inv["ref"] in [i["ref"] for i in result["invoices"]]
    assert result["count"] == 1
    assert result["total_residual"] == inv["total"]


def test_vendor_bill_creates_unknown_vendor(odoo, uniq):
    bill = invoices.create_vendor_bill(
        odoo,
        vendor=f"Anadolu Kırtasiye {uniq}",
        lines=[{"description": "A4 kağıt", "quantity": 10, "price_unit": 150}],
        date="2026-11-01",
    )

    assert bill["untaxed"] == 1500
    assert bill["state"] == "draft"


def test_sales_summary(odoo, customer, product):
    today = datetime.date.today().isoformat()
    before = reports.sales_summary(odoo, today, today)

    quote = sales.create_quotation(
        odoo, customer["name"], [{"product": product["name"], "quantity": 1}]
    )
    sales.confirm_order(odoo, quote["ref"])
    after = reports.sales_summary(odoo, today, today)

    assert after["order_count"] == before["order_count"] + 1
    assert after["total"] > before["total"]
