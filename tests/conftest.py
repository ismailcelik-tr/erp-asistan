import os

import httpx
import pytest
from dotenv import load_dotenv

from erp_asistan.erp.odoo_erp import OdooErp
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
def odoo_erp(odoo) -> OdooErp:
    return OdooErp(odoo, os.environ["ODOO_URL"], os.environ["ODOO_TEST_DB"])


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
