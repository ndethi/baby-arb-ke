"""Application configuration loaded from environment.

All operating parameters live here as a single source of truth.
Environment overrides are explicit in `.env.example`.
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings, loaded once per process."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # External APIs
    ebay_app_id: str | None = None
    ebay_cert_id: str | None = None
    ebay_environment: str = "PRODUCTION"

    cpsc_api_base: str = "https://www.saferproducts.gov/RestWebServices/Recall"

    dhl_api_key: str | None = None
    dhl_account_number: str | None = None

    fx_provider: str = "openexchangerates"
    fx_api_key: str | None = None

    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    # Storage
    database_url: str = "sqlite:///./data/baby_arb.db"

    # Operating parameters — these are the dials of the business.
    margin_floor_pct: Decimal = Field(default=Decimal("50"))
    max_auto_buy_usd: Decimal = Field(default=Decimal("200"))
    target_sell_through_days: int = 45

    default_carseat_dom_ceiling_years: int = 6

    ke_duty_pct: Decimal = Field(default=Decimal("25"))
    ke_vat_pct: Decimal = Field(default=Decimal("16"))
    ke_idf_pct: Decimal = Field(default=Decimal("3.5"))
    ke_rdl_pct: Decimal = Field(default=Decimal("2"))

    # FX cache TTL
    fx_cache_ttl_hours: int = 12

    # CPSC cache TTL
    cpsc_cache_ttl_hours: int = 24

    # Logging
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings singleton."""
    return Settings()
