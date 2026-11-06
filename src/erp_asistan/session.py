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
        make_agent: Callable[[Tools, str, str], Agent],
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
            self._agent = self._make_agent(self.tools, self.company()["name"], self.active.label)
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
