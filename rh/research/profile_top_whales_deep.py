#!/usr/bin/env python3
"""
Deep Forensic Profiler for Top Pendle V2 Whales (Last 3 Months)
Persona: Taleb Desk (Antifragile Quant & Microstructure Forensics)

Analyzes the Top 5 Cross-Chain Whales + 0x743d7b:
1. 0xb1350ae77f1f7d977fab077ea71c6011e74b9306 (Global #1 - $33.8k rewards)
2. 0xc693b4ffb338579467a541b2bf267b1955870920 (Global #2 - $24.2k rewards)
3. 0x804528cbf2d6d27f3b0b35bddd7cbafbe06e83ba (Global #3 - $12.0k rewards)
4. 0x9c80a96a06cb6f7943a462dde7ac215011fa8ace (Global #4 - $10.5k rewards)
5. 0xa8236ead24b2a3085a6e5f11a23b39eee03ae300 (Global #5 - $10.5k rewards)
6. 0x743d7b30661d65b41960bf6b5d1bb93cf7972a73 (Robinhood Chain Monopoly)
"""

import os
import json
import time
import urllib.request

BASE_API = "https://api-v2.pendle.finance/core"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

TARGETS = [
    {"rank": 1, "addr": "0xb1350ae77f1f7d977fab077ea71c6011e74b9306", "name": "The Short-Yield Titan"},
    {"rank": 2, "addr": "0xc693b4ffb338579467a541b2bf267b1955870920", "name": "The Cross-Chain Yield King"},
    {"rank": 3, "addr": "0x804528cbf2d6d27f3b0b35bddd7cbafbe06e83ba", "name": "The Monad & HyperEVM Arbitrageur"},
    {"rank": 4, "addr": "0x9c80a96a06cb6f7943a462dde7ac215011fa8ace", "name": "The Delta-Neutral Market Maker"},
    {"rank": 5, "addr": "0xa8236ead24b2a3085a6e5f11a23b39eee03ae300", "name": "The Arbitrum CLOB Monopoly"},
    {"rank": 41, "addr": "0x743d7b30661d65b41960bf6b5d1bb93cf7972a73", "name": "The Robinhood Chain Goliath"}
]

def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            time.sleep(0.5)
    return None

def main():
    print("=" * 90)
    print("🦅 DEEP FORENSIC PROFILING OF TOP PENDLE V2 WHALES")
    print("=" * 90)

    dossiers = []

    for item in TARGETS:
        addr = item["addr"]
        name = item["name"]
        rank = item["rank"]
        print(f"\nProfiling #{rank}: {name} ({addr})...")

        # 1. Incentive Aggregate
        agg = fetch_json(f"{BASE_API}/v1/limit-orders/incentive/user/aggregate?user={addr}") or {}
        
        # 2. Reward History
        hist = fetch_json(f"{BASE_API}/v1/limit-orders/incentive/user/reward-history?user={addr}") or {}

        # 3. Active Orders Sample
        orders_data = fetch_json(f"{BASE_API}/v2/limit-orders?maker={addr}&limit=50") or {}
        orders = orders_data.get("results", [])

        # Active resting capital calculation
        active_orders = [o for o in orders if o.get("isActive", False)]
        total_active_orders_found = len(active_orders)

        profile = {
            "rank": rank,
            "name": name,
            "address": addr,
            "lifetime_reward_pendle": agg.get("lifetimeReward", 0.0),
            "current_epoch_reward_pendle": agg.get("currentEpochReward", 0.0),
            "current_resting_usd": agg.get("userMakingAmountUsdTotal", 0.0),
            "current_incentivized_usd": agg.get("userMakingAmountUsdIncentivized", 0.0),
            "placed_market_count": agg.get("placedMarketCount", 0),
            "incentivized_market_count": agg.get("incentivizedMarketCount", 0),
            "total_active_orders_found": total_active_orders_found,
            "participated_markets": agg.get("participatedMarkets", []),
            "history_epochs_count": len(hist.get("epochs", []))
        }

        print(f"  • Lifetime Harvest: {profile['lifetime_reward_pendle']:,.2f} PENDLE (~${profile['lifetime_reward_pendle']*2.5:,.2f})")
        print(f"  • Currently Resting Capital: ${profile['current_resting_usd']:,.2f} USD")
        print(f"  • Active Markets Quoted: {profile['placed_market_count']} (Incentivized: {profile['incentivized_market_count']})")
        print(f"  • Sample Participated Markets: {len(profile['participated_markets'])} pools")

        dossiers.append(profile)
        time.sleep(0.3)

    os.makedirs("rh/research", exist_ok=True)
    with open("rh/research/top_whales_detailed_profiles.json", "w") as f:
        json.dump(dossiers, f, indent=2)

    print("\nProfiles saved to rh/research/top_whales_detailed_profiles.json")

if __name__ == "__main__":
    main()
