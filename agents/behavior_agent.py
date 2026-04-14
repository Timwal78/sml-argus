"""
ARGUS — Behavior Agent
Models crowd psychology: chase, panic, exhaustion, euphoria, apathy.
"""
from core.perception import MarketFeatures
from schemas.state import AgentResult


def run(features: MarketFeatures) -> AgentResult:
    """
    Behavior Agent: reads mass psychology and crowd-level market behavior.
    High scores indicate squeeze-prone or chase conditions.
    Low scores indicate panic exhaustion or apathy.
    """
    score = 50.0
    thesis_parts = []
    contradictions = []
    triggers = []
    invalidation = []

    # Volume + velocity combo defines crowd energy
    vol = features.volume_surge
    vel = features.price_velocity

    if vol > 2.5 and vel > 1.5:
        score += 18.0
        thesis_parts.append("High volume + positive velocity: crowd is in chase mode.")
        contradictions.append("Chase behavior is euphoric — late entries create reversal risk.")
        triggers.append("Continuation requires fresh volume; stalling = exhaustion signal.")
    elif vol > 2.5 and vel < -1.5:
        score -= 15.0
        thesis_parts.append("High volume + negative velocity: crowd panic or capitulation underway.")
        triggers.append("Panic selling climax may create a bottom — watch for volume tail-off.")
    elif vol < 0.7 and abs(vel) < 0.5:
        score -= 10.0
        thesis_parts.append("Low volume and flat velocity: crowd is apathetic.")
        contradictions.append("Apathy reduces breakout reliability significantly.")

    # RSI as crowd sentiment proxy
    rsi = features.rsi
    if rsi > 78:
        score += 8.0
        thesis_parts.append(f"RSI at {rsi:.1f} — crowd sentiment is in euphoric territory.")
        contradictions.append("Euphoric RSI historically precedes mean reversion or exhaustion events.")
    elif rsi > 65:
        score += 5.0
        thesis_parts.append(f"RSI at {rsi:.1f} — crowd is broadly optimistic, not yet euphoric.")
    elif rsi < 25:
        score -= 8.0
        thesis_parts.append(f"RSI at {rsi:.1f} — crowd is in fear or capitulation.")
        triggers.append("RSI divergence from further lows = potential behavioral reversal.")
    elif rsi < 40:
        score -= 4.0
        thesis_parts.append(f"RSI at {rsi:.1f} — mild pessimism in crowd behavior.")

    # Gap events signal crowd surprise reactions
    if features.gap_up:
        score += 7.0
        thesis_parts.append("Gap-up: crowd reacting to catalyst — FOMO buying likely.")
        contradictions.append("Gaps filled intraday reveal weak behavioral conviction.")
    if features.gap_down:
        score -= 7.0
        thesis_parts.append("Gap-down: crowd reacting with fear — panic selling risk elevated.")

    # Squeeze detection from compression + volume buildup
    if features.compression_detected and vol > 1.3:
        score += 10.0
        thesis_parts.append("Compression with elevated volume: squeeze behavior building.")
        triggers.append("Squeeze release typically produces the most violent behavioral reactions.")

    # RSI divergence: crowd isn't aligned with price movement
    if abs(features.rsi_divergence) > 8:
        score -= 6.0
        contradictions.append(
            f"RSI divergence detected ({features.rsi_divergence:+.1f}) — crowd conviction does not match price."
        )

    score = max(0.0, min(100.0, score))
    confidence = min(1.0, 0.45 + (abs(score - 50) / 90))

    thesis = " ".join(thesis_parts) if thesis_parts else "Crowd behavior is neutral and uncommitted."

    return AgentResult(
        name="behavior",
        score=round(score, 2),
        confidence=round(confidence, 3),
        thesis=thesis,
        contradictions=contradictions,
        trigger_conditions=triggers,
        invalidation=invalidation,
    )
