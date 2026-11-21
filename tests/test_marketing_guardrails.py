"""Phase 0-2 guardrails: no publishing or Meta calls exist in the marketing code."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent / "src" / "baby_arb"
PACKAGES = ["marketing", "posting"]
FORBIDDEN = re.compile(
    r"graph\.facebook\.com|graph\.instagram\.com|facebook\.com/v\d|open-api\.tiktok\.com",
    re.IGNORECASE,
)


@pytest.mark.parametrize("package", PACKAGES)
def test_no_meta_or_tiktok_endpoints(package):
    offenders = [
        str(p.relative_to(SRC))
        for p in (SRC / package).rglob("*.py")
        if FORBIDDEN.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == [], f"publishing endpoints found before Phase 3: {offenders}"


def test_no_publish_package_yet():
    assert not (SRC / "marketing" / "publish").exists()
