"""Name/code search over Frappe doctypes; same semantics as erp._lookup (Odoo)."""

from erp_asistan.erp._lookup import stems
from erp_asistan.erp.errors import ErpError
from erp_asistan.erpnext.client import ErpNextClient

__all__ = ["resolve", "search"]

_MAX_CANDIDATES = 5


def _like(text: str) -> list:
    return ["like", f"%{text}%"]


def search(
    c: ErpNextClient,
    doctype: str,
    name_field: str,
    name: str,
    fields: list[str],
    limit: int,
    code_field: str | None = None,
    filters: list | tuple = (),
) -> list[dict]:
    """Whole-phrase match (name or code) first; else every word stem must match the name (AND)."""
    or_filters = [[name_field, *_like(name)]]
    if code_field:
        or_filters.append([code_field, *_like(name)])

    rows = c.get_list(doctype, fields, filters=filters, or_filters=or_filters, limit=limit)
    if rows:
        return rows

    words = stems(name)
    if not words:
        return []

    return c.get_list(doctype, fields, filters=[*filters, *([name_field, *_like(w)] for w in words)], limit=limit)


def resolve(
    c: ErpNextClient,
    doctype: str,
    name_field: str,
    name: str,
    label: str,
    code_field: str | None = None,
    filters: list | tuple = (),
) -> dict:
    """Exact name/code match wins; otherwise a single match; else ErpError."""
    fields = ["name", name_field, *([code_field] if code_field else [])]
    rows = search(c, doctype, name_field, name, fields, _MAX_CANDIDATES + 1, code_field, filters)

    key = name.casefold()
    exact = [
        r for r in rows
        if r[name_field].casefold() == key or (code_field and str(r[code_field]).casefold() == key)
    ]
    if len(exact) == 1:
        return {"id": exact[0]["name"], "name": exact[0][name_field]}

    if len(rows) == 1:
        return {"id": rows[0]["name"], "name": rows[0][name_field]}

    if not rows:
        raise ErpError(f"'{name}' adında {label} bulunamadı.")

    names = ", ".join(r[name_field] for r in rows[:_MAX_CANDIDATES])
    raise ErpError(f"'{name}' için birden fazla {label} var: {names}. Hangisi?")
