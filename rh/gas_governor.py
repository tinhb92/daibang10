#!/usr/bin/env python3
"""
Robinhood Chain (4663) Gas Governor & Economics Model
Unlike Boros (where cancels/orders are 100% off-chain & gasless),
Pendle V2 on Robinhood Chain requires an on-chain L2 transaction for cancellations.
This governor enforces gas-efficiency hurdles to ensure gas costs never erode yield.
"""

from web3 import Web3

# Base parameters on Robinhood Chain
ROUTER_ADDRESS = "0x000000000000c9B3E2C3Ec88B1B4c0cD853f4321"
AVG_CANCEL_GAS_UNITS = 72000
MIN_REWARD_TO_GAS_RATIO = 5.0  # Projected incentive must exceed 5x gas cost

# Hard 10x Safety Ceiling Guard
MAX_ALLOWED_GAS_UNITS = 720000     # 10x of 72,000 baseline
MAX_ALLOWED_GAS_COST_USD = 0.2200   # 10x of $0.022 USD baseline

def check_and_enforce_gas_ceiling(gas_units: int, gas_cost_usd: float, market_name: str = "NVDA") -> bool:
    """
    Strict 10x Gas Ceiling Guard:
    Baseline: 72,000 gas units (~$0.022 USD).
    Ceiling:  720,000 gas units (~$0.220 USD).
    If estimated gas exceeds either threshold, the operation MUST be ignored
    and an alert dispatched to Telegram.
    Returns: True if within allowable ceiling; False if breached and ignored.
    """
    if gas_units > MAX_ALLOWED_GAS_UNITS or gas_cost_usd > MAX_ALLOWED_GAS_COST_USD:
        breach_reason = []
        if gas_units > MAX_ALLOWED_GAS_UNITS:
            breach_reason.append(f"Gas Units ({gas_units:,}) > 10x ceiling ({MAX_ALLOWED_GAS_UNITS:,})")
        if gas_cost_usd > MAX_ALLOWED_GAS_COST_USD:
            breach_reason.append(f"Gas Cost (${gas_cost_usd:.4f}) > 10x ceiling (${MAX_ALLOWED_GAS_COST_USD:.4f})")
            
        alert_msg = (
            f"🚨 <b>[GAS SPIKE BREACH: ACTION IGNORED]</b>\n\n"
            f"• <b>Market:</b> {market_name} (Robinhood Chain 4663)\n"
            f"• <b>Estimated Gas:</b> {gas_units:,} units\n"
            f"• <b>Estimated Cost:</b> ${gas_cost_usd:.4f} USD\n"
            f"• <b>Breach Details:</b> {'; '.join(breach_reason)}\n"
            f"• <b>Action Taken:</b> <b>EXECUTION ABORTED & IGNORED</b>\n"
            f"• <b>Policy:</b> Hard 10x ceiling on 72,000 units ($0.022 USD) to prevent fee burning."
        )
        try:
            from alerter import send_telegram_alert
            send_telegram_alert(alert_msg)
        except Exception as e:
            print(f"Failed to dispatch Telegram gas alert: {e}")
            
        return False
    return True

def get_gas_metrics(w3: Web3, maker_address: str, eth_price_usd: float = 2500.0):
    """
    Evaluates current gas balance, transaction cost, and remaining runway.
    """
    checksum_maker = Web3.to_checksum_address(maker_address)
    eth_bal_wei = w3.eth.get_balance(checksum_maker)
    eth_bal = eth_bal_wei / 1e18
    eth_bal_usd = eth_bal * eth_price_usd

    gas_price_wei = w3.eth.gas_price
    gas_price_gwei = gas_price_wei / 1e9

    cost_per_cancel_eth = (AVG_CANCEL_GAS_UNITS * gas_price_wei) / 1e18
    cost_per_cancel_usd = cost_per_cancel_eth * eth_price_usd

    runway_transactions = int(eth_bal / cost_per_cancel_eth) if cost_per_cancel_eth > 0 else 0

    return {
        "eth_balance": eth_bal,
        "eth_balance_usd": eth_bal_usd,
        "gas_price_gwei": gas_price_gwei,
        "cost_per_cancel_eth": cost_per_cancel_eth,
        "cost_per_cancel_usd": cost_per_cancel_usd,
        "runway_cancels": runway_transactions,
        "is_low_gas": eth_bal < 0.002 # Alert if less than ~200 txs remaining
    }

def evaluate_shift_economic_viability(
    order_size_usd: float,
    current_incentive_apr: float,
    new_incentive_apr: float,
    gas_cost_usd: float,
    projected_holding_hours: float = 24.0
):
    """
    Determines if cancelling and shifting an order is economically justified.
    In Boros: Shift cost is $0.
    In Robinhood: Shift costs gas_cost_usd ($0.02 - $0.05).
    """
    # Incremental APR gain
    incremental_apr = max(0.0, (new_incentive_apr - current_incentive_apr) / 100.0)
    
    # Expected incremental reward over the holding period
    expected_incremental_reward_usd = (order_size_usd * incremental_apr * (projected_holding_hours / 8760.0))
    
    # Breakeven ratio
    ratio = expected_incremental_reward_usd / gas_cost_usd if gas_cost_usd > 0 else float("inf")
    is_viable = ratio >= MIN_REWARD_TO_GAS_RATIO or (current_incentive_apr == 0.0 and order_size_usd >= 10.0)

    hours_to_breakeven = (gas_cost_usd / (order_size_usd * incremental_apr / 8760.0)) if (order_size_usd * incremental_apr) > 0 else float("inf")

    return {
        "is_viable": is_viable,
        "expected_reward_usd": expected_incremental_reward_usd,
        "gas_cost_usd": gas_cost_usd,
        "reward_to_gas_ratio": ratio,
        "hours_to_breakeven": hours_to_breakeven,
        "min_required_ratio": MIN_REWARD_TO_GAS_RATIO
    }

if __name__ == "__main__":
    rpc = "https://rpc.mainnet.chain.robinhood.com"
    w3 = Web3(Web3.HTTPProvider(rpc))
    wallet = "0xaa7c405151c1a11fc2e9998a31b285c7b53d248b"
    metrics = get_gas_metrics(w3, wallet)
    print("=== ROBINHOOD CHAIN GAS METRICS ===")
    print(f"Native ETH Balance:      {metrics['eth_balance']:.6f} ETH (${metrics['eth_balance_usd']:.2f} USD)")
    print(f"Current Gas Price:       {metrics['gas_price_gwei']:.4f} Gwei")
    print(f"Est. Cost per Cancel:    {metrics['cost_per_cancel_eth']:.8f} ETH (~${metrics['cost_per_cancel_usd']:.4f} USD)")
    print(f"Runway (Total Cancels):  {metrics['runway_cancels']:,} transactions")
    print(f"Low Gas Alert:           {metrics['is_low_gas']}")
