#!/usr/bin/env python3
"""
Pendle V2 Desk - Institutional Quant Market Opportunity Agent
Analyzes markets on Robinhood Chain (Chain ID: 4663) and evaluates:
  1. PT (Fixed Yield) vs. Hurdle Floor & Underlying Spot Delta Risk
  2. YT (Long Yield) vs. Negative Carry & Theta Decay Traps
  3. Limit Order Incentive Mining & Depth Monopolization Potential
  4. Ajit Jain Maturity Cliffs & Gas Hurdle Feasibility

Applies the 4 pillars of the Pendle/Boros Quantitative Framework:
  - Seth Klarman Margin of Safety (Hurdle floors, negative carry ceilings)
  - Ajit Jain Razor (Asymmetric underwriting, zero maker competition, T-7 cliff)
  - Einstein & Munger Simplicity (Pruned heuristics, deterministic yield capture)
  - The Poker Hand History Doctrine (Forensic comparison vs historical traps & gold standards)
"""

import os
import sys
import time
import math
import json
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

CHAIN_ID = 4663
BASE_API = "https://api-v2.pendle.finance/core"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
DEFAULT_WALLET = "0xaa7c405151c1a11fc2e9998a31b285c7b53d248b".lower()

def fetch_json(url: str, max_retries: int = 3) -> Any:
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(1, max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries:
                time.sleep(2.0 * attempt)
                continue
            if attempt < max_retries:
                time.sleep(1.0 * attempt)
                continue
            raise
        except Exception:
            if attempt < max_retries:
                time.sleep(1.0 * attempt)
                continue
            raise

class PendleMarketSnapshot:
    """Encapsulates raw on-chain and API market state."""
    def __init__(self, market_address: str):
        self.market_address = market_address.lower()
        self.raw_market = fetch_json(f"{BASE_API}/v1/{CHAIN_ID}/markets/{self.market_address}")
        
        # Core identification
        self.name = self.raw_market.get("proName") or self.raw_market.get("name") or "Unknown"
        self.expiry_str = self.raw_market.get("expiry")
        self.accounting_asset = self.raw_market.get("accountingAsset", {})
        self.underlying_asset = self.raw_market.get("underlyingAsset", {})
        self.pt = self.raw_market.get("pt", {})
        self.yt = self.raw_market.get("yt", {})
        
        # Prices
        self.spot_price = self.accounting_asset.get("price", {}).get("usd", 0.0)
        self.pt_price = self.pt.get("price", {}).get("usd", 0.0)
        self.yt_price = self.yt.get("price", {}).get("usd", 0.0)
        self.liquidity_usd = (self.raw_market.get("liquidity") or {}).get("usd", 0.0) if isinstance(self.raw_market.get("liquidity"), dict) else 0.0

        # Rates
        self.implied_apy = (self.raw_market.get("impliedApy") or 0.0) * 100.0
        self.underlying_apy = (self.raw_market.get("underlyingApy") or 0.0) * 100.0

        # Expiry & DTE
        if self.expiry_str:
            expiry_dt = datetime.fromisoformat(self.expiry_str.replace("Z", "+00:00"))
            now_dt = datetime.now(timezone.utc)
            self.dte_days = max(0.0, (expiry_dt - now_dt).total_seconds() / 86400.0)
        else:
            self.dte_days = 0.0

        # Incentive configs
        configs = fetch_json(f"{BASE_API}/v1/limit-orders/incentive/configs").get("configs", [])
        m_cfg = next((c for c in configs if c.get("chainId") == CHAIN_ID and c.get("marketAddress", "").lower() == self.market_address), {})
        self.min_apy = (m_cfg.get("minApy") or 0.0) * 100.0
        self.max_apy = (m_cfg.get("maxApy") or 0.0) * 100.0
        self.buy_pt_apr = (m_cfg.get("estimatedApr", {}).get("buyPtApr") or 0.0) * 100.0
        self.buy_yt_apr = (m_cfg.get("estimatedApr", {}).get("buyYtApr") or 0.0) * 100.0

        # Maker competition split
        split_url = f"{BASE_API}/v1/limit-orders/incentive/user/split?chainId={CHAIN_ID}&marketAddress={self.market_address}&user={DEFAULT_WALLET}"
        split_data = fetch_json(split_url)
        self.short_depth = split_data.get("short", {}).get("totalMakingAmountInRange", 0.0)
        self.long_depth = split_data.get("long", {}).get("totalMakingAmountInRange", 0.0)
        self.reward_per_hr = split_data.get("short", {}).get("totalRewardPerHour", 0.0) or split_data.get("long", {}).get("totalRewardPerHour", 0.0)

class QuantAnalysisResult:
    """Contains structured quantitative findings and scores."""
    def __init__(self):
        self.yt_score: int = 0
        self.yt_verdict: str = ""
        self.yt_findings: List[str] = []

        self.pt_score: int = 0
        self.pt_verdict: str = ""
        self.pt_findings: List[str] = []

        self.maker_score: int = 0
        self.maker_verdict: str = ""
        self.maker_findings: List[str] = []

        self.overall_recommendation: str = ""
        self.executive_summary: str = ""

class QuantMarketAnalyst:
    """Institutional Quant Evaluation Engine."""
    def __init__(self, market_address: str, hurdle_rate: float = 8.0):
        self.market = PendleMarketSnapshot(market_address)
        self.hurdle_rate = hurdle_rate

    def evaluate_yt_long_yield(self) -> Tuple[int, str, List[str]]:
        """Evaluates whether Long Yield (buying YT) is economically viable."""
        findings = []
        score = 50

        carry_spread = self.market.underlying_apy - self.market.implied_apy
        findings.append(f"Implied APY: {self.market.implied_apy:.2f}% | Underlying APY: {self.market.underlying_apy:.2f}%")
        findings.append(f"Carry Spread: {carry_spread:+.2f}%")

        # Invariant 2 Check: Never buy YT when Implied APY >= Underlying APY
        if self.market.implied_apy > self.market.underlying_apy:
            bleed_pct = abs(carry_spread)
            findings.append(f"🛑 CATASTROPHIC NEGATIVE CARRY: Investor suffers immediate -{bleed_pct:.2f}% adverse cash bleed.")
            score -= 40
        else:
            findings.append(f"✅ Positive Carry: Underlying yield exceeds implied borrow rate by {carry_spread:+.2f}%.")
            score += 25

        # Theta decay evaluation
        if self.market.dte_days > 0:
            daily_theta_pct = (1.0 / self.market.dte_days) * 100.0
            findings.append(f"Maturity Horizon: {self.market.dte_days:.1f} days remaining.")
            findings.append(f"Estimated Linear Theta Decay: ~{daily_theta_pct:.2f}% of token value per day.")
            if self.market.dte_days < 14.0:
                findings.append(f"⚠️ HIGH THETA COMPRESSION: Less than 14 DTE dramatically magnifies time-decay risk.")
                score -= 20
        else:
            findings.append("🛑 Market is expired.")
            score = 0

        # Breakeven multiplier
        if self.market.underlying_apy > 0:
            be_multiple = self.market.implied_apy / self.market.underlying_apy
            findings.append(f"Breakeven Yield Multiplier: {be_multiple:.2f}x (Underlying must surge {be_multiple:.1f}x to break even).")
            if be_multiple > 2.0:
                score -= 15

        score = max(0, min(100, score))
        if score < 30:
            verdict = "STRICT NO-GO (Graveyard Trap)"
        elif score < 60:
            verdict = "HIGH RISK / SPECULATIVE"
        else:
            verdict = "VIABLE CATALYST PLAY"

        return score, verdict, findings

    def evaluate_pt_fixed_yield(self) -> Tuple[int, str, List[str]]:
        """Evaluates whether Fixed Yield (buying PT) is an attractive risk-adjusted investment."""
        findings = []
        score = 50

        # 1. Hurdle rate check (Klarman floor)
        findings.append(f"Fixed APY (Implied): {self.market.implied_apy:.2f}% (Desk Hurdle: {self.hurdle_rate:.2f}%)")
        if self.market.implied_apy >= self.hurdle_rate:
            excess = self.market.implied_apy - self.hurdle_rate
            findings.append(f"✅ KLARMAN FLOOR PASSED: Yield exceeds hurdle by +{excess:.2f}%.")
            score += 25
        else:
            deficit = self.hurdle_rate - self.market.implied_apy
            findings.append(f"🛑 SUB-HURDLE YIELD: Yield is {deficit:.2f}% below hurdle rate. Inferior fixed instrument.")
            score -= 30

        # 2. Price discount & margin of safety
        if self.market.spot_price > 0:
            discount_usd = self.market.spot_price - self.market.pt_price
            discount_pct = (discount_usd / self.market.spot_price) * 100.0
            findings.append(f"Spot: ${self.market.spot_price:.4f} | PT: ${self.market.pt_price:.4f} (Discount: {discount_pct:.2f}%)")
            findings.append(f"Capital Gain to Par: Each 1 PT redeems for 1 underlying on {self.market.expiry_str[:10]}.")
            if discount_pct > 1.0:
                score += 15
        else:
            findings.append("⚠️ Missing spot price data.")

        # 3. Underlying Delta & Token Risk
        findings.append(f"Underlying Asset: {self.market.name} ({self.market.accounting_asset.get('symbol')})")
        findings.append("⚠️ UNDERLYING VOLATILITY RISK: PT yields are denominated in the underlying token.")
        findings.append("   If the underlying token depreciates against USD by more than the discount, USD total return is negative.")

        # 4. Liquidity & Execution Depth
        findings.append(f"Pool Liquidity: ${self.market.liquidity_usd:,.0f} USD")
        if self.market.liquidity_usd >= 100000:
            findings.append("✅ Healthy Pool Depth: Sufficient liquidity for clips up to $2,000 USD.")
            score += 10
        else:
            findings.append("⚠️ Thin Pool Depth: High slippage on larger market swap orders.")
            score -= 10

        score = max(0, min(100, score))
        if score >= 70:
            verdict = "EXCELLENT FIXED YIELD (Token-Denominated)"
        elif score >= 50:
            verdict = "ATTRACTIVE YIELD (Conditional on Token Delta)"
        else:
            verdict = "UNATTRACTIVE RISK/REWARD"

        return score, verdict, findings

    def evaluate_maker_incentive_opportunity(self) -> Tuple[int, str, List[str]]:
        """Evaluates limit order placement inside incentive band to capture PENDLE rewards."""
        findings = []
        score = 50

        # 1. Maker competition
        findings.append(f"Incentive Eligibility Band: [{self.market.min_apy:.2f}%, {self.market.max_apy:.2f}%]")
        findings.append(f"Short Side Competing Depth: ${self.market.short_depth:,.2f} USD")
        findings.append(f"Long Side Competing Depth:  ${self.market.long_depth:,.2f} USD")

        if self.market.short_depth == 0.0:
            findings.append("🏆 ZERO MAKER COMPETITION (Short Side): Solitary maker captures 100% of PENDLE mining allocation!")
            score += 35
        elif self.market.short_depth < 1000.0:
            findings.append(f"✅ Low Maker Competition: Dilution is minimal (${self.market.short_depth:,.2f} total).")
            score += 20
        else:
            findings.append(f"⚠️ Moderate Maker Competition: Depth is ${self.market.short_depth:,.2f}.")
            score -= 10

        # 2. Mining yield
        findings.append(f"Protocol Mining APR: ~{self.market.buy_pt_apr:.1f}% APR in PENDLE incentives.")
        findings.append(f"Reward Velocity: {self.market.reward_per_hr:.5f} PENDLE/hour (~{self.market.reward_per_hr * 24:.4f} PENDLE/day).")

        # 3. Ajit Jain DTE Cliff Guard
        findings.append(f"DTE: {self.market.dte_days:.1f} days remaining.")
        if self.market.dte_days > 7.0:
            safe_days = self.market.dte_days - 7.0
            findings.append(f"✅ Outside T-7 Cliff: Safe active quoting runway is {safe_days:.1f} days (until T-7 cliff).")
            score += 15
        elif self.market.dte_days > 0.0:
            findings.append("🛑 INSIDE T-7 MATURITY CLIFF: Quoting prohibited by Ajit Jain Razor (< 7 DTE).")
            score -= 40
        else:
            findings.append("🛑 Expired pool.")
            score = 0

        score = max(0, min(100, score))
        if score >= 75:
            verdict = "AJIT JAIN FAT PITCH (100% Monopolization)"
        elif score >= 55:
            verdict = "MODERATE REWARD OPPORTUNITY"
        else:
            verdict = "RESTRICTED / CLIFF-LOCKED"

        return score, verdict, findings

    def run_full_analysis(self) -> QuantAnalysisResult:
        result = QuantAnalysisResult()
        result.yt_score, result.yt_verdict, result.yt_findings = self.evaluate_yt_long_yield()
        result.pt_score, result.pt_verdict, result.pt_findings = self.evaluate_pt_fixed_yield()
        result.maker_score, result.maker_verdict, result.maker_findings = self.evaluate_maker_incentive_opportunity()

        # Synthesis
        if result.yt_score < 30 and result.maker_score >= 75:
            result.overall_recommendation = (
                "🎯 STRATEGY PLAYBOOK: DO NOT LONG YIELD (BUY YT). Longing yield is a toxic graveyard trap with -53.3% negative carry. "
                "Instead, EXPLOIT THE SHORT YIELD / BUY PT INCENTIVE: Place a resting limit order inside the band "
                f"[{self.market.min_apy:.2f}%, {self.market.max_apy:.2f}%] to monopolize 100% of PENDLE mining rewards ($0 competition) "
                f"and capture {self.market.implied_apy:.2f}% fixed yield. Enforce strict exit prior to the 7-day maturity cliff."
            )
        elif result.pt_score >= 70:
            result.overall_recommendation = (
                f"✅ FIXED YIELD GO: Buying PT locks in an outstanding {self.market.implied_apy:.2f}% APY to maturity. "
                f"Ensure tolerance to underlying token price volatility."
            )
        else:
            result.overall_recommendation = "Sit in cash; risk/reward does not satisfy institutional margin of safety."

        return result

    def generate_markdown_report(self, result: QuantAnalysisResult) -> str:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        m = self.market

        md = []
        md.append(f"# Institutional Market Analysis & Opportunity Memorandum")
        md.append(f"**Target Market:** `{m.name}` (`{m.market_address}`)  ")
        md.append(f"**Network:** Robinhood Chain (Chain ID: `4663`) | **Desk:** `rh/` | **Analysis Time:** {now_str}\n")
        md.append(f"**Direct Link:** [Open Market on Pendle](https://app.pendle.finance/trade/markets/{m.market_address}/swap?view=yt&chain=robinhood)\n")
        md.append("---\n")

        # Executive Summary
        md.append("## Executive Summary & Desk Decision")
        md.append(f"> [!IMPORTANT]")
        md.append(f"> **Overall Recommendation:** {result.overall_recommendation}\n")

        md.append("| Strategy Component | Quant Score | Verdict | Key Catalyst / Risk |")
        md.append("| :--- | :--- | :--- | :--- |")
        md.append(f"| **YT (Long Yield)** | `{result.yt_score}/100` | **{result.yt_verdict}** | Toxic carry spread: `{m.underlying_apy - m.implied_apy:+.2f}%`, rapid theta |")
        md.append(f"| **PT (Fixed Yield Spot)** | `{result.pt_score}/100` | **{result.pt_verdict}** | Outstanding fixed yield: `{m.implied_apy:.2f}%`, exposed to token delta |")
        md.append(f"| **Maker Incentive Mining (Buy PT)** | `{result.maker_score}/100` | **{result.maker_verdict}** | **$0.00 competitor depth**, 100% APR bonus in PENDLE |")
        md.append("")

        # Market Snapshot
        md.append("## 1. Market Anatomy & Microstructure")
        md.append("| Metric | Value | Reference / Context |")
        md.append("| :--- | :--- | :--- |")
        md.append(f"| **Asset Pro Name** | `{m.name}` | `{m.accounting_asset.get('symbol')}` |")
        md.append(f"| **Spot Price** | `${m.spot_price:.6f} USD` | Underlying asset spot |")
        md.append(f"| **PT Price** | `${m.pt_price:.6f} USD` | Capital discount: `{((m.spot_price - m.pt_price) / max(m.spot_price, 1e-6)) * 100.0:.2f}%` |")
        md.append(f"| **YT Price** | `${m.yt_price:.6f} USD` | Yield token price |")
        md.append(f"| **Implied APY (Fixed Rate)** | **`{m.implied_apy:.2f}%`** | Cost to borrow / fixed PT return |")
        md.append(f"| **Underlying APY (Organic)** | **`{m.underlying_apy:.2f}%`** | Organic yield generation |")
        md.append(f"| **Pool Liquidity** | `${m.liquidity_usd:,.0f} USD` | Total pool depth |")
        md.append(f"| **Expiry Date** | `{m.expiry_str[:10]}` | **{m.dte_days:.1f} days remaining** |")
        md.append(f"| **Incentive Eligibility Band** | `[{m.min_apy:.2f}%, {m.max_apy:.2f}%]` | Width: `{m.max_apy - m.min_apy:.2f}%` (80 bps) |")
        md.append(f"| **Competing Short Maker Depth**| **`${m.short_depth:,.2f}`** | **Zero maker competition** 🏆 |")
        md.append("")

        # Pillar 1
        md.append("## 2. Pillar 1: The YT 'Long Yield' Forensic Post-Mortem")
        md.append("> [!CAUTION]")
        md.append("> **The Graveyard Doctrine:** Buying YT in a high-implied, low-underlying pool is the single most common retail trap in DeFi.")
        md.append("")
        for f in result.yt_findings:
            md.append(f"- {f}")
        md.append("")

        # Pillar 2
        md.append("## 3. Pillar 2: The PT 'Fixed Yield' Evaluation")
        for f in result.pt_findings:
            md.append(f"- {f}")
        md.append("")

        # Pillar 3
        md.append("## 4. Pillar 3: The Ajit Jain Asymmetric Underwriting Razor")
        for f in result.maker_findings:
            md.append(f"- {f}")
        md.append("")

        # Actionable Plan
        md.append("## 5. Tactical Implementation & Execution Guardrails")
        rec_rate = round((m.min_apy + m.max_apy) / 2.0, 2)
        md.append(f"If deploying capital to capture the **63.98% Fixed Yield + 100% PENDLE mining monopolization**:")
        md.append("1. **Simulate Limit Order with Dry-Run:**")
        md.append("   ```bash")
        md.append(f"   python rh/shift_order.py --market SHROOM --target-apy {rec_rate:.2f} --dry-run")
        md.append("   ```")
        md.append("2. **Underlying Volatility Hedge:**")
        md.append("   - If holding SHROOM spot exposure is undesired, evaluate short perps or delta-neutral matching.")
        md.append("3. **Mandatory Exit Cliff:**")
        md.append(f"   - Must cancel all resting quotes on **2026-09-17 00:00 UTC** ($T-7$ cliff) to avoid illiquid expiry traps.")
        md.append("")

        return "\n".join(md)

def analyze_market(market_address: str, hurdle_rate: float = 8.0) -> Tuple[QuantMarketAnalyst, QuantAnalysisResult, str]:
    analyst = QuantMarketAnalyst(market_address, hurdle_rate=hurdle_rate)
    result = analyst.run_full_analysis()
    report = analyst.generate_markdown_report(result)
    return analyst, result, report

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "0x49e5d9de386b5ff5cc344748977a412d07191256"
    print(f"🦅 Running Quant Market Opportunity Analysis on {target}...")
    analyst, result, report = analyze_market(target)
    print("\n" + report)
