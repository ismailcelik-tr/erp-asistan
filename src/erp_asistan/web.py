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
from erp_asistan.invoice_reader import check, read_invoice

__all__ = ["Services", "create_app", "main"]

_STATIC = Path(__file__).parent / "static"
_HTTP_UNPROCESSABLE = 422
_HTTP_NOT_FOUND = 404
_HTTP_BAD_GATEWAY = 502

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
    "partner": "Müşteri", "vendor": "Tedarikçi", "name": "Ad", "city": "Şehir", "phone": "Telefon",
    "email": "E-posta", "product": "Ürün", "price": "Yeni fiyat (KDV hariç)", "lines": "Kalemler",
    "order_ref": "Sipariş", "date": "Tarih", "ref": "Belge no",
}


@dataclass
class Services:
    agent: Agent
    tools: Any
    extractor: Any
    transcribe: Callable[[Path], str]
    company: dict
    odoo_url: str
    odoo_db: str
    probes: dict[str, Callable[[], bool]] = field(default_factory=dict)


class ChatIn(BaseModel):
    text: str


class InvoiceIn(BaseModel):
    vendor: str
    invoice_no: str = ""
    date: str
    lines: list[dict]
    untaxed: float
    vat: float
    total: float


def _line(item: dict) -> str:
    qty = item.get("quantity")
    if "product" in item:
        return f"{qty:g} × {item['product']}"
    return f"{qty:g} × {item.get('description')} · {item.get('price_unit')} TL"


def _pending(call: ToolCall) -> dict:
    rows = []
    for key, value in call.arguments.items():
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

    def step(fn: Callable[[], Turn]) -> dict:
        started = time.time()
        with lock:
            try:
                turn = fn()
            except httpx.HTTPError as e:
                raise HTTPException(_HTTP_BAD_GATEWAY, f"Model veya ERP'ye ulaşılamadı: {e}") from e
        return _turn(turn, time.time() - started)

    @app.get("/api/health")
    def health() -> dict:
        return {"company": s.company["name"], **{k: probe() for k, probe in s.probes.items()}}

    @app.get("/api/logo")
    def logo() -> Response:
        if not s.company.get("logo"):
            raise HTTPException(_HTTP_NOT_FOUND)
        return Response(s.company["logo"], media_type="image/png")

    @app.post("/api/chat")
    def chat(body: ChatIn) -> dict:
        return step(lambda: s.agent.send(body.text))

    @app.post("/api/approve")
    def approve() -> dict:
        return step(s.agent.approve)

    @app.post("/api/reject")
    def reject() -> dict:
        return step(s.agent.reject)

    @app.post("/api/reset")
    def reset() -> dict:
        with lock:
            s.agent.reset()
        return {"ok": True}

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
        result = s.tools.run("create_vendor_bill", args)
        if "error" in result:
            raise HTTPException(_HTTP_UNPROCESSABLE, result["error"])

        # ?db= is required: the server hosts more than one DB (demo + tests).
        url = f"{s.odoo_url}/odoo/account.move/{result['id']}?db={s.odoo_db}"
        return result | {"url": url}

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(_STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=_STATIC), name="static")
    return app


_PORT = 7860
_OLLAMA_PS = "http://localhost:11434/api/ps"
_PROBE_TIMEOUT_SECONDS = 2
_WARM_UP_AUDIO = Path(__file__).resolve().parents[2] / "samples" / "audio" / "teklif-komutu.wav"


def _reachable(url: str) -> bool:
    try:
        return httpx.get(url, timeout=_PROBE_TIMEOUT_SECONDS).status_code < _HTTP_UNPROCESSABLE
    except httpx.HTTPError:
        return False


def main() -> None:
    import uvicorn
    from dotenv import load_dotenv

    from erp_asistan.erp.company import company_info
    from erp_asistan.llm import OllamaLLM
    from erp_asistan.odoo.client import OdooClient
    from erp_asistan.speech import is_ready, transcribe, warm_up
    from erp_asistan.tools import ToolRegistry

    load_dotenv(Path.cwd() / ".env")
    warm_up(_WARM_UP_AUDIO)

    odoo = OdooClient.from_env()
    company = company_info(odoo)
    llm = OllamaLLM()
    tools = ToolRegistry(odoo)
    odoo_url = os.environ["ODOO_URL"]

    services = Services(
        agent=Agent(llm, tools, company=company["name"]),
        tools=tools,
        extractor=llm,
        transcribe=transcribe,
        company=company,
        odoo_url=odoo_url,
        odoo_db=os.environ["ODOO_DB"],
        probes={
            "model": lambda: _reachable(_OLLAMA_PS),
            "erp": lambda: _reachable(f"{odoo_url}/web/health"),
            "speech": is_ready,
        },
    )
    uvicorn.run(create_app(services), host="127.0.0.1", port=_PORT, log_level="warning")


if __name__ == "__main__":
    main()
