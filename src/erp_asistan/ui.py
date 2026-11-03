"""Gradio chat UI with tool trace and human approval."""

import os

# Must precede the gradio import: demo runs offline.
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

import json
import time

import gradio as gr
import httpx
from dotenv import load_dotenv

from erp_asistan.agent import Agent, Status, ToolCall, Turn
from erp_asistan.fmt import tl
from erp_asistan.invoice_reader import check, read_invoice
from erp_asistan.llm import OllamaLLM
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

_LINE_HEADERS = ["Açıklama", "Miktar", "Birim Fiyat (KDV hariç)"]

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


def _rows_to_lines(rows: list[list]) -> list[dict]:
    lines = []
    for desc, qty, price in rows:
        if not str(desc).strip():
            continue
        lines.append({"description": str(desc), "quantity": float(qty), "price_unit": float(price)})
    return lines


def _check_md(inv: dict, lines: list[dict]) -> str:
    edited = inv | {"lines": lines}
    warnings = check(edited)
    head = f"**Ara toplam:** {tl(inv['untaxed'])} · **KDV:** {tl(inv['vat'])} · **Ödenecek:** {tl(inv['total'])}"
    if not warnings:
        return f"{head}\n\n✅ Kalemler ve toplamlar birbirini tutuyor."
    return head + "\n\n" + "\n".join(f"⚠️ {w}" for w in warnings)


def _build(agent: Agent, tools: ToolRegistry, llm: OllamaLLM) -> gr.Blocks:
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

    def on_read(image: str | None):
        if not image:
            return gr.update(), gr.update(), gr.update(), gr.update(), "Önce bir fatura görseli seçin.", None
        started = time.time()
        try:
            inv = read_invoice(llm, image)
        except (httpx.HTTPError, ValueError, KeyError) as e:
            return gr.update(), gr.update(), gr.update(), gr.update(), f"Okunamadı: {e}", None

        rows = [[l["description"], l["quantity"], l["price_unit"]] for l in inv["lines"]]
        status = f"🔍 Model faturayı {time.time() - started:.1f} sn'de okudu.\n\n" + _check_md(inv, inv["lines"])
        return inv["vendor"], inv["invoice_no"], inv["date"], rows, status, inv

    def on_edit(rows: list[list], inv: dict | None):
        if not inv:
            return gr.update()
        try:
            return _check_md(inv, _rows_to_lines(rows))
        except (TypeError, ValueError):
            return "⚠️ Tabloda geçersiz sayı var."

    def on_post(vendor: str, invoice_no: str, date: str, rows: list[list], inv: dict | None):
        if not inv:
            return "Önce faturayı okutun."
        try:
            lines = _rows_to_lines(rows)
        except (TypeError, ValueError):
            return "⛔ Tabloda geçersiz sayı var."
        if check(inv | {"lines": lines}):
            return "⛔ Kalemler toplamları tutmuyor. Önce tabloyu düzeltin; tutarsız fatura işlenmez."

        args = {"vendor": vendor, "lines": lines, "date": date, "ref": invoice_no}
        result = tools.run("create_vendor_bill", args)
        if "error" in result:
            return f"❌ {result['error']}"

        # ?db= is required: the server hosts more than one DB (demo + tests).
        url = f"{os.environ['ODOO_URL']}/odoo/account.move/{result['id']}?db={os.environ['ODOO_DB']}"
        return (
            f"✅ Taslak tedarikçi faturası oluşturuldu: **{result['partner']}** · "
            f"Ödenecek **{tl(result['total'])}** · [Odoo'da aç ↗]({url})"
        )

    with gr.Blocks(title="ERP Asistanı") as demo:
        gr.Markdown("## 🧾 ERP Asistanı\nOdoo 19 + yerel **Gemma 4 12B** · veri bu bilgisayardan çıkmaz")

        with gr.Row():
            with gr.Column(scale=3):
                with gr.Tab("💬 Sohbet"):
                    chat = gr.Chatbot(height=560, show_label=False)
                    with gr.Group(visible=False, elem_id="approval") as approval_box:
                        approval_md = gr.Markdown()
                        with gr.Row():
                            approve_btn = gr.Button("✅ Onayla", variant="primary")
                            reject_btn = gr.Button("❌ Reddet", variant="stop")
                    with gr.Row():
                        box = gr.Textbox(placeholder="Komutunuzu yazın…", show_label=False, scale=8)
                        send_btn = gr.Button("Gönder", variant="primary", scale=1)

                with gr.Tab("📷 Fatura oku"):
                    inv_state = gr.State(None)
                    with gr.Row():
                        image = gr.Image(
                            type="filepath", sources=["upload", "webcam", "clipboard"],
                            label="Fatura görseli", height=420, scale=2,
                        )
                        with gr.Column(scale=3):
                            read_btn = gr.Button("🔍 Faturayı oku", variant="primary")
                            vendor = gr.Textbox(label="Tedarikçi")
                            with gr.Row():
                                inv_no = gr.Textbox(label="Fatura no")
                                inv_date = gr.Textbox(label="Tarih (YYYY-AA-GG)")
                    lines_df = gr.Dataframe(
                        headers=_LINE_HEADERS, datatype=["str", "number", "number"],
                        type="array", interactive=True, column_count=(3, "fixed"),
                    )
                    inv_status = gr.Markdown()
                    post_btn = gr.Button("📥 Odoo'ya tedarikçi faturası olarak işle", variant="primary")
                    post_result = gr.Markdown()

            with gr.Column(scale=1):
                gr.Markdown("**Örnek komutlar**")
                example_btns = [gr.Button(e, size="sm") for e in _EXAMPLES]
                reset_btn = gr.Button("🗑️ Yeni sohbet", size="sm")
                gr.Markdown(f"[Odoo'yu aç ↗]({os.environ['ODOO_URL']}/odoo?db={os.environ['ODOO_DB']})")

        outputs = [chat, approval_box, approval_md, send_btn]
        box.submit(on_send, [box, chat], [*outputs, box])
        send_btn.click(on_send, [box, chat], [*outputs, box])
        approve_btn.click(on_approve, chat, outputs)
        reject_btn.click(on_reject, chat, outputs)
        reset_btn.click(on_reset, None, outputs)
        read_btn.click(on_read, image, [vendor, inv_no, inv_date, lines_df, inv_status, inv_state])
        lines_df.input(on_edit, [lines_df, inv_state], inv_status)
        post_btn.click(on_post, [vendor, inv_no, inv_date, lines_df, inv_state], post_result)
        for b in example_btns:
            b.click(lambda e=b.value: e, None, box)

    return demo


def main() -> None:
    load_dotenv(".env")
    llm = OllamaLLM()
    tools = ToolRegistry(OdooClient.from_env())
    agent = Agent(llm, tools)
    theme = gr.themes.Soft(font=["system-ui", "sans-serif"], font_mono=["ui-monospace", "monospace"])
    _build(agent, tools, llm).launch(server_port=_PORT, theme=theme, css=_CSS)


if __name__ == "__main__":
    main()
