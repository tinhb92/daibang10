#!/usr/bin/env python3
import json

with open("rh/research/pendlev2_pool_competitors_roi.json") as f:
    data = json.load(f)

targets = [
    "0x11c9ac11ce9913e26faa7a9ee5b07c92b0c8c372",
    "0x010b23b2f2a5f6bc4ce0c68a5f65c248c1129831",
    "0x08a743041f7b809226d7390ed6b62e37c6b56aad",
    "0x09a72958044f48e117235ad88af8a75818f81384"
]

for c in data:
    if c["wallet"] in targets:
        w = c["wallet"]
        gain = c["total_gain_usd"]
        tvl = c["total_peak_tvl"]
        roi = c["aggregate_roi_pct"]
        print(f"=== {w} ===")
        print(f"Total Gain: ${gain:,.2f} | Peak TVL: ${tvl:,.2f} | Aggregate ROI: {roi:.2f}%")
        for p in c["pools"]:
            pname = p["pool_name"]
            cid = p["chainId"]
            pgain = p["net_gain_usd"]
            ptvl = p["peak_tvl_usd"]
            proi = p["roi_pct"]
            pvol = p["trading_volume_usd"]
            print(f"  • {pname} (Chain {cid}): Net Gain: ${pgain:,.2f} | Peak TVL: ${ptvl:,.2f} | ROI: {proi:.2f}% | Vol: ${pvol:,.2f}")
        print()
