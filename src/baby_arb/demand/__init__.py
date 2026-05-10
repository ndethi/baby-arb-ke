"""KE demand signal aggregation.

MVP: signals entered manually via CLI or Telegram. This module computes
the composite demand_score from raw signals.

Hermes handoff for post-MVP:
    Build src/baby_arb/demand/jiji.py — Apify-backed scraper for Jiji listings
    Build src/baby_arb/demand/phyllo.py — IG/TikTok creator coverage via Phyllo
    Build src/baby_arb/demand/fb_groups.py — FB parenting group sentiment
    Build src/baby_arb/demand/jumia.py — stock check via product page scrape
"""

from baby_arb.demand.aggregator import compose_signal
from baby_arb.demand.weights import DEFAULT_WEIGHTS

__all__ = ["DEFAULT_WEIGHTS", "compose_signal"]
