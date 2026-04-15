"""
ARGUS — Echo Context Schemas
Pydantic models for the ECHO FORGE response fields consumed by ARGUS.

These are intentionally *not* a full mirror of the ECHO FORGE response.
Only the fields specified in the ECHO FORGE ↔ ARGUS integration spec are
represented here.  ARGUS treats ECHO FORGE as an advisory oracle, not a
dependency — all fields are Optional and have safe defaults.
"""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class EchoOutcomeDistribution(BaseModel):
    """Historical outcome probability distribution from matched echoes."""
    continuation: float = 0.0
    reversal: float = 0.0
    failure: float = 0.0
    neutral: float = 0.0


class EchoScenario(BaseModel):
    """A single forward scenario as projected by ECHO FORGE."""
    label: str
    probability: float
    expected_return: float
    return_range: List[float] = Field(default_factory=lambda: [0.0, 0.0])
    time_to_resolution: str = ""
    confidence: float = 0.0
    description: str = ""


class EchoProjection(BaseModel):
    """Forward projection produced by ECHO FORGE's ProjectionEngine."""
    primary_scenario: Optional[EchoScenario] = None
    overall_confidence: float = 0.0
    time_horizon: str = ""
    narrative: str = ""


class EchoFailureAnalysis(BaseModel):
    """Failure mode analysis from ECHO FORGE."""
    failure_rate: float = 0.0
    failure_risk_score: float = 0.0
    divergence_signals: List[str] = Field(default_factory=list)
    risk_factors: List[str] = Field(default_factory=list)


class EchoContext(BaseModel):
    """
    The structural memory context delivered by ECHO FORGE to ARGUS.

    Consumed by:
      - core/engine.py  (scoring modulation)
      - core/narrative_engine.py  (echo briefing paragraph)
      - schemas/state.py  (ScanResponse field)

    Integration rules (enforced in engine.py):
      - low_confidence=True   → engine skips echo modulation entirely
      - defensive_mode=True   → engine applies -5 pt veil_score penalty
      - cross_asset_conflict  → narrative flags regime ambiguity
    """
    # ── Core identity ─────────────────────────────────────────────────────────
    echo_type: str = ""
    confidence: float = 0.0
    n_matches: int = 0
    similarity_score: float = 0.0

    # ── Outcome intelligence ───────────────────────────────────────────────────
    outcome_distribution: EchoOutcomeDistribution = Field(
        default_factory=EchoOutcomeDistribution
    )
    failure_analysis: Optional[EchoFailureAnalysis] = None
    projection: Optional[EchoProjection] = None

    # ── Derived flags (computed by echo_forge_client, not from raw response) ──
    low_confidence: bool = False       # confidence < ECHO_CONFIDENCE_THRESHOLD
    defensive_mode: bool = False       # failure_risk_score > ECHO_DEFENSIVE_RISK_THRESHOLD
    cross_asset_conflict: bool = False # same structure resolving bearishly elsewhere
