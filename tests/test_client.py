import pytest

from erp_asistan.odoo.client import OdooError


def test_search_read_returns_company(odoo):
    rows = odoo.search_read("res.partner", [("is_company", "=", True)], ["name"])

    assert "Demo Ticaret A.Ş." in [r["name"] for r in rows]


def test_create_then_write(odoo):
    [pid] = odoo.create("res.partner", [{"name": "Test Cari"}])
    odoo.write("res.partner", [pid], {"city": "Ankara"})

    [row] = odoo.search_read("res.partner", [("id", "=", pid)], ["city"])
    assert row["city"] == "Ankara"


def test_unknown_model_raises(odoo):
    with pytest.raises(OdooError):
        odoo.search_read("no.such.model", [], ["name"])
