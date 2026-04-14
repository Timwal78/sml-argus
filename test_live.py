"""
ARGUS — Live Real Data Test
Tests yfinance integration + BYOK payload structure
"""
import urllib.request, json, sys, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = "http://localhost:8765"

def scan(ticker, data_source="yfinance", polygon_key=None):
    payload = {
        "ticker": ticker,
        "timeframes": ["1h", "1d"],
        "data_source": data_source,
    }
    if polygon_key:
        payload["polygon_key"] = polygon_key

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{BASE}/scan", data=data,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def show(result):
    score = result["veil_score"]
    filled = int(score / 10)
    bar = "█" * filled + "░" * (10 - filled)
    print(f"\n{'═' * 55}")
    print(f"  {result['ticker']}  [{bar}]  {score:.1f}  |  {result['data_source'].upper()}")
    print(f"  State:    {result['state'].upper()}")
    print(f"  Bias:     {result['bias']}")
    print(f"  Mode:     {result['alert_mode']}")
    print(f"  Stability:{result['stability']}")
    print()
    print(f"  Event Risk:")
    for k, v in result["event_risk"].items():
        b = int(v * 15) * "▪"
        print(f"    {k:<15} {v:.0%}  {b}")
    print()
    print(f"  Agents:")
    for a in result["agents"]:
        f = int(a["score"] / 10)
        b = "█" * f + "░" * (10 - f)
        print(f"    {a['name']:<12} {a['score']:5.1f}  [{b}]  conf:{a['confidence']:.0%}")
    print()
    print(f"  BRIEFING:")
    words = result["briefing"].split()
    line = "  "
    for w in words:
        if len(line) + len(w) > 70:
            print(line)
            line = "  " + w + " "
        else:
            line += w + " "
    if line.strip():
        print(line)

print("\n🔴 ARGUS — SML Market Intelligence Organism")
print("   100 eyes. Always watching. Nothing hidden.")
print("   Powered by: yfinance (real market data)")

tickers = ["AMC", "SPY", "NVDA"]
for t in tickers:
    print(f"\n⏳ Scanning {t} with real market data...")
    try:
        result = scan(t, data_source="yfinance")
        show(result)
    except Exception as e:
        print(f"  ERROR: {e}")
    time.sleep(1)  # be gentle with yfinance rate limits

print(f"\n\n✅ ARGUS is online. Real data. Real intelligence.")
print(f"   API Docs: {BASE}/docs")
print(f"   Health:   {BASE}/health")
