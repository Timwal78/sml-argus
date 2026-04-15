"""
ARGUS — Echo Forge Client
HTTP bridge from ARGUS to the ECHO FORGE pattern memory service.

Design principles:
  - Fully non-blocking: runs concurrently with ARGUS's own market data fetch.
  - Gracefully degrading: any failure (timeout, connection refused, bad response)
    returns None. ARGUS never hard-fails because ECHO FORGE is unavailable.
  - Zero side effects: ECHO FORGE is read-only intelligence. This client
    never triggers writes in ECHO FORGE.
  - Key forwarding: the caller's Polygon key is forwarded so ECHO FORGE can
    fetch the same live data ARGUS is seeing.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from schemas.echo_context import (
    EchoContext,
    EchoFailureAnalysis,
    EchoOutcomeDistribution,
    EchoProjection,
    EchoScenario,
)
from app.config import get_settings

logger = logging.getLogger("argus.integrations.echo_forge")


async def fetch_echo_context(
    ticker: str,
    timeframe: str,
    polygon_key: Optional[str] = None,
    window_size: int = 60,
    top_n: int = 20,
) -> Optional[EchoContext]:
    """
    Call ECHO FORGE's /echo_scan endpoint and translate the response into an
    EchoContext object for use in the ARGUS intelligence pipeline.

    Returns None if:
      - ECHO_FORGE_URL is not configured (ECHO FORGE disabled)
      - Network failure, timeout, or HTTP error
      - Response cannot be parsed
      - Service returns an unexpected structure

    Parameters
    ----------
    ticker      : Instrument to scan (e.g., 'AMC', 'TSLA', 'BTC-USD')
    timeframe   : Bar timeframe string ('1h', '15m', '1d', etc.)
    polygon_key : Optional Polygon.io API key to forward to ECHO FORGE
    window_size : Number of bars in the structural fingerprint window
    top_n       : Number of historical echo matches to retrieve
    """
    settings = get_settings()

    if not settings.echo_forge_url:
        logger.debug("ECHO FORGE disabled (ECHO_FORGE_URL not set) — skipping echo context fetch")
        return None

    endpoint = f"{settings.echo_forge_url.rstrip('/')}/echo_scan"

    payload: dict = {
        "ticker": ticker.upper(),
        "timeframe": timeframe,
        "window_size": window_size,
        "top_n": top_n,
        "cross_asset": True,
        "include_failure_analysis": True,
        "include_projections": True,
    }
    # Only forward the key if the caller actually has one
    if polygon_key:
        payload["polygon_key"] = polygon_key

    try:
        async with httpx.AsyncClient(timeout=settings.echo_forge_timeout) as client:
            resp = await client.post(endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        logger.warning("ECHO FORGE timeout (%ss) for %s — proceeding without echo context", settings.echo_forge_timeout, ticker)
        return None
    except httpx.ConnectError:
        logger.warning("ECHO FORGE unreachable at %s — proceeding without echo context", settings.echo_forge_url)
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning("ECHO FORGE returned HTTP %s for %s — proceeding without echo context", exc.response.status_code, ticker)
        return None
    except Exception as exc:
        logger.error("Unexpected ECHO FORGE error for %s: %s — proceeding without echo context", ticker, exc)
        return None

    try:
        return _parse_echo_response(data, settings.echo_confidence_threshold, settings.echo_defensive_risk_threshold)
    except Exception as exc:
        logger.error("Failed to parse ECHO FORGE response for %s: %s", ticker, exc)
        return None


def _parse_echo_response(
    data: dict,
    confidence_threshold: float,
    defensive_risk_threshold: float,
) -> EchoContext:
    """
    Translate raw ECHO FORGE JSON into a typed EchoContext.
    Applies the integration rules to set derived flags.
    """
    # ── Outcome distribution ──────────────────────────────────────────────────
    dist_raw = data.get("outcome_distribution", {})
    outcome_distribution = EchoOutcomeDistribution(
        continuation=dist_raw.get("continuation", 0.0),
        reversal=dist_raw.get("reversal", 0.0),
        failure=dist_raw.get("failure", 0.0),
        neutral=dist_raw.get("neutral", 0.0),
    )

    # ── Failure analysis ──────────────────────────────────────────────────────
    failure_analysis: Optional[EchoFailureAnalysis] = None
    fa_raw = data.get("failure_analysis")
    if fa_raw:
        failure_analysis = EchoFailureAnalysis(
            failure_rate=fa_raw.get("failure_rate", 0.0),
            failure_risk_score=fa_raw.get("failure_risk_score", 0.0),
            divergence_signals=fa_raw.get("divergence_signals", []),
            risk_factors=fa_raw.get("risk_factors", []),
        )

    # ── Projection ────────────────────────────────────────────────────────────
    projection: Optional[EchoProjection] = None
    proj_raw = data.get("projection")
    if proj_raw:
        primary_raw = proj_raw.get("primary_scenario", {})
        primary_scenario: Optional[EchoScenario] = None
        if primary_raw:
            primary_scenario = EchoScenario(
                label=primary_raw.get("label", ""),
                probability=primary_raw.get("probability", 0.0),
                expected_return=primary_raw.get("expected_return", 0.0),
                return_range=primary_raw.get("return_range", [0.0, 0.0]),
                time_to_resolution=primary_raw.get("time_to_resolution", ""),
                confidence=primary_raw.get("confidence", 0.0),
                description=primary_raw.get("description", ""),
            )
        projection = EchoProjection(
            primary_scenario=primary_scenario,
            overall_confidence=proj_raw.get("overall_confidence", 0.0),
            time_horizon=proj_raw.get("time_horizon", ""),
            narrative=proj_raw.get("narrative", ""),
        )

    # ── Core fields ───────────────────────────────────────────────────────────
    confidence = float(data.get("confidence", 0.0))
    failure_risk_score = failure_analysis.failure_risk_score if failure_analysis else 0.0

    # ── Integration rule flags ─────────────────────────────────────────────────
    # Rule: confidence < threshold → low_confidence, ARGUS skips modulation
    low_confidence = confidence < confidence_threshold

    # Rule: failure_risk_score > threshold → defensive mode, ARGUS applies risk penalty
    defensive_mode = failure_risk_score > defensive_risk_threshold

    # Rule: cross-asset conflict — populated by future batch scan logic
    # For now: flag if reversal probability exceeds continuation probability
    # AND we have enough matches to trust the signal
    n_matches = int(data.get("n_matches", 0))
    cross_asset_conflict = (
        not low_confidence
        and n_matches >= 5
        and outcome_distribution.reversal > outcome_distribution.continuation
    )

    return EchoContext(
        echo_type=data.get("echo_type", ""),
        confidence=confidence,
        n_matches=n_matches,
        similarity_score=float(data.get("similarity_score", 0.0)),
        outcome_distribution=outcome_distribution,
        failure_analysis=failure_analysis,
        projection=projection,
        low_confidence=low_confidence,
        defensive_mode=defensive_mode,
        cross_asset_conflict=cross_asset_conflict,
    )
