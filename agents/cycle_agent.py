"""
ARGUS — Cycle Agent
Looks for timing symmetry, fractal repetition, rhythm shifts, and lagged echoes.
"""
from core.perception import MarketFeatures
from schemas.state import AgentResult


def run(features: MarketFeatures) -> AgentResult:
    """
    Cycle Agent: evaluates whether market timing aligns with repeating cycles.
    Incorporates 3-6-9 rhythm principles and multi-timeframe resonance.
    """
    score = 50.0
    thesis_parts = []
    contradictions = []
    triggers = []
    invalidation = []

    # Compression as a timing signal: cycles typically compress before releasing
    if features.compression_detected:
        score += 12.0
        thesis_parts.append(
            "Compression present — this often marks the coiling phase before a cycle expansion."
        )
        triggers.append("Cycle timing suggests the next 1–3 bars are critical for direction confirmation.")

    # Expansion: we may be mid-cycle or near exhaustion of the current wave
    if features.expansion_detected:
        score += 8.0
        thesis_parts.append(
            "Expansion underway — this is mid-cycle or the terminal phase of the current wave."
        )
        contradictions.append("If expansion is mature, the next phase may be correction or reset.")

    # RSI near cycle extremes are timing signals
    rsi = features.rsi
    if 48 <= rsi <= 54:
        score += 6.0
        thesis_parts.append(
            "RSI is near midpoint balance — cycle may be at a critical inflection zone."
        )
    elif rsi > 75 or rsi < 27:
        score -= 6.0
        thesis_parts.append(
            f"RSI at extreme ({rsi:.1f}) — late in a cycle wave, correction risk rises."
        )

    # Volume rhythm: declining volume often marks late-cycle
    if features.volume_surge < 0.7:
        score -= 7.0
        thesis_parts.append(
            "Volume rhythm declining — may indicate end-of-cycle exhaustion."
        )
        contradictions.append("Declining volume into a high creates divergence — classic late-cycle warning.")
    elif features.volume_surge > 2.0:
        score += 7.0
        thesis_parts.append("Volume spike marks a potential cycle transition point.")

    # ATR rhythm: volatility cycles typically expand → contract → expand
    if features.atr_pct > 3.5:
        score += 5.0
        thesis_parts.append(
            f"ATR at {features.atr_pct:.2f}% — volatility cycle is in an expansion phase."
        )
    elif features.atr_pct < 0.8:
        score += 3.0
        thesis_parts.append(
            f"ATR compressed at {features.atr_pct:.2f}% — volatility cycle is contracting before next expansion."
        )

    # Memory-based cycle match (if prior pattern was identified)
    if features.memory_score > 0.7:
        score += 15.0
        thesis_parts.append(
            f"Memory similarity at {features.memory_score:.0%} — current setup resembles a prior high-confidence cycle entry."
        )
        triggers.append(
            "If prior cycle analogy holds, pay attention to the timing of the next pivot."
        )
    elif features.memory_score > 0.4:
        score += 7.0
        thesis_parts.append(
            f"Partial memory match ({features.memory_score:.0%}) — possible cycle echo, watch for confirmation."
        )

    # Pine signal hints at cycle timing
    if features.pine_signal in ("compression", "trigger"):
        score += 8.0
        thesis_parts.append("Pine cycle signal armed — external timing confirmation.")

    score = max(0.0, min(100.0, score))
    confidence = min(1.0, 0.4 + (abs(score - 50) / 100))

    thesis = " ".join(thesis_parts) if thesis_parts else "No dominant cycle pattern detected at this time."

    return AgentResult(
        name="cycle",
        score=round(score, 2),
        confidence=round(confidence, 3),
        thesis=thesis,
        contradictions=contradictions,
        trigger_conditions=triggers,
        invalidation=invalidation,
    )
