from erp_asistan.tools import Kind, ToolRegistry


def test_schemas_cover_all_tools(odoo):
    reg = ToolRegistry(odoo)
    names = {s["function"]["name"] for s in reg.schemas()}

    assert {"find_partner", "create_quotation", "create_vendor_bill", "sales_summary"} <= names


def test_kinds(odoo):
    reg = ToolRegistry(odoo)

    assert reg.kind("get_low_stock") is Kind.READ
    assert reg.kind("confirm_order") is Kind.WRITE


def test_business_error_becomes_message(odoo):
    result = ToolRegistry(odoo).run("confirm_order", {"order_ref": "YOK-999"})

    assert "bulunamadı" in result["error"]


def test_unknown_tool(odoo):
    assert "error" in ToolRegistry(odoo).run("drop_database", {})
