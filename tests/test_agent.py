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
