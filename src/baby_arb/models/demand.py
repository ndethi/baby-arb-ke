"""Models for demand signals."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class DemandSignals(BaseModel):
    """Raw signal block for one product."""

    # Jiji marketplace
    jiji_active_listings: int | None = None
    jiji_sold_30d: int | None = None
    jiji_median_sold_kes: Decimal | None = None
    jiji_median_listed_kes: Decimal | None = None

    # Retail availability
    jumia_stock: str | None = None  # in_stock | out_of_stock | not_listed
    jumia_weeks_out_of_stock: int | None = None
    kilimall_stock: str | None = None

    # FB groups
    fb_group_mentions_30d: int | None = None
    fb_group_intent_score: Decimal | None = None

    # Price discovery
    pigiame_volume: int | None = None

    # Social
    ig_kenyan_mentions_30d: int | None = None
    tiktok_kenyan_mentions_30d: int | None = None

    # Provenance
    entered_by: str = "manual"  # manual | scraper | api
    entered_at: datetime = Field(default_factory=datetime.utcnow)


class ProductSignal(BaseModel):
    """Composed signal report for one product."""

    name: str
    brand: str | None = None
    model: str | None = None
    category: str | None = None

    signals: DemandSignals
    missing_data: list[str] = Field(default_factory=list)

    demand_score: Decimal  # 0.0 - 1.0
    confidence: str  # HIGH | MEDIUM | LOW
    recommendation: str | None = None  # PURSUE | WATCH | SKIP


class DemandReport(BaseModel):
    """Weekly demand scout output."""

    generated_at: datetime = Field(default_factory=datetime.utcnow)
    products: list[ProductSignal] = Field(default_factory=list)
    notes: str | None = None
