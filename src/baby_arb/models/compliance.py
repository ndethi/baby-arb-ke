"""Models for compliance gate output."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class ComplianceVerdictKind(str, Enum):
    """The three legal states of a compliance verdict.

    There are no other states. PASS = clear to proceed.
    BLOCK = hard veto, never override. REVIEW = human eyes required.
    """

    PASS = "PASS"
    BLOCK = "BLOCK"
    REVIEW = "REVIEW"


class ComplianceVerdict(BaseModel):
    """Verdict from the compliance gate."""

    candidate_id: str
    verdict: ComplianceVerdictKind
    reasons: list[str] = Field(default_factory=list)

    checks_run: list[str] = Field(default_factory=list)
    checks_skipped: list[str] = Field(default_factory=list)

    cpsc_cache_age_hours: Decimal | None = None

    checked_at: datetime = Field(default_factory=datetime.utcnow)
