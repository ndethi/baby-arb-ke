"""The single compliance gate entry point.

Cheapest checks first, short-circuit on BLOCK. Collect REVIEW reasons.
Final verdict is the strictest seen.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from baby_arb.compliance.authenticity import check_authenticity
from baby_arb.compliance.carseat import check_carseat_dom
from baby_arb.compliance.cpsc import check_cpsc_recall
from baby_arb.compliance.kebs import check_kebs_restricted
from baby_arb.compliance.rules import SAFETY_BLOCK_KEYWORDS
from baby_arb.models.candidate import BuyCandidate, ItemCategory
from baby_arb.models.compliance import ComplianceVerdict, ComplianceVerdictKind


def gate(
    candidate: BuyCandidate,
    *,
    now: datetime | None = None,
) -> ComplianceVerdict:
    """Run the compliance gate on a candidate.

    Cheapest checks first. Short-circuits on first BLOCK.

    Args:
        candidate: The candidate to evaluate.
        now: Override for testing.

    Returns:
        ComplianceVerdict with PASS, BLOCK, or REVIEW.
    """
    now = now or datetime.now(UTC)
    reasons: list[str] = []
    checks_run: list[str] = []
    checks_skipped: list[str] = []
    cpsc_age: Decimal | None = None

    # ── Step 1: static safety blocks (cheapest) ─────────────────────
    checks_run.append("safety_blocks")
    safety = _check_safety_blocks(candidate)
    if safety:
        checks_skipped = ["carseat_dom", "authenticity", "kebs", "cpsc"]
        return ComplianceVerdict(
            candidate_id=candidate.candidate_id,
            verdict=ComplianceVerdictKind.BLOCK,
            reasons=[safety],
            checks_run=checks_run,
            checks_skipped=checks_skipped,
            checked_at=now,
        )

    # ── Step 2: car seat DOM ────────────────────────────────────────
    if candidate.category == ItemCategory.CAR_SEAT:
        checks_run.append("carseat_dom")
        carseat = check_carseat_dom(candidate, now=now)
        if carseat.verdict == ComplianceVerdictKind.BLOCK:
            checks_skipped = ["authenticity", "kebs", "cpsc"]
            return ComplianceVerdict(
                candidate_id=candidate.candidate_id,
                verdict=ComplianceVerdictKind.BLOCK,
                reasons=carseat.reasons,
                checks_run=checks_run,
                checks_skipped=checks_skipped,
                checked_at=now,
            )
        if carseat.verdict == ComplianceVerdictKind.REVIEW:
            reasons.extend(carseat.reasons)

    # ── Step 3: counterfeit-prone brand authenticity ────────────────
    checks_run.append("authenticity")
    auth = check_authenticity(candidate)
    if auth.verdict == ComplianceVerdictKind.BLOCK:
        checks_skipped = ["kebs", "cpsc"]
        return ComplianceVerdict(
            candidate_id=candidate.candidate_id,
            verdict=ComplianceVerdictKind.BLOCK,
            reasons=auth.reasons,
            checks_run=checks_run,
            checks_skipped=checks_skipped,
            checked_at=now,
        )
    if auth.verdict == ComplianceVerdictKind.REVIEW:
        reasons.extend(auth.reasons)

    # ── Step 4: KEBS restricted ─────────────────────────────────────
    checks_run.append("kebs")
    kebs = check_kebs_restricted(candidate)
    if kebs.verdict == ComplianceVerdictKind.BLOCK:
        checks_skipped = ["cpsc"]
        return ComplianceVerdict(
            candidate_id=candidate.candidate_id,
            verdict=ComplianceVerdictKind.BLOCK,
            reasons=kebs.reasons,
            checks_run=checks_run,
            checks_skipped=checks_skipped,
            checked_at=now,
        )
    if kebs.verdict == ComplianceVerdictKind.REVIEW:
        reasons.extend(kebs.reasons)

    # ── Step 5: CPSC recall (most expensive) ────────────────────────
    checks_run.append("cpsc")
    cpsc = check_cpsc_recall(candidate, now=now)
    cpsc_age = cpsc.cache_age_hours
    if cpsc.kind == "recalled":
        return ComplianceVerdict(
            candidate_id=candidate.candidate_id,
            verdict=ComplianceVerdictKind.BLOCK,
            reasons=[f"cpsc_recalled: {cpsc.detail}"],
            checks_run=checks_run,
            checks_skipped=checks_skipped,
            cpsc_cache_age_hours=cpsc_age,
            checked_at=now,
        )
    if cpsc.kind in ("related_recall", "unreachable"):
        reasons.append(f"cpsc_{cpsc.kind}: {cpsc.detail}")

    # ── Final verdict ───────────────────────────────────────────────
    if reasons:
        return ComplianceVerdict(
            candidate_id=candidate.candidate_id,
            verdict=ComplianceVerdictKind.REVIEW,
            reasons=reasons,
            checks_run=checks_run,
            checks_skipped=checks_skipped,
            cpsc_cache_age_hours=cpsc_age,
            checked_at=now,
        )

    return ComplianceVerdict(
        candidate_id=candidate.candidate_id,
        verdict=ComplianceVerdictKind.PASS,
        reasons=[],
        checks_run=checks_run,
        checks_skipped=checks_skipped,
        cpsc_cache_age_hours=cpsc_age,
        checked_at=now,
    )


def _check_safety_blocks(candidate: BuyCandidate) -> str | None:
    """Return BLOCK reason if listing matches a static safety block."""
    haystack = (
        f"{candidate.brand} {candidate.model} {candidate.condition_text}"
    ).lower()
    for keyword, reason in SAFETY_BLOCK_KEYWORDS:
        if keyword in haystack:
            return f"safety_block: {reason}"
    return None
