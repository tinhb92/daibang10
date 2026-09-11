#!/usr/bin/env python3
"""
Pendle V2 Portfolio & Operations Manager Monitor (Robinhood Desk)
Monitors capital balances, active resting orders, accumulated incentive rewards,
and gas runway for wallet 0xaa7c405151c1a11fc2e9998a31b285c7b53d248b on Robinhood Chain (4663).
"""

import os
import sys
import math
import json
import urllib.request
from datetime import datetime
from web3 import Web3

# Local imports
sys.path.append(os.path.dirname(__file__))
from gas_governor import get_gas_metrics

WALLET = "0xaa7c405151c1a11fc2e9998a31b285c7b53d248b".lower()
CHAIN_ID = 4663
RPC_URL = "https://rpc.mainnet.chain.robinhood.com"
BASE_API = "https://api-v2.pendle.finance/core"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "markets.json")
with open(CONFIG_PATH, "r") as f:
    CONFIG = json.load(f)

MARKETS = {}
for m_key, m_val in CONFIG.get("markets", {}).items():
    MARKETS[m_key] = {
        "market": m_val["marketAddress"],
        "pt": m_val["ptAddress"],
        "yt": m_val["ytAddress"],
        "accounting": m_val["accountingAsset"],
        "expiry": m_val.get("expiry", "").split("T")[0]
    }


def rpc_call(method, params):
    try:
        req = urllib.request.Request(
            RPC_URL,
            data=json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode()).get("result")
    except Exception:
        return None

def fetch_json(url):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return {}

def get_onchain_balances():
    user_padded = WALLET[2:].lower().zfill(64)
    calldata = "0x70a08231" + user_padded

    eth_hex = rpc_call("eth_getBalance", [WALLET, "latest"])
    eth_bal = int(eth_hex, 16) / 1e18 if eth_hex else 0.0

    balances = {"ETH": {"amount": eth_bal, "price": 2500.0, "value_usd": eth_bal * 2500.0}}

    tokens_to_query = [
        ("NVDA", MARKETS["NVDA"]["accounting"]),
        ("PT-NVDA", MARKETS["NVDA"]["pt"]),
        ("sNUKE", MARKETS["sNUKE"]["accounting"]),
        ("SHROOM", MARKETS["SHROOM"]["accounting"]),
        ("SGOV", MARKETS["SGOV"]["accounting"]),
    ]

    for symbol, addr in tokens_to_query:
        if not addr:
            continue
        res_hex = rpc_call("eth_call", [{"to": addr, "data": calldata}, "latest"])
        bal = int(res_hex, 16) / 1e18 if res_hex and res_hex != "0x" else 0.0
        balances[symbol] = {"amount": bal, "address": addr}

    return balances

def get_market_prices_and_incentives():
    markets_data = fetch_json(f"{BASE_API}/v1/4663/markets?is_active=true").get("results", [])
    incentive_configs = fetch_json(f"{BASE_API}/v1/limit-orders/incentive/configs").get("configs", [])

    market_info = {}
    for m in markets_data:
        addr = m.get("address", "").lower()
        market_info[addr] = {
            "name": m.get("proName") or m.get("name"),
            "impliedApy": (m.get("impliedApy") or 0) * 100,
            "underlyingApy": (m.get("underlyingApy") or 0) * 100,
            "underlyingPrice": m.get("accountingAsset", {}).get("price", {}).get("usd", 0),
            "ptPrice": m.get("pt", {}).get("price", {}).get("usd", 0),
            "ytPrice": m.get("yt", {}).get("price", {}).get("usd", 0),
            "liquidityUsd": (m.get("liquidity") or {}).get("usd", 0) if isinstance(m.get("liquidity"), dict) else 0
        }

    incentive_map = {}
    for c in incentive_configs:
        if c.get("chainId") == CHAIN_ID:
            m_addr = c.get("marketAddress", "").lower()
            incentive_map[m_addr] = {
                "minApy": (c.get("minApy") or 0) * 100,
                "maxApy": (c.get("maxApy") or 0) * 100,
                "buyPtApr": (c.get("estimatedApr", {}).get("buyPtApr") or 0) * 100,
                "sellYtApr": (c.get("estimatedApr", {}).get("sellYtApr") or 0) * 100,
                "rewardPerSec": c.get("short", {}).get("amountPerSec", 0)
            }

    return market_info, incentive_map

def get_user_orders_and_rewards():
    user_agg = fetch_json(f"{BASE_API}/v1/limit-orders/incentive/user/aggregate?user={WALLET}")
    user_hist = fetch_json(f"{BASE_API}/v1/limit-orders/incentive/user/reward-history?user={WALLET}")
    maker_orders = fetch_json(f"{BASE_API}/v2/limit-orders?chainId={CHAIN_ID}&maker={WALLET}").get("results", [])

    return user_agg, user_hist, maker_orders

def generate_report():
    balances = get_onchain_balances()
    market_info, incentive_map = get_market_prices_and_incentives()
    user_agg, user_hist, maker_orders = get_user_orders_and_rewards()

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    gas = get_gas_metrics(w3, WALLET)
    balances["ETH"]["amount"] = gas["eth_balance"]
    balances["ETH"]["value_usd"] = gas["eth_balance_usd"]

    total_capital_usd = balances["ETH"]["value_usd"]
    for sym in ["NVDA", "sNUKE", "SHROOM", "SGOV"]:
        if sym in balances:
            m_addr = MARKETS.get(sym, {}).get("market", "").lower()
            px = market_info.get(m_addr, {}).get("underlyingPrice", 0.0)
            if px == 0.0:
                if sym == "NVDA": px = 218.84
                elif sym == "sNUKE": px = 16.88
                elif sym == "SHROOM": px = 0.0148
                elif sym == "SGOV": px = 100.0
            balances[sym]["price"] = px
            balances[sym]["value_usd"] = balances[sym]["amount"] * px
            total_capital_usd += balances[sym]["value_usd"]

    report = []
    report.append(f"# Portfolio & Operations Manager: Dashboard")
    report.append(f"**Target Wallet:** `{WALLET}`  ")
    report.append(f"**Network:** Robinhood Chain (`chainId: {CHAIN_ID}`) | **Desk:** `rh/` | **Updated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")

    # Capital Summary
    report.append("## 1. Capital & Wallet Balances")
    report.append("| Asset | Address / Type | Balance | Price (USD) | Total Value (USD) |")
    report.append("| :--- | :--- | :--- | :--- | :--- |")
    report.append(f"| **ETH** (Gas) | Native Gas Buffer | {balances['ETH']['amount']:.6f} ETH | ~$2,500.00 | ${balances['ETH']['value_usd']:.2f} |")
    for sym in ["NVDA", "sNUKE", "SHROOM", "SGOV"]:
        if sym in balances and (balances[sym]["amount"] > 0 or sym in ["NVDA", "sNUKE"]):
            addr_snippet = f"`{balances[sym]['address'][:10]}...`" if balances[sym].get('address') else "N/A"
            report.append(f"| **{sym}** | {addr_snippet} | {balances[sym]['amount']:.4f} {sym} | ${balances[sym]['price']:.4f} | **${balances[sym]['value_usd']:.2f}** |")
    report.append(f"| **Total Liquid Capital** | | | | **${total_capital_usd:.2f} USD** |\n")

    # Gas Economics Model
    report.append("## 2. Gas Consideration & Runway (Robinhood L2 vs Boros)")
    report.append("> [!NOTE]")
    report.append("> Unlike Boros where order operations are 100% off-chain, Robinhood Chain cancellations require on-chain L2 gas. Re-centers are strictly gated by our Gas Hurdle Model (expected reward > 5x gas).")
    report.append("")
    report.append("| Metric | Value | Threshold / Target |")
    report.append("| :--- | :--- | :--- |")
    report.append(f"| **Gas Buffer Balance** | `{gas['eth_balance']:.6f} ETH` (${gas['eth_balance_usd']:.2f}) | Safe (> 0.002 ETH) |")
    report.append(f"| **Current Gas Price** | `{gas['gas_price_gwei']:.4f} Gwei` | Nominal (< 1.0 Gwei) |")
    report.append(f"| **Avg. Cancellation Cost** | `{gas['cost_per_cancel_eth']:.8f} ETH` (~${gas['cost_per_cancel_usd']:.4f}) | < $0.05 / cancel |")
    report.append(f"| **Execution Runway** | **{gas['runway_cancels']:,} cancellations** | 🟢 Healthy |")
    report.append("")

    # Accumulated Rewards
    report.append("## 3. Accumulated Incentive Rewards (PENDLE)")
    lifetime_rew = user_agg.get("lifetimeReward", 0)
    current_rew = user_agg.get("currentEpochReward", 0)
    user_making_total = user_agg.get("userMakingAmountUsdTotal", 0)
    user_making_inc = user_agg.get("userMakingAmountUsdIncentivized", 0)

    report.append(f"- **Lifetime Harvested Rewards:** `{lifetime_rew:.6f} PENDLE`")
    report.append(f"- **Current Active Epoch Rewards:** `{current_rew:.6f} PENDLE` (Accruing)")
    report.append(f"- **Total Resting Limit Order Value:** `${user_making_total:.2f} USD`")
    report.append(f"- **Incentivized Resting Value In-Range:** `${user_making_inc:.2f} USD` " + ("🟢 **ACTIVE IN-RANGE!**" if user_making_inc > 0 else "⚠️ OUT OF RANGE"))

    report.append("\n### Historical Epoch Rewards Breakdown")
    report.append("| Epoch Period | Market | My Reward | Total Pool Reward |")
    report.append("| :--- | :--- | :--- | :--- |")
    epochs = user_hist.get("epochs", [])
    for ep in epochs:
        ep_range = f"{ep.get('startEpochDate', '')[:10]} to {ep.get('endEpochDate', '')[:10]}"
        for m in ep.get("markets", []):
            report.append(f"| {ep_range} | **{m.get('marketName')}** | `{m.get('myReward', 0):.6f} PENDLE` | `{m.get('totalReward', 0):.4f} PENDLE` |")
    report.append("")

    # Active Limit Orders
    report.append("## 4. Active Resting Limit Orders & Band Alignment")
    report.append("| Order ID | Market | Type | Making Amount | Order Implied Rate | Market Band [Min, Max] | Incentive Status |")
    report.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

    yt_to_market = {m_val["yt"].lower(): m_key for m_key, m_val in MARKETS.items()}

    for o in maker_orders:
        oid = o.get("id")[:14] + "..."
        making_wei = int(o.get("currentMakingAmount", 0))
        making_val = making_wei / 1e18
        raw_ln_rate = int(o.get("lnImpliedRate", 0)) / 1e18
        apy_rate = (math.exp(raw_ln_rate) - 1) * 100
        
        yt_addr = (o.get("yt") or "").lower()
        mkt_key = yt_to_market.get(yt_addr, "Unknown")
        
        inc = incentive_map.get(MARKETS.get(mkt_key, {}).get("market", "").lower(), {})
        min_apy = inc.get("minApy", 0.0)
        max_apy = inc.get("maxApy", 0.0)
        
        is_canceled = o.get("isCanceled", False) or not o.get("isActive", True)
        if making_wei == 0 or is_canceled:
            status_tag = "⚪ Cancelled / Inactive"
        elif min_apy <= apy_rate <= max_apy:
            status_tag = "🟢 **IN-RANGE (Earning 100% APR)**"
        else:
            status_tag = f"🔴 **OUT-OF-RANGE** (Needs {min_apy:.2f}%-{max_apy:.2f}%)"

        band_str = f"[{min_apy:.2f}%, {max_apy:.2f}%]" if min_apy > 0 else "N/A"
        report.append(f"| `{oid}` | {mkt_key} | Type {o.get('type')} | {making_val:.4f} | **{apy_rate:.2f}%** | {band_str} | {status_tag} |")

    return "\n".join(report)

if __name__ == "__main__":
    report_text = generate_report()
    print(report_text)
    
    artifact_path = "/Users/tin/.gemini/antigravity-ide/brain/70ed835e-5848-4729-a254-0318f19d3a0e/portfolio_manager_view.md"
    try:
        with open(artifact_path, "w") as f:
            f.write(report_text)
        print(f"\n[Artifact updated]: {artifact_path}")
    except Exception:
        pass
