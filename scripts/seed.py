"""Seeds the demo DB with fictional Turkish data. Run once: uv run python scripts/seed.py"""

import datetime
import random

from dotenv import load_dotenv

from erp_asistan.erp import invoices, partners, products, sales
from erp_asistan.odoo.client import OdooClient

CUSTOMERS = [
    ("Anadolu Gıda Ltd. Şti.", "Ankara"),
    ("Ege Yapı Malzemeleri A.Ş.", "İzmir"),
    ("Karadeniz Lojistik", "Trabzon"),
    ("Marmara Ofis Çözümleri", "İstanbul"),
    ("Akdeniz Otelcilik A.Ş.", "Antalya"),
    ("Yılmaz Mimarlık", "Bursa"),
    ("Kaya Tekstil San. Tic.", "Denizli"),
    ("Doğu Eğitim Kurumları", "Erzurum"),
]

# name, price, cost, stock
PRODUCTS = [
    ("Dizüstü Bilgisayar Pro 14", 42000, 33000, 18),
    ("Dizüstü Bilgisayar Air 13", 31000, 24000, 3),
    ("27 inç Monitör", 8900, 6500, 25),
    ("Kablosuz Klavye Mouse Seti", 1450, 900, 60),
    ("Lazer Yazıcı", 7600, 5400, 2),
    ("Toner Kartuşu", 1850, 1100, 7),
    ("Ofis Sandalyesi Ergonomik", 5200, 3600, 12),
    ("Çalışma Masası 160 cm", 6800, 4700, 4),
    ("A4 Fotokopi Kağıdı (5 top)", 650, 420, 140),
    ("Projeksiyon Cihazı", 18500, 14000, 1),
    ("Ağ Switch 24 Port", 9400, 7000, 6),
    ("Harici SSD 1 TB", 3200, 2300, 35),
]

START = datetime.date(2026, 10, 1)
END = datetime.date(2026, 11, 2)
ORDER_COUNT = 26
INVOICE_RATIO = 0.6


def main() -> None:
    load_dotenv()
    odoo = OdooClient.from_env()
    random.seed(42)

    if partners.find_partner(odoo, CUSTOMERS[0][0]):
        print("Already seeded.")
        return

    for name, city in CUSTOMERS:
        partners.create_partner(odoo, name, city=city)

    for name, price, cost, stock in PRODUCTS:
        products.create_product(odoo, name, price=price, cost=cost)
        products.set_stock(odoo, name, stock)

    span = (END - START).days
    for _ in range(ORDER_COUNT):
        customer = random.choice(CUSTOMERS)[0]
        picks = random.sample(PRODUCTS, k=random.randint(1, 3))
        lines = [{"product": p[0], "quantity": random.randint(1, 4)} for p in picks]

        quote = sales.create_quotation(odoo, customer, lines)
        sales.confirm_order(odoo, quote["ref"])

        when = START + datetime.timedelta(days=random.randint(0, span))
        order = sales.resolve_order(odoo, quote["ref"])
        odoo.write("sale.order", [order["id"]], {"date_order": f"{when.isoformat()} 10:00:00"})

        if random.random() < INVOICE_RATIO:
            invoices.create_invoice(odoo, quote["ref"])

    # A few open quotations for the confirm/invoice demo.
    sales.create_quotation(odoo, "Akdeniz Otelcilik A.Ş.", [{"product": "27 inç Monitör", "quantity": 6}])
    sales.create_quotation(odoo, "Doğu Eğitim Kurumları", [{"product": "Projeksiyon Cihazı", "quantity": 1}])

    print("Seeded.")


if __name__ == "__main__":
    main()
