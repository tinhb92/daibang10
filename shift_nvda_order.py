#!/usr/bin/env python3
"""
Pendle V2 - NVDA Limit Order Cancel & Shift Script
Target Market: NVDA (Oct 15, 2026) on Robinhood Chain (Chain ID: 4663)
Cancels existing out-of-band order (7.79%) and shifts to target incentive band (e.g. 9.95%).

Usage:
  python3 shift_nvda_order.py --dry-run
  python3 shift_nvda_order.py --execute --target-apy 9.95
"""

import os
import sys
import time
import json
import argparse
import urllib.request
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_typed_data

CHAIN_ID = 4663
RPC_URL = "https://rpc.mainnet.chain.robinhood.com"
BASE_API = "https://api-v2.pendle.finance/core"
ROUTER_ADDRESS = "0x000000000000c9B3E2C3Ec88B1B4c0cD853f4321"

NVDA_MARKET = "0x206a5cd00e9ffabb8ca564076b64799a78df19b9"
NVDA_YT = "0x9cc22e51c6f0cb4aa1bfd1f18e85df1451ebb9b3"
NVDA_TOKEN = "0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec"

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

def load_private_key():
    """Safely loads I3 from .env without writing or modifying the file."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        raise FileNotFoundError(f".env file not found at {env_path}")
    
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("I3"):
                key = line.split("=", 1)[1].strip().strip("\"'")
                return key
    raise ValueError("I3 key not found in .env")

def fetch_json(url, data=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data else None,
        headers={"Content-Type": "application/json", **HEADERS}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_nvda_incentive_band():
    configs = fetch_json(f"{BASE_API}/v1/limit-orders/incentive/configs").get("configs", [])
    for c in configs:
        if c.get("chainId") == CHAIN_ID and c.get("marketAddress", "").lower() == NVDA_MARKET.lower():
            return {
                "impliedApy": (c.get("impliedApy") or 0) * 100,
                "minApy": (c.get("minApy") or 0) * 100,
                "maxApy": (c.get("maxApy") or 0) * 100,
                "buyPtApr": (c.get("estimatedApr", {}).get("buyPtApr") or 0) * 100,
                "sellYtApr": (c.get("estimatedApr", {}).get("sellYtApr") or 0) * 100
            }
    return {"impliedApy": 10.00, "minApy": 9.65, "maxApy": 10.40, "buyPtApr": 100.0, "sellYtApr": 100.0}

def get_active_nvda_orders(maker_address):
    orders = fetch_json(f"{BASE_API}/v2/limit-orders?chainId={CHAIN_ID}&maker={maker_address}").get("results", [])
    active_nvda = []
    for o in orders:
        if o.get("yt", "").lower() == NVDA_YT.lower() and int(o.get("currentMakingAmount", 0)) > 0:
            active_nvda.append(o)
    return active_nvda

def build_cancel_tx(maker_address, order_ids):
    url = f"{BASE_API}/v1/sdk/{CHAIN_ID}/limit-order/cancel-batch"
    payload = {"maker": maker_address, "orderIds": order_ids}
    res = fetch_json(url, data=payload)
    return res.get("tx", {})

def generate_and_sign_new_order(maker_address, private_key, amount_wei, target_apy_percent):
    implied_apy_dec = target_apy_percent / 100.0
    expiry_ts = str(int(time.time()) + 86400 * 14) # 14 days order validity

    gen_url = f"{BASE_API}/v1/limit-orders/makers/generate-limit-order-data"
    gen_payload = {
        "chainId": CHAIN_ID,
        "YT": NVDA_YT,
        "orderType": 2, # TOKEN_FOR_YT (Long Yield / Sell YT / Buy PT)
        "token": NVDA_TOKEN,
        "maker": maker_address,
        "makingAmount": str(amount_wei),
        "impliedApy": implied_apy_dec,
        "expiry": expiry_ts
    }
    
    order_data = fetch_json(gen_url, data=gen_payload)
    
    # EIP-712 structured data
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
    parser = argparse.ArgumentParser(description="Cancel & Shift NVDA Limit Order into Incentive Band")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without submitting on-chain tx or new order")
    parser.add_argument("--execute", action="store_true", help="Execute on-chain cancellation and post new order")
    parser.add_argument("--target-apy", type=float, default=9.95, help="Target implied APY in percent (default: 9.95)")
    parser.add_argument("--amount", type=float, default=0.05, help="Amount of NVDA to order (default: 0.05)")
    args = parser.parse_args()

    if not args.execute:
        args.dry_run = True

    pk = load_private_key()
    acct = Account.from_key(pk)
    maker = acct.address
    print(f"=== NVDA LIMIT ORDER MANAGER ===")
    print(f"Maker Wallet: {maker}")
    print(f"Network:      Robinhood Chain (Chain ID: {CHAIN_ID})")

    # 1. Market & Incentive Band check
    band = get_nvda_incentive_band()
    print(f"\n[Market State]")
    print(f"  - Implied APY:    {band['impliedApy']:.2f}%")
    print(f"  - Incentive Band: [{band['minApy']:.2f}%, {band['maxApy']:.2f}%]")
    print(f"  - Target APY:     {args.target_apy:.2f}%")

    if not (band["minApy"] <= args.target_apy <= band["maxApy"]):
        print(f"[!] Warning: Target APY {args.target_apy:.2f}% is outside incentive band [{band['minApy']:.2f}%, {band['maxApy']:.2f}%]!")
        if args.execute:
            print("Aborting to avoid earning zero rewards.")
            sys.exit(1)

    # 2. Existing active orders
    active_orders = get_active_nvda_orders(maker)
    print(f"\n[Active NVDA Orders]: {len(active_orders)}")
    order_ids_to_cancel = []
    for o in active_orders:
        oid = o.get("id")
        rate = int(o.get("lnImpliedRate", 0)) / 1e18 * 100
        cur_making = int(o.get("currentMakingAmount", 0)) / 1e18
        print(f"  - Order {oid[:14]}... | Rate: {rate:.2f}% | Size: {cur_making:.4f} NVDA (Status: Active)")
        order_ids_to_cancel.append(oid)

    w3 = Web3(Web3.HTTPProvider(RPC_URL))

    # 3. Cancel Plan
    cancel_tx_data = None
    if order_ids_to_cancel:
        print(f"\n[Step 1: Cancel {len(order_ids_to_cancel)} Order(s)]")
        cancel_tx = build_cancel_tx(maker, order_ids_to_cancel)
        cancel_tx_data = cancel_tx.get("data")
        to_addr = Web3.to_checksum_address(cancel_tx.get("to", ROUTER_ADDRESS))
        from_addr = Web3.to_checksum_address(maker)

        gas_est = w3.eth.estimate_gas({"from": from_addr, "to": to_addr, "data": cancel_tx_data})
        gas_price = w3.eth.gas_price
        tx_cost_eth = (gas_est * gas_price) / 1e18
        print(f"  - Router:       {to_addr}")
        print(f"  - Est Gas:      {gas_est} units")
        print(f"  - Est Cost:     {tx_cost_eth:.8f} ETH (~${tx_cost_eth * 2500:.4f} USD)")

    # 4. Generate New Order
    print(f"\n[Step 2: Generate New Shifted Order]")
    amount_wei = int(args.amount * 1e18)
    new_order_payload = generate_and_sign_new_order(maker, pk, amount_wei, args.target_apy)
    print(f"  - Size:         {args.amount} NVDA")
    print(f"  - Implied APY:  {args.target_apy:.2f}% (Inside Band [{band['minApy']:.2f}%, {band['maxApy']:.2f}%])")
    print(f"  - lnImpliedRate:{new_order_payload['lnImpliedRate']}")
    print(f"  - Signature:    {new_order_payload['signature'][:20]}...")

    if args.dry_run:
        print("\n[DRY RUN COMPLETE] Everything validated successfully. Run with --execute to broadcast.")
        return

    # EXECUTE PHASE
    if args.execute:
        # Step A: Cancel on-chain
        if order_ids_to_cancel and cancel_tx_data:
            print("\n>>> Broadcasting On-Chain Cancel Transaction...")
            max_retries = 5
            cancellation_confirmed = False

            for attempt in range(1, max_retries + 1):
                try:
                    # Query pending nonce to avoid collisions
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

        # Step B: Submit New Order
        print("\n>>> Submitting New In-Band Limit Order to Pendle API...")
        res = submit_order_to_pendle(new_order_payload)
        print("✅ New Order Placed Successfully!")
        print(f"Order ID: {res.get('id') or res}")

        # Step C: Refresh Dashboard
        print("\n>>> Updating Portfolio & Operations Manager Dashboard...")
        os.system(f"{sys.executable} monitor_portfolio.py")
        print("Done!")

if __name__ == "__main__":
    main()
