# ERPNext Backend + ERP Seçici — Uygulama Planı

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Asistan, Odoo'ya dokunmadan ERPNext ile de çalışsın. Sağ üstteki seçiciden Odoo / ERPNext seçilsin; kapalı ERP ekranda "kapalı" görünsün, açılınca kendiliğinden açık görünsün.

**Architecture:** `erp/backend.py` ERP'den bağımsız bir sözleşme (`Erp` Protocol) tanımlar. Mevcut Odoo kodu `OdooErp` ile bu sözleşmeye bağlanır. Yeni `erpnext/` paketi aynı sözleşmeyi Frappe REST API ile uygular. `Session` yapılandırılmış ERP'leri ve aktif olanı tutar; web katmanı yalnız `Session` ile konuşur. Arayüz `/api/health` yoklamasıyla (10 sn) ERP durumlarını günceller.

**Tech Stack:** Python 3.12, FastAPI, httpx, pytest; ERPNext v16.53.0 (frappe/erpnext Docker imajı, MariaDB 11.8, Redis 6.2); vanilla JS.

## Global Constraints

- Odoo ortamı (`docker-compose.yml`, `erp-asistan-db-1`, `erp-asistan-odoo-1`, volume'lar) değişmez. ERPNext ayrı compose projesi: `erp-asistan-erpnext`, port `8080`.
- Aynı anda yalnız bir ERP açık olur (16 GB RAM, Docker Desktop 3 GB). Açma/kapama Docker Desktop'tan İsmail tarafından yapılır; uygulama Docker'ı yönetmez.
- Kapalı ERP seçicide `· kapalı` etiketiyle, seçilemez görünür. Açılınca 10 sn içinde seçilebilir olur.
- ERP değişince sohbet sıfırlanır (eski sohbet geçmişte kalır).
- ERPNext'e Netelsan veri setinin aynısı (`SEED_DATASET`) yüklenir. Özet kartları Odoo ile aynı ya da kuruş farkıyla aynı çıkmalı.
- ERPNext'te 13 aracın hepsi çalışır.
- Kod, yorum, commit mesajı İngilizce. Commit: 50 karakter başlık, emir kipi. Yorum yalnız açık olmayan iş mantığı için.
- Sihirli sayı/string yok: anlamlı değerler sabit. Erken dönüş. JS'te tek satırlık `if` için de `{}`.
- Her davranış için önce başarısız test, sonra kod (TDD).
- **Commit adımları yalnız İsmail'in onayıyla çalışır** (bu oturumun kuralı).
- Odoo testleri Odoo açıkken, ERPNext testleri ERPNext açıkken koşar; kapalı olanın testleri `skip` olur.

## Dosya Yapısı

| Dosya | Durum | Sorumluluk |
|---|---|---|
| `docker/erpnext/compose.yml` | Yeni | ERPNext container'ları (ayrı proje) |
| `scripts/setup_erpnext.py` | Yeni | Site oluşturma, kurulum sihirbazı, KDV hesapları, API anahtarı |
| `scripts/reset_erpnext.sh` | Yeni | Demo sitesini sıfırla + seed |
| `src/erp_asistan/erp/backend.py` | Yeni | `Erp`, `Seedable` Protocol |
| `src/erp_asistan/erp/odoo_erp.py` | Yeni | `OdooErp`: mevcut Odoo fonksiyonlarını sözleşmeye bağlar |
| `src/erp_asistan/erp/_lookup.py` | Değişir | `_stems` → `stems` (ERPNext de kullanır) |
| `src/erp_asistan/erp/reports.py` | Değişir | `period`, `summarize`, `compare` ortak yardımcılar |
| `src/erp_asistan/erpnext/client.py` | Yeni | Frappe REST sürücüsü |
| `src/erp_asistan/erpnext/lookup.py` | Yeni | İsim/kod arama ve çözümleme |
| `src/erp_asistan/erpnext/catalog.py` | Yeni | Cari, tedarikçi, ürün, stok, fiyat |
| `src/erp_asistan/erpnext/sales.py` | Yeni | Teklif, sipariş, satış ve alış faturası |
| `src/erp_asistan/erpnext/reports.py` | Yeni | Satış özeti ve karşılaştırma |
| `src/erp_asistan/erpnext/backend.py` | Yeni | `ErpNextErp` |
| `src/erp_asistan/session.py` | Yeni | `Slot`, `Session`, `ErpClosed` |
| `src/erp_asistan/backends.py` | Yeni | `.env`'den ERP listesi, `pick`, `reachable` |
| `src/erp_asistan/tools.py` | Değişir | `ToolRegistry(erp: Erp)` |
| `src/erp_asistan/agent.py` | Değişir | Sistem prompt'unda "Odoo" kalkar |
| `src/erp_asistan/history.py` | Değişir | Sohbet hangi ERP'de geçti (`erp`) |
| `src/erp_asistan/web.py` | Değişir | `Services.session`, `POST /api/erp`, `health.erps` |
| `src/erp_asistan/static/{index.html,app.js,app.css}` | Değişir | Seçici, "ERP'ye işle" |
| `scripts/seed.py`, `scripts/eval.py` | Değişir | `ERP_DEFAULT` ile ERP seçimi |
| `tests/conftest.py` | Değişir | `odoo_erp`, `erpnext`, `erpnext_erp` fixture; kapalıysa skip |
| `tests/test_erpnext_*.py`, `tests/test_session.py` | Yeni | |
| `.env.example`, `README.md`, `DEMO.md` | Değişir | |

---

### Task 1: ERPNext Docker ortamı ve kurulum scripti

Altyapı görevi: birim testi yok, doğrulama komutlarla. Bu görev ayrıca sonraki görevlerin dayandığı ERPNext API varsayımlarını doğrular (Adım 8).

**Files:**
- Create: `docker/erpnext/compose.yml`
- Create: `scripts/setup_erpnext.py`
- Modify: `.env.example`

**Interfaces:**
- Produces: `http://localhost:8080` üzerinde iki site: `localhost` (demo) ve `test.localhost` (testler). nginx siteyi `Host` başlığından seçer. `setup_erpnext.py <site> [dataset_dir]` stdout'a tek satır `api_key:api_secret` basar.
- Produces (sitede): şirket = dataset'teki şirket adı, ülke Türkiye, para birimi TRY, yuvarlanmış toplam kapalı, `Hesaplanan KDV` ve `İndirilecek KDV` hesapları (%20), arayüz dili Türkçe.

- [ ] **Step 1: Compose dosyasını yaz**

`frappe_docker/pwd.yml`'den türetildi. Farklar: proje adı sabit; `create-site` yok (siteleri script kurar); tek worker tüm kuyrukları dinler (RAM); nginx siteyi `Host`'tan seçer; MariaDB buffer küçük.

```yaml
# ERPNext, separate from Odoo (docker-compose.yml). Start/stop from Docker Desktop.
# Sites: localhost (demo), test.localhost (tests); nginx picks the site from the Host header.
name: erp-asistan-erpnext

x-erpnext: &erpnext
  image: frappe/erpnext:v16.53.0
  networks: [frappe_network]
  volumes:
    - sites:/home/frappe/frappe-bench/sites
    - logs:/home/frappe/frappe-bench/logs

services:
  configurator:
    <<: *erpnext
    deploy:
      restart_policy:
        condition: none
    entrypoint: [bash, -c]
    command:
      - >
        ls -1 apps > sites/apps.txt;
        bench set-config -g db_host $$DB_HOST;
        bench set-config -gp db_port $$DB_PORT;
        bench set-config -g redis_cache "redis://$$REDIS_CACHE";
        bench set-config -g redis_queue "redis://$$REDIS_QUEUE";
        bench set-config -g redis_socketio "redis://$$REDIS_QUEUE";
        bench set-config -gp socketio_port $$SOCKETIO_PORT;
    environment:
      DB_HOST: db
      DB_PORT: "3306"
      REDIS_CACHE: redis-cache:6379
      REDIS_QUEUE: redis-queue:6379
      SOCKETIO_PORT: "9000"

  backend:
    <<: *erpnext
    deploy:
      restart_policy:
        condition: on-failure
    environment:
      DB_HOST: db
      DB_PORT: "3306"
      MYSQL_ROOT_PASSWORD: admin
      MARIADB_ROOT_PASSWORD: admin
    depends_on:
      configurator:
        condition: service_completed_successfully

  frontend:
    <<: *erpnext
    deploy:
      restart_policy:
        condition: on-failure
    command: [nginx-entrypoint.sh]
    environment:
      BACKEND: backend:8000
      FRAPPE_SITE_NAME_HEADER: $$host
      SOCKETIO: websocket:9000
      UPSTREAM_REAL_IP_ADDRESS: 127.0.0.1
      UPSTREAM_REAL_IP_HEADER: X-Forwarded-For
      UPSTREAM_REAL_IP_RECURSIVE: "off"
      PROXY_READ_TIMEOUT: 300
      CLIENT_MAX_BODY_SIZE: 50m
    ports:
      - "8080:8080"
    depends_on: [websocket, backend]

  queue:
    <<: *erpnext
    deploy:
      restart_policy:
        condition: on-failure
    command: [bench, worker, --queue, "long,default,short"]
    depends_on:
      configurator:
        condition: service_completed_successfully

  scheduler:
    <<: *erpnext
    deploy:
      restart_policy:
        condition: on-failure
    command: [bench, schedule]
    depends_on:
      configurator:
        condition: service_completed_successfully

  websocket:
    <<: *erpnext
    deploy:
      restart_policy:
        condition: on-failure
    command: [node, /home/frappe/frappe-bench/apps/frappe/socketio.js]
    depends_on:
      configurator:
        condition: service_completed_successfully

  db:
    image: mariadb:11.8
    networks: [frappe_network]
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      start_period: 5s
      interval: 5s
      timeout: 5s
      retries: 5
    deploy:
      restart_policy:
        condition: on-failure
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
      - --skip-character-set-client-handshake
      - --innodb-snapshot-isolation=OFF
      - --innodb-buffer-pool-size=256M
    environment:
      MYSQL_ROOT_PASSWORD: admin
      MARIADB_ROOT_PASSWORD: admin
    volumes:
      - db-data:/var/lib/mysql

  redis-queue:
    image: redis:6.2-alpine
    networks: [frappe_network]
    deploy:
      restart_policy:
        condition: on-failure
    volumes:
      - redis-queue-data:/data

  redis-cache:
    image: redis:6.2-alpine
    networks: [frappe_network]
    deploy:
      restart_policy:
        condition: on-failure

volumes:
  db-data:
  redis-queue-data:
  sites:
  logs:

networks:
  frappe_network:
    driver: bridge
```

- [ ] **Step 2: Odoo'yu durdur, ERPNext'i başlat, belleği ölç**

```bash
cd ~/Desktop/erp-asistan
docker compose stop                                   # Odoo (veri korunur)
docker compose -f docker/erpnext/compose.yml up -d
docker compose -f docker/erpnext/compose.yml ps       # configurator Exited (0), diğerleri Up
docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' | grep erpnext
```

Beklenen: toplam bellek < 2,5 GB. Container'lar `OOMKilled` ise ya da sürekli yeniden başlıyorsa dur; İsmail Docker Desktop → Settings → Resources'tan belleği 4 GB'a çıkarsın.

- [ ] **Step 3: Kurulum scriptini yaz**

`scripts/setup_erpnext.py`:

```python
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
```

- [ ] **Step 4: İki siteyi kur**

```bash
uv run python scripts/setup_erpnext.py test.localhost data/demo   # → api_key:api_secret
uv run python scripts/setup_erpnext.py localhost                   # SEED_DATASET şirketiyle
```

Beklenen: her biri tek satır `xxxxxxxx:yyyyyyyy` basar. `setup_complete` hata verirse yanıttaki eksik alan adına bak ve `args`'a ekle. Doğru anahtar adları: `docker compose -f docker/erpnext/compose.yml exec backend grep -n "args.get\|args\[" apps/erpnext/erpnext/setup/setup_wizard/operations/install_fixtures.py apps/frappe/frappe/desk/page/setup_wizard/setup_wizard.py`.

- [ ] **Step 5: `.env` ve `.env.example`'a ERPNext değişkenlerini ekle**

`.env.example` sonuna:

```
ERPNEXT_URL=http://localhost:8080
ERPNEXT_SITE=localhost
ERPNEXT_API_KEY=
ERPNEXT_API_SECRET=
ERPNEXT_TEST_SITE=test.localhost
ERPNEXT_TEST_API_KEY=
ERPNEXT_TEST_API_SECRET=
# odoo or erpnext: active at startup; seed.py and eval.py use it too
ERP_DEFAULT=odoo
```

Aynı satırları `.env`'e ekle; Adım 4'teki anahtarları yaz (`:` öncesi KEY, sonrası SECRET).

- [ ] **Step 6: Tarayıcıdan ve API'den doğrula**

```bash
curl -s localhost:8080/api/method/ping                                  # {"message":"pong"}
curl -s -H "Host: test.localhost" localhost:8080/api/method/ping        # {"message":"pong"}
source .env && curl -s -H "Authorization: token $ERPNEXT_API_KEY:$ERPNEXT_API_SECRET" \
  "localhost:8080/api/resource/Company?fields=%5B%22name%22,%22default_currency%22,%22country%22%5D"
```

Beklenen: son komut şirket adını, `TRY` ve `Türkiye`/`Turkey` döndürür. Tarayıcı: http://localhost:8080 → `Administrator` / `admin`, arayüz Türkçe.

- [ ] **Step 7: Kurulumun ürettiği isimleri kaydet**

```bash
H='-H "Host: test.localhost"'
source .env; AUTH="Authorization: token $ERPNEXT_TEST_API_KEY:$ERPNEXT_TEST_API_SECRET"
for q in 'Warehouse?filters=[["is_group","=",0]]' 'Price%20List' 'Item%20Group' 'Customer%20Group' 'Supplier%20Group' 'Territory' 'Account?filters=[["account_type","=","Tax"]]'; do
  echo "== $q"; curl -s -g -H "Host: test.localhost" -H "$AUTH" "localhost:8080/api/resource/$q"; echo
done
```

Beklenen: `Stores - <ABBR>` deposu, `Standard Selling` fiyat listesi, `Products` ürün grubu, `Hesaplanan KDV - <ABBR>` ve `İndirilecek KDV - <ABBR>` hesapları. İsimler farklıysa `erpnext/catalog.py` ve `erpnext/sales.py`'deki sabitleri (Task 4–5) buna göre yaz.

- [ ] **Step 8: Commit (İsmail onayıyla)**

```bash
git add docker/erpnext/compose.yml scripts/setup_erpnext.py .env.example
git commit -m "Add ERPNext Docker setup alongside Odoo"
```

---

### Task 2: ERPNext REST sürücüsü

**Files:**
- Create: `src/erp_asistan/erpnext/__init__.py` (boş)
- Create: `src/erp_asistan/erpnext/client.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_erpnext_client.py`

**Interfaces:**
- Produces: `ErpNextClient(url: str, site: str, api_key: str, api_secret: str)`; `ErpNextClient.from_env()`; `.url: str`; `.call(method, **params) -> Any`; `.get_list(doctype, fields, filters=(), or_filters=(), limit=None, order_by=None, parent=None) -> list[dict]`; `.get_doc(doctype, name) -> dict`; `.insert(doc: dict) -> dict`; `.set_value(doctype, name, vals: dict) -> dict`; `.file(path) -> bytes`; `.upload(filename, content, doctype, name, field) -> str` (file_url). `ErpNextError(Exception)`: kullanıcıya gösterilebilir mesaj.
- Produces (tests): `erpnext` fixture (test sitesi), `odoo` fixture artık Odoo kapalıysa skip.

- [ ] **Step 1: Fixture'ları yaz**

`tests/conftest.py` tamamı:

```python
import os

import httpx
import pytest
from dotenv import load_dotenv

from erp_asistan.erpnext.client import ErpNextClient
from erp_asistan.odoo.client import OdooClient

load_dotenv()

_PROBE_TIMEOUT_SECONDS = 2
_HTTP_OK = 200


def _up(url: str) -> bool:
    try:
        return httpx.get(url, timeout=_PROBE_TIMEOUT_SECONDS).status_code == _HTTP_OK
    except httpx.HTTPError:
        return False


@pytest.fixture(scope="session")
def odoo() -> OdooClient:
    # Only one ERP runs at a time (RAM): the other one's tests skip.
    if not _up(f"{os.environ['ODOO_URL']}/web/health"):
        pytest.skip("Odoo kapalı")
    return OdooClient(
        url=os.environ["ODOO_URL"],
        db=os.environ["ODOO_TEST_DB"],
        api_key=os.environ["ODOO_TEST_API_KEY"],
    )


@pytest.fixture(scope="session")
def erpnext() -> ErpNextClient:
    url = os.environ.get("ERPNEXT_URL")
    if not url or not _up(f"{url}/api/method/ping"):
        pytest.skip("ERPNext kapalı")
    return ErpNextClient(
        url, os.environ["ERPNEXT_TEST_SITE"],
        os.environ["ERPNEXT_TEST_API_KEY"], os.environ["ERPNEXT_TEST_API_SECRET"],
    )


@pytest.fixture
def uniq() -> str:
    import uuid

    return uuid.uuid4().hex[:6]
```

- [ ] **Step 2: Başarısız testi yaz**

`tests/test_erpnext_client.py`:

```python
import pytest

from erp_asistan.erpnext.client import ErpNextError


def test_get_list_returns_company(erpnext):
    rows = erpnext.get_list("Company", ["name", "default_currency"])

    assert [r["default_currency"] for r in rows] == ["TRY"]


def test_insert_then_set_value(erpnext, uniq):
    doc = erpnext.insert({"doctype": "Customer", "customer_name": f"Test Cari {uniq}", "customer_type": "Company"})
    erpnext.set_value("Customer", doc["name"], {"website": "https://ornek.com.tr"})

    assert erpnext.get_doc("Customer", doc["name"])["website"] == "https://ornek.com.tr"


def test_get_list_without_limit_returns_all(erpnext):
    rows = erpnext.get_list("Account", ["name"])

    assert len(rows) > 20  # Frappe's default page size


def test_unknown_doctype_raises_readable_error(erpnext):
    with pytest.raises(ErpNextError) as e:
        erpnext.get_list("No Such Doctype", ["name"])

    assert "<" not in str(e.value)
```

- [ ] **Step 3: Testin başarısız olduğunu gör**

Run: `uv run pytest tests/test_erpnext_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'erp_asistan.erpnext'`

- [ ] **Step 4: Sürücüyü yaz**

`src/erp_asistan/erpnext/client.py`:

```python
"""Frappe/ERPNext REST driver."""

import json
import os
import re
from typing import Any

import httpx

__all__ = ["ErpNextClient", "ErpNextError"]

_TIMEOUT_SECONDS = 60
_HTTP_OK = 200
_ALL_ROWS = 0  # Frappe: limit_page_length=0 means no limit (default is 20)
_TAGS = re.compile(r"<[^>]+>")


class ErpNextError(Exception):
    pass


class ErpNextClient:
    def __init__(self, url: str, site: str, api_key: str, api_secret: str) -> None:
        self.url = url.rstrip("/")
        # One server hosts the demo and test sites; nginx routes by Host.
        self._http = httpx.Client(
            base_url=self.url,
            headers={"Authorization": f"token {api_key}:{api_secret}", "Host": site},
            timeout=_TIMEOUT_SECONDS,
        )

    @classmethod
    def from_env(cls) -> "ErpNextClient":
        return cls(
            os.environ["ERPNEXT_URL"], os.environ["ERPNEXT_SITE"],
            os.environ["ERPNEXT_API_KEY"], os.environ["ERPNEXT_API_SECRET"],
        )

    def call(self, method: str, **params: Any) -> Any:
        resp = self._http.post(f"/api/method/{method}", json=params)
        if resp.status_code != _HTTP_OK:
            raise ErpNextError(_error_message(resp))

        return resp.json().get("message")

    def get_list(
        self,
        doctype: str,
        fields: list[str],
        filters: list | tuple = (),
        or_filters: list | tuple = (),
        limit: int | None = None,
        order_by: str | None = None,
        parent: str | None = None,
    ) -> list[dict]:
        params: dict[str, Any] = {
            "doctype": doctype,
            "fields": fields,
            "filters": list(filters),
            "limit_page_length": limit or _ALL_ROWS,
        }
        if or_filters:
            params["or_filters"] = list(or_filters)
        if order_by:
            params["order_by"] = order_by
        if parent:
            params["parent"] = parent

        return self.call("frappe.client.get_list", **params)

    def get_doc(self, doctype: str, name: str) -> dict:
        return self.call("frappe.client.get", doctype=doctype, name=name)

    def insert(self, doc: dict) -> dict:
        """docstatus=1 in doc inserts and submits in one step."""
        return self.call("frappe.client.insert", doc=doc)

    def set_value(self, doctype: str, name: str, vals: dict) -> dict:
        return self.call("frappe.client.set_value", doctype=doctype, name=name, fieldname=vals)

    def file(self, path: str) -> bytes:
        resp = self._http.get(path)
        if resp.status_code != _HTTP_OK:
            raise ErpNextError(_error_message(resp))

        return resp.content

    def upload(self, filename: str, content: bytes, doctype: str, name: str, field: str) -> str:
        resp = self._http.post(
            "/api/method/upload_file",
            files={"file": (filename, content)},
            data={"doctype": doctype, "docname": name, "fieldname": field, "is_private": "0"},
        )
        if resp.status_code != _HTTP_OK:
            raise ErpNextError(_error_message(resp))

        return resp.json()["message"]["file_url"]


def _error_message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text

    # _server_messages: JSON list of JSON objects, each with an HTML "message".
    try:
        messages = [json.loads(m).get("message", "") for m in json.loads(body.get("_server_messages") or "[]")]
    except (ValueError, AttributeError):
        messages = []

    text = " ".join(m for m in messages if m) or body.get("exception") or body.get("exc_type") or resp.text
    return _TAGS.sub("", str(text)).strip()
```

- [ ] **Step 5: Testlerin geçtiğini gör**

Run: `uv run pytest tests/test_erpnext_client.py -v`
Expected: 4 passed. ERPNext kapalıysa 4 skipped; ERPNext'i aç ve tekrar koş.

- [ ] **Step 6: Commit (İsmail onayıyla)**

```bash
git add src/erp_asistan/erpnext tests/conftest.py tests/test_erpnext_client.py
git commit -m "Add ERPNext REST client"
```

---

### Task 3: ERP sözleşmesi ve Odoo uygulaması

Davranış değişmez: mevcut Odoo testleri aynen geçmeli. ToolRegistry artık `OdooClient` değil `Erp` alır.

**Files:**
- Create: `src/erp_asistan/erp/backend.py`
- Create: `src/erp_asistan/erp/odoo_erp.py`
- Modify: `src/erp_asistan/erp/_lookup.py` (`_stems` → `stems`)
- Modify: `src/erp_asistan/erp/reports.py`
- Modify: `src/erp_asistan/tools.py`
- Modify: `src/erp_asistan/agent.py:33`
- Modify: `tests/conftest.py`, `tests/test_tools.py`, `tests/test_agent.py`

**Interfaces:**
- Produces: `Erp` Protocol: `quote_example: str`, `order_example: str`, `company_info() -> dict` (`name`, `city`, `logo: bytes | None`), `record_url(record_id: int | str) -> str` ve 13 araç metodu (imzalar aşağıda). `Seedable(Erp)`: `set_company(info: dict, logo: bytes | None)`, `create_vendor(name, city=None) -> dict`, `create_product(name, price, cost=0, code=None, category=None) -> dict`, `set_stock(product, quantity)`, `seed_order(partner, lines, date: str, invoice: bool)`.
- Produces: `OdooErp(client: OdooClient, url: str, db: str)`.
- Produces: `erp.reports.period(date_from, date_to) -> tuple[date, date]` (bitiş hariç), `summarize(orders: list[dict], lines: list[dict]) -> dict` (`orders`: `customer`, `untaxed`, `total`; `lines`: `product`, `untaxed`), `compare(first: dict, second: dict) -> dict`.
- Produces: `erp._lookup.stems(text) -> list[str]`.
- Produces: `ToolRegistry(erp: Erp)`; hata yakalama: `ErpError`, `OdooError`, `ErpNextError`.
- Produces (tests): `odoo_erp` fixture.

- [ ] **Step 1: Başarısız testleri yaz**

`tests/test_tools.py` tamamı:

```python
from erp_asistan.erpnext.client import ErpNextError
from erp_asistan.tools import Kind, ToolRegistry


class FakeErp:
    quote_example = "Q-1"
    order_example = "O-1"

    def __getattr__(self, name):
        return lambda **kwargs: {"called": name, **kwargs}


class BrokenErp(FakeErp):
    def confirm_order(self, order_ref):
        raise ErpNextError("ERPNext hata verdi")


def test_runs_tools_through_erp():
    result = ToolRegistry(FakeErp()).run("find_partner", {"name": "Ege"})

    assert result == {"called": "find_partner", "name": "Ege"}


def test_ref_examples_come_from_erp():
    params = {s["function"]["name"]: s["function"]["parameters"]["properties"] for s in ToolRegistry(FakeErp()).schemas()}

    assert "Q-1" in params["confirm_order"]["order_ref"]["description"]
    assert "O-1" in params["create_invoice"]["order_ref"]["description"]


def test_driver_error_becomes_message():
    assert ToolRegistry(BrokenErp()).run("confirm_order", {"order_ref": "X"}) == {"error": "ERPNext hata verdi"}


def test_schemas_cover_all_tools(odoo_erp):
    reg = ToolRegistry(odoo_erp)
    names = {s["function"]["name"] for s in reg.schemas()}

    assert {"find_partner", "create_quotation", "create_vendor_bill", "sales_summary"} <= names


def test_kinds(odoo_erp):
    reg = ToolRegistry(odoo_erp)

    assert reg.kind("get_low_stock") is Kind.READ
    assert reg.kind("confirm_order") is Kind.WRITE


def test_business_error_becomes_message(odoo_erp):
    result = ToolRegistry(odoo_erp).run("confirm_order", {"order_ref": "YOK-999"})

    assert "bulunamadı" in result["error"]


def test_unknown_tool(odoo_erp):
    assert "error" in ToolRegistry(odoo_erp).run("drop_database", {})
```

`tests/conftest.py`'ye ekle (importlara `from erp_asistan.erp.odoo_erp import OdooErp`):

```python
@pytest.fixture(scope="session")
def odoo_erp(odoo) -> OdooErp:
    return OdooErp(odoo, os.environ["ODOO_URL"], os.environ["ODOO_TEST_DB"])
```

`tests/test_agent.py` sonuna:

```python
def test_prompt_is_erp_neutral():
    agent = Agent(FakeLLM([]), FakeTools(), company="Netelsan")

    assert "Odoo" not in agent._messages[0]["content"]
```

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

Run: `uv run pytest tests/test_tools.py tests/test_agent.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'erp_asistan.erp.odoo_erp'` (collection) ve `test_prompt_is_erp_neutral` assertion.

- [ ] **Step 3: Sözleşmeyi yaz**

`src/erp_asistan/erp/backend.py`:

```python
"""ERP contract: the tool layer, web session and seeding talk only to this."""

from typing import Protocol

__all__ = ["Erp", "Seedable"]


class Erp(Protocol):
    quote_example: str
    order_example: str

    def company_info(self) -> dict: ...
    def record_url(self, record_id: int | str) -> str: ...

    def find_partner(self, name: str) -> list[dict]: ...
    def find_products(self, name: str) -> list[dict]: ...
    def get_low_stock(self, threshold: float) -> list[dict]: ...
    def list_open_invoices(self, partner: str | None = None) -> dict: ...
    def find_orders(self, partner: str | None = None, state: str | None = None) -> list[dict]: ...
    def sales_summary(self, date_from: str, date_to: str) -> dict: ...
    def compare_sales(self, first_from: str, first_to: str, second_from: str, second_to: str) -> dict: ...

    def create_partner(
        self, name: str, city: str | None = None, phone: str | None = None, email: str | None = None
    ) -> dict: ...
    def update_product_price(self, product: str, price: float) -> dict: ...
    def create_quotation(self, partner: str, lines: list[dict]) -> dict: ...
    def confirm_order(self, order_ref: str) -> dict: ...
    def create_invoice(self, order_ref: str) -> dict: ...
    def create_vendor_bill(self, vendor: str, lines: list[dict], date: str, ref: str | None = None) -> dict: ...


class Seedable(Erp, Protocol):
    def set_company(self, info: dict, logo: bytes | None) -> None: ...
    def create_vendor(self, name: str, city: str | None = None) -> dict: ...
    def create_product(
        self, name: str, price: float, cost: float = 0, code: str | None = None, category: str | None = None
    ) -> dict: ...
    def set_stock(self, product: str, quantity: float) -> None: ...
    def seed_order(self, partner: str, lines: list[dict], date: str, invoice: bool) -> None: ...
```

- [ ] **Step 4: Ortak rapor yardımcılarını çıkar**

`src/erp_asistan/erp/reports.py` tamamı (Odoo davranışı aynı):

```python
import datetime
from collections import Counter

from erp_asistan.erp.errors import ErpError
from erp_asistan.odoo.client import OdooClient

__all__ = ["compare", "compare_sales", "period", "sales_summary", "summarize"]

_CONFIRMED = ["sale", "done"]
_TOP_N = 5


def period(date_from: str, date_to: str) -> tuple[datetime.date, datetime.date]:
    """Inclusive YYYY-MM-DD range as [start, end)."""
    try:
        start = datetime.date.fromisoformat(date_from)
        end = datetime.date.fromisoformat(date_to) + datetime.timedelta(days=1)
    except ValueError as e:
        raise ErpError("Tarihler YYYY-AA-GG biçiminde olmalı.") from e
    return start, end


def summarize(orders: list[dict], lines: list[dict]) -> dict:
    """orders: [{"customer", "untaxed", "total"}], lines: [{"product", "untaxed"}]."""
    if not orders:
        return {"order_count": 0, "total": 0, "untaxed": 0, "top_customers": [], "top_products": []}

    by_customer: Counter = Counter()
    for o in orders:
        by_customer[o["customer"]] += o["untaxed"]

    by_product: Counter = Counter()
    for l in lines:
        by_product[l["product"]] += l["untaxed"]

    return {
        "order_count": len(orders),
        "untaxed": round(sum(o["untaxed"] for o in orders), 2),
        "total": round(sum(o["total"] for o in orders), 2),
        "top_customers": [{"name": n, "untaxed": round(v, 2)} for n, v in by_customer.most_common(_TOP_N)],
        "top_products": [{"name": n, "untaxed": round(v, 2)} for n, v in by_product.most_common(_TOP_N)],
    }


def sales_summary(odoo: OdooClient, date_from: str, date_to: str) -> dict:
    """Confirmed sales between dates (inclusive, YYYY-MM-DD)."""
    start, end = period(date_from, date_to)
    domain = [
        ("state", "in", _CONFIRMED),
        ("date_order", ">=", start.isoformat()),
        ("date_order", "<", end.isoformat()),
    ]
    orders = odoo.search_read("sale.order", domain, ["id", "partner_id", "amount_untaxed", "amount_total"])
    if not orders:
        return summarize([], [])

    lines = odoo.search_read(
        "sale.order.line",
        [("order_id", "in", [o["id"] for o in orders]), ("display_type", "=", False)],
        ["product_id", "product_uom_qty", "price_subtotal"],
    )
    return summarize(
        [{"customer": o["partner_id"][1], "untaxed": o["amount_untaxed"], "total": o["amount_total"]} for o in orders],
        [{"product": l["product_id"][1], "untaxed": l["price_subtotal"]} for l in lines],
    )


def _pct(old: float, new: float) -> float | None:
    return round((new - old) / old * 100, 1) if old else None


def compare(first: dict, second: dict) -> dict:
    """Two period summaries side by side; deltas are computed here, not by the LLM."""
    return {
        "first": first,
        "second": second,
        "change": {
            "total": round(second["total"] - first["total"], 2),
            "total_pct": _pct(first["total"], second["total"]),
            "order_count": second["order_count"] - first["order_count"],
        },
    }


def compare_sales(odoo: OdooClient, first_from: str, first_to: str, second_from: str, second_to: str) -> dict:
    return compare(sales_summary(odoo, first_from, first_to), sales_summary(odoo, second_from, second_to))
```

- [ ] **Step 5: `_stems`'i aç**

`src/erp_asistan/erp/_lookup.py`: `def _stems(` → `def stems(` ve `search` içindeki `stems = _stems(name)` → `words = stems(name)`, sonraki iki satırda `stems` → `words`:

```python
    words = stems(name)
    if not words:
        return []

    domain = [*extra_domain, *(("name", "ilike", s) for s in words)]
```

- [ ] **Step 6: Odoo uygulamasını yaz**

`src/erp_asistan/erp/odoo_erp.py`:

```python
"""Odoo implementation of the ERP contract."""

import base64

from erp_asistan.erp import company, invoices, partners, products, reports, sales
from erp_asistan.odoo.client import OdooClient

__all__ = ["OdooErp"]

_COMPANY_FIELDS = ["name", "street", "city", "zip", "phone", "email", "website"]
_SEED_ORDER_TIME = "10:00:00"


class OdooErp:
    quote_example = "S00012"
    order_example = "S00012"

    def __init__(self, client: OdooClient, url: str, db: str) -> None:
        self._c = client
        self._url = url.rstrip("/")
        self._db = db

    def company_info(self) -> dict:
        return company.company_info(self._c)

    def record_url(self, record_id: int | str) -> str:
        # ?db= is required: the server hosts more than one DB (demo + tests).
        return f"{self._url}/odoo/account.move/{record_id}?db={self._db}"

    def find_partner(self, name: str) -> list[dict]:
        return partners.find_partner(self._c, name)

    def find_products(self, name: str) -> list[dict]:
        return products.find_products(self._c, name)

    def get_low_stock(self, threshold: float) -> list[dict]:
        return products.get_low_stock(self._c, threshold)

    def list_open_invoices(self, partner: str | None = None) -> dict:
        return invoices.list_open_invoices(self._c, partner)

    def find_orders(self, partner: str | None = None, state: str | None = None) -> list[dict]:
        return sales.find_orders(self._c, partner, state)

    def sales_summary(self, date_from: str, date_to: str) -> dict:
        return reports.sales_summary(self._c, date_from, date_to)

    def compare_sales(self, first_from: str, first_to: str, second_from: str, second_to: str) -> dict:
        return reports.compare_sales(self._c, first_from, first_to, second_from, second_to)

    def create_partner(
        self, name: str, city: str | None = None, phone: str | None = None, email: str | None = None
    ) -> dict:
        return partners.create_partner(self._c, name, city, phone, email)

    def update_product_price(self, product: str, price: float) -> dict:
        return products.update_product_price(self._c, product, price)

    def create_quotation(self, partner: str, lines: list[dict]) -> dict:
        return sales.create_quotation(self._c, partner, lines)

    def confirm_order(self, order_ref: str) -> dict:
        return sales.confirm_order(self._c, order_ref)

    def create_invoice(self, order_ref: str) -> dict:
        return invoices.create_invoice(self._c, order_ref)

    def create_vendor_bill(self, vendor: str, lines: list[dict], date: str, ref: str | None = None) -> dict:
        return invoices.create_vendor_bill(self._c, vendor, lines, date, ref)

    def set_company(self, info: dict, logo: bytes | None) -> None:
        vals = {k: info[k] for k in _COMPANY_FIELDS if info.get(k)}
        if logo:
            vals["logo"] = base64.b64encode(logo).decode()

        [row] = self._c.search_read("res.company", [], ["id"], limit=1)
        self._c.write("res.company", [row["id"]], vals)

    def create_vendor(self, name: str, city: str | None = None) -> dict:
        return partners.create_partner(self._c, name, city=city)

    def create_product(
        self, name: str, price: float, cost: float = 0, code: str | None = None, category: str | None = None
    ) -> dict:
        return products.create_product(self._c, name, price, cost, code, category)

    def set_stock(self, product: str, quantity: float) -> None:
        products.set_stock(self._c, product, quantity)

    def seed_order(self, partner: str, lines: list[dict], date: str, invoice: bool) -> None:
        quote = sales.create_quotation(self._c, partner, lines)
        sales.confirm_order(self._c, quote["ref"])

        order = sales.resolve_order(self._c, quote["ref"])
        self._c.write("sale.order", [order["id"]], {"date_order": f"{date} {_SEED_ORDER_TIME}"})

        if invoice:
            invoices.create_invoice(self._c, quote["ref"])
```

- [ ] **Step 7: ToolRegistry'yi `Erp`'ye bağla**

`src/erp_asistan/tools.py`: importları değiştir:

```python
from erp_asistan.erp.backend import Erp
from erp_asistan.erp.errors import ErpError
from erp_asistan.erpnext.client import ErpNextError
from erp_asistan.odoo.client import OdooError
```

(`from erp_asistan.erp import invoices, partners, products, reports, sales` ve `OdooClient` importu kalkar.) `_build` tamamı:

```python
def _build(erp: Erp) -> list[_Tool]:
    R, W = Kind.READ, Kind.WRITE
    return [
        _Tool("find_partner", "Search customers/vendors by name.",
              {"name": _s("Full or partial name")}, ["name"], R, erp.find_partner),
        _Tool("find_products", "Search products by name or product code (e.g. M.U.CLV.00001); returns code, category, price and stock.",
              {"name": _s("Product name or code, full or partial")}, ["name"], R, erp.find_products),
        _Tool("get_low_stock", "List products with stock below a threshold.",
              {"threshold": _n("Stock threshold")}, ["threshold"], R, erp.get_low_stock),
        _Tool("list_open_invoices", "List unpaid customer invoices, optionally for one customer.",
              {"partner": _s("Customer name (optional)")}, [], R, erp.list_open_invoices),
        _Tool("find_orders", "List sales quotations/orders, optionally filtered by customer and state.",
              {"partner": _s("Customer name (optional)"),
               "state": {"type": "string", "enum": ["quotation", "order"],
                         "description": "quotation = not yet confirmed, order = confirmed (optional)"}},
              [], R, erp.find_orders),
        _Tool("sales_summary", "Confirmed sales totals, top customers and top products for a date range.",
              {"date_from": _s(_DATE), "date_to": _s(_DATE)}, ["date_from", "date_to"], R, erp.sales_summary),
        _Tool("compare_sales", "Compare confirmed sales of two periods; returns both summaries and the change.",
              {"first_from": _s(_DATE), "first_to": _s(_DATE), "second_from": _s(_DATE), "second_to": _s(_DATE)},
              ["first_from", "first_to", "second_from", "second_to"], R, erp.compare_sales),
        _Tool("create_partner", "Create a new customer/vendor company.",
              {"name": _s("Company name"), "city": _s("City"), "phone": _s("Phone"), "email": _s("Email")},
              ["name"], W, erp.create_partner),
        _Tool("update_product_price", "Change a product's sales price (TL, excluding VAT).",
              {"product": _s("Product name"), "price": _n("New price")}, ["product", "price"], W,
              erp.update_product_price),
        _Tool("create_quotation", "Create a sales quotation (draft order) for a customer.",
              {"partner": _s("Customer name"), "lines": _SALE_LINES}, ["partner", "lines"], W, erp.create_quotation),
        _Tool("confirm_order", "Confirm a quotation into a sales order.",
              {"order_ref": _s(f"Quotation reference, e.g. {erp.quote_example}")}, ["order_ref"], W,
              erp.confirm_order),
        _Tool("create_invoice", "Create and post the customer invoice of a confirmed sales order.",
              {"order_ref": _s(f"Sales order reference, e.g. {erp.order_example}")}, ["order_ref"], W,
              erp.create_invoice),
        _Tool("create_vendor_bill", "Create a draft vendor bill. Unknown vendors are created.",
              {"vendor": _s("Vendor company name"), "lines": _BILL_LINES, "date": _s(_DATE),
               "ref": _s("Vendor invoice number (optional)")},
              ["vendor", "lines", "date"], W, erp.create_vendor_bill),
    ]
```

`ToolRegistry.__init__(self, odoo: OdooClient)` → `__init__(self, erp: Erp)` ve `_build(odoo)` → `_build(erp)`. `run` içinde `except (ErpError, OdooError) as e:` → `except (ErpError, OdooError, ErpNextError) as e:`.

- [ ] **Step 7b: `ToolRegistry` çağıranlarını güncelle (uygulama arada bozuk kalmasın)**

`src/erp_asistan/web.py` `main()`: `from erp_asistan.erp.odoo_erp import OdooErp` importu ekle; `tools = ToolRegistry(odoo)` satırını, `odoo_url` tanımından sonraya taşıyıp şöyle yap:

```python
    tools = ToolRegistry(OdooErp(odoo, odoo_url, os.environ["ODOO_DB"]))
```

`scripts/eval.py` `main()`: `tools = ToolRegistry(odoo)` → `tools = ToolRegistry(OdooErp(odoo, os.environ["ODOO_URL"], os.environ["ODOO_DB"]))`; importlara `import os` ve `from erp_asistan.erp.odoo_erp import OdooErp`. (Task 7 ve 8 bu satırları yeniden yazar.)

- [ ] **Step 8: Prompt'u ERP'den bağımsız yap**

`src/erp_asistan/agent.py:33`: `Sen "{company}" şirketinin Odoo ERP asistanısın.` → `Sen "{company}" şirketinin ERP asistanısın.`

- [ ] **Step 9: Tüm testlerin geçtiğini gör (Odoo açık)**

ERPNext'i Docker Desktop'tan durdur, Odoo'yu başlat (`docker compose up -d`).

Run: `uv run pytest -q`
Expected: tüm Odoo testleri ve yeni testler geçer; `test_erpnext_client.py` 4 skipped.

- [ ] **Step 10: Commit (İsmail onayıyla)**

```bash
git add src/erp_asistan/erp src/erp_asistan/tools.py src/erp_asistan/agent.py src/erp_asistan/web.py scripts/eval.py tests
git commit -m "Route tools through an ERP-neutral contract"
```

---

### Task 4: ERPNext arama, cari ve ürün

**Files:**
- Create: `src/erp_asistan/erpnext/lookup.py`
- Create: `src/erp_asistan/erpnext/catalog.py`
- Test: `tests/test_erpnext_catalog.py`

**Interfaces:**
- Consumes: `ErpNextClient` (Task 2), `erp._lookup.stems`, `ErpError` (Task 3).
- Produces: `lookup.search(c, doctype, name_field, name, fields, limit, code_field=None, filters=()) -> list[dict]`; `lookup.resolve(c, doctype, name_field, name, label, code_field=None, filters=()) -> {"id": docname, "name": display}`.
- Produces: `catalog.find_partner(c, name) -> list[dict]` (`id`, `name`, `type`: `customer|supplier`, `city`), `resolve_partner(c, name)` (yalnız Customer), `create_partner(c, name, city=None, phone=None, email=None) -> {"id", "name"}`, `create_vendor(c, name, city=None) -> {"id", "name"}`, `find_products(c, name) -> list[dict]` (`id`, `code`, `name`, `category`, `price`, `stock`), `resolve_product(c, name) -> {"id": item_code, "name": item_name}`, `create_product(c, name, price, cost=0, code=None, category=None)`, `set_stock(c, product, quantity)`, `get_low_stock(c, threshold)`, `update_product_price(c, product, price) -> {"name", "old_price", "new_price"}`, `item_prices(c, codes) -> dict[str, float]`, `UOM`.

- [ ] **Step 1: Başarısız testleri yaz**

`tests/test_erpnext_catalog.py`:

```python
import pytest

from erp_asistan.erp.errors import ErpError
from erp_asistan.erpnext import catalog


@pytest.fixture
def customer(erpnext, uniq):
    return catalog.create_partner(erpnext, name=f"Yılmaz Ltd {uniq}", city="İzmir")


@pytest.fixture
def product(erpnext, uniq):
    p = catalog.create_product(erpnext, name=f"Laptop {uniq}", price=25000, cost=20000)
    catalog.set_stock(erpnext, p["name"], 4)
    return p


def test_find_partner_with_city(erpnext, customer):
    [row] = catalog.find_partner(erpnext, customer["name"][:-2])

    assert (row["name"], row["type"], row["city"]) == (customer["name"], "customer", "İzmir")


def test_find_partner_includes_suppliers(erpnext, uniq):
    catalog.create_vendor(erpnext, f"Ostim Tedarik {uniq}")

    assert [r["type"] for r in catalog.find_partner(erpnext, f"Ostim Tedarik {uniq}")] == ["supplier"]


def test_resolve_ambiguous_partner_raises(erpnext, uniq):
    catalog.create_partner(erpnext, name=f"Kaya {uniq} A")
    catalog.create_partner(erpnext, name=f"Kaya {uniq} B")

    with pytest.raises(ErpError, match="birden fazla"):
        catalog.resolve_partner(erpnext, f"Kaya {uniq}")


def test_unknown_partner_raises(erpnext, uniq):
    with pytest.raises(ErpError, match="bulunamadı"):
        catalog.resolve_partner(erpnext, f"Yok {uniq}")


def test_find_partner_tolerates_turkish_suffixes(erpnext, customer, uniq):
    rows = catalog.find_partner(erpnext, f"Yılmaz'ın {uniq}")

    assert [r["name"] for r in rows] == [customer["name"]]


def test_product_price_and_stock(erpnext, product):
    [row] = catalog.find_products(erpnext, product["name"])

    assert (row["price"], row["stock"], row["code"]) == (25000, 4, None)


def test_low_stock_and_price_update(erpnext, product):
    low = catalog.get_low_stock(erpnext, threshold=5)
    assert product["name"] in [p["name"] for p in low]

    result = catalog.update_product_price(erpnext, product["name"], 27500)
    assert (result["old_price"], result["new_price"]) == (25000, 27500)
    assert catalog.find_products(erpnext, product["name"])[0]["price"] == 27500


def test_resolve_product_tolerates_suffixes(erpnext, product, uniq):
    assert catalog.resolve_product(erpnext, f"laptopu {uniq}")["name"] == product["name"]


def test_product_code_and_category(erpnext, uniq):
    code = f"M.U.TST.{uniq}"
    catalog.create_product(erpnext, name=f"Test Şube {uniq}", price=100, code=code, category=f"Kategori {uniq}")

    [row] = catalog.find_products(erpnext, code)
    assert row["code"] == code
    assert row["category"] == f"Kategori {uniq}"
    assert catalog.resolve_product(erpnext, code.lower())["name"] == f"Test Şube {uniq}"
```

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

Run: `uv run pytest tests/test_erpnext_catalog.py -v`
Expected: FAIL — `ImportError: cannot import name 'catalog'`

- [ ] **Step 3: Aramayı yaz**

`src/erp_asistan/erpnext/lookup.py`:

```python
"""Name/code search over Frappe doctypes; same semantics as erp._lookup (Odoo)."""

from erp_asistan.erp._lookup import stems
from erp_asistan.erp.errors import ErpError
from erp_asistan.erpnext.client import ErpNextClient

__all__ = ["resolve", "search"]

_MAX_CANDIDATES = 5


def _like(text: str) -> list:
    return ["like", f"%{text}%"]


def search(
    c: ErpNextClient,
    doctype: str,
    name_field: str,
    name: str,
    fields: list[str],
    limit: int,
    code_field: str | None = None,
    filters: list | tuple = (),
) -> list[dict]:
    """Whole-phrase match (name or code) first; else every word stem must match the name (AND)."""
    or_filters = [[name_field, *_like(name)]]
    if code_field:
        or_filters.append([code_field, *_like(name)])

    rows = c.get_list(doctype, fields, filters=filters, or_filters=or_filters, limit=limit)
    if rows:
        return rows

    words = stems(name)
    if not words:
        return []

    return c.get_list(doctype, fields, filters=[*filters, *([name_field, *_like(w)] for w in words)], limit=limit)


def resolve(
    c: ErpNextClient,
    doctype: str,
    name_field: str,
    name: str,
    label: str,
    code_field: str | None = None,
    filters: list | tuple = (),
) -> dict:
    """Exact name/code match wins; otherwise a single match; else ErpError."""
    fields = ["name", name_field, *([code_field] if code_field else [])]
    rows = search(c, doctype, name_field, name, fields, _MAX_CANDIDATES + 1, code_field, filters)

    key = name.casefold()
    exact = [
        r for r in rows
        if r[name_field].casefold() == key or (code_field and str(r[code_field]).casefold() == key)
    ]
    if len(exact) == 1:
        return {"id": exact[0]["name"], "name": exact[0][name_field]}

    if len(rows) == 1:
        return {"id": rows[0]["name"], "name": rows[0][name_field]}

    if not rows:
        raise ErpError(f"'{name}' adında {label} bulunamadı.")

    names = ", ".join(r[name_field] for r in rows[:_MAX_CANDIDATES])
    raise ErpError(f"'{name}' için birden fazla {label} var: {names}. Hangisi?")
```

- [ ] **Step 4: Cari ve ürünü yaz**

`src/erp_asistan/erpnext/catalog.py` (sabit isimler Task 1 Adım 7'deki çıktıyla aynı olmalı):

```python
"""Customers, suppliers, items, prices and stock."""

from collections import Counter

from erp_asistan.erpnext.client import ErpNextClient
from erp_asistan.erpnext.lookup import resolve, search

__all__ = [
    "UOM",
    "create_partner",
    "create_product",
    "create_vendor",
    "find_partner",
    "find_products",
    "get_low_stock",
    "item_prices",
    "resolve_partner",
    "resolve_product",
    "set_stock",
    "update_product_price",
]

UOM = "Nos"
_PARTNER_LIMIT = 10
_PRODUCT_LIMIT = 20
_PRICE_LIST = "Standard Selling"
_DEFAULT_ITEM_GROUP = "Products"
_ROOT_ITEM_GROUP = "All Item Groups"
_WAREHOUSE = "Stores"
_COMPANY_TYPE = "Company"
_ADDRESS_TYPE = "Billing"
_PARTIES = [("Customer", "customer_name"), ("Supplier", "supplier_name")]
_ITEM_FIELDS = ["name", "item_code", "item_name", "item_group"]


def find_partner(c: ErpNextClient, name: str) -> list[dict]:
    rows = []
    for doctype, field in _PARTIES:
        for r in search(c, doctype, field, name, ["name", field], _PARTNER_LIMIT):
            rows.append({"id": r["name"], "name": r[field], "type": doctype.lower(), "city": _city(c, r["name"])})
    return rows[:_PARTNER_LIMIT]


def _city(c: ErpNextClient, party: str) -> str | None:
    rows = c.get_list("Address", ["city"], filters=[["Dynamic Link", "link_name", "=", party]], limit=1)
    return rows[0]["city"] if rows else None


def resolve_partner(c: ErpNextClient, name: str) -> dict:
    return resolve(c, "Customer", "customer_name", name, "cari")


def create_partner(
    c: ErpNextClient, name: str, city: str | None = None, phone: str | None = None, email: str | None = None
) -> dict:
    doc = c.insert({"doctype": "Customer", "customer_name": name, "customer_type": _COMPANY_TYPE})
    _link_details(c, "Customer", doc["name"], name, city, phone, email)
    return {"id": doc["name"], "name": name}


def create_vendor(c: ErpNextClient, name: str, city: str | None = None) -> dict:
    doc = c.insert({"doctype": "Supplier", "supplier_name": name, "supplier_type": _COMPANY_TYPE})
    _link_details(c, "Supplier", doc["name"], name, city, None, None)
    return {"id": doc["name"], "name": name}


def _link_details(
    c: ErpNextClient, doctype: str, party: str, title: str, city: str | None, phone: str | None, email: str | None
) -> None:
    """ERPNext keeps city in Address and phone/email in Contact, linked to the party."""
    links = [{"link_doctype": doctype, "link_name": party}]
    if city:
        c.insert({
            "doctype": "Address", "address_title": title, "address_type": _ADDRESS_TYPE,
            "address_line1": city, "city": city, "country": _country(c), "links": links,
        })
    if phone or email:
        c.insert({
            "doctype": "Contact", "first_name": title, "links": links,
            "email_ids": [{"email_id": email, "is_primary": 1}] if email else [],
            "phone_nos": [{"phone": phone, "is_primary_phone": 1}] if phone else [],
        })


def _country(c: ErpNextClient) -> str:
    return c.get_list("Company", ["country"], limit=1)[0]["country"]


def item_prices(c: ErpNextClient, codes: list[str]) -> dict[str, float]:
    rows = c.get_list(
        "Item Price", ["item_code", "price_list_rate"],
        filters=[["price_list", "=", _PRICE_LIST], ["item_code", "in", codes]],
    )
    return {r["item_code"]: r["price_list_rate"] for r in rows}


def _stocks(c: ErpNextClient, codes: list[str]) -> Counter:
    totals: Counter = Counter()
    for r in c.get_list("Bin", ["item_code", "actual_qty"], filters=[["item_code", "in", codes]]):
        totals[r["item_code"]] += r["actual_qty"]
    return totals


def _views(c: ErpNextClient, rows: list[dict]) -> list[dict]:
    codes = [r["name"] for r in rows]
    if not codes:
        return []

    prices, stocks = item_prices(c, codes), _stocks(c, codes)
    return [
        {
            "id": r["name"],
            # Items without a product code use their name as item_code.
            "code": r["item_code"] if r["item_code"] != r["item_name"] else None,
            "name": r["item_name"],
            "category": r["item_group"],
            "price": prices.get(r["name"], 0),
            "stock": stocks[r["name"]],
        }
        for r in rows
    ]


def find_products(c: ErpNextClient, name: str) -> list[dict]:
    rows = search(c, "Item", "item_name", name, _ITEM_FIELDS, _PRODUCT_LIMIT, code_field="item_code")
    return _views(c, rows)


def resolve_product(c: ErpNextClient, name: str) -> dict:
    return resolve(c, "Item", "item_name", name, "ürün", code_field="item_code")


def create_product(
    c: ErpNextClient, name: str, price: float, cost: float = 0, code: str | None = None, category: str | None = None
) -> dict:
    item_code = code or name
    c.insert({
        "doctype": "Item", "item_code": item_code, "item_name": name,
        "item_group": _item_group(c, category) if category else _DEFAULT_ITEM_GROUP,
        "stock_uom": UOM, "is_stock_item": 1, "valuation_rate": cost,
    })
    c.insert({"doctype": "Item Price", "item_code": item_code, "price_list": _PRICE_LIST, "price_list_rate": price})
    return resolve_product(c, item_code)


def _item_group(c: ErpNextClient, name: str) -> str:
    if c.get_list("Item Group", ["name"], filters=[["name", "=", name]], limit=1):
        return name

    c.insert({"doctype": "Item Group", "item_group_name": name, "parent_item_group": _ROOT_ITEM_GROUP})
    return name


def _warehouse(c: ErpNextClient) -> str:
    [row] = c.get_list("Warehouse", ["name"], filters=[["warehouse_name", "=", _WAREHOUSE], ["is_group", "=", 0]], limit=1)
    return row["name"]


def set_stock(c: ErpNextClient, product: str, quantity: float) -> None:
    code = resolve_product(c, product)["id"]
    rate = c.get_doc("Item", code)["valuation_rate"]
    row = {"item_code": code, "warehouse": _warehouse(c), "qty": quantity, "valuation_rate": rate}
    if not rate:
        row["allow_zero_valuation_rate"] = 1

    c.insert({"doctype": "Stock Reconciliation", "purpose": "Stock Reconciliation", "items": [row], "docstatus": 1})


def get_low_stock(c: ErpNextClient, threshold: float) -> list[dict]:
    rows = c.get_list("Item", _ITEM_FIELDS, filters=[["is_stock_item", "=", 1], ["disabled", "=", 0]])
    low = [p for p in _views(c, rows) if p["stock"] < threshold]
    return sorted(low, key=lambda p: p["stock"])


def update_product_price(c: ErpNextClient, product: str, price: float) -> dict:
    p = resolve_product(c, product)
    [row] = c.get_list(
        "Item Price", ["name", "price_list_rate"],
        filters=[["item_code", "=", p["id"]], ["price_list", "=", _PRICE_LIST]], limit=1,
    )
    c.set_value("Item Price", row["name"], {"price_list_rate": price})
    return {"name": p["name"], "old_price": row["price_list_rate"], "new_price": price}
```

- [ ] **Step 5: Testlerin geçtiğini gör (ERPNext açık)**

Run: `uv run pytest tests/test_erpnext_catalog.py -v`
Expected: 9 passed.

Olası sapmalar ve çözümleri:
- `Customer Group`/`Territory` zorunlu hatası: `create_partner`'daki insert'e Task 1 Adım 7'de görülen yaprak grupları ekle (`"customer_group": "Commercial", "territory": "Türkiye"` gibi), sabit olarak.
- `Supplier Group` zorunlu: `create_vendor`'a aynı şekilde `"supplier_group"` ekle.
- `Valuation Rate` hatası: `set_stock` satırında `allow_zero_valuation_rate`'in uygulandığını kontrol et.

- [ ] **Step 6: Commit (İsmail onayıyla)**

```bash
git add src/erp_asistan/erpnext/lookup.py src/erp_asistan/erpnext/catalog.py tests/test_erpnext_catalog.py
git commit -m "Add ERPNext partners, products and stock"
```

---

### Task 5: ERPNext teklif, sipariş ve faturalar

ERPNext'te teklif (`Quotation`) ve sipariş (`Sales Order`) ayrı belgelerdir. Teklif oluşturulunca onaylanır (`docstatus=1`, durum `Open`); Odoo'daki "onay bekleyen teklif" budur. `confirm_order` tekliften sipariş üretir. `create_invoice` sipariş ya da teklif referansını kabul eder.

**Files:**
- Create: `src/erp_asistan/erpnext/sales.py`
- Test: `tests/test_erpnext_sales.py`

**Interfaces:**
- Consumes: `catalog.resolve_partner`, `catalog.resolve_product`, `catalog.item_prices`, `catalog.create_vendor`, `catalog.UOM` (Task 4).
- Produces: `create_quotation(c, partner, lines, date=None) -> {"ref", "partner", "total"}`; `confirm_order(c, order_ref, date=None) -> {"ref", "quotation", "state": "order", "total"}`; `find_orders(c, partner=None, state=None) -> list[{"ref", "partner", "state", "total", "date"}]`; `create_invoice(c, order_ref) -> invoice view`; `list_open_invoices(c, partner=None) -> {"count", "total_residual", "invoices"}`; `create_vendor_bill(c, vendor, lines, date, ref=None) -> invoice view`. Invoice view: `id`, `ref`, `partner`, `date`, `due`, `untaxed`, `total`, `residual`, `state`.

- [ ] **Step 1: Başarısız testleri yaz**

`tests/test_erpnext_sales.py`:

```python
import pytest

from erp_asistan.erp.errors import ErpError
from erp_asistan.erpnext import catalog, sales


@pytest.fixture
def customer(erpnext, uniq):
    return catalog.create_partner(erpnext, name=f"Yılmaz Ltd {uniq}", city="İzmir")


@pytest.fixture
def product(erpnext, uniq):
    p = catalog.create_product(erpnext, name=f"Laptop {uniq}", price=25000, cost=20000)
    catalog.set_stock(erpnext, p["name"], 4)
    return p


def test_quotation_to_invoice_flow(erpnext, customer, product):
    quote = sales.create_quotation(erpnext, customer["name"], [{"product": product["name"], "quantity": 2}])
    assert quote["total"] == 60000  # 2 × 25.000 + %20 KDV

    order = sales.confirm_order(erpnext, quote["ref"])
    assert (order["state"], order["quotation"], order["total"]) == ("order", quote["ref"], quote["total"])

    inv = sales.create_invoice(erpnext, order["ref"])
    assert (inv["total"], inv["residual"], inv["untaxed"]) == (60000, 60000, 50000)

    result = sales.list_open_invoices(erpnext, customer["name"])
    assert [i["ref"] for i in result["invoices"]] == [inv["ref"]]
    assert result["total_residual"] == inv["total"]


def test_invoice_accepts_quotation_ref(erpnext, customer, product):
    quote = sales.create_quotation(erpnext, customer["name"], [{"product": product["name"], "quantity": 1}])
    sales.confirm_order(erpnext, quote["ref"])

    assert sales.create_invoice(erpnext, quote["ref"])["total"] == quote["total"]


def test_invoice_of_unconfirmed_quotation_raises(erpnext, customer, product):
    quote = sales.create_quotation(erpnext, customer["name"], [{"product": product["name"], "quantity": 1}])

    with pytest.raises(ErpError, match="onaylanmamış"):
        sales.create_invoice(erpnext, quote["ref"])


def test_confirm_twice_raises(erpnext, customer, product):
    quote = sales.create_quotation(erpnext, customer["name"], [{"product": product["name"], "quantity": 1}])
    sales.confirm_order(erpnext, quote["ref"])

    with pytest.raises(ErpError, match="zaten"):
        sales.confirm_order(erpnext, quote["ref"])


def test_unknown_ref_raises(erpnext):
    with pytest.raises(ErpError, match="bulunamadı"):
        sales.confirm_order(erpnext, "YOK-999")


def test_find_orders_by_partner_and_state(erpnext, customer, product):
    quote = sales.create_quotation(erpnext, customer["name"], [{"product": product["name"], "quantity": 1}])

    drafts = sales.find_orders(erpnext, partner=customer["name"], state="quotation")
    confirmed = sales.find_orders(erpnext, partner=customer["name"], state="order")
    assert [o["ref"] for o in drafts] == [quote["ref"]]
    assert confirmed == []

    order = sales.confirm_order(erpnext, quote["ref"])
    assert sales.find_orders(erpnext, partner=customer["name"], state="quotation") == []
    assert [o["ref"] for o in sales.find_orders(erpnext, partner=customer["name"])] == [order["ref"]]


def test_backdated_seed_order(erpnext, customer, product):
    quote = sales.create_quotation(erpnext, customer["name"], [{"product": product["name"], "quantity": 1}],
                                   date="2026-09-15")
    sales.confirm_order(erpnext, quote["ref"], date="2026-09-15")

    [row] = sales.find_orders(erpnext, partner=customer["name"], state="order")
    assert row["date"] == "2026-09-15"


def test_vendor_bill_creates_unknown_vendor(erpnext, uniq):
    bill = sales.create_vendor_bill(
        erpnext,
        vendor=f"Anadolu Kırtasiye {uniq}",
        lines=[{"description": "A4 kağıt", "quantity": 10, "price_unit": 150}],
        date="2026-11-01",
        ref=f"A-{uniq}",
    )

    assert (bill["untaxed"], bill["total"], bill["state"]) == (1500, 1800, "Draft")
    assert catalog.find_partner(erpnext, f"Anadolu Kırtasiye {uniq}")[0]["type"] == "supplier"


def test_vendor_bill_rejects_bad_date(erpnext):
    with pytest.raises(ErpError, match="Geçersiz tarih"):
        sales.create_vendor_bill(erpnext, "X", [], "01.11.2026")
```

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

Run: `uv run pytest tests/test_erpnext_sales.py -v`
Expected: FAIL — `ImportError: cannot import name 'sales'`

- [ ] **Step 3: Satış modülünü yaz**

`src/erp_asistan/erpnext/sales.py`:

```python
"""Quotations, sales orders, customer invoices and vendor bills."""

import datetime

from erp_asistan.erp.errors import ErpError
from erp_asistan.erpnext import catalog
from erp_asistan.erpnext.client import ErpNextClient

__all__ = [
    "confirm_order",
    "create_invoice",
    "create_quotation",
    "create_vendor_bill",
    "find_orders",
    "list_open_invoices",
]

_SUBMITTED = 1
_SEARCH_LIMIT = 20
_QUOTE_VALID_DAYS = 30
# Submitted but not yet turned into a sales order: Odoo's "draft/sent" quotation.
_OPEN_QUOTATION = ["Open", "Replied"]
_VAT_RATE = 20
_VAT_LABEL = f"KDV %{_VAT_RATE}"
_SALES_VAT = "Hesaplanan KDV"
_PURCHASE_VAT = "İndirilecek KDV"
_ORDER_FIELDS = ["name", "customer_name", "grand_total", "transaction_date"]
_INVOICE_FIELDS = ["name", "customer_name", "posting_date", "due_date", "net_total", "grand_total",
                   "outstanding_amount", "status"]
_MAKE_ORDER = "erpnext.selling.doctype.quotation.quotation.make_sales_order"
_MAKE_INVOICE = "erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice"


def _today() -> str:
    return datetime.date.today().isoformat()


def _vat_account(c: ErpNextClient, account_name: str) -> str:
    [row] = c.get_list("Account", ["name"], filters=[["account_name", "=", account_name], ["is_group", "=", 0]], limit=1)
    return row["name"]


def _sales_taxes(c: ErpNextClient) -> list[dict]:
    return [{"charge_type": "On Net Total", "account_head": _vat_account(c, _SALES_VAT),
             "rate": _VAT_RATE, "description": _VAT_LABEL}]


def _purchase_taxes(c: ErpNextClient) -> list[dict]:
    return [{"category": "Total", "add_deduct_tax": "Add", "charge_type": "On Net Total",
             "account_head": _vat_account(c, _PURCHASE_VAT), "rate": _VAT_RATE, "description": _VAT_LABEL}]


def _submitted(c: ErpNextClient, doctype: str, ref: str) -> str | None:
    rows = c.get_list(doctype, ["name"], filters=[["name", "=", ref], ["docstatus", "=", _SUBMITTED]], limit=1)
    return rows[0]["name"] if rows else None


def _order_of(c: ErpNextClient, quotation: str) -> str | None:
    rows = c.get_list(
        "Sales Order", ["name"],
        filters=[["Sales Order Item", "prevdoc_docname", "=", quotation], ["docstatus", "=", _SUBMITTED]], limit=1,
    )
    return rows[0]["name"] if rows else None


def create_quotation(c: ErpNextClient, partner: str, lines: list[dict], date: str | None = None) -> dict:
    """lines: [{"product": str, "quantity": float}]. date (YYYY-MM-DD) backdates seed data."""
    customer = catalog.resolve_partner(c, partner)
    codes = [catalog.resolve_product(c, l["product"])["id"] for l in lines]
    prices = catalog.item_prices(c, codes)
    valid_till = datetime.date.today() + datetime.timedelta(days=_QUOTE_VALID_DAYS)

    quote = c.insert({
        "doctype": "Quotation", "quotation_to": "Customer", "party_name": customer["id"],
        "transaction_date": date or _today(),
        # Counted from today: an expired quotation cannot become an order.
        "valid_till": valid_till.isoformat(),
        "items": [{"item_code": code, "qty": l["quantity"], "rate": prices.get(code, 0)} for code, l in zip(codes, lines)],
        "taxes": _sales_taxes(c),
        "docstatus": _SUBMITTED,
    })
    return {"ref": quote["name"], "partner": customer["name"], "total": quote["grand_total"]}


def confirm_order(c: ErpNextClient, order_ref: str, date: str | None = None) -> dict:
    quote = _submitted(c, "Quotation", order_ref)
    if quote is None:
        raise ErpError(f"'{order_ref}' adında teklif bulunamadı.")
    if _order_of(c, quote):
        raise ErpError(f"{quote} zaten siparişe dönüştürülmüş.")

    when = date or _today()
    doc = c.call(_MAKE_ORDER, source_name=quote)
    doc.update({"transaction_date": when, "delivery_date": when, "docstatus": _SUBMITTED})
    for item in doc["items"]:
        item["delivery_date"] = when

    order = c.insert(doc)
    return {"ref": order["name"], "quotation": quote, "state": "order", "total": order["grand_total"]}


def _sales_order(c: ErpNextClient, ref: str) -> str:
    """ref may be the order itself or the quotation it came from."""
    order = _submitted(c, "Sales Order", ref)
    if order:
        return order

    quote = _submitted(c, "Quotation", ref)
    if quote is None:
        raise ErpError(f"'{ref}' adında sipariş/teklif bulunamadı.")

    order = _order_of(c, quote)
    if order is None:
        raise ErpError(f"{quote} henüz onaylanmamış; önce teklifi onaylayın.")
    return order


def _invoice_view(row: dict) -> dict:
    return {
        "id": row["name"],
        "ref": row["name"],
        "partner": row.get("customer_name") or row.get("supplier_name"),
        "date": row["posting_date"],
        "due": row["due_date"],
        "untaxed": row["net_total"],
        "total": row["grand_total"],
        "residual": row["outstanding_amount"],
        "state": row["status"],
    }


def create_invoice(c: ErpNextClient, order_ref: str) -> dict:
    doc = c.call(_MAKE_INVOICE, source_name=_sales_order(c, order_ref))
    doc["docstatus"] = _SUBMITTED
    return _invoice_view(c.insert(doc))


def list_open_invoices(c: ErpNextClient, partner: str | None = None) -> dict:
    """Totals are computed here: the LLM must not do arithmetic."""
    filters = [["docstatus", "=", _SUBMITTED], ["outstanding_amount", ">", 0], ["is_return", "=", 0]]
    if partner:
        filters.append(["customer_name", "like", f"%{partner}%"])

    rows = c.get_list("Sales Invoice", _INVOICE_FIELDS, filters=filters, order_by="due_date asc")
    return {
        "count": len(rows),
        "total_residual": round(sum(r["outstanding_amount"] for r in rows), 2),
        "invoices": [_invoice_view(r) for r in rows],
    }


def _order_view(row: dict, state: str) -> dict:
    return {"ref": row["name"], "partner": row["customer_name"], "state": state,
            "total": row["grand_total"], "date": str(row["transaction_date"])[:10]}


def find_orders(c: ErpNextClient, partner: str | None = None, state: str | None = None) -> list[dict]:
    """state: "quotation" (not yet an order) or "order" (sales order); anything else: both."""
    customer = catalog.resolve_partner(c, partner)["id"] if partner else None
    rows = []

    if state != "order":
        filters = [["docstatus", "=", _SUBMITTED], ["status", "in", _OPEN_QUOTATION]]
        if customer:
            filters.append(["party_name", "=", customer])
        quotes = c.get_list("Quotation", _ORDER_FIELDS, filters=filters, limit=_SEARCH_LIMIT,
                            order_by="transaction_date desc")
        rows += [_order_view(r, "quotation") for r in quotes]

    if state != "quotation":
        filters = [["docstatus", "=", _SUBMITTED]]
        if customer:
            filters.append(["customer", "=", customer])
        orders = c.get_list("Sales Order", _ORDER_FIELDS, filters=filters, limit=_SEARCH_LIMIT,
                            order_by="transaction_date desc")
        rows += [_order_view(r, "order") for r in orders]

    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows[:_SEARCH_LIMIT]


def _supplier(c: ErpNextClient, name: str) -> str:
    rows = c.get_list("Supplier", ["name"], filters=[["supplier_name", "=", name]], limit=1)
    if rows:
        return rows[0]["name"]
    return catalog.create_vendor(c, name)["id"]


def create_vendor_bill(c: ErpNextClient, vendor: str, lines: list[dict], date: str, ref: str | None = None) -> dict:
    """lines: [{"description": str, "quantity": float, "price_unit": float}]. Unknown vendor is created. Stays draft."""
    try:
        datetime.date.fromisoformat(date)
    except ValueError as e:
        raise ErpError(f"Geçersiz tarih: {date} (YYYY-AA-GG bekleniyor).") from e

    doc = {
        "doctype": "Purchase Invoice", "supplier": _supplier(c, vendor),
        "posting_date": date, "set_posting_time": 1, "bill_date": date, "due_date": date,
        "items": [
            {"item_name": l["description"], "description": l["description"], "qty": l["quantity"],
             "rate": l["price_unit"], "uom": catalog.UOM, "conversion_factor": 1}
            for l in lines
        ],
        "taxes": _purchase_taxes(c),
    }
    if ref:
        doc["bill_no"] = ref

    bill = c.insert(doc)
    return _invoice_view(bill | {"supplier_name": vendor})
```

- [ ] **Step 4: Testlerin geçtiğini gör**

Run: `uv run pytest tests/test_erpnext_sales.py -v`
Expected: 9 passed.

Olası sapmalar ve çözümleri:
- `insert` `docstatus=1` ile gönderilmiyorsa (belge taslak kalıyorsa): `docstatus`'u kaldır; insert'ten sonra `c.call("frappe.client.submit", doc=inserted)` çağır.
- `make_sales_order` "already ordered"/"expired" hatası: `valid_till`'in bugünden ileride olduğunu kontrol et.
- Kalemsiz alış faturası satırı `expense_account` isterse: Task 1 Adım 7'deki `Cost of Goods Sold - <ABBR>` hesabını `_EXPENSE_ACCOUNT` sabiti olarak satıra ekle.

- [ ] **Step 5: Commit (İsmail onayıyla)**

```bash
git add src/erp_asistan/erpnext/sales.py tests/test_erpnext_sales.py
git commit -m "Add ERPNext quotations, orders and invoices"
```

---

### Task 6: ERPNext raporları ve `ErpNextErp`

**Files:**
- Create: `src/erp_asistan/erpnext/reports.py`
- Create: `src/erp_asistan/erpnext/backend.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_erpnext_backend.py`

**Interfaces:**
- Consumes: `erp.reports.period`, `summarize`, `compare` (Task 3); `catalog`, `sales` (Task 4–5).
- Produces: `erpnext.reports.sales_summary(c, date_from, date_to)`, `compare_sales(c, ...)`; `ErpNextErp(client: ErpNextClient)` (`Seedable` uygular); `erpnext_erp` fixture.

- [ ] **Step 1: Başarısız testleri yaz**

`tests/conftest.py`'ye ekle (import: `from erp_asistan.erpnext.backend import ErpNextErp`):

```python
@pytest.fixture(scope="session")
def erpnext_erp(erpnext) -> ErpNextErp:
    return ErpNextErp(erpnext)
```

`tests/test_erpnext_backend.py`:

```python
import datetime

from erp_asistan.tools import ToolRegistry


def _sale(erp, uniq, quantity=1):
    customer = erp.create_partner(f"Rapor Müşteri {uniq}")
    product = erp.create_product(f"Rapor Ürün {uniq}", price=1000)
    erp.set_stock(product["name"], 10)
    quote = erp.create_quotation(customer["name"], [{"product": product["name"], "quantity": quantity}])
    return customer, product, erp.confirm_order(quote["ref"])


def test_sales_summary(erpnext_erp, uniq):
    today = datetime.date.today().isoformat()
    before = erpnext_erp.sales_summary(today, today)

    _sale(erpnext_erp, uniq, quantity=3)
    after = erpnext_erp.sales_summary(today, today)

    assert after["order_count"] == before["order_count"] + 1
    assert round(after["untaxed"] - before["untaxed"], 2) == 3000
    assert round(after["total"] - before["total"], 2) == 3600


def test_compare_sales_computes_deltas(erpnext_erp, uniq):
    today = datetime.date.today().isoformat()
    _sale(erpnext_erp, uniq)

    result = erpnext_erp.compare_sales("2001-01-01", "2001-01-31", today, today)

    assert result["first"]["total"] == 0
    assert result["change"]["total"] == result["second"]["total"]
    assert result["change"]["total_pct"] is None


def test_company_info(erpnext_erp):
    info = erpnext_erp.company_info()

    assert info["name"]
    assert info["logo"] is None or info["logo"][:4] == b"\x89PNG"


def test_record_url_points_to_purchase_invoice(erpnext_erp):
    assert erpnext_erp.record_url("ACC-PINV-2026-00001").endswith("/app/purchase-invoice/ACC-PINV-2026-00001")


def test_seed_order_backdates_and_invoices(erpnext_erp, uniq):
    customer = erpnext_erp.create_partner(f"Seed Müşteri {uniq}")
    product = erpnext_erp.create_product(f"Seed Ürün {uniq}", price=500, code=f"SEED.{uniq}")
    erpnext_erp.set_stock(f"SEED.{uniq}", 5)

    erpnext_erp.seed_order(customer["name"], [{"product": f"SEED.{uniq}", "quantity": 2}], "2026-10-03", invoice=True)

    [order] = erpnext_erp.find_orders(partner=customer["name"])
    assert order["date"] == "2026-10-03"
    assert erpnext_erp.list_open_invoices(customer["name"])["total_residual"] == 1200


def test_tools_run_on_erpnext(erpnext_erp):
    result = ToolRegistry(erpnext_erp).run("confirm_order", {"order_ref": "YOK-999"})

    assert "bulunamadı" in result["error"]
```

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

Run: `uv run pytest tests/test_erpnext_backend.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'erp_asistan.erpnext.backend'`

- [ ] **Step 3: Raporları yaz**

`src/erp_asistan/erpnext/reports.py`:

```python
"""Sales summaries over submitted sales orders."""

import datetime

from erp_asistan.erp.reports import compare, period, summarize
from erp_asistan.erpnext.client import ErpNextClient

__all__ = ["compare_sales", "sales_summary"]

_SUBMITTED = 1


def sales_summary(c: ErpNextClient, date_from: str, date_to: str) -> dict:
    """Submitted sales orders between dates (inclusive, YYYY-MM-DD)."""
    start, end = period(date_from, date_to)
    last = end - datetime.timedelta(days=1)
    orders = c.get_list(
        "Sales Order", ["name", "customer_name", "net_total", "grand_total"],
        filters=[["docstatus", "=", _SUBMITTED], ["transaction_date", "between", [start.isoformat(), last.isoformat()]]],
    )
    if not orders:
        return summarize([], [])

    lines = c.get_list(
        "Sales Order Item", ["item_name", "net_amount"],
        filters=[["parent", "in", [o["name"] for o in orders]]], parent="Sales Order",
    )
    return summarize(
        [{"customer": o["customer_name"], "untaxed": o["net_total"], "total": o["grand_total"]} for o in orders],
        [{"product": l["item_name"], "untaxed": l["net_amount"]} for l in lines],
    )


def compare_sales(c: ErpNextClient, first_from: str, first_to: str, second_from: str, second_to: str) -> dict:
    return compare(sales_summary(c, first_from, first_to), sales_summary(c, second_from, second_to))
```

- [ ] **Step 4: `ErpNextErp`'yi yaz**

`src/erp_asistan/erpnext/backend.py`:

```python
"""ERPNext implementation of the ERP contract."""

from urllib.parse import quote

from erp_asistan.erpnext import catalog, reports, sales
from erp_asistan.erpnext.client import ErpNextClient

__all__ = ["ErpNextErp"]

_LOGO_NAME = "logo.png"


class ErpNextErp:
    quote_example = "SAL-QTN-2026-00012"
    order_example = "SAL-ORD-2026-00012"

    def __init__(self, client: ErpNextClient) -> None:
        self._c = client

    def company_info(self) -> dict:
        [row] = self._c.get_list("Company", ["company_name", "company_logo"], limit=1)
        logo = self._c.file(row["company_logo"]) if row["company_logo"] else None
        return {"name": row["company_name"], "city": None, "logo": logo}

    def record_url(self, record_id: int | str) -> str:
        return f"{self._c.url}/app/purchase-invoice/{quote(str(record_id))}"

    def find_partner(self, name: str) -> list[dict]:
        return catalog.find_partner(self._c, name)

    def find_products(self, name: str) -> list[dict]:
        return catalog.find_products(self._c, name)

    def get_low_stock(self, threshold: float) -> list[dict]:
        return catalog.get_low_stock(self._c, threshold)

    def list_open_invoices(self, partner: str | None = None) -> dict:
        return sales.list_open_invoices(self._c, partner)

    def find_orders(self, partner: str | None = None, state: str | None = None) -> list[dict]:
        return sales.find_orders(self._c, partner, state)

    def sales_summary(self, date_from: str, date_to: str) -> dict:
        return reports.sales_summary(self._c, date_from, date_to)

    def compare_sales(self, first_from: str, first_to: str, second_from: str, second_to: str) -> dict:
        return reports.compare_sales(self._c, first_from, first_to, second_from, second_to)

    def create_partner(
        self, name: str, city: str | None = None, phone: str | None = None, email: str | None = None
    ) -> dict:
        return catalog.create_partner(self._c, name, city, phone, email)

    def update_product_price(self, product: str, price: float) -> dict:
        return catalog.update_product_price(self._c, product, price)

    def create_quotation(self, partner: str, lines: list[dict]) -> dict:
        return sales.create_quotation(self._c, partner, lines)

    def confirm_order(self, order_ref: str) -> dict:
        return sales.confirm_order(self._c, order_ref)

    def create_invoice(self, order_ref: str) -> dict:
        return sales.create_invoice(self._c, order_ref)

    def create_vendor_bill(self, vendor: str, lines: list[dict], date: str, ref: str | None = None) -> dict:
        return sales.create_vendor_bill(self._c, vendor, lines, date, ref)

    def set_company(self, info: dict, logo: bytes | None) -> None:
        """Name is set by setup_erpnext.py: renaming a Company in ERPNext rewrites every linked record."""
        if not logo:
            return

        [row] = self._c.get_list("Company", ["name"], limit=1)
        url = self._c.upload(_LOGO_NAME, logo, "Company", row["name"], "company_logo")
        self._c.set_value("Company", row["name"], {"company_logo": url})

    def create_vendor(self, name: str, city: str | None = None) -> dict:
        return catalog.create_vendor(self._c, name, city)

    def create_product(
        self, name: str, price: float, cost: float = 0, code: str | None = None, category: str | None = None
    ) -> dict:
        return catalog.create_product(self._c, name, price, cost, code, category)

    def set_stock(self, product: str, quantity: float) -> None:
        catalog.set_stock(self._c, product, quantity)

    def seed_order(self, partner: str, lines: list[dict], date: str, invoice: bool) -> None:
        quote_ = sales.create_quotation(self._c, partner, lines, date=date)
        order = sales.confirm_order(self._c, quote_["ref"], date=date)
        if invoice:
            sales.create_invoice(self._c, order["ref"])
```

- [ ] **Step 5: Testlerin geçtiğini gör**

Run: `uv run pytest tests/test_erpnext_backend.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit (İsmail onayıyla)**

```bash
git add src/erp_asistan/erpnext tests/conftest.py tests/test_erpnext_backend.py
git commit -m "Add ERPNext reports and backend"
```

---

### Task 7: Ortak seed, ERP seçimi ve sıfırlama

`seed.py` artık `Seedable` ile konuşur; hangi ERP'ye yükleneceğini `ERP_DEFAULT` belirler. Rastgele sayı çağrılarının sırası korunur; Odoo verisi birebir aynı çıkmalı.

**Files:**
- Create: `src/erp_asistan/backends.py`
- Modify: `scripts/seed.py`
- Modify: `scripts/eval.py`
- Create: `scripts/reset_erpnext.sh`

**Interfaces:**
- Consumes: `OdooErp`, `ErpNextErp`, `Slot` (`session.py`, Task 8'de yazılır; bu görevde yalnız `Slot` dataclass'ı gerekir, Step 1'de oluşturulur).
- Produces: `backends.DEFAULT_ERP = "odoo"`, `backends.reachable(url) -> bool`, `backends.load_slots() -> list[Slot]`, `backends.pick(slot_id) -> Slot`.

- [ ] **Step 1: `Slot`'u ve ERP listesini yaz**

`src/erp_asistan/session.py` (Task 8'de genişler):

```python
"""Configured ERPs and the one the conversation runs against."""

from collections.abc import Callable
from dataclasses import dataclass

from erp_asistan.erp.backend import Erp

__all__ = ["Slot"]


@dataclass(frozen=True)
class Slot:
    id: str
    label: str
    erp: Erp
    probe: Callable[[], bool]
```

`src/erp_asistan/backends.py`:

```python
"""ERPs configured in .env."""

import os

import httpx

from erp_asistan.erp.odoo_erp import OdooErp
from erp_asistan.erpnext.backend import ErpNextErp
from erp_asistan.erpnext.client import ErpNextClient
from erp_asistan.odoo.client import OdooClient
from erp_asistan.session import Slot

__all__ = ["DEFAULT_ERP", "load_slots", "pick", "reachable"]

DEFAULT_ERP = "odoo"
_PROBE_TIMEOUT_SECONDS = 2
_HTTP_OK = 200


def reachable(url: str) -> bool:
    try:
        return httpx.get(url, timeout=_PROBE_TIMEOUT_SECONDS).status_code == _HTTP_OK
    except httpx.HTTPError:
        return False


def load_slots() -> list[Slot]:
    odoo_url = os.environ["ODOO_URL"]
    slots = [Slot(
        "odoo", "Odoo",
        OdooErp(OdooClient.from_env(), odoo_url, os.environ["ODOO_DB"]),
        lambda: reachable(f"{odoo_url}/web/health"),
    )]

    erpnext_url = os.environ.get("ERPNEXT_URL")
    if erpnext_url:
        slots.append(Slot(
            "erpnext", "ERPNext",
            ErpNextErp(ErpNextClient.from_env()),
            lambda: reachable(f"{erpnext_url}/api/method/ping"),
        ))
    return slots


def pick(slot_id: str) -> Slot:
    return {s.id: s for s in load_slots()}[slot_id]
```

- [ ] **Step 2: Mevcut Odoo verisinin sayılarını kaydet (karşılaştırma için)**

Odoo açık. Önce İsmail'in sıfırlama onayı gerekir (mevcut demo verisi silinir).

```bash
pgrep -fl erp-asistan                      # asistan çalışıyorsa: pkill -f erp-asistan
scripts/reset_demo.sh                      # ESKİ seed.py ile
uv run erp-asistan & sleep 20; curl -s localhost:7860/api/overview; pkill -f erp-asistan
```

Beklenen: veri setinin `private/<veri-seti>/DEMO.md` dosyasındaki özet sayıları. Çıktıyı not et.

- [ ] **Step 3: `seed.py`'yi ortak hale getir**

`scripts/seed.py` tamamı:

```python
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
```

- [ ] **Step 4: Odoo verisinin aynı çıktığını doğrula**

```bash
scripts/reset_demo.sh                      # YENİ seed.py ile
uv run erp-asistan & sleep 20; curl -s localhost:7860/api/overview; pkill -f erp-asistan
```

Beklenen: Adım 2'deki çıktının birebir aynısı.

- [ ] **Step 5: ERPNext sıfırlama scriptini yaz**

`scripts/reset_erpnext.sh`:

```bash
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
```

```bash
chmod +x scripts/reset_erpnext.sh
```

- [ ] **Step 6: ERPNext'i seed'le ve Odoo ile karşılaştır**

Docker Desktop'tan Odoo'yu durdur, ERPNext'i başlat.

```bash
time scripts/reset_erpnext.sh
source .env && AUTH="Authorization: token $ERPNEXT_API_KEY:$ERPNEXT_API_SECRET"
uv run python -c "
from dotenv import load_dotenv; load_dotenv('.env')
from erp_asistan.backends import pick
e = pick('erpnext').erp
print(len(e.find_orders(state='quotation')), len(e.get_low_stock(5)), e.list_open_invoices()['count'], e.list_open_invoices()['total_residual'])
"
```

Beklenen: Odoo ile aynı sayılar (ya da toplamda yalnız kuruş farkı). Fark varsa: önce sipariş sayısını (`find_orders(state='order')` ≥ 20 sınırlı; doğrudan `Sales Order` sayısı 48 olmalı), sonra satır bazında KDV yuvarlamasını karşılaştır. Süreyi not et.

- [ ] **Step 7: `eval.py`'yi ERP seçimine bağla**

`scripts/eval.py`: importlarda `company_info` ve `OdooClient` yerine `from erp_asistan.backends import DEFAULT_ERP, pick` ve `import os`. `main()` içinde:

```python
    slot = pick(os.environ.get("ERP_DEFAULT", DEFAULT_ERP))
    tools = ToolRegistry(slot.erp)
    company = slot.erp.company_info()["name"]
```

Rapor başlığı: `f"# Eval — {stamp} · {company} · {slot.label} · {path.name} · {runs} koşu/senaryo"`. Dosya adı: `f"eval-{slot.id}-{datetime.datetime.now():%Y%m%d-%H%M}.md"`. Docstring'in `Usage` satırına ekle: `ERP_DEFAULT=erpnext uv run python scripts/eval.py 3`.

- [ ] **Step 8: Testleri koş**

Run: `uv run pytest -q` (ERPNext açık)
Expected: ERPNext testleri geçer, Odoo testleri skipped.

- [ ] **Step 9: Commit (İsmail onayıyla)**

```bash
git add src/erp_asistan/backends.py src/erp_asistan/session.py scripts/seed.py scripts/eval.py scripts/reset_erpnext.sh
git commit -m "Seed and evaluate either ERP via ERP_DEFAULT"
```

---

### Task 8: Oturum, ERP değiştirme ve web API

**Files:**
- Modify: `src/erp_asistan/session.py`
- Modify: `src/erp_asistan/history.py`
- Modify: `src/erp_asistan/web.py`
- Test: `tests/test_session.py`, `tests/test_history.py`, `tests/test_web.py`

**Interfaces:**
- Consumes: `Slot`, `load_slots`, `reachable`, `DEFAULT_ERP` (Task 7).
- Produces: `Session(slots, active: str, make_agent: Callable[[Tools, str], Agent], make_tools=ToolRegistry)`; `.active -> Slot`; `.tools`; `.agent` (lazy; ERP kapalıysa httpx/sürücü hatası); `.company() -> dict`; `.company_name() -> str`; `.reset()`; `.switch(slot_id)` (`KeyError`, `ErpClosed`); `.status() -> list[{"id", "label", "up", "active"}]`.
- Produces: `History(root, erp=None)`, `.start(erp=None)`, `.erp`; liste ve sohbet kayıtlarında `erp` alanı.
- Produces (HTTP): `GET /api/health` → `{"company", "erp": bool, "erps": [...], "model", "speech"}`; `POST /api/erp {"id"}` → `{"ok": true}` | 404 | 409.

- [ ] **Step 1: Başarısız oturum testlerini yaz**

`tests/test_session.py`:

```python
import httpx
import pytest

from erp_asistan.session import ErpClosed, Session, Slot


class FakeErp:
    def __init__(self, name, down=False):
        self.name = name
        self.down = down
        self.calls = 0

    def company_info(self):
        self.calls += 1
        if self.down:
            raise httpx.ConnectError("kapalı")
        return {"name": self.name, "city": None, "logo": None}


def _session(odoo=None, erpnext_up=True):
    built = []
    session = Session(
        [Slot("odoo", "Odoo", odoo or FakeErp("A"), lambda: True),
         Slot("erpnext", "ERPNext", FakeErp("B"), lambda: erpnext_up)],
        "odoo",
        make_agent=lambda tools, company: built.append((tools, company)) or object(),
        make_tools=lambda erp: ("tools", erp.name),
    )
    return session, built


def test_agent_is_built_lazily_with_company():
    session, built = _session()
    assert built == []

    agent = session.agent

    assert session.agent is agent
    assert built == [(("tools", "A"), "A")]


def test_switch_rebuilds_tools_and_agent():
    session, built = _session()
    session.agent

    session.switch("erpnext")
    session.agent

    assert session.active.id == "erpnext"
    assert built[-1] == (("tools", "B"), "B")


def test_switch_to_closed_erp_raises():
    session, _ = _session(erpnext_up=False)

    with pytest.raises(ErpClosed):
        session.switch("erpnext")
    assert session.active.id == "odoo"


def test_switch_to_unknown_erp_raises():
    session, _ = _session()

    with pytest.raises(KeyError):
        session.switch("sap")


def test_company_name_falls_back_to_label_and_retries():
    erp = FakeErp("A", down=True)
    session, _ = _session(odoo=erp)

    assert session.company_name() == "Odoo"
    erp.down = False
    assert session.company_name() == "A"
    assert session.company_name() == "A"
    assert erp.calls == 2


def test_reset_rebuilds_agent():
    session, built = _session()
    first = session.agent

    session.reset()

    assert session.agent is not first
    assert len(built) == 2


def test_status_marks_active_and_closed():
    session, _ = _session(erpnext_up=False)

    assert session.status() == [
        {"id": "odoo", "label": "Odoo", "up": True, "active": True},
        {"id": "erpnext", "label": "ERPNext", "up": False, "active": False},
    ]
```

`tests/test_history.py` sonuna:

```python
def test_conversation_records_erp(tmp_path):
    h = History(tmp_path, erp="odoo")
    h.add({"type": "user", "text": "ilk"})

    h.start(erp="erpnext")
    h.add({"type": "user", "text": "ikinci"})

    assert [(i["title"], i["erp"]) for i in h.list()] == [("ikinci", "erpnext"), ("ilk", "odoo")]
```

- [ ] **Step 2: Testlerin başarısız olduğunu gör**

Run: `uv run pytest tests/test_session.py tests/test_history.py -v`
Expected: FAIL — `ImportError: cannot import name 'ErpClosed'` ve `TypeError: History.__init__() got an unexpected keyword argument 'erp'`.

- [ ] **Step 3: `Session`'ı yaz**

`src/erp_asistan/session.py` tamamı:

```python
"""Configured ERPs and the one the conversation runs against."""

from collections.abc import Callable
from dataclasses import dataclass

import httpx

from erp_asistan.agent import Agent, Tools
from erp_asistan.erp.backend import Erp
from erp_asistan.erpnext.client import ErpNextError
from erp_asistan.odoo.client import OdooError
from erp_asistan.tools import ToolRegistry

__all__ = ["ErpClosed", "Session", "Slot"]

_UNREACHABLE = (httpx.HTTPError, OdooError, ErpNextError)


class ErpClosed(Exception):
    pass


@dataclass(frozen=True)
class Slot:
    id: str
    label: str
    erp: Erp
    probe: Callable[[], bool]


class Session:
    def __init__(
        self,
        slots: list[Slot],
        active: str,
        make_agent: Callable[[Tools, str], Agent],
        make_tools: Callable[[Erp], Tools] = ToolRegistry,
    ) -> None:
        self._slots = {s.id: s for s in slots}
        self._make_agent = make_agent
        self._make_tools = make_tools
        self._companies: dict[str, dict] = {}
        self._select(active)

    @property
    def active(self) -> Slot:
        return self._slots[self._active]

    @property
    def agent(self) -> Agent:
        # Lazy: the system prompt needs the company name, which needs the ERP up.
        if self._agent is None:
            self._agent = self._make_agent(self.tools, self.company()["name"])
        return self._agent

    def company(self) -> dict:
        """Cached per ERP; raises while the active ERP is down."""
        if self._active not in self._companies:
            self._companies[self._active] = self.active.erp.company_info()
        return self._companies[self._active]

    def company_name(self) -> str:
        try:
            return self.company()["name"]
        except _UNREACHABLE:
            return self.active.label

    def reset(self) -> None:
        self._agent = None

    def switch(self, slot_id: str) -> None:
        slot = self._slots[slot_id]
        if not slot.probe():
            raise ErpClosed(slot.label)
        self._select(slot_id)

    def status(self) -> list[dict]:
        return [
            {"id": s.id, "label": s.label, "up": s.probe(), "active": s.id == self._active}
            for s in self._slots.values()
        ]

    def _select(self, slot_id: str) -> None:
        self._active = slot_id
        self.tools = self._make_tools(self.active.erp)
        self._agent = None
```

`Tools` Protocol `agent.py`'de zaten var; `__all__`'a ekle: `__all__ = ["Agent", "Status", "ToolCall", "Tools", "TraceEntry", "Turn"]`.

- [ ] **Step 4: `History`'ye ERP'yi ekle**

`src/erp_asistan/history.py`:

```python
    def __init__(self, root: Path, erp: str | None = None) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        self.erp = erp
        self.current = _new_id()

    def start(self, erp: str | None = None) -> None:
        if erp:
            self.erp = erp
        self.current = _new_id()
```

`add` içindeki yeni sohbet sözlüğüne `"erp": self.erp,` (`"title"`'dan sonra). `list` içinde: `items.append({"id": convo["id"], "title": convo["title"], "started": convo["started"], "erp": convo.get("erp")})` — eski kayıtlarda alan yok.

- [ ] **Step 5: Oturum ve geçmiş testlerinin geçtiğini gör**

Run: `uv run pytest tests/test_session.py tests/test_history.py -v`
Expected: hepsi passed.

- [ ] **Step 6: Başarısız web testlerini yaz**

`tests/test_web.py`: importlara `import httpx` ve `from erp_asistan.session import Session, Slot`. `_client` ve yardımcıları değiştir:

```python
class FakeErp:
    def __init__(self, name="Netelsan", down=False):
        self.name = name
        self.down = down

    def company_info(self):
        if self.down:
            raise httpx.ConnectError("kapalı")
        return {"name": self.name, "city": None, "logo": None}

    def record_url(self, record_id):
        return f"http://odoo/odoo/account.move/{record_id}?db=erp"


def _client(replies=(), invoice=INVOICE, tools=None, slots=None):
    tools = tools or FakeTools()
    llm = FakeLLM(replies, invoice)
    session = Session(
        slots or [Slot("odoo", "Odoo", FakeErp(), lambda: True)],
        "odoo",
        make_agent=lambda t, company: Agent(llm, t, company=company),
        make_tools=lambda erp: tools,
    )
    services = Services(
        session=session,
        extractor=llm,
        transcribe=lambda path: "üç adet vega şube",
        history=History(Path(tempfile.mkdtemp()), erp="odoo"),
    )
    return TestClient(create_app(services)), tools


def _two_erps(erpnext_up=True):
    return [Slot("odoo", "Odoo", FakeErp("Netelsan"), lambda: True),
            Slot("erpnext", "ERPNext", FakeErp("Netelsan B"), lambda: erpnext_up)]
```

Yeni testler (dosya sonuna):

```python
def test_health_lists_erps():
    client, _ = _client(slots=_two_erps(erpnext_up=False))

    body = client.get("/api/health").json()

    assert body["erp"] is True
    assert body["erps"] == [
        {"id": "odoo", "label": "Odoo", "up": True, "active": True},
        {"id": "erpnext", "label": "ERPNext", "up": False, "active": False},
    ]


def test_health_survives_active_erp_down():
    client, _ = _client(slots=[Slot("odoo", "Odoo", FakeErp(down=True), lambda: False)])

    body = client.get("/api/health").json()

    assert (body["company"], body["erp"]) == ("Odoo", False)


def test_switch_starts_new_conversation_on_that_erp():
    client, _ = _client([_text("A"), _text("B")], slots=_two_erps())
    client.post("/api/chat", json={"text": "bir"})

    assert client.post("/api/erp", json={"id": "erpnext"}).json() == {"ok": True}
    client.post("/api/chat", json={"text": "iki"})

    items = client.get("/api/history").json()["items"]
    assert [(i["title"], i["erp"]) for i in items] == [("iki", "erpnext"), ("bir", "odoo")]
    assert client.get("/api/health").json()["company"] == "Netelsan B"


def test_switch_to_closed_erp_is_409():
    client, _ = _client(slots=_two_erps(erpnext_up=False))

    resp = client.post("/api/erp", json={"id": "erpnext"})

    assert resp.status_code == 409
    assert "kapalı" in resp.json()["detail"]


def test_switch_to_unknown_erp_is_404():
    client, _ = _client()

    assert client.post("/api/erp", json={"id": "sap"}).status_code == 404


def test_chat_while_erp_down_is_502():
    client, _ = _client(slots=[Slot("odoo", "Odoo", FakeErp(down=True), lambda: False)])

    assert client.post("/api/chat", json={"text": "selam"}).status_code == 502
```

- [ ] **Step 7: Web testlerinin başarısız olduğunu gör**

Run: `uv run pytest tests/test_web.py -v`
Expected: FAIL — `TypeError: Services.__init__() got an unexpected keyword argument 'session'`.

- [ ] **Step 8: `web.py`'yi oturuma bağla**

`src/erp_asistan/web.py` değişiklikleri:

Importlar: `from erp_asistan.session import ErpClosed, Session` ekle.

Sabitler: `_HTTP_CONFLICT = 409` ekle.

`Services`:

```python
@dataclass
class Services:
    session: Session
    extractor: Any
    transcribe: Callable[[Path], str]
    history: History
    probes: dict[str, Callable[[], bool]] = field(default_factory=dict)
```

Yeni istek gövdesi (`InvoiceIn`'den sonra):

```python
class ErpIn(BaseModel):
    id: str
```

`create_app` içindeki uç noktalar:

```python
    @app.get("/api/health")
    def health() -> dict:
        erps = s.session.status()
        return {
            "company": s.session.company_name(),
            "erp": next(e["up"] for e in erps if e["active"]),
            "erps": erps,
            **{k: probe() for k, probe in s.probes.items()},
        }

    @app.get("/api/logo")
    def logo() -> Response:
        try:
            data = s.session.company().get("logo")
        except httpx.HTTPError:
            data = None
        if not data:
            raise HTTPException(_HTTP_NOT_FOUND)
        return Response(data, media_type="image/png")

    @app.post("/api/chat")
    def chat(body: ChatIn) -> dict:
        return step(lambda: s.session.agent.send(body.text), {"type": "user", "text": body.text, "voice": body.voice})

    @app.post("/api/approve")
    def approve() -> dict:
        return step(lambda: s.session.agent.approve(), {"type": "decision", "approved": True})

    @app.post("/api/reject")
    def reject() -> dict:
        return step(lambda: s.session.agent.reject(), {"type": "decision", "approved": False})

    @app.post("/api/reset")
    def reset() -> dict:
        with lock:
            s.session.reset()
            s.history.start()
        return {"ok": True}

    @app.post("/api/erp")
    def switch_erp(body: ErpIn) -> dict:
        with lock:
            try:
                s.session.switch(body.id)
            except KeyError as e:
                raise HTTPException(_HTTP_NOT_FOUND) from e
            except ErpClosed as e:
                raise HTTPException(_HTTP_CONFLICT, f"{e} kapalı. Docker Desktop'tan başlatın.") from e
            s.history.start(erp=body.id)
        return {"ok": True}
```

`step` içindeki `except httpx.HTTPError as e:` aynı kalır (`session.agent` ERP kapalıyken `httpx.ConnectError` fırlatır). Not: ERPNext kapalıyken sürücü `ErpNextError` değil `httpx.ConnectError` fırlatır (bağlantı kurulamaz), yani 502 yolu çalışır.

`overview`: `s.tools.run` → `s.session.tools.run` (üç yerde).

`invoice_post`: `s.tools.run` → `s.session.tools.run`; URL satırları:

```python
        return result | {"url": s.session.active.erp.record_url(result["id"])}
```

(eski `# ?db= is required` yorumu ve `url = ...` satırı kalkar; yorum `OdooErp.record_url`'e taşındı.)

`_PROBE_TIMEOUT_SECONDS` ve `_reachable` kalkar. `main()` tamamı:

```python
def main() -> None:
    import uvicorn
    from dotenv import load_dotenv

    from erp_asistan.backends import DEFAULT_ERP, load_slots, reachable
    from erp_asistan.llm import OllamaLLM
    from erp_asistan.speech import is_ready, transcribe, warm_up

    load_dotenv(Path.cwd() / ".env")
    warm_up(_WARM_UP_AUDIO)

    llm = OllamaLLM()
    session = Session(
        load_slots(),
        os.environ.get("ERP_DEFAULT", DEFAULT_ERP),
        make_agent=lambda tools, company: Agent(llm, tools, company=company),
    )
    services = Services(
        session=session,
        extractor=llm,
        transcribe=transcribe,
        history=History(Path.cwd() / _HISTORY_DIR, erp=session.active.id),
        probes={
            "model": lambda: reachable(_OLLAMA_PS),
            "speech": is_ready,
        },
    )
    uvicorn.run(create_app(services), host="127.0.0.1", port=_PORT, log_level="warning")
```

- [ ] **Step 9: Tüm testlerin geçtiğini gör**

Run: `uv run pytest -q`
Expected: web, oturum, geçmiş testleri ve açık ERP'nin testleri geçer; kapalı ERP'ninkiler skipped.

- [ ] **Step 10: Commit (İsmail onayıyla)**

```bash
git add src/erp_asistan tests
git commit -m "Switch ERP at runtime from the web API"
```

---

### Task 9: Arayüzde ERP seçici

JS için test altyapısı yok; doğrulama tarayıcıda (projenin mevcut arayüz testi yöntemi, önceki devam dosyasında).

**Files:**
- Modify: `src/erp_asistan/static/index.html:20`, `:102`, `:133`
- Modify: `src/erp_asistan/static/app.js`
- Modify: `src/erp_asistan/static/app.css`

**Interfaces:**
- Consumes: `GET /api/health` (`erps`), `POST /api/erp`, `GET /api/history` (`erp`) (Task 8).

- [ ] **Step 1: Başlığa seçiciyi koy**

`index.html:20`:

```html
      <li data-probe="erp"><i class="led"></i><select id="erp" class="erp-pick" aria-label="ERP seçimi"></select></li>
```

`index.html:102`: `Odoo'ya işle` → `ERP'ye işle`. `index.html:133`: `<b>Odoo'ya işle</b>` → `<b>ERP'ye işle</b>`. Yardım metninin sonuna ekle: `Sağ üstteki seçiciden ERP'yi değiştirebilirsiniz; kapalı olan ERP seçilemez, Docker Desktop'tan başlatılınca birkaç saniye içinde seçilebilir olur.`

- [ ] **Step 2: Stil**

`app.css`, `.leds li` kuralından sonra:

```css
.erp-pick {
  padding: 4px 8px;
  border: 1px solid var(--hair);
  border-radius: 8px;
  background: var(--plate);
  color: inherit;
  font: inherit;
  cursor: pointer;
}
.erp-pick:hover { border-color: var(--black); }
.erp-pick:disabled { cursor: progress; opacity: .6; }
```

- [ ] **Step 3: Seçiciyi sağlık yoklamasına bağla**

`app.js`, `refreshHealth`'ten önce:

```js
let erpLabels = {};

// Updated in place: rebuilding options would close an open dropdown.
function renderErps(erps) {
  const select = $("erp");
  if (select.options.length !== erps.length) {
    select.replaceChildren(...erps.map((e) => {
      const opt = el("option");
      opt.value = e.id;
      return opt;
    }));
  }
  erps.forEach((e, i) => {
    const opt = select.options[i];
    opt.textContent = e.up ? e.label : `${e.label} · kapalı`;
    opt.disabled = !e.up && !e.active;
    if (e.active) { select.value = e.id; }
  });
  erpLabels = Object.fromEntries(erps.map((e) => [e.id, e.label]));
}
```

`refreshHealth` içinde `$("company").textContent = h.company;`'den sonra: `renderErps(h.erps);`.

- [ ] **Step 4: Logo değişimine izin ver**

`initBrand` tamamı (eski hali logoyu siliyordu; ikinci ERP'nin logosu gösterilemezdi):

```js
function initBrand() {
  const logo = $("logo");
  const show = (ok) => { logo.hidden = !ok; $("company").hidden = ok; };
  // A cached logo can finish loading before this script runs.
  if (logo.complete && logo.naturalWidth) { show(true); }
  logo.addEventListener("load", () => show(true));
  logo.addEventListener("error", () => show(false));
}
```

- [ ] **Step 5: Yeni sohbet akışını paylaş ve ERP değişimini ekle**

`initChat` içindeki `new-chat` dinleyicisini ortak fonksiyona çıkar (`initChat`'ten önce):

```js
// Starts an empty live conversation after the server accepted path; false if it refused.
async function freshChat(path, data) {
  if (busy || recorder) { return false; }
  toggleDrawer(false);
  showView("view-chat");
  try {
    await postJson(path, data);
  } catch (e) {
    renderError(e.message);
    return false;
  }
  liveNodes = null;
  pastId = null;
  lockComposer();
  renderEmpty();
  await loadHistory();
  $("input").focus();
  return true;
}
```

`initChat` içinde:

```js
  $("new-chat").addEventListener("click", () => { freshChat("/api/reset"); });

  $("erp").addEventListener("change", async (e) => {
    const id = e.target.value;
    company = "";
    if (await freshChat("/api/erp", { id })) {
      $("logo").src = `/api/logo?erp=${id}`;
    }
    refreshHealth();
  });
```

`setBusy` içinde `lockComposer();`'dan sonra: `$("erp").disabled = on;`.

- [ ] **Step 6: Geçmişte ERP'yi göster ve metinleri düzelt**

`loadHistory` içinde `const stamp = ...` satırından sonra:

```js
      const where = item.erp && Object.keys(erpLabels).length > 1 ? ` · ${erpLabels[item.erp]}` : "";
```

ve `el("span", "when", stamp)` → `el("span", "when", stamp + where)`.

`app.js:850`: `"Odoo'ya işleniyor…"` → `"ERP'ye işleniyor…"`. `app.js:854`: `"Odoo'da aç"` → `"ERP'de aç"`.

- [ ] **Step 7: Tarayıcıda doğrula**

Odoo açık, ERPNext kapalı:

```bash
pgrep -fl erp-asistan || true; uv run erp-asistan &
sleep 20; curl -s localhost:7860/api/health
```

Beklenen: `"erps":[{"id":"odoo",...,"up":true,"active":true},{"id":"erpnext",...,"up":false,"active":false}]`.

Tarayıcıda http://localhost:7860, sırayla:
1. Sağ üstte LED + seçici: `Odoo` seçili, listede `ERPNext · kapalı` gri ve seçilemez.
2. Docker Desktop'tan Odoo'yu durdur, ERPNext'i başlat. 10–60 sn içinde: ERP LED'i kırmızı, `Odoo · kapalı`, `ERPNext` seçilebilir. Sayfa yenilemeden.
3. `ERPNext`'i seç: sohbet boşalır, özet kartları ERPNext'ten gelir (Odoo ile aynı sayılar), logo ve şirket adı güncellenir, LED yeşil.
4. "Onay bekleyen teklifler hangileri?" → iki ERPNext teklifi.
5. Geçmiş panelinde eski sohbet `· Odoo`, yenisi `· ERPNext` etiketli.
6. Fatura oku → "ERP'ye işle" → "ERP'de aç" bağlantısı ERPNext'te alış faturasını açar.
7. ERPNext'i durdur: LED kırmızıya döner; bir soru sorulursa "Model veya ERP'ye ulaşılamadı" hatası çıkar.

- [ ] **Step 8: Commit (İsmail onayıyla)**

```bash
git add src/erp_asistan/static
git commit -m "Add ERP picker to the header"
```

---

### Task 10: İki ERP'de eval ve dokümanlar

**Files:**
- Modify: `README.md`, `DEMO.md`
- Output: `reports/eval-odoo-*.md`, `reports/eval-erpnext-*.md` (git dışı)

- [ ] **Step 1: ERPNext'te eval**

ERPNext açık, asistan kapalı (`pkill -f erp-asistan`), Firefox kapalı.

```bash
scripts/reset_erpnext.sh
ERP_DEFAULT=erpnext uv run python scripts/eval.py 3
```

Beklenen: rapor `reports/eval-erpnext-<zaman>.md`. Başarısız senaryoları hata sütununa göre sınıfla: araç sonucu farkı (ERPNext kodu) mı, model davranışı mı.

- [ ] **Step 2: Odoo'da eval (regresyon)**

Docker Desktop: ERPNext dur, Odoo başlat.

```bash
scripts/reset_demo.sh
uv run python scripts/eval.py 3
```

Beklenen: `docs/eval-2026-11-03.md` ile aynı düzey (16 senaryo, 48/48'e yakın). Düşüş varsa prompt değişikliğinden ("Odoo ERP" → "ERP") şüphelen.

- [ ] **Step 3: Dokümanları güncelle**

`README.md`: ilk satır `Natural-language (Turkish) assistant for Odoo 19 Community and ERPNext v16, ...`; mimari şemada `Odoo JSON-2 API` → `ERP contract ─ Odoo JSON-2 API | ERPNext REST API`; `## Run` altına:

```bash
# ERPNext (optional; stop Odoo first, one ERP at a time):
docker compose -f docker/erpnext/compose.yml up -d
uv run python scripts/setup_erpnext.py test.localhost data/demo   # → ERPNEXT_TEST_API_KEY:SECRET
scripts/reset_erpnext.sh                                           # demo site + seed
```

`DEMO.md` "Hazırlık"a ERPNext bloğu: Odoo'yu durdur → ERPNext'i başlat → `scripts/reset_erpnext.sh` (~süre Task 7 Adım 6'dan) → asistan. ERPNext girişi: http://localhost:8080 → `Administrator` / `admin`. "Arayüz"e seçici satırı.

- [ ] **Step 4: Son doğrulama**

```bash
uv run pytest -q            # açık ERP'nin testleri geçer, diğerininkiler skipped
git status --short          # yalnız beklenen dosyalar
```

- [ ] **Step 5: Commit (İsmail onayıyla)**

```bash
git add README.md DEMO.md
git commit -m "Document ERPNext setup and ERP picker"
```

---

## Bilinen sınırlar (bilerek kapsam dışı)

- ERPNext'te cari telefon/e-posta `Contact`'a yazılır ama `find_partner` yalnız şehri döndürür.
- KDV hesapları basit: iki hesap da "Duties and Taxes" altında. Gerçek muhasebe planı (191/391) kapsam dışı.
- Satış faturası stok düşürmez (iki ERP'de de teslimat yok); Odoo ile aynı davranış.
- `reset_erpnext.sh` sohbet geçmişini silmez; `reset_demo.sh` hepsini siler (mevcut davranış).
- Uygulama Docker'ı başlatıp durdurmaz.
