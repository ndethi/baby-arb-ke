"""Margin floor enforcement and verdict generation.

The pricing engine computes costs. This module turns a cost picture
into a buy decision: BUY, SKIP, ABSTAIN, or REVIEW.
"""

from __future__ import annotations

from decimal import Decimal

from baby_arb.models.candidate import BuyCandidate
from baby_arb.models.pricing import (
    Confidence,
    LandedCost,
    PricingVerdict,
    PricingVerdictKind,
)
from baby_arb.pricing.rules import (
    ENGINE_VERSION,
    MARGIN_FLOOR_PCT,
    MARGIN_REVIEW_BAND_PCT,
)


def pricing_verdict(
    candidate: BuyCandidate,
    landed: LandedCost,
    reference_ke_sale_price_kes: Decimal | None = None,
) -> PricingVerdict:
    """Decide BUY/SKIP/ABSTAIN/REVIEW from a landed cost and reference price.

    Args:
        candidate: The buy candidate.
        landed: The full landed cost breakdown.
        reference_ke_sale_price_kes: Override the candidate's KE reference
            (useful for what-if pricing).

    Returns:
        A PricingVerdict with verdict, margin, and explanation.
    """
    ke_price = reference_ke_sale_price_kes or candidate.reference_ke_sale_price_kes

    if ke_price is None or ke_price <= 0:
        return PricingVerdict(
            candidate_id=candidate.candidate_id,
            verdict=PricingVerdictKind.ABSTAIN,
            margin_pct=Decimal("0"),
            margin_kes=Decimal("0"),
            total_landed_kes=landed.total_landed_kes,
            reference_ke_sale_price_kes=None,
            confidence=Confidence.LOW,
            biggest_cost_driver=_biggest_cost_driver(landed),
            slimmest_assumption="no KE reference price",
            explanation=(
                "No reference KE sale price available, so margin cannot be "
                "computed. Demand Scout must provide a reference before this "
                "candidate can be evaluated."
            ),
            breakdown=landed,
            engine_version=ENGINE_VERSION,
        )

    margin_kes = ke_price - landed.total_landed_kes
    if landed.total_landed_kes > 0:
        margin_pct = (margin_kes / landed.total_landed_kes) * Decimal("100")
    else:
        margin_pct = Decimal("0")

    verdict = _choose_verdict(margin_pct, landed.confidence)

    biggest = _biggest_cost_driver(landed)
    slimmest = _slimmest_assumption(landed)
    explanation = _build_explanation(
        verdict=verdict,
        margin_pct=margin_pct,
        biggest=biggest,
        slimmest=slimmest,
        landed=landed,
        ke_price=ke_price,
    )

    return PricingVerdict(
        candidate_id=candidate.candidate_id,
        verdict=verdict,
        margin_pct=margin_pct,
        margin_kes=margin_kes,
        total_landed_kes=landed.total_landed_kes,
        reference_ke_sale_price_kes=ke_price,
        confidence=landed.confidence,
        biggest_cost_driver=biggest,
        slimmest_assumption=slimmest,
        explanation=explanation,
        breakdown=landed,
        engine_version=ENGINE_VERSION,
    )


def _choose_verdict(margin_pct: Decimal, confidence: Confidence) -> PricingVerdictKind:
    """Apply the margin floor and confidence rules.

    SKIP    if margin < MARGIN_FLOOR_PCT
    ABSTAIN if confidence == LOW
    REVIEW  if margin in [floor, floor + review_band)
    BUY     otherwise
    """
    if margin_pct < MARGIN_FLOOR_PCT:
        return PricingVerdictKind.SKIP

    if confidence == Confidence.LOW:
        return PricingVerdictKind.ABSTAIN

    if margin_pct < MARGIN_FLOOR_PCT + MARGIN_REVIEW_BAND_PCT:
        return PricingVerdictKind.REVIEW

    return PricingVerdictKind.BUY


def _biggest_cost_driver(landed: LandedCost) -> str:
    """Identify the largest single cost component for human review."""
    components: dict[str, Decimal] = {
        "listing_price_usd": landed.listing_price_usd * landed.fx_rate_usdkes,
        "us_shipping_usd": landed.us_shipping_usd * landed.fx_rate_usdkes,
        "us_sales_tax_usd": landed.us_sales_tax_usd * landed.fx_rate_usdkes,
        "warehouse_handling_usd": landed.warehouse_handling_usd * landed.fx_rate_usdkes,
        "international_shipping_usd": (
            landed.international_shipping_usd * landed.fx_rate_usdkes
        ),
        "insurance_usd": landed.insurance_usd * landed.fx_rate_usdkes,
        "ke_duty_kes": landed.ke_duty_kes,
        "ke_vat_kes": landed.ke_vat_kes,
        "ke_idf_kes": landed.ke_idf_kes,
        "ke_rdl_kes": landed.ke_rdl_kes,
        "ke_last_mile_kes": landed.ke_last_mile_kes,
        "ke_storage_kes": landed.ke_storage_kes,
    }
    return max(components, key=lambda k: components[k])


def _slimmest_assumption(landed: LandedCost) -> str:
    """Identify the weakest input that could shift the verdict."""
    notes: list[str] = []
    if landed.weight_source == "category_avg":
        notes.append(f"weight estimated from category average ({landed.weight_used_lb} lb)")
    elif landed.weight_source == "estimated":
        notes.append(f"weight estimated ({landed.weight_used_lb} lb)")
    if landed.dim_weight_used:
        notes.append("dim weight billed (item is bulky)")
    if landed.fx_rate_age_hours > Decimal("6"):
        notes.append(f"FX rate {landed.fx_rate_age_hours:.1f}h old")
    if not notes:
        return "all inputs verified"
    return "; ".join(notes)


def _build_explanation(
    *,
    verdict: PricingVerdictKind,
    margin_pct: Decimal,
    biggest: str,
    slimmest: str,
    landed: LandedCost,
    ke_price: Decimal,
) -> str:
    """Build a one-paragraph explanation for human review."""
    margin_str = f"{margin_pct:.1f}%"
    landed_str = f"{landed.total_landed_kes:,.0f} KES"
    ke_str = f"{ke_price:,.0f} KES"

    base = (
        f"Margin {margin_str} on a landed cost of {landed_str} versus a "
        f"reference KE sale of {ke_str}. Largest cost component: {biggest}. "
        f"Confidence note: {slimmest}."
    )

    if verdict == PricingVerdictKind.BUY:
        return base + " Verdict BUY — clears the margin floor with confidence."
    if verdict == PricingVerdictKind.SKIP:
        return (
            base
            + f" Verdict SKIP — margin below the {MARGIN_FLOOR_PCT}% floor."
        )
    if verdict == PricingVerdictKind.ABSTAIN:
        return (
            base
            + " Verdict ABSTAIN — confidence too low to commit. Improve the "
            "weakest input and re-run."
        )
    if verdict == PricingVerdictKind.REVIEW:
        return (
            base
            + " Verdict REVIEW — margin is just above the floor. Worth a "
            "human look before proceeding."
        )
    return base
