# Portfolio & Operations Manager: Dashboard
**Target Wallet:** `0xaa7c405151c1a11fc2e9998a31b285c7b53d248b`  
**Network:** Robinhood Chain (`chainId: 4663`) | **Desk:** `rh/` | **Updated:** 2026-09-11 23:07:29 UTC

## 1. Capital & Wallet Balances
| Asset | Address / Type | Balance | Price (USD) | Total Value (USD) |
| :--- | :--- | :--- | :--- | :--- |
| **ETH** (Gas) | Native Gas Buffer | 0.009558 ETH | ~$2,500.00 | $23.90 |
| **NVDA** | `0xd0601ce1...` | 0.4524 NVDA | $218.4145 | **$98.81** |
| **sNUKE** | `0xcd7079e3...` | 0.0000 sNUKE | $8.2350 | **$0.00** |
| **Total Liquid Capital** | | | | **$122.71 USD** |

## 2. Gas Consideration & Runway (Robinhood L2 vs Boros)
> [!NOTE]
> Unlike Boros where order operations are 100% off-chain, Robinhood Chain cancellations require on-chain L2 gas. Re-centers are strictly gated by our Gas Hurdle Model (expected reward > 5x gas).

| Metric | Value | Threshold / Target |
| :--- | :--- | :--- |
| **Gas Buffer Balance** | `0.009558 ETH` ($23.90) | Safe (> 0.002 ETH) |
| **Current Gas Price** | `0.1044 Gwei` | Nominal (< 1.0 Gwei) |
| **Avg. Cancellation Cost** | `0.00000752 ETH` (~$0.0188) | < $0.05 / cancel |
| **Execution Runway** | **1,271 cancellations** | 🟢 Healthy |

## 3. Accumulated Incentive Rewards (PENDLE)
- **Lifetime Harvested Rewards:** `0.016734 PENDLE`
- **Current Active Epoch Rewards:** `0.074824 PENDLE` (Accruing)
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