# erp-asistan

Natural-language (Turkish) assistant for Odoo 19 Community, running fully local on a laptop with Ollama (`gemma4:12b`).

```
Gradio UI ─ agent (tool calling, human approval for writes) ─ domain tools ─ Odoo JSON-2 API
```

- The model gets a small set of domain tools (`create_quotation`, `sales_summary`, …), not raw ORM access.
- Every write waits for an explicit approve/reject in the UI.
- Totals are computed by tools, never by the model.

## Run

```bash
docker compose up -d
scripts/setup_db.sh erp        # prints an API key
cp .env.example .env           # fill ODOO_API_KEY
uv run python scripts/seed.py  # fictional Turkish demo data
uv run erp-asistan             # http://localhost:7860
```

Tests need a second DB: `scripts/setup_db.sh erp_test` → `ODOO_TEST_DB` / `ODOO_TEST_API_KEY` in `.env`, then `uv run pytest`.
