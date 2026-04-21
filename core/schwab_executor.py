"""
ARGUS — Schwab Execution Service
Manages the schwabdev client, OAuth lifecycle, and order execution.
Supports both Paper (simulated) and Live (brokerage) modes.
"""
from __future__ import annotations
import os
import json
import logging
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import schwabdev
from app.config import get_settings
from schemas.trade_intent import TradeIntent, ActionClass
from storage.models import PaperTrade
from core.data_adapter import fetch_features, get_latest_price

logger = logging.getLogger("argus.schwab")
settings = get_settings()

class SchwabExecutor:
    _instance: Optional[SchwabExecutor] = None

    def __init__(self):
        self.client: Optional[schwabdev.Client] = None
        self.paper_mode = settings.schwab_paper_mode
        self._is_connected = False
        self._initialize_from_storage()

    @classmethod
    def get_instance(cls) -> SchwabExecutor:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _initialize_from_storage(self):
        """Attempts to initialize the schwabdev client if credentials and tokens exist."""
        if not settings.schwab_app_key or not settings.schwab_app_secret:
            logger.info("Schwab keys missing or empty. Execution limb restricted to Paper Mode.")
            return

        try:
            # schwabdev handles token loading/refreshing internally
            self.client = schwabdev.Client(
                app_key=settings.schwab_app_key,
                app_secret=settings.schwab_app_secret,
                callback_url=settings.schwab_callback_url,
                tokens_file=settings.schwab_tokens_path
            )
            # Check connection by fetching account numbers (hashValue)
            resp = self.client.linked_accounts()
            if resp.status_code == 200:
                self._is_connected = True
                logger.info("Schwab Limb connected and authorized.")
            else:
                self._is_connected = False
                logger.info(f"Schwab authorized but connection check failed (status: {resp.status_code}).")
        except Exception as e:
            logger.error(f"Schwab client initialization failed: {e}")
            self._is_connected = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    def get_auth_url(self) -> str:
        """Generates the URL for the user to log in to Schwab."""
        if not settings.schwab_app_key or not settings.schwab_app_secret:
            return ""
            
        if not self.client:
            try:
                # Temporary client for URL generation if keys are present
                temp_client = schwabdev.Client(
                    app_key=settings.schwab_app_key,
                    app_secret=settings.schwab_app_secret,
                    callback_url=settings.schwab_callback_url
                )
                return temp_client.auth_url()
            except Exception as e:
                logger.error(f"Failed to generate auth URL: {e}")
                return ""
        return self.client.auth_url()

    def update_tokens(self, response_url: str):
        """Pass the full redirect URL back to the client to capture the auth code."""
        if not self.client:
            self.client = schwabdev.Client(
                app_key=settings.schwab_app_key,
                app_secret=settings.schwab_app_secret,
                callback_url=settings.schwab_callback_url,
                tokens_file=settings.schwab_tokens_path
            )
        
        # This exchanges the code for tokens and saves them to the file
        self.client.update_tokens(response_url)
        self._is_connected = True
        logger.info("Schwab tokens updated and saved.")

    async def execute_trade(self, intent: TradeIntent, session: AsyncSession) -> Dict[str, Any]:
        """Entry point for executing a trade directive."""
        if intent.action_class in (ActionClass.OBSERVE_ONLY, ActionClass.WATCH_FOR_TRIGGER):
            return {"status": "skipped", "reason": "Action class requires observation only."}

        if self.paper_mode:
            return await self._execute_paper_trade(intent, session)
        
        if not self.is_connected:
            return {"status": "failed", "reason": "Schwab not connected. Authorization required."}

        return await self._execute_live_trade(intent, session)

    async def _calculate_position_size(self, ticker: str, price: float, confidence: float) -> float:
        """
        Calculate quantity based on target risk per trade and engine confidence.
        Logic: (Max Risk USD * Confidence) / Price
        """
        target_risk = settings.schwab_risk_per_trade_usd
        risk_at_confidence = target_risk * confidence
        
        if price <= 0:
            return 0
            
        quantity = risk_at_confidence / price
        
        # Round to nearest share for equity (standard for this limb)
        return float(round(quantity))

    async def _execute_paper_trade(self, intent: TradeIntent, session: AsyncSession) -> Dict[str, Any]:
        """Simulate a trade in the local database using real-time prices."""
        logger.info(f"EXECUTING PAPER TRADE: {intent.direction} {intent.ticker}")
        
        try:
            # Fetch latest price from the data adapter (lightweight fetch)
            entry_price = await get_latest_price(intent.ticker)
        except Exception as e:
            logger.warning(f"Failed to fetch real price for paper trade: {e}. Falling back to indicator close.")
            features = await fetch_features(intent.ticker, timeframe="1m")
            entry_price = features.close
        
        # Calculate dynamic quantity
        quantity = await self._calculate_position_size(intent.ticker, entry_price, intent.confidence)
        if quantity <= 0:
            quantity = 1.0 # Minimum 1 unit
        
        trade = PaperTrade(
            ticker=intent.ticker,
            direction=intent.direction,
            quantity=quantity,
            entry_price=entry_price,
            veil_score=intent.veil_score,
            status="open",
            opened_at=datetime.utcnow()
        )
        session.add(trade)
        await session.commit()
        
        return {
            "status": "success", 
            "mode": "paper", 
            "ticker": intent.ticker, 
            "direction": intent.direction,
            "entry": entry_price,
            "quantity": quantity,
            "confidence": intent.confidence
        }

    async def _execute_live_trade(self, intent: TradeIntent, session: AsyncSession) -> Dict[str, Any]:
        """Actually place the order on Schwab."""
        logger.info(f"EXECUTING LIVE TRADE: {intent.direction} {intent.ticker}")
        
        if not self.client:
             return {"status": "failed", "mode": "live", "reason": "Client not initialized"}

        # 1. Get account hash
        try:
            accounts = self.client.linked_accounts().json()
            account_hash = accounts[0].get('hashValue')
        except Exception as e:
            return {"status": "failed", "mode": "live", "reason": f"Account fetch failed: {e}"}
        
        # 2. Get current price for sizing
        try:
            current_price = await get_latest_price(intent.ticker)
        except Exception as e:
            logger.warning(f"Live execution failed to fetch fast price: {e}. Trying full fetch.")
            try:
                features = await fetch_features(intent.ticker, timeframe="1m")
                current_price = features.close
            except Exception as fe:
                return {"status": "failed", "mode": "live", "reason": f"Could not fetch price: {fe}"}

        quantity = await self._calculate_position_size(intent.ticker, current_price, intent.confidence)
        if quantity <= 0:
            return {"status": "skipped", "mode": "live", "reason": "Calculated quantity is zero."}

        # 3. Build order payload
        instruction = "BUY" if intent.direction == "long" else "SELL_SHORT"
        
        order = {
            "orderType": "MARKET",
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [
                {
                    "instruction": instruction,
                    "quantity": int(quantity), 
                    "instrument": {
                        "symbol": intent.ticker,
                        "assetType": "EQUITY"
                    }
                }
            ]
        }
        
        resp = self.client.place_order(account_hash, order)
        if resp.status_code in (200, 201):
            return {
                "status": "success", 
                "mode": "live", 
                "order_id": resp.headers.get('location', '').split('/')[-1],
                "quantity": quantity
            }
        else:
            return {"status": "failed", "mode": "live", "reason": resp.text}

    async def get_active_positions(self, session: AsyncSession) -> Dict[str, Any]:
        """Fetch both active Paper Trades and Live Brokerage Positions."""
        # 1. Paper Positions
        stmt = select(PaperTrade).where(PaperTrade.status == "open")
        result = await session.execute(stmt)
        paper_trades = result.scalars().all()
        
        paper_positions = []
        for trade in paper_trades:
            current_price = await get_latest_price(trade.ticker)
            pnl_pct = ((current_price - trade.entry_price) / trade.entry_price * 100) if trade.direction == "long" else \
                      ((trade.entry_price - current_price) / trade.entry_price * 100)
            
            paper_positions.append({
                "id": trade.id,
                "ticker": trade.ticker,
                "direction": trade.direction,
                "quantity": trade.quantity,
                "entry": trade.entry_price,
                "current": current_price,
                "pnl_pct": round(pnl_pct, 2),
                "type": "paper"
            })

        # 2. Live Positions
        live_positions = []
        if self.is_connected and self.client:
            try:
                accounts = self.client.linked_accounts().json()
                account_hash = accounts[0].get('hashValue')
                # get_account() in schwabdev returns positions if included
                resp = self.client.account_details(account_hash, fields="positions")
                if resp.status_code == 200:
                    data = resp.json()
                    raw_positions = data.get('securitiesAccount', {}).get('positions', [])
                    for p in raw_positions:
                        instr = p.get('instrument', {})
                        live_positions.append({
                            "id": instr.get('symbol'),
                            "ticker": instr.get('symbol'),
                            "direction": "long" if p.get('longQuantity', 0) > 0 else "short",
                            "quantity": p.get('longQuantity') or p.get('shortQuantity'),
                            "entry": p.get('averagePrice'),
                            "current": p.get('marketValue') / (p.get('longQuantity') or p.get('shortQuantity')) if (p.get('longQuantity') or p.get('shortQuantity')) else 0,
                            "pnl_pct": 0.0, # Schwab provides PnL in the response usually
                            "type": "live"
                        })
            except Exception as e:
                logger.error(f"Failed to fetch live positions: {e}")

        return {
            "paper": paper_positions,
            "live": live_positions
        }

    async def close_position(self, target_id: str, mode: str, session: AsyncSession) -> Dict[str, Any]:
        """Close an active position."""
        if mode == "paper":
            stmt = select(PaperTrade).where(PaperTrade.id == int(target_id))
            result = await session.execute(stmt)
            trade = result.scalar_one_or_none()
            if not trade:
                return {"status": "failed", "reason": "Trade not found"}
            
            exit_price = await get_latest_price(trade.ticker)
            trade.exit_price = exit_price
            trade.status = "closed"
            trade.closed_at = datetime.utcnow()
            
            pnl = (exit_price - trade.entry_price) * trade.quantity if trade.direction == "long" else \
                  (trade.entry_price - exit_price) * trade.quantity
            trade.pnl = pnl
            
            await session.commit()
            return {"status": "success", "pnl": pnl, "exit": exit_price}

        # Live closing (simplified: market order to flatten)
        if mode == "live" and self.is_connected and self.client:
            # To simplify, we fetch positions to find quantity
            positions_data = await self.get_active_positions(session)
            target = next((p for p in positions_data['live'] if p['ticker'] == target_id), None)
            if not target:
                return {"status": "failed", "reason": "Live position not found"}
            
            instruction = "SELL" if target['direction'] == "long" else "BUY_TO_COVER"
            
            accounts = self.client.linked_accounts().json()
            account_hash = accounts[0].get('hashValue')
            
            order = {
                "orderType": "MARKET",
                "session": "NORMAL",
                "duration": "DAY",
                "orderStrategyType": "SINGLE",
                "orderLegCollection": [{
                    "instruction": instruction,
                    "quantity": int(target['quantity']),
                    "instrument": {"symbol": target['ticker'], "assetType": "EQUITY"}
                }]
            }
            resp = self.client.place_order(account_hash, order)
            if resp.status_code in (200, 201):
                return {"status": "success", "mode": "live"}
            return {"status": "failed", "reason": resp.text}

        return {"status": "failed", "reason": "Invalid mode or connection lost"}
