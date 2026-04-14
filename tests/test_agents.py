"""
ARGUS — Test Suite: Agent Layer
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.perception import MarketFeatures


def base_features(ticker="TEST", timeframe="1h") -> MarketFeatures:
    return MarketFeatures(ticker=ticker, timeframe=timeframe, close=100.0, rsi=50.0, volume_surge=1.0)


class TestPressureAgent:
    def test_returns_valid_result(self):
        from agents.pressure_agent import run
        result = run(base_features())
        assert result.name == "pressure"
        assert 0 <= result.score <= 100
        assert 0 <= result.confidence <= 1

    def test_high_volume_bullish_increases_score(self):
        from agents.pressure_agent import run
        f = base_features()
        f.volume_surge = 3.0
        f.above_vwap = True
        result = run(f)
        assert result.score > 55

    def test_low_volume_below_vwap_decreases_score(self):
        from agents.pressure_agent import run
        f = base_features()
        f.volume_surge = 0.5
        f.above_vwap = False
        result = run(f)
        assert result.score < 50


class TestStructureAgent:
    def test_returns_valid_result(self):
        from agents.structure_agent import run
        result = run(base_features())
        assert result.name == "structure"
        assert 0 <= result.score <= 100

    def test_intact_trend_boosts_score(self):
        from agents.structure_agent import run
        f = base_features()
        f.trend_intact = True
        f.macd_hist = 1.0
        result = run(f)
        assert result.score > 55

    def test_broken_trend_lowers_score(self):
        from agents.structure_agent import run
        f = base_features()
        f.trend_intact = False
        f.recent_pivot_break = True
        result = run(f)
        assert result.score < 45


class TestBehaviorAgent:
    def test_returns_valid_result(self):
        from agents.behavior_agent import run
        result = run(base_features())
        assert result.name == "behavior"
        assert 0 <= result.score <= 100

    def test_chase_conditions_raise_score(self):
        from agents.behavior_agent import run
        f = base_features()
        f.volume_surge = 3.0
        f.price_velocity = 2.0
        result = run(f)
        assert result.score > 60


class TestAnomalyAgent:
    def test_returns_valid_result(self):
        from agents.anomaly_agent import run
        result = run(base_features())
        assert result.name == "anomaly"
        assert 0 <= result.score <= 100

    def test_no_anomalies_gives_low_score(self):
        from agents.anomaly_agent import run
        f = base_features()
        f.volume_surge = 1.0
        f.rsi_divergence = 2.0
        f.compression_detected = False
        result = run(f)
        assert result.score < 60

    def test_multiple_anomalies_raise_score(self):
        from agents.anomaly_agent import run
        f = base_features()
        f.volume_surge = 3.0
        f.range_pct = 0.5  # high vol, tiny range = absorption
        f.rsi_divergence = -12.0
        f.expansion_detected = True
        f.trend_intact = False
        result = run(f)
        assert result.score > 55


class TestCycleAgent:
    def test_returns_valid_result(self):
        from agents.cycle_agent import run
        result = run(base_features())
        assert result.name == "cycle"
        assert 0 <= result.score <= 100

    def test_memory_score_boosts_cycle(self):
        from agents.cycle_agent import run
        f = base_features()
        f.memory_score = 0.85
        result = run(f)
        assert result.score > 55
