"""
ARGUS — Chart Data Route
GET /chart/{ticker}   — lightweight Pine-consumable data
GET /chart/multi      — batch chart data for multi-ticker surfaces
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from storage.repository import StateRepository
from core.memory_engine import MemoryEngine
from app.database import get_session

router = APIRouter()


class ChartPoint(BaseModel):
    """Lightweight chart-consumable data point."""
    ticker: str
    veil_score: float = Field(..., ge=0, le=100)
    bias_code: int = Field(..., description="0=neutral, 1=bullish, 2=unstable_bull, -1=bearish, -2=unstable_bear, 3=fractured")
    stability_code: int = Field(..., description="0=stable, 1=fragile, 2=distorted, 3=breaking")
    state_code: int = Field(..., description="0=dormant..6=triggered, 7=distorted, 8=trap, 9=cooldown")
    alert_mode: str
    agent_pressure: float
    agent_structure: float
    agent_behavior: float
    agent_anomaly: float
    agent_cycle: float
    memory_matched: bool = False
    scanned_at: str


_BIAS_MAP = {
    "neutral": 0, "bullish": 1, "unstable_bullish": 2,
    "bearish": -1, "unstable_bearish": -2, "fractured": 3,
}
_STABILITY_MAP = {"stable": 0, "fragile": 1, "distorted": 2, "breaking": 3}
_STATE_MAP = {
    "dormant": 0, "watching": 1, "building": 2, "tension": 3,
    "escalation": 4, "armed": 5, "triggered": 6,
    "distorted": 7, "failure": 8, "trap": 8, "cooldown": 9,
}


@router.get(
    "/chart/{ticker}",
    response_model=ChartPoint,
    summary="Get lightweight chart data for Pine Script consumption",
    tags=["Chart Surface"],
)
async def get_chart_data(
    ticker: str,
    session: AsyncSession = Depends(get_session),
) -> ChartPoint:
    """
    Returns a single lightweight data point for Pine Script external requests.
    No narrative, no full briefing — just numbers for plotting.
    """
    repo = StateRepository(session)
    states = await repo.get_states(ticker.upper(), limit=1)

    if not states:
        raise HTTPException(status_code=404, detail=f"No chart data for {ticker.upper()}")

    state = states[0]
    scores = state.agent_scores or {}

    return ChartPoint(
        ticker=state.ticker,
        veil_score=state.veil_score,
        bias_code=_BIAS_MAP.get(state.bias.value if hasattr(state.bias, 'value') else state.bias, 0),
        stability_code=_STABILITY_MAP.get(state.stability.value if hasattr(state.stability, 'value') else state.stability, 0),
        state_code=_STATE_MAP.get(state.state.value if hasattr(state.state, 'value') else state.state, 0),
        alert_mode="observation",  # derived from state
        agent_pressure=scores.get("pressure", 50.0),
        agent_structure=scores.get("structure", 50.0),
        agent_behavior=scores.get("behavior", 50.0),
        agent_anomaly=scores.get("anomaly", 50.0),
        agent_cycle=scores.get("cycle", 50.0),
        memory_matched=False,
        scanned_at=state.scanned_at.isoformat() if state.scanned_at else datetime.utcnow().isoformat(),
    )


@router.get(
    "/chart/history/{ticker}",
    response_model=List[ChartPoint],
    summary="Get chart data history for timeline visualization",
    tags=["Chart Surface"],
)
async def get_chart_history(
    ticker: str,
    limit: int = Query(default=50, le=200),
    session: AsyncSession = Depends(get_session),
) -> List[ChartPoint]:
    """
    Returns historical chart data points for the command center timeline.
    """
    repo = StateRepository(session)
    states = await repo.get_states(ticker.upper(), limit=limit)

    points = []
    for state in reversed(states):  # oldest → newest
        scores = state.agent_scores or {}
        points.append(ChartPoint(
            ticker=state.ticker,
            veil_score=state.veil_score,
            bias_code=_BIAS_MAP.get(state.bias.value if hasattr(state.bias, 'value') else state.bias, 0),
            stability_code=_STABILITY_MAP.get(state.stability.value if hasattr(state.stability, 'value') else state.stability, 0),
            state_code=_STATE_MAP.get(state.state.value if hasattr(state.state, 'value') else state.state, 0),
            alert_mode="observation",
            agent_pressure=scores.get("pressure", 50.0),
            agent_structure=scores.get("structure", 50.0),
            agent_behavior=scores.get("behavior", 50.0),
            agent_anomaly=scores.get("anomaly", 50.0),
            agent_cycle=scores.get("cycle", 50.0),
            memory_matched=False,
            scanned_at=state.scanned_at.isoformat() if state.scanned_at else datetime.utcnow().isoformat(),
        ))

    return points
