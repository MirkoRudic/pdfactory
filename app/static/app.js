// PDFabrika - UI. Plain JS, no build step.
// Coordinates of objects are display points of the page (rotation applied, origin top-left, 1 = 1 pt).
"use strict";
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const PT = 96 / 72;                       // px per pt at 100%
const SRC_COLORS = ["#e0302b", "#4f8fd9", "#4caf50", "#c062d9", "#e5734d", "#3fb8b0"];
const COLORS = ["#000000", "#ffffff", "#1f3a8a", "#c62f34", "#2e7d32", "#d9a441"];
const MARKS = ["#ffd600", "#7ee07e", "#7fd3ff", "#ff9bd2"];

const S = {
  docs: [], cur: null, mode: "read", zoom: 1, fit: "auto", tool: "select", shapeKind: "rect",
  sel: null, fonts: [], defFont: "Arial", pid: null, hits: [], hit: -1, cropMode: false,
  def: {
    text: { font: null, size: 12, color: "#000000", bold: false, italic: false, underline: false, strike: false, align: "left", lineHeight: 1.2 },
    shape: { stroke: "#c62f34", fill: "", width: 2, opacity: 1 },
    mark: { color: "#ffd600", opacity: 0.4 },
  },
};
const textCache = new Map();   // "src:page" -> {words, spans}
const formCache = new Map();
let uidN = 0;
const newUid = () => "u" + Date.now().toString(36) + (uidN++).toString(36);
const D = () => S.docs.find((d) => d.key === S.cur) || null;

// ---------- formatting (T2) ----------
function formatNumber(n, dec = 0) {
  const s = Math.abs(n).toFixed(dec).split(".");
  s[0] = s[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return (n < 0 ? "-" : "") + s.join(",");
}
function formatPercent(p) { return Math.round(p * 100) + "%"; }
function formatMm(pt) { return formatNumber(pt / 72 * 25.4, 0) + " mm"; }
function formatDate(iso) {
  const d = new Date(iso); const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()}`;
}

// ---------- api ----------
async function api(path, opt = {}) {
  const o = { method: opt.body !== undefined || opt.form ? "POST" : (opt.method || "GET"), headers: {} };
  if (opt.form) o.body = opt.form;
  else if (opt.body !== undefined) { o.body = JSON.stringify(opt.body); o.headers["Content-Type"] = "application/json"; }
  let r;
  try { r = await fetch(path, o); } catch (e) { throw new Error("PDFabrika ne odgovara. Pokreni je ponovo."); }
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || "Nešto nije u redu.");
  return j;
}
async function safe(fn) {
  try { return await fn(); } catch (e) { await vd.message(e.message); return null; }
}
function toast(text, ms = 3000) {
  const t = document.createElement("div");
  t.className = "toast"; t.textContent = text;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), ms);
}
function icon(id, cls = "icon") { return `<svg class="${cls}"><use href="#i-${id}"/></svg>`; }
function esc(s) { return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

// ---------- documents (workspaces) ----------
function itemsFromInfo(info) {
  return info.pages.map((p, i) => ({ uid: newUid(), src: info.id, page: i, rot: 0, w: p.w, h: p.h }));
}
function addDoc(info) {
  const d = {
    key: newUid(), name: info.name, path: info.path, items: itemsFromInfo(info), objects: {}, forms: {},
    dirty: false, hist: [], fut: [], osel: new Set(), srcInfo: { [info.id]: info }, scroll: 0,
  };
  S.docs.push(d);
  S.fit = "auto";              // a newly opened file fits its first page
  switchDoc(d.key);
  autoOcr();
  return d;
}
function itemDims(it) { return it.rot % 180 ? [it.h, it.w] : [it.w, it.h]; }
function snapshot(d) { return JSON.stringify({ items: d.items, objects: d.objects, forms: d.forms }); }
function commit(d = D()) {
  if (!d) return;
  d.hist.push(snapshot(d)); if (d.hist.length > 100) d.hist.shift();
  d.fut = []; d.dirty = true; persist(); renderChrome();
}
function undo(redo = false) {
  const d = D(); if (!d) return;
  const from = redo ? d.fut : d.hist, to = redo ? d.hist : d.fut;
  if (!from.length) return;
  to.push(snapshot(d));
  const s = JSON.parse(from.pop());
  d.items = s.items; d.objects = s.objects; d.forms = s.forms;
  d.dirty = d.hist.length > 0;      // back at the first step = as it was opened or last saved
  S.sel = null; renderAll(); persist();
}
async function openPaths(paths) {
  const r = await safe(() => api("/api/open", { body: { paths } }));
  if (r) r.docs.forEach(addDoc);
}
async function pickOpen() {
  const r = await safe(() => api("/api/pick-open", { body: {} }));
  if (r) r.docs.forEach(addDoc);
}
async function uploadFiles(files) {
  for (const f of files) {
    const fd = new FormData(); fd.append("file", f);
    const info = await safe(() => api("/api/upload", { form: fd }));
    if (info) addDoc(info);
  }
}
async function closeDoc(key) {
  const d = S.docs.find((x) => x.key === key); if (!d) return;
  if (d.dirty && !(await vd.confirm(`„${d.name}“ ima nesačuvane izmene. Zatvoriti bez čuvanja?`, { ok: "Zatvori", danger: true }))) return;
  const used = new Set(S.docs.filter((x) => x !== d).flatMap((x) => x.items.map((i) => i.src)));
  for (const s of new Set(d.items.map((i) => i.src))) if (!used.has(s)) api("/api/close/" + s, { body: {} }).catch(() => {});
  S.docs = S.docs.filter((x) => x !== d);
  S.cur = S.docs.length ? S.docs[S.docs.length - 1].key : null;
  S.sel = null; renderAll(); persist();
}
function switchDoc(key) {
  const old = D(); if (old) old.scroll = $("#pages").scrollTop;
  S.cur = key; S.sel = null; S.hits = []; S.hit = -1; $("#q").value = ""; $("#qn").textContent = "";
  renderAll(); persist();
  const d = D(); if (d) requestAnimationFrame(() => {
    $("#pages").scrollTop = d.scroll || 0;
    const pg = $(`.page[data-i="${d.curPage || 0}"]`); if (pg) centerX(pg);
  });
}

// ---------- persistence (window closed by accident: the server keeps the files) ----------
function persist() {
  try {
    localStorage.setItem("pdfabrika.ws", JSON.stringify({
      pid: S.pid, cur: S.cur,
      docs: S.docs.map((d) => ({ key: d.key, name: d.name, path: d.path, items: d.items, objects: d.objects, forms: d.forms, dirty: d.dirty, srcInfo: d.srcInfo })),
    }));
  } catch (e) { /* storage unavailable: nothing to restore later */ }
}
async function restore() {
  let ws; try { ws = JSON.parse(localStorage.getItem("pdfabrika.ws") || "null"); } catch (e) { ws = null; }
  if (!ws || !ws.docs || !ws.docs.length) return;
  if (ws.pid === S.pid) {
    for (const d of ws.docs) S.docs.push({ ...d, hist: [], fut: [], osel: new Set(), scroll: 0 });
    S.cur = ws.cur;
    return;
  }
  // server restarted: reopen files from disk; unsaved edits are carried over onto the reopened file
  for (const d of ws.docs) {
    if (!d.path) continue;
    try {
      const r = await api("/api/open", { body: { paths: [d.path] } });
      const info = r.docs[0];
      const srcs = new Set(d.items.map((i) => i.src));
      if (srcs.size === 1 && d.dirty) {
        const nd = { ...d, hist: [], fut: [], osel: new Set(), scroll: 0, srcInfo: { [info.id]: info } };
        nd.items = d.items.filter((i) => i.page < info.pages.length).map((i) => ({ ...i, src: info.id }));
        S.docs.push(nd);
      } else {
        S.docs.push({ key: newUid(), name: info.name, path: info.path, items: itemsFromInfo(info), objects: {}, forms: {},
          dirty: false, hist: [], fut: [], osel: new Set(), srcInfo: { [info.id]: info }, scroll: 0 });
      }
    } catch (e) { /* file moved or deleted */ }
  }
  S.cur = S.docs.length ? S.docs[0].key : null;
}

// ---------- chrome: header, tabs, footer ----------
function renderChrome() {
  const d = D();
  document.title = d ? `PDFabrika - ${d.dirty ? "● " : ""}${d.name}` : "PDFabrika";   // name shown in the window title bar
  $$(".mode").forEach((b) => { b.classList.toggle("on", !!d && b.dataset.mode === S.mode); b.disabled = !d; });
  ["#bSave", "#bSaveMenu", "#bPrint"].forEach((s) => ($(s).disabled = !d));
  $("#bUndo").disabled = !d || !d.hist.length; $("#bRedo").disabled = !d || !d.fut.length;   // undo for every mode
  const tabs = $("#tabs");
  tabs.hidden = S.docs.length < 2;
  tabs.innerHTML = "";
  for (const x of S.docs) {
    const b = document.createElement("button");
    b.className = "tab" + (x.key === S.cur ? " on" : "");
    b.innerHTML = (x.dirty ? '<i class="dot"></i>' : "") + `<span>${esc(x.name)}</span><button class="x" aria-label="Zatvori">${icon("x")}</button>`;
    b.onclick = (e) => { if (e.target.closest(".x")) closeDoc(x.key); else if (x.key !== S.cur) switchDoc(x.key); };
    tabs.appendChild(b);
  }
  renderFooter();
}
function renderFooter() {
  const d = D();
  if (!d) { $("#fLeft").textContent = ""; $("#fMid").textContent = ""; return; }
  if (S.mode === "pages") $("#fLeft").textContent = `${formatNumber(d.items.length)} strana · izabrano ${formatNumber(d.osel.size)}`;
  else $("#fLeft").textContent = `Strana ${formatNumber((d.curPage || 0) + 1)} od ${formatNumber(d.items.length)}`;
  $("#zVal").textContent = formatPercent(S.zoom);
  $$(".bottom .fright button").forEach((b) => (b.disabled = S.mode === "pages"));
}
function setMode(m) {
  if (!D()) return;
  S.mode = m; S.sel = null; S.cropMode = false;
  if (m === "edit" && S.hits.length) { S.hits = []; S.hit = -1; $("#q").value = ""; $("#qn").textContent = ""; }
  if (m !== "edit") S.tool = "select";
  renderAll();
  const d = D();
  if (m !== "pages") requestAnimationFrame(() => scrollToPage(d.curPage || 0));   // UI2: same page in every mode
}
function renderAll() {
  const d = D();
  document.body.className = `mode-${S.mode} tool-${S.tool}`;
  $("#start").hidden = !!d;
  $("#viewer").hidden = !d || S.mode === "pages";
  $("#organizer").hidden = !d || S.mode !== "pages";
  renderChrome();
  if (!d) { renderStart(); return; }
  if (S.mode === "pages") renderOrganizer();
  else renderViewer();
}

// ---------- start screen ----------
async function renderStart() {
  const r = await api("/api/recent").catch(() => ({ recent: [] }));
  const box = $("#recent");
  box.innerHTML = r.recent.length ? "<h3>Nedavno</h3>" : "";
  for (const x of r.recent.slice(0, 8)) {
    const b = document.createElement("button");
    b.innerHTML = `<span>${esc(x.name)}</span><span class="rp">${esc(x.path)}</span>`;
    b.onclick = () => openPaths([x.path]);
    box.appendChild(b);
  }
}

// ---------- viewer (read + edit) ----------
let io = null;
function scale() { return S.zoom * PT; }
function fitZoom() {
  const d = D(); if (!d) return 1;
  const avail = $("#pages").clientWidth - 48 - 12;
  const it = d.items[d.curPage || 0] || d.items[0];
  const w = itemDims(it)[0];                        // the page being read (first page on open); not the widest page
  const width = avail / (w * PT);
  // "auto" (on open): page width, but never above 100% - an A4 page at 161% on a wide screen is too big
  return Math.max(0.25, Math.min(S.fit === "width" ? 2 : 1, width));
}
function renderViewer() {
  const d = D();
  renderThumbs(); renderPanel(); renderVbar();
  if (S.fit) S.zoom = fitZoom();
  const host = $("#pages");
  host.innerHTML = "";
  const inner = document.createElement("div");
  inner.className = "pages-in";
  host.appendChild(inner);
  if (io) io.disconnect();
  io = new IntersectionObserver((ents) => ents.forEach((e) => { if (e.isIntersecting) fillPage(e.target); }), { root: host, rootMargin: "600px 0px" });
  d.items.forEach((it, i) => {
    const [w, h] = itemDims(it);
    const pg = document.createElement("div");
    pg.className = "page"; pg.dataset.i = i; pg.dataset.uid = it.uid;
    pg.style.width = w * scale() + "px"; pg.style.height = h * scale() + "px";
    inner.appendChild(pg);
    io.observe(pg);
  });
  renderFooter();
}
function pageImgUrl(it, px) { return `/api/src/${it.src}/page/${it.page}.png?w=${Math.round(px)}&rot=${it.rot}`; }
function fillPage(pg) {
  const d = D(); const it = d.items[+pg.dataset.i]; if (!it) return;
  const [w] = itemDims(it);
  const px = Math.min(3600, w * scale() * (window.devicePixelRatio || 1));
  const want = pageImgUrl(it, Math.ceil(px / 100) * 100);
  let img = $("img.pg", pg);
  if (!img) { img = document.createElement("img"); img.className = "pg"; img.alt = ""; pg.appendChild(img); }
  if (img.dataset.src !== want) { img.dataset.src = want; img.src = want; }
  if (!pg.dataset.filled) {
    pg.dataset.filled = "1";
    buildOverlay(pg);
    if (S.mode === "read") buildTextLayer(pg, it);
    drawHits(pg);
  }
}
function relayout() {   // zoom changed: resize pages, keep the reading position (UI2)
  const d = D(); const host = $("#pages");
  const ratio = host.scrollTop / Math.max(1, host.scrollHeight);
  $$(".page", host).forEach((pg) => {
    const it = d.items[+pg.dataset.i]; const [w, h] = itemDims(it);
    pg.style.width = w * scale() + "px"; pg.style.height = h * scale() + "px";
    $$(".tl,.ol,.hit,.fld", pg).forEach((x) => x.remove());
    delete pg.dataset.filled;
  });
  host.scrollTop = ratio * host.scrollHeight;
  const cur = $(`.page[data-i="${d.curPage || 0}"]`, host); if (cur) centerX(cur);
  clearTimeout(relayout.t);
  relayout.t = setTimeout(() => $$(".page", host).forEach((pg) => { const r = pg.getBoundingClientRect(); const hr = host.getBoundingClientRect();
    if (r.bottom > hr.top - 600 && r.top < hr.bottom + 600) fillPage(pg); }), 120);
  renderFooter();
}
function setZoom(z, fit = false) {   // fit: false | "auto" | "width"
  S.fit = fit; S.zoom = Math.max(0.25, Math.min(4, z));
  if (fit) S.zoom = fitZoom();
  relayout();
}
function rotRect(r, W, H, rot) {   // r=[x0,y0,x1,y1] on a page W x H, rotated clockwise by rot
  const pts = [[r[0], r[1]], [r[2], r[3]]].map(([x, y]) =>
    rot === 90 ? [H - y, x] : rot === 180 ? [W - x, H - y] : rot === 270 ? [y, W - x] : [x, y]);
  return [Math.min(pts[0][0], pts[1][0]), Math.min(pts[0][1], pts[1][1]), Math.max(pts[0][0], pts[1][0]), Math.max(pts[0][1], pts[1][1])];
}
async function getText(it) {
  const k = it.src + ":" + it.page;
  if (!textCache.has(k)) textCache.set(k, api(`/api/src/${it.src}/page/${it.page}/text`).catch(() => ({ words: [], spans: [] })));
  return textCache.get(k);
}
const measureCtx = document.createElement("canvas").getContext("2d");
async function buildTextLayer(pg, it) {
  if (it.rot) return;   // pages rotated in "Strane" get their text layer after saving
  const t = await getText(it);
  if (!pg.isConnected) return;
  const sc = scale();
  const tl = document.createElement("div"); tl.className = "tl";
  const frag = document.createDocumentFragment();
  for (const [x0, y0, x1, y1, txt] of t.words) {
    const s = document.createElement("span");
    const h = (y1 - y0) * sc, w = (x1 - x0) * sc;
    const fs = h * 0.88;
    s.textContent = txt + " ";
    measureCtx.font = `${fs}px sans-serif`;
    const nat = measureCtx.measureText(txt).width || 1;
    s.style.cssText = `left:${x0 * sc}px;top:${y0 * sc + h * 0.06}px;font-size:${fs}px;transform:scaleX(${w / nat})`;
    frag.appendChild(s);
  }
  tl.appendChild(frag); pg.appendChild(tl);
}

// thumbnails
let tio = null;
function renderThumbs() {
  const d = D(); const box = $("#thumbs");
  box.innerHTML = "";
  if (tio) tio.disconnect();
  tio = new IntersectionObserver((ents) => ents.forEach((e) => {
    if (e.isIntersecting) { const im = $("img", e.target); if (!im.src) im.src = im.dataset.src; }
  }), { root: box, rootMargin: "400px 0px" });
  d.items.forEach((it, i) => {
    const [w, h] = itemDims(it);
    const k = 112 / Math.max(w, h * 0.75);
    const b = document.createElement("button");
    b.className = "thumb" + (i === (d.curPage || 0) ? " on" : "");
    b.innerHTML = `<img class="ti" width="${Math.round(w * k)}" height="${Math.round(h * k)}" alt=""><span>${i + 1}</span>`;
    $("img", b).dataset.src = pageImgUrl(it, 240);
    b.onclick = () => scrollToPage(i);
    box.appendChild(b); tio.observe(b);
  });
}
function scrollToPage(i, offsetPt = 0) {
  const pg = $(`.page[data-i="${i}"]`); if (!pg) return;
  const host = $("#pages");
  host.scrollTop = pg.offsetTop - 24 + offsetPt * scale();
  centerX(pg);
}
function centerX(pg) {     // wider pages make the strip wider than the window: keep the page being read in the middle
  const host = $("#pages");
  const p = pg.getBoundingClientRect(), h = host.getBoundingClientRect();   // offsetLeft counted from the window, not the strip
  host.scrollLeft = Math.max(0, host.scrollLeft + (p.left + p.width / 2) - (h.left + host.clientWidth / 2));
}
function trackPage() {
  const d = D(); if (!d || S.mode === "pages") return;
  const host = $("#pages"); const mid = host.scrollTop + host.clientHeight * 0.35;
  let cur = 0;
  for (const pg of $$(".page", host)) { if (pg.offsetTop <= mid) cur = +pg.dataset.i; else break; }
  if (cur !== d.curPage) {
    d.curPage = cur; renderFooter();
    $$(".thumb").forEach((t, i) => t.classList.toggle("on", i === cur));
    const t = $$(".thumb")[cur]; if (t) { const r = t.getBoundingClientRect(), br = $("#thumbs").getBoundingClientRect();
      if (r.top < br.top || r.bottom > br.bottom) $("#thumbs").scrollTop += r.top - br.top - 40; }
  }
}

// top bar of the viewer (left: undo/OCR, right: context)
function renderVbar() {
  const d = D(); const L = $("#vbarL"), R = $("#vbarR");
  L.innerHTML = ""; R.innerHTML = "";
}

// ---------- search ----------
async function doSearch() {
  const d = D(); const q = $("#q").value.trim();
  S.hits = []; S.hit = -1;
  if (q) {
    const bySrc = {};
    for (const s of new Set(d.items.map((i) => i.src))) bySrc[s] = (await api(`/api/src/${s}/search?q=${encodeURIComponent(q)}`).catch(() => ({ hits: [] }))).hits;
    d.items.forEach((it, i) => {
      const info = d.srcInfo[it.src]; const p = info && info.pages[it.page];
      for (const h of bySrc[it.src] || []) if (h.page === it.page) S.hits.push({ i, rect: it.rot && p ? rotRect(h.rect, p.w, p.h, it.rot) : h.rect });
    });
  }
  $("#qn").textContent = q ? (S.hits.length ? `${S.hit + 1}/${formatNumber(S.hits.length)}` : "0") : "";
  $$(".page").forEach(drawHits);
  if (S.hits.length) gotoHit(0);
}
function gotoHit(n) {
  if (!S.hits.length) return;
  S.hit = (n + S.hits.length) % S.hits.length;
  const h = S.hits[S.hit];
  $("#qn").textContent = `${S.hit + 1}/${formatNumber(S.hits.length)}`;
  scrollToPage(h.i, Math.max(0, h.rect[1] - 80));
  $$(".page").forEach(drawHits);
}
function drawHits(pg) {
  $$(".hit", pg).forEach((x) => x.remove());
  const sc = scale(); const i = +pg.dataset.i;
  S.hits.forEach((h, n) => {
    if (h.i !== i) return;
    const e = document.createElement("div");
    e.className = "hit" + (n === S.hit ? " cur" : "");
    e.style.cssText = `left:${h.rect[0] * sc}px;top:${h.rect[1] * sc}px;width:${(h.rect[2] - h.rect[0]) * sc}px;height:${(h.rect[3] - h.rect[1]) * sc}px`;
    pg.appendChild(e);
  });
}

// ---------- OCR ----------
// pages without text (scans) get recognized in the background, no button and no questions
const ocrStarted = new Set();
async function autoOcr() {
  if (autoOcr.busy) return;
  autoOcr.busy = true;
  try {
    for (;;) {
      const want = (x, s) => x.srcInfo[s] && x.srcInfo[s].needsOcr && !ocrStarted.has(s);
      const d = S.docs.find((x) => x.items.some((i) => want(x, i.src)));
      if (!d) break;
      const src = d.items.map((i) => i.src).find((s) => want(d, s));
      ocrStarted.add(src);
      const r = await api("/api/ocr/" + src, { body: {} }).catch(() => null);
      if (!r) continue;
      for (;;) {
        await new Promise((res) => setTimeout(res, 800));
        const st = await api(`/api/ocr/${src}/status`).catch(() => ({ state: "greška" }));
        $("#fMid").textContent = st.state === "radi" ? `Prepoznavanje teksta ${formatPercent(st.total ? st.done / st.total : 0)}` : "";
        if (st.state !== "radi") break;
      }
      const info = await api("/api/src/" + src).catch(() => null);
      for (const x of S.docs) if (info && x.srcInfo[src]) x.srcInfo[src] = info;
      for (const k of [...textCache.keys()]) if (k.startsWith(src + ":")) textCache.delete(k);
      const cur = D();
      if (cur && S.mode === "read") $$(".page").forEach((pg) => {     // fresh text layer, page stays where it is
        const it = cur.items[+pg.dataset.i];
        if (it && it.src === src && pg.dataset.filled) { $$(".tl", pg).forEach((x) => x.remove()); buildTextLayer(pg, it); }
      });
      persist();
    }
  } finally { autoOcr.busy = false; $("#fMid").textContent = ""; }
}
function showProgress(text) {
  const ov = document.createElement("div"); ov.className = "vd-overlay";
  ov.innerHTML = `<div class="vd-card"><p class="vd-text"></p><div class="prog"><i></i></div></div>`;
  $(".vd-text", ov).textContent = text;
  document.body.appendChild(ov);
  return { set: (f) => ($("i", ov).style.width = Math.round(f * 100) + "%"), close: () => ov.remove() };
}

// ---------- edit: panel ----------
const TOOLS = [
  ["select", "pointer", "Izaberi i pomeri"], ["text", "text", "Dodaj tekst"], ["fix", "cursor", "Ispravi tekst"],
  ["mark", "mark", "Istakni"], ["shape", "shapes", "Oblik"], ["image", "photo", "Slika"], ["form", "form", "Popuni formular"],
];
function setTool(t) {
  if (t === "image") { $("#fileImg").click(); return; }
  S.tool = t; S.sel = null; S.cropMode = false;
  document.body.className = `mode-${S.mode} tool-${S.tool}`;
  renderPanel(); refreshOverlays();
}
function hasForms(d) { return d.items.some((it) => { const p = d.srcInfo[it.src] && d.srcInfo[it.src].pages[it.page]; return p && p.forms; }); }
function renderPanel() {
  const d = D(); const P = $("#panel");
  P.hidden = S.mode !== "edit";
  if (P.hidden) return;
  P.innerHTML = "";
  for (const [k, ic, label] of TOOLS) {
    if (k === "form" && !hasForms(d)) continue;
    const b = document.createElement("button");
    b.className = "tool" + (S.tool === k ? " on" : "");
    b.innerHTML = icon(ic) + label;
    b.onclick = () => setTool(k);
    P.appendChild(b);
  }
  const o = selObj();
  const kind = o ? o.type : S.tool;
  const box = document.createElement("div"); box.className = "props";
  if (kind === "text" || kind === "fix") propsText(box, o || S.def.text);
  else if (kind === "shape") propsShape(box, o || S.def.shape, !o);
  else if (kind === "mark") propsMark(box, o || S.def.mark);
  else if (kind === "image" && o) propsImage(box, o);
  if (box.childElementCount) { P.appendChild(sep()); P.appendChild(box); }
  if (o) {
    P.appendChild(sep());
    const r = row(2);
    r.appendChild(btn(icon("copy") + "Dupliraj", () => dupObj(), "txt"));
    r.appendChild(btn(icon("trash") + "Obriši", () => delObj(), "txt"));
    P.appendChild(r);
  }
}
const sep = () => Object.assign(document.createElement("div"), { className: "sep" });
function row(n) { const r = document.createElement("div"); r.className = "row"; r.style.setProperty("--n", n); return r; }
function btn(html, fn, cls = "", label) {
  const b = document.createElement("button"); b.innerHTML = html; if (cls) b.className = cls;
  if (label) b.setAttribute("aria-label", label);
  b.onclick = fn; return b;
}
function lbl(text, right = "") { const l = document.createElement("div"); l.className = "lbl"; l.innerHTML = `<span>${text}</span><span>${right}</span>`; return l; }

// change a property of the selected object (and remember it as the default for new ones)
function setProp(target, k, v, defKey) {
  const o = selObj();
  if (o) { commit(); o[k] = v; if (defKey && k in S.def[defKey]) S.def[defKey][k] = v; refreshObj(o); }
  else target[k] = v;
  renderPanel();
}
function propsText(box, t) {
  box.appendChild(fontButton(t.font || S.defFont, (f) => setProp(t, "font", f, "text")));
  const r = row(2);
  r.appendChild(stepper(t.size, 4, 200, 1, (v) => setProp(t, "size", v, "text"), " pt", t.size % 1 ? 1 : 0));
  r.appendChild(stepper(t.lineHeight, 0.8, 3, 0.1, (v) => setProp(t, "lineHeight", Math.round(v * 10) / 10, "text"), "", 1));
  box.appendChild(r);
  const r2 = row(4);
  for (const [k, txt, st] of [["bold", "B", "font-weight:700"], ["italic", "I", "font-style:italic;font-family:Georgia,serif"],
    ["underline", "U", "text-decoration:underline"], ["strike", "S", "text-decoration:line-through"]]) {
    const b = btn(`<span style="${st}">${txt}</span>`, () => setProp(t, k, !t[k], "text"), t[k] ? "on" : "",
      { bold: "Podebljano", italic: "Kurziv", underline: "Podvučeno", strike: "Precrtano" }[k]);
    r2.appendChild(b);
  }
  for (const [a, ic, lab] of [["left", "al-left", "Levo"], ["center", "al-center", "Centar"], ["right", "al-right", "Desno"], ["justify", "al-just", "Poravnato"]])
    r2.appendChild(btn(icon(ic), () => setProp(t, "align", a, "text"), t.align === a ? "on" : "", lab));
  box.appendChild(r2);
  box.appendChild(colorPick(COLORS, t.color, (c) => setProp(t, "color", c, "text")));
}
function propsShape(box, s, chooseKind) {
  if (chooseKind || selObj()) {
    const r = row(4); const cur = selObj() ? selObj().kind : S.shapeKind;
    for (const [k, ic, lab] of [["rect", "square", "Pravougaonik"], ["ellipse", "circle", "Elipsa"], ["line", "line", "Linija"], ["arrow", "arrow", "Strelica"]])
      r.appendChild(btn(icon(ic), () => { if (selObj()) setProp(s, "kind", k); else { S.shapeKind = k; renderPanel(); } }, cur === k ? "on" : "", lab));
    box.appendChild(r);
  }
  box.appendChild(lbl("Linija"));
  box.appendChild(colorPick(COLORS, s.stroke, (c) => setProp(s, "stroke", c, "shape"), true));
  const k = selObj() ? selObj().kind : S.shapeKind;
  if (k === "rect" || k === "ellipse") {
    box.appendChild(lbl("Popuna"));
    box.appendChild(colorPick(COLORS, s.fill, (c) => setProp(s, "fill", c, "shape"), true));
  }
  box.appendChild(lbl("Debljina"));
  box.appendChild(stepper(s.width, 0.5, 40, 0.5, (v) => setProp(s, "width", v, "shape"), " pt", 1));
  box.appendChild(lbl("Providnost", formatPercent(s.opacity)));
  box.appendChild(slider(s.opacity, 0.05, 1, (v) => setProp(s, "opacity", v, "shape")));
}
function propsMark(box, m) {
  box.appendChild(lbl("Boja"));
  box.appendChild(colorPick(MARKS, m.color, (c) => setProp(m, "color", c, "mark")));
}
function propsImage(box, o) {
  const r = row(2);
  const keep = () => o.keep !== false;
  r.appendChild(numField("Širina", o.w / 72 * 25.4, (mm) => { commit(); const nw = mm / 25.4 * 72; if (keep()) o.h *= nw / o.w; o.w = nw; refreshObj(o); renderPanel(); }));
  r.appendChild(numField("Visina", o.h / 72 * 25.4, (mm) => { commit(); const nh = mm / 25.4 * 72; if (keep()) o.w *= nh / o.h; o.h = nh; refreshObj(o); renderPanel(); }));
  box.appendChild(r);
  box.appendChild(check("Zadrži proporcije", keep(), (v) => { o.keep = v; persist(); }));
  const r2 = row(5);
  r2.appendChild(btn(icon("crop"), () => { S.cropMode = !S.cropMode; refreshObj(o); renderPanel(); }, S.cropMode ? "on" : "", "Iseci"));
  r2.appendChild(btn(icon("rot-r"), () => setProp(o, "angle", ((o.angle || 0) + 90) % 360), "", "Okreni za 90°"));
  r2.appendChild(btn(icon("flip-h"), () => setProp(o, "flipH", !o.flipH), o.flipH ? "on" : "", "Preslikaj levo-desno"));
  r2.appendChild(btn(icon("flip-v"), () => setProp(o, "flipV", !o.flipV), o.flipV ? "on" : "", "Preslikaj gore-dole"));
  r2.appendChild(btn(icon("layers"), () => setProp(o, "behind", !o.behind), o.behind ? "on" : "", "Iza teksta"));
  box.appendChild(r2);
  box.appendChild(lbl("Ugao", formatNumber(Math.round(o.angle || 0)) + "°"));
  box.appendChild(slider((o.angle || 0) / 360, 0, 1, (v) => setProp(o, "angle", Math.round(v * 360) % 360), true));
  box.appendChild(lbl("Providnost", formatPercent(o.opacity ?? 1)));
  box.appendChild(slider(o.opacity ?? 1, 0.05, 1, (v) => setProp(o, "opacity", v)));
  box.appendChild(check("Na svim stranama", !!o.allPages, (v) => setProp(o, "allPages", v)));
  box.appendChild(btn(icon("refresh") + "Zameni sliku", () => { S.replaceImg = o.id; $("#fileImg").click(); }, "txt"));
}

// small controls
function stepper(v, min, max, step, cb, unit = "", dec = 0) {
  const w = document.createElement("div"); w.className = "stepper";
  w.innerHTML = `<button aria-label="Manje">${icon("minus")}</button><input><button aria-label="Više">${icon("plus")}</button>`;
  const inp = $("input", w);
  inp.value = formatNumber(v, dec) + unit;
  const set = (n) => { n = Math.max(min, Math.min(max, n)); cb(Math.round(n * 100) / 100); };
  const btns = $$("button", w);
  btns[0].onclick = () => set(v - step); btns[1].onclick = () => set(v + step);
  inp.onchange = () => { const n = parseFloat(inp.value.replace(",", ".")); if (!isNaN(n)) set(n); else inp.value = formatNumber(v, dec) + unit; };
  inp.onfocus = () => inp.select();
  return w;
}
function numField(label, v, cb) {
  const f = document.createElement("label"); f.className = "field";
  f.innerHTML = `${label}<input>`;
  const inp = $("input", f); inp.value = formatNumber(v, 0) + " mm";
  inp.onchange = () => { const n = parseFloat(inp.value.replace(",", ".")); if (n > 0) cb(n); };
  inp.onfocus = () => inp.select();
  return f;
}
function check(text, on, cb) {
  const l = document.createElement("label"); l.className = "check";
  l.innerHTML = `<input type="checkbox"${on ? " checked" : ""}>${text}`;
  $("input", l).onchange = (e) => cb(e.target.checked);
  return l;
}
function slider(v, min, max, cb, raw = false) {
  const s = document.createElement("div"); s.className = "slider";
  const f = (x) => (raw ? x : (x - min) / (max - min));
  s.innerHTML = `<div class="fill" style="width:${f(v) * 100}%"></div><div class="knob" style="left:${f(v) * 100}%"></div>`;
  s.onmousedown = (e) => {
    const r = s.getBoundingClientRect();
    const val = (ev) => { const k = Math.max(0, Math.min(1, (ev.clientX - r.left) / r.width)); return raw ? k : min + k * (max - min); };
    const show = (x) => { const k = raw ? x : (x - min) / (max - min); $(".fill", s).style.width = k * 100 + "%"; $(".knob", s).style.left = k * 100 + "%"; };
    let cur = val(e); show(cur);
    const mv = (ev) => { cur = val(ev); show(cur); };
    const up = () => { removeEventListener("mousemove", mv); removeEventListener("mouseup", up); cb(Math.round(cur * 100) / 100); };
    addEventListener("mousemove", mv); addEventListener("mouseup", up);
  };
  return s;
}
function colorPick(list, cur, cb, allowNone = false) {
  const w = document.createElement("div"); w.className = "swatches";
  if (allowNone) w.appendChild(Object.assign(btn("", () => cb(""), "sw none" + (!cur ? " on" : ""), "Bez boje")));
  for (const c of list) { const b = btn("", () => cb(c), "sw" + (c.toLowerCase() === (cur || "").toLowerCase() ? " on" : ""), c); b.style.background = c; w.appendChild(b); }
  const hex = document.createElement("input"); hex.className = "hex"; hex.value = cur || ""; hex.placeholder = "#000000";
  hex.onchange = () => { const v = hex.value.trim(); if (/^#?[0-9a-f]{6}$/i.test(v)) cb(v.startsWith("#") ? v : "#" + v); else hex.value = cur || ""; };
  w.appendChild(hex);
  return w;
}

// custom dropdown menu (UI4)
function openMenu(anchor, items, { search = false, width, render } = {}) {
  closeMenu();
  const m = document.createElement("div"); m.className = "menu";
  const r = anchor.getBoundingClientRect();
  m.style.left = Math.min(r.left, innerWidth - (width || r.width) - 8) + "px";
  m.style.minWidth = (width || r.width) + "px";
  const below = innerHeight - r.bottom > 300;
  if (below) m.style.top = r.bottom + 4 + "px"; else m.style.bottom = innerHeight - r.top + 4 + "px";
  const list = document.createElement("div"); list.className = "mlist";
  let inp = null;
  if (search) { inp = document.createElement("input"); inp.placeholder = "Traži"; m.appendChild(inp); }
  m.appendChild(list);
  const fill = (q = "") => {
    list.innerHTML = "";
    for (const it of items) {
      if (q && !it.label.toLowerCase().includes(q.toLowerCase())) continue;
      const b = document.createElement("button"); b.className = "mi" + (it.on ? " on" : "");
      b.innerHTML = it.html || esc(it.label);
      b.onclick = () => { closeMenu(); it.fn(); };
      if (render) render(b, it);
      list.appendChild(b);
    }
  };
  fill();
  if (inp) inp.oninput = () => fill(inp.value);
  document.body.appendChild(m);
  openMenu.el = m;
  setTimeout(() => { addEventListener("mousedown", openMenu.out = (e) => { if (!m.contains(e.target)) closeMenu(); }); if (inp) inp.focus();
    const on = $(".mi.on", list); if (on) on.scrollIntoView({ block: "center" }); });
  return m;
}
function closeMenu() { if (openMenu.el) { openMenu.el.remove(); openMenu.el = null; removeEventListener("mousedown", openMenu.out); } }

// fonts
const loadedFonts = new Map();
function fontFamily(name) { return `"PF ${name}", sans-serif`; }
function loadFont(name, style = "r") {
  const k = name + "|" + style;
  if (loadedFonts.has(k) || !name) return;
  const f = S.fonts.find((x) => x.name === name);
  if (!f) return;
  const st = f.styles.includes(style) ? style : "r";
  const ff = new FontFace(`PF ${name}`, `url(/api/font?name=${encodeURIComponent(name)}&s=${st})`,
    { weight: style.includes("b") ? "700" : "400", style: style.includes("i") ? "italic" : "normal" });
  loadedFonts.set(k, ff.load().then((x) => document.fonts.add(x)).catch(() => {}));
}
function loadFontFor(o) {
  const f = o.font || S.defFont;
  loadFont(f, "r");
  if (o.bold) loadFont(f, "b"); if (o.italic) loadFont(f, "i"); if (o.bold && o.italic) loadFont(f, "bi");
}
function fontButton(cur, cb) {
  const b = document.createElement("button"); b.className = "sel-btn";
  b.innerHTML = `<span>${esc(cur)}</span>${icon("down")}`;
  loadFont(cur); $("span", b).style.fontFamily = fontFamily(cur);
  b.onclick = () => {
    const fio = new IntersectionObserver((ents) => ents.forEach((e) => { if (e.isIntersecting) { loadFont(e.target.dataset.f); e.target.style.fontFamily = fontFamily(e.target.dataset.f); fio.unobserve(e.target); } }));
    openMenu(b, S.fonts.map((f) => ({ label: f.name, on: f.name === cur, fn: () => cb(f.name) })), {
      search: true, width: 280, render: (el, it) => { el.dataset.f = it.label; el.style.fontSize = "15px"; fio.observe(el); },
    });
  };
  return b;
}

// ---------- edit: objects on pages ----------
function selObj() {
  const d = D(); if (!d || !S.sel) return null;
  for (const list of Object.values(d.objects)) { const o = list.find((x) => x.id === S.sel); if (o) return o; }
  return null;
}
function objUid(o) { const d = D(); for (const [u, l] of Object.entries(d.objects)) if (l.includes(o)) return u; return null; }
function refreshOverlays() { $$(".page").forEach((pg) => { if (pg.dataset.filled) buildOverlay(pg); }); }
function select(id) {
  S.sel = id; S.cropMode = false;
  $$(".obj").forEach((e) => { const on = e.dataset.id === id; e.classList.toggle("sel", on); if (!on) $$(".h", e).forEach((h) => h.remove()); });
  const o = selObj(); if (o) refreshObj(o);
  renderPanel();
}
function buildOverlay(pg) {
  $$(".ol,.fld", pg).forEach((x) => x.remove());
  const d = D(); const it = d.items[+pg.dataset.i];
  const ol = document.createElement("div"); ol.className = "ol" + (S.mode === "edit" ? "" : " static");
  const img = $("img.pg", pg);
  if (img) img.after(ol); else pg.prepend(ol);
  for (const o of d.objects[it.uid] || []) ol.appendChild(objEl(o));
  for (const [u, list] of Object.entries(d.objects)) {     // images placed on every page (shown where they will be)
    if (u === it.uid) continue;
    for (const o of list) if (o.type === "image" && o.allPages) { const e = objEl(o, true); e.style.opacity = (o.opacity ?? 1) * 0.6; e.style.pointerEvents = "none"; ol.appendChild(e); }
  }
  if (S.mode !== "edit") return;
  ol.onmousedown = (e) => overlayDown(e, pg, it);
  ol.onmousemove = (e) => { if (S.tool === "fix") hoverSpan(e, pg, it); };
  ol.onmouseleave = () => $$(".spanhint", pg).forEach((x) => x.remove());
  if (S.tool === "form") buildForms(pg, it);
}
function objEl(o, ghost = false) {
  const e = document.createElement("div");
  e.className = `obj ${o.type}` + (o.id === S.sel && !ghost ? " sel" : "") + (o.id === S.sel && S.cropMode ? " crop" : "");
  e.dataset.id = o.id;
  paintObj(e, o);
  return e;
}
function refreshObj(o) {
  for (const e of $$(`.obj[data-id="${o.id}"]`)) {
    const tx = $(".tx", e);
    if (tx && document.activeElement === tx) { paintObj(e, o, true); continue; }  // typing: keep the caret
    const n = objEl(o, !!e.style.pointerEvents);
    if (e.style.pointerEvents) { n.style.opacity = e.style.opacity; n.style.pointerEvents = "none"; }
    e.replaceWith(n);
  }
}
function paintObj(e, o, keepText = false) {
  const sc = scale();
  let x = o.x, y = o.y, w = o.w, h = o.h;
  if (o.type === "shape" && (o.kind === "line" || o.kind === "arrow")) { x = Math.min(o.x, o.x + o.w); y = Math.min(o.y, o.y + o.h); w = Math.abs(o.w); h = Math.abs(o.h); }
  e.style.left = x * sc + "px"; e.style.top = y * sc + "px"; e.style.width = Math.max(w, 1) * sc + "px";
  if (o.type !== "text" && o.type !== "fix") e.style.height = Math.max(h, 1) * sc + "px"; else e.style.minHeight = h * sc + "px";
  if (o.type === "text" || o.type === "fix") {
    loadFontFor(o);
    let tx = $(".tx", e);
    if (!tx) { tx = document.createElement("div"); tx.className = "tx"; tx.spellcheck = false; e.appendChild(tx); }
    if (!keepText) tx.textContent = o.text;
    const deco = [o.underline && "underline", o.strike && "line-through"].filter(Boolean).join(" ") || "none";
    tx.style.cssText = `font-family:${fontFamily(o.font || S.defFont)};font-size:${o.size * sc}px;line-height:${o.lineHeight};color:${o.color};` +
      `font-weight:${o.bold ? 700 : 400};font-style:${o.italic ? "italic" : "normal"};text-decoration:${deco};text-align:${o.align}`;
    tx.contentEditable = o.id === S.sel ? "plaintext-only" : "false";
  } else if (o.type === "image") {
    e.style.transform = o.angle ? `rotate(${o.angle}deg)` : "";
    e.style.opacity = o.opacity ?? 1;
    e.style.mixBlendMode = o.behind ? "multiply" : "";
    const c = o.crop || { l: 0, t: 0, r: 0, b: 0 };
    const fw = o.w / (1 - c.l - c.r), fh = o.h / (1 - c.t - c.b);
    e.innerHTML = `<div class="clip"><img alt="" src="/api/image/${o.img}"></div>`;
    const im = $("img", e);
    im.style.cssText = `width:${fw * sc}px;height:${fh * sc}px;left:${-c.l * fw * sc}px;top:${-c.t * fh * sc}px;` +
      `transform:scale(${o.flipH ? -1 : 1},${o.flipV ? -1 : 1})`;
  } else if (o.type === "shape") {
    const sw = o.width * sc;
    const st = o.stroke ? `stroke="${o.stroke}" stroke-width="${sw}"` : 'stroke="none"';
    const fill = o.fill || "none";
    let svg = "";
    const W = Math.abs(o.w) * sc, H = Math.abs(o.h) * sc;
    if (o.kind === "rect") svg = `<rect x="0" y="0" width="${W}" height="${H}" fill="${fill}" ${st} stroke-linejoin="round"/>`;
    else if (o.kind === "ellipse") svg = `<ellipse cx="${W / 2}" cy="${H / 2}" rx="${W / 2}" ry="${H / 2}" fill="${fill}" ${st}/>`;
    else {
      const x1 = o.w >= 0 ? 0 : W, y1 = o.h >= 0 ? 0 : H, x2 = o.w >= 0 ? W : 0, y2 = o.h >= 0 ? H : 0;
      svg = `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" ${st} stroke-linecap="round"/>`;
      if (o.kind === "arrow") {
        const a = Math.atan2(y2 - y1, x2 - x1), ln = Math.max(9, o.width * 4) * sc;
        const p = (d) => `${x2 - ln * Math.cos(a + d)},${y2 - ln * Math.sin(a + d)}`;
        svg += `<polyline points="${p(0.45)} ${x2},${y2} ${p(-0.45)}" fill="none" ${st} stroke-linecap="round" stroke-linejoin="round"/>`;
      }
    }
    e.innerHTML = `<svg width="${W}" height="${H}" style="opacity:${o.opacity ?? 1}">${svg}</svg>`;
  } else if (o.type === "mark") {
    e.style.background = o.color; e.style.opacity = o.opacity ?? 0.4;
  }
  $$(".h", e).forEach((h) => h.remove());
  if (o.id === S.sel && !e.style.pointerEvents && S.mode === "edit") addHandles(e, o);
}
function addHandles(e, o) {
  const line = o.type === "shape" && (o.kind === "line" || o.kind === "arrow");
  let hs = line ? [] : (o.type === "text" || o.type === "fix") ? ["w", "e"] : ["nw", "n", "ne", "e", "se", "s", "sw", "w"];
  if (o.type === "image" && !S.cropMode) hs = hs.concat("rot");
  for (const k of hs) { const h = document.createElement("div"); h.className = "h " + k; h.dataset.h = k; e.appendChild(h); }
  if (line) {
    const sc = scale();
    for (const [k, px, py] of [["p1", o.w >= 0 ? 0 : -o.w, o.h >= 0 ? 0 : -o.h], ["p2", o.w >= 0 ? o.w : 0, o.h >= 0 ? o.h : 0]]) {
      const h = document.createElement("div"); h.className = "h"; h.dataset.h = k;
      h.style.cssText = `left:${px * sc - 5}px;top:${py * sc - 5}px;cursor:move`;
      e.appendChild(h);
    }
  }
}
function pagePoint(e, pg) { const r = pg.getBoundingClientRect(), sc = scale(); return [(e.clientX - r.left) / sc, (e.clientY - r.top) / sc]; }
function addObj(uid, o) {
  const d = D();
  // an empty new text box is not an undo step until something is typed into it
  if (o.type === "text" && !o.text) Object.defineProperty(o, "_fresh", { value: true, writable: true, enumerable: false });
  else commit(d);
  o.id = o.id || newUid();
  (d.objects[uid] = d.objects[uid] || []).push(o);
  S.sel = o.id;
  const pg = $(`.page[data-uid="${uid}"]`); if (pg) buildOverlay(pg);
  if (o.type === "image" && o.allPages) refreshOverlays();
  renderPanel(); renderVbar();
  return o;
}
function delObj() {
  const o = selObj(); if (!o) return;
  const d = D(); commit(d);
  const u = objUid(o); d.objects[u] = d.objects[u].filter((x) => x !== o);
  S.sel = null; refreshOverlays(); renderPanel(); renderVbar();
}
function dupObj() {
  const o = selObj(); if (!o) return;
  const c = JSON.parse(JSON.stringify(o)); c.id = newUid(); c.x += 12; c.y += 12;
  if (c.type === "fix") { c.type = "text"; delete c.orig; }
  addObj(objUid(o), c);
}
function focusText(o) {
  requestAnimationFrame(() => {
    const tx = $(`.obj[data-id="${o.id}"] .tx`); if (!tx) return;
    tx.contentEditable = "plaintext-only"; tx.focus();
    const r = document.createRange(); r.selectNodeContents(tx); r.collapse(false);
    const s = getSelection(); s.removeAllRanges(); s.addRange(r);
  });
}
function overlayDown(e, pg, it) {
  if (e.button !== 0) return;
  const d = D(); const objE = e.target.closest(".obj"); const handle = e.target.closest(".h");
  if (objE && !objE.style.pointerEvents) {
    const o = (d.objects[it.uid] || []).find((x) => x.id === objE.dataset.id); if (!o) return;
    if ((o.type === "text" || o.type === "fix") && o.id === S.sel && e.target.closest(".tx") && !handle) return; // caret
    e.preventDefault();
    if (o.id !== S.sel) select(o.id);
    dragObj(e, pg, o, handle ? handle.dataset.h : "move");
    return;
  }
  const [px, py] = pagePoint(e, pg);
  if (S.tool === "text") {
    e.preventDefault();
    const t = S.def.text;
    const o = addObj(it.uid, { type: "text", x: px, y: py - t.size * 0.6, w: 220, h: t.size * t.lineHeight + 2, text: "", ...t, font: t.font || S.defFont });
    focusText(o);
  } else if (S.tool === "fix") {
    e.preventDefault();
    fixAt(px, py, pg, it);
  } else if (S.tool === "mark" || S.tool === "shape") {
    e.preventDefault();
    drawDraft(e, pg, it, px, py);
  } else if (S.sel) {
    select(null);
  }
}
function dragObj(e, pg, o, mode) {
  const sc = scale(); const x0 = e.clientX, y0 = e.clientY;
  const start = JSON.parse(JSON.stringify(o)); let moved = false;
  const el = () => $(`.obj[data-id="${o.id}"]`, pg);
  const mv = (ev) => {
    const dx = (ev.clientX - x0) / sc, dy = (ev.clientY - y0) / sc;
    if (!moved && Math.abs(dx) + Math.abs(dy) < 2 / sc) return;
    if (!moved) { moved = true; commit(); }
    if (mode === "move") { o.x = start.x + dx; o.y = start.y + dy; }
    else if (mode === "p1") { o.x = start.x + dx; o.y = start.y + dy; o.w = start.w - dx; o.h = start.h - dy; }
    else if (mode === "p2") { o.w = start.w + dx; o.h = start.h + dy; }
    else if (mode === "rot") {
      const r = pg.getBoundingClientRect(); const cx = r.left + (o.x + o.w / 2) * sc, cy = r.top + (o.y + o.h / 2) * sc;
      let a = Math.atan2(ev.clientY - cy, ev.clientX - cx) * 180 / Math.PI + 90;
      if (ev.shiftKey) a = Math.round(a / 15) * 15;
      o.angle = Math.round((a + 360) % 360);
    } else resizeObj(o, start, mode, dx, dy, ev.shiftKey);
    const n = el(); if (n) paintObj(n, o, true);
  };
  const up = () => {
    removeEventListener("mousemove", mv); removeEventListener("mouseup", up);
    if (moved) { persist(); if (o.type === "image" && o.allPages) refreshOverlays(); renderPanel(); }
    else if (o.type === "text" || o.type === "fix") focusText(o);
  };
  addEventListener("mousemove", mv); addEventListener("mouseup", up);
}
function resizeObj(o, s, mode, dx, dy, shift) {
  const keep = o.type === "image" && o.keep !== false && !S.cropMode ? !shift : shift;
  let { x, y, w, h } = s;
  if (mode.includes("e")) w = s.w + dx;
  if (mode.includes("w")) { w = s.w - dx; x = s.x + dx; }
  if (mode.includes("s")) h = s.h + dy;
  if (mode.includes("n")) { h = s.h - dy; y = s.y + dy; }
  if (keep && mode.length === 2) {
    const k = Math.max(w / s.w, h / s.h); const nw = s.w * k, nh = s.h * k;
    if (mode.includes("w")) x = s.x + s.w - nw; if (mode.includes("n")) y = s.y + s.h - nh;
    w = nw; h = nh;
  }
  if (w < 4 || h < 4) return;
  if (o.type === "image" && S.cropMode) {        // cropping: the picture stays, the window into it changes
    const c = { ...(s.crop || { l: 0, t: 0, r: 0, b: 0 }) };
    const fw = s.w / (1 - c.l - c.r), fh = s.h / (1 - c.t - c.b);
    if (mode.includes("e")) c.r = Math.max(0, c.r - (w - s.w) / fw);
    if (mode.includes("w")) c.l = Math.max(0, c.l - (w - s.w) / fw);
    if (mode.includes("s")) c.b = Math.max(0, c.b - (h - s.h) / fh);
    if (mode.includes("n")) c.t = Math.max(0, c.t - (h - s.h) / fh);
    if (c.l + c.r > 0.95 || c.t + c.b > 0.95) return;
    o.crop = c; o.w = fw * (1 - c.l - c.r); o.h = fh * (1 - c.t - c.b);
    o.x = mode.includes("w") ? s.x + s.w - o.w : s.x; o.y = mode.includes("n") ? s.y + s.h - o.h : s.y;
    return;
  }
  Object.assign(o, { x, y, w, h });
}
function drawDraft(e, pg, it, px, py) {
  const sc = scale(); const dr = document.createElement("div"); dr.className = "draft"; pg.appendChild(dr);
  let qx = px, qy = py;
  const mv = (ev) => {
    [qx, qy] = pagePoint(ev, pg);
    dr.style.cssText = `left:${Math.min(px, qx) * sc}px;top:${Math.min(py, qy) * sc}px;width:${Math.abs(qx - px) * sc}px;height:${Math.abs(qy - py) * sc}px`;
  };
  const up = () => {
    removeEventListener("mousemove", mv); removeEventListener("mouseup", up); dr.remove();
    const w = qx - px, h = qy - py;
    if (Math.abs(w) < 3 && Math.abs(h) < 3) return;
    if (S.tool === "mark") addObj(it.uid, { type: "mark", x: Math.min(px, qx), y: Math.min(py, qy), w: Math.abs(w), h: Math.abs(h), ...S.def.mark });
    else {
      const k = S.shapeKind;
      const base = { type: "shape", kind: k, ...S.def.shape };
      if (k === "line" || k === "arrow") addObj(it.uid, { ...base, x: px, y: py, w, h });
      else addObj(it.uid, { ...base, x: Math.min(px, qx), y: Math.min(py, qy), w: Math.abs(w), h: Math.abs(h) });
    }
  };
  addEventListener("mousemove", mv); addEventListener("mouseup", up);
}
async function spanAt(px, py, it) {
  if (it.rot) return null;
  const t = await getText(it);
  return (t.lines || t.spans).find((s) => px >= s.bbox[0] - 1 && px <= s.bbox[2] + 1 && py >= s.bbox[1] - 1 && py <= s.bbox[3] + 1) || null;
}
async function hoverSpan(e, pg, it) {
  const [px, py] = pagePoint(e, pg);
  const s = await spanAt(px, py, it);
  let h = $(".spanhint", pg);
  if (!s) { if (h) h.remove(); return; }
  if (!h) { h = document.createElement("div"); h.className = "spanhint"; pg.appendChild(h); }
  const sc = scale();
  h.style.cssText = `left:${s.bbox[0] * sc - 2}px;top:${s.bbox[1] * sc - 2}px;width:${(s.bbox[2] - s.bbox[0]) * sc + 4}px;height:${(s.bbox[3] - s.bbox[1]) * sc + 4}px`;
}
async function fixAt(px, py, pg, it) {
  const s = await spanAt(px, py, it);
  if (!s) { if (it.rot) toast("Ispravka teksta radi na stranama koje nisu okretane u Stranama. Sačuvaj pa probaj ponovo."); return; }
  const used = (D().objects[it.uid] || []).some((o) => o.type === "fix" && o.orig.join() === s.bbox.join());
  if (used) return;
  $$(".spanhint", pg).forEach((x) => x.remove());
  const o = addObj(it.uid, {
    type: "fix", orig: s.bbox, x: s.bbox[0], y: s.bbox[1], w: s.bbox[2] - s.bbox[0] + 4, h: s.bbox[3] - s.bbox[1],
    text: s.text, font: s.font || S.defFont, size: s.size, color: s.color, bold: s.bold, italic: s.italic,
    underline: false, strike: false, align: "left", lineHeight: 1.15,
  });
  focusText(o);
  // many PDFs map letters wrongly (č shown, c extracted): take the text as it looks (OCR of the line)
  const q = `x0=${s.bbox[0]}&y0=${s.bbox[1]}&x1=${s.bbox[2]}&y1=${s.bbox[3]}&text=${encodeURIComponent(s.text)}`;
  const r = await api(`/api/src/${it.src}/page/${it.page}/fixtext?${q}`).catch(() => null);
  if (r && r.text && r.text !== o.text && o.text === s.text) {
    o.text = r.text; persist();
    const tx = $(`.obj[data-id="${o.id}"] .tx`);
    if (tx) { tx.textContent = o.text; if (document.activeElement === tx) focusText(o); }
  }
}
// typing into text boxes
document.addEventListener("focusin", (e) => {
  const tx = e.target.closest && e.target.closest(".tx"); if (!tx) return;
  const o = selObj(); if (o && !o._fresh && !tx.dataset.committed) { commit(); tx.dataset.committed = "1"; }
});
document.addEventListener("input", (e) => {
  const tx = e.target.closest && e.target.closest(".tx"); if (!tx) return;
  const o = selObj(); if (!o) return;
  if (o._fresh) {          // first letter in a new box: the undo step is "before this box existed"
    const d = D(); const x = JSON.parse(snapshot(d));
    for (const k in x.objects) x.objects[k] = x.objects[k].filter((y) => y.id !== o.id);
    d.hist.push(JSON.stringify(x)); d.fut = []; d.dirty = true; o._fresh = false; tx.dataset.committed = "1"; renderChrome();
  }
  o.text = tx.innerText.replace(/\n$/, "");
  const sc = scale(); o.h = Math.max(o.h, tx.offsetHeight / sc);
  if (o.type === "fix") { o.w = Math.max(o.orig[2] - o.orig[0], tx.scrollWidth / sc + 2); tx.parentElement.style.width = o.w * sc + "px"; }
  persist();
});
document.addEventListener("focusout", (e) => {
  const tx = e.target.closest && e.target.closest(".tx"); if (!tx) return;
  delete tx.dataset.committed;
  const id = tx.closest(".obj") && tx.closest(".obj").dataset.id;
  const d = D(); if (!d || !id) return;
  const sc = scale();
  for (const [u, list] of Object.entries(d.objects)) {
    const o = list.find((x) => x.id === id); if (!o) continue;
    if (o.type === "text" && !o.text.trim()) {
      // "Dodaj tekst" with nothing typed leaves nothing on the page (and no undo step)
      d.objects[u] = list.filter((x) => x !== o);
      if (S.sel === o.id) S.sel = null;
      const el = $(`.obj[data-id="${o.id}"]`); if (el) el.remove();
      renderPanel(); renderChrome(); persist();
    } else if (o.type === "text" || o.type === "fix") { o.h = tx.offsetHeight / sc; persist(); }
  }
});

// forms
async function buildForms(pg, it) {
  const k = it.src + ":" + it.page;
  if (!formCache.has(k)) formCache.set(k, api(`/api/src/${it.src}/page/${it.page}/forms`).then((r) => r.fields).catch(() => []));
  const fields = await formCache.get(k);
  if (!pg.isConnected || it.rot) return;
  const d = D(); const vals = (d.forms[it.uid] = d.forms[it.uid] || {}); const sc = scale();
  for (const f of fields) {
    let el;
    const v = f.name in vals ? vals[f.name] : f.value;
    if (f.type === "CheckBox" || f.type === "RadioButton") {
      el = document.createElement("input"); el.type = "checkbox"; el.checked = v === true || (v && v !== "Off");
      el.onchange = () => { commit(); vals[f.name] = el.checked; persist(); };
    } else if (f.options && f.options.length) {
      el = document.createElement("button"); el.textContent = v || "";
      el.onclick = () => openMenu(el, f.options.map((op) => ({ label: String(Array.isArray(op) ? op[1] : op),
        fn: () => { commit(); vals[f.name] = Array.isArray(op) ? op[0] : op; el.textContent = vals[f.name]; persist(); } })));
    } else {
      el = document.createElement("input"); el.value = v || "";
      el.onchange = () => { commit(); vals[f.name] = el.value; persist(); };
    }
    el.className = "fld";
    el.style.cssText += `;left:${f.rect[0] * sc}px;top:${f.rect[1] * sc}px;width:${(f.rect[2] - f.rect[0]) * sc}px;height:${(f.rect[3] - f.rect[1]) * sc}px`;
    pg.appendChild(el);
  }
}

// images
$("#fileImg").onchange = async (e) => {
  const f = e.target.files[0]; e.target.value = ""; if (!f) return;
  const fd = new FormData(); fd.append("file", f);
  const r = await safe(() => api("/api/image", { form: fd })); if (!r) return;
  const d = D();
  if (S.replaceImg) {
    const o = selObj(); S.replaceImg = null;
    if (o && o.type === "image") { commit(); o.img = r.id; o.h = o.w * r.h / r.w; o.crop = null; refreshObj(o); renderPanel(); }
    return;
  }
  const it = d.items[d.curPage || 0]; const [W, H] = itemDims(it);
  let w = Math.min(W * 0.5, r.w * 0.75), h = w * r.h / r.w;
  if (h > H * 0.5) { h = H * 0.5; w = h * r.w / r.h; }
  S.tool = "select"; document.body.className = `mode-${S.mode} tool-select`;
  addObj(it.uid, { type: "image", img: r.id, x: (W - w) / 2, y: (H - h) / 2, w, h, angle: 0, opacity: 1, behind: false, allPages: false, keep: true });
  scrollToPage(d.curPage || 0);
};

// ---------- pages mode (organizer) ----------
let dragFrom = null;
function srcColor(d, src) { const l = [...new Set(d.items.map((i) => i.src))]; return SRC_COLORS[l.indexOf(src) % SRC_COLORS.length]; }
function renderOrganizer() {
  const d = D(); const g = $("#ogrid");
  const keepScroll = g.scrollTop;
  g.innerHTML = "";
  const multi = new Set(d.items.map((i) => i.src)).size > 1;
  d.items.forEach((it, i) => {
    const [w, h] = itemDims(it); const k = 150 / Math.max(w, h);
    const c = document.createElement("button");
    c.className = "ocell" + (d.osel.has(it.uid) ? " on" : ""); c.draggable = true; c.dataset.i = i;
    c.innerHTML = `<div class="box"><img width="${Math.round(w * k)}" height="${Math.round(h * k)}" alt="" src="${pageImgUrl(it, 300)}"></div>` +
      `<span class="cap">${multi ? `<i class="dot" style="background:${srcColor(d, it.src)}"></i>` : ""}${i + 1}</span>`;
    c.onclick = (e) => {
      if (e.shiftKey && S.anchor != null) { const [a, b] = [Math.min(S.anchor, i), Math.max(S.anchor, i)]; for (let n = a; n <= b; n++) d.osel.add(d.items[n].uid); }
      else if (e.ctrlKey) { d.osel.has(it.uid) ? d.osel.delete(it.uid) : d.osel.add(it.uid); S.anchor = i; }
      else { const only = d.osel.size === 1 && d.osel.has(it.uid); d.osel.clear(); if (!only) d.osel.add(it.uid); S.anchor = i; }
      $$(".ocell", g).forEach((x, n) => x.classList.toggle("on", d.osel.has(d.items[n].uid))); renderFooter();
    };
    c.ondblclick = () => { d.curPage = i; setMode("read"); setTimeout(() => scrollToPage(i), 50); };
    c.ondragstart = (e) => { dragFrom = i; e.dataTransfer.effectAllowed = "move"; };
    c.ondragover = (e) => {
      if (dragFrom === null) return; e.preventDefault();
      const r = c.getBoundingClientRect(); const left = e.clientX < r.left + r.width / 2;
      $$(".ocell", g).forEach((x) => x.classList.remove("drop-l", "drop-r"));
      c.classList.add(left ? "drop-l" : "drop-r");
    };
    c.ondrop = (e) => {
      e.preventDefault(); if (dragFrom === null) return;
      const r = c.getBoundingClientRect(); let to = e.clientX < r.left + r.width / 2 ? i : i + 1;
      const moving = d.osel.has(d.items[dragFrom].uid) ? d.items.filter((x) => d.osel.has(x.uid)) : [d.items[dragFrom]];
      const before = d.items.slice(0, to).filter((x) => !moving.includes(x)).length;
      commit();
      const rest = d.items.filter((x) => !moving.includes(x));
      rest.splice(before, 0, ...moving); d.items = rest; dragFrom = null;
      renderOrganizer();
    };
    c.ondragend = () => { dragFrom = null; $$(".ocell", g).forEach((x) => x.classList.remove("drop-l", "drop-r")); };
    g.appendChild(c);
  });
  g.scrollTop = keepScroll;
  const lg = $("#olegend"); lg.innerHTML = "";
  if (multi) for (const s of new Set(d.items.map((i) => i.src))) {
    const n = d.srcInfo[s] ? d.srcInfo[s].name : "";
    lg.insertAdjacentHTML("beforeend", `<span><i class="dot" style="background:${srcColor(d, s)}"></i>${esc(n)}</span>`);
  }
  renderFooter();
}
function selectedItems(d) { return d.items.filter((x) => d.osel.has(x.uid)); }
$("#oAll").onclick = () => { const d = D(); if (d.osel.size === d.items.length) d.osel.clear(); else d.items.forEach((x) => d.osel.add(x.uid)); renderOrganizer(); };
function rotateSel(by) {
  const d = D(); const sel = selectedItems(d); if (!sel.length) { toast("Izaberi strane."); return; }
  commit();
  for (const it of sel) {
    const [W, H] = itemDims(it);
    // keep edits on the rotated page where they were on the content
    for (const o of d.objects[it.uid] || []) rotObj(o, W, H, by);
    it.rot = (it.rot + by + 360) % 360;
  }
  renderOrganizer();
}
function rotObj(o, W, H, by) {     // clockwise steps of 90; W x H = page size before the turn
  const steps = ((by + 360) % 360) / 90;
  for (let n = 0; n < steps; n++) {
    const cH = n % 2 ? W : H;
    if (o.type === "shape" && (o.kind === "line" || o.kind === "arrow")) {
      const p1 = [cH - o.y, o.x], p2 = [cH - (o.y + o.h), o.x + o.w];
      o.x = p1[0]; o.y = p1[1]; o.w = p2[0] - p1[0]; o.h = p2[1] - p1[1];
    } else if (o.type === "text" || o.type === "fix") {
      const cx = o.x + o.w / 2, cy = o.y + o.h / 2; const nx = cH - cy, ny = cx;
      o.x = nx - o.w / 2; o.y = ny - o.h / 2;
    } else { [o.x, o.y, o.w, o.h] = [cH - (o.y + o.h), o.x, o.h, o.w]; }
    if (o.orig) { const r = o.orig; o.orig = [cH - r[3], r[0], cH - r[1], r[2]]; }
  }
}
$("#oRotL").onclick = () => rotateSel(-90);
$("#oRotR").onclick = () => rotateSel(90);
$("#oDel").onclick = async () => {
  const d = D(); const sel = selectedItems(d); if (!sel.length) { toast("Izaberi strane."); return; }
  if (sel.length === d.items.length) { await vd.message("Ne mogu da obrišem sve strane."); return; }
  commit();
  d.items = d.items.filter((x) => !d.osel.has(x.uid)); sel.forEach((x) => delete d.objects[x.uid]); d.osel.clear();
  renderOrganizer();
};
$("#oAdd").onclick = async () => {
  const r = await safe(() => api("/api/pick-open", { body: {} })); if (!r || !r.docs.length) return;
  appendDocs(r.docs);
};
function appendDocs(infos) {
  const d = D(); commit();
  for (const info of infos) { d.srcInfo[info.id] = info; d.items.push(...itemsFromInfo(info)); }
  renderOrganizer();
  autoOcr();
  requestAnimationFrame(() => ($("#ogrid").scrollTop = $("#ogrid").scrollHeight));
}
function payload(d, items = d.items) {
  return { items: items.map((i) => ({ src: i.src, page: i.page, rot: i.rot, uid: i.uid })), objects: d.objects, forms: d.forms, name: d.name };
}
$("#oExtract").onclick = async () => {
  const d = D(); const sel = selectedItems(d); if (!sel.length) { toast("Izaberi strane."); return; }
  const stem = d.name.replace(/\.pdf$/i, "");
  const r = await safe(() => api("/api/extract", { body: { ...payload(d, sel), suggest: (d.path ? d.path.replace(/[^\\/]+$/, "") : "") + `${stem}_izdvojeno.pdf` } }));
  if (r && r.path) savedToast(r.path);
};
$("#oSplit").onclick = async () => {
  const d = D();
  if (!d.osel.size) { await vd.message("Izaberi strane od kojih počinje novi deo."); return; }
  const parts = []; let cur = [];
  d.items.forEach((it, i) => { if (i > 0 && d.osel.has(it.uid) && cur.length) { parts.push(cur); cur = []; } cur.push(it); });
  if (cur.length) parts.push(cur);
  if (parts.length < 2) { await vd.message("Izaberi bar jednu stranu posle prve."); return; }
  if (!(await vd.confirm(`Podeliti na ${parts.length} fajla?`, { ok: "Podeli" }))) return;
  const r = await safe(() => api("/api/split", { body: { parts: parts.map((p) => payload(d, p).items), objects: d.objects, forms: d.forms, name: d.name,
    dir: d.path ? d.path.replace(/[\\/][^\\/]+$/, "") : "" } }));
  if (r && r.paths) savedToast(r.paths[0], `Sačuvano ${r.paths.length} fajla.`);
};

// ---------- save / print ----------
function savedToast(path, text = "Sačuvano.") {
  const t = document.createElement("div"); t.className = "toast";
  t.innerHTML = `${icon("check")}<span></span><button class="ghost">${icon("folder")}Prikaži</button>`;
  $("span", t).textContent = text;
  $("button", t).onclick = () => api("/api/show-in-folder", { body: { path } });
  document.body.appendChild(t); setTimeout(() => t.remove(), 5000);
}
async function save(ask = false) {
  const d = D(); if (!d) return;
  if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
  const r = await safe(() => api("/api/save", { body: { ...payload(d), path: d.path, ask: ask || !d.path, name: d.name } }));
  if (!r || r.cancelled) return;
  const info = r.doc;
  d.name = info.name; d.path = info.path; d.items = itemsFromInfo(info); d.objects = {}; d.forms = {};
  d.srcInfo = { [info.id]: info }; d.dirty = false; d.hist = []; d.fut = []; d.osel.clear(); S.sel = null;
  formCache.clear();
  renderAll(); persist();
  savedToast(r.path);
}
async function printDlg() {
  const d = D(); if (!d) return;
  const pr = await safe(() => api("/api/printers")); if (!pr) return;
  if (!pr.available) { await vd.message("Štampa radi samo na Windows-u."); return; }
  if (!pr.printers.length) { await vd.message("Nije pronađen nijedan štampač."); return; }
  const o = { printer: pr.default || pr.printers[0], pages: "", copies: 1, gray: false, duplex: false, fit: true, perSheet: 1 };
  const it = d.items[d.curPage || 0];
  const res = await modal("Štampa", (body) => {
    body.innerHTML = `<div class="pr"><div class="pr-prev"><img alt="" src="${pageImgUrl(it, 300)}"></div><div class="pr-opts"></div></div>`;
    const P = $(".pr-opts", body);
    const pb = document.createElement("button"); pb.className = "sel-btn";
    const showP = () => (pb.innerHTML = `<span>${esc(o.printer)}</span>${icon("down")}`); showP();
    pb.onclick = () => openMenu(pb, pr.printers.map((n) => ({ label: n, on: n === o.printer, fn: () => { o.printer = n; showP(); } })));
    P.appendChild(pb);
    const r = row(2);
    const f1 = document.createElement("label"); f1.className = "field"; f1.innerHTML = "Strane<input placeholder=\"sve\">";
    $("input", f1).oninput = (e) => (o.pages = e.target.value);
    const f2 = document.createElement("label"); f2.className = "field"; f2.innerHTML = "Primeraka<input value=\"1\">";
    $("input", f2).oninput = (e) => (o.copies = Math.max(1, parseInt(e.target.value) || 1));
    r.append(f1, f2); P.appendChild(r);
    P.appendChild(seg([["Boja", false], ["Crno-belo", true]], o.gray, (v) => (o.gray = v)));
    P.appendChild(seg([["Jednostrano", false], ["Obostrano", true]], o.duplex, (v) => (o.duplex = v)));
    P.appendChild(seg([["Uklopi", true], ["Stvarna veličina", false]], o.fit, (v) => (o.fit = v)));
    P.appendChild(seg([["1 po listu", 1], ["2 po listu", 2]], o.perSheet, (v) => (o.perSheet = v)));
  }, [{ label: "Odustani", value: false }, { label: "Štampaj", value: true, cls: "primary" }]);
  if (!res) return;
  if (o.pages.trim().toLowerCase() === "ova") o.pages = String((d.curPage || 0) + 1);
  const r = await safe(() => api("/api/print", { body: { ...payload(d), options: o } })); if (!r) return;
  const prog = showProgress("Štampa…");
  for (;;) {
    await new Promise((x) => setTimeout(x, 600));
    const st = await api("/api/print/" + r.job).catch(() => ({ state: "greška", error: "PDFabrika ne odgovara." }));
    prog.set(st.total ? st.done / st.total : 0);
    if (st.state !== "radi") { prog.close(); if (st.state === "greška") await vd.message(st.error || "Štampa nije uspela."); else toast("Poslato na štampu."); return; }
  }
}
function seg(opts, cur, cb) {
  const s = document.createElement("div"); s.className = "seg"; s.style.setProperty("--n", opts.length);
  for (const [label, v] of opts) {
    const b = document.createElement("button"); b.textContent = label; b.className = v === cur ? "on" : "";
    b.onclick = () => { $$("button", s).forEach((x) => x.classList.remove("on")); b.classList.add("on"); cb(v); };
    s.appendChild(b);
  }
  return s;
}
// app modal with own content (same look as dialog.js; Esc / click outside = cancel)
function modal(title, build, buttons) {
  return new Promise((resolve) => {
    const ov = document.createElement("div"); ov.className = "vd-overlay";
    ov.innerHTML = `<div class="vd-card dlg" role="dialog" aria-modal="true"><h2></h2><div class="body"></div><div class="vd-buttons"></div></div>`;
    $("h2", ov).textContent = title;
    const close = (v) => { removeEventListener("keydown", key, true); ov.remove(); closeMenu(); resolve(v); };
    const key = (e) => { if (e.key === "Escape" && !openMenu.el) { e.preventDefault(); close(false); } };
    for (const b of buttons) {
      const el = document.createElement("button"); el.textContent = b.label; if (b.cls) el.className = b.cls;
      el.onclick = () => close(b.value); $(".vd-buttons", ov).appendChild(el);
    }
    ov.addEventListener("mousedown", (e) => { if (e.target === ov) close(false); });
    addEventListener("keydown", key, true);
    build($(".body", ov), close);
    document.body.appendChild(ov);
  });
}

// ---------- settings ----------
async function settingsDlg() {
  let s = await safe(() => api("/api/settings")); if (!s) return;
  await modal("Podešavanja", (body) => {
    const draw = () => {
      body.innerHTML = "";
      const sec = (t) => { const x = document.createElement("div"); x.className = "set-sec"; x.innerHTML = `<h3>${t}</h3>`; body.appendChild(x); return x; };
      const srow = (parent, label, el) => { const r = document.createElement("div"); r.className = "set-row"; r.innerHTML = `<span>${label}</span>`; r.appendChild(el); parent.appendChild(r); };
      const tgl = (on, fn) => { const b = document.createElement("button"); b.className = "tgl" + (on ? " on" : ""); b.setAttribute("aria-label", "Uključi ili isključi"); b.onclick = fn; return b; };

      const a = sec("Izgled");
      srow(a, "Tema", seg([["Tamna", "dark"], ["Svetla", "light"]], s.theme, async (v) => {
        document.documentElement.dataset.theme = v; s = await api("/api/settings", { body: { theme: v } }); }));

      if (s.windows) {
        const b = sec("Windows");
        srow(b, "Pokreće se sa Windows-om", tgl(s.autostart, async () => { s = await api("/api/settings", { body: { autostart: !s.autostart } }); draw(); }));
        if (s.is_default) {
          const ok = document.createElement("span"); ok.className = "ok isdef";
          ok.innerHTML = `${icon("check")}Podrazumevani program`;
          srow(b, "Program za PDF", ok);
        } else {
          srow(b, "Program za PDF", btn("Postavi kao podrazumevani", async () => { await api("/api/default-app", { body: {} }); watchDefault(); }));
        }
      }

      const lg = sec("Dnevnik");
      const box = document.createElement("div"); box.className = "log";
      const ctl = document.createElement("div"); ctl.className = "set-row";
      const q = document.createElement("input"); q.placeholder = "Filter"; q.style.flex = "1";
      let only = false;
      const load = async () => {
        const r = await api(`/api/log?days=3&problems=${only}&q=${encodeURIComponent(q.value)}`).catch(() => ({ lines: [] }));
        box.innerHTML = r.lines.map((l) => `<div class="${/ (ERROR|CRITICAL|WARNING) /.test(l) || /^\s|Traceback/.test(l) ? "e" : ""}">${esc(l)}</div>`).join("") || '<span class="muted">Prazno</span>';
        box.scrollTop = box.scrollHeight;
      };
      q.oninput = () => { clearTimeout(q.t); q.t = setTimeout(load, 250); };
      const pb = btn("Samo problemi", () => { only = !only; pb.classList.toggle("on", only); load(); });
      ctl.append(q, pb);
      lg.append(ctl, box);
      const del = document.createElement("div"); del.className = "set-row";
      del.innerHTML = `<span class="muted">Veličina: ${formatNumber(s.log_mb, 1)} MB</span>`;
      del.appendChild(btn("Obriši starije od 30 dana", async () => {
        if (!(await vd.confirm("Obrisati dnevnik stariji od 30 dana?", { ok: "Obriši", danger: true }))) return;
        await api("/api/log/delete", { body: { days: 30 } }); s = await api("/api/settings"); draw(); }));
      lg.appendChild(del);
      load();

      const v = sec("Verzija");
      const vr = document.createElement("div"); vr.className = "set-row";
      vr.innerHTML = `<span>${esc(s.version)}</span>`;
      vr.appendChild(btn(icon("refresh") + "Proveri", async (e) => {
        const r = await api("/api/update").catch(() => ({ ok: false }));
        const nova = r.ok && (r.behind || r.restart);
        e.target.closest("button").outerHTML = r.ok ? (nova ? `<span class="ok">Nova verzija ${esc(r.version || "")}</span>` : '<span class="muted">Najnovija verzija</span>') : '<span class="muted">Provera nije uspela</span>';
        if (nova) showUpdate(r);
      }));
      v.appendChild(vr);
    };
    // after "Postavi": Windows Settings is a separate window; watch until PDFabrika is the default (or the dialog closes)
    const watchDefault = () => {
      clearInterval(S.defWatch);
      const t0 = Date.now();
      S.defWatch = setInterval(async () => {
        if (!body.isConnected || Date.now() - t0 > 300000) { clearInterval(S.defWatch); return; }
        const r = await api("/api/default-check").catch(() => null);
        if (r && r.is_default) { clearInterval(S.defWatch); s = await api("/api/settings"); draw(); bar("def", null); }
      }, 1500);
    };
    draw();
  }, [{ label: "Zatvori", value: true, cls: "primary" }]);
  clearInterval(S.defWatch);
}

// ---------- bars: update, default program ----------
function bar(id, html, cls = "") {
  let b = document.getElementById(id);
  if (!html) { if (b) b.remove(); return null; }
  if (!b) { b = document.createElement("div"); b.id = id; $("#bars").appendChild(b); }
  b.className = "bar " + cls; b.innerHTML = html; return b;
}
function showUpdate(r) {
  const b = bar("upd", `${icon("refresh")}<span>Nova verzija ${esc(r.version || "")}</span><button class="primary">Ažuriraj</button>`);
  $("button", b).onclick = async () => {
    if (S.docs.some((d) => d.dirty) && !(await vd.confirm("Ima nesačuvanih izmena. Ažurirati sada?", { ok: "Ažuriraj" }))) return;
    persist();
    const p = await safe(() => api("/api/update", { body: {} }));
    if (p && p.ok) { bar("upd", `${icon("refresh")}<span>Ažuriranje…</span>`); setTimeout(waitRestart, 1500); }
  };
}
async function waitRestart() {
  for (let i = 0; i < 60; i++) {
    await new Promise((r) => setTimeout(r, 1000));
    try { const h = await (await fetch("/health")).json(); if (h.pid !== S.pid) { location.reload(); return; } } catch (e) { /* restarting */ }
  }
}
async function checkDefault() {
  const r = await api("/api/default-check").catch(() => null);
  if (r && r.lost) {
    const b = bar("def", `${icon("alert")}<span>PDFabrika više nije podrazumevani program za PDF.</span><button>Vrati</button><button class="sq ghost" aria-label="Zatvori">${icon("x")}</button>`, "red");
    $$("button", b)[0].onclick = () => api("/api/default-app", { body: {} });
    $$("button", b)[1].onclick = () => b.remove();
  }
}

// ---------- quit ----------
async function quit() {
  const dirty = S.docs.filter((d) => d.dirty);
  const msg = dirty.length ? `Ima nesačuvanih izmena (${dirty.map((d) => d.name).join(", ")}). Ugasiti PDFabriku?` : "Ugasiti PDFabriku?";
  if (!(await vd.confirm(msg, { ok: "Ugasi", danger: !!dirty.length }))) return;
  S.docs = []; persist();
  await api("/api/shutdown", { body: {} }).catch(() => {});
  window.close();
}

// ---------- wiring ----------
$$(".mode").forEach((b) => (b.onclick = () => setMode(b.dataset.mode)));
$("#bOpen").onclick = pickOpen; $("#bOpen2").onclick = pickOpen;
$("#bSave").onclick = () => save(false);
$("#bSaveMenu").onclick = () => {
  const d = D(); if (!d) return;
  const items = [{ label: "Sačuvaj kao…", html: icon("save") + "Sačuvaj kao…", fn: () => save(true) }];
  if (d.path) items.push({ label: "Prikaži u folderu", html: icon("folder") + "Prikaži u folderu", fn: () => api("/api/show-in-folder", { body: { path: d.path } }) });
  openMenu($("#bSaveMenu"), items, { width: 220 });
};
$("#bPrint").onclick = printDlg;
$("#bUndo").onclick = () => undo(); $("#bRedo").onclick = () => undo(true);
$("#bSettings").onclick = settingsDlg;
$("#bQuit").onclick = quit;
$("#zIn").onclick = () => setZoom(S.zoom * 1.15);
$("#z100").onclick = () => setZoom(1);
$("#zOut").onclick = () => setZoom(S.zoom / 1.15);
$("#zVal").onclick = () => openMenu($("#zVal"), [
  { label: "Automatski", on: S.fit === "auto", fn: () => setZoom(1, "auto") },
  { label: "Uklopi širinu", on: S.fit === "width", fn: () => setZoom(1, "width") },
  ...[0.5, 0.75, 1, 1.25, 1.5, 2, 3].map((z) => ({ label: formatPercent(z), on: !S.fit && Math.abs(S.zoom - z) < 0.01, fn: () => setZoom(z) })),
], { width: 150 });
$("#pages").addEventListener("scroll", () => requestAnimationFrame(trackPage), { passive: true });
$("#pages").addEventListener("wheel", (e) => { if (e.ctrlKey) { e.preventDefault(); setZoom(S.zoom * (e.deltaY < 0 ? 1.1 : 1 / 1.1)); } }, { passive: false });
$("#q").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { if (S.hits.length && $("#q").value.trim() === S.lastQ) gotoHit(S.hit + (e.shiftKey ? -1 : 1)); else { S.lastQ = $("#q").value.trim(); doSearch(); } }
  if (e.key === "Escape") { $("#q").value = ""; S.lastQ = ""; doSearch(); }
});
$("#qPrev").onclick = () => gotoHit(S.hit - 1);
$("#qNext").onclick = () => gotoHit(S.hit + 1);
addEventListener("resize", () => { if (S.fit && D() && S.mode !== "pages") { clearTimeout(S.rt); S.rt = setTimeout(() => setZoom(1, S.fit), 150); } });

addEventListener("keydown", (e) => {
  const typing = e.target.closest && (e.target.closest(".tx") || /INPUT|TEXTAREA/.test(e.target.tagName));
  const k = e.key.toLowerCase();
  if (e.ctrlKey && k === "s") { e.preventDefault(); save(e.shiftKey); return; }
  if (e.ctrlKey && k === "o") { e.preventDefault(); pickOpen(); return; }
  if (e.ctrlKey && k === "0") { e.preventDefault(); setZoom(1); return; }
  if (e.ctrlKey && k === "p") { e.preventDefault(); printDlg(); return; }
  if (e.ctrlKey && k === "f") { e.preventDefault(); if (S.mode === "pages") setMode("read"); $("#q").focus(); $("#q").select(); return; }
  if (document.querySelector(".vd-overlay")) return;
  if (typing) { if (e.key === "Escape") { e.target.blur(); } return; }
  if (e.ctrlKey && k === "z") { e.preventDefault(); undo(e.shiftKey); return; }
  if (e.ctrlKey && k === "y") { e.preventDefault(); undo(true); return; }
  if (e.ctrlKey && k === "a" && S.mode === "pages") { e.preventDefault(); $("#oAll").click(); return; }
  if (S.mode === "edit") {
    const o = selObj();
    if (o && (e.key === "Delete" || e.key === "Backspace")) { e.preventDefault(); delObj(); return; }
    if (o && e.key.startsWith("Arrow")) {
      e.preventDefault(); if (!e.repeat) commit();
      const st = e.shiftKey ? 10 : 1;
      if (e.key === "ArrowLeft") o.x -= st; if (e.key === "ArrowRight") o.x += st; if (e.key === "ArrowUp") o.y -= st; if (e.key === "ArrowDown") o.y += st;
      refreshObj(o); persist(); return;
    }
    if (e.key === "Escape") { if (S.sel) select(null); else setTool("select"); }
  }
  if (S.mode === "pages" && e.key === "Delete") $("#oDel").click();
});

// drag & drop files onto the window
let dragDepth = 0;
addEventListener("dragenter", (e) => { if (e.dataTransfer.types.includes("Files")) { dragDepth++; document.body.classList.add("dragging"); } });
addEventListener("dragleave", () => { if (--dragDepth <= 0) { dragDepth = 0; document.body.classList.remove("dragging"); } });
addEventListener("dragover", (e) => { if (e.dataTransfer.types.includes("Files")) e.preventDefault(); });
addEventListener("drop", async (e) => {
  if (!e.dataTransfer.files.length) return;
  e.preventDefault(); dragDepth = 0; document.body.classList.remove("dragging");
  const files = [...e.dataTransfer.files];
  if (S.mode === "pages" && D()) {
    const infos = [];
    for (const f of files) { const fd = new FormData(); fd.append("file", f); const i = await safe(() => api("/api/upload", { form: fd })); if (i) infos.push(i); }
    if (infos.length) appendDocs(infos);
  } else uploadFiles(files);
});

// files opened from outside (double click on a PDF while PDFabrika runs)
async function pollInbox() {
  try {
    const r = await api("/api/inbox");
    r.docs.forEach(addDoc);
    if (r.errors.length) vd.message(r.errors.join("\n"));
    if (r.askQuit) quit();
  } catch (e) { /* server restarting */ }
  setTimeout(pollInbox, 1200);
}

(async function init() {
  const h = await api("/health").catch(() => ({}));
  S.pid = h.pid;
  const f = await api("/api/fonts").catch(() => ({ fonts: [], default: "Arial" }));
  S.fonts = f.fonts; S.defFont = f.default || "Arial";
  if (!S.fonts.length) setTimeout(async () => { const g = await api("/api/fonts").catch(() => null); if (g) { S.fonts = g.fonts; S.defFont = g.default; } }, 4000);
  await restore();
  autoOcr();
  const ext = new URLSearchParams(location.search).get("otvori");
  if (ext) history.replaceState(null, "", "/");
  renderAll();
  pollInbox();
  checkDefault();
  const u = await api("/api/update").catch(() => null);
  if (u && u.ok && (u.behind || u.restart)) showUpdate(u);
  setInterval(async () => { const r = await api("/api/update").catch(() => null); if (r && r.ok && (r.behind || r.restart)) showUpdate(r); }, 3600 * 1000);
})();
