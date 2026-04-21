"""
ARGUS — Scan Route
POST /scan — runs the full intelligence organism on a ticker.

Delegates to core.engine.run_full_cycle which handles:
  Perception → Echo Context (concurrent) → Agents → Scoring →
  Echo Modulation → Debate → Narrative → Persist → Alert
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.state import ScanRequest, ScanResponse, DataSource
from core.engine import run_full_cycle
from app.config import get_settings
from app.database import get_session
from integrations.s3_credit_gate import check_access

router = APIRouter()
settings = get_settings()


@router.post("/scan", response_model=ScanResponse, summary="Run full organism scan on a ticker")
async def scan_ticker(
    request: ScanRequest,
    session: AsyncSession = Depends(get_session),
    x_user_id: str = Header(default="anonymous_user"),
) -> ScanResponse:
    """Core endpoint — protected by S3 Credit Gate."""
    await check_access(user_id=x_user_id, endpoint="scan", session=session)

    Pipeline (inside core/engine.py):
      Step 0  — Concurrent fetch: market data + ECHO FORGE echo context
      Step 1  — Perception (features built)
      Step 2  — Agent layer (5 agents)
      Step 3  — Initial Veil Score
      Step 4  — Memory match + rescore
      Step 4.5— Echo modulation (if echo_context present and confident)
      Step 5  — Debate Engine
      Step 6  — Narrative Engine (includes ECHO FORGE paragraph)
      Step 7  — Build ScanResponse (includes echo_context field)
      Step 8  — Persist state to DB
      Step 9  — Discord alert (escalated states only)

    Supports BYOK (Bring Your Own Key):
      - polygon_key / alphavantage_key forwarded to both data fetcher and ECHO FORGE
      - Default: yfinance (free, no key needed)
    """
    ticker = request.ticker.upper()
    primary_tf = request.timeframes[0] if request.timeframes else "1d"

    return await run_full_cycle(
        ticker=ticker,
        timeframe=primary_tf,
        session=session,
        data_source=request.data_source,
        polygon_key=request.polygon_key,
        alpha_vantage_key=request.alpha_vantage_key,
    )
