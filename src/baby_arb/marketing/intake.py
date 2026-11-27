"""Parse the one-line caption of a drop (ENGINE_SPEC Phase 1, Intake).

    <price> [grade A|B|C] [age range] [notes]        own stock
    #seller <price> <seller name> [notes]             seller listing

Two optional tokens anywhere in the notes are also read, because the pricing
check and the "new from" anchor need them and the spec forbids inventing
either: `buy 600` (what we paid) and `ref 8500` or `new 8500` (the admin's
"new in Nairobi" reference price).

The price must be the first token (after `#seller`). If it is not there the
result has `price=None` and the bot asks. The parser never searches the rest
of the line for a number to use as the price.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

MAX_PHOTOS = 6

_PRICE = re.compile(
    r"^(?:kes|ksh|kshs|sh)?\.?\s*(?P<num>\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?P<k>k)?$",
    re.IGNORECASE,
)
_GRADE = re.compile(r"^[ABC]$", re.IGNORECASE)
_AGE = re.compile(
    r"^(?:\d{1,2}\s*-\s*\d{1,2}\s*(?:m|mo|mos|months?|y|yr|yrs|years?)"
    r"|\d{1,2}\s*(?:m|mo|y|yr)\+|newborn|nb)$",
    re.IGNORECASE,
)
_TAGGED = re.compile(r"\b(?P<tag>buy|ref|new)\s*(?::|=)?\s*(?P<amount>(?:kes\s*)?[\d,.]+k?)\b",
                     re.IGNORECASE)


@dataclass(frozen=True)
class ParsedLine:
    """What the admin's line says. Nothing here is guessed."""

    kind: Literal["own", "seller"]
    price: int | None
    grade: str | None = None
    age_range: str | None = None
    notes: str | None = None
    buy_price: int | None = None
    ref_new_price: int | None = None
    seller_name: str | None = None
    problems: list[str] = field(default_factory=list)


def parse_price(token: str) -> int | None:
    """Whole shillings from "2000", "2,000", "2k", "2.5k" or "KES2000"; else None."""
    match = _PRICE.match(token.strip())
    if not match:
        return None
    number = float(match.group("num").replace(",", ""))
    if match.group("k"):
        number *= 1000
    if number <= 0 or number != int(number):
        return None
    return int(number)


def _join_price_tokens(tokens: list[str]) -> list[str]:
    """Merge "KES 2000" into one token so the price check sees it."""
    if len(tokens) >= 2 and tokens[0].lower().rstrip(".") in {"kes", "ksh", "kshs", "sh"}:
        return [tokens[0] + tokens[1], *tokens[2:]]
    return tokens


def _age_token(tokens: list[str]) -> tuple[str | None, int]:
    """Age range from the first one to four tokens ("0-36m", "6 - 12 months")."""
    for width in (4, 3, 2, 1):
        if len(tokens) >= width:
            candidate = " ".join(tokens[:width])
            if _AGE.match(candidate):
                return re.sub(r"\s+", "", candidate), width
    return None, 0


def parse_line(line: str | None) -> ParsedLine:
    """Parse a drop caption.

    Args:
        line: The album caption (may be empty).

    Returns:
        ParsedLine. `price` is None when the first token is not a price.
    """
    text = " ".join((line or "").split())
    kind: Literal["own", "seller"] = "own"
    if text.lower().startswith("#seller"):
        kind = "seller"
        text = text[len("#seller"):].strip()

    buy_price: int | None = None
    ref_price: int | None = None
    problems: list[str] = []
    for match in list(_TAGGED.finditer(text)):
        amount = parse_price(match.group("amount").replace(" ", ""))
        if amount is None:
            problems.append(f"could not read {match.group(0)!r}")
            continue
        if match.group("tag").lower() == "buy":
            buy_price = amount
        else:
            ref_price = amount
        text = text.replace(match.group(0), " ")
    tokens = _join_price_tokens(text.split())

    price = parse_price(tokens[0]) if tokens else None
    rest = tokens[1:] if price is not None else tokens

    seller_name: str | None = None
    grade: str | None = None
    age: str | None = None
    if kind == "seller":
        if price is not None and rest:
            seller_name, rest = rest[0], rest[1:]
    else:
        if rest and _GRADE.match(rest[0]) and (len(rest) == 1 or rest[0].isupper()):
            grade, rest = rest[0].upper(), rest[1:]
        age, used = _age_token(rest)
        rest = rest[used:]
    notes = " ".join(rest).strip(" ,;") or None
    if kind == "seller" and price is not None and seller_name is None:
        problems.append("seller name missing")
    return ParsedLine(
        kind=kind,
        price=price,
        grade=grade,
        age_range=age,
        notes=notes,
        buy_price=buy_price,
        ref_new_price=ref_price,
        seller_name=seller_name,
        problems=problems,
    )


def price_warnings(price: int | None, buy_price: int | None) -> list[str]:
    """Warnings for the preview. The price is never changed."""
    if price is not None and buy_price is not None and price < 3 * buy_price:
        return [f"Price KES {price:,} is below 3x the buy price (KES {buy_price:,})."]
    return []
