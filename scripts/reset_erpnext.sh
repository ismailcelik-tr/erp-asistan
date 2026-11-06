#!/usr/bin/env bash
# Recreates the ERPNext demo site ($ERPNEXT_SITE) with fresh seed data and rotates its API key in .env.
# ERPNext must be up. Restart the app afterwards: it holds the old key.
set -euo pipefail
cd "$(dirname "$0")/.."

SITE=$(grep '^ERPNEXT_SITE=' .env | cut -d= -f2)
DATASET=$(grep '^SEED_DATASET=' .env | cut -d= -f2)

CRED=$(uv run python scripts/setup_erpnext.py "$SITE" "$DATASET")
sed -i '' "s|^ERPNEXT_API_KEY=.*|ERPNEXT_API_KEY=${CRED%%:*}|; s|^ERPNEXT_API_SECRET=.*|ERPNEXT_API_SECRET=${CRED#*:}|" .env

ERP_DEFAULT=erpnext uv run python scripts/seed.py
