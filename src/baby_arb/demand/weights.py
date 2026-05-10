"""Signal weights for the composite demand score.

Recalibrate quarterly based on Margin Evaluator data.
"""

from __future__ import annotations

from decimal import Decimal

DEFAULT_WEIGHTS: dict[str, Decimal] = {
    "jiji_sold_30d": Decimal("0.30"),
    "jiji_supply_demand_ratio": Decimal("0.20"),
    "retail_stockout_weeks": Decimal("0.15"),
    "fb_intent_score": Decimal("0.15"),
    "pigiame_volume": Decimal("0.10"),
    "ig_kenyan_mentions": Decimal("0.05"),
    "tiktok_kenyan_mentions": Decimal("0.05"),
}
