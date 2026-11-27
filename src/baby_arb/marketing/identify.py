"""Identify an item from its photos (ENGINE_SPEC Phase 2, Model ID).

One vision call through llm.py returns brand, model, a category from a fixed
list, an age range, the text it could read and a confidence score.

- Brand and model are taken only from text visible in the photos; anything
  else is left empty (the online lookup may fill specs later, with sources).
- The category comes from CATEGORIES so the safety screen sees our own words,
  never the model's: a "baby walker" the model calls a push walker is screened
  as "push walker", and a seated walker as "seated walker" (BLOCK).
- Confidence of AUTO_THRESHOLD or more fills the listing ("(auto)" on the
  preview); below it the bot asks the admin to confirm. Prices are never read
  from photos.
"""

from __future__ import annotations

import base64
import io
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps
from pydantic import BaseModel, Field, ValidationError, field_validator

from baby_arb.marketing.llm import LLMResult, complete

AUTO_THRESHOLD = 0.8
MAX_PHOTOS = 3
MAX_SIDE = 1024

# category key -> words the safety screen and captions see
CATEGORIES: dict[str, str] = {
    "stroller": "stroller",
    "car_seat": "car seat",
    "carrier": "baby carrier",
    "cot_or_crib": "cot",
    "bassinet": "bassinet",
    "high_chair": "high chair",
    "bouncer_rocker_swing": "bouncer",
    "push_walker": "push walker",
    "seated_walker": "seated walker",
    "activity_toy": "activity toy",
    "play_mat_or_gym": "play mat",
    "playpen": "playpen",
    "bath": "baby bath",
    "feeding": "feeding",
    "monitor": "baby monitor",
    "clothing": "baby clothing",
    "bedding": "baby bedding",
    "other": "baby item",
}

PROMPT = """You identify pre-loved baby items for a Nairobi resale shop.
Look at the photos and return JSON only:
{"brand": str|null, "model": str|null, "category": <one key>, "item_name": str,
 "age_range": str|null, "visible_text": [str], "confidence": number 0..1}

Rules:
- brand and model: ONLY from text you can read on the item, box or labels. If not
  readable, null. Never guess a brand from the look of the item.
- category: exactly one of: """ + ", ".join(CATEGORIES) + """.
  push_walker = the child stands and pushes it from behind; seated_walker = the
  child sits inside a frame or ring on wheels. If unsure which, use seated_walker.
- item_name: a short plain name, e.g. "Music Walker", "FastAction Fold stroller".
- age_range: only if printed (e.g. "6m+", "0-36m"), else null.
- confidence: how sure you are of brand + model + category together.
- Never mention prices."""


class _Raw(BaseModel):
    brand: str | None = None
    model: str | None = None
    category: str = "other"
    item_name: str | None = None
    age_range: str | None = None
    visible_text: list[str] = Field(default_factory=list)
    confidence: float = 0.0

    @field_validator("category")
    @classmethod
    def _known(cls, value: str) -> str:
        key = value.strip().lower().replace(" ", "_").replace("-", "_")
        return key if key in CATEGORIES else "other"

    @field_validator("confidence")
    @classmethod
    def _clamp(cls, value: float) -> float:
        return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class Identification:
    """What the photos show. `degraded` when the model could not be used."""

    brand: str | None = None
    model: str | None = None
    category: str = "other"
    item_name: str | None = None
    age_range: str | None = None
    visible_text: list[str] = field(default_factory=list)
    confidence: float = 0.0
    degraded: bool = False
    reason: str | None = None

    @property
    def auto(self) -> bool:
        """Confident enough to fill the listing without asking."""
        return not self.degraded and self.confidence >= AUTO_THRESHOLD and bool(self.title)

    @property
    def title(self) -> str | None:
        """E.g. "Huanger Music Walker"; None when nothing usable was found."""
        brand = _tidy_brand(self.brand) if self.brand else None
        name = (self.model or self.item_name or "").strip() or None
        if brand and name and brand.lower() in name.lower():
            return name
        return " ".join(x for x in (brand, name) if x) or None

    @property
    def category_words(self) -> str:
        """Our wording for the category (what the safety screen sees)."""
        return CATEGORIES.get(self.category, "baby item")


def _tidy_brand(brand: str) -> str:
    brand = brand.strip()
    return brand.title() if brand.isupper() and len(brand) > 3 else brand


def encode_photo(path: Path) -> str:
    """Downscaled JPEG data URI (EXIF rotation applied) to keep tokens low."""
    with Image.open(path) as im:
        img = ImageOps.exif_transpose(im).convert("RGB")
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


Completer = Callable[..., LLMResult]


def identify(photos: Sequence[Path], completer: Completer = complete) -> Identification:
    """Identify the item from up to MAX_PHOTOS photos. Never raises."""
    if not photos:
        return Identification(degraded=True, reason="no photos")
    try:
        images = [encode_photo(p) for p in list(photos)[:MAX_PHOTOS]]
    except OSError as exc:
        return Identification(degraded=True, reason=f"unreadable photo: {exc}")
    content: list[dict[str, Any]] = [{"type": "text", "text": PROMPT}]
    content += [{"type": "image_url", "image_url": {"url": uri}} for uri in images]
    result = completer("identify", [{"role": "user", "content": content}],
                       max_tokens=400, temperature=0.0)
    if result.degraded or not result.text:
        return Identification(degraded=True, reason=result.reason or "no reply")
    text = result.text
    start, end = text.find("{"), text.rfind("}")
    try:
        raw = _Raw.model_validate(json.loads(text[start:end + 1]))
    except (ValueError, ValidationError) as exc:
        return Identification(degraded=True, reason=f"unreadable model reply: {str(exc)[:120]}")
    return Identification(
        brand=(raw.brand or "").strip() or None,
        model=(raw.model or "").strip() or None,
        category=raw.category,
        item_name=(raw.item_name or "").strip() or None,
        age_range=(raw.age_range or "").strip() or None,
        visible_text=[t for t in raw.visible_text if isinstance(t, str)][:20],
        confidence=raw.confidence,
    )
