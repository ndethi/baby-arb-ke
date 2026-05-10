"""Pricing engine: deterministic landed-cost calculation and margin guard.

This is the single source of truth for the buy decision economics.
Pure Python, no LLM in the calculation path. No randomness. No hidden
side effects. Every fee is named.
"""

from baby_arb.pricing.engine import calculate_landed_cost
from baby_arb.pricing.rules import (
    ENGINE_VERSION,
    MARGIN_FLOOR_PCT,
    MARGIN_REVIEW_BAND_PCT,
)
from baby_arb.pricing.verdict import pricing_verdict

__all__ = [
    "ENGINE_VERSION",
    "MARGIN_FLOOR_PCT",
    "MARGIN_REVIEW_BAND_PCT",
    "calculate_landed_cost",
    "pricing_verdict",
]
