"""
ARGUS — Schwab Bridge
Generates trade intent payloads for Schwab execution adapter consumption.
No direct broker calls. ARGUS is the brain — Schwab is the limb.
"""
from __future__ import annotations
from schemas.state import ScanResponse, PressureBias, StabilityGrade, VeilState
from schemas.trade_intent import TradeIntent, ActionClass


def generate_trade_intent(scan: ScanResponse) -> TradeIntent:
    """
    Convert a ARGUS scan result into a structured trade intent payload.
    The Schwab execution adapter consumes this — it does not drive itself.
    """
    action_class = _classify_action(scan)
    direction = _classify_direction(scan.bias)
    confidence = _compute_confidence(scan)

    invalidation = []
    for agent in scan.agents:
        invalidation.extend(agent.invalidation[:1])  # top 1 per agent

    risk_note = _build_risk_note(scan)

    return TradeIntent(
        ticker=scan.ticker,
        action_class=action_class,
        direction=direction,
        veil_score=scan.veil_score,
        confidence=confidence,
        bias=scan.bias.value,
        stability=scan.stability.value,
        invalidation_conditions=invalidation[:5],
        confirm_above=scan.trigger_map.confirm_above,
        invalidate_below=scan.trigger_map.invalidate_below,
        risk_note=risk_note,
        briefing=scan.briefing[:300],
    )


def _classify_action(scan: ScanResponse) -> ActionClass:
    score = scan.veil_score
    state = scan.state
    stability = scan.stability

    if state in (VeilState.FAILURE, VeilState.TRAP, VeilState.COOLDOWN):
        return ActionClass.OBSERVE_ONLY

    if stability == StabilityGrade.BREAKING:
        return ActionClass.REDUCE_RISK

    if stability == StabilityGrade.DISTORTED:
        if score >= 75:
            return ActionClass.WATCH_FOR_TRIGGER
        return ActionClass.OBSERVE_ONLY

    if score >= 82 and state in (VeilState.TRIGGERED, VeilState.ARMED):
        if stability == StabilityGrade.STABLE:
            return ActionClass.LIVE_HIGH_CONVICTION
        return ActionClass.LIVE_LOW_SIZE

    if score >= 70:
        if stability in (StabilityGrade.STABLE, StabilityGrade.FRAGILE):
            return ActionClass.PAPER_CANDIDATE
        return ActionClass.WATCH_FOR_TRIGGER

    if score >= 55:
        return ActionClass.WATCH_FOR_TRIGGER

    return ActionClass.OBSERVE_ONLY


def _classify_direction(bias: PressureBias) -> str:
    if bias in (PressureBias.BULLISH, PressureBias.UNSTABLE_BULLISH):
        return "long"
    if bias in (PressureBias.BEARISH, PressureBias.UNSTABLE_BEARISH):
        return "short"
    return "none"


def _compute_confidence(scan: ScanResponse) -> float:
    avg_confidence = sum(a.confidence for a in scan.agents) / len(scan.agents) if scan.agents else 0.5
    score_factor = scan.veil_score / 100
    return round(min(1.0, (avg_confidence * 0.6) + (score_factor * 0.4)), 3)


def _build_risk_note(scan: ScanResponse) -> str:
    notes = []
    if scan.event_risk.trap > 0.55:
        notes.append(f"Trap probability elevated at {scan.event_risk.trap:.0%}.")
    if scan.stability == StabilityGrade.DISTORTED:
        notes.append("Distortion present — anomalous conditions may produce unexpected outcomes.")
    if scan.memory_matched and scan.memory_note:
        notes.append(f"Memory: {scan.memory_note[:100]}")
    return " ".join(notes) if notes else "Standard risk parameters apply."
