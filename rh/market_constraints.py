"""
Pendle V2 - Robinhood Desk Market Constraint Safety Engine
Boros-Style Quantitative Safety Constraint Framework.

Calculates mathematically grounded safety bounds:
- Seth Klarman Margin of Safety Hurdle Floor (Min Short / PT Rate)
- Negative-Carry Ceiling (Max Long / YT Rate)
- Ajit Jain Maturity Cliff (< 7 DTE Time Decay Guard)
- Incentive Buffer Hysteresis
- Gas Economics (10x Ceiling & 5x Reward-to-Gas Ratio)

Usage:
  python rh/market_constraints.py --suggest NVDA
  python rh/market_constraints.py --suggest sNET
  python rh/market_constraints.py --suggest sNUKE
  python rh/market_constraints.py --suggest PFE
  python rh/market_constraints.py --all
  python rh/market_constraints.py --update
"""

import os
import sys
import math
import json
import argparse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Add parent directory to path
RH_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(RH_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)
if RH_DIR not in sys.path:
    sys.path.insert(0, RH_DIR)

from rh.config.market_params import (
    load_market_config,
    get_supported_markets,
    get_min_short_rates,
    get_max_long_rates,
    get_market_metadata,
    normalize_market_key,
    get_gas_guardrails,
    MARKETS_CONFIG_FILE
)
from gas_governor import MAX_ALLOWED_GAS_UNITS, MAX_ALLOWED_GAS_COST_USD, MIN_REWARD_TO_GAS_RATIO

CHAIN_ID = 4663
BASE_API = "https://api-v2.pendle.finance/core"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

def fetch_json(url: str) -> Any:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode("utf-8"))

def calculate_dte(expiry_iso: str) -> float:
    try:
        exp_dt = datetime.fromisoformat(expiry_iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = exp_dt - now
        return max(0.0, diff.total_seconds() / 86400.0)
    except Exception:
        return 30.0

def suggest_market_constraints(market_identifier: str) -> Optional[Dict[str, Any]]:
    """
    Evaluates live market data and computes Boros-style safety invariants.
    Case-insensitive symbol and address resolution.
    """
    key = normalize_market_key(market_identifier)
    if not key:
        print(f"❌ Unknown market identifier: '{market_identifier}'")
        print(f"   Supported markets: {', '.join(get_supported_markets())}")
        return None

    meta = get_market_metadata(key)
    if not meta:
        print(f"❌ Missing metadata for {key}")
        return None

    m_addr = meta["marketAddress"].lower()

    # 1. Query live market state
    m_url = f"{BASE_API}/v1/{CHAIN_ID}/markets/{m_addr}"
    try:
        market = fetch_json(m_url)
    except Exception as e:
        print(f"❌ Error fetching market {m_addr}: {e}")
        return None

    implied_apy = (market.get("impliedApy") or 0.0) * 100.0
    underlying_apy = (market.get("underlyingApy") or 0.0) * 100.0
    spot_price = market.get("accountingAsset", {}).get("price", {}).get("usd", 0.0)
    pt_price = market.get("pt", {}).get("price", {}).get("usd", 0.0)
    yt_price = market.get("yt", {}).get("price", {}).get("usd", 0.0)
    
    liq_val = market.get("liquidity")
    liquidity_usd = liq_val.get("usd", 0.0) if isinstance(liq_val, dict) else 0.0
    dte = calculate_dte(meta["expiry"])

    # 2. Query incentive configuration
    min_apy, max_apy, reward_per_hr = 0.0, 0.0, 0.0
    try:
        configs = fetch_json(f"{BASE_API}/v1/limit-orders/incentive/configs").get("configs", [])
        cfg = next((c for c in configs if c.get("chainId") == CHAIN_ID and c.get("marketAddress", "").lower() == m_addr), {})
        min_apy = (cfg.get("minApy") or 0.0) * 100.0
        max_apy = (cfg.get("maxApy") or 0.0) * 100.0
        reward_per_hr = cfg.get("short", {}).get("amountPerSec", 0.0) * 3600.0
    except Exception as e:
        print(f"⚠️ Warning: could not query incentive config: {e}")

    # 3. Apply Quantitative Safety Formulations
    # A. Seth Klarman Floor (Min Short / PT Rate)
    # Never lock capital below hurdle floor or below incentive band min
    base_floor = meta.get("base_hurdle_floor", 8.00)
    suggested_min_floor = max(base_floor, round(min_apy, 2))

    # B. Negative-Carry Ceiling (Max Long Yield)
    # Avoid buying fixed borrow / YT at peak euphoric implied yield
    max_long_cap = meta.get("max_long_ceiling", 15.00)
    suggested_max_ceiling = min(max_long_cap, round(max_apy, 2)) if max_apy > 0 else max_long_cap

    # C. Target Resting Order APY (Optimal In-Band Position)
    edge_buffer_bps = meta.get("edge_buffer_bps", 20)
    buffer_pct = edge_buffer_bps / 100.0
    if min_apy > 0 and max_apy > 0:
        suggested_order_apy = round(min(max_apy - buffer_pct, max(min_apy + buffer_pct, implied_apy)), 2)
    else:
        suggested_order_apy = round(implied_apy, 2)

    # D. Ajit Jain Maturity Cliff (< 7 DTE Razor)
    min_dte_threshold = meta.get("min_dte_threshold", 7.0)
    is_maturity_cliff = dte < min_dte_threshold
    if is_maturity_cliff:
        maturity_status = f"⚠️ EXTREME HAZARD: DTE ({dte:.1f}d) < {min_dte_threshold}d cliff! Theta decay collapses YT to 0."
        maturity_action = "🚨 AJIT JAIN RAZOR: Do NOT open new positions. Avoid inventory holding across maturity cliff."
    else:
        maturity_status = f"✅ Healthy Runway: {dte:.1f} days to expiry (> {min_dte_threshold}d threshold)."
        maturity_action = "✅ Structural carry profile is stable."

    # E. Seth Klarman Margin of Safety Assessment
    if implied_apy < base_floor:
        klarman_status = f"⚠️ SUB-HURDLE WARNING: Market Implied APY ({implied_apy:.2f}%) < Hurdle ({base_floor:.2f}%). Unfavorable risk-adjusted yield."
    else:
        klarman_status = f"✅ Attractive Spread: Implied APY ({implied_apy:.2f}%) meets/exceeds base hurdle ({base_floor:.2f}%)."

    gas_cfg = get_gas_guardrails()

    constraints = {
        "market": key,
        "symbol": meta.get("symbol", key),
        "address": m_addr,
        "asset": meta.get("assetName", key),
        "spot_price": spot_price,
        "pt_price": pt_price,
        "yt_price": yt_price,
        "dte_days": dte,
        "implied_apy": implied_apy,
        "underlying_apy": underlying_apy,
        "liquidity_usd": liquidity_usd,
        "incentive_band": [min_apy, max_apy],
        "reward_pool_per_hr": reward_per_hr,
        "suggested_min_floor": suggested_min_floor,
        "suggested_max_ceiling": suggested_max_ceiling,
        "suggested_order_apy": suggested_order_apy,
        "edge_buffer_bps": edge_buffer_bps,
        "is_maturity_cliff": is_maturity_cliff,
        "maturity_status": maturity_status,
        "maturity_action": maturity_action,
        "klarman_status": klarman_status,
        "max_allowed_gas_units": gas_cfg.get("max_gas_units", MAX_ALLOWED_GAS_UNITS),
        "max_allowed_gas_cost_usd": gas_cfg.get("max_gas_cost_usd", MAX_ALLOWED_GAS_COST_USD),
        "min_reward_to_gas_ratio": gas_cfg.get("min_reward_to_gas_ratio", MIN_REWARD_TO_GAS_RATIO)
    }

    # Format Constraint Card Output (Identical to Boros Standard)
    print("\n" + "═" * 84)
    print(f"🛡️  BOROS-STYLE QUANTITATIVE SAFETY CONSTRAINTS: {key} (Robinhood Chain 4663)")
    print("═" * 84)
    print(f"   Asset & Spot : {meta.get('assetName', key)} | Spot: ${spot_price:.2f} (PT: ${pt_price:.2f}, YT: ${yt_price:.4f})")
    print(f"   Expiry & DTE : {meta['expiry'][:10]} | Days to Expiry: {dte:.1f} Days")
    print(f"   Market Rates : Implied APY: {implied_apy:.2f}% | Underlying Yield: {underlying_apy:.2f}% | Liq: ${liquidity_usd:,.0f}")
    print(f"   Incentives   : Band: [{min_apy:.2f}%, {max_apy:.2f}%] | Rewards: {reward_per_hr:.4f} PENDLE/hr")
    print("   " + "─" * 80)
    print(f"   🎯 Seth Klarman Floor (Min PT / Short): ≥ {suggested_min_floor:.2f}% APY")
    print(f"      └─ Invariant: Never lock capital in fixed PT below hurdle floor")
    print(f"      └─ Status: {klarman_status}")
    print(f"   🎯 Negative-Carry Ceiling (Max Long)  : ≤ {suggested_max_ceiling:.2f}% APY")
    print(f"      └─ Invariant: Avoid buying fixed borrow / YT at euphoric peaks")
    print(f"   🎯 Recommended In-Band Resting Rate   : {suggested_order_apy:.2f}% APY (Buffer: {edge_buffer_bps} bps)")
    print(f"   🚨 Ajit Jain Expiry Hazard Status     : {maturity_status}")
    print(f"      └─ Guidance: {maturity_action}")
    print(f"   ⛽ Robinhood Gas Governor Ceiling     : Hard Limit: $0.22 USD ({constraints['max_allowed_gas_units']:,} gas units)")
    print(f"      └─ Minimum Economic Hurdle Ratio   : ≥ {constraints['min_reward_to_gas_ratio']:.1f}x Reward-to-Gas")
    print("═" * 84 + "\n")

    return constraints

def update_markets_config():
    """Recalculates suggestions for all supported markets and persists into markets.json."""
    markets = get_supported_markets()
    cfg = load_market_config()

    min_shorts = cfg.get("min_short_rates", {})
    max_longs = cfg.get("max_long_rates", {})

    print(f"🔄 Updating safety constraints for {len(markets)} markets in {MARKETS_CONFIG_FILE}...")
    for m in markets:
        res = suggest_market_constraints(m)
        if res:
            min_shorts[m] = res["suggested_min_floor"]
            max_longs[m] = res["suggested_max_ceiling"]

    cfg["min_short_rates"] = min_shorts
    cfg["max_long_rates"] = max_longs

    with open(MARKETS_CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

    print(f"✅ Successfully updated {MARKETS_CONFIG_FILE}")

def main():
    parser = argparse.ArgumentParser(description="Pendle V2 Market Safety Constraints Engine (Robinhood Chain)")
    parser.add_argument("--suggest", type=str, help="Market symbol or key (e.g. NVDA, sNET, sNUKE, PFE, or 'all')")
    parser.add_argument("--all", action="store_true", help="Suggest constraints for all supported markets")
    parser.add_argument("--update", action="store_true", help="Recalculate and update rh/config/markets.json")
    args = parser.parse_args()

    if args.update:
        update_markets_config()
    elif args.all or (args.suggest and args.suggest.lower() == "all"):
        for m in get_supported_markets():
            suggest_market_constraints(m)
    elif args.suggest:
        suggest_market_constraints(args.suggest)
    else:
        for m in get_supported_markets():
            suggest_market_constraints(m)

if __name__ == "__main__":
    main()
