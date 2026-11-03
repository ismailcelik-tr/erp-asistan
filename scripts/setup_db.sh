#!/usr/bin/env bash
# Creates a TR-localized Odoo DB and prints an admin API key.
# Usage: scripts/setup_db.sh <db_name>
set -euo pipefail

DB="$1"
CONN=(--db_host db --db_user odoo --db_password odoo -d "$DB" --http-port 8070)
MODULES="sale_management,purchase,stock,account"

odoo_run() {
    docker compose exec -T odoo odoo "${CONN[@]}" --stop-after-init "$@" >/dev/null 2>&1
}

odoo_shell() {
    docker compose exec -T odoo odoo shell "${CONN[@]}" --no-http 2>/dev/null
}

odoo_run -i base --load-language tr_TR

# Country must be set before `account` install so the TR chart of accounts is picked.
odoo_shell <<'PY' >/dev/null
env.ref('base.TRY').active = True
env.company.write({
    'name': 'Demo Ticaret A.Ş.',
    'country_id': env.ref('base.tr').id,
    'currency_id': env.ref('base.TRY').id,
    'city': 'İstanbul',
})
env['res.users'].search([]).write({'lang': 'tr_TR', 'tz': 'Europe/Istanbul'})
env.cr.commit()
PY

odoo_run -i "$MODULES"

odoo_shell <<'PY' | tail -1
import datetime
admin = env.ref('base.user_admin')
expiry = datetime.datetime.now() + datetime.timedelta(days=90)
key = env['res.users.apikeys'].with_user(admin)._generate(None, 'erp-asistan', expiry)
env.cr.commit()
print(key)
PY
