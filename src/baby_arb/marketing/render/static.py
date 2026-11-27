"""Render listing graphics: Jinja2 HTML templates -> PNG with Playwright.

Assets per round (ENGINE_SPEC Phase 1, Render):
- feed_4x5.png   1080x1350: hero photo, price, code, condition, CTA strip,
  "Seller listing" tag on L-codes.
- story_9x16.png 1080x1920: same elements inside story-safe margins.
- tiktok/NN.png  1080x1920: one frame per photo; price and code on the first.

Real photos only: the template frames the photo and never alters it. The
"new in Nairobi from KES X" anchor appears only when the admin gave a
reference price. Deterministic: no model calls.

The browser is Playwright's bundled Chromium when installed, else the
system Google Chrome (`channel="chrome"`), which GitHub's Ubuntu runners
and this Mac both have.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import Browser, Page, sync_playwright
from playwright.sync_api import Error as PlaywrightError

from baby_arb.marketing.render.checks import MEASURE_JS, MIN_TEXT_PX, Expectation, check_asset
from baby_arb.marketing.render.layout import (
    MAX_STEP,
    MIN_STEP,
    TEMPLATE_VERSION,
    Focus,
    Layout,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
TEMPLATES_DIR = REPO_ROOT / "assets" / "templates"

BASE_PX: dict[str, int] = {
    "price": 96, "code": 44, "condition": 44, "cta": 52, "anchor": 38, "seller_tag": 40,
}
STEP = 0.15

FOCUS_CSS: dict[str, str] = {
    "center": "50% 50%", "top": "50% 15%", "bottom": "50% 85%",
    "left": "15% 50%", "right": "85% 50%",
}


@dataclass(frozen=True)
class Format:
    """Canvas and safe-area geometry for one asset type."""

    name: str
    width: int
    height: int
    margin_x: int
    safe_top: int
    safe_bottom: int
    cta_height: int = 0
    cta_bottom: int = 0


FEED = Format("feed", 1080, 1350, 48, 48, 190, cta_height=140)
STORY = Format("story", 1080, 1920, 64, 270, 520, cta_height=140, cta_bottom=300)
TIKTOK = Format("tiktok", 1080, 1920, 64, 180, 480)


@dataclass(frozen=True)
class ListingView:
    """The listing fields a render needs (no database objects)."""

    code: str
    price: int | None
    grade: str | None = None
    age_range: str | None = None
    ref_new_price: int | None = None
    seller: bool = False
    content: bool = False  # C-code: no price, no buy CTA


@dataclass
class RenderResult:
    """Paths and remaining issues per asset name."""

    paths: dict[str, Path] = field(default_factory=dict)
    issues: dict[str, list[str]] = field(default_factory=dict)

    @property
    def all_issues(self) -> list[str]:
        """Issues across assets, prefixed by asset name."""
        return [f"{name}: {msg}" for name, msgs in self.issues.items() for msg in msgs]


class RenderError(RuntimeError):
    """Rendering could not run (no browser, missing photo)."""


def kes(amount: int) -> str:
    """Format whole shillings: 2000 -> "KES 2,000"."""
    return f"KES {amount:,}"


def px_for(element: str, step: int) -> int:
    """Pixel size for an element at a size step, never under MIN_TEXT_PX."""
    step = max(MIN_STEP, min(MAX_STEP, step))
    return max(MIN_TEXT_PX, round(BASE_PX[element] * (1 + STEP * step)))


def _condition_text(view: ListingView) -> str | None:
    parts = []
    if view.grade:
        parts.append(f"Grade {view.grade}")
    if view.age_range:
        parts.append(view.age_range)
    return " · ".join(parts) or None


def _anchor_style(layout: Layout, price_px: int) -> str:
    pos = layout.position("price")
    vertical, horizontal = pos.split("-")
    offset = round(price_px * 1.61) + 16  # badge: 1.05 line + 2 x 0.28em padding
    return f"{horizontal}: 0; {vertical}: {offset}px;"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )


def build_context(
    view: ListingView, layout: Layout, fmt: Format, photo: Path, focus: Focus, first: bool
) -> dict[str, Any]:
    """Template variables for one asset."""
    px = {el: px_for(el, layout.step(el)) for el in BASE_PX}
    show_price = view.price is not None and not view.content and (fmt.name != "tiktok" or first)
    needs_cta = fmt.name in {"feed", "story"} and not view.content
    seller_tag_top = 0
    if layout.shown("condition") and layout.position("condition") == "top-left":
        seller_tag_top = round(px["condition"] * 1.61) + 14
    return {
        "template": layout.template,
        "template_version": TEMPLATE_VERSION,
        "width": fmt.width,
        "height": fmt.height,
        "photo_height": fmt.height,
        "margin_x": fmt.margin_x,
        "safe_top": fmt.safe_top,
        "safe_bottom": fmt.safe_bottom,
        "cta_height": fmt.cta_height,
        "cta_bottom": fmt.cta_bottom,
        "hero_src": photo.resolve().as_uri(),
        "focus": FOCUS_CSS[focus],
        "px": px,
        "pos": {el: layout.position(el) for el in ("price", "code", "condition")},
        "show": {el: layout.shown(el) for el in ("condition", "cta", "anchor")},
        "code": view.code,
        "price_text": kes(view.price) if show_price and view.price is not None else None,
        "condition_text": _condition_text(view) if (fmt.name != "tiktok" or first) else None,
        "anchor_text": (
            f"New in Nairobi from {kes(view.ref_new_price)}"
            if view.ref_new_price and not view.seller and show_price
            else None
        ),
        "anchor_style": _anchor_style(layout, px["price"]),
        "seller": view.seller,
        "seller_tag_top": seller_tag_top,
        "cta_text": f"DM {view.code} to buy" if needs_cta else None,
    }


@contextmanager
def open_browser(channel: str | None = None) -> Iterator[Browser]:
    """Launch headless Chromium, falling back to the system Chrome.

    Raises:
        RenderError: no usable browser.
    """
    with sync_playwright() as p:
        errors: list[str] = []
        attempts: list[dict[str, Any]] = (
            [{"channel": channel}] if channel else [{}, {"channel": "chrome"}]
        )
        for kwargs in attempts:
            try:
                browser = p.chromium.launch(**kwargs)
            except PlaywrightError as exc:
                errors.append(str(exc).splitlines()[0])
                continue
            try:
                yield browser
            finally:
                browser.close()
            return
        raise RenderError("no browser for rendering: " + " | ".join(errors))


def _render_one(
    page: Page, html: str, html_path: Path, out: Path, exp: Expectation
) -> list[str]:
    html_path.write_text(html, encoding="utf-8")
    page.set_viewport_size({"width": exp.width, "height": exp.height})
    page.goto(html_path.resolve().as_uri())
    page.wait_for_load_state("load")
    measures: list[dict[str, Any]] = page.evaluate(MEASURE_JS)
    out.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out), full_page=False)
    return check_asset(measures, exp)


def render_listing(
    view: ListingView,
    photos: dict[int, Path],
    layout: Layout,
    out_dir: Path,
    *,
    browser: Browser | None = None,
    channel: str | None = None,
) -> RenderResult:
    """Render feed, story and TikTok frames for one round into `out_dir`.

    Args:
        view: Listing fields.
        photos: Photo number -> local file.
        layout: Render state (order, sizes, positions, toggles, crops).
        out_dir: Round directory, e.g. assets/ready/P-0007/r1.
        browser: Reuse an open browser (tests); otherwise one is launched.
        channel: Force a browser channel.

    Raises:
        RenderError: a photo is missing or no browser is available.
    """
    order = [n for n in layout.photo_order if n in photos] or sorted(photos)
    if not order:
        raise RenderError(f"{view.code}: no photos to render")
    for n in order:
        if not photos[n].is_file():
            raise RenderError(f"{view.code}: photo {n} missing at {photos[n]}")

    if browser is None:
        with open_browser(channel) as owned:
            return render_listing(view, photos, layout, out_dir, browser=owned)

    env = _env()
    template = env.get_template("listing.html.j2")
    result = RenderResult()
    work = out_dir / "_html"
    work.mkdir(parents=True, exist_ok=True)
    page = browser.new_page(device_scale_factor=1)
    try:
        jobs: list[tuple[str, Format, int, bool, Path]] = [
            ("feed", FEED, order[0], True, out_dir / "feed_4x5.png"),
            ("story", STORY, order[0], True, out_dir / "story_9x16.png"),
        ]
        for i, n in enumerate(order, start=1):
            jobs.append((f"tiktok_{i}", TIKTOK, n, i == 1, out_dir / "tiktok" / f"{i:02d}.png"))
        for name, fmt, n, first, out in jobs:
            ctx = build_context(view, layout, fmt, photos[n], layout.crops.get(n, "center"), first)
            exp = Expectation(
                width=fmt.width,
                height=fmt.height,
                code=view.code,
                price_text=ctx["price_text"],
                needs_cta=fmt.name in {"feed", "story"} and not view.content,
                seller=view.seller,
                safe_top=fmt.safe_top,
                safe_bottom=fmt.safe_bottom,
                flaw_zones=tuple(layout.flaw_zones) if n == order[0] else (),
            )
            html = template.render(**ctx)
            result.issues[name] = _render_one(page, html, work / f"{name}.html", out, exp)
            result.paths[name] = out
    finally:
        page.close()
    return result
