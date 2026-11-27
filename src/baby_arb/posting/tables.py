"""SQLModel tables for the listing store (ENGINE_SPEC section 7).

Only the tables a phase uses are created by that phase's migration
(`migrations/versions/`). Columns that later phases fill are nullable now so
those phases add behaviour, not schema churn.

Prices are whole Kenyan shillings (int). The admin's price is stored as given.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Column, DateTime, Numeric, UniqueConstraint
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    """Timezone-aware current UTC time (column default)."""
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """DateTime stored as naive UTC and read back aware (SQLite drops tzinfo).

    Aware values in any zone are converted to UTC before they are written or
    compared, so a Nairobi time and its UTC equivalent match in queries.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> datetime | None:
        """Convert to naive UTC."""
        if value is None:
            return None
        if not isinstance(value, datetime):
            raise TypeError(f"expected datetime, got {type(value).__name__}")
        moment: datetime = value
        if moment.tzinfo is not None:
            moment = moment.astimezone(UTC)
        return moment.replace(tzinfo=None)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        """Attach UTC."""
        if value is None:
            return None
        if not isinstance(value, datetime):
            raise TypeError(f"expected datetime, got {type(value).__name__}")
        moment: datetime = value
        return moment.replace(tzinfo=UTC)


def as_utc(value: datetime) -> datetime:
    """Read a stored time back as aware UTC (SQLite drops tzinfo)."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Listing(SQLModel, table=True):
    """One item (P-code), seller listing (L-code) or content post (C-code)."""

    __tablename__ = "listings"

    code: str = Field(primary_key=True, max_length=16)
    kind: str = Field(max_length=16)  # own | seller | content
    status: str = Field(max_length=16, index=True)
    title: str | None = None
    brand: str | None = None
    model: str | None = None
    model_source: str | None = Field(default=None, max_length=8)  # auto | admin
    model_confidence: Decimal | None = Field(
        default=None, sa_column=Column(Numeric(4, 3), nullable=True)
    )
    category: str | None = None
    age_range: str | None = None
    grade: str | None = Field(default=None, max_length=1)  # A | B | C
    condition_note: str | None = None
    buy_price: int | None = None
    price: int | None = None
    price_source: str | None = Field(default=None, max_length=8)  # admin only
    ref_new_price: int | None = None
    seller_id: int | None = None  # FK added with the sellers table (Phase 3)
    template_version: int | None = None
    # Phase 1: render state and current captions (the latest round wins).
    layout: str | None = None  # JSON, see marketing/render/layout.py
    caption_ig: str | None = None
    caption_tiktok: str | None = None
    round: int = 0  # render round shown in the latest preview
    created_by: str | None = None  # admin Telegram ID or "cli"
    is_test: bool = False  # test drops: never real stock, left out of reports
    created_at: datetime = Field(default_factory=utcnow)
    live_at: datetime | None = None
    sold_at: datetime | None = None


class Photo(SQLModel, table=True):
    """One photo of a listing, numbered from 1 in the order received."""

    __tablename__ = "photos"
    __table_args__ = (UniqueConstraint("listing_code", "n"),)

    id: int | None = Field(default=None, primary_key=True)
    listing_code: str = Field(foreign_key="listings.code", index=True)
    n: int
    path: str
    hash: str = Field(max_length=64)
    is_hero: bool = False


class ListingEvent(SQLModel, table=True):
    """Audit row for every listing and schedule status change."""

    __tablename__ = "listing_events"

    id: int | None = Field(default=None, primary_key=True)
    listing_code: str = Field(foreign_key="listings.code", index=True)
    from_status: str | None = None
    to_status: str
    actor: str  # Telegram admin ID or "system"
    note: str | None = None
    at: datetime = Field(default_factory=utcnow)


class SafetyVerdictRow(SQLModel, table=True):
    """Safety screen result for a listing; override_by is set by an admin."""

    __tablename__ = "safety_verdicts"

    id: int | None = Field(default=None, primary_key=True)
    listing_code: str = Field(foreign_key="listings.code", index=True)
    verdict: str = Field(max_length=8)  # PASS | REVIEW | BLOCK
    reasons: str  # JSON list
    recall_source: str  # e.g. "not_checked" until Phase 2
    override_by: str | None = None
    at: datetime = Field(default_factory=utcnow)


class LlmCall(SQLModel, table=True):
    """Every model call, including capped and failed ones."""

    __tablename__ = "llm_calls"

    id: int | None = Field(default=None, primary_key=True)
    purpose: str
    provider: str
    model: str
    status: str = Field(max_length=8)  # ok | error | capped
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: Decimal = Field(
        default=Decimal("0"), sa_column=Column(Numeric(10, 6), nullable=False)
    )
    error: str | None = None
    at: datetime = Field(default_factory=utcnow, index=True)


class CodeCounter(SQLModel, table=True):
    """Last number issued per code prefix (P, L, C)."""

    __tablename__ = "code_counters"

    prefix: str = Field(primary_key=True, max_length=1)
    last: int = 0


class BotState(SQLModel, table=True):
    """Small key/value flags such as `paused`."""

    __tablename__ = "bot_state"

    key: str = Field(primary_key=True)
    value: str
    updated_at: datetime = Field(default_factory=utcnow)


class ScheduleRow(SQLModel, table=True):
    """A calendar slot for a listing or content post (ENGINE_SPEC section 4).

    Status: PROPOSED -> QUEUED -> POSTED; QUEUED -> MISSED -> QUEUED | SKIPPED;
    PROPOSED | QUEUED -> SKIPPED.
    """

    __tablename__ = "schedule"

    id: int | None = Field(default=None, primary_key=True)
    listing_code: str = Field(foreign_key="listings.code", index=True)
    kind: str = Field(max_length=16)  # drop | listing | teaser | tip | behind
    slot_at: datetime = Field(sa_type=UTCDateTime, index=True)
    channels: str  # comma-separated, e.g. "instagram,facebook,tiktok"
    status: str = Field(max_length=10, index=True)
    proposed_by: str = Field(max_length=8)  # system | admin
    moved_from: datetime | None = Field(default=None, sa_type=UTCDateTime)
    reminded_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    posted_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    created_at: datetime = Field(default_factory=utcnow, sa_type=UTCDateTime)


class Render(SQLModel, table=True):
    """One rendered asset for one round of a listing's preview."""

    __tablename__ = "renders"

    id: int | None = Field(default=None, primary_key=True)
    listing_code: str = Field(foreign_key="listings.code", index=True)
    round: int
    asset: str  # feed | story | tiktok_<n> | reel | sold
    path: str
    template_version: int
    at: datetime = Field(default_factory=utcnow)


class EditEvent(SQLModel, table=True):
    """The drift log: one row per applied edit operation (or reject)."""

    __tablename__ = "edit_events"

    id: int | None = Field(default=None, primary_key=True)
    listing_code: str = Field(foreign_key="listings.code", index=True)
    round: int
    raw_text: str
    op: str
    target: str | None = None
    before: str | None = None
    after: str | None = None
    parsed_by: str = Field(max_length=8)  # rules | model | admin
    at: datetime = Field(default_factory=utcnow)
