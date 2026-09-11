# Competitors & Whales Intelligence Desk

> **Desk:** Antifragile Quant & Market Historian Desk ([`taleb`](file:///Users/tin/eagle/daibang10/.agents/agents/taleb/agent.md))  
> **Protocol Scope:** **Pendle V2 ONLY (All Chains)**  
> **Time Horizon:** Last 3 Months (June 19, 2026 – September 11, 2026)  
> **Live Monitor Tooling:** [`rh/competitors/monitor_whale_tendency.py`](file:///Users/tin/eagle/daibang10/rh/competitors/monitor_whale_tendency.py)  
> **Mined Dataset:** [`rh/research/pendlev2_top_whales_3months.json`](file:///Users/tin/eagle/daibang10/rh/research/pendlev2_top_whales_3months.json)

---

## Master Dossier Index

This directory maintains comprehensive forensic profiles on the dominant liquidity makers, institutional yield syndicates, and quant whales active across Pendle V2.

### 1. Macro Census & Ecosystem Audit
* 📊 [**`pendlev2_top_whales_3month_census.md`**](file:///Users/tin/eagle/daibang10/competitors/pendlev2_top_whales_3month_census.md):
  * Complete 3-month ranking of all 332 active makers across Ethereum, Arbitrum, Base, BSC, Monad, Plasma, Robinhood, and HyperEVM.
  * Breakdown of the Top 20 accounts capturing >$185k in protocol incentives.
  * Quantitative analysis of the 4 winning behavioral archetypes (Short-Yield Snipers, Delta-Neutral MMs, New Chain Colonists, and L2 Specialists).

### 2. In-Depth Competitor Profiles

| Rank | Dossier Link | Entity Name / Archetype | Primary Chains | 3-Mo. PENDLE Harvest | Active Resting Capital | Core Strategy & Desk Takeaway |
| :---: | :--- | :--- | :--- | :---: | :---: | :--- |
| **#1** | [**`0xb1350a` Profile**](file:///Users/tin/eagle/daibang10/competitors/0xb1350a_the_short_yield_titan.md) | **The Short-Yield Titan** | Ethereum (1), Monad (143) | **`13,541.86 P`** (~$33.8k) | **`$136,583 USD`** | **68.4% Short Yield (PT Buyer)**. Eliminates negative carry; compounds PT discounts into par value while harvesting 200–500 PENDLE/wk. |
| **#2** | [**`0xc693b4` Profile**](file:///Users/tin/eagle/daibang10/competitors/0xc693b4_the_cross_chain_yield_king.md) | **Cross-Chain Yield King** | ETH, Monad, Base, Plasma | **`9,675.63 P`** (~$24.2k) | **`$371,505 USD`** | **80.0% Long Yield**. Largest active resting book on Pendle V2. Deploys wide liquidity across 7 pools to absorb taker flows. |
| **#4** | [**`0x9c80a9` Profile**](file:///Users/tin/eagle/daibang10/competitors/0x9c80a9_the_delta_neutral_mm.md) | **Delta-Neutral MM** | ETH, BSC, Monad, Plasma | **`4,198.63 P`** (~$10.5k) | **`$61,509 USD`** | **50.9% Long / 49.1% Short**. Avellaneda-Stoikov pure market maker. Quotes both sides across 10 pools, double-dipping long and short reward pools. |
| **#5** | [**`0xa8236e` Profile**](file:///Users/tin/eagle/daibang10/competitors/0xa8236e_the_arbitrum_clob_monopoly.md) | **Arbitrum CLOB Monopoly** | Arbitrum (42161) ONLY | **`4,196.82 P`** (~$10.5k) | **`$85,598 USD`** | **Arbitrum Specialist**. Exploits near-zero gas on L2 to continuously re-center quotes tick-for-tick with zero static drift. |
| **#41**| [**`0x743d7b` Profile**](file:///Users/tin/eagle/daibang10/competitors/0x743d7b_mega_whale_profile.md) | **Robinhood Chain Goliath** | Robinhood (4663) + 7 chains | **`676.61 P`** (~$1.7k) | **`$812,498 USD`** | **Robinhood Monopolist**. Controls 85.8% of RH chain. Sits on coarse round numbers (50%), creating the **Static Drift Blindspot** our desk exploits. |

---

## Real-Time Competitor Telemetry Commands

```bash
# Run one-off audit snapshot of local whale 0x743d7b:
python3 rh/competitors/monitor_whale_tendency.py --once

# Run continuous 5-minute background monitoring daemon:
python3 rh/competitors/monitor_whale_tendency.py --interval 300

# Re-run global 3-month whale census across all chains:
python3 rh/research/mine_pendlev2_3month_whales.py
```
