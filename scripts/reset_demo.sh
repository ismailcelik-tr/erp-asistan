#!/usr/bin/env bash
# Recreates the demo DB ($ODOO_DB) with fresh seed data and rotates ODOO_API_KEY in .env.
# Restart the app afterwards: it holds the old key.
set -euo pipefail
cd "$(dirname "$0")/.."

DB=$(grep '^ODOO_DB=' .env | cut -d= -f2)

docker compose exec -T db dropdb -U odoo --if-exists --force "$DB"
docker compose exec -T odoo rm -rf "/var/lib/odoo/filestore/$DB"

KEY=$(scripts/setup_db.sh "$DB")
sed -i '' "s|^ODOO_API_KEY=.*|ODOO_API_KEY=$KEY|" .env

rm -rf history  # conversation transcripts
uv run python scripts/seed.py
