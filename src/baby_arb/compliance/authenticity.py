"""Counterfeit risk check for brands with known fake-market presence."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from baby_arb.compliance.rules import (
    COUNTERFEIT_PRONE_BRANDS,
    MIN_SELLER_FEEDBACK_COUNT,
    MIN_SELLER_FEEDBACK_PCT_NUM,
)
from baby_arb.models.candidate import BuyCandidate
from baby_arb.models.compliance import ComplianceVerdictKind


@dataclass
class AuthResult:
    verdict: ComplianceVerdictKind
    reasons: list[str]


def check_authenticity(candidate: BuyCandidate) -> AuthResult:
    """Check seller signals for counterfeit-prone brands.

    For brands NOT on the list: PASS automatically.
    For brands on the list: require strong seller signals or REVIEW.
    Multiple weak signals → BLOCK.
    """
    brand = (candidate.brand or "").lower().strip()

    if brand not in COUNTERFEIT_PRONE_BRANDS:
        return AuthResult(verdict=ComplianceVerdictKind.PASS, reasons=[])

    weak_signals: list[str] = []

    if (
        candidate.seller_feedback_count is None
        or candidate.seller_feedback_count < MIN_SELLER_FEEDBACK_COUNT
    ):
        weak_signals.append("auth_seller_feedback_count_low")

    if (
        candidate.seller_feedback_pct is None
        or candidate.seller_feedback_pct < Decimal(MIN_SELLER_FEEDBACK_PCT_NUM)
    ):
        weak_signals.append("auth_seller_feedback_pct_low")

    if not candidate.photos or len(candidate.photos) < 3:
        weak_signals.append("auth_photos_missing")

    if len(weak_signals) >= 2:
        return AuthResult(
            verdict=ComplianceVerdictKind.BLOCK,
            reasons=["auth_high_risk: multiple counterfeit risk signals", *weak_signals],
        )

    if weak_signals:
        return AuthResult(
            verdict=ComplianceVerdictKind.REVIEW,
            reasons=weak_signals,
        )

    return AuthResult(verdict=ComplianceVerdictKind.PASS, reasons=[])
