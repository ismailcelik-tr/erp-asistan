"""Invoice image → structured vendor bill, with arithmetic cross-checks."""

import datetime
import json
from pathlib import Path
from typing import Protocol

from erp_asistan.fmt import tl

__all__ = ["check", "read_invoice"]

_TOLERANCE_TL = 0.05
_DATE_FORMATS = ["%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]
_MAX_AGE_DAYS = 365

_PROMPT = """Bu bir Türk tedarikçi faturası. Faturayı kesen firmayı (alıcıyı değil) ve tüm kalemleri çıkar.
- date: faturada yazdığı gibi, hiç değiştirmeden (ör. 27.10.2026).
- line_count: "Mal / Hizmet" tablosundaki satır sayısı. lines dizisi tam bu kadar eleman içermeli.
- price_unit: KDV hariç birim fiyat.
- untaxed: Mal Hizmet Toplam Tutarı; vat: Hesaplanan KDV; total: Ödenecek Tutar.
- Sayıları Türkçe biçimden çevir: 1.540,00 → 1540.00. Hiçbir değeri tahmin etme; görselde ne yazıyorsa onu yaz."""

_NUM = {"type": "number"}
_SCHEMA = {
    "type": "object",
    "properties": {
        "vendor": {"type": "string"},
        "invoice_no": {"type": "string"},
        "date": {"type": "string"},
        # Counting rows before listing them stops the model from truncating the table.
        "line_count": {"type": "integer"},
        "lines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"description": {"type": "string"}, "quantity": _NUM, "price_unit": _NUM},
                "required": ["description", "quantity", "price_unit"],
            },
        },
        "untaxed": _NUM,
        "vat": _NUM,
        "total": _NUM,
    },
    "required": ["vendor", "invoice_no", "date", "line_count", "lines", "untaxed", "vat", "total"],
}


class _Extractor(Protocol):
    def extract(self, prompt: str, image: Path, fmt: dict | str) -> dict: ...


def read_invoice(llm: _Extractor, image: Path) -> dict:
    # Grammar-constrained `format=<schema>` truncated tables (1 of 3 rows, every run);
    # plain JSON mode with the schema in the prompt read all rows.
    prompt = f"{_PROMPT}\nYalnızca şu JSON şemasına uyan bir JSON döndür:\n{json.dumps(_SCHEMA, ensure_ascii=False)}"
    inv = llm.extract(prompt, image, "json")
    # The model garbled dates when asked to convert them (27.10.2026 → 2026-01-27).
    inv["date"] = _iso_date(str(inv.get("date", "")))
    return inv


def _iso_date(text: str) -> str:
    """Unparseable dates are returned as-is so a human can fix them."""
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(text.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return text


def check(inv: dict) -> list[str]:
    """User-facing warnings when the extracted numbers don't add up."""
    warnings = []
    line_sum = sum(l["quantity"] * l["price_unit"] for l in inv["lines"])

    if abs(line_sum - inv["untaxed"]) > _TOLERANCE_TL:
        warnings.append(f"Kalemlerin toplamı ({tl(line_sum)}) ara toplamla ({tl(inv['untaxed'])}) tutmuyor.")

    if abs(inv["untaxed"] + inv["vat"] - inv["total"]) > _TOLERANCE_TL:
        warnings.append(f"Ara toplam + KDV, Ödenecek Tutar ({tl(inv['total'])}) ile tutmuyor.")

    date_warning = _check_date(inv["date"])
    if date_warning:
        warnings.append(date_warning)

    return warnings


def _check_date(text: str) -> str | None:
    try:
        date = datetime.date.fromisoformat(text)
    except ValueError:
        return f"Tarih ({text}) okunamadı; YYYY-AA-GG biçiminde girin."

    age = (datetime.date.today() - date).days
    if age < 0 or age > _MAX_AGE_DAYS:
        return f"Tarih ({text}) beklenmedik; faturadaki tarihle karşılaştırın."
    return None
