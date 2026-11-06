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
        make_agent=lambda tools, company, erp: built.append((tools, company, erp)) or object(),
        make_tools=lambda erp: ("tools", erp.name),
    )
    return session, built


def test_agent_is_built_lazily_with_company():
    session, built = _session()
    assert built == []

    agent = session.agent

    assert session.agent is agent
    assert built == [(("tools", "A"), "A", "Odoo")]


def test_switch_rebuilds_tools_and_agent():
    session, built = _session()
    session.agent

    session.switch("erpnext")
    session.agent

    assert session.active.id == "erpnext"
    assert built[-1] == (("tools", "B"), "B", "ERPNext")


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
