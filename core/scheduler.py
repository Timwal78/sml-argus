"""
ARGUS — Auto Sweep Scheduler
Runs the Pulse Radar on a timer during market hours.

- Every 15 minutes during market hours (9:30 AM - 4:00 PM ET)
- Respects free tier daily scan limits
- Pinned core (AMC, GME, IWM, SPY) always scanned
- World fetch discovers movers automatically
- Results pushed to Discord

The organism never sleeps during market hours.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime, time
from typing import Optional

from app.config import get_settings

logger = logging.getLogger("argus.scheduler")
settings = get_settings()

# Market hours (Eastern Time — UTC-4 during EDT)
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)

# Sweep interval in seconds (15 minutes)
SWEEP_INTERVAL = 15 * 60

# Track daily scan count for free tier gating
_daily_scan_count = 0
_daily_reset_date: Optional[str] = None


def _is_market_hours() -> bool:
    """Check if current time is during US market hours (approximate)."""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        # Fallback: assume ET is UTC-4
        from datetime import timedelta, timezone
        et = timezone(timedelta(hours=-4))
        now = datetime.now(et)

    current_time = now.time()
    weekday = now.weekday()  # 0=Monday, 6=Sunday

    # No weekends
    if weekday >= 5:
        return False

    # Market hours
    return MARKET_OPEN <= current_time <= MARKET_CLOSE


def _check_daily_limit() -> bool:
    """Check if we've exceeded the daily scan limit for the current tier."""
    global _daily_scan_count, _daily_reset_date

    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Reset counter on new day
    if _daily_reset_date != today:
        _daily_reset_date = today
        _daily_scan_count = 0
        logger.info("Daily scan counter reset for %s", today)

    max_scans = settings.paid_tier_daily_scans  # Use paid tier for auto-sweep
    if _daily_scan_count >= max_scans:
        logger.warning("Daily scan limit reached (%d/%d). Skipping sweep.", _daily_scan_count, max_scans)
        return False

    return True


def _increment_scan_count(count: int):
    """Increment the daily scan counter."""
    global _daily_scan_count
    _daily_scan_count += count


async def auto_sweep_loop(app):
    """
    Background task that auto-sweeps the market during trading hours.
    Runs as a FastAPI background task via the lifespan.
    """
    logger.info("Auto-sweep scheduler started. Interval: %ds", SWEEP_INTERVAL)

    # Wait a bit for the app to fully initialize
    await asyncio.sleep(10)

    while True:
        try:
            if _is_market_hours():
                if _check_daily_limit():
                    logger.info("Auto-sweep triggered — market hours active")
                    await _run_auto_sweep(app)
                else:
                    logger.info("Auto-sweep skipped — daily limit reached")
            else:
                logger.debug("Auto-sweep skipped — outside market hours")

        except Exception as e:
            logger.error("Auto-sweep error: %s", e, exc_info=True)

        # Wait for next cycle
        await asyncio.sleep(SWEEP_INTERVAL)


async def _run_auto_sweep(app):
    """Execute a single auto-sweep cycle."""
    from core.pulse_radar import run_radar_sweep, PINNED_CORE
    from app.database import get_session_factory

    session_factory = get_session_factory()
    if not session_factory:
        logger.error("No database session factory available for auto-sweep")
        return

    async with session_factory() as session:
        try:
            sweep = await run_radar_sweep(
                session=session,
                pinned=PINNED_CORE,
                max_discovered=4,  # Keep discovery small for auto-sweeps
                send_discord=True,
            )

            _increment_scan_count(sweep.total_scanned)

            logger.info(
                "Auto-sweep complete: %d scanned, %d actionable (daily total: %d)",
                sweep.total_scanned,
                sweep.total_actionable,
                _daily_scan_count,
            )

        except Exception as e:
            logger.error("Auto-sweep execution failed: %s", e, exc_info=True)
