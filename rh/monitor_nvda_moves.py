#!/usr/bin/env python3
"""
Pendle V2 - Robinhood Chain Multi-Market Big Move & Order Fill Monitor
Monitors active watch markets on Robinhood Chain (4663):
  1. NVDA (15-OCT-2026): 0x206a5cd00e9ffabb8ca564076b64799a78df19b9
  2. sNET (17-SEP-2026): 0x23c68474e3cd533a2f952a0fb998f1867e57d27f
  3. sNUKE (24-SEP-2026): 0x8547b391a65deb89c41a4c3b2eb1502d0bbc566a
  4. PFE (10-DEC-2026):  0x892defbf510d9baa96dbd2a51b13e879a857a79b

Noise Reduction & Signal Optimization:
  - High-Signal Priority: Limit order fills and out-of-band drifts are dispatched immediately.
  - Position-Aware Filtering: Sensitive alerts for markets with active capital; high macro thresholds for background markets.
  - Relative APY Scaling: Avoids spamming on minor basis wiggles in hyper-yield pools (e.g. sNET 13,000%).
  - Cooldown & Debouncing: 30-minute cooldown and anchored baselines prevent oscillation ping-pongs.
  - Structured Heartbeat: 1-hour heartbeat ping reporting health, resting orders, and gas runway.

Usage:
  python rh/monitor_nvda_moves.py --loop --interval 60 --heartbeat-interval 3600
  python rh/monitor_nvda_moves.py --once
  python rh/monitor_nvda_moves.py --test-heartbeat
"""

import os
import sys
import time
import math
import json
import signal
import socket
import argparse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from web3 import Web3

# Local package imports
RH_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(RH_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)
if RH_DIR not in sys.path:
    sys.path.insert(0, RH_DIR)

from alerter import send_telegram_alert
from gas_governor import get_gas_metrics

CHAIN_ID = 4663
RPC_URL = "https://rpc.mainnet.chain.robinhood.com"
WALLET = "0xaa7c405151c1a11fc2e9998a31b285c7b53d248b".lower()
BASE_API = "https://api-v2.pendle.finance/core"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
STATE_FILE = os.path.join(RH_DIR, "rh_markets_state.json")
TRACKER_FILE = os.path.join(RH_DIR, "rh_alert_tracker.json")

# Monitored Markets on Robinhood Chain
WATCHLIST = {
    "NVDA": {
        "market": "0x206a5cd00e9ffabb8ca564076b64799a78df19b9",
        "yt": "0x9cc22e51c6f0cb4aa1bfd1f18e85df1451ebb9b3",
        "pt": "0x4bcb25fce9618e62e9f9fba8d65af50cf867b812",
        "accounting": "0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec",
        "expiry": "2026-10-15"
    },
    "sNET": {
        "market": "0x23c68474e3cd533a2f952a0fb998f1867e57d27f",
        "yt": "0xfb2d72fc9c378a73b4e03abac48194367447fa5a",
        "pt": "0x72b8e8c226848ceb35ba51d193f4f962dee957c1",
        "accounting": "0xba46fc84409589f369c107e869c06809df3d9727",
        "expiry": "2026-09-17"
    },
    "sNUKE": {
        "market": "0x8547b391a65deb89c41a4c3b2eb1502d0bbc566a",
        "yt": "0xe32a6d0356d080d9dd8c0bd8e7ab3f464b3f1dbc",
        "pt": "0xb06180609b22973bee751a6c833db4821f8476fb",
        "accounting": "0xcd7079e32bf53093f60bf973c28e5d72937c12f2",
        "expiry": "2026-09-24"
    },
    "PFE": {
        "market": "0x892defbf510d9baa96dbd2a51b13e879a857a79b",
        "yt": "0x7600d0a61f83d7e4c4154c4664b19be6d9acf180",
        "pt": "0xf9cd484f7e7799ae32b7f9a75e60c478fd1f0b6e",
        "accounting": "0x7066a64c24e4206cd62e83bf198c1e7eb361f51e",
        "expiry": "2026-12-10"
    }
}

# Global lifecycle state
START_TIME = time.time()
LOOP_COUNT = 0
SHUTDOWN_TRIGGERED = False

def fetch_json(url: str) -> Any:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def fetch_gas_status() -> Dict[str, Any]:
    try:
        w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 8}))
        return get_gas_metrics(w3, WALLET)
    except Exception as e:
        return {
            "eth_balance": 0.0,
            "eth_balance_usd": 0.0,
            "cost_per_cancel_usd": 0.022,
            "runway_cancels": 0,
            "is_runway_critical": False
        }

def get_market_state(m_key: str, m_cfg: Dict[str, Any], user_orders: list, all_incentives: list) -> Dict[str, Any]:
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

def get_all_markets_state() -> Dict[str, Any]:
    user_orders = fetch_json(f"{BASE_API}/v2/limit-orders?chainId={CHAIN_ID}&maker={WALLET}").get("results", [])
    all_incentives = fetch_json(f"{BASE_API}/v1/limit-orders/incentive/configs").get("configs", [])

    results = {}
    for m_key, m_cfg in WATCHLIST.items():
        try:
            results[m_key] = get_market_state(m_key, m_cfg, user_orders, all_incentives)
        except Exception as e:
            print(f"Error fetching state for {m_key}: {e}")
    return results

def load_previous_state() -> Optional[Dict[str, Any]]:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return None
    return None

def save_current_state(state: Dict[str, Any]):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Error saving state: {e}")

# -----------------------------------------------------------------------------
# NOISE SUPPRESSION & COOLDOWN TRACKER
# -----------------------------------------------------------------------------
def load_alert_tracker() -> Dict[str, Any]:
    if os.path.exists(TRACKER_FILE):
        try:
            with open(TRACKER_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"timestamps": {}, "baselines": {}}

def save_alert_tracker(tracker: Dict[str, Any]):
    try:
        with open(TRACKER_FILE, "w") as f:
            json.dump(tracker, f, indent=2)
    except Exception as e:
        print(f"Error saving alert tracker: {e}")

ALERT_TRACKER = load_alert_tracker()

def should_alert(event_key: str, cooldown_seconds: int = 1800) -> bool:
    """Returns True if the cooldown window has elapsed for this specific alert event."""
    now = time.time()
    last = ALERT_TRACKER.get("timestamps", {}).get(event_key, 0)
    return (now - last) >= cooldown_seconds

def record_alert(event_key: str, baseline_val: Optional[float] = None):
    """Records the timestamp and updated anchor baseline for an event."""
    now = time.time()
    ALERT_TRACKER.setdefault("timestamps", {})[event_key] = now
    if baseline_val is not None:
        ALERT_TRACKER.setdefault("baselines", {})[event_key] = baseline_val
    save_alert_tracker(ALERT_TRACKER)

def get_alert_baseline(event_key: str, fallback: float) -> float:
    return ALERT_TRACKER.get("baselines", {}).get(event_key, fallback)

# -----------------------------------------------------------------------------
# LIFECYCLE ALERTS (STARTUP, HEARTBEAT, SHUTDOWN)
# -----------------------------------------------------------------------------
def send_startup_alert(states: Dict[str, Any], interval: int, heartbeat_interval: int):
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    host = socket.gethostname()
    gas = fetch_gas_status()

    market_lines = []
    for k, s in states.items():
        band_str = f"[{s['min_apy']:.2f}%, {s['max_apy']:.2f}%]"
        if s.get("order"):
            o = s["order"]
            in_b = s["min_apy"] <= o["apy"] <= s["max_apy"]
            b_tag = "✅ IN-BAND" if in_b else "⚠️ OUT-OF-BAND"
            ord_str = f"Order: <code>{o['apy']:.2f}%</code> ({o['making_amt']:.3f} {k}) {b_tag}"
        else:
            ord_str = "No active order"
        market_lines.append(f"  • <b>{k}:</b> Rate: <code>{s['implied_apy']:.2f}%</code> | Band: <code>{band_str}</code>\n    └─ {ord_str}")

    msg = (
        f"🚀 <b>[PENDLE V2 DESK MONITOR STARTED]</b>\n\n"
        f"• <b>Host:</b> <code>{host}</code> | <b>PID:</b> <code>{os.getpid()}</code>\n"
        f"• <b>Network:</b> Robinhood Chain (ID: <code>4663</code>)\n"
        f"• <b>Wallet:</b> <code>{WALLET[:8]}...{WALLET[-6:]}</code>\n"
        f"• <b>ETH Gas Runway:</b> <code>{gas['eth_balance']:.6f} ETH</code> (~{gas['runway_cancels']:,} cancels)\n"
        f"• <b>Scan Interval:</b> {interval}s | <b>Heartbeat:</b> every {heartbeat_interval//60}m\n\n"
        f"<b>Monitored Markets ({len(states)}):</b>\n" +
        "\n".join(market_lines) +
        f"\n\n🕒 <i>Initialized at {now_str}</i>"
    )
    print("\n>>> DISPATCHING STARTUP ALERT <<<")
    send_telegram_alert(msg)

def send_shutdown_alert(start_time: float, loop_count: int, reason: str = "Manual Stop"):
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    host = socket.gethostname()
    uptime_sec = int(time.time() - start_time)
    hours, rem = divmod(uptime_sec, 3600)
    minutes, seconds = divmod(rem, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"

    msg = (
        f"⏹️ <b>[PENDLE V2 DESK MONITOR STOPPED]</b>\n\n"
        f"• <b>Host:</b> <code>{host}</code> | <b>PID:</b> <code>{os.getpid()}</code>\n"
        f"• <b>Uptime:</b> <code>{uptime_str}</code>\n"
        f"• <b>Inspection Cycles:</b> {loop_count:,}\n"
        f"• <b>Reason:</b> {reason}\n"
        f"• <b>Timestamp:</b> {now_str}\n\n"
        f"⚠️ <i>Radar monitoring is currently inactive.</i>"
    )
    print("\n>>> DISPATCHING SHUTDOWN ALERT <<<")
    send_telegram_alert(msg)

def send_heartbeat_alert(states: Dict[str, Any], start_time: float, loop_count: int):
    now_str = datetime.now(timezone.utc).strftime('%H:%M:%S UTC')
    host = socket.gethostname()
    uptime_sec = int(time.time() - start_time)
    hours, rem = divmod(uptime_sec, 3600)
    minutes, _ = divmod(rem, 60)
    uptime_str = f"{hours}h {minutes}m"
    gas = fetch_gas_status()

    market_lines = []
    active_order_count = 0
    for k, s in states.items():
        band = f"[{s['min_apy']:.1f}%, {s['max_apy']:.1f}%]"
        if s.get("order"):
            active_order_count += 1
            o = s["order"]
            in_b = s["min_apy"] <= o["apy"] <= s["max_apy"]
            b_tag = "✅ IN-BAND" if in_b else "⚠️ DRIFTED"
            ord_str = f"Order: <code>{o['apy']:.2f}%</code> ({o['making_amt']:.3f} {k}) {b_tag}"
        else:
            ord_str = "No active order"
        market_lines.append(f"  • <b>{k}:</b> Rate: <code>{s['implied_apy']:.2f}%</code> | Band: <code>{band}</code> | Spot: ${s['spot_price']:.2f}\n    └─ {ord_str}")

    msg = (
        f"💓 <b>[PENDLE V2 DESK HEARTBEAT - ALIVE]</b>\n\n"
        f"• <b>Status:</b> All systems nominal & monitoring 24/7\n"
        f"• <b>Host:</b> <code>{host}</code> | <b>Uptime:</b> <code>{uptime_str}</code> | <b>Loops:</b> {loop_count:,}\n"
        f"• <b>ETH Gas Runway:</b> <code>{gas['eth_balance']:.6f} ETH</code> (~{gas['runway_cancels']:,} cancels)\n"
        f"• <b>Active Resting Orders:</b> {active_order_count} deployed\n\n"
        f"<b>Market Radar Snapshot:</b>\n" +
        "\n".join(market_lines) +
        f"\n\n🕒 <i>Heartbeat ping at {now_str}</i>"
    )
    print("\n>>> DISPATCHING HEARTBEAT ALERT <<<")
    send_telegram_alert(msg)

# -----------------------------------------------------------------------------
# HIGH-SIGNAL MARKET RADAR MOVE DETECTION (ZERO-NOISE OPTIMIZED)
# -----------------------------------------------------------------------------
def check_market_moves(m_key: str, current: Dict[str, Any], prev: Dict[str, Any]) -> list:
    m_cfg = WATCHLIST[m_key]
    alerts = []
    cur_order = current.get("order")
    prev_order = prev.get("order") if prev else None
    has_active_order = bool(cur_order and cur_order.get("making_amt", 0) > 0)

    # -------------------------------------------------------------------------
    # 1. CRITICAL: LIMIT ORDER FILL DETECTION (Immediate, 0 Cooldown)
    # -------------------------------------------------------------------------
    if cur_order and prev_order:
        delta_filled = cur_order["net_output"] - prev_order["net_output"]
        if delta_filled > 0:
            alerts.append(
                f"🎯 <b>LIMIT ORDER FILL DETECTED!</b>\n"
                f"  • Market: <b>{m_key}</b> ({m_cfg['expiry']})\n"
                f"  • Filled Size: <b>{delta_filled:.4f}</b>\n"
                f"  • Total Received: <code>{cur_order['net_output']:.4f}</code>\n"
                f"  • Remaining Making: <code>{cur_order['making_amt']:.4f}</code>"
            )

    # -------------------------------------------------------------------------
    # 2. CRITICAL: ORDER DRIFT OUT-OF-RANGE & COMPRESSION (For Active Orders)
    # -------------------------------------------------------------------------
    if cur_order:
        order_apy = cur_order["apy"]
        min_band = current["min_apy"]
        max_band = current["max_apy"]
        is_in_band = min_band <= order_apy <= max_band
        prev_in_band = prev.get("min_apy", 0) <= prev.get("order", {}).get("apy", 0) <= prev.get("max_apy", 999) if prev_order else True

        drift_key = f"{m_key}:order_drift"
        if not is_in_band:
            # Immediate alert on transition, 30m reminder if still out
            if prev_in_band or should_alert(drift_key, cooldown_seconds=1800):
                alerts.append(
                    f"🚨 <b>Order Drifted OUT-OF-RANGE!</b>\n"
                    f"  • Market: <b>{m_key}</b>\n"
                    f"  • Your Order Rate: <code>{order_apy:.2f}%</code>\n"
                    f"  • Current Eligible Band: <code>[{min_band:.2f}%, {max_band:.2f}%]</code>\n"
                    f"  • Action Required: Re-center to continue mining rewards."
                )
                record_alert(drift_key)
        elif is_in_band:
            # Compression warning: resting within 10 bps of edge, throttled to 30 mins
            compress_key = f"{m_key}:band_compress"
            dist_to_min = order_apy - min_band
            dist_to_max = max_band - order_apy
            if (dist_to_min < 0.10 or dist_to_max < 0.10) and should_alert(compress_key, cooldown_seconds=1800):
                alerts.append(
                    f"⚠️ <b>Incentive Band Compression Alert:</b>\n"
                    f"  • Market: <b>{m_key}</b>\n"
                    f"  • Order Rate: <code>{order_apy:.2f}%</code>\n"
                    f"  • Eligible Band: <code>[{min_band:.2f}%, {max_band:.2f}%]</code>\n"
                    f"  • Warning: Order is resting within 10 bps of band boundary."
                )
                record_alert(compress_key)

    # -------------------------------------------------------------------------
    # 3. VOLATILITY RADAR: IMPLIED APY MOVES (Position-Aware & Relative-Scaled)
    # -------------------------------------------------------------------------
    apy_key = f"{m_key}:apy"
    baseline_apy = get_alert_baseline(apy_key, prev["implied_apy"] if prev else current["implied_apy"])
    cur_apy = current["implied_apy"]
    delta_apy = cur_apy - baseline_apy

    threshold_met = False
    if has_active_order:
        # Active market: sensitive to genuine moves
        if cur_apy > 100.0:
            rel_change = abs(delta_apy) / max(baseline_apy, 1.0) * 100.0
            threshold_met = rel_change >= 5.0  # 5% relative move
        else:
            threshold_met = abs(delta_apy) >= 0.50  # 50 bps absolute move
    else:
        # Background market: ONLY alert on major macro regime shifts
        if cur_apy > 100.0:
            rel_change = abs(delta_apy) / max(baseline_apy, 1.0) * 100.0
            threshold_met = rel_change >= 15.0  # 15% relative move (e.g. >1,800% shift on sNET)
        else:
            threshold_met = abs(delta_apy) >= 2.0  # 200 bps move

    if threshold_met and should_alert(apy_key, cooldown_seconds=1800):
        direction = "📈 SPIKED" if delta_apy > 0 else "📉 DROPPED"
        alerts.append(
            f"<b>Implied APY Move ({direction}):</b>\n"
            f"  • Market: <b>{m_key}</b>\n"
            f"  • Current APY: <code>{cur_apy:.2f}%</code>\n"
            f"  • Baseline APY: <code>{baseline_apy:.2f}%</code>\n"
            f"  • Delta: <b>{delta_apy:+.2f}%</b>"
        )
        record_alert(apy_key, baseline_val=cur_apy)

    # -------------------------------------------------------------------------
    # 4. VOLATILITY RADAR: SPOT PRICE MOVES (Position-Aware)
    # -------------------------------------------------------------------------
    spot_key = f"{m_key}:spot"
    prev_spot = prev["spot_price"] if prev else current["spot_price"]
    baseline_spot = get_alert_baseline(spot_key, prev_spot)
    cur_spot = current["spot_price"]

    if baseline_spot > 0:
        pct_spot = (cur_spot - baseline_spot) / baseline_spot * 100.0
        # Active order market: 3.0% threshold | Background market: 6.0% threshold
        spot_threshold = 3.0 if has_active_order else 6.0

        if abs(pct_spot) >= spot_threshold and should_alert(spot_key, cooldown_seconds=1800):
            direction = "🟢 SURGED" if pct_spot > 0 else "🔴 DUMPED"
            alerts.append(
                f"<b>Underlying Spot Price {direction}:</b>\n"
                f"  • Market: <b>{m_key}</b>\n"
                f"  • Current: <code>${cur_spot:.2f}</code>\n"
                f"  • Baseline: <code>${baseline_spot:.2f}</code>\n"
                f"  • Move: <b>{pct_spot:+.2f}%</b> (${cur_spot - baseline_spot:+.2f})"
            )
            record_alert(spot_key, baseline_val=cur_spot)

    # -------------------------------------------------------------------------
    # 5. POOL LIQUIDITY SHOCK (Threshold: 15% active, 25% background)
    # -------------------------------------------------------------------------
    liq_key = f"{m_key}:liq"
    prev_liq = prev["liquidity_usd"] if prev else current["liquidity_usd"]
    baseline_liq = get_alert_baseline(liq_key, prev_liq)
    cur_liq = current["liquidity_usd"]

    if baseline_liq > 0:
        pct_liq = (cur_liq - baseline_liq) / baseline_liq * 100.0
        liq_threshold = 15.0 if has_active_order else 25.0

        if abs(pct_liq) >= liq_threshold and should_alert(liq_key, cooldown_seconds=1800):
            alerts.append(
                f"<b>Pool Liquidity Shock:</b>\n"
                f"  • Market: <b>{m_key}</b>\n"
                f"  • Current: <code>${cur_liq:,.0f}</code>\n"
                f"  • Baseline: <code>${baseline_liq:,.0f}</code>\n"
                f"  • Delta: <b>{pct_liq:+.1f}%</b> (${cur_liq - baseline_liq:+,.0f})"
            )
            record_alert(liq_key, baseline_val=cur_liq)

    # -------------------------------------------------------------------------
    # 6. COMPETITOR INFLUX ON SHORT SIDE (Throttled to 1 hour)
    # -------------------------------------------------------------------------
    comp_key = f"{m_key}:competitor"
    prev_short_depth = prev.get("short_depth", 0.0) if prev else 0.0
    if prev_short_depth == 0.0 and current["short_depth"] > 200.0:
        if should_alert(comp_key, cooldown_seconds=3600):
            alerts.append(
                f"⚔️ <b>Competitor Influx on Short Side:</b>\n"
                f"  • Market: <b>{m_key}</b>\n"
                f"  • Short depth jumped from $0.00 to <code>${current['short_depth']:,.2f}</code>.\n"
                f"  • Reward pool dilution active."
            )
            record_alert(comp_key)

    return alerts

def inspect_all_and_alert(current_states: Dict[str, Any], prev_states: Optional[Dict[str, Any]]):
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
            f"{k}: Imp {v['implied_apy']:.1f}% (Spot: ${v['spot_price']:.2f}, In-Band: {v['min_apy'] <= (v.get('order') or {}).get('apy', -999) <= v['max_apy'] if v.get('order') else 'NoOrd'})"
            for k, v in current_states.items()
        ])
        print(f"[{now_str}] Markets stable. {status_line}")

    save_current_state(current_states)

# -----------------------------------------------------------------------------
# SIGNAL HANDLER
# -----------------------------------------------------------------------------
def setup_signal_handlers():
    def handle_signal(signum, frame):
        global SHUTDOWN_TRIGGERED
        if not SHUTDOWN_TRIGGERED:
            SHUTDOWN_TRIGGERED = True
            sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
            print(f"\n[!] Caught {sig_name}, sending graceful shutdown alert...")
            send_shutdown_alert(START_TIME, LOOP_COUNT, reason=f"Signal {sig_name}")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

def main():
    global START_TIME, LOOP_COUNT
    parser = argparse.ArgumentParser(description="Multi-Market Robinhood Monitor with Noise Suppression")
    parser.add_argument("--once", action="store_true", help="Run a single inspection cycle and exit")
    parser.add_argument("--loop", action="store_true", help="Run continuously in background daemon mode")
    parser.add_argument("--interval", type=int, default=60, help="Check interval in seconds (default: 60s)")
    parser.add_argument("--heartbeat-interval", type=int, default=3600, help="Heartbeat alert interval in seconds (default: 3600s / 1h)")
    parser.add_argument("--test-alert", action="store_true", help="Force send a test alert with live market status")
    parser.add_argument("--test-heartbeat", action="store_true", help="Force send a test heartbeat alert immediately")
    parser.add_argument("--test-startup", action="store_true", help="Force send a test startup alert immediately")
    parser.add_argument("--test-shutdown", action="store_true", help="Force send a test shutdown alert immediately")
    args = parser.parse_args()

    # Manual test triggers
    if args.test_heartbeat:
        states = get_all_markets_state()
        send_heartbeat_alert(states, time.time() - 3600, 60)
        return

    if args.test_startup:
        states = get_all_markets_state()
        send_startup_alert(states, args.interval, args.heartbeat_interval)
        return

    if args.test_shutdown:
        send_shutdown_alert(time.time() - 7200, 120, reason="Test Shutdown Trigger")
        return

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
        msg = f"🦅 <b>[PENDLE V2 RADAR: MULTI-MARKET RADAR TEST]</b>\n\n" + "\n\n".join(lines) + f"\n\n✅ <i>Tracking {len(states)} markets on Robinhood Chain.</i>"
        send_telegram_alert(msg)
        save_current_state(states)
        return

    # Single inspection cycle
    if args.once or not args.loop:
        prev = load_previous_state()
        current = get_all_markets_state()
        inspect_all_and_alert(current, prev)
        return

    # Daemon Loop Mode
    setup_signal_handlers()
    START_TIME = time.time()
    last_heartbeat_time = START_TIME

    print(f"🚀 Starting Multi-Market Robinhood Monitor Daemon (Noise-Filtered)...")
    print(f"   - Host:               {socket.gethostname()}")
    print(f"   - Scan Interval:      {args.interval}s")
    print(f"   - Heartbeat Interval: {args.heartbeat_interval}s ({args.heartbeat_interval//60} mins)")
    print(f"   - Monitored Markets:  {list(WATCHLIST.keys())}")
    print(f"   - Active Alert Filter: 30m Cooldowns & Position-Aware Thresholds Enabled")

    # Fetch initial state and send Startup Alert
    try:
        current = get_all_markets_state()
        prev = load_previous_state()
        inspect_all_and_alert(current, prev)
        send_startup_alert(current, args.interval, args.heartbeat_interval)
    except Exception as e:
        print(f"Warning during initial cycle: {e}")

    while True:
        try:
            time.sleep(args.interval)
            LOOP_COUNT += 1
            prev = load_previous_state()
            current = get_all_markets_state()
            inspect_all_and_alert(current, prev)

            # Check Heartbeat Trigger
            now = time.time()
            if (now - last_heartbeat_time) >= args.heartbeat_interval:
                send_heartbeat_alert(current, START_TIME, LOOP_COUNT)
                last_heartbeat_time = now

        except Exception as e:
            print(f"Error in monitor loop: {e}")

if __name__ == "__main__":
    main()
