"""Renders fictional Turkish vendor invoices to samples/invoices/*.png."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
OUT = Path(__file__).resolve().parent.parent / "samples" / "invoices"
VAT_RATE = 0.20
WIDTH, HEIGHT = 1240, 1754  # A4 @ 150 dpi

INVOICES = [
    {
        "file": "fatura-anadolu-kirtasiye.png",
        "vendor": "Anadolu Kırtasiye ve Ofis Malz. Ltd. Şti.",
        "address": "Kızılay Mah. Atatürk Blv. No:112 Çankaya / ANKARA",
        "tax": "Çankaya V.D. 0681234567",
        "no": "AKO2026000418",
        "date": "28.10.2026",
        "lines": [
            ("A4 Fotokopi Kağıdı 80 gr (koli)", 20, 540.00),
            ("Tükenmez Kalem Mavi (50'li)", 6, 275.00),
            ("Klasör Geniş Sırt", 40, 38.50),
            ("Yapışkan Not Kağıdı 76x76", 25, 22.00),
        ],
    },
    {
        "file": "fatura-ege-bilisim.png",
        "vendor": "Ege Bilişim Teknolojileri A.Ş.",
        "address": "Alsancak Mah. Kıbrıs Şehitleri Cad. No:45 Konak / İZMİR",
        "tax": "Kordon V.D. 3349876501",
        "no": "EBT2026001173",
        "date": "02.11.2026",
        "lines": [
            ("Ağ Kablosu Cat6 305 m", 2, 4850.00),
            ("Kablosuz Erişim Noktası AX3000", 3, 3900.00),
            ("Kurulum ve Yapılandırma Hizmeti", 1, 6500.00),
        ],
    },
]


def _tl(v: float) -> str:
    s = f"{v:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") + " TL"


def render(inv: dict) -> None:
    img = Image.new("RGB", (WIDTH, HEIGHT), "white")
    d = ImageDraw.Draw(img)
    f = lambda size, bold=False: ImageFont.truetype(FONT_BOLD if bold else FONT, size)

    d.text((80, 80), inv["vendor"], font=f(34, True), fill="black")
    d.text((80, 130), inv["address"], font=f(22), fill="#333")
    d.text((80, 162), inv["tax"], font=f(22), fill="#333")
    d.text((WIDTH - 380, 80), "e-ARŞİV FATURA", font=f(34, True), fill="#1d4ed8")
    d.text((WIDTH - 380, 135), f"Fatura No: {inv['no']}", font=f(22), fill="black")
    d.text((WIDTH - 380, 167), f"Tarih: {inv['date']}", font=f(22), fill="black")

    d.text((80, 250), "SAYIN", font=f(22, True), fill="black")
    d.text((80, 282), "Demo Ticaret A.Ş. — İstanbul", font=f(22), fill="black")

    cols = [80, 700, 860, 1040]
    y = 380
    d.rectangle([70, y - 10, WIDTH - 70, y + 36], fill="#e5e7eb")
    for x, h in zip(cols, ["Mal / Hizmet", "Miktar", "Birim Fiyat", "Tutar"]):
        d.text((x, y), h, font=f(22, True), fill="black")

    untaxed = 0.0
    for desc, qty, price in inv["lines"]:
        y += 56
        amount = qty * price
        untaxed += amount
        d.text((cols[0], y), desc, font=f(22), fill="black")
        d.text((cols[1], y), str(qty), font=f(22), fill="black")
        d.text((cols[2], y), _tl(price), font=f(22), fill="black")
        d.text((cols[3], y), _tl(amount), font=f(22), fill="black")
        d.line([70, y + 40, WIDTH - 70, y + 40], fill="#d1d5db")

    vat = untaxed * VAT_RATE
    y += 100
    for label, value, bold in [
        ("Mal Hizmet Toplam Tutarı", untaxed, False),
        ("Hesaplanan KDV (%20)", vat, False),
        ("Ödenecek Tutar", untaxed + vat, True),
    ]:
        d.text((640, y), label, font=f(24, bold), fill="black")
        d.text((1040, y), _tl(value), font=f(24, bold), fill="black")
        y += 44

    img.save(OUT / inv["file"])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for inv in INVOICES:
        render(inv)
        print("wrote", inv["file"])


if __name__ == "__main__":
    main()
