"""Landed-cost engine. Pure orchestrator over the cost components.

This is the single function the rest of the system calls to get a
complete cost picture. No LLM here. No randomness. Deterministic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from baby_arb.models.candidate import BuyCandidate, ItemCategory
from baby_arb.models.pricing import Confidence, LandedCost
from baby_arb.pricing import fx
from baby_arb.pricing.intl_shipping import (
    Carrier,
    international_shipping_usd,
)
from baby_arb.pricing.ke_customs import calculate_ke_customs
from baby_arb.pricing.rules import (
    DEFAULT_KE_LAST_MILE_KES,
    ENGINE_VERSION,
    INSURANCE_MAX_USD,
    INSURANCE_RATE,
)
from baby_arb.pricing.us_costs import (
    calculate_us_sales_tax,
    warehouse_handling_fee,
)

# Category-average weight estimates (lb) used as last-resort fallback.
# Triggers LOW confidence.
CATEGORY_WEIGHT_FALLBACK: dict[ItemCategory, Decimal] = {
    ItemCategory.CAR_SEAT: Decimal("12"),
    ItemCategory.STROLLER: Decimal("25"),
    ItemCategory.CRIB: Decimal("60"),
    ItemCategory.HIGH_CHAIR: Decimal("18"),
    ItemCategory.BABY_CARRIER: Decimal("3"),
    ItemCategory.MONITOR: Decimal("2"),
    ItemCategory.BREAST_PUMP: Decimal("4"),
    ItemCategory.BOUNCER: Decimal("8"),
    ItemCategory.PLAY_MAT: Decimal("6"),
    ItemCategory.BATHTUB: Decimal("4"),
    ItemCategory.DIAPER_BAG: Decimal("2"),
    ItemCategory.OTHER: Decimal("5"),
}


def calculate_landed_cost(
    candidate: BuyCandidate,
    *,
    warehouse_state: str = "DE",
    carrier: Carrier = Carrier.DHL_EXPRESS,
    last_mile_kes: Decimal = DEFAULT_KE_LAST_MILE_KES,
    storage_kes: Decimal = Decimal("0"),
    now: datetime | None = None,
) -> LandedCost:
    """Calculate complete landed cost for a candidate listing.

    Args:
        candidate: The buy candidate.
        warehouse_state: 2-letter US state of the receiving warehouse.
        carrier: International carrier choice.
        last_mile_kes: KE last-mile delivery cost.
        storage_kes: KE storage if applicable.
        now: Override current time (for testing).

    Returns:
        Complete LandedCost with all components named and confidence flag.
    """
    now = now or datetime.now(timezone.utc)

    # ── Weight resolution ────────────────────────────────────────────
    if candidate.weight_lb is not None:
        weight_lb = candidate.weight_lb
        weight_source = candidate.weight_source
    else:
        weight_lb = CATEGORY_WEIGHT_FALLBACK.get(candidate.category, Decimal("5"))
        weight_source = "category_avg"

    # ── US-side costs ────────────────────────────────────────────────
    us_sales_tax_usd = calculate_us_sales_tax(
        candidate.listing_price_usd,
        candidate.us_shipping_usd,
        warehouse_state,
        is_clothing=False,
    )
    warehouse_usd = warehouse_handling_fee()

    us_subtotal_usd = (
        candidate.listing_price_usd
        + candidate.us_shipping_usd
        + us_sales_tax_usd
        + warehouse_usd
    )

    # ── International shipping ──────────────────────────────────────
    intl_shipping_usd, billable_weight, dim_dominated = international_shipping_usd(
        weight_lb,
        candidate.length_in,
        candidate.width_in,
        candidate.height_in,
        carrier=carrier,
    )

    # ── Insurance ───────────────────────────────────────────────────
    insurance_usd = min(
        INSURANCE_MAX_USD,
        candidate.listing_price_usd * INSURANCE_RATE,
    )

    # ── CIF in USD then KES ─────────────────────────────────────────
    cif_usd = us_subtotal_usd + intl_shipping_usd + insurance_usd

    rate, rate_age_hours = fx.get_usdkes_rate(now=now)
    cif_kes = cif_usd * rate

    # ── KE customs ──────────────────────────────────────────────────
    customs = calculate_ke_customs(cif_kes)

    # ── Total landed in KES ─────────────────────────────────────────
    total_landed_kes = (
        cif_kes
        + customs["duty"]
        + customs["idf"]
        + customs["rdl"]
        + customs["vat"]
        + last_mile_kes
        + storage_kes
    )

    # ── Confidence assessment ───────────────────────────────────────
    confidence = _assess_confidence(
        weight_source=weight_source,
        has_dims=all(
            x is not None for x in (candidate.length_in, candidate.width_in, candidate.height_in)
        ),
        rate_age_hours=rate_age_hours,
        has_ke_reference=candidate.reference_ke_sale_price_kes is not None,
        ke_reference_n=candidate.reference_n,
    )

    return LandedCost(
        listing_price_usd=candidate.listing_price_usd,
        us_shipping_usd=candidate.us_shipping_usd,
        us_sales_tax_usd=us_sales_tax_usd,
        warehouse_handling_usd=warehouse_usd,
        international_shipping_usd=intl_shipping_usd,
        insurance_usd=insurance_usd,
        cif_kes=cif_kes,
        ke_duty_kes=customs["duty"],
        ke_idf_kes=customs["idf"],
        ke_rdl_kes=customs["rdl"],
        ke_vat_kes=customs["vat"],
        ke_last_mile_kes=last_mile_kes,
        ke_storage_kes=storage_kes,
        total_landed_kes=total_landed_kes,
        fx_rate_usdkes=rate,
        fx_rate_age_hours=rate_age_hours,
        weight_used_lb=billable_weight,
        weight_source=weight_source,
        dim_weight_used=dim_dominated,
        confidence=confidence,
        engine_version=ENGINE_VERSION,
        calculated_at=now,
    )


def _assess_confidence(
    *,
    weight_source: str,
    has_dims: bool,
    rate_age_hours: Decimal,
    has_ke_reference: bool,
    ke_reference_n: int | None,
) -> Confidence:
    """Determine confidence based on input quality.

    HIGH:   actual weight + dims + fresh FX + KE ref from 5+ obs
    MEDIUM: estimated/listed weight or dims missing or FX 6-12h, KE ref 2-4 obs
    LOW:    category_avg weight or FX > 12h or KE ref missing/single obs
    """
    if not has_ke_reference:
        return Confidence.LOW
    if weight_source == "category_avg":
        return Confidence.LOW
    if rate_age_hours > Decimal("12"):
        return Confidence.LOW
    if (ke_reference_n or 0) < 2:
        return Confidence.LOW

    if (
        weight_source == "actual"
        and has_dims
        and rate_age_hours <= Decimal("6")
        and (ke_reference_n or 0) >= 5
    ):
        return Confidence.HIGH

    return Confidence.MEDIUM
