from erp_asistan.erp._lookup import resolve, search
from erp_asistan.odoo.client import OdooClient

__all__ = ["find_partner", "resolve_partner", "create_partner"]

_FIELDS = ["id", "name", "city", "phone", "email"]
_SEARCH_LIMIT = 10


def find_partner(odoo: OdooClient, name: str) -> list[dict]:
    return search(odoo, "res.partner", name, _FIELDS, _SEARCH_LIMIT)


def resolve_partner(odoo: OdooClient, name: str) -> dict:
    return resolve(odoo, "res.partner", name, "cari")


def create_partner(
    odoo: OdooClient,
    name: str,
    city: str | None = None,
    phone: str | None = None,
    email: str | None = None,
) -> dict:
    vals = {"name": name, "is_company": True, "city": city, "phone": phone, "email": email}
    [pid] = odoo.create("res.partner", [{k: v for k, v in vals.items() if v}])
    return {"id": pid, "name": name}
