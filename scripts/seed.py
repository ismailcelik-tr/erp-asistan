"""Seeds the demo DB of $ERP_DEFAULT (odoo | erpnext) from a dataset folder (dataset.json + optional logo).

Usage: uv run python scripts/seed.py [dataset_dir]   (default: $SEED_DATASET or data/demo)
       ERP_DEFAULT=erpnext uv run python scripts/seed.py
"""

import datetime
import json
import os
import random
import sys
from pathlib import Path

from dotenv import load_dotenv

from erp_asistan.backends import DEFAULT_ERP, pick
from erp_asistan.erp.backend import Seedable

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = "data/demo"
MAX_LINES_PER_ORDER = 3
# (unit price TL above, max quantity): nobody orders 25 fire panels at once.
QTY_CAPS = [(50_000, 3), (10_000, 12), (2_000, 60)]


def _qty(rng: random.Random, price: float, lo: int, hi: int) -> int:
    cap = next((q for limit, q in QTY_CAPS if price > limit), hi)
    return rng.randint(min(lo, cap), min(hi, cap))


def _orders(erp: Seedable, ds: dict) -> None:
    cfg = ds["orders"]
    rng = random.Random(cfg["random_seed"])
    start = datetime.date.fromisoformat(cfg["start"])
    span = (datetime.date.fromisoformat(cfg["end"]) - start).days

    # rng call order is part of the dataset: changing it changes every order.
    for _ in range(cfg["count"]):
        customer = rng.choice(ds["customers"])
        pool = [p for p in ds["products"] if not customer.get("buys") or p["category"] in customer["buys"]]
        picks = rng.sample(pool, k=min(len(pool), rng.randint(1, MAX_LINES_PER_ORDER)))
        lo, hi = customer["qty"]
        lines = [{"product": p.get("code") or p["name"], "quantity": _qty(rng, p["price"], lo, hi)} for p in picks]

        when = start + datetime.timedelta(days=rng.randint(0, span))
        invoice = rng.random() < cfg["invoice_ratio"]
        erp.seed_order(customer["name"], lines, when.isoformat(), invoice)


def main() -> None:
    load_dotenv(ROOT / ".env")
    folder = ROOT / (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SEED_DATASET", DEFAULT_DATASET))
    ds = json.loads((folder / "dataset.json").read_text())
    slot = pick(os.environ.get("ERP_DEFAULT", DEFAULT_ERP))
    erp: Seedable = slot.erp

    if erp.find_partner(ds["customers"][0]["name"]):
        print("Already seeded.")
        return

    info = ds["company"]
    erp.set_company(info, (folder / info["logo"]).read_bytes() if info.get("logo") else None)

    for c in ds["customers"]:
        erp.create_partner(c["name"], city=c.get("city"))
    for v in ds["vendors"]:
        erp.create_vendor(v["name"], city=v.get("city"))

    for p in ds["products"]:
        erp.create_product(p["name"], price=p["price"], cost=p.get("cost", 0), code=p.get("code"),
                           category=p.get("category"))
        erp.set_stock(p.get("code") or p["name"], p["stock"])

    _orders(erp, ds)

    for q in ds["open_quotations"]:
        erp.create_quotation(q["partner"], q["lines"])

    print(f"Seeded {folder.name} into {slot.label}: {len(ds['products'])} products, {ds['orders']['count']} orders.")


if __name__ == "__main__":
    main()
