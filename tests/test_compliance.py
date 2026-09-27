"""Compliance gate tests."""

from __future__ import annotations

from decimal import Decimal

from baby_arb.compliance.authenticity import check_authenticity
from baby_arb.compliance.carseat import check_carseat_dom
from baby_arb.compliance.cpsc import check_cpsc_recall
from baby_arb.compliance.gate import gate
from baby_arb.compliance.kebs import check_kebs_restricted
from baby_arb.models.compliance import ComplianceVerdictKind


# ── Car seat DOM ─────────────────────────────────────────────────────
class TestCarseatDom:
    def test_dom_in_text_2024_passes(self, standard_carseat_candidate, now):
        cand = standard_carseat_candidate.model_copy(
            update={"condition_text": "Manufactured 06/2024 like-new"}
        )
        result = check_carseat_dom(cand, now=now)
        assert result.verdict == ComplianceVerdictKind.PASS

    def test_dom_2018_blocked(self, standard_carseat_candidate, now):
        cand = standard_carseat_candidate.model_copy(
            update={"condition_text": "DOM 06/2018, all parts intact"}
        )
        result = check_carseat_dom(cand, now=now)
        assert result.verdict == ComplianceVerdictKind.BLOCK
        assert any("dom_expired" in r for r in result.reasons)

    def test_dom_near_expiry_review(self, standard_carseat_candidate, now):
        # 5 years 1 month before now → near expiry
        cand = standard_carseat_candidate.model_copy(
            update={"condition_text": "Manufactured 04/2021"}
        )
        result = check_carseat_dom(cand, now=now)
        assert result.verdict == ComplianceVerdictKind.REVIEW
        assert any("dom_near_expiry" in r for r in result.reasons)

    def test_dom_missing_review(self, standard_carseat_candidate, now):
        cand = standard_carseat_candidate.model_copy(
            update={"condition_text": "Used, in great shape, no manufacturing date listed"}
        )
        result = check_carseat_dom(cand, now=now)
        assert result.verdict == ComplianceVerdictKind.REVIEW
        assert any("dom_not_visible" in r for r in result.reasons)


# ── Authenticity ────────────────────────────────────────────────────
class TestAuthenticity:
    def test_non_listed_brand_passes(self, standard_carseat_candidate):
        cand = standard_carseat_candidate.model_copy(update={"brand": "GenericBrand"})
        result = check_authenticity(cand)
        assert result.verdict == ComplianceVerdictKind.PASS

    def test_listed_brand_strong_signals_passes(self, standard_carseat_candidate):
        # 200 feedback @ 99.2% with 4 photos
        result = check_authenticity(standard_carseat_candidate)
        assert result.verdict == ComplianceVerdictKind.PASS

    def test_listed_brand_low_feedback_review(self, standard_carseat_candidate):
        cand = standard_carseat_candidate.model_copy(
            update={"seller_feedback_count": 12}
        )
        result = check_authenticity(cand)
        assert result.verdict == ComplianceVerdictKind.REVIEW

    def test_listed_brand_multiple_weak_signals_blocks(
        self, standard_carseat_candidate
    ):
        cand = standard_carseat_candidate.model_copy(
            update={
                "seller_feedback_count": 5,
                "seller_feedback_pct": Decimal("90"),
                "photos": [],
            }
        )
        result = check_authenticity(cand)
        assert result.verdict == ComplianceVerdictKind.BLOCK


# ── KEBS ─────────────────────────────────────────────────────────────
class TestKebs:
    def test_clean_item_passes(self, standard_carseat_candidate):
        result = check_kebs_restricted(standard_carseat_candidate)
        assert result.verdict == ComplianceVerdictKind.PASS

    def test_mattress_review(self, standard_carseat_candidate):
        cand = standard_carseat_candidate.model_copy(
            update={
                "model": "Crib Mattress",
                "condition_text": "Like new mattress, gently used",
            }
        )
        result = check_kebs_restricted(cand)
        assert result.verdict == ComplianceVerdictKind.REVIEW
        assert any("kebs" in r.lower() for r in result.reasons)


# ── CPSC ─────────────────────────────────────────────────────────────
class TestCpsc:
    def test_clear_when_no_recalls(self, standard_carseat_candidate, empty_cpsc_cache, now):
        result = check_cpsc_recall(standard_carseat_candidate, now=now)
        assert result.kind == "clear"

    def test_unreachable_when_no_cache(self, standard_carseat_candidate, now):
        # No cache fixture applied
        result = check_cpsc_recall(standard_carseat_candidate, now=now)
        assert result.kind == "unreachable"

    def test_recalled_when_match(self, standard_carseat_candidate, loaded_cpsc_cache, now):
        cand = standard_carseat_candidate.model_copy(
            update={"brand": "MockBrand", "model": "X1 stroller"}
        )
        result = check_cpsc_recall(cand, now=now)
        assert result.kind == "recalled"


# ── Gate integration ────────────────────────────────────────────────
class TestGate:
    def test_clean_carseat_passes(
        self, standard_carseat_candidate, empty_cpsc_cache, now
    ):
        verdict = gate(standard_carseat_candidate, now=now)
        assert verdict.verdict == ComplianceVerdictKind.PASS

    def test_safety_block_short_circuits(
        self, standard_carseat_candidate, empty_cpsc_cache, now
    ):
        cand = standard_carseat_candidate.model_copy(
            update={"model": "Rock 'n Play Sleeper"}
        )
        verdict = gate(cand, now=now)
        assert verdict.verdict == ComplianceVerdictKind.BLOCK
        # Other checks were skipped
        assert "carseat_dom" in verdict.checks_skipped or len(verdict.checks_run) == 1

    def test_carseat_dom_block(
        self, standard_carseat_candidate, empty_cpsc_cache, now
    ):
        cand = standard_carseat_candidate.model_copy(
            update={"condition_text": "DOM 2018, used 4 years"}
        )
        verdict = gate(cand, now=now)
        assert verdict.verdict == ComplianceVerdictKind.BLOCK

    def test_review_collected_when_dom_missing(
        self, standard_carseat_candidate, empty_cpsc_cache, now
    ):
        cand = standard_carseat_candidate.model_copy(
            update={"condition_text": "Used, like-new"}
        )
        verdict = gate(cand, now=now)
        assert verdict.verdict == ComplianceVerdictKind.REVIEW
        assert any("dom_not_visible" in r for r in verdict.reasons)

    def test_unreachable_cpsc_yields_review(self, standard_carseat_candidate, now):
        # No cache loaded → CPSC unreachable → REVIEW (not BLOCK)
        verdict = gate(standard_carseat_candidate, now=now)
        assert verdict.verdict == ComplianceVerdictKind.REVIEW
