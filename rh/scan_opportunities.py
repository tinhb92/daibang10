#!/usr/bin/env python3
"""
Desk Opportunity & Gas Hurdle Scanner: Robinhood Chain (Chain ID: 4663)
Persona: Taleb Desk (Antifragile Quant & Microstructure Forensics)

Scans all active Robinhood Chain Pendle V2 markets:
- Audits active incentive bands vs current implied APYs
- Checks our wallet's resting orders (In-Band vs Out-of-Band drift)
- Detects competitor whale vacuums (e.g. 0x743d7b drift leaving $0 maker competition)
- Computes exact minimum capital needed to clear the 5.0x gas hurdle across 24h, 3d, and 7d horizons
- Generates recommended copy-paste execution commands
"""

import os
import sys
import json
import math
import argparse
import urllib.request
from datetime import datetime, timezone

try:
    from web3 import Web3
except ImportError:
    print("\n[!] Error: 'web3' module not found. Please activate conda environment: 'conda activate jlab'\n")
    sys.exit(1)

RH_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(RH_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)
if RH_DIR not in sys.path:
    sys.path.insert(0, RH_DIR)

from gas_governor import (
    get_gas_metrics,
    evaluate_shift_economic_viability,
    AVG_CANCEL_GAS_UNITS,
    MIN_REWARD_TO_GAS_RATIO
)
from config.market_params import (
    get_supported_markets,
    load_market_config,
    get_market_metadata,
    get_min_short_rates,
    get_max_long_rates
)

CHAIN_ID = 4663
RPC_URL = "https://rpc.mainnet.chain.robinhood.com"
BASE_API = "https://api-v2.pendle.finance/core"
OUR_WALLET = "0xaa7c405151c1a11fc2e9998a31b285c7b53d248b"
WHALE_WALLET = "0x743d7b30661d65b41960bf6b5d1bb93cf7972a73"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

def main():
    parser = argparse.ArgumentParser(description="Pendle V2 Market Opportunity & Gas Hurdle Scanner")
    parser.add_argument("--horizon-days", type=float, default=7.0, help="Holding horizon in days (default: 7.0)")
    args = parser.parse_args()

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    gas_metrics = get_gas_metrics(w3, OUR_WALLET)
    cost_cancel_usd = gas_metrics["cost_per_cancel_usd"]

    print("=" * 105)
    print("🦅 TALEB DESK: ROBINHOOD CHAIN OPPORTUNITY & GAS HURDLE SCANNER")
    print("=" * 105)
    print(f"• Desk Wallet:       {OUR_WALLET}")
    print(f"• Native Gas Runway: {gas_metrics['eth_balance']:.6f} ETH (${gas_metrics['eth_balance_usd']:.2f} USD) | {gas_metrics['runway_cancels']:,} txs runway")
    print(f"• Cost per Cancel:   ${cost_cancel_usd:.4f} USD | Hurdle Ratio: ≥ {MIN_REWARD_TO_GAS_RATIO:.1f}x")
    print(f"• Evaluation Horizon:{args.horizon_days:.1f} Days")
    print("-" * 105)

    # 1. Fetch incentive configs
    configs_data = fetch_json(f"{BASE_API}/v1/limit-orders/incentive/configs") or {}
    configs = configs_data.get("configs", [])
    band_map = {}
    for c in configs:
        if c.get("chainId") == CHAIN_ID:
            m_addr = c.get("marketAddress", "").lower()
            band_map[m_addr] = {
                "impliedApy": (c.get("impliedApy") or 0.0) * 100.0,
                "minApy": (c.get("minApy") or 0.0) * 100.0,
                "maxApy": (c.get("maxApy") or 0.0) * 100.0,
                "buyPtApr": (c.get("estimatedApr", {}).get("buyPtApr") or 0.0) * 100.0,
                "sellYtApr": (c.get("estimatedApr", {}).get("sellYtApr") or 0.0) * 100.0,
            }

    # 2. Fetch our active orders
    our_orders_data = fetch_json(f"{BASE_API}/v2/limit-orders?chainId={CHAIN_ID}&maker={OUR_WALLET}") or {}
    our_orders = [o for o in our_orders_data.get("results", []) if o.get("isActive", False)]
    our_order_map = {}
    for o in our_orders:
        yt = o.get("yt", "").lower()
        if yt not in our_order_map:
            our_order_map[yt] = []
        raw_ln = int(o.get("lnImpliedRate", 0)) / 1e18
        apy = (math.exp(raw_ln) - 1.0) * 100.0
        cur_making = int(o.get("currentMakingAmount", 0)) / 1e18
        our_order_map[yt].append({"id": o.get("id"), "apy": apy, "size": cur_making})

    # 3. Fetch whale active orders
    whale_data = fetch_json(f"{BASE_API}/v2/limit-orders?chainId={CHAIN_ID}&maker={WHALE_WALLET}") or {}
    whale_orders = [o for o in whale_data.get("results", []) if o.get("isActive", False)]
    whale_order_map = {}
    for o in whale_orders:
        yt = o.get("yt", "").lower()
        if yt not in whale_order_map:
            whale_order_map[yt] = []
        raw_ln = int(o.get("lnImpliedRate", 0)) / 1e18
        apy = (math.exp(raw_ln) - 1.0) * 100.0
        vol_usd = o.get("orderState", {}).get("notionalVolumeUSD", 0.0)
        whale_order_map[yt].append({"id": o.get("id"), "apy": apy, "vol_usd": vol_usd})

    # 4. Analyze each supported market
    supported = get_supported_markets()
    all_cfg = load_market_config().get("markets", {})
    min_shorts = get_min_short_rates()

    print(f"{'Market':<8} | {'Implied':<8} | {'Incentive Band':<17} | {'BuyPT APR':<9} | {'Min $ (7d 5x)':<14} | {'Our Orders':<16} | {'Whale Status'}")
    print("-" * 105)

    recommendations = []

    for m in supported:
        m_info = all_cfg.get(m, {})
        m_addr = m_info.get("marketAddress", "").lower()
        yt_addr = m_info.get("ytAddress", "").lower()
        b_info = band_map.get(m_addr, {})
        imp_apy = b_info.get("impliedApy", 0.0)
        min_apy = b_info.get("minApy", 0.0)
        max_apy = b_info.get("maxApy", 0.0)
        buy_pt_apr = b_info.get("buyPtApr", 100.0)

        # Min capital calculation for 5x hurdle
        inc_apr_dec = buy_pt_apr / 100.0
        # 5x hurdle over horizon: size * inc_apr_dec * (horizon_hours / 8760) >= cost * 5.0
        horizon_hours = args.horizon_days * 24.0
        min_usd_horizon = (cost_cancel_usd * MIN_REWARD_TO_GAS_RATIO) / (inc_apr_dec * (horizon_hours / 8760.0)) if inc_apr_dec > 0 else 0.0
        min_usd_24h = (cost_cancel_usd * MIN_REWARD_TO_GAS_RATIO) / (inc_apr_dec * (24.0 / 8760.0)) if inc_apr_dec > 0 else 0.0

        # Check our orders
        our_m_orders = our_order_map.get(yt_addr, [])
        our_status = "None"
        if our_m_orders:
            in_range = any(min_apy <= o["apy"] <= max_apy for o in our_m_orders)
            our_status = f"{len(our_m_orders)} orders (✅ In-Band)" if in_range else f"{len(our_m_orders)} orders (❌ Drifted)"

        # Check whale orders
        whale_m_orders = whale_order_map.get(yt_addr, [])
        whale_status = "No Whale"
        whale_vacuum = False
        if whale_m_orders:
            in_range_whale = any(min_apy <= o["apy"] <= max_apy for o in whale_m_orders)
            if in_range_whale:
                tot_vol = sum(o["vol_usd"] for o in whale_m_orders)
                whale_status = f"In-Band (${tot_vol:,.0f})"
            else:
                tot_vol = sum(o["vol_usd"] for o in whale_m_orders)
                drift_rates = "/".join(f"{o['apy']:.1f}%" for o in whale_m_orders[:2])
                whale_status = f"🚨 DRIFT ({drift_rates})"
                whale_vacuum = True

        band_str = f"[{min_apy:.2f}%, {max_apy:.2f}%]"
        print(f"{m:<8} | {imp_apy:>6.2f}% | {band_str:<17} | {buy_pt_apr:>7.1f}% | ${min_usd_horizon:>11.2f} USD | {our_status:<16} | {whale_status}")

        # Recommended order target
        target_rec = round(min(max_apy - 0.02, max(min_apy + 0.02, imp_apy)), 2)
        if our_status.startswith("None") or "Drifted" in our_status:
            recommendations.append({
                "market": m,
                "target_apy": target_rec,
                "min_usd": min_usd_horizon,
                "whale_vacuum": whale_vacuum,
                "band": band_str,
                "apr": buy_pt_apr
            })

    print("-" * 105)

    if recommendations:
        print("\n🎯 ACTIONABLE DESK RECOMMENDATIONS (ORDER SHIFTS & DRY-RUN COMMANDS)")
        print("=" * 105)
        for r in recommendations:
            vac_flag = " [🚨 WHALE VACUUM: 0 Competing Depth!]" if r["whale_vacuum"] else ""
            print(f"• {r['market']}{vac_flag}:")
            print(f"  Target APY:    {r['target_apy']:.2f}% (Inside {r['band']} earning {r['apr']:.1f}% BuyPT APR)")
            print(f"  Min Capital:   ${r['min_usd']:.2f} USD (guarantees ≥ 5.0x gas hurdle over {args.horizon_days:.0f} days)")
            print(f"  Dry-Run Shift: python rh/shift_order.py --market {r['market']} --target-apy {r['target_apy']:.2f} --horizon-days {args.horizon_days:.0f}")
            print()
    print("=" * 105)

if __name__ == "__main__":
    main()
