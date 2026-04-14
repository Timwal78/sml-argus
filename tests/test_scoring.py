"""
ARGUS — Test Suite: Scoring Engine
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from schemas.state import AgentResult
from core.scoring import compute_veil_score


def make_agent(name: str, score: float, confidence: float = 0.75) -> AgentResult:
    return AgentResult(
        name=name, score=score, confidence=confidence,
        thesis=f"{name} test thesis",
    )


class TestVeilScoring:
    def test_basic_score_in_range(self):
        agents = [
            make_agent("pressure", 70),
            make_agent("structure", 60),
            make_agent("behavior", 65),
            make_agent("anomaly", 45),
            make_agent("cycle", 55),
        ]
        score = compute_veil_score(agents)
        assert 0 <= score <= 100

    def test_high_scores_produce_high_veil(self):
        agents = [
            make_agent("pressure", 90),
            make_agent("structure", 85),
            make_agent("behavior", 88),
            make_agent("anomaly", 80),
            make_agent("cycle", 82),
        ]
        score = compute_veil_score(agents)
        assert score >= 70, f"Expected high Veil Score, got {score}"

    def test_low_scores_produce_low_veil(self):
        agents = [
            make_agent("pressure", 20),
            make_agent("structure", 15),
            make_agent("behavior", 25),
            make_agent("anomaly", 10),
            make_agent("cycle", 20),
        ]
        score = compute_veil_score(agents)
        assert score <= 40, f"Expected low Veil Score, got {score}"

    def test_memory_match_bonus_applied(self):
        agents = [make_agent(n, 60) for n in ["pressure", "structure", "behavior", "anomaly", "cycle"]]
        base = compute_veil_score(agents, memory_matched=False)
        boosted = compute_veil_score(agents, memory_matched=True)
        assert boosted > base, "Memory match should increase score"

    def test_compression_boost_applied(self):
        agents = [make_agent(n, 60) for n in ["pressure", "structure", "behavior", "anomaly", "cycle"]]
        base = compute_veil_score(agents, compression_active=False)
        boosted = compute_veil_score(agents, compression_active=True)
        assert boosted > base, "Compression boost should increase score"

    def test_contradiction_reduces_score(self):
        """Highly divergent agent scores should be penalized."""
        agents = [
            make_agent("pressure", 95),
            make_agent("structure", 5),
            make_agent("behavior", 95),
            make_agent("anomaly", 5),
            make_agent("cycle", 95),
        ]
        score = compute_veil_score(agents)
        naive_avg = (95 + 5 + 95 + 5 + 95) / 5  # 59
        assert score < naive_avg, "Contradiction should reduce the score below naive average"

    def test_score_never_exceeds_100(self):
        agents = [make_agent(n, 100) for n in ["pressure", "structure", "behavior", "anomaly", "cycle"]]
        score = compute_veil_score(agents, memory_matched=True, compression_active=True)
        assert score <= 100

    def test_score_never_below_zero(self):
        agents = [make_agent(n, 0) for n in ["pressure", "structure", "behavior", "anomaly", "cycle"]]
        score = compute_veil_score(agents)
        assert score >= 0
