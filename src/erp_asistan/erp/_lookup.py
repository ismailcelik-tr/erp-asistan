from erp_asistan.erp.errors import ErpError
from erp_asistan.odoo.client import OdooClient

_MAX_CANDIDATES = 5


def resolve(odoo: OdooClient, model: str, name: str, label: str, extra_domain: list = ()) -> dict:
    """Exact name match wins; otherwise a single ilike match; else ErpError."""
    domain = [("name", "ilike", name), *extra_domain]
    rows = odoo.search_read(model, domain, ["id", "name"], limit=_MAX_CANDIDATES + 1)

    exact = [r for r in rows if r["name"].casefold() == name.casefold()]
    if len(exact) == 1:
        return exact[0]

    if len(rows) == 1:
        return rows[0]

    if not rows:
        raise ErpError(f"'{name}' adında {label} bulunamadı.")

    names = ", ".join(r["name"] for r in rows[:_MAX_CANDIDATES])
    raise ErpError(f"'{name}' için birden fazla {label} var: {names}. Hangisi?")
