"""
ARGUS — Perception Layer
Normalizes raw market data into a feature packet for the agent layer.
"""
from __future__ import annotations
import math
from typing import Optional, Dict, Any
from pydantic import BaseModel


class MarketFeatures(BaseModel):
    """Normalized feature packet produced by the perception layer."""
    ticker: str
    timeframe: str

    # Price structure
    close: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    volume: float = 0.0

    # Derived volatility
    atr: float = 0.0
    atr_pct: float = 0.0           # ATR as % of price
    bb_width: float = 0.0          # Bollinger Band width (compression proxy)
    range_pct: float = 0.0         # bar range as % of price

    # Momentum
    rsi: float = 50.0
    rsi_divergence: float = 0.0    # positive = bullish div, negative = bearish
    macd_hist: float = 0.0

    # Structure
    above_vwap: bool = True
    trend_intact: bool = True       # higher highs / higher lows present
    recent_pivot_break: bool = False
    compression_detected: bool = False
    expansion_detected: bool = False

    # Crowd / behavior
    volume_surge: float = 1.0       # volume vs. average (1.0 = normal)
    price_velocity: float = 0.0     # rate of change
    gap_up: bool = False
    gap_down: bool = False

    # Historical memory context (injected by memory engine)
    memory_score: float = 0.0       # similarity to prior patterns
    prior_outcome: Optional[str] = None  # "expansion", "trap", "reversal", etc.

    # Pine webhook overlays (optional, injected if available)
    pine_signal: Optional[str] = None
    pine_value: Optional[float] = None


def build_features_from_pine(
    ticker: str,
    timeframe: str,
    raw: Dict[str, Any],
) -> MarketFeatures:
    """
    Build a MarketFeatures packet from a Pine webhook payload dict.
    This is the bridge between TradingView inputs and the agent layer.
    """
    close = raw.get("close", 0.0) or 0.0
    high = raw.get("high", close)
    low = raw.get("low", close)
    atr = raw.get("atr", 0.0) or 0.0
    bb_width = raw.get("bb_width", 0.0) or 0.0

    range_pct = ((high - low) / close * 100) if close > 0 else 0.0
    atr_pct = (atr / close * 100) if close > 0 else 0.0

    rsi = raw.get("rsi", 50.0) or 50.0
    compression_detected = bb_width < 0.03 and atr_pct < 1.0  # heuristic

    return MarketFeatures(
        ticker=ticker,
        timeframe=timeframe,
        close=close,
        open=raw.get("open", close),
        high=high,
        low=low,
        volume=raw.get("volume", 0.0),
        atr=atr,
        atr_pct=atr_pct,
        bb_width=bb_width,
        range_pct=range_pct,
        rsi=rsi,
        above_vwap=close >= (raw.get("vwap", close) or close),
        compression_detected=compression_detected,
        pine_signal=raw.get("custom_signal"),
        pine_value=raw.get("custom_value"),
    )


