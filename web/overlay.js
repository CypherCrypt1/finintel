/* SOVEREIGN — Chart Lab: TradingView-style chart. One main symbol in real prices, plus any overlays you choose
   (on the price chart with their own scale, or in their own panel below). Built on Lightweight Charts v5 (TradingView, open source). */
(() => {
const MAX = 12;
const LW5_URL = "https://unpkg.com/lightweight-charts@5.3.0/dist/lightweight-charts.standalone.production.js";
const COLORS = ["#f2a93b", "#3987e5", "#e66767", "#9085e9", "#4fb3a6", "#d98bbf", "#7cc4f5", "#8bc34a", "#b7b0a2", "#f2d45c", "#5ad1d1", "#ff8a65"];
const TFS = [["D", "1D"], ["W", "1W"], ["M", "1M"]];
const RANGES = [["3M", 0.25], ["6M", 0.5], ["1Y", 1], ["3Y", 3], ["5Y", 5], ["10Y", 10], ["All", 99]];
const CRYPTO_QUICK = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "TON", "TRX", "DOT", "LTC", "SUI", "PEPE"];
const OV = { file: null, loading: null, main: "bin:BTC", tf: "W", range: "3Y", type: "candles", log: false, vol: true, ov: [], cache: {}, err: {}, chart: null, corr: "chg" };
window.OV = OV;
/* ---------- catalogue ---------- */
const mDate = d => /^\d{4}-\d{2}$/.test(d) ? d + "-01" : /^\d{4}-Q\d$/.test(d) ? `${d.slice(0, 4)}-${String(+d.slice(6) * 3).padStart(2, "0")}-01` : /^\d{4}$/.test(d) ? d + "-07-01" : d.slice(0, 10);
function catalogue() {
  const out = [], add = (id, name, group, unit, freq, source, get) => out.push({ id, name, group, unit, freq, source, get });
  const F = OV.file?.series || {};
  Object.entries(F).forEach(([id, s]) => add(id, s.name, s.group, s.unit, s.freq, s.source, () => ({ dates: s.dates, values: s.values, o: s.o, h: s.h, l: s.l })));
  const G = S.G || {};
  // gold and bitcoin from the core engine if the long file is missing them
  (S.data?.assets || []).forEach(a => { if (a.ohlc?.length) add(`sov:${a.symbol}`, `${a.name} (engine price)`, "Gold & Bitcoin", "price", "Daily", a.price_source || "", () => ({ dates: a.ohlc.map(r => r[0]), values: a.ohlc.map(r => r[4]), o: a.ohlc.map(r => r[1]), h: a.ohlc.map(r => r[2]), l: a.ohlc.map(r => r[3]) })); });
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
  CRYPTO_QUICK.forEach(c => add(`bin:${c}`, `${c}/USDT`, "Crypto (Binance, live)", "USDT", "Daily", "Binance", null));
  return out;
}
const find = id => catalogue().find(x => x.id === id) || (id.startsWith("bin:") ? { id, name: `${id.slice(4)}/USDT`, group: "Crypto (Binance, live)", unit: "USDT", freq: "Daily", source: "Binance", get: null } : null);

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
      return { dates: rows.map(k => new Date(k[0]).toISOString().slice(0, 10)), values: rows.map(k => +k[4]), o: rows.map(k => +k[1]), h: rows.map(k => +k[2]), l: rows.map(k => +k[3]), vol: rows.map(k => +k[7]), pair };
    } catch (e) { OV.err[sym] = e.message; }
  }
  throw new Error(`${pair} not found on Binance`);
}
async function getData(id) {
  if (OV.cache[id]) return OV.cache[id];
  let d;
  if (id.startsWith("bin:")) {
    try { d = await binance(id.slice(4).toUpperCase()); }
    catch (e) { const a = (S.data?.assets || []).find(x => x.symbol === id.slice(4).toUpperCase() && x.ohlc?.length); if (!a) throw e;   // Binance blocked: use the site's own copy
      d = { dates: a.ohlc.map(r => r[0]), values: a.ohlc.map(r => r[4]), o: a.ohlc.map(r => r[1]), h: a.ohlc.map(r => r[2]), l: a.ohlc.map(r => r[3]), vol: a.ohlc.map(r => r[5]) }; }
  }
  else { const c = find(id); if (!c) throw new Error("unknown series"); d = c.get(); }
  const ohlc = d.o && d.h && d.l;
  const pairs = d.dates.map((t, i) => [mDate(t), d.values[i], ohlc ? d.o[i] : null, ohlc ? d.h[i] : null, ohlc ? d.l[i] : null, d.vol ? d.vol[i] : null]).filter(p => p[1] != null && isFinite(p[1])).sort((a, b) => a[0].localeCompare(b[0]));
  const ded = []; pairs.forEach(p => { if (ded.length && ded[ded.length - 1][0] === p[0]) ded[ded.length - 1] = p; else ded.push(p); });
  const out = { t: ded.map(p => p[0]), v: ded.map(p => p[1]) };
  if (ohlc && ded.every(p => p[2] != null && p[3] != null && p[4] != null)) { out.o = ded.map(p => p[2]); out.h = ded.map(p => p[3]); out.l = ded.map(p => p[4]); }
  if (d.vol) out.vol = ded.map(p => p[5] || 0);
  if (d.pair) out.pair = d.pair;
  return (OV.cache[id] = out);
}


/* ---------- frequency ---------- */
const bucket = t => { if (OV.tf === "M") return t.slice(0, 7) + "-01"; if (OV.tf === "W") { const d = new Date(t + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7)); return d.toISOString().slice(0, 10); } return t; };
function resample(d, c) {
  if (OV.tf === "D" || (c && (/Monthly|Quarterly|\?/.test(c.freq) || (c.freq === "Weekly" && OV.tf === "W")))) return d;
  const out = { t: [], v: [] }, has = !!d.o; if (has) { out.o = []; out.h = []; out.l = []; } if (d.vol) out.vol = [];
  d.t.forEach((t, i) => { const k = bucket(t), n = out.t.length - 1;
    if (n >= 0 && out.t[n] === k) { out.v[n] = d.v[i]; if (has) { out.h[n] = Math.max(out.h[n], d.h[i]); out.l[n] = Math.min(out.l[n], d.l[i]); } if (d.vol) out.vol[n] += d.vol[i]; }
    else { out.t.push(k); out.v.push(d.v[i]); if (has) { out.o.push(d.o[i]); out.h.push(d.h[i]); out.l.push(d.l[i]); } if (d.vol) out.vol.push(d.vol[i]); } });
  return out;
}
const at = (d, t) => { let lo = 0, hi = d.t.length - 1, r = -1; while (lo <= hi) { const m = (lo + hi) >> 1; if (d.t[m] <= t) { r = m; lo = m + 1; } else hi = m - 1; } return r; };
const rateLike = c => /%|pp/.test(c.unit || "") || /rate|yield|spread|inflation|y\/y|growth/i.test(c.name);
function corr(a, b) { const n = a.length; if (n < 6) return null; const ma = a.reduce((x, y) => x + y) / n, mb = b.reduce((x, y) => x + y) / n; let sab = 0, sa = 0, sb = 0; for (let i = 0; i < n; i++) { sab += (a[i] - ma) * (b[i] - mb); sa += (a[i] - ma) ** 2; sb += (b[i] - mb) ** 2; } return sa && sb ? sab / Math.sqrt(sa * sb) : null; }
const fmtP = v => v == null || !isFinite(v) ? "—" : Math.abs(v) >= 1000 ? v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : Math.abs(v) >= 1 ? v.toFixed(Math.abs(v) >= 100 ? 2 : 3) : v.toPrecision(4);
const fmtVol = v => v >= 1e9 ? (v / 1e9).toFixed(2) + "B" : v >= 1e6 ? (v / 1e6).toFixed(2) + "M" : v >= 1e3 ? (v / 1e3).toFixed(1) + "K" : String(Math.round(v));
const pfmt = v => { const a = Math.abs(v); const p = a >= 1000 ? 2 : a >= 1 ? 3 : a >= 0.01 ? 5 : 8; return { type: "price", precision: p, minMove: 1 / 10 ** p }; };

/* ---------- library loader (v5 kept separate from the v4 used elsewhere on the site) ---------- */
function loadLW5() {
  if (window.LW5) return Promise.resolve(window.LW5);
  return new Promise((res, rej) => { const prev = window.LightweightCharts, sc = document.createElement("script"); sc.src = LW5_URL;
    sc.onload = () => { window.LW5 = window.LightweightCharts; if (prev) window.LightweightCharts = prev; res(window.LW5); }; sc.onerror = () => rej(new Error("chart library failed to load")); document.head.appendChild(sc); });
}

/* ---------- state <-> URL ---------- */
const enc = () => `${OV.main};${OV.tf};${OV.range};${OV.type};${OV.log ? 1 : 0};${OV.vol ? 1 : 0};${OV.ov.map(o => `${o.id}@${o.pane}${o.hidden ? "!" : ""}@${o.color.slice(1)}`).join(",")}`;
function save() { const p = enc(); history.replaceState(null, "", `#/tools/overlay/${encodeURIComponent(p)}`); try { localStorage.setItem("sov.chartlab", p); } catch (e) { /* storage unavailable */ } }
function restore(param) {
  let p = param && param.split(";").length >= 6 ? param : null; if (!p) { try { p = localStorage.getItem("sov.chartlab"); } catch (e) { p = null; } }
  OV.main = "bin:BTC"; OV.tf = "W"; OV.range = "3Y"; OV.type = "candles"; OV.log = false; OV.vol = true; OV.ov = [];
  if (!p) return;
  const [m, tf, rg, ty, lg, vo, ovs] = p.split(";");
  if (m) OV.main = m; if (TFS.some(x => x[0] === tf)) OV.tf = tf; if (RANGES.some(x => x[0] === rg)) OV.range = rg; if (ty === "line" || ty === "candles") OV.type = ty;
  OV.log = lg === "1"; OV.vol = vo !== "0";
  OV.ov = (ovs || "").split(",").filter(Boolean).slice(0, MAX).map((x, i) => { const [id, pn, col] = x.split("@"); return { id, pane: parseInt(pn) || 0, hidden: /!$/.test(pn || ""), color: col ? "#" + col : COLORS[(i + 1) % COLORS.length] }; });
}
const nextColor = () => COLORS.slice(1).find(c => !OV.ov.some(x => x.color === c)) || COLORS[(OV.ov.length + 1) % COLORS.length];
const nextPane = () => Math.max(0, ...OV.ov.map(o => o.pane)) + 1;
const tidyPanes = () => { const used = [...new Set(OV.ov.map(o => o.pane).filter(p => p > 0))].sort((a, b) => a - b); OV.ov.forEach(o => { if (o.pane > 0) o.pane = used.indexOf(o.pane) + 1; }); };

/* ---------- chart ---------- */
const startDate = () => { const y = RANGES.find(r => r[0] === OV.range)[1]; if (y >= 99) return null; const d = new Date(); d.setUTCMonth(d.getUTCMonth() - Math.round(y * 12)); return d.toISOString().slice(0, 10); };
async function draw() {
  const wrap = document.getElementById("cl-wrap"), el = document.getElementById("cl-chart"); if (!el) return;
  let LW; try { LW = await loadLW5(); } catch (e) { el.innerHTML = `<div class="pending">${esc(e.message)}</div>`; return; }
  if (OV.chart) { try { OV.chart.remove(); } catch (e) { /* gone */ } }
  el.innerHTML = "";
  const panes = Math.max(0, ...OV.ov.filter(o => !o.hidden).map(o => o.pane));
  el.style.height = (520 + panes * 150) + "px";
  const chart = LW.createChart(el, { autoSize: true, layout: { background: { color: "#0d0f12" }, textColor: "#9aa0a8", fontFamily: "IBM Plex Sans, system-ui", fontSize: 11, panes: { separatorColor: "#2a2e35", enableResize: true } },
    grid: { vertLines: { color: "#161a20" }, horzLines: { color: "#161a20" } }, crosshair: { mode: 0 },
    localization: { priceFormatter: v => Math.abs(v) >= 1000 ? v.toLocaleString("en-US", { maximumFractionDigits: 2 }) : Math.abs(v) >= 1 ? v.toFixed(2) : v.toPrecision(4) },
    rightPriceScale: { borderColor: "#2a2e35", mode: OV.log ? 1 : 0 }, leftPriceScale: { borderColor: "#2a2e35", visible: OV.ov.some(o => o.pane === 0 && !o.hidden) },
    timeScale: { borderColor: "#2a2e35", rightOffset: 6, barSpacing: OV.tf === "D" ? 6 : 9 } });
  OV.chart = chart;
  // main symbol
  const mc = find(OV.main) || { id: OV.main, name: OV.main, freq: "Daily", unit: "price" }, shown = [];
  setMainTitle(mc, null);
  let md;
  try { md = resample(await getData(OV.main), mc); } catch (e) { document.getElementById("cl-legend").innerHTML = `<span class="dn">${esc(mc.name)}: ${esc(e.message)}</span>`; }
  if (OV.chart !== chart) return;
  let main = null;
  if (md && md.t.length) {
    const last = md.v[md.v.length - 1];
    if (OV.type === "candles" && md.o) { main = chart.addSeries(LW.CandlestickSeries, { upColor: "#26a69a", downColor: "#ef5350", borderVisible: false, wickUpColor: "#26a69a", wickDownColor: "#ef5350", priceFormat: pfmt(last) });
      main.setData(md.t.map((t, k) => ({ time: t, open: md.o[k], high: md.h[k], low: md.l[k], close: md.v[k] }))); }
    else { main = chart.addSeries(LW.LineSeries, { color: COLORS[0], lineWidth: 2, priceFormat: pfmt(last), lineType: mc.freq === "Daily" ? 0 : 1 }); main.setData(md.t.map((t, k) => ({ time: t, value: md.v[k] }))); }
    if (OV.vol && md.vol) { const vs = chart.addSeries(LW.HistogramSeries, { priceScaleId: "vol", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false });
      chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
      vs.setData(md.t.map((t, k) => ({ time: t, value: md.vol[k], color: md.o && md.v[k] >= md.o[k] ? "rgba(38,166,154,.35)" : "rgba(239,83,80,.35)" }))); }
  }
  // overlays
  let leftUsed = false;
  for (const [i, o] of OV.ov.entries()) {
    const c = find(o.id); o.status = "loading…"; listStatus(o);
    if (!c) { o.status = "not available"; listStatus(o); continue; }
    try {
      const d = resample(await getData(o.id), c); if (OV.chart !== chart) return;
      o.d = d; o.c = c; o.status = ""; listStatus(o);
      if (o.hidden || !d.t.length) continue;
      let scaleId;
      if (o.pane === 0) { scaleId = leftUsed ? "ov" + i : "left"; leftUsed = true; }
      else { const firstInPane = !shown.some(s => s.o.pane === o.pane); scaleId = firstInPane ? "right" : "ov" + i; }
      const s = chart.addSeries(LW.LineSeries, { color: o.color, lineWidth: 2, lineType: c.freq === "Daily" || (c.freq === "Weekly" && OV.tf !== "D") ? 0 : 1, priceScaleId: scaleId, priceFormat: pfmt(d.v[d.v.length - 1]),
        lastValueVisible: scaleId === "left" || scaleId === "right", priceLineVisible: false, title: "" }, o.pane);
      if (scaleId.startsWith("ov")) chart.priceScale(scaleId, o.pane).applyOptions({ visible: false, scaleMargins: { top: 0.1, bottom: 0.1 } });
      s.setData(d.t.map((t, k) => ({ time: t, value: d.v[k] })));
      shown.push({ o, c, s });
    } catch (e) { o.status = e.message; listStatus(o); }
  }
  const ps = chart.panes(); ps.forEach((p, i) => { try { p.setStretchFactor(i === 0 ? 3.5 : 1); } catch (e) { /* older API */ } });
  // visible range
  const st = startDate();
  if (md && md.t.length) { const from = st && st > md.t[0] ? st : md.t[0]; try { chart.timeScale().setVisibleRange({ from, to: md.t[md.t.length - 1] }); } catch (e) { chart.timeScale().fitContent(); } }
  else chart.timeScale().fitContent();
  // legends
  const legend = t => {
    if (md && md.t.length) { const k = at(md, t || md.t[md.t.length - 1]); if (k >= 0) setMainTitle(mc, { k, d: md }); }
    const lg = document.getElementById("cl-ovleg"); if (!lg) return;
    const byPane = {}; shown.forEach(x => (byPane[x.o.pane] = byPane[x.o.pane] || []).push(x));
    let left = 10; try { left += chart.priceScale("left").width(); } catch (e) { /* no left scale */ }
    const tops = []; let y = 0; chart.panes().forEach((p, i) => { tops[i] = y; y += p.getHeight() + 1; });
    document.getElementById("cl-legend").style.left = left + "px";
    lg.innerHTML = Object.entries(byPane).map(([p, xs]) => `<div class="cl-lp" style="left:${left}px;top:${(tops[+p] || 0) + (+p === 0 ? 28 : 6)}px">` + xs.map(({ o, c }) => { const k = at(o.d, t || o.d.t[o.d.t.length - 1]);
      return `<span class="cl-li"><span class="sw" style="background:${o.color}"></span>${esc(c.name)} <b class="num">${k >= 0 ? fmtP(o.d.v[k]) : "—"}</b><span class="dim sm"> ${k >= 0 ? o.d.t[k] : ""}</span></span>`; }).join("") + `</div>`).join("");
  };
  setTimeout(() => legend(null), 50);
  chart.subscribeCrosshairMove(p => { const t = p?.time; legend(!t ? null : typeof t === "string" ? t : typeof t === "object" ? `${t.year}-${String(t.month).padStart(2, "0")}-${String(t.day).padStart(2, "0")}` : new Date(t * 1000).toISOString().slice(0, 10)); });
  drawCorr(md, mc, shown);
}
function setMainTitle(mc, x) {
  const el = document.getElementById("cl-legend"); if (!el) return;
  const tfl = TFS.find(t => t[0] === OV.tf)[1];
  let ohlc = "";
  if (x) { const { k, d } = x, prev = k > 0 ? d.v[k - 1] : null, ch = prev ? (d.v[k] / prev - 1) * 100 : null, col = ch == null ? "" : ch >= 0 ? "#26a69a" : "#ef5350";
    ohlc = d.o ? `<span>O <b style="color:${col}">${fmtP(d.o[k])}</b></span><span>H <b style="color:${col}">${fmtP(d.h[k])}</b></span><span>L <b style="color:${col}">${fmtP(d.l[k])}</b></span><span>C <b style="color:${col}">${fmtP(d.v[k])}</b></span>` : `<span><b style="color:${col}">${fmtP(d.v[k])}</b></span>`;
    if (ch != null) ohlc += `<span style="color:${col}">${ch >= 0 ? "+" : ""}${(d.v[k] - prev).toLocaleString("en-US", { maximumFractionDigits: Math.abs(d.v[k]) < 1 ? 6 : 2 })} (${ch >= 0 ? "+" : ""}${ch.toFixed(2)}%)</span>`;
    if (d.vol) ohlc += `<span class="dim">Vol ${fmtVol(d.vol[k])}</span>`;
    ohlc += `<span class="dim">${d.t[k]}</span>`; }
  const nm = OV.cache[OV.main]?.pair ? OV.cache[OV.main].pair.replace(/(USDT|USDC|BTC|ETH|FDUSD)$/, "/$1") : mc.name;
  el.innerHTML = `<span class="cl-sym">${esc(nm)}</span><span class="dim">${tfl} · ${esc(mc.source || "")}</span>${ohlc}`;
}
function listStatus(o) { const el = document.querySelector(`[data-cls="${CSS.escape(o.id)}"]`); if (el) el.innerHTML = o.status ? `<span class="${/loading/.test(o.status) ? "dim" : "dn"}">${esc(o.status)}</span>` : ""; }
function drawCorr(md, mc, shown) {
  const el = document.getElementById("cl-corr"); if (!el) return;
  if (!md || !shown.length) { el.innerHTML = `<div class="dim sm">Add an overlay to see how it has moved with ${esc(mc.name)}.</div>`; return; }
  const st = startDate() || "1900-01-01", mon = d => { const m = new Map(); d.t.forEach((t, i) => { if (t >= st) m.set(t.slice(0, 7), d.v[i]); }); return m; };
  const mm = mon(md), keys = [...mm.keys()].sort();
  const val = (m, k, i, c) => { if (OV.corr === "lvl") return m.get(k) ?? null; if (i < 1) return null; const a = m.get(keys[i - 1]), b = m.get(k); if (a == null || b == null) return null; return rateLike(c) || a <= 0 ? b - a : (b / a - 1) * 100; };
  el.innerHTML = `<table class="t"><thead><tr><th>Overlay</th><th class="r">Correlation with ${esc(mc.name)}</th><th class="r">Months</th></tr></thead><tbody>` + shown.map(({ o, c }) => {
    const om = mon(o.d), a = [], b = []; keys.forEach((k, i) => { const x = val(mm, k, i, mc), y = val(om, k, i, c); if (x != null && y != null) { a.push(x); b.push(y); } });
    const r = corr(a, b), bg = r == null ? "" : r > 0 ? `rgba(57,135,229,${Math.abs(r) * 0.5})` : `rgba(230,103,103,${Math.abs(r) * 0.5})`;
    return `<tr><td><span class="sw" style="background:${o.color}"></span>${esc(c.name)}</td><td class="r num" style="background:${bg}">${r == null ? "—" : r.toFixed(2)}</td><td class="r num dim">${a.length}</td></tr>`; }).join("") + `</tbody></table>
    <p class="sm dim">Over the selected range, using ${OV.corr === "lvl" ? "monthly levels" : "month-to-month changes"}. +1 = always move together, −1 = always opposite, 0 = no relation. Correlation is not causation; levels of two trending series often correlate by accident, so changes are the stricter test.</p>`;
}

/* ---------- side panel ---------- */
function ovListHtml() {
  if (!OV.ov.length) return `<div class="dim sm">No overlays. Search on the right and choose <b>On price</b> or <b>New panel</b>.</div>`;
  const panes = [...new Set(OV.ov.map(o => o.pane))].sort((a, b) => a - b), maxP = Math.max(0, ...panes);
  return OV.ov.map((o, i) => { const c = find(o.id);
    const opts = [`<option value="0"${o.pane === 0 ? " selected" : ""}>On price (own scale)</option>`, ...Array.from({ length: maxP }, (_, j) => `<option value="${j + 1}"${o.pane === j + 1 ? " selected" : ""}>Panel ${j + 1}</option>`), `<option value="new">New panel</option>`].join("");
    return `<div class="cl-row${o.hidden ? " off" : ""}"><input type="color" value="${o.color}" data-clc="${i}" title="Colour"><span class="cl-n">${esc(c ? c.name : o.id)}<div class="sm dim">${esc(c ? `${c.freq} · ${c.source}` : "")} <span data-cls="${esc(o.id)}"></span></div></span>
      <select class="cl-sel" data-clp="${i}">${opts}</select><button class="btn sm" data-clh="${i}">${o.hidden ? "Show" : "Hide"}</button><button class="btn sm" data-clx="${i}" title="Remove">✕</button></div>`; }).join("");
}
function refresh() { tidyPanes(); const l = document.getElementById("cl-list"); if (l) l.innerHTML = ovListHtml(); const n = document.getElementById("cl-count"); if (n) n.textContent = `${OV.ov.length} / ${MAX}`; bindList(); save(); draw(); }
function msg(m) { const el = document.getElementById("cl-msg"); if (el) { el.textContent = m; setTimeout(() => { if (el.textContent === m) el.textContent = ""; }, 5000); } }
function addOv(id, pane) { if (id === OV.main) return msg("That is already the main chart."); if (OV.ov.some(x => x.id === id)) return msg("Already on the chart."); if (OV.ov.length >= MAX) return msg(`Up to ${MAX} overlays. Remove one first.`);
  OV.ov.push({ id, pane: pane === "new" ? nextPane() : pane, hidden: false, color: nextColor() }); refresh(); }
function setMain(id) { OV.main = id; OV.ov = OV.ov.filter(o => o.id !== id); refresh(); const q = document.getElementById("cl-q"); if (q) q.value = ""; renderHits(); }
function bindList() {
  document.querySelectorAll("[data-clx]").forEach(b => b.onclick = () => { OV.ov.splice(+b.dataset.clx, 1); refresh(); });
  document.querySelectorAll("[data-clh]").forEach(b => b.onclick = () => { const o = OV.ov[+b.dataset.clh]; o.hidden = !o.hidden; refresh(); });
  document.querySelectorAll("[data-clc]").forEach(b => b.onchange = () => { OV.ov[+b.dataset.clc].color = b.value; refresh(); });
  document.querySelectorAll("[data-clp]").forEach(b => b.onchange = () => { const o = OV.ov[+b.dataset.clp]; o.pane = b.value === "new" ? nextPane() : +b.value; refresh(); });
}
function renderHits() {
  const res = document.getElementById("cl-res"), q = document.getElementById("cl-q"); if (!res || !q) return;
  const words = q.value.toLowerCase().split(/\s+/).filter(Boolean), cat = catalogue();
  const hits = cat.filter(c => words.every(w => (c.name + " " + c.group + " " + c.id).toLowerCase().includes(w))).slice(0, 80);
  const groups = {}; hits.forEach(h => (groups[h.group] = groups[h.group] || []).push(h));
  res.innerHTML = Object.entries(groups).map(([g, hs]) => `<div class="cl-g">${esc(g)}</div>` + hs.map(h => `<div class="cl-hit"><span>${esc(h.name)} <span class="dim sm">${esc(h.freq)}</span></span>
    <span class="cl-acts"><button class="btn sm" data-clm="${esc(h.id)}" title="Show as the main chart">Main</button><button class="btn sm" data-cla="${esc(h.id)}" data-pane="0" title="Overlay on the price chart with its own scale">On price</button><button class="btn sm" data-cla="${esc(h.id)}" data-pane="new" title="Show in its own panel below">New panel</button></span></div>`).join("")).join("") || `<div class="dim sm">No match. For any coin, type its symbol in the coin box above.</div>`;
  res.querySelectorAll("[data-cla]").forEach(b => b.onclick = () => addOv(b.dataset.cla, b.dataset.pane === "new" ? "new" : 0));
  res.querySelectorAll("[data-clm]").forEach(b => b.onclick = () => setMain(b.dataset.clm));
}
function bindTop() {
  const q = document.getElementById("cl-q"); q.oninput = renderHits; renderHits();
  const coin = document.getElementById("cl-coin"), sym = () => (coin.value || "").trim().toUpperCase().replace(/[^A-Z0-9]/g, "");
  document.getElementById("cl-coin-main").onclick = () => { const v = sym(); if (v) { setMain("bin:" + v); coin.value = ""; } };
  document.getElementById("cl-coin-ov").onclick = () => { const v = sym(); if (v) { addOv("bin:" + v, 0); coin.value = ""; } };
  coin.onkeydown = e => { if (e.key === "Enter") document.getElementById("cl-coin-main").click(); };
  document.querySelectorAll("[data-clq]").forEach(b => b.onclick = () => setMain("bin:" + b.dataset.clq));
  document.querySelectorAll("[data-clt]").forEach(b => b.onclick = () => { OV.tf = b.dataset.clt; document.querySelectorAll("[data-clt]").forEach(x => x.classList.toggle("on", x === b)); save(); draw(); });
  document.querySelectorAll("[data-clr]").forEach(b => b.onclick = () => { OV.range = b.dataset.clr; document.querySelectorAll("[data-clr]").forEach(x => x.classList.toggle("on", x === b)); save(); draw(); });
  document.querySelectorAll("[data-cly]").forEach(b => b.onclick = () => { OV.type = b.dataset.cly; document.querySelectorAll("[data-cly]").forEach(x => x.classList.toggle("on", x === b)); save(); draw(); });
  document.getElementById("cl-log").onchange = e => { OV.log = e.target.checked; save(); draw(); };
  document.getElementById("cl-vol").onchange = e => { OV.vol = e.target.checked; save(); draw(); };
  document.getElementById("cl-clear").onclick = () => { OV.ov = []; refresh(); };
  document.querySelectorAll("[data-clk]").forEach(b => b.onclick = () => { OV.corr = b.dataset.clk; document.querySelectorAll("[data-clk]").forEach(x => x.classList.toggle("on", x === b)); draw(); });
  document.getElementById("cl-copy").onclick = () => { try { navigator.clipboard.writeText(location.href); msg("Link copied: it reopens this exact chart."); } catch (e) { msg(location.href); } };
}

PAGES["tools/overlay"] = pg => {
  restore(pg.param);
  mount(async () => { await loadFile(); const l = document.getElementById("cl-list"); if (l) l.innerHTML = ovListHtml(); document.getElementById("cl-count").textContent = `${OV.ov.length} / ${MAX}`; bindList(); bindTop(); draw(); });
  const b = (attr, val, cur, label) => `<button class="btn sm${cur === val ? " on" : ""}" data-${attr}="${val}">${label}</button>`;
  return `<style>
   .cl-top{display:flex;flex-wrap:wrap;gap:6px;align-items:center;padding:8px 10px;border:1px solid #23272e;border-bottom:0;border-radius:6px 6px 0 0;background:#111418}
   .cl-top .btn{background:transparent;border-color:#2a2e35;color:#c9ccd1}.cl-top .btn.on{border-color:${C.gold};color:${C.gold};background:#1b1810}.cl-sep{width:1px;height:20px;background:#2a2e35;margin:0 4px}
   #cl-wrap{position:relative;border:1px solid #23272e;border-radius:0 0 6px 6px;overflow:hidden;background:#0d0f12}
   #cl-legend{position:absolute;left:10px;top:8px;z-index:3;display:flex;flex-wrap:wrap;gap:4px 12px;font-size:12.5px;pointer-events:none;font-variant-numeric:tabular-nums}
   #cl-legend b{font-weight:500}.cl-sym{font-weight:600;color:#e8e9eb;font-size:14px}
   #cl-ovleg{position:absolute;inset:0;z-index:3;font-size:12px;pointer-events:none}.cl-lp{position:absolute;display:flex;flex-direction:column;gap:2px;background:rgba(13,15,18,.6);padding:2px 4px;border-radius:3px}.cl-li .sw{margin-right:4px}
   .cl-row{display:grid;grid-template-columns:26px 1fr auto auto auto;gap:6px;align-items:center;padding:7px 0;border-bottom:1px solid #1d2026}.cl-row.off{opacity:.45}
   .cl-row input[type=color]{width:22px;height:22px;border:0;background:none;padding:0;cursor:pointer}
   .cl-sel,.cl-in{background:#0f1114;border:1px solid #2a2e35;color:inherit;padding:6px 8px;border-radius:4px;font:inherit}.cl-in{width:100%}
   .cl-g{margin:10px 0 4px;font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:${C.muted}}
   .cl-hit{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:5px 2px;border-bottom:1px solid #1a1d22}.cl-hit:hover{background:#15181d}
   .cl-acts{display:flex;gap:4px;flex-shrink:0}.cl-acts .btn{padding:3px 8px;font-size:11.5px}#cl-res{max-height:430px;overflow:auto}</style>` +
  header(pg, "A TradingView-style chart: pick the main symbol (shown in real prices), then add only the overlays you want, either on the price chart with their own scale or in their own panel below.") +
  `<div class="cl-top"><span class="sm dim">Interval</span>${TFS.map(([k, l]) => b("clt", k, OV.tf, l)).join("")}<span class="cl-sep"></span>
     ${RANGES.map(([k]) => b("clr", k, OV.range, k)).join("")}<span class="cl-sep"></span>${b("cly", "candles", OV.type, "Candles")}${b("cly", "line", OV.type, "Line")}
     <label class="sm"><input type="checkbox" id="cl-log" ${OV.log ? "checked" : ""}> Log</label><label class="sm"><input type="checkbox" id="cl-vol" ${OV.vol ? "checked" : ""}> Volume</label>
     <button class="btn sm" id="cl-copy" style="margin-left:auto">Copy link</button></div>
   <div id="cl-wrap"><div id="cl-legend"></div><div id="cl-ovleg"></div><div id="cl-chart" style="height:520px"></div></div>
   <div class="sm" id="cl-msg" style="color:${C.gold};min-height:18px;margin:4px 0"></div>
   <div class="g g2">${panel(`Overlays <span class="dim sm" id="cl-count"></span>`, `<div id="cl-list"></div><div style="margin-top:8px"><button class="btn sm" id="cl-clear">Remove all overlays</button></div>`)}
     ${panel("Symbols and data", `<div class="sm dim" style="margin-bottom:4px">Any coin on Binance</div><div style="display:flex;gap:6px;margin-bottom:6px"><input class="cl-in" id="cl-coin" placeholder="e.g. ETH, SOL, PEPE, ETHBTC"><button class="btn" id="cl-coin-main">Chart it</button><button class="btn" id="cl-coin-ov">Overlay</button></div>
        <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px">${CRYPTO_QUICK.slice(0, 10).map(c => `<button class="btn sm" data-clq="${c}">${c}</button>`).join("")}</div>
        <input class="cl-in" id="cl-q" placeholder="Search everything: gold, nasdaq, CPI, unemployment, fed funds, M2, yen, VIX, Japan inflation…"><div id="cl-res"></div>`)}</div>` +
  panel("How each overlay has moved with the main chart", `<div style="display:flex;gap:6px;margin-bottom:6px">${b("clk", "chg", OV.corr, "Monthly changes")}${b("clk", "lvl", OV.corr, "Levels")}</div><div id="cl-corr"></div>`) +
  `<p class="sm dim">Scroll to zoom, drag to pan, drag the line between panels to resize them. The main chart always shows real prices. An overlay "on price" gets its own scale (the first one uses the left axis); an overlay in a panel uses that panel's right axis. Weekly bars run Monday to Sunday and are dated by the Monday; candles use the period's open, high, low and close. Monthly and quarterly data (CPI, unemployment, rates) keep their real release dates and are drawn as steps. Sources: Binance (crypto, loaded live from 2017), Yahoo Finance (10 years daily), FRED, OECD, BIS, IMF.</p>`;
};
})();
