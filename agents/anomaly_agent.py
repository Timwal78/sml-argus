"""
ARGUS — Anomaly Agent
Flags behaviors that should not exist relative to the asset's historical profile.
"Something is wrong here."
"""
from core.perception import MarketFeatures
from schemas.state import AgentResult


def run(features: MarketFeatures) -> AgentResult:
    """
    Anomaly Agent: detects statistical and behavioral outliers.
    High score = many anomalies are present = elevated event risk.
    """
    score = 30.0  # starts LOW — anomalies must be earned
    thesis_parts = []
    contradictions = []
    triggers = []
    invalidation = []

    anomaly_count = 0

    # Extreme volume with no visible price follow-through
    if features.volume_surge > 2.5 and features.range_pct < 1.0:
        score += 20.0
        anomaly_count += 1
        thesis_parts.append(
            "High volume with minimal price movement — hidden absorption or suppression detected."
        )
        triggers.append("If suppression breaks, move can be violent.")

    # Compression persists despite elevated volume (institutional coil)
    if features.compression_detected and features.volume_surge > 1.5:
        score += 15.0
        anomaly_count += 1
        thesis_parts.append(
            "Compression persisting under elevated volume — atypical coil signature."
        )

    # RSI divergence: price moved but crowd didn't agree
    if features.rsi_divergence < -10:
        score += 12.0
        anomaly_count += 1
        thesis_parts.append(
            f"Bearish RSI divergence ({features.rsi_divergence:.1f}) — price rising but momentum fading. Hidden weakness."
        )
        contradictions.append("Surface strength may be deceptive.")
    elif features.rsi_divergence > 10:
        score += 12.0
        anomaly_count += 1
        thesis_parts.append(
            f"Bullish RSI divergence (+{features.rsi_divergence:.1f}) — price falling but momentum strengthening. Hidden strength."
        )

    # Gap with no volume: suspicious
    if (features.gap_up or features.gap_down) and features.volume_surge < 0.9:
        score += 10.0
        anomaly_count += 1
        thesis_parts.append(
            "Gap event occurred with below-average volume — low conviction move, trap risk elevated."
        )
        contradictions.append("Gaps on thin volume are frequently filled quickly.")

    # Expansion detected but trend is broken (structural contradiction)
    if features.expansion_detected and not features.trend_intact:
        score += 15.0
        anomaly_count += 1
        thesis_parts.append(
            "Expansion occurring within broken structure — this is anomalous behavior with high reversal probability."
        )
        contradictions.append("A broken-structure expansion is one of the highest-risk anomaly patterns.")

    # Extreme velocity with low volume (thin air move)
    if abs(features.price_velocity) > 2.5 and features.volume_surge < 0.8:
        score += 12.0
        anomaly_count += 1
        thesis_parts.append(
            f"Extreme velocity ({features.price_velocity:+.1f}) on thin volume — this move lacks institutional backing."
        )
        triggers.append("Without volume confirmation, high-velocity moves are anomalous and fragile.")

    # Memory analogy: prior state informed this anomaly
    if features.prior_outcome in ("trap", "failure"):
        score += 8.0
        anomaly_count += 1
        thesis_parts.append(
            f"Memory match flagged: prior similar state led to '{features.prior_outcome}'. Elevated caution."
        )

    # Pine signal override: external anomaly flag
    if features.pine_signal == "anomaly":
        score += 10.0
        anomaly_count += 1
        thesis_parts.append("Pine script flagged an anomaly event on this timeframe.")

    score = max(0.0, min(100.0, score))
    confidence = min(1.0, 0.3 + (anomaly_count * 0.12))

    if anomaly_count == 0:
        thesis = "No anomalies detected. Behavior is consistent with historical norms for this asset."
        invalidation = ["Anomaly absence does not mean low risk — it means the risk is orthodox."]
    else:
        thesis = f"{anomaly_count} anomal{'y' if anomaly_count == 1 else 'ies'} detected. " + " ".join(thesis_parts)

    return AgentResult(
        name="anomaly",
        score=round(score, 2),
        confidence=round(confidence, 3),
        thesis=thesis,
        contradictions=contradictions,
        trigger_conditions=triggers,
        invalidation=invalidation,
    )
