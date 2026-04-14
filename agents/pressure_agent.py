"""
ARGUS — Pressure Agent
Measures directional force, compression, expansion, and hidden imbalance.
"""
from core.perception import MarketFeatures
from schemas.state import AgentResult


def run(features: MarketFeatures) -> AgentResult:
    """
    Pressure Agent: evaluates whether buying or selling pressure is dominant
    and how strongly it's building or fading.
    """
    score = 50.0
    thesis_parts = []
    contradictions = []
    triggers = []
    invalidation = []

    # Volume surge amplifies pressure in the dominant direction
    vol = features.volume_surge
    if vol > 2.0:
        score += 12.0
        thesis_parts.append(f"Volume surge at {vol:.1f}x average — pressure is amplified.")
    elif vol > 1.5:
        score += 7.0
        thesis_parts.append(f"Elevated volume at {vol:.1f}x — moderate pressure present.")
    elif vol < 0.7:
        score -= 8.0
        thesis_parts.append("Volume below average — pressure is thin.")
        contradictions.append("Weak volume limits conviction.")

    # VWAP position is a structural pressure anchor
    if features.above_vwap:
        score += 8.0
        thesis_parts.append("Price is above VWAP — bullish structural pressure.")
        triggers.append("Sustained VWAP holding confirms pressure.")
        invalidation.append("VWAP loss invalidates bullish pressure read.")
    else:
        score -= 8.0
        thesis_parts.append("Price is below VWAP — bearish pressure dominates.")
        triggers.append("VWAP reclaim needed to shift pressure.")

    # Compression means pressure is coiling
    if features.compression_detected:
        score += 10.0
        thesis_parts.append("Compression active — pressure is coiling beneath the surface.")
        triggers.append("Expansion out of compression = high-probability pressure release.")

    # Expansion already underway
    if features.expansion_detected:
        if features.above_vwap:
            score += 8.0
            thesis_parts.append("Expansion detected above VWAP — bullish pressure releasing.")
        else:
            score -= 5.0
            thesis_parts.append("Expansion while below VWAP — bearish pressure releasing.")

    # RSI extremes signal imbalanced pressure
    if features.rsi > 72:
        score += 5.0
        thesis_parts.append(f"RSI at {features.rsi:.1f} — overbought pressure territory.")
        contradictions.append("Extreme RSI may signal exhaustion, not continuation.")
    elif features.rsi < 30:
        score -= 5.0
        thesis_parts.append(f"RSI at {features.rsi:.1f} — oversold territory.")
        contradictions.append("Extreme RSI may signal panic exhaustion.")

    # Velocity as a momentum pressure proxy
    if features.price_velocity > 2.0:
        score += 6.0
        thesis_parts.append("High positive velocity — buying pressure accelerating.")
    elif features.price_velocity < -2.0:
        score -= 6.0
        thesis_parts.append("High negative velocity — selling pressure accelerating.")

    # Gap events
    if features.gap_up:
        score += 5.0
        thesis_parts.append("Gap-up detected — institutional pressure or catalyst present.")
    if features.gap_down:
        score -= 5.0
        thesis_parts.append("Gap-down detected — bearish institutional pressure or capitulation.")

    score = max(0.0, min(100.0, score))
    confidence = min(1.0, 0.5 + (abs(score - 50) / 100))

    thesis = " ".join(thesis_parts) if thesis_parts else "Pressure is neutral and undecided."

    return AgentResult(
        name="pressure",
        score=round(score, 2),
        confidence=round(confidence, 3),
        thesis=thesis,
        contradictions=contradictions,
        trigger_conditions=triggers,
        invalidation=invalidation,
    )
