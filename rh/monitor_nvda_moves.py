#!/usr/bin/env python3
"""
Pendle V2 - NVDA Market Big Move & Order Fill Monitor
Monitors Robinhood Chain (4663) NVDA Market (0x206a5cd00e9ffabb8ca564076b64799a78df19b9).
Dispatches immediate Telegram alerts when significant moves occur:
  - Implied APY shifts >= 0.25%
  - Spot NVDA moves >= 1.0%
  - Pool Liquidity shocks >= 5.0%
  - Incentive band drift (approaching boundaries or falling out-of-range)
  - Limit Order Fills (partial or full fills detected)
  - Competitor maker depth entry on short side

Usage:
  python rh/monitor_nvda_moves.py --once
  python rh/monitor_nvda_moves.py --loop --interval 60
"""

import os
import sys
import time
import json
import argparse
import urllib.request
from datetime import datetime

# Local imports
sys.path.append(os.path.dirname(__file__))
from alerter import send_telegram_alert

CHAIN_ID = 4663
NVDA_MARKET = "0x206a5cd00e9ffabb8ca564076b64799a78df19b9"
NVDA_YT = "0x9cc22e51c6f0cb4aa1bfd1f18e85df1451ebb9b3"
WALLET = "0xaa7c405151c1a11fc2e9998a31b285c7b53d248b".lower()

BASE_API = "https://api-v2.pendle.finance/core"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
STATE_FILE = os.path.join(os.path.dirname(__file__), "nvda_monitor_state.json")

# Alert Thresholds
DELTA_IMPLIED_APY_ALERT = 0.25      # 25 bps shift in Implied APY
DELTA_SPOT_PRICE_PCT_ALERT = 1.0    # 1.0% move in underlying NVDA equity price
DELTA_LIQUIDITY_PCT_ALERT = 5.0     # 5.0% change in pool liquidity

def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_nvda_market_state():
    """Queries comprehensive live NVDA market and incentive data."""
    # 1. Market metrics
    m_url = f"{BASE_API}/v1/{CHAIN_ID}/markets/{NVDA_MARKET}"
    market = fetch_json(m_url)

    implied_apy = (market.get("impliedApy") or 0.0) * 100.0
    underlying_apy = (market.get("underlyingApy") or 0.0) * 100.0
    spot_price = market.get("accountingAsset", {}).get("price", {}).get("usd", 0.0)
    pt_price = market.get("pt", {}).get("price", {}).get("usd", 0.0)
    yt_price = market.get("yt", {}).get("price", {}).get("usd", 0.0)
    liquidity_usd = (market.get("liquidity") or {}).get("usd", 0.0) if isinstance(market.get("liquidity"), dict) else 0.0

    # 2. Incentive configs & bounds
    configs = fetch_json(f"{BASE_API}/v1/limit-orders/incentive/configs").get("configs", [])
    nvda_cfg = next((c for c in configs if c.get("chainId") == CHAIN_ID and c.get("marketAddress", "").lower() == NVDA_MARKET.lower()), {})
    min_apy = (nvda_cfg.get("minApy") or 0.0) * 100.0
    max_apy = (nvda_cfg.get("maxApy") or 0.0) * 100.0
    buy_pt_apr = (nvda_cfg.get("estimatedApr", {}).get("buyPtApr") or 0.0) * 100.0

    # 3. User split & maker competition
    split_url = f"{BASE_API}/v1/limit-orders/incentive/user/split?chainId={CHAIN_ID}&marketAddress={NVDA_MARKET}&user={WALLET}"
    split_data = fetch_json(split_url)
    short_depth = split_data.get("short", {}).get("totalMakingAmountInRange", 0.0)
    long_depth = split_data.get("long", {}).get("totalMakingAmountInRange", 0.0)

    # 4. User's resting limit order status
    orders_url = f"{BASE_API}/v2/limit-orders?chainId={CHAIN_ID}&maker={WALLET}"
    orders = fetch_json(orders_url).get("results", [])
    active_order = next((o for o in orders if o.get("yt", "").lower() == NVDA_YT.lower() and o.get("isActive", False)), None)

    order_info = None
    if active_order:
        raw_ln = int(active_order.get("lnImpliedRate", 0)) / 1e18
        import math
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
        "timestamp": time.time(),
        "implied_apy": implied_apy,
        "underlying_apy": underlying_apy,
        "spot_price": spot_price,
        "pt_price": pt_price,
        "yt_price": yt_price,
        "liquidity_usd": liquidity_usd,
        "min_apy": min_apy,
        "max_apy": max_apy,
        "buy_pt_apr": buy_pt_apr,
        "short_depth": short_depth,
        "long_depth": long_depth,
        "order": order_info
    }

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

def check_for_big_moves_and_alert(current, prev):
    alerts = []

    if prev is None:
        print("Initial state recorded. Monitoring will compare from next cycle.")
        save_current_state(current)
        return

    # 1. Implied APY Shift
    delta_implied = current["implied_apy"] - prev["implied_apy"]
    if abs(delta_implied) >= DELTA_IMPLIED_APY_ALERT:
        direction = "📈 SPIKED UP" if delta_implied > 0 else "📉 DROPPED DOWN"
        alerts.append(
            f"<b>Implied APY Move ({direction}):</b>\n"
            f"  • Current: <code>{current['implied_apy']:.2f}%</code>\n"
            f"  • Previous: <code>{prev['implied_apy']:.2f}%</code>\n"
            f"  • Delta: <b>{delta_implied:+.2f}%</b>"
        )

    # 2. Spot NVDA Price Jump
    prev_spot = prev["spot_price"]
    if prev_spot > 0:
        pct_spot = (current["spot_price"] - prev_spot) / prev_spot * 100.0
        if abs(pct_spot) >= DELTA_SPOT_PRICE_PCT_ALERT:
            direction = "🟢 SURGED" if pct_spot > 0 else "🔴 DUMPED"
            alerts.append(
                f"<b>NVDA Spot Price {direction}:</b>\n"
                f"  • Current: <code>${current['spot_price']:.2f}</code>\n"
                f"  • Previous: <code>${prev_spot:.2f}</code>\n"
                f"  • Move: <b>{pct_spot:+.2f}%</b> (${current['spot_price'] - prev_spot:+.2f})"
            )

    # 3. Pool Liquidity Shock
    prev_liq = prev["liquidity_usd"]
    if prev_liq > 0:
        pct_liq = (current["liquidity_usd"] - prev_liq) / prev_liq * 100.0
        if abs(pct_liq) >= DELTA_LIQUIDITY_PCT_ALERT:
            alerts.append(
                f"<b>Pool Liquidity Shock:</b>\n"
                f"  • Current: <code>${current['liquidity_usd']:,.0f}</code>\n"
                f"  • Delta: <b>{pct_liq:+.1f}%</b> (${current['liquidity_usd'] - prev_liq:+,.0f})"
            )

    # 4. Incentive Band Drift / Out-of-Range Risk
    cur_order = current.get("order")
    if cur_order:
        order_apy = cur_order["apy"]
        min_band = current["min_apy"]
        max_band = current["max_apy"]
        
        is_in_band = min_band <= order_apy <= max_band
        prev_in_band = prev.get("min_apy", 0) <= prev.get("order", {}).get("apy", 0) <= prev.get("max_apy", 999) if prev.get("order") else True

        if not is_in_band and prev_in_band:
            alerts.append(
                f"🚨 <b>CRITICAL: Order Drifted OUT-OF-RANGE!</b>\n"
                f"  • Your Order Rate: <code>{order_apy:.2f}%</code>\n"
                f"  • Current Band: <code>[{min_band:.2f}%, {max_band:.2f}%]</code>\n"
                f"  • Warning: Order earning <b>0 PENDLE/hr</b> until re-centered!"
            )
        elif is_in_band:
            # Check if close to boundary (within 10 bps)
            dist_to_min = order_apy - min_band
            dist_to_max = max_band - order_apy
            if (dist_to_min < 0.10 or dist_to_max < 0.10) and abs(delta_implied) >= 0.10:
                alerts.append(
                    f"⚠️ <b>Incentive Band Compression Alert:</b>\n"
                    f"  • Order Rate: <code>{order_apy:.2f}%</code>\n"
                    f"  • Eligible Band: <code>[{min_band:.2f}%, {max_band:.2f}%]</code>\n"
                    f"  • Warning: Resting near boundary threshold."
                )

        # 5. Order Fill Detection
        prev_order = prev.get("order")
        if prev_order:
            delta_filled = cur_order["net_output"] - prev_order["net_output"]
            if delta_filled > 0:
                alerts.append(
                    f"🎯 <b>LIMIT ORDER FILL DETECTED!</b>\n"
                    f"  • Market: NVDA (15-OCT-2026)\n"
                    f"  • Filled Amount: <b>{delta_filled:.4f}</b>\n"
                    f"  • Total Received: <code>{cur_order['net_output']:.4f}</code>\n"
                    f"  • Remaining Size: <code>{cur_order['making_amt']:.4f} NVDA</code>"
                )

    # 6. Maker Competition Influx on Short Side
    if prev.get("short_depth", 0.0) == 0.0 and current["short_depth"] > 200.0:
        alerts.append(
            f"⚔️ <b>Competitor Influx on Short Side:</b>\n"
            f"  • Maker depth jumped from $0.00 to <code>${current['short_depth']:,.2f}</code>.\n"
            f"  • Incentive reward dilution active."
        )

    # Dispatch alerts if any triggered
    if alerts:
        header = (
            f"🦅 <b>[PENDLE V2 RADAR] Big Move in NVDA Market!</b>\n"
            f"• <b>Chain:</b> Robinhood (4663)\n"
            f"• <b>Time:</b> {datetime.utcnow().strftime('%H:%M:%S UTC')}\n\n"
        )
        body = "\n\n".join(alerts)
        full_msg = header + body
        print("\n>>> DISPATCHING TELEGRAM ALERT <<<")
        print(full_msg)
        send_telegram_alert(full_msg)
    else:
        print(f"[{datetime.utcnow().strftime('%H:%M:%S')}] NVDA Market stable. Implied: {current['implied_apy']:.2f}% | Spot: ${current['spot_price']:.2f} | Order in-band: {min_band <= cur_order['apy'] <= max_band if cur_order else 'N/A'}")

    save_current_state(current)

def main():
    parser = argparse.ArgumentParser(description="Monitor NVDA Market Big Moves & Order Fills")
    parser.add_argument("--once", action="store_true", help="Run a single inspection cycle and exit")
    parser.add_argument("--loop", action="store_true", help="Run continuously in background daemon mode")
    parser.add_argument("--interval", type=int, default=60, help="Check interval in seconds (default: 60s)")
    parser.add_argument("--test-alert", action="store_true", help="Force send a test alert with live market status")
    args = parser.parse_args()

    if args.test_alert:
        state = get_nvda_market_state()
        cur_order = state.get("order")
        order_str = f"{cur_order['apy']:.2f}% ({cur_order['making_amt']:.4f} NVDA)" if cur_order else "None"
        msg = (
            f"🦅 <b>[PENDLE V2 RADAR: TEST ALERT]</b>\n\n"
            f"• <b>Market:</b> NVDA (Oct 15, 2026)\n"
            f"• <b>Network:</b> Robinhood Chain (`4663`)\n"
            f"• <b>Spot NVDA:</b> ${state['spot_price']:.2f}\n"
            f"• <b>Implied APY:</b> {state['implied_apy']:.2f}%\n"
            f"• <b>Underlying Yield:</b> {state['underlying_apy']:.2f}%\n"
            f"• <b>Incentive Band:</b> [{state['min_apy']:.2f}%, {state['max_apy']:.2f}%]\n"
            f"• <b>My Active Order:</b> {order_str}\n"
            f"• <b>Short Maker Depth:</b> ${state['short_depth']:,.2f}\n\n"
            f"✅ <i>Monitor active and listening for rate/spot wicks.</i>"
        )
        send_telegram_alert(msg)
        save_current_state(state)
        return

    if args.once or not args.loop:
        prev = load_previous_state()
        current = get_nvda_market_state()
        check_for_big_moves_and_alert(current, prev)
        return

    # Loop Daemon Mode
    print(f"Starting NVDA Big Move Monitor Daemon (Interval: {args.interval}s)...")
    while True:
        try:
            prev = load_previous_state()
            current = get_nvda_market_state()
            check_for_big_moves_and_alert(current, prev)
        except Exception as e:
            print(f"Error in monitor loop: {e}")
        time.sleep(args.interval)

if __name__ == "__main__":
    main()
