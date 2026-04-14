"""
ARGUS — Pine Webhook Ingestion
Accepts TradingView-style webhook alerts and maps them to perception inputs.
"""
from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from schemas.webhook import PineWebhookPayload, VALID_EVENT_TYPES
from core.perception import MarketFeatures, build_features_from_pine

logger = logging.getLogger("argus.pine")


class PineWebhookError(Exception):
    pass


def validate_payload(raw: dict) -> PineWebhookPayload:
    """
    Validate an incoming Pine webhook payload.
    Raises PineWebhookError on validation failure.
    """
    try:
        payload = PineWebhookPayload(**raw)
    except Exception as e:
        raise PineWebhookError(f"Invalid Pine payload schema: {e}")

    if payload.event_type not in VALID_EVENT_TYPES:
        raise PineWebhookError(
            f"Unknown event_type '{payload.event_type}'. "
            f"Valid types: {sorted(VALID_EVENT_TYPES)}"
        )

    return payload


def map_to_features(payload: PineWebhookPayload) -> MarketFeatures:
    """
    Map a validated Pine webhook payload to a MarketFeatures packet
    suitable for the agent layer.
    """
    raw = payload.model_dump()
    return build_features_from_pine(
        ticker=payload.ticker.upper(),
        timeframe=payload.timeframe,
        raw=raw,
    )


def extract_log_record(payload: PineWebhookPayload) -> dict:
    """
    Extract a storage-ready log record from a Pine payload.
    """
    return {
        "ticker": payload.ticker.upper(),
        "timeframe": payload.timeframe,
        "event_type": payload.event_type,
        "payload": payload.model_dump(mode="json"),
        "fired_at": payload.fired_at,
    }
