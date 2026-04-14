# ARGUS

> **A standalone market intelligence organism.**  
> Detects, scores, debates, remembers, and narrates market pressure before it becomes obvious.

---

## What This Is

ARGUS is not a trading bot. It's not a dashboard. It's not an indicator.

It is a **synthetic market entity** — an intelligence layer that forms an evolving internal "belief state" about a ticker, sector, or market regime, then narrates what it sees in human-readable machine-intelligence language.

---

## Core Outputs

| Output | Description |
|--------|-------------|
| **Veil Score** | Hidden-state intensity, 0–100 |
| **Pressure Bias** | Bullish / Bearish / Neutral / Fractured |
| **Stability Grade** | Stable / Fragile / Distorted / Breaking |
| **Event Risk** | Expansion / Reversal / Squeeze / Trap probability |
| **Narrative Briefing** | Machine-generated field report |
| **Trigger Map** | What confirms or kills the thesis |

---

## Architecture

```
Perception → 5 Agents → Debate Engine → Memory Engine → Narrative Engine → API
```

### The 5 Internal Agents

| Agent | Role |
|-------|------|
| **Pressure** | Directional force, volume, VWAP, compression/expansion |
| **Structure** | Trend integrity, pivots, MACD, ATR |
| **Behavior** | Crowd psychology — chase, panic, exhaustion, squeeze |
| **Anomaly** | Things that should not be happening — hidden absorption, divergence |
| **Cycle** | Timing symmetry, fractal repetition, memory matches |

The agents **disagree**. The Debate Engine resolves their conflict into a final state.

### State Machine

```
Dormant → Watching → Building → Tension → Escalation → Armed → Triggered
                                                               ↓
                                                     Distorted / Trap / Failure → Cooldown
```

---

## Killer Features

### 1. State Replay
Pick any ticker and watch the organism's internal belief evolve over time — candle by candle. Not price replay. **Intelligence replay.** See when pressure built, when the anomaly agent fired, when the thesis broke.

### 2. Debate Transcript
When a signal escalates, inspect *why* the system changed its mind. Which agent overruled which. What conditions tipped the vote.

### 3. Ticker Personality
ARGUS learns how each symbol behaves. AMC doesn't trade like SPY. The engine knows that from experience.

---

## Integrations

| Integration | Role |
|-------------|------|
| **Discord** | Branded intelligence briefings — not alerts, *field reports* |
| **Pine (TradingView)** | Visual surface + webhook ingestion into the core engine |
| **Schwab** | Execution limb — consumes trade intent payloads from the brain |
| **S3 Credits** | Economic shell — free/paid tiers, per-endpoint credit costs |

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# edit .env with your Discord webhook URL
```

### 3. Run (dev mode — SQLite)
```bash
uvicorn app.main:app --reload
```

### 4. Run a scan
```bash
curl -X POST http://localhost:8000/scan \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AMC", "timeframes": ["15m", "1h", "1d"]}'
```

### 5. Get state history
```bash
curl http://localhost:8000/state/AMC
```

### 6. Replay intelligence history
```bash
curl http://localhost:8000/replay/AMC
```

---

## Docker (Production)
```bash
docker-compose up --build
```

---

## Run Tests
```bash
pytest tests/ -v
```

---

## Phase Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1** | ✅ Built | Standalone organism — scan, score, debate, memory, narrative, Discord |
| **Phase 2** | Next | Pine chart surface — Veil Score, bias, anomaly markers |
| **Phase 3** | Planned | Schwab paper mode → live execution |
| **Phase 4** | Planned | S3 credit monetization, premium API, user tiers |

---

## Brand

```
ARGUS — See the hidden market state before the move becomes obvious.
Not a signal. A synthetic intelligence layer.
The market moves twice: once underneath, once on the chart.
```

---

*Built with Google Antigravity.*
