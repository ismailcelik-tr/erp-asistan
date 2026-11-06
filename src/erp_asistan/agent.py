"""Tool-calling loop that pauses on write tools until a human approves."""

import datetime
import enum
import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from erp_asistan.tools import Kind

__all__ = ["Agent", "Status", "ToolCall", "Tools", "TraceEntry", "Turn"]

_MAX_STEPS = 10
_NOTHING_PENDING = "Onay bekleyen işlem yok."

# gemma4:12b sometimes reports "teklif oluşturuldu" after only read tools ran.
_SUCCESS_CLAIM = re.compile(
    r"(oluşturul|güncellen|kesil|onaylan|eklen|kaydedil|işlen)(dı|di|du|dü|mış|miş|muş|müş)",
    re.IGNORECASE,
)
_MAX_CHALLENGES = 2
# First match wins: "teklif oluşturuldu ve onaylandı" → create_quotation.
_LIKELY_TOOL = [
    (re.compile(r"teklif", re.IGNORECASE), "create_quotation"),
    (re.compile(r"fatura", re.IGNORECASE), "create_invoice"),
    (re.compile(r"onaylan", re.IGNORECASE), "confirm_order"),
    (re.compile(r"fiyat", re.IGNORECASE), "update_product_price"),
    (re.compile(r"müşteri|cari", re.IGNORECASE), "create_partner"),
]
_CLAIM_CHALLENGE = (
    "[Sistem denetimi] Bu istekte henüz hiçbir yazma aracı çalışmadı; ERP'de değişiklik yok. "
    "İşlem gerekiyorsa aracı ŞİMDİ çağır{hint}; \"yapacağım\" deyip durma. "
    "Gerekmiyorsa işlemin yapılmadığını açıkça söyle."
)

_SYSTEM_PROMPT = """Sen "{company}" şirketinin ERP asistanısın; {erp} sistemine bağlısın. Bugün {today}.
Kurallar:
- Veriyi asla uydurma; her bilgi için araç çağır.
- Kullanıcı kayıt oluşturmak/değiştirmek isterse ilgili yazma aracını MUTLAKA çağır. Onayı arayüz ister; sen ayrıca onay sorma.
- Bir işlemi ancak yazma aracı sonuç döndürdükten sonra "yapıldı" diye bildir; referans numarasını araç sonucundan al.
- Arama araçlarından sonra yazma aracını aynı yanıtta çağır; "oluşturuyorum" deyip durma.
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
    GUARDED = "guarded"


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


def _challenge(claim: str) -> str:
    tool = next((t for pattern, t in _LIKELY_TOOL if pattern.search(claim)), None)
    hint = f" (muhtemelen {tool})" if tool else ""
    return _CLAIM_CHALLENGE.format(hint=hint)


class Agent:
    def __init__(self, llm: LLM, tools: Tools, company: str = "şirket", erp: str = "ERP") -> None:
        self._llm = llm
        self._company = company
        self._erp = erp
        self._tools = tools
        self._queue: list[ToolCall] = []
        self.reset()

    def reset(self) -> None:
        today = datetime.date.today().isoformat()
        self._messages: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT.format(company=self._company, erp=self._erp, today=today)}]
        self._queue = []
        self._wrote = False
        self._challenges = 0

    def send(self, text: str, images: list[str] | None = None) -> Turn:
        msg: dict = {"role": "user", "content": text}
        if images:
            msg["images"] = images
        self._messages.append(msg)
        self._wrote = False
        self._challenges = 0

        return self._loop([])

    def approve(self) -> Turn:
        if not self._queue:
            return Turn(reply=_NOTHING_PENDING)

        call = self._queue.pop(0)
        trace = [self._execute(call)]
        return self._loop(trace)

    def reject(self) -> Turn:
        if not self._queue:
            return Turn(reply=_NOTHING_PENDING)

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

            if not calls and self._needs_challenge(resp["content"]):
                self._challenges += 1
                self._messages.append({"role": "user", "content": _challenge(resp["content"])})
                trace.append(TraceEntry("claim_guard", {"iddia": resp["content"]}, Status.GUARDED, "Model uyarıldı."))
                continue

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

    def _needs_challenge(self, content: str) -> bool:
        """A success claim without any write; after one challenge, any write-less stop."""
        if self._wrote or self._challenges >= _MAX_CHALLENGES:
            return False
        return self._challenges > 0 or bool(_SUCCESS_CLAIM.search(content))

    def _execute(self, call: ToolCall) -> TraceEntry:
        if self._tools.kind(call.name) is Kind.WRITE:
            self._wrote = True
        result = self._tools.run(call.name, call.arguments)
        self._tool_message(call.name, result)
        return TraceEntry(call.name, call.arguments, Status.DONE, result)

    def _tool_message(self, name: str, result: Any) -> None:
        content = json.dumps(result, ensure_ascii=False, default=str)
        self._messages.append({"role": "tool", "tool_name": name, "content": content})
