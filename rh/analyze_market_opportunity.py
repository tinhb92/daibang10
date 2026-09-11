#!/usr/bin/env python3
"""
CLI Tool: Analyze Pendle V2 Market Opportunity (Robinhood Desk)
Usage:
  python rh/analyze_market_opportunity.py --market SHROOM
  python rh/analyze_market_opportunity.py --market 0x49e5d9de386b5ff5cc344748977a412d07191256
"""

import os
import sys
import argparse

RH_DIR = os.path.dirname(os.path.abspath(__file__))
if RH_DIR not in sys.path:
    sys.path.insert(0, RH_DIR)

from agents.pt_quant_agent import analyze_market

NAMED_MARKETS = {
    "SHROOM": "0x49e5d9de386b5ff5cc344748977a412d07191256",
    "NVDA": "0x206a5cd00e9ffabb8ca564076b64799a78df19b9",
    "sNUKE": "0x8547b391a65deb89c41a4c3b2eb1502d0bbc566a",
    "SGOV": "0xd6e26e957b3207a5c618213d928647ec84150ca0",
    "sNET": "0x23c68474e3cd533a2f952a0fb998f1867e57d27f",
    "PFE": "0x892defbf510d9baa96dbd2a51b13e879a857a79b"
}

def main():
    parser = argparse.ArgumentParser(description="Pendle V2 Market Opportunity & Yield Quant Analyst")
    parser.add_argument("--market", type=str, default="SHROOM", help="Market name or contract address (default: SHROOM)")
    parser.add_argument("--hurdle", type=float, default=8.0, help="Minimum acceptable PT hurdle rate (default: 8.0%%)")
    parser.add_argument("--save-artifact", type=str, default=None, help="Path to save markdown analysis")
    args = parser.parse_args()

    m_target = NAMED_MARKETS.get(args.market, args.market)
    print(f"================================================================")
    print(f"🦅 PENDLE V2 QUANT DESK: EVALUATING MARKET OPPORTUNITY")
    print(f"Target: {args.market} ({m_target})")
    print(f"Hurdle Rate: {args.hurdle:.2f}% APY")
    print(f"================================================================\n")

    analyst, result, report = analyze_market(m_target, hurdle_rate=args.hurdle)
    print(report)

    if args.save_artifact:
        with open(args.save_artifact, "w") as f:
            f.write(report)
        print(f"\n✅ Report written to {args.save_artifact}")

if __name__ == "__main__":
    main()
