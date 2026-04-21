"""
ARGUS — State & Replay Routes
GET /state/{ticker}    — latest state for a ticker
GET /replay/{ticker}   — full history for state replay (killer feature)
"""
from fastapi import APIRouter, Depends, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from storage.repository import StateRepository
from schemas.state import StateSnapshot, TickerPersonality
from core.memory_engine import MemoryEngine
from app.database import get_session
from integrations.s3_credit_gate import check_access

router = APIRouter()


@router.get(
    "/state/{ticker}",
    response_model=StateSnapshot,
    summary="Get latest state for a ticker",
)
async def get_latest_state(
    ticker: str,
    session: AsyncSession = Depends(get_session),
) -> StateSnapshot:
    repo = StateRepository(session)
    states = await repo.get_states(ticker.upper(), limit=1)
    if not states:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"No state found for {ticker.upper()}")
    return states[0]


@router.get(
    "/replay/{ticker}",
    response_model=List[StateSnapshot],
    summary="Replay the organism's belief evolution for a ticker (killer feature)",
)
async def get_replay(
    ticker: str,
    limit: int = Query(default=100, le=500),
    session: AsyncSession = Depends(get_session),
    x_user_id: str = Header(default="anonymous_user"),
) -> List[StateSnapshot]:
    """
    State Replay: returns the full temporal history of ARGUS's internal belief.
    (Protected by S3 Credit Gate)
    """
    # ── Credit Check ──────────────────────────────────────────────────────────
    await check_access(user_id=x_user_id, endpoint="replay", session=session)
    # ──────────────────────────────────────────────────────────────────────────
    """
    State Replay: returns the full temporal history of ARGUS's internal belief
    for a ticker, from oldest to newest. Watch how the organism saw it forming.
    """
    repo = StateRepository(session)
    memory = MemoryEngine(repo)
    states = await memory.get_replay(ticker.upper(), limit=limit)
    return list(reversed(states))  # oldest → newest for chronological replay


@router.get(
    "/personality/{ticker}",
    response_model=TickerPersonality,
    summary="Get the learned personality profile for a ticker",
)
async def get_personality(
    ticker: str,
    session: AsyncSession = Depends(get_session),
) -> TickerPersonality:
    """
    Ticker Personality: returns the organism's learned behavioral model for a symbol.
    AMC doesn't trade like SPY. The engine knows that.
    """
    repo = StateRepository(session)
    memory = MemoryEngine(repo)
    return await memory.get_or_create_personality(ticker.upper())
