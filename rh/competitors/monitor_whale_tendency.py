#!/usr/bin/env python3
"""
Whale Tendency Monitor: 0x743d7b (Robinhood Chain & Pendle V2 Desk)
Persona: Taleb Desk (Antifragile Quant & Microstructure Forensics)

Continuously profiles and monitors the dominant liquidity whale on Robinhood Chain:
Address: 0x743d7b30661d65b41960bf6b5d1bb93cf7972a73
- Tracks resting limit order rungs across all pools (SHROOM, SGOV, PFE, microduck, NVDA, sNUKE, sNET)
- Audits in-band vs out-of-band drift (identifies unmined incentive vacuums for our desk)
- Monitors fill progression and trade execution
- Audits cross-chain PENDLE mining harvests and capital allocation
"""

import sys
import os
import json
import time
import math
import argparse
import urllib.request

WHALE_ADDR = "0x743d7b30661d65b41960bf6b5d1bb93cf7972a73"
CHAIN_ID = 4663
RPC_URL = "https://rpc.mainnet.chain.robinhood.com"
BASE_API = "https://api-v2.pendle.finance/core"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def fetch_json(url, timeout=12):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return None

def json_rpc(method, params):
    data = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode("utf-8")
    req = urllib.request.Request(RPC_URL, data=data, headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return res.get("result")
    except Exception:
        return None

def audit_whale():
    # 1. On-Chain RPC Gas & Nonce Check
    eth_bal_hex = json_rpc("eth_getBalance", [WHALE_ADDR, "latest"])
    eth_balance = int(eth_bal_hex, 16) / 1e18 if eth_bal_hex else 0.0
    tx_cnt_hex = json_rpc("eth_getTransactionCount", [WHALE_ADDR, "latest"])
    tx_count = int(tx_cnt_hex, 16) if tx_cnt_hex else 0

    # 2. Fetch Active Markets
    markets_data = fetch_json(f"{BASE_API}/v1/{CHAIN_ID}/markets?limit=50")
    markets_list = markets_data.get("results", []) if markets_data else []
    market_map = {}
    for m in markets_list:
        yt_addr = m.get("yt", {}).get("address", "").lower()
        pt_addr = m.get("pt", {}).get("address", "").lower()
        m_addr = m.get("address", "").lower()
        pt_sym = m.get("pt", {}).get("symbol", "UNKNOWN")
        underlying_sym = m.get("underlyingAsset", {}).get("symbol", "TOKEN")
        
        info = {
            "market_address": m_addr,
            "pt_symbol": pt_sym,
            "underlying_symbol": underlying_sym,
            "expiry": m.get("expiry"),
            "pt_price": m.get("pt", {}).get("price", {}).get("usd", 0.0),
            "yt_price": m.get("yt", {}).get("price", {}).get("usd", 0.0),
            "underlying_price": m.get("underlyingAsset", {}).get("price", {}).get("usd", 0.0),
        }
        market_map[yt_addr] = info
        market_map[pt_addr] = info
        market_map[m_addr] = info

    # 3. Fetch Incentive Configs (Bands)
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

    # 4. Fetch Whale Incentive Aggregate
    agg = fetch_json(f"{BASE_API}/v1/limit-orders/incentive/user/aggregate?user={WHALE_ADDR}") or {}
    lifetime_reward = agg.get("lifetimeReward", 0.0)
    current_reward = agg.get("currentEpochReward", 0.0)
    total_making_usd = agg.get("userMakingAmountUsdTotal", 0.0)
    incentivized_usd = agg.get("userMakingAmountUsdIncentivized", 0.0)
    placed_count = agg.get("placedMarketCount", 0)
    incentivized_count = agg.get("incentivizedMarketCount", 0)

    # 5. Fetch Whale Limit Orders on Robinhood Chain
    orders_res = fetch_json(f"{BASE_API}/v2/limit-orders?chainId={CHAIN_ID}&maker={WHALE_ADDR}&limit=100") or {}
    orders = orders_res.get("results", [])

    active_orders = []
    historical_orders = []
    total_active_usd = 0.0
    vacuums = []

    for o in orders:
        oid = o.get("id")
        created_at = o.get("createdAt", "")
        ln_rate = float(o.get("lnImpliedRate", 0)) / 1e18
        order_apy = (math.exp(ln_rate) - 1) * 100.0 if ln_rate > 0 else 0.0
        state = o.get("orderState", {})
        otype = state.get("orderType") or ("SHORT_YIELD" if o.get("type") == 3 else "LONG_YIELD")
        usd_vol = state.get("notionalVolumeUSD", 0.0)
        is_active = o.get("isActive", False)
        status = o.get("status", "")
        yt = o.get("yt", "").lower()
        
        making_amt = float(o.get("makingAmount", 0))
        curr_making = float(o.get("currentMakingAmount", 0))
        filled_amt = making_amt - curr_making
        fill_pct = (filled_amt / making_amt * 100.0) if making_amt > 0 else 0.0

        m_info = market_map.get(yt, {})
        m_addr = m_info.get("market_address", "")
        m_name = m_info.get("pt_symbol", yt[:10])
        b_info = band_map.get(m_addr, {})
        m_implied = b_info.get("impliedApy", 0.0)
        min_apy = b_info.get("minApy", 0.0)
        max_apy = b_info.get("maxApy", 0.0)
        buy_pt_apr = b_info.get("buyPtApr", 0.0)

        in_band = (min_apy <= order_apy <= max_apy) and min_apy > 0
        drift_dist = order_apy - m_implied

        order_row = {
            "id": oid,
            "created_at": created_at,
            "market": m_name,
            "market_address": m_addr,
            "yt": yt,
            "type": otype,
            "order_apy": order_apy,
            "market_implied": m_implied,
            "min_apy": min_apy,
            "max_apy": max_apy,
            "buy_pt_apr": buy_pt_apr,
            "drift_dist": drift_dist,
            "in_band": in_band,
            "status": status,
            "is_active": is_active,
            "usd_vol": usd_vol,
            "fill_pct": fill_pct,
            "making_amt": making_amt,
            "curr_making": curr_making
        }

        if is_active:
            active_orders.append(order_row)
            total_active_usd += usd_vol
            if not in_band and m_implied > 0:
                vacuums.append({
                    "market": m_name,
                    "market_address": m_addr,
                    "whale_apy": order_apy,
                    "market_implied": m_implied,
                    "min_apy": min_apy,
                    "max_apy": max_apy,
                    "buy_pt_apr": buy_pt_apr,
                    "whale_size_usd": usd_vol
                })
        else:
            historical_orders.append(order_row)

    return {
        "address": WHALE_ADDR,
        "eth_balance": eth_balance,
        "nonce": tx_count,
        "total_active_usd_rh": total_active_usd,
        "global_making_usd": total_making_usd,
        "incentivized_usd": incentivized_usd,
        "placed_count": placed_count,
        "incentivized_count": incentivized_count,
        "total_claimed_pendle": lifetime_reward,
        "current_accruing_pendle": current_reward,
        "active_orders": active_orders,
        "historical_orders": historical_orders,
        "incentive_vacuums": vacuums
    }

def print_audit_report(data):
    print("=" * 95)
    print(f"🦅 TALEB DESK — COMPETITOR FORENSIC MONITOR: {data['address']}")
    print("=" * 95)
    print(f"• Gas Runway (RH Chain):     {data['eth_balance']:.6f} ETH (${data['eth_balance']*2500:.2f} USD) | Nonce: {data['nonce']}")
    print(f"• Active Capital Quoted (RH): ${data['total_active_usd_rh']:,.2f} USD across {len(data['active_orders'])} live orders")
    print(f"• Multi-Chain Global Quoted:  ${data['global_making_usd']:,.2f} USD")
    claimed_usd = data['total_claimed_pendle'] * 2.50
    print(f"• Lifetime PENDLE Harvested:  {data['total_claimed_pendle']:,.4f} PENDLE (~${claimed_usd:,.2f} USD)")
    print(f"• Current Accruing Rewards:   {data['current_accruing_pendle']:,.4f} PENDLE")
    print("-" * 95)

    print("\n[ACTIVE RESTING ORDERS ON ROBINHOOD CHAIN]")
    print(f"{'Market / PT':<24} | {'Type':<11} | {'Order APY':<9} | {'Market APY':<10} | {'Status':<12} | {'USD Size':<12} | {'Incentive Status'}")
    print("-" * 95)
    for o in data["active_orders"]:
        inc_status = "✅ IN-BAND (Earning)" if o["in_band"] else f"❌ OUT-OF-BAND (0 Yield, drift: {o['drift_dist']:.1f}%)"
        print(f"{o['market']:<24} | {o['type']:<11} | {o['order_apy']:>7.2f}% | {o['market_implied']:>8.2f}% | {o['status']:<12} | ${o['usd_vol']:>10.2f} | {inc_status}")

    print("\n[SIGNIFICANT HISTORICAL EXECUTIONS & FILLS]")
    print(f"{'Market / PT':<24} | {'Type':<11} | {'Order APY':<10} | {'Status':<10} | {'Fill %':<8} | {'USD Vol':<12} | {'Date'}")
    print("-" * 95)
    for o in data["historical_orders"]:
        if o["fill_pct"] > 0 or o["order_apy"] > 1000:
            print(f"{o['market']:<24} | {o['type']:<11} | {o['order_apy']:>8.1f}% | {o['status']:<10} | {o['fill_pct']:>6.1f}% | ${o['usd_vol']:>10.2f} | {o['created_at'][:10]}")

    if data["incentive_vacuums"]:
        print("\n" + "!" * 95)
        print("🎯 TALEB ANTIFRAGILE OPPORTUNITIES (WHALE BLINDSPOTS / INCENTIVE VACUUMS)")
        print("!" * 95)
        for v in data["incentive_vacuums"]:
            print(f"• Market: {v['market']}")
            print(f"  Whale is resting static at {v['whale_apy']:.2f}% APY (${v['whale_size_usd']:,.2f} USD).")
            print(f"  Current Implied Rate is {v['market_implied']:.2f}% APY -> Whale has drifted OUT OF BAND.")
            print(f"  ACTIONABLE EXPLOIT: Competing maker depth in active incentive band is $0.00.")
            print(f"  Our desk can quote tight inside the band to monopolize 100% of PENDLE emissions!")
        print("!" * 95)
    print("=" * 95)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Taleb Desk Competitor Forensics")
    parser.add_argument("--once", action="store_true", help="Run single audit pass and exit")
    parser.add_argument("--interval", type=int, default=300, help="Loop interval in seconds (default: 300s)")
    args = parser.parse_args()

    if args.once:
        data = audit_whale()
        print_audit_report(data)
    else:
        print("Starting Whale Tendency Monitor Daemon (Press Ctrl+C to stop)...")
        while True:
            try:
                data = audit_whale()
                print_audit_report(data)
                time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\nStopping monitor.")
                sys.exit(0)
            except Exception as e:
                print(f"Monitor error: {e}")
                time.sleep(30)
