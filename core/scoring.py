"""
ARGUS — Scoring Engine
Computes the Veil Score from weighted agent results + modifiers.
"""
from __future__ import annotations
from typing import List
from schemas.state import AgentResult
from app.config import get_settings

settings = get_settings()


WEIGHTS: dict[str, float] = {
    "pressure": settings.pressure_weight,
    "structure": settings.structure_weight,
    "behavior": settings.behavior_weight,
    "anomaly": settings.anomaly_weight,
    "cycle": settings.cycle_weight,
}


def compute_veil_score(
    agents: List[AgentResult],
    memory_matched: bool = False,
    compression_active: bool = False,
    override_anomaly_boost: bool = False,
) -> float:
    """
    Core Veil Score computation.

    Formula:
        veil_score = base_weighted_score
                   + memory_bonus
                   + anomaly_boost
                   + compression_boost
                   - contradiction_penalty

    Range: 0–100
    """
    # Base weighted score
    base = 0.0
    weight_used = 0.0

    for agent in agents:
        w = WEIGHTS.get(agent.name, 0.0)
        base += agent.score * w
        weight_used += w

    if weight_used > 0:
        base = base / weight_used  # normalize in case weights don't sum to 1

    # ── Modifiers ─────────────────────────────────────────────────────────────

    # Contradiction penalty: when agents disagree strongly, reduce conviction
    agent_scores = [a.score for a in agents]
    if len(agent_scores) > 1:
        mean = sum(agent_scores) / len(agent_scores)
        variance = sum((s - mean) ** 2 for s in agent_scores) / len(agent_scores)
        # penalty scales with disagreement
        penalty = min(settings.contradiction_penalty, (variance / 100) * settings.contradiction_penalty)
    else:
        penalty = 0.0

    # Memory match bonus: prior confirmed pattern increases conviction
    memory_bonus = settings.memory_match_bonus if memory_matched else 0.0

    # Compression boost: compressed state amplifies pending event probability
    compression_boost = settings.compression_boost if compression_active else 0.0

    # Anomaly boost: extreme anomaly elevates overall strangeness score
    anomaly_agent = next((a for a in agents if a.name == "anomaly"), None)
    anomaly_boost = 0.0
    if anomaly_agent and anomaly_agent.score >= settings.anomaly_boost_threshold:
        anomaly_boost = settings.anomaly_boost_value

    veil_score = base + memory_bonus + compression_boost + anomaly_boost - penalty
    veil_score = max(0.0, min(100.0, veil_score))

    return round(veil_score, 2)
