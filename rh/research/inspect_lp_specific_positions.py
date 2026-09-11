#!/usr/bin/env python3
"""
Inspect specific LP moves (excluding pure YT/PT trades) for capital between $1k and $20k.
"""

import json
import urllib.request
import time

WALLETS = [
    "0x743d7b30661d65b41960bf6b5d1bb93cf7972a73",
    "0x010b23b2f2a5f6bc4ce0c68a5f65c248c1129831",
    "0x11c9ac11ce9913e26faa7a9ee5b07c92b0c8c372",
    "0x08a743041f7b809226d7390ed6b62e37c6b56aad",
    "0x16c29e0cf90bb07d4022c927cbbe1693956044c7",
    "0xf9bb823a2eaa181ab89b79cea6301274368999b4",
    "0x697999ecfc86f0bfa43235bcf324cc7f186e3d54",
    "0x56ed60c71e3f193b20c6d144144dd7d32638f934",
    "0x136342756cc5fb8f4e53bfe581f9b5b5aef27032",
    "0x09a72958044f48e117235ad88af8a75818f81384"
]

def main():
    pure_lp_moves = []

    for w in WALLETS:
        url = f"https://api-v2.pendle.finance/core/v1/pnl/gained/{w}/positions"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                d = json.loads(r.read().decode())
        except Exception as e:
            print(f"Error fetching {w[:10]}: {e}")
            continue

        time.sleep(0.3)
        for pos in d.get("positions", []):
            lp_data = pos.get("lpData", {})
            lp_spent = lp_data.get("spent_v2", {}).get("usd", 0.0)
            lp_bal = pos.get("lpBalance", 0.0)
            yt_spent = pos.get("ytData", {}).get("spent_v2", {}).get("usd", 0.0)
            pt_spent = pos.get("ptData", {}).get("spent_v2", {}).get("usd", 0.0)

            pnl = pos.get("pnl", {})
            gain = pnl.get("netGain", {}).get("usd", 0.0)
            peak_tvl = pnl.get("peakTvlUsd", 0.0)
            vol = pnl.get("tradingVolume", 0.0)
            market = pos.get("market")
            chain = pos.get("chainId")

            # Must be an LP position (lp_spent > 0 or lp_bal > 0)
            if lp_spent > 0 or lp_bal > 0:
                capital = lp_spent if lp_spent > 0 else peak_tvl
                roi = (gain / capital * 100.0) if capital > 0 else 0.0
                pure_lp_moves.append({
                    "wallet": w,
                    "market": market,
                    "chainId": chain,
                    "capital": capital,
                    "lp_spent": lp_spent,
                    "lp_bal": lp_bal,
                    "yt_spent": yt_spent,
                    "pt_spent": pt_spent,
                    "gain": gain,
                    "peak_tvl": peak_tvl,
                    "vol": vol,
                    "roi": roi
                })

    print(f"Total Pure LP Positions Found: {len(pure_lp_moves)}")

    # Filter for $1,000 <= Capital <= $20,000
    target_bracket = [m for m in pure_lp_moves if 1000.0 <= m["capital"] <= 20000.0]
    print(f"LP Moves with $1k <= Capital <= $20k: {len(target_bracket)}")

    print("\n" + "=" * 115)
    print("🏆 TOP 15 PURE POOL LP MOVES BY ROI ($1,000 - $20,000 CAPITAL)")
    print("=" * 115)
    fmt = "{rank:2d}. {wallet:12s} | Market: {market:14s} | Chain {chain:5d} | Capital: ${cap:9.2f} | Gain: ${gain:9.2f} | ROI: {roi:7.2f}% | Vol: ${vol:9.2f}"
    by_roi = sorted(target_bracket, key=lambda x: x["roi"], reverse=True)
    for i, m in enumerate(by_roi[:15], 1):
        print(fmt.format(
            rank=i,
            wallet=m["wallet"][:10],
            market=m["market"][:14],
            chain=m["chainId"],
            cap=m["capital"],
            gain=m["gain"],
            roi=m["roi"],
            vol=m["vol"]
        ))

    print("\n" + "=" * 115)
    print("💰 TOP 15 PURE POOL LP MOVES BY NET PROFIT ($1,000 - $20,000 CAPITAL)")
    print("=" * 115)
    by_gain = sorted(target_bracket, key=lambda x: x["gain"], reverse=True)
    for i, m in enumerate(by_gain[:15], 1):
        print(fmt.format(
            rank=i,
            wallet=m["wallet"][:10],
            market=m["market"][:14],
            chain=m["chainId"],
            cap=m["capital"],
            gain=m["gain"],
            roi=m["roi"],
            vol=m["vol"]
        ))

if __name__ == "__main__":
    main()
