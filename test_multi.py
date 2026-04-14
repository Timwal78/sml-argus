import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

for ticker in ["GME", "SPY", "NVDA"]:
    data = json.dumps({"ticker": ticker, "timeframes": ["15m","1h","1d"]}).encode()
    req = urllib.request.Request(
        "http://localhost:8765/scan", data=data,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req) as r:
        result = json.loads(r.read())

    score = result["veil_score"]
    filled = int(score / 10)
    bar = "█" * filled + "░" * (10 - filled)
    print(f"\n{'=' * 50}")
    print(f"  {result['ticker']}  [{bar}]  {score:.1f}")
    print(f"  state={result['state'].upper()}  bias={result['bias']}  mode={result['alert_mode']}")
    print(f"  {result['briefing'][:220]}")
