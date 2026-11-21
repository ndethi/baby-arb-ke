"""Never-sell safety screen for listings (deterministic, no model calls).

Sources:
- babyReShop drop-to-draft skill, "Safety screen": BLOCK car seats, cots and
  cribs, inclined sleepers and loungers, seated walkers, mattresses, bottles
  and teethers; REVIEW carriers and straps, bouncers, bath seats, strollers,
  anything with batteries or a heating element, magnets, plush.
- docs/skills/compliance-checker step 5: drop-side cribs, inclined sleepers
  (Rock 'n Play class), Boppy newborn loungers and walkers are BLOCK.

Rules: BLOCK can never be approved. REVIEW needs an explicit admin override.
Recall status is not checked here; until the recall lookup exists (Phase 2),
`recall_source` is "not_checked" and the item is REVIEW (spec section 2:
unknown recall status needs an override). New BLOCK terms can be added
freely; removing one needs explicit human approval in a PR.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

Verdict = Literal["PASS", "REVIEW", "BLOCK"]

RECALL_NOT_CHECKED = "not_checked"

# reason -> patterns (matched case-insensitively on word boundaries)
BLOCK_RULES: dict[str, tuple[str, ...]] = {
    "car_seat": (r"car ?seats?", r"booster seats?", r"infant carrier car seat", r"isofix"),
    "cot_or_crib": (r"cots?", r"cribs?", r"drop[- ]side"),
    "inclined_sleeper": (r"inclined sleepers?", r"rock\s*['\u2019]?\s*n['\u2019]?\s*play", r"rock and play"),
    "lounger": (r"loungers?", r"boppy", r"dockatot", r"nest(?:ing)? pods?"),
    "seated_walker": (r"seated walkers?", r"baby walkers?", r"walkers? with (?:wheels|casters)"),
    "mattress": (r"mattress(?:es)?",),
    "bottle": (r"bottles?", r"feeding bottles?"),
    "teether": (r"teethers?", r"teething (?:ring|toy)s?"),
}

REVIEW_RULES: dict[str, tuple[str, ...]] = {
    "carrier_or_strap": (r"carriers?", r"straps?", r"slings?", r"wraps?", r"ergobaby"),
    "bouncer": (r"bouncers?", r"rockers?", r"swings?"),
    "bath_seat": (r"bath seats?", r"bath rings?"),
    "stroller": (r"strollers?", r"prams?", r"pushchairs?", r"buggy|buggies", r"travel systems?"),
    "battery_or_heating": (
        r"batter(?:y|ies)",
        r"battery[- ]operated",
        r"heat(?:er|ing|ed)",
        r"warmers?",
        r"sterili[sz]ers?",
        r"electric",
    ),
    "magnets": (r"magnet(?:s|ic)?",),
    "plush": (r"plush", r"soft toys?", r"teddy", r"stuffed"),
    # A plain "walker" may be a push walker (fine) or a seated one (BLOCK): ask.
    "walker_type_unclear": (r"walkers?",),
}


def _compile(rules: dict[str, tuple[str, ...]]) -> dict[str, re.Pattern[str]]:
    return {
        reason: re.compile(r"\b(?:" + "|".join(patterns) + r")\b", re.IGNORECASE)
        for reason, patterns in rules.items()
    }


_BLOCK = _compile(BLOCK_RULES)
_REVIEW = _compile(REVIEW_RULES)


@dataclass(frozen=True)
class ScreenResult:
    """Outcome of the safety screen."""

    verdict: Verdict
    reasons: list[str] = field(default_factory=list)
    recall_source: str = RECALL_NOT_CHECKED

    @property
    def approvable_without_override(self) -> bool:
        """True only for PASS; REVIEW needs an override and BLOCK never passes."""
        return self.verdict == "PASS"


def screen(*texts: str | None, recall_checked: bool = False) -> ScreenResult:
    """Screen a listing's free text (caption line, title, category, notes).

    Args:
        *texts: Any text describing the item; None values are ignored.
        recall_checked: True once a recall lookup has cleared the item.
            Until then the result is at least REVIEW.

    Returns:
        BLOCK with every matching block reason, else REVIEW with reasons,
        else PASS.
    """
    haystack = " ".join(t for t in texts if t)
    blocks = [reason for reason, rx in _BLOCK.items() if rx.search(haystack)]
    if blocks:
        return ScreenResult("BLOCK", blocks)
    reviews = [reason for reason, rx in _REVIEW.items() if rx.search(haystack)]
    if not recall_checked:
        reviews.append("recall_not_checked")
    if reviews:
        return ScreenResult("REVIEW", reviews)
    return ScreenResult("PASS", [], recall_source="checked")
