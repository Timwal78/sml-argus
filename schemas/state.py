"""
ARGUS — State Schemas
"""
from __future__ import annotations
from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime
from schemas.echo_context import EchoContext


# ─── Enumerations ─────────────────────────────────────────────────────────────

class PressureBias(str, Enum):
    BULLISH = "bullish"
    UNSTABLE_BULLISH = "unstable_bullish"
    BEARISH = "bearish"
    UNSTABLE_BEARISH = "unstable_bearish"
    NEUTRAL = "neutral"
    FRACTURED = "fractured"


class StabilityGrade(str, Enum):
    STABLE = "stable"
    FRAGILE = "fragile"
    DISTORTED = "distorted"
    BREAKING = "breaking"


class VeilState(str, Enum):
    DORMANT = "dormant"
    WATCHING = "watching"
    BUILDING = "building"
    TENSION = "tension"
    ESCALATION = "escalation"
    ARMED = "armed"
    TRIGGERED = "triggered"
    DISTORTED = "distorted"
    FAILURE = "failure"
    TRAP = "trap"
    COOLDOWN = "cooldown"


class AlertMode(str, Enum):
    OBSERVATION = "observation"
    ESCALATION = "escalation"
    COMPRESSION_WARNING = "compression_warning"
    DISTORTION_ALERT = "distortion_alert"
    TRIGGER_ARMED = "trigger_armed"
    TRAP_RISK = "trap_risk"
    REGIME_BREAK = "regime_break"


# ─── Agent Result ──────────────────────────────────────────────────────────────

class AgentResult(BaseModel):
    name: str
    score: float = Field(..., ge=0, le=100)
    confidence: float = Field(..., ge=0, le=1)
    thesis: str
    contradictions: List[str] = []
    trigger_conditions: List[str] = []
    invalidation: List[str] = []


# ─── Event Risk ───────────────────────────────────────────────────────────────

class EventRisk(BaseModel):
    expansion: float = Field(..., ge=0, le=1)
    reversal: float = Field(..., ge=0, le=1)
    squeeze: float = Field(..., ge=0, le=1)
    trap: float = Field(..., ge=0, le=1)
    regime_break: float = Field(0.0, ge=0, le=1)

    @property
    def dominant(self) -> str:
        risks = {
            "expansion": self.expansion,
            "reversal": self.reversal,
            "squeeze": self.squeeze,
            "trap": self.trap,
            "regime_break": self.regime_break,
        }
        return max(risks, key=risks.get)


# ─── Trigger Map ──────────────────────────────────────────────────────────────

class TriggerMap(BaseModel):
    confirm_above: Optional[float] = None
    invalidate_below: Optional[float] = None
    time_limit_bars: Optional[int] = None
    conditions: List[str] = []


# ─── Data Source ──────────────────────────────────────────────────────────────

class DataSource(str, Enum):
    YFINANCE = "yfinance"        # free, default
    POLYGON = "polygon"          # BYOK
    ALPHAVANTAGE = "alphavantage"  # BYOK


# ─── Scan Request ─────────────────────────────────────────────────────────────

class ScanRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)
    timeframes: List[str] = Field(default=["15m", "1h", "1d"])
    force_refresh: bool = False

    # BYOK — Bring Your Own Key
    # Users on paid tiers can supply their own API keys for premium data sources
    data_source: DataSource = DataSource.YFINANCE
    polygon_key: Optional[str] = Field(None, description="BYOK: Your Polygon.io API key")
    alpha_vantage_key: Optional[str] = Field(None, description="BYOK: Your Alpha Vantage API key")


# ─── Scan Response ────────────────────────────────────────────────────────────

class ScanResponse(BaseModel):
    ticker: str
    veil_score: float = Field(..., ge=0, le=100)
    state: VeilState
    bias: PressureBias
    stability: StabilityGrade
    event_risk: EventRisk
    agents: List[AgentResult]
    briefing: str
    trigger_map: TriggerMap
    alert_mode: AlertMode
    memory_matched: bool = False
    memory_note: Optional[str] = None
    data_source: str = "yfinance"
    scanned_at: datetime = Field(default_factory=datetime.utcnow)
    # ── ECHO FORGE context ───────────────────────────────────────────────────
    # Present when ECHO_FORGE_URL is configured and the service is reachable.
    # None when ECHO FORGE is disabled, unreachable, or returns low confidence.
    echo_context: Optional[EchoContext] = None


# ─── State History ────────────────────────────────────────────────────────────

class StateSnapshot(BaseModel):
    id: Optional[int] = None
    ticker: str
    veil_score: float
    state: VeilState
    bias: PressureBias
    stability: StabilityGrade
    briefing: str
    agent_scores: Dict[str, float]
    scanned_at: datetime


# ─── Ticker Personality ───────────────────────────────────────────────────────

class TickerPersonality(BaseModel):
    ticker: str
    squeeze_prone: bool = False
    narrative_sensitive: bool = False
    anomaly_rich: bool = False
    failure_prone: bool = False
    macro_responsive: bool = False
    typical_veil_range: tuple = (20, 70)
    notes: str = ""
    last_updated: Optional[datetime] = None
