"""
Priority order:
  1. Polygon.io (Primary Institutional Feed)
  2. Alpha Vantage (Secondary)
  3. yfinance (Tertiary/Free)

Usage:
    features = await fetch_features(ticker="AMC", timeframe="1h")
"""

from __future__ import annotations
import logging
from typing import Optional
import asyncio

from core.perception import MarketFeatures
from app.config import get_settings

logger = logging.getLogger("argus.data")
settings = get_settings()

# Timeframe mapping: ARGUS format → yfinance period/interval
_YF_INTERVAL_MAP = {
    "1m":  ("1d",   "1m"),
    "5m":  ("5d",   "5m"),
    "15m": ("5d",   "15m"),
    "30m": ("1mo",  "30m"),
    "1h":  ("1mo",  "1h"),
    "4h":  ("3mo",  "1h"),  # yf doesn't do 4h; use 1h and we aggregate
    "1d":  ("1y",   "1d"),
    "1w":  ("5y",   "1wk"),
}

async def fetch_features(
    ticker: str,
    timeframe: str = "1d",
    polygon_key: Optional[str] = None,
    alpha_vantage_key: Optional[str] = None,
) -> MarketFeatures:
    """
    Main entry point for market data.
    STRICT DATA INTEGRITY: Synthetic fallback removed.
    """
    # Priority 1: Polygon.io
    polygon_key = polygon_key or settings.polygon_key
    if polygon_key:
        try:
            return await _fetch_polygon(ticker, timeframe, polygon_key)
        except Exception as e:
            logger.warning(f"Polygon failed for {ticker}: {e}. Trying fallbacks.")

    # Priority 2: Alpha Vantage
    alpha_vantage_key = alpha_vantage_key or settings.alpha_vantage_key
    if alpha_vantage_key:
        try:
            return await _fetch_alphavantage(ticker, timeframe, alpha_vantage_key)
        except Exception as e:
            logger.warning(f"Alpha Vantage failed for {ticker}: {e}. Trying yfinance.")

    # Priority 3: yfinance (Free)
    try:
        return await _fetch_yfinance(ticker, timeframe)
    except Exception as e:
        logger.error(f"yfinance failed for {ticker}/{timeframe}: {e}.")
        raise ValueError(f"CRITICAL: Failed to fetch institutional-grade data for {ticker}. Check API keys.")


async def _fetch_yfinance(ticker: str, timeframe: str) -> MarketFeatures:
    """Fetch and compute features from Yahoo Finance (free, no key)."""
    import yfinance as yf
    import pandas as pd

    period, interval = _YF_INTERVAL_MAP.get(timeframe, ("1mo", "1d"))

    # yfinance is sync — run in thread to not block async event loop
    loop = asyncio.get_event_loop()
    df = await loop.run_in_executor(
        None,
        lambda: yf.download(ticker, period=period, interval=interval,
                            progress=False, auto_adjust=True)
    )

    if df is None or df.empty:
        logger.error(f"yfinance: Zero data returned for {ticker} ({timeframe}).")
        raise ValueError(f"yfinance returned empty data for {ticker}/{timeframe}")

    if len(df) < 14:
        logger.warning(f"yfinance: Insufficient history for {ticker} ({len(df)} bars).")
        # Try to expand the period if it's too short
        period = "max"
        df = await loop.run_in_executor(
            None,
            lambda: yf.download(ticker, period=period, interval=interval,
                                progress=False, auto_adjust=True)
        )
        if df is None or df.empty or len(df) < 14:
            raise ValueError(f"yfinance: Insufficient history even with max period for {ticker}")

    logger.info(f"yfinance: Successfully fetched {len(df)} bars for {ticker} ({timeframe})")

    return _compute_features_from_ohlcv(ticker, timeframe, df)


async def _fetch_polygon(ticker: str, timeframe: str, api_key: str) -> MarketFeatures:
    """Fetch from Polygon.io using user's BYOK key."""
    import httpx
    import pandas as pd

    # Map timeframe to Polygon multiplier/timespan
    tf_map = {
        "1m": (1, "minute"), "5m": (5, "minute"), "15m": (15, "minute"),
        "30m": (30, "minute"), "1h": (1, "hour"), "4h": (4, "hour"),
        "1d": (1, "day"), "1w": (1, "week"),
    }
    mult, span = tf_map.get(timeframe, (1, "day"))

    from datetime import date, timedelta
    end = date.today().isoformat()
    start = (date.today() - timedelta(days=365)).isoformat()

    url = (
        f"https://api.polygon.io/v2/aggs/ticker/{ticker.upper()}/range/"
        f"{mult}/{span}/{start}/{end}"
        f"?adjusted=true&sort=asc&limit=300&apiKey={api_key}"
    )

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    if not data.get("results"):
        raise ValueError(f"No Polygon data for {ticker}")

    rows = data["results"]
    df = pd.DataFrame(rows)
    df = df.rename(columns={"o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume"})
    df.index = pd.to_datetime(df["t"], unit="ms")
    df = df[["Open", "High", "Low", "Close", "Volume"]].sort_index()

    return _compute_features_from_ohlcv(ticker, timeframe, df)


async def _fetch_alphavantage(ticker: str, timeframe: str, api_key: str) -> MarketFeatures:
    """Fetch from Alpha Vantage using user's BYOK key."""
    import httpx
    import pandas as pd

    func_map = {
        "1m": "TIME_SERIES_INTRADAY", "5m": "TIME_SERIES_INTRADAY",
        "15m": "TIME_SERIES_INTRADAY", "30m": "TIME_SERIES_INTRADAY",
        "1h": "TIME_SERIES_INTRADAY", "1d": "TIME_SERIES_DAILY_ADJUSTED",
        "1w": "TIME_SERIES_WEEKLY_ADJUSTED",
    }
    func = func_map.get(timeframe, "TIME_SERIES_DAILY_ADJUSTED")
    interval_map = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min", "1h": "60min"}

    params = {"function": func, "symbol": ticker, "apikey": api_key, "datatype": "json", "outputsize": "compact"}
    if timeframe in interval_map:
        params["interval"] = interval_map[timeframe]

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get("https://www.alphavantage.co/query", params=params)
        resp.raise_for_status()
        data = resp.json()

    # Extract the time series key (varies by function)
    ts_key = next((k for k in data if "Time Series" in k), None)
    if not ts_key:
        raise ValueError(f"No Alpha Vantage data for {ticker}: {list(data.keys())}")

    ts = data[ts_key]
    rows = []
    for dt, vals in ts.items():
        rows.append({
            "Date": pd.Timestamp(dt),
            "Open": float(vals.get("1. open", vals.get("1. Open", 0))),
            "High": float(vals.get("2. high", vals.get("2. High", 0))),
            "Low": float(vals.get("3. low", vals.get("3. Low", 0))),
            "Close": float(vals.get("4. close", vals.get("4. Close",
                            vals.get("5. adjusted close", 0)))),
            "Volume": float(vals.get("5. volume", vals.get("6. volume", 0))),
        })
    df = pd.DataFrame(rows).set_index("Date").sort_index()

    return _compute_features_from_ohlcv(ticker, timeframe, df)


def _compute_features_from_ohlcv(ticker: str, timeframe: str, df) -> MarketFeatures:
    """
    Compute all MarketFeatures from a standard OHLCV DataFrame.
    Handles column flattening for multi-level yfinance output.
    """
    import pandas as pd
    import numpy as np

    # Flatten MultiIndex columns (yfinance returns these)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Ensure we have enough rows
    df = df.dropna(how="all").tail(200)
    if len(df) < 14:
        raise ValueError("Not enough rows to compute indicators")

    close = df["Close"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    volume = df["Volume"].astype(float)

    # ── RSI (14) ──────────────────────────────────────────────────────────────
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=13, adjust=False).mean()
    avg_loss = loss.ewm(com=13, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi_series = 100 - (100 / (1 + rs))
    rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0

    # RSI divergence: slope of price vs slope of RSI over last 5 bars
    if len(rsi_series) >= 6:
        price_slope = float(close.iloc[-1] - close.iloc[-6])
        rsi_slope = float(rsi_series.iloc[-1] - rsi_series.iloc[-6])
        # Divergence = RSI going opposite direction to price
        rsi_divergence = rsi_slope if abs(rsi_slope) > 2 else 0.0
        if (price_slope > 0 and rsi_slope < -3):
            rsi_divergence = rsi_slope  # bearish divergence
        elif (price_slope < 0 and rsi_slope > 3):
            rsi_divergence = rsi_slope  # bullish divergence
        else:
            rsi_divergence = 0.0
    else:
        rsi_divergence = 0.0

    # ── ATR (14) ──────────────────────────────────────────────────────────────
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr = float(tr.ewm(span=14, adjust=False).mean().iloc[-1])

    # ── Bollinger Bands (20, 2σ) ──────────────────────────────────────────────
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    bb_upper = sma20 + 2 * std20
    bb_lower = sma20 - 2 * std20
    bb_mid = sma20
    bb_width = float(
        ((bb_upper - bb_lower) / bb_mid.replace(0, float("nan"))).iloc[-1]
    ) if not bb_mid.empty else 0.05

    # ── MACD (12, 26, 9) ──────────────────────────────────────────────────────
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = float((macd_line - signal).iloc[-1])

    # ── VWAP (session approximation) ─────────────────────────────────────────
    # Typical price × volume / cumulative volume
    typical = (high + low + close) / 3
    vwap_num = (typical * volume).rolling(min(len(df), 20)).sum()
    vwap_denom = volume.rolling(min(len(df), 20)).sum()
    vwap = float((vwap_num / vwap_denom.replace(0, float("nan"))).iloc[-1])

    # ── Volume surge (vs 20-period average) ──────────────────────────────────
    vol_avg = float(volume.rolling(20).mean().iloc[-1])
    current_vol = float(volume.iloc[-1])
    volume_surge = (current_vol / vol_avg) if vol_avg > 0 else 1.0

    # ── Current OHLCV ─────────────────────────────────────────────────────────
    c = float(close.iloc[-1])
    o = float(df["Open"].astype(float).iloc[-1])
    h = float(high.iloc[-1])
    l = float(low.iloc[-1])

    # ── Structure signals ─────────────────────────────────────────────────────
    ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
    ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1]) if len(close) >= 50 else ema20

    above_vwap = c >= vwap
    trend_intact = c > ema20 and ema20 > ema50

    # Recent pivot break: new 20-day high or low
    rolling_high = float(high.rolling(20).max().iloc[-2]) if len(high) > 20 else h
    rolling_low = float(low.rolling(20).min().iloc[-2]) if len(low) > 20 else l
    recent_pivot_break = h > rolling_high or l < rolling_low

    # Compression / expansion
    compression_detected = bb_width < 0.04
    expansion_detected = bb_width > 0.08

    # Gap detection (vs prior close)
    prior_close = float(close.iloc[-2]) if len(close) > 1 else c
    gap_pct = (o - prior_close) / prior_close if prior_close > 0 else 0
    gap_up = gap_pct > 0.015
    gap_down = gap_pct < -0.015

    # Price velocity: 5-bar rate of change
    price_velocity = float(
        ((c - float(close.iloc[-6])) / float(close.iloc[-6]) * 100)
        if len(close) >= 6 else 0.0
    )

    atr_pct = (atr / c * 100) if c > 0 else 0.0
    range_pct = ((h - l) / c * 100) if c > 0 else 0.0

    return MarketFeatures(
        ticker=ticker.upper(),
        timeframe=timeframe,
        close=c,
        open=o,
        high=h,
        low=l,
        volume=current_vol,
        atr=atr,
        atr_pct=atr_pct,
        bb_width=bb_width,
        range_pct=range_pct,
        rsi=max(0.0, min(100.0, rsi)),
        rsi_divergence=rsi_divergence,
        macd_hist=macd_hist,
        above_vwap=above_vwap,
        trend_intact=trend_intact,
        recent_pivot_break=recent_pivot_break,
        compression_detected=compression_detected,
        expansion_detected=expansion_detected,
        volume_surge=volume_surge,
        price_velocity=price_velocity,
        gap_up=gap_up,
        gap_down=gap_down,
    )
