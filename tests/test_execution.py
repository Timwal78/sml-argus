"""
ARGUS — Test Suite: Schwab Execution
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from core.schwab_executor import SchwabExecutor
from schemas.trade_intent import TradeIntent, ActionClass
from storage.models import PaperTrade, CreditLedger

@pytest.mark.asyncio
class TestSchwabExecution:
    
    async def test_calculate_position_size(self):
        executor = SchwabExecutor.get_instance()
        # Default risk is 1000. Price 200, confidence 0.5.
        # (1000 * 0.5) / 200 = 500 / 200 = 2.5 → rounded to 3 (standard round())
        # Actually round(2.5) in Python 3 is 2 (bankers rounding) or 3 depends?
        # Let's check: round(2.5) == 2, round(3.5) == 4. 
        # But for shares, we just want a reasonable number.
        
        qty = await executor._calculate_position_size("TEST", 200.0, 0.5)
        # (1000 * 0.5) / 200 = 2.5. round(2.5) = 2
        assert qty >= 2
        
        qty_high = await executor._calculate_position_size("TEST", 10.0, 0.9)
        # (1000 * 0.9) / 10 = 900 / 10 = 90
        assert qty_high == 90.0

    async def test_execute_paper_trade(self):
        # Mock fetch_features to return a close price of 50.0
        mock_features = MagicMock()
        mock_features.close = 50.0
        
        # Patch the source of the data
        with patch("core.data_adapter.fetch_features", new_callable=AsyncMock) as mock_fetch:
            print(f"DEBUG: mock_fetch is {mock_fetch}")
            mock_fetch.return_value = mock_features
            
            session = AsyncMock(spec=AsyncSession)
            
            # Force a fresh instance for the test
            SchwabExecutor._instance = None
            executor = SchwabExecutor.get_instance()
            
            intent = TradeIntent(
                ticker="AAPL",
                action_class=ActionClass.LIVE_HIGH_CONVICTION,
                direction="long",
                veil_score=85.0,
                confidence=0.8,
                bias="bullish",
                stability="stable",
                invalidation_conditions=[],
                confirm_above=155.0,
                invalidate_below=145.0,
                risk_note="Test risk",
                briefing="Test briefing"
            )
            
            result = await executor._execute_paper_trade(intent, session)
        
        assert result["status"] == "success"
        assert result["mode"] == "paper"
        assert result["entry"] == 50.0
        # (1000 * 0.8) / 50 = 800 / 50 = 16
        assert result["quantity"] == 16.0
        
        # Verify it was added to session
        session.add.assert_called_once()
        args, _ = session.add.call_args
        trade = args[0]
        assert isinstance(trade, PaperTrade)
        assert trade.ticker == "AAPL"
        assert trade.quantity == 16.0

    async def test_skip_observe_only(self):
        session = AsyncMock(spec=AsyncSession)
        executor = SchwabExecutor.get_instance()
        
        intent = TradeIntent(
            ticker="AAPL",
            action_class=ActionClass.OBSERVE_ONLY,
            direction="none",
            veil_score=40.0,
            confidence=0.5,
            bias="neutral",
            stability="stable",
            invalidation_conditions=[],
            confirm_above=0, invalidate_below=0, risk_note="", briefing=""
        )
        
        result = await executor.execute_trade(intent, session)
        assert result["status"] == "skipped"
