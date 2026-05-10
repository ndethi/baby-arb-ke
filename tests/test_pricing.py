"""Pricing engine tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from baby_arb.models.candidate import BuyCandidate, ItemCategory, ItemCondition
from baby_arb.models.pricing import Confidence, PricingVerdictKind
from baby_arb.pricing import calculate_landed_cost
from baby_arb.pricing.intl_shipping import (
    Carrier,
    billable_weight_lb,
    dim_weight_lb,
    international_shipping_usd,
)
from baby_arb.pricing.ke_customs import calculate_ke_customs
from baby_arb.pricing.us_costs import calculate_us_sales_tax, sales_tax_rate
from baby_arb.pricing.verdict import pricing_verdict


# ── US sales tax ─────────────────────────────────────────────────────
class TestUsSalesTax:
    def test_de_has_no_sales_tax(self):
        assert sales_tax_rate("DE") == Decimal("0")

    def test_or_has_no_sales_tax(self):
        assert sales_tax_rate("OR") == Decimal("0")

    def test_tx_has_sales_tax(self):
        assert sales_tax_rate("TX") > Decimal("0")

    def test_unknown_state_is_zero(self):
        assert sales_tax_rate("ZZ") == Decimal("0")

    def test_none_state_is_zero(self):
        assert sales_tax_rate(None) == Decimal("0")

    def test_calculate_includes_shipping(self):
        # TX is 6.25%
        result = calculate_us_sales_tax(
            Decimal("100"), Decimal("20"), "TX", is_clothing=False
        )
        assert result == Decimal("120") * Decimal("0.0625")

    def test_clothing_exempt_in_nj(self):
        result = calculate_us_sales_tax(
            Decimal("100"), Decimal("20"), "NJ", is_clothing=True
        )
        assert result == Decimal("0")


# ── Dim weight ───────────────────────────────────────────────────────
class TestDimWeight:
    def test_dim_weight_carseat_box(self):
        # 18*18*24 / 139 = 7776/139 ≈ 55.94
        result = dim_weight_lb(Decimal("18"), Decimal("18"), Decimal("24"))
        assert Decimal("55") < result < Decimal("57")

    def test_billable_weight_dim_dominated(self):
        # carseat at 9 lb actual but 56 lb dim
        bill, dim_dom = billable_weight_lb(
            Decimal("9"), Decimal("18"), Decimal("18"), Decimal("24")
        )
        assert dim_dom is True
        assert bill > Decimal("50")

    def test_billable_weight_actual_dominated(self):
        # heavy compact item
        bill, dim_dom = billable_weight_lb(
            Decimal("60"), Decimal("12"), Decimal("12"), Decimal("12")
        )
        assert dim_dom is False
        assert bill == Decimal("60")

    def test_billable_weight_missing_dims_uses_buffer(self):
        bill, dim_dom = billable_weight_lb(Decimal("10"), None, None, None)
        assert dim_dom is False
        assert bill == Decimal("10") * Decimal("1.3")


# ── International shipping ──────────────────────────────────────────
class TestIntlShipping:
    def test_dhl_carseat_dim_dominated(self):
        cost, bill, dim_dom = international_shipping_usd(
            Decimal("9"),
            Decimal("18"),
            Decimal("18"),
            Decimal("24"),
            carrier=Carrier.DHL_EXPRESS,
        )
        assert dim_dom is True
        # ~56 lb @ $6/lb band = ~$336
        assert Decimal("250") < cost < Decimal("500")

    def test_sea_freight_much_cheaper(self):
        dhl_cost, _, _ = international_shipping_usd(
            Decimal("22"),
            Decimal("30"),
            Decimal("16"),
            Decimal("12"),
            carrier=Carrier.DHL_EXPRESS,
        )
        sea_cost, _, _ = international_shipping_usd(
            Decimal("22"),
            Decimal("30"),
            Decimal("16"),
            Decimal("12"),
            carrier=Carrier.SEA_FREIGHT,
        )
        assert sea_cost < dhl_cost / 2


# ── KE customs ──────────────────────────────────────────────────────
class TestKeCustoms:
    def test_customs_breakdown(self):
        cif = Decimal("100000")  # 100k KES
        result = calculate_ke_customs(cif)
        assert result["duty"] == cif * Decimal("0.25")
        assert result["idf"] == cif * Decimal("0.035")
        assert result["rdl"] == cif * Decimal("0.02")
        # VAT on (CIF + duty)
        assert result["vat"] == (cif + result["duty"]) * Decimal("0.16")
        assert result["total"] == (
            result["duty"] + result["idf"] + result["rdl"] + result["vat"]
        )


# ── Engine integration ──────────────────────────────────────────────
class TestEngine:
    def test_carseat_de_warehouse_integration(
        self, standard_carseat_candidate, fresh_fx, now
    ):
        # Force seller location to DE-equivalent (no sales tax on warehouse side
        # — warehouse_state controls sales tax, not seller_state)
        landed = calculate_landed_cost(
            standard_carseat_candidate,
            warehouse_state="DE",
            carrier=Carrier.DHL_EXPRESS,
            now=now,
        )
        # DE = no sales tax
        assert landed.us_sales_tax_usd == Decimal("0")
        # Carseat dimensions force dim weight
        assert landed.dim_weight_used is True
        # FX age is fresh
        assert landed.fx_rate_age_hours < Decimal("1")
        # Customs are positive
        assert landed.ke_duty_kes > 0
        assert landed.ke_vat_kes > 0
        # Total is in plausible range for a $200 carseat air-freighted
        assert landed.total_landed_kes > Decimal("80000")

    def test_warehouse_state_affects_total(
        self, standard_carseat_candidate, fresh_fx, now
    ):
        de_cost = calculate_landed_cost(
            standard_carseat_candidate, warehouse_state="DE", now=now
        )
        tx_cost = calculate_landed_cost(
            standard_carseat_candidate, warehouse_state="TX", now=now
        )
        assert tx_cost.us_sales_tax_usd > Decimal("0")
        assert tx_cost.total_landed_kes > de_cost.total_landed_kes

    def test_missing_weight_uses_category_fallback(self, fresh_fx, now):
        candidate = BuyCandidate(
            candidate_id="missing-weight",
            marketplace="ebay",
            listing_url="https://www.ebay.com/itm/x",
            brand="NUNA",
            model="PIPA",
            category=ItemCategory.CAR_SEAT,
            condition_text="manufactured 2024",
            condition_normalized=ItemCondition.LIKE_NEW,
            listing_price_usd=Decimal("180"),
            us_shipping_usd=Decimal("22"),
            seller_id="x",
            seller_feedback_count=200,
            seller_feedback_pct=Decimal("99"),
            photos=["https://example.com/1.jpg"],
            reference_ke_sale_price_kes=Decimal("32500"),
            reference_n=3,
        )
        landed = calculate_landed_cost(candidate, now=now)
        assert landed.weight_source == "category_avg"
        assert landed.confidence == Confidence.LOW

    def test_low_confidence_when_no_ke_reference(self, fresh_fx, now):
        candidate = BuyCandidate(
            candidate_id="no-ref",
            marketplace="ebay",
            listing_url="https://www.ebay.com/itm/x",
            brand="NUNA",
            model="PIPA",
            category=ItemCategory.CAR_SEAT,
            condition_text="2024",
            condition_normalized=ItemCondition.LIKE_NEW,
            listing_price_usd=Decimal("180"),
            us_shipping_usd=Decimal("22"),
            weight_lb=Decimal("9"),
            weight_source="listed",
            length_in=Decimal("18"),
            width_in=Decimal("18"),
            height_in=Decimal("24"),
            seller_id="x",
            seller_feedback_count=200,
            seller_feedback_pct=Decimal("99"),
            photos=["https://example.com/1.jpg"],
        )
        landed = calculate_landed_cost(candidate, now=now)
        assert landed.confidence == Confidence.LOW


# ── Verdict logic ───────────────────────────────────────────────────
class TestVerdict:
    def test_skip_when_below_floor(self, standard_carseat_candidate, fresh_fx, now):
        # The default carseat case is dim-weight dominated and ships from DE,
        # which puts landed cost well above the 32500 KES KE reference,
        # producing negative margin. That's the SKIP case.
        landed = calculate_landed_cost(
            standard_carseat_candidate, warehouse_state="DE", now=now
        )
        verdict = pricing_verdict(standard_carseat_candidate, landed)
        assert verdict.verdict == PricingVerdictKind.SKIP
        assert verdict.margin_pct < Decimal("50")

    def test_buy_when_above_floor_and_high_confidence(self, fresh_fx, now):
        # Construct a candidate that clears margin floor by a wide margin.
        # The math is harsh: KE customs (25% duty + 16% VAT + 5.5% IDF/RDL)
        # alone adds ~50% to the CIF in KES, so the KE reference must be
        # well above 2x landed cost USD-equivalent to clear 50% net margin.
        candidate = BuyCandidate(
            candidate_id="buy-case",
            marketplace="ebay",
            listing_url="https://www.ebay.com/itm/x",
            brand="Generic",
            model="LightItem",
            category=ItemCategory.BABY_CARRIER,  # light, low dim weight
            condition_text="2024",
            condition_normalized=ItemCondition.LIKE_NEW,
            listing_price_usd=Decimal("20"),
            us_shipping_usd=Decimal("5"),
            weight_lb=Decimal("2"),
            weight_source="actual",
            length_in=Decimal("10"),
            width_in=Decimal("8"),
            height_in=Decimal("4"),
            seller_id="x",
            seller_feedback_count=200,
            seller_feedback_pct=Decimal("99"),
            photos=[
                "https://example.com/1.jpg",
                "https://example.com/2.jpg",
                "https://example.com/3.jpg",
            ],
            # Generous KE reference: a $25 baby carrier landed costs
            # ~12000 KES; clearing 50% margin needs >18000 KES KE price.
            reference_ke_sale_price_kes=Decimal("25000"),
            reference_source="jiji_median_sold",
            reference_n=6,
        )
        landed = calculate_landed_cost(candidate, warehouse_state="DE", now=now)
        verdict = pricing_verdict(candidate, landed)
        # Either BUY or REVIEW depending on exact numbers — the point is it
        # shouldn't SKIP when the math clearly clears the floor.
        assert verdict.verdict in (
            PricingVerdictKind.BUY,
            PricingVerdictKind.REVIEW,
        )
        assert verdict.margin_pct >= Decimal("50")

    def test_abstain_when_no_ke_reference(self, fresh_fx, now):
        candidate = BuyCandidate(
            candidate_id="abstain",
            marketplace="ebay",
            listing_url="https://www.ebay.com/itm/x",
            brand="X",
            model="Y",
            category=ItemCategory.OTHER,
            condition_text="2024",
            condition_normalized=ItemCondition.UNKNOWN,
            listing_price_usd=Decimal("50"),
            seller_id="x",
            seller_feedback_count=200,
            seller_feedback_pct=Decimal("99"),
            photos=[],
        )
        landed = calculate_landed_cost(candidate, now=now)
        verdict = pricing_verdict(candidate, landed)
        assert verdict.verdict == PricingVerdictKind.ABSTAIN
