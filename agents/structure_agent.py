"""
ARGUS — Structure Agent
Reads trend integrity, pivots, compression, expansion, and failed breaks.
"""
from core.perception import MarketFeatures
from schemas.state import AgentResult


def run(features: MarketFeatures) -> AgentResult:
    """
    Structure Agent: evaluates the quality and integrity of price structure.
    A weak structure score flags that trends may be false, traps may form.
    """
    score = 50.0
    thesis_parts = []
    contradictions = []
    triggers = []
    invalidation = []

    # Trend integrity: the backbone of clean structure
    if features.trend_intact:
        score += 15.0
        thesis_parts.append("Trend structure is intact — price is respecting higher-timeframe bias.")
        invalidation.append("A pivot failure beneath recent swing low invalidates the structure.")
    else:
        score -= 15.0
        thesis_parts.append("Trend structure is broken — higher-timeframe bias is compromised.")
        contradictions.append("Broken structure raises trap and reversal probability significantly.")

    # Pivot break: momentum confirmation or false break
    if features.recent_pivot_break:
        if features.trend_intact:
            score += 10.0
            thesis_parts.append("Pivot break occurred within intact trend — potential momentum continuation.")
            triggers.append("Close above broken pivot level with volume confirms continuation.")
        else:
            score -= 10.0
            thesis_parts.append("Pivot break against broken trend — elevated trap probability.")
            contradictions.append("Pivot break in a broken structure often marks a bear trap or bull trap.")

    # ATR range quality: narrow range = structural uncertainty
    if features.atr_pct < 0.8:
        score -= 8.0
        thesis_parts.append(f"ATR very low at {features.atr_pct:.2f}% — market lacks structural energy.")
        contradictions.append("Low ATR means structure is ambiguous and compressed.")
    elif features.atr_pct > 3.0:
        score += 5.0
        thesis_parts.append(f"ATR elevated at {features.atr_pct:.2f}% — structure is active.")

    # MACD histogram as structural momentum filter
    if features.macd_hist > 0.5:
        score += 7.0
        thesis_parts.append("MACD histogram positive and rising — structural bullish momentum confirmed.")
    elif features.macd_hist < -0.5:
        score -= 7.0
        thesis_parts.append("MACD histogram negative — structural bearish pressure present.")

    # Compression = structure coiling before release
    if features.compression_detected:
        score -= 5.0  # structure is unclear until release
        thesis_parts.append("Compression detected — structure is coiling, direction undetermined.")
        triggers.append("Breakout from compression with volume determines structural direction.")
        contradictions.append("Compression creates ambiguity — false breakout risk is elevated.")

    # Expansion = structure is releasing
    if features.expansion_detected:
        score += 8.0
        thesis_parts.append("Expansion underway — structure is releasing energy.")

    # BB width gives a sense of structure breadth
    if features.bb_width > 0.06:
        score += 4.0
        thesis_parts.append("Wide Bollinger Bands confirm active range — structure is expressive.")

    score = max(0.0, min(100.0, score))
    confidence = min(1.0, 0.45 + (abs(score - 50) / 100))

    thesis = " ".join(thesis_parts) if thesis_parts else "Structure is unclear — no dominant bias detected."

    return AgentResult(
        name="structure",
        score=round(score, 2),
        confidence=round(confidence, 3),
        thesis=thesis,
        contradictions=contradictions,
        trigger_conditions=triggers,
        invalidation=invalidation,
    )
