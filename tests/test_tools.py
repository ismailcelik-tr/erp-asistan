from erp_asistan.erpnext.client import ErpNextError
from erp_asistan.tools import Kind, ToolRegistry


class FakeErp:
    quote_example = "Q-1"
    order_example = "O-1"

    def __getattr__(self, name):
        return lambda **kwargs: {"called": name, **kwargs}


class BrokenErp(FakeErp):
    def confirm_order(self, order_ref):
        raise ErpNextError("ERPNext hata verdi")


def test_runs_tools_through_erp():
    result = ToolRegistry(FakeErp()).run("find_partner", {"name": "Ege"})

    assert result == {"called": "find_partner", "name": "Ege"}


def test_ref_examples_come_from_erp():
    params = {s["function"]["name"]: s["function"]["parameters"]["properties"] for s in ToolRegistry(FakeErp()).schemas()}

    assert "Q-1" in params["confirm_order"]["order_ref"]["description"]
    assert "O-1" in params["create_invoice"]["order_ref"]["description"]


def test_driver_error_becomes_message():
    assert ToolRegistry(BrokenErp()).run("confirm_order", {"order_ref": "X"}) == {"error": "ERPNext hata verdi"}


def test_schemas_cover_all_tools(odoo_erp):
    reg = ToolRegistry(odoo_erp)
    names = {s["function"]["name"] for s in reg.schemas()}

    assert {"find_partner", "create_quotation", "create_vendor_bill", "sales_summary"} <= names


def test_kinds(odoo_erp):
    reg = ToolRegistry(odoo_erp)

    assert reg.kind("get_low_stock") is Kind.READ
    assert reg.kind("confirm_order") is Kind.WRITE


def test_business_error_becomes_message(odoo_erp):
    result = ToolRegistry(odoo_erp).run("confirm_order", {"order_ref": "YOK-999"})

    assert "bulunamadı" in result["error"]


def test_unknown_tool(odoo_erp):
    assert "error" in ToolRegistry(odoo_erp).run("drop_database", {})
