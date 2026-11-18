"""Probe: Westmetall LME official prices; Yahoo ALI=F recent days."""
import re, requests
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
for f in ("LME_Al_cash", "LME_Cu_cash", "LME_Ni_cash", "LME_Zn_cash"):
    try:
        r = requests.get("https://www.westmetall.com/en/markdaten.php", params={"action": "table", "field": f}, headers=H, timeout=60)
        print(f"\n### {f}: HTTP {r.status_code} len={len(r.content)}")
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", r.text, re.S)
        for tr in rows[:8]:
            print("  ", [re.sub(r"<[^>]+>|\s+", " ", c).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)])
    except Exception as e:
        print(f, "ERROR", e)
r = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/ALI=F", params={"range": "1mo", "interval": "1d"}, headers=H, timeout=60)
j = r.json()["chart"]["result"][0]; q = j["indicators"]["quote"][0]
print("\n### Yahoo ALI=F meta:", {k: j["meta"].get(k) for k in ("regularMarketPrice", "regularMarketTime", "exchangeName", "currency", "previousClose")})
import datetime
for t, c, v in list(zip(j["timestamp"], q["close"], q["volume"]))[-10:]:
    print("  ", datetime.datetime.utcfromtimestamp(t).date(), c, v)
