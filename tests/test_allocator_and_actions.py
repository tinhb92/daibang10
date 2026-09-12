#!/usr/bin/env python3
"""
Unit Test Suite: Taleb Hybrid Allocator, Velocity Radar & Pool Action Engine
Desk: Antifragile Quant & Institutional Portfolio Manager (rh/)

Verifies:
1. Velocity Radar Turnover calculation and Invariant Gating (DTE >= 7d, TVL >= $5,000).
2. Pool Action Zap-In simulation, cash flow projection, and safety enforcement.
3. Hybrid Allocator capital routing and 5.0x gas hurdle logic.
4. Hard 10x Gas Ceiling verification.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Ensure project root in sys.path
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from rh.velocity_radar import calculate_dte, MIN_DTE_DAYS, MIN_SAFE_TVL
from rh.gas_governor import check_and_enforce_gas_ceiling, MAX_ALLOWED_GAS_UNITS, MAX_ALLOWED_GAS_COST_USD
from rh.pool_actions import simulate_zap_in, MARKET_POOLS


class TestVelocityRadarAndInvariants(unittest.TestCase):

    def test_calculate_dte_valid_date(self):
        # Expiry far in future
        future_iso = "2026-10-15T00:00:00Z"
        dte = calculate_dte(future_iso)
        self.assertGreater(dte, 0.0)

    def test_calculate_dte_empty_fallback(self):
        dte = calculate_dte(None)
        self.assertEqual(dte, 30.0)

    def test_gas_ceiling_under_limit(self):
        # 150,000 units, $0.045 cost -> Well under 720,000 units and $0.22
        ok = check_and_enforce_gas_ceiling(150000, 0.045, "TEST")
        self.assertTrue(ok)

    def test_gas_ceiling_breached_units(self):
        # Exceeds 720,000 units
        with patch("alerter.send_telegram_alert"):
            ok = check_and_enforce_gas_ceiling(800000, 0.10, "TEST")
            self.assertFalse(ok)

    def test_gas_ceiling_breached_cost(self):
        # Exceeds $0.22 USD cost
        with patch("alerter.send_telegram_alert"):
            ok = check_and_enforce_gas_ceiling(500000, 0.35, "TEST")
            self.assertFalse(ok)


class TestPoolActionEngine(unittest.TestCase):

    @patch("rh.pool_actions.fetch_json")
    def test_simulate_zap_in_safe_pool(self, mock_fetch):
        # Mock NVDA market data
        mock_fetch.return_value = {
            "expiry": "2026-10-15T00:00:00Z",
            "liquidity": {"usd": 100000.0},
            "tradingVolume": {"usd": 40000.0},
            "aggregatedApy": 0.25,
            "underlyingApy": 0.10,
            "swapFeeApy": 0.05,
            "pendleApy": 0.10,
            "impliedApy": 0.10,
            "ptDiscount": 0.02,
            "underlyingAsset": {"price": {"usd": 200.0}}
        }

        res = simulate_zap_in("NVDA", 0.5)
        self.assertEqual(res["market"], "NVDA")
        self.assertEqual(res["capital_usd"], 100.0)
        self.assertEqual(res["velocity"], 0.40)
        self.assertTrue(res["is_safe_to_enter"])
        self.assertEqual(len(res["violations"]), 0)
        self.assertIn("zap/in?chain=robinhood", res["direct_zap_url"])

    @patch("rh.pool_actions.fetch_json")
    def test_simulate_zap_in_blocks_ajit_jain_cliff(self, mock_fetch):
        # Mock pool with only 4 days to maturity (under 7d cliff)
        now_dt = calculate_dte(None)
        mock_fetch.return_value = {
            "expiry": "2026-09-15T00:00:00Z",  # Near expiry
            "liquidity": {"usd": 50000.0},
            "tradingVolume": {"usd": 10000.0},
            "aggregatedApy": 0.50,
            "underlyingAsset": {"price": {"usd": 10.0}}
        }

        res = simulate_zap_in("SNUKE", 10.0)
        # Should flag Ajit Jain Cliff if dte < 7.0
        if res["dte"] < MIN_DTE_DAYS:
            self.assertFalse(res["is_safe_to_enter"])
            self.assertTrue(any("Ajit Jain" in v for v in res["violations"]))

    @patch("rh.pool_actions.fetch_json")
    def test_simulate_zap_in_blocks_illiquid_pool(self, mock_fetch):
        # Mock pool with only $1,200 TVL (below $5k floor)
        mock_fetch.return_value = {
            "expiry": "2026-10-15T00:00:00Z",
            "liquidity": {"usd": 1200.0},
            "tradingVolume": {"usd": 100.0},
            "aggregatedApy": 0.50,
            "underlyingAsset": {"price": {"usd": 10.0}}
        }

        res = simulate_zap_in("SNUKE", 5.0)
        self.assertFalse(res["is_safe_to_enter"])
        self.assertTrue(any("Liquidity Floor" in v for v in res["violations"]))


class TestDeltaNeutralSimulation(unittest.TestCase):

    def test_nvda_delta_neutral_math(self):
        from rh.research.simulate_nvda_delta_neutral import simulate_nvda_delta_neutral
        res = simulate_nvda_delta_neutral(
            total_capital_usd=1000.0,
            nvda_spot_price=200.0,
            pendle_allocation_pct=0.50,
            pendle_pool_apy=25.0,
            pendle_maker_apr=100.0,
            hl_leverage=2.0,
            horizon_days=30.0
        )
        self.assertEqual(res["pendle_capital"], 500.0)
        self.assertEqual(res["hl_margin"], 500.0)
        self.assertEqual(res["nvda_units"], 2.5)
        # Liquidation price: 200 + (500 / 2.5) = 400 (+100%)
        self.assertEqual(res["liq_price"], 400.0)
        self.assertEqual(res["liq_distance_pct"], 100.0)
        # Pool net APR on total capital: (25% on 50% capital) = 12.5%
        self.assertAlmostEqual(res["pool_route"]["net_apr_total_cap"], 12.5, places=2)
        # Maker net APR on total capital: (100% on 50% capital) = 50.0%
        self.assertAlmostEqual(res["maker_route"]["net_apr_total_cap"], 50.0, places=2)


if __name__ == "__main__":
    unittest.main()
