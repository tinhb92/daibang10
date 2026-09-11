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
- Every on-chain cancellation on Robinhood Chain costs gas (~72,000 gas units, ~$0.022 USD).
- **Invariant:** **Never micro-recenter for minor basis point wiggles.**
- Orders are only re-centered when:
  1. The market implied APY has drifted completely outside the incentive eligibility window `[minApy, maxApy]`, causing the incentive harvest to hit zero.
  2. The drift has sustained across at least 1 hourly snapshot boundary (preventing reacting to flash wicks).
  3. The projected reward over 24h exceeds the gas cancellation cost by at least **5.0x**.

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
- Terminal stdout is reserved for high-signal events (fills, on-chain confirmations, drift alerts, heartbeats).
- Routine status belongs in persistent markdown artifacts ([`portfolio_manager_view.md`](file:///Users/tin/.gemini/antigravity-ide/brain/70ed835e-5848-4729-a254-0318f19d3a0e/portfolio_manager_view.md)), not transient console spam.

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
- **Hard Rule:** **Never establish new resting quotes inside the final 7 days of a pool's maturity ($T-7$ cliff).** Cancel all resting orders and hold underlying or PT to maturity for flawless 1:1 redemption.

---

## Core Principle 4: "Empirical Realism — The Poker Hand History Doctrine"
> *"In the real world, brilliant algorithms die on edge cases that historical data predicted days in advance."*

- **The Poker Hand History Doctrine:**
  - Complex market making mirrors deep-stack, high-stakes poker. Optimal play is not derived solely from pure mathematical abstractions, but from studying **difficult spots, opponent tendencies, and historical hand histories**.
  - Document every difficult spot: What was the board texture (liquidity, underlying yield vs. implied rate, days to maturity)? Who held position (toxic maker flow vs. passive arbitrageur)? Where was the inflection point?
- **Data > Code:**
  - Detailed historical logs of real fills, adverse selections, and rate blowouts are infinitely more valuable than hundreds of lines of untested predictive heuristics.

---

## The Pendle Historian Persona (The Post-Mortem & Forensic Desk)

A permanent analytical persona dedicated to logging, categorizing, and dissecting live Pendle scenarios and historical market moves into a cumulative archive of institutional memory.

### 1. Core Mandate
- Continuously catalog both **Profitable Scenarios (The Gold Standards)** and **Unprofitable Scenarios (The Graveyard)**.
- Transform raw on-chain state, limit order fills, rate divergences, and Telegram alerts into structured case studies.
- Extract concrete, code-enforceable invariants for [`rh/config/market_params.py`](file:///Users/tin/eagle/daibang10/rh/config/market_params.py) and [`rh/market_constraints.json`](file:///Users/tin/eagle/daibang10/rh/config/markets.json) after every high-volatility event.

### 2. The Case Study Taxonomy (Hand History Schema)
Every recorded historical scenario must be documented under the following taxonomy:

```markdown
### Case Study [ID]: [Descriptive Title]
- **Date & Market:** [e.g. 2026-09-11 | NVDA 15OCT2026 Chain 4663]
- **Macro Spot & Texture:**
  - Underlying Price & Yield: [e.g. $218.86 NVDA, 17.54% APY]
  - Implied APY & Incentive Band: [e.g. 10.00%, Band: 9.65% - 10.40%]
  - Liquidity Depth & Days to Expiry (DTE): [e.g. $81k TVL, 34 DTE]
  - Maker Competition: [e.g. Short depth = $0.00]
- **The Setup & Decision:**
  - Order type (PT buyer / YT seller), rate, size, and economic rationale.
- **The Friction / Difficult Spot:**
  - Did the market shift? Did implied rates spike or crash? Did incentive bands compress?
- **Outcome & Financial Result:**
  - Realized yield, time-in-trade, fill status, capital preservation outcome.
- **Ajit Jain Post-Mortem & Codified Invariants:**
  - *What worked or what went wrong?*
  - *The exact rule codified into Desk engine to prevent recurrence or replicate success.*
```

### 3. Living Archive Archetypes
- **The Graveyard (Toxic Traps to Avoid):**
  - *The Euphoric YT Squeeze Trap:* Buying YT at peak euphoric implied APYs (e.g. 400%+ on sNUKE or 70% on USDe), suffering an instant 70–90% capital destruction when yields normalize.
  - *The $T-7$ Expiry Theta Abyss:* Holding YT into the final 7 days of maturity. Theta acceleration exponentially decays YT value to $0.00, annihilating any residual carry.
  - *The Sub-Hurdle Fixed Yield Mirage:* Locking capital into a fixed PT below the 8.00% hurdle (e.g. PFE @ 3.90%), suffering opportunity loss while gas costs to exit exceed returns.
  - *The Gas-Erosion Micro-Churn:* Re-centering orders on tiny basis point wiggles on L2 (Robinhood Chain), where on-chain cancellation fees ($0.022/tx) erode weeks of mining yield.
- **The Gold Standard (Profitable Plays to Replicate):**
  - *The Genesis Window Monopolization:* Being the solitary maker in a virgin pool (e.g. NVDA Short side), capturing 100% of protocol incentive emissions at 100%+ APR on capital.
  - *The Klarman Margin of Safety PT Arbitrage:* Buying PT at extreme discounts during transient depegs/panics (e.g. ezETH depeg), securing guaranteed par redemption at maturity.
  - *The Basis Divergence Harvest:* Shorting yield (buying PT) when Implied APY is artificially depressed vs huge underlying yield, while simultaneously capturing maker incentives.

---

## Codified Historical Case Studies

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

---

### Case Study 002: The sNUKE 300% Yield Crash & YT Implosion
- **Date & Market:** 2026-09-08 to 2026-09-11 | sNUKE (24-SEP-2026) Robinhood Chain (`4663`)
- **Macro Spot & Texture:**
  - Underlying: Nuclear Power Synthetic Yield ($15.26 spot) | DTE: 13 Days
  - Initial Implied APY: **399.35%** (Sep 8)
  - Normalized Implied APY: **104.68%** (Sep 11)
  - Underlying Yield: 116.51%
  - TVL: Collapsed from $61,214 to $33,246 (-45.7% liquidity drain)
- **The Microstructure Catalyst & Crash:**
  - On Sept 8, initial speculative buying of YT-sNUKE pushed the market implied APY to an irrational **399.35%**, pricing in explosive short-term dividend yields.
  - As actual underlying yields settled at ~116%, arbitrageurs minted PT + YT and dumped YT into the pool.
  - Within 24 hours (Sept 8 ➔ Sept 9), Implied APY collapsed from **399.35% ➔ 124.52%** (-27,483 bps crash!).
  - YT-sNUKE price cratered from ~$1.85 down to $0.38 (-79.4% loss in 72 hours).
- **Ajit Jain Post-Mortem & Codified Invariants:**
  - *The Fatal Mistake:* Buying YT at the peak of an implied yield spike is financial suicide; when implied APY compresses, YT loses both rate value and time value simultaneously (double-whammy decay).
  - *The Winning Play:* Disciplined desks bought PT-sNUKE at 399% fixed APY (buying a massive synthetic discount on spot) and held to maturity.
  - *The Invariant Codified:*
    1. **Max Long Rate Ceiling:** Enforce a strict ceiling (`max_long_ceiling`) of 116.76% in [`rh/config/markets.json`](file:///Users/tin/eagle/daibang10/rh/config/markets.json). Any YT buy or Long quote above this level is hard-rejected.

---

### Case Study 003: The sNET 16,000% Hyper-Yield & The Final Week Theta Cliff
- **Date & Market:** 2026-09-04 to 2026-09-11 | sNET (17-SEP-2026) Robinhood Chain (`4663`)
- **Macro Spot & Texture:**
  - Asset: Cloudflare Synthetic Equity ($641.46 spot) | PT: $593.40 | YT: $48.05
  - Expiry: 2026-09-17 (DTE: 5.9 Days — **Inside the $T-7$ Hazard Zone**)
  - Historical Implied APY Trajectory:
    - 2026-09-04: 3,768.97% (TVL: $1.49M)
    - 2026-09-06: 15,937.05% (Peak Frenzy)
    - 2026-09-08: 16,191.45% (All-Time High)
    - 2026-09-11: 12,131.69% (Underlying: 19,378.94%, TVL: $904k)
- **The Microstructure Dynamics:**
  - As sNET entered its final week ($T-7$), the market experienced a violent divergence:
    - Underlying yield climbed to 19,378%, but Implied APY collapsed from 16,191% down to 12,131% (-4,060 bps).
    - Protocol incentive emissions remained huge (**0.1666 PENDLE/hr**, ~32x higher than NVDA).
    - However, with only 5.9 days remaining, **YT-sNET ($48.05) loses ~$8.14 per day purely from time decay ($\theta$)**.
- **Ajit Jain Post-Mortem & Codified Invariants:**
  - *The Edge vs. The Trap:* Collecting 0.1666 PENDLE/hr (~$0.40/hr) is attractive, but holding YT inventory across the maturity cliff guarantees total capital loss.
  - *The Winning Play:* Provide passive Short liquidity (PT buying) strictly within the `[11333%, 13333%]` incentive band with instantaneous fill hedging.
  - *The Invariant Codified:*
    1. **Ajit Jain $T-7$ Day Razor:** Mark markets with DTE < 7.0 days with **`⚠️ EXTREME HAZARD`** in radar daemons.
    2. Enforce 200 bps buffer on hyper-yield markets. Never accumulate speculative unhedged YT inventory in the final 7 days.

---

### Case Study 004: The Ethena USDe/sUSDe Yield Normalization (Macro Historical Standard)
- **Historical Scope:** March 2024 – July 2024 | Ethereum & Arbitrum
- **Context & Macro Catalyst:**
  - During the Q1 2024 crypto bull run (BTC $73k), CEX perpetual funding rates spiked to 60%–110% annualized.
  - Ethena USDe minting surged, and Pendle's USDe/sUSDe pools exploded to >$2 Billion TVL.
  - Speculators aggressively bought YT-sUSDe at 40%–70% implied APYs to farm 20x–50x Ethena Shards.
- **The Breakdown:**
  - As market volatility cooled, funding rates compressed to 8%–12%.
  - YT holders who paid 50%+ implied rates bled out completely. At maturity, YT expired to $0.00, and cumulative yield distributions failed to cover the purchase price by over 60%.
  - Meanwhile, PT-sUSDe buyers locked in 30%–45% guaranteed fixed USD yield on billions of institutional capital.
- **Codified Invariant:**
  - *The Klarman Fixed Anchor:* In euphoric yield regimes, **always be the seller of yield (PT buyer)**. The crowd systematically overpays for yield options (YT) to chase points/airdrop hype.

---

### Case Study 005: The ezETH Depeg & Parity Convergence Squeeze
- **Date & Market:** April 24, 2024 | ezETH (Renzo) on Ethereum Mainnet
- **Macro Texture & Event:**
  - Renzo announced an unpopular tokenomics model, triggering a panic selloff of ezETH on DEXes.
  - ezETH spot price briefly depegged by ~15% down to 0.85 ETH.
  - In Pendle AMM pools, PT-ezETH plunged dramatically as panicking liquidity providers dumped PT to exit back into raw ETH.
- **The Quantitative Execution:**
  - Smart quantitative desks recognized that under Renzo's smart contracts, 1 ezETH remained 100% backed 1:1 by staked ETH on the consensus layer, and would be redeemable upon EigenLayer withdrawal enablement.
  - Desks bought PT-ezETH at effective annual yields exceeding **65% APY**.
  - Within 48 hours, the DEX peg was restored to 0.99 ETH. PT-ezETH appreciated instantly by +14% in spot terms plus the locked accrual yield.
- **Codified Invariant:**
  - *Panic Convergence Arbitrage:* Structural market depegs create massive PT discount spikes. When underlying protocol solvency is verified, buying PT during panic sweeps yields the highest risk-adjusted alpha in DeFi.

---

## Comparative Playbook: What Separates Winners from Losers on Pendle V2

| Dimension | ❌ The Fatal Mistakes (Retail & Naive Makers) | 🏆 The Winning Plays (Quantitative Institutional Desk) |
| :--- | :--- | :--- |
| **Yield Selection** | **Chasing peak implied APY:** Buys YT when implied yield is 300%+ (e.g. sNUKE), then watches rate collapse to 100%. | **Selling euphoric yield / Buying PT:** Locks in massive guaranteed fixed return (PT) when implied yield is artificially pumped. |
| **Maturity Cliff** | **Holding YT into final week:** Holds YT-sNET at 5 DTE, watching $48 token bleed to $0.00 in 120 hours. | **Enforcing $T-7$ Razor:** Exits or delta-neutralizes all YT exposure before final 7 days; holds PT for 1:1 par redemption. |
| **Incentive Capture**| **Quoting out-of-band:** Lets orders drift outside `[minApy, maxApy]`, earning 0 rewards while locking capital. | **Edge-Rung Anchoring:** Uses dynamic monitoring daemons to rest strictly at the campaign edge with safe buffer. |
| **Gas Economics** | **Continuous micro-shifts:** Cancels and moves orders for 5 bps moves on L2, spending $0.022 per cancel until gas exceeds rewards. | **5.0x Gas Governor:** Only shifts when 24h expected rewards exceed gas costs by $\ge 5.0\times$. Aborts if gas units $> 720,000$. |
| **Maker Depth** | **Bidding into crowded walls:** Competes with $500k of existing makers, diluting incentive share to <1% APR. | **Monopolizing Virgin Depth:** Targets pools with $0.00 competing depth (e.g. NVDA Short side), taking 100% of emissions. |

---

## The 4 Immutable Rules for the Pendle Robinhood Desk

1. **Rule 1 (Seth Klarman Floor):** Never buy PT or quote Short below the 8.00% base hurdle rate. If market implied APY is 3.90% (PFE), sit in cash.
2. **Rule 2 (The Ajit Jain $T-7$ Razor):** Never accumulate unhedged YT or write new speculative policies inside the final 7 days of contract maturity (e.g. sNET).
3. **Rule 3 (The 5x Gas Economic Guard):** Never submit an on-chain cancellation unless the projected incremental reward is at least 5.0x the transaction fee.
4. **Rule 4 (24/7 Autonomous Radar & Heartbeat):** Keep [`rh/monitor_nvda_moves.py`](file:///Users/tin/eagle/daibang10/rh/monitor_nvda_moves.py) running 24/7 with hourly heartbeat alerts to ensure zero unmonitored drift and instant fill detection.
