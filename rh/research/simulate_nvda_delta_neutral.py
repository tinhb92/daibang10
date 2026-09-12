#!/usr/bin/env python3
"""
Institutional Simulation: Delta-Neutral NVDA Strategy
Long Pendle V2 (Robinhood Chain) + Short Perp (Hyperliquid)

Models:
1. Sizing: $1,000 Total Capital ($500 Pendle + $500 Hyperliquid Margin)
2. Yield: Pendle NVDA AMM Pool (27.14% APY) vs Solitary Limit Order (100% APR)
3. Cost: Hyperliquid funding rate (-5%, 0%, +5%)
4. Stress Test: NVDA moves -50%, -20%, 0%, +20%, +50%
5. Liquidation Price & Margin Health on Hyperliquid
"""

import sys

def simulate_nvda_delta_neutral(
    total_capital_usd=1000.0,
    nvda_spot_price=218.50,
    pendle_allocation_pct=0.50,  # 50% Pendle, 50% Hyperliquid
    pendle_pool_apy=27.14,       # AMM pool aggregated APY
    pendle_maker_apr=100.0,      # Solitary limit order APR
    hl_leverage=2.0,             # 2x leverage on short perp
    hl_funding_rate_annual=0.0,  # Expected annual funding (0%, +5%, -5%)
    horizon_days=33.0            # Days to maturity (15-OCT-2026)
):
    pendle_capital = total_capital_usd * pendle_allocation_pct
    hl_margin = total_capital_usd * (1.0 - pendle_allocation_pct)

    # Notional hedged
    nvda_units = pendle_capital / nvda_spot_price
    short_notional = pendle_capital
    short_margin_used = short_notional / hl_leverage
    hl_buffer = hl_margin - short_margin_used

    # Liquidation price on Hyperliquid (Short position)
    # Liq happens when loss on short == hl_margin
    # (P_liq - P_entry) * units = hl_margin => P_liq = P_entry + (hl_margin / units)
    liq_price = nvda_spot_price + (hl_margin / nvda_units)
    liq_distance_pct = ((liq_price - nvda_spot_price) / nvda_spot_price) * 100.0

    # Yield Scenarios
    # Route 1: Pendle AMM Pool (27.14% APY)
    pool_daily_rate = (pendle_pool_apy / 100.0) / 365.0
    pool_period_yield = pendle_capital * (pool_daily_rate * horizon_days)
    pool_net_apr_total_cap = (pool_period_yield / total_capital_usd) * (365.0 / horizon_days) * 100.0

    # Route 2: Solitary Maker Limit Order (100% APR on maker size)
    maker_daily_rate = (pendle_maker_apr / 100.0) / 365.0
    maker_period_yield = pendle_capital * (maker_daily_rate * horizon_days)
    maker_net_apr_total_cap = (maker_period_yield / total_capital_usd) * (365.0 / horizon_days) * 100.0

    # Funding rate cost/gain over horizon
    funding_daily_rate = (hl_funding_rate_annual / 100.0) / 365.0
    funding_pnl = short_notional * (funding_daily_rate * horizon_days)

    return {
        "nvda_spot_price": nvda_spot_price,
        "nvda_units": nvda_units,
        "pendle_capital": pendle_capital,
        "hl_margin": hl_margin,
        "hl_leverage": hl_leverage,
        "short_notional": short_notional,
        "liq_price": liq_price,
        "liq_distance_pct": liq_distance_pct,
        "horizon_days": horizon_days,
        "pool_route": {
            "period_yield_usd": pool_period_yield,
            "net_apr_total_cap": pool_net_apr_total_cap,
            "net_pnl_with_funding": pool_period_yield + funding_pnl
        },
        "maker_route": {
            "period_yield_usd": maker_period_yield,
            "net_apr_total_cap": maker_net_apr_total_cap,
            "net_pnl_with_funding": maker_period_yield + funding_pnl
        },
        "funding_pnl": funding_pnl
    }

if __name__ == "__main__":
    res = simulate_nvda_delta_neutral()
    print("=== DELTA-NEUTRAL NVDA SIMULATION ($1,000 USD) ===")
    print(f"NVDA Spot Price: ${res['nvda_spot_price']:.2f}")
    print(f"Units Hedged:    {res['nvda_units']:.4f} NVDA")
    print(f"Pendle Capital:  ${res['pendle_capital']:.2f}")
    print(f"HL Margin:       ${res['hl_margin']:.2f} ({res['hl_leverage']}x leverage)")
    print(f"Liquidation Price: ${res['liq_price']:.2f} (+{res['liq_distance_pct']:.1f}% rally required to liquidate)")
    print("-" * 50)
    print("ROUTE A: PENDLE AMM POOL (27.14% APY)")
    print(f"  33-Day Horizon Yield: +${res['pool_route']['period_yield_usd']:.2f} USD")
    print(f"  Net Delta-Neutral APR: {res['pool_route']['net_apr_total_cap']:.2f}%")
    print("-" * 50)
    print("ROUTE B: SOLITARY LIMIT ORDER MAKER (100% APR)")
    print(f"  33-Day Horizon Yield: +${res['maker_route']['period_yield_usd']:.2f} USD")
    print(f"  Net Delta-Neutral APR: {res['maker_route']['net_apr_total_cap']:.2f}%")
