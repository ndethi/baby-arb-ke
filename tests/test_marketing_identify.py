"""Photo identification: parsing, safety-relevant categories, confidence gate."""

from __future__ import annotations

import json

import pytest
from baby_arb.marketing.identify import AUTO_THRESHOLD, Identification, encode_photo, identify
from baby_arb.marketing.llm import LLMResult
from PIL import Image


def _reply(payload, degraded=False):
    calls = []

    def completer(purpose, messages, **kw):
        calls.append((purpose, messages))
        text = payload if isinstance(payload, str) else json.dumps(payload)
        return LLMResult(None if degraded else text, degraded, "capped" if degraded else None)

    completer.calls = calls
    return completer


@pytest.fixture
def photo(tmp_path):
    path = tmp_path / "p.jpg"
    Image.new("RGB", (2400, 1800), (200, 180, 160)).save(path)
    return path


WALKER = {"brand": "HUANGER", "model": None, "category": "push_walker",
          "item_name": "Music Walker", "age_range": "6m+", "visible_text": ["MUSIC WALKER"],
          "confidence": 0.95}


def test_confident_result_fills_title(photo):
    completer = _reply(WALKER)
    ident = identify([photo], completer)
    assert ident.auto and ident.title == "Huanger Music Walker"
    assert ident.category_words == "push walker"
    purpose, messages = completer.calls[0]
    assert purpose == "identify"
    parts = messages[0]["content"]
    assert parts[1]["type"] == "image_url"
    assert parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_low_confidence_is_not_auto(photo):
    ident = identify([photo], _reply({**WALKER, "confidence": AUTO_THRESHOLD - 0.01}))
    assert not ident.auto and ident.title == "Huanger Music Walker"


@pytest.mark.parametrize(("raw", "expected"), [
    ("Baby Walker", "other"), ("seated walker", "seated_walker"), ("car-seat", "car_seat"),
    ("spaceship", "other"),
])
def test_categories_are_our_keys_never_free_text(photo, raw, expected):
    ident = identify([photo], _reply({**WALKER, "category": raw}))
    assert ident.category == expected


def test_confidence_clamped_and_brand_in_model_not_doubled(photo):
    ident = identify([photo], _reply({"brand": "Graco", "model": "Graco Modes Nest",
                                      "category": "stroller", "confidence": 7}))
    assert ident.confidence == 1.0 and ident.title == "Graco Modes Nest"


@pytest.mark.parametrize("reply", ["not json", "{}garbage", json.dumps({"confidence": "x"})])
def test_bad_replies_degrade(photo, reply):
    ident = identify([photo], _reply(reply))
    assert ident.degraded or not ident.auto


def test_degraded_model_and_no_photos():
    assert identify([], _reply(WALKER)).degraded
    assert Identification(degraded=True).auto is False


def test_degraded_call(photo):
    ident = identify([photo], _reply(WALKER, degraded=True))
    assert ident.degraded and ident.reason == "capped"


def test_encode_photo_downscales(photo):
    import base64
    import io

    uri = encode_photo(photo)
    data = base64.b64decode(uri.split(",", 1)[1])
    assert max(Image.open(io.BytesIO(data)).size) == 1024
