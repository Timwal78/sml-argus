"""
ARGUS — Pine Webhook Schema
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class PineWebhookPayload(BaseModel):
    """Accepts TradingView-style Pine alert payloads"""
    ticker: str = Field(..., min_length=1, max_length=10)
    timeframe: str = Field(..., description="e.g. 15m, 1h, 1d")
    event_type: str = Field(..., description="e.g. compression, breakout, anomaly, trigger")
    close: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[float] = None
    rsi: Optional[float] = None
    atr: Optional[float] = None
    vwap: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_width: Optional[float] = None
    custom_signal: Optional[str] = None
    custom_value: Optional[float] = None
    fired_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        extra = "allow"  # accept additional Pine fields


VALID_EVENT_TYPES = {
    "compression",
    "breakout",
    "breakdown",
    "anomaly",
    "trigger",
    "squeeze",
    "expansion",
    "reversal",
    "trap",
    "regime_break",
    "custom",
}
