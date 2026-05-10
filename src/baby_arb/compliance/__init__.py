"""Compliance gate. Hard veto layer over every buy candidate.

Single entry point: `gate(candidate) -> ComplianceVerdict`.
Returns one of PASS, BLOCK, REVIEW. No other states. Fail closed.
"""

from baby_arb.compliance.gate import gate
from baby_arb.compliance.rules import (
    CARSEAT_DOM_CEILING_YEARS,
    COUNTERFEIT_PRONE_BRANDS,
)

__all__ = [
    "CARSEAT_DOM_CEILING_YEARS",
    "COUNTERFEIT_PRONE_BRANDS",
    "gate",
]
