# Portfolio & Operations Manager: Dashboard
**Target Wallet:** `0xaa7c405151c1a11fc2e9998a31b285c7b53d248b`  
**Network:** Robinhood Chain (`chainId: 4663`) | **Desk:** `rh/` | **Updated:** 2026-09-11 23:15:26 UTC

## 1. Capital & Wallet Balances
| Asset | Address / Type | Balance | Price (USD) | Total Value (USD) |
| :--- | :--- | :--- | :--- | :--- |
| **ETH** (Gas) | Native Gas Buffer | 0.009558 ETH | ~$2,500.00 | $23.90 |
| **NVDA** | `0xd0601ce1...` | 0.4524 NVDA | $218.4695 | **$98.84** |
| **sNUKE** | `0xcd7079e3...` | 0.0000 sNUKE | $8.2354 | **$0.00** |
| **Total Liquid Capital** | | | | **$122.74 USD** |

## 2. Gas Consideration & Runway (Robinhood L2 vs Boros)
> [!NOTE]
> Unlike Boros where order operations are 100% off-chain, Robinhood Chain cancellations require on-chain L2 gas. Re-centers are strictly gated by our Gas Hurdle Model (expected reward > 5x gas).

| Metric | Value | Threshold / Target |
| :--- | :--- | :--- |
| **Gas Buffer Balance** | `0.009558 ETH` ($23.90) | Safe (> 0.002 ETH) |
| **Current Gas Price** | `0.1038 Gwei` | Nominal (< 1.0 Gwei) |
| **Avg. Cancellation Cost** | `0.00000747 ETH` (~$0.0187) | < $0.05 / cancel |
| **Execution Runway** | **1,279 cancellations** | 🟢 Healthy |

## 3. Accumulated Incentive Rewards (PENDLE)
- **Lifetime Harvested Rewards:** `0.016734 PENDLE`
- **Current Active Epoch Rewards:** `0.075357 PENDLE` (Accruing)
- **Total Resting Limit Order Value:** `$36.52 USD`
- **Incentivized Resting Value In-Range:** `$36.50 USD` 🟢 **ACTIVE IN-RANGE!**

### Historical Epoch Rewards Breakdown
| Epoch Period | Market | My Reward | Total Pool Reward |
| :--- | :--- | :--- | :--- |
| 2026-09-04 to 2026-09-11 | **ROBINHOOD sNUKE 2026Sep** | `0.016670 PENDLE` | `0.2107 PENDLE` |
| 2026-09-04 to 2026-09-11 | **ROBINHOOD NVDA 2026Oct** | `0.000064 PENDLE` | `0.0769 PENDLE` |

## 4. Active Resting Limit Orders & Band Alignment
| Order ID | Market | Type | Making Amount | Order Implied Rate | Market Band [Min, Max] | Incentive Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `0x36ab55e71047...` | sNUKE | Type 3 | 10.0000 | **120.00%** | [99.38%, 121.47%] | 🟢 **IN-RANGE (Earning 100% APR)** |
| `0xcce971dc14c8...` | SGOV | Type 3 | 0.1000 | **0.95%** | [0.96%, 1.07%] | 🔴 **OUT-OF-RANGE** (Needs 0.96%-1.07%) |
| `0x7d520aad5d1a...` | SGOV | Type 3 | 0.1000 | **3.00%** | [0.96%, 1.07%] | 🔴 **OUT-OF-RANGE** (Needs 0.96%-1.07%) |
| `0xa7c68c5b5f77...` | sNUKE | Type 2 | 2.8175 | **103.00%** | [99.38%, 121.47%] | 🟢 **IN-RANGE (Earning 100% APR)** |
| `0x9fbd180f1dd3...` | NVDA | Type 2 | 0.0500 | **9.95%** | [9.65%, 10.40%] | 🟢 **IN-RANGE (Earning 100% APR)** |
| `0x7e8f89429e71...` | sNUKE | Type 2 | 0.0000 | **108.00%** | [99.38%, 121.47%] | ⚪ Cancelled / Inactive |
| `0x25b6e378c627...` | NVDA | Type 2 | 0.0500 | **8.10%** | [9.65%, 10.40%] | ⚪ Cancelled / Inactive |

## 5. Pendle V2 AMM Liquidity Pool Positions & Yield Opportunities
> [!TIP]
> Pendle V2 AMM Pools generate continuous multi-stream yield (Underlying Yield + AMM Swap Fees + PENDLE Emissions) with Zero Impermanent Loss at Maturity ($PT \to SY$ at 1:1), contrasting Boros which has 0% pool LP yield.

| Pool | Holding | Pool Aggregated APY | Implied APY | Status | Direct Zap-In |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **NVDA** | 0.0000 LP | **27.15%** | 10.00% | ⚪ No LP Deployed | [Zap In](https://app.pendle.finance/trade/pools/0x206a5cd00e9ffabb8ca564076b64799a78df19b9/zap/in?chain=robinhood) |
| **sNET** | 0.0000 LP | **14859.38%** | 12858.03% | ⚪ No LP Deployed | [Zap In](https://app.pendle.finance/trade/pools/0x23c68474e3cd533a2f952a0fb998f1867e57d27f/zap/in?chain=robinhood) |
| **sNUKE** | 0.0000 LP | **147.70%** | 110.43% | ⚪ No LP Deployed | [Zap In](https://app.pendle.finance/trade/pools/0x8547b391a65deb89c41a4c3b2eb1502d0bbc566a/zap/in?chain=robinhood) |
| **PFE** | 0.0000 LP | **23.38%** | 4.74% | ⚪ No LP Deployed | [Zap In](https://app.pendle.finance/trade/pools/0x892defbf510d9baa96dbd2a51b13e879a857a79b/zap/in?chain=robinhood) |
| **SGOV** | 0.0000 LP | **139.08%** | 1.00% | ⚪ No LP Deployed | [Zap In](https://app.pendle.finance/trade/pools/0xd6e26e957b3207a5c618213d928647ec84150ca0/zap/in?chain=robinhood) |
| **SHROOM** | 0.0000 LP | **72.82%** | 61.43% | ⚪ No LP Deployed | [Zap In](https://app.pendle.finance/trade/pools/0x49e5d9de386b5ff5cc344748977a412d07191256/zap/in?chain=robinhood) |