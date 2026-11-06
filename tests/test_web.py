import tempfile
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from erp_asistan.agent import Agent
from erp_asistan.history import History
from erp_asistan.session import Session, Slot
from erp_asistan.tools import Kind
from erp_asistan.web import Services, create_app


class FakeLLM:
    def __init__(self, replies, invoice=None):
        self._replies = list(replies)
        self._invoice = invoice

    def chat(self, messages, tools):
        return self._replies.pop(0)

    def extract(self, prompt, image, fmt):
        return self._invoice


class FakeTools:
    def __init__(self):
        self.ran = []

    def schemas(self):
        return []

    def kind(self, name):
        return Kind.WRITE if name.startswith("create") else Kind.READ

    def run(self, name, args):
        self.ran.append((name, args))
        return {"id": 7, "partner": args.get("vendor", "X"), "total": 120.0}


class OverviewTools(FakeTools):
    def run(self, name, args):
        self.ran.append((name, args))
        return {
            "find_orders": [{"ref": "S1"}, {"ref": "S2"}],
            "get_low_stock": [{"name": "A"}],
            "list_open_invoices": {"count": 3, "total_residual": 1500.0, "invoices": []},
        }[name]


def _call(tool, **args):
    return {"content": "", "tool_calls": [{"name": tool, "arguments": args}]}


def _text(t):
    return {"content": t, "tool_calls": []}


INVOICE = {
    "vendor": "Ostim Elektronik", "invoice_no": "A1", "date": "2026-11-01", "line_count": 1,
    "lines": [{"description": "PCB", "quantity": 2, "price_unit": 50}],
    "untaxed": 100, "vat": 20, "total": 120,
}


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
        make_agent=lambda t, company, erp: Agent(llm, t, company=company, erp=erp),
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


def test_chat_pauses_on_write_then_approve_runs_it():
    client, tools = _client([_call("find_partner", name="X"), _call("create_partner", name="X"), _text("Eklendi.")])

    turn = client.post("/api/chat", json={"text": "X ekle"}).json()
    assert [t["status"] for t in turn["trace"]] == ["done"]
    assert turn["pending"]["name"] == "create_partner"
    assert turn["pending"]["label"]

    turn = client.post("/api/approve").json()
    assert turn["reply"] == "Eklendi."
    assert ("create_partner", {"name": "X"}) in tools.ran


def test_transcribe_returns_text():
    client, _ = _client()

    resp = client.post("/api/transcribe", files={"audio": ("a.webm", b"x", "audio/webm")})

    assert resp.json()["text"] == "üç adet vega şube"


def test_invoice_read_reports_consistency():
    client, _ = _client()

    body = client.post("/api/invoice/read", files={"image": ("f.png", b"x", "image/png")}).json()

    assert body["invoice"]["vendor"] == "Ostim Elektronik"
    assert body["warnings"] == []


def test_inconsistent_invoice_is_not_posted():
    client, tools = _client()
    bad = INVOICE | {"lines": [{"description": "PCB", "quantity": 1, "price_unit": 50}]}

    resp = client.post("/api/invoice/post", json=bad)

    assert resp.status_code == 422
    assert tools.ran == []


def test_consistent_invoice_is_posted_with_odoo_link():
    client, tools = _client()

    body = client.post("/api/invoice/post", json=INVOICE).json()

    assert tools.ran[0][0] == "create_vendor_bill"
    assert body["url"] == "http://odoo/odoo/account.move/7?db=erp"


def test_health_reports_company():
    client, _ = _client()

    assert client.get("/api/health").json()["company"] == "Netelsan"


def test_pending_rows_follow_fixed_order():
    client, _ = _client([_call("create_partner", city="Ankara", name="X")])

    rows = client.post("/api/chat", json={"text": "X ekle"}).json()["pending"]["rows"]

    assert [r["label"] for r in rows] == ["Ad", "Şehir"]


def test_conversation_is_recorded_with_decision():
    client, _ = _client([_call("create_partner", name="X"), _text("Eklendi.")])

    client.post("/api/chat", json={"text": "X ekle", "voice": True})
    client.post("/api/approve")

    listing = client.get("/api/history").json()
    [item] = listing["items"]
    assert item["id"] == listing["current"]
    assert item["title"] == "X ekle"

    events = client.get(f"/api/history/{item['id']}").json()["events"]
    assert [e["type"] for e in events] == ["user", "turn", "decision", "turn"]
    assert events[0]["voice"] is True
    assert events[1]["pending"]["name"] == "create_partner"
    assert events[2]["approved"] is True
    assert events[3]["reply"] == "Eklendi."


def test_reset_starts_new_conversation():
    client, _ = _client([_text("A"), _text("B")])

    client.post("/api/chat", json={"text": "bir"})
    client.post("/api/reset")
    client.post("/api/chat", json={"text": "iki"})

    listing = client.get("/api/history").json()
    assert [i["title"] for i in listing["items"]] == ["iki", "bir"]
    assert listing["items"][0]["id"] == listing["current"]


def test_unknown_conversation_is_404():
    client, _ = _client()

    assert client.get("/api/history/20990101-000000-000000").status_code == 404


def test_overview_counts_from_erp():
    client, tools = _client(tools=OverviewTools())

    body = client.get("/api/overview", params={"low_stock": 7}).json()

    assert body == {"quotations": 2, "low_stock": 1, "open_invoices": 3, "open_total": 1500.0}
    assert ("find_orders", {"state": "quotation"}) in tools.ran
    assert ("get_low_stock", {"threshold": 7}) in tools.ran


class FailingTools(FakeTools):
    def run(self, name, args):
        return {"error": "Odoo hata verdi"}


def test_overview_reports_erp_error():
    client, _ = _client(tools=FailingTools())

    assert client.get("/api/overview", params={"low_stock": 5}).status_code == 502


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
