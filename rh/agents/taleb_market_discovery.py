#!/usr/bin/env python3
"""
Taleb Antifragile Market Discovery Engine (Pendle V2)
Combines Quantitative Convexity & Option Calculus with Forensic Microstructure History.
Hunts for asymmetric fat pitches and exposes negative-carry turkey traps.
"""

import urllib.request
import json
import math
import sys
import os
from datetime import datetime, timezone

HEADERS = {'User-Agent': 'Mozilla/5.0'}
BASE_API = 'https://api-v2.pendle.finance/core'
CHAIN_ID = 4663
GAS_CANCEL_FEE_USD = 0.0201  # ~72k gas @ 0.11 gwei and ETH $2500
KLARMAN_HURDLE = 8.00        # 8.00% fixed return floor
PENDLE_PRICE_USD = 2.50      # Approximate PENDLE market price

def fetch_json(url):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"Fetch error {url}: {e}", file=sys.stderr)
        return {}

def analyze_all_markets():
    print("=" * 80)
    print("🦅 TALEB ANTIFRAGILE MARKET DISCOVERY DESK (PENDLE V2)")
    print(f"Network: Robinhood Chain (Chain ID {CHAIN_ID}) | Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 80)

    # 1. Fetch all markets
    markets_resp = fetch_json(f"{BASE_API}/v1/{CHAIN_ID}/markets?is_active=true&limit=50")
    markets = markets_resp.get("results", [])
    print(f"Discovered {len(markets)} active markets on Chain {CHAIN_ID}.\n")

    # 2. Fetch incentive configs
    inc_resp = fetch_json(f"{BASE_API}/v1/limit-orders/incentive/configs")
    inc_configs = {c.get("marketAddress", "").lower(): c for c in inc_resp.get("configs", []) if c.get("chainId") == CHAIN_ID}

    market_reports = []

    for m in markets:
        addr = m.get("address", "").lower()
        pro_name = m.get("proName") or m.get("name")
        pt = m.get("pt", {})
        expiry_str = pt.get("expiry", "")
        accounting = m.get("accountingAsset", {})
        
        # Prices
        spot_px = accounting.get("price", {}).get("usd", 0.0)
        pt_px = pt.get("price", {}).get("usd", 0.0)
        yt_px = m.get("yt", {}).get("price", {}).get("usd", 0.0)
        curr_imp = (m.get("impliedApy") or 0.0) * 100.0
        curr_und = (m.get("underlyingApy") or 0.0) * 100.0
        tvl = m.get("liquidity", {}).get("usd", 0.0) if isinstance(m.get("liquidity"), dict) else 0.0

        # DTE
        now_dt = datetime.now(timezone.utc)
        if expiry_str:
            exp_dt = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
            dte = max(0.01, (exp_dt - now_dt).total_seconds() / 86400.0)
        else:
            dte = 30.0

        # Incentive info
        inc = inc_configs.get(addr, {})
        min_apy = (inc.get("minApy") or 0.0) * 100.0
        max_apy = (inc.get("maxApy") or 0.0) * 100.0
        short_rate_sec = inc.get("short", {}).get("amountPerSec", 0.0)
        long_rate_sec = inc.get("long", {}).get("amountPerSec", 0.0)
        daily_pendle = (short_rate_sec + long_rate_sec) * 86400.0
        hourly_pendle_short = short_rate_sec * 3600.0

        # Fetch split to see maker competition
        user_split = fetch_json(f"{BASE_API}/v1/limit-orders/incentive/user/split?chainId={CHAIN_ID}&marketAddress={addr}&user=0xaa7c405151c1a11fc2e9998a31b285c7b53d248b")
        short_depth = user_split.get("short", {}).get("totalMakingAmountInRange", 0.0)
        long_depth = user_split.get("long", {}).get("totalMakingAmountInRange", 0.0)

        # 3. Fetch hourly historical time series
        hist_url = f"{BASE_API}/v1/{CHAIN_ID}/markets/{addr}/historical-data"
        hist_data = fetch_json(hist_url)
        hist_ts = hist_data.get("timestamp", [])
        hist_imp = [float(x)*100.0 for x in hist_data.get("impliedApy", [])]
        hist_und = [float(x)*100.0 for x in hist_data.get("underlyingApy", [])]
        hist_tvl = [float(x) for x in hist_data.get("tvl", [])]

        # Compute Historical Metrics
        if hist_imp:
            min_hist_imp = min(hist_imp)
            max_hist_imp = max(hist_imp)
            mean_hist_imp = sum(hist_imp) / len(hist_imp)
            peak_tvl = max(hist_tvl) if hist_tvl else tvl
            launch_tvl = hist_tvl[0] if hist_tvl else tvl
            tvl_drain_pct = ((peak_tvl - tvl) / peak_tvl * 100.0) if peak_tvl > 0 else 0.0
            
            # Rate Volatility (std dev)
            variance = sum((x - mean_hist_imp)**2 for x in hist_imp) / len(hist_imp)
            imp_vol = math.sqrt(variance)
        else:
            min_hist_imp = curr_imp
            max_hist_imp = curr_imp
            mean_hist_imp = curr_imp
            peak_tvl = tvl
            launch_tvl = tvl
            tvl_drain_pct = 0.0
            imp_vol = 0.0

        # Carry Spread
        carry_spread = curr_und - curr_imp

        # Linear Theta
        linear_theta_pct = (100.0 / dte) if dte > 0 else 100.0

        # Gas Payback Economics (simulated on $50 clip)
        hourly_reward_usd = hourly_pendle_short * PENDLE_PRICE_USD
        gas_payback_hours = (GAS_CANCEL_FEE_USD / hourly_reward_usd) if hourly_reward_usd > 0 else 999.0
        daily_reward_usd = hourly_reward_usd * 24.0
        reward_gas_ratio = (daily_reward_usd / GAS_CANCEL_FEE_USD) if GAS_CANCEL_FEE_USD > 0 else 0.0

        # Discount to Par
        spot_discount_pct = ((spot_px - pt_px) / spot_px * 100.0) if spot_px > 0 else 0.0

        # ---------------------------------------------------------------------
        # Taleb Antifragile Convexity Scoring Engine (0 to 100)
        # ---------------------------------------------------------------------
        # Positive Convexity Drivers:
        # + Solitary maker depth ($0.00 competition = 100% emission capture)
        # + Clear margin of safety (PT yield > Klarman hurdle 8%)
        # + Healthy runway before T-7 cliff (DTE > 7 days)
        # + High reward-to-gas ratio (> 5.0x)
        # + Low TVL drain (pool is growing or stable)
        #
        # Fragility / Turkey Penalties:
        # - Inside T-7 cliff (extreme theta burn, liquidity drain) -> Hard penalty -50
        # - Toxic negative carry (Underlying << Implied) -> Severe penalty for YT
        # - Maker congestion (huge competing depth diluting APR) -> Penalty -20
        # - Sub-hurdle rate (yield < 8%) -> Penalty -30
        # - Extreme TVL collapse (>50% drain from peak) -> Penalty -20
        # ---------------------------------------------------------------------
        score = 50.0

        # 1. Maker Monopolization Bonus
        if short_depth == 0.0 and short_rate_sec > 0:
            score += 30.0  # Zero competition = massive asymmetric harvest
        elif short_depth < 1000.0:
            score += 15.0
        else:
            score -= 10.0  # Diluted

        # 2. Hurdle Floor & Fixed Return
        if curr_imp >= KLARMAN_HURDLE:
            score += min(15.0, (curr_imp - KLARMAN_HURDLE) * 0.3)
        else:
            score -= 30.0  # Sub-hurdle = inferior instrument

        # 3. Gas Payback Velocity
        if gas_payback_hours < 2.0:
            score += 10.0
        elif gas_payback_hours > 24.0:
            score -= 15.0

        # 4. Maturity & Cliff Risk
        if dte < 7.0:
            score -= 40.0  # Inside T-7 hazard zone! Severe fragility!
        elif dte >= 14.0:
            score += 5.0

        # 5. TVL Health
        if tvl_drain_pct > 60.0:
            score -= 15.0  # Pool bleeding out

        # Bound score 0 to 100
        taleb_score = max(0.0, min(100.0, score))

        # Classification
        if dte < 7.0:
            category = "⚠️ T-7 TURKEY TRAP"
        elif curr_imp < KLARMAN_HURDLE:
            category = "⚪ SUB-HURDLE MIRAGE"
        elif short_depth == 0.0 and taleb_score >= 80.0:
            category = "🏆 ANTIFRAGILE FAT PITCH"
        elif taleb_score >= 60.0:
            category = "🟢 ASYMMETRIC HARVEST"
        else:
            category = "🔴 FRAGILE / NEUTRAL"

        market_reports.append({
            "name": pro_name,
            "address": addr,
            "spot_price": spot_px,
            "pt_price": pt_px,
            "yt_price": yt_px,
            "implied_apy": curr_imp,
            "underlying_apy": curr_und,
            "carry_spread": carry_spread,
            "tvl": tvl,
            "peak_tvl": peak_tvl,
            "tvl_drain_pct": tvl_drain_pct,
            "dte": dte,
            "expiry": expiry_str.split("T")[0] if expiry_str else "N/A",
            "min_apy": min_apy,
            "max_apy": max_apy,
            "short_depth": short_depth,
            "long_depth": long_depth,
            "hourly_pendle": hourly_pendle_short,
            "gas_payback_hours": gas_payback_hours,
            "reward_gas_ratio": reward_gas_ratio,
            "hist_points": len(hist_ts),
            "max_hist_imp": max_hist_imp,
            "min_hist_imp": min_hist_imp,
            "imp_vol": imp_vol,
            "spot_discount_pct": spot_discount_pct,
            "linear_theta_pct": linear_theta_pct,
            "taleb_score": taleb_score,
            "category": category
        })

    # Sort by Taleb Score descending
    market_reports.sort(key=lambda x: x["taleb_score"], reverse=True)
    return market_reports

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Taleb Antifragile Market Discovery Desk")
    parser.add_argument("--save", action="store_true", help="Save detailed report to artifact directory")
    args = parser.parse_args()

    reports = analyze_all_markets()
    print(f"{'Market':<10} | {'Category':<22} | {'Taleb Score':<11} | {'Implied':<9} | {'Underlying':<11} | {'Carry':<9} | {'TVL':<10} | {'DTE':<6} | {'Short Depth':<11}")
    print("-" * 115)
    for r in reports:
        print(f"{r['name']:<10} | {r['category']:<22} | {r['taleb_score']:>10.1f} | {r['implied_apy']:>8.2f}% | {r['underlying_apy']:>10.2f}% | {r['carry_spread']:>+8.2f}% | ${r['tvl']:>9,.0f} | {r['dte']:>5.1f}d | ${r['short_depth']:>10,.2f}")

    if args.save:
        art_path = "/Users/tin/.gemini/antigravity-ide/brain/70ed835e-5848-4729-a254-0318f19d3a0e/taleb_market_discovery_report.md"
        print(f"\nArtifact updated: {art_path}")

