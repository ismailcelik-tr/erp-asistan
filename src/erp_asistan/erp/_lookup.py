from erp_asistan.erp.errors import ErpError
from erp_asistan.odoo.client import OdooClient

_MAX_CANDIDATES = 5
_MIN_WORD = 3
_MIN_STEM = 4
# Turkish is agglutinative: "ofisi", "ofise" must still hit "Ofis".
_SUFFIX_SLACK = 2
_APOSTROPHES = "'’"


def stems(text: str) -> list[str]:
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
    odoo: OdooClient,
    model: str,
    name: str,
    fields: list[str],
    limit: int,
    extra_domain: list = (),
    code_field: str | None = None,
) -> list[dict]:
    """Whole-phrase match (name or code) first; else every word stem must match the name (AND)."""
    phrase = [("name", "ilike", name)]
    if code_field:
        phrase = ["|", *phrase, (code_field, "ilike", name)]

    rows = odoo.search_read(model, [*phrase, *extra_domain], fields, limit=limit)
    if rows:
        return rows

    words = stems(name)
    if not words:
        return []

    domain = [*extra_domain, *(("name", "ilike", s) for s in words)]
    return odoo.search_read(model, domain, fields, limit=limit)


def resolve(
    odoo: OdooClient, model: str, name: str, label: str, extra_domain: list = (), code_field: str | None = None
) -> dict:
    """Exact name/code match wins; otherwise a single match; else ErpError."""
    fields = ["id", "name", *([code_field] if code_field else [])]
    rows = search(odoo, model, name, fields, _MAX_CANDIDATES + 1, extra_domain, code_field)

    key = name.casefold()
    exact = [r for r in rows if r["name"].casefold() == key or (code_field and str(r[code_field]).casefold() == key)]
    if len(exact) == 1:
        return {"id": exact[0]["id"], "name": exact[0]["name"]}

    if len(rows) == 1:
        return {"id": rows[0]["id"], "name": rows[0]["name"]}

    if not rows:
        raise ErpError(f"'{name}' adında {label} bulunamadı.")

    names = ", ".join(r["name"] for r in rows[:_MAX_CANDIDATES])
    raise ErpError(f"'{name}' için birden fazla {label} var: {names}. Hangisi?")
