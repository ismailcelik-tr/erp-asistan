"use strict";

const EXAMPLES = [
  ["Sorgu", [
    "Stokta 5'ten az kalan ürünler hangileri?",
    "M.U.CLV.00001 kodlu ürünün fiyatı ve stoğu ne?",
    "Ege Güvenlik'in açık faturaları toplam ne kadar?",
    "Onay bekleyen teklifler hangileri?",
  ]],
  ["Analiz", [
    "Eylül ve Ekim satışlarını karşılaştır.",
    "Ekim'de en çok satan ürünler ve en iyi müşteri kim?",
  ]],
  ["İşlem", [
    "Yeni müşteri ekle: Kızılay Elektrik, Ankara",
    "LUCIANO USB şarj prizinin fiyatını 1.150 TL yap.",
    "Akdeniz Resort'un bekleyen teklifini onayla.",
  ]],
  ["Çok adımlı", [
    "Porsuk Sitesi'ne 24 adet VEGA kapıcısız şube için teklif oluştur, onayla ve faturasını kes.",
  ]],
];

const HEALTH_INTERVAL_MS = 10000;
const CHECK_DEBOUNCE_MS = 300;
const MIN_RECORDING_MS = 400;
const TRACE_ARGS_MAX = 70;
const SPACE = " ";

const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) { node.className = cls; }
  if (text !== undefined) { node.textContent = text; }
  return node;
};

const money = new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const tl = (v) => `${money.format(v || 0)} TL`;
const seconds = (v) => `${String(v).replace(".", ",")} sn`;

async function api(path, options = {}) {
  const resp = await fetch(path, options);
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(body.detail || `İstek başarısız (${resp.status})`);
  }
  return body;
}

const postJson = (path, data) => api(path, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: data === undefined ? undefined : JSON.stringify(data),
});

/* ---------- Header ---------- */

async function refreshHealth() {
  try {
    const h = await api("/api/health");
    $("company").textContent = h.company;
    document.querySelectorAll(".leds li").forEach((li) => {
      li.querySelector(".led").className = `led ${h[li.dataset.probe] ? "ok" : "alarm"}`;
    });
  } catch {
    document.querySelectorAll(".leds .led").forEach((led) => { led.className = "led alarm"; });
  }
}

function initBrand() {
  const logo = $("logo");
  const show = () => { logo.hidden = false; $("company").hidden = true; };
  // A cached logo can finish loading before this script runs.
  if (logo.complete && logo.naturalWidth) { show(); return; }
  logo.addEventListener("load", show);
  logo.addEventListener("error", () => { logo.remove(); });
}

function initTabs() {
  const tabs = [["tab-chat", "view-chat"], ["tab-invoice", "view-invoice"]];
  for (const [tabId, viewId] of tabs) {
    $(tabId).addEventListener("click", () => {
      for (const [t, v] of tabs) {
        $(t).setAttribute("aria-selected", String(t === tabId));
        $(v).hidden = v !== viewId;
      }
      if (viewId === "view-chat") { $("input").focus(); }
    });
  }
}

/* ---------- Chat rendering ---------- */

const stream = $("stream");
let busy = false;

function push(node) {
  $("empty")?.remove();
  stream.append(node);
  stream.scrollTop = stream.scrollHeight;
  return node;
}

function inline(text) {
  const span = el("span");
  const parts = text.split(/\*\*(.+?)\*\*/g);
  parts.forEach((part, i) => span.append(i % 2 ? el("strong", null, part) : document.createTextNode(part)));
  return span;
}

// Minimal markdown: paragraphs, bullet and numbered lists, **bold**. Text only, never HTML.
function renderMarkdown(text) {
  const box = el("div");
  let list = null;
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    const bullet = line.match(/^[*-]\s+(.*)$/);
    const numbered = line.match(/^\d+[.)]\s+(.*)$/);
    const item = bullet || numbered;
    if (item) {
      const tag = bullet ? "ul" : "ol";
      if (!list || list.tagName.toLowerCase() !== tag) { list = box.appendChild(el(tag)); }
      list.appendChild(el("li")).append(inline(item[1]));
      continue;
    }
    list = null;
    if (line) { box.appendChild(el("p")).append(inline(line)); }
  }
  return box;
}

const MIC_SVG = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 15a3.5 3.5 0 0 0 3.5-3.5v-6a3.5 3.5 0 1 0-7 0v6A3.5 3.5 0 0 0 12 15Z"/></svg>';

function renderUser(text, voice) {
  const msg = el("div", "msg user");
  const plate = msg.appendChild(el("div", "plate"));
  if (voice) {
    const tag = plate.appendChild(el("div", "voice"));
    tag.innerHTML = MIC_SVG;
    tag.append("Sesli komut");
  }
  plate.append(el("div", null, text));
  push(msg);
}

function argSummary(args) {
  const parts = Object.values(args || {}).map((v) => (Array.isArray(v) ? `${v.length} kalem` : String(v)));
  const joined = parts.join(", ");
  return joined.length > TRACE_ARGS_MAX ? `${joined.slice(0, TRACE_ARGS_MAX)}…` : joined;
}

const STATUS_LED = { done: "ok", rejected: "alarm", guarded: "alarm" };
const STATUS_NOTE = { rejected: "vazgeçildi" };

function renderTrace(trace, secs) {
  if (!trace.length) { return; }
  const list = el("ul", "trace");
  trace.forEach((t, i) => {
    const details = list.appendChild(el("li")).appendChild(el("details"));
    const summary = details.appendChild(el("summary"));
    summary.append(el("i", `led ${STATUS_LED[t.status] || "ok"}`), el("b", null, t.label));
    const note = STATUS_NOTE[t.status] || argSummary(t.arguments);
    if (note) { summary.append(el("span", "args", note)); }
    if (i === trace.length - 1) { summary.append(el("span", "time", seconds(secs))); }
    details.append(el("pre", null, JSON.stringify({ parametreler: t.arguments, sonuç: t.result }, null, 2)));
  });
  push(list);
}

function renderWorking(text) {
  const row = el("div", "msg working");
  row.append(el("i", "led"), el("i", "led"), el("i", "led"), el("span", null, text));
  return push(row);
}

function renderError(message) {
  const row = el("div", "msg error");
  row.append(el("i", "led alarm"), el("span", null, message));
  push(row);
}

function renderApproval(pending) {
  const panel = el("section", "approval");
  panel.setAttribute("aria-label", "Onay bekleyen işlem");
  const title = panel.appendChild(el("h3"));
  title.append(el("i", "led wait"), `Onay bekliyor: ${pending.label}`);

  const dl = panel.appendChild(el("dl"));
  for (const row of pending.rows) {
    dl.append(el("dt", null, row.label));
    const dd = dl.appendChild(el("dd"));
    if (Array.isArray(row.value)) {
      const ul = dd.appendChild(el("ul"));
      row.value.forEach((v) => ul.append(el("li", null, v)));
    } else {
      dd.textContent = row.value;
    }
  }

  const actions = panel.appendChild(el("div", "actions"));
  const ok = actions.appendChild(el("button", "primary", "Onayla"));
  const no = actions.appendChild(el("button", "secondary", "Vazgeç"));
  ok.type = no.type = "button";
  ok.addEventListener("click", () => decide(panel, "/api/approve"));
  no.addEventListener("click", () => decide(panel, "/api/reject"));
  push(panel);
  ok.focus({ preventScroll: true });
}

function renderTurn(turn) {
  renderTrace(turn.trace, turn.seconds);
  if (turn.pending) {
    renderApproval(turn.pending);
    return;
  }
  if (turn.reply) {
    const msg = el("div", "msg bot");
    msg.append(renderMarkdown(turn.reply));
    push(msg);
  }
}

function setBusy(on) {
  busy = on;
  $("input").disabled = on;
  $("send").disabled = on;
  $("talk").classList.toggle("busy", on);
}

async function run(path, data, workingText) {
  setBusy(true);
  const working = renderWorking(workingText);
  try {
    renderTurn(await postJson(path, data));
  } catch (e) {
    renderError(e.message);
  } finally {
    working.remove();
    setBusy(false);
    if (!stream.querySelector(".approval")) { $("input").focus({ preventScroll: true }); }
  }
}

function showExamples(open) {
  $("toggle-examples").setAttribute("aria-expanded", String(open));
  $("example-groups").hidden = !open;
}

function send(text, voice = false) {
  const clean = text.trim();
  if (!clean || busy) { return; }
  if (!stream.querySelector(".msg")) { showExamples(false); }
  renderUser(clean, voice);
  $("input").value = "";
  run("/api/chat", { text: clean }, "Çalışıyor");
}

function decide(panel, path) {
  if (busy) { return; }
  panel.remove();
  run(path, undefined, path.endsWith("approve") ? "Uygulanıyor" : "Vazgeçiliyor");
}

function initChat() {
  $("composer").addEventListener("submit", (e) => {
    e.preventDefault();
    send($("input").value);
  });

  $("reset").addEventListener("click", async () => {
    await postJson("/api/reset");
    stream.replaceChildren();
    const empty = el("div", "empty");
    empty.id = "empty";
    empty.append(el("h1", null, "Ne yapmak istersiniz?"), el("p", null, "Yeni sohbet başladı."));
    stream.append(empty);
    $("input").focus();
  });

  $("toggle-examples").addEventListener("click", () => {
    showExamples($("toggle-examples").getAttribute("aria-expanded") !== "true");
  });

  const groups = $("example-groups");
  for (const [title, items] of EXAMPLES) {
    const group = groups.appendChild(el("div", "group"));
    group.append(el("h3", null, title));
    const chips = group.appendChild(el("div", "chips"));
    for (const text of items) {
      const chip = chips.appendChild(el("button", "chip", text));
      chip.type = "button";
      chip.addEventListener("click", () => send(text));
    }
  }
}

/* ---------- Talk button ---------- */

const talk = $("talk");
const hint = $("talk-hint");
const HINT_IDLE = hint.textContent;
let recorder = null;
let chunks = [];
let startedAt = 0;
let cancelled = false;
let meter = null;

function pickMime() {
  const types = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  return types.find((t) => window.MediaRecorder && MediaRecorder.isTypeSupported(t)) || "";
}

function startMeter(streamIn) {
  const ctx = new AudioContext();
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 512;
  ctx.createMediaStreamSource(streamIn).connect(analyser);
  const data = new Uint8Array(analyser.fftSize);
  let frame = 0;
  const tick = () => {
    analyser.getByteTimeDomainData(data);
    let peak = 0;
    for (const v of data) { peak = Math.max(peak, Math.abs(v - 128) / 128); }
    talk.style.setProperty("--level", Math.min(1, peak * 2.5).toFixed(2));
    const secs = Math.floor((performance.now() - startedAt) / 1000);
    hint.textContent = `Dinleniyor ${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}. Bitirmek için tekrar basın, iptal için Esc.`;
    frame = requestAnimationFrame(tick);
  };
  tick();
  return () => { cancelAnimationFrame(frame); ctx.close(); talk.style.setProperty("--level", 0); };
}

async function startRecording() {
  if (recorder || busy) { return; }
  let input;
  try {
    input = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    renderError("Mikrofona erişilemedi. Tarayıcının mikrofon iznini açın.");
    return;
  }

  chunks = [];
  cancelled = false;
  const mimeType = pickMime();
  recorder = new MediaRecorder(input, mimeType ? { mimeType } : undefined);
  recorder.addEventListener("dataavailable", (e) => chunks.push(e.data));
  recorder.addEventListener("stop", () => finishRecording(input, recorder.mimeType));
  startedAt = performance.now();
  recorder.start();
  meter = startMeter(input);
  talk.setAttribute("aria-pressed", "true");
  hint.classList.add("live");
}

function stopRecording(cancel = false) {
  if (!recorder) { return; }
  cancelled = cancel || performance.now() - startedAt < MIN_RECORDING_MS;
  recorder.stop();
}

async function finishRecording(input, mimeType) {
  input.getTracks().forEach((t) => t.stop());
  meter?.();
  recorder = null;
  talk.setAttribute("aria-pressed", "false");
  hint.classList.remove("live");
  hint.textContent = HINT_IDLE;
  if (cancelled) { return; }

  const ext = mimeType.includes("mp4") ? "m4a" : "webm";
  const form = new FormData();
  form.append("audio", new Blob(chunks, { type: mimeType }), `komut.${ext}`);

  setBusy(true);
  const working = renderWorking("Ses yazıya dökülüyor");
  let text = "";
  try {
    text = (await api("/api/transcribe", { method: "POST", body: form })).text;
  } catch (e) {
    renderError(e.message);
  } finally {
    working.remove();
    setBusy(false);
  }

  if (!text) {
    if (!cancelled) { renderError("Ses anlaşılamadı. Tekrar deneyin."); }
    return;
  }
  send(text, true);
}

function initTalk() {
  talk.addEventListener("click", () => (recorder ? stopRecording() : startRecording()));

  // Hold Space anywhere outside a text field to talk.
  const typing = (e) => e.target.closest("input, textarea, [contenteditable]");
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && recorder) { stopRecording(true); return; }
    if (e.key !== SPACE || e.repeat || typing(e) || $("view-chat").hidden) { return; }
    if (e.target.closest("button")) { return; }
    e.preventDefault();
    startRecording();
  });
  document.addEventListener("keyup", (e) => {
    if (e.key === SPACE && recorder && !typing(e)) { stopRecording(); }
  });
}

/* ---------- Invoice ---------- */

let invoice = null;
let imageBlob = null;
let checkTimer = 0;

function showImage(blob) {
  imageBlob = blob;
  const preview = $("preview");
  preview.src = URL.createObjectURL(blob);
  preview.hidden = false;
  $("camera").hidden = true;
  $("drop-empty").hidden = true;
  $("read").disabled = false;
  $("read-status").textContent = "";
}

function lineRow(line = { description: "", quantity: 1, price_unit: 0 }) {
  const tr = el("tr");
  const cell = (cls, value, type, label) => {
    const td = tr.appendChild(el("td", cls));
    const input = td.appendChild(el("input"));
    input.value = value;
    input.type = type;
    input.setAttribute("aria-label", label);
    if (type === "number") { input.step = "any"; input.min = "0"; }
    input.addEventListener("input", recalc);
    return input;
  };
  cell("", line.description, "text", "Açıklama");
  cell("num", line.quantity, "number", "Miktar");
  cell("num", line.price_unit, "number", "Birim fiyat");
  tr.append(el("td", "num amount"));
  const del = tr.appendChild(el("td")).appendChild(el("button", "del", "×"));
  del.type = "button";
  del.setAttribute("aria-label", "Satırı sil");
  del.addEventListener("click", () => { tr.remove(); recalc(); });
  return tr;
}

function currentLines() {
  return [...$("line-rows").querySelectorAll("tr")].map((tr) => {
    const [d, q, p] = tr.querySelectorAll("input");
    return { description: d.value.trim(), quantity: Number(q.value), price_unit: Number(p.value) };
  }).filter((l) => l.description);
}

function currentInvoice() {
  return {
    vendor: $("vendor").value.trim(),
    invoice_no: $("inv-no").value.trim(),
    date: $("inv-date").value.trim(),
    lines: currentLines(),
    untaxed: invoice.untaxed,
    vat: invoice.vat,
    total: invoice.total,
  };
}

function showCheck(warnings) {
  const ok = warnings.length === 0;
  const box = $("check");
  box.className = `check${ok ? "" : " bad"}`;
  box.querySelector(".led").className = `led ${ok ? "ok" : "alarm"}`;
  box.querySelector("span").textContent = ok
    ? "Kalemler faturadaki toplamlarla tutuyor."
    : `${warnings.join(" ")} Tutarsız fatura işlenmez.`;
  $("post").disabled = !ok;
}

function recalc() {
  for (const tr of $("line-rows").querySelectorAll("tr")) {
    const [, q, p] = tr.querySelectorAll("input");
    tr.querySelector(".amount").textContent = tl(Number(q.value) * Number(p.value));
  }
  clearTimeout(checkTimer);
  checkTimer = setTimeout(async () => {
    try {
      showCheck((await postJson("/api/invoice/check", currentInvoice())).warnings);
    } catch (e) {
      showCheck([e.message]);
    }
  }, CHECK_DEBOUNCE_MS);
}

function fillBill(inv, warnings) {
  invoice = inv;
  $("vendor").value = inv.vendor;
  $("inv-no").value = inv.invoice_no || "";
  $("inv-date").value = inv.date;
  $("line-rows").replaceChildren(...inv.lines.map(lineRow));
  $("t-untaxed").textContent = tl(inv.untaxed);
  $("t-vat").textContent = tl(inv.vat);
  $("t-total").textContent = tl(inv.total);
  $("bill").hidden = false;
  $("post-status").textContent = "";
  for (const tr of $("line-rows").querySelectorAll("tr")) {
    const [, q, p] = tr.querySelectorAll("input");
    tr.querySelector(".amount").textContent = tl(Number(q.value) * Number(p.value));
  }
  showCheck(warnings);
}

let cameraStream = null;

async function openCamera() {
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1920 }, facingMode: "environment" } });
  } catch {
    $("read-status").textContent = "Kameraya erişilemedi. Tarayıcının kamera iznini açın.";
    return;
  }
  const video = $("camera");
  video.srcObject = cameraStream;
  video.hidden = false;
  $("preview").hidden = true;
  $("drop-empty").hidden = true;
  await video.play();
  $("shoot").hidden = false;
  $("cam").hidden = true;
}

function closeCamera() {
  cameraStream?.getTracks().forEach((t) => t.stop());
  cameraStream = null;
  $("shoot").hidden = true;
  $("cam").hidden = false;
}

function shoot() {
  const video = $("camera");
  const canvas = el("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0);
  canvas.toBlob((blob) => { closeCamera(); showImage(blob); }, "image/jpeg", 0.92);
}

function initInvoice() {
  const drop = $("drop");
  const file = $("file");
  drop.addEventListener("click", () => { if (!cameraStream) { file.click(); } });
  drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === SPACE) { e.preventDefault(); file.click(); } });
  file.addEventListener("change", () => { if (file.files[0]) { showImage(file.files[0]); } });
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => {
    e.preventDefault();
    drop.classList.remove("over");
    const f = [...e.dataTransfer.files].find((x) => x.type.startsWith("image/"));
    if (f) { showImage(f); }
  });
  document.addEventListener("paste", (e) => {
    if ($("view-invoice").hidden) { return; }
    const item = [...e.clipboardData.items].find((i) => i.type.startsWith("image/"));
    if (item) { showImage(item.getAsFile()); }
  });

  $("cam").addEventListener("click", openCamera);
  $("shoot").addEventListener("click", shoot);

  $("read").addEventListener("click", async () => {
    const status = $("read-status");
    const form = new FormData();
    form.append("image", imageBlob, "fatura.jpg");
    $("read").disabled = true;
    status.className = "status";
    status.textContent = "Model faturayı okuyor…";
    try {
      const body = await api("/api/invoice/read", { method: "POST", body: form });
      status.textContent = `Model faturayı ${seconds(body.seconds)} içinde okudu. Alanları kontrol edin, gerekirse düzeltin.`;
      fillBill(body.invoice, body.warnings);
    } catch (e) {
      status.className = "status bad";
      status.textContent = e.message;
    } finally {
      $("read").disabled = false;
    }
  });

  $("add-line").addEventListener("click", () => {
    $("line-rows").append(lineRow());
    recalc();
  });

  $("bill").addEventListener("submit", async (e) => {
    e.preventDefault();
    const status = $("post-status");
    $("post").disabled = true;
    status.className = "status";
    status.textContent = "Odoo'ya işleniyor…";
    try {
      const r = await postJson("/api/invoice/post", currentInvoice());
      status.replaceChildren(`Taslak tedarikçi faturası oluşturuldu: ${r.partner}, ${tl(r.total)}. `);
      const link = status.appendChild(el("a", null, "Odoo'da aç"));
      link.href = r.url;
      link.target = "_blank";
      link.rel = "noopener";
    } catch (err) {
      status.className = "status bad";
      status.textContent = err.message;
      $("post").disabled = false;
    }
  });
}

/* ---------- Boot ---------- */

initBrand();
initTabs();
initChat();
initTalk();
initInvoice();
refreshHealth();
setInterval(refreshHealth, HEALTH_INTERVAL_MS);
$("input").focus();
