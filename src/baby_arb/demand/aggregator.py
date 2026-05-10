"""Compose a ProductSignal from raw DemandSignals.

Pure function. No I/O. Maps raw counts/scores to a normalised demand_score.
"""

from __future__ import annotations

from decimal import Decimal

from baby_arb.demand.weights import DEFAULT_WEIGHTS
from baby_arb.models.demand import DemandSignals, ProductSignal


def compose_signal(
    name: str,
    signals: DemandSignals,
    *,
    brand: str | None = None,
    model: str | None = None,
    category: str | None = None,
) -> ProductSignal:
    """Compute composite demand score from raw signals.

    Each signal is normalised to a 0-1 sub-score, then weighted.
    Missing signals are tracked for confidence assessment.

    Args:
        name: Display name of the product.
        signals: Raw signal block.

    Returns:
        ProductSignal with demand_score, confidence, recommendation.
    """
    sub_scores: dict[str, Decimal] = {}
    missing: list[str] = []

    # Jiji 30-day sold count: 0 → 0, 5 → 0.5, 15+ → 1.0
    if signals.jiji_sold_30d is not None:
        sub_scores["jiji_sold_30d"] = _saturate(Decimal(signals.jiji_sold_30d), Decimal("15"))
    else:
        missing.append("jiji_sold_30d")

    # Supply tightness: active / max(1, sold). Tight = <0.5 → score high.
    if signals.jiji_active_listings is not None and signals.jiji_sold_30d is not None:
        ratio = Decimal(signals.jiji_active_listings) / Decimal(max(1, signals.jiji_sold_30d))
        # Score = 1 if ratio < 0.3, 0 if ratio > 2
        if ratio <= Decimal("0.3"):
            sub_scores["jiji_supply_demand_ratio"] = Decimal("1")
        elif ratio >= Decimal("2"):
            sub_scores["jiji_supply_demand_ratio"] = Decimal("0")
        else:
            sub_scores["jiji_supply_demand_ratio"] = (
                Decimal("2") - ratio
            ) / Decimal("1.7")
    else:
        missing.append("jiji_supply_demand_ratio")

    # Retail stockout: weeks_out_of_stock saturated at 8
    if signals.jumia_weeks_out_of_stock is not None:
        sub_scores["retail_stockout_weeks"] = _saturate(
            Decimal(signals.jumia_weeks_out_of_stock), Decimal("8")
        )
    elif signals.jumia_stock == "out_of_stock":
        sub_scores["retail_stockout_weeks"] = Decimal("0.5")
    else:
        missing.append("retail_stockout_weeks")

    if signals.fb_group_intent_score is not None:
        sub_scores["fb_intent_score"] = signals.fb_group_intent_score
    else:
        missing.append("fb_intent_score")

    if signals.pigiame_volume is not None:
        sub_scores["pigiame_volume"] = _saturate(
            Decimal(signals.pigiame_volume), Decimal("100")
        )
    else:
        missing.append("pigiame_volume")

    if signals.ig_kenyan_mentions_30d is not None:
        sub_scores["ig_kenyan_mentions"] = _saturate(
            Decimal(signals.ig_kenyan_mentions_30d), Decimal("50")
        )
    else:
        missing.append("ig_kenyan_mentions")

    if signals.tiktok_kenyan_mentions_30d is not None:
        sub_scores["tiktok_kenyan_mentions"] = _saturate(
            Decimal(signals.tiktok_kenyan_mentions_30d), Decimal("50")
        )
    else:
        missing.append("tiktok_kenyan_mentions")

    # Weighted sum, with weights normalised to sum of present sub-scores.
    total_weight = sum(
        (DEFAULT_WEIGHTS[k] for k in sub_scores), start=Decimal("0")
    )
    if total_weight > 0:
        score = sum(
            (sub_scores[k] * DEFAULT_WEIGHTS[k] for k in sub_scores),
            start=Decimal("0"),
        ) / total_weight
    else:
        score = Decimal("0")

    confidence = _confidence_for_missing(missing)
    recommendation = _recommendation(score, confidence)

    return ProductSignal(
        name=name,
        brand=brand,
        model=model,
        category=category,
        signals=signals,
        missing_data=missing,
        demand_score=score,
        confidence=confidence,
        recommendation=recommendation,
    )


def _saturate(value: Decimal, ceiling: Decimal) -> Decimal:
    """Clamp value/ceiling to [0, 1]."""
    if value <= 0:
        return Decimal("0")
    ratio = value / ceiling
    return ratio if ratio < 1 else Decimal("1")


def _confidence_for_missing(missing: list[str]) -> str:
    """High-weight signals being missing → lower confidence."""
    high_weight_missing = sum(
        1 for k in missing if DEFAULT_WEIGHTS.get(k, Decimal("0")) >= Decimal("0.15")
    )
    if high_weight_missing >= 2:
        return "LOW"
    if high_weight_missing == 1 or len(missing) >= 4:
        return "MEDIUM"
    return "HIGH"


def _recommendation(score: Decimal, confidence: str) -> str:
    """Recommendation label."""
    if confidence == "LOW":
        return "WATCH — improve signal coverage before pursuing"
    if score >= Decimal("0.7"):
        return "PURSUE — strong demand signal"
    if score >= Decimal("0.4"):
        return "WATCH — moderate demand"
    return "SKIP — insufficient demand"
