"""Edit parsing (rules + model fallback), validation, application and echo text."""

from __future__ import annotations

import json

import pytest
from baby_arb.marketing.edits import (
    EditOp,
    apply_layout_and_fields,
    describe,
    parse_edit,
    parse_rules,
    validate_op,
)
from baby_arb.marketing.llm import LLMResult
from baby_arb.marketing.render.layout import Layout

from tests.fixtures_edit_phrasings import PHRASINGS, UNPARSED

STATE = {"photos": [1, 2, 3, 4], "price": 2000}


def _fake(text: str | None, degraded: bool = False):
    calls: list[str] = []

    def completer(purpose, messages, **_kw):
        calls.append(purpose)
        return LLMResult(text, degraded, "capped" if degraded else None, "fake", "fake")

    completer.calls = calls  # type: ignore[attr-defined]
    return completer


def _no_model(*_a, **_kw):
    raise AssertionError("model must not be called for rule-covered phrasings")


def test_fixture_has_at_least_twenty_phrasings():
    assert len(PHRASINGS) >= 20


@pytest.mark.parametrize(("text", "expected"), PHRASINGS, ids=[p[0] for p in PHRASINGS])
def test_rule_phrasings(text, expected):
    plan = parse_edit(text, STATE, completer=_no_model)
    assert plan.question is None, plan.question
    assert plan.parsed_by == "rules"
    assert [(o.op, o.target, o.value) for o in plan.ops] == expected


@pytest.mark.parametrize("text", UNPARSED)
def test_unparsed_phrasings_need_model(text):
    assert parse_rules(text) is None


def test_model_fallback_validated():
    completer = _fake(json.dumps({"ops": [{"op": "swap_photo", "target": "1", "value": 2}]}))
    plan = parse_edit("the main photo should be the one with the canopy up", STATE, completer)
    assert plan.parsed_by == "model"
    assert [(o.op, o.value) for o in plan.ops] == [("swap_photo", 2)]
    assert completer.calls == ["edit_parse"]


def test_model_cannot_invent_a_price():
    completer = _fake(json.dumps({"ops": [{"op": "set_field", "target": "price",
                                           "value": 1500}]}))
    plan = parse_edit("make it cheaper", STATE, completer)
    assert plan.ops == []
    assert "not a number you typed" in (plan.question or "")


def test_model_question_is_relayed():
    plan = parse_edit("less busy overall", STATE, _fake(json.dumps({"question": "Which part?"})))
    assert plan.ops == [] and plan.question == "Which part?"


def test_degraded_model_asks_instead_of_guessing():
    plan = parse_edit("make it pop more", STATE, _fake(None, degraded=True))
    assert plan.ops == [] and plan.question and "didn't get that" in plan.question


def test_garbage_model_reply_asks():
    plan = parse_edit("make it pop more", STATE, _fake("sure! I'll make it pop"))
    assert plan.ops == [] and plan.question


def test_unknown_photo_rejected():
    plan = parse_edit("use photo 9 as main", STATE, _no_model)
    assert plan.ops == [] and "no photo 9" in (plan.question or "")


def test_code_cannot_be_hidden():
    problems = validate_op(EditOp(op="toggle", target="code", value="off"), "", STATE)
    assert problems and "can't be switched off" in problems[0]


def test_apply_changes_and_drift_values():
    layout = Layout(photo_order=[1, 2, 3])
    ops = parse_edit("price bigger, drop 'washed', use photo 3 as main, price 1800",
                     STATE, _no_model).ops
    out = apply_layout_and_fields(
        ops, {"price": 2000, "condition_note": "washed, small mark on strap"}, layout,
        "Stroller · KES 2,000\n\nWashed, small mark on strap.\n\nDM P-0001 to buy.",
        "Stroller KES 2,000 | P-0001\nWashed, small mark on strap.",
    )
    assert out.layout.photo_order == [3, 1, 2]
    assert out.layout.step("price") == 1
    assert out.fields["price"] == 1800 and out.fields_changed
    assert "washed" not in out.caption_ig.lower() and "washed" not in out.caption_tiktok.lower()
    assert out.fields["condition_note"] == "small mark on strap"
    assert layout.photo_order == [1, 2, 3]  # input not mutated
    assert [c.op.op for c in out.changes] == ["resize", "rewrite_caption", "swap_photo",
                                              "set_field"]
    assert (out.changes[0].before, out.changes[0].after) == ("0", "1")
    assert (out.changes[3].before, out.changes[3].after) == ("2000", "1800")


def test_resize_limit_reported():
    layout = Layout(photo_order=[1], sizes={"price": 3})
    out = apply_layout_and_fields([EditOp(op="resize", target="price", value="up")], {},
                                  layout, "", "")
    assert out.problems and "limit" in out.problems[0]


@pytest.mark.parametrize(
    ("op", "text"),
    [
        (EditOp(op="resize", target="price", value="up"), "make price badge larger"),
        (EditOp(op="swap_photo", target="1", value=3), "set photo 3 as hero"),
        (EditOp(op="rewrite_caption", target="all", value="remove: washed"),
         "remove 'washed' from captions"),
        (EditOp(op="set_field", target="price", value=1800), "set price to KES 1,800"),
        (EditOp(op="move", target="price", value="top-right"), "move price badge to top right"),
    ],
)
def test_describe(op, text):
    assert describe(op) == text
