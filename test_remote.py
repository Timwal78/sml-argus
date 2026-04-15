import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = "https://sml-argus.onrender.com"

def scan(ticker):
    payload = json.dumps({"ticker": ticker, "timeframes": ["1h","1d"]}).encode()
    req = urllib.request.Request(
        f"{BASE}/scan", data=payload,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def show(result):
    score = result["veil_score"]
    filled = int(score / 10)
    bar = "█" * filled + "░" * (10 - filled)
    print(f"\n{'═'*55}")
    print(f"  ARGUS // {result['ticker']} // {result['alert_mode'].upper()} ⚡")
    print(f"{'═'*55}")
    print(f"  Score:     [{bar}]  {score:.1f} / 100")
    print(f"  State:     {result['state'].upper()}")
    print(f"  Bias:      {result['bias'].upper()}")
    print(f"  Stability: {result['stability'].upper()}")
    print(f"  Data:      {result['data_source'].upper()} (real market data)")
    print()
    print(f"  EVENT RISK:")
    for k, v in result["event_risk"].items():
        b = int(v * 20) * "▪"
        print(f"    {k:<15} {v:.0%}  {b}")
    print()
    print(f"  AGENTS:")
    for a in result["agents"]:
        f = int(a["score"] / 10)
        b = "█" * f + "░" * (10 - f)
        print(f"    {a['name']:<12} {a['score']:5.1f}  [{b}]")
    print()
    words = result["briefing"].split()
    line = "  "
    for w in words:
        if len(line) + len(w) > 68:
            print(line)
            line = "  " + w + " "
        else:
            line += w + " "
    if line.strip():
        print(line)

for ticker in ["AMC", "SPY", "NVDA"]:
    print(f"\n⏳ ARGUS scanning {ticker}...")
    try:
        result = scan(ticker)
        show(result)
    except Exception as e:
        print(f"  ERROR: {e}")

print(f"\n\n  SML ARGUS — 100 eyes. Always watching. Nothing hidden.")
print(f"  https://sml-argus.onrender.com")
