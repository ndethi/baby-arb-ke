"""Plain words -> edit operations -> applied changes + drift log (Phase 1 edit loop).

Operations come from a closed list (ENGINE_SPEC Phase 1):
    set_field(field, value)      swap_photo(slot, photo_n)   reorder_photos([...])
    resize(element, up|down)     move(element, position)     toggle(element, on|off)
    set_template(name)           rewrite_caption(platform, instruction)
    crop(photo_n, focus)

Parsing is deterministic first: each clause of the admin's text is matched
by rules. Only when a clause is not understood does the whole text go to the
model (through llm.py), and its operations are validated like any other. If
neither yields valid operations the bot asks a short question; it never
guesses. A model may only set the price to a number the admin typed.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from baby_arb.marketing.intake import parse_price
from baby_arb.marketing.llm import LLMResult, complete
from baby_arb.marketing.render.layout import (
    ELEMENTS,
    FOCI,
    MAX_STEP,
    MIN_STEP,
    MOVABLE,
    POSITIONS,
    TEMPLATES,
    TOGGLEABLE,
    Layout,
)

OpName = Literal[
    "set_field", "swap_photo", "reorder_photos", "resize", "move", "toggle",
    "set_template", "rewrite_caption", "crop",
]
FIELDS = ("price", "grade", "age_range", "condition_note", "title", "ref_new_price",
          "buy_price")
INT_FIELDS = frozenset({"price", "ref_new_price", "buy_price"})
CAPTION_TARGETS = ("ig", "tiktok", "all")
REMOVE_PREFIX = "remove: "


class EditOp(BaseModel):
    """One operation. `target` and `value` meaning depends on `op`."""

    op: OpName
    target: str | None = None
    value: Any = None


@dataclass
class EditPlan:
    """Parsed operations, or a question when the text was not understood."""

    ops: list[EditOp]
    parsed_by: Literal["rules", "model"]
    question: str | None = None


# --------------------------------------------------------------------------- rules

_ELEMENT_WORDS: list[tuple[str, str]] = [
    (r"details?|specs?|spec strip|info strip|chips?|stickers?", "details"),
    (r"seller tag|seller label", "seller_tag"),
    (r"call to action|cta|dm (?:strip|bar|line)|bottom (?:bar|strip)|buy (?:strip|bar)", "cta"),
    (r"new(?:-| in nairobi)? ?(?:price )?anchor|anchor|new in nairobi|reference price|ref price",
     "anchor"),
    (r"price(?: badge| tag| text)?", "price"),
    (r"(?:listing )?code(?: badge)?", "code"),
    (r"condition(?: badge)?|grade(?: badge)?|age(?: badge)?", "condition"),
]


def _element(text: str) -> str | None:
    for pattern, name in _ELEMENT_WORDS:
        if re.search(rf"\b(?:{pattern})\b", text):
            return name
    return None


_POSITION = re.compile(r"\b(top|upper|bottom|lower)[ -]?(left|right)\b")
_FOCUS_WORDS = {"centre": "center", "center": "center", "middle": "center", "top": "top",
                "bottom": "bottom", "left": "left", "right": "right"}


def _position(text: str) -> str | None:
    match = _POSITION.search(text)
    if not match:
        return None
    vertical = "top" if match.group(1) in {"top", "upper"} else "bottom"
    return f"{vertical}-{match.group(2)}"


# Straight and curly quotes (escaped so the source stays ASCII).
_Q = "'\"\u2018\u2019\u201c\u201d"


def _split_clauses(text: str) -> list[str]:
    protected = re.sub(rf"([{_Q}])(.*?)([{_Q}])",
                       lambda m: m.group(1) + m.group(2).replace(",", "\0") + m.group(3), text)
    # A comma followed by a digit is part of a number or a photo order ("1,800", "2,3,1").
    parts = re.split(r"\s*(?:,(?!\d)|;|\n|\band then\b|\bthen\b|\band\b|\balso\b)\s*",
                     protected)
    return [p.replace("\0", ",").strip(" .!") for p in parts if p and p.strip(" .!")]


_QUOTED = re.compile(rf"[{_Q}](.+?)[{_Q}]")


def _rule_clause(clause: str, raw_lower: str) -> list[EditOp] | None:
    """Operations for one clause, or None when no rule understands it."""
    c = clause.lower().strip()

    # Photos: hero / reorder / crop.
    m = re.search(r"\bphoto\s*(\d)\b.*\b(?:as|for|the)?\s*(?:main|hero|cover|first|lead)\b", c) \
        or re.search(r"\b(?:main|hero|cover|lead with|start with)\b(?: photo| image)?\s*(?:to |=|is )?"
                     r"(?:photo\s*)?(\d)\b", c)
    if m and not re.search(r"\bcrop|focus\b", c):
        return [EditOp(op="swap_photo", target="1", value=int(m.group(1)))]
    if re.search(r"\b(?:order|reorder)\b|\bphotos\b", c) and not re.search(r"\bcrop|focus", c):
        nums = [int(n) for n in re.findall(r"\b(\d)\b", c)]
        if len(nums) >= 2:
            return [EditOp(op="reorder_photos", value=nums)]
    focus = r"\b(top|bottom|left|right|cent(?:er|re)|middle)\b"
    m = re.search(rf"\b(?:crop|focus|zoom)\b.*?\bphoto\s*(\d)\b.*?{focus}", c) or re.search(
        rf"\bphoto\s*(\d)\b.*?\b(?:crop|focus|show more)\b.*?{focus}", c
    )
    if m:
        return [EditOp(op="crop", target=m.group(1), value=_FOCUS_WORDS[m.group(2)])]

    # Template.
    m = re.search(r"\b(classic|bold)\b(?: template| look| style)?", c)
    if m and re.search(r"\btemplate|style|look|use\b|switch", c):
        return [EditOp(op="set_template", value=m.group(1))]

    # Field values (need a value in the clause).
    m = re.search(r"\b(?:price|sell(?:ing)? (?:for|at))\b\s*(?:to|=|:|is|at|of)?\s*"
                  r"((?:kes|ksh)?\s*[\d,.]+k?)\b", c)
    if m and not re.search(r"\b(?:new|ref|reference|buy|bought|paid)\b", c[:m.start() + 1]):
        amount = parse_price(m.group(1).replace(" ", ""))
        if amount is not None:
            return [EditOp(op="set_field", target="price", value=amount)]
    m = re.search(r"\b(?:new in nairobi|new price|ref(?:erence)?(?: price)?|anchor)\b\s*"
                  r"(?:to|=|:|is|at|of|from)?\s*((?:kes|ksh)?\s*[\d,.]+k?)\b", c)
    if m:
        amount = parse_price(m.group(1).replace(" ", ""))
        if amount is not None:
            return [EditOp(op="set_field", target="ref_new_price", value=amount)]
    m = re.search(r"\b(?:buy price|bought (?:for|at)|paid)\b\s*(?:to|=|:|is|at)?\s*"
                  r"((?:kes|ksh)?\s*[\d,.]+k?)\b", c)
    if m:
        amount = parse_price(m.group(1).replace(" ", ""))
        if amount is not None:
            return [EditOp(op="set_field", target="buy_price", value=amount)]
    m = re.search(r"\bgrade\s*(?:to|=|:|is)?\s*([abc])\b", c)
    if m and not re.search(r"\b(bigger|larger|smaller|up|down|hide|remove|show)\b", c):
        return [EditOp(op="set_field", target="grade", value=m.group(1).upper())]
    m = re.search(r"\bage(?: range)?\s*(?:to|=|:|is)?\s*(\d{1,2}\s*-\s*\d{1,2}\s*[a-z]*|\d{1,2}m\+)",
                  c)
    if m:
        return [EditOp(op="set_field", target="age_range", value=re.sub(r"\s+", "", m.group(1)))]
    m = re.search(r"^(?:title|item|name|it'?s an?|it is an?)\s*(?:is|=|:|to)?\s*(.+)$", clause.strip(),
                  re.IGNORECASE)
    if m and len(m.group(1)) >= 3:
        return [EditOp(op="set_field", target="title", value=m.group(1).strip(" '\""))]

    # Caption edits.
    platform = "ig" if re.search(r"\b(?:ig|insta(?:gram)?|fb|facebook)\b", c) else (
        "tiktok" if "tiktok" in c else "all")
    quoted = _QUOTED.search(clause)
    m = re.match(r"^(?:drop|remove|delete|take out|cut|lose|no)\b\s*(.*)$", c)
    if m:
        rest = m.group(1).strip()
        element = _element(rest)
        if quoted is None and element is not None and not re.search(r"\bcaption\b", rest):
            if element in TOGGLEABLE:
                return [EditOp(op="toggle", target=element, value="off")]
            return None
        phrase = quoted.group(1) if quoted else re.sub(
            r"\b(?:the word|from (?:the )?(?:ig |instagram |tiktok |fb )?captions?|"
            r"in (?:the )?captions?)\b", "", rest).strip(" '\"")
        if phrase:
            return [EditOp(op="rewrite_caption", target=platform, value=REMOVE_PREFIX + phrase)]
    if re.search(r"\bcaption\b", c):
        instruction = re.sub(r"^(?:make )?(?:the )?(?:ig |instagram |tiktok |fb )?caption\b\s*:?\s*",
                             "", clause.strip(), flags=re.IGNORECASE)
        if instruction:
            return [EditOp(op="rewrite_caption", target=platform, value=instruction)]

    # Layout: toggle / move / resize.
    element = _element(c)
    if element is not None:
        if re.search(r"\b(?:hide|turn off|switch off|without|no)\b", c) and element in TOGGLEABLE:
            return [EditOp(op="toggle", target=element, value="off")]
        if re.search(r"\b(?:show|add|bring back|turn on|put back|include)\b", c) \
                and element in TOGGLEABLE:
            return [EditOp(op="toggle", target=element, value="on")]
        pos = _position(c)
        if pos and element in MOVABLE:
            return [EditOp(op="move", target=element, value=pos)]
        if re.search(r"\b(?:bigger|larger|big|bolder|up|increase|enlarge|more visible|louder)\b", c):
            return [EditOp(op="resize", target=element, value="up")]
        if re.search(r"\b(?:smaller|small|down|decrease|shrink|less|subtler|tone down)\b", c):
            return [EditOp(op="resize", target=element, value="down")]
    return None


def parse_rules(text: str) -> list[EditOp] | None:
    """Operations for every clause, or None if any clause is not understood."""
    ops: list[EditOp] = []
    lowered = text.lower()
    for clause in _split_clauses(text):
        found = _rule_clause(clause, lowered)
        if found is None:
            return None
        ops.extend(found)
    return ops or None


# --------------------------------------------------------------------------- model

PARSE_PROMPT = """You turn a shop admin's edit request for a listing graphic and caption
into operations. Allowed operations only (JSON list):
{"op":"set_field","target":<price|grade|age_range|condition_note|title|ref_new_price|buy_price>,"value":...}
{"op":"swap_photo","target":"<slot number, 1 = hero>","value":<photo number>}
{"op":"reorder_photos","value":[photo numbers]}
{"op":"resize","target":<price|code|condition|cta|anchor|seller_tag|details>,"value":"up"|"down"}
{"op":"move","target":<price|code|condition>,"value":<top-left|top-right|bottom-left|bottom-right>}
{"op":"toggle","target":<condition|cta|anchor|details>,"value":"on"|"off"}
{"op":"set_template","value":"classic"|"bold"}
{"op":"rewrite_caption","target":"ig"|"tiktok"|"all","value":"<instruction>"}
{"op":"crop","target":"<photo number>","value":<center|top|bottom|left|right>}
Return JSON only: {"ops": [...]} or, if the request cannot be expressed with these,
{"question": "<one short clarifying question>"}. Never invent prices."""


Completer = Callable[..., LLMResult]


def _parse_model(text: str, state: dict[str, Any], completer: Completer) -> EditPlan:
    result = completer(
        "edit_parse",
        [{"role": "system", "content": PARSE_PROMPT},
         {"role": "user", "content": f"Current state: {json.dumps(state)}\nRequest: {text}"}],
        max_tokens=400,
        temperature=0.0,
    )
    fallback = EditPlan([], "model", question=(
        "I didn't get that. Try e.g. 'price bigger', 'use photo 3 as main', "
        "\"drop 'washed'\", 'move price to top right', 'price 1800'."
    ))
    if result.degraded or not result.text:
        return fallback
    raw = result.text
    start, end = raw.find("{"), raw.rfind("}")
    try:
        data = json.loads(raw[start:end + 1]) if start >= 0 else None
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict):
        return fallback
    if isinstance(data.get("question"), str) and not data.get("ops"):
        return EditPlan([], "model", question=data["question"][:300])
    try:
        ops = [EditOp.model_validate(o) for o in data.get("ops") or []]
    except ValidationError:
        return fallback
    return EditPlan(ops, "model") if ops else fallback


def parse_edit(
    text: str, state: dict[str, Any] | None = None, completer: Completer = complete
) -> EditPlan:
    """Rules first, model second, question last."""
    ops = parse_rules(text)
    plan = EditPlan(ops, "rules") if ops else _parse_model(text, state or {}, completer)
    if plan.ops:
        problems = [p for op in plan.ops for p in validate_op(op, text, state or {})]
        if problems:
            return EditPlan([], plan.parsed_by, question="I can't do that: " + "; ".join(problems))
    return plan


# --------------------------------------------------------------------------- validate

def _digits_in(text: str) -> set[int]:
    found = set()
    for token in re.findall(r"(?:kes|ksh)?\s*[\d][\d,.]*k?", text.lower()):
        value = parse_price(token.replace(" ", ""))
        if value is not None:
            found.add(value)
    return found


def validate_op(op: EditOp, raw_text: str, state: dict[str, Any]) -> list[str]:
    """Problems with one operation (empty when it may be applied)."""
    photos = set(state.get("photos") or [])
    if op.op == "set_field":
        if op.target not in FIELDS:
            return [f"unknown field {op.target}"]
        if op.target in INT_FIELDS:
            if not isinstance(op.value, int) or op.value <= 0:
                return [f"{op.target} must be a whole number of shillings"]
            if op.value not in _digits_in(raw_text):
                return [f"{op.target} {op.value} is not a number you typed"]
        if op.target == "grade" and op.value not in {"A", "B", "C"}:
            return ["grade must be A, B or C"]
        if op.target not in INT_FIELDS and not (isinstance(op.value, str) and op.value.strip()):
            return [f"{op.target} needs a value"]
    elif op.op == "swap_photo":
        if not (isinstance(op.value, int) and (not photos or op.value in photos)):
            return [f"there is no photo {op.value}"]
        if not (op.target or "").isdigit():
            return ["photo slot must be a number"]
    elif op.op == "reorder_photos":
        if not isinstance(op.value, list) or not all(isinstance(n, int) for n in op.value):
            return ["photo order must be numbers"]
        if photos and not set(op.value) <= photos:
            return [f"unknown photo in {op.value}"]
        if len(set(op.value)) != len(op.value):
            return ["a photo appears twice in the order"]
    elif op.op == "resize":
        if op.target not in ELEMENTS or op.value not in {"up", "down"}:
            return [f"can't resize {op.target}"]
    elif op.op == "move":
        if op.target not in MOVABLE or op.value not in POSITIONS:
            return [f"can't move {op.target} to {op.value}"]
    elif op.op == "toggle":
        if op.target not in TOGGLEABLE:
            return [f"{op.target} can't be switched off (code, price and seller tag stay)"]
        if op.value not in {"on", "off"}:
            return ["toggle needs on or off"]
    elif op.op == "set_template":
        if op.value not in TEMPLATES:
            return [f"unknown template {op.value}; have {', '.join(TEMPLATES)}"]
    elif op.op == "rewrite_caption":
        if op.target not in CAPTION_TARGETS or not isinstance(op.value, str) or not op.value:
            return ["caption change needs a platform and an instruction"]
    elif op.op == "crop":
        if not (op.target or "").isdigit() or (photos and int(op.target or 0) not in photos):
            return [f"there is no photo {op.target}"]
        if op.value not in FOCI:
            return [f"crop focus must be one of {', '.join(FOCI)}"]
    return []


# --------------------------------------------------------------------------- describe

_ELEMENT_LABEL = {"details": "details strip",
                  "price": "price badge", "code": "code", "condition": "condition badge",
                  "cta": "DM strip", "anchor": "'new in Nairobi' line", "seller_tag": "seller tag"}


def describe(op: EditOp) -> str:
    """Short echo text, e.g. "make price badge larger"."""
    v, t = op.value, op.target
    if op.op == "set_field":
        shown = f"KES {v:,}" if isinstance(v, int) else v
        return f"set {str(t).replace('_', ' ')} to {shown}"
    if op.op == "swap_photo":
        return f"set photo {v} as hero" if t == "1" else f"put photo {v} in position {t}"
    if op.op == "reorder_photos":
        return "order photos " + ", ".join(str(n) for n in v)
    if op.op == "resize":
        return f"make {_ELEMENT_LABEL.get(str(t), t)} {'larger' if v == 'up' else 'smaller'}"
    if op.op == "move":
        return f"move {_ELEMENT_LABEL.get(str(t), t)} to {str(v).replace('-', ' ')}"
    if op.op == "toggle":
        return f"{'show' if v == 'on' else 'hide'} {_ELEMENT_LABEL.get(str(t), t)}"
    if op.op == "set_template":
        return f"use the {v} template"
    if op.op == "rewrite_caption":
        where = {"ig": "IG/FB caption", "tiktok": "TikTok caption", "all": "captions"}[str(t)]
        if isinstance(v, str) and v.startswith(REMOVE_PREFIX):
            return f"remove '{v[len(REMOVE_PREFIX):]}' from {where}"
        return f"rewrite {where}: {v}"
    if op.op == "crop":
        return f"crop photo {t} to the {v}"
    return op.op  # pragma: no cover


# --------------------------------------------------------------------------- apply

@dataclass
class Change:
    """One applied change for the drift log."""

    op: EditOp
    before: str | None
    after: str | None


@dataclass
class Applied:
    """Result of applying a plan to in-memory state."""

    fields: dict[str, Any]
    layout: Layout
    caption_ig: str
    caption_tiktok: str
    changes: list[Change] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    fields_changed: bool = False


def _bump(layout: Layout, element: str, direction: str) -> tuple[int, int]:
    before = layout.step(element)
    after = max(MIN_STEP, min(MAX_STEP, before + (1 if direction == "up" else -1)))
    layout.sizes[element] = after
    return before, after


def apply_layout_and_fields(
    ops: list[EditOp], fields: dict[str, Any], layout: Layout, caption_ig: str,
    caption_tiktok: str,
) -> Applied:
    """Apply every operation except caption rewrites (which the caller runs).

    Caption *removals* are deterministic and applied here.
    """
    out = Applied(dict(fields), layout.model_copy(deep=True), caption_ig, caption_tiktok)
    lay = out.layout
    for op in ops:
        if op.op == "set_field":
            key = str(op.target)
            before = out.fields.get(key)
            out.fields[key] = op.value
            out.fields_changed = True
            out.changes.append(Change(op, _s(before), _s(op.value)))
        elif op.op == "swap_photo":
            before_order = list(lay.photo_order)
            slot = max(1, int(op.target or "1"))
            order = [n for n in lay.photo_order if n != op.value]
            order.insert(min(slot - 1, len(order)), int(op.value))
            lay.photo_order = order
            out.changes.append(Change(op, _s(before_order), _s(order)))
        elif op.op == "reorder_photos":
            before_order = list(lay.photo_order)
            rest = [n for n in lay.photo_order if n not in op.value]
            lay.photo_order = list(op.value) + rest
            out.changes.append(Change(op, _s(before_order), _s(lay.photo_order)))
        elif op.op == "resize":
            b, a = _bump(lay, str(op.target), str(op.value))
            if a == b:
                out.problems.append(f"{describe(op)}: already at the limit")
            out.changes.append(Change(op, str(b), str(a)))
        elif op.op == "move":
            before_pos = lay.position(str(op.target))
            lay.positions[str(op.target)] = op.value
            out.changes.append(Change(op, before_pos, str(op.value)))
        elif op.op == "toggle":
            before_on = lay.shown(str(op.target))
            lay.toggles[str(op.target)] = op.value == "on"
            out.changes.append(Change(op, "on" if before_on else "off", str(op.value)))
        elif op.op == "set_template":
            before_t = lay.template
            lay.template = op.value
            out.changes.append(Change(op, before_t, str(op.value)))
        elif op.op == "crop":
            n = int(op.target or 0)
            before_f = lay.crops.get(n, "center")
            lay.crops[n] = op.value
            out.changes.append(Change(op, before_f, str(op.value)))
        elif op.op == "rewrite_caption" and isinstance(op.value, str) \
                and op.value.startswith(REMOVE_PREFIX):
            from baby_arb.marketing.captions import strip_phrase

            phrase = op.value[len(REMOVE_PREFIX):]
            before_c = f"{out.caption_ig}\n---\n{out.caption_tiktok}"
            found = phrase.lower() in before_c.lower()
            if op.target in {"ig", "all"}:
                out.caption_ig = strip_phrase(out.caption_ig, phrase)
            if op.target in {"tiktok", "all"}:
                out.caption_tiktok = strip_phrase(out.caption_tiktok, phrase)
            if not found:
                out.problems.append(f"'{phrase}' is not in the caption")
            if str(out.fields.get("condition_note") or "").lower().find(phrase.lower()) >= 0:
                out.fields["condition_note"] = strip_phrase(
                    str(out.fields["condition_note"]), phrase) or None
            out.changes.append(Change(op, before_c, f"{out.caption_ig}\n---\n{out.caption_tiktok}"))
    return out


def _s(value: Any) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else json.dumps(value)
