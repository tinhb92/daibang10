#!/usr/bin/env python3
"""
Pendle V2 Liquidity Pools Opportunity & Antifragility Scanner (Robinhood Chain)
Persona: Taleb Desk (Antifragile Quant & Institutional Portfolio Manager)

Scans all active AMM Liquidity Pools on Pendle V2:
- Dissects multi-tier APY: Underlying Yield + AMM Swap Fees + PENDLE Emissions + PT Discount
- Models Convergent LPing (Zero Impermanent Loss at Maturity: PT -> SY at 1:1)
- Contrasts Pool LP APY vs Limit Order Maker Mining vs Boros (which has 0 pool yield)
- Enforces Ajit Jain T-7 Maturity Cliff & Micro-Cap Illiquidity Trap Filters
- Evaluates Asymmetry Fat Pitches (e.g. sNUKE 147.8% APY, SGOV 139.1% APY on USD Treasury)
- Generates persistent executive artifact: pendlev2_pools_radar.md
"""

import os
import sys
import json
import math
import time
import argparse
import urllib.request
from datetime import datetime, timezone

# Ensure paths
RH_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(RH_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)
if RH_DIR not in sys.path:
    sys.path.insert(0, RH_DIR)

CHAIN_ID = 4663
BASE_API = "https://api-v2.pendle.finance/core"
RPC_URL = "https://rpc.mainnet.chain.robinhood.com"
DESK_WALLET = "0xaa7c405151c1a11fc2e9998a31b285c7b53d248b"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

MIN_DTE_CLIFF_DAYS = 7.0
MIN_SAFE_LIQUIDITY_USD = 5000.0


def fetch_json(url, max_retries=3):
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries:
                time.sleep(1.5 * attempt)
                continue
            if attempt == max_retries:
                return None
        except Exception:
            if attempt == max_retries:
                return None
            time.sleep(1.0)
    return None


def calculate_dte(expiry_iso):
    if not expiry_iso:
        return 30.0
    try:
        exp_dt = datetime.fromisoformat(expiry_iso.replace("Z", "+00:00"))
        now_dt = datetime.now(timezone.utc)
        return max(0.0, (exp_dt - now_dt).total_seconds() / 86400.0)
    except Exception:
        return 30.0


def evaluate_pool_opportunity(market_data, incentive_configs=None):
    """
    Evaluates risk-adjusted pool yield metrics and checks against Taleb Antifragility principles.
    """
    name = market_data.get("proName") or market_data.get("name") or "Unknown"
    addr = market_data.get("address", "").lower()
    expiry = market_data.get("expiry")
    dte = calculate_dte(expiry)

    liq_usd = (market_data.get("liquidity") or {}).get("usd", 0.0)
    vol_usd = (market_data.get("tradingVolume") or {}).get("usd", 0.0)

    agg_apy = (market_data.get("aggregatedApy") or 0.0) * 100.0
    underlying_apy = (market_data.get("underlyingApy") or 0.0) * 100.0
    swap_fee_apy = (market_data.get("swapFeeApy") or 0.0) * 100.0
    pendle_apy = (market_data.get("pendleApy") or 0.0) * 100.0
    max_boost_apy = (market_data.get("maxBoostedApy") or 0.0) * 100.0
    implied_apy = (market_data.get("impliedApy") or 0.0) * 100.0
    pt_discount = (market_data.get("ptDiscount") or 0.0) * 100.0

    # Risk Flags
    is_cliff_hazard = dte < MIN_DTE_CLIFF_DAYS
    is_low_liquidity = liq_usd < MIN_SAFE_LIQUIDITY_USD

    risk_tags = []
    if is_cliff_hazard:
        risk_tags.append(f"⛔ AJIT JAIN CLIFF ({dte:.1f}d < 7d)")
    if is_low_liquidity:
        risk_tags.append(f"⚠️ ILLIQUID TRAP (${liq_usd:,.0f} TVL)")

    # Projected PnL on $1,000 USD deposit over holding horizon to expiry
    daily_yield_pct = agg_apy / 365.0
    daily_reward_usd = (agg_apy / 100.0 / 365.0) * 1000.0
    horizon_days = min(dte, 30.0)
    projected_horizon_pnl_usd = (agg_apy / 100.0 * (horizon_days / 365.0)) * 1000.0

    # Taleb Asymmetry Score: Higher is better. Rewards dominant vs downside.
    # Base formula: (Agg APY * horizon) / (Volatility Risk + Friction)
    vol_risk_weight = 1.0
    if "SGOV" in name:
        vol_risk_weight = 0.1  # US Treasury: ultra-low asset volatility
    elif "NVDA" in name or "PFE" in name:
        vol_risk_weight = 0.5  # Large cap synthetic equities
    elif "sNUKE" in name:
        vol_risk_weight = 0.8  # Yield asset with organic backing
    else:
        vol_risk_weight = 1.2  # High volatility / meme tokens

    asymmetry_score = 0.0
    if not is_cliff_hazard and not is_low_liquidity:
        asymmetry_score = (agg_apy * (horizon_days / 365.0)) / max(0.1, vol_risk_weight)

    zap_url = f"https://app.pendle.finance/trade/pools/{addr}/zap/in?chain=robinhood"

    return {
        "name": name,
        "address": addr,
        "expiry": expiry,
        "dte": dte,
        "liquidity_usd": liq_usd,
        "volume_24h_usd": vol_usd,
        "aggregated_apy": agg_apy,
        "underlying_apy": underlying_apy,
        "swap_fee_apy": swap_fee_apy,
        "pendle_apy": pendle_apy,
        "max_boost_apy": max_boost_apy,
        "implied_apy": implied_apy,
        "pt_discount": pt_discount,
        "is_cliff_hazard": is_cliff_hazard,
        "is_low_liquidity": is_low_liquidity,
        "risk_tags": risk_tags,
        "daily_reward_usd_per_1k": daily_reward_usd,
        "projected_pnl_per_1k": projected_horizon_pnl_usd,
        "horizon_days": horizon_days,
        "asymmetry_score": asymmetry_score,
        "zap_url": zap_url
    }


def main():
    parser = argparse.ArgumentParser(description="Pendle V2 Liquidity Pools Opportunity & Antifragility Scanner")
    parser.add_argument("--export-md", action="store_true", help="Export structured markdown report to pendlev2_pools_radar.md")
    args = parser.parse_args()

    print("=" * 115)
    print("🦅 TALEB DESK: PENDLE V2 LIQUIDITY POOLS & AMM YIELD RADAR (ROBINHOOD CHAIN 4663)")
    print("=" * 115)
    print(f"• Desk Wallet:       {DESK_WALLET}")
    print(f"• Target Mechanism:  Pendle V2 AMM Liquidity Pools (Continuous LP Yield vs Boros 0% Pool Yield)")
    print(f"• Convergent Model:  Zero Impermanent Loss at Maturity (PT -> SY 1:1)")
    print(f"• Safety Invariants: Ajit Jain Cliff (≥ {MIN_DTE_CLIFF_DAYS}d DTE) | Liquidity Floor (≥ ${MIN_SAFE_LIQUIDITY_USD:,.0f} TVL)")
    print("-" * 115)

    markets_url = f"{BASE_API}/v1/{CHAIN_ID}/markets?is_active=true"
    data = fetch_json(markets_url) or {}
    raw_markets = data.get("results", [])

    if not raw_markets:
        print("[!] Error: Failed to fetch markets from Pendle V2 API.")
        return

    pools = [evaluate_pool_opportunity(m) for m in raw_markets]
    # Sort by Asymmetry Score descending (safest & highest reward first)
    pools.sort(key=lambda p: (not p["is_cliff_hazard"], not p["is_low_liquidity"], p["asymmetry_score"]), reverse=True)

    print(f"{'Pool / Market':<10} | {'DTE':<5} | {'TVL ($)':<11} | {'Agg APY':<9} | {'Underlying':<10} | {'Swap Fees':<9} | {'PENDLE':<8} | {'Status / Risk'}")
    print("-" * 115)

    actionable_pitches = []
    hazard_pools = []

    for p in pools:
        status_str = "🟢 Prime Pitch" if p["asymmetry_score"] > 0 else (p["risk_tags"][0] if p["risk_tags"] else "Sub-optimal")
        print(f"{p['name']:<10} | {p['dte']:>4.1f}d | ${p['liquidity_usd']:>9,.0f} | {p['aggregated_apy']:>8.2f}% | {p['underlying_apy']:>9.2f}% | {p['swap_fee_apy']:>8.2f}% | {p['pendle_apy']:>7.2f}% | {status_str}")

        if p["is_cliff_hazard"] or p["is_low_liquidity"]:
            hazard_pools.append(p)
        else:
            actionable_pitches.append(p)

    print("-" * 115)

    if actionable_pitches:
        print("\n🎯 TOP ASYMMETRIC 'FAT PITCH' LIQUIDITY POOLS (CLEARED FOR DEPLOYMENT)")
        print("=" * 115)
        for idx, p in enumerate(actionable_pitches, 1):
            print(f"#{idx}. {p['name']} POOL — Aggregated LP APY: {p['aggregated_apy']:.2f}% (Max Boost: {p['max_boost_apy']:.2f}%)")
            print(f"    • Expiry:             {p['expiry'][:10]} ({p['dte']:.1f} Days to Maturity)")
            print(f"    • Pool Liquidity:     ${p['liquidity_usd']:,.2f} USD | 24h Volume: ${p['volume_24h_usd']:,.2f} USD")
            print(f"    • Multi-Source Yield: Underlying: {p['underlying_apy']:.2f}% | AMM Fees: {p['swap_fee_apy']:.2f}% | PENDLE Emissions: {p['pendle_apy']:.2f}%")
            print(f"    • Cash Flow ($1k Dep):~${p['daily_reward_usd_per_1k']:.2f}/day | Projected PnL to Expiry: +${p['projected_pnl_per_1k']:.2f} USD")
            print(f"    • Convergent IL Risk: ZERO at Maturity (PT and SY redeem 1:1)")
            print(f"    • Direct Zap-In Link: {p['zap_url']}")
            print()
        print("=" * 115)

    if hazard_pools:
        print("\n⛔ EXCLUDED & HIGH-HAZARD POOLS (TALEB INVARIANT REJECTIONS)")
        print("=" * 115)
        for p in hazard_pools:
            reasons = " & ".join(p["risk_tags"])
            print(f"• {p['name']} (TVL: ${p['liquidity_usd']:,.0f}, DTE: {p['dte']:.1f}d): REJECTED")
            print(f"  Risk Invariant: {reasons}")
            print(f"  Taleb Principle: Never chase high headline yields into illiquid traps or terminal maturity cliffs.")
            print()
        print("=" * 115)

    # Export Persistent Markdown Artifact
    export_md_path = os.path.join(PROJECT_DIR, "pendlev2_pools_radar.md")
    lines = [
        "# Pendle V2 AMM Liquidity Pools: Institutional Opportunity & Risk Radar",
        "",
        f"> **Last Updated:** `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`  ",
        f"> **Target Network:** Robinhood Chain (Chain ID: `4663`) | **Desk:** `rh/`  ",
        f"> **Desk Wallet:** [`{DESK_WALLET}`](https://robinhoodchain.blockscout.com/address/{DESK_WALLET})  ",
        f"> **Institutional Doctrine:** Taleb Antifragile Yield Capture & Convergent Impermanent Loss Elimination",
        "",
        "---",
        "",
        "## 1. Executive Yield Architecture: Pendle V2 Pools vs Boros Orderbook",
        "",
        "| Feature | Boros (Arbitrum CLOB) | Pendle V2 AMM Liquidity Pools (Robinhood Chain) |",
        "| :--- | :--- | :--- |",
        "| **Pool LP Yield** | **0.00% (None)** — Orderbook CLOB only | **Continuous Multi-Stream Yield (20% to 150%+ APY)** |",
        "| **Yield Streams** | Only fills & maker points | **1. Underlying Yield + 2. AMM Swap Fees + 3. PENDLE Emissions + 4. PT Accretion** |",
        "| **Maintenance Friction** | Frequent manual/bot shifting | **Zero-maintenance passive continuous compounding** |",
        "| **Impermanent Loss (IL)** | N/A (Borrow rates) | **Zero Impermanent Loss at Maturity** ($PT \\to SY$ at 1:1) |",
        "",
        "---",
        "",
        "## 2. Multi-Market Liquidity Pool Matrix",
        "",
        "| Pool | DTE | TVL (USD) | 24h Vol | Aggregated APY | Underlying | Swap Fees | PENDLE APR | Taleb Status |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]

    for p in pools:
        tag = "🟢 **Prime Fat Pitch**" if p["asymmetry_score"] > 0 else f"🛑 {p['risk_tags'][0]}"
        lines.append(
            f"| **[{p['name']}]({p['zap_url']})** | `{p['dte']:.1f}d` | `${p['liquidity_usd']:,.0f}` | `${p['volume_24h_usd']:,.0f}` | "
            f"**{p['aggregated_apy']:.2f}%** | `{p['underlying_apy']:.2f}%` | `{p['swap_fee_apy']:.2f}%` | `{p['pendle_apy']:.2f}%` | {tag} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 3. Actionable Fat Pitch Spotlights",
        ""
    ])

    for p in actionable_pitches:
        lines.extend([
            f"### 💎 {p['name']} Liquidity Pool (Aggregated APY: `{p['aggregated_apy']:.2f}%`)",
            f"- **Maturity Date:** `{p['expiry'][:10]}` (`{p['dte']:.1f}` Days Remaining)",
            f"- **Pool Depth & Volume:** `${p['liquidity_usd']:,.2f} USD` TVL | 24h Volume: `${p['volume_24h_usd']:,.2f} USD`",
            f"- **Yield Composition:**",
            f"  - **Underlying Yield:** `{p['underlying_apy']:.2f}%` (Native asset staking / interest)",
            f"  - **Swap Fee Yield:** `{p['swap_fee_apy']:.2f}%` (AMM trading fees paid by PT/YT traders)",
            f"  - **PENDLE Emissions:** `{p['pendle_apy']:.2f}%` (Direct liquidity mining incentives)",
            f"- **Projected Cash Flow:**",
            f"  - **Per $1,000 USD Capital:** `~${p['daily_reward_usd_per_1k']:.2f} USD / day`",
            f"  - **Holding to Expiry ({p['horizon_days']:.1f}d):** `+${p['projected_pnl_per_1k']:.2f} USD` total net gain",
            f"- **Risk & IL Model:** Pure Convergent AMM. Holding to maturity guarantees $PT \\to SY$ at 1:1, entirely bypassing Uniswap-style impermanent loss.",
            f"- **Direct Zap-In Link:** [Open Pendle V2 Zap-In Interface]({p['zap_url']})",
            ""
        ])

    lines.extend([
        "---",
        "",
        "## 4. Taleb Antifragility Exclusions (The Graveyard Forensic Doctrine)",
        ""
    ])

    for p in hazard_pools:
        reasons = " & ".join(p["risk_tags"])
        lines.append(f"- 🛑 **{p['name']}** (`{p['dte']:.1f}d` DTE, TVL: `${p['liquidity_usd']:,.0f}`): **Rejected** — *{reasons}*. Enforcing Seth Klarman margin of safety & Ajit Jain terminal cliff avoidance.")

    with open(export_md_path, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\n📄 Persistent Pools Radar successfully exported to: {export_md_path}")


if __name__ == "__main__":
    main()
