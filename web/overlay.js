/* SOVEREIGN — Overlay Lab: put up to 12 series (assets, crypto, macro) on one chart. */
(() => {
const MAX = 12;
const COLORS = ["#c6a052", "#3987e5", "#e66767", "#9085e9", "#4fb3a6", "#e0a85c", "#d98bbf", "#7cc4f5", "#8bc34a", "#b7b0a2", "#f2d45c", "#5ad1d1"];
const MODES = [["own", "True values, each on its own scale"], ["rebase", "Rebased to 100 at start"], ["change", "Change since start"], ["z", "Z-score (standardised)"]];
const RANGES = [["6M", 0.5], ["1Y", 1], ["3Y", 3], ["5Y", 5], ["10Y", 10], ["20Y", 20], ["Max", 99]];
const CRYPTO_QUICK = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "TON", "TRX", "DOT", "LTC", "SUI", "PEPE"];
const PRESETS = [
  ["Bitcoin vs US macro", "bin:BTC,fred:us_cpi_yoy,fred:us_unrate,fred:us_fedfunds,fred:us_10y,fred:us_m2_yoy,mkt:dxy,fred:us_hy_spread,fred:us_fed_assets,mkt:vix"],
  ["Gold vs real yields and the dollar", "mkt:gold,fred:us_real10,fred:us_dollar,fred:us_cpi_yoy,fred:us_fedfunds,fred:us_be5,cbgold:CN"],
  ["Liquidity and risk assets", "mkt:spx,mkt:ndx,bin:BTC,fred:us_m2,fred:us_fed_assets,fred:us_rrp,fred:us_hy_spread"],
  ["Crypto majors", "bin:BTC,bin:ETH,bin:SOL,bin:BNB,bin:XRP,bin:DOGE"],
  ["Inflation around the world", "oecd:us:CP,oecd:gb:CP,oecd:de:CP,oecd:fr:CP,oecd:jp:CP,oecd:ca:CP,oecd:in:CP,oecd:cn:CP"],
  ["Unemployment around the world", "oecd:us:UNEMP,oecd:gb:UNEMP,oecd:de:UNEMP,oecd:fr:UNEMP,oecd:jp:UNEMP,oecd:ca:UNEMP"],
  ["Policy rates", "rate:US,rate:XM,rate:GB,rate:JP,rate:CA,rate:CH,rate:IN,rate:CN,rate:RU"],
];
const OV = { file: null, loading: null, list: [], mode: "own", range: "5Y", log: false, corr: "chg", cache: {}, err: {}, chart: null };
window.OV = OV;

/* ---------- catalogue ---------- */
const mDate = d => /^\d{4}-\d{2}$/.test(d) ? d + "-01" : /^\d{4}-Q\d$/.test(d) ? `${d.slice(0, 4)}-${String(+d.slice(6) * 3).padStart(2, "0")}-01` : /^\d{4}$/.test(d) ? d + "-07-01" : d.slice(0, 10);
function catalogue() {
  const out = [], add = (id, name, group, unit, freq, source, get) => out.push({ id, name, group, unit, freq, source, get });
  const F = OV.file?.series || {};
  Object.entries(F).forEach(([id, s]) => add(id, s.name, s.group, s.unit, s.freq, s.source, () => s));
  const G = S.G || {};
  // gold and bitcoin from the core engine if the long file is missing them
  (S.data?.assets || []).forEach(a => { if (a.ohlc?.length) add(`sov:${a.symbol}`, `${a.name} (engine price)`, "Gold & Bitcoin", "price", "Daily", a.price_source || "", () => ({ dates: a.ohlc.map(r => r[0]), values: a.ohlc.map(r => r[4]) })); });
  const nl = S.data?.macro?.NETLIQ; if (nl?.series) add("sov:NETLIQ", "US net liquidity (Fed assets − RRP − TGA, $bn)", "Liquidity", "$bn", "Weekly", "FRED (derived)", () => nl.series);
  const cname = k => (CTRY().find(c => c.key === k) || {}).name || k.toUpperCase();
  Object.entries(G.oecd?.countries || {}).forEach(([k, ms]) => Object.entries(ms).forEach(([m, r]) => r.series && add(`oecd:${k}:${m}`, `${cname(k)}: ${r.label}${r.transform ? " (" + r.transform.replace("Growth rate, over 1 year", "y/y %") + ")" : ""}`, "Countries — monthly", r.unit || "", "Monthly", r.source || "OECD", () => ({ dates: r.series.dates.map(mDate), values: r.series.values }))));
  const bisName = { US: "United States", XM: "Euro area (ECB)", GB: "United Kingdom", JP: "Japan", CN: "China", IN: "India", CA: "Canada", CH: "Switzerland", RU: "Russia" };
  Object.entries(G.rates || {}).forEach(([k, r]) => r.series && add(`rate:${k}`, `${bisName[k] || k}: central bank policy rate`, "Policy rates", "%", "Monthly", "BIS", () => ({ dates: r.series.dates.map(mDate), values: r.series.values })));
  Object.entries(G.gdp_q || {}).forEach(([k, r]) => add(`gdpq:${k}`, `${cname(k)}: real GDP growth, y/y`, "Countries — quarterly", "%", "Quarterly", "OECD", () => ({ dates: r.series.dates.map(mDate), values: r.series.values })));
  Object.entries(G.iip || {}).forEach(([k, r]) => r.items?.NET && add(`iip:${k}`, `${cname(k)}: net international investment position ($bn)`, "Countries — quarterly", "$bn", "Quarterly", "IMF", () => ({ dates: r.items.NET.series.dates.map(mDate), values: r.items.NET.series.values })));
  Object.entries(G.reserves || {}).forEach(([k, r]) => r.series && add(`res:${k}`, `${cname(k)}: official reserves ($bn)`, "Reserves & gold", "$bn", "Monthly", "IMF", () => ({ dates: r.series.dates.map(d => mDate(d.replace("-M", "-"))), values: r.series.values })));
  (G.cb_gold?.holders || []).forEach(h => add(`cbgold:${h.iso2}`, `${h.name}: central bank gold (tonnes)`, "Reserves & gold", "t", "Monthly", "IMF", () => ({ dates: h.series.dates.map(d => mDate(d.replace("-M", "-"))), values: h.series.values })));
  Object.entries(G.valuation || {}).forEach(([k, v]) => v.series && add(`val:${k}`, v.name, "Valuation", "", "Monthly", "multpl.com", () => ({ dates: v.series.dates.map(mDate), values: v.series.values })));
  // short (2-year) market series only if the long file has no copy
  const have = new Set(out.map(x => x.id));
  [["indices", "Equity indices"], ["commodities", "Commodities"], ["sectors", "US sectors"]].forEach(([g, lab]) => (G.markets?.[g] || []).forEach(i => i.series && !have.has(`mkt:${i.key}`) && add(`mkt:${i.key}`, i.name, lab, "price", "Daily", "Yahoo Finance (2 years)", () => i.series)));
  CRYPTO_QUICK.forEach(c => add(`bin:${c}`, `${c} / USDT (live, Binance)`, "Crypto (live)", "USDT", "Daily", "Binance", null));
  return out;
}
const find = id => catalogue().find(x => x.id === id) || (id.startsWith("bin:") ? { id, name: `${id.slice(4)} / USDT (live, Binance)`, group: "Crypto (live)", unit: "USDT", freq: "Daily", source: "Binance", get: null } : null);

/* ---------- loading ---------- */
async function loadFile() {
  if (OV.file) return OV.file;
  if (!OV.loading) OV.loading = fetch("data/overlay.json", { cache: "no-cache" }).then(r => r.ok ? r.json() : { series: {} }).catch(() => ({ series: {} })).then(j => (OV.file = j));
  return OV.loading;
}
async function binance(sym) {
  const pair = /USDT$|BTC$|ETH$|USDC$|FDUSD$/.test(sym) && sym.length > 5 ? sym : sym + "USDT";
  for (const host of ["https://api.binance.com", "https://data-api.binance.vision"]) {
    try {
      let start = Date.UTC(2017, 0, 1), rows = [];
      for (let i = 0; i < 6; i++) {
        const r = await fetch(`${host}/api/v3/klines?symbol=${pair}&interval=1d&limit=1000&startTime=${start}`);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const k = await r.json(); rows = rows.concat(k);
        if (k.length < 1000) break; start = k[k.length - 1][0] + 864e5;
      }
      if (!rows.length) throw new Error("no data");
      return { dates: rows.map(k => new Date(k[0]).toISOString().slice(0, 10)), values: rows.map(k => +k[4]) };
    } catch (e) { OV.err[sym] = e.message; }
  }
  throw new Error(`${pair} not found on Binance`);
}
async function getData(id) {
  if (OV.cache[id]) return OV.cache[id];
  let d;
  if (id.startsWith("bin:")) d = await binance(id.slice(4).toUpperCase());
  else { const c = find(id); if (!c) throw new Error("unknown series"); d = c.get(); }
  const pairs = d.dates.map((t, i) => [mDate(t), d.values[i]]).filter(p => p[1] != null && isFinite(p[1])).sort((a, b) => a[0].localeCompare(b[0]));
  const ded = []; pairs.forEach(p => { if (ded.length && ded[ded.length - 1][0] === p[0]) ded[ded.length - 1] = p; else ded.push(p); });
  return (OV.cache[id] = { t: ded.map(p => p[0]), v: ded.map(p => p[1]) });
}

/* ---------- maths ---------- */
const startDate = () => { const y = RANGES.find(r => r[0] === OV.range)[1]; const d = new Date(); d.setUTCMonth(d.getUTCMonth() - Math.round(y * 12)); return d.toISOString().slice(0, 10); };
const rateLike = c => /%|pp/.test(c.unit) || /rate|yield|spread|inflation|y\/y|growth|change/i.test(c.name);
function transform(c, d, start) {
  let i0 = d.t.findIndex(t => t >= start); if (i0 < 0) return { t: [], v: [] };
  if (i0 > 0 && c.freq !== "Daily") i0--;      // keep the last low-frequency reading before the window
  const t = d.t.slice(i0), v = d.v.slice(i0);
  if (OV.mode === "own" || !v.length) return { t, v };
  if (OV.mode === "z") { const m = v.reduce((a, b) => a + b, 0) / v.length, sd = Math.sqrt(v.reduce((a, b) => a + (b - m) ** 2, 0) / v.length) || 1; return { t, v: v.map(x => (x - m) / sd) }; }
  const b = v[0];
  if (OV.mode === "rebase") return rateLike(c) || b <= 0 ? { t, v: v.map(x => 100 + (x - b)), note: "pp" } : { t, v: v.map(x => x / b * 100) };
  return rateLike(c) || b <= 0 ? { t, v: v.map(x => x - b), note: "pp" } : { t, v: v.map(x => (x / b - 1) * 100) };
}
const at = (d, t) => { let lo = 0, hi = d.t.length - 1, r = -1; while (lo <= hi) { const m = (lo + hi) >> 1; if (d.t[m] <= t) { r = m; lo = m + 1; } else hi = m - 1; } return r; };
function monthly(d, start) { const m = new Map(); d.t.forEach((t, i) => { if (t >= start) m.set(t.slice(0, 7), d.v[i]); }); return m; }
function corr(a, b) { const n = a.length; if (n < 6) return null; const ma = a.reduce((x, y) => x + y) / n, mb = b.reduce((x, y) => x + y) / n; let sab = 0, sa = 0, sb = 0; for (let i = 0; i < n; i++) { sab += (a[i] - ma) * (b[i] - mb); sa += (a[i] - ma) ** 2; sb += (b[i] - mb) ** 2; } return sa && sb ? sab / Math.sqrt(sa * sb) : null; }

/* ---------- state <-> URL ---------- */
function save() { const p = `${OV.mode};${OV.range};${OV.log ? 1 : 0};${OV.list.map(x => x.id + (x.hidden ? "!" : "")).join(",")}`; history.replaceState(null, "", `#/tools/overlay/${encodeURIComponent(p)}`); try { localStorage.setItem("sov.overlay", p); } catch (e) { /* storage unavailable */ } }
function restore(param) {
  let p = param; if (!p) { try { p = localStorage.getItem("sov.overlay"); } catch (e) { p = null; } }
  if (!p) p = `own;5Y;0;${PRESETS[0][1]}`;
  const [mode, range, log, ids] = p.split(";");
  if (MODES.some(m => m[0] === mode)) OV.mode = mode; if (RANGES.some(r => r[0] === range)) OV.range = range; OV.log = log === "1";
  OV.list = (ids || "").split(",").filter(Boolean).slice(0, MAX).map((x, i) => ({ id: x.replace("!", ""), hidden: x.endsWith("!"), color: COLORS[i % COLORS.length] }));
}
const nextColor = () => COLORS.find(c => !OV.list.some(x => x.color === c)) || COLORS[OV.list.length % COLORS.length];

/* ---------- drawing ---------- */
const fmtV = (v, c) => v == null ? "—" : Math.abs(v) >= 1e4 ? v.toLocaleString("en-US", { maximumFractionDigits: 0 }) : Math.abs(v) >= 100 ? v.toFixed(1) : Math.abs(v) >= 1 ? v.toFixed(2) : v.toPrecision(3);
async function draw() {
  const el = document.getElementById("ov-chart"); if (!el || !window.LightweightCharts) return;
  if (OV.chart) { try { OV.chart.remove(); } catch (e) { /* gone */ } S.charts = S.charts.filter(c => c !== OV.chart); }
  el.innerHTML = "";
  const chart = LightweightCharts.createChart(el, { autoSize: true, layout: { background: { color: "transparent" }, textColor: C.muted, fontFamily: "IBM Plex Sans, system-ui", fontSize: 11 },
    grid: { vertLines: { color: "#15181d" }, horzLines: { color: "#15181d" } }, rightPriceScale: { borderColor: C.axis, visible: true, mode: OV.log && OV.mode === "rebase" ? 1 : 0 },
    leftPriceScale: { borderColor: C.axis, visible: OV.mode === "own" }, timeScale: { borderColor: C.axis }, crosshair: { mode: 0 } });
  OV.chart = chart; S.charts.push(chart);
  const start = startDate(), shown = [];
  let firstLeft = true, firstRight = true;
  for (const [i, it] of OV.list.entries()) {
    const c = find(it.id); setRow(it, "loading…");
    if (!c) { setRow(it, "not available"); continue; }
    try {
      const d = await getData(it.id);
      if (OV.chart !== chart) return;          // page changed or redrawn while loading
      it.raw = d; it.meta = c;
      const x = transform(c, d, start);
      setRow(it, d.t.length ? `${fmtV(d.v[d.v.length - 1], c)} <span class="dim">${d.t[d.t.length - 1]}</span>` : "no data");
      if (it.hidden || !x.t.length) continue;
      let scale = "right";
      if (OV.mode === "own") { if (firstRight) { scale = "right"; firstRight = false; } else if (firstLeft) { scale = "left"; firstLeft = false; } else scale = "s" + i; }
      const s = chart.addLineSeries({ color: it.color, lineWidth: i < 2 ? 2 : 1.5, lineStyle: i >= 7 ? 2 : 0, lineType: c.freq === "Daily" ? 0 : 1, priceScaleId: scale, priceLineVisible: false, lastValueVisible: OV.mode !== "own" || i < 2, title: "",
        priceFormat: { type: "price", precision: Math.abs(x.v[x.v.length - 1]) < 1 ? 4 : 2, minMove: Math.abs(x.v[x.v.length - 1]) < 1 ? 0.0001 : 0.01 } });
      if (scale.startsWith("s")) chart.priceScale(scale).applyOptions({ scaleMargins: { top: 0.08, bottom: 0.08 }, visible: false });
      s.setData(x.t.map((t, k) => ({ time: t, value: x.v[k] })));
      shown.push({ it, c, s, x });
    } catch (e) { setRow(it, `<span class="dn">${esc(e.message)}</span>`); }
  }
  chart.timeScale().fitContent();
  const leg = document.getElementById("ov-legend");
  const legend = t => { if (!leg) return; leg.innerHTML = shown.map(({ it, c }) => { const k = at(it.raw, t || it.raw.t[it.raw.t.length - 1]); return `<span class="ov-l"><span class="sw" style="background:${it.color}"></span>${esc(c.name)}: <b class="num">${k >= 0 ? fmtV(it.raw.v[k], c) : "—"}</b> <span class="dim sm">${k >= 0 ? it.raw.t[k] : ""}</span></span>`; }).join("") + (t ? `<span class="dim sm">at ${t}</span>` : ""); };
  legend(null);
  chart.subscribeCrosshairMove(p => { const t = p?.time; legend(t ? (typeof t === "string" ? t : typeof t === "object" ? `${t.year}-${String(t.month).padStart(2, "0")}-${String(t.day).padStart(2, "0")}` : new Date(t * 1000).toISOString().slice(0, 10)) : null); });
  drawCorr(shown, start);
  const note = document.getElementById("ov-note");
  if (note) note.innerHTML = OV.mode === "own" ? "Each series keeps its true values. The first series uses the right axis, the second the left axis, the rest have their own hidden scales (hover to read values)." :
    OV.mode === "rebase" ? "Prices are rebased to 100 at the start of the range. Rates, yields and other percentages are shown as 100 plus the change in percentage points, so they share the axis without being distorted." :
    OV.mode === "change" ? "Prices show % change since the start of the range; rates and percentages show the change in percentage points." :
    "Each series is standardised over the visible range: 0 is its average, ±1 is one standard deviation. This puts very different units on one axis.";
}
function setRow(it, html) { const el = document.querySelector(`[data-ovv="${CSS.escape(it.id)}"]`); if (el) el.innerHTML = html; }
function drawCorr(shown, start) {
  const el = document.getElementById("ov-corr"); if (!el) return;
  if (shown.length < 2) { el.innerHTML = `<div class="dim sm">Add two or more series to see how they move together.</div>`; return; }
  const ms = shown.map(({ it }) => monthly(it.raw, start)), keys = [...new Set(ms.flatMap(m => [...m.keys()]))].sort();
  const val = (m, k, c) => { if (OV.corr === "lvl") return m.get(k) ?? null; const i = keys.indexOf(k); if (i < 1 || m.get(k) == null || m.get(keys[i - 1]) == null) return null; const a = m.get(keys[i - 1]), b = m.get(k); return rateLike(c) || a <= 0 ? b - a : (b / a - 1) * 100; };
  const cell = (i, j) => { if (i === j) return `<td class="num dim">1</td>`; const a = [], b = []; keys.forEach(k => { const x = val(ms[i], k, shown[i].c), y = val(ms[j], k, shown[j].c); if (x != null && y != null) { a.push(x); b.push(y); } }); const r = corr(a, b);
    const bg = r == null ? "" : r > 0 ? `rgba(57,135,229,${Math.abs(r) * 0.55})` : `rgba(230,103,103,${Math.abs(r) * 0.55})`; return `<td class="num" style="background:${bg}" title="${a.length} months">${r == null ? "—" : r.toFixed(2)}</td>`; };
  el.innerHTML = `<div style="overflow-x:auto"><table class="t"><thead><tr><th></th>${shown.map((s, j) => `<th style="text-align:center"><span class="sw" style="background:${s.it.color}"></span>${j + 1}</th>`).join("")}</tr></thead><tbody>${shown.map((s, i) => `<tr><td><span class="sw" style="background:${s.it.color}"></span>${i + 1}. ${esc(s.c.name)}</td>${shown.map((_, j) => cell(i, j)).join("")}</tr>`).join("")}</tbody></table></div>
    <p class="sm dim">Correlation of ${OV.corr === "lvl" ? "monthly levels" : "month-to-month changes"} over the selected range (blue = move together, red = move opposite). Correlation is not causation, and levels of trending series often correlate by accident; changes are the stricter test.</p>`;
}

/* ---------- controls ---------- */
function listHtml() {
  return OV.list.map((it, i) => { const c = find(it.id); return `<div class="ov-row${it.hidden ? " off" : ""}">
    <input type="color" value="${it.color}" data-ovc="${i}" title="Colour"><span class="ov-n">${i + 1}. ${esc(c ? c.name : it.id)}<div class="sm dim">${esc(c ? `${c.group} · ${c.freq} · ${c.source}` : "")}</div></span>
    <span class="ov-v sm" data-ovv="${esc(it.id)}"></span>
    <button class="btn sm" data-ovh="${i}" title="${it.hidden ? "Show" : "Hide"}">${it.hidden ? "Show" : "Hide"}</button><button class="btn sm" data-ovu="${i}" title="Move up">↑</button><button class="btn sm" data-ovx="${i}" title="Remove">✕</button></div>`; }).join("") || `<div class="dim sm">Nothing selected yet. Search below or pick a preset.</div>`;
}
function rerender() { const l = document.getElementById("ov-list"); if (l) l.innerHTML = listHtml(); document.getElementById("ov-count").textContent = `${OV.list.length} / ${MAX}`; bindList(); save(); draw(); }
function addId(id) { if (OV.list.some(x => x.id === id)) return; if (OV.list.length >= MAX) { alertMsg(`The chart holds up to ${MAX} series. Remove one first.`); return; } OV.list.push({ id, hidden: false, color: nextColor() }); rerender(); }
function alertMsg(m) { const el = document.getElementById("ov-msg"); if (el) { el.textContent = m; setTimeout(() => { if (el.textContent === m) el.textContent = ""; }, 5000); } }
function bindList() {
  document.querySelectorAll("[data-ovx]").forEach(b => b.onclick = () => { const it = OV.list.splice(+b.dataset.ovx, 1)[0]; rerender(); });
  document.querySelectorAll("[data-ovh]").forEach(b => b.onclick = () => { const it = OV.list[+b.dataset.ovh]; it.hidden = !it.hidden; rerender(); });
  document.querySelectorAll("[data-ovu]").forEach(b => b.onclick = () => { const i = +b.dataset.ovu; if (i > 0) { [OV.list[i - 1], OV.list[i]] = [OV.list[i], OV.list[i - 1]]; rerender(); } });
  document.querySelectorAll("[data-ovc]").forEach(b => b.onchange = () => { OV.list[+b.dataset.ovc].color = b.value; rerender(); });
}
function searchResults(q) {
  const cat = catalogue(), words = q.toLowerCase().split(/\s+/).filter(Boolean);
  const hits = cat.filter(c => !OV.list.some(x => x.id === c.id) && words.every(w => (c.name + " " + c.group + " " + c.id).toLowerCase().includes(w))).slice(0, 60);
  const groups = {}; hits.forEach(h => (groups[h.group] = groups[h.group] || []).push(h));
  return Object.entries(groups).map(([g, hs]) => `<div class="ov-g">${esc(g)}</div>` + hs.map(h => `<button class="ov-hit" data-ova="${esc(h.id)}">${esc(h.name)} <span class="dim sm">${esc(h.freq)}</span></button>`).join("")).join("") || `<div class="dim sm">No match. For a coin, type its symbol in the crypto box.</div>`;
}
function bindSearch() {
  const q = document.getElementById("ov-q"), res = document.getElementById("ov-res");
  const upd = () => { res.innerHTML = searchResults(q.value); res.querySelectorAll("[data-ova]").forEach(b => b.onclick = () => { addId(b.dataset.ova); upd(); }); };
  q.oninput = upd; upd();
  const cs = document.getElementById("ov-coin");
  document.getElementById("ov-coin-add").onclick = () => { const v = (cs.value || "").trim().toUpperCase().replace(/[^A-Z0-9]/g, ""); if (v) { addId("bin:" + v); cs.value = ""; } };
  cs.onkeydown = e => { if (e.key === "Enter") document.getElementById("ov-coin-add").click(); };
  document.querySelectorAll("[data-ovq]").forEach(b => b.onclick = () => addId("bin:" + b.dataset.ovq));
  document.querySelectorAll("[data-ovp]").forEach(b => b.onclick = () => { OV.list = PRESETS[+b.dataset.ovp][1].split(",").slice(0, MAX).map((id, i) => ({ id, hidden: false, color: COLORS[i] })); rerender(); upd(); });
  document.getElementById("ov-clear").onclick = () => { OV.list = []; rerender(); upd(); };
  document.querySelectorAll("[data-ovm]").forEach(b => b.onclick = () => { OV.mode = b.dataset.ovm; document.querySelectorAll("[data-ovm]").forEach(x => x.classList.toggle("on", x === b)); save(); draw(); });
  document.querySelectorAll("[data-ovr]").forEach(b => b.onclick = () => { OV.range = b.dataset.ovr; document.querySelectorAll("[data-ovr]").forEach(x => x.classList.toggle("on", x === b)); save(); draw(); });
  document.getElementById("ov-log").onchange = e => { OV.log = e.target.checked; save(); draw(); };
  document.querySelectorAll("[data-ovk]").forEach(b => b.onclick = () => { OV.corr = b.dataset.ovk; document.querySelectorAll("[data-ovk]").forEach(x => x.classList.toggle("on", x === b)); draw(); });
  document.getElementById("ov-copy").onclick = () => { try { navigator.clipboard.writeText(location.href); alertMsg("Link copied. It reopens this exact chart."); } catch (e) { alertMsg(location.href); } };
}

PAGES["tools/overlay"] = pg => {
  restore(pg.param); OV.cache = OV.cache || {};
  mount(async () => { await loadFile(); const l = document.getElementById("ov-list"); if (l) l.innerHTML = listHtml(); document.getElementById("ov-count").textContent = `${OV.list.length} / ${MAX}`; bindList(); bindSearch(); draw(); });
  const n = OV.file ? Object.keys(OV.file.series || {}).length : null;
  return header(pg, "Put up to 12 series on one chart: gold, Bitcoin or any coin on Binance, stocks, indices, currencies, commodities, and macro data such as CPI, unemployment, interest rates, money supply and credit spreads.") +
  `<style>.ov-bar{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin-bottom:8px}.ov-bar .btn.on{background:#2a2416;border-color:${C.gold};color:${C.gold}}
   .ov-row{display:grid;grid-template-columns:28px 1fr auto auto auto auto;gap:6px;align-items:center;padding:6px 0;border-bottom:1px solid #1d2026}.ov-row.off{opacity:.45}
   .ov-row input[type=color]{width:24px;height:24px;border:0;background:none;padding:0;cursor:pointer}.ov-v{text-align:right;min-width:120px}
   .ov-g{margin:10px 0 4px;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:${C.muted}}.ov-hit{display:block;width:100%;text-align:left;background:none;border:0;border-bottom:1px solid #1a1d22;color:inherit;padding:5px 2px;cursor:pointer;font:inherit}.ov-hit:hover{background:#171a1f;color:${C.gold}}
   #ov-res{max-height:420px;overflow:auto}#ov-legend{display:flex;flex-wrap:wrap;gap:4px 14px;margin:6px 0 8px;font-size:12px}.ov-l .sw{margin-right:5px}
   .ov-in{background:#0f1114;border:1px solid #2a2e35;color:inherit;padding:7px 9px;border-radius:4px;font:inherit;width:100%}</style>` +
  panel("", `<div class="ov-bar">${MODES.map(([k, l]) => `<button class="btn sm${OV.mode === k ? " on" : ""}" data-ovm="${k}">${l}</button>`).join("")}</div>
     <div class="ov-bar">${RANGES.map(([k]) => `<button class="btn sm${OV.range === k ? " on" : ""}" data-ovr="${k}">${k}</button>`).join("")}
       <label class="sm" style="margin-left:8px"><input type="checkbox" id="ov-log" ${OV.log ? "checked" : ""}> Log scale (rebased mode)</label>
       <button class="btn sm" id="ov-copy" style="margin-left:auto">Copy link to this chart</button></div>
     <div id="ov-legend"></div><div class="lwc" id="ov-chart" style="height:560px"></div><div class="note" id="ov-note"></div><div class="sm" id="ov-msg" style="color:${C.gold}"></div>`) +
  `<div class="g g2" style="margin-top:12px">${panel(`On the chart <span class="dim sm" id="ov-count"></span>`, `<div id="ov-list"><div class="dim sm">Loading…</div></div><div class="ov-bar" style="margin-top:10px"><span class="sm dim">Presets:</span>${PRESETS.map(([n], i) => `<button class="btn sm" data-ovp="${i}">${esc(n)}</button>`).join("")}<button class="btn sm" id="ov-clear">Clear all</button></div>`)}
     ${panel("Add a series", `<div style="display:flex;gap:6px;margin-bottom:8px"><input class="ov-in" id="ov-coin" placeholder="Any coin on Binance, e.g. ETH, SOL, PEPE, ETHBTC"><button class="btn" id="ov-coin-add">Add coin</button></div>
        <div class="ov-bar">${CRYPTO_QUICK.slice(0, 10).map(c => `<button class="btn sm" data-ovq="${c}">${c}</button>`).join("")}</div>
        <input class="ov-in" id="ov-q" placeholder="Search: gold, nasdaq, CPI, unemployment, fed funds, M2, yen, copper, Japan inflation…"><div id="ov-res"></div>`)}</div>` +
  panel("How the selected series move together", `<div class="ov-bar"><button class="btn sm${OV.corr === "chg" ? " on" : ""}" data-ovk="chg">Monthly changes</button><button class="btn sm${OV.corr === "lvl" ? " on" : ""}" data-ovk="lvl">Levels</button></div><div id="ov-corr"></div>`) +
  `<p class="sm dim">Sources: Yahoo Finance (10 years of daily prices), FRED (US macro back to 1990), OECD, BIS and IMF (country data, monthly and quarterly), Binance (crypto, loaded live in your browser from 2017). Lower-frequency data is drawn as steps: a monthly figure holds until the next release. Nothing is interpolated.</p>`;
};
})();
