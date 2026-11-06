import pytest

from erp_asistan.erp.errors import ErpError
from erp_asistan.erpnext import catalog


@pytest.fixture
def customer(erpnext, uniq):
    return catalog.create_partner(erpnext, name=f"Yılmaz Ltd {uniq}", city="İzmir")


@pytest.fixture
def product(erpnext, uniq):
    p = catalog.create_product(erpnext, name=f"Laptop {uniq}", price=25000, cost=20000)
    catalog.set_stock(erpnext, p["name"], 4)
    return p


def test_find_partner_with_city(erpnext, customer):
    [row] = catalog.find_partner(erpnext, customer["name"][:-2])

    assert (row["name"], row["type"], row["city"]) == (customer["name"], "customer", "İzmir")


def test_find_partner_includes_suppliers(erpnext, uniq):
    catalog.create_vendor(erpnext, f"Ostim Tedarik {uniq}")

    assert [r["type"] for r in catalog.find_partner(erpnext, f"Ostim Tedarik {uniq}")] == ["supplier"]


def test_resolve_ambiguous_partner_raises(erpnext, uniq):
    catalog.create_partner(erpnext, name=f"Kaya {uniq} A")
    catalog.create_partner(erpnext, name=f"Kaya {uniq} B")

    with pytest.raises(ErpError, match="birden fazla"):
        catalog.resolve_partner(erpnext, f"Kaya {uniq}")


def test_unknown_partner_raises(erpnext, uniq):
    with pytest.raises(ErpError, match="bulunamadı"):
        catalog.resolve_partner(erpnext, f"Yok {uniq}")


def test_find_partner_tolerates_turkish_suffixes(erpnext, customer, uniq):
    rows = catalog.find_partner(erpnext, f"Yılmaz'ın {uniq}")

    assert [r["name"] for r in rows] == [customer["name"]]


def test_product_price_and_stock(erpnext, product):
    [row] = catalog.find_products(erpnext, product["name"])

    assert (row["price"], row["stock"], row["code"]) == (25000, 4, None)


def test_low_stock_and_price_update(erpnext, product):
    low = catalog.get_low_stock(erpnext, threshold=5)
    assert product["name"] in [p["name"] for p in low]

    result = catalog.update_product_price(erpnext, product["name"], 27500)
    assert (result["old_price"], result["new_price"]) == (25000, 27500)
    assert catalog.find_products(erpnext, product["name"])[0]["price"] == 27500


def test_resolve_product_tolerates_suffixes(erpnext, product, uniq):
    assert catalog.resolve_product(erpnext, f"laptopu {uniq}")["name"] == product["name"]


def test_product_code_and_category(erpnext, uniq):
    code = f"M.U.TST.{uniq}"
    catalog.create_product(erpnext, name=f"Test Şube {uniq}", price=100, code=code, category=f"Kategori {uniq}")

    [row] = catalog.find_products(erpnext, code)
    assert row["code"] == code
    assert row["category"] == f"Kategori {uniq}"
    assert catalog.resolve_product(erpnext, code.lower())["name"] == f"Test Şube {uniq}"


def test_set_stock_again_adjusts_quantity(erpnext, product):
    catalog.set_stock(erpnext, product["name"], 9)

    assert catalog.find_products(erpnext, product["name"])[0]["stock"] == 9
