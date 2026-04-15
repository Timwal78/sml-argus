"""
ARGUS — Trade Directive Engine
Translates raw organism intelligence into plain-English trade directives.

THIS is what you read. The scores are background. The directive is the action.
ARGUS is the brain. You are the hands. It tells you what to do — you decide IF.
"""
from __future__ import annotations
from schemas.state import ScanResponse, PressureBias, StabilityGrade, VeilState
from schemas.trade_intent import TradeIntent, ActionClass
from integrations.schwab_bridge import generate_trade_intent
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class TradeDirective(BaseModel):
    """The human-readable trade directive. This is the headline."""
    ticker: str

    # ── THE CALL ──────────────────────────────────────────────────────────────
    action: str                     # "BUY", "SELL SHORT", "HOLD", "WAIT", "STAY OUT", "EXIT", "REDUCE"
    action_color: str               # hex color for the action badge
    conviction: str                 # "HIGH CONVICTION", "MODERATE", "LOW", "SPECULATIVE", "NO TRADE"
    conviction_pct: int             # 0-100 confidence percentage

    # ── THE WHY ───────────────────────────────────────────────────────────────
    headline: str                   # One-sentence summary: "AMC is building pressure for a breakout..."
    reasoning: str                  # Plain-English 2-3 sentences explaining the thesis

    # ── THE LEVELS ────────────────────────────────────────────────────────────
    current_price: Optional[float] = None
    entry_above: Optional[float] = None        # "Buy above this price"
    stop_loss: Optional[float] = None          # "Get out if it drops to here"
    target_1: Optional[float] = None           # "First profit target"
    target_2: Optional[float] = None           # "Stretch target"
    invalidation: Optional[float] = None       # "The thesis is dead below this"

    # ── THE RISK ──────────────────────────────────────────────────────────────
    risk_grade: str                 # "LOW", "MODERATE", "HIGH", "EXTREME"
    risk_emoji: str                 # 🟢 🟡 🟠 🔴
    risk_note: str                  # "Trap probability is elevated..."
    position_size: str              # "FULL", "HALF", "QUARTER", "SKIP"

    # ── WHAT TO WATCH ─────────────────────────────────────────────────────────
    watch_for: List[str] = []       # Things that would change the call
    kill_conditions: List[str] = [] # If any of these happen, the trade is dead

    # ── UNDERLYING DATA ───────────────────────────────────────────────────────
    veil_score: float
    state: str
    bias: str
    stability: str
    dominant_risk: str
    data_source: str = "yfinance"
    scanned_at: datetime = Field(default_factory=datetime.utcnow)


def generate_directive(scan: ScanResponse) -> TradeDirective:
    """
    Convert a scan result into a plain-English trade directive.
    This is the layer between the organism and the human.
    """
    intent = generate_trade_intent(scan)
    close = _get_close_price(scan)

    action, action_color = _translate_action(intent, scan)
    conviction, conviction_pct = _translate_conviction(intent, scan)
    headline = _write_headline(scan, intent)
    reasoning = _write_reasoning(scan, intent)
    risk_grade, risk_emoji = _assess_risk(scan)
    position_size = _recommend_size(intent, risk_grade)

    # Price levels
    entry_above = intent.confirm_above
    stop_loss = intent.invalidate_below
    target_1, target_2 = _estimate_targets(scan, close, intent)

    # Watch conditions
    watch_for = _build_watch_list(scan)
    kill_conditions = _build_kill_list(scan, intent)

    return TradeDirective(
        ticker=scan.ticker,
        action=action,
        action_color=action_color,
        conviction=conviction,
        conviction_pct=conviction_pct,
        headline=headline,
        reasoning=reasoning,
        current_price=close,
        entry_above=entry_above,
        stop_loss=stop_loss,
        target_1=target_1,
        target_2=target_2,
        invalidation=intent.invalidate_below,
        risk_grade=risk_grade,
        risk_emoji=risk_emoji,
        risk_note=intent.risk_note or "Standard risk.",
        position_size=position_size,
        watch_for=watch_for,
        kill_conditions=kill_conditions,
        veil_score=scan.veil_score,
        state=scan.state.value if hasattr(scan.state, 'value') else str(scan.state),
        bias=scan.bias.value if hasattr(scan.bias, 'value') else str(scan.bias),
        stability=scan.stability.value if hasattr(scan.stability, 'value') else str(scan.stability),
        dominant_risk=scan.event_risk.dominant if scan.event_risk else "unknown",
        data_source=scan.data_source,
        scanned_at=scan.scanned_at,
    )


def _get_close_price(scan: ScanResponse) -> Optional[float]:
    """Extract current price from the scan trigger map or agents."""
    if scan.trigger_map and scan.trigger_map.confirm_above:
        # Estimate current price as slightly below confirm level
        return None
    return None  # Will be populated from the data adapter in future


def _translate_action(intent: TradeIntent, scan: ScanResponse) -> tuple[str, str]:
    """Translate ActionClass + direction into a human action word."""
    ac = intent.action_class
    direction = intent.direction

    if ac == ActionClass.LIVE_HIGH_CONVICTION:
        if direction == "long":
            return "BUY", "#00FF88"
        elif direction == "short":
            return "SELL SHORT", "#FF3030"
        return "BUY", "#00FF88"

    if ac == ActionClass.LIVE_LOW_SIZE:
        if direction == "long":
            return "BUY (small size)", "#00CC66"
        elif direction == "short":
            return "SELL SHORT (small)", "#FF6644"
        return "BUY (small size)", "#00CC66"

    if ac == ActionClass.PAPER_CANDIDATE:
        if direction == "long":
            return "BUY (paper first)", "#5B8CFF"
        elif direction == "short":
            return "SELL SHORT (paper)", "#FF8844"
        return "WATCH TO BUY", "#5B8CFF"

    if ac == ActionClass.WATCH_FOR_TRIGGER:
        if direction == "long":
            return "WAIT — setting up long", "#FFD700"
        elif direction == "short":
            return "WAIT — setting up short", "#FF8800"
        return "WAIT — no clear setup", "#FFD700"

    if ac == ActionClass.REDUCE_RISK:
        return "REDUCE / TRIM", "#FF6600"

    if ac == ActionClass.EXIT_POSITION:
        return "EXIT NOW", "#FF0044"

    # OBSERVE_ONLY
    if scan.state in (VeilState.TRAP, VeilState.FAILURE):
        return "STAY OUT — trap risk", "#FF4444"
    if scan.state == VeilState.COOLDOWN:
        return "STAY OUT — cooling off", "#888888"

    return "NO TRADE — nothing here yet", "#555577"


def _translate_conviction(intent: TradeIntent, scan: ScanResponse) -> tuple[str, int]:
    """Map confidence to plain-English conviction level."""
    conf = intent.confidence
    ac = intent.action_class

    if ac in (ActionClass.OBSERVE_ONLY,):
        return "NO TRADE", 0

    if conf >= 0.80 and ac == ActionClass.LIVE_HIGH_CONVICTION:
        return "HIGH CONVICTION", int(conf * 100)
    if conf >= 0.65:
        return "MODERATE", int(conf * 100)
    if conf >= 0.50:
        return "LOW", int(conf * 100)
    if conf >= 0.35:
        return "SPECULATIVE", int(conf * 100)

    return "NO TRADE", int(conf * 100)


def _write_headline(scan: ScanResponse, intent: TradeIntent) -> str:
    """One sentence a trader can read in 2 seconds."""
    ticker = scan.ticker
    state = scan.state
    bias = scan.bias
    direction = intent.direction

    if intent.action_class == ActionClass.LIVE_HIGH_CONVICTION:
        dir_word = "long" if direction == "long" else "short"
        return f"{ticker} is showing high-conviction {dir_word} setup. The organism sees strong alignment across all agents."

    if intent.action_class == ActionClass.LIVE_LOW_SIZE:
        dir_word = "upside" if direction == "long" else "downside"
        return f"{ticker} has a playable {dir_word} setup, but stability is not perfect. Small size recommended."

    if intent.action_class == ActionClass.PAPER_CANDIDATE:
        return f"{ticker} is building toward a setup. Worth tracking on paper — not ready for live risk yet."

    if intent.action_class == ActionClass.WATCH_FOR_TRIGGER:
        if state == VeilState.TENSION:
            return f"{ticker} is in tension. Pressure is building but hasn't broken through yet. Watch for trigger."
        if state == VeilState.BUILDING:
            return f"{ticker} conditions are forming. Still early — wait for structure to confirm."
        if state == VeilState.ESCALATION:
            return f"{ticker} is escalating. Getting close to an actionable setup. Stay alert."
        return f"{ticker} is on the radar but not ready yet. Wait for a clear signal."

    if intent.action_class == ActionClass.REDUCE_RISK:
        return f"{ticker} structure is breaking down. If you're in, consider trimming or tightening stops."

    if state == VeilState.TRAP:
        return f"{ticker} looks like a trap. The setup is deceptive — stay out until it resolves."

    if state == VeilState.DORMANT:
        return f"{ticker} is quiet. No meaningful pressure or setup forming. Nothing to do here right now."

    if state == VeilState.WATCHING:
        return f"{ticker} has some early movement but nothing actionable yet. The organism is watching."

    return f"{ticker} scan complete. No strong setup detected at this time."


def _write_reasoning(scan: ScanResponse, intent: TradeIntent) -> str:
    """2-3 sentences explaining why, in trader language."""
    agents = {a.name: a for a in scan.agents}
    parts = []

    p = agents.get("pressure")
    s = agents.get("structure")
    b = agents.get("behavior")
    a = agents.get("anomaly")

    if p and p.score > 65:
        parts.append(f"Pressure is strong at {p.score:.0f}/100 — volume and directional force are present.")
    elif p and p.score < 40:
        parts.append(f"Pressure is weak at {p.score:.0f}/100 — no real buying/selling conviction.")
    else:
        parts.append(f"Pressure is moderate at {p.score:.0f}/100." if p else "")

    if s and s.score > 60:
        parts.append(f"Structure supports the move — trend is intact with MACD confirmation.")
    elif s and s.score < 40:
        parts.append(f"Structure is weak — trend is breaking down or non-existent.")

    if a and a.score > 60:
        parts.append(f"⚠️ Anomaly agent fired at {a.score:.0f} — something unusual is happening. Could be opportunity or deception.")

    if b and b.score > 65:
        parts.append(f"Crowd behavior is heated — watch for exhaustion or chase dynamics.")

    if scan.event_risk:
        dominant = scan.event_risk.dominant
        if dominant == "trap":
            parts.append("Dominant risk is a TRAP — the setup could be deceptive.")
        elif dominant == "expansion":
            parts.append("Dominant outcome is expansion — breakout is the most likely scenario.")
        elif dominant == "reversal":
            parts.append("Reversal risk is elevated — the move may be overextended.")
        elif dominant == "squeeze":
            parts.append("Squeeze conditions detected — a sharp move in either direction is possible.")

    return " ".join(parts) if parts else "Standard market conditions. No exceptional signals."


def _assess_risk(scan: ScanResponse) -> tuple[str, str]:
    """Grade the overall risk of taking this trade."""
    stability = scan.stability
    event_risk = scan.event_risk

    trap_risk = event_risk.trap if event_risk else 0
    regime_risk = event_risk.regime_break if event_risk else 0

    if stability == StabilityGrade.BREAKING or trap_risk > 0.6:
        return "EXTREME", "🔴"
    if stability == StabilityGrade.DISTORTED or trap_risk > 0.45 or regime_risk > 0.5:
        return "HIGH", "🟠"
    if stability == StabilityGrade.FRAGILE or trap_risk > 0.3:
        return "MODERATE", "🟡"
    return "LOW", "🟢"


def _recommend_size(intent: TradeIntent, risk_grade: str) -> str:
    """Recommend position size based on conviction + risk."""
    if intent.action_class in (ActionClass.OBSERVE_ONLY,):
        return "SKIP"
    if intent.action_class == ActionClass.LIVE_HIGH_CONVICTION and risk_grade == "LOW":
        return "FULL"
    if intent.action_class in (ActionClass.LIVE_HIGH_CONVICTION, ActionClass.LIVE_LOW_SIZE):
        return "HALF" if risk_grade in ("LOW", "MODERATE") else "QUARTER"
    if intent.action_class == ActionClass.PAPER_CANDIDATE:
        return "QUARTER"
    return "SKIP"


def _estimate_targets(scan: ScanResponse, close: Optional[float], intent: TradeIntent) -> tuple[Optional[float], Optional[float]]:
    """Estimate price targets based on trigger map and ATR."""
    if not close or not intent.confirm_above:
        return None, None

    entry = intent.confirm_above
    risk = abs(entry - (intent.invalidate_below or entry * 0.97))

    target_1 = round(entry + risk * 1.5, 2)  # 1.5:1 R
    target_2 = round(entry + risk * 3.0, 2)  # 3:1 R
    return target_1, target_2


def _build_watch_list(scan: ScanResponse) -> List[str]:
    """Things that would confirm or improve the setup."""
    items = []
    for agent in scan.agents:
        for tc in agent.trigger_conditions[:1]:
            items.append(tc)
    if scan.trigger_map and scan.trigger_map.conditions:
        items.extend(scan.trigger_map.conditions[:3])
    return items[:6]


def _build_kill_list(scan: ScanResponse, intent: TradeIntent) -> List[str]:
    """Conditions that kill the thesis."""
    items = []
    if intent.invalidate_below:
        items.append(f"Price drops below ${intent.invalidate_below:.2f}")
    for agent in scan.agents:
        for inv in agent.invalidation[:1]:
            items.append(inv)
    return items[:5]
