"""
Robinhood Chain Pendle Desk Configuration Package
Mirrors Boros config architecture with Robinhood-specific gas economics.
"""
from .market_params import (
    load_market_config,
    get_supported_markets,
    get_min_short_rates,
    get_max_long_rates,
    get_market_metadata,
    validate_order_safety,
    SUPPORTED_MARKETS,
    MIN_SHORT_RATES,
    MAX_LONG_RATES,
)

__all__ = [
    "load_market_config",
    "get_supported_markets",
    "get_min_short_rates",
    "get_max_long_rates",
    "get_market_metadata",
    "validate_order_safety",
    "SUPPORTED_MARKETS",
    "MIN_SHORT_RATES",
    "MAX_LONG_RATES",
]
