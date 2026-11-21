"""marketing/llm.py: providers, fallback, daily cap and logging. No real network."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import httpx
import respx
from baby_arb.config import Settings
from baby_arb.marketing.llm import PROVIDERS, complete
from baby_arb.posting.tables import LlmCall
from sqlmodel import Session, select

NOW = datetime(2026, 11, 21, 9, 0, tzinfo=UTC)  # 12:00 Nairobi
MSGS = [{"role": "user", "content": "hi"}]


def _settings(**overrides):
    base = dict(
        nvidia_api_key="test-nv",
        openrouter_api_key="test-or",
        llm_daily_call_cap=3,
        llm_daily_cap_usd=Decimal("1"),
        _env_file=None,
    )
    base.update(overrides)
    return Settings(**base)


def _ok(text="ready", tin=10, tout=2):
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": text}}],
              "usage": {"prompt_tokens": tin, "completion_tokens": tout}},
    )


def _rows(engine):
    with Session(engine) as s:
        return list(s.exec(select(LlmCall)))


@respx.mock
def test_primary_success_is_logged(db_engine):
    respx.post(f"{PROVIDERS['nvidia']}/chat/completions").mock(return_value=_ok())
    result = complete("test", MSGS, settings=_settings(), engine=db_engine, now=NOW)
    assert not result.degraded
    assert result.text == "ready"
    assert result.provider == "nvidia"
    [row] = _rows(db_engine)
    assert (row.status, row.tokens_in, row.tokens_out) == ("ok", 10, 2)


@respx.mock
def test_falls_back_to_openrouter_on_error(db_engine):
    respx.post(f"{PROVIDERS['nvidia']}/chat/completions").mock(return_value=httpx.Response(503))
    respx.post(f"{PROVIDERS['openrouter']}/chat/completions").mock(return_value=_ok("ok2"))
    result = complete("test", MSGS, settings=_settings(), engine=db_engine, now=NOW)
    assert result.text == "ok2"
    assert result.provider == "openrouter"
    assert [r.status for r in _rows(db_engine)] == ["error", "ok"]


@respx.mock
def test_all_providers_down_degrades_without_raising(db_engine):
    respx.post(f"{PROVIDERS['nvidia']}/chat/completions").mock(side_effect=httpx.ConnectError("x"))
    respx.post(f"{PROVIDERS['openrouter']}/chat/completions").mock(return_value=httpx.Response(429))
    result = complete("test", MSGS, settings=_settings(), engine=db_engine, now=NOW)
    assert result.degraded
    assert result.text is None
    assert "nvidia" in (result.reason or "") and "openrouter" in (result.reason or "")


@respx.mock
def test_call_cap_blocks_further_calls(db_engine):
    route = respx.post(f"{PROVIDERS['nvidia']}/chat/completions").mock(return_value=_ok())
    for _ in range(3):
        assert not complete("t", MSGS, settings=_settings(), engine=db_engine, now=NOW).degraded
    capped = complete("t", MSGS, settings=_settings(), engine=db_engine, now=NOW)
    assert capped.degraded
    assert "daily cap" in (capped.reason or "")
    assert route.call_count == 3
    assert _rows(db_engine)[-1].status == "capped"


@respx.mock
def test_cost_cap_blocks_paid_models(db_engine):
    respx.post(f"{PROVIDERS['nvidia']}/chat/completions").mock(
        return_value=_ok(tin=1_000_000, tout=0)
    )
    paid = _settings(llm_price_in_per_mtok=Decimal("2"), llm_daily_call_cap=100)
    assert not complete("t", MSGS, settings=paid, engine=db_engine, now=NOW).degraded
    assert complete("t", MSGS, settings=paid, engine=db_engine, now=NOW).degraded


@respx.mock
def test_cap_resets_at_nairobi_midnight(db_engine):
    respx.post(f"{PROVIDERS['nvidia']}/chat/completions").mock(return_value=_ok())
    late = datetime(2026, 11, 21, 20, 30, tzinfo=UTC)  # 23:30 Nairobi
    for _ in range(3):
        complete("t", MSGS, settings=_settings(), engine=db_engine, now=late)
    assert complete("t", MSGS, settings=_settings(), engine=db_engine, now=late).degraded
    next_day = datetime(2026, 11, 21, 21, 30, tzinfo=UTC)  # 00:30 Nairobi, next day
    assert not complete("t", MSGS, settings=_settings(), engine=db_engine, now=next_day).degraded


def test_missing_keys_degrade_without_network(db_engine):
    result = complete(
        "t", MSGS, settings=_settings(nvidia_api_key=None, openrouter_api_key=None),
        engine=db_engine, now=NOW,
    )
    assert result.degraded
    assert "not configured" in (result.reason or "")
