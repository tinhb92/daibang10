#!/usr/bin/env python3
"""
Pendle V2 Pool Competitors & ROI Miner (Last 2 Months)
Mines all unique LP providers across Pendle V2 AMM pools (Robinhood Chain & Key Cross-Chain Pools),
extracts their net gains, peak capital deployed, and actual realized/unrealized ROI.
"""

import os
import sys
import json
import time
import urllib.request
from datetime import datetime, timezone

# Ensure path
RH_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_API = "https://api-v2.pendle.finance/core"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

RH_POOLS = {
    "sNUKE": "0x8547b391a65deb89c41a4c3b2eb1502d0bbc566a",
    "sNET": "0x23c68474e3cd533a2f952a0fb998f1867e57d27f",
    "SHROOM": "0x49e5d9de386b5ff5cc344748977a412d07191256",
    "NVDA": "0x206a5cd00e9ffabb8ca564076b64799a78df19b9",
    "SGOV": "0xd6e26e957b3207a5c618213d928647ec84150ca0",
    "PFE": "0x892defbf510d9baa96dbd2a51b13e879a857a79b",
    "microduck": "0xdd34d9471667107f9b45e2204add3dd4da54e5a6"
}


def fetch_json(url, max_retries=5):
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                sleep_time = 1.0 * attempt
                time.sleep(sleep_time)
                continue
            if attempt == max_retries:
                return None
        except Exception:
            if attempt == max_retries:
                return None
            time.sleep(0.5)
    return None


def main():
    print("=" * 95, flush=True)
    print("🦅 PENDLE V2 POOL COMPETITOR MINER: 2-MONTH ROI & PROFIT ANALYSIS", flush=True)
    print("=" * 95, flush=True)

    all_users = set()
    pool_to_users = {}

    for name, addr in RH_POOLS.items():
        url = f"{BASE_API}/v1/statistics/get-distinct-user-from-token?token={addr}&chainId=4663"
        res = fetch_json(url)
        time.sleep(0.2)
        users = []
        if isinstance(res, dict):
            users = res.get("users", [])
        elif isinstance(res, list):
            users = res

        clean_users = [u.lower() for u in users if u and u.lower() not in ("0x0000000000000000000000000000000000000000", "0x0000000000000000000000000000000000000001")]
        pool_to_users[name] = clean_users
        all_users.update(clean_users)
        print(f"• {name:<10} ({addr}): {len(clean_users)} distinct LP users", flush=True)

    # Prioritize active non-sNET pools and top census whales
    priority_users = set()
    for name, u_list in pool_to_users.items():
        if name != "sNET":
            priority_users.update(u_list)
        else:
            # Take first 50 sNET users
            priority_users.update(u_list[:50])

    # Also load the top 3-month whales from census
    census_file = os.path.join(RH_DIR, "research", "pendlev2_top_whales_3months.json")
    if os.path.exists(census_file):
        try:
            with open(census_file, "r") as f:
                census_data = json.load(f)
                for w in census_data[:50]:
                    priority_users.add(w["wallet"].lower())
        except Exception:
            pass

    target_users = sorted(priority_users)
    print(f"\nTarget Priority Set: {len(target_users)} unique LP & Whale wallets to mine.", flush=True)
    print("-" * 95, flush=True)

    out_file = os.path.join(RH_DIR, "research", "pendlev2_pool_competitors_roi.json")
    existing_results = {}
    if os.path.exists(out_file):
        try:
            with open(out_file, "r") as f:
                for c in json.load(f):
                    existing_results[c["wallet"].lower()] = c
            print(f"Loaded {len(existing_results)} pre-mined wallets from cache.", flush=True)
        except Exception:
            pass

    competitor_results = list(existing_results.values())
    processed = 0

    for user in target_users:
        processed += 1
        if user in existing_results:
            continue

        pnl_url = f"{BASE_API}/v1/pnl/gained/{user}/positions"
        data = fetch_json(pnl_url)
        time.sleep(0.2)

        if not data:
            continue

        positions = data.get("positions", [])
        user_total_gain_usd = 0.0
        user_total_peak_tvl = 0.0
        pool_breakdowns = []

        for pos in positions:
            m_addr = pos.get("market", "").lower()
            c_id = pos.get("chainId")
            pnl = pos.get("pnl", {})

            net_gain = pnl.get("netGain", {}).get("usd", 0.0)
            peak_tvl = pnl.get("peakTvlUsd", 0.0)
            vol_usd = pnl.get("tradingVolume", 0.0)
            lp_bal = pos.get("lpBalance", 0.0)

            # Match pool name
            matched_name = None
            for p_name, p_addr in RH_POOLS.items():
                if p_addr.lower() == m_addr:
                    matched_name = p_name
                    break

            if not matched_name and c_id == 4663:
                matched_name = f"RH-Pool-{m_addr[:6]}"

            # Only consider pool positions
            if matched_name or peak_tvl > 5.0 or net_gain != 0:
                roi_pct = (net_gain / peak_tvl * 100.0) if peak_tvl > 1.0 else 0.0
                pool_breakdowns.append({
                    "pool_name": matched_name or f"Chain{c_id}-{m_addr[:8]}",
                    "market_address": m_addr,
                    "chainId": c_id,
                    "net_gain_usd": net_gain,
                    "peak_tvl_usd": peak_tvl,
                    "trading_volume_usd": vol_usd,
                    "lp_balance": lp_bal,
                    "roi_pct": roi_pct
                })
                user_total_gain_usd += net_gain
                user_total_peak_tvl += peak_tvl

        if user_total_peak_tvl > 5.0 or user_total_gain_usd > 1.0:
            agg_roi = (user_total_gain_usd / user_total_peak_tvl * 100.0) if user_total_peak_tvl > 1.0 else 0.0
            rec = {
                "wallet": user,
                "total_gain_usd": user_total_gain_usd,
                "total_peak_tvl": user_total_peak_tvl,
                "aggregate_roi_pct": agg_roi,
                "pools_count": len(pool_breakdowns),
                "pools": pool_breakdowns
            }
            competitor_results.append(rec)
            existing_results[user] = rec

        if processed % 15 == 0 or processed == len(target_users):
            print(f"  [{processed}/{len(target_users)}] Processed {user[:10]}... | Total qualifying: {len(competitor_results)}", flush=True)
            # Save incremental checkpoint
            with open(out_file, "w") as f:
                json.dump(competitor_results, f, indent=2)

    with open(out_file, "w") as f:
        json.dump(competitor_results, f, indent=2)

    print(f"\n✅ Mining complete! Total qualifying LP competitors: {len(competitor_results)}", flush=True)
    print(f"Dataset saved to: {out_file}", flush=True)

    # Sort winners
    by_profit = sorted(competitor_results, key=lambda x: x["total_gain_usd"], reverse=True)
    by_roi = sorted([c for c in competitor_results if c["total_peak_tvl"] >= 50.0 and c["total_gain_usd"] > 0], key=lambda x: x["aggregate_roi_pct"], reverse=True)

    print("\n" + "=" * 105, flush=True)
    print("🏆 TOP 10 POOL WINNERS BY ABSOLUTE NET GAIN ($ USD) (LAST 2 MONTHS)", flush=True)
    print("=" * 105, flush=True)
    for i, c in enumerate(by_profit[:10], 1):
        print(f"#{i:2d}: {c['wallet']} | Net Gain: ${c['total_gain_usd']:>11,.2f} | Peak TVL: ${c['total_peak_tvl']:>11,.2f} | ROI: {c['aggregate_roi_pct']:>7.2f}% | Pools: {c['pools_count']}", flush=True)

    print("\n" + "=" * 105, flush=True)
    print("🚀 TOP 10 POOL WINNERS BY ROI (%) (Min $50 Peak Capital)", flush=True)
    print("=" * 105, flush=True)
    for i, c in enumerate(by_roi[:10], 1):
        print(f"#{i:2d}: {c['wallet']} | ROI: {c['aggregate_roi_pct']:>8.2f}% | Net Gain: ${c['total_gain_usd']:>10,.2f} | Peak TVL: ${c['total_peak_tvl']:>10,.2f} | Pools: {c['pools_count']}", flush=True)
    print("=" * 105, flush=True)


if __name__ == "__main__":
    main()
