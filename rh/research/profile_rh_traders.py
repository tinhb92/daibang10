#!/usr/bin/env python3
"""
Robinhood Chain (Chain 4663) Pendle V2 Trader & Market Maker Profiler.
Fetches all orders, classifies market participants, and profiles top whales and makers.
"""

import urllib.request
import json
import math
import time
import os
from collections import defaultdict

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
BASE_API = 'https://api-v2.pendle.finance/core'
CHAIN_ID = 4663

PRICES = {
    "NVDA": 220.0,
    "sNET": 510.0,
    "sNUKE": 9.10,
    "SHROOM": 0.0148,
    "SGOV": 101.0,
    "PFE": 27.6,
    "microduck": 0.0075
}

def run_profiler():
    all_orders = []
    offset = 0
    total_expected = 600

    print("=== PENDLE V2 ROBINHOOD CHAIN (4663) TRADER PROFILER ===")
    print(f"Connecting to {BASE_API}...")

    while offset < total_expected:
        url = f"{BASE_API}/v2/limit-orders?chainId={CHAIN_ID}&limit=100&offset={offset}"
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                res = data.get("results", [])
                total_expected = data.get("total", total_expected)
                if not res:
                    break
                all_orders.extend(res)
                print(f"  Offset {offset:3d}: Fetched {len(res):2d} orders (Total: {len(all_orders)} / {total_expected})")
                if len(res) < 100:
                    break
        except Exception as e:
            print(f"  Fetch error at offset {offset}: {e}")
            time.sleep(2.0)
            continue
            
        offset += 100
        time.sleep(0.5)

    print(f"\nCollected {len(all_orders)} total limit orders on Chain 4663.")

    # Aggregate by Maker
    makers = defaultdict(lambda: {
        "address": "",
        "total_orders": 0,
        "active_orders": 0,
        "canceled_orders": 0,
        "filled_orders": 0,
        "markets": defaultdict(int),
        "tokens_quoted": defaultdict(float),
        "total_notional_usd": 0.0,
        "active_notional_usd": 0.0,
        "filled_notional_usd": 0.0,
        "rates": [],
        "order_types": defaultdict(int)
    })

    for o in all_orders:
        addr = o.get("maker", "").lower()
        if not addr:
            continue
            
        m = makers[addr]
        m["address"] = addr
        m["total_orders"] += 1
        
        is_active = o.get("isActive", True)
        is_canceled = o.get("isCanceled", False)
        making_wei = float(o.get("makingAmount", 0))
        curr_making_wei = float(o.get("currentMakingAmount", 0))
        making_val = making_wei / 1e18
        curr_making_val = curr_making_wei / 1e18
        
        otype = o.get("orderType", o.get("type", 0))
        m["order_types"][str(otype)] += 1
        
        ln_rate = float(o.get("lnImpliedRate", 0)) / 1e18
        implied_apy = (math.exp(ln_rate) - 1) * 100.0 if ln_rate > 0 else 0.0
        if implied_apy > 0:
            m["rates"].append(implied_apy)

        # Status classification
        if is_canceled:
            m["canceled_orders"] += 1
        elif curr_making_wei == 0 and making_wei > 0:
            m["filled_orders"] += 1
        elif is_active:
            m["active_orders"] += 1
            
        token_sym = o.get("orderTokenSymbol") or o.get("makingTokenSymbol") or "TOKEN"
        # Try to infer token symbol from price keys
        token_upper = token_sym.upper()
        matched_px = 1.0
        for k, p in PRICES.items():
            if k.upper() in token_upper:
                matched_px = p
                token_sym = k
                break
                
        m["tokens_quoted"][token_sym] += making_val
        usd_val = making_val * matched_px
        m["total_notional_usd"] += usd_val
        
        if is_active and not is_canceled and curr_making_wei > 0:
            m["active_notional_usd"] += curr_making_val * matched_px
        elif curr_making_wei == 0 and making_wei > 0 and not is_canceled:
            m["filled_notional_usd"] += usd_val
            
        mkt = o.get("marketAddress") or o.get("yt") or "UNKNOWN"
        m["markets"][mkt] += 1

    print(f"Total Unique Makers Analyzed: {len(makers)}\n")

    # Sort by total notional capital quoted
    sorted_by_notional = sorted(makers.values(), key=lambda x: x["total_notional_usd"], reverse=True)
    
    # Save structured results
    output_data = {
        "timestamp": time.time(),
        "total_orders": len(all_orders),
        "total_makers": len(makers),
        "top_makers": sorted_by_notional
    }
    
    with open("/root/daibang10/rh/research/rh_makers_census.json" if os.path.exists("/root/daibang10") else "rh/research/rh_makers_census.json", "w") as f:
        json.dump(output_data, f, indent=2)

    print("=" * 100)
    print(f"{'Rank':<4} | {'Maker Address':<42} | {'Orders (Act/Fill/Ccl)':<22} | {'Total Quoted (USD)':<18} | {'Active (USD)':<14} | {'Avg Rate':<9}")
    print("=" * 100)
    
    for i, m in enumerate(sorted_by_notional[:15], 1):
        avg_rate = (sum(m["rates"]) / len(m["rates"])) if m["rates"] else 0.0
        ord_str = f"{m['total_orders']} ({m['active_orders']}/{m['filled_orders']}/{m['canceled_orders']})"
        print(f"#{i:2d}  | {m['address']:<42} | {ord_str:<22} | ${m['total_notional_usd']:>16,.2f} | ${m['active_notional_usd']:>12,.2f} | {avg_rate:>7.1f}%")

if __name__ == "__main__":
    run_profiler()
