"""
ARGUS — Storage Repository
Async-compatible data access layer.
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, insert, update, desc

from storage.models import Base, StateLog, TickerMemory, PineEvent, AlertHistory
from schemas.state import StateSnapshot, VeilState, PressureBias, StabilityGrade, TickerPersonality


def create_engine_and_session(database_url: str):
    """
    Build async engine from database URL.
    Handles:
      - sqlite:///   -> sqlite+aiosqlite:///      (local dev)
      - postgres://  -> postgresql+asyncpg://     (Render legacy format)
      - postgresql:// -> postgresql+asyncpg://   (standard)
    """
    if database_url.startswith("sqlite:///"):
        async_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    elif database_url.startswith("postgres://"):
        # Render provides postgres:// — SQLAlchemy needs postgresql+asyncpg://
        async_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgresql://"):
        async_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        async_url = database_url

    engine = create_async_engine(async_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory


class StateRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def insert_state(self, snapshot: StateSnapshot) -> None:
        row = StateLog(
            ticker=snapshot.ticker.upper(),
            veil_score=snapshot.veil_score,
            state=snapshot.state.value if hasattr(snapshot.state, 'value') else snapshot.state,
            bias=snapshot.bias.value if hasattr(snapshot.bias, 'value') else snapshot.bias,
            stability=snapshot.stability.value if hasattr(snapshot.stability, 'value') else snapshot.stability,
            briefing=snapshot.briefing,
            agent_scores=snapshot.agent_scores,
            scanned_at=snapshot.scanned_at or datetime.utcnow(),
        )
        self.session.add(row)
        await self.session.commit()

    async def get_states(self, ticker: str, limit: int = 50) -> List[StateSnapshot]:
        result = await self.session.execute(
            select(StateLog)
            .where(StateLog.ticker == ticker.upper())
            .order_by(desc(StateLog.scanned_at))
            .limit(limit)
        )
        rows = result.scalars().all()
        return [
            StateSnapshot(
                id=r.id,
                ticker=r.ticker,
                veil_score=r.veil_score,
                state=VeilState(r.state),
                bias=PressureBias(r.bias),
                stability=StabilityGrade(r.stability),
                briefing=r.briefing,
                agent_scores=r.agent_scores or {},
                scanned_at=r.scanned_at,
            )
            for r in rows
        ]

    async def get_personality(self, ticker: str) -> Optional[TickerPersonality]:
        result = await self.session.execute(
            select(TickerMemory).where(TickerMemory.ticker == ticker.upper())
        )
        row = result.scalar_one_or_none()
        if not row:
            return None
        return TickerPersonality(
            ticker=row.ticker,
            squeeze_prone=row.squeeze_prone,
            narrative_sensitive=row.narrative_sensitive,
            anomaly_rich=row.anomaly_rich,
            failure_prone=row.failure_prone,
            macro_responsive=row.macro_responsive,
            typical_veil_range=(row.typical_veil_min, row.typical_veil_max),
            notes=row.notes,
            last_updated=row.last_updated,
        )

    async def upsert_personality(self, personality: TickerPersonality) -> None:
        existing = await self.session.execute(
            select(TickerMemory).where(TickerMemory.ticker == personality.ticker.upper())
        )
        row = existing.scalar_one_or_none()

        if row:
            row.squeeze_prone = personality.squeeze_prone
            row.narrative_sensitive = personality.narrative_sensitive
            row.anomaly_rich = personality.anomaly_rich
            row.failure_prone = personality.failure_prone
            row.macro_responsive = personality.macro_responsive
            row.typical_veil_min = personality.typical_veil_range[0]
            row.typical_veil_max = personality.typical_veil_range[1]
            row.notes = personality.notes
            row.last_updated = datetime.utcnow()
        else:
            self.session.add(TickerMemory(
                ticker=personality.ticker.upper(),
                squeeze_prone=personality.squeeze_prone,
                narrative_sensitive=personality.narrative_sensitive,
                anomaly_rich=personality.anomaly_rich,
                failure_prone=personality.failure_prone,
                macro_responsive=personality.macro_responsive,
                typical_veil_min=personality.typical_veil_range[0],
                typical_veil_max=personality.typical_veil_range[1],
                notes=personality.notes,
                last_updated=datetime.utcnow(),
            ))

        await self.session.commit()

    async def log_pine_event(self, ticker: str, timeframe: str, event_type: str, payload: dict, fired_at: datetime) -> None:
        self.session.add(PineEvent(
            ticker=ticker.upper(),
            timeframe=timeframe,
            event_type=event_type,
            payload=payload,
            fired_at=fired_at,
        ))
        await self.session.commit()

    async def log_alert(self, ticker: str, alert_mode: str, channel: str, payload: dict, success: bool = True, error: str = None) -> None:
        self.session.add(AlertHistory(
            ticker=ticker.upper(),
            alert_mode=alert_mode,
            channel=channel,
            payload=payload,
            success=success,
            error_message=error,
        ))
        await self.session.commit()
