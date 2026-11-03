"""Gradio chat UI with tool trace and human approval."""

import os

# Must precede the gradio import: demo runs offline.
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import json
import time

import gradio as gr
import httpx
from dotenv import load_dotenv

from erp_asistan.agent import Agent, OllamaLLM, Status, ToolCall, Turn
from erp_asistan.odoo.client import OdooClient
from erp_asistan.tools import ToolRegistry

__all__ = ["main"]

_PORT = 7860
_TRACE_LIMIT = 1500

_LABELS = {
    "find_partner": "Cari ara",
    "find_products": "Ürün ara",
    "get_low_stock": "Kritik stok",
    "list_open_invoices": "Açık faturalar",
    "sales_summary": "Satış özeti",
    "create_partner": "Yeni cari",
    "update_product_price": "Fiyat güncelle",
    "create_quotation": "Teklif oluştur",
    "confirm_order": "Siparişi onayla",
    "create_invoice": "Fatura kes",
    "create_vendor_bill": "Tedarikçi faturası",
}

_ARG_LABELS = {
    "partner": "Müşteri", "vendor": "Tedarikçi", "name": "Ad", "city": "Şehir",
    "phone": "Telefon", "email": "E-posta", "product": "Ürün", "price": "Yeni fiyat",
    "lines": "Kalemler", "order_ref": "Sipariş", "date": "Tarih", "ref": "Belge no",
}

_EXAMPLES = [
    "Stokta 5'ten az kalan ürünler hangileri?",
    "Anadolu Gıda'nın açık faturaları toplam ne kadar?",
    "Yeni müşteri ekle: Boğaziçi Danışmanlık, İstanbul",
    "Lazer yazıcının fiyatını 7.900 TL yap",
    "Marmara Ofis'e 3 adet 27 inç monitör için teklif oluştur, onayla ve faturasını kes",
    "Ekim satışlarını özetle; en çok satan ürün ve en iyi müşteri kim?",
]

_CSS = """
#approval {border: 2px solid #d97706; border-radius: 10px; padding: 12px; background: #fffbeb;}
footer {display: none !important;}
"""


def _line(item: dict) -> str:
    qty = item.get("quantity")
    if "product" in item:
        return f"{qty} × {item['product']}"
    return f"{qty} × {item.get('description')} @ {item.get('price_unit')} TL"


def _describe(call: ToolCall) -> str:
    rows = [f"### ⚠️ Onay bekliyor: {_LABELS.get(call.name, call.name)}"]
    for key, value in call.arguments.items():
        label = _ARG_LABELS.get(key, key)
        if isinstance(value, list):
            rows.append(f"- **{label}:**")
            rows += [f"    - {_line(v)}" for v in value]
            continue
        rows.append(f"- **{label}:** {value}")
    return "\n".join(rows)


def _trace_message(entry, elapsed: float) -> dict:
    icon = "🔧" if entry.status is Status.DONE else "⛔ Reddedildi:"
    body = {"parametreler": entry.arguments, "sonuç": entry.result}
    text = json.dumps(body, ensure_ascii=False, indent=2, default=str)[:_TRACE_LIMIT]
    return {
        "role": "assistant",
        "content": f"```json\n{text}\n```",
        "metadata": {"title": f"{icon} {_LABELS.get(entry.name, entry.name)} · {elapsed:.1f} sn"},
    }


def _build(agent: Agent) -> gr.Blocks:
    def render(history: list, turn: Turn, started: float):
        elapsed = time.time() - started
        history += [_trace_message(e, elapsed) for e in turn.trace if e.status is not Status.PENDING]
        if turn.reply:
            history.append({"role": "assistant", "content": turn.reply})

        pending = turn.pending is not None
        approval = _describe(turn.pending) if pending else ""
        return history, gr.update(visible=pending), approval, gr.update(interactive=not pending)

    def run(history: list, step):
        started = time.time()
        try:
            turn = step()
        except httpx.HTTPError as e:
            turn = Turn(reply=f"Model veya ERP'ye ulaşılamadı: {e}")
        return render(history, turn, started)

    def on_send(text: str, history: list):
        if not text.strip():
            yield history, gr.update(), "", gr.update(), text
            return

        history = history + [{"role": "user", "content": text}]
        yield history, gr.update(visible=False), "", gr.update(interactive=False), ""
        yield *run(history, lambda: agent.send(text)), ""

    def decide(history: list, step):
        yield history, gr.update(visible=False), "", gr.update(interactive=False)
        yield run(history, step)

    def on_approve(history: list):
        yield from decide(history, agent.approve)

    def on_reject(history: list):
        yield from decide(history, agent.reject)

    def on_reset():
        agent.reset()
        return [], gr.update(visible=False), "", gr.update(interactive=True)

    with gr.Blocks(title="ERP Asistanı") as demo:
        gr.Markdown("## 🧾 ERP Asistanı\nOdoo 19 + yerel **Gemma 4 12B** · veri bu bilgisayardan çıkmaz")

        with gr.Row():
            with gr.Column(scale=3):
                chat = gr.Chatbot(height=560, show_label=False)
                with gr.Group(visible=False, elem_id="approval") as approval_box:
                    approval_md = gr.Markdown()
                    with gr.Row():
                        approve_btn = gr.Button("✅ Onayla", variant="primary")
                        reject_btn = gr.Button("❌ Reddet", variant="stop")
                with gr.Row():
                    box = gr.Textbox(placeholder="Komutunuzu yazın…", show_label=False, scale=8)
                    send_btn = gr.Button("Gönder", variant="primary", scale=1)

            with gr.Column(scale=1):
                gr.Markdown("**Örnek komutlar**")
                example_btns = [gr.Button(e, size="sm") for e in _EXAMPLES]
                reset_btn = gr.Button("🗑️ Yeni sohbet", size="sm")
                gr.Markdown(f"[Odoo'yu aç ↗]({os.environ['ODOO_URL']})")

        outputs = [chat, approval_box, approval_md, send_btn]
        box.submit(on_send, [box, chat], [*outputs, box])
        send_btn.click(on_send, [box, chat], [*outputs, box])
        approve_btn.click(on_approve, chat, outputs)
        reject_btn.click(on_reject, chat, outputs)
        reset_btn.click(on_reset, None, outputs)
        for b in example_btns:
            b.click(lambda e=b.value: e, None, box)

    return demo


def main() -> None:
    load_dotenv(".env")
    agent = Agent(OllamaLLM(), ToolRegistry(OdooClient.from_env()))
    theme = gr.themes.Soft(font=["system-ui", "sans-serif"], font_mono=["ui-monospace", "monospace"])
    _build(agent).launch(server_port=_PORT, theme=theme, css=_CSS)


if __name__ == "__main__":
    main()
