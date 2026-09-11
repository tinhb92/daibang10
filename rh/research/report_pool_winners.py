#!/usr/bin/env python3
import json
import os

filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pendlev2_pool_competitors_roi.json")
with open(filepath, "r") as f:
    data = json.load(f)

print(f"Total Mined Competitors in Dataset: {len(data)}\n")

# Top by Net Gain
by_gain = sorted(data, key=lambda x: x.get("total_gain_usd", 0.0), reverse=True)
print("=" * 105)
print("🏆 TOP 10 POOL LP WINNERS BY ABSOLUTE NET GAIN ($ USD)")
print("=" * 105)
for i, c in enumerate(by_gain[:10], 1):
    w = c["wallet"]
    gain = c.get("total_gain_usd", 0.0)
    tvl = c.get("total_peak_tvl", 0.0)
    roi = c.get("aggregate_roi_pct", 0.0)
    pools = c.get("pools_count", 0)
    print(f"#{i:2d}: {w} | Gain: ${gain:>11,.2f} | Peak TVL: ${tvl:>11,.2f} | ROI: {roi:>7.2f}% | Pools: {pools}")

# Top by ROI
by_roi = sorted([c for c in data if c.get("total_peak_tvl", 0.0) >= 50.0 and c.get("total_gain_usd", 0.0) > 0.0], key=lambda x: x.get("aggregate_roi_pct", 0.0), reverse=True)
print("\n" + "=" * 105)
print("🚀 TOP 10 POOL LP WINNERS BY ROI (%) (Min $50 Peak Capital)")
print("=" * 105)
for i, c in enumerate(by_roi[:10], 1):
    w = c["wallet"]
    gain = c.get("total_gain_usd", 0.0)
    tvl = c.get("total_peak_tvl", 0.0)
    roi = c.get("aggregate_roi_pct", 0.0)
    pools = c.get("pools_count", 0)
    print(f"#{i:2d}: {w} | ROI: {roi:>8.2f}% | Gain: ${gain:>10,.2f} | Peak TVL: ${tvl:>10,.2f} | Pools: {pools}")

print("=" * 105)

# Detailed Breakdown of Top Winner
if by_roi:
    top = by_roi[0]
    print(f"\n🔬 DEEP-DIVE INTO TOP ROI WINNER: {top['wallet']}")
    print(f"• Aggregate ROI:  {top['aggregate_roi_pct']:.2f}%")
    print(f"• Net Profit:     ${top['total_gain_usd']:,.2f} USD")
    print(f"• Peak Capital:   ${top['total_peak_tvl']:,.2f} USD")
    print("• Pool Breakdown:")
    for p in top.get("pools", []):
        print(f"  - {p['pool_name']} (Chain {p['chainId']}): Gain ${p['net_gain_usd']:,.2f} on Peak ${p['peak_tvl_usd']:,.2f} (ROI: {p['roi_pct']:.2f}%)")

if by_gain:
    top_whale = by_gain[0]
    print(f"\n🔬 DEEP-DIVE INTO TOP PROFIT WHALE: {top_whale['wallet']}")
    print(f"• Net Profit:     ${top_whale['total_gain_usd']:,.2f} USD")
    print(f"• Peak Capital:   ${top_whale['total_peak_tvl']:,.2f} USD")
    print(f"• Aggregate ROI:  {top_whale['aggregate_roi_pct']:.2f}%")
    print("• Top 3 Pools:")
    sorted_pools = sorted(top_whale.get("pools", []), key=lambda x: x.get("net_gain_usd", 0.0), reverse=True)
    for p in sorted_pools[:3]:
        print(f"  - {p['pool_name']} (Chain {p['chainId']}): Gain ${p['net_gain_usd']:,.2f} on Peak ${p['peak_tvl_usd']:,.2f} (ROI: {p['roi_pct']:.2f}%)")
