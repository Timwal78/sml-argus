"""
ARGUS — Pulse Radar (World Fetch + Pinned Core)

The open-world market scanner. Two modes running together:

1. PINNED CORE — AMC, GME, IWM, SPY always scanned, every cycle.
2. WORLD FETCH — discovers movers via yfinance screener (volume spikes,
   gap ups, unusual activity). The radar finds what you're not looking for.

The radar runs on-demand via POST /radar/sweep, or you can trigger it
from the dashboard. Each sweep:
  - Scans all pinned tickers
  - Discovers top movers via yfinance
  - Runs directives on the best candidates
  - Pushes everything to Discord
  - Returns ranked results to the dashboard
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel, Field

import yfinance as yf

from core.trade_directive import generate_directive, TradeDirective
from core.engine import run_full_cycle
from integrations.discord_dispatcher import send_directive as discord_send_directive
from schemas.state import DataSource
from app.config import get_settings

logger = logging.getLogger("argus.radar")
settings = get_settings()

# ── Pinned Core Tickers — always scanned ─────────────────────────────────────
PINNED_CORE = ["AMC", "GME", "IWM", "SPY"]

# ── World Fetch Discovery Pool ───────────────────────────────────────────────
# These are scanned for unusual activity, then the top movers get full scans
DISCOVERY_POOL = [
    # Meme / retail momentum
    "BBBY", "SOFI", "PLTR", "RIVN", "LCID", "MARA", "RIOT",
    "NIO", "BABA", "SNAP", "HOOD", "DKNG", "RBLX",
    # Large cap momentum
    "TSLA", "NVDA", "AAPL", "MSFT", "AMZN", "META", "GOOG",
    "AMD", "NFLX", "CRM", "SQ", "PYPL", "COIN",
    # ETFs & sectors
    "QQQ", "DIA", "XLF", "XLE", "XLK", "GLD", "SLV",
    "ARKK", "SOXL", "TQQQ", "TNA", "UVXY",
    # Small cap / high beta
    "UPST", "AFRM", "CLOV", "WISH", "OPEN", "SPCE",
]

# How many world-fetch movers to promote to a full scan
MAX_WORLD_FETCH = 8


class RadarResult(BaseModel):
    """Result of a single radar sweep."""
    ticker: str
    source: str = "pinned"  # "pinned" or "discovered"
    directive: Optional[TradeDirective] = None
    error: Optional[str] = None
    scan_time_ms: int = 0


class RadarSweep(BaseModel):
    """Full radar sweep result."""
    sweep_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    pinned_results: List[RadarResult] = []
    discovered_results: List[RadarResult] = []
    discovery_candidates: List[str] = []
    total_scanned: int = 0
    total_actionable: int = 0


async def discover_movers(max_results: int = MAX_WORLD_FETCH) -> List[str]:
    """
    World Fetch: scan the discovery pool for unusual activity.
    Returns tickers ranked by volume surge and price movement.
    Uses yfinance for free, no-API-key discovery.
    """
    logger.info("World Fetch: scanning %d tickers for unusual activity...", len(DISCOVERY_POOL))

    # Fetch quick data for all discovery pool tickers
    movers = []

    try:
        # Batch download 1-day data for all discovery pool tickers
        data = yf.download(
            DISCOVERY_POOL,
            period="2d",
            interval="1d",
            group_by="ticker",
            progress=False,
            threads=True,
        )

        for ticker in DISCOVERY_POOL:
            try:
                if ticker not in data.columns.get_level_values(0):
                    continue

                ticker_data = data[ticker]
                if len(ticker_data) < 2:
                    continue

                today = ticker_data.iloc[-1]
                yesterday = ticker_data.iloc[-2]

                if yesterday["Volume"] == 0 or yesterday["Close"] == 0:
                    continue

                vol_ratio = today["Volume"] / yesterday["Volume"]
                price_change_pct = ((today["Close"] - yesterday["Close"]) / yesterday["Close"]) * 100
                gap_pct = ((today["Open"] - yesterday["Close"]) / yesterday["Close"]) * 100

                # Score the mover: volume surge + absolute price move + gap
                mover_score = (
                    max(0, vol_ratio - 1) * 30 +          # volume surge above normal
                    abs(price_change_pct) * 5 +            # price movement
                    abs(gap_pct) * 8 +                     # gap significance
                    (10 if vol_ratio > 2.0 else 0) +       # big volume bonus
                    (15 if abs(price_change_pct) > 3 else 0)  # big move bonus
                )

                movers.append({
                    "ticker": ticker,
                    "score": mover_score,
                    "vol_ratio": vol_ratio,
                    "price_change": price_change_pct,
                    "gap": gap_pct,
                })
            except Exception:
                continue

    except Exception as e:
        logger.error("World Fetch discovery failed: %s", e)
        return []

    # Sort by mover score descending, take top N
    movers.sort(key=lambda x: x["score"], reverse=True)
    top_movers = [m["ticker"] for m in movers[:max_results]]

    # Filter out pinned tickers (they're already scanned)
    top_movers = [t for t in top_movers if t not in PINNED_CORE]

    logger.info(
        "World Fetch found %d movers: %s",
        len(top_movers),
        ", ".join(f"{m['ticker']}({m['vol_ratio']:.1f}x vol, {m['price_change']:+.1f}%)" for m in movers[:max_results])
    )

    return top_movers[:max_results]


async def run_radar_sweep(
    session,
    pinned: List[str] = None,
    max_discovered: int = MAX_WORLD_FETCH,
    send_discord: bool = True,
) -> RadarSweep:
    """
    Execute a full radar sweep:
    1. Discover world-fetch movers
    2. Scan all pinned tickers
    3. Scan top discovered movers
    4. Rank and push to Discord
    """
    sweep = RadarSweep(
        sweep_id=f"sweep-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
        started_at=datetime.utcnow(),
    )

    pinned_tickers = pinned or PINNED_CORE

    # ── Step 1: World Fetch Discovery ─────────────────────────────────────────
    discovered = await discover_movers(max_discovered)
    sweep.discovery_candidates = discovered

    # ── Step 2: Scan pinned tickers ───────────────────────────────────────────
    logger.info("Radar: scanning %d pinned tickers: %s", len(pinned_tickers), ", ".join(pinned_tickers))

    for ticker in pinned_tickers:
        result = await _scan_ticker_safe(ticker, "pinned", session)
        sweep.pinned_results.append(result)
        if result.directive and send_discord and settings.discord_webhook_url:
            asyncio.create_task(discord_send_directive(result.directive))
        # Small delay to avoid rate limits
        await asyncio.sleep(1.0)

    # ── Step 3: Scan discovered movers ────────────────────────────────────────
    logger.info("Radar: scanning %d discovered movers: %s", len(discovered), ", ".join(discovered))

    for ticker in discovered:
        result = await _scan_ticker_safe(ticker, "discovered", session)
        sweep.discovered_results.append(result)
        if result.directive and send_discord and settings.discord_webhook_url:
            # Only push discovered tickers to Discord if they have an actionable call
            if result.directive.action not in ("NO TRADE — nothing here yet",):
                asyncio.create_task(discord_send_directive(result.directive))
        await asyncio.sleep(1.0)

    # ── Finalize ──────────────────────────────────────────────────────────────
    sweep.completed_at = datetime.utcnow()
    sweep.total_scanned = len(sweep.pinned_results) + len(sweep.discovered_results)
    sweep.total_actionable = sum(
        1 for r in (sweep.pinned_results + sweep.discovered_results)
        if r.directive and "NO TRADE" not in r.directive.action and "STAY OUT" not in r.directive.action
    )

    logger.info(
        "Radar sweep complete: %d scanned, %d actionable, took %.1fs",
        sweep.total_scanned,
        sweep.total_actionable,
        (sweep.completed_at - sweep.started_at).total_seconds(),
    )

    return sweep


async def _scan_ticker_safe(ticker: str, source: str, session) -> RadarResult:
    """Scan a single ticker with error handling."""
    start = datetime.utcnow()
    try:
        scan = await run_full_cycle(
            ticker=ticker,
            timeframe="15m",
            session=session,
            data_source=DataSource.YFINANCE,
        )
        directive = generate_directive(scan)
        elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)
        return RadarResult(
            ticker=ticker,
            source=source,
            directive=directive,
            scan_time_ms=elapsed,
        )
    except Exception as e:
        elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)
        logger.error("Radar scan failed for %s: %s", ticker, e)
        return RadarResult(
            ticker=ticker,
            source=source,
            error=str(e),
            scan_time_ms=elapsed,
        )
