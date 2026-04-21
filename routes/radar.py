"""
ARGUS — Radar Route
POST /radar/sweep    — run a full world-fetch + pinned-core sweep
GET  /radar/status   — get the latest sweep results

The open-world scanner. Discovers movers + always monitors your core tickers.
"""
from __future__ import annotations
import asyncio
from fastapi import APIRouter, Depends, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from core.pulse_radar import run_radar_sweep, RadarSweep, PINNED_CORE
from app.config import get_settings
from app.database import get_session
from integrations.s3_credit_gate import check_access

router = APIRouter()
settings = get_settings()

# Store last sweep in memory for quick access
_last_sweep: Optional[RadarSweep] = None


@router.post(
    "/radar/sweep",
    response_model=RadarSweep,
    summary="Run a full Pulse Radar sweep — world fetch + pinned core",
    tags=["Pulse Radar"],
)
async def radar_sweep(
    max_discovered: int = Query(default=6, le=12, description="Max world-fetch tickers to scan"),
    send_discord: bool = Query(default=True, description="Push results to Discord"),
    session: AsyncSession = Depends(get_session),
    x_user_id: str = Header(default="anonymous_user"),
) -> RadarSweep:
    """
    Runs the full Pulse Radar:
    (Protected by S3 Credit Gate)
    """
    # ── Credit Check ──────────────────────────────────────────────────────────
    await check_access(user_id=x_user_id, endpoint="sweep", session=session)
    # ──────────────────────────────────────────────────────────────────────────
    1. **Pinned Core** — AMC, GME, IWM, SPY scanned every time
    2. **World Fetch** — discovers movers via yfinance (volume spikes, gaps, unusual activity)
    3. **Directive Generation** — each ticker gets a plain-English trade call
    4. **Discord Push** — all results sent to your Discord channel

    Takes 30-60 seconds depending on how many tickers are discovered.
    """
    global _last_sweep
    sweep = await run_radar_sweep(
        session=session,
        pinned=PINNED_CORE,
        max_discovered=max_discovered,
        send_discord=send_discord,
    )
    _last_sweep = sweep
    return sweep


@router.get(
    "/radar/status",
    summary="Get the latest radar sweep results",
    tags=["Pulse Radar"],
)
async def radar_status():
    """Returns the most recent sweep results, or null if no sweep has run."""
    if _last_sweep is None:
        return {"status": "no_sweep_run", "message": "Run POST /radar/sweep to start scanning."}
    return _last_sweep


@router.get(
    "/radar/pinned",
    summary="Get the pinned core ticker list",
    tags=["Pulse Radar"],
)
async def get_pinned():
    """Returns the list of pinned core tickers that are always scanned."""
    return {"pinned": PINNED_CORE}
