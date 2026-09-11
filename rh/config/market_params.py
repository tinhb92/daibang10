"""
Centralized Robinhood Desk Market Parameters & Constraint Safety Engine
Mirrors the Boros market_params architecture with Robinhood-specific gas economics,
Seth Klarman Margin of Safety Hurdle rates, and Ajit Jain Maturity Cliffs.
"""

import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
MARKETS_CONFIG_FILE = os.path.join(CONFIG_DIR, "markets.json")

# -----------------------------------------------------------------------------
# DEFAULT FALLBACK INVARIANTS
# -----------------------------------------------------------------------------
DEFAULT_SUPPORTED_MARKETS = ["NVDA", "sNET", "sNUKE", "PFE"]

DEFAULT_MIN_SHORT_RATES: Dict[str, float] = {
    "NVDA": 9.65,    # Band floor [9.65%, 10.40%], Klarman base hurdle ≥ 8.00%
    "sNET": 11334.00,# Hyper-yield band floor [11334%, 13334%]
    "sNUKE": 95.50,  # Band floor [95.53%, 116.76%]
    "PFE": 3.76      # Band floor [3.76%, 4.17%] (sub-hurdle caution)
}

DEFAULT_MAX_LONG_RATES: Dict[str, float] = {
    "NVDA": 10.40,   # Band ceiling; avoid paying euphoric fixed borrow
    "sNET": 13334.00,# Hyper-yield ceiling
    "sNUKE": 116.76, # Band ceiling
    "PFE": 4.17      # Band ceiling
}

DEFAULT_EDGE_BUFFERS_BPS: Dict[str, int] = {
    "NVDA": 20,      # 0.20% buffer from edge
    "sNET": 200,     # 2.00% buffer
    "sNUKE": 50,     # 0.50% buffer
    "PFE": 10        # 0.10% buffer
}

DEFAULT_GAS_GUARDRAILS: Dict[str, Any] = {
    "baseline_gas_units": 72000,
    "max_allowed_gas_multiplier": 10,
    "max_gas_units": 720000,
    "max_gas_cost_usd": 0.22,
    "min_reward_to_gas_ratio": 5.0,
    "min_eth_runway": 0.002
}

DEFAULT_MIN_DTE_CLIFF_DAYS = 7.0


# -----------------------------------------------------------------------------
# DYNAMIC JSON LOADER
# -----------------------------------------------------------------------------
def load_market_config() -> Dict[str, Any]:
    """Loads markets configuration from markets.json if available, falling back to defaults."""
    if os.path.exists(MARKETS_CONFIG_FILE):
        try:
            with open(MARKETS_CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def get_supported_markets() -> List[str]:
    cfg = load_market_config()
    raw = cfg.get("supported_markets")
    if raw and isinstance(raw, list):
        return [str(x) for x in raw]
    return list(DEFAULT_SUPPORTED_MARKETS)


def get_min_short_rates() -> Dict[str, float]:
    cfg = load_market_config()
    raw = cfg.get("min_short_rates", {})
    merged = dict(DEFAULT_MIN_SHORT_RATES)
    if raw and isinstance(raw, dict):
        for k, v in raw.items():
            try:
                merged[str(k).upper()] = float(v)
            except (ValueError, TypeError):
                pass
    return merged


def get_max_long_rates() -> Dict[str, float]:
    cfg = load_market_config()
    raw = cfg.get("max_long_rates", {})
    merged = dict(DEFAULT_MAX_LONG_RATES)
    if raw and isinstance(raw, dict):
        for k, v in raw.items():
            try:
                merged[str(k).upper()] = float(v)
            except (ValueError, TypeError):
                pass
    return merged


def get_gas_guardrails() -> Dict[str, Any]:
    cfg = load_market_config()
    return cfg.get("gas_guardrails", DEFAULT_GAS_GUARDRAILS)


def normalize_market_key(market_identifier: str) -> Optional[str]:
    """Resolves case-insensitive symbols or contract addresses to canonical market key."""
    if not market_identifier:
        return None
    ident = market_identifier.strip().lower()
    
    cfg = load_market_config()
    markets = cfg.get("markets", {})
    
    # Check by key
    for k in markets.keys():
        if k.lower() == ident:
            return k
            
    # Check by contract addresses or symbol name
    for k, m in markets.items():
        if m.get("marketAddress", "").lower() == ident:
            return k
        if m.get("ptAddress", "").lower() == ident:
            return k
        if m.get("ytAddress", "").lower() == ident:
            return k
        if m.get("symbol", "").lower() == ident:
            return k
            
    return None


def get_market_metadata(market_identifier: str) -> Optional[Dict[str, Any]]:
    """Returns metadata for a given market symbol or address."""
    key = normalize_market_key(market_identifier)
    if not key:
        return None
    cfg = load_market_config()
    return cfg.get("markets", {}).get(key)


# -----------------------------------------------------------------------------
# CONSTRAINT SAFETY VALIDATION ENGINE (BOROS-STYLE)
# -----------------------------------------------------------------------------
def validate_order_safety(
    market_identifier: str,
    side: str,
    rate_apy: float,
    gas_units: Optional[int] = None,
    gas_cost_usd: Optional[float] = None,
    expected_reward_usd: Optional[float] = None,
    dte_days: Optional[float] = None
) -> Tuple[bool, str, List[str]]:
    """
    Validates order parameters against Boros-Pendle institutional safety invariants:
    1. Seth Klarman Floor (Min Short / PT Yield)
    2. Negative-Carry Ceiling (Max Long / YT Borrow Yield)
    3. Ajit Jain Maturity Cliff (< 7 DTE hazard)
    4. 10x Gas Ceiling (< 720,000 units, < $0.22 USD)
    5. Minimum 5x Reward-to-Gas Ratio

    Returns:
      (is_safe: bool, summary_reason: str, violations: List[str])
    """
    key = normalize_market_key(market_identifier)
    if not key:
        return False, f"Unknown market identifier: {market_identifier}", ["UNKNOWN_MARKET"]

    violations: List[str] = []
    side_clean = side.upper().strip()

    min_shorts = get_min_short_rates()
    max_longs = get_max_long_rates()
    gas_cfg = get_gas_guardrails()

    # 1. Seth Klarman Floor Invariant (PT / Short)
    if side_clean in ("SHORT", "SELL_YT", "BUY_PT", "PT"):
        min_floor = min_shorts.get(key, min_shorts.get(key.upper(), 8.00))
        if rate_apy < min_floor:
            violations.append(
                f"KLARMAN_FLOOR_VIOLATION: Order APY {rate_apy:.2f}% is below hurdle floor {min_floor:.2f}%."
            )

    # 2. Negative-Carry Ceiling Invariant (YT / Long)
    if side_clean in ("LONG", "BUY_YT", "SELL_PT", "YT"):
        max_ceil = max_longs.get(key, max_longs.get(key.upper(), 15.00))
        if rate_apy > max_ceil:
            violations.append(
                f"NEGATIVE_CARRY_CEILING_VIOLATION: Long APY {rate_apy:.2f}% exceeds ceiling {max_ceil:.2f}%."
            )

    # 3. Ajit Jain Maturity Cliff
    if dte_days is not None:
        cliff_threshold = gas_cfg.get("min_dte_cliff_days", DEFAULT_MIN_DTE_CLIFF_DAYS)
        if dte_days < cliff_threshold:
            violations.append(
                f"MATURITY_CLIFF_HAZARD: Market is {dte_days:.1f} days from expiry (< {cliff_threshold}d cliff). "
                f"Theta decay risk is extreme."
            )

    # 4. Gas Ceiling (Strict 10x Limit)
    max_allowed_units = gas_cfg.get("max_gas_units", 720000)
    max_allowed_usd = gas_cfg.get("max_gas_cost_usd", 0.22)

    if gas_units is not None and gas_units > max_allowed_units:
        violations.append(
            f"GAS_CEILING_BREACH: Gas units ({gas_units:,}) exceeds 10x ceiling ({max_allowed_units:,})."
        )
    if gas_cost_usd is not None and gas_cost_usd > max_allowed_usd:
        violations.append(
            f"GAS_COST_BREACH: Gas cost (${gas_cost_usd:.4f} USD) exceeds 10x ceiling (${max_allowed_usd:.2f} USD)."
        )

    # 5. Economic Breakeven Ratio (Minimum 5.0x Reward to Gas)
    min_ratio = gas_cfg.get("min_reward_to_gas_ratio", 5.0)
    if gas_cost_usd is not None and expected_reward_usd is not None and gas_cost_usd > 0:
        ratio = expected_reward_usd / gas_cost_usd
        if ratio < min_ratio:
            violations.append(
                f"GAS_UNECONOMIC: Expected reward (${expected_reward_usd:.4f}) / gas cost (${gas_cost_usd:.4f}) "
                f"is {ratio:.2f}x (< {min_ratio:.1f}x hurdle)."
            )

    if violations:
        return False, f"Rejected by {len(violations)} safety constraint(s)", violations

    return True, "All Seth Klarman, Ajit Jain, and Gas Governor safety constraints passed.", []


# Runtime exports initialized from config
SUPPORTED_MARKETS = get_supported_markets()
MIN_SHORT_RATES = get_min_short_rates()
MAX_LONG_RATES = get_max_long_rates()
