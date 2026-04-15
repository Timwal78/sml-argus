"""
ARGUS — Intelligence Engine
Central logic for running the full Perception → Agents → Scoring → Debate cycle.
Shared by the API scan route and the background Pulse Radar.

Integration with ECHO FORGE:
  Step 0 runs fetch_features() and fetch_echo_context() *concurrently*.
  Echo context modulates the veil_score at Step 4.5 before the Debate Engine.
  If ECHO FORGE is unavailable or returns low confidence, the cycle runs
  unchanged — ARGUS degrades gracefully, never hard-failing.
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.state import ScanResponse, StateSnapshot, DataSource, PressureBias, VeilState
from schemas.alert import AlertPayload
from schemas.echo_context import EchoContext
from core.data_adapter import fetch_features
from core import scoring, debate_engine, narrative_engine
from core.memory_engine import MemoryEngine
from agents import pressure_agent, structure_agent, behavior_agent, anomaly_agent, cycle_agent
from integrations import discord_dispatcher
from integrations.echo_forge_client import fetch_echo_context
from storage.repository import StateRepository
from app.config import get_settings

logger = logging.getLogger("argus.engine")
settings = get_settings()

# Scoring modulation constants (tuned against the integration spec)
_ECHO_DEFENSIVE_PENALTY = 5.0   # veil_score pts deducted when defensive_mode=True
_ECHO_CONTINUATION_BOOST = 3.0  # pts added when continuation > 65% and bias is bullish
_ECHO_REVERSAL_PENALTY = 4.0    # pts deducted when reversal > 50%


async def run_full_cycle(
    ticker: str,
    timeframe: str,
    session: AsyncSession,
    data_source: DataSource = DataSource.YFINANCE,
    polygon_key: str = None,
    alpha_vantage_key: str = None,
    force_alert: bool = False,
) -> ScanResponse:
    """
    Executes the full intelligence pipeline for a single ticker.
    STRICT DATA INTEGRITY: Synthetic/Mock fallback paths have been removed.
    Failed data acquisition triggers a structural halt.
    """
    repo = StateRepository(session)
    memory = MemoryEngine(repo)
    ticker = ticker.upper()

    # ── 0. Concurrent Pre-fetch: market data + echo context ───────────────────
    features_task = asyncio.create_task(
        fetch_features(
            ticker=ticker,
            timeframe=timeframe,
            polygon_key=polygon_key,
            alpha_vantage_key=alpha_vantage_key,
        )
    )
    echo_task = asyncio.create_task(
        fetch_echo_context(
            ticker=ticker,
            timeframe=timeframe,
            polygon_key=polygon_key,
            window_size=60,
        )
    )

    # Await both — echo failure never blocks the main scan
    features, echo_context = await asyncio.gather(features_task, echo_task)

    if echo_context:
        logger.info(
            "Echo context received for %s: type=%s confidence=%.2f matches=%d defensive=%s",
            ticker, echo_context.echo_type, echo_context.confidence,
            echo_context.n_matches, echo_context.defensive_mode,
        )
    else:
        logger.debug("No echo context for %s (ECHO FORGE disabled or unavailable)", ticker)

    # Inject memory context
    features.memory_score = await memory.get_memory_score(ticker, 50.0)

    # ── 1. Perception — complete ───────────────────────────────────────────────
    # (already done in Step 0 via features_task)

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

    # ── 4.5 Echo Modulation ────────────────────────────────────────────────────
    # Apply echo context to modulate veil_score before the Debate Engine.
    # All modulation is skipped when:
    #   - echo_context is None (ECHO FORGE unavailable)
    #   - echo_context.low_confidence is True (confidence < threshold)
    veil_score = _apply_echo_modulation(veil_score, echo_context, quick_bias)

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
        echo_context=echo_context,
    )

    now = datetime.utcnow()

    # ── 7. Build Response ──────────────────────────────────────────────────────
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
        data_source=data_source.value,
        scanned_at=now,
        echo_context=echo_context,
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

    # ── 9. Discord Alert ───────────────────────────────────────────────────────
    should_alert = force_alert or debate.state in (
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


def _apply_echo_modulation(
    veil_score: float,
    echo_context: Optional[EchoContext],
    bias: PressureBias,
) -> float:
    """
    Modulate the veil_score using ECHO FORGE's structural memory context.

    Rules (per integration spec):
      1. If echo_context is None or low_confidence → no change (return as-is)
      2. If defensive_mode (failure_risk_score > threshold) → apply penalty
      3. If continuation > 65% and bias is bullish → apply confirmation boost
      4. If reversal > 50% → apply reversal penalty (structure is suspect)

    The modulated score is clamped to [0, 100].
    """
    if not echo_context or echo_context.low_confidence:
        return veil_score

    delta = 0.0
    dist = echo_context.outcome_distribution

    # Rule 2: defensive mode
    if echo_context.defensive_mode:
        delta -= _ECHO_DEFENSIVE_PENALTY
        logger.info(
            "Echo defensive mode active (failure_risk_score=%.2f) — applying %.1f pt penalty",
            echo_context.failure_analysis.failure_risk_score if echo_context.failure_analysis else 0.0,
            _ECHO_DEFENSIVE_PENALTY,
        )

    # Rule 3: strong continuation with directional agreement
    if dist.continuation > 0.65 and bias == PressureBias.BULLISH:
        delta += _ECHO_CONTINUATION_BOOST
        logger.info(
            "Echo continuation boost: %.0f%% historical continuation, bullish bias — +%.1f pts",
            dist.continuation * 100, _ECHO_CONTINUATION_BOOST,
        )

    # Rule 4: majority reversal — structure is historically suspect
    if dist.reversal > 0.50:
        delta -= _ECHO_REVERSAL_PENALTY
        logger.info(
            "Echo reversal warning: %.0f%% historical reversal — applying %.1f pt penalty",
            dist.reversal * 100, _ECHO_REVERSAL_PENALTY,
        )

    modulated = veil_score + delta
    return max(0.0, min(100.0, modulated))
