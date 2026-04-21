"""
ARGUS — Test Suite: Credit Gating
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta
from fastapi import HTTPException

from integrations.s3_credit_gate import check_access, get_credit_account, CreditGateError
from storage.models import CreditLedger

@pytest.mark.asyncio
class TestCreditGating:
    
    @patch("integrations.s3_credit_gate.get_credit_account")
    async def test_free_tier_limits(self, mock_get_account):
        # Setup free account with maxed out scans
        account = CreditLedger(
            user_id="free_user",
            credits_remaining=0.0,
            tier="free",
            daily_scans_used=3, # assume limit is 3
            last_reset=datetime.utcnow()
        )
        mock_get_account.return_value = account
        
        session = AsyncMock()
        
        # Should raise 429 for free tier scan
        with pytest.raises(CreditGateError) as excinfo:
            await check_access("free_user", "scan", session)
        assert excinfo.value.status_code == 429
        
    @patch("integrations.s3_credit_gate.get_credit_account")
    async def test_free_tier_premium_rejection(self, mock_get_account):
        # Setup free account
        account = CreditLedger(
            user_id="free_user",
            credits_remaining=0.0,
            tier="free",
            daily_scans_used=0,
            last_reset=datetime.utcnow()
        )
        mock_get_account.return_value = account
        
        session = AsyncMock()
        
        # Should raise 402 for replay (premium feature)
        with pytest.raises(CreditGateError) as excinfo:
            await check_access("free_user", "replay", session)
        assert excinfo.value.status_code == 402
        assert "premium_required" in excinfo.value.detail["error"]

    @patch("integrations.s3_credit_gate.get_credit_account")
    async def test_paid_tier_credit_deduction(self, mock_get_account):
        # Setup paid account with 50 credits
        account = CreditLedger(
            user_id="paid_user",
            credits_remaining=50.0,
            tier="paid",
            daily_scans_used=0,
            last_reset=datetime.utcnow()
        )
        mock_get_account.return_value = account
        
        session = AsyncMock()
        
        # Replay costs 10 credits
        result = await check_access("paid_user", "replay", session)
        
        assert result["credits_remaining"] == 40.0
        assert account.credits_remaining == 40.0
        session.commit.assert_called()

    @patch("integrations.s3_credit_gate.get_credit_account")
    async def test_insufficient_credits(self, mock_get_account):
        # Setup paid account with 5 credits
        account = CreditLedger(
            user_id="paid_user",
            credits_remaining=5.0,
            tier="paid",
            daily_scans_used=0,
            last_reset=datetime.utcnow()
        )
        mock_get_account.return_value = account
        
        session = AsyncMock()
        
        # Replay costs 10 credits -> 402
        with pytest.raises(CreditGateError) as excinfo:
            await check_access("paid_user", "replay", session)
        assert excinfo.value.status_code == 402
        assert "insufficient_credits" in excinfo.value.detail["error"]
