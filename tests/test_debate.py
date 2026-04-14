"""
ARGUS — Test Suite: Debate Engine
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from schemas.state import AgentResult, VeilState, PressureBias, StabilityGrade, AlertMode
from core.debate_engine import resolve


def make_agent(name: str, score: float, confidence: float = 0.75) -> AgentResult:
    return AgentResult(name=name, score=score, confidence=confidence, thesis=f"{name} thesis")


class TestDebateEngine:
    def _agents(self, p, s, b, a, c):
        return [
            make_agent("pressure", p),
            make_agent("structure", s),
            make_agent("behavior", b),
            make_agent("anomaly", a),
            make_agent("cycle", c),
        ]

    def test_high_coherent_state_is_armed(self):
        agents = self._agents(88, 82, 85, 70, 80)
        result = resolve(agents, veil_score=85)
        assert result.state in (VeilState.ARMED, VeilState.TRIGGERED, VeilState.ESCALATION)

    def test_low_coherent_state_is_dormant_or_watching(self):
        agents = self._agents(25, 20, 22, 15, 18)
        result = resolve(agents, veil_score=22)
        assert result.state in (VeilState.DORMANT, VeilState.WATCHING)

    def test_high_anomaly_triggers_distortion(self):
        agents = self._agents(75, 40, 60, 92, 55)
        result = resolve(agents, veil_score=78)
        assert result.stability in (StabilityGrade.DISTORTED, StabilityGrade.FRAGILE)

    def test_fractured_bias_when_high_contradiction(self):
        agents = self._agents(95, 5, 90, 8, 85)
        result = resolve(agents, veil_score=57)
        assert result.bias == PressureBias.FRACTURED

    def test_bullish_bias_when_pressure_and_structure_high(self):
        agents = self._agents(80, 75, 70, 40, 65)
        result = resolve(agents, veil_score=72)
        assert result.bias in (PressureBias.BULLISH, PressureBias.UNSTABLE_BULLISH)

    def test_bearish_bias_when_pressure_and_structure_low(self):
        agents = self._agents(25, 20, 35, 40, 30)
        result = resolve(agents, veil_score=28)
        assert result.bias in (PressureBias.BEARISH, PressureBias.UNSTABLE_BEARISH)

    def test_event_risk_sums_reasonable(self):
        agents = self._agents(70, 65, 72, 55, 60)
        result = resolve(agents, veil_score=66)
        er = result.event_risk
        assert 0 <= er.expansion <= 1
        assert 0 <= er.reversal <= 1
        assert 0 <= er.squeeze <= 1
        assert 0 <= er.trap <= 1

    def test_debate_summary_is_string(self):
        agents = self._agents(60, 55, 58, 50, 52)
        result = resolve(agents, veil_score=57)
        assert isinstance(result.debate_summary, str)
        assert len(result.debate_summary) > 10

    def test_memory_match_influences_state(self):
        agents = self._agents(55, 50, 52, 40, 48)
        without = resolve(agents, veil_score=50, memory_matched=False)
        with_mem = resolve(agents, veil_score=50, memory_matched=True)
        # Memory match should push toward BUILDING or higher
        state_order = [
            VeilState.DORMANT, VeilState.WATCHING, VeilState.BUILDING,
            VeilState.TENSION, VeilState.ESCALATION, VeilState.ARMED, VeilState.TRIGGERED
        ]
        if without.state in state_order and with_mem.state in state_order:
            assert state_order.index(with_mem.state) >= state_order.index(without.state)
