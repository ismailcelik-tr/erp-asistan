import pytest

from erp_asistan.erp.errors import ErpError
from erp_asistan.erpnext import catalog, sales


@pytest.fixture
def customer(erpnext, uniq):
    return catalog.create_partner(erpnext, name=f"Yılmaz Ltd {uniq}", city="İzmir")


@pytest.fixture
def product(erpnext, uniq):
    p = catalog.create_product(erpnext, name=f"Laptop {uniq}", price=25000, cost=20000)
    catalog.set_stock(erpnext, p["name"], 4)
    return p


def test_quotation_to_invoice_flow(erpnext, customer, product):
    quote = sales.create_quotation(erpnext, customer["name"], [{"product": product["name"], "quantity": 2}])
    assert quote["total"] == 60000  # 2 × 25.000 + %20 KDV

    order = sales.confirm_order(erpnext, quote["ref"])
    assert (order["state"], order["quotation"], order["total"]) == ("order", quote["ref"], quote["total"])

    inv = sales.create_invoice(erpnext, order["ref"])
    assert (inv["total"], inv["residual"], inv["untaxed"]) == (60000, 60000, 50000)

    result = sales.list_open_invoices(erpnext, customer["name"])
    assert [i["ref"] for i in result["invoices"]] == [inv["ref"]]
    assert result["total_residual"] == inv["total"]


def test_invoice_accepts_quotation_ref(erpnext, customer, product):
    quote = sales.create_quotation(erpnext, customer["name"], [{"product": product["name"], "quantity": 1}])
    sales.confirm_order(erpnext, quote["ref"])

    assert sales.create_invoice(erpnext, quote["ref"])["total"] == quote["total"]


def test_invoice_of_unconfirmed_quotation_raises(erpnext, customer, product):
    quote = sales.create_quotation(erpnext, customer["name"], [{"product": product["name"], "quantity": 1}])

    with pytest.raises(ErpError, match="onaylanmamış"):
        sales.create_invoice(erpnext, quote["ref"])


def test_confirm_twice_raises(erpnext, customer, product):
    quote = sales.create_quotation(erpnext, customer["name"], [{"product": product["name"], "quantity": 1}])
    sales.confirm_order(erpnext, quote["ref"])

    with pytest.raises(ErpError, match="zaten"):
        sales.confirm_order(erpnext, quote["ref"])


def test_unknown_ref_raises(erpnext):
    with pytest.raises(ErpError, match="bulunamadı"):
        sales.confirm_order(erpnext, "YOK-999")


def test_find_orders_by_partner_and_state(erpnext, customer, product):
    quote = sales.create_quotation(erpnext, customer["name"], [{"product": product["name"], "quantity": 1}])

    drafts = sales.find_orders(erpnext, partner=customer["name"], state="quotation")
    confirmed = sales.find_orders(erpnext, partner=customer["name"], state="order")
    assert [o["ref"] for o in drafts] == [quote["ref"]]
    assert confirmed == []

    order = sales.confirm_order(erpnext, quote["ref"])
    assert sales.find_orders(erpnext, partner=customer["name"], state="quotation") == []
    assert [o["ref"] for o in sales.find_orders(erpnext, partner=customer["name"])] == [order["ref"]]


def test_backdated_seed_order(erpnext, customer, product):
    quote = sales.create_quotation(erpnext, customer["name"], [{"product": product["name"], "quantity": 1}],
                                   date="2026-09-15")
    sales.confirm_order(erpnext, quote["ref"], date="2026-09-15")

    [row] = sales.find_orders(erpnext, partner=customer["name"], state="order")
    assert row["date"] == "2026-09-15"


def test_vendor_bill_creates_unknown_vendor(erpnext, uniq):
    bill = sales.create_vendor_bill(
        erpnext,
        vendor=f"Anadolu Kırtasiye {uniq}",
        lines=[{"description": "A4 kağıt", "quantity": 10, "price_unit": 150}],
        date="2026-11-01",
        ref=f"A-{uniq}",
    )

    assert (bill["untaxed"], bill["total"], bill["state"]) == (1500, 1800, "Draft")
    assert catalog.find_partner(erpnext, f"Anadolu Kırtasiye {uniq}")[0]["type"] == "supplier"


def test_vendor_bill_rejects_bad_date(erpnext):
    with pytest.raises(ErpError, match="Geçersiz tarih"):
        sales.create_vendor_bill(erpnext, "X", [], "01.11.2026")


def test_submitted_documents_show_their_status(erpnext, customer, product):
    quote = sales.create_quotation(erpnext, customer["name"], [{"product": product["name"], "quantity": 1}])
    assert erpnext.get_doc("Quotation", quote["ref"])["status"] == "Open"

    order = sales.confirm_order(erpnext, quote["ref"])
    assert erpnext.get_doc("Sales Order", order["ref"])["status"] != "Draft"
