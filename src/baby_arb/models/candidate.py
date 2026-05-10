"""Models for sourcing candidates."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class ItemCategory(str, Enum):
    """Top-level item category for routing through compliance and pricing."""

    CAR_SEAT = "car_seat"
    STROLLER = "stroller"
    CRIB = "crib"
    HIGH_CHAIR = "high_chair"
    BABY_CARRIER = "baby_carrier"
    MONITOR = "monitor"
    BREAST_PUMP = "breast_pump"
    BOUNCER = "bouncer"
    PLAY_MAT = "play_mat"
    BATHTUB = "bathtub"
    DIAPER_BAG = "diaper_bag"
    OTHER = "other"


class ItemCondition(str, Enum):
    """Normalised condition grade."""

    NEW = "new"
    LIKE_NEW = "like_new"
    GENTLY_USED = "gently_used"
    FUNCTIONAL = "functional"
    UNKNOWN = "unknown"


class BuyCandidate(BaseModel):
    """A candidate listing under consideration for purchase.

    Carries enough information for Compliance and Pricing to decide
    PASS/BLOCK/REVIEW and BUY/SKIP/ABSTAIN/REVIEW respectively.
    """

    # Identity
    candidate_id: str
    marketplace: str  # ebay, mercari, fb, offerup
    listing_url: HttpUrl

    # Product
    brand: str
    model: str
    category: ItemCategory
    upc: str | None = None
    condition_text: str
    condition_normalized: ItemCondition

    # Pricing inputs (USD)
    listing_price_usd: Decimal
    us_shipping_usd: Decimal = Field(default=Decimal("0"))

    # Physical (for international shipping cost)
    weight_lb: Decimal | None = None
    weight_source: str = "estimated"  # actual | listed | estimated | category_avg
    length_in: Decimal | None = None
    width_in: Decimal | None = None
    height_in: Decimal | None = None

    # Origin
    seller_id: str
    seller_state: str | None = None  # US state code
    seller_feedback_count: int | None = None
    seller_feedback_pct: Decimal | None = None

    # Listing metadata
    listing_ends_at: datetime | None = None
    photos: list[HttpUrl] = Field(default_factory=list)
    raw_listing_data: dict = Field(default_factory=dict)

    # Car seat extra
    dom_extracted: datetime | None = None
    dom_source: str | None = None  # listing_text, photo_ocr, seller_message

    # KE reference (set by Demand Scout, not Sourcing Scout)
    reference_ke_sale_price_kes: Decimal | None = None
    reference_source: str | None = None  # jiji_median_sold, etc.
    reference_n: int | None = None  # number of observations

    captured_at: datetime = Field(default_factory=datetime.utcnow)
