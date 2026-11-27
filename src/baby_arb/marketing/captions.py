"""Caption drafts for Instagram/Facebook and TikTok (ENGINE_SPEC Phase 1, step 4).

The house template (`template_captions`) always works and needs no model.
`draft_captions` asks the model (through llm.py, under the daily cap) for a
warmer version and accepts it only if it passes `validate_caption`:
- the first line has the price and the age range when known,
- the listing code and exactly the call to action "DM <code> to buy" appear,
- no shilling amount other than the admin's price (and reference price),
- hashtag counts follow the format rules (IG/FB 5 or fewer, TikTok 3 to 5).
Anything else falls back to the template, so the admin's price can never be
changed by a model.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from baby_arb.marketing.llm import LLMResult, complete

Platform = Literal["ig", "tiktok"]

BASE_TAGS = ["#babyreshopke", "#nairobimums", "#prelovedbaby"]
CONTENT_CTA = "Follow @babyreshopke for Thursday drops"

_AMOUNT = re.compile(r"(?:kes|ksh|kshs|sh)\.?\s*([\d,]+(?:\.\d+)?)\s*(k)?", re.IGNORECASE)


@dataclass(frozen=True)
class CaptionInput:
    """Listing fields a caption may use. Nothing else is invented."""

    code: str
    price: int | None
    title: str | None = None
    grade: str | None = None
    age_range: str | None = None
    notes: str | None = None
    ref_new_price: int | None = None
    seller: bool = False
    content_kind: str | None = None  # C-codes: teaser | tip | behind
    facts: tuple[str, ...] = ()  # looked-up details with a source, e.g. "Age range: 6m+"


@dataclass(frozen=True)
class Captions:
    """Captions plus where they came from and why a model draft was dropped."""

    ig: str
    tiktok: str
    source: Literal["model", "template"]
    notes: list[str] = field(default_factory=list)


def cta(code: str) -> str:
    """The one call to action for a listing."""
    return f"DM {code} to buy"


def _kes(amount: int) -> str:
    return f"KES {amount:,}"


def _first_line(item: CaptionInput) -> str:
    parts = [item.title or "Fresh find"]
    if item.price is not None:
        parts.append(_kes(item.price))
    if item.age_range:
        parts.append(item.age_range)
    return " · ".join(parts)


def template_captions(item: CaptionInput) -> Captions:
    """The deterministic house template."""
    if item.content_kind:
        headline = item.title or item.notes or "This week at babyReShop KE"
        body = [headline] + ([item.notes] if item.title and item.notes else [])
        tags = " ".join(BASE_TAGS)
        ig = "\n\n".join([*body, f"{CONTENT_CTA}\n{item.code}", tags])
        tiktok = f"{headline} | {item.code}\n{CONTENT_CTA}\n{tags}"
        return Captions(ig, tiktok, "template")

    lines = [_first_line(item)]
    detail = []
    if item.grade:
        detail.append(f"Condition: grade {item.grade}")
    if item.notes:
        detail.append(item.notes[0].upper() + item.notes[1:])
    if detail:
        lines.append(". ".join(detail) + ".")
    if item.facts:
        lines.append("\n".join(f"• {fact}" for fact in item.facts))
    if item.ref_new_price and not item.seller:
        lines.append(f"New in Nairobi from {_kes(item.ref_new_price)}.")
    if item.seller:
        lines.append("Seller listing: sold by a Nairobi parent, checked by us.")
    lines.append(f"Pickup or delivery in Nairobi. {cta(item.code)}.")
    ig = "\n\n".join(lines) + "\n\n" + " ".join(BASE_TAGS)
    price = f" {_kes(item.price)}" if item.price is not None else ""
    short_facts = " · ".join(f.split(": ", 1)[-1] for f in item.facts[:2])
    tiktok = (
        f"{item.title or 'Fresh find'}{price} | {item.code}\n"
        f"{lines[1] if len(lines) > 1 else ''}\n{short_facts}\n{cta(item.code)}\n"
        + " ".join(BASE_TAGS)
    ).replace("\n\n", "\n")
    return Captions(ig, tiktok, "template")


def _amounts(text: str) -> set[int]:
    found: set[int] = set()
    for match in _AMOUNT.finditer(text):
        number = float(match.group(1).replace(",", "") or 0)
        if match.group(2):
            number *= 1000
        found.add(int(number))
    return found


def validate_caption(text: str, item: CaptionInput, platform: Platform) -> list[str]:
    """Problems with a caption (empty when it is acceptable)."""
    problems: list[str] = []
    if not text.strip():
        return ["empty"]
    first = text.strip().splitlines()[0]
    if item.code not in text:
        problems.append("listing code missing")
    if item.content_kind is None:
        if item.price is not None and _kes(item.price) not in first:
            problems.append(f"first line must show {_kes(item.price)}")
        if platform == "ig" and item.age_range and item.age_range.lower() not in first.lower():
            problems.append(f"first line must show {item.age_range}")
        if text.count(cta(item.code)) != 1:
            problems.append(f"must contain '{cta(item.code)}' exactly once")
        allowed = {a for a in (item.price, item.ref_new_price) if a is not None}
        stray = _amounts(text) - allowed
        if stray:
            problems.append("contains a price the admin did not give: "
                            + ", ".join(_kes(a) for a in sorted(stray)))
    tags = re.findall(r"(?<!\w)#\w+", text)
    if platform == "ig" and len(tags) > 5:
        problems.append(f"{len(tags)} hashtags (5 or fewer on IG/FB)")
    if platform == "tiktok" and not 3 <= len(tags) <= 5:
        problems.append(f"{len(tags)} hashtags (3 to 5 on TikTok)")
    return problems


SYSTEM_PROMPT = """You write captions for babyReShop KE, a Nairobi shop for quality
pre-loved baby items. Voice: warm, practical, short sentences, no hype, no emojis
beyond one or two. Use only the facts given. Never mention a price other than the
ones given, never invent brand, model, size or condition details.

Return JSON only: {"ig": "...", "tiktok": "..."}.
ig (Instagram and Facebook): line 1 is "<item> · <price> · <age range>" exactly as
given; then 1-2 short lines on condition; then the product details as "• Label: value"
bullets, using only the details given, word for word; then the exact call to action;
then at most 5 hashtags. tiktok: line 1 is "<item> <price> | <code>"; one short line; the
exact call to action; 3 to 5 hashtags."""


def _user_prompt(item: CaptionInput, template: Captions) -> str:
    facts = {
        "item": item.title or "Fresh find",
        "price": _kes(item.price) if item.price is not None else None,
        "age_range": item.age_range,
        "grade": item.grade,
        "notes": item.notes,
        "new_in_nairobi_from": _kes(item.ref_new_price) if item.ref_new_price else None,
        "seller_listing": item.seller,
        "details_from_maker_pages": list(item.facts),
        "code": item.code,
        "call_to_action": cta(item.code),
    }
    return (
        "Facts:\n" + json.dumps(facts, ensure_ascii=False)
        + "\n\nHouse template to improve on:\n" + json.dumps(
            {"ig": template.ig, "tiktok": template.tiktok}, ensure_ascii=False)
    )


def _parse_json(text: str) -> dict[str, Any] | None:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


Completer = Callable[..., LLMResult]


def draft_captions(item: CaptionInput, completer: Completer = complete) -> Captions:
    """Model draft if it validates, otherwise the house template.

    Content posts (C-codes) always use the template in Phase 1.
    """
    template = template_captions(item)
    if item.content_kind or item.price is None:
        return template
    result = completer(
        "caption",
        [{"role": "system", "content": SYSTEM_PROMPT},
         {"role": "user", "content": _user_prompt(item, template)}],
        max_tokens=500,
        temperature=0.4,
    )
    if result.degraded or not result.text:
        return Captions(template.ig, template.tiktok, "template",
                        [f"model unavailable: {result.reason}"])
    data = _parse_json(result.text)
    if data is None or not isinstance(data.get("ig"), str) or not isinstance(
        data.get("tiktok"), str
    ):
        return Captions(template.ig, template.tiktok, "template", ["model reply was not JSON"])
    ig, tiktok = data["ig"].strip(), data["tiktok"].strip()
    problems = [f"ig: {p}" for p in validate_caption(ig, item, "ig")]
    problems += [f"tiktok: {p}" for p in validate_caption(tiktok, item, "tiktok")]
    if problems:
        return Captions(template.ig, template.tiktok, "template", problems)
    return Captions(ig, tiktok, "model")


def rewrite_caption(
    current: str,
    platform: Platform,
    instruction: str,
    item: CaptionInput,
    completer: Completer = complete,
) -> tuple[str, list[str]]:
    """Apply an admin's caption instruction through the model, validated.

    Returns:
        (caption, problems). On any problem the current caption is kept.
    """
    result = completer(
        "caption_rewrite",
        [{"role": "system", "content": SYSTEM_PROMPT.split("Return JSON")[0]
          + "Return only the rewritten caption text."},
         {"role": "user", "content": f"Caption:\n{current}\n\nChange: {instruction}\n\n"
          f"Keep line 1 facts, the code {item.code} and '{cta(item.code)}' unless the "
          "change says otherwise. Do not add prices."}],
        max_tokens=400,
        temperature=0.3,
    )
    if result.degraded or not result.text:
        return current, [f"model unavailable: {result.reason}"]
    text = result.text.strip().strip("`").strip()
    problems = validate_caption(text, item, platform)
    if problems:
        return current, problems
    return text, []


def strip_phrase(caption: str, phrase: str) -> str:
    """Remove a phrase from a caption (case-insensitive) and tidy spacing."""
    pattern = re.compile(r"[ ,]*\b" + re.escape(phrase) + r"\b[ ,]*", re.IGNORECASE)
    cleaned = pattern.sub(" ", caption)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" +([.,;:])", r"\1", cleaned)
    cleaned = re.sub(r"^\s*([.,;:])\s*", "", cleaned, flags=re.M)
    return "\n".join(line.strip() for line in cleaned.splitlines())
