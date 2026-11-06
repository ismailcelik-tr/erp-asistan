"""Recreates an ERPNext site for the dataset's company; prints the Administrator "api_key:api_secret".

Usage: uv run python scripts/setup_erpnext.py <site> [dataset_dir]   (default dataset: $SEED_DATASET or data/demo)
ERPNext must be up: docker compose -f docker/erpnext/compose.yml up -d
"""

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ["docker", "compose", "-f", str(ROOT / "docker" / "erpnext" / "compose.yml")]
URL = "http://localhost:8080"
DB_ROOT_PASSWORD = "admin"
ADMIN_PASSWORD = "admin"
DEFAULT_DATASET = "data/demo"
# The setup wizard builds the chart of accounts synchronously.
TIMEOUT_SECONDS = 600
HTTP_OK = 200
# Wizard in English keeps record names predictable (Stores, Products, Standard Selling); UI switches to Turkish after.
WIZARD_LANGUAGE = "English"
UI_LANGUAGE = "tr"
COUNTRY_NAMES = ["Türkiye", "Turkey"]
TAX_PARENT = "Duties and Taxes"
VAT_RATE = 20
VAT_ACCOUNTS = ["Hesaplanan KDV", "İndirilecek KDV"]
ABBR_WORDS = 3


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _bench(*args: str, check: bool = True) -> None:
    subprocess.run([*COMPOSE, "exec", "-T", "backend", "bench", *args],
                   check=check, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _recreate(site: str) -> None:
    _bench("drop-site", site, "--force", "--no-backup", "--db-root-password", DB_ROOT_PASSWORD, check=False)
    _bench("new-site", site, "--mariadb-user-host-login-scope=%", "--admin-password", ADMIN_PASSWORD,
           "--db-root-username", "root", "--db-root-password", DB_ROOT_PASSWORD, "--install-app", "erpnext")


def _login(site: str) -> httpx.Client:
    http = httpx.Client(base_url=URL, headers={"Host": site}, timeout=TIMEOUT_SECONDS)
    resp = http.post("/api/method/login", json={"usr": "Administrator", "pwd": ADMIN_PASSWORD})
    if resp.status_code != HTTP_OK:
        sys.exit(f"login: {resp.text[:500]}")
    return http


def _call(http: httpx.Client, method: str, **params):
    resp = http.post(f"/api/method/{method}", json=params)
    if resp.status_code != HTTP_OK:
        sys.exit(f"{method}: {resp.text[:1000]}")
    return resp.json().get("message")


def _abbr(company: str) -> str:
    return "".join(w[0] for w in company.split()[:ABBR_WORDS]).upper()


def _country(http: httpx.Client) -> str:
    rows = _call(http, "frappe.client.get_list", doctype="Country", fields=["name"],
                 filters=[["name", "in", COUNTRY_NAMES]])
    if not rows:
        sys.exit("Country Türkiye/Turkey not found")
    return rows[0]["name"]


def _wizard(http: httpx.Client, company: str) -> None:
    year = datetime.date.today().year
    args = {
        "language": WIZARD_LANGUAGE, "country": _country(http), "timezone": "Europe/Istanbul",
        "currency": "TRY", "company_name": company, "company_abbr": _abbr(company),
        "chart_of_accounts": "Standard", "fy_start_date": f"{year}-01-01", "fy_end_date": f"{year}-12-31",
        "setup_demo": 0,
    }
    _call(http, "frappe.desk.page.setup_wizard.setup_wizard.setup_complete", args=json.dumps(args))


def _vat_accounts(http: httpx.Client, company: str) -> None:
    parent = _call(http, "frappe.client.get_value", doctype="Account", fieldname="name",
                   filters={"account_name": TAX_PARENT, "company": company})["name"]
    for name in VAT_ACCOUNTS:
        _call(http, "frappe.client.insert", doc={
            "doctype": "Account", "account_name": name, "parent_account": parent, "company": company,
            "account_type": "Tax", "tax_rate": VAT_RATE,
        })


def _settings(http: httpx.Client) -> None:
    # Outstanding = grand total, as in Odoo; otherwise totals are rounded to whole lira.
    _call(http, "frappe.client.set_value", doctype="Global Defaults", name="Global Defaults",
          fieldname="disable_rounded_total", value=1)
    _call(http, "frappe.client.set_value", doctype="System Settings", name="System Settings",
          fieldname="language", value=UI_LANGUAGE)
    _call(http, "frappe.client.set_value", doctype="User", name="Administrator",
          fieldname="language", value=UI_LANGUAGE)


def _api_key(http: httpx.Client) -> str:
    secret = _call(http, "frappe.core.doctype.user.user.generate_keys", user="Administrator")["api_secret"]
    key = _call(http, "frappe.client.get_value", doctype="User", fieldname="api_key",
                filters="Administrator")["api_key"]
    return f"{key}:{secret}"


def main() -> None:
    load_dotenv(ROOT / ".env")
    site = sys.argv[1]
    folder = ROOT / (sys.argv[2] if len(sys.argv) > 2 else os.environ.get("SEED_DATASET", DEFAULT_DATASET))
    company = json.loads((folder / "dataset.json").read_text())["company"]["name"]

    _log(f"{site}: recreating site")
    _recreate(site)
    http = _login(site)
    _log(f"{site}: setup wizard for {company}")
    _wizard(http, company)
    _vat_accounts(http, company)
    _settings(http)
    print(_api_key(http))


if __name__ == "__main__":
    main()
