"""Seeds the demo DB from a dataset folder (dataset.json + optional logo).

Usage: uv run python scripts/seed.py [dataset_dir]   (default: $SEED_DATASET or data/demo)
"""

import base64
import datetime
import json
import os
import random
import sys
from pathlib import Path

from dotenv import load_dotenv

from erp_asistan.erp import invoices, partners, products, sales
from erp_asistan.odoo.client import OdooClient

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = "data/demo"
MAX_LINES_PER_ORDER = 3
COMPANY_FIELDS = ["name", "street", "city", "zip", "phone", "email", "website"]
# (unit price TL above, max quantity): nobody orders 25 fire panels at once.
QTY_CAPS = [(50_000, 3), (10_000, 12), (2_000, 60)]


def _qty(rng: random.Random, price: float, lo: int, hi: int) -> int:
    cap = next((q for limit, q in QTY_CAPS if price > limit), hi)
    return rng.randint(min(lo, cap), min(hi, cap))


def _company(odoo: OdooClient, info: dict, folder: Path) -> None:
    vals = {k: info[k] for k in COMPANY_FIELDS if info.get(k)}
    if info.get("logo"):
        vals["logo"] = base64.b64encode((folder / info["logo"]).read_bytes()).decode()

    [company] = odoo.search_read("res.company", [], ["id"], limit=1)
    odoo.write("res.company", [company["id"]], vals)


def _orders(odoo: OdooClient, ds: dict) -> None:
    cfg = ds["orders"]
    rng = random.Random(cfg["random_seed"])
    start = datetime.date.fromisoformat(cfg["start"])
    span = (datetime.date.fromisoformat(cfg["end"]) - start).days

    for _ in range(cfg["count"]):
        customer = rng.choice(ds["customers"])
        pool = [p for p in ds["products"] if not customer.get("buys") or p["category"] in customer["buys"]]
        picks = rng.sample(pool, k=min(len(pool), rng.randint(1, MAX_LINES_PER_ORDER)))
        lo, hi = customer["qty"]
        lines = [{"product": p.get("code") or p["name"], "quantity": _qty(rng, p["price"], lo, hi)} for p in picks]

        quote = sales.create_quotation(odoo, customer["name"], lines)
        sales.confirm_order(odoo, quote["ref"])

        when = start + datetime.timedelta(days=rng.randint(0, span))
        order = sales.resolve_order(odoo, quote["ref"])
        odoo.write("sale.order", [order["id"]], {"date_order": f"{when.isoformat()} 10:00:00"})

        if rng.random() < cfg["invoice_ratio"]:
            invoices.create_invoice(odoo, quote["ref"])


def main() -> None:
    load_dotenv(ROOT / ".env")
    folder = ROOT / (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SEED_DATASET", DEFAULT_DATASET))
    ds = json.loads((folder / "dataset.json").read_text())
    odoo = OdooClient.from_env()

    if partners.find_partner(odoo, ds["customers"][0]["name"]):
        print("Already seeded.")
        return

    _company(odoo, ds["company"], folder)

    for c in ds["customers"]:
        partners.create_partner(odoo, c["name"], city=c.get("city"))
    for v in ds["vendors"]:
        partners.create_partner(odoo, v["name"], city=v.get("city"))

    for p in ds["products"]:
        products.create_product(odoo, p["name"], price=p["price"], cost=p.get("cost", 0),
                                code=p.get("code"), category=p.get("category"))
        products.set_stock(odoo, p.get("code") or p["name"], p["stock"])

    _orders(odoo, ds)

    for q in ds["open_quotations"]:
        sales.create_quotation(odoo, q["partner"], q["lines"])

    print(f"Seeded {folder.name}: {len(ds['products'])} products, {ds['orders']['count']} orders.")


if __name__ == "__main__":
    main()
