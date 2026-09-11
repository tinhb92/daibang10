#!/usr/bin/env python3
import urllib.request
import json
from datetime import datetime, timezone

url = 'https://api-v2.pendle.finance/core/v1/4663/markets?is_active=true'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as resp:
    markets = json.loads(resp.read().decode('utf-8')).get('results', [])

print(f"Total Active Pools on Robinhood Chain: {len(markets)}\n")
for m in markets:
    name = m.get('proName') or m.get('name')
    addr = m.get('address')
    liq = m.get('liquidity', {}).get('usd', 0)
    vol = m.get('tradingVolume', {}).get('usd', 0)
    agg_apy = (m.get('aggregatedApy') or 0) * 100
    underlying_apy = (m.get('underlyingApy') or 0) * 100
    swap_fee_apy = (m.get('swapFeeApy') or 0) * 100
    pendle_apy = (m.get('pendleApy') or 0) * 100
    max_boost = (m.get('maxBoostedApy') or 0) * 100
    imp_apy = (m.get('impliedApy') or 0) * 100
    pt_discount = (m.get('ptDiscount') or 0) * 100
    expiry = m.get('expiry')
    
    print(f"=== {name} ({addr}) ===")
    print(f"  • Expiry:             {expiry}")
    print(f"  • TVL (Liquidity):     ${liq:,.2f} USD")
    print(f"  • 24h Volume:          ${vol:,.2f} USD")
    print(f"  • Aggregated LP APY:   {agg_apy:.2f}% (Max Boosted: {max_boost:.2f}%)")
    print(f"  • Yield Breakdown:     Underlying: {underlying_apy:.2f}% | Fees: {swap_fee_apy:.2f}% | PENDLE: {pendle_apy:.2f}%")
    print(f"  • Implied APY:         {imp_apy:.2f}% | PT Discount: {pt_discount:.2f}%")
    daily_rew = m.get('estimatedDailyPoolRewards', [])
    for r in daily_rew:
        tok = r.get('asset', {}).get('symbol')
        amt = r.get('amount', 0)
        px = r.get('asset', {}).get('price', {}).get('usd', 0)
        print(f"  • Daily Rewards:       {amt:.4f} {tok} (~${amt*px:.2f}/day)")
    print()
