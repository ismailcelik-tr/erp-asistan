import os

import pytest
from dotenv import load_dotenv

from erp_asistan.odoo.client import OdooClient

load_dotenv()


@pytest.fixture(scope="session")
def odoo() -> OdooClient:
    return OdooClient(
        url=os.environ["ODOO_URL"],
        db=os.environ["ODOO_TEST_DB"],
        api_key=os.environ["ODOO_TEST_API_KEY"],
    )


@pytest.fixture
def uniq() -> str:
    import uuid

    return uuid.uuid4().hex[:6]
