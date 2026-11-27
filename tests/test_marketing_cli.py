"""`baby-arb mkt ...` commands end to end on a temp database (fake renderer, no model)."""

from __future__ import annotations

import pytest
from baby_arb.cli import app
from baby_arb.config import get_settings
from baby_arb.storage.db import get_engine
from PIL import Image
from typer.testing import CliRunner

from tests.test_marketing_pipeline import fake_renderer

runner = CliRunner()


@pytest.fixture
def env(tmp_path, monkeypatch, db_url):
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("MARKETING_ASSETS_DIR", str(tmp_path / "assets"))
    monkeypatch.setenv("TELEGRAM_OPS_CHAT_ID", "-1001")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("NVIDIA_API_KEY", "")
    get_settings.cache_clear()
    get_engine.cache_clear()
    monkeypatch.setattr("baby_arb.marketing.render.static.render_listing",
                        lambda view, photos, layout, out, **_kw: fake_renderer(
                            view, photos, layout, out))
    album = tmp_path / "album"
    album.mkdir()
    for i in range(2):
        Image.new("RGB", (40, 50), (i * 90, 100, 120)).save(album / f"{i}.jpg")
    yield album
    get_settings.cache_clear()
    get_engine.cache_clear()


def _ok(args):
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.stdout
    return result.stdout


def test_cli_drop_to_approved(env):
    out = _ok(["mkt", "intake", "--album", str(env), "--line", "2000 B 0-36m washed"])
    assert "Needs title" in out
    out = _ok(["mkt", "answer", "P-0001", "title", "Graco Modes stroller"])
    assert "Needs override" in out
    out = _ok(["mkt", "override", "P-0001"])
    assert "P-0001 round 1" in out and "DM P-0001 to buy" in out
    out = _ok(["mkt", "edit", "P-0001", "--text", "price bigger"])
    assert "applied: make price badge larger" in out
    out = _ok(["mkt", "approve", "P-0001"])
    assert "approved and queued" in out
    out = _ok(["mkt", "cal", "week"])
    assert "This week's slots" in out
    _ok(["mkt", "cal", "posted", "P-0001"])


def test_cli_block_exits_cleanly_and_approve_refuses(env):
    _ok(["mkt", "intake", "--album", str(env), "--line", "3000"])
    out = _ok(["mkt", "answer", "P-0001", "title", "Chicco car seat"])
    assert "BLOCKED P-0001" in out
    result = runner.invoke(app, ["mkt", "approve", "P-0001"])
    assert result.exit_code == 1 and "only a preview can be approved" in result.stdout


def test_cli_tick_dry_run_silent_when_idle(env):
    result = runner.invoke(app, ["mkt", "cal", "tick", "--dry-run"])
    assert result.exit_code == 0


def test_cli_cal_next(env):
    assert "Slot:" in _ok(["mkt", "cal", "next", "drop"])
