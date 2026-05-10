"""International shipping cost calculation.

DHL Express + Aramex rate cards by weight band. Uses dimensional weight
when greater than actual weight — this is the silent killer for bulky
baby items like strollers.

MVP: hardcoded simplified rate cards. Production: pull from DHL API.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from baby_arb.pricing.rules import DIM_WEIGHT_DIVISOR


class Carrier(str, Enum):
    DHL_EXPRESS = "dhl_express"
    ARAMEX = "aramex"
    SEA_FREIGHT = "sea_freight"


# DHL Express US → Nairobi, USD per lb by weight band (billable weight).
# Simplified MVP rate card. Real rates have non-linear breakpoints,
# fuel surcharges, and account discounts. Refresh from DHL API in production.
DHL_EXPRESS_RATES: list[tuple[Decimal, Decimal]] = [
    (Decimal("1"), Decimal("28.00")),
    (Decimal("3"), Decimal("16.00")),
    (Decimal("5"), Decimal("11.00")),
    (Decimal("10"), Decimal("8.50")),
    (Decimal("20"), Decimal("7.00")),
    (Decimal("50"), Decimal("6.00")),
    (Decimal("100"), Decimal("5.50")),
]

ARAMEX_RATES: list[tuple[Decimal, Decimal]] = [
    (Decimal("1"), Decimal("22.00")),
    (Decimal("3"), Decimal("13.00")),
    (Decimal("5"), Decimal("9.00")),
    (Decimal("10"), Decimal("7.00")),
    (Decimal("20"), Decimal("5.50")),
    (Decimal("50"), Decimal("4.80")),
    (Decimal("100"), Decimal("4.20")),
]

# Sea freight is per-cubic-metre; consolidated, much cheaper but slow.
# Used for non-urgent bulk (cribs, strollers in volume).
SEA_FREIGHT_PER_CBM_USD: Decimal = Decimal("180")
SEA_FREIGHT_MIN_USD: Decimal = Decimal("60")


def dim_weight_lb(length_in: Decimal, width_in: Decimal, height_in: Decimal) -> Decimal:
    """Calculate dimensional weight in lb from inch dimensions."""
    return (length_in * width_in * height_in) / DIM_WEIGHT_DIVISOR


def billable_weight_lb(
    actual_weight_lb: Decimal,
    length_in: Decimal | None,
    width_in: Decimal | None,
    height_in: Decimal | None,
) -> tuple[Decimal, bool]:
    """Return (billable_weight, is_dim_dominated).

    Carriers charge on max(actual, dimensional). If any dimension is
    missing, fall back to actual weight + 30% as a conservative buffer.
    """
    if length_in is None or width_in is None or height_in is None:
        # Conservative buffer for unknown dims — strollers and car seats
        # tend to be dim-dominated.
        return actual_weight_lb * Decimal("1.3"), False

    dim = dim_weight_lb(length_in, width_in, height_in)
    if dim > actual_weight_lb:
        return dim, True
    return actual_weight_lb, False


def _rate_for_weight(weight_lb: Decimal, rate_card: list[tuple[Decimal, Decimal]]) -> Decimal:
    """Return the per-lb rate for the band containing this weight."""
    for max_band_lb, rate in rate_card:
        if weight_lb <= max_band_lb:
            return rate
    return rate_card[-1][1]  # heaviest band


def international_shipping_usd(
    actual_weight_lb: Decimal,
    length_in: Decimal | None,
    width_in: Decimal | None,
    height_in: Decimal | None,
    carrier: Carrier = Carrier.DHL_EXPRESS,
) -> tuple[Decimal, Decimal, bool]:
    """Calculate international shipping cost.

    Returns:
        Tuple of (cost_usd, billable_weight_lb, is_dim_dominated).
    """
    bill_lb, dim_dominated = billable_weight_lb(
        actual_weight_lb, length_in, width_in, height_in
    )

    if carrier == Carrier.SEA_FREIGHT:
        if length_in and width_in and height_in:
            cbm = (length_in * width_in * height_in) * Decimal("0.0000163871")  # in³ → m³
            cost = max(SEA_FREIGHT_MIN_USD, cbm * SEA_FREIGHT_PER_CBM_USD)
        else:
            # Estimate from actual weight; very rough
            cost = max(SEA_FREIGHT_MIN_USD, actual_weight_lb * Decimal("3"))
        return cost, bill_lb, dim_dominated

    rate_card = DHL_EXPRESS_RATES if carrier == Carrier.DHL_EXPRESS else ARAMEX_RATES
    rate = _rate_for_weight(bill_lb, rate_card)
    cost = bill_lb * rate
    return cost, bill_lb, dim_dominated
