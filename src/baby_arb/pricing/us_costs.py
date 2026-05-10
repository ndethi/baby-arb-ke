"""US-side costs: sales tax by state, warehouse handling fees."""

from __future__ import annotations

from decimal import Decimal

from baby_arb.pricing.rules import DEFAULT_WAREHOUSE_HANDLING_USD

# Destination state determines sales tax for most US transactions.
# Source: state revenue departments, 2026 rates. Update as needed.
# Some baby items may be exempt in certain states (e.g. clothing in NJ/PA).
# This is a conservative default; product-level exemptions handled by
# `is_exempt_in_state()`.
SALES_TAX_BY_STATE: dict[str, Decimal] = {
    "AL": Decimal("0.04"),
    "AK": Decimal("0"),
    "AZ": Decimal("0.056"),
    "AR": Decimal("0.065"),
    "CA": Decimal("0.0725"),
    "CO": Decimal("0.029"),
    "CT": Decimal("0.0635"),
    "DE": Decimal("0"),
    "FL": Decimal("0.06"),
    "GA": Decimal("0.04"),
    "HI": Decimal("0.04"),
    "ID": Decimal("0.06"),
    "IL": Decimal("0.0625"),
    "IN": Decimal("0.07"),
    "IA": Decimal("0.06"),
    "KS": Decimal("0.065"),
    "KY": Decimal("0.06"),
    "LA": Decimal("0.0445"),
    "ME": Decimal("0.055"),
    "MD": Decimal("0.06"),
    "MA": Decimal("0.0625"),
    "MI": Decimal("0.06"),
    "MN": Decimal("0.06875"),
    "MS": Decimal("0.07"),
    "MO": Decimal("0.04225"),
    "MT": Decimal("0"),
    "NE": Decimal("0.055"),
    "NV": Decimal("0.0685"),
    "NH": Decimal("0"),
    "NJ": Decimal("0.06625"),
    "NM": Decimal("0.04875"),
    "NY": Decimal("0.04"),
    "NC": Decimal("0.0475"),
    "ND": Decimal("0.05"),
    "OH": Decimal("0.0575"),
    "OK": Decimal("0.045"),
    "OR": Decimal("0"),
    "PA": Decimal("0.06"),
    "RI": Decimal("0.07"),
    "SC": Decimal("0.06"),
    "SD": Decimal("0.045"),
    "TN": Decimal("0.07"),
    "TX": Decimal("0.0625"),
    "UT": Decimal("0.0485"),
    "VT": Decimal("0.06"),
    "VA": Decimal("0.053"),
    "WA": Decimal("0.065"),
    "WV": Decimal("0.06"),
    "WI": Decimal("0.05"),
    "WY": Decimal("0.04"),
    "DC": Decimal("0.06"),
}

# States with broad clothing/baby-item exemptions.
# Conservative — only the clearly exempt categories.
CLOTHING_EXEMPT_STATES = {"NJ", "PA", "MN", "VT"}


def sales_tax_rate(warehouse_state: str | None) -> Decimal:
    """Return the sales tax rate for the warehouse state.

    Args:
        warehouse_state: 2-letter state code where the US warehouse sits.

    Returns:
        Decimal rate (e.g. 0.0625 for 6.25%). Returns 0 if state unknown
        — the caller should treat unknown state as a confidence hit.
    """
    if not warehouse_state:
        return Decimal("0")
    return SALES_TAX_BY_STATE.get(warehouse_state.upper(), Decimal("0"))


def calculate_us_sales_tax(
    price_usd: Decimal,
    shipping_usd: Decimal,
    warehouse_state: str | None,
    is_clothing: bool = False,
) -> Decimal:
    """Calculate US sales tax on price + shipping.

    Args:
        price_usd: Item price in USD.
        shipping_usd: Shipping cost (taxable in most states).
        warehouse_state: Destination state code.
        is_clothing: True if item is clothing (some states exempt).

    Returns:
        Sales tax amount in USD.
    """
    if is_clothing and warehouse_state and warehouse_state.upper() in CLOTHING_EXEMPT_STATES:
        return Decimal("0")

    rate = sales_tax_rate(warehouse_state)
    return (price_usd + shipping_usd) * rate


def warehouse_handling_fee() -> Decimal:
    """Per-item warehouse handling fee in USD."""
    return DEFAULT_WAREHOUSE_HANDLING_USD
