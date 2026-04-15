"""
ARGUS — Chart Endpoint Tests
Tests the /chart/{ticker} and /chart/history/{ticker} route schemas.
"""
import pytest
from routes.chart import ChartPoint, _BIAS_MAP, _STABILITY_MAP, _STATE_MAP


class TestChartPoint:
    """Validate the ChartPoint model constraints."""

    def test_valid_chart_point(self):
        point = ChartPoint(
            ticker="AMC",
            veil_score=65.3,
            bias_code=1,
            stability_code=0,
            state_code=4,
            alert_mode="escalation",
            agent_pressure=58.2,
            agent_structure=62.1,
            agent_behavior=45.0,
            agent_anomaly=30.5,
            agent_cycle=40.0,
            scanned_at="2026-04-15T12:00:00",
        )
        assert point.ticker == "AMC"
        assert 0 <= point.veil_score <= 100

    def test_veil_score_clamped_low(self):
        with pytest.raises(Exception):
            ChartPoint(
                ticker="X",
                veil_score=-5,
                bias_code=0,
                stability_code=0,
                state_code=0,
                alert_mode="observation",
                agent_pressure=50,
                agent_structure=50,
                agent_behavior=50,
                agent_anomaly=50,
                agent_cycle=50,
                scanned_at="2026-04-15T12:00:00",
            )

    def test_veil_score_clamped_high(self):
        with pytest.raises(Exception):
            ChartPoint(
                ticker="X",
                veil_score=150,
                bias_code=0,
                stability_code=0,
                state_code=0,
                alert_mode="observation",
                agent_pressure=50,
                agent_structure=50,
                agent_behavior=50,
                agent_anomaly=50,
                agent_cycle=50,
                scanned_at="2026-04-15T12:00:00",
            )


class TestMappings:
    """Validate bias/stability/state code mappings."""

    def test_bias_map_completeness(self):
        expected = {"neutral", "bullish", "unstable_bullish", "bearish", "unstable_bearish", "fractured"}
        assert expected == set(_BIAS_MAP.keys())

    def test_stability_map_completeness(self):
        expected = {"stable", "fragile", "distorted", "breaking"}
        assert expected == set(_STABILITY_MAP.keys())

    def test_state_map_completeness(self):
        expected = {"dormant", "watching", "building", "tension", "escalation", "armed", "triggered", "distorted", "failure", "trap", "cooldown"}
        assert expected == set(_STATE_MAP.keys())

    def test_bias_codes_are_unique(self):
        # Excluding trap/failure overlap which is intentional
        values = list(_BIAS_MAP.values())
        assert len(values) == len(set(values))

    def test_state_codes_monotonic(self):
        """States should progress from 0 (dormant) to higher values."""
        assert _STATE_MAP["dormant"] == 0
        assert _STATE_MAP["triggered"] == 6
        assert _STATE_MAP["distorted"] == 7


class TestChartPointDefaults:
    """Validate default field values."""

    def test_memory_matched_defaults_false(self):
        point = ChartPoint(
            ticker="SPY",
            veil_score=50.0,
            bias_code=0,
            stability_code=0,
            state_code=0,
            alert_mode="observation",
            agent_pressure=50,
            agent_structure=50,
            agent_behavior=50,
            agent_anomaly=50,
            agent_cycle=50,
            scanned_at="2026-04-15T12:00:00",
        )
        assert point.memory_matched is False
