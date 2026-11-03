"""Tool-calling loop that pauses on write tools until a human approves."""

import datetime
import enum
import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from erp_asistan.tools import Kind

__all__ = ["Agent", "Status", "ToolCall", "TraceEntry", "Turn"]

_MAX_STEPS = 10

_SYSTEM_PROMPT = """Sen "Demo Ticaret A.Ş." şirketinin Odoo ERP asistanısın. Bugün {today}.
Kurallar:
- Veriyi asla uydurma; her bilgi için araç çağır.
- Kendin toplama/hesap yapma; araçların döndürdüğü toplamları (total, total_residual, untaxed) aynen kullan.
- Kullanıcının verdiği firma/ürün adlarını olduğu gibi araçlara ilet.
- Bir araç birden fazla eşleşme veya hata döndürürse kullanıcıya sor.
- Çok adımlı isteklerde adımları sırayla yap: teklif → onay → fatura. Önceki adımın döndürdüğü referansı (ör. S00012) kullan.
- Tutarlar TL'dir. Fiyatlar KDV hariçtir, toplamlar KDV dahildir.
- Yanıtları kısa, net ve Türkçe ver. Rakamları binlik ayraçla yaz (ör. 42.000 TL).
- Analiz isteklerinde rakamları yorumla: artış/azalış yüzdesi, öne çıkan müşteri/ürün."""


class Status(enum.Enum):
    DONE = "done"
    PENDING = "pending"
    REJECTED = "rejected"


@dataclass
class ToolCall:
    name: str
    arguments: dict


@dataclass
class TraceEntry:
    name: str
    arguments: dict
    status: Status
    result: Any = None


@dataclass
class Turn:
    reply: str | None = None
    pending: ToolCall | None = None
    trace: list[TraceEntry] = field(default_factory=list)


class LLM(Protocol):
    def chat(self, messages: list[dict], tools: list[dict]) -> dict: ...


class Tools(Protocol):
    def schemas(self) -> list[dict]: ...
    def kind(self, name: str) -> Kind: ...
    def run(self, name: str, args: dict) -> Any: ...


class Agent:
    def __init__(self, llm: LLM, tools: Tools) -> None:
        self._llm = llm
        self._tools = tools
        self._queue: list[ToolCall] = []
        self.reset()

    def reset(self) -> None:
        today = datetime.date.today().isoformat()
        self._messages: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT.format(today=today)}]
        self._queue = []

    def send(self, text: str, images: list[str] | None = None) -> Turn:
        msg: dict = {"role": "user", "content": text}
        if images:
            msg["images"] = images
        self._messages.append(msg)

        return self._loop([])

    def approve(self) -> Turn:
        call = self._queue.pop(0)
        trace = [self._execute(call)]
        return self._loop(trace)

    def reject(self) -> Turn:
        call = self._queue.pop(0)
        self._tool_message(call.name, {"error": "Kullanıcı bu işlemi reddetti."})
        trace = [TraceEntry(call.name, call.arguments, Status.REJECTED)]
        return self._loop(trace)

    def _loop(self, trace: list[TraceEntry]) -> Turn:
        for _ in range(_MAX_STEPS):
            pending = self._drain(trace)
            if pending:
                return Turn(pending=pending, trace=trace)

            resp = self._llm.chat(self._messages, self._tools.schemas())
            calls = [ToolCall(c["name"], c["arguments"]) for c in resp["tool_calls"]]
            self._messages.append({
                "role": "assistant",
                "content": resp["content"],
                "tool_calls": [{"function": {"name": c.name, "arguments": c.arguments}} for c in calls],
            })

            if not calls:
                return Turn(reply=resp["content"], trace=trace)

            self._queue = calls

        return Turn(reply="İşlem adım sınırını aştı; isteği daha küçük parçalara bölün.", trace=trace)

    def _drain(self, trace: list[TraceEntry]) -> ToolCall | None:
        while self._queue:
            call = self._queue[0]
            if self._tools.kind(call.name) is Kind.WRITE:
                trace.append(TraceEntry(call.name, call.arguments, Status.PENDING))
                return call

            self._queue.pop(0)
            trace.append(self._execute(call))

        return None

    def _execute(self, call: ToolCall) -> TraceEntry:
        result = self._tools.run(call.name, call.arguments)
        self._tool_message(call.name, result)
        return TraceEntry(call.name, call.arguments, Status.DONE, result)

    def _tool_message(self, name: str, result: Any) -> None:
        content = json.dumps(result, ensure_ascii=False, default=str)
        self._messages.append({"role": "tool", "tool_name": name, "content": content})
