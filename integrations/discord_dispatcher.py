"""
ARGUS — Discord Dispatcher
Sends branded intelligence briefings to Discord via webhook.
"""
from __future__ import annotations
import asyncio
import httpx
import logging
from datetime import datetime
from typing import Optional

from schemas.alert import AlertPayload, DiscordEmbed, DiscordMessage
from schemas.state import AlertMode, StabilityGrade, PressureBias, VeilState
from app.config import get_settings

logger = logging.getLogger("argus.discord")
settings = get_settings()

# ── Color palette for states ──────────────────────────────────────────────────
_STATE_COLORS = {
    AlertMode.OBSERVATION: 0x4A4A6A,       # muted purple
    AlertMode.ESCALATION: 0xE8A020,        # amber
    AlertMode.COMPRESSION_WARNING: 0x5B8CFF,  # blue
    AlertMode.DISTORTION_ALERT: 0xCC44FF,  # electric violet
    AlertMode.TRIGGER_ARMED: 0xFF3030,     # red
    AlertMode.TRAP_RISK: 0xFF6600,         # orange
    AlertMode.REGIME_BREAK: 0xFF0080,      # hot pink
}

_BIAS_EMOJI = {
    PressureBias.BULLISH: "🟢",
    PressureBias.UNSTABLE_BULLISH: "🟡",
    PressureBias.BEARISH: "🔴",
    PressureBias.UNSTABLE_BEARISH: "🟠",
    PressureBias.NEUTRAL: "⬜",
    PressureBias.FRACTURED: "🔀",
}

_STABILITY_EMOJI = {
    StabilityGrade.STABLE: "✅",
    StabilityGrade.FRAGILE: "⚠️",
    StabilityGrade.DISTORTED: "🌀",
    StabilityGrade.BREAKING: "💥",
}


def build_discord_message(payload: AlertPayload) -> DiscordMessage:
    """Build a rich Discord embed from an alert payload."""
    color = _STATE_COLORS.get(payload.mode, 0x4A4A6A)
    bias_emoji = _BIAS_EMOJI.get(payload.bias, "")
    stability_emoji = _STABILITY_EMOJI.get(payload.stability, "")
    mode_label = payload.mode.value.upper().replace("_", " ")

    title = f"ARGUS // {payload.ticker} // {mode_label} ⚡"

    # Veil score bar
    filled = int(payload.veil_score / 10)
    bar = "█" * filled + "░" * (10 - filled)
    score_display = f"`{bar}` {payload.veil_score:.0f}/100"

    fields = [
        {"name": "Veil Score", "value": score_display, "inline": False},
        {"name": f"Pressure Bias {bias_emoji}", "value": payload.bias.value.replace("_", " ").title(), "inline": True},
        {"name": f"Stability {stability_emoji}", "value": payload.stability.value.title(), "inline": True},
        {"name": "State", "value": payload.state.value.upper(), "inline": True},
        {"name": "Dominant Risk", "value": payload.event_risk_dominant.replace("_", " ").title(), "inline": True},
    ]

    if payload.memory_matched and payload.memory_note:
        fields.append({"name": "🧠 Memory Match", "value": payload.memory_note[:200], "inline": False})

    embed = DiscordEmbed(
        title=title,
        description=f"> {payload.briefing}",
        color=color,
        fields=fields,
        footer={"text": f"SML ARGUS by ScriptMasterLabs | {payload.timestamp.strftime('%Y-%m-%d %H:%M UTC')}"},
        timestamp=payload.timestamp.isoformat(),
    )

    return DiscordMessage(embeds=[embed], username="ARGUS")


async def send_alert(
    payload: AlertPayload,
    webhook_url: Optional[str] = None,
    retries: int = 3,
) -> bool:
    """
    Send a Discord alert via webhook.
    Retry-safe with exponential backoff.
    """
    url = webhook_url or settings.discord_webhook_url
    if not url:
        logger.warning("Discord webhook URL not configured. Alert not sent.")
        return False

    message = build_discord_message(payload)
    message_dict = message.model_dump(mode="json")

    for attempt in range(1, retries + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=message_dict)
                if resp.status_code in (200, 204):
                    logger.info(f"Discord alert sent for {payload.ticker} [{payload.mode.value}]")
                    return True
                else:
                    logger.warning(
                        f"Discord returned {resp.status_code} on attempt {attempt}/{retries}"
                    )
        except httpx.RequestError as e:
            logger.error(f"Discord request error attempt {attempt}/{retries}: {e}")

        if attempt < retries:
            await asyncio.sleep(2 ** attempt)  # exponential backoff

    logger.error(f"Failed to send Discord alert after {retries} attempts.")
    return False


async def send_state_change_alert(
    ticker: str,
    payload: AlertPayload,
    webhook_url: Optional[str] = None,
) -> bool:
    """Convenience wrapper for state change events."""
    return await send_alert(payload, webhook_url=webhook_url)
