"""
ARGUS — Memory Engine
Stores and retrieves state history per ticker.
Enables pattern matching, personality tracking, and state replay.
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from storage.repository import StateRepository
from schemas.state import StateSnapshot, VeilState, PressureBias, StabilityGrade, TickerPersonality


class MemoryEngine:
    """
    The memory engine gives ARGUS its temporal awareness.
    It remembers what a ticker has done before, builds personality models,
    and enables the State Replay killer feature.
    """

    def __init__(self, repo: StateRepository):
        self.repo = repo

    async def record_state(self, snapshot: StateSnapshot) -> None:
        """Persist a state snapshot for a ticker."""
        await self.repo.insert_state(snapshot)

    async def get_recent_states(
        self, ticker: str, limit: int = 20
    ) -> List[StateSnapshot]:
        """Retrieve the most recent states for a ticker."""
        return await self.repo.get_states(ticker, limit)

    async def check_memory_match(
        self, ticker: str, current_score: float, current_bias: PressureBias
    ) -> tuple[bool, Optional[str]]:
        """
        Compare current state against prior states for this ticker.
        Returns (matched, memory_note).
        """
        recent = await self.get_recent_states(ticker, limit=50)
        if not recent:
            return False, None

        # Look for similar Veil Score ranges and bias
        matches = [
            s for s in recent
            if abs(s.veil_score - current_score) < 12
            and s.bias == current_bias.value
        ]

        if len(matches) >= 2:
            outcomes = [m.state for m in matches[-5:]]
            outcome_str = ", ".join(set(outcomes))
            note = (
                f"Current setup resembles {len(matches)} prior states with {current_bias.value} bias. "
                f"Historical outcomes included: {outcome_str}."
            )
            return True, note

        return False, None

    async def get_or_create_personality(
        self, ticker: str
    ) -> TickerPersonality:
        """
        Build or retrieve the ticker personality model.
        This evolves over time as ARGUS accumulates observations.
        """
        existing = await self.repo.get_personality(ticker)
        if existing:
            return existing

        # Default personality — overridden by known patterns
        known_defaults = {
            "AMC": TickerPersonality(
                ticker="AMC",
                squeeze_prone=True,
                narrative_sensitive=True,
                failure_prone=True,
                typical_veil_range=(30, 85),
                notes="AMC is narrative-sensitive and frequently squeeze-prone. Failure after euphoric extensions is common.",
            ),
            "GME": TickerPersonality(
                ticker="GME",
                squeeze_prone=True,
                anomaly_rich=True,
                narrative_sensitive=True,
                typical_veil_range=(25, 90),
                notes="GME is event-sensitive, anomaly-rich, and amplified by social energy.",
            ),
            "SPY": TickerPersonality(
                ticker="SPY",
                macro_responsive=True,
                typical_veil_range=(20, 70),
                notes="SPY is macro-responsive with clean structure. Less tolerant of distortion.",
            ),
        }

        if ticker.upper() in known_defaults:
            personality = known_defaults[ticker.upper()]
        else:
            personality = TickerPersonality(ticker=ticker.upper())

        await self.repo.upsert_personality(personality)
        return personality

    async def get_replay(
        self, ticker: str, limit: int = 100
    ) -> List[StateSnapshot]:
        """
        Return full state history for replay mode.
        Users can watch the organism's belief evolve over time.
        """
        return await self.repo.get_states(ticker, limit=limit)

    async def get_memory_score(self, ticker: str, current_score: float) -> float:
        """
        Returns a 0–1 similarity score against historical states.
        Used by the Cycle Agent for pattern recognition.
        """
        recent = await self.get_recent_states(ticker, limit=30)
        if not recent:
            return 0.0

        similar = [s for s in recent if abs(s.veil_score - current_score) < 15]
        return min(1.0, len(similar) / 10)
