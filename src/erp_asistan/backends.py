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
