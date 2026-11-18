"""Compare today's run with yesterday's and open a GitHub issue when something material changed.

GitHub emails the repository owner about new issues, so this works as a free alert channel.
Usage (in the daily workflow): python -m tools.notify /tmp/prev_results.json /tmp/prev_global.json
Thresholds are deliberately conservative so alerts stay rare and meaningful.
"""
from __future__ import annotations

import json
import os
import sys

import requests

SCORE_MOVE = 15        # points on the -100..+100 scale
IDX_MOVE, COM_MOVE, FX_MOVE = 3.0, 4.0, 1.5   # % one-day moves
ASSETS = {"XAU": "Gold", "BTC": "Bitcoin"}


def load(p):
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return {}


def score_alerts(prev, cur):
    out = []
    for a, name in ASSETS.items():
        for h in ("short", "medium", "long"):
            p = (prev.get(a) or {}).get("decision", {}).get(h) or {}
            c = (cur.get(a) or {}).get("decision", {}).get(h) or {}
            if not c or not p:
                continue
            if p.get("label") != c.get("label"):
                out.append(f"**{name} {h}-term outlook changed:** {p.get('label')} → **{c.get('label')}** (score {p.get('combined')} → {c.get('combined')}, confidence {c.get('confidence', {}).get('label')})")
            elif p.get("combined") is not None and c.get("combined") is not None and abs(c["combined"] - p["combined"]) >= SCORE_MOVE:
                out.append(f"**{name} {h}-term score moved {c['combined'] - p['combined']:+d} points:** {p['combined']} → {c['combined']} ({c.get('label')})")
            if bool(p.get("contested")) != bool(c.get("contested")):
                out.append(f"**{name} {h}-term signals {'are now contested' if c.get('contested') else 'are no longer contested'}** (agreement {round((c.get('agreement') or 0) * 100)}%)")
    return out


def market_alerts(cur):
    out = []
    m = cur.get("markets") or {}
    for i in m.get("indices", []):
        d = (i.get("perf") or {}).get("d1")
        if d is not None and abs(d) >= IDX_MOVE:
            out.append(f"{i['name']} {d:+.1f}% on {i['perf']['date']}")
    for i in m.get("commodities", []):
        d = (i.get("perf") or {}).get("d1")
        if d is not None and abs(d) >= COM_MOVE:
            out.append(f"{i['name']} {d:+.1f}% on {i['perf']['date']}")
    for s in (cur.get("fx") or {}).get("strength", []):
        a = s.get("absolute") or {}
        if a.get("d1") is not None and abs(a["d1"]) >= FX_MOVE:
            out.append(f"{s['name']} {a['d1']:+.1f}% on {a.get('date')}")
    return out


def rate_alerts(prev, cur):
    out = []
    names = {c["bis"]: c["name"] for c in cur.get("countries", [])}
    for k, r in (cur.get("rates") or {}).items():
        a, b = ((prev.get("rates") or {}).get(k) or {}).get("latest") or {}, (r or {}).get("latest") or {}
        if a.get("value") is not None and b.get("value") is not None and a["value"] != b["value"]:
            out.append(f"**{names.get(k, k)} policy rate:** {a['value']}% → **{b['value']}%** ({b.get('date')})")
    return out


def main():
    prev_r, prev_g = load(sys.argv[1]), load(sys.argv[2])
    cur_r, cur_g = load("data/last_results.json"), load("data/global.json")
    if not prev_g or not cur_g:
        print("[notify] no previous run to compare with")
        return
    scores, rates, moves = [], rate_alerts(prev_g, cur_g) if prev_g else [], market_alerts(cur_g)
    if not (scores or rates or moves):
        print("[notify] nothing material changed")
        return
    date = cur_g.get("generated_at", "")[:10]
    body = ["SOVEREIGN daily alert. These are factual changes in the platform's data and scores, not recommendations.", ""]
    if scores:
        body += ["### Gold and Bitcoin scores", *[f"- {x}" for x in scores], ""]
    if rates:
        body += ["### Central bank policy rates", *[f"- {x}" for x in rates], ""]
    if moves:
        body += [f"### Large one-day moves (indices ≥{IDX_MOVE}%, commodities ≥{COM_MOVE}%, currencies ≥{FX_MOVE}%)", *[f"- {x}" for x in moves], ""]
    body += ["Dashboard: https://cyphercrypt1.github.io/finintel/", "", f"@{os.environ.get('ALERT_USER', 'CypherCrypt1')}"]
    title = f"SOVEREIGN alert {date}: " + ", ".join(x for x in [f"{len(scores)} score change(s)" if scores else "", f"{len(rates)} rate change(s)" if rates else "", f"{len(moves)} large move(s)" if moves else ""] if x)
    text = "\n".join(body)
    print(title + "\n" + text)
    tok, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not tok or not repo:
        return
    r = requests.post(f"https://api.github.com/repos/{repo}/issues", json={"title": title, "body": text, "labels": ["alert"]},
                      headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}, timeout=30)
    print("[notify] issue", r.status_code, r.json().get("html_url") if r.ok else r.text[:200])


if __name__ == "__main__":
    main()
