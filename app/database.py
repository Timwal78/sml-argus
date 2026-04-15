"""
ARGUS — Database Dependency
Singleton session factory, shared across all route modules.
"""
from __future__ import annotations
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Module-level factory — set by app lifespan
_session_factory: Optional[async_sessionmaker] = None


def set_session_factory(factory: async_sessionmaker) -> None:
    global _session_factory
    _session_factory = factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async DB session."""
    if _session_factory is None:
        raise RuntimeError("Session factory not initialized")
    async with _session_factory() as session:
        yield session


def get_session_factory() -> Optional[async_sessionmaker]:
    """Return the session factory for background tasks (like the auto-sweep scheduler)."""
    return _session_factory
