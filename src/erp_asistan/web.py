"""HTTP API + static single-page UI."""

import os
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from erp_asistan.agent import Agent, Status, ToolCall, Turn
from erp_asistan.history import History
from erp_asistan.invoice_reader import check, read_invoice
from erp_asistan.session import ErpClosed, Session

__all__ = ["Services", "create_app", "main"]

_STATIC = Path(__file__).parent / "static"
_HTTP_UNPROCESSABLE = 422
_HTTP_NOT_FOUND = 404
_HTTP_BAD_GATEWAY = 502
_HTTP_CONFLICT = 409
_LOW_STOCK_THRESHOLD = 5

_LABELS = {
    "find_partner": "Cari arandı",
    "find_products": "Ürün arandı",
    "get_low_stock": "Kritik stok listelendi",
    "list_open_invoices": "Açık faturalar listelendi",
    "find_orders": "Teklif ve siparişler arandı",
    "sales_summary": "Satış özeti çıkarıldı",
    "compare_sales": "Dönemler karşılaştırıldı",
    "create_partner": "Yeni cari",
    "update_product_price": "Fiyat güncelleme",
    "create_quotation": "Teklif oluşturma",
    "confirm_order": "Sipariş onayı",
    "create_invoice": "Fatura kesme",
    "create_vendor_bill": "Tedarikçi faturası",
    "claim_guard": "Denetim: araç çağrılmadan işlem yapıldı denildi, model uyarıldı",
}

_ARG_LABELS = {
    "order_ref": "Sipariş", "partner": "Müşteri", "vendor": "Tedarikçi", "name": "Ad", "city": "Şehir",
    "phone": "Telefon", "email": "E-posta", "product": "Ürün", "price": "Yeni fiyat (KDV hariç)",
    "lines": "Kalemler", "date": "Tarih", "ref": "Belge no",
}


@dataclass
class Services:
    session: Session
    extractor: Any
    transcribe: Callable[[Path], str]
    history: History
    probes: dict[str, Callable[[], bool]] = field(default_factory=dict)


class ChatIn(BaseModel):
    text: str
    voice: bool = False


class InvoiceIn(BaseModel):
    vendor: str
    invoice_no: str = ""
    date: str
    lines: list[dict]
    untaxed: float
    vat: float
    total: float


class ErpIn(BaseModel):
    id: str


def _line(item: dict) -> str:
    qty = item.get("quantity")
    if "product" in item:
        return f"{qty:g} × {item['product']}"
    return f"{qty:g} × {item.get('description')} · {item.get('price_unit')} TL"


def _pending(call: ToolCall) -> dict:
    # Fixed field order: the model emits arguments in arbitrary order.
    order = list(_ARG_LABELS)
    keys = sorted(call.arguments, key=lambda k: order.index(k) if k in order else len(order))
    rows = []
    for key in keys:
        value = call.arguments[key]
        shown = [_line(v) for v in value] if isinstance(value, list) else value
        rows.append({"label": _ARG_LABELS.get(key, key), "value": shown})
    return {"name": call.name, "label": _LABELS.get(call.name, call.name), "rows": rows}


def _turn(turn: Turn, seconds: float) -> dict:
    trace = [
        {"name": e.name, "label": _LABELS.get(e.name, e.name), "status": e.status.value,
         "arguments": e.arguments, "result": e.result}
        for e in turn.trace
        if e.status is not Status.PENDING
    ]
    return {
        "reply": turn.reply,
        "pending": _pending(turn.pending) if turn.pending else None,
        "trace": trace,
        "seconds": round(seconds, 1),
    }


def _save_upload(upload: UploadFile) -> Path:
    suffix = Path(upload.filename or "").suffix or ".bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(upload.file.read())
    return Path(f.name)


def create_app(s: Services) -> FastAPI:
    app = FastAPI(title="ERP Asistanı")
    lock = threading.Lock()  # single shared conversation

    def step(fn: Callable[[], Turn], event: dict) -> dict:
        started = time.time()
        with lock:
            s.history.add(event)
            try:
                turn = fn()
            except httpx.HTTPError as e:
                detail = f"Model veya ERP'ye ulaşılamadı: {e}"
                s.history.add({"type": "error", "message": detail})
                raise HTTPException(_HTTP_BAD_GATEWAY, detail) from e
            result = _turn(turn, time.time() - started)
            s.history.add({"type": "turn", **result})
        return result

    @app.get("/api/health")
    def health() -> dict:
        erps = s.session.status()
        return {
            "company": s.session.company_name(),
            "erp": next(e["up"] for e in erps if e["active"]),
            "erps": erps,
            **{k: probe() for k, probe in s.probes.items()},
        }

    @app.get("/api/logo")
    def logo() -> Response:
        try:
            data = s.session.company().get("logo")
        except httpx.HTTPError:
            data = None
        if not data:
            raise HTTPException(_HTTP_NOT_FOUND)
        return Response(data, media_type="image/png")

    @app.post("/api/chat")
    def chat(body: ChatIn) -> dict:
        return step(lambda: s.session.agent.send(body.text), {"type": "user", "text": body.text, "voice": body.voice})

    @app.post("/api/approve")
    def approve() -> dict:
        return step(lambda: s.session.agent.approve(), {"type": "decision", "approved": True})

    @app.post("/api/reject")
    def reject() -> dict:
        return step(lambda: s.session.agent.reject(), {"type": "decision", "approved": False})

    @app.post("/api/reset")
    def reset() -> dict:
        with lock:
            s.session.reset()
            s.history.start()
        return {"ok": True}

    @app.post("/api/erp")
    def switch_erp(body: ErpIn) -> dict:
        with lock:
            try:
                s.session.switch(body.id)
            except KeyError as e:
                raise HTTPException(_HTTP_NOT_FOUND) from e
            except ErpClosed as e:
                raise HTTPException(_HTTP_CONFLICT, f"{e} kapalı. Docker Desktop'tan başlatın.") from e
            s.history.start(erp=body.id)
        return {"ok": True}

    @app.get("/api/history")
    def history() -> dict:
        return {"current": s.history.current, "items": s.history.list()}

    @app.get("/api/history/{convo_id}")
    def conversation(convo_id: str) -> dict:
        convo = s.history.get(convo_id)
        if convo is None:
            raise HTTPException(_HTTP_NOT_FOUND)
        return convo

    @app.get("/api/overview")
    def overview() -> dict:
        try:
            quotations = s.session.tools.run("find_orders", {"state": "quotation"})
            low = s.session.tools.run("get_low_stock", {"threshold": _LOW_STOCK_THRESHOLD})
            invoices = s.session.tools.run("list_open_invoices", {})
        except httpx.HTTPError as e:
            raise HTTPException(_HTTP_BAD_GATEWAY, f"ERP'ye ulaşılamadı: {e}") from e

        for result in (quotations, low, invoices):
            if isinstance(result, dict) and "error" in result:
                raise HTTPException(_HTTP_BAD_GATEWAY, result["error"])
        return {
            "quotations": len(quotations),
            "low_stock": len(low),
            "open_invoices": invoices["count"],
            "open_total": invoices["total_residual"],
        }

    @app.post("/api/transcribe")
    def transcribe(audio: UploadFile = File(...)) -> dict:
        path = _save_upload(audio)
        try:
            return {"text": s.transcribe(path)}
        finally:
            path.unlink(missing_ok=True)

    @app.post("/api/invoice/read")
    def invoice_read(image: UploadFile = File(...)) -> dict:
        path = _save_upload(image)
        started = time.time()
        try:
            inv = read_invoice(s.extractor, path)
        except (httpx.HTTPError, ValueError) as e:
            raise HTTPException(_HTTP_BAD_GATEWAY, f"Fatura okunamadı: {e}") from e
        finally:
            path.unlink(missing_ok=True)
        return {"invoice": inv, "warnings": check(inv), "seconds": round(time.time() - started, 1)}

    @app.post("/api/invoice/check")
    def invoice_check(body: InvoiceIn) -> dict:
        return {"warnings": check(body.model_dump())}

    @app.post("/api/invoice/post")
    def invoice_post(body: InvoiceIn) -> dict:
        inv = body.model_dump()
        warnings = check(inv)
        if warnings:
            raise HTTPException(_HTTP_UNPROCESSABLE, " ".join(warnings))

        args = {"vendor": inv["vendor"], "lines": inv["lines"], "date": inv["date"], "ref": inv["invoice_no"] or None}
        result = s.session.tools.run("create_vendor_bill", args)
        if "error" in result:
            raise HTTPException(_HTTP_UNPROCESSABLE, result["error"])

        return result | {"url": s.session.active.erp.record_url(result["id"])}

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(_STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=_STATIC), name="static")
    return app


_PORT = 7860
_HISTORY_DIR = "history"
_OLLAMA_PS = "http://localhost:11434/api/ps"
_WARM_UP_AUDIO = Path(__file__).resolve().parents[2] / "samples" / "audio" / "teklif-komutu.wav"


def main() -> None:
    import uvicorn
    from dotenv import load_dotenv

    from erp_asistan.backends import DEFAULT_ERP, load_slots, reachable
    from erp_asistan.llm import OllamaLLM
    from erp_asistan.speech import is_ready, transcribe, warm_up

    load_dotenv(Path.cwd() / ".env")
    warm_up(_WARM_UP_AUDIO)

    llm = OllamaLLM()
    session = Session(
        load_slots(),
        os.environ.get("ERP_DEFAULT", DEFAULT_ERP),
        make_agent=lambda tools, company, erp: Agent(llm, tools, company=company, erp=erp),
    )
    services = Services(
        session=session,
        extractor=llm,
        transcribe=transcribe,
        history=History(Path.cwd() / _HISTORY_DIR, erp=session.active.id),
        probes={
            "model": lambda: reachable(_OLLAMA_PS),
            "speech": is_ready,
        },
    )
    uvicorn.run(create_app(services), host="127.0.0.1", port=_PORT, log_level="warning")


if __name__ == "__main__":
    main()
