"""
ARGUS — Schwab Control Routes
Handle OAuth redirects, status reports, and manual execution triggers.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.database import get_session
from core.schwab_executor import SchwabExecutor
from integrations.schwab_bridge import generate_trade_intent
from routes.scan import scan_ticker
from schemas.state import ScanRequest

router = APIRouter()

@router.get("/status", summary="Get Schwab limb connection status")
async def get_schwab_status():
    executor = SchwabExecutor.get_instance()
    return {
        "connected": executor.is_connected,
        "paper_mode": executor.paper_mode,
        "auth_url": executor.get_auth_url() if not executor.is_connected else None
    }

@router.get("/auth-url", summary="Get the Schwab authorization URL")
async def get_auth_url():
    executor = SchwabExecutor.get_instance()
    return {"url": executor.get_auth_url()}

@router.get("/callback", summary="OAuth callback handler")
async def schwab_callback(request: Request):
    """
    Schwab redirects here after user login. 
    URL looks like: /schwab/callback?code=...
    """
    # schwabdev wants the FULL redirect url to parse the code/state
    full_url = str(request.url)
    executor = SchwabExecutor.get_instance()
    try:
        executor.update_tokens(full_url)
        # Redirect back to the dashboard after successful auth
        return RedirectResponse(url="/dashboard")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth failed: {e}")

@router.post("/toggle-mode", summary="Toggle between Paper and Live mode")
async def toggle_paper_mode():
    executor = SchwabExecutor.get_instance()
    executor.paper_mode = not executor.paper_mode
    return {"status": "success", "paper_mode": executor.paper_mode}

@router.post("/execute/{ticker}", summary="Manually execute a trade for a ticker")
async def execute_trade_for_ticker(ticker: str, session: AsyncSession = Depends(get_session)):
    """
    1. Runs a fresh scan for the ticker.
    2. Generates trade intent.
    3. Executes via Schwab limb (Real or Paper).
    """
    ticker = ticker.upper()
    
    # 1. Fresh scan
    scan_req = ScanRequest(ticker=ticker, timeframes=["15m", "1h", "1d"])
    scan_result = await scan_ticker(scan_req, session)
    
    # 2. Build intent
    intent = generate_trade_intent(scan_result)
    
    # 3. Execute
    executor = SchwabExecutor.get_instance()
    result = await executor.execute_trade(intent, session)
    
    return {
        "ticker": ticker,
        "intent": intent,
        "execution": result
    }

@router.get("/positions", summary="Get active paper and live positions")
async def get_positions(session: AsyncSession = Depends(get_session)):
    executor = SchwabExecutor.get_instance()
    return await executor.get_active_positions(session)

@router.post("/close/{mode}/{target_id}", summary="Close an active position")
async def close_position(mode: str, target_id: str, session: AsyncSession = Depends(get_session)):
    executor = SchwabExecutor.get_instance()
    return await executor.close_position(target_id, mode, session)
