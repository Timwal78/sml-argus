"""
ECHO FORGE — Window Extraction
Handles time-series slicing and forward-labeling.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from typing import List, Tuple, Dict, Any

def extract_windows(
    df: pd.DataFrame, 
    window_size: int = 60, 
    step_size: int = 10,
    min_future_bars: int = 20
) -> List[Dict[str, Any]]:
    """
    Extracts sliding windows from OHLCV data.
    Each window is a dictionary containing:
    - 'data': The OHLCV slice (window_size length)
    - 'outcome': The forward price action (min_future_bars length)
    - 'metadata': Start/End times, etc.
    """
    windows = []
    
    if len(df) < window_size + min_future_bars:
        return []

    # Ensure index is sorted
    df = df.sort_index()

    for i in range(0, len(df) - window_size - min_future_bars + 1, step_size):
        window_df = df.iloc[i : i + window_size]
        future_df = df.iloc[i + window_size : i + window_size + min_future_bars]
        
        start_time = window_df.index[0]
        end_time = window_df.index[-1]
        
        # Calculate outcome metrics
        initial_price = window_df["Close"].iloc[-1]
        max_high = future_df["High"].max()
        min_low = future_df["Low"].min()
        final_price = future_df["Close"].iloc[-1]
        
        max_return = (max_high - initial_price) / initial_price
        max_drawdown = (min_low - initial_price) / initial_price
        final_return = (final_price - initial_price) / initial_price
        
        windows.append({
            "ticker": getattr(df, "ticker", "UNKNOWN"),
            "start_time": start_time,
            "end_time": end_time,
            "ohlcv": window_df,
            "outcome": {
                "max_upside": float(max_return),
                "max_downside": float(max_drawdown),
                "final_return": float(final_return),
                "forward_bars": len(future_df)
            }
        })
        
    return windows

def label_window(window: Dict[str, Any]) -> str:
    """
    Classifies a window based on its forward outcome.
    """
    out = window["outcome"]
    if out["max_upside"] > 0.05 and out["final_return"] > 0.03:
        return "explosive_continuation"
    if out["max_upside"] > 0.03 and out["max_downside"] > -0.01:
        return "slow_grind_up"
    if out["max_downside"] < -0.05:
        return "reversal_collapse"
    if out["max_upside"] < 0.01 and out["max_downside"] > -0.01:
        return "directionless_compression"
    
    return "standard_drift"
