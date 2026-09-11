#!/usr/bin/env python3
"""
Pendle V2 - Robinhood Chain Multi-Market Big Move & Order Fill Monitor
Monitors active watch markets on Robinhood Chain (4663):
  1. NVDA (15-OCT-2026): 0x206a5cd00e9ffabb8ca564076b64799a78df19b9
  2. sNET (17-SEP-2026): 0x23c68474e3cd533a2f952a0fb998f1867e57d27f (YT Focus)

Dispatches immediate Telegram alerts when significant moves occur:
  - Implied APY shifts (wicks / dislocations)
  - Spot price moves
  - Pool Liquidity shocks
  - Incentive band drift (approaching boundaries or falling out-of-range)
  - Limit Order Fills (partial or full fills detected)
  - Competitor maker depth entry on short/long side

Usage:
  python rh/monitor_nvda_moves.py --once
  python rh/monitor_nvda_moves.py --loop --interval 60
  python rh/monitor_nvda_moves.py --test-alert
"""

import os
import sys
import time
import math
import json
import argparse
import urllib.request
from datetime import datetime, timezone

# Local imports
sys.path.append(os.path.dirname(__file__))
from alerter import send_telegram_alert

CHAIN_ID = 4663
WALLET = "0xaa7c405151c1a11fc2e9998a31b285c7b53d248b".lower()
BASE_API = "https://api-v2.pendle.finance/core"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
STATE_FILE = os.path.join(os.path.dirname(__file__), "rh_markets_state.json")

# Monitored Markets on Robinhood Chain
WATCHLIST = {
    "NVDA": {
        "market": "0x206a5cd00e9ffabb8ca564076b64799a78df19b9",
        "yt": "0x9cc22e51c6f0cb4aa1bfd1f18e85df1451ebb9b3",
        "pt": "0x4bcb25fce9618e62e9f9fba8d65af50cf867b812",
        "accounting": "0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec",
        "expiry": "2026-10-15",
        "delta_apy_alert": 0.25,     # 25 bps shift
        "delta_spot_pct": 1.0,       # 1.0% spot move
        "delta_liq_pct": 5.0         # 5% liquidity shift
    },
    "sNET": {
        "market": "0x23c68474e3cd533a2f952a0fb998f1867e57d27f",
        "yt": "0xfb2d72fc9c378a73b4e03abac48194367447fa5a",
        "pt": "0x72b8e8c226848ceb35ba51d193f4f962dee957c1",
        "accounting": "0xba46fc84409589f369c107e869c06809df3d9727",
        "expiry": "2026-09-17",
        "delta_apy_alert": 5.0,      # 500 bps (since base APY is >10,000%)
        "delta_spot_pct": 1.5,       # 1.5% spot move
        "delta_liq_pct": 5.0         # 5% liquidity shift
    }
}

def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_market_state(m_key, m_cfg, user_orders, all_incentives):
    m_addr = m_cfg["market"].lower()
    yt_addr = m_cfg["yt"].lower()
    
    # 1. Market metrics
    m_url = f"{BASE_API}/v1/{CHAIN_ID}/markets/{m_addr}"
    market = fetch_json(m_url)

    implied_apy = (market.get("impliedApy") or 0.0) * 100.0
    underlying_apy = (market.get("underlyingApy") or 0.0) * 100.0
    spot_price = market.get("accountingAsset", {}).get("price", {}).get("usd", 0.0)
    pt_price = market.get("pt", {}).get("price", {}).get("usd", 0.0)
    yt_price = market.get("yt", {}).get("price", {}).get("usd", 0.0)
    liquidity_usd = (market.get("liquidity") or {}).get("usd", 0.0) if isinstance(market.get("liquidity"), dict) else 0.0

    # 2. Incentive configs & bounds
    nvda_cfg = next((c for c in all_incentives if c.get("chainId") == CHAIN_ID and c.get("marketAddress", "").lower() == m_addr), {})
    min_apy = (nvda_cfg.get("minApy") or 0.0) * 100.0
    max_apy = (nvda_cfg.get("maxApy") or 0.0) * 100.0
    buy_pt_apr = (nvda_cfg.get("estimatedApr", {}).get("buyPtApr") or 0.0) * 100.0
    buy_yt_apr = (nvda_cfg.get("estimatedApr", {}).get("buyYtApr") or 0.0) * 100.0

    # 3. User split & maker competition
    split_url = f"{BASE_API}/v1/limit-orders/incentive/user/split?chainId={CHAIN_ID}&marketAddress={m_addr}&user={WALLET}"
    split_data = fetch_json(split_url)
    short_depth = split_data.get("short", {}).get("totalMakingAmountInRange", 0.0)
    long_depth = split_data.get("long", {}).get("totalMakingAmountInRange", 0.0)
    reward_per_hr = split_data.get("short", {}).get("totalRewardPerHour", 0.0) or split_data.get("long", {}).get("totalRewardPerHour", 0.0)

    # 4. User's resting limit order status
    active_order = next((o for o in user_orders if o.get("yt", "").lower() == yt_addr and o.get("isActive", False)), None)
    order_info = None
    if active_order:
        raw_ln = int(active_order.get("lnImpliedRate", 0)) / 1e18
        order_apy = (math.exp(raw_ln) - 1.0) * 100.0
        making_amt = int(active_order.get("currentMakingAmount", 0)) / 1e18
        filled_status = active_order.get("orderFilledStatus", {})
        net_output = int(filled_status.get("netOutputToMaker", 0)) / 1e18
        net_input = int(filled_status.get("netInputFromMaker", 0)) / 1e18

        order_info = {
            "id": active_order.get("id"),
            "apy": order_apy,
            "making_amt": making_amt,
            "net_output": net_output,
            "net_input": net_input,
            "status": active_order.get("status")
        }

    return {
        "market_key": m_key,
        "implied_apy": implied_apy,
        "underlying_apy": underlying_apy,
        "spot_price": spot_price,
        "pt_price": pt_price,
        "yt_price": yt_price,
        "liquidity_usd": liquidity_usd,
        "min_apy": min_apy,
        "max_apy": max_apy,
        "buy_pt_apr": buy_pt_apr,
        "buy_yt_apr": buy_yt_apr,
        "reward_per_hr": reward_per_hr,
        "short_depth": short_depth,
        "long_depth": long_depth,
        "order": order_info
    }

def get_all_markets_state():
    user_orders = fetch_json(f"{BASE_API}/v2/limit-orders?chainId={CHAIN_ID}&maker={WALLET}").get("results", [])
    all_incentives = fetch_json(f"{BASE_API}/v1/limit-orders/incentive/configs").get("configs", [])

    results = {}
    for m_key, m_cfg in WATCHLIST.items():
        try:
            results[m_key] = get_market_state(m_key, m_cfg, user_orders, all_incentives)
        except Exception as e:
            print(f"Error fetching state for {m_key}: {e}")
    return results

def load_previous_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def save_current_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Error saving state: {e}")

def check_market_moves(m_key, current, prev):
    m_cfg = WATCHLIST[m_key]
    alerts = []

    # 1. Implied APY Shift
    delta_implied = current["implied_apy"] - prev["implied_apy"]
    if abs(delta_implied) >= m_cfg["delta_apy_alert"]:
        direction = "📈 SPIKED" if delta_implied > 0 else "📉 DROPPED"
        alerts.append(
            f"<b>Implied APY Move ({direction}):</b>\n"
            f"  • Current: <code>{current['implied_apy']:.2f}%</code>\n"
            f"  • Previous: <code>{prev['implied_apy']:.2f}%</code>\n"
            f"  • Delta: <b>{delta_implied:+.2f}%</b>"
        )

    # 2. Spot Price Jump
    prev_spot = prev["spot_price"]
    if prev_spot > 0:
        pct_spot = (current["spot_price"] - prev_spot) / prev_spot * 100.0
        if abs(pct_spot) >= m_cfg["delta_spot_pct"]:
            direction = "🟢 SURGED" if pct_spot > 0 else "🔴 DUMPED"
            alerts.append(
                f"<b>Underlying Spot Price {direction}:</b>\n"
                f"  • Current: <code>${current['spot_price']:.2f}</code>\n"
                f"  • Previous: <code>${prev_spot:.2f}</code>\n"
                f"  • Move: <b>{pct_spot:+.2f}%</b> (${current['spot_price'] - prev_spot:+.2f})"
            )

    # 3. Pool Liquidity Shock
    prev_liq = prev["liquidity_usd"]
    if prev_liq > 0:
        pct_liq = (current["liquidity_usd"] - prev_liq) / prev_liq * 100.0
        if abs(pct_liq) >= m_cfg["delta_liq_pct"]:
            alerts.append(
                f"<b>Pool Liquidity Shock:</b>\n"
                f"  • Current: <code>${current['liquidity_usd']:,.0f}</code>\n"
                f"  • Delta: <b>{pct_liq:+.1f}%</b> (${current['liquidity_usd'] - prev_liq:+,.0f})"
            )

    # 4. User Order Status & Band Alignment
    cur_order = current.get("order")
    if cur_order:
        order_apy = cur_order["apy"]
        min_band = current["min_apy"]
        max_band = current["max_apy"]
        is_in_band = min_band <= order_apy <= max_band
        prev_in_band = prev.get("min_apy", 0) <= prev.get("order", {}).get("apy", 0) <= prev.get("max_apy", 999) if prev.get("order") else True

        if not is_in_band and prev_in_band:
            alerts.append(
                f"🚨 <b>Order Drifted OUT-OF-RANGE!</b>\n"
                f"  • Your Order Rate: <code>{order_apy:.2f}%</code>\n"
                f"  • Current Band: <code>[{min_band:.2f}%, {max_band:.2f}%]</code>\n"
                f"  • Action Required: Re-center to continue mining rewards."
            )
        elif is_in_band:
            dist_to_min = order_apy - min_band
            dist_to_max = max_band - order_apy
            if (dist_to_min < 0.10 or dist_to_max < 0.10) and abs(delta_implied) >= 0.10:
                alerts.append(
                    f"⚠️ <b>Incentive Band Compression Alert:</b>\n"
                    f"  • Order Rate: <code>{order_apy:.2f}%</code>\n"
                    f"  • Eligible Band: <code>[{min_band:.2f}%, {max_band:.2f}%]</code>\n"
                    f"  • Resting near edge threshold."
                )

        # 5. Order Fill Detection
        prev_order = prev.get("order")
        if prev_order:
            delta_filled = cur_order["net_output"] - prev_order["net_output"]
            if delta_filled > 0:
                alerts.append(
                    f"🎯 <b>LIMIT ORDER FILL DETECTED!</b>\n"
                    f"  • Market: {m_key} ({m_cfg['expiry']})\n"
                    f"  • Filled Size: <b>{delta_filled:.4f}</b>\n"
                    f"  • Total Received: <code>{cur_order['net_output']:.4f}</code>\n"
                    f"  • Remaining Making: <code>{cur_order['making_amt']:.4f}</code>"
                )

    # 6. Maker Competition Influx
    if prev.get("short_depth", 0.0) == 0.0 and current["short_depth"] > 200.0:
        alerts.append(
            f"⚔️ <b>Competitor Influx on Short Side:</b>\n"
            f"  • Short depth jumped from $0.00 to <code>${current['short_depth']:,.2f}</code>.\n"
            f"  • Reward pool dilution active."
        )

    return alerts

def inspect_all_and_alert(current_states, prev_states):
    now_str = datetime.now(timezone.utc).strftime('%H:%M:%S UTC')
    
    if prev_states is None:
        print(f"[{now_str}] Initial baseline recorded for {list(current_states.keys())}.")
        save_current_state(current_states)
        return

    all_alerts = []
    for m_key, cur in current_states.items():
        prev = prev_states.get(m_key)
        if not prev:
            continue
        m_alerts = check_market_moves(m_key, cur, prev)
        if m_alerts:
            header = f"🦅 <b>[{m_key} MARKET RADAR ALERT]</b>\n"
            all_alerts.append(header + "\n\n".join(m_alerts))

    if all_alerts:
        full_msg = f"🦅 <b>[PENDLE V2 ROBINHOOD RADAR] Activity Detected ({now_str})</b>\n\n" + "\n\n---\n\n".join(all_alerts)
        print("\n>>> DISPATCHING TELEGRAM ALERT <<<")
        print(full_msg)
        send_telegram_alert(full_msg)
    else:
        status_line = " | ".join([
            f"{k}: Implied {v['implied_apy']:.1f}% (Spot: ${v['spot_price']:.2f}, In-Band: {v['min_apy'] <= (v.get('order') or {}).get('apy', -999) <= v['max_apy'] if v.get('order') else 'NoOrder'})"
            for k, v in current_states.items()
        ])
        print(f"[{now_str}] Markets stable. {status_line}")

    save_current_state(current_states)

def main():
    parser = argparse.ArgumentParser(description="Multi-Market Robinhood Monitor (NVDA + sNET)")
    parser.add_argument("--once", action="store_true", help="Run a single inspection cycle and exit")
    parser.add_argument("--loop", action="store_true", help="Run continuously in background daemon mode")
    parser.add_argument("--interval", type=int, default=60, help="Check interval in seconds (default: 60s)")
    parser.add_argument("--test-alert", action="store_true", help="Force send a test alert with live market status")
    args = parser.parse_args()

    if args.test_alert:
        states = get_all_markets_state()
        lines = []
        for k, s in states.items():
            order_s = f"{s['order']['apy']:.2f}% ({s['order']['making_amt']:.4f})" if s.get("order") else "None"
            lines.append(
                f"• <b>{k} ({WATCHLIST[k]['expiry']}):</b>\n"
                f"  - Implied APY: <code>{s['implied_apy']:.2f}%</code>\n"
                f"  - Underlying APY: <code>{s['underlying_apy']:.2f}%</code>\n"
                f"  - Spot Price: <code>${s['spot_price']:.2f}</code> | YT: <code>${s['yt_price']:.2f}</code> | PT: <code>${s['pt_price']:.2f}</code>\n"
                f"  - Liquidity: <code>${s['liquidity_usd']:,.0f}</code>\n"
                f"  - Incentive Band: <code>[{s['min_apy']:.2f}%, {s['max_apy']:.2f}%]</code>\n"
                f"  - Hourly Reward Pool: <code>{s['reward_per_hr']:.4f} PENDLE/hr</code>\n"
                f"  - Short Maker Depth: <code>${s['short_depth']:,.2f}</code>\n"
                f"  - My Active Order: <code>{order_s}</code>"
            )
        msg = f"🦅 <b>[PENDLE V2 RADAR: MULTI-MARKET RADAR TEST]</b>\n\n" + "\n\n".join(lines) + "\n\n✅ <i>Both NVDA & sNET actively monitored.</i>"
        send_telegram_alert(msg)
        save_current_state(states)
        return

    if args.once or not args.loop:
        prev = load_previous_state()
        current = get_all_markets_state()
        inspect_all_and_alert(current, prev)
        return

    print(f"Starting Multi-Market Robinhood Monitor Daemon (Interval: {args.interval}s, Markets: {list(WATCHLIST.keys())})...")
    while True:
        try:
            prev = load_previous_state()
            current = get_all_markets_state()
            inspect_all_and_alert(current, prev)
        except Exception as e:
            print(f"Error in monitor loop: {e}")
        time.sleep(args.interval)

if __name__ == "__main__":
    main()
