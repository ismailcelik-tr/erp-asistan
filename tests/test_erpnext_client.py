import pytest

from erp_asistan.erpnext.client import ErpNextError


def test_get_list_returns_company(erpnext):
    rows = erpnext.get_list("Company", ["name", "default_currency"])

    assert [r["default_currency"] for r in rows] == ["TRY"]


def test_insert_then_set_value(erpnext, uniq):
    doc = erpnext.insert({"doctype": "Customer", "customer_name": f"Test Cari {uniq}", "customer_type": "Company"})
    erpnext.set_value("Customer", doc["name"], {"website": "https://ornek.com.tr"})

    assert erpnext.get_doc("Customer", doc["name"])["website"] == "https://ornek.com.tr"


def test_get_list_without_limit_returns_all(erpnext):
    rows = erpnext.get_list("Account", ["name"])

    assert len(rows) > 20  # Frappe's default page size


def test_unknown_doctype_raises_readable_error(erpnext):
    with pytest.raises(ErpNextError) as e:
        erpnext.get_list("No Such Doctype", ["name"])

    assert "<" not in str(e.value)
