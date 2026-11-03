from fastapi.testclient import TestClient

from erp_asistan.agent import Agent
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


def _call(tool, **args):
    return {"content": "", "tool_calls": [{"name": tool, "arguments": args}]}


def _text(t):
    return {"content": t, "tool_calls": []}


INVOICE = {
    "vendor": "Ostim Elektronik", "invoice_no": "A1", "date": "2026-11-01", "line_count": 1,
    "lines": [{"description": "PCB", "quantity": 2, "price_unit": 50}],
    "untaxed": 100, "vat": 20, "total": 120,
}


def _client(replies=(), invoice=INVOICE, tools=None):
    tools = tools or FakeTools()
    llm = FakeLLM(replies, invoice)
    services = Services(
        agent=Agent(llm, tools, company="Netelsan"),
        tools=tools,
        extractor=llm,
        transcribe=lambda path: "üç adet vega şube",
        company={"name": "Netelsan", "logo": None},
        odoo_url="http://odoo",
        odoo_db="erp",
    )
    return TestClient(create_app(services)), tools


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
