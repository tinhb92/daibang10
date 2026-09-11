#!/usr/bin/env python3
"""
Filter and rank high-ROI moves within Pendle V2 AMM pools for capital between $1,000 and $20,000 USD.
"""

import json
import os

DATA_FILE = os.path.join(os.path.dirname(__file__), "pendlev2_pool_competitors_roi.json")

def main():
    if not os.path.exists(DATA_FILE):
        print(f"File not found: {DATA_FILE}")
        return

    with open(DATA_FILE, "r") as f:
        competitors = json.load(f)

    positions = []
    for c in competitors:
        wallet = c["wallet"]
        for p in c.get("pools", []):
            tvl = p.get("peak_tvl_usd", 0.0)
            gain = p.get("net_gain_usd", 0.0)
            roi = p.get("roi_pct", 0.0)
            vol = p.get("trading_volume_usd", 0.0)
            market = p.get("market_address", "")
            chain = p.get("chainId")
            pool_name = p.get("pool_name", "")

            # Filter criteria: $1,000 <= Capital <= $20,000 and positive gain
            if 1000.0 <= tvl <= 20000.0 and gain > 0:
                positions.append({
                    "wallet": wallet,
                    "pool_name": pool_name,
                    "market_address": market,
                    "chainId": chain,
                    "peak_tvl_usd": tvl,
                    "net_gain_usd": gain,
                    "trading_volume_usd": vol,
                    "roi_pct": roi
                })

    print(f"Total matching positions ($1k <= Capital <= $20k with net gain > 0): {len(positions)}")

    # Sort by ROI
    by_roi = sorted(positions, key=lambda x: x["roi_pct"], reverse=True)
    print("\n" + "=" * 110)
    print("🚀 TOP 20 POOL MOVES BY ROI (%) ($1,000 - $20,000 CAPITAL)")
    print("=" * 110)
    fmt = "{rank:2d}. {wallet:12s} | {pool:20s} | Chain {chain:5d} | TVL: ${tvl:9.2f} | Gain: ${gain:9.2f} | ROI: {roi:7.2f}% | Vol: ${vol:9.2f}"
    for i, pos in enumerate(by_roi[:20], 1):
        print(fmt.format(
            rank=i,
            wallet=pos["wallet"][:10],
            pool=pos["pool_name"][:20],
            chain=pos["chainId"],
            tvl=pos["peak_tvl_usd"],
            gain=pos["net_gain_usd"],
            roi=pos["roi_pct"],
            vol=pos["trading_volume_usd"]
        ))

    # Sort by Net Gain
    by_gain = sorted(positions, key=lambda x: x["net_gain_usd"], reverse=True)
    print("\n" + "=" * 110)
    print("💰 TOP 20 POOL MOVES BY NET PROFIT ($ USD) ($1,000 - $20,000 CAPITAL)")
    print("=" * 110)
    for i, pos in enumerate(by_gain[:20], 1):
        print(fmt.format(
            rank=i,
            wallet=pos["wallet"][:10],
            pool=pos["pool_name"][:20],
            chain=pos["chainId"],
            tvl=pos["peak_tvl_usd"],
            gain=pos["net_gain_usd"],
            roi=pos["roi_pct"],
            vol=pos["trading_volume_usd"]
        ))

if __name__ == "__main__":
    main()
