"""
ARGUS — Alert Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from schemas.state import VeilState, PressureBias, StabilityGrade, AlertMode


class AlertPayload(BaseModel):
    system: str = "ARGUS"
    ticker: str
    mode: AlertMode
    veil_score: float
    bias: PressureBias
    stability: StabilityGrade
    state: VeilState
    event_risk_dominant: str
    briefing: str
    memory_matched: bool = False
    memory_note: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DiscordEmbed(BaseModel):
    title: str
    description: str
    color: int  # hex color as int
    fields: List[dict] = []
    footer: Optional[dict] = None
    timestamp: Optional[str] = None


class DiscordMessage(BaseModel):
    content: Optional[str] = None
    embeds: List[DiscordEmbed] = []
    username: str = "ARGUS"
    avatar_url: Optional[str] = None
