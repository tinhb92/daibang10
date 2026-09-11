#!/usr/bin/env python3
"""
On-Chain Pendle V2 Pool Whale & Competitor Analyzer (Robinhood Chain 4663)
Queries on-chain LP balances and pool metrics for all participants across the active AMM pools:
- sNUKE (147.7% APY)
- SHROOM (72.8% APY)
- NVDA (27.2% APY)
- SGOV (139.1% APY)
- PFE (23.4% APY)
- sNET (14,859% APY)
"""

import os
import sys
import json
import urllib.request
from datetime import datetime, timezone

RPC_URL = "https://rpc.mainnet.chain.robinhood.com"
BASE_API = "https://api-v2.pendle.finance/core"
HEADERS = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

RH_POOLS = {
    "sNUKE": {
        "market": "0x8547b391a65deb89c41a4c3b2eb1502d0bbc566a",
        "underlying_price": 8.235,
        "lp_price_est": 16.93,
        "agg_apy": 147.70,
        "dte": 12.0
    },
    "SHROOM": {
        "market": "0x49e5d9de386b5ff5cc344748977a412d07191256",
        "underlying_price": 0.0148,
        "lp_price_est": 0.0150,
        "agg_apy": 72.82,
        "dte": 12.0
    },
    "NVDA": {
        "market": "0x206a5cd00e9ffabb8ca564076b64799a78df19b9",
        "underlying_price": 218.47,
        "lp_price_est": 218.0,
        "agg_apy": 27.15,
        "dte": 33.0
    },
    "SGOV": {
        "market": "0xd6e26e957b3207a5c618213d928647ec84150ca0",
        "underlying_price": 100.93,
        "lp_price_est": 100.90,
        "agg_apy": 139.08,
        "dte": 68.0
    },
    "PFE": {
        "market": "0x892defbf510d9baa96dbd2a51b13e879a857a79b",
        "underlying_price": 27.62,
        "lp_price_est": 27.50,
        "agg_apy": 23.38,
        "dte": 89.0
    },
    "sNET": {
        "market": "0x23c68474e3cd533a2f952a0fb998f1867e57d27f",
        "underlying_price": 507.0,
        "lp_price_est": 507.0,
        "agg_apy": 14859.0,
        "dte": 5.0
    }
}


def rpc_call(method, params):
    payload = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
    req = urllib.request.Request(RPC_URL, data=payload, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode()).get("result")
    except Exception as e:
        return None


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def get_token_balance(token_addr, wallet_addr):
    padded = wallet_addr[2:].lower().zfill(64)
    data = "0x70a08231" + padded
    res = rpc_call("eth_call", [{"to": token_addr, "data": data}, "latest"])
    if res and res != "0x":
        return int(res, 16) / 1e18
    return 0.0


def main():
    print("=" * 105)
    print("🦅 PENDLE V2 POOL COMPETITOR MINER: ON-CHAIN HOLDINGS & ROI FORENSICS")
    print("=" * 105)

    all_lp_holders = []

    for pool_name, p_info in RH_POOLS.items():
        m_addr = p_info["market"]
        # Fetch interacting users from statistics endpoint
        url = f"{BASE_API}/v1/statistics/get-distinct-user-from-token?token={m_addr}&chainId=4663"
        res = fetch_json(url) or {}
        users = res.get("users", []) if isinstance(res, dict) else (res if isinstance(res, list) else [])
        clean_users = [u.lower() for u in users if u and u.lower() not in ("0x0000000000000000000000000000000000000000", "0x0000000000000000000000000000000000000001")]

        print(f"Scanning {pool_name:<8} ({m_addr}) across {len(clean_users)} participant wallets...")

        for u in clean_users:
            lp_bal = get_token_balance(m_addr, u)
            if lp_bal > 0.0001:  # Significant holding
                val_usd = lp_bal * p_info["lp_price_est"]
                daily_cashflow = (val_usd * (p_info["agg_apy"] / 100.0)) / 365.0
                horizon_pnl = (val_usd * (p_info["agg_apy"] / 100.0)) * (p_info["dte"] / 365.0)
                roi_to_maturity = (horizon_pnl / val_usd * 100.0) if val_usd > 0 else 0.0

                all_lp_holders.append({
                    "pool": pool_name,
                    "market_address": m_addr,
                    "wallet": u,
                    "lp_balance": lp_bal,
                    "value_usd": val_usd,
                    "pool_agg_apy": p_info["agg_apy"],
                    "daily_cashflow_usd": daily_cashflow,
                    "projected_pnl_usd": horizon_pnl,
                    "projected_roi_pct": roi_to_maturity,
                    "dte": p_info["dte"]
                })

    print(f"\nTotal Active On-Chain LP Positions Discovered: {len(all_lp_holders)}")
    print("-" * 105)

    # Sort by Current LP Position Value (USD)
    all_lp_holders.sort(key=lambda x: x["value_usd"], reverse=True)

    # Output Rankings
    print(f"{'Rank':<4} | {'Pool':<7} | {'Wallet':<42} | {'LP Tokens':<10} | {'Value ($)':<12} | {'Daily Cashflow':<14} | {'Proj. Gain ($)'}")
    print("-" * 105)

    for i, h in enumerate(all_lp_holders[:20], 1):
        print(f"#{i:<3} | {h['pool']:<7} | {h['wallet']:<42} | {h['lp_balance']:>9.4f} | ${h['value_usd']:>10,.2f} | ${h['daily_cashflow_usd']:>12,.2f}/d | +${h['projected_pnl_usd']:>10,.2f}")

    # Save to JSON artifact
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pendlev2_active_pool_competitors.json")
    with open(out_path, "w") as f:
        json.dump(all_lp_holders, f, indent=2)

    print(f"\n✅ Successfully exported on-chain active LP database to: {out_path}")


if __name__ == "__main__":
    main()
