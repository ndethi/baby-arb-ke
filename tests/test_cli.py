"""Smoke tests for CLI commands. Verifies the main paths run without error."""

from __future__ import annotations

from typer.testing import CliRunner

from baby_arb.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "baby-arb-ke" in result.stdout


def test_health():
    result = runner.invoke(app, ["health"])
    assert result.exit_code == 0


def test_price_smoke_default():
    result = runner.invoke(app, ["price", "smoke"])
    assert result.exit_code == 0
    # default carseat from TX → DE smoke is dim-dominated; verdict will be SKIP
    assert "SKIP" in result.stdout or "REVIEW" in result.stdout or "BUY" in result.stdout


def test_compliance_smoke_default():
    result = runner.invoke(app, ["compliance", "smoke"])
    assert result.exit_code == 0


def test_compliance_smoke_safety_block():
    result = runner.invoke(
        app,
        [
            "compliance", "smoke",
            "--brand", "Fisher-Price",
            "--model", "Rock 'n Play Sleeper",
            "--condition-text", "Used Rock 'n Play",
        ],
    )
    assert result.exit_code == 0
    assert "BLOCK" in result.stdout


def test_demand_score():
    result = runner.invoke(
        app,
        [
            "demand", "score", "TestProduct",
            "--jiji-active", "2",
            "--jiji-sold-30d", "14",
            "--fb-mentions", "23",
            "--fb-intent", "0.75",
        ],
    )
    assert result.exit_code == 0
    assert "demand_score" in result.stdout
