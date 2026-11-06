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
