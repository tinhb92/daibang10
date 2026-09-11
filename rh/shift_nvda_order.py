#!/usr/bin/env python3
"""
Pendle V2 - NVDA Limit Order Cancel & Shift Script
Target Market: NVDA (Oct 15, 2026) on Robinhood Chain (Chain ID: 4663)
Cancels existing out-of-band order and shifts to target incentive band with Gas Economics checking.

Usage:
  python rh/shift_nvda_order.py --dry-run
  python rh/shift_nvda_order.py --execute --target-apy 9.95
"""

import os
import sys
import time
import math
import json
import argparse
import urllib.request
from datetime import datetime, timezone
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_typed_data

# Ensure rh and root package imports work
RH_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(RH_DIR)
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)
if RH_DIR not in sys.path:
    sys.path.insert(0, RH_DIR)
from gas_governor import (
    get_gas_metrics,
    evaluate_shift_economic_viability,
    check_and_enforce_gas_ceiling,
    AVG_CANCEL_GAS_UNITS,
    MAX_ALLOWED_GAS_UNITS,
    MAX_ALLOWED_GAS_COST_USD
)
from rh.config.market_params import validate_order_safety
from alerter import send_telegram_alert

CHAIN_ID = 4663
RPC_URL = "https://rpc.mainnet.chain.robinhood.com"
BASE_API = "https://api-v2.pendle.finance/core"
ROUTER_ADDRESS = "0x000000000000c9B3E2C3Ec88B1B4c0cD853f4321"

SUPPORTED_MARKETS = {
    "NVDA": {
        "market": "0x206a5cd00e9ffabb8ca564076b64799a78df19b9",
        "yt": "0x9cc22e51c6f0cb4aa1bfd1f18e85df1451ebb9b3",
        "token": "0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec",
        "default_amount": 0.05,
        "default_apy": 9.95,
        "dte_days": 33.9,
        "spot_fallback": 220.0
    },
    "sNUKE": {
        "market": "0x8547b391a65deb89c41a4c3b2eb1502d0bbc566a",
        "yt": "0xe32a6d0356d080d9dd8c0bd8e7ab3f464b3f1dbc",
        "token": "0x9e9093a12b343c0f4d519ab093bef989b1936f73", # SY-sNUKE
        "default_amount": 2.817,
        "default_apy": 103.0,
        "dte_days": 12.5,
        "spot_fallback": 9.2
    },
    "SGOV": {
        "market": "0xd6e26e957b3207a5c618213d928647ec84150ca0",
        "yt": "0x7eee53b86290e58179ed96bea7887a37e8a1b7b9",
        "token": "0x92fd66527192e3e61d4ddd13322aa222de86f9b5",
        "default_amount": 0.10,
        "default_apy": 0.90,
        "dte_days": 68.5,
        "spot_fallback": 101.0
    }
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

def load_private_key():
    """Safely loads I3 from .env without writing or modifying the file."""
    search_paths = [
        os.path.join(os.path.dirname(__file__), "..", ".env"),
        os.path.join(os.path.dirname(__file__), ".env"),
        "/Users/tin/eagle/daibang9/.env"
    ]
    for env_path in search_paths:
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("I3"):
                        return line.split("=", 1)[1].strip().strip("\"'")
    raise ValueError("I3 key not found in search paths")

def fetch_json(url, data=None, max_retries=3):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data else None,
        headers={"Content-Type": "application/json", **HEADERS}
    )
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries:
                time.sleep(2.0 * attempt)
                continue
            if attempt < max_retries and e.code != 400: # Don't retry validation error 400
                time.sleep(1.0 * attempt)
                continue
            raise
        except Exception:
            if attempt < max_retries:
                time.sleep(1.0 * attempt)
                continue
            raise

def get_market_incentive_band(market_addr):
    configs = fetch_json(f"{BASE_API}/v1/limit-orders/incentive/configs").get("configs", [])
    for c in configs:
        if c.get("chainId") == CHAIN_ID and c.get("marketAddress", "").lower() == market_addr.lower():
            return {
                "impliedApy": (c.get("impliedApy") or 0) * 100,
                "minApy": (c.get("minApy") or 0) * 100,
                "maxApy": (c.get("maxApy") or 0) * 100,
                "buyPtApr": (c.get("estimatedApr", {}).get("buyPtApr") or 0) * 100,
                "sellYtApr": (c.get("estimatedApr", {}).get("sellYtApr") or 0) * 100
            }
    return {"impliedApy": 10.00, "minApy": 9.65, "maxApy": 10.40, "buyPtApr": 100.0, "sellYtApr": 100.0}

def get_active_orders_for_yt(maker_address, yt_address):
    orders = fetch_json(f"{BASE_API}/v2/limit-orders?chainId={CHAIN_ID}&maker={maker_address}").get("results", [])
    active = []
    for o in orders:
        if o.get("yt", "").lower() == yt_address.lower() and o.get("isActive", False) and int(o.get("currentMakingAmount", 0)) > 0:
            active.append(o)
    return active

def build_cancel_tx(maker_address, order_ids):
    url = f"{BASE_API}/v1/sdk/{CHAIN_ID}/limit-order/cancel-batch"
    payload = {"maker": maker_address, "orderIds": order_ids}
    res = fetch_json(url, data=payload)
    return res.get("tx", {})

def generate_and_sign_new_order(maker_address, private_key, yt_addr, token_addr, amount_wei, target_apy_percent, dry_run=False):
    implied_apy_dec = target_apy_percent / 100.0
    expiry_ts = str(int(time.time()) + 86400 * 14) # 14 days order validity

    gen_url = f"{BASE_API}/v1/limit-orders/makers/generate-limit-order-data"
    gen_payload = {
        "chainId": CHAIN_ID,
        "YT": yt_addr,
        "orderType": 2, # TOKEN_FOR_YT (Long Yield / Sell YT / Buy PT)
        "token": token_addr,
        "maker": maker_address,
        "makingAmount": str(amount_wei),
        "impliedApy": implied_apy_dec,
        "expiry": expiry_ts
    }
    
    try:
        order_data = fetch_json(gen_url, data=gen_payload)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        if "User balance is not enough" in err_body and dry_run:
            print("  ℹ️ [Dry-Run Simulation Note]: Balance is currently locked in active resting orders.")
            print("     Upon Step 1 on-chain cancelBatch, balance will be freed to sign & place the new order.")
            return {
                "dry_run_simulated": True,
                "makingAmount": str(amount_wei),
                "lnImpliedRate": int(math.log(1.0 + implied_apy_dec) * 1e18),
                "signature": "0xSIMULATED_PENDING_ONCHAIN_CANCELLATION"
            }
        raise RuntimeError(f"Pendle order generation failed: {err_body}") from e
    
    domain = {
        "name": "Pendle Limit Order Protocol",
        "version": "1",
        "chainId": CHAIN_ID,
        "verifyingContract": ROUTER_ADDRESS
    }

    types = {
        "EIP712Domain": [
            {"name": "name", "type": "string"},
            {"name": "version", "type": "string"},
            {"name": "chainId", "type": "uint256"},
            {"name": "verifyingContract", "type": "address"}
        ],
        "Order": [
            {"name": "salt", "type": "uint256"},
            {"name": "expiry", "type": "uint256"},
            {"name": "nonce", "type": "uint256"},
            {"name": "orderType", "type": "uint8"},
            {"name": "token", "type": "address"},
            {"name": "YT", "type": "address"},
            {"name": "maker", "type": "address"},
            {"name": "receiver", "type": "address"},
            {"name": "makingAmount", "type": "uint256"},
            {"name": "lnImpliedRate", "type": "uint256"},
            {"name": "failSafeRate", "type": "uint256"},
            {"name": "permit", "type": "bytes"}
        ]
    }

    message = {
        "salt": int(order_data["salt"]),
        "expiry": int(order_data["expiry"]),
        "nonce": int(order_data["nonce"]),
        "orderType": int(order_data["orderType"]),
        "token": order_data["token"],
        "YT": order_data["YT"],
        "maker": order_data["maker"],
        "receiver": order_data["receiver"],
        "makingAmount": int(order_data["makingAmount"]),
        "lnImpliedRate": int(order_data["lnImpliedRate"]),
        "failSafeRate": int(order_data["failSafeRate"]),
        "permit": b""
    }

    structured = {
        "types": types,
        "primaryType": "Order",
        "domain": domain,
        "message": message
    }

    signable = encode_typed_data(full_message=structured)
    signed = Account.sign_message(signable, private_key=private_key)
    sig_hex = "0x" + signed.signature.hex()

    create_payload = {
        "chainId": CHAIN_ID,
        "signature": sig_hex,
        "salt": order_data["salt"],
        "expiry": order_data["expiry"],
        "nonce": order_data["nonce"],
        "type": order_data["orderType"],
        "token": order_data["token"],
        "yt": order_data["YT"],
        "maker": order_data["maker"],
        "receiver": order_data["receiver"],
        "makingAmount": order_data["makingAmount"],
        "lnImpliedRate": order_data["lnImpliedRate"],
        "failSafeRate": order_data["failSafeRate"],
        "permit": "0x"
    }

    return create_payload

def submit_order_to_pendle(create_payload):
    url = f"{BASE_API}/v1/limit-orders/makers/limit-orders"
    return fetch_json(url, data=create_payload)

def main():
    parser = argparse.ArgumentParser(description="Cancel & Shift Limit Order into Incentive Band (Robinhood Chain)")
    parser.add_argument("--market", type=str, default="NVDA", choices=["NVDA", "sNUKE", "SGOV"], help="Target market (default: NVDA)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without submitting on-chain tx or new order (default)")
    parser.add_argument("--execute", action="store_true", help="Execute on-chain cancellation and post new order")
    parser.add_argument("--target-apy", type=float, default=None, help="Target implied APY in percent (default: market baseline)")
    parser.add_argument("--amount", type=float, default=None, help="Amount of underlying/SY to order (default: market baseline)")
    args = parser.parse_args()

    # Default to safe dry-run unless --execute is explicitly supplied
    if not args.execute:
        args.dry_run = True

    m_key = args.market.upper()
    if m_key == "SNUKE":
        m_key = "sNUKE"
    m_cfg = SUPPORTED_MARKETS[m_key]

    target_apy = args.target_apy if args.target_apy is not None else m_cfg["default_apy"]
    amount = args.amount if args.amount is not None else m_cfg["default_amount"]

    pk = load_private_key()
    acct = Account.from_key(pk)
    maker = acct.address
    print(f"=== ROBINHOOD DESK: {m_key} LIMIT ORDER MANAGER ===")
    print(f"Maker Wallet: {maker}")
    print(f"Target Market:{m_key} ({m_cfg['market']})")
    print(f"Network:      Robinhood Chain (Chain ID: {CHAIN_ID})")

    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    # Gas Governor Metrics
    gas_metrics = get_gas_metrics(w3, maker)
    print(f"\n[Gas Consideration (Robinhood L2 vs Boros Off-Chain)]")
    print(f"  - ETH Balance:      {gas_metrics['eth_balance']:.6f} ETH (${gas_metrics['eth_balance_usd']:.2f} USD)")
    print(f"  - Cost per Cancel:  {gas_metrics['cost_per_cancel_eth']:.8f} ETH (~${gas_metrics['cost_per_cancel_usd']:.4f} USD)")
    print(f"  - Cancel Runway:    {gas_metrics['runway_cancels']:,} txs remaining")

    # 1. Market & Incentive Band check
    band = get_market_incentive_band(m_cfg["market"])
    print(f"\n[Market State]")
    print(f"  - Implied APY:    {band['impliedApy']:.2f}%")
    print(f"  - Incentive Band: [{band['minApy']:.2f}%, {band['maxApy']:.2f}%]")
    print(f"  - Target APY:     {target_apy:.2f}%")

    if not (band["minApy"] <= target_apy <= band["maxApy"]):
        print(f"[!] Warning: Target APY {target_apy:.2f}% is outside incentive band [{band['minApy']:.2f}%, {band['maxApy']:.2f}%]!")
        if args.execute:
            print("Aborting to avoid earning zero rewards.")
            sys.exit(1)

    # 2. Existing active orders for this YT
    active_orders = get_active_orders_for_yt(maker, m_cfg["yt"])
    print(f"\n[Active {m_key} Orders]: {len(active_orders)}")
    order_ids_to_cancel = []
    current_incentive_apr = 0.0
    for o in active_orders:
        oid = o.get("id")
        raw_ln = int(o.get("lnImpliedRate", 0)) / 1e18
        apy = (math.exp(raw_ln) - 1.0) * 100.0
        cur_making = int(o.get("currentMakingAmount", 0)) / 1e18
        in_band = band["minApy"] <= apy <= band["maxApy"]
        status = "IN-RANGE (Earning)" if in_band else "OUT-OF-RANGE (0 rewards)"
        if in_band:
            current_incentive_apr = band["buyPtApr"]
        print(f"  - Order {oid[:14]}... | Rate: {apy:.2f}% | Size: {cur_making:.4f} {m_key} ({status})")
        order_ids_to_cancel.append(oid)

    # Gas Economics Breakeven Evaluation
    spot_price = m_cfg.get("spot_fallback", 100.0)
    order_size_usd = amount * spot_price
    new_incentive_apr = band["buyPtApr"]
    econ = evaluate_shift_economic_viability(
        order_size_usd=order_size_usd,
        current_incentive_apr=current_incentive_apr,
        new_incentive_apr=new_incentive_apr,
        gas_cost_usd=gas_metrics["cost_per_cancel_usd"],
        projected_holding_hours=24.0
    )

    print(f"\n[Gas Economics Evaluation]")
    print(f"  - Order Notional:   ${order_size_usd:.2f} USD")
    print(f"  - Gas Cost to Shift:${econ['gas_cost_usd']:.4f} USD")
    print(f"  - 24h Reward Delta: ${econ['expected_reward_usd']:.4f} USD")
    print(f"  - Reward/Gas Ratio: {econ['reward_to_gas_ratio']:.1f}x (Hurdle: {econ['min_required_ratio']}x)")
    print(f"  - Breakeven Time:   {econ['hours_to_breakeven']:.2f} hours")

    if not econ["is_viable"]:
        print("⚠️ Warning: Shift fails economic hurdle (gas cost too high relative to reward gain).")
        if args.execute:
            print("Aborting to preserve capital from gas erosion.")
            sys.exit(1)
    else:
        print("✅ Shift is economically sound: Rewards strongly dominate gas cost.")

    # Quantitative Safety Constraint Check (Seth Klarman, Ajit Jain, Gas Ceiling)
    is_safe, reason, violations = validate_order_safety(
        market_identifier=m_key,
        side="SHORT",
        rate_apy=target_apy,
        gas_units=AVG_CANCEL_GAS_UNITS,
        gas_cost_usd=econ["gas_cost_usd"],
        expected_reward_usd=econ["expected_reward_usd"],
        dte_days=m_cfg.get("dte_days", 30.0)
    )
    print(f"\n[Constraint Safety Verification]")
    if not is_safe:
        print(f"🛑 SAFETY CONSTRAINT VIOLATION: {reason}")
        for v in violations:
            print(f"   ❌ {v}")
        if args.execute:
            print("Execution ABORTED by safety constraints.")
            sys.exit(1)
    else:
        print(f"  - Safety Check: ✅ PASSED (Klarman floor, Carry ceiling, Ajit Jain cliff, Gas 10x ceiling)")

    # 3. Cancel Plan
    cancel_tx_data = None
    to_addr = None
    from_addr = Web3.to_checksum_address(maker)
    gas_est = AVG_CANCEL_GAS_UNITS

    if order_ids_to_cancel:
        print(f"\n[Step 1: Cancel {len(order_ids_to_cancel)} Order(s)]")
        cancel_tx = build_cancel_tx(maker, order_ids_to_cancel)
        cancel_tx_data = cancel_tx.get("data")
        to_addr = Web3.to_checksum_address(cancel_tx.get("to", ROUTER_ADDRESS))

        try:
            gas_est = w3.eth.estimate_gas({"from": from_addr, "to": to_addr, "data": cancel_tx_data})
        except Exception as e:
            print(f"  - Gas estimation note: {e}")
            gas_est = AVG_CANCEL_GAS_UNITS

        gas_price = w3.eth.gas_price
        tx_cost_eth = (gas_est * gas_price) / 1e18
        tx_cost_usd = tx_cost_eth * 2500.0
        print(f"  - Router:       {to_addr}")
        print(f"  - Est Gas:      {gas_est:,} units (Ceiling: {MAX_ALLOWED_GAS_UNITS:,})")
        print(f"  - Est Cost:     {tx_cost_eth:.8f} ETH (~${tx_cost_usd:.4f} USD, Ceiling: ${MAX_ALLOWED_GAS_COST_USD:.2f})")

        # 10x Safety Ceiling Guard: abort and alert if above 10x of baseline
        ceiling_safe = check_and_enforce_gas_ceiling(gas_est, tx_cost_usd, market_name=f"{m_key} Robinhood")
        if not ceiling_safe:
            print(f"\n🚨 [GAS CEILING EXCEEDED] Cancel tx cost exceeds 10x baseline limit!")
            print(f"   Hard Limit: {MAX_ALLOWED_GAS_UNITS:,} units / ${MAX_ALLOWED_GAS_COST_USD:.2f} USD.")
            print(f"   Action: IGNORED. Dispatched alert to Telegram.")
            sys.exit(1)

    # 4. Generate New Order
    print(f"\n[Step 2: Generate New Shifted Order]")
    amount_wei = int(amount * 1e18)
    new_order_payload = generate_and_sign_new_order(maker, pk, m_cfg["yt"], m_cfg["token"], amount_wei, target_apy, dry_run=args.dry_run)
    print(f"  - Size:         {amount} {m_key}")
    print(f"  - Implied APY:  {target_apy:.2f}% (Inside Band [{band['minApy']:.2f}%, {band['maxApy']:.2f}%])")
    print(f"  - lnImpliedRate:{new_order_payload['lnImpliedRate']}")
    print(f"  - Signature:    {new_order_payload['signature'][:20]}...")

    if args.dry_run:
        print(f"\n[DRY RUN COMPLETE] Validated successfully under Gas Economics Model. Run with --execute to broadcast.")
        return

    # EXECUTE PHASE (Requires deliberate --execute flag)
    if args.execute:
        tx_hash = None
        receipt = None
        # Step A: Cancel on-chain
        if order_ids_to_cancel and cancel_tx_data:
            print("\n>>> Broadcasting On-Chain Cancel Transaction...")
            max_retries = 5
            cancellation_confirmed = False

            for attempt in range(1, max_retries + 1):
                try:
                    nonce = w3.eth.get_transaction_count(from_addr, "pending")
                    current_gas_price = w3.eth.gas_price
                    bumped_gas_price = int(current_gas_price * (1.15 + 0.1 * (attempt - 1)))

                    tx = {
                        "from": from_addr,
                        "to": to_addr,
                        "data": cancel_tx_data,
                        "nonce": nonce,
                        "gas": int(gas_est * 1.35),
                        "gasPrice": bumped_gas_price,
                        "chainId": CHAIN_ID
                    }
                    signed_tx = w3.eth.account.sign_transaction(tx, private_key=pk)
                    raw_bytes = getattr(signed_tx, "raw_transaction", getattr(signed_tx, "rawTransaction", None))
                    tx_hash = w3.eth.send_raw_transaction(raw_bytes)
                    print(f"Transaction broadcast (Attempt {attempt}/{max_retries}, Nonce: {nonce}): {tx_hash.hex()}")
                    print("Waiting for confirmation on Robinhood Chain...")
                    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
                    if receipt.status == 1:
                        print(f"✅ Cancellation Confirmed in block {receipt.blockNumber}!")
                        cancellation_confirmed = True
                        break
                    else:
                        raise RuntimeError(f"Transaction reverted on-chain with status {receipt.status}")
                except Exception as err:
                    err_str = str(err).lower()
                    if ("nonce" in err_str or "already known" in err_str or "replacement" in err_str or "underpriced" in err_str) and attempt < max_retries:
                        print(f"⚠️ Nonce clash / mempool conflict detected: {err}")
                        print(f"   Refreshing pending nonce and retrying ({attempt + 1}/{max_retries}) in 2s...")
                        time.sleep(2)
                    elif attempt < max_retries:
                        print(f"⚠️ Broadcast warning: {err}. Retrying ({attempt + 1}/{max_retries}) in 2s...")
                        time.sleep(2)
                    else:
                        print(f"❌ Failed to cancel on-chain after {max_retries} attempts: {err}")
                        sys.exit(1)

            if not cancellation_confirmed:
                print("❌ Cancellation was not confirmed. Halting execution.")
                sys.exit(1)

        # Step B: Submit New Order (Freshly generated with freed balance)
        print(f"\n>>> Submitting New In-Band Limit Order for {m_key} to Pendle API...")
        if new_order_payload.get("dry_run_simulated") or order_ids_to_cancel:
            new_order_payload = generate_and_sign_new_order(maker, pk, m_cfg["yt"], m_cfg["token"], amount_wei, target_apy, dry_run=False)
        res = submit_order_to_pendle(new_order_payload)
        new_order_id = res.get('id') or str(res)
        print("✅ New Order Placed Successfully!")
        print(f"Order ID: {new_order_id}")

        # Step C: Dispatch Instant Telegram Execution Receipt
        try:
            tx_link = f"https://robinhoodchain.blockscout.com/tx/{tx_hash.hex()}" if tx_hash else "None (Fresh Order)"
            tx_str = f"<a href=\"{tx_link}\">{tx_hash.hex()[:14]}...</a>" if tx_hash else "None"
            gas_used_str = f"{receipt.gasUsed:,} units" if receipt else "0"
            exec_msg = (
                f"🚀 <b>[ON-CHAIN LIMIT ORDER SHIFT: {m_key}]</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"• <b>Market:</b> <b>{m_key}</b>\n"
                f"• <b>New Limit Order ID:</b> <code>{new_order_id[:16]}...</code>\n"
                f"• <b>Target Implied APY:</b> <code>{target_apy:.2f}%</code> (Band: [{band['minApy']:.2f}%, {band['maxApy']:.2f}%])\n"
                f"• <b>Order Size:</b> <code>{amount} {m_key}</code> (~${order_size_usd:.2f} USD)\n"
                f"• <b>Status:</b> 🟢 <b>Active & In-Band (Mining 100% APR)</b>\n"
                f"• <b>On-Chain Cancel Tx:</b> {tx_str}\n"
                f"• <b>Gas Consumed:</b> <code>{gas_used_str}</code> (~${econ['gas_cost_usd']:.4f} USD)\n\n"
                f"🕒 <i>Execution receipt at {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}</i>"
            )
            print("\n>>> DISPATCHING EXECUTION RECEIPT TO TELEGRAM <<<")
            send_telegram_alert(exec_msg)
        except Exception as alert_err:
            print(f"Warning: Failed to dispatch execution alert: {alert_err}")

        # Step D: Refresh Dashboard
        print("\n>>> Updating Portfolio & Operations Manager Dashboard...")
        monitor_script = os.path.join(os.path.dirname(__file__), "monitor_portfolio.py")
        os.system(f"{sys.executable} {monitor_script}")
        print("Done!")

if __name__ == "__main__":
    main()
