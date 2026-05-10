"""Pricing constants. Single source of truth.

If you find any of these values hardcoded elsewhere in the codebase,
that is a bug — fix it as part of your change.
"""

from __future__ import annotations

from decimal import Decimal

from baby_arb.config import get_settings

ENGINE_VERSION = "0.1.0"

# Margin discipline. THE buy-floor.
# Override only via env (MARGIN_FLOOR_PCT). Hardcoded changes here require
# explicit human approval per SOUL.md.
_settings = get_settings()
MARGIN_FLOOR_PCT: Decimal = _settings.margin_floor_pct

# Items between floor and floor+REVIEW_BAND get REVIEW verdict instead of BUY.
MARGIN_REVIEW_BAND_PCT: Decimal = Decimal("5")

# KE customs rates. Loaded from settings (env-overridable).
KE_DUTY_RATE: Decimal = _settings.ke_duty_pct / Decimal("100")
KE_VAT_RATE: Decimal = _settings.ke_vat_pct / Decimal("100")
KE_IDF_RATE: Decimal = _settings.ke_idf_pct / Decimal("100")
KE_RDL_RATE: Decimal = _settings.ke_rdl_pct / Decimal("100")

# Dimensional weight divisor (DHL standard, inches/lb).
DIM_WEIGHT_DIVISOR: Decimal = Decimal("139")

# Default last-mile fee KE (Sendy/Glovo for non-fragile, in-Nairobi).
# Override per-shipment when known.
DEFAULT_KE_LAST_MILE_KES: Decimal = Decimal("1500")

# Default warehouse handling (consolidator per-item fee).
DEFAULT_WAREHOUSE_HANDLING_USD: Decimal = Decimal("5")

# Insurance default — 1% of declared value, capped.
INSURANCE_RATE: Decimal = Decimal("0.01")
INSURANCE_MAX_USD: Decimal = Decimal("25")
