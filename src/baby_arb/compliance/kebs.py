"""KEBS restricted items check.

Loads from data/fixtures/kebs_restricted.json. Update via PR, never at runtime.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from baby_arb.models.candidate import BuyCandidate
from baby_arb.models.compliance import ComplianceVerdictKind

KEBS_FILE = Path("data/fixtures/kebs_restricted.json")


@dataclass
class KebsResult:
    verdict: ComplianceVerdictKind
    reasons: list[str]


@lru_cache(maxsize=1)
def _load_kebs_rules() -> dict:
    """Load KEBS restricted items list. Cached after first load."""
    if not KEBS_FILE.exists():
        # Permissive default if file missing — but log it.
        # Production should always have this file present.
        return {"blocked": [], "review": []}
    with KEBS_FILE.open() as f:
        return json.load(f)


def check_kebs_restricted(candidate: BuyCandidate) -> KebsResult:
    """Check candidate against KEBS restricted list."""
    rules = _load_kebs_rules()
    haystack = (
        f"{candidate.brand} {candidate.model} {candidate.category.value} "
        f"{candidate.condition_text}"
    ).lower()

    for entry in rules.get("blocked", []):
        keyword = entry.get("keyword", "").lower()
        if keyword and keyword in haystack:
            return KebsResult(
                verdict=ComplianceVerdictKind.BLOCK,
                reasons=[f"kebs_restricted: {entry.get('reason', keyword)}"],
            )

    for entry in rules.get("review", []):
        keyword = entry.get("keyword", "").lower()
        if keyword and keyword in haystack:
            return KebsResult(
                verdict=ComplianceVerdictKind.REVIEW,
                reasons=[f"kebs_certification_required: {entry.get('reason', keyword)}"],
            )

    return KebsResult(verdict=ComplianceVerdictKind.PASS, reasons=[])
