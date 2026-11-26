"""The single gateway for every model call (ENGINE_SPEC section 10).

- Providers are OpenAI-compatible chat endpoints: OpenRouter's free Nemotron
  first (reasoning off unless LLM_REASONING=true), NVIDIA's hosted API as the
  fallback. An empty completion counts as an error.
- Before each call the daily cap is checked: total cost against
  LLM_DAILY_CAP_USD and call count against LLM_DAILY_CALL_CAP, per Nairobi
  calendar day. Over the cap no call is made.
- Every attempt is written to `llm_calls` (ok, error or capped).
- Never raises for provider problems: callers get `degraded=True` and must
  fall back to asking the admin or a fixed template.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import structlog
from sqlalchemy import func
from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from baby_arb.config import Settings, get_settings
from baby_arb.posting.tables import LlmCall, utcnow
from baby_arb.storage.db import get_engine

logger = structlog.get_logger()

NAIROBI = ZoneInfo("Africa/Nairobi")

PROVIDERS: dict[str, str] = {
    "nvidia": "https://integrate.api.nvidia.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}

TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True)
class LLMResult:
    """Outcome of a model call."""

    text: str | None
    degraded: bool
    reason: str | None = None
    provider: str | None = None
    model: str | None = None


def _api_key(settings: Settings, provider: str) -> str | None:
    if provider == "nvidia":
        return settings.nvidia_api_key
    if provider == "openrouter":
        return settings.openrouter_api_key
    return None


def _nairobi_day_start_utc(now: datetime) -> datetime:
    """UTC instant of the most recent Nairobi midnight (all stored times are UTC)."""
    local = now.astimezone(NAIROBI)
    start_local = datetime.combine(local.date(), time.min, tzinfo=NAIROBI)
    return start_local.astimezone(UTC)


def usage_today(session: Session, now: datetime) -> tuple[Decimal, int]:
    """Return (cost_usd, call_count) of non-capped calls since Nairobi midnight."""
    start = _nairobi_day_start_utc(now)
    end = start + timedelta(days=1)
    row = session.exec(
        select(func.coalesce(func.sum(LlmCall.cost_usd), 0), func.count(col(LlmCall.id))).where(
            LlmCall.at >= start, LlmCall.at < end, LlmCall.status != "capped"
        )
    ).one()
    return Decimal(str(row[0])), int(row[1])


def _cost(settings: Settings, tokens_in: int, tokens_out: int) -> Decimal:
    million = Decimal(1_000_000)
    return (
        Decimal(tokens_in) * settings.llm_price_in_per_mtok
        + Decimal(tokens_out) * settings.llm_price_out_per_mtok
    ) / million


def _log(session: Session, **fields: Any) -> None:
    session.add(LlmCall(**fields))
    session.commit()


def complete(
    purpose: str,
    messages: Sequence[dict[str, Any]],
    *,
    max_tokens: int = 600,
    temperature: float = 0.2,
    settings: Settings | None = None,
    engine: Engine | None = None,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> LLMResult:
    """Run one chat completion through the configured providers.

    Args:
        purpose: Short label logged with the call (e.g. "caption", "edit_parse").
        messages: OpenAI-style chat messages.
        max_tokens: Completion token limit.
        temperature: Sampling temperature.
        settings: Override settings (tests).
        engine: Override database engine (tests).
        client: Override HTTP client (tests).
        now: Override the current time (tests).

    Returns:
        LLMResult with text, or degraded=True and a reason. Never raises for
        cap, configuration or provider errors.
    """
    settings = settings or get_settings()
    now = now or utcnow()
    attempts = [(settings.llm_provider, settings.llm_model)]
    if settings.llm_fallback_provider and settings.llm_fallback_model:
        attempts.append((settings.llm_fallback_provider, settings.llm_fallback_model))

    with Session(engine or get_engine()) as session:
        spent, calls = usage_today(session, now)
        if spent >= settings.llm_daily_cap_usd or calls >= settings.llm_daily_call_cap:
            reason = f"daily cap reached ({calls} calls, ${spent:.4f})"
            _log(session, purpose=purpose, provider=attempts[0][0], model=attempts[0][1],
                 status="capped", error=reason, at=now)
            logger.info("LLM capped", purpose=purpose, reason=reason)
            return LLMResult(None, True, reason)

        errors: list[str] = []
        owns_client = client is None
        http = client or httpx.Client(timeout=TIMEOUT_SECONDS)
        try:
            for provider, model in attempts:
                key = _api_key(settings, provider)
                base = PROVIDERS.get(provider)
                if not key or not base:
                    errors.append(f"{provider}: not configured")
                    continue
                payload: dict[str, Any] = {
                    "model": model,
                    "messages": list(messages),
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                }
                if provider == "openrouter":
                    # Nemotron "thinks" by default and can spend the whole budget on it.
                    payload["reasoning"] = {"enabled": settings.llm_reasoning}
                try:
                    resp = http.post(
                        f"{base}/chat/completions",
                        headers={"Authorization": f"Bearer {key}"},
                        json=payload,
                    )
                    resp.raise_for_status()
                    body = resp.json()
                    text = body["choices"][0]["message"]["content"]
                    usage = body.get("usage") or {}
                    tokens_in = int(usage.get("prompt_tokens", 0))
                    tokens_out = int(usage.get("completion_tokens", 0))
                    if not isinstance(text, str) or not text.strip():
                        raise ValueError("empty completion (token budget spent or no content)")
                except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
                    message = f"{type(exc).__name__}: {str(exc)[:200]}"
                    errors.append(f"{provider}: {message}")
                    _log(session, purpose=purpose, provider=provider, model=model,
                         status="error", error=message, at=now)
                    continue
                _log(session, purpose=purpose, provider=provider, model=model, status="ok",
                     tokens_in=tokens_in, tokens_out=tokens_out,
                     cost_usd=_cost(settings, tokens_in, tokens_out), at=now)
                return LLMResult(text.strip(), False, None, provider, model)
        finally:
            if owns_client:
                http.close()

    reason = "; ".join(errors) or "no provider configured"
    logger.warning("LLM degraded", purpose=purpose, reason=reason)
    return LLMResult(None, True, reason)
