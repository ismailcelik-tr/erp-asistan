import base64

from erp_asistan.odoo.client import OdooClient

__all__ = ["company_info"]


def company_info(odoo: OdooClient) -> dict:
    [row] = odoo.search_read("res.company", [], ["name", "city", "logo"], limit=1)
    logo = base64.b64decode(row["logo"]) if row["logo"] else None
    return {"name": row["name"], "city": row["city"] or None, "logo": logo}
