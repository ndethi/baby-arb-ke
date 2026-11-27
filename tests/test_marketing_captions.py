"""Captions: house template, model drafts accepted only when they keep the facts."""

from __future__ import annotations

import json

from baby_arb.marketing.captions import (
    CaptionInput,
    draft_captions,
    rewrite_caption,
    strip_phrase,
    template_captions,
    validate_caption,
)
from baby_arb.marketing.llm import LLMResult

ITEM = CaptionInput(code="P-0007", price=2000, title="Graco FastAction Fold stroller",
                    grade="B", age_range="0-36m", notes="washed, small mark on strap")


def _fake(text, degraded=False):
    def completer(purpose, messages, **_kw):
        return LLMResult(text, degraded, "capped" if degraded else None, "fake", "fake")
    return completer


def test_template_meets_house_rules():
    caps = template_captions(ITEM)
    assert caps.ig.splitlines()[0] == "Graco FastAction Fold stroller · KES 2,000 · 0-36m"
    assert validate_caption(caps.ig, ITEM, "ig") == []
    assert validate_caption(caps.tiktok, ITEM, "tiktok") == []
    assert caps.ig.count("DM P-0007 to buy") == 1


def test_template_anchor_only_with_ref_price():
    assert "New in Nairobi" not in template_captions(ITEM).ig
    with_ref = CaptionInput(**{**ITEM.__dict__, "ref_new_price": 8500})
    caps = template_captions(with_ref)
    assert "New in Nairobi from KES 8,500" in caps.ig
    assert validate_caption(caps.ig, with_ref, "ig") == []


def test_seller_template_mentions_seller():
    seller = CaptionInput(**{**ITEM.__dict__, "code": "L-0002", "seller": True})
    assert "Seller listing" in template_captions(seller).ig


def test_content_post_template_has_code_no_price():
    item = CaptionInput(code="C-0001", price=None, title="How we recall-check",
                        content_kind="tip")
    caps = template_captions(item)
    assert "C-0001" in caps.ig and "KES" not in caps.ig
    assert validate_caption(caps.ig, item, "ig") == []


def test_good_model_draft_accepted():
    ig = ("Graco FastAction Fold stroller · KES 2,000 · 0-36m\nFolds in one hand. Grade B, "
          "washed.\nDM P-0007 to buy\n#babyreshopke #nairobimums")
    tt = ("Graco FastAction Fold stroller KES 2,000 | P-0007\nOne-hand fold.\nDM P-0007 to buy\n"
          "#babyreshopke #nairobimums #stroller")
    caps = draft_captions(ITEM, _fake(json.dumps({"ig": ig, "tiktok": tt})))
    assert caps.source == "model" and caps.ig == ig


def test_model_draft_with_changed_price_rejected():
    ig = ("Graco FastAction Fold stroller · KES 1,800 · 0-36m\nDM P-0007 to buy\n#babyreshopke")
    tt = "Graco KES 2,000 | P-0007\nDM P-0007 to buy\n#a #b #c"
    caps = draft_captions(ITEM, _fake(json.dumps({"ig": ig, "tiktok": tt})))
    assert caps.source == "template"
    assert any("KES 1,800" in n for n in caps.notes)
    assert "KES 2,000" in caps.ig


def test_model_draft_with_invented_retail_price_rejected():
    ig = ("Graco FastAction Fold stroller · KES 2,000 · 0-36m\nNew it costs KES 15,000!\n"
          "DM P-0007 to buy\n#babyreshopke")
    tt = "Graco KES 2,000 | P-0007\nDM P-0007 to buy\n#a #b #c"
    caps = draft_captions(ITEM, _fake(json.dumps({"ig": ig, "tiktok": tt})))
    assert caps.source == "template"


def test_model_missing_cta_or_too_many_tags_rejected():
    ig = "Graco FastAction Fold stroller · KES 2,000 · 0-36m\n#a #b #c #d #e #f"
    caps = draft_captions(ITEM, _fake(json.dumps({"ig": ig, "tiktok": ig})))
    assert caps.source == "template"
    assert any("exactly once" in n for n in caps.notes)
    assert any("hashtags" in n for n in caps.notes)


def test_degraded_or_non_json_falls_back():
    assert draft_captions(ITEM, _fake(None, degraded=True)).source == "template"
    assert draft_captions(ITEM, _fake("Here you go: great stroller")).source == "template"


def test_rewrite_keeps_current_when_invalid():
    current = template_captions(ITEM).ig
    text, problems = rewrite_caption(current, "ig", "shorter", ITEM, _fake("Short. KES 999"))
    assert text == current and problems


def test_strip_phrase():
    assert strip_phrase("Washed, small mark on strap.", "washed") == "small mark on strap."
    assert strip_phrase("Grade B. Washed, fine.", "washed") == "Grade B. fine."
