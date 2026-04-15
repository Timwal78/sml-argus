"""
ARGUS — Directive Route
POST /directive         — runs a scan and returns a plain-English trade directive
GET  /directive/{ticker} — quick directive from latest stored state

This is the endpoint you actually READ. Everything else is background.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.state import ScanRequest, ScanResponse, DataSource
from core.engine import run_full_cycle
from core.trade_directive import generate_directive, TradeDirective
from app.config import get_settings
from app.database import get_session

router = APIRouter()
settings = get_settings()


@router.post(
    "/directive",
    response_model=TradeDirective,
    summary="Scan a ticker and get a plain-English trade directive",
    tags=["Trade Directives"],
)
async def get_directive(
    request: ScanRequest,
    session: AsyncSession = Depends(get_session),
) -> TradeDirective:
    """
    The action endpoint. Runs a full scan, then translates the result
    into a plain-English trade directive:

    - **Action**: BUY / SELL / WAIT / STAY OUT
    - **Conviction**: HIGH / MODERATE / LOW / NO TRADE
    - **Levels**: Entry, stop, targets
    - **Risk**: Grade + position size recommendation
    - **Reasoning**: Why, in trader language

    ARGUS is the brain. You are the hands.
    """
    ticker = request.ticker.upper()
    primary_tf = request.timeframes[0] if request.timeframes else "1d"

    scan = await run_full_cycle(
        ticker=ticker,
        timeframe=primary_tf,
        session=session,
        data_source=request.data_source,
        polygon_key=request.polygon_key,
        alpha_vantage_key=request.alpha_vantage_key,
    )

    return generate_directive(scan)
