# Pendle V2 Trading Patterns & Institutional Core Principles

Adapted from the Boros Quantitative Trading Framework for **Pendle V2 Autonomous Operations**.

---

## Core Principle 1: "The Seth Klarman Margin of Safety — Floor & Ceiling Invariants"
> *"A margin of safety is achieved when securities are purchased at prices sufficiently below underlying value to allow for human error, bad luck, or extreme volatility."* — Seth Klarman

### 1. PT Hurdle Floor
- In Pendle V2, buying PT (`TOKEN_FOR_PT` or `SHORT_YIELD`) locks in a fixed return until maturity.
- **Invariant:** **Never purchase PT or place a resting bid at an Implied APY below the risk-free hurdle rate (e.g. 8.00% on synthetic equities).**
- *The Danger:* If market yield compresses to 3-4% (e.g. PFE @ 3.90%), bidding inside the incentive band locks capital in an inferior fixed instrument with zero upside.
- *Action:* If market implied APY falls below the hurdle floor, **sit out**. Do not quote.

### 2. YT Negative-Carry Ceiling
- Buying YT (`LONG_YIELD`) is a directional bet that the underlying yield will outperform the implied APY.
- **Invariant:** **Never buy YT when Implied APY $\ge$ Underlying APY without an explicit catalyst.**
- *The Danger:* If Implied APY is 10% and Underlying APY is 5%, YT suffers an immediate adverse cash bleed of $-5.0\%$ APR plus continuous time decay ($\theta$).

### 3. Anti-Churn & Hysteresis Invariant
- Every on-chain cancellation costs gas.
- **Invariant:** **Never micro-recenter for minor basis point wiggles.**
- Orders are only re-centered when:
  1. The market implied APY has drifted completely outside the incentive eligibility window `[minApy, maxApy]`, causing the incentive harvest to hit zero.
  2. The drift has sustained across at least 1 hourly snapshot boundary (preventing reacting to flash wicks).

---

## Core Principle 2: "Keep It Simple, But Not Simpler" (Einstein & Munger)
> *"Everything should be made as simple as possible, but not simpler."* — Albert Einstein  
> *"Take a simple idea and take it seriously."* — Charlie Munger

### 1. The Capital Compounding Razor
- **Only add code, logic, or scripts if it demonstrably compounds capital or prevents catastrophic loss.**
- Ruthlessly prune complex forecasting models, speculative trend predictions, and continuous rebalance churn.
- Pendle profitability rests on three deterministic pillars:
  1. **Incentive Harvest:** Resting orders in low-competition bands (e.g. 100% APR on NVDA Short side).
  2. **Discounted PT Carry:** Guaranteed fixed capital growth to maturity (e.g. $216.52 $\to$ $218.62).
  3. **Gas Minimization:** Robinhood Chain L2 fees must remain $< 0.1\%$ of generated alpha.

### 2. Zero-Noise Operations
- Terminal stdout is reserved for high-signal events (fills, on-chain confirmations, drift alerts).
- Routine status belongs in persistent markdown artifacts ([portfolio_manager_view.md](file:///Users/tin/.gemini/antigravity-ide/brain/70ed835e-5848-4729-a254-0318f19d3a0e/portfolio_manager_view.md)), not transient console spam.

---

## Core Principle 3: "The Ajit Jain Razor — Underwriting Catastrophe & Unknown Risk"
> *"Ajit came to Berkshire in 1986. He has insured risks that no one else had the courage or the capital to take on... He has created tens of billions of value."* — Warren Buffett

### 1. Underwriting Philosophy for Pendle Limit Orders
- **You are an underwriter of interest rate and maturity tail risk, not a flow maker.**
- When placing a limit order, you are selling an option to takers to lock in fixed yield or swap into yield tokens at your price.
- **Only write the policy when the premium is overwhelmingly asymmetric:**
  - In NVDA (Chain 4663), competing maker depth on the Short side is **$0.00**. The protocol allocates up to 100% APR in PENDLE incentives to the solitary maker.
  - This is an **Ajit Jain fat pitch**: huge premium, zero maker competition, short maturity (34 days), and backed by liquid synthetic equity.
- **Patience as Alpha:**
  - Sitting idle with 100% unallocated capital is an active, profitable position when available market spreads do not offer adequate margin of safety.
  - Never quote simply to "have an order open."

### 2. The Expiry Cliff Hazard
- Pendle markets have hard expiration dates.
- As $T \to \text{Maturity}$, liquidity naturally evaporates and taker flow becomes intensely one-sided.
- **Hard Rule:** **Never establish new resting quotes inside the final 7 days of a pool's maturity.** Cancel all resting orders and hold underlying or PT to maturity for flawless 1:1 redemption.

---

## Core Principle 4: "Empirical Realism — Data Trumps Algorithmic Cleverness"
> *"In the real world, brilliant algorithms die on edge cases that historical data predicted days in advance."*

### 1. The Poker Hand History Doctrine
- DeFi yield operations mirror deep-stack poker:
  - You analyze table position (maker queue depth, incentive pool allocations).
  - You assess opponent tendencies (toxic algorithmic arbitrageurs sweeping mispriced quotes).
  - You log difficult spots and post-mortems rather than relying on theoretical abstractions.

### 2. The Pendle Historian (Hand History Archive)

All live execution events, order shifts, and fills must be documented using the standard taxonomy:

```markdown
### Case Study [ID]: [Title]
- **Date & Market:** [e.g. 2026-09-11 | NVDA 15OCT2026 Chain 4663]
- **Macro Spot & Texture:**
  - Underlying Price & Yield: [e.g. $218.86 NVDA, 17.54% APY]
  - Implied APY & Incentive Band: [e.g. 10.00%, Band: 9.65% - 10.40%]
  - Maker Competition: [e.g. Short depth = $0.00]
- **The Setup & Decision:**
  - Placed Order Type 2 (Sell YT / Buy PT) at 9.95% APY for 0.05 NVDA.
- **The Friction / Difficult Spot:**
  - What edge case was encountered? (e.g. Nonce clash, LOP: already filled contract revert).
- **Outcome & Financial Result:**
  - Captured incentive share, gas cost, PENDLE accrued.
- **Ajit Jain Post-Mortem & Rule Codified:**
  - Exact rule added to code or invariant guidelines.
```

---

## Living Archive of Pendle Hand Histories

### Case Study 001: The Out-of-Band Yield Drift & Solitary Maker Capture
- **Date & Market:** 2026-09-11 | NVDA (15-OCT-2026) Robinhood Chain (`4663`)
- **Macro Spot & Texture:**
  - NVDA Price: $218.86 | Implied APY: 10.00% | Underlying APY: 17.54% | DTE: 34 Days
  - Incentive Band: `[9.65%, 10.40%]`
  - Maker Depth: Long side = $214.70, **Short side = $0.00**
- **The Setup & Decision:**
  - Discovered existing resting order `0x25b6e378...` (0.05 NVDA) was stuck at `7.79%`, sitting below the `9.65%` minimum incentive line and earning 0 PENDLE/hr.
  - Executed on-chain cancellation (Tx: `0x0123812b...`, Block `59865127`, cost: 0.000009 ETH) and shifted to `9.95%` (Order `0x9fbd180f...`).
- **The Friction / Difficult Spot:**
  1. `web3.py` v6 snake_case `raw_transaction` compatibility.
  2. Potential nonce collisions with shared multi-market bot operations.
  3. Re-cancelling an already-cancelled order causes `LOP: already filled` contract revert.
- **Outcome & Financial Result:**
  - **Incentivized resting value restored from $0.00 to $10.94 (100% of capital).**
  - Captured 100% of the Short-side hourly incentive pool allocation (~100% APR).
  - Rewards immediately began accruing (`0.000007 PENDLE` in first cycle).
- **Ajit Jain Rule Codified:**
  - *Invariant:* `get_active_nvda_orders()` must verify `isActive == True` to avoid attempting redundant on-chain cancellations.
  - *Invariant:* All on-chain broadcasts must include automatic `pending` nonce query and retry loops with exponential backoff.
