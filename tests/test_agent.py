from erp_asistan.agent import Agent, Status
from erp_asistan.tools import Kind


class FakeLLM:
    def __init__(self, replies):
        self._replies = list(replies)
        self.calls = 0

    def chat(self, messages, tools):
        self.calls += 1
        return self._replies.pop(0)


class FakeTools:
    def __init__(self):
        self.ran = []

    def schemas(self):
        return []

    def kind(self, name):
        return Kind.WRITE if name.startswith("create") else Kind.READ

    def run(self, name, args):
        self.ran.append(name)
        return {"ok": name}


def _call(tool, **args):
    return {"content": "", "tool_calls": [{"name": tool, "arguments": args}]}


def _text(t):
    return {"content": t, "tool_calls": []}


def test_read_tool_runs_without_approval():
    tools = FakeTools()
    agent = Agent(FakeLLM([_call("find_partner", name="X"), _text("Bulundu.")]), tools)

    turn = agent.send("X'i bul")

    assert turn.reply == "Bulundu."
    assert tools.ran == ["find_partner"]
    assert turn.trace[0].status is Status.DONE


def test_write_tool_waits_for_approval():
    tools = FakeTools()
    agent = Agent(FakeLLM([_call("create_partner", name="X"), _text("Oluşturuldu.")]), tools)

    turn = agent.send("X ekle")
    assert turn.pending.name == "create_partner"
    assert tools.ran == []

    turn = agent.approve()
    assert tools.ran == ["create_partner"]
    assert turn.reply == "Oluşturuldu."


def test_reject_skips_write():
    tools = FakeTools()
    agent = Agent(FakeLLM([_call("create_partner", name="X"), _text("İptal edildi.")]), tools)

    agent.send("X ekle")
    turn = agent.reject()

    assert tools.ran == []
    assert turn.trace[-1].status is Status.REJECTED
    assert turn.reply == "İptal edildi."


def test_approve_without_pending_is_harmless():
    agent = Agent(FakeLLM([]), FakeTools())

    assert agent.approve().reply
    assert agent.reject().reply


def test_false_success_claim_is_challenged():
    tools = FakeTools()
    llm = FakeLLM([
        _call("find_partner", name="X"),
        _text("Teklif başarıyla oluşturuldu."),
        _call("create_quotation", partner="X"),
    ])
    agent = Agent(llm, tools)

    turn = agent.send("X için teklif oluştur")

    assert turn.pending.name == "create_quotation"
    assert Status.GUARDED in [e.status for e in turn.trace]


def test_claim_is_challenged_at_most_twice():
    llm = FakeLLM([_text("Oluşturuldu."), _text("Oluşturuldu."), _text("Oluşturuldu.")])
    agent = Agent(llm, FakeTools())

    assert agent.send("teklif oluştur").reply == "Oluşturuldu."
    assert llm.calls == 3


def test_second_challenge_gets_the_call():
    llm = FakeLLM([_text("Teklif oluşturuldu."), _text("Şimdi oluşturuyorum."), _call("create_quotation", partner="X")])
    agent = Agent(llm, FakeTools())

    assert agent.send("X için teklif oluştur").pending.name == "create_quotation"


class SpyLLM(FakeLLM):
    def chat(self, messages, tools):
        self.last = messages[-1]["content"]
        return super().chat(messages, tools)


def test_challenge_names_the_likely_tool():
    llm = SpyLLM([_text("Teklif başarıyla oluşturuldu."), _call("create_quotation", partner="X")])

    Agent(llm, FakeTools()).send("X için teklif oluştur")

    assert "create_quotation" in llm.last


def test_claim_after_real_write_is_accepted():
    llm = FakeLLM([_call("create_partner", name="X"), _text("Cari oluşturuldu.")])
    agent = Agent(llm, FakeTools())

    agent.send("X ekle")
    turn = agent.approve()

    assert turn.reply == "Cari oluşturuldu."
    assert llm.calls == 2
