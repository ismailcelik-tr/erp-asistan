from pathlib import Path

import pytest

from erp_asistan.invoice_reader import check, read_invoice
from erp_asistan.llm import OllamaLLM

SAMPLE = Path(__file__).parent.parent / "samples" / "invoices" / "fatura-anadolu-kirtasiye.png"


def _inv(**over):
    base = {
        "vendor": "X", "invoice_no": "1", "date": "2026-10-28",
        "lines": [{"description": "a", "quantity": 2, "price_unit": 50}],
        "untaxed": 100, "vat": 20, "total": 120,
    }
    return base | over


def test_consistent_invoice_has_no_warnings():
    assert check(_inv()) == []


def test_line_sum_mismatch_is_flagged():
    warnings = check(_inv(untaxed=110, total=132, vat=22))

    assert any("Kalem" in w for w in warnings)


def test_total_mismatch_is_flagged():
    assert any("Ödenecek" in w for w in check(_inv(total=150)))


@pytest.mark.llm
def test_reads_sample_invoice():
    inv = read_invoice(OllamaLLM(), SAMPLE)

    assert "Anadolu Kırtasiye" in inv["vendor"]
    assert inv["date"] == "2026-10-28"
    assert len(inv["lines"]) == 4
    assert inv["untaxed"] == pytest.approx(14540)
    assert check(inv) == []


@pytest.mark.llm
def test_reads_every_row_of_three_line_invoice():
    inv = read_invoice(OllamaLLM(), SAMPLE.with_name("fatura-ege-bilisim.png"))

    assert len(inv["lines"]) == 3
    assert check(inv) == []
