#!/usr/bin/env python3
"""
Unit Test Suite for Pendle V2 Liquidity Pools Opportunity & Antifragility Scanner
Tests:
- Yield decomposition (Underlying, Swap Fees, PENDLE Rewards, PT Discount)
- Ajit Jain Cliff Hazard detection (DTE < 7.0d)
- Micro-cap illiquidity trap detection (TVL < $5,000 USD)
- Asymmetry ranking and cash flow projections
- Direct Zap-In URL generation
"""

import os
import sys
import unittest
from datetime import datetime, timezone, timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RH_DIR = os.path.join(REPO_ROOT, "rh")
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if RH_DIR not in sys.path:
    sys.path.insert(0, RH_DIR)

from scan_pools import evaluate_pool_opportunity, calculate_dte, MIN_DTE_CLIFF_DAYS, MIN_SAFE_LIQUIDITY_USD


class TestPoolsScanner(unittest.TestCase):

    def test_snuke_pool_evaluation(self):
        """Validates evaluation of high-yield sNUKE AMM pool."""
        now = datetime.now(timezone.utc)
        expiry_12d = (now + timedelta(days=12)).isoformat()

        raw_data = {
            "proName": "sNUKE",
            "address": "0x8547b391a65deb89c41a4c3b2eb1502d0bbc566a",
            "expiry": expiry_12d,
            "liquidity": {"usd": 21580.0},
            "tradingVolume": {"usd": 1080.0},
            "aggregatedApy": 1.4778,     # 147.78%
            "underlyingApy": 1.0434,     # 104.34%
            "swapFeeApy": 0.2721,        # 27.21%
            "pendleApy": 0.1332,         # 13.32%
            "maxBoostedApy": 1.6776,
            "impliedApy": 1.1042,
            "ptDiscount": 0.0242
        }

        res = evaluate_pool_opportunity(raw_data)
        self.assertEqual(res["name"], "sNUKE")
        self.assertAlmostEqual(res["aggregated_apy"], 147.78, delta=0.01)
        self.assertAlmostEqual(res["underlying_apy"], 104.34, delta=0.01)
        self.assertAlmostEqual(res["swap_fee_apy"], 27.21, delta=0.01)
        self.assertAlmostEqual(res["pendle_apy"], 13.32, delta=0.01)
        self.assertFalse(res["is_cliff_hazard"], "12d DTE should pass cliff check")
        self.assertFalse(res["is_low_liquidity"], "$21.5k TVL should pass liquidity check")
        self.assertGreater(res["asymmetry_score"], 0.0)
        self.assertIn("0x8547b391a65deb89c41a4c3b2eb1502d0bbc566a", res["zap_url"])

    def test_ajit_jain_cliff_rejection_for_pools(self):
        """Validates that pools approaching maturity (< 7d) are flagged with cliff hazard."""
        now = datetime.now(timezone.utc)
        expiry_4d = (now + timedelta(days=4)).isoformat()

        raw_data = {
            "proName": "sNET",
            "address": "0x23c68474e3cd533a2f952a0fb998f1867e57d27f",
            "expiry": expiry_4d,
            "liquidity": {"usd": 500000.0},
            "tradingVolume": {"usd": 50000.0},
            "aggregatedApy": 100.0,
            "underlyingApy": 50.0,
            "swapFeeApy": 10.0,
            "pendleApy": 10.0
        }

        res = evaluate_pool_opportunity(raw_data)
        self.assertTrue(res["is_cliff_hazard"], "4d DTE must trigger cliff hazard")
        self.assertEqual(res["asymmetry_score"], 0.0, "Hazard pools must receive 0 asymmetry score")
        self.assertTrue(any("AJIT JAIN CLIFF" in tag for tag in res["risk_tags"]))

    def test_illiquid_pool_trap_rejection(self):
        """Validates rejection of micro-cap pools with TVL < $5,000 USD."""
        now = datetime.now(timezone.utc)
        expiry_20d = (now + timedelta(days=20)).isoformat()

        raw_data = {
            "proName": "microduck",
            "address": "0xdd34d9471667107f9b45e2204add3dd4da54e5a6",
            "expiry": expiry_20d,
            "liquidity": {"usd": 1200.0},  # < $5,000 threshold
            "tradingVolume": {"usd": 50.0},
            "aggregatedApy": 250.0,
            "underlyingApy": 0.0,
            "swapFeeApy": 10.0,
            "pendleApy": 240.0
        }

        res = evaluate_pool_opportunity(raw_data)
        self.assertTrue(res["is_low_liquidity"], "$1,200 TVL must trigger illiquid trap warning")
        self.assertEqual(res["asymmetry_score"], 0.0)
        self.assertTrue(any("ILLIQUID TRAP" in tag for tag in res["risk_tags"]))

    def test_daily_cashflow_calculation(self):
        """Validates daily reward and horizon return math per $1,000 USD deposit."""
        now = datetime.now(timezone.utc)
        expiry_10d = (now + timedelta(days=10)).isoformat()

        raw_data = {
            "proName": "TEST_POOL",
            "address": "0x1234567890abcdef1234567890abcdef12345678",
            "expiry": expiry_10d,
            "liquidity": {"usd": 50000.0},
            "tradingVolume": {"usd": 1000.0},
            "aggregatedApy": 0.365,  # 36.5% APY -> exactly 0.1% per day
            "underlyingApy": 0.20,
            "swapFeeApy": 0.10,
            "pendleApy": 0.065
        }

        res = evaluate_pool_opportunity(raw_data)
        # $1,000 * 36.5% / 365 = $1.00 USD / day
        self.assertAlmostEqual(res["daily_reward_usd_per_1k"], 1.00, delta=0.01)
        # Over 10 days = $10.00 USD
        self.assertAlmostEqual(res["projected_pnl_per_1k"], 10.00, delta=0.1)


if __name__ == "__main__":
    unittest.main()
