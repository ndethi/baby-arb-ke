"""Rendering: creative checks (pure) and real renders with golden images.

Real renders need a browser (Playwright's Chromium or Google Chrome); they are
skipped when none is available. Golden images are per platform because font
rasterising differs: tests/golden/<sys.platform>/. Missing goldens are skipped;
run with UPDATE_GOLDEN=1 to write them, then review the PNGs before committing.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from baby_arb.marketing.render.checks import MIN_TEXT_PX, Expectation, check_asset
from baby_arb.marketing.render.layout import Layout, Rect
from baby_arb.marketing.render.static import (
    ListingView,
    RenderError,
    open_browser,
    px_for,
    render_listing,
)
from PIL import Image, ImageChops, ImageDraw, ImageStat

GOLDEN_DIR = Path(__file__).parent / "golden" / sys.platform
TOLERANCE = 3.0  # mean absolute difference per channel, 0-255


def _m(el, x, y, w, h, text="", font=48, visible=True):
    return {"el": el, "x": x, "y": y, "w": w, "h": h, "text": text, "font_px": font,
            "visible": visible}


EXP = Expectation(width=1080, height=1350, code="P-0007", price_text="KES 2,000",
                  needs_cta=True, seller=False, safe_top=48, safe_bottom=190)
CLEAN = [
    _m("code", 800, 48, 200, 70, "P-0007"),
    _m("price", 48, 1000, 500, 150, "KES 2,000", 96),
    _m("cta", 0, 1210, 1080, 140, "DM P-0007 to buy", 52),
]


def test_clean_measurements_pass():
    assert check_asset(CLEAN, EXP) == []


def test_small_text_flagged():
    bad = [*CLEAN[:2], _m("cta", 0, 1210, 1080, 140, "DM P-0007 to buy", 20)]
    assert any("under" in i for i in check_asset(bad, EXP))


def test_missing_price_code_cta_flagged():
    issues = check_asset([], EXP)
    assert "code P-0007 not visible" in issues
    assert "price KES 2,000 not visible" in issues
    assert any("exactly one call to action" in i for i in issues)


def test_two_ctas_flagged():
    issues = check_asset([*CLEAN, _m("cta", 0, 0, 10, 10, "DM", 40)], EXP)
    assert any("found 2" in i for i in issues)


def test_overlap_and_off_canvas_flagged():
    issues = check_asset([*CLEAN, _m("condition", 790, 60, 100, 50, "Grade B")], EXP)
    assert any("overlaps" in i for i in issues)
    issues = check_asset([*CLEAN[1:], _m("code", 1000, 48, 200, 70, "P-0007")], EXP)
    assert any("off the canvas" in i for i in issues)


def test_seller_tag_rules():
    seller = Expectation(**{**EXP.__dict__, "seller": True})
    assert "seller listing tag missing" in check_asset(CLEAN, seller)
    assert "seller tag on an own-stock item" in check_asset(
        [*CLEAN, _m("seller_tag", 48, 150, 300, 60, "Seller listing")], EXP)


def test_flaw_zone_flagged():
    exp = Expectation(**{**EXP.__dict__, "flaw_zones": (Rect(x=0.0, y=0.7, w=0.5, h=0.2),)})
    assert any("flaw" in i for i in check_asset(CLEAN, exp))


def test_sizes_are_clamped_to_minimum():
    assert px_for("anchor", -2) >= MIN_TEXT_PX
    assert px_for("price", 3) > px_for("price", 0)
    assert px_for("price", 99) == px_for("price", 3)


# --------------------------------------------------------------------------- real renders

def _photos(folder: Path) -> dict[int, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    out = {}
    for n, colour in enumerate([(180, 200, 220), (220, 190, 170), (200, 220, 180)], start=1):
        im = Image.new("RGB", (1200, 1600), colour)
        d = ImageDraw.Draw(im)
        d.rectangle([300, 400, 900, 1300], fill=(90, 110, 130))
        d.ellipse([350, 1150, 550, 1350], fill=(40, 40, 40))
        path = folder / f"{n:02d}.jpg"
        im.save(path, quality=95)
        out[n] = path
    return out


@pytest.fixture(scope="module")
def browser():
    try:
        with open_browser() as b:
            yield b
    except RenderError as exc:
        pytest.skip(f"no browser: {exc}")


def _render(browser, tmp_path, view, layout=None):
    photos = _photos(tmp_path / "photos")
    return render_listing(view, photos, layout or Layout(photo_order=[1, 2, 3]),
                          tmp_path / "out", browser=browser)


OWN = ListingView("P-0007", 2000, "B", "0-36m", ref_new_price=8500)
SELLER = ListingView("L-0003", 4500, "A", None, seller=True)


def test_render_sizes_and_clean_checks(browser, tmp_path):
    result = _render(browser, tmp_path, OWN)
    assert result.all_issues == []
    assert Image.open(result.paths["feed"]).size == (1080, 1350)
    assert Image.open(result.paths["story"]).size == (1080, 1920)
    assert [k for k in result.paths if k.startswith("tiktok")] == ["tiktok_1", "tiktok_2",
                                                                   "tiktok_3"]
    assert Image.open(result.paths["tiktok_2"]).size == (1080, 1920)


def test_seller_render_clean(browser, tmp_path):
    assert _render(browser, tmp_path, SELLER).all_issues == []


def test_hidden_cta_is_reported(browser, tmp_path):
    layout = Layout(photo_order=[1, 2, 3], toggles={"cta": False})
    result = _render(browser, tmp_path, OWN, layout)
    assert any("call to action" in i for i in result.issues["feed"])


def test_missing_photo_raises(browser, tmp_path):
    with pytest.raises(RenderError):
        render_listing(OWN, {1: tmp_path / "nope.jpg"}, Layout(photo_order=[1]),
                       tmp_path / "out", browser=browser)


def _diff(a: Path, b: Path) -> float:
    with Image.open(a) as ia, Image.open(b) as ib:
        if ia.size != ib.size:
            return 255.0
        diff = ImageChops.difference(ia.convert("RGB"), ib.convert("RGB"))
        return sum(ImageStat.Stat(diff).mean) / 3


@pytest.mark.parametrize(("name", "view"), [("own", OWN), ("seller", SELLER)])
@pytest.mark.parametrize("asset", ["feed", "story", "tiktok_1"])
def test_golden_images(browser, tmp_path, name, view, asset):
    result = _render(browser, tmp_path, view)
    golden = GOLDEN_DIR / f"{name}_{asset}.png"
    if os.environ.get("UPDATE_GOLDEN") == "1":
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_bytes(result.paths[asset].read_bytes())
    if not golden.exists():
        pytest.skip(f"no golden for {sys.platform}; run with UPDATE_GOLDEN=1 and review")
    assert _diff(result.paths[asset], golden) <= TOLERANCE


CHIPS = ListingView("P-0008", 2000, "B", "6m+", ref_new_price=8500,
                    chips=("45x42x34 cm", "2x AA, not included", "Piano keys"))


def test_details_strip_renders_clean(browser, tmp_path):
    result = _render(browser, tmp_path, CHIPS)
    assert result.all_issues == []
    html = (tmp_path / "out" / "_html" / "feed.html").read_text()
    assert 'data-el="details"' in html and "Piano keys" in html
    tiktok_1 = (tmp_path / "out" / "_html" / "tiktok_1.html").read_text()
    tiktok_2 = (tmp_path / "out" / "_html" / "tiktok_2.html").read_text()
    assert "Piano keys" not in tiktok_1 and "Piano keys" in tiktok_2


def test_details_strip_can_be_hidden_and_drops_long_chips(browser, tmp_path):
    view = ListingView("P-0009", 2000, chips=("x" * 40, "Piano keys"))
    result = _render(browser, tmp_path, view, Layout(photo_order=[1, 2, 3],
                                                      toggles={"details": False}))
    html = (tmp_path / "out" / "_html" / "feed.html").read_text()
    assert 'data-el="details"' not in html and result.all_issues == []
    result = _render(browser, tmp_path, view)
    html = (tmp_path / "out" / "_html" / "feed.html").read_text()
    assert "x" * 40 not in html and "Piano keys" in html
