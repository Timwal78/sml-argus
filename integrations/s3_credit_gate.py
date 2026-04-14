"""
ARGUS — S3 Credit Gate
Modular credit-based access control for premium intelligence endpoints.
Free tier | Paid tier | Per-endpoint credit costs.
"""
from __future__ import annotations
import logging
from datetime import datetime, date
from typing import Optional

from fastapi import HTTPException, Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import CreditLedger
from sqlalchemy import select
from app.config import get_settings

logger = logging.getLogger("argus.credit_gate")
settings = get_settings()

# ── Credit costs per endpoint ──────────────────────────────────────────────────
CREDIT_COSTS = {
    "scan": 1,
    "deep_scan": settings.credits_per_deep_scan,
    "replay": settings.credits_per_replay,
    "sweep": settings.credits_per_sweep,
    "debate_transcript": 3,
    "trade_intent": 2,
    "memory_compare": 4,
}


class CreditGateError(HTTPException):
    pass


async def get_credit_account(
    user_id: str,
    session: AsyncSession,
) -> CreditLedger:
    """Fetch or create a credit account for a user."""
    result = await session.execute(
        select(CreditLedger).where(CreditLedger.user_id == user_id)
    )
    account = result.scalar_one_or_none()

    if not account:
        # New users get a free tier account
        account = CreditLedger(
            user_id=user_id,
            credits_remaining=0.0,
            tier="free",
            daily_scans_used=0,
            last_reset=datetime.utcnow(),
        )
        session.add(account)
        await session.commit()

    # Reset daily scan count if it's a new day
    if account.last_reset.date() < date.today():
        account.daily_scans_used = 0
        account.last_reset = datetime.utcnow()
        await session.commit()

    return account


async def check_access(
    user_id: str,
    endpoint: str,
    session: AsyncSession,
) -> dict:
    """
    Check if a user has access to a specific endpoint.
    Returns access metadata dict.
    Raises CreditGateError (HTTP 402/429) if access is denied.
    """
    account = await get_credit_account(user_id, session)
    cost = CREDIT_COSTS.get(endpoint, 1)

    if account.tier == "free":
        # Free tier: limited daily scans, no credits
        if endpoint in ("deep_scan", "replay", "sweep", "debate_transcript", "memory_compare"):
            raise CreditGateError(
                status_code=402,
                detail={
                    "error": "premium_required",
                    "message": f"Endpoint '{endpoint}' requires a paid tier subscription.",
                    "upgrade_url": "/upgrade",
                }
            )
        if account.daily_scans_used >= settings.free_tier_daily_scans:
            raise CreditGateError(
                status_code=429,
                detail={
                    "error": "daily_limit_exceeded",
                    "message": f"Free tier limit of {settings.free_tier_daily_scans} scans/day reached.",
                    "resets_at": "midnight UTC",
                }
            )
        account.daily_scans_used += 1
        await session.commit()

    else:
        # Paid tier: credit-based
        if account.credits_remaining < cost:
            raise CreditGateError(
                status_code=402,
                detail={
                    "error": "insufficient_credits",
                    "message": f"This endpoint costs {cost} credits. You have {account.credits_remaining:.0f} remaining.",
                    "cost": cost,
                    "remaining": account.credits_remaining,
                }
            )
        account.credits_remaining -= cost
        account.daily_scans_used += 1
        await session.commit()

    return {
        "user_id": user_id,
        "tier": account.tier,
        "credits_remaining": account.credits_remaining,
        "daily_scans_used": account.daily_scans_used,
    }


async def add_credits(user_id: str, amount: float, session: AsyncSession) -> float:
    """Add credits to a user's account."""
    account = await get_credit_account(user_id, session)
    account.credits_remaining += amount
    account.tier = "paid"
    account.updated_at = datetime.utcnow()
    await session.commit()
    return account.credits_remaining


async def upgrade_to_paid(user_id: str, initial_credits: float, session: AsyncSession) -> None:
    """Upgrade a user to the paid tier."""
    account = await get_credit_account(user_id, session)
    account.tier = "paid"
    account.credits_remaining = initial_credits
    await session.commit()
