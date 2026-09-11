#!/usr/bin/env python3
"""
Pendle V2 3-Month Cross-Chain Whales Census
Persona: Taleb Desk (Antifragile Quant & Microstructure Forensics)

Mines all 13 weekly limit-order incentive epochs (last 3 months) across ALL chains:
- Ethereum (1), Arbitrum (42161), Base (8453), BSC (56), Monad (143), Plasma (9745),
  Robinhood (4663), Sonic (146), Mantle (5000), Avalanche (43114), Berachain (80094).
- Aggregates top reward harvesters, capital size, long vs short yield skew, and consistency.
"""

import os
import sys
import json
import time
import datetime
import urllib.request
from collections import defaultdict

BASE_API = "https://api-v2.pendle.finance/core"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def fetch_json(url, timeout=12):
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception:
            time.sleep(0.5)
    return None

def main():
    print("=" * 90)
    print("🦅 PENDLE V2 CROSS-CHAIN 3-MONTH WHALE MINER (LAST 13 EPOCHS)")
    print("=" * 90)

    # 1. Generate 13 Friday UTC epochs (past 3 months)
    d = datetime.datetime(2026, 9, 11, 0, 0, 0, tzinfo=datetime.timezone.utc)
    epochs = []
    for i in range(13):
        dt = d - datetime.timedelta(days=7 * i)
        sec = int(dt.timestamp())
        epochs.append((dt.strftime("%Y-%m-%d"), sec))

    print(f"Targeting {len(epochs)} weekly epochs from {epochs[-1][0]} to {epochs[0][0]}...\n")

    traders = defaultdict(lambda: {
        "user": "",
        "total_reward_pendle": 0.0,
        "reward_long": 0.0,
        "reward_short": 0.0,
        "epochs_active": 0,
        "chains": set(),
        "markets": set(),
        "weekly_rewards": {},
        "raw_entries": []
    })

    for dt_str, sec in epochs:
        # Fetch top 100 for each epoch
        url = f"{BASE_API}/v1/limit-orders/incentive/leaderboard?epochStart={sec}&limit=100"
        data = fetch_json(url)
        if not data:
            print(f"Epoch {dt_str}: Failed to fetch.")
            continue

        results = data.get("results", [])
        total_in_epoch = data.get("total", 0)
        print(f"Epoch {dt_str} (timestamp {sec}): Indexed {len(results)} makers (Total makers: {total_in_epoch})")

        for r in results:
            u = r.get("user", "").lower()
            if not u:
                continue
            tot = float(r.get("totalReward", 0.0))
            rl = float(r.get("rewardLong", 0.0))
            rs = float(r.get("rewardShort", 0.0))

            t = traders[u]
            t["user"] = u
            t["total_reward_pendle"] += tot
            t["reward_long"] += rl
            t["reward_short"] += rs
            t["epochs_active"] += 1
            t["weekly_rewards"][dt_str] = tot

            for m in r.get("markets", []):
                cid = m.get("chainId")
                mname = m.get("marketName")
                if cid:
                    t["chains"].add(cid)
                if mname:
                    t["markets"].add(mname)

        time.sleep(0.2)

    print(f"\nTotal unique whales / makers indexed across 3 months: {len(traders)}")

    # Sort descending by total rewards
    sorted_traders = sorted(traders.values(), key=lambda x: x["total_reward_pendle"], reverse=True)

    # Save to JSON
    out_data = []
    for t in sorted_traders:
        out_data.append({
            "user": t["user"],
            "total_reward_pendle": t["total_reward_pendle"],
            "total_reward_usd_approx": t["total_reward_pendle"] * 2.50,
            "reward_long": t["reward_long"],
            "reward_short": t["reward_short"],
            "long_pct": (t["reward_long"] / t["total_reward_pendle"] * 100) if t["total_reward_pendle"] > 0 else 0,
            "short_pct": (t["reward_short"] / t["total_reward_pendle"] * 100) if t["total_reward_pendle"] > 0 else 0,
            "epochs_active": t["epochs_active"],
            "active_ratio": f"{t['epochs_active']}/13",
            "chains": sorted(list(t["chains"])),
            "market_count": len(t["markets"]),
            "markets_sample": list(t["markets"])[:8],
            "weekly_rewards": t["weekly_rewards"]
        })

    os.makedirs("rh/research", exist_ok=True)
    with open("rh/research/pendlev2_top_whales_3months.json", "w") as f:
        json.dump(out_data, f, indent=2)

    print(f"Saved census to rh/research/pendlev2_top_whales_3months.json")

    print("\n" + "=" * 105)
    print("TOP 20 ELITE PENDLE V2 MAKERS / WHALES OVER THE LAST 3 MONTHS (ALL CHAINS)")
    print("=" * 105)
    print(f"{'Rank':<4} | {'User Address':<42} | {'Total PENDLE':<12} | {'Est. USD':<11} | {'Active':<6} | {'Long%':<6} | {'Short%':<6} | {'Chains'}")
    print("-" * 105)

    for rank, t in enumerate(out_data[:20], 1):
        u = t["user"]
        tot = t["total_reward_pendle"]
        usd = t["total_reward_usd_approx"]
        act = t["active_ratio"]
        lp = t["long_pct"]
        sp = t["short_pct"]
        chains_str = ",".join(str(c) for c in t["chains"])
        print(f"#{rank:<3d} | {u:<42} | {tot:>10.2f} P | ${usd:>9.2f} | {act:<6} | {lp:>5.1f}% | {sp:>5.1f}% | [{chains_str}]")

    print("=" * 105)

if __name__ == "__main__":
    main()
