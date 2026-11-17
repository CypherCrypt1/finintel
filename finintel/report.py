"""Renders the results dict into one self-contained HTML dashboard (no external files)."""
from __future__ import annotations

import html
import json
from pathlib import Path

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{
  --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --ring:rgba(11,11,11,.10);
  --bull:#2a78d6; --bear:#e34948; --mid:#f0efec; --accent:#2a78d6;
  --warn:#fab219; --good:#006300;
}
@media (prefers-color-scheme: dark){
  :root{ --page:#0d0d0d; --surface:#1a1a19; --ink:#f0efec; --ink2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.10);
    --bull:#3987e5; --bear:#e66767; --mid:#383835; --accent:#3987e5; --good:#0ca30c; }
}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:24px 20px 48px}
header{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:12px;margin-bottom:18px}
h1{font-size:20px;margin:0 0 4px;font-weight:650;letter-spacing:-.01em}
h2{font-size:15px;margin:0 0 10px;font-weight:650}
h3{font-size:13px;margin:0 0 6px;font-weight:650}
.sub{color:var(--ink2);font-size:13px}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;border:1px solid var(--ring);color:var(--ink2);background:var(--surface)}
.badge.snap::before{content:"\25CF ";color:var(--warn)}
.badge.live::before{content:"\25CF ";color:var(--good)}
.tabs{display:flex;gap:6px;margin:4px 0 16px}
.tab{appearance:none;border:1px solid var(--ring);background:var(--surface);color:var(--ink);padding:7px 14px;border-radius:8px;font:inherit;font-weight:600;cursor:pointer}
.tab[aria-selected=true]{border-color:var(--accent);box-shadow:inset 0 0 0 1px var(--accent)}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:16px}
.grid4{display:grid;grid-template-columns:1.1fr 1fr 1fr 1fr;gap:12px;margin-bottom:12px}
.grid2{display:grid;grid-template-columns:1.6fr 1fr;gap:12px;margin-bottom:12px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:12px}
@media (max-width:900px){.grid4{grid-template-columns:1fr 1fr}.grid2,.grid3{grid-template-columns:1fr}}
.kicker{font-size:12px;color:var(--ink2);text-transform:uppercase;letter-spacing:.04em;font-weight:600}
.hero{font-size:30px;font-weight:650;letter-spacing:-.02em;font-variant-numeric:tabular-nums;margin:2px 0}
.stance{font-size:19px;font-weight:650;margin:2px 0 6px}
.num{font-variant-numeric:tabular-nums}
.meter{position:relative;height:8px;background:var(--mid);border-radius:4px;margin:8px 0 6px}
.meter .zero{position:absolute;left:50%;top:-3px;bottom:-3px;width:1px;background:var(--axis)}
.meter .fill{position:absolute;top:0;bottom:0;border-radius:4px}
.meta{font-size:12px;color:var(--ink2)}
table{width:100%;border-collapse:collapse}
th{font-size:12px;color:var(--ink2);font-weight:600;text-align:left;padding:6px 8px;border-bottom:1px solid var(--grid)}
td{padding:8px;border-bottom:1px solid var(--grid);vertical-align:middle}
tr.drv:hover td{background:color-mix(in srgb,var(--accent) 6%,transparent)}
.dname{font-weight:600}
.chip{display:inline-block;font-size:11px;padding:1px 6px;border-radius:4px;border:1px solid var(--ring);color:var(--ink2);margin-right:4px;white-space:nowrap}
.bar{position:relative;height:16px;min-width:150px}
.bar .axis{position:absolute;left:50%;top:0;bottom:0;width:1px;background:var(--axis)}
.bar .b{position:absolute;top:3px;height:10px;border-radius:0}
.bar .b.pos{border-radius:0 4px 4px 0}
.bar .b.neg{border-radius:4px 0 0 4px}
.sig{font-weight:650;font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.missing td{color:var(--muted)}
ul{margin:4px 0 0;padding-left:18px}
li{margin:3px 0}
.olk p{margin:4px 0 8px}
.lbl{font-size:12px;font-weight:650;color:var(--ink2);margin-top:8px}
.levels td{padding:6px 8px}
#tip{position:fixed;pointer-events:none;background:var(--surface);color:var(--ink);border:1px solid var(--ring);border-radius:8px;padding:8px 10px;font-size:12px;max-width:320px;box-shadow:0 4px 16px rgba(0,0,0,.12);display:none;z-index:9}
a{color:var(--accent)}
.legend{display:flex;gap:14px;align-items:center;font-size:12px;color:var(--ink2);margin-bottom:8px}
.sw{display:inline-block;width:10px;height:10px;border-radius:2px;vertical-align:-1px;margin-right:4px}
footer{margin-top:20px;color:var(--ink2);font-size:12px}
.note{font-size:12px;color:var(--ink2);margin-top:8px}
svg text{font:11px system-ui,-apple-system,"Segoe UI",sans-serif;fill:var(--muted)}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div>
    <h1>Global Financial Intelligence Terminal</h1>
    <div class="sub" id="asof"></div>
  </div>
  <div id="mode"></div>
</header>
<div class="tabs" role="tablist" id="tabs"></div>
<main id="view"></main>
<footer id="foot"></footer>
</div>
<div id="tip" role="tooltip"></div>
<script>
const DATA = __DATA__;
const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt = (v, d=2) => v==null||isNaN(v) ? "n/a" : Number(v).toLocaleString("en-US",{minimumFractionDigits:d,maximumFractionDigits:d});
const sgn = v => v==null ? "n/a" : (v>0?"+":"") + Number(v).toFixed(1);
const tip = $("#tip");
function showTip(e, h){ tip.innerHTML = h; tip.style.display = "block";
  const x = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8), y = Math.min(e.clientY + 14, innerHeight - tip.offsetHeight - 8);
  tip.style.left = x + "px"; tip.style.top = y + "px"; }
function hideTip(){ tip.style.display = "none"; }

$("#asof").textContent = `Data as of ${DATA.as_of} · generated ${DATA.generated_at}`;
$("#mode").innerHTML = DATA.mode === "live"
  ? `<span class="badge live">Live engine run</span>`
  : `<span class="badge snap">Snapshot: readings looked up by hand, signals assigned by Claude</span>`;

const slug = a => a.symbol === "XAU" ? "gold" : "bitcoin";
const tabs = $("#tabs");
DATA.assets.forEach(a => { const b = document.createElement("button"); b.className = "tab"; b.setAttribute("role","tab");
  b.textContent = a.name; b.dataset.slug = slug(a); b.onclick = () => { location.hash = slug(a); }; tabs.appendChild(b); });

function meter(c){ if (c==null) return `<div class="meter"><span class="zero"></span></div>`;
  const w = Math.min(Math.abs(c),2)/2*50, col = c>=0 ? "var(--bull)" : "var(--bear)";
  const left = c>=0 ? 50 : 50-w;
  return `<div class="meter" aria-hidden="true"><span class="fill" style="left:${left}%;width:${w}%;background:${col}"></span><span class="zero"></span></div>`; }

function horizonTile(a, h, label){ const s = a.scores[h];
  return `<div class="card"><div class="kicker">${label}</div><div class="stance">${esc(s.stance)}</div>
  ${meter(s.composite)}<div class="meta num">Composite ${sgn(s.composite)} of ±2 · agreement ${s.agreement==null?"n/a":Math.round(s.agreement*100)+"%"}
  · coverage ${Math.round((s.coverage||0)*100)}% of weight</div></div>`; }

function scorecard(a){
  const rows = [...a.drivers].sort((x,y)=> (y.signal==null?-1:Math.abs(y.signal*y.weight)) - (x.signal==null?-1:Math.abs(x.signal*x.weight)));
  const body = rows.map((d,i) => {
    if (d.signal==null) return `<tr class="missing"><td><div class="dname">${esc(d.name)}</div><span class="chip">Layer ${d.layer}</span></td>
      <td colspan="3">Not collected (${esc(d.note||"no data")})</td><td class="num">${Math.round(d.weight*100)}%</td></tr>`;
    const w = Math.min(Math.abs(d.signal),2)/2*50, pos = d.signal>=0;
    const bar = `<div class="bar" aria-label="signal ${sgn(d.signal)}"><span class="axis"></span><span class="b ${pos?"pos":"neg"}" style="${pos?`left:50%`:`left:${50-w}%`};width:${w}%;background:${pos?"var(--bull)":"var(--bear)"}"></span></div>`;
    return `<tr class="drv" data-i="${i}"><td><div class="dname">${esc(d.name)}</div><span class="chip">Layer ${d.layer}</span><span class="chip">${esc(d.evidence_class)}</span></td>
      <td><div>${esc(d.reading)}</div><div class="meta">${esc(d.as_of||"")} · ${d.source_url?`<a href="${esc(d.source_url)}" target="_blank" rel="noopener">${esc(d.source_name)}</a>`:esc(d.source_name)}</div></td>
      <td>${bar}</td><td class="sig">${sgn(d.signal)}</td><td class="num">${Math.round(d.weight*100)}%</td></tr>`; }).join("");
  return {rows, html:`<div class="card" style="margin-bottom:12px"><h2>Driver scorecard</h2>
    <div class="legend"><span><span class="sw" style="background:var(--bear)"></span>Bearish for price</span><span><span class="sw" style="background:var(--bull)"></span>Bullish for price</span><span>Scale −2 to +2, sorted by weighted contribution</span></div>
    <table><thead><tr><th>Driver</th><th>Latest reading</th><th style="text-align:center">−2 &nbsp; signal &nbsp; +2</th><th style="text-align:right">Signal</th><th>Weight</th></tr></thead><tbody>${body}</tbody></table></div>`}; }

function priceChart(a){
  const h = a.history||[]; if (h.length < 2) return `<div class="card"><h2>Price</h2><p class="meta">No price history in this file.</p></div>`;
  const W=640,H=260,L=56,R=86,T=14,B=26; const xs=h.map((p,i)=>i), ys=h.map(p=>p[1]);
  const lv = [...(a.levels.support||[]), ...(a.levels.resistance||[])].map(l=>l.price);
  let lo=Math.min(...ys,...lv), hi=Math.max(...ys,...lv); const pad=(hi-lo)*0.08||1; lo-=pad; hi+=pad;
  const X=i=>L+(i/(h.length-1))*(W-L-R), Y=v=>T+(1-(v-lo)/(hi-lo))*(H-T-B);
  const ticks=[]; const step=(hi-lo)/4; for(let k=0;k<=4;k++) ticks.push(lo+step*k);
  const path=h.map((p,i)=>(i?"L":"M")+X(i).toFixed(1)+" "+Y(p[1]).toFixed(1)).join("");
  const dec = a.symbol==="BTC"?0:0;
  const lvl=(l,kind)=>`<line x1="${L}" x2="${W-R}" y1="${Y(l.price)}" y2="${Y(l.price)}" stroke="var(--axis)" stroke-dasharray="4 4"/><text x="${W-R+6}" y="${Y(l.price)+4}">${kind} ${fmt(l.price,dec)}</text>`;
  const xl=[0,Math.floor((h.length-1)/2),h.length-1].map(i=>`<text x="${X(i)}" y="${H-6}" text-anchor="middle">${esc(h[i][0].slice(5))}</text>`).join("");
  return `<div class="card"><h2>Price, ${esc(a.history_label||"")}</h2>
  <svg id="pc" viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Price chart with key levels">
  ${ticks.map(t=>`<line x1="${L}" x2="${W-R}" y1="${Y(t)}" y2="${Y(t)}" stroke="var(--grid)"/><text x="${L-6}" y="${Y(t)+4}" text-anchor="end">${fmt(t,0)}</text>`).join("")}
  ${(a.levels.support||[]).map(l=>lvl(l,"S")).join("")}${(a.levels.resistance||[]).map(l=>lvl(l,"R")).join("")}
  <path d="${path}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round"/>
  ${xl}<line id="ch" y1="${T}" y2="${H-B}" stroke="var(--axis)" style="display:none"/><circle id="cd" r="4" fill="var(--accent)" stroke="var(--surface)" stroke-width="2" style="display:none"/>
  <rect x="${L}" y="${T}" width="${W-L-R}" height="${H-T-B}" fill="transparent" id="hit"/></svg>
  <div class="note">${esc(a.price_note||"")}</div></div>`; }

function wireChart(a){
  const svg=$("#pc"); if(!svg) return; const h=a.history; const W=640,L=56,R=86,T=14,B=26,H=260;
  const ys=h.map(p=>p[1]); const lv=[...(a.levels.support||[]),...(a.levels.resistance||[])].map(l=>l.price);
  let lo=Math.min(...ys,...lv),hi=Math.max(...ys,...lv); const pad=(hi-lo)*0.08||1; lo-=pad; hi+=pad;
  const X=i=>L+(i/(h.length-1))*(W-L-R), Y=v=>T+(1-(v-lo)/(hi-lo))*(H-T-B);
  const hit=$("#hit"), ch=$("#ch"), cd=$("#cd");
  hit.addEventListener("mousemove", e=>{ const r=svg.getBoundingClientRect(); const sx=(e.clientX-r.left)*W/r.width;
    const i=Math.max(0,Math.min(h.length-1,Math.round((sx-L)/(W-L-R)*(h.length-1))));
    ch.setAttribute("x1",X(i)); ch.setAttribute("x2",X(i)); ch.style.display="block";
    cd.setAttribute("cx",X(i)); cd.setAttribute("cy",Y(h[i][1])); cd.style.display="block";
    showTip(e, `<b>${esc(h[i][0])}</b><br>Close ${fmt(h[i][1], 2)}`); });
  hit.addEventListener("mouseleave", ()=>{ ch.style.display="none"; cd.style.display="none"; hideTip(); });
}

function levelsCard(a){ const l=a.levels;
  const row=(k,x)=>`<tr><td><b>${k}</b></td><td class="num">${fmt(x.price,2)}</td><td class="meta">${esc(x.label)}</td></tr>`;
  return `<div class="card"><h2>Key levels</h2><table class="levels"><tbody>
  ${(l.resistance||[]).slice().reverse().map((x,i,arr)=>row("R"+(arr.length-i),x)).join("")}
  <tr><td><b>Last</b></td><td class="num"><b>${fmt(a.price,2)}</b></td><td class="meta">${esc(a.price_date||"")}</td></tr>
  ${(l.support||[]).map((x,i)=>row("S"+(i+1),x)).join("")}
  ${l.sma200!=null?`<tr><td>200-day avg</td><td class="num">${fmt(l.sma200,2)}</td><td></td></tr>`:""}
  ${l.high_52w!=null?`<tr><td>52-wk range</td><td class="num" colspan="2">${fmt(l.low_52w,0)} to ${fmt(l.high_52w,0)}</td></tr>`:""}
  </tbody></table>${l.note?`<div class="note">${esc(l.note)}</div>`:""}</div>`; }

function list(items){ return items&&items.length ? `<ul>${items.map(x=>`<li>${esc(x)}</li>`).join("")}</ul>` : `<p class="meta">None.</p>`; }

function outlooks(a){ return `<div class="grid3">${(a.outlooks||[]).map(o=>`<div class="card olk">
  <div class="kicker">${esc(o.horizon)}</div><div class="stance">${esc(o.stance)}</div>
  <span class="chip">${esc(o.evidence_class||"AI interpretation")}</span>
  <p>${esc(o.thesis)}</p>
  <div class="lbl">Supporting</div>${list(o.supports)}
  <div class="lbl">Contradicting</div>${list(o.contradicts)}
  <div class="lbl">Would invalidate</div>${list(o.invalidation)}
  <div class="lbl">Would confirm</div>${list(o.confirmation)}
  </div>`).join("")}</div>`; }

function render(){
  const s = (location.hash||"#gold").slice(1); const a = DATA.assets.find(x=>slug(x)===s) || DATA.assets[0];
  document.querySelectorAll(".tab").forEach(t=>t.setAttribute("aria-selected", t.dataset.slug===slug(a)));
  const sc = scorecard(a);
  $("#view").innerHTML = `
  <div class="grid4">
    <div class="card"><div class="kicker">${esc(a.name)}</div><div class="hero">${fmt(a.price, 2)}</div>
      <div class="meta">${esc(a.price_date||"")} · ${esc(a.price_source||"")}</div>
      ${a.price_change?`<div class="meta" style="margin-top:6px">${esc(a.price_change)}</div>`:""}</div>
    ${horizonTile(a,"long","Long term · 1–12 months")}${horizonTile(a,"medium","Medium term · 1–4 weeks")}${horizonTile(a,"short","Short term · 1–5 days")}
  </div>
  ${sc.html}
  <div class="grid2">${priceChart(a)}${levelsCard(a)}</div>
  <h2 style="margin:18px 0 10px">Outlooks</h2>${outlooks(a)}
  <div class="grid2"><div class="card"><h2>Contradictions</h2>${list(a.contradictions)}<h2 style="margin-top:14px">What changed</h2>${list(a.changes)}</div>
  <div class="card"><h2>Not collected yet</h2>${list(a.missing)}<div class="note">Missing drivers are left out of the composite; coverage on each horizon tile shows how much weight had data.</div></div></div>`;
  document.querySelectorAll("tr.drv").forEach(tr => { const d = sc.rows[+tr.dataset.i];
    tr.addEventListener("mousemove", e=>showTip(e, `<b>${esc(d.name)}</b><br>Signal ${sgn(d.signal)} · weight ${Math.round(d.weight*100)}%<br>Bullish when: ${esc(d.bullish_when)}${d.z!=null?`<br>z-score ${Number(d.z).toFixed(2)}, percentile ${Math.round(d.percentile)}`:""}${d.note?`<br>${esc(d.note)}`:""}`));
    tr.addEventListener("mouseleave", hideTip); });
  wireChart(a);
}
addEventListener("hashchange", render); render();

$("#foot").innerHTML = `<div class="card"><h2>Sources</h2>${DATA.sources&&DATA.sources.length?`<ul>${DATA.sources.map(s=>`<li><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title)}</a></li>`).join("")}</ul>`:`<p class="meta">Listed per driver.</p>`}
<p class="note">Evidence classes: Fact (published figure) · Estimate (third-party or modelled figure) · AI interpretation (Claude's reading of the evidence) · Model forecast. ${esc(DATA.disclaimer||"")}</p></div>`;
</script>
</body>
</html>
"""


def render(results: dict, out: Path) -> Path:
    data = json.dumps(results, default=str).replace("</", "<\\/")
    page = TEMPLATE.replace("__TITLE__", html.escape(results.get("title", "Financial Intelligence Terminal"))) \
                   .replace("__DATA__", data)
    out.write_text(page, encoding="utf-8")
    return out
