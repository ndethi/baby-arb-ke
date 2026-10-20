"""Car seat date-of-manufacture check.

A car seat older than CARSEAT_DOM_CEILING_YEARS from now is BLOCK.
A seat near expiry is REVIEW. Missing DOM is REVIEW.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from dateutil.relativedelta import relativedelta

from baby_arb.compliance.rules import CARSEAT_DOM_CEILING_YEARS
from baby_arb.models.candidate import BuyCandidate
from baby_arb.models.compliance import ComplianceVerdictKind


@dataclass
class CarseatResult:
    verdict: ComplianceVerdictKind
    reasons: list[str]


# Patterns for date-of-manufacture extraction from listing text.
DOM_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"manufactured?\s*[:\-]?\s*(\d{1,2})/(\d{4})", re.IGNORECASE),
    re.compile(r"manufactured?\s*[:\-]?\s*(\d{4})", re.IGNORECASE),
    re.compile(r"DOM\s*[:\-]?\s*(\d{1,2})/(\d{4})", re.IGNORECASE),
    re.compile(r"DOM\s*[:\-]?\s*(\d{4})", re.IGNORECASE),
    re.compile(r"date of (?:manufacture|man\.?)\s*[:\-]?\s*(\d{1,2})/(\d{4})", re.IGNORECASE),
    re.compile(r"date of (?:manufacture|man\.?)\s*[:\-]?\s*(\d{4})", re.IGNORECASE),
    re.compile(r"made (?:in )?(\d{4})", re.IGNORECASE),
]


def check_carseat_dom(
    candidate: BuyCandidate,
    *,
    now: datetime | None = None,
) -> CarseatResult:
    """Check car seat DOM against the operating ceiling."""
    now = now or datetime.now(UTC)

    dom = candidate.dom_extracted or _extract_dom_from_text(
        candidate.condition_text, now=now
    )

    if dom is None:
        return CarseatResult(
            verdict=ComplianceVerdictKind.REVIEW,
            reasons=["dom_not_visible"],
        )

    # Ensure dom is timezone-aware for comparison
    if dom.tzinfo is None:
        dom = dom.replace(tzinfo=UTC)

    age = relativedelta(now, dom)
    age_years = age.years + (age.months / 12)

    if age_years > CARSEAT_DOM_CEILING_YEARS:
        return CarseatResult(
            verdict=ComplianceVerdictKind.BLOCK,
            reasons=[
                f"dom_expired: manufactured {dom.date()}, "
                f"{age_years:.1f}y old (ceiling {CARSEAT_DOM_CEILING_YEARS}y)"
            ],
        )

    if age_years > CARSEAT_DOM_CEILING_YEARS - 1:
        return CarseatResult(
            verdict=ComplianceVerdictKind.REVIEW,
            reasons=[
                f"dom_near_expiry: manufactured {dom.date()}, "
                f"{age_years:.1f}y old"
            ],
        )

    return CarseatResult(verdict=ComplianceVerdictKind.PASS, reasons=[])


def _extract_dom_from_text(text: str, *, now: datetime) -> datetime | None:
    """Extract DOM from listing text. Returns None if not found."""
    for pattern in DOM_PATTERNS:
        match = pattern.search(text)
        if match:
            groups = match.groups()
            try:
                if len(groups) == 2:
                    month, year = int(groups[0]), int(groups[1])
                    if 1 <= month <= 12 and 2000 <= year <= now.year:
                        return datetime(year, month, 1, tzinfo=UTC)
                elif len(groups) == 1:
                    year = int(groups[0])
                    if 2000 <= year <= now.year:
                        return datetime(year, 1, 1, tzinfo=UTC)
            except (ValueError, TypeError):
                continue
    return None
