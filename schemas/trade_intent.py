"""
ARGUS — Trade Intent Schema (Schwab Bridge Contract)
"""
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ActionClass(str, Enum):
    OBSERVE_ONLY = "observe_only"
    WATCH_FOR_TRIGGER = "watch_for_trigger"
    PAPER_CANDIDATE = "paper_candidate"
    LIVE_LOW_SIZE = "live_low_size"
    LIVE_HIGH_CONVICTION = "live_high_conviction"
    REDUCE_RISK = "reduce_risk"
    EXIT_POSITION = "exit_position"


class TradeIntent(BaseModel):
    ticker: str
    action_class: ActionClass
    direction: str  # "long" | "short" | "none"
    veil_score: float
    confidence: float = Field(..., ge=0, le=1)
    bias: str
    stability: str
    invalidation_conditions: List[str] = []
    confirm_above: Optional[float] = None
    invalidate_below: Optional[float] = None
    risk_note: Optional[str] = None
    briefing: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True
