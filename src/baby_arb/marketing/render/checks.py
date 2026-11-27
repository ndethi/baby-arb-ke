"""Creative checks as code (the deterministic half of `baby-creative-eval`).

The renderer measures every `data-el` element in the page (`MEASURE_JS`) and
`check_asset` turns those measurements into issues. Size problems are fixed
by the renderer before rendering (sizes are clamped); anything left is shown
on the preview so the admin can decide.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from baby_arb.marketing.render.layout import Rect

# 1080 px shown on a ~390 pt wide phone screen is a 0.36 scale; 32 px is
# about 11.5 pt at phone size, the smallest comfortable caption text.
MIN_TEXT_PX = 32
TEXT_ELEMENTS = ("price", "code", "condition", "cta", "anchor", "seller_tag", "details")

MEASURE_JS = """
() => Array.from(document.querySelectorAll('[data-el]')).map(el => {
  const r = el.getBoundingClientRect();
  const cs = getComputedStyle(el);
  return {
    el: el.dataset.el,
    text: (el.innerText || '').trim(),
    x: r.left, y: r.top, w: r.width, h: r.height,
    font_px: parseFloat(cs.fontSize),
    visible: cs.display !== 'none' && cs.visibility !== 'hidden' && parseFloat(cs.opacity) > 0.5,
  };
})
"""


@dataclass(frozen=True)
class Expectation:
    """What one asset must show."""

    width: int
    height: int
    code: str
    price_text: str | None  # None when this asset carries no price
    needs_cta: bool
    seller: bool
    safe_top: int = 0
    safe_bottom: int = 0  # distance from the bottom edge kept clear of text
    flaw_zones: tuple[Rect, ...] = ()
    photo_height: int | None = None


def _inside(m: dict[str, Any], exp: Expectation) -> bool:
    return bool(
        m["x"] >= 0
        and m["y"] >= 0
        and m["x"] + m["w"] <= exp.width + 0.5
        and m["y"] + m["h"] <= exp.height + 0.5
        and m["w"] > 0
        and m["h"] > 0
    )


def _overlap(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return not bool(
        a["x"] + a["w"] <= b["x"]
        or b["x"] + b["w"] <= a["x"]
        or a["y"] + a["h"] <= b["y"]
        or b["y"] + b["h"] <= a["y"]
    )


def check_asset(measures: list[dict[str, Any]], exp: Expectation) -> list[str]:
    """Return human-readable issues for one rendered asset (empty when clean)."""
    issues: list[str] = []
    texts = [m for m in measures if m["el"] in TEXT_ELEMENTS and m["visible"]]
    by_el: dict[str, list[dict[str, Any]]] = {}
    for m in texts:
        by_el.setdefault(m["el"], []).append(m)

    for m in texts:
        if m["font_px"] < MIN_TEXT_PX:
            issues.append(f"{m['el']} text is {m['font_px']:.0f}px, under {MIN_TEXT_PX}px")
        if not _inside(m, exp):
            issues.append(f"{m['el']} runs off the canvas")

    codes = by_el.get("code", [])
    if not codes or exp.code not in codes[0]["text"]:
        issues.append(f"code {exp.code} not visible")

    if exp.price_text is not None:
        prices = by_el.get("price", [])
        if not prices or exp.price_text not in prices[0]["text"]:
            issues.append(f"price {exp.price_text} not visible")

    ctas = by_el.get("cta", [])
    if exp.needs_cta and len(ctas) != 1:
        issues.append(f"needs exactly one call to action, found {len(ctas)}")
    if not exp.needs_cta and ctas:
        issues.append("this asset should not carry a call to action")

    if exp.seller and not by_el.get("seller_tag"):
        issues.append("seller listing tag missing")
    if not exp.seller and by_el.get("seller_tag"):
        issues.append("seller tag on an own-stock item")

    for m in texts:
        if m["el"] == "cta":
            continue
        if m["y"] < exp.safe_top or m["y"] + m["h"] > exp.height - exp.safe_bottom:
            issues.append(f"{m['el']} is outside the safe area")

    for i, a in enumerate(texts):
        for b in texts[i + 1:]:
            if _overlap(a, b):
                issues.append(f"{a['el']} overlaps {b['el']}")

    photo_h = exp.photo_height or exp.height
    for zone in exp.flaw_zones:
        box = {"x": zone.x * exp.width, "y": zone.y * photo_h,
               "w": zone.w * exp.width, "h": zone.h * photo_h}
        for m in texts:
            if _overlap(m, box):
                issues.append(f"{m['el']} covers a flagged flaw area")
    return issues
