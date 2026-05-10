"""Models for pricing engine output."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class Confidence(str, Enum):
    """Confidence level on a pricing calculation."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class PricingVerdictKind(str, Enum):
    """The buy decision a Pricing Engineer can return."""

    BUY = "BUY"
    SKIP = "SKIP"
    ABSTAIN = "ABSTAIN"
    REVIEW = "REVIEW"


class LandedCost(BaseModel):
    """Full cost breakdown from listing to KE buyer's hand.

    Every component is named. No 'fees' bucket. The math is the spine
    of the business and must be inspectable.
    """

    # USD components (origin side)
    listing_price_usd: Decimal
    us_shipping_usd: Decimal
    us_sales_tax_usd: Decimal
    warehouse_handling_usd: Decimal
    international_shipping_usd: Decimal
    insurance_usd: Decimal = Field(default=Decimal("0"))

    # KE components (destination side, in KES)
    cif_kes: Decimal
    ke_duty_kes: Decimal
    ke_idf_kes: Decimal
    ke_rdl_kes: Decimal
    ke_vat_kes: Decimal
    ke_last_mile_kes: Decimal
    ke_storage_kes: Decimal = Field(default=Decimal("0"))

    # Totals
    total_landed_kes: Decimal

    # Provenance
    fx_rate_usdkes: Decimal
    fx_rate_age_hours: Decimal
    weight_used_lb: Decimal
    weight_source: str
    dim_weight_used: bool

    # Quality flag
    confidence: Confidence

    # Audit
    engine_version: str
    calculated_at: datetime = Field(default_factory=datetime.utcnow)


class PricingVerdict(BaseModel):
    """The Pricing Engineer's recommendation on a candidate."""

    candidate_id: str
    verdict: PricingVerdictKind

    margin_pct: Decimal
    margin_kes: Decimal
    total_landed_kes: Decimal
    reference_ke_sale_price_kes: Decimal | None

    confidence: Confidence
    biggest_cost_driver: str  # name of the largest cost component
    slimmest_assumption: str  # human-readable note on the weakest input
    explanation: str  # one paragraph for human review

    breakdown: LandedCost

    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    engine_version: str
