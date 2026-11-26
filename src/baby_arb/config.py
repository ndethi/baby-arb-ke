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

    # Demand APIs
    jiji_api_key: str | None = None
    facebook_app_id: str | None = None
    facebook_app_secret: str | None = None
    facebook_access_token: str | None = None

    # Marketing engine (docs/marketing/ENGINE_SPEC.md)
    # TELEGRAM_BOT_TOKEN above is the shop bot's token.
    telegram_admin_ids: str = ""  # comma-separated Telegram user IDs
    telegram_ops_chat_id: int | None = None  # the "babyReShop Ops" group

    meta_app_id: str | None = None
    meta_app_secret: str | None = None
    meta_page_id: str | None = None
    meta_ig_user_id: str | None = None
    meta_system_user_token: str | None = None
    meta_ad_account_id: str | None = None

    llm_provider: str = "openrouter"  # openrouter | nvidia
    llm_model: str = "nvidia/nemotron-3.5-super-vl:free"
    llm_fallback_provider: str | None = "nvidia"
    llm_fallback_model: str | None = "nvidia/nemotron-3.5-super-vl-120b-a12b"
    llm_reasoning: bool = False  # OpenRouter reasoning; off keeps short answers short
    llm_daily_cap_usd: Decimal = Field(default=Decimal("1"))
    # Free-tier models cost $0, so a call-count cap also protects rate limits.
    llm_daily_call_cap: int = 200
    # USD per million tokens for the configured models (0 for free tiers).
    llm_price_in_per_mtok: Decimal = Field(default=Decimal("0"))
    llm_price_out_per_mtok: Decimal = Field(default=Decimal("0"))
    nvidia_api_key: str | None = None
    openrouter_api_key: str | None = None

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

    @property
    def admin_ids(self) -> frozenset[int]:
        """Telegram user IDs allowed to command the shop bot."""
        return frozenset(
            int(part) for part in self.telegram_admin_ids.replace(" ", "").split(",") if part
        )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings singleton."""
    return Settings()
