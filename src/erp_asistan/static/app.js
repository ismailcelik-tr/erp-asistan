"use strict";

const LOW_STOCK = 5;

// Turkish ablative after a numeral follows how it is read: 5'ten (beş), 10'dan (on), 20'den (yirmi).
const ABLATIVE_UNITS = ["", "den", "den", "ten", "ten", "ten", "dan", "den", "den", "dan"];
const ABLATIVE_TENS = ["", "dan", "den", "dan", "tan", "den", "tan", "ten", "den", "dan"];

function ablative(n) {
  if (n % 10) { return ABLATIVE_UNITS[n % 10]; }
  if (n % 100) { return ABLATIVE_TENS[(n % 100) / 10]; }
  return "den";  // yüz, bin
}

const LOW_STOCK_QUESTION = `Stokta ${LOW_STOCK}'${ablative(LOW_STOCK)} az kalan ürünler hangileri?`;

const EXAMPLES = [
  ["Sorgu", [
    LOW_STOCK_QUESTION,
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
const OVERVIEW_INTERVAL_MS = 10000;
const CHECK_DEBOUNCE_MS = 300;
const MIN_RECORDING_MS = 400;
const TRACE_ARGS_MAX = 70;
const COPIED_MS = 1500;
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

let erpLabels = {};

// Updated in place: rebuilding options would close an open dropdown.
function renderErps(erps) {
  const select = $("erp");
  if (select.options.length !== erps.length) {
    select.replaceChildren(...erps.map((e) => {
      const opt = el("option");
      opt.value = e.id;
      return opt;
    }));
  }
  erps.forEach((e, i) => {
    const opt = select.options[i];
    opt.textContent = e.up ? e.label : `${e.label} · kapalı`;
    opt.disabled = !e.up && !e.active;
    if (e.active) { select.value = e.id; }
  });
  const first = Object.keys(erpLabels).length === 0;
  erpLabels = Object.fromEntries(erps.map((e) => [e.id, e.label]));
  // History may have rendered before the labels arrived.
  if (first) { loadHistory(); }
}

async function refreshHealth() {
  try {
    const h = await api("/api/health");
    $("company").textContent = h.company;
    renderErps(h.erps);
    if (h.company !== company) {
      company = h.company;
      const intro = $("intro");
      if (intro) { intro.textContent = introText(); }
    }
    document.querySelectorAll(".leds li").forEach((li) => {
      li.querySelector(".led").className = `led ${h[li.dataset.probe] ? "ok" : "alarm"}`;
    });
  } catch {
    document.querySelectorAll(".leds .led").forEach((led) => { led.className = "led alarm"; });
  }
}

function initBrand() {
  const logo = $("logo");
  const show = (ok) => { logo.hidden = !ok; $("company").hidden = ok; };
  // A cached logo can finish loading before this script runs.
  if (logo.complete && logo.naturalWidth) { show(true); }
  logo.addEventListener("load", () => show(true));
  logo.addEventListener("error", () => show(false));
}

const VIEWS = ["view-chat", "view-invoice"];

function showView(viewId) {
  for (const v of VIEWS) { $(v).hidden = v !== viewId; }
  if (viewId === "view-invoice") {
    $("open-invoice").setAttribute("aria-current", "page");
  } else {
    $("open-invoice").removeAttribute("aria-current");
  }
  markActive();
}

/* ---------- Chat rendering ---------- */

const stream = $("stream");
let busy = false;
let company = "";

const GENITIVE = { a: "ın", ı: "ın", o: "un", u: "un", e: "in", i: "in", ö: "ün", ü: "ün" };

// Turkish genitive follows the last vowel; a final vowel takes a buffer n: Netelsan'ın, Ege'nin.
function genitive(name) {
  const lower = name.toLocaleLowerCase("tr");
  const vowels = [...lower].filter((c) => c in GENITIVE);
  const suffix = GENITIVE[vowels.at(-1)] || "in";
  const buffer = lower.at(-1) in GENITIVE ? "n" : "";
  return `${name}'${buffer}${suffix}`;
}

function introText() {
  const who = company ? `${genitive(company)} ` : "";
  return `Ben ${who}ERP asistanıyım. Ürün, stok ve fiyatları sorgular, satışları özetler ve dönemleri karşılaştırırım. `
    + "Müşteri, teklif, sipariş ve faturaları sizin onayınızla oluştururum. Tedarikçi faturalarını fotoğraftan okuyabilirim.";
}

const OVERVIEW_CARDS = [
  [(o) => String(o.quotations), "teklif onay bekliyor", "Onay bekleyen teklifler hangileri?"],
  [(o) => String(o.low_stock), "ürün kritik stokta", LOW_STOCK_QUESTION],
  [(o) => tl(o.open_total), (o) => `${o.open_invoices} açık fatura`, "Açık faturalar toplam ne kadar?"],
];

const fetchOverview = () => api(`/api/overview?low_stock=${LOW_STOCK}`);
const captionOf = (caption, o) => (typeof caption === "function" ? caption(o) : caption);

async function fillOverview(box) {
  try {
    const o = await fetchOverview();
    for (const [value, caption, question] of OVERVIEW_CARDS) {
      const card = box.appendChild(el("button", "card"));
      card.type = "button";
      card.title = question;
      card.append(el("b", null, value(o)), el("span", null, captionOf(caption, o)));
      card.addEventListener("click", () => draft(question));
    }
  } catch {
    box.remove();
  }
}

// Start screen only: the cards follow changes made directly in the ERP.
async function refreshOverview() {
  if (busy || !document.querySelector("#empty .overview .card")) { return; }
  let o;
  try {
    o = await fetchOverview();
  } catch {
    return;
  }

  const cards = document.querySelectorAll("#empty .overview .card");
  OVERVIEW_CARDS.forEach(([value, caption], i) => {
    const card = cards[i];
    if (!card) { return; }
    const [b, span] = card.children;
    const next = [value(o), captionOf(caption, o)];
    if (b.textContent === next[0] && span.textContent === next[1]) { return; }

    b.textContent = next[0];
    span.textContent = next[1];
    card.classList.remove("changed");
    void card.offsetWidth;  // restart the animation
    card.classList.add("changed");
  });
}

function renderExamples() {
  const box = el("section", "examples");
  box.append(el("h2", null, "Örnek komutlar"));
  for (const [title, items] of EXAMPLES) {
    const group = box.appendChild(el("div", "group"));
    group.append(el("h3", null, title));
    const chips = group.appendChild(el("div", "chips"));
    for (const text of items) {
      const chip = chips.appendChild(el("button", "chip", text));
      chip.type = "button";
      chip.addEventListener("click", () => draft(text));
    }
  }
  return box;
}

function renderEmpty() {
  const empty = el("div", "empty");
  empty.id = "empty";
  empty.append(el("h1", null, "Ne yapmak istersiniz?"));
  empty.appendChild(el("p", "intro", introText())).id = "intro";
  empty.append(el("p", "how", "Konuş düğmesine basıp söyleyin ya da yazın."));

  const overview = empty.appendChild(el("div", "overview"));
  overview.setAttribute("role", "group");
  overview.setAttribute("aria-label", "ERP özeti");
  fillOverview(overview);

  empty.append(renderExamples());
  stream.replaceChildren(empty);
}

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

const DECISION_NOTE = new Map([[true, ["ok", "onaylandı"]], [false, ["alarm", "vazgeçildi"]], [null, ["", "karar verilmedi"]]]);

// decision: undefined = awaiting the user (buttons); true/false/null = replayed from history.
function renderApproval(pending, decision) {
  const panel = el("section", "approval");
  panel.setAttribute("aria-label", "Onay bekleyen işlem");
  const title = panel.appendChild(el("h3"));
  if (decision === undefined) {
    title.append(el("i", "led wait"), `Onay bekliyor: ${pending.label}`);
  } else {
    const [led, note] = DECISION_NOTE.get(decision);
    panel.classList.add("decided");
    title.append(el("i", `led ${led}`), `${pending.label} · ${note}`);
  }

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

  if (decision !== undefined) {
    push(panel);
    return;
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

function renderTurn(turn, decision) {
  renderTrace(turn.trace, turn.seconds);
  if (turn.pending) {
    renderApproval(turn.pending, decision);
    return;
  }
  if (turn.reply) {
    const msg = el("div", "msg bot");
    msg.append(renderMarkdown(turn.reply));
    push(msg);
  }
}

const PLACEHOLDER = $("input").placeholder;

function lockComposer() {
  const readOnly = pastId !== null;
  $("input").disabled = busy || readOnly;
  $("send").disabled = busy || readOnly;
  $("talk").disabled = readOnly;
  $("input").placeholder = readOnly ? "Geçmiş sohbet salt okunur. Yazmak için şu anki sohbete dönün." : PLACEHOLDER;
}

function setBusy(on) {
  busy = on;
  lockComposer();
  $("erp").disabled = on;
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
    if (!stream.querySelector(".approval:not(.decided)")) { $("input").focus({ preventScroll: true }); }
    loadHistory();
  }
}

// Examples fill the input; the user reviews and sends.
function draft(text) {
  const input = $("input");
  input.value = text;
  input.focus();
  input.setSelectionRange(text.length, text.length);
}

function send(text, voice = false) {
  const clean = text.trim();
  if (!clean || busy || pastId) { return; }
  renderUser(clean, voice);
  $("input").value = "";
  run("/api/chat", { text: clean, voice }, "Çalışıyor");
}

function decide(panel, path) {
  if (busy) { return; }
  panel.remove();
  run(path, undefined, path.endsWith("approve") ? "Uygulanıyor" : "Vazgeçiliyor");
}

// Starts an empty live conversation after the server accepted path; false if it refused.
async function freshChat(path, data) {
  if (busy || recorder) { return false; }
  toggleDrawer(false);
  showView("view-chat");
  try {
    await postJson(path, data);
  } catch (e) {
    renderError(e.message);
    return false;
  }
  liveNodes = null;
  pastId = null;
  lockComposer();
  renderEmpty();
  await loadHistory();
  $("input").focus();
  return true;
}

function initChat() {
  $("composer").addEventListener("submit", (e) => {
    e.preventDefault();
    send($("input").value);
  });

  $("new-chat").addEventListener("click", () => { freshChat("/api/reset"); });

  $("erp").addEventListener("change", async (e) => {
    const id = e.target.value;
    company = "";
    if (await freshChat("/api/erp", { id })) {
      $("logo").src = `/api/logo?erp=${id}`;
    }
    refreshHealth();
  });
}

/* ---------- History ---------- */

const historyList = $("history-list");
const dayTime = new Intl.DateTimeFormat("tr-TR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const clockTime = new Intl.DateTimeFormat("tr-TR", { hour: "2-digit", minute: "2-digit" });
let currentId = null;
let pastId = null;     // conversation shown read-only; null = live
let liveNodes = null;  // live conversation, detached while a past one is shown

function when(iso) {
  const d = new Date(iso);
  return d.toDateString() === new Date().toDateString() ? clockTime.format(d) : dayTime.format(d);
}

function markActive() {
  const active = $("view-chat").hidden ? null : pastId ?? currentId;
  historyList.querySelectorAll("button").forEach((b) => {
    if (b.dataset.id === active) {
      b.setAttribute("aria-current", "true");
    } else {
      b.removeAttribute("aria-current");
    }
  });
}

async function loadHistory() {
  try {
    const { current, items } = await api("/api/history");
    currentId = current;
    historyList.replaceChildren();
    $("history-none").hidden = items.length > 0;
    for (const item of items) {
      const btn = historyList.appendChild(el("li")).appendChild(el("button", "history-item"));
      btn.type = "button";
      btn.dataset.id = item.id;
      const stamp = item.id === current ? "Şu anki sohbet" : when(item.started);
      const where = item.erp && Object.keys(erpLabels).length > 1 ? ` · ${erpLabels[item.erp]}` : "";
      btn.append(el("span", "title", item.title || "Sohbet"), el("span", "when", stamp + where));
      btn.addEventListener("click", () => openConversation(item.id));
    }
    markActive();
  } catch {
    // The list is a convenience: chat keeps working without it.
  }
}

function replay(events, live) {
  events.forEach((e, i) => {
    if (e.type === "user") { renderUser(e.text, e.voice); return; }
    if (e.type === "error") { renderError(e.message); return; }
    if (e.type !== "turn") { return; }

    const next = events[i + 1];
    const awaiting = live && !next;
    renderTurn(e, awaiting ? undefined : (next?.type === "decision" ? next.approved : null));
  });
}

function showLive() {
  if (liveNodes) {
    stream.replaceChildren(...liveNodes);
    liveNodes = null;
    stream.scrollTop = stream.scrollHeight;
  }
  pastId = null;
  lockComposer();
  markActive();
}

async function openConversation(id) {
  if (busy || recorder) { return; }
  toggleDrawer(false);
  showView("view-chat");
  if (id === currentId) {
    showLive();
    return;
  }

  let convo;
  try {
    convo = await api(`/api/history/${id}`);
  } catch {
    return;
  }
  if (!liveNodes) { liveNodes = [...stream.childNodes]; }
  pastId = id;

  const banner = el("div", "past");
  banner.append(el("span", null, `Geçmiş sohbet · ${when(convo.started)} · salt okunur`));
  const back = banner.appendChild(el("button", "link", "Şu anki sohbete dön"));
  back.type = "button";
  back.addEventListener("click", showLive);

  stream.replaceChildren(banner);
  replay(convo.events, false);
  stream.scrollTop = 0;
  lockComposer();
  markActive();
}

const NARROW = window.matchMedia("(max-width: 900px)");
const PANEL_COLLAPSED_KEY = "panel-collapsed";

// Narrow screens: the panel is an overlay drawer. Wide screens: a column that can be collapsed.
function toggleDrawer(open) {
  if (!NARROW.matches) { return; }
  document.body.classList.toggle("panel-open", open);
  $("toggle-panel").setAttribute("aria-expanded", String(open));
}

function togglePanel() {
  if (NARROW.matches) {
    toggleDrawer(!document.body.classList.contains("panel-open"));
    return;
  }
  const collapsed = document.body.classList.toggle("panel-collapsed");
  localStorage.setItem(PANEL_COLLAPSED_KEY, collapsed ? "1" : "");
  $("toggle-panel").setAttribute("aria-expanded", String(!collapsed));
}

async function initHistory() {
  const collapsed = Boolean(localStorage.getItem(PANEL_COLLAPSED_KEY));
  document.body.classList.toggle("panel-collapsed", collapsed);
  $("toggle-panel").setAttribute("aria-expanded", String(!NARROW.matches && !collapsed));
  $("toggle-panel").addEventListener("click", togglePanel);
  NARROW.addEventListener("change", () => {
    document.body.classList.remove("panel-open");
    const open = !NARROW.matches && !document.body.classList.contains("panel-collapsed");
    $("toggle-panel").setAttribute("aria-expanded", String(open));
  });
  $("open-invoice").addEventListener("click", () => {
    toggleDrawer(false);
    showView("view-invoice");
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { toggleDrawer(false); }
  });
  // The narrow-layout backdrop is body::after, so its clicks target body.
  document.body.addEventListener("click", (e) => {
    if (e.target === document.body) { toggleDrawer(false); }
  });

  renderEmpty();
  await loadHistory();

  // After a page reload, show the conversation the server still holds.
  try {
    const convo = await api(`/api/history/${currentId}`);
    stream.replaceChildren();
    replay(convo.events, true);
  } catch {
    // No current conversation yet: keep the empty state.
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
  if (recorder || busy || pastId) { return; }
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
    if (e.key !== SPACE || e.repeat || typing(e) || $("view-chat").hidden || $("help").open) { return; }
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
    status.textContent = "ERP'ye işleniyor…";
    try {
      const r = await postJson("/api/invoice/post", currentInvoice());
      status.replaceChildren(`Taslak tedarikçi faturası oluşturuldu: ${r.partner}, ${tl(r.total)}. `);
      const link = status.appendChild(el("a", null, "ERP'de aç"));
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

/* ---------- Help ---------- */

async function copy(btn, text) {
  try {
    await navigator.clipboard.writeText(text);
    btn.textContent = "Kopyalandı";
  } catch {
    btn.textContent = "Kopyalanamadı";
  }
  setTimeout(() => { btn.textContent = "Kopyala"; }, COPIED_MS);
}

function initHelp() {
  const dialog = $("help");
  $("open-help").addEventListener("click", () => {
    toggleDrawer(false);
    dialog.showModal();
  });
  $("close-help").addEventListener("click", () => dialog.close());
  // Backdrop clicks target the dialog element itself; its content sits in child elements.
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog) { dialog.close(); }
  });

  const box = $("help-examples");
  for (const [title, items] of EXAMPLES) {
    box.append(el("h4", null, title));
    const list = box.appendChild(el("ul", "copy-list"));
    for (const text of items) {
      const li = list.appendChild(el("li"));
      li.append(el("span", null, text));
      const btn = li.appendChild(el("button", "copy", "Kopyala"));
      btn.type = "button";
      btn.setAttribute("aria-label", `Kopyala: ${text}`);
      btn.addEventListener("click", () => copy(btn, text));
    }
  }
}

/* ---------- Boot ---------- */

initBrand();
initChat();
initHistory();
initHelp();
initTalk();
initInvoice();
refreshHealth();
setInterval(refreshHealth, HEALTH_INTERVAL_MS);
setInterval(refreshOverview, OVERVIEW_INTERVAL_MS);
$("input").focus();
