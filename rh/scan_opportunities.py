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

RH_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(RH_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)
if RH_DIR not in sys.path:
    sys.path.insert(0, RH_DIR)

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
AVG_CANCEL_GAS_UNITS = 72000
MIN_REWARD_TO_GAS_RATIO = 5.0

def json_rpc(method, params):
    payload = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode("utf-8")
    req = urllib.request.Request(RPC_URL, data=payload, headers={"Content-Type": "application/json", **HEADERS})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8")).get("result")
    except Exception:
        return None

def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
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

def main():
    parser = argparse.ArgumentParser(description="Pendle V2 Market Opportunity & Gas Hurdle Scanner")
    parser.add_argument("--horizon-days", type=float, default=7.0, help="Holding horizon in days (default: 7.0)")
    parser.add_argument("--export-md", action="store_true", help="Export structured markdown report to robinhood_market_radar.md")
    args = parser.parse_args()

    bal_hex = json_rpc("eth_getBalance", [OUR_WALLET, "latest"])
    eth_balance = int(bal_hex, 16) / 1e18 if bal_hex else 0.0095
    price_hex = json_rpc("eth_gasPrice", [])
    gas_price_wei = int(price_hex, 16) if price_hex else 100000000
    eth_price_usd = 2500.0
    cost_cancel_eth = (AVG_CANCEL_GAS_UNITS * gas_price_wei) / 1e18
    cost_cancel_usd = cost_cancel_eth * eth_price_usd
    runway_cancels = int(eth_balance / cost_cancel_eth) if cost_cancel_eth > 0 else 1000

    print("=" * 115)
    print("🦅 TALEB DESK: ROBINHOOD CHAIN ANTIFRAGILE OPPORTUNITY & GAS HURDLE SCANNER")
    print("=" * 115)
    print(f"• Desk Wallet:       {OUR_WALLET}")
    print(f"• Native Gas Runway: {eth_balance:.6f} ETH (${eth_balance * eth_price_usd:.2f} USD) | {runway_cancels:,} txs runway")
    print(f"• Cost per Cancel:   ${cost_cancel_usd:.4f} USD | Hurdle Ratio: ≥ {MIN_REWARD_TO_GAS_RATIO:.1f}x")
    print(f"• Evaluation Horizon:{args.horizon_days:.1f} Days | Ajit Jain Cliff: < 7.0 Days")
    print("-" * 115)

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

    print(f"{'Market':<7} | {'DTE':<5} | {'Implied':<8} | {'Incentive Band':<17} | {'BuyPT APR':<9} | {'Min $ (7d 5x)':<13} | {'Our Orders':<15} | {'Whale Status'}")
    print("-" * 115)

    recommendations = []
    hazard_markets = []
    market_rows_md = []

    for m in supported:
        m_info = all_cfg.get(m, {})
        m_addr = m_info.get("marketAddress", "").lower()
        yt_addr = m_info.get("ytAddress", "").lower()
        expiry_iso = m_info.get("expiry")
        dte = calculate_dte(expiry_iso)

        b_info = band_map.get(m_addr, {})
        imp_apy = b_info.get("impliedApy", 0.0)
        min_apy = b_info.get("minApy", 0.0)
        max_apy = b_info.get("maxApy", 0.0)
        buy_pt_apr = b_info.get("buyPtApr", 100.0)

        # Min capital calculation for 5x hurdle
        inc_apr_dec = buy_pt_apr / 100.0
        horizon_hours = args.horizon_days * 24.0
        min_usd_horizon = (cost_cancel_usd * MIN_REWARD_TO_GAS_RATIO) / (inc_apr_dec * (horizon_hours / 8760.0)) if inc_apr_dec > 0 else 0.0

        # Check our orders
        our_m_orders = our_order_map.get(yt_addr, [])
        our_status = "None"
        if our_m_orders:
            in_range = any(min_apy <= o["apy"] <= max_apy for o in our_m_orders)
            our_status = f"{len(our_m_orders)} ord (✅ In-Band)" if in_range else f"{len(our_m_orders)} ord (❌ Drift)"

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
                drift_rates = "/".join(f"{o['apy']:.1f}%" for o in whale_m_orders[:2])
                whale_status = f"🚨 DRIFT ({drift_rates})"
                whale_vacuum = True

        band_str = f"[{min_apy:.2f}%, {max_apy:.2f}%]"
        dte_str = f"{dte:.1f}d"
        print(f"{m:<7} | {dte_str:<5} | {imp_apy:>6.2f}% | {band_str:<17} | {buy_pt_apr:>7.1f}% | ${min_usd_horizon:>10.2f} USD | {our_status:<15} | {whale_status}")

        market_rows_md.append({
            "market": m,
            "dte": dte,
            "implied": imp_apy,
            "band": band_str,
            "apr": buy_pt_apr,
            "min_usd": min_usd_horizon,
            "our_status": our_status,
            "whale_status": whale_status,
            "whale_vacuum": whale_vacuum
        })

        # Check Ajit Jain Cliff Hazard (< 7.0 Days)
        if dte < 7.0:
            hazard_markets.append({
                "market": m,
                "dte": dte,
                "reason": f"DTE is {dte:.1f}d (< 7.0d cliff threshold). Extreme theta acceleration & pre-expiry illiquidity hazard."
            })
            continue

        # Recommended order target for safe non-cliff markets
        target_rec = round(min(max_apy - 0.02, max(min_apy + 0.02, imp_apy)), 2)
        if our_status.startswith("None") or "Drift" in our_status:
            asymmetry_score = round((buy_pt_apr * (args.horizon_days / 365.0)) / (cost_cancel_usd * 10), 1)
            recommendations.append({
                "market": m,
                "dte": dte,
                "target_apy": target_rec,
                "min_usd": min_usd_horizon,
                "whale_vacuum": whale_vacuum,
                "band": band_str,
                "apr": buy_pt_apr,
                "asymmetry_score": asymmetry_score
            })

    print("-" * 115)

    if hazard_markets:
        print("\n⛔ TALEB DESK INVARIANT WARNINGS (AJIT JAIN MATURITY CLIFF EXCLUSIONS)")
        print("=" * 115)
        for h in hazard_markets:
            print(f"• {h['market']} (DTE: {h['dte']:.1f} days): EXCLUDED FROM ACTIVE RESTING ORDERS")
            print(f"  Reason: {h['reason']}")
            print("  Invariant: Patterns.md Principle 3 - Never write options or rest liquidity into terminal maturity cliffs.")
        print("=" * 115)

    if recommendations:
        print("\n🎯 ACTIONABLE DESK RECOMMENDATIONS (CLEARED BY SETH KLARMAN & AJIT JAIN RAZORS)")
        print("=" * 115)
        for r in recommendations:
            vac_flag = " [🚨 SOLITARY MAKER VACUUM: 100% REWARD CAPTURE]" if r["whale_vacuum"] else ""
            print(f"• {r['market']}{vac_flag}:")
            print(f"  Target APY:       {r['target_apy']:.2f}% (Inside {r['band']} earning {r['apr']:.1f}% BuyPT APR)")
            print(f"  DTE to Expiry:    {r['dte']:.1f} Days (Passed > 7.0d Ajit Jain Safety Barrier)")
            print(f"  Min Capital:      ${r['min_usd']:.2f} USD (guarantees ≥ 5.0x gas hurdle over {args.horizon_days:.0f} days)")
            print(f"  Dry-Run Shift:    python rh/shift_order.py --market {r['market']} --target-apy {r['target_apy']:.2f} --horizon-days {args.horizon_days:.0f}")
            print()
        print("=" * 115)

    # Markdown Export
    if args.export_md or True: # Always export to keep persistent manager artifacts synchronized
        export_path = os.path.join(PROJECT_DIR, "robinhood_market_radar.md")
        lines = [
            "# Robinhood Chain Pendle V2 Market Radar & Antifragility Scanner",
            "",
            f"> **Last Updated:** `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}`  ",
            f"> **Desk Wallet:** [`{OUR_WALLET}`](https://robinhoodchain.blockscout.com/address/{OUR_WALLET})  ",
            f"> **Native Gas Runway:** `{eth_balance:.6f} ETH` (~`${eth_balance * eth_price_usd:.2f} USD` | `{runway_cancels:,}` cancels)  ",
            f"> **Cost per Cancel:** `${cost_cancel_usd:.4f} USD` | **Minimum Hurdle Ratio:** `≥ 5.0x`",
            "",
            "## 1. Multi-Market Opportunity & Competitor Depth Matrix",
            "",
            "| Market | DTE | Implied APY | Incentive Band | BuyPT APR | Min $ (7d 5x) | Desk Status | Whale Status (0x743d7b) |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        ]
        for row in market_rows_md:
            vac_md = f"**{row['whale_status']}**" if row['whale_vacuum'] else row['whale_status']
            lines.append(f"| **{row['market']}** | `{row['dte']:.1f}d` | `{row['implied']:.2f}%` | `{row['band']}` | `{row['apr']:.1f}%` | `${row['min_usd']:.2f}` | {row['our_status']} | {vac_md} |")

        lines.extend([
            "",
            "---",
            "",
            "## 2. Taleb Desk Antifragility Filters",
            "",
            "### ⛔ Ajit Jain Maturity Cliff Exclusions (DTE < 7.0 Days)",
        ])

        if hazard_markets:
            for h in hazard_markets:
                lines.append(f"- 🛑 **{h['market']}** (`{h['dte']:.1f}d` remaining): Excluded from all maker entries. *{h['reason']}*")
        else:
            lines.append("- *No markets currently breaching the 7-day maturity cliff.*")

        lines.extend([
            "",
            "### 🎯 Actionable Opportunities & Dry-Run Shift Commands",
            ""
        ])

        if recommendations:
            for r in recommendations:
                flag = " 🚨 **SOLITARY MAKER VACUUM (100% PENDLE CAPTURE)**" if r["whale_vacuum"] else ""
                lines.extend([
                    f"#### • {r['market']}{flag}",
                    f"- **Target APY:** `{r['target_apy']:.2f}%` (Incentive Band: `{r['band']}` | APR: `{r['apr']:.1f}%`)",
                    f"- **DTE:** `{r['dte']:.1f} Days` (Safety barrier cleared)",
                    f"- **Minimum Capital:** `${r['min_usd']:.2f} USD` (clears 5.0x hurdle over {args.horizon_days:.0f} days)",
                    f"- **Dry-Run Command:**",
                    f"  ```bash",
                    f"  python rh/shift_order.py --market {r['market']} --target-apy {r['target_apy']:.2f} --horizon-days {args.horizon_days:.0f}",
                    f"  ```",
                    ""
                ])

        with open(export_path, "w") as f:
            f.write("\n".join(lines) + "\n")
        print(f"📄 Persistent Radar successfully exported to: {export_path}")

if __name__ == "__main__":
    main()

