/* SOVEREIGN core: data, navigation, routing, components, charts. Pages live in pages.js. */
"use strict";
const S = { data: null, ref: {}, asset: lsGet("sov.asset", "XAU"), mounts: [], charts: [] };
const C = { bull: "#3987e5", bear: "#e66767", gold: "#c6a052", ink: "#ebe8e1", ink2: "#a7abb3", muted: "#727780",
  grid: "#1b1e24", axis: "#2b3038", mid: "#383835", s1: "#3987e5", s2: "#eb6834", s3: "#199e70", s4: "#c98500", s5: "#9085e9" };

function lsGet(k, d) { try { return localStorage.getItem(k) ?? d; } catch { return d; } }
function lsSet(k, v) { try { localStorage.setItem(k, v); } catch { /* storage unavailable */ } }
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (v, d = 2) => v == null || isNaN(v) ? "—" : Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
const fmt0 = v => fmt(v, 0);
const sgn = (v, d = 0) => v == null || isNaN(v) ? "—" : (v > 0 ? "+" : "") + Number(v).toFixed(d);
const pct = (v, d = 2) => v == null ? `<span class="dim">—</span>` : `<span class="num ${v > 0 ? "up" : v < 0 ? "dn" : ""}">${v > 0 ? "+" : ""}${Number(v).toFixed(d)}%</span>`;
const A = sym => S.data.assets.find(a => a.symbol === sym);
const assetName = sym => sym === "XAU" ? "Gold" : "Bitcoin";
const pxFmt = (sym, v) => fmt(v, sym === "BTC" ? 0 : 2);

/* ---------------- navigation ---------------- */
const NAV = [
  ["command", "A", "Command Centre", [["global-dashboard", "Global Markets Dashboard"], ["dashboard", "Gold & Bitcoin Dashboard"], ["market-overview", "Market Overview"], ["what-changed", "What Changed Today?"], ["calendar", "Global Economic Calendar"], ["alerts", "Intelligence Alerts"], ["briefings", "Research Briefings"]]],
  ["economies", "B", "Global Economies", [["comparison", "Economic Comparison"], ["monthly", "Monthly Indicators (OECD)"], ["us", "United States"], ["cn", "China"], ["jp", "Japan"], ["de", "Germany"], ["fr", "France"], ["in", "India"], ["gb", "United Kingdom"], ["ca", "Canada"], ["ch", "Switzerland"], ["ru", "Russia"]]],
  ["equities", "C", "Global Equities", [["dashboard", "Global Equity Dashboard"], ["americas", "Americas"], ["europe", "Europe"], ["asia", "Asia-Pacific"], ["index", "Index Detail"], ["valuation", "Valuation & Fundamentals"], ["sectors", "Sector Intelligence"]]],
  ["currencies", "D", "Currency Intelligence", [["dashboard", "Currency Dashboard"], ["ranking", "Currency Strength Ranking"], ["relative", "Relative Strength Matrix"], ["detail", "Currency Detail"], ["valuation", "Valuation: PPP & REER"], ["differentials", "Rate & Inflation Differentials"], ["positioning", "Positioning & Volatility"], ["asset-matrix", "Currency vs Asset Matrix"]]],
  ["commodities", "E", "Commodity Intelligence", [["overview", "Commodity Dashboard"], ["energy", "Energy"], ["metals", "Metals"], ["agriculture", "Agriculture"], ["detail", "Commodity Detail"], ["fundamentals", "Supply & Demand Fundamentals", 1]]],
  ["fiscal", "F", "Government & Fiscal", [["comparison", "Fiscal Comparison"], ["debt", "Debt & Deficits"], ["revenue", "Revenue & Expenditure"], ["spending", "Interest, Defence & Subsidies"], ["sovereign-risk", "Sovereign Credit Risk"], ["country", "Country Fiscal Profile"], ["debt-structure", "Debt Maturity & Ownership", 1]]],
  ["trade", "G", "International Trade", [["overview", "Trade Overview"], ["partners", "Top Trading Partners"], ["bilateral", "Bilateral Trade Matrix"], ["products", "Products & Concentration"], ["dependency", "Strategic Dependencies"], ["tariffs", "Tariffs & Restrictions"]]],
  ["flows", "H", "Capital & Investment Flows", [["overview", "Capital Flow Overview"], ["map", "World Investment Map"], ["investor", "By Investor Country"], ["destination", "By Destination Country"], ["positions", "Flows vs Positions"], ["iip", "International Investment Position"], ["tic", "Foreign Holders of US Treasuries"], ["banking", "Cross-Border Banking"], ["institutions", "Sovereign Wealth & Pension Funds", 1]]],
  ["corporate", "I", "Corporate Intelligence", [["database", "Corporate Database"], ["company", "Company Profile"], ["coverage", "Coverage by Country"], ["exposure", "Investment Exposure Report"], ["country-reports", "Country Investment Reports"]]],
  ["credit", "J", "Credit & Banking", [["overview", "Credit & Banking Overview"], ["private-credit", "Private Sector Credit"], ["banks", "Bank Health"], ["spreads", "Credit Spreads & High Yield"], ["stress", "Banking Stress Indicators"]]],
  ["relationships", "K", "Macro Relationship Engine", [["overview", "Relationship Engine"], ["usd-commodities", "USD → Commodities"], ["real-yields-gold", "Real Yields → Gold"], ["china-copper", "China Industry → Copper"], ["japan-tightening", "BoJ Tightening → Capital Flows"], ["europe-germany", "Europe Industry → German Equities"], ["oil-india", "Oil → India"], ["us-deficit", "US Deficit → Treasury Yields"], ["fdi-currency", "Foreign Investment → FX & Equities"], ["explorer", "Relationship Explorer"]]],
  ["gold", "L", "Gold Intelligence", [["overview", "Gold Overview"], ["fundamentals", "Gold Fundamental Analysis"], ["supply", "Global Gold Supply", 1], ["demand", "Global Gold Demand"], ["balance", "Gold Supply & Demand Balance", 1], ["nowcast", "Daily / Weekly Gold Nowcasting"], ["mining", "Gold Mining Intelligence", 1], ["cost-curve", "Mining Cost Curve", 1], ["central-banks", "Central Bank Gold Reserves"], ["etf", "Gold ETF Intelligence"], ["trade", "International Gold Trade", 1], ["physical", "Gold Physical Market", 1], ["technical", "Gold Technical Analysis"], ["scenarios", "Gold Price Scenarios"]]],
  ["bitcoin", "M", "Bitcoin Intelligence", [["overview", "Bitcoin Overview"], ["fundamentals", "Bitcoin Fundamentals"], ["network", "Bitcoin Network Intelligence"], ["mining", "Bitcoin Mining Intelligence"], ["miner-economics", "Bitcoin Miner Economics"], ["etf", "Bitcoin ETF Flows"], ["corporate", "Corporate Bitcoin Holdings", 1], ["exchanges", "Exchange Reserves & Flows"], ["whales", "Whale & Institutional Activity", 1], ["technical", "Bitcoin Technical Analysis"], ["scenarios", "Bitcoin Price Scenarios"]]],
  ["macro", "N", "US Macro Intelligence", [["central-banks", "Central Bank Policies"], ["rates", "Interest Rates"], ["yields", "Government Bond Yields"], ["real-rates", "Real Interest Rates"], ["inflation", "Inflation"], ["dxy", "US Dollar Index"], ["liquidity", "Global Liquidity"], ["growth", "Economic Growth"], ["employment", "Employment"], ["recession", "Recession Indicators"], ["geopolitics", "Geopolitical Intelligence"]]],
  ["institutional", "O", "Institutional Intelligence", [["cb-activity", "Central Bank Activity"], ["investments", "Institutional Investments"], ["company-financials", "Public Company Financials"], ["balance-sheets", "Corporate Balance Sheets"], ["holdings", "Institutional Asset Holdings"], ["ownership", "Ownership Changes", 1], ["flows", "Major Investment Flows"]]],
  ["quant", "P", "Quantitative Research", [["historical", "Historical Market Analysis"], ["correlations", "Asset Correlations"], ["volatility", "Volatility Analysis"], ["statistics", "Statistical Research"], ["regimes", "Market Regimes"], ["backtesting", "Backtesting"], ["scenario-modelling", "Scenario Modelling"], ["forecast-accuracy", "Forecast Accuracy"]]],
  ["technical", "Q", "Technical Intelligence", [["multi-timeframe", "Multi-Timeframe Charts"], ["structure", "Market Structure"], ["support-resistance", "Support & Resistance"], ["trend", "Trend Analysis"], ["momentum", "Momentum Indicators"], ["volume", "Volume Analysis"], ["liquidity", "Liquidity Analysis"], ["signals", "Technical Signals & Confirmations"]]],
  ["decision", "R", "Decision Intelligence", [["fundamental-scores", "Fundamental Scores"], ["technical-scores", "Technical Scores"], ["combined", "Combined Intelligence Score"], ["short", "Short-Term Outlook"], ["medium", "Medium-Term Outlook"], ["long", "Long-Term Outlook"], ["scenarios", "Bullish / Base / Bearish Scenarios"], ["forecast-history", "Forecast History"], ["confidence", "Model Confidence"]]],
  ["tools", "S", "Trading Tools", [["overlay", "Chart Lab (TradingView-style)"], ["position-size", "Position Size Calculator"], ["risk", "Risk Management Calculator"], ["risk-reward", "Risk-to-Reward Calculator"], ["leverage", "Leverage & Margin Calculator"], ["dca", "DCA Calculator"], ["average-entry", "Average Entry Calculator"], ["compounding", "Compounding Calculator"], ["multi-trade", "Multi-Trade Risk Simulator"]]],
  ["platform", "T", "Platform", [["coverage", "Data Coverage & Transparency"], ["methodology", "Research Methodology"], ["sources", "Data Sources"], ["models", "Model Documentation"], ["data-quality", "Data Quality & Reliability"], ["about", "About SOVEREIGN"], ["settings", "Settings"]]],
];
const PAGES = {}; // filled by pages.js: PAGES["gold/overview"] = ctx => html
const allPages = () => NAV.flatMap(([sec, code, stitle, items]) => items.map(([id, title, pend]) => ({ sec, code, stitle, id, title, pend, key: `${sec}/${id}` })));

function buildNav() {
  const closed = JSON.parse(lsGet("sov.closed", "[]"));
  document.getElementById("side").innerHTML = NAV.map(([sec, code, title, items]) => `
    <div class="grp ${closed.includes(sec) ? "closed" : ""}" data-sec="${sec}">
      <button class="grp-h" aria-expanded="${!closed.includes(sec)}"><span class="code">${code}</span>${esc(title)}<span class="chev">▾</span></button>
      <div class="items">${items.map(([id, t, pend]) => `<a href="#/${sec}/${id}" data-key="${sec}/${id}">${esc(t)}${pend ? `<span class="pend" title="Data collection pending">pending</span>` : ""}</a>`).join("")}</div>
    </div>`).join("");
  document.querySelectorAll(".grp-h").forEach(b => b.onclick = () => {
    const g = b.parentElement; g.classList.toggle("closed"); b.setAttribute("aria-expanded", !g.classList.contains("closed"));
    lsSet("sov.closed", JSON.stringify([...document.querySelectorAll(".grp.closed")].map(x => x.dataset.sec)));
  });
}

function buildSearch() {
  const q = document.getElementById("q"), res = document.getElementById("qres"), pages = allPages();
  let sel = 0, hits = [];
  const draw = () => { res.innerHTML = hits.map((p, i) => `<a href="#/${p.key}" class="${i === sel ? "on" : ""}">${esc(p.title)}<small>${esc(p.stitle)}</small></a>`).join(""); res.style.display = hits.length ? "block" : "none"; };
  q.oninput = () => { const t = q.value.toLowerCase().trim(); sel = 0; hits = t ? pages.filter(p => (p.title + " " + p.stitle).toLowerCase().includes(t)).slice(0, 12) : []; draw(); };
  q.onkeydown = e => {
    if (e.key === "ArrowDown") { sel = Math.min(sel + 1, hits.length - 1); draw(); e.preventDefault(); }
    if (e.key === "ArrowUp") { sel = Math.max(sel - 1, 0); draw(); e.preventDefault(); }
    if (e.key === "Enter" && hits[sel]) { location.hash = `#/${hits[sel].key}`; q.value = ""; hits = []; draw(); q.blur(); }
    if (e.key === "Escape") { q.value = ""; hits = []; draw(); q.blur(); }
  };
  q.onblur = () => setTimeout(() => { res.style.display = "none"; }, 150);
  document.addEventListener("keydown", e => { if (e.key === "/" && document.activeElement.tagName !== "INPUT") { e.preventDefault(); q.focus(); } });
}

function buildTicker() {
  const d = S.data, m = d.macro || {};
  const items = d.assets.map(a => `<span class="tk"><b>${a.symbol === "XAU" ? "XAU/USD" : "BTC/USD"}</b><span class="num">${pxFmt(a.symbol, a.performance.last)}</span>${pct(a.performance.d1)}</span>`);
  [["DFII10", "US10Y REAL", "%"], ["DGS2", "US2Y", "%"], ["DGS10", "US10Y", "%"], ["DTWEXBGS", "USD BROAD", ""]].forEach(([k, lab, u]) => {
    const l = m[k] && m[k].latest; if (!l) return;
    items.push(`<span class="tk"><b>${lab}</b><span class="num">${fmt(l.last, 2)}${u}</span><span class="num ${l.chg_1w > 0 ? "up" : l.chg_1w < 0 ? "dn" : ""}">${sgn(l.chg_1w, 2)} 1w</span></span>`);
  });
  document.getElementById("ticker").innerHTML = items.join("");
  const fresh = d.mode === "live";
  document.getElementById("stamp").innerHTML = `<span class="dot" style="background:${fresh ? "var(--good)" : "var(--warn)"}"></span>Updated ${esc(d.generated_at)}`;
}

/* ---------------- routing ---------------- */
function route() {
  const parts = (location.hash.replace(/^#\/?/, "") || "command/global-dashboard").split("/");
  const key = parts.slice(0, 2).join("/");
  const base = allPages().find(p => p.key === key) || allPages()[0];
  const page = { ...base, param: parts.length > 2 ? decodeURIComponent(parts.slice(2).join("/")) : null };
  document.querySelectorAll(".items a").forEach(a => a.classList.toggle("on", a.dataset.key === page.key));
  const grp = document.querySelector(`.grp[data-sec="${page.sec}"]`); if (grp) grp.classList.remove("closed");
  document.body.classList.remove("nav-open");
  S.charts.forEach(c => { try { c.remove(); } catch { /* chart already removed */ } }); S.charts = []; S.mounts = [];
  const fn = PAGES[page.key];
  let html;
  try { html = fn ? fn(page) : pendingPage(page, {}); }
  catch (e) { console.error(e); html = header(page) + `<div class="pending">This page could not be drawn from the current data file: ${esc(e.message)}</div>`; }
  const modelSec = ["decision", "technical"].includes(page.sec) || ["gold/overview", "bitcoin/overview", "command/dashboard", "gold/nowcast", "quant/scenario-modelling", "quant/backtesting", "quant/regimes"].includes(page.key);
  if (modelSec && typeof MODEL_NOTE !== "undefined") html = html.includes("<!--/ph-->") ? html.replace("<!--/ph-->", MODEL_NOTE) : MODEL_NOTE + html;
  if (typeof MODEL_NOTE !== "undefined") { const i = html.indexOf(MODEL_NOTE); if (i >= 0) html = html.slice(0, i + MODEL_NOTE.length) + html.slice(i + MODEL_NOTE.length).split(MODEL_NOTE).join(""); }   // show the note once per page
  document.getElementById("main").innerHTML = html + footer();
  document.title = `${page.title} — SOVEREIGN`;
  window.scrollTo(0, 0);
  whenLWC(() => S.mounts.forEach(f => { try { f(); } catch (e) { console.error(e); } }));
  document.querySelectorAll("[data-asset]").forEach(b => b.onclick = () => { S.asset = b.dataset.asset; lsSet("sov.asset", S.asset); route(); });
}
function whenLWC(cb) { if (window.LightweightCharts) cb(); else window.addEventListener("load", cb, { once: true }); }
const mount = f => S.mounts.push(f);

/* ---------------- components ---------------- */
let UID = 0; const uid = () => "c" + (++UID);
function header(page, lede = "", opts = {}) {
  const toggle = opts.asset ? `<div class="seg" role="group" aria-label="Asset">${["XAU", "BTC"].map(s => `<button data-asset="${s}" class="${S.asset === s ? "on" : ""}">${assetName(s)}</button>`).join("")}</div>` : "";
  return `<div class="ph"><div><div class="crumb"><b>${page.code}</b> · ${esc(page.stitle)}</div><h1>${esc(page.title)}</h1>${lede ? `<p class="lede">${lede}</p>` : ""}</div>${toggle}${opts.right || ""}</div><!--/ph-->`;
}
const panel = (title, body, meta = "", cls = "") => `<section class="p ${cls}">${title ? `<div class="p-h"><h2>${title}</h2>${meta ? `<span class="meta">${meta}</span>` : ""}</div>` : ""}<div class="p-b ${cls.includes("flush") ? "flush" : ""}">${body}</div></section>`;
const kpi = (k, v, s = "") => `<section class="p kpi"><div class="k">${k}</div><div class="v">${v}</div><div class="s">${s}</div></section>`;
function table(cols, rows, opts = {}) {
  return `<div class="tw"${opts.max ? ` style="max-height:${opts.max}px;overflow:auto"` : ""}><table><thead><tr>${cols.map(c => `<th class="${c.n ? "n" : ""}">${c.t ?? c}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${r.map((v, i) => `<td class="${cols[i] && cols[i].n ? "n" : ""}">${v ?? "—"}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
const why = (g, b) => `<div class="why"><div><div class="k">Why it matters for gold</div>${g}</div><div><div class="k">Why it matters for Bitcoin</div>${b}</div></div>`;
const src = list => list && list.length ? `<div class="src">Source: ${list.map(([t, u]) => u ? `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(t)}</a>` : esc(t)).join(" · ")}</div>` : "";
const chip = (t, gold) => `<span class="chip ${gold ? "gold" : ""}">${esc(t)}</span>`;
function labClass(l) { l = (l || "").toLowerCase(); return l.includes("bull") ? "bull" : l.includes("bear") ? "bear" : "neu"; }
const labelHtml = l => `<span class="lab ${labClass(l)}">${esc(l)}</span>`;
function sbar(v, max = 100) {
  if (v == null) return `<div class="sbar"><span class="z"></span></div>`;
  const w = Math.min(Math.abs(v), max) / max * 50, pos = v >= 0;
  return `<div class="sbar" role="img" aria-label="score ${sgn(v)}"><i style="${pos ? "left:50%" : `left:${50 - w}%`};width:${w}%;background:${pos ? C.bull : C.bear};border-radius:${pos ? "0 4px 4px 0" : "4px 0 0 4px"}"></i><span class="z"></span></div>`;
}
const scoreRow = (v, max = 100, d = 0) => `<div class="score">${sbar(v, max)}<span class="val">${sgn(v, d)}</span></div>`;
function statusPill(s) { const m = { Fresh: "good", Stale: "warn", Missing: "crit", "Insufficient history": "warn", Good: "good", Fair: "warn", Poor: "crit", High: "good", Medium: "warn", Low: "crit" }; return `<span class="pill ${m[s] || ""}">${esc(s)}</span>`; }
function pendingPage(page, o) {
  return header(page, o.lede || "", { asset: o.asset }) + (o.why ? why(o.why[0], o.why[1]) : "") +
    `<div class="pending"><b>Data collection pending.</b> ${o.what || "This page is part of the SOVEREIGN structure; its data feed is not connected yet."}
     ${o.fields ? `<div style="margin-top:8px"><b>Will show:</b> ${o.fields}</div>` : ""}
     ${o.source ? `<div style="margin-top:6px"><b>Planned source:</b> ${o.source}</div>` : ""}
     <div style="margin-top:6px"><b>Phase:</b> ${o.phase || "Phase 1 (data layer)"}. Nothing on this page is estimated or invented while the feed is missing.</div></div>` +
    (o.related ? `<div style="margin-top:12px">${o.related}</div>` : "");
}
function footer() {
  const d = S.data;
  return `<div class="foot"><span>SOVEREIGN — Intelligence Without Influence. Research tool; not investment advice.</span><span>Data as of ${esc(d.as_of)} · ${esc(d.mode)} build · ${esc(d.generated_at)}</span></div>`;
}
function tipAt(e, html) { const t = document.getElementById("tip"); t.innerHTML = html; t.style.display = "block"; const x = Math.min(e.clientX + 14, innerWidth - t.offsetWidth - 8), y = Math.min(e.clientY + 14, innerHeight - t.offsetHeight - 8); t.style.left = x + "px"; t.style.top = y + "px"; }
function tipOff() { document.getElementById("tip").style.display = "none"; }

/* ---------------- charts ---------------- */
function niceTicks(lo, hi, n = 4) {
  const span = hi - lo || 1, step0 = span / n, mag = Math.pow(10, Math.floor(Math.log10(step0))), r = step0 / mag;
  const step = (r < 1.5 ? 1 : r < 3 ? 2 : r < 7 ? 5 : 10) * mag, out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}
/** Multi-series time line chart in SVG with a crosshair tooltip. series: [{name, dates, values, color}] */
function lineChart(series, o = {}) {
  const id = uid(), H = o.height || 220;
  mount(() => {
    const el = document.getElementById(id); if (!el) return;
    const W = Math.max(320, el.clientWidth), L = 52, R = o.rightPad ?? 14, T = 10, B = 22;
    const ss = series.filter(s => s.values && s.values.length);
    if (!ss.length) { el.innerHTML = `<div class="dim sm" style="padding:20px 0">No data available yet.</div>`; return; }
    const pts = ss.map(s => s.dates.map((d, i) => [Date.parse(d), s.values[i]]).filter(p => p[1] != null));
    const xs = pts.flat().map(p => p[0]), ys = pts.flat().map(p => p[1]).concat(o.zero ? [0] : []).concat(o.refs ? o.refs.map(r => r.v) : []);
    const x0 = Math.min(...xs), x1 = Math.max(...xs); let y0 = Math.min(...ys), y1 = Math.max(...ys); const pad = (y1 - y0) * 0.06 || 1; y0 -= pad; y1 += pad;
    const X = t => L + (t - x0) / ((x1 - x0) || 1) * (W - L - R), Y = v => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B);
    const yt = niceTicks(y0, y1, 4), f = o.fmt || (v => fmt(v, Math.abs(y1 - y0) < 10 ? 2 : 0));
    const xt = [x0, x0 + (x1 - x0) / 3, x0 + 2 * (x1 - x0) / 3, x1];
    const dlab = t => new Date(t).toISOString().slice(0, 7);
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.title || ss.map(s => s.name).join(", "))}">`;
    yt.forEach(v => { svg += `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="${C.grid}"/><text x="${L - 6}" y="${Y(v) + 3}" text-anchor="end">${f(v)}</text>`; });
    xt.forEach(t => { svg += `<text x="${X(t)}" y="${H - 6}" text-anchor="middle">${dlab(t)}</text>`; });
    if (o.zero && y0 < 0 && y1 > 0) svg += `<line x1="${L}" x2="${W - R}" y1="${Y(0)}" y2="${Y(0)}" stroke="#555a63"/>`;
    (o.refs || []).forEach(r => { svg += `<line x1="${L}" x2="${W - R}" y1="${Y(r.v)}" y2="${Y(r.v)}" stroke="#555a63" stroke-dasharray="3 4"/><text x="${W - R}" y="${Y(r.v) - 4}" text-anchor="end">${esc(r.label)}</text>`; });
    pts.forEach((p, i) => {
      const d = p.map((q, j) => (j ? "L" : "M") + X(q[0]).toFixed(1) + " " + Y(q[1]).toFixed(1)).join("");
      if (o.area && i === 0) svg += `<path d="${d}L${X(p[p.length - 1][0])} ${Y(Math.max(y0, 0 > y0 && 0 < y1 ? 0 : y0))}L${X(p[0][0])} ${Y(Math.max(y0, 0 > y0 && 0 < y1 ? 0 : y0))}Z" fill="${ss[i].color || C.gold}" opacity=".08"/>`;
      svg += `<path d="${d}" fill="none" stroke="${ss[i].color || C.gold}" stroke-width="${ss[i].width || 1.75}" stroke-linejoin="round"${ss[i].dash ? ` stroke-dasharray="${ss[i].dash}"` : ""}/>`;
    });
    svg += `<line class="ch" y1="${T}" y2="${H - B}" stroke="#6b6f77" style="display:none"/>${pts.map((_, i) => `<circle class="cd${i}" r="3.5" fill="${ss[i].color || C.gold}" stroke="#101216" stroke-width="2" style="display:none"/>`).join("")}
      <rect x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="transparent" class="hit"/></svg>`;
    el.innerHTML = (ss.length > 1 ? `<div class="legend">${ss.map(s => `<span><span class="sw" style="background:${s.color}"></span>${esc(s.name)}</span>`).join("")}</div>` : "") + svg;
    const sv = el.querySelector("svg"), ch = sv.querySelector(".ch");
    sv.querySelector(".hit").addEventListener("mousemove", e => {
      const r = sv.getBoundingClientRect(), t = x0 + ((e.clientX - r.left) * W / r.width - L) / (W - L - R) * (x1 - x0);
      ch.setAttribute("x1", X(t)); ch.setAttribute("x2", X(t)); ch.style.display = "block";
      let rows = "";
      pts.forEach((p, i) => { let best = p[0]; for (const q of p) if (Math.abs(q[0] - t) < Math.abs(best[0] - t)) best = q; const c = sv.querySelector(".cd" + i); c.setAttribute("cx", X(best[0])); c.setAttribute("cy", Y(best[1])); c.style.display = "block"; rows += `<div>${ss.length > 1 ? `<span class="sw" style="background:${ss[i].color}"></span>${esc(ss[i].name)}: ` : ""}<b class="num">${f(best[1])}${o.unit || ""}</b></div>`; });
      tipAt(e, `<div class="dim">${new Date(t).toISOString().slice(0, 10)}</div>${rows}`);
    });
    sv.querySelector(".hit").addEventListener("mouseleave", () => { ch.style.display = "none"; sv.querySelectorAll("circle").forEach(c => c.style.display = "none"); tipOff(); });
  });
  return `<div class="chart" id="${id}" style="min-height:${H}px"></div>`;
}
/** Vertical bars; diverging colours around zero when o.diverging. */
function barChart(labels, values, o = {}) {
  const id = uid(), H = o.height || 200;
  mount(() => {
    const el = document.getElementById(id); if (!el) return;
    const W = Math.max(300, el.clientWidth), L = 48, R = 8, T = 10, B = 24, n = values.length;
    let y0 = Math.min(0, ...values.filter(v => v != null)), y1 = Math.max(0, ...values.filter(v => v != null)); const pad = (y1 - y0) * 0.08 || 1; y0 -= y0 < 0 ? pad : 0; y1 += pad;
    const Y = v => T + (1 - (v - y0) / (y1 - y0)) * (H - T - B), bw = (W - L - R) / n, f = o.fmt || (v => fmt(v, 0));
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.title || "bar chart")}">`;
    niceTicks(y0, y1, 4).forEach(v => { svg += `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="${C.grid}"/><text x="${L - 6}" y="${Y(v) + 3}" text-anchor="end">${f(v)}</text>`; });
    values.forEach((v, i) => {
      if (v == null) return; const x = L + i * bw + Math.max(1, bw * 0.14), w = Math.max(1, bw * 0.72), y = Y(Math.max(v, 0)), h = Math.abs(Y(v) - Y(0));
      const col = o.diverging ? (v >= 0 ? C.bull : C.bear) : (o.color || C.gold);
      svg += `<rect x="${x}" y="${y}" width="${w}" height="${Math.max(h, 1)}" fill="${col}" rx="2" data-i="${i}"/>`;
    });
    svg += `<line x1="${L}" x2="${W - R}" y1="${Y(0)}" y2="${Y(0)}" stroke="#555a63"/>`;
    const every = Math.ceil(n / Math.max(1, Math.floor((W - L) / 64)));
    labels.forEach((l, i) => { if (i % every === 0) svg += `<text x="${L + i * bw + bw / 2}" y="${H - 6}" text-anchor="middle">${esc(l)}</text>`; });
    el.innerHTML = svg + "</svg>";
    el.querySelectorAll("rect[data-i]").forEach(r => { r.addEventListener("mousemove", e => { const i = +r.dataset.i; tipAt(e, `<div class="dim">${esc(labels[i])}</div><b class="num">${f(values[i])}${o.unit || ""}</b>`); }); r.addEventListener("mouseleave", tipOff); });
  });
  return `<div class="chart" id="${id}" style="min-height:${H}px"></div>`;
}
/** Correlation heatmap, diverging blue (+) / red (−). */
function heatmap(keys, m) {
  const id = uid();
  mount(() => {
    const el = document.getElementById(id); if (!el) return;
    const n = keys.length, cell = Math.min(64, Math.max(34, (el.clientWidth - 110) / n)), L = 104, T = 8, W = L + n * cell + 4, H = T + n * cell + 64;
    const col = v => { if (v == null) return "#16191e"; const a = Math.min(1, Math.abs(v)); const c = v >= 0 ? [57, 135, 229] : [230, 103, 103]; return `rgba(${c[0]},${c[1]},${c[2]},${0.12 + a * 0.78})`; };
    let svg = `<svg viewBox="0 0 ${W} ${H}" style="max-width:${W}px" role="img" aria-label="Correlation matrix">`;
    keys.forEach((k, i) => { svg += `<text x="${L - 8}" y="${T + i * cell + cell / 2 + 4}" text-anchor="end">${esc(k)}</text>`; svg += `<text transform="translate(${L + i * cell + cell / 2},${T + n * cell + 10}) rotate(40)" text-anchor="start">${esc(k)}</text>`; });
    m.forEach((row, i) => row.forEach((v, j) => { svg += `<rect x="${L + j * cell + 1}" y="${T + i * cell + 1}" width="${cell - 2}" height="${cell - 2}" fill="${col(v)}" rx="2" data-v="${v}" data-a="${esc(keys[i])}" data-b="${esc(keys[j])}"/>`; if (v != null) svg += `<text x="${L + j * cell + cell / 2}" y="${T + i * cell + cell / 2 + 4}" text-anchor="middle" style="fill:${Math.abs(v) > 0.55 ? "#fff" : C.ink2};font-family:var(--mono)">${v.toFixed(2)}</text>`; }));
    el.innerHTML = svg + "</svg>";
    el.querySelectorAll("rect[data-a]").forEach(r => { r.addEventListener("mousemove", e => tipAt(e, `${r.dataset.a} vs ${r.dataset.b}<br><b class="num">${r.dataset.v === "null" ? "n/a" : (+r.dataset.v).toFixed(2)}</b>`)); r.addEventListener("mouseleave", tipOff); });
  });
  return `<div class="chart" id="${id}"></div>`;
}
/** Price chart (TradingView Lightweight Charts): candles when OHLC is real, else a line. */
function priceChart(asset, o = {}) {
  const id = uid();
  mount(() => {
    const el = document.getElementById(id); if (!el || !window.LightweightCharts) { if (el) el.innerHTML = `<div class="dim sm">Chart library unavailable.</div>`; return; }
    let rows = asset.ohlc.slice(-(o.days || 400));
    if (o.weekly) rows = toWeekly(rows);
    const chart = LightweightCharts.createChart(el, { autoSize: true, layout: { background: { color: "transparent" }, textColor: C.muted, fontFamily: "IBM Plex Sans, system-ui", fontSize: 11 },
      grid: { vertLines: { color: "#15181d" }, horzLines: { color: "#15181d" } }, rightPriceScale: { borderColor: C.axis }, timeScale: { borderColor: C.axis }, crosshair: { mode: 0 } });
    S.charts.push(chart);
    const real = rows.some(r => r[2] !== r[3]);
    let main;
    if (real) { main = chart.addCandlestickSeries({ upColor: C.bull, downColor: C.bear, borderVisible: false, wickUpColor: C.bull, wickDownColor: C.bear }); main.setData(rows.map(r => ({ time: r[0], open: r[1], high: r[2], low: r[3], close: r[4] }))); }
    else { main = chart.addLineSeries({ color: C.gold, lineWidth: 2, priceLineVisible: false }); main.setData(rows.map(r => ({ time: r[0], value: r[4] }))); }
    if (!o.weekly && o.ma !== false) {
      const ds = asset.technicals.daily_series, dates = ds.dates;
      [["sma50", "#9085e9", "50-day"], ["sma200", "#a7abb3", "200-day"]].forEach(([k, c]) => { const s = chart.addLineSeries({ color: c, lineWidth: 1, priceLineVisible: false, lastValueVisible: false }); s.setData(dates.map((d, i) => ({ time: d, value: ds[k][i] })).filter(p => p.value != null && p.time >= rows[0][0])); });
    }
    if (o.levels !== false) {
      (asset.levels.support || []).forEach((l, i) => main.createPriceLine({ price: l.price, color: C.bull, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "S" + (i + 1) }));
      (asset.levels.resistance || []).forEach((l, i) => main.createPriceLine({ price: l.price, color: C.bear, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "R" + (i + 1) }));
    }
    if (o.volume && rows.some(r => r[5] > 0)) { const v = chart.addHistogramSeries({ priceScaleId: "", priceFormat: { type: "volume" }, color: "#2b3038" }); chart.priceScale("").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } }); v.setData(rows.map(r => ({ time: r[0], value: r[5], color: r[4] >= r[1] ? "rgba(57,135,229,.35)" : "rgba(230,103,103,.35)" }))); }
    chart.timeScale().fitContent();
  });
  const legend = o.ma === false || o.weekly ? "" : `<div class="legend"><span><span class="sw" style="background:#9085e9"></span>50-day average</span><span><span class="sw" style="background:#a7abb3"></span>200-day average</span><span><span class="sw" style="background:${C.bull}"></span>Support</span><span><span class="sw" style="background:${C.bear}"></span>Resistance</span></div>`;
  return legend + `<div class="lwc" id="${id}" style="height:${o.height || 380}px"></div>`;
}
function toWeekly(rows) {
  const out = []; let cur = null;
  rows.forEach(r => { const d = new Date(r[0] + "T00:00:00Z"), wk = new Date(d); wk.setUTCDate(d.getUTCDate() + ((5 - d.getUTCDay() + 7) % 7)); const k = wk.toISOString().slice(0, 10);
    if (!cur || cur[0] !== k) { cur && out.push(cur); cur = [k, r[1], r[2], r[3], r[4], r[5]]; } else { cur[2] = Math.max(cur[2], r[2]); cur[3] = Math.min(cur[3], r[3]); cur[4] = r[4]; cur[5] += r[5]; } });
  cur && out.push(cur); return out;
}

/* ---------------- boot ---------------- */
async function boot() {
  buildNav(); buildSearch();
  document.getElementById("menuBtn").onclick = () => document.body.classList.toggle("nav-open");
  try { S.data = await (await fetch("data/sovereign.json", { cache: "no-cache" })).json(); }
  catch (e) { document.getElementById("main").innerHTML = `<div class="pending"><b>Data file not found.</b> The daily build writes data/sovereign.json. ${esc(e.message)}</div>`; return; }
  try { S.G = await (await fetch("data/global.json", { cache: "no-cache" })).json(); } catch { S.G = null; }
  const refs = ["calendar", "central_banks", "gold_market", "btc_market", "geopolitics", "briefings"];
  await Promise.all(refs.map(async r => { try { S.ref[r] = await (await fetch(`reference/${r}.json`, { cache: "no-cache" })).json(); } catch { S.ref[r] = null; } }));
  buildTicker();
  window.addEventListener("hashchange", route);
  route();
}
