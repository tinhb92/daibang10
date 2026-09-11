# Pendle V2 AMM Liquidity Pools: Institutional Opportunity & Risk Radar

> **Last Updated:** `2026-09-11 23:14:08 UTC`  
> **Target Network:** Robinhood Chain (Chain ID: `4663`) | **Desk:** `rh/`  
> **Desk Wallet:** [`0xaa7c405151c1a11fc2e9998a31b285c7b53d248b`](https://robinhoodchain.blockscout.com/address/0xaa7c405151c1a11fc2e9998a31b285c7b53d248b)  
> **Institutional Doctrine:** Taleb Antifragile Yield Capture & Convergent Impermanent Loss Elimination

---

## 1. Executive Yield Architecture: Pendle V2 Pools vs Boros Orderbook

| Feature | Boros (Arbitrum CLOB) | Pendle V2 AMM Liquidity Pools (Robinhood Chain) |
| :--- | :--- | :--- |
| **Pool LP Yield** | **0.00% (None)** — Orderbook CLOB only | **Continuous Multi-Stream Yield (20% to 150%+ APY)** |
| **Yield Streams** | Only fills & maker points | **1. Underlying Yield + 2. AMM Swap Fees + 3. PENDLE Emissions + 4. PT Accretion** |
| **Maintenance Friction** | Frequent manual/bot shifting | **Zero-maintenance passive continuous compounding** |
| **Impermanent Loss (IL)** | N/A (Borrow rates) | **Zero Impermanent Loss at Maturity** ($PT \to SY$ at 1:1) |

---

## 2. Multi-Market Liquidity Pool Matrix

| Pool | DTE | TVL (USD) | 24h Vol | Aggregated APY | Underlying | Swap Fees | PENDLE APR | Taleb Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **[sNUKE](https://app.pendle.finance/trade/pools/0x8547b391a65deb89c41a4c3b2eb1502d0bbc566a/zap/in?chain=robinhood)** | `12.0d` | `$21,581` | `$1,013` | **147.70%** | `104.20%` | `27.18%` | `13.33%` | 🟢 **Prime Fat Pitch** |
| **[NVDA](https://app.pendle.finance/trade/pools/0x206a5cd00e9ffabb8ca564076b64799a78df19b9/zap/in?chain=robinhood)** | `33.0d` | `$109,440` | `$49,290` | **27.15%** | `11.14%` | `5.29%` | `11.82%` | 🟢 **Prime Fat Pitch** |
| **[PFE](https://app.pendle.finance/trade/pools/0x892defbf510d9baa96dbd2a51b13e879a857a79b/zap/in?chain=robinhood)** | `89.0d` | `$45,555` | `$14,354` | **23.38%** | `0.00%` | `4.58%` | `16.94%` | 🟢 **Prime Fat Pitch** |
| **[SHROOM](https://app.pendle.finance/trade/pools/0x49e5d9de386b5ff5cc344748977a412d07191256/zap/in?chain=robinhood)** | `12.0d` | `$195,876` | `$62,092` | **72.82%** | `52.37%` | `16.44%` | `1.28%` | 🟢 **Prime Fat Pitch** |
| **[microduck](https://app.pendle.finance/trade/pools/0xdd34d9471667107f9b45e2204add3dd4da54e5a6/zap/in?chain=robinhood)** | `12.0d` | `$1,196` | `$167` | **254.34%** | `0.00%` | `17.12%` | `209.23%` | 🛑 ⚠️ ILLIQUID TRAP ($1,196 TVL) |
| **[SGOV](https://app.pendle.finance/trade/pools/0xd6e26e957b3207a5c618213d928647ec84150ca0/zap/in?chain=robinhood)** | `68.0d` | `$1,801` | `$43` | **139.08%** | `0.00%` | `0.09%` | `138.89%` | 🛑 ⚠️ ILLIQUID TRAP ($1,801 TVL) |
| **[sNET](https://app.pendle.finance/trade/pools/0x23c68474e3cd533a2f952a0fb998f1867e57d27f/zap/in?chain=robinhood)** | `5.0d` | `$737,385` | `$89,039` | **14859.40%** | `22129.63%` | `16.84%` | `10.22%` | 🛑 ⛔ AJIT JAIN CLIFF (5.0d < 7d) |

---

## 3. Actionable Fat Pitch Spotlights

### 💎 sNUKE Liquidity Pool (Aggregated APY: `147.70%`)
- **Maturity Date:** `2026-09-24` (`12.0` Days Remaining)
- **Pool Depth & Volume:** `$21,580.91 USD` TVL | 24h Volume: `$1,012.92 USD`
- **Yield Composition:**
  - **Underlying Yield:** `104.20%` (Native asset staking / interest)
  - **Swap Fee Yield:** `27.18%` (AMM trading fees paid by PT/YT traders)
  - **PENDLE Emissions:** `13.33%` (Direct liquidity mining incentives)
- **Projected Cash Flow:**
  - **Per $1,000 USD Capital:** `~$4.05 USD / day`
  - **Holding to Expiry (12.0d):** `+$48.69 USD` total net gain
- **Risk & IL Model:** Pure Convergent AMM. Holding to maturity guarantees $PT \to SY$ at 1:1, entirely bypassing Uniswap-style impermanent loss.
- **Direct Zap-In Link:** [Open Pendle V2 Zap-In Interface](https://app.pendle.finance/trade/pools/0x8547b391a65deb89c41a4c3b2eb1502d0bbc566a/zap/in?chain=robinhood)

### 💎 NVDA Liquidity Pool (Aggregated APY: `27.15%`)
- **Maturity Date:** `2026-10-15` (`33.0` Days Remaining)
- **Pool Depth & Volume:** `$109,440.24 USD` TVL | 24h Volume: `$49,290.11 USD`
- **Yield Composition:**
  - **Underlying Yield:** `11.14%` (Native asset staking / interest)
  - **Swap Fee Yield:** `5.29%` (AMM trading fees paid by PT/YT traders)
  - **PENDLE Emissions:** `11.82%` (Direct liquidity mining incentives)
- **Projected Cash Flow:**
  - **Per $1,000 USD Capital:** `~$0.74 USD / day`
  - **Holding to Expiry (30.0d):** `+$22.31 USD` total net gain
- **Risk & IL Model:** Pure Convergent AMM. Holding to maturity guarantees $PT \to SY$ at 1:1, entirely bypassing Uniswap-style impermanent loss.
- **Direct Zap-In Link:** [Open Pendle V2 Zap-In Interface](https://app.pendle.finance/trade/pools/0x206a5cd00e9ffabb8ca564076b64799a78df19b9/zap/in?chain=robinhood)

### 💎 PFE Liquidity Pool (Aggregated APY: `23.38%`)
- **Maturity Date:** `2026-12-10` (`89.0` Days Remaining)
- **Pool Depth & Volume:** `$45,555.50 USD` TVL | 24h Volume: `$14,354.03 USD`
- **Yield Composition:**
  - **Underlying Yield:** `0.00%` (Native asset staking / interest)
  - **Swap Fee Yield:** `4.58%` (AMM trading fees paid by PT/YT traders)
  - **PENDLE Emissions:** `16.94%` (Direct liquidity mining incentives)
- **Projected Cash Flow:**
  - **Per $1,000 USD Capital:** `~$0.64 USD / day`
  - **Holding to Expiry (30.0d):** `+$19.22 USD` total net gain
- **Risk & IL Model:** Pure Convergent AMM. Holding to maturity guarantees $PT \to SY$ at 1:1, entirely bypassing Uniswap-style impermanent loss.
- **Direct Zap-In Link:** [Open Pendle V2 Zap-In Interface](https://app.pendle.finance/trade/pools/0x892defbf510d9baa96dbd2a51b13e879a857a79b/zap/in?chain=robinhood)

### 💎 SHROOM Liquidity Pool (Aggregated APY: `72.82%`)
- **Maturity Date:** `2026-09-24` (`12.0` Days Remaining)
- **Pool Depth & Volume:** `$195,875.75 USD` TVL | 24h Volume: `$62,091.75 USD`
- **Yield Composition:**
  - **Underlying Yield:** `52.37%` (Native asset staking / interest)
  - **Swap Fee Yield:** `16.44%` (AMM trading fees paid by PT/YT traders)
  - **PENDLE Emissions:** `1.28%` (Direct liquidity mining incentives)
- **Projected Cash Flow:**
  - **Per $1,000 USD Capital:** `~$1.99 USD / day`
  - **Holding to Expiry (12.0d):** `+$24.00 USD` total net gain
- **Risk & IL Model:** Pure Convergent AMM. Holding to maturity guarantees $PT \to SY$ at 1:1, entirely bypassing Uniswap-style impermanent loss.
- **Direct Zap-In Link:** [Open Pendle V2 Zap-In Interface](https://app.pendle.finance/trade/pools/0x49e5d9de386b5ff5cc344748977a412d07191256/zap/in?chain=robinhood)

---

## 4. Taleb Antifragility Exclusions (The Graveyard Forensic Doctrine)

- 🛑 **microduck** (`12.0d` DTE, TVL: `$1,196`): **Rejected** — *⚠️ ILLIQUID TRAP ($1,196 TVL)*. Enforcing Seth Klarman margin of safety & Ajit Jain terminal cliff avoidance.
- 🛑 **SGOV** (`68.0d` DTE, TVL: `$1,801`): **Rejected** — *⚠️ ILLIQUID TRAP ($1,801 TVL)*. Enforcing Seth Klarman margin of safety & Ajit Jain terminal cliff avoidance.
- 🛑 **sNET** (`5.0d` DTE, TVL: `$737,385`): **Rejected** — *⛔ AJIT JAIN CLIFF (5.0d < 7d)*. Enforcing Seth Klarman margin of safety & Ajit Jain terminal cliff avoidance.
