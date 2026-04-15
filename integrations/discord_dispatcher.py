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


# ── Trade Directive Discord Embed ─────────────────────────────────────────────
# This fires on EVERY directive scan — not just escalated states.
# When you scan from the dashboard, you get the result in Discord.

_ACTION_COLORS = {
    "BUY": 0x00FF88,
    "SELL SHORT": 0xFF3030,
    "BUY (small size)": 0x00CC66,
    "SELL SHORT (small)": 0xFF6644,
    "BUY (paper first)": 0x5B8CFF,
    "SELL SHORT (paper)": 0xFF8844,
    "REDUCE / TRIM": 0xFF6600,
    "EXIT NOW": 0xFF0044,
}


async def send_directive(directive, webhook_url: Optional[str] = None, retries: int = 3) -> bool:
    """
    Send a Trade Directive to Discord. Fires on EVERY scan.
    ARGUS tells you what to trade. This puts it in your Discord.
    """
    url = webhook_url or settings.discord_webhook_url
    if not url:
        logger.warning("Discord webhook URL not configured. Directive not sent.")
        return False

    # Pick color from action text
    color = 0x555577  # default: no-trade grey
    for key, val in _ACTION_COLORS.items():
        if key in directive.action:
            color = val
            break
    if "WAIT" in directive.action:
        color = 0xFFD700  # amber for wait
    if "STAY OUT" in directive.action:
        color = 0xFF4444  # red for stay out

    # Build conviction bar
    pct = directive.conviction_pct
    filled = pct // 10
    bar = "█" * filled + "░" * (10 - filled)
    conviction_line = f"`{bar}` {pct}% — {directive.conviction}"

    # Build level lines
    levels = []
    if directive.entry_above is not None:
        levels.append(f"🎯 Entry Above: **${directive.entry_above:.2f}**")
    if directive.stop_loss is not None:
        levels.append(f"🛑 Stop Loss: **${directive.stop_loss:.2f}**")
    if directive.target_1 is not None:
        levels.append(f"💰 Target 1: **${directive.target_1:.2f}**")
    if directive.target_2 is not None:
        levels.append(f"🚀 Target 2: **${directive.target_2:.2f}**")
    levels_text = "\n".join(levels) if levels else "No price levels generated."

    # Kill conditions
    kills = "\n".join(f"✕ {k}" for k in directive.kill_conditions[:4]) if directive.kill_conditions else "None"

    fields = [
        {"name": "📊 Conviction", "value": conviction_line, "inline": False},
        {"name": f"{directive.risk_emoji} Risk / Size", "value": f"**{directive.risk_grade}** risk · Position: **{directive.position_size}**", "inline": True},
        {"name": "📈 Veil Score", "value": f"**{directive.veil_score:.1f}** — {directive.state.upper()}", "inline": True},
    ]

    if levels:
        fields.append({"name": "🎯 Price Levels", "value": levels_text, "inline": False})

    fields.append({"name": "💡 Reasoning", "value": directive.reasoning[:400], "inline": False})

    if directive.kill_conditions:
        fields.append({"name": "🚫 Kill Conditions", "value": kills, "inline": False})

    embed = DiscordEmbed(
        title=f"⚡ {directive.ticker} — {directive.action}",
        description=f"> {directive.headline}",
        color=color,
        fields=fields,
        footer={"text": f"SML ARGUS Trade Directive | {directive.scanned_at.strftime('%Y-%m-%d %H:%M UTC') if directive.scanned_at else ''}"},
        timestamp=directive.scanned_at.isoformat() if directive.scanned_at else None,
    )

    message = DiscordMessage(embeds=[embed], username="ARGUS")
    message_dict = message.model_dump(mode="json")

    for attempt in range(1, retries + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=message_dict)
                if resp.status_code in (200, 204):
                    logger.info(f"Discord directive sent for {directive.ticker} [{directive.action}]")
                    return True
                else:
                    logger.warning(f"Discord returned {resp.status_code} on directive attempt {attempt}/{retries}")
        except httpx.RequestError as e:
            logger.error(f"Discord directive error attempt {attempt}/{retries}: {e}")

        if attempt < retries:
            await asyncio.sleep(2 ** attempt)

    logger.error(f"Failed to send Discord directive after {retries} attempts.")
    return False

