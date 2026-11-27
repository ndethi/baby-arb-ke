"""Turn pipeline results into Telegram messages (no Telegram objects here).

Button callback data is `a:<action>:<code>`; the handlers check the sender
against the admin allow-list before acting on any of them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from baby_arb.marketing.pipeline import Blocked, Need, Preview, Question, Step

ALBUM_LIMIT = 10
Buttons = list[list[tuple[str, str]]]


@dataclass(frozen=True)
class Text:
    """A text message, optionally with inline buttons."""

    text: str
    buttons: Buttons = field(default_factory=list)


@dataclass(frozen=True)
class Album:
    """Up to 10 images sent as one album."""

    paths: list[Path]
    caption: str | None = None


Out = Text | Album


def preview_buttons(code: str, needs_check: bool = False,
                    price_ref: int | None = None) -> Buttons:
    """✅ Approve ✏️ Edit ❌ Reject / ⏩ Now 🕒 Move ⏭ Skip.

    With open safety review reasons the approve label says the admin checked it.
    """
    approve = "✅ Approve (checked)" if needs_check else "✅ Approve"
    return [
        [(approve, f"a:approve:{code}"), ("✏️ Edit", f"a:edit:{code}"),
         ("❌ Reject", f"a:reject:{code}")],
        [("⏩ Now", f"a:now:{code}"), ("🕒 Move", f"a:move:{code}"),
         ("⏭ Skip", f"a:skip:{code}")],
    ] + ([[(f"Use KES {price_ref:,} as 'new from'", f"a:useref:{code}")]] if price_ref else [])


def _card(p: Preview) -> str:
    test = "🧪 TEST · " if p.is_test else ""
    lines = [f"{test}{p.code} · preview round {p.round}"]
    if p.echo:
        lines.append("Applied: " + "; ".join(p.echo))
    lines.append(p.slot_line)
    for line in p.info:
        lines.append(f"\N{INFORMATION SOURCE}\ufe0f {line}")
    for warning in p.warnings:
        lines.append(f"⚠️ {warning}")
    for issue in p.issues:
        lines.append(f"🔎 {issue}")
    return "\n".join(lines)


def step_messages(step: Step) -> list[Out]:
    """Messages for a pipeline step."""
    if isinstance(step, Need):
        return [Text(step.message)]
    if isinstance(step, Blocked):
        reasons = ", ".join(r.replace("_", " ") for r in step.reasons)
        return [Text(f"⛔ {step.code} blocked: {reasons}. This is on the never-sell list, "
                     "so it can't be listed.")]
    if isinstance(step, Question):
        return [Text(f"{step.code}: {step.text}")]
    assets = [a for a in step.assets if a.is_file()][:ALBUM_LIMIT]
    out: list[Out] = []
    if assets:
        out.append(Album(assets, caption=f"{step.code} · round {step.round}"))
    out.append(Text(f"IG + FB caption:\n\n{step.caption_ig}"))
    out.append(Text(f"TikTok caption:\n\n{step.caption_tiktok}"))
    out.append(Text(_card(step), preview_buttons(step.code, step.needs_check, step.price_ref)))
    return out


HELP = """babyReShop Ops bot

New listing: send 1-6 photos as one album with a caption line:
  2000 B 0-36m washed, small mark on strap     (own stock)
  #seller 4500 Mary barely used                (seller listing)
  optional: buy 600 · ref 8500 (new-in-Nairobi price) · #test (a test drop)
Content post: /post teaser|tip|behind, then the album with one line.

On a preview: ✅ Approve · ✏️ Edit (plain words) · ❌ Reject · ⏩ Now · 🕒 Move · ⏭ Skip

move P-0007 fri 19:00 · skip P-0007 · posted P-0007 · test P-0007
/week  this week's slots      /slots  the calendar file
/pause /resume  scheduled messages      /cancel  drop a pending question
/ping  check the bot"""
