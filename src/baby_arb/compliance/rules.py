"""Compliance constants and static rules.

If you find any of these duplicated elsewhere in the codebase, that is
a bug — fix it as part of your change.
"""

from __future__ import annotations

from baby_arb.config import get_settings

_settings = get_settings()

# Hard ceiling on car seat date-of-manufacture age (years).
# A used car seat older than this is BLOCK regardless of any other signal.
CARSEAT_DOM_CEILING_YEARS: int = _settings.default_carseat_dom_ceiling_years

# Brands with known counterfeit issues. Triggers extra signals required
# before PASS verdict.
COUNTERFEIT_PRONE_BRANDS: set[str] = {
    "nuna",
    "uppababy",
    "stokke",
    "babybjorn",
    "babybjörn",
    "doona",
    "cybex",
}

# Static safety blocks — never bought regardless of other signals.
# Match against listing title or category text.
SAFETY_BLOCK_KEYWORDS: list[tuple[str, str]] = [
    ("drop-side crib", "Drop-side cribs banned in US since 2011"),
    ("dropside crib", "Drop-side cribs banned in US since 2011"),
    ("inclined sleeper", "Inclined sleepers banned 2019, multiple deaths"),
    ("rock 'n play", "Fisher-Price Rock 'n Play recalled 2019"),
    ("rock-n-play", "Fisher-Price Rock 'n Play recalled 2019"),
    ("boppy newborn lounger", "Boppy newborn loungers recalled 2021"),
    ("boppy original lounger", "Boppy original loungers recalled 2021"),
    ("boppy preferred lounger", "Boppy preferred loungers recalled 2021"),
    ("bumbo seat", "Bumbo seats recalled 2012 if missing restraint"),
]

# Counterfeit risk thresholds.
MIN_SELLER_FEEDBACK_COUNT: int = 50
MIN_SELLER_FEEDBACK_PCT_NUM: int = 98  # 98%

# CPSC recall lookback window for related-SKU check.
CPSC_RELATED_RECALL_LOOKBACK_DAYS: int = 1825  # 5 years
