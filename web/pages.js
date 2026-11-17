/* SOVEREIGN page renderers. Every number comes from data/sovereign.json (engine) or reference/*.json (sourced, hand-entered). */
"use strict";
const HZ = [["short", "Short term", "1–5 days"], ["medium", "Medium term", "1–4 weeks"], ["long", "Long term", "1–12 months"]];
const R = n => S.ref[n] || {};
const cur = () => A(S.asset);

/* ---------- shared blocks ---------- */
function perfLine(a) { const p = a.performance; return `<span>1D ${pct(p.d1)}</span><span>1W ${pct(p.w1)}</span><span>1M ${pct(p.m1)}</span><span>YTD ${pct(p.ytd)}</span>`; }
function priceKpi(a) { return kpi(`${assetName(a.symbol)} · ${a.symbol}/USD`, pxFmt(a.symbol, a.performance.last), perfLine(a)); }
function decKpi(a, hz = "medium") { const d = a.decision[hz]; return kpi(`${assetName(a.symbol)} · combined (${hz})`, `<span class="lab ${labClass(d.label)}">${sgn(d.combined)}</span>`, `${labelHtml(d.label)}${d.contested ? " · contested" : ""} · confidence ${d.confidence.label}`); }
function driverTable(a, layers) {
  const rows = a.drivers.filter(d => !layers || layers.includes(d.layer)).sort((x, y) => (y.signal == null ? -9 : Math.abs(y.signal * y.weight)) - (x.signal == null ? -9 : Math.abs(x.signal * x.weight)));
  return table([{ t: "Driver" }, { t: "Latest reading" }, { t: "Signal (−2 to +2)" }, { t: "Weight", n: 1 }, { t: "Status" }], rows.map(d => [
    `<div>${esc(d.name)}</div>${chip("Layer " + d.layer)}${chip(d.evidence_class)}`,
    d.signal == null ? `<span class="dim">${esc(d.note || "not collected")}</span>` : `<div class="num sm">${esc(d.reading)}</div><div class="src">${esc(d.as_of || "")} · ${d.source_url ? `<a href="${esc(d.source_url)}" target="_blank" rel="noopener">${esc(d.source_name)}</a>` : esc(d.source_name)}</div>`,
    d.signal == null ? "" : scoreRow(d.signal, 2, 1), `${Math.round(d.weight * 100)}%`,
    d.signal == null ? statusPill("Missing") : `<span class="sm dim">bullish when ${esc(d.bullish_when.toLowerCase())}</span>`]));
}
function decisionMatrix(assets = S.data.assets, field = "combined") {
  return table([{ t: "Asset" }, ...HZ.map(([, t, s]) => ({ t: `${t} <span class="dim">(${s})</span>` }))], assets.map(a => [
    `<b>${assetName(a.symbol)}</b>`, ...HZ.map(([k]) => { const d = a.decision[k]; const v = d[field]; return `${scoreRow(v)}<div class="sm" style="margin-top:3px">${field === "combined" ? labelHtml(d.label) + (d.contested ? ` <span class="dim">· contested</span>` : "") : `<span class="dim">${esc(field)}</span>`}</div>`; })]));
}
function outlookCard(o, a) {
  const d = a.decision[o.key];
  return panel(`${esc(o.horizon)}`, `<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:6px">${labelHtml(o.label)}<span class="num">${sgn(o.combined)}</span></div>${sbar(o.combined)}
    <p style="margin:10px 0">${esc(o.thesis)}</p>${chip(o.evidence_class)}${chip("Confidence " + d.confidence.label + " (" + d.confidence.value + ")", true)}
    <div class="g g2" style="margin:10px 0 0"><div><h3>Supporting</h3>${listOr(o.supports)}</div><div><h3>Contradicting</h3>${listOr(o.contradicts)}</div>
    <div><h3>Would invalidate</h3>${listOr(o.invalidation)}</div><div><h3>Would confirm</h3>${listOr(o.confirmation)}</div></div>`, `${assetName(a.symbol)}`);
}
const listOr = (l, empty = "None at present.") => l && l.length ? `<ul class="clean">${l.map(x => `<li>${typeof x === "string" ? esc(x) : x}</li>`).join("")}</ul>` : `<span class="dim sm">${empty}</span>`;
function levelsTable(a) {
  const l = a.levels, p = a.performance.last, rows = [], nm = (k, b) => `<b>${k}</b>${b ? `<div class="sm dim">${esc(b)}</div>` : ""}`;
  (l.resistance || []).slice().reverse().forEach((x, i, arr) => rows.push([nm(`R${arr.length - i}`, x.label), `<span class="num">${pxFmt(a.symbol, x.price)}</span>`, pct((x.price / p - 1) * 100, 1)]));
  rows.push([nm("Last", a.performance.date), `<b class="num">${pxFmt(a.symbol, p)}</b>`, ""]);
  (l.support || []).forEach((x, i) => rows.push([nm(`S${i + 1}`, x.label), `<span class="num">${pxFmt(a.symbol, x.price)}</span>`, pct((x.price / p - 1) * 100, 1)]));
  if (l.sma200) rows.push([nm("200-day average"), `<span class="num">${pxFmt(a.symbol, l.sma200)}</span>`, pct((l.sma200 / p - 1) * 100, 1)]);
  rows.push([nm("52-week range"), `<span class="num">${pxFmt(a.symbol, l.low_52w)}<br>${pxFmt(a.symbol, l.high_52w)}</span>`, ""]);
  return table([{ t: "Level" }, { t: "Price", n: 1 }, { t: "From last", n: 1 }], rows);
}
function refRows(block, cols) { return block && block.rows ? table(cols, block.rows.map(r => r.map(c => esc(typeof c === "number" ? fmt(c, 1) : c)))) + src(block.sources) : `<span class="dim">Not available.</span>`; }
function seriesOf(key) { const m = S.data.macro[key]; return m && m.series && m.series.values.length ? m : null; }
function macroLatestRow(key) { const m = S.data.macro[key]; if (!m || !m.latest) return null; const l = m.latest; return [esc(m.label), `<span class="num">${fmt(l.last, 2)}</span>`, `<span class="num">${sgn(l.chg_1m, 2)}</span>`, `<span class="num">${sgn(l.chg_3m, 2)}</span>`, `<span class="dim sm">${esc(l.date)}</span>`]; }
const needKey = `Requires the free FRED API key: the FRED website blocks GitHub's servers. Add it under repository Settings → Secrets → Actions as <span class="mono">FRED_API_KEY</span>.`;
function yoy(m) { if (!m) return null; const d = m.series.dates, v = m.series.values, out = { dates: [], values: [] }; for (let i = 12; i < v.length; i++) { out.dates.push(d[i]); out.values.push(+((v[i] / v[i - 12] - 1) * 100).toFixed(2)); } return out; }

/* ======================= A. COMMAND CENTRE ======================= */
PAGES["command/dashboard"] = pg => {
  const g = A("XAU"), b = A("BTC"), m = S.data.macro;
  const macroRows = ["DFII10", "DGS2", "DGS10", "DTWEXBGS", "NETLIQ"].map(macroLatestRow).filter(Boolean);
  const cb = R("central_banks").banks || [], cal = (R("calendar").events || []).filter(e => e.date >= S.data.as_of);
  const gm = R("gold_market"), bm = R("btc_market"), geo = R("geopolitics").items || [], br = R("briefings").items || [];
  const wc = a => a.what_changed;
  const mv = (x, dir) => `${dir} ${x.driver}: ${sgn(x.from, 1)} → ${sgn(x.to, 1)}`;
  const changed = [g, b].map(a => { const w = wc(a), day = [...w.developments, ...w.model, ...w.deteriorating.slice(0, 2).map(x => mv(x, "▼")), ...w.improving.slice(0, 2).map(x => mv(x, "▲"))];
    const week = [...w.deteriorating_7d.slice(0, 3).map(x => mv(x, "▼")), ...w.improving_7d.slice(0, 3).map(x => mv(x, "▲"))];
    return `<div><h3>${assetName(a.symbol)}</h3>${day.length ? listOr(day.slice(0, 5)) : `<div class="sm dim" style="margin-bottom:4px">No material change since the ${esc(w.basis)}. Over the past week:</div>` + listOr(week, "No driver moved by 0.3 or more.")}</div>`; }).join("");
  return header(pg, `The platform's current reading of gold and Bitcoin across macro, fundamental and technical evidence. Scores run from −100 to +100.`) +
    `<div class="g g4">${priceKpi(g)}${priceKpi(b)}${decKpi(g)}${decKpi(b)}</div>
     <div class="g g-32">${panel("Combined intelligence score", decisionMatrix() + `<div class="note">Combined = macro, fundamental and technical scores blended by horizon (see Decision Intelligence → Combined). Contested means drivers or components disagree.</div>`, `<a href="#/decision/combined">Detail →</a>`)}
       ${panel("Market trend and sentiment", table([{ t: "" }, { t: "Gold" }, { t: "Bitcoin" }], [
         ["Daily trend", esc(g.technicals.daily.trend.label), esc(b.technicals.daily.trend.label)],
         ["Weekly trend", esc(g.technicals.weekly.trend.label), esc(b.technicals.weekly.trend.label)],
         ["Technical sentiment", scoreRow(g.decision.medium.technical), scoreRow(b.decision.medium.technical)],
         ["Fundamental sentiment", scoreRow(g.decision.medium.fundamental), scoreRow(b.decision.medium.fundamental)],
         ["Macro conditions", scoreRow(g.decision.medium.macro), scoreRow(b.decision.medium.macro)],
         ["Regime", `<span class="sm">${esc(g.regime.current)}</span>`, `<span class="sm">${esc(b.regime.current)}</span>`]]), "medium term")}</div>
     ${panel("What changed today?", `<div class="g g2" style="margin:0">${changed}</div><div class="note">Compared with the ${esc(g.what_changed.basis)}. <a href="#/command/what-changed">Full breakdown →</a></div>`)}
     <div class="g g3" style="margin-top:12px">
       ${panel("Global macro conditions", macroRows.length ? table([{ t: "Indicator" }, { t: "Latest", n: 1 }, { t: "1M chg", n: 1 }, { t: "3M chg", n: 1 }, { t: "As of" }], macroRows) : `<span class="dim">No macro data.</span>`, `<a href="#/macro/real-rates">Macro →</a>`)}
       ${panel("Central bank developments", `<div class="lst">${cb.slice(0, 4).map(x => `<div><b>${esc(x.bank)}</b> <span class="num dim">${esc(x.rate)}</span><div class="sm">${esc(x.last_move)}</div><div class="sm dim">${esc(x.market)}</div></div>`).join("")}</div>`, `as of ${esc(R("central_banks").as_of || "")}`)}
       ${panel("Upcoming events", cal.length ? `<div class="lst">${cal.slice(0, 5).map(e => `<div><span class="num">${esc(e.date)}</span> · <b>${esc(e.event)}</b> ${chip(e.importance)}<div class="sm dim">${esc(e.why)}</div></div>`).join("")}</div>` : `<span class="dim">No confirmed events in the calendar file.</span>`, `<a href="#/command/calendar">Calendar →</a>`)}
     </div>
     <div class="g g3">
       ${panel("Gold ETF flows", gm.etf_monthly ? table([{ t: "Month" }, { t: "Flow" }, { t: "Value" }, { t: "Note" }], gm.etf_monthly.rows.map(r => r.map(esc))) + src(gm.etf_monthly.sources) : "—", "WGC")}
       ${panel("Bitcoin ETF flows", bm.etf_monthly ? barChart(bm.etf_monthly.rows.map(r => r[0]), bm.etf_monthly.rows.map(r => r[1]), { diverging: true, height: 150, unit: " $m", fmt: v => fmt(v, 0) }) + `<div class="sm" style="margin-top:6px">${esc(bm.etf_recent.rows[0][0])}: <b>${esc(bm.etf_recent.rows[0][1])}</b>; ${esc(bm.etf_recent.rows[1][0])}: <b>${esc(bm.etf_recent.rows[1][1])}</b></div>` + src(bm.etf_monthly.sources) : "—", "US spot ETFs, $m")}
       ${panel("Institutional activity", `<div class="lst">
          ${gm.wgc_q3_2026 ? `<div><b>Central banks</b> bought 321 t of gold in Q3 2026 (+42% y/y).${src([gm.wgc_q3_2026.sources[0]])}</div>` : ""}
          <div><b>Gold futures</b>: managed money net long ${fmt(g.drivers.find(d => d.key === "cot")?.raw_value, 1)}% of open interest (${esc(g.drivers.find(d => d.key === "cot")?.as_of || "")}).${src([["CFTC", "https://publicreporting.cftc.gov/"]])}</div>
          ${(bm.corporate_notes || []).slice(0, 1).map(n => `<div>${esc(n.text)}${src([n.source])}</div>`).join("")}</div>`)}
     </div>
     <div class="g g2">
       ${panel("Geopolitical developments", `<div class="lst">${geo.map(x => `<div><span class="num dim">${esc(x.date)}</span> · <b>${esc(x.headline)}</b><div class="sm"><span class="dim">Gold:</span> ${esc(x.gold)} <span class="dim">Bitcoin:</span> ${esc(x.bitcoin)}</div>${src([x.source])}</div>`).join("") || `<span class="dim">None recorded.</span>`}</div>`, `<a href="#/macro/geopolitics">More →</a>`)}
       ${panel("Latest research", `<div class="lst">${br.map(x => `<div><span class="num dim">${esc(x.date)}</span> · <b>${esc(x.title)}</b> ${chip(x.author)}<div class="sm">${esc(x.body[0])}</div></div>`).join("")}</div>`, `<a href="#/command/briefings">Briefings →</a>`)}
     </div>`;
};

PAGES["command/market-overview"] = pg => {
  const rows = S.data.assets.map(a => { const p = a.performance, t = a.technicals.daily; return [`<b>${assetName(a.symbol)}</b> <span class="dim">${a.symbol}/USD</span>`, `<span class="num">${pxFmt(a.symbol, p.last)}</span>`, pct(p.d1), pct(p.w1), pct(p.m1), pct(p.m3), pct(p.ytd), pct(p.y1), esc(t.trend.label), `<span class="num">${fmt(t.rsi, 0)}</span>`, `<span class="num">${fmt(a.volatility.vol30, 1)}%</span>`, `<span class="sm">${esc(a.regime.current)}</span>`]; });
  const macro = ["DFII10", "DGS2", "DGS10", "T10Y2Y", "DTWEXBGS", "NETLIQ"].map(macroLatestRow).filter(Boolean);
  return header(pg, "Prices, performance, trend and volatility for every covered market, with the main macro gauges.") +
    panel("Assets", table([{ t: "Market" }, { t: "Last", n: 1 }, { t: "1D", n: 1 }, { t: "1W", n: 1 }, { t: "1M", n: 1 }, { t: "3M", n: 1 }, { t: "YTD", n: 1 }, { t: "1Y", n: 1 }, { t: "Trend" }, { t: "RSI", n: 1 }, { t: "Vol 30d", n: 1 }, { t: "Regime" }], rows), "", "flush") +
    `<div class="g g2" style="margin-top:12px">${S.data.assets.map(a => panel(`${assetName(a.symbol)}, 1 year`, lineChart([{ name: assetName(a.symbol), dates: a.ohlc.slice(-365).map(r => r[0]), values: a.ohlc.slice(-365).map(r => r[4]), color: C.gold }], { height: 200, area: true }))).join("")}</div>` +
    panel("Macro gauges", macro.length ? table([{ t: "Indicator" }, { t: "Latest", n: 1 }, { t: "1M chg", n: 1 }, { t: "3M chg", n: 1 }, { t: "As of" }], macro) : `<span class="dim">${needKey}</span>`) +
    `<div class="note">Equities, silver, oil and FX are planned additions (spec section 9); they will appear here as rows when added.</div>`;
};

PAGES["command/what-changed"] = pg => header(pg, "New developments, improving and deteriorating indicators, sentiment and model changes since the last assessment.") +
  S.data.assets.map(a => { const w = a.what_changed, ch = x => `${esc(x.driver)} <span class="num dim">${sgn(x.from, 2)} → ${sgn(x.to, 2)}</span>`;
    return `<div class="g g3">${panel(`${assetName(a.symbol)}: important new developments`, listOr(w.developments, "No new developments flagged."), `vs ${esc(w.basis)}`)}
      ${panel("Indicators improving (more bullish)", listOr(w.improving.map(ch), `None moved by 0.3 or more since the ${esc(w.basis)}.`) + (w.basis === "previous run" ? `<h3 style="margin-top:10px">Over 7 days</h3>` + listOr(w.improving_7d.map(ch), "None.") : ""))}
      ${panel("Indicators deteriorating (more bearish)", listOr(w.deteriorating.map(ch), `None moved by 0.3 or more since the ${esc(w.basis)}.`) + (w.basis === "previous run" ? `<h3 style="margin-top:10px">Over 7 days</h3>` + listOr(w.deteriorating_7d.map(ch), "None.") : ""))}</div>
      <div class="g g3">${panel("Changes in market sentiment", listOr(w.sentiment, "Technical score broadly unchanged."))}
      ${panel("Changes in model outlook", listOr(w.model, w.basis === "previous run" ? "No label changes." : "First run on record: label changes appear from the next daily run."))}
      ${panel("Three developments to monitor", `<ol style="margin:0;padding-left:18px">${w.monitor.map(x => `<li style="margin:4px 0">${esc(x)}</li>`).join("")}</ol>`, "", "")}</div>`; }).join("");

PAGES["command/calendar"] = pg => { const ev = R("calendar").events || [];
  return header(pg, "Scheduled events that move rates, the dollar, gold and Bitcoin.") +
    panel("Confirmed events", ev.length ? table([{ t: "Date" }, { t: "Event" }, { t: "Region" }, { t: "Importance" }, { t: "Why it matters" }, { t: "Source" }], ev.map(e => [`<span class="num">${esc(e.date)}${e.end ? "–" + esc(e.end.slice(8)) : ""}</span>`, `<b>${esc(e.event)}</b>`, esc(e.region), chip(e.importance), esc(e.why), `<a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.source)}</a>`])) : `<span class="dim">No events.</span>`) +
    `<div class="pending" style="margin-top:12px"><b>Full calendar feed pending.</b> Only events confirmed by the issuing institution are listed. A complete calendar (CPI, payrolls, PCE, ECB, BoE, BoJ, WGC releases, Bitcoin difficulty adjustments) needs a calendar data feed (Phase 1). Add confirmed rows to <span class="mono">reference/calendar.json</span>.</div>`; };

PAGES["command/alerts"] = pg => { const al = S.data.assets.flatMap(a => a.alerts), fe = Object.entries(S.data.feed_errors || {});
  const order = { High: 0, Medium: 1, Info: 2 };
  return header(pg, "Rule-based alerts raised by today's run: extreme driver readings, outlook changes, price near key levels and low confidence.") +
    panel(`Active alerts (${al.length})`, al.length ? table([{ t: "Severity" }, { t: "Asset" }, { t: "Alert" }], al.sort((x, y) => order[x.severity] - order[y.severity]).map(x => [statusPill(x.severity === "High" ? "Poor" : x.severity === "Medium" ? "Fair" : "Good").replace(/>(Poor|Fair|Good)</, `>${x.severity}<`), assetName(x.asset), esc(x.text)])) : `<span class="dim">No alerts.</span>`) +
    `<div style="margin-top:12px">${panel(`Data feed alerts (${fe.length})`, fe.length ? table([{ t: "Series" }, { t: "Problem" }], fe.map(([k, v]) => [`<span class="mono">${esc(k)}</span>`, `<span class="sm">${esc(v)}</span>`])) : "All feeds loaded.")}</div>
     <div class="note">Rules: driver signal beyond ±1.5; outlook label change since the last run; price within 1% of the nearest support or resistance; confidence below 45. Telegram/email delivery is Phase 3.</div>`; };

PAGES["command/briefings"] = pg => { const br = R("briefings").items || [];
  return header(pg, "Dated research notes. Analyst notes are AI interpretation of cited evidence; engine summaries are rule-based model output.") +
    br.map(x => panel(esc(x.title), `${chip(x.author, true)}${x.body.map(p => `<p style="margin:6px 0">${esc(p)}</p>`).join("")}${src(x.sources)}`, esc(x.date))).join(`<div style="height:12px"></div>`) +
    `<h2 style="margin:18px 0 10px">Engine summaries (today)</h2><div class="g g2">${S.data.assets.map(a => panel(assetName(a.symbol), a.outlooks.map(o => `<div style="margin-bottom:8px"><b>${esc(o.horizon)}:</b> ${labelHtml(o.label)} <span class="num">${sgn(o.combined)}</span><div class="sm">${esc(o.thesis)}</div></div>`).join(""), "Model output")).join("")}</div>`; };

/* ======================= B / C. ASSET PAGES ======================= */
function overviewPage(pg, sym) {
  const a = A(sym), mo = a.outlooks.find(o => o.key === "medium");
  const top = a.drivers.filter(d => d.signal != null).sort((x, y) => Math.abs(y.signal * y.weight) - Math.abs(x.signal * x.weight)).slice(0, 5);
  return header(pg, `${assetName(sym)} at a glance: price, the platform's three-horizon view, the drivers that matter most and the levels that matter technically.`) +
    `<div class="g g4">${priceKpi(a)}${HZ.map(([k, t]) => { const d = a.decision[k]; return kpi(`${t}`, `<span class="lab ${labClass(d.label)}">${sgn(d.combined)}</span>`, `${labelHtml(d.label)} · conf. ${d.confidence.label}`); }).join("")}</div>
     <div class="g g-21">${panel("Price", priceChart(a, { days: 365 }), esc(a.price_source))}${panel("Key levels", levelsTable(a))}</div>
     <div class="g g2">${panel("Strongest drivers now", table([{ t: "Driver" }, { t: "Signal" }], top.map(d => [esc(d.name), scoreRow(d.signal, 2, 1)])) + `<div class="note"><a href="#/${sym === "XAU" ? "gold" : "bitcoin"}/fundamentals">Full scorecard →</a></div>`)}
       ${outlookCard(mo, a)}</div>`;
}
function fundamentalsPage(pg, sym, charts) {
  const a = A(sym);
  return header(pg, `Every driver in the ${assetName(sym)} scorecard, its latest reading and its signal against its own 3-year history.`) +
    `<div class="g g4">${HZ.map(([k, t]) => kpi(`${t} · fundamental`, sgn(a.decision[k].fundamental), `macro ${sgn(a.decision[k].macro)} · coverage ${Math.round((a.decision[k].coverage || 0) * 100)}%`)).join("")}${kpi("Data quality", `${a.data_quality.score}`, statusPill(a.data_quality.label))}</div>` +
    panel("Driver scorecard", driverTable(a), "sorted by weighted contribution", "flush") +
    `<div class="g g2" style="margin-top:12px">${panel("Contradictions", listOr(a.contradictions))}${panel("Week-on-week signal changes", listOr(a.weekly_changes, "No driver moved by 0.5 or more."))}</div>` + (charts || "");
}
function technicalPage(pg, a) {
  const t = a.technicals;
  return header(pg, `Price structure, trend, momentum and the levels that matter for ${assetName(a.symbol)}.`) +
    `<div class="g g4">${kpi("Technical score (daily)", sgn(t.daily.score), esc(t.daily.trend.label))}${kpi("Technical score (weekly)", sgn(t.weekly.score), esc(t.weekly.trend.label))}${kpi("RSI (14, daily)", fmt(t.daily.rsi, 0), "above 70 overbought · below 30 oversold")}${kpi("Volatility (30d, annualised)", fmt(a.volatility.vol30, 1) + "%", `percentile ${fmt(a.volatility.vol30_pct_rank, 0)} of 2 years`)}</div>` +
    `<div class="g g-21">${panel("Daily chart", priceChart(a, { days: 400, volume: true }), esc(a.price_source))}${panel("Key levels", levelsTable(a))}</div>` +
    panel("Signals and confirmations", signalsTable(a)) +
    `<div class="g g2" style="margin-top:12px">${panel("Market structure", `<dl class="kv"><dt>Daily</dt><dd>${esc(t.daily.structure.label)}<div class="sm dim">${esc(t.daily.structure.detail)}</div></dd><dt>Weekly</dt><dd>${esc(t.weekly.structure.label)}<div class="sm dim">${esc(t.weekly.structure.detail)}</div></dd></dl>`)}
      ${panel("Momentum", rsiChart(a))}</div>`;
}
function signalsTable(a) { return table([{ t: "Signal" }, { t: "State" }, { t: "Bias" }, { t: "Detail" }], a.technicals.daily.signals.map(s => [esc(s.name), `<b>${esc(s.state)}</b>`, s.bias > 0 ? `<span class="lab bull">Bullish</span>` : s.bias < 0 ? `<span class="lab bear">Bearish</span>` : `<span class="dim">Neutral / reference</span>`, `<span class="sm">${esc(s.detail)}</span>`])); }
function rsiChart(a, h = 170) { const ds = a.technicals.daily_series; return lineChart([{ name: "RSI (14)", dates: ds.dates.slice(-250), values: ds.rsi.slice(-250), color: C.gold }], { height: h, refs: [{ v: 70, label: "70" }, { v: 30, label: "30" }], fmt: v => fmt(v, 0) }); }
function scenariosPage(pg, sym) {
  const a = A(sym);
  return header(pg, `Bullish, base and bearish scenarios for ${assetName(sym)} defined by conditions, not by price targets or probabilities. Levels are technical references only.`) +
    `<div class="g g3">${a.scenarios.map(s => panel(esc(s.name), `<h3>Assumptions</h3>${listOr(s.assumptions)}<h3 style="margin-top:10px">Technical path</h3><p class="sm" style="margin:0">${esc(s.technical_path)}</p><h3 style="margin-top:10px">What to watch</h3><p class="sm" style="margin:0">${esc(s.watch)}</p>`, s.name === "Base" ? "current readings persist" : "")).join("")}</div>` +
    panel("Current combined view", decisionMatrix([a])) +
    `<div class="note">SOVEREIGN does not publish price targets or scenario probabilities. Calibrated probabilities need a scored forecast history first (see Quantitative Research → Forecast Accuracy).</div>`;
}

/* ---- Gold ---- */
PAGES["gold/overview"] = pg => overviewPage(pg, "XAU");
PAGES["gold/fundamentals"] = pg => { const a = A("XAU"), cot = a.series.cot, ry = seriesOf("DFII10");
  return fundamentalsPage(pg, "XAU", `<div class="g g2">${panel("CFTC managed money net long, % of open interest", lineChart([{ name: "Net long % OI", dates: cot ? cot.dates : [], values: cot ? cot.values : [], color: C.gold }], { height: 200, fmt: v => fmt(v, 0), unit: "%" }), "weekly, CFTC")}${panel("US 10y real yield", ry ? lineChart([{ name: "Real yield", dates: ry.series.dates.slice(-750), values: ry.series.values.slice(-750), color: C.s1 }], { height: 200, unit: "%" }) : needKey, "daily")}</div>`); };
PAGES["gold/supply"] = pg => pendingPage(pg, { lede: "Global mine production, top producing countries and recycling.", why: ["Supply responds slowly to price; mine output grows about 1% a year, so recycling swings with price and is the faster lever.", "Not directly relevant; included for the cross-asset view of scarcity."],
  what: "Mine production by country and recycled supply are published quarterly (WGC) and annually (USGS); none of these are entered yet.", fields: "global mine production (t), top 10 producing countries, recycling (t), net producer hedging, year-on-year change", source: "WGC Gold Demand Trends supply tables (quarterly); USGS Mineral Commodity Summaries (annual)" });
PAGES["gold/demand"] = pg => { const gm = R("gold_market");
  return header(pg, "Official quarterly demand from the World Gold Council, by sector. These are estimates published with a delay of about one month after the quarter.") +
    why("Central bank and ETF demand set the marginal price when jewellery demand falls on high prices.", "Gold ETF and central bank flows show whether reserve managers prefer gold, a signal Bitcoin bulls often contrast against.") +
    `<div class="g g-21">${panel(esc(gm.wgc_q3_2026?.period || "Latest quarter"), refRows(gm.wgc_q3_2026, [{ t: "Measure" }, { t: "Value" }, { t: "Context" }]), esc(gm.wgc_q3_2026?.class || ""))}
     ${panel("Central bank buyers, Q3 2026", refRows(gm.central_banks_q3_2026, [{ t: "Buyer" }, { t: "Amount" }, { t: "Note" }]))}</div>` +
    `<div class="pending"><b>Pending:</b> jewellery and technology demand by country and a quarterly history table (WGC data download). Jewellery tonnage for Q3 2026 has not been entered.</div>`; };
PAGES["gold/balance"] = pg => pendingPage(pg, { lede: "Quarterly supply minus demand, and what the gap implies for price.", what: "The balance needs both sides. Q3 2026 demand (1,369 t incl. OTC) is entered; the supply side is not, so no balance is shown.", fields: "supply (mine + recycling + hedging) vs demand (jewellery, technology, investment, central banks), surplus/deficit by quarter, price response", source: "WGC Gold Demand Trends (quarterly)", related: panel("Demand side available", refRows(R("gold_market").wgc_q3_2026, [{ t: "Measure" }, { t: "Value" }, { t: "Context" }])) });
PAGES["gold/nowcast"] = pg => { const a = A("XAU"), cot = a.drivers.find(d => d.key === "cot"), cs = a.series.cot, gm = R("gold_market"), ry = S.data.macro.DFII10?.latest, usd = S.data.macro.DTWEXBGS?.latest;
  const cotChg = cs && cs.values.length > 4 ? cs.values[cs.values.length - 1] - cs.values[cs.values.length - 5] : null;
  const rows = [
    ["Managed money positioning (CFTC)", "Weekly", cot?.raw_value != null ? `${fmt(cot.raw_value, 1)}% of OI` : "—", cotChg == null ? "—" : `${sgn(cotChg, 1)} pp over 4 weeks`, cotChg == null ? "" : cotChg > 0 ? `<span class="lab bull">Stronger</span>` : `<span class="lab bear">Weaker</span>`, "Fact", cot?.as_of || ""],
    ["Gold ETF holdings (global)", "Monthly", "4,275 t (record)", "+19 t in October", `<span class="lab bull">Stronger</span>`, "Fact", "2026-10-31"],
    ["US 10y real yield", "Daily", ry ? `${fmt(ry.last, 2)}%` : "—", ry ? `${sgn(ry.chg_1m, 2)} pp over 1 month` : "—", ry ? (ry.chg_1m > 0 ? `<span class="lab bear">Headwind</span>` : `<span class="lab bull">Tailwind</span>`) : "", "Fact", ry?.date || ""],
    ["Broad US dollar", "Daily", usd ? fmt(usd.last, 2) : "—", usd ? `${sgn(usd.chg_1m, 2)} over 1 month` : "Requires FRED key", usd ? (usd.chg_1m > 0 ? `<span class="lab bear">Headwind</span>` : `<span class="lab bull">Tailwind</span>`) : "", "Fact", usd?.date || ""],
    ["Price momentum (1 month)", "Daily", pxFmt("XAU", a.performance.last), pct(a.performance.m1), a.performance.m1 > 0 ? `<span class="lab bull">Stronger</span>` : `<span class="lab bear">Weaker</span>`, "Fact", a.performance.date],
    ["COMEX inventories", "Daily", "—", "Pending feed", "", "Fact", ""],
    ["Shanghai premium / India discount", "Daily–weekly", "—", "Pending feed", "", "Fact", ""]];
  return header(pg, "High-frequency proxies for gold investment and physical demand between quarterly official releases.") +
    `<div class="pending" style="margin-bottom:12px"><b>Official vs high-frequency.</b> Official supply and demand statistics (WGC, Metals Focus) are quarterly and arrive about a month after the quarter ends. The rows below are <b>proxies</b> that move daily or weekly. SOVEREIGN never converts them into daily tonnage estimates of physical supply or demand.</div>` +
    `<div class="g g-21">${panel("High-frequency proxies", table([{ t: "Proxy" }, { t: "Frequency" }, { t: "Latest" }, { t: "Change" }, { t: "Read-through" }, { t: "Class" }, { t: "As of" }], rows))}
      ${panel("Last official quarter", refRows(gm.wgc_q3_2026, [{ t: "Measure" }, { t: "Value" }, { t: "Context" }]), "Q3 2026, published 3 Nov")}</div>` +
    panel("Positioning history", lineChart([{ name: "Managed money net long % OI", dates: cs ? cs.dates.slice(-160) : [], values: cs ? cs.values.slice(-160) : [], color: C.gold }], { height: 190, unit: "%", fmt: v => fmt(v, 0) }));
};
PAGES["gold/mining"] = pg => pendingPage(pg, { lede: "Production, costs and profitability of the major listed gold miners.", why: ["Miner margins show whether the industry can sustain supply at current prices; rising all-in costs lift the long-run price floor.", "Gold miners and Bitcoin miners face the same margin squeeze logic: price vs all-in cost decides who keeps producing."],
  what: "Company data comes from quarterly filings and has not been entered yet.", fields: "production volume, AISC, cash cost, realised gold price, EBITDA, operating profit, free cash flow, capex, debt and cash, reserves, mine life; history and peer comparison (Newmont, Barrick, Agnico Eagle, AngloGold Ashanti, Gold Fields, Kinross)", source: "SEC EDGAR filings (10-Q, 40-F, 6-K) and company quarterly reports" });
PAGES["gold/cost-curve"] = pg => pendingPage(pg, { lede: "Global all-in sustaining cost curve: how much production is profitable at each gold price.", what: "Needs mine-level AISC and production; not yet entered.", fields: "cumulative production (x) vs AISC per ounce (y), current price line, share of production under water", source: "Company filings; mine-level disclosures. Commercial cost-curve data (S&P, Metals Focus) needs a licence." });
PAGES["gold/central-banks"] = pg => { const gm = R("gold_market"), a = A("XAU"), cb = a.drivers.find(d => d.key === "cb");
  return header(pg, "Official sector buying and reserves. WGC figures include an estimate of unreported buying.") +
    why("Central banks have been the steadiest buyer since 2022; their buying is price-insensitive and sets a floor under dips.", "Reserve diversification away from the dollar is the same theme that supports the 'digital gold' case, though no central bank holds Bitcoin at scale.") +
    `<div class="g g3">${kpi("Q3 2026 net purchases", "321 t", "+42% y/y · most since Q4 2024")}${kpi("Year to date (Q1–Q3)", "675 t", "+6% y/y")}${kpi("Scorecard driver", cb?.signal == null ? "Not scored" : sgn(cb.signal, 1), cb?.signal == null ? esc(cb?.note || "") : "")}</div>` +
    `<div class="g g2">${panel("Largest reported buyers, Q3 2026", refRows(gm.central_banks_q3_2026, [{ t: "Buyer" }, { t: "Amount" }, { t: "Note" }]))}
      <div class="pending"><b>Pending:</b> reserves by country (IMF IFS), monthly reported changes and the top-20 holders table. The central bank driver needs 60+ quarters of history in <span class="mono">manual_inputs/cb_purchases.csv</span> before it is scored.</div></div>`; };
PAGES["gold/etf"] = pg => { const gm = R("gold_market"), a = A("XAU"), d = a.drivers.find(x => x.key === "etf");
  return header(pg, "Holdings and flows of physically backed gold ETFs worldwide.") +
    why("ETF flows are the clearest daily read on Western investment demand.", "Gold and Bitcoin ETFs compete for the same 'alternative asset' allocation; diverging flows show which story investors prefer.") +
    `<div class="g g3">${kpi("Global holdings", "4,275 t", "record, end of October 2026")}${kpi("October flow", "+19 t", "US$2.7bn · Europe led")}${kpi("Q3 2026 flow", "211 t", "record US$31bn quarter")}</div>` +
    panel("Monthly flows", refRows(gm.etf_monthly, [{ t: "Month" }, { t: "Flow" }, { t: "Value" }, { t: "Note" }])) +
    `<div class="pending" style="margin-top:12px"><b>Scorecard driver:</b> ${d?.signal == null ? "not scored yet" : sgn(d.signal, 1)}. Daily holdings in tonnes go in <span class="mono">manual_inputs/gold_etf_tonnes.csv</span> (date,value). Issuer pages (SPDR GLD, iShares IAU) publish daily tonnes.</div>`; };
PAGES["gold/trade"] = pg => pendingPage(pg, { lede: "Imports and exports by country (HS 7108).", why: ["Flows into China, India, Switzerland and Türkiye show where physical demand is moving.", "No direct link; useful for the 'East vs West' demand picture."], what: "Trade data is monthly with a 1–3 month lag and not yet collected.", fields: "top 10 importers and exporters, Swiss refinery flows, China and India imports", source: "UN Comtrade API; Swiss Federal Customs; India Ministry of Commerce" });
PAGES["gold/physical"] = pg => pendingPage(pg, { lede: "COMEX and LBMA inventories, Shanghai Gold Exchange indicators, physical premiums and recycling.", what: "No physical-market feed is connected yet.", fields: "COMEX registered and eligible stocks, LBMA vault holdings, SGE premium and withdrawals, India premium/discount, recycling", source: "CME daily warehouse report; LBMA monthly vault data; SGE releases", related: `<div class="note">India bar and coin demand was 55 t in Q3 2026 (−40% y/y) and the PBoC reported buying for an eighth quarter. ${src([["WGC GDT Q3 2026: Investment", "https://www.gold.org/goldhub/research/gold-demand-trends/gold-demand-trends-q3-2026/investment"]])}</div>` });
PAGES["gold/technical"] = pg => technicalPage(pg, A("XAU"));
PAGES["gold/scenarios"] = pg => scenariosPage(pg, "XAU");

/* ---- Bitcoin ---- */
PAGES["bitcoin/overview"] = pg => overviewPage(pg, "BTC");
PAGES["bitcoin/fundamentals"] = pg => { const a = A("BTC"), mv = a.series.mvrv, fu = a.series.funding;
  return fundamentalsPage(pg, "BTC", `<div class="g g2">${panel("MVRV ratio", lineChart([{ name: "MVRV", dates: mv ? mv.dates.slice(-1000) : [], values: mv ? mv.values.slice(-1000) : [], color: C.gold }], { height: 200, refs: [{ v: 1, label: "1.0" }] }), "Coin Metrics")}${panel("Perpetual funding, 7-day average", lineChart([{ name: "Funding %", dates: fu ? fu.dates : [], values: fu ? fu.values : [], color: C.s2 }], { height: 200, zero: true, fmt: v => fmt(v, 3), unit: "%" }), "per 8 hours")}</div>`); };
PAGES["bitcoin/network"] = pg => { const a = A("BTC"), hr = a.series.hashrate, iss = R("btc_market").issuance || {};
  return header(pg, "Network security, issuance and activity.") +
    why("Not directly relevant to gold.", "Hashrate measures the capital committed to securing the network; falling hashrate with falling price signals miner stress and possible selling.") +
    `<div class="g g4">${kpi("Hashrate (daily avg)", hr ? fmt(hr.values[hr.values.length - 1], 0) + " EH/s" : "—", esc(hr ? hr.dates[hr.dates.length - 1] : ""))}${kpi("Block subsidy", `${iss.subsidy_btc ?? 3.125} BTC`, esc(iss.since || ""))}${kpi("New supply per day", `${fmt((iss.subsidy_btc || 3.125) * (iss.blocks_per_day || 144), 0)} BTC`, "at 144 blocks a day")}${kpi("Next halving", "≈ April 2028", "estimate: block 1,050,000")}</div>` +
    panel("Network hashrate", lineChart([{ name: "Hashrate EH/s", dates: hr ? hr.dates : [], values: hr ? hr.values : [], color: C.gold }], { height: 230, fmt: v => fmt(v, 0) }), "mempool.space, daily") +
    `<div class="pending" style="margin-top:12px"><b>Pending:</b> difficulty history, active addresses, transaction counts and fees, long- and short-term holder supply (Coin Metrics paid tiers or Glassnode).</div>`; };
PAGES["bitcoin/mining"] = pg => { const a = A("BTC"), hr = a.series.hashrate, bm = R("btc_market");
  return header(pg, "Mining activity, the industry's shift to AI hosting and miner behaviour.") +
    `<div class="g g-21">${panel("Hashrate, 3 years", lineChart([{ name: "Hashrate EH/s", dates: hr ? hr.dates : [], values: hr ? hr.values : [], color: C.gold }], { height: 220, fmt: v => fmt(v, 0) }), "mempool.space")}
      ${panel("Mining news", `<div class="lst">${(bm.mining_notes || []).map(n => `<div><span class="num dim">${esc(n.date)}</span><div class="sm">${esc(n.text)}</div>${src([n.source])}</div>`).join("")}</div>`)}</div>` +
    `<div class="pending"><b>Pending:</b> hashrate share by country (Cambridge CBECI is no longer updated monthly), miner holdings and miner-to-exchange flows (on-chain vendor), public miner production (8-K monthly updates).</div>`; };
PAGES["bitcoin/miner-economics"] = pg => { const a = A("BTC"), hp = a.series.miner_rev, d = a.drivers.find(x => x.key === "miner_rev"), bm = R("btc_market");
  return header(pg, "Revenue per unit of hashrate against miners' costs. When revenue falls below cost, weaker miners sell coins or switch off.") +
    why("Gold miners' margin (price minus AISC) plays the same role in gold supply.", "Miner selling adds supply in stress; miners pivoting to AI hosting removes a structural seller.") +
    `<div class="g g3">${kpi("Subsidy revenue per EH/s per day", hp ? "$" + fmt(hp.values[hp.values.length - 1], 0) : "—", "= $" + (hp ? fmt(hp.values[hp.values.length - 1] / 1000, 2) : "—") + " per PH/s; fees excluded")}${kpi("Driver signal (3-month change)", d?.signal == null ? "—" : sgn(d.signal, 1), d?.as_of || "")}${kpi("Reported hashprice (incl. fees)", "$31.89 /PH/day", "9 Nov 2026 · Hashrate Index")}</div>` +
    panel("Hashprice proxy (USD per EH/s per day, subsidy only)", lineChart([{ name: "USD per EH/s/day", dates: hp ? hp.dates : [], values: hp ? hp.values : [], color: C.gold }], { height: 230, fmt: v => fmt(v, 0) }), "price × 3.125 × 144 ÷ hashrate") +
    `<div class="note">The proxy excludes transaction fees, so it sits slightly below commercial hashprice indices. ${src([bm.mining_notes?.[0]?.source].filter(Boolean))}</div>`; };
PAGES["bitcoin/etf"] = pg => { const bm = R("btc_market"), a = A("BTC"), d = a.drivers.find(x => x.key === "etf");
  return header(pg, "Net flows into US spot Bitcoin ETFs, the largest source of institutional demand.") +
    why("Gold and Bitcoin ETFs compete for the same alternative-asset allocation.", "ETF flows have been the dominant medium-term driver since January 2024; flows far larger than new supply move price.") +
    `<div class="g g-21">${panel("Monthly net flows ($m)", barChart(bm.etf_monthly.rows.map(r => r[0]), bm.etf_monthly.rows.map(r => r[1]), { diverging: true, height: 220, unit: " $m", fmt: v => fmt(v, 0) }) + src(bm.etf_monthly.sources))}
     ${panel("Recent", table([{ t: "Period" }, { t: "Flow" }, { t: "Context" }], bm.etf_recent.rows.map(r => r.map(esc))) + src(bm.etf_recent.sources))}</div>` +
    panel("Month-end net assets", table(bm.etf_monthly.columns.map((c, i) => ({ t: c, n: i > 0 })), bm.etf_monthly.rows.map(r => [esc(r[0]), `<span class="num ${r[1] < 0 ? "dn" : "up"}">${fmt(r[1], 1)}</span>`, `<span class="num">${fmt(r[2], 1)}</span>`]))) +
    `<div class="pending" style="margin-top:12px"><b>Scorecard driver:</b> ${d?.signal == null ? `not scored yet (${esc(d?.note || "")})` : sgn(d.signal, 1)}. Daily flows go in <span class="mono">manual_inputs/btc_etf_flows.csv</span>; 60+ days of history are needed for a z-score.</div>`; };
PAGES["bitcoin/corporate"] = pg => pendingPage(pg, { lede: "Public companies holding Bitcoin on their balance sheets.", what: "A holdings table needs company filings parsed; only individual developments are recorded so far.", fields: "company, BTC held, average cost, latest purchase, funding source (equity, convertibles, preferred), share of market cap", source: "SEC EDGAR 8-K and 10-Q filings", related: panel("Recorded developments", `<div class="lst">${(R("btc_market").corporate_notes || []).map(n => `<div><span class="num dim">${esc(n.date)}</span> ${esc(n.text)}${src([n.source])}</div>`).join("")}</div>`) });
PAGES["bitcoin/exchanges"] = pg => { const er = R("btc_market").exchange_reserves || {};
  return header(pg, "Bitcoin held on exchanges, and flows in and out.") +
    why("Not directly relevant.", "Coins moving onto exchanges are potential sell supply; coins leaving suggest accumulation into self-custody.") +
    `<div class="g g3">${kpi("Exchange reserves", esc(er.value || "—"), esc(er.detail || ""))}${kpi("As of", esc(er.as_of || "—"), esc(er.class || ""))}${kpi("Live feed", "Pending", "paid on-chain data")}</div>${src([er.source].filter(Boolean))}` +
    `<div class="pending" style="margin-top:12px"><b>Pending live feed.</b> Exchange balances depend on each vendor's address labelling, so figures differ between CryptoQuant and Glassnode. The driver needs <span class="mono">manual_inputs/exchange_reserves.csv</span> or a paid API.</div>`; };
PAGES["bitcoin/whales"] = pg => pendingPage(pg, { lede: "Large-holder and institutional on-chain behaviour.", what: "Requires entity-labelled on-chain data from a paid provider.", fields: "wallets holding 1,000+ BTC, net accumulation, large transfers to exchanges, long- vs short-term holder supply", source: "Glassnode or CryptoQuant API (paid tiers)", phase: "Phase 2, if the backtest shows these drivers add accuracy" });
PAGES["bitcoin/technical"] = pg => technicalPage(pg, A("BTC"));
PAGES["bitcoin/scenarios"] = pg => scenariosPage(pg, "BTC");

/* ======================= D. MACRO ======================= */
function macroPage(pg, o) {
  const charts = o.series.map(([key, name, color, transform]) => { let m = seriesOf(key); let ser = m && (transform === "yoy" ? yoy(m) : m.series);
    return panel(esc(name), ser && ser.values.length ? lineChart([{ name, dates: ser.dates, values: ser.values, color: color || C.gold }], { height: 210, zero: o.zero, unit: transform === "yoy" ? "%" : (m.unit === "%" || m.unit === "pp" ? "%" : "") }) + `<div class="note">${m.latest ? `Latest ${fmt(m.latest.last, 2)} (${esc(m.latest.date)}) · 1M ${sgn(m.latest.chg_1m, 2)} · 3M ${sgn(m.latest.chg_3m, 2)}` : ""}</div>` : `<div class="pending">${needKey}</div>`, `FRED ${esc(key)}`); });
  return header(pg, o.lede) + why(o.why[0], o.why[1]) + `<div class="g ${charts.length > 1 ? "g2" : ""}">${charts.join("")}</div>` + (o.extra || "");
}
PAGES["macro/central-banks"] = pg => { const cb = R("central_banks");
  return header(pg, "Policy rates, last decisions and market pricing for the major central banks.") +
    why("Rate hikes raise the opportunity cost of holding gold, which pays no yield; the end of a hiking cycle has historically been supportive.", "Tighter policy drains liquidity and lifts real yields, both headwinds for Bitcoin.") +
    panel(`Policy tracker (as of ${esc(cb.as_of || "")})`, table([{ t: "Central bank" }, { t: "Policy rate" }, { t: "Last move" }, { t: "Next meeting" }, { t: "Market pricing" }, { t: "Sources" }], (cb.banks || []).map(b => [`<b>${esc(b.bank)}</b>`, `<span class="num">${esc(b.rate)}</span>`, esc(b.last_move), esc(b.next), esc(b.market), b.sources.map(([t, u]) => `<a href="${esc(u)}" target="_blank" rel="noopener" class="sm">${esc(t)}</a>`).join("<br>")]))) +
    `<div class="note">"Not collected" means the figure was not in the sources gathered; it is left blank rather than estimated.</div>`; };
PAGES["macro/rates"] = pg => macroPage(pg, { lede: "Short-term rates and policy expectations. The 2-year Treasury yield is the market's best read of the Fed path.", why: ["A rising 2-year yield means markets expect more hikes, raising the cost of holding gold.", "Higher expected policy rates tighten liquidity and weigh on Bitcoin."], series: [["DGS2", "US 2y Treasury yield", C.s1]] });
PAGES["macro/yields"] = pg => { const d2 = seriesOf("DGS2"), d10 = seriesOf("DGS10"), sp = seriesOf("T10Y2Y");
  return header(pg, "Government bond yields and the shape of the US curve.") + why("Higher nominal yields compete with gold unless inflation rises faster.", "Rising long-end yields tighten financial conditions for risk assets including Bitcoin.") +
    `<div class="g g2">${panel("US 2y and 10y Treasury yields", d2 || d10 ? lineChart([d2 && { name: "2y", dates: d2.series.dates, values: d2.series.values, color: C.s1 }, d10 && { name: "10y", dates: d10.series.dates, values: d10.series.values, color: C.s2 }].filter(Boolean), { height: 220, unit: "%" }) : needKey)}
      ${panel("10y minus 2y spread", sp ? lineChart([{ name: "10y–2y", dates: sp.series.dates, values: sp.series.values, color: C.gold }], { height: 220, zero: true, unit: " pp" }) : d2 && d10 ? lineChart([{ name: "10y–2y", ...spread(d10, d2), color: C.gold }], { height: 220, zero: true, unit: " pp" }) : `<div class="pending">${needKey}</div>`)}</div>` +
    `<div class="pending"><b>Pending:</b> Bunds, gilts and JGBs (ECB, BoE and BoJ data portals).</div>`; };
function spread(a, b) { const m = new Map(b.series.dates.map((d, i) => [d, b.series.values[i]])); const dates = [], values = []; a.series.dates.forEach((d, i) => { if (m.has(d)) { dates.push(d); values.push(+(a.series.values[i] - m.get(d)).toFixed(3)); } }); return { dates, values }; }
PAGES["macro/real-rates"] = pg => macroPage(pg, { lede: "Inflation-adjusted yields: the single most-watched macro driver for gold.", why: ["Gold pays no income, so the real yield is its opportunity cost. The link weakened after 2022, when central bank buying offset rising real yields; SOVEREIGN tracks the rolling correlation (Quantitative Research → Correlations).", "High real yields make cash and bonds attractive against non-yielding assets, including Bitcoin."], series: [["DFII10", "US 10y real yield (TIPS)", C.s1]] });
PAGES["macro/inflation"] = pg => macroPage(pg, { lede: "Consumer and core inflation. Shown as year-on-year change computed from the index.", why: ["Inflation above expectations supports gold over the long run, but in the short run it lifts rate-hike expectations, which hurts gold (as in November 2026).", "Hot inflation means tighter policy, a headwind for Bitcoin."], series: [["CPIAUCSL", "US CPI, % y/y", C.s2, "yoy"], ["PCEPILFE", "US core PCE, % y/y", C.s1, "yoy"]] });
PAGES["macro/dxy"] = pg => macroPage(pg, { lede: "The trade-weighted dollar (Fed broad index). The ICE DXY, quoted near 103 on 11 Nov 2026, weights the euro far more heavily.", why: ["Gold is priced in dollars; a stronger dollar makes it dearer for other buyers and usually pushes the price down.", "A strong dollar tightens global liquidity, which has historically weighed on Bitcoin."], series: [["DTWEXBGS", "Broad US dollar index", C.s1]] });
PAGES["macro/liquidity"] = pg => macroPage(pg, { lede: "US net liquidity: Fed balance sheet minus the reverse repo facility and the Treasury's cash account.", why: ["Abundant liquidity has supported all scarce assets; gold responds less than Bitcoin.", "Bitcoin's medium-term moves have tracked net liquidity closely; it carries the largest weight in the Bitcoin macro layer."], series: [["NETLIQ", "US net liquidity, $bn", C.s3]], extra: `<div class="pending"><b>Pending:</b> global M2 (euro area, China, Japan) from the ECB, PBoC and BoJ portals.</div>` });
PAGES["macro/growth"] = pg => macroPage(pg, { lede: "Real output growth.", why: ["Weak growth with sticky inflation (stagflation) has been the best macro backdrop for gold.", "Bitcoin trades as a risk asset in growth scares."], series: [["A191RL1Q225SBEA", "US real GDP growth, annualised q/q %", C.s1]], zero: true });
PAGES["macro/employment"] = pg => macroPage(pg, { lede: "Labour market: unemployment, payrolls and weekly claims.", why: ["A cooling labour market brings rate cuts closer, which supports gold.", "Strong jobs data lifts hike odds, as on 6 Nov 2026, weighing on Bitcoin."], series: [["UNRATE", "US unemployment rate %", C.s2], ["ICSA", "US initial jobless claims", C.s1]] });
PAGES["macro/recession"] = pg => macroPage(pg, { lede: "Indicators that have historically preceded US recessions.", why: ["Recessions usually bring rate cuts and lower real yields, historically positive for gold.", "Recession onsets have been negative for Bitcoin initially, then positive once liquidity is added."], series: [["T10Y2Y", "10y–2y yield spread", C.gold], ["UNRATE", "Unemployment rate %", C.s2]], zero: true, extra: `<div class="note">Debt: US federal debt to GDP is collected as FRED GFDEGDQ188S when the key is set.</div>` });
PAGES["macro/geopolitics"] = pg => { const g = R("geopolitics").items || [];
  return header(pg, "Geopolitical developments and how each one reaches gold and Bitcoin.") + why("Conflict lifts safe-haven demand, unless it raises oil and inflation enough to push rate expectations higher.", "Bitcoin has mostly traded as a risk asset in geopolitical shocks, not as a haven.") +
    table([{ t: "Date" }, { t: "Region" }, { t: "Development" }, { t: "Gold" }, { t: "Bitcoin" }, { t: "Source" }], g.map(x => [`<span class="num">${esc(x.date)}</span>`, esc(x.region), `<b>${esc(x.headline)}</b>`, `<span class="sm">${esc(x.gold)}</span>`, `<span class="sm">${esc(x.bitcoin)}</span>`, `<a class="sm" href="${esc(x.source[1])}" target="_blank" rel="noopener">${esc(x.source[0])}</a>`])) +
    `<div class="pending" style="margin-top:12px"><b>Pending:</b> the Geopolitical Risk Index (Caldara and Iacoviello) as a daily series, and a news feed (GDELT) for automatic detection.</div>`; };

/* ======================= E. INSTITUTIONAL ======================= */
PAGES["institutional/cb-activity"] = pg => PAGES["gold/central-banks"]({ ...pg });
PAGES["institutional/investments"] = pg => { const gm = R("gold_market"), bm = R("btc_market");
  return header(pg, "Institutional money moving into and out of gold and Bitcoin through ETFs.") +
    `<div class="g g2">${panel("Gold ETFs, monthly", refRows(gm.etf_monthly, [{ t: "Month" }, { t: "Flow" }, { t: "Value" }, { t: "Note" }]))}${panel("US spot Bitcoin ETFs, monthly ($m)", barChart(bm.etf_monthly.rows.map(r => r[0]), bm.etf_monthly.rows.map(r => r[1]), { diverging: true, height: 200, fmt: v => fmt(v, 0) }) + src(bm.etf_monthly.sources))}</div>` +
    `<div class="pending"><b>Pending:</b> 13F institutional ownership of GLD, IAU, IBIT and FBTC (quarterly, SEC EDGAR).</div>`; };
PAGES["institutional/company-financials"] = pg => pendingPage(pg, { lede: "Income statements and cash flows of gold miners and Bitcoin miners.", what: "Filings are not parsed yet.", fields: "revenue, EBITDA, operating profit, free cash flow, margins; quarterly history and peer comparison", source: "SEC EDGAR XBRL company facts API (free)" });
PAGES["institutional/balance-sheets"] = pg => pendingPage(pg, { lede: "Debt, cash and asset holdings of companies exposed to gold and Bitcoin.", what: "Filings are not parsed yet.", fields: "cash, debt, net debt, BTC or gold held, liquidity runway", source: "SEC EDGAR XBRL company facts API" });
PAGES["institutional/holdings"] = pg => { const g = A("XAU").series.cot, b = A("BTC").series.cme;
  return header(pg, "How large investors are positioned in futures markets.") +
    `<div class="g g2">${panel("Gold: managed money net long, % of open interest", lineChart([{ name: "Net long % OI", dates: g ? g.dates : [], values: g ? g.values : [], color: C.gold }], { height: 220, unit: "%", fmt: v => fmt(v, 0) }), "CFTC disaggregated, weekly")}
      ${panel("Bitcoin: CME leveraged funds net position (contracts)", lineChart([{ name: "Net contracts", dates: b ? b.dates : [], values: b ? b.values : [], color: C.s1 }], { height: 220, zero: true, fmt: v => fmt(v, 0) }), "CFTC traders in financial futures, weekly")}</div>` +
    `<div class="note">Leveraged funds are often short CME Bitcoin futures as one leg of a basis trade against long ETF holdings, so a large short is not a directional bet by itself.</div>`; };
PAGES["institutional/ownership"] = pg => pendingPage(pg, { lede: "Changes in who owns gold and Bitcoin vehicles and producers.", what: "13F and 13D/G filings are not parsed yet.", fields: "top holders of GLD, IAU, IBIT, FBTC, major miners; quarter-on-quarter changes", source: "SEC EDGAR 13F (quarterly, 45-day lag)" });
PAGES["institutional/flows"] = pg => PAGES["institutional/investments"](pg) + `<div class="g g3" style="margin-top:12px">${kpi("Central banks, gold, Q3 2026", "321 t", "+42% y/y")}${kpi("Gold ETFs, Q3 2026", "211 t", "US$31bn record")}${kpi("Bitcoin ETFs, 2–6 Nov", "−$1.28bn", "worst week since June")}</div>`;

/* ======================= F. QUANT ======================= */
PAGES["quant/historical"] = pg => { const a = cur(), mr = a.monthly_returns; const years = [...new Set(mr.map(x => x.month.slice(0, 4)))];
  const grid = years.map(y => [`<b>${y}</b>`, ...Array.from({ length: 12 }, (_, i) => { const r = mr.find(x => x.month === `${y}-${String(i + 1).padStart(2, "0")}`); return r ? `<span class="num ${r.ret > 0 ? "up" : "dn"}">${sgn(r.ret, 1)}</span>` : ""; })]);
  return header(pg, "Price history and monthly returns over the stored sample.", { asset: true }) +
    panel(`${assetName(a.symbol)}, full stored history`, lineChart([{ name: assetName(a.symbol), dates: a.ohlc.map(r => r[0]), values: a.ohlc.map(r => r[4]), color: C.gold }], { height: 260, area: true }), `${a.ohlc[0][0]} to ${a.ohlc[a.ohlc.length - 1][0]}`) +
    panel("Monthly returns (%)", table([{ t: "Year" }, ..."Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(" ").map(m => ({ t: m, n: 1 }))], grid)) +
    `<div class="note">The stored sample starts in ${esc(a.ohlc[0][0].slice(0, 4))} because the free price source returns about 1,000 days. Longer history (gold from 1971, Bitcoin from 2010) is a Phase 1 backfill.</div>`; };
PAGES["quant/correlations"] = pg => { const q = S.data.quant;
  return header(pg, "How gold, Bitcoin and the macro drivers move together. Correlations are statistical relationships that change over time, not causes.") +
    `<div class="g g2">${panel("Last 90 trading days", heatmap(q.corr_90.keys, q.corr_90.matrix))}${panel("Last 250 trading days", heatmap(q.corr_365.keys, q.corr_365.matrix))}</div>` +
    panel("Rolling 90-day correlation", lineChart(Object.entries(q.rolling).map(([k, v], i) => ({ name: k, dates: v.dates, values: v.values, color: [C.gold, C.s1, C.s2][i] })), { height: 240, zero: true, fmt: v => fmt(v, 2) })) +
    `<div class="note">${esc(q.note)} Blue = move together, red = move opposite. Missing macro series (dollar, liquidity) appear once the FRED key is set.</div>`; };
PAGES["quant/volatility"] = pg => header(pg, "Realised volatility, annualised, and drawdowns.") +
  `<div class="g g4">${S.data.assets.flatMap(a => [kpi(`${assetName(a.symbol)} vol (30d)`, fmt(a.volatility.vol30, 1) + "%", `percentile ${fmt(a.volatility.vol30_pct_rank, 0)} vs 2 years`), kpi(`${assetName(a.symbol)} max drawdown (1y)`, fmt(a.volatility.max_drawdown_1y, 1) + "%", `vol (90d) ${fmt(a.volatility.vol90, 1)}%`)]).join("")}</div>` +
  panel("30-day realised volatility (annualised %)", lineChart(S.data.assets.map((a, i) => ({ name: assetName(a.symbol), dates: a.volatility.dates, values: a.volatility.values, color: [C.gold, C.s1][i] })), { height: 260, unit: "%", fmt: v => fmt(v, 0) }));
PAGES["quant/statistics"] = pg => { const a = cur();
  return header(pg, "Each driver's latest reading against its own 3-year distribution.", { asset: true }) +
    panel("Driver statistics", table([{ t: "Driver" }, { t: "Raw", n: 1 }, { t: "Transformed", n: 1 }, { t: "z-score", n: 1 }, { t: "Percentile", n: 1 }, { t: "Signal", n: 1 }, { t: "Bullish when" }], a.drivers.map(d => [esc(d.name), `<span class="num">${fmt(d.raw_value, 2)}</span>`, `<span class="num">${fmt(d.value, 2)}</span>`, `<span class="num">${fmt(d.z, 2)}</span>`, `<span class="num">${fmt(d.percentile, 0)}</span>`, `<span class="num">${sgn(d.signal, 2)}</span>`, `<span class="sm dim">${esc(d.bullish_when)}</span>`]))) +
    `<div class="note">z = (latest − 3-year mean) ÷ 3-year standard deviation; signal = direction × z, capped at ±2. Drivers with fewer than 60 distinct observations are not scored.</div>`; };
PAGES["quant/regimes"] = pg => { const a = cur(), r = a.regime;
  const colors = { "Uptrend, low volatility": C.bull, "Uptrend, high volatility": "#8fb8ef", "Downtrend, low volatility": "#f0a3a3", "Downtrend, high volatility": C.bear };
  const strip = `<div style="display:flex;height:16px;border-radius:3px;overflow:hidden">${(r.history || []).map(h => `<span title="${esc(h.date)}: ${esc(h.regime)}" style="flex:1;background:${colors[h.regime] || C.mid}"></span>`).join("")}</div><div class="legend" style="margin-top:6px">${Object.entries(colors).map(([k, c]) => `<span><span class="sw" style="background:${c};height:8px"></span>${k}</span>`).join("")}</div>`;
  return header(pg, "Regimes from trend (price vs 200-day average) and volatility (vs its 1-year median).", { asset: true }) +
    `<div class="g g3">${kpi("Current regime", esc(r.current), `${r.days_in_regime} sessions`)}${kpi("Sample from", esc(r.sample_start || ""), "")}${kpi("Daily trend", esc(a.technicals.daily.trend.label), "")}</div>` +
    panel("Regime timeline (last 500 sessions)", strip) +
    panel("Historical behaviour by regime", table([{ t: "Regime" }, { t: "Sessions", n: 1 }, { t: "Share", n: 1 }, { t: "Median next-20-session return", n: 1 }, { t: "Share positive", n: 1 }], r.table.map(x => [esc(x.regime), `<span class="num">${x.days}</span>`, `<span class="num">${fmt(x.share, 1)}%</span>`, pct(x.fwd20_median), `<span class="num">${fmt(x.fwd20_hit, 0)}%</span>`]))) +
    `<div class="note">Historical observation from a short sample; it describes the past and is not a forecast or a probability.</div>`; };
PAGES["quant/backtesting"] = pg => { const a = cur(), b = a.backtest;
  if (!b.curve) return header(pg, "", { asset: true }) + `<div class="pending">${esc(b.note)}</div>`;
  const row = (n, s) => [n, pct(s.total, 1), pct(s.cagr, 1), pct(s.max_dd, 1), `<span class="num">${fmt(s.sharpe, 2)}</span>`];
  return header(pg, "Benchmark test from the specification: a 200-day moving average rule against buy-and-hold. The scorecard itself is backtested once enough point-in-time history accumulates.", { asset: true }) +
    panel("Equity curves (start = 1.0)", lineChart([{ name: "200-day rule", dates: b.curve.dates, values: b.curve.strategy, color: C.gold }, { name: "Buy and hold", dates: b.curve.dates, values: b.curve.buy_hold, color: C.s1 }], { height: 260, fmt: v => fmt(v, 2) }), `${esc(b.start)} to ${esc(b.end)}`) +
    panel("Results", table([{ t: "Strategy" }, { t: "Total", n: 1 }, { t: "Annualised", n: 1 }, { t: "Max drawdown", n: 1 }, { t: "Sharpe", n: 1 }], [row("200-day rule", b.strategy), row("Buy and hold", b.buy_hold)]) + `<div class="note">${b.trades} switches, ${b.cost_bp} bp cost per switch, invested ${fmt(b.time_in_market, 0)}% of the time. Sample of ${b.days} sessions is short; results are illustrative.</div>`); };
PAGES["quant/scenario-modelling"] = pg => { const a = cur(), live = a.drivers.filter(d => d.signal != null);
  const id = uid();
  mount(() => { const box = document.getElementById(id); if (!box) return;
    const calc = () => { const sig = {}; box.querySelectorAll("input[type=range]").forEach(i => { sig[i.dataset.k] = +i.value; i.nextElementSibling.textContent = sgn(+i.value, 1); });
      const out = HZ.map(([hz, t]) => { const comp = layers => { const ds = live.filter(d => layers.includes(d.layer)); const w = ds.reduce((s, d) => s + d.weight * d.horizons[hz], 0); return w ? Math.round(ds.reduce((s, d) => s + d.weight * d.horizons[hz] * sig[d.key], 0) / w * 50) : null; };
        const mac = comp([1]), fun = comp([2, 3, 4]), tec = a.decision[hz].technical, bl = S.data.blend[hz]; const parts = { macro: mac, fundamental: fun, technical: tec }; const ws = Object.entries(parts).filter(([, v]) => v != null);
        const c = Math.round(ws.reduce((s, [k, v]) => s + v * bl[k], 0) / ws.reduce((s, [k]) => s + bl[k], 0));
        return [t, scoreRow(mac), scoreRow(fun), scoreRow(tec), `${scoreRow(c)}<div class="sm">${labelHtml(c >= 60 ? "Strong bullish" : c >= 20 ? "Moderately bullish" : c > -20 ? "Neutral" : c > -60 ? "Moderately bearish" : "Strong bearish")} <span class="dim">(now ${sgn(a.decision[hz].combined)})</span></div>`]; });
      box.querySelector(".res").innerHTML = table([{ t: "Horizon" }, { t: "Macro" }, { t: "Fundamental" }, { t: "Technical (fixed)" }, { t: "Combined" }], out); };
    box.querySelectorAll("input[type=range]").forEach(i => i.oninput = calc);
    box.querySelector(".btn").onclick = () => { box.querySelectorAll("input[type=range]").forEach(i => { i.value = i.dataset.v; }); calc(); };
    calc(); });
  return header(pg, "Change any driver's signal and see how the scores respond. A deterministic what-if: it shows how the model works, not what will happen.", { asset: true }) +
    `<div id="${id}" class="g g-12"><div>${panel("Driver signals", live.map(d => `<div style="margin-bottom:9px"><div class="sm">${esc(d.name)}</div><div style="display:flex;gap:10px;align-items:center"><input type="range" min="-2" max="2" step="0.1" value="${d.signal}" data-k="${d.key}" data-v="${d.signal}" aria-label="${esc(d.name)}"><span class="num" style="width:38px;text-align:right"></span></div></div>`).join("") + `<button class="btn">Reset to today</button>`)}</div><div>${panel("Resulting scores", `<div class="res"></div>`)}</div></div>`; };
PAGES["quant/forecast-accuracy"] = pg => { const rc = S.data.report_card || [], log = S.data.forecast_log || [], done = log.filter(x => x.hit != null), next = log.filter(x => x.hit == null).map(x => x.resolve_on).sort()[0];
  return header(pg, "Every published outlook is frozen and scored when its horizon ends. This is how SOVEREIGN measures whether its reasoning works.") +
    `<div class="g g3">${kpi("Outlooks logged", log.length, "")}${kpi("Scored so far", done.length, "")}${kpi("Next to resolve", esc(next || "—"), "short-term outlooks resolve after 5 days")}</div>` +
    (rc.length ? panel("Report card", table([{ t: "Asset" }, { t: "Horizon" }, { t: "Scored", n: 1 }, { t: "Hit rate", n: 1 }], rc.map(r => [assetName(r.asset), esc(r.horizon), `<span class="num">${r.n}</span>`, `<span class="num">${fmt(r.hit_rate * 100, 0)}%</span>`]))) : `<div class="pending"><b>No outlooks have resolved yet.</b> Hit rates appear once horizons end: 5 days for short term, 4 weeks for medium, 3 months for long. A hit rate needs 30+ scored outlooks per asset and horizon before it means much.</div>`) +
    `<div style="margin-top:12px">${panel("Forecast log (latest 40)", table([{ t: "Asset" }, { t: "Horizon" }, { t: "As of" }, { t: "Label" }, { t: "Score", n: 1 }, { t: "Price", n: 1 }, { t: "Resolves" }, { t: "Return", n: 1 }, { t: "Hit" }], log.slice(0, 40).map(x => [assetName(x.asset), esc(x.horizon), esc(x.as_of), labelHtml(x.stance), `<span class="num">${sgn(x.composite)}</span>`, `<span class="num">${pxFmt(x.asset, x.price)}</span>`, esc(x.resolve_on), x.realised_return == null ? "—" : pct(x.realised_return * 100, 1), x.hit == null ? `<span class="dim">open</span>` : x.hit ? "Yes" : "No"])), "", "flush")}</div>`; };

/* ======================= G. TECHNICAL ======================= */
PAGES["technical/multi-timeframe"] = pg => { const a = cur(), t = a.technicals;
  return header(pg, "The same market on daily and weekly timeframes. Agreement between them strengthens a signal.", { asset: true }) +
    `<div class="g g2">${panel("Daily", priceChart(a, { days: 300, height: 340 }))}${panel("Weekly", priceChart(a, { days: 1100, weekly: true, ma: false, height: 340 }))}</div>` +
    panel("Timeframe comparison", table([{ t: "" }, { t: "Daily" }, { t: "Weekly" }], [["Trend", esc(t.daily.trend.label), esc(t.weekly.trend.label)], ["Structure", esc(t.daily.structure.label), esc(t.weekly.structure.label)], ["RSI (14)", fmt(t.daily.rsi, 0), fmt(t.weekly.rsi, 0)], ["Technical score", scoreRow(t.daily.score), scoreRow(t.weekly.score)]]) + `<div class="note">Weekly trend uses 10- and 40-week averages.</div>`); };
PAGES["technical/structure"] = pg => { const a = cur(), t = a.technicals;
  return header(pg, "Swing highs and lows: are buyers or sellers in control?", { asset: true }) +
    `<div class="g g2">${kpi("Daily structure", esc(t.daily.structure.label), esc(t.daily.structure.detail))}${kpi("Weekly structure", esc(t.weekly.structure.label), esc(t.weekly.structure.detail))}</div>` + panel("Daily chart with swing levels", priceChart(a, { days: 250 })); };
PAGES["technical/support-resistance"] = pg => { const a = cur();
  return header(pg, "Levels from clustered swing points over the last year, with the 200-day average and 52-week range.", { asset: true }) + `<div class="g g-21">${panel("Chart", priceChart(a, { days: 365 }))}${panel("Levels", levelsTable(a))}</div>` + `<div class="note">A level is a zone where several swing highs or lows cluster within one day's typical move. More touches mean a more established level.</div>`; };
PAGES["technical/trend"] = pg => { const a = cur(), d = a.technicals.daily.trend, w = a.technicals.weekly.trend, p = a.performance.last, l = a.levels;
  return header(pg, "Direction from moving averages and their slope.", { asset: true }) +
    `<div class="g g4">${kpi("Daily trend", esc(d.label), `50-day slope ${sgn(d.sma50_slope_10, 2)}% over 10 sessions`)}${kpi("Weekly trend", esc(w.label), "10 / 40-week averages")}${kpi("Price vs 200-day", l.sma200 ? pct((p / l.sma200 - 1) * 100, 1) : "—", l.sma200 ? "average " + pxFmt(a.symbol, l.sma200) : "")}${kpi("50 vs 200-day", d.sma50_above_sma200 ? "Golden cross" : "Death cross", "")}</div>` + panel("Price with 50- and 200-day averages", priceChart(a, { days: 500, levels: false })); };
PAGES["technical/momentum"] = pg => { const a = cur(), ds = a.technicals.daily_series;
  return header(pg, "RSI and MACD measure the speed of moves and when they are fading.", { asset: true }) +
    `<div class="g g2">${panel("RSI (14)", rsiChart(a, 220))}${panel("MACD histogram (12, 26, 9)", barChart(ds.dates.slice(-120), ds.macd_hist.slice(-120), { diverging: true, height: 220, fmt: v => fmt(v, a.symbol === "BTC" ? 0 : 1) }))}</div>` + panel("Signals", signalsTable(a)); };
PAGES["technical/volume"] = pg => { const a = cur(), vr = a.technicals.daily.vol_ratio;
  return header(pg, "Traded volume confirms or questions price moves.", { asset: true }) + `<div class="g g3">${kpi("Volume vs 20-day average", vr == null ? "—" : fmt(vr, 2) + "×", "")}${kpi("Venue", a.symbol === "XAU" ? "PAXG/USDT, Binance" : "BTC/USDT, Binance", "")}${kpi("Coverage", "Single venue", "")}</div>` + panel("Price and volume", priceChart(a, { days: 250, volume: true })) +
    `<div class="note">${a.symbol === "XAU" ? "PAXG token volume is a small slice of gold trading; COMEX futures and LBMA OTC volume are pending feeds, so treat gold volume signals as indicative only." : "Volume is from one exchange; aggregated spot and ETF volume is a pending feed."}</div>`; };
PAGES["technical/liquidity"] = pg => { const a = cur();
  if (a.symbol === "BTC") { const fu = a.series.funding; return header(pg, "Leverage and funding in derivatives markets.", { asset: true }) + panel("Perpetual funding rate, 7-day average (%)", lineChart([{ name: "Funding", dates: fu ? fu.dates : [], values: fu ? fu.values : [], color: C.s2 }], { height: 230, zero: true, fmt: v => fmt(v, 3) })) + `<div class="pending" style="margin-top:12px"><b>Pending:</b> open interest, liquidation heatmaps and order-book depth.</div>`; }
  return pendingPage(pg, { asset: true, lede: "Market depth and liquidity in gold.", what: "No gold liquidity feed is connected.", fields: "COMEX open interest and depth, LBMA clearing volumes, bid-ask spreads", source: "CME, LBMA" }); };
PAGES["technical/signals"] = pg => { const a = cur();
  return header(pg, "Every technical signal in one table, with whether it confirms or contradicts the trend.", { asset: true }) + panel("Daily signals", signalsTable(a)) +
    `<div class="g g2" style="margin-top:12px">${panel("Confirmation status", `<p style="margin:0">${a.technicals.daily.signals.filter(s => s.bias > 0).length} bullish, ${a.technicals.daily.signals.filter(s => s.bias < 0).length} bearish, ${a.technicals.daily.signals.filter(s => s.bias === 0).length} neutral or reference signals. Daily trend: <b>${esc(a.technicals.daily.trend.label)}</b>; weekly trend: <b>${esc(a.technicals.weekly.trend.label)}</b>.</p>`)}${panel("Technical score", HZ.map(([k, t]) => `<div style="margin-bottom:8px"><div class="sm">${t}</div>${scoreRow(a.decision[k].technical)}</div>`).join(""))}</div>`; };

/* ======================= H. DECISION ======================= */
PAGES["decision/fundamental-scores"] = pg => header(pg, "Fundamental (supply, demand, positioning, institutional) and macro scores, −100 to +100.") +
  panel("Fundamental score", decisionMatrix(S.data.assets, "fundamental")) + `<div style="height:12px"></div>` + panel("Macro score", decisionMatrix(S.data.assets, "macro")) +
  `<div class="g g2" style="margin-top:12px">${S.data.assets.map(a => panel(`${assetName(a.symbol)}: fundamental drivers`, driverTable(a, [2, 3, 4]), "", "flush")).join("")}</div>`;
PAGES["decision/technical-scores"] = pg => header(pg, "Technical score: trend 40%, market structure 20%, momentum (MACD, RSI, 1-month return) 40%.") + panel("Technical score by horizon", decisionMatrix(S.data.assets, "technical")) +
  `<div class="g g2" style="margin-top:12px">${S.data.assets.map(a => panel(assetName(a.symbol), signalsTable(a))).join("")}</div>`;
PAGES["decision/combined"] = pg => { const bl = S.data.blend;
  return header(pg, "The platform's overall conclusion for each asset and horizon.") + panel("Combined intelligence score", decisionMatrix()) +
    `<div class="g g2" style="margin-top:12px">${S.data.assets.map(a => panel(`${assetName(a.symbol)}: components`, table([{ t: "Horizon" }, { t: "Macro" }, { t: "Fundamental" }, { t: "Technical" }, { t: "Combined" }, { t: "Confidence" }], HZ.map(([k, t]) => { const d = a.decision[k]; return [t, scoreRow(d.macro), scoreRow(d.fundamental), scoreRow(d.technical), scoreRow(d.combined), statusPill(d.confidence.label)]; })))).join("")}</div>` +
    panel("Blend weights", table([{ t: "Horizon" }, { t: "Macro", n: 1 }, { t: "Fundamental", n: 1 }, { t: "Technical", n: 1 }], HZ.map(([k, t]) => [t, `${bl[k].macro * 100}%`, `${bl[k].fundamental * 100}%`, `${bl[k].technical * 100}%`])) + `<div class="note">Bands: ≥ +60 strong bullish · +20 to +59 moderately bullish · −19 to +19 neutral · −20 to −59 moderately bearish · ≤ −60 strong bearish. A missing component is left out and the others are re-weighted.</div>`); };
const outlookPage = hz => pg => header(pg, `The ${hz}-term assessment for each asset: evidence for and against, what would invalidate it, confidence and data quality.`) +
  `<div class="g g2">${S.data.assets.map(a => outlookCard(a.outlooks.find(o => o.key === hz), a)).join("")}</div>` +
  `<div class="g g2">${S.data.assets.map(a => panel(`${assetName(a.symbol)}: model confidence`, `<dl class="kv"><dt>Confidence</dt><dd>${statusPill(a.decision[hz].confidence.label)} <span class="num">${a.decision[hz].confidence.value}</span></dd><dt>Data quality</dt><dd>${statusPill(a.data_quality.label)} <span class="num">${a.data_quality.score}</span></dd><dt>Why</dt><dd>${listOr(a.decision[hz].confidence.why)}</dd></dl>`)).join("")}</div>`;
PAGES["decision/short"] = outlookPage("short"); PAGES["decision/medium"] = outlookPage("medium"); PAGES["decision/long"] = outlookPage("long");
PAGES["decision/scenarios"] = pg => header(pg, "Scenario assumptions for both assets. Conditions, not targets or probabilities.") + S.data.assets.map(a => `<h2 style="margin:6px 0 10px">${assetName(a.symbol)}</h2><div class="g g3">${a.scenarios.map(s => panel(esc(s.name), `<h3>Assumptions</h3>${listOr(s.assumptions)}<h3 style="margin-top:8px">Technical path</h3><p class="sm" style="margin:0">${esc(s.technical_path)}</p>`)).join("")}</div>`).join("");
PAGES["decision/forecast-history"] = pg => { const h = S.data.score_history || [];
  const lines = S.data.assets.flatMap((a, i) => HZ.map(([k, t], j) => { const r = h.filter(x => x.asset === a.symbol && x.horizon === k); return { name: `${assetName(a.symbol)} ${k}`, dates: r.map(x => x.date), values: r.map(x => x.combined), color: [[C.gold, "#e0c27e", "#8a6f37"], [C.s1, "#8fb8ef", "#1f5aa8"]][i][j] }; }));
  return header(pg, "The combined score recorded on every daily run. History builds from the first live run on 17 Nov 2026.") +
    panel("Combined score over time", h.length > 1 ? lineChart(lines, { height: 280, zero: true, fmt: v => fmt(v, 0) }) : `<div class="dim">One run recorded so far; the chart draws from the second run.</div>`) +
    panel("Recorded scores", table([{ t: "Date" }, { t: "Asset" }, { t: "Horizon" }, { t: "Macro", n: 1 }, { t: "Fundamental", n: 1 }, { t: "Technical", n: 1 }, { t: "Combined", n: 1 }, { t: "Label" }, { t: "Price", n: 1 }], h.slice().reverse().slice(0, 60).map(x => [esc(x.date), assetName(x.asset), esc(x.horizon), sgn(x.macro), sgn(x.fundamental), sgn(x.technical), `<b class="num">${sgn(x.combined)}</b>`, labelHtml(x.label), pxFmt(x.asset, x.price)])), "", "flush"); };
PAGES["decision/confidence"] = pg => header(pg, "How much weight to put on each conclusion: data coverage, agreement between drivers, and agreement between components.") +
  panel("Model confidence", table([{ t: "Asset" }, ...HZ.map(([, t]) => ({ t }))], S.data.assets.map(a => [`<b>${assetName(a.symbol)}</b>`, ...HZ.map(([k]) => { const c = a.decision[k].confidence; return `${statusPill(c.label)} <span class="num">${c.value}</span><div class="sm dim" style="margin-top:4px">${c.why.map(esc).join("<br>")}</div>`; })]))) +
  `<div class="note">Confidence = 60% data coverage + 40% driver agreement, minus 15 when macro, fundamental and technical scores point in opposite directions. High ≥ 70 (and never High while less than 60% of driver weight has data), Medium ≥ 45.</div>`;

/* ======================= I. TOOLS ======================= */
function tool(pg, lede, fields, compute, outs) {
  const id = uid();
  mount(() => { const box = document.getElementById(id); if (!box) return; const run = () => { const v = {}; box.querySelectorAll("[data-f]").forEach(i => v[i.dataset.f] = i.tagName === "SELECT" ? i.value : parseFloat(i.value)); const n0 = S.mounts.length; let r; try { r = compute(v); } catch { r = {}; }
      box.querySelector(".out").innerHTML = outs.map(([k, lab, f]) => `<div><div class="k">${lab}</div><div class="v">${r[k] == null || (typeof r[k] === "number" && !isFinite(r[k])) ? "—" : f ? f(r[k]) : fmt(r[k], 2)}</div></div>`).join("") + (r.extra || ""); S.mounts.splice(n0).forEach(f => f()); };
    box.querySelectorAll("[data-f]").forEach(i => i.oninput = run); run(); });
  return header(pg, lede) + `<div id="${id}" class="g g2">${panel("Inputs", `<div class="form">${fields.map(([k, lab, val, opts]) => `<label>${lab}${opts ? `<select data-f="${k}">${opts.map(o => `<option ${o === val ? "selected" : ""}>${o}</option>`).join("")}</select>` : `<input data-f="${k}" type="number" step="any" value="${val}">`}</label>`).join("")}</div>`)}${panel("Results", `<div class="out"></div>`)}</div><div class="note">Calculators run in your browser; nothing is stored or sent.</div>`;
}
const usd = v => "$" + fmt(v, 2), num2 = v => fmt(v, 2), q4 = v => fmt(v, 4);
PAGES["tools/position-size"] = pg => tool(pg, "How large a position can be so that hitting the stop loses only the chosen share of the account.",
  [["acct", "Account size ($)", 10000], ["riskp", "Risk per trade (%)", 1], ["entry", "Entry price", fmt(A("XAU").performance.last, 2).replace(/,/g, "")], ["stop", "Stop-loss price", Math.round(A("XAU").performance.last * 0.98)]],
  v => { const risk = v.acct * v.riskp / 100, per = Math.abs(v.entry - v.stop), units = risk / per; return { risk, per, units, notional: units * v.entry, lev: units * v.entry / v.acct }; },
  [["risk", "Amount at risk", usd], ["per", "Risk per unit", usd], ["units", "Position size (units / oz / BTC)", q4], ["notional", "Position value", usd], ["lev", "Implied leverage", v => fmt(v, 2) + "×"]]);
PAGES["tools/risk"] = pg => tool(pg, "Portfolio-level risk: how many losing trades in a row the account can take, and the drawdown they cause.",
  [["acct", "Account size ($)", 10000], ["riskp", "Risk per trade (%)", 1], ["losses", "Consecutive losses", 10], ["maxdd", "Maximum drawdown you accept (%)", 20]],
  v => { const after = v.acct * Math.pow(1 - v.riskp / 100, v.losses), dd = (1 - after / v.acct) * 100, n = Math.log(1 - v.maxdd / 100) / Math.log(1 - v.riskp / 100), rec = (v.acct / after - 1) * 100; return { after, dd, n, rec }; },
  [["after", "Account after the losing streak", usd], ["dd", "Drawdown", v => fmt(v, 1) + "%"], ["rec", "Gain needed to recover", v => fmt(v, 1) + "%"], ["n", "Losses until max drawdown", v => fmt(v, 0)]]);
PAGES["tools/risk-reward"] = pg => tool(pg, "Reward-to-risk ratio and the win rate needed to break even.",
  [["entry", "Entry price", fmt(A("BTC").performance.last, 0).replace(/,/g, "")], ["stop", "Stop-loss price", Math.round(A("BTC").performance.last * 0.95)], ["target", "Target price", Math.round(A("BTC").performance.last * 1.1)], ["side", "Direction", "Long", ["Long", "Short"]]],
  v => { const long = v.side === "Long", risk = long ? v.entry - v.stop : v.stop - v.entry, rew = long ? v.target - v.entry : v.entry - v.target, rr = rew / risk; return { risk, rew, rr, be: 100 / (1 + rr) }; },
  [["risk", "Risk per unit", num2], ["rew", "Reward per unit", num2], ["rr", "Reward : risk", v => "1 : " + fmt(v, 2)], ["be", "Break-even win rate", v => fmt(v, 1) + "%"]]);
PAGES["tools/leverage"] = pg => tool(pg, "Margin, exposure and the approximate liquidation price for a leveraged position (isolated margin, fees and funding excluded).",
  [["margin", "Margin posted ($)", 1000], ["lev", "Leverage (×)", 5], ["entry", "Entry price", fmt(A("BTC").performance.last, 0).replace(/,/g, "")], ["mmr", "Maintenance margin (%)", 0.5], ["side", "Direction", "Long", ["Long", "Short"]]],
  v => { const exp = v.margin * v.lev, units = exp / v.entry, long = v.side === "Long", liq = long ? v.entry * (1 - 1 / v.lev + v.mmr / 100) : v.entry * (1 + 1 / v.lev - v.mmr / 100); return { exp, units, liq, dist: Math.abs(liq / v.entry - 1) * 100 }; },
  [["exp", "Position exposure", usd], ["units", "Units", q4], ["liq", "Approx. liquidation price", num2], ["dist", "Distance to liquidation", v => fmt(v, 2) + "%"]]);
PAGES["tools/dca"] = pg => tool(pg, "Dollar-cost averaging: buying a fixed amount at regular intervals. Uses the stored daily price history.",
  [["amt", "Amount per purchase ($)", 100], ["every", "Every (days)", 7], ["months", "Over the last (months)", 12], ["asset", "Asset", "Bitcoin", ["Bitcoin", "Gold"]]],
  v => { const a = A(v.asset === "Gold" ? "XAU" : "BTC"), rows = a.ohlc, start = new Date(rows[rows.length - 1][0]); start.setMonth(start.getMonth() - v.months); const iso = start.toISOString().slice(0, 10);
    const sel = rows.filter(r => r[0] >= iso).filter((_, i) => i % Math.max(1, Math.round(v.every)) === 0); const units = sel.reduce((s, r) => s + v.amt / r[4], 0), spent = sel.length * v.amt, val = units * rows[rows.length - 1][4];
    return { buys: sel.length, spent, units, avg: spent / units, val, ret: (val / spent - 1) * 100 }; },
  [["buys", "Purchases", v => fmt(v, 0)], ["spent", "Total invested", usd], ["units", "Units bought", q4], ["avg", "Average cost", usd], ["val", "Value today", usd], ["ret", "Return", v => fmt(v, 1) + "%"]]);
PAGES["tools/average-entry"] = pg => tool(pg, "Average entry price across up to four fills.",
  [["p1", "Fill 1 price", 4000], ["q1", "Fill 1 size", 1], ["p2", "Fill 2 price", 3900], ["q2", "Fill 2 size", 1], ["p3", "Fill 3 price", 0], ["q3", "Fill 3 size", 0], ["p4", "Fill 4 price", 0], ["q4", "Fill 4 size", 0], ["now", "Current price", fmt(A("XAU").performance.last, 2).replace(/,/g, "")]],
  v => { let q = 0, c = 0; [1, 2, 3, 4].forEach(i => { q += v["q" + i] || 0; c += (v["p" + i] || 0) * (v["q" + i] || 0); }); const avg = c / q; return { q, cost: c, avg, pnl: (v.now - avg) * q, pnlp: (v.now / avg - 1) * 100 }; },
  [["q", "Total size", q4], ["cost", "Total cost", usd], ["avg", "Average entry", num2], ["pnl", "Unrealised P&L", usd], ["pnlp", "Unrealised P&L %", v => fmt(v, 2) + "%"]]);
PAGES["tools/compounding"] = pg => tool(pg, "Growth of capital at a constant periodic return, with optional regular additions.",
  [["start", "Starting capital ($)", 10000], ["ret", "Return per period (%)", 2], ["periods", "Number of periods", 24], ["add", "Addition per period ($)", 0]],
  v => { let x = v.start; const path = []; for (let i = 0; i < v.periods; i++) { x = x * (1 + v.ret / 100) + v.add; path.push(x); } const inv = v.start + v.add * v.periods; return { end: x, inv, gain: x - inv, mult: x / inv, extra: `<div style="grid-column:1/-1">${barChart(path.map((_, i) => String(i + 1)), path, { height: 150, fmt: v2 => fmt(v2, 0) })}</div>` }; },
  [["end", "Ending capital", usd], ["inv", "Total contributed", usd], ["gain", "Growth", usd], ["mult", "Multiple of contributions", v => fmt(v, 2) + "×"]]);
PAGES["tools/multi-trade"] = pg => tool(pg, "Simulates many sequences of trades with a given win rate and reward-to-risk to show the range of outcomes. Random simulation for planning, not a forecast.",
  [["acct", "Account size ($)", 10000], ["riskp", "Risk per trade (%)", 1], ["win", "Win rate (%)", 45], ["rr", "Reward : risk (R)", 2], ["n", "Trades per sequence", 100], ["sims", "Sequences simulated", 1000]],
  v => { const ends = [], dds = []; let seed = 42; const rnd = () => (seed = (seed * 1664525 + 1013904223) % 4294967296) / 4294967296;
    for (let s = 0; s < Math.min(v.sims, 5000); s++) { let x = v.acct, peak = x, dd = 0; for (let t = 0; t < v.n; t++) { const r = x * v.riskp / 100; x += rnd() < v.win / 100 ? r * v.rr : -r; peak = Math.max(peak, x); dd = Math.max(dd, 1 - x / peak); } ends.push(x); dds.push(dd * 100); }
    ends.sort((a, b) => a - b); dds.sort((a, b) => a - b); const q = (arr, p) => arr[Math.floor(p * (arr.length - 1))];
    return { exp: (v.win / 100 * v.rr - (1 - v.win / 100)), p5: q(ends, 0.05), p50: q(ends, 0.5), p95: q(ends, 0.95), dd50: q(dds, 0.5), dd95: q(dds, 0.95), loss: ends.filter(e => e < v.acct).length / ends.length * 100 }; },
  [["exp", "Expectancy per trade (R)", v => fmt(v, 2) + " R"], ["p50", "Median ending balance", usd], ["p5", "5th percentile ending balance", usd], ["p95", "95th percentile ending balance", usd], ["dd50", "Median max drawdown", v => fmt(v, 1) + "%"], ["dd95", "Bad-case max drawdown (95th pct)", v => fmt(v, 1) + "%"], ["loss", "Sequences ending below start", v => fmt(v, 1) + "%"]]);

/* ======================= J. PLATFORM ======================= */
PAGES["platform/methodology"] = pg => header(pg, "How SOVEREIGN turns data into conclusions.") + `<div class="g g2">
  ${panel("Principles", `<ol class="clean" style="padding-left:18px"><li>Every number carries its source, date and evidence class.</li><li>Data is stored point-in-time: each value keeps the date it applies to and the date the platform first saw it, so backtests never use information that wasn't available.</li><li>Conclusions come from computed scores; text never introduces numbers that aren't stored.</li><li>Disagreement is reported, not averaged away: a Contested label and a confidence figure accompany every score.</li><li>Every outlook is logged and scored when its horizon ends.</li><li>No price targets or probabilities until a scored history supports calibration.</li></ol>`)}
  ${panel("Pipeline", `<ol class="clean" style="padding-left:18px"><li><b>Collect</b> from free official and market sources each morning (07:07 Dubai).</li><li><b>Transform</b> each series (level, change, % change, rolling sum or distance from the 200-day average).</li><li><b>Normalise</b>: z-score against its own 3-year history; signal = direction × z, capped at ±2.</li><li><b>Combine</b> into macro (layer 1) and fundamental (layers 2–4) scores per horizon, scaled to −100…+100.</li><li><b>Technical score</b> from trend, structure and momentum on daily and weekly charts.</li><li><b>Blend</b> into the combined score with horizon weights; compute agreement, confidence and data quality.</li><li><b>Log and score</b> every outlook.</li></ol>`)}</div>
  ${panel("Evidence classes", table([{ t: "Class" }, { t: "Meaning" }], [["Fact", "Published, confirmed figure (CFTC positions, Treasury yields, exchange prices)"], ["Estimate", "Third-party or modelled figure (WGC demand incl. unreported central bank buying, on-chain entity labels)"], ["Historical observation", "What happened before in similar conditions (regime statistics)"], ["Statistical relationship", "Measured correlation with its window"], ["AI interpretation", "Claude's reading of cited evidence (analyst notes)"], ["Model output", "Rule-based scores and outlook text from the engine"]]))}`;
PAGES["platform/sources"] = pg => { const dc = S.data.drivers_config, rows = [];
  Object.entries(dc).forEach(([sym, ds]) => ds.forEach(d => rows.push([assetName(sym), esc(d.name), `<span class="mono sm">${esc(d.series)}</span>`, d.source[1] ? `<a href="${esc(d.source[1])}" target="_blank" rel="noopener">${esc(d.source[0])}</a>` : esc(d.source[0]), esc(d.evidence_class), d.series.startsWith("manual") ? `<span class="dim">Manual file</span>` : "Automatic"])));
  return header(pg, "Every feed behind the scorecards, plus the sourced reference files.") + panel("Driver feeds", table([{ t: "Asset" }, { t: "Driver" }, { t: "Series" }, { t: "Source" }, { t: "Class" }, { t: "Collection" }], rows), "", "flush") +
    `<div style="margin-top:12px">${panel("Reference files (hand-entered, sourced)", table([{ t: "File" }, { t: "Contents" }], [["reference/calendar.json", "confirmed scheduled events"], ["reference/central_banks.json", "policy rates and market pricing"], ["reference/gold_market.json", "WGC quarterly demand, central bank buyers, ETF monthly"], ["reference/btc_market.json", "ETF monthly flows, exchange reserves snapshot, mining and corporate notes"], ["reference/geopolitics.json", "dated developments with read-through"], ["reference/briefings.json", "analyst notes"]]) + `<div class="note">Each item in these files names its source page and date.</div>`)}</div>`; };
PAGES["platform/models"] = pg => { const dc = S.data.drivers_config;
  return header(pg, "Model specification: driver weights, horizon multipliers, blend weights and score bands.") +
    `<div class="g g2">${Object.entries(dc).map(([sym, ds]) => panel(`${assetName(sym)} drivers`, table([{ t: "Driver" }, { t: "Layer", n: 1 }, { t: "Weight", n: 1 }, { t: "Transform" }, { t: "Dir.", n: 1 }, { t: "S/M/L multipliers" }], ds.map(d => [esc(d.name), d.layer, `${Math.round(d.weight * 100)}%`, `${esc(d.transform)}${d.window ? " " + d.window + "d" : ""}`, d.direction > 0 ? "+" : "−", `<span class="mono sm">${d.horizons.short} / ${d.horizons.medium} / ${d.horizons.long}</span>`])), "", "flush")).join("")}</div>` +
    panel("Formulas", `<div class="mono sm" style="line-height:1.9">signal = clip(direction × (x − mean₃ᵧ) ÷ sd₃ᵧ, −2, +2)<br>component score = 50 × Σ(weight × multiplier × signal) ÷ Σ(weight × multiplier)<br>technical = 100 × (0.4 trend + 0.2 structure + 0.4 momentum)<br>combined = Σ(blend × component) ÷ Σ(blend over available components)<br>agreement = active weight on the composite's side ÷ total active weight (|signal| ≥ 0.25)</div><div class="note">Weights are starting assumptions from the specification and will be re-fitted once 6–12 months of scored outlooks exist.</div>`); };
PAGES["platform/data-quality"] = pg => header(pg, "Freshness and coverage of every driver. Stale or missing data lowers confidence automatically.") +
  `<div class="g g2">${S.data.assets.map(a => kpi(`${assetName(a.symbol)} data quality`, `${a.data_quality.score} / 100`, `${statusPill(a.data_quality.label)} · share of driver weight with fresh data`)).join("")}</div>` +
  S.data.assets.map(a => panel(assetName(a.symbol), table([{ t: "Driver" }, { t: "Status" }, { t: "As of" }, { t: "Age (days)", n: 1 }, { t: "Max age", n: 1 }, { t: "Class" }, { t: "Source" }], a.data_quality.rows.map(r => [esc(r.driver), statusPill(r.status), esc(r.as_of || "—"), r.age_days ?? "—", r.max_age, esc(r.evidence_class), `<span class="sm">${esc(r.source)}</span>`])), "", "flush")).join(`<div style="height:12px"></div>`) +
  `<div style="margin-top:12px">${panel("Feed errors in the latest run", Object.keys(S.data.feed_errors).length ? table([{ t: "Series" }, { t: "Error" }], Object.entries(S.data.feed_errors).map(([k, v]) => [`<span class="mono sm">${esc(k)}</span>`, `<span class="sm">${esc(v)}</span>`])) : "None.")}</div>`;
PAGES["platform/about"] = pg => header(pg, "") + `<div class="g g-21">${panel("SOVEREIGN — Global Financial Intelligence", `<p style="font-size:16px;margin:0 0 10px;color:var(--gold2)">Intelligence Without Influence.</p>
  <p>SOVEREIGN is an independent financial intelligence and predictive analytics platform. It researches the forces behind asset prices: macro policy, supply and demand, institutional positioning and price structure. It connects them into evidence-backed outlooks instead of opinions or isolated indicators.</p>
  <p>It starts with gold and Bitcoin, built in depth before adding silver, crude oil, natural gas, major FX pairs, equity indices and listed companies.</p>
  <p>Every conclusion shows its evidence, the evidence against it, what would prove it wrong and how confident the model is. Every outlook is scored against what actually happened.</p>`)}
  ${panel("Status", `<dl class="kv"><dt>Version</dt><dd>v0.2 · SOVEREIGN interface</dd><dt>Build</dt><dd>${esc(S.data.mode)} · ${esc(S.data.generated_at)}</dd><dt>Coverage</dt><dd>Gold, Bitcoin</dd><dt>Update</dt><dd>Daily, 07:07 Dubai</dd></dl><p class="note">A research tool for its owner's decisions. Not investment advice, not a trading signal service.</p>`)}</div>`;
PAGES["platform/settings"] = pg => { mount(() => { document.querySelectorAll("[data-set]").forEach(b => b.onclick = () => { const k = b.dataset.set; if (k === "asset-XAU" || k === "asset-BTC") { S.asset = k.slice(6); lsSet("sov.asset", S.asset); route(); } if (k === "expand") { lsSet("sov.closed", "[]"); buildNav(); route(); } if (k === "collapse") { lsSet("sov.closed", JSON.stringify(NAV.map(n => n[0]))); buildNav(); route(); } }); });
  return header(pg, "Preferences are kept in this browser only.") + `<div class="g g2">${panel("Display", `<dl class="kv"><dt>Default asset</dt><dd><div class="seg">${["XAU", "BTC"].map(s => `<button data-set="asset-${s}" class="${S.asset === s ? "on" : ""}">${assetName(s)}</button>`).join("")}</div></dd><dt>Navigation</dt><dd><button class="btn" data-set="expand">Expand all</button> <button class="btn" data-set="collapse">Collapse all</button></dd></dl>`)}
    ${panel("Data connections", `<dl class="kv"><dt>FRED API key</dt><dd>${S.data.macro.DTWEXBGS?.latest ? statusPill("Good").replace("Good", "Connected") : statusPill("Poor").replace("Poor", "Not set")}<div class="sm dim" style="margin-top:4px">${needKey}</div></dd><dt>Manual files</dt><dd class="sm">Edit CSVs in <span class="mono">manual_inputs/</span> on GitHub; the site rebuilds after each edit.</dd><dt>Run now</dt><dd class="sm">GitHub → Actions → Daily dashboard → Run workflow.</dd></dl>`)}</div>`; };

boot();
