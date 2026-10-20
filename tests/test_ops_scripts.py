"""Ops scripts run by Hermes cron must not emit demo values (Phase 0 exit criterion)."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "sourcing"))

import aggregator_top5  # noqa: E402
import collect_multi_source  # noqa: E402
import demand_check_job  # noqa: E402
import generate_weekly_ideas  # noqa: E402
import priority_item_sourcer  # noqa: E402


async def test_demand_report_says_no_live_data_and_has_no_scores():
    results = await demand_check_job.check_demand_for_products()
    message = demand_check_job.format_telegram_message(results)
    assert "No live demand data" in message
    assert "Score:" not in message
    assert "demo" not in message.lower()


async def test_multi_source_reports_unknown_not_defaults():
    result = await collect_multi_source.collect_multi_source_demand()
    agg = result["aggregated_signals"]
    assert agg["confidence"] == "UNKNOWN"
    assert agg["sentiment_score"] is None
    assert all(p["score"] is None for p in result["products"])
    assert all(s["status"] == "unknown" for s in result["sources"].values())


def test_aggregator_abstains_without_ke_price(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tracker = tmp_path / "data" / "tracker"
    tracker.mkdir(parents=True)
    (tracker / "pump_tracker.csv").write_text(
        "timestamp,model,price_usd,source,link,tier,demand_score\n"
        "2026-10-01,Spectra S2,60.00,ebay,https://example.test/1,light,40\n"
    )
    ranked, abstained = aggregator_top5.process_items()
    assert ranked == []
    assert [a["model"] for a in abstained] == ["Spectra S2"]


def test_priority_sourcer_returns_no_mock_listings():
    assert priority_item_sourcer.search_ebay_for_item("Medela Pump in Style") == []


def test_weekly_ideas_reports_missing_category_as_unknown():
    score, confidence = generate_weekly_ideas.get_category_score([], "stroller")
    assert score is None
    assert confidence == "UNKNOWN"
    block = generate_weekly_ideas.generate_ideas_for_category("stroller", score, confidence)
    assert "UNKNOWN" in block
