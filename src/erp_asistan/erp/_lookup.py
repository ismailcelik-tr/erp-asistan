from erp_asistan.erp.errors import ErpError
from erp_asistan.odoo.client import OdooClient

_MAX_CANDIDATES = 5
_MIN_WORD = 3
_MIN_STEM = 4
# Turkish is agglutinative: "ofisi", "ofise" must still hit "Ofis".
_SUFFIX_SLACK = 2
_APOSTROPHES = "'’"


def _stems(text: str) -> list[str]:
    stems = []
    for word in text.split():
        for a in _APOSTROPHES:
            word = word.split(a)[0]
        word = word.strip(".,;:!?()")
        if len(word) < _MIN_WORD:
            continue
        stems.append(word[: max(_MIN_STEM, len(word) - _SUFFIX_SLACK)])
    return stems


def search(
    odoo: OdooClient, model: str, name: str, fields: list[str], limit: int, extra_domain: list = ()
) -> list[dict]:
    """Whole-phrase match first; else every word stem must match (AND)."""
    rows = odoo.search_read(model, [("name", "ilike", name), *extra_domain], fields, limit=limit)
    if rows:
        return rows

    stems = _stems(name)
    if not stems:
        return []

    domain = [*extra_domain, *(("name", "ilike", s) for s in stems)]
    return odoo.search_read(model, domain, fields, limit=limit)


def resolve(odoo: OdooClient, model: str, name: str, label: str, extra_domain: list = ()) -> dict:
    """Exact name match wins; otherwise a single match; else ErpError."""
    rows = search(odoo, model, name, ["id", "name"], _MAX_CANDIDATES + 1, extra_domain)

    exact = [r for r in rows if r["name"].casefold() == name.casefold()]
    if len(exact) == 1:
        return exact[0]

    if len(rows) == 1:
        return rows[0]

    if not rows:
        raise ErpError(f"'{name}' adında {label} bulunamadı.")

    names = ", ".join(r["name"] for r in rows[:_MAX_CANDIDATES])
    raise ErpError(f"'{name}' için birden fazla {label} var: {names}. Hangisi?")
