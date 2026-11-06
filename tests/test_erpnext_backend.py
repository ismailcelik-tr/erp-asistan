import datetime

from erp_asistan.tools import ToolRegistry


def _sale(erp, uniq, quantity=1):
    customer = erp.create_partner(f"Rapor Müşteri {uniq}")
    product = erp.create_product(f"Rapor Ürün {uniq}", price=1000)
    erp.set_stock(product["name"], 10)
    quote = erp.create_quotation(customer["name"], [{"product": product["name"], "quantity": quantity}])
    return customer, product, erp.confirm_order(quote["ref"])


def test_sales_summary(erpnext_erp, uniq):
    today = datetime.date.today().isoformat()
    before = erpnext_erp.sales_summary(today, today)

    _sale(erpnext_erp, uniq, quantity=3)
    after = erpnext_erp.sales_summary(today, today)

    assert after["order_count"] == before["order_count"] + 1
    assert round(after["untaxed"] - before["untaxed"], 2) == 3000
    assert round(after["total"] - before["total"], 2) == 3600


def test_compare_sales_computes_deltas(erpnext_erp, uniq):
    today = datetime.date.today().isoformat()
    _sale(erpnext_erp, uniq)

    result = erpnext_erp.compare_sales("2001-01-01", "2001-01-31", today, today)

    assert result["first"]["total"] == 0
    assert result["change"]["total"] == result["second"]["total"]
    assert result["change"]["total_pct"] is None


def test_company_info(erpnext_erp):
    info = erpnext_erp.company_info()

    assert info["name"]
    assert info["logo"] is None or info["logo"][:4] == b"\x89PNG"


def test_record_url_points_to_purchase_invoice(erpnext_erp):
    assert erpnext_erp.record_url("ACC-PINV-2026-00001").endswith("/app/purchase-invoice/ACC-PINV-2026-00001")


def test_seed_order_backdates_and_invoices(erpnext_erp, uniq):
    customer = erpnext_erp.create_partner(f"Seed Müşteri {uniq}")
    product = erpnext_erp.create_product(f"Seed Ürün {uniq}", price=500, code=f"SEED.{uniq}")
    erpnext_erp.set_stock(f"SEED.{uniq}", 5)

    erpnext_erp.seed_order(customer["name"], [{"product": f"SEED.{uniq}", "quantity": 2}], "2026-10-03", invoice=True)

    [order] = erpnext_erp.find_orders(partner=customer["name"])
    assert order["date"] == "2026-10-03"
    assert erpnext_erp.list_open_invoices(customer["name"])["total_residual"] == 1200


def test_tools_run_on_erpnext(erpnext_erp):
    result = ToolRegistry(erpnext_erp).run("confirm_order", {"order_ref": "YOK-999"})

    assert "bulunamadı" in result["error"]


def _png() -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", (40, 10), (220, 30, 40, 255)).save(buf, "PNG")
    return buf.getvalue()


def test_set_company_brands_the_ui(erpnext, erpnext_erp):
    name = erpnext_erp.company_info()["name"]

    erpnext_erp.set_company({"name": name}, _png())

    logo = erpnext.get_doc("Navbar Settings", "Navbar Settings")["app_logo"]
    site = erpnext.get_doc("Website Settings", "Website Settings")
    assert logo.startswith("/files/")
    assert (site["app_name"], site["app_logo"], site["splash_image"], site["favicon"]) == (f"{name} ERP", logo, logo, logo)
    assert erpnext.get_doc("System Settings", "System Settings")["app_name"] == f"{name} ERP"
    assert erpnext.get_doc("Company", name)["company_logo"] == logo
    [head] = erpnext.get_list("Letter Head", ["image"], filters=[["is_default", "=", 1]])
    assert head["image"] == logo
