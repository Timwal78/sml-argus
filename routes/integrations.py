"""
ARGUS — Integration Routes
POST /webhook/pine          — ingest TradingView Pine alerts
POST /intent/schwab/{ticker} — generate trade intent for Schwab bridge
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from integrations.pine_webhook import validate_payload, map_to_features, extract_log_record, PineWebhookError
from integrations.schwab_bridge import generate_trade_intent
from integrations.discord_dispatcher import send_alert
import httpx
from schemas.webhook import PineWebhookPayload
from schemas.trade_intent import TradeIntent
from schemas.alert import AlertPayload
from storage.repository import StateRepository
from core.memory_engine import MemoryEngine
from core import scoring, debate_engine, narrative_engine
from agents import pressure_agent, structure_agent, behavior_agent, anomaly_agent, cycle_agent
from schemas.state import StateSnapshot
from app.config import get_settings
from app.database import get_session

router = APIRouter()
settings = get_settings()


@router.post(
    "/webhook/pine",
    summary="Ingest a TradingView Pine Script alert webhook",
)
async def receive_pine_webhook(
    payload: dict,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    TradingView sends a POST here when a Pine alert fires.
    The payload is validated, mapped to features, and logged.
    """
    try:
        pine = validate_payload(payload)
    except PineWebhookError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Log the Pine event
    repo = StateRepository(session)
    log = extract_log_record(pine)
    await repo.log_pine_event(
        ticker=log["ticker"],
        timeframe=log["timeframe"],
        event_type=log["event_type"],
        payload=log["payload"],
        fired_at=log["fired_at"],
    )

    # Map to features for a quick re-scan
    features = map_to_features(pine)

    # Run agents on Pine-enriched features
    agents = [
        pressure_agent.run(features),
        structure_agent.run(features),
        behavior_agent.run(features),
        anomaly_agent.run(features),
        cycle_agent.run(features),
    ]

    veil_score = scoring.compute_veil_score(agents, compression_active=features.compression_detected)
    debate = debate_engine.resolve(agents, veil_score)
    briefing = narrative_engine.generate_briefing(
        ticker=pine.ticker,
        veil_score=veil_score,
        bias=debate.bias,
        stability=debate.stability,
        state=debate.state,
        alert_mode=debate.alert_mode,
        event_risk=debate.event_risk,
        agents=agents,
    )

    # Persist Pine-triggered state
    await repo.insert_state(StateSnapshot(
        ticker=pine.ticker.upper(),
        veil_score=veil_score,
        state=debate.state,
        bias=debate.bias,
        stability=debate.stability,
        briefing=briefing,
        agent_scores={a.name: a.score for a in agents},
        scanned_at=datetime.utcnow(),
    ))

    return {
        "status": "processed",
        "ticker": pine.ticker.upper(),
        "event_type": pine.event_type,
        "veil_score": veil_score,
        "state": debate.state.value,
        "briefing": briefing[:200],
    }


@router.post(
    "/intent/{ticker}",
    response_model=TradeIntent,
    summary="Generate a Schwab trade intent payload",
)
async def get_trade_intent(
    ticker: str,
    session: AsyncSession = Depends(get_session),
) -> TradeIntent:
    """
    Generates a structured trade intent for the Schwab execution bridge.
    Based on the latest stored state for the ticker.
    """
    from schemas.state import ScanResponse, ScanRequest
    from routes.scan import scan_ticker

    # Run a fresh scan
    request = ScanRequest(ticker=ticker, timeframes=["15m", "1h", "1d"])
    scan_result = await scan_ticker(request, session)
    intent = generate_trade_intent(scan_result)
    return intent


@router.post(
    "/discord/test",
    summary="Send a test message to Discord to verify webhook connectivity",
)
async def test_discord():
    """
    Sends a plain-text + embed test message to verify the Discord webhook works.
    """
    url = settings.discord_webhook_url
    if not url:
        return {"success": False, "error": "DISCORD_WEBHOOK_URL not configured"}

    test_message = {
        "content": "⚡ **ARGUS Test Message** — If you see this, Discord is connected!",
        "username": "ARGUS",
        "embeds": [{
            "title": "🟢 ARGUS Discord Connection Verified",
            "description": "The Trade Command Center is connected to this channel.\n\nAll trade directives will appear here automatically when you scan tickers.",
            "color": 0x00FF88,
            "fields": [
                {"name": "System", "value": "SML ARGUS v0.2.2", "inline": True},
                {"name": "Status", "value": "✅ Online", "inline": True},
                {"name": "Mode", "value": "Trade Directive + Pulse Radar", "inline": True},
            ],
            "footer": {"text": "ScriptMasterLabs — ARGUS Trade Command Center"},
        }],
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=test_message)
            if resp.status_code in (200, 204):
                return {"success": True, "status_code": resp.status_code, "message": "Test message sent to Discord!"}
            else:
                return {"success": False, "status_code": resp.status_code, "error": resp.text[:200]}
    except httpx.RequestError as e:
        return {"success": False, "error": str(e)}

