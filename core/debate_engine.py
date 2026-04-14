"""
ARGUS — Debate Engine
Resolves multi-agent conflict into a final unified state and briefing.
This is where individual agent theses are weighed, argued, and reconciled.
"""
from __future__ import annotations
from typing import List, Dict, Tuple
from schemas.state import (
    AgentResult, PressureBias, StabilityGrade, VeilState, AlertMode, EventRisk, TriggerMap
)
from app.config import get_settings


settings = get_settings()


class DebateResult:
    def __init__(
        self,
        veil_score: float,
        bias: PressureBias,
        stability: StabilityGrade,
        state: VeilState,
        alert_mode: AlertMode,
        event_risk: EventRisk,
        trigger_map: TriggerMap,
        contradiction_level: float,
        dominant_agents: List[str],
        minority_agents: List[str],
        debate_summary: str,
    ):
        self.veil_score = veil_score
        self.bias = bias
        self.stability = stability
        self.state = state
        self.alert_mode = alert_mode
        self.event_risk = event_risk
        self.trigger_map = trigger_map
        self.contradiction_level = contradiction_level
        self.dominant_agents = dominant_agents
        self.minority_agents = minority_agents
        self.debate_summary = debate_summary


def resolve(
    agents: List[AgentResult],
    veil_score: float,
    memory_matched: bool = False,
) -> DebateResult:
    """
    The debate engine takes all agent results and resolves their disagreements
    into a final coherent state.
    """
    agent_map: Dict[str, AgentResult] = {a.name: a for a in agents}
    scores = {a.name: a.score for a in agents}

    pressure = scores.get("pressure", 50)
    structure = scores.get("structure", 50)
    behavior = scores.get("behavior", 50)
    anomaly = scores.get("anomaly", 30)
    cycle = scores.get("cycle", 50)

    # ── Contradiction Analysis ─────────────────────────────────────────────────
    # Calculate variance between agents as a measure of disagreement
    values = list(scores.values())
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    contradiction_level = min(1.0, variance / 1000)  # normalize 0–1

    # ── Dominant vs Minority Agents ────────────────────────────────────────────
    dominant_agents = [a for a in scores if scores[a] >= mean + 10]
    minority_agents = [a for a in scores if scores[a] <= mean - 10]

    # ── Bias Determination ─────────────────────────────────────────────────────
    bias = _determine_bias(pressure, structure, anomaly, contradiction_level)

    # ── Stability Grade ────────────────────────────────────────────────────────
    stability = _determine_stability(anomaly, structure, contradiction_level)

    # ── Veil State Machine ─────────────────────────────────────────────────────
    state = _determine_state(veil_score, anomaly, structure, behavior, memory_matched)

    # ── Alert Mode ────────────────────────────────────────────────────────────
    alert_mode = _determine_alert_mode(state, anomaly, bias)

    # ── Event Risk ────────────────────────────────────────────────────────────
    event_risk = _compute_event_risk(pressure, structure, behavior, anomaly, cycle)

    # ── Trigger Map ───────────────────────────────────────────────────────────
    trigger_map = _build_trigger_map(agents)

    # ── Debate Summary ────────────────────────────────────────────────────────
    debate_summary = _write_debate_summary(
        agents, bias, stability, state, contradiction_level, dominant_agents, minority_agents
    )

    return DebateResult(
        veil_score=veil_score,
        bias=bias,
        stability=stability,
        state=state,
        alert_mode=alert_mode,
        event_risk=event_risk,
        trigger_map=trigger_map,
        contradiction_level=contradiction_level,
        dominant_agents=dominant_agents,
        minority_agents=minority_agents,
        debate_summary=debate_summary,
    )


def _determine_bias(
    pressure: float, structure: float, anomaly: float, contradiction: float
) -> PressureBias:
    avg = (pressure + structure) / 2
    if contradiction > 0.55:
        return PressureBias.FRACTURED
    if anomaly > 75 and contradiction > 0.35:
        return PressureBias.FRACTURED
    if avg >= 65:
        return PressureBias.BULLISH if contradiction < 0.3 else PressureBias.UNSTABLE_BULLISH
    if avg >= 55:
        return PressureBias.UNSTABLE_BULLISH
    if avg <= 35:
        return PressureBias.BEARISH if contradiction < 0.3 else PressureBias.UNSTABLE_BEARISH
    if avg <= 45:
        return PressureBias.UNSTABLE_BEARISH
    return PressureBias.NEUTRAL


def _determine_stability(
    anomaly: float, structure: float, contradiction: float
) -> StabilityGrade:
    if anomaly > 80 or contradiction > 0.6:
        return StabilityGrade.DISTORTED
    if anomaly > 65 or structure < 35:
        if contradiction > 0.4:
            return StabilityGrade.BREAKING
        return StabilityGrade.FRAGILE
    if structure < 45 or contradiction > 0.4:
        return StabilityGrade.FRAGILE
    return StabilityGrade.STABLE


def _determine_state(
    veil_score: float,
    anomaly: float,
    structure: float,
    behavior: float,
    memory_matched: bool,
) -> VeilState:
    if veil_score >= 85:
        return VeilState.TRIGGERED if structure > 55 else VeilState.ARMED
    if veil_score >= 75:
        if anomaly > 78:
            return VeilState.DISTORTED
        return VeilState.ARMED
    if veil_score >= 65:
        return VeilState.ESCALATION
    if veil_score >= 55:
        return VeilState.TENSION
    if veil_score >= 45:
        return VeilState.BUILDING if memory_matched else VeilState.WATCHING
    if veil_score >= 30:
        return VeilState.WATCHING
    return VeilState.DORMANT


def _determine_alert_mode(
    state: VeilState,
    anomaly: float,
    bias: PressureBias,
) -> AlertMode:
    if state in (VeilState.TRIGGERED, VeilState.ARMED):
        return AlertMode.TRIGGER_ARMED
    if state == VeilState.DISTORTED or anomaly > 80:
        return AlertMode.DISTORTION_ALERT
    if state in (VeilState.ESCALATION, VeilState.TENSION):
        return AlertMode.ESCALATION
    if bias == PressureBias.FRACTURED:
        return AlertMode.TRAP_RISK
    if state == VeilState.BUILDING:
        return AlertMode.COMPRESSION_WARNING
    return AlertMode.OBSERVATION


def _compute_event_risk(
    pressure: float, structure: float, behavior: float, anomaly: float, cycle: float
) -> EventRisk:
    def norm(v: float) -> float:
        return v / 100.0

    expansion = round(
        min(1.0, norm(pressure) * 0.4 + norm(structure) * 0.3 + norm(cycle) * 0.3), 3
    )
    reversal = round(
        min(1.0, (1 - norm(pressure)) * 0.35 + norm(anomaly) * 0.35 + (1 - norm(structure)) * 0.3), 3
    )
    squeeze = round(
        min(1.0, norm(behavior) * 0.5 + norm(anomaly) * 0.3 + norm(pressure) * 0.2), 3
    )
    trap = round(
        min(1.0, norm(anomaly) * 0.4 + (1 - norm(structure)) * 0.35 + norm(behavior) * 0.25), 3
    )
    regime_break = round(
        min(1.0, norm(anomaly) * 0.5 + (1 - norm(structure)) * 0.3 + norm(cycle) * 0.2), 3
    )

    return EventRisk(
        expansion=expansion,
        reversal=reversal,
        squeeze=squeeze,
        trap=trap,
        regime_break=regime_break,
    )


def _build_trigger_map(agents: List[AgentResult]) -> TriggerMap:
    conditions = []
    for agent in agents:
        conditions.extend(agent.trigger_conditions[:2])  # top 2 per agent

    return TriggerMap(conditions=conditions[:8])  # cap at 8 total


def _write_debate_summary(
    agents: List[AgentResult],
    bias: PressureBias,
    stability: StabilityGrade,
    state: VeilState,
    contradiction: float,
    dominant: List[str],
    minority: List[str],
) -> str:
    lines = []
    scores_fmt = ", ".join(
        f"{a.name.title()} {a.score:.0f} ({a.confidence:.0%})" for a in agents
    )
    lines.append(f"Agent votes: {scores_fmt}")

    if contradiction > 0.5:
        lines.append(
            f"High internal disagreement ({contradiction:.0%} variance). "
            f"Dominant: {', '.join(dominant) or 'none'}. Minority dissent: {', '.join(minority) or 'none'}."
        )
    elif contradiction > 0.25:
        lines.append(f"Moderate disagreement. Minority dissent from: {', '.join(minority) or 'none'}.")
    else:
        lines.append("Agents are broadly aligned.")

    lines.append(f"Final state: {state.value.upper()} | Bias: {bias.value} | Stability: {stability.value}.")

    return " ".join(lines)
