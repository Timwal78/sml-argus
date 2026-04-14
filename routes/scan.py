"""
ARGUS — Scan Route
POST /scan — runs the full intelligence organism on a ticker
"""
from __future__ import annotations
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.state import ScanRequest, ScanResponse, StateSnapshot, DataSource, PressureBias, VeilState
from schemas.alert import AlertPayload
from core.data_adapter import fetch_features
from core.perception import build_synthetic_features
from core import scoring, debate_engine, narrative_engine
from core.memory_engine import MemoryEngine
from agents import pressure_agent, structure_agent, behavior_agent, anomaly_agent, cycle_agent
from integrations import discord_dispatcher
from storage.repository import StateRepository
from app.config import get_settings
from app.database import get_session

router = APIRouter()
settings = get_settings()


@router.post("/scan", response_model=ScanResponse, summary="Run full organism scan on a ticker")
async def scan_ticker(
    request: ScanRequest,
    session: AsyncSession = Depends(get_session),
) -> ScanResponse:
    """
    Core endpoint — runs the full ARGUS intelligence cycle:
    Perception → Agents → Scoring → Debate → Memory → Narrative → Alert

    Supports BYOK (Bring Your Own Key):
    - Pass polygon_key or alphavantage_key in the request body
    - Default: yfinance (free, no key needed)
    """
    repo = StateRepository(session)
    memory = MemoryEngine(repo)

    ticker = request.ticker.upper()
    primary_tf = request.timeframes[0] if request.timeframes else "1d"

    # ── 1. Perception — Real Market Data ──────────────────────────────────────
    use_synthetic = request.data_source == DataSource.SYNTHETIC
    data_source_used = request.data_source.value

    features = await fetch_features(
        ticker=ticker,
        timeframe=primary_tf,
        polygon_key=request.polygon_key,
        alphavantage_key=request.alphavantage_key,
        use_synthetic=use_synthetic,
    )

    # Inject memory context
    features.memory_score = await memory.get_memory_score(ticker, 50.0)

    # ── 2. Agent Layer ─────────────────────────────────────────────────────────
    agents = [
        pressure_agent.run(features),
        structure_agent.run(features),
        behavior_agent.run(features),
        anomaly_agent.run(features),
        cycle_agent.run(features),
    ]

    # ── 3. Initial Scoring ─────────────────────────────────────────────────────
    veil_score = scoring.compute_veil_score(
        agents=agents,
        compression_active=features.compression_detected,
    )

    # ── 4. Memory Match ────────────────────────────────────────────────────────
    p_score = next(a.score for a in agents if a.name == "pressure")
    s_score = next(a.score for a in agents if a.name == "structure")
    quick_bias = PressureBias.BULLISH if (p_score + s_score) / 2 > 55 else PressureBias.BEARISH

    memory_matched, memory_note = await memory.check_memory_match(ticker, veil_score, quick_bias)

    # Rescore with memory bonus
    veil_score = scoring.compute_veil_score(
        agents=agents,
        memory_matched=memory_matched,
        compression_active=features.compression_detected,
    )

    # ── 5. Debate Engine ───────────────────────────────────────────────────────
    debate = debate_engine.resolve(agents, veil_score, memory_matched)

    # ── 6. Narrative Engine ────────────────────────────────────────────────────
    briefing = narrative_engine.generate_briefing(
        ticker=ticker,
        veil_score=veil_score,
        bias=debate.bias,
        stability=debate.stability,
        state=debate.state,
        alert_mode=debate.alert_mode,
        event_risk=debate.event_risk,
        agents=agents,
        memory_matched=memory_matched,
        memory_note=memory_note,
    )

    # ── 7. Build Response ──────────────────────────────────────────────────────
    now = datetime.utcnow()
    response = ScanResponse(
        ticker=ticker,
        veil_score=veil_score,
        state=debate.state,
        bias=debate.bias,
        stability=debate.stability,
        event_risk=debate.event_risk,
        agents=agents,
        briefing=briefing,
        trigger_map=debate.trigger_map,
        alert_mode=debate.alert_mode,
        memory_matched=memory_matched,
        memory_note=memory_note,
        data_source=data_source_used,
        scanned_at=now,
    )

    # ── 8. Persist State ───────────────────────────────────────────────────────
    await repo.insert_state(StateSnapshot(
        ticker=ticker,
        veil_score=veil_score,
        state=debate.state,
        bias=debate.bias,
        stability=debate.stability,
        briefing=briefing,
        agent_scores={a.name: a.score for a in agents},
        scanned_at=now,
    ))

    # ── 9. Discord Alert (escalated states only) ───────────────────────────────
    should_alert = debate.state in (
        VeilState.ARMED, VeilState.TRIGGERED, VeilState.ESCALATION, VeilState.DISTORTED
    )

    if should_alert and settings.discord_webhook_url:
        alert_payload = AlertPayload(
            ticker=ticker,
            mode=debate.alert_mode,
            veil_score=veil_score,
            bias=debate.bias,
            stability=debate.stability,
            state=debate.state,
            event_risk_dominant=debate.event_risk.dominant,
            briefing=briefing,
            memory_matched=memory_matched,
            memory_note=memory_note,
        )
        asyncio.create_task(discord_dispatcher.send_alert(alert_payload))

    return response
