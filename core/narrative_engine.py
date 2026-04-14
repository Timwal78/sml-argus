"""
ARGUS — Narrative Engine
Converts machine state into high-conviction, branded intelligence briefings.
Output tone: classified briefings, machine intuition, field reports.
Not chatty. Not robotic. Not generic.
"""
from __future__ import annotations
from typing import Optional
from schemas.state import (
    PressureBias, StabilityGrade, VeilState, AlertMode, EventRisk, AgentResult
)
from typing import List


# ── Bias language map ──────────────────────────────────────────────────────────
_BIAS_PHRASES = {
    PressureBias.BULLISH: "directional conviction is tilted long",
    PressureBias.UNSTABLE_BULLISH: "bullish pressure is building inside unstable structure",
    PressureBias.BEARISH: "directional conviction is tilted short",
    PressureBias.UNSTABLE_BEARISH: "bearish pressure is rising but conviction is fractured",
    PressureBias.NEUTRAL: "no dominant directional force is present",
    PressureBias.FRACTURED: "internal pressure is contradicting itself — direction is unresolvable",
}

_STABILITY_PHRASES = {
    StabilityGrade.STABLE: "Structure is clean and well-defined.",
    StabilityGrade.FRAGILE: "Structure is holding but showing internal stress.",
    StabilityGrade.DISTORTED: "Distortion is present — the surface reading does not match the underlying state.",
    StabilityGrade.BREAKING: "Structure is breaking down. High-risk environment.",
}

_STATE_OPENERS = {
    VeilState.DORMANT: "No active signal. The organism is observing.",
    VeilState.WATCHING: "State is building. Early conditions are accumulating below threshold.",
    VeilState.BUILDING: "The internal state is developing. Conviction is incomplete but directional.",
    VeilState.TENSION: "Tension is rising. The system is approaching a decision point.",
    VeilState.ESCALATION: "Escalation detected. Internal pressure is reaching critical mass.",
    VeilState.ARMED: "The organism is armed. A trigger event is imminent.",
    VeilState.TRIGGERED: "Trigger confirmed. The hidden state has become visible.",
    VeilState.DISTORTED: "Distortion is active. Something does not match — proceed with elevated caution.",
    VeilState.FAILURE: "State has collapsed. Prior thesis has been invalidated.",
    VeilState.TRAP: "Trap risk is high. The market is attempting to deceive.",
    VeilState.COOLDOWN: "Cooling down after a significant state event.",
}

_ALERT_MODE_SUFFIX = {
    AlertMode.OBSERVATION: "",
    AlertMode.ESCALATION: "This is not a routine observation — escalation requires attention.",
    AlertMode.COMPRESSION_WARNING: "Compression is the setup. The release will be the event.",
    AlertMode.DISTORTION_ALERT: "Anomaly levels are elevated. Standard interpretations should be discarded.",
    AlertMode.TRIGGER_ARMED: "Trigger is armed. The next confirmation or failure will define the thesis.",
    AlertMode.TRAP_RISK: "Trap probability is elevated. Do not chase the surface move.",
    AlertMode.REGIME_BREAK: "A regime-level change may be underway. Prior context may no longer apply.",
}


def generate_briefing(
    ticker: str,
    veil_score: float,
    bias: PressureBias,
    stability: StabilityGrade,
    state: VeilState,
    alert_mode: AlertMode,
    event_risk: EventRisk,
    agents: List[AgentResult],
    memory_matched: bool = False,
    memory_note: Optional[str] = None,
) -> str:
    """
    Generates a high-conviction narrative briefing for the current state.
    """
    parts = []

    # Opening: state declaration
    opener = _STATE_OPENERS.get(state, "State is active.")
    parts.append(opener)

    # Bias sentence
    bias_phrase = _BIAS_PHRASES.get(bias, "")
    if bias_phrase:
        parts.append(f"Currently, {bias_phrase}.")

    # Stability sentence
    stability_phrase = _STABILITY_PHRASES.get(stability, "")
    if stability_phrase:
        parts.append(stability_phrase)

    # Veil score context
    if veil_score >= 80:
        parts.append(f"Veil Score is {veil_score:.0f} — extreme internal pressure detected.")
    elif veil_score >= 65:
        parts.append(f"Veil Score at {veil_score:.0f} — elevated hidden-state intensity.")
    elif veil_score >= 45:
        parts.append(f"Veil Score at {veil_score:.0f} — moderate state, no dominant conviction.")
    else:
        parts.append(f"Veil Score at {veil_score:.0f} — organism is in observation mode.")

    # Dominant event risk
    dominant_risk = event_risk.dominant
    risk_map = {
        "expansion": f"Highest event probability: explosive expansion ({event_risk.expansion:.0%}).",
        "reversal": f"Highest event probability: sharp reversal ({event_risk.reversal:.0%}).",
        "squeeze": f"Highest event probability: squeeze event ({event_risk.squeeze:.0%}).",
        "trap": f"Highest event probability: trap formation ({event_risk.trap:.0%}).",
        "regime_break": f"Highest event probability: regime break ({event_risk.regime_break:.0%}).",
    }
    if dominant_risk in risk_map:
        parts.append(risk_map[dominant_risk])

    # Agent contradiction highlight
    scores = [a.score for a in agents]
    if scores:
        mean = sum(scores) / len(scores)
        spread = max(scores) - min(scores)
        if spread > 40:
            top_agent = max(agents, key=lambda a: a.score)
            bottom_agent = min(agents, key=lambda a: a.score)
            parts.append(
                f"Internal debate is active: {top_agent.name.title()} Agent leads at {top_agent.score:.0f} "
                f"while {bottom_agent.name.title()} Agent dissents at {bottom_agent.score:.0f}."
            )

    # Memory match note
    if memory_matched and memory_note:
        parts.append(f"Memory match: {memory_note}")
    elif memory_matched:
        parts.append("This setup matches a confirmed prior state pattern in memory.")

    # Alert mode closing statement
    suffix = _ALERT_MODE_SUFFIX.get(alert_mode, "")
    if suffix:
        parts.append(suffix)

    return " ".join(parts)
