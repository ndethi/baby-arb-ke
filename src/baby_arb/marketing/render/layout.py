"""Per-listing render state that edit operations change (stored in listings.layout).

Elements: price, code, condition, cta, anchor, seller_tag, details (the strip
of short looked-up facts). Sizes are steps
(-2..+3) around each element's base size; positions are corners; toggles
switch optional elements. `code`, `price` and `seller_tag` cannot be
toggled off because the creative checks require them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Element = Literal["price", "code", "condition", "cta", "anchor", "seller_tag", "details"]
ELEMENTS: tuple[Element, ...] = ("price", "code", "condition", "cta", "anchor", "seller_tag",
                                 "details")
Position = Literal["top-left", "top-right", "bottom-left", "bottom-right"]
POSITIONS: tuple[Position, ...] = ("top-left", "top-right", "bottom-left", "bottom-right")
Focus = Literal["center", "top", "bottom", "left", "right"]
FOCI: tuple[Focus, ...] = ("center", "top", "bottom", "left", "right")
Template = Literal["classic", "bold"]
TEMPLATES: tuple[Template, ...] = ("classic", "bold")

TOGGLEABLE: frozenset[str] = frozenset({"condition", "cta", "anchor", "details"})
MOVABLE: frozenset[str] = frozenset({"price", "code", "condition"})
MIN_STEP, MAX_STEP = -2, 3

TEMPLATE_VERSION = 2  # 2: details strip

DEFAULT_POSITIONS: dict[str, Position] = {
    "price": "bottom-left", "code": "top-right", "condition": "top-left",
}


class Rect(BaseModel):
    """A region as fractions of the photo (0..1), e.g. a flaw to keep clear."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)


class Layout(BaseModel):
    """Everything about a render that is not a listing field."""

    template: Template = "classic"
    photo_order: list[int] = Field(default_factory=list)  # photo numbers, hero first
    sizes: dict[str, int] = Field(default_factory=dict)
    positions: dict[str, Position] = Field(default_factory=lambda: dict(DEFAULT_POSITIONS))
    toggles: dict[str, bool] = Field(default_factory=dict)
    crops: dict[int, Focus] = Field(default_factory=dict)
    flaw_zones: list[Rect] = Field(default_factory=list)

    @property
    def hero(self) -> int | None:
        """Photo number used as the hero (first in order)."""
        return self.photo_order[0] if self.photo_order else None

    def step(self, element: str) -> int:
        """Size step for an element (0 when unset)."""
        return self.sizes.get(element, 0)

    def shown(self, element: str) -> bool:
        """Whether an optional element is switched on (default on)."""
        return self.toggles.get(element, True) if element in TOGGLEABLE else True

    def position(self, element: str) -> Position:
        """Corner for a movable element."""
        return self.positions.get(element, "top-left")


def load_layout(raw: str | None, photo_numbers: list[int]) -> Layout:
    """Parse listings.layout, filling photo order from the photos when empty."""
    layout = Layout.model_validate_json(raw) if raw else Layout()
    known = [n for n in layout.photo_order if n in photo_numbers]
    missing = [n for n in photo_numbers if n not in known]
    layout.photo_order = known + missing
    return layout


def dump_layout(layout: Layout) -> str:
    """Serialise for listings.layout."""
    return layout.model_dump_json()
