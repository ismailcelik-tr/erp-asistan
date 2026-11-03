# erp-asistan

Natural-language (Turkish) assistant for Odoo 19 Community, running fully local on a laptop with Ollama (`gemma4:12b`).

```
web UI (FastAPI + static JS) ─ agent (tool calling, human approval for writes) ─ domain tools ─ Odoo JSON-2 API
```

- The model gets a small set of domain tools (`create_quotation`, `sales_summary`, …), not raw ORM access.
- Every write waits for an explicit approve/reject in the UI.
- Totals are computed by tools, never by the model.
- Vendor bills can be read from a photo; line sums are cross-checked before posting.
- Turkish voice commands via local Whisper (push-to-talk).

Reliability: `uv run python scripts/eval.py 5` → [docs/eval-2026-11-03.md](docs/eval-2026-11-03.md) (80/80 on 16 scenarios, temperature 0).

## Run

```bash
docker compose up -d
scripts/setup_db.sh erp        # prints an API key
cp .env.example .env           # fill ODOO_API_KEY
uv run python scripts/seed.py  # dataset from $SEED_DATASET (default data/demo, fictional)
uv run erp-asistan             # http://localhost:7860
```

A dataset is a folder with `dataset.json` (company, customers, vendors, coded products, order history) and an optional logo. Company-specific datasets belong in `private/` (git-ignored).

Tests need a second DB: `scripts/setup_db.sh erp_test` → `ODOO_TEST_DB` / `ODOO_TEST_API_KEY` in `.env`, then `uv run pytest`.
