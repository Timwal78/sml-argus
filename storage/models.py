"""
ARGUS — Storage Models (SQLAlchemy)
"""
from sqlalchemy import (
    Column, Integer, Float, String, Boolean, DateTime, Text, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class StateLog(Base):
    __tablename__ = "state_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    veil_score = Column(Float, nullable=False)
    state = Column(String(30), nullable=False)
    bias = Column(String(30), nullable=False)
    stability = Column(String(30), nullable=False)
    briefing = Column(Text, nullable=False)
    agent_scores = Column(JSON, nullable=False)  # {"pressure": 81, "structure": 58, ...}
    scanned_at = Column(DateTime, default=datetime.utcnow, index=True)


class TickerMemory(Base):
    __tablename__ = "ticker_memory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), unique=True, nullable=False, index=True)
    squeeze_prone = Column(Boolean, default=False)
    narrative_sensitive = Column(Boolean, default=False)
    anomaly_rich = Column(Boolean, default=False)
    failure_prone = Column(Boolean, default=False)
    macro_responsive = Column(Boolean, default=False)
    typical_veil_min = Column(Float, default=20.0)
    typical_veil_max = Column(Float, default=70.0)
    notes = Column(Text, default="")
    last_updated = Column(DateTime, default=datetime.utcnow)


class PineEvent(Base):
    __tablename__ = "pine_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)
    event_type = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=True)
    fired_at = Column(DateTime, nullable=False, index=True)
    received_at = Column(DateTime, default=datetime.utcnow)


class CreditLedger(Base):
    __tablename__ = "credit_ledger"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), nullable=False, index=True)
    credits_remaining = Column(Float, default=0.0)
    tier = Column(String(20), default="free")  # "free" | "paid"
    daily_scans_used = Column(Integer, default=0)
    last_reset = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class AlertHistory(Base):
    __tablename__ = "alert_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    alert_mode = Column(String(50), nullable=False)
    channel = Column(String(50), nullable=False)  # "discord" | "webhook" | "api"
    payload = Column(JSON, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    direction = Column(String(10), nullable=False)  # "long" | "short"
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    veil_score = Column(Float, nullable=False)
    status = Column(String(20), default="open")  # "open" | "closed"
    pnl = Column(Float, default=0.0)
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    directive_id = Column(Integer, nullable=True)  # link to state_log if needed

