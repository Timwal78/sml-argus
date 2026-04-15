"""
ARGUS — Configuration
"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    app_name: str = "SML ARGUS"
    app_version: str = "0.1.0"
    debug: bool = False
    secret_key: str = "argus-dev-secret-change-in-production"

    # Database
    database_url: str = "sqlite:///./argus.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Discord
    discord_webhook_url: str = ""
    discord_alert_channel_id: str = ""

    # API Keys
    alpha_vantage_key: str = ""
    polygon_key: str = ""

    # S3 Credit Gate
    free_tier_daily_scans: int = 3
    paid_tier_daily_scans: int = 100
    credits_per_deep_scan: int = 5
    credits_per_replay: int = 10
    credits_per_sweep: int = 20

    # Scoring weights
    pressure_weight: float = 0.25
    structure_weight: float = 0.20
    behavior_weight: float = 0.20
    anomaly_weight: float = 0.20
    cycle_weight: float = 0.15

    # Scoring modifiers
    contradiction_penalty: float = 8.0
    memory_match_bonus: float = 6.0
    compression_boost: float = 5.0
    anomaly_boost_threshold: float = 85.0
    anomaly_boost_value: float = 7.0

    # ── ECHO FORGE integration ────────────────────────────────────────────────
    # Set to the ECHO FORGE service URL to enable cross-asset pattern memory.
    # Empty string = ECHO FORGE disabled (ARGUS runs in standalone mode).
    # Local dev: http://localhost:8001
    # Docker:    http://echo-forge:8001
    # Render:    https://your-echo-forge-service.onrender.com
    echo_forge_url: str = ""
    echo_forge_timeout: int = 15  # seconds before giving up on ECHO FORGE call

    # If echo confidence falls below this threshold, ARGUS ignores the echo
    # context entirely and relies solely on its own real-time analysis.
    echo_confidence_threshold: float = 0.5

    # If failure_risk_score exceeds this threshold, ARGUS enters defensive mode:
    # veil_score is penalised and the narrative flags elevated risk.
    echo_defensive_risk_threshold: float = 0.6

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
