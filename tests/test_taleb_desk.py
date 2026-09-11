#!/usr/bin/env python3
"""
Institutional Invariant & Gas Economics Test Suite for Taleb Desk (Pendle V2)
Validates core mathematical invariants:
1. Seth Klarman Margin of Safety Floor
2. Negative Carry Ceiling
3. Ajit Jain Maturity Cliff (< 7.0 DTE Hazard)
4. 10x Gas Ceiling Guard (< 720,000 units, < $0.22 USD)
5. Multi-Day Gas Hurdle Amortization (≥ 5.0x Reward-to-Gas Ratio)
"""

import os
import sys
import unittest
from datetime import datetime, timezone, timedelta

# Ensure repo root and rh/ are in sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RH_DIR = os.path.join(REPO_ROOT, "rh")
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if RH_DIR not in sys.path:
    sys.path.insert(0, RH_DIR)

from gas_governor import (
    evaluate_shift_economic_viability,
    check_and_enforce_gas_ceiling,
    AVG_CANCEL_GAS_UNITS,
    MAX_ALLOWED_GAS_UNITS,
    MAX_ALLOWED_GAS_COST_USD,
    MIN_REWARD_TO_GAS_RATIO
)
from config.market_params import (
    validate_order_safety,
    normalize_market_key,
    get_supported_markets,
    get_min_short_rates,
    get_max_long_rates
)
from scan_opportunities import calculate_dte


class TestTalebDeskInvariants(unittest.TestCase):

    def setUp(self):
        self.gas_cost_usd = 0.0184  # Standard Robinhood L2 cancellation cost

    def test_gas_economic_viability_multi_day_horizon(self):
        """Validates that multi-day horizon properly amortizes gas and avoids the 24h false rejection."""
        order_size_usd = 10.0  # $10 USD notional
        current_apr = 0.0      # Currently out of band
        new_apr = 100.0        # 100% APR in band

        # 24-hour horizon: $10 * 100% * (24 / 8760) = $0.0274 reward. Gas = $0.0184. Ratio = 1.49x (< 5.0x hurdle)
        econ_24h = evaluate_shift_economic_viability(
            order_size_usd=order_size_usd,
            current_incentive_apr=current_apr,
            new_incentive_apr=new_apr,
            gas_cost_usd=self.gas_cost_usd,
            projected_holding_hours=24.0
        )
        self.assertFalse(econ_24h["is_viable"], "24h horizon on $10 order must fail the 5.0x hurdle")
        self.assertLess(econ_24h["reward_to_gas_ratio"], 5.0)

        # 7-day horizon: $10 * 100% * (168 / 8760) = $0.1918 reward. Gas = $0.0184. Ratio = 10.42x (>= 5.0x hurdle)
        econ_7d = evaluate_shift_economic_viability(
            order_size_usd=order_size_usd,
            current_incentive_apr=current_apr,
            new_incentive_apr=new_apr,
            gas_cost_usd=self.gas_cost_usd,
            projected_holding_hours=168.0
        )
        self.assertTrue(econ_7d["is_viable"], "7-day horizon on $10 order must pass the 5.0x hurdle")
        self.assertGreaterEqual(econ_7d["reward_to_gas_ratio"], 5.0)
        self.assertAlmostEqual(econ_7d["hours_to_breakeven"], 16.12, delta=0.5)

    def test_gas_governor_10x_ceiling_enforcement(self):
        """Validates that operations exceeding 10x baseline gas units or $0.22 USD are rejected."""
        from unittest.mock import patch

        with patch("alerter.send_telegram_alert") as mock_alert:
            # Within nominal limits
            self.assertTrue(check_and_enforce_gas_ceiling(72000, 0.018))
            self.assertTrue(check_and_enforce_gas_ceiling(300000, 0.10))
            self.assertEqual(mock_alert.call_count, 0)

            # Exceeding gas units limit (720,000 units)
            self.assertFalse(check_and_enforce_gas_ceiling(750000, 0.15))
            self.assertGreaterEqual(mock_alert.call_count, 1)

            # Exceeding USD cost ceiling ($0.22 USD)
            self.assertFalse(check_and_enforce_gas_ceiling(50000, 0.35))

    def test_seth_klarman_floor_invariant(self):
        """Validates rejection of PT/Short orders below the Seth Klarman hurdle rate."""
        # NVDA hurdle floor is 9.65%
        is_safe, reason, violations = validate_order_safety(
            market_identifier="NVDA",
            side="SHORT",
            rate_apy=8.50,  # Below 9.65% floor
            dte_days=30.0
        )
        self.assertFalse(is_safe)
        self.assertTrue(any("KLARMAN_FLOOR_VIOLATION" in v for v in violations))

        # NVDA valid rate above hurdle
        is_safe, _, violations = validate_order_safety(
            market_identifier="NVDA",
            side="SHORT",
            rate_apy=10.00,
            dte_days=30.0
        )
        self.assertTrue(is_safe, f"Expected safe order, got violations: {violations}")

    def test_negative_carry_ceiling_invariant(self):
        """Validates rejection of Long/YT orders above the negative carry ceiling."""
        # NVDA max long ceiling is 10.40%
        is_safe, reason, violations = validate_order_safety(
            market_identifier="NVDA",
            side="LONG",
            rate_apy=15.00,  # Paying 15% borrow
            dte_days=30.0
        )
        self.assertFalse(is_safe)
        self.assertTrue(any("NEGATIVE_CARRY_CEILING_VIOLATION" in v for v in violations))

    def test_ajit_jain_maturity_cliff_invariant(self):
        """Validates that any order within 7 days of expiry is rejected as a terminal cliff hazard."""
        # Market with DTE = 5.0 days (< 7.0d threshold)
        is_safe, reason, violations = validate_order_safety(
            market_identifier="sNET",
            side="SHORT",
            rate_apy=12500.0,
            dte_days=5.0
        )
        self.assertFalse(is_safe)
        self.assertTrue(any("MATURITY_CLIFF_HAZARD" in v for v in violations))

        # Market with DTE = 14.0 days (> 7.0d threshold)
        is_safe, _, violations = validate_order_safety(
            market_identifier="SHROOM",
            side="SHORT",
            rate_apy=63.95,
            dte_days=14.0
        )
        self.assertTrue(is_safe, f"Expected safe order, got violations: {violations}")

    def test_calculate_dte_dynamic(self):
        """Validates dynamic DTE calculation from ISO expiry timestamps."""
        now = datetime.now(timezone.utc)

        # 10 days in future
        fut_10d = (now + timedelta(days=10)).isoformat()
        dte = calculate_dte(fut_10d)
        self.assertAlmostEqual(dte, 10.0, delta=0.1)

        # Past expiry (expired)
        past_5d = (now - timedelta(days=5)).isoformat()
        dte_past = calculate_dte(past_5d)
        self.assertEqual(dte_past, 0.0)

    def test_market_normalization(self):
        """Validates resolution of symbols and addresses to standard market keys."""
        self.assertEqual(normalize_market_key("nvda"), "NVDA")
        self.assertEqual(normalize_market_key("sNet"), "sNET")
        self.assertEqual(normalize_market_key("0x206a5cd00e9ffabb8ca564076b64799a78df19b9"), "NVDA")
        self.assertIsNone(normalize_market_key("non_existent_token"))


if __name__ == "__main__":
    unittest.main()
