"""Admin phrasings -> expected edit operations (ENGINE_SPEC section 11: 20 or more).

Each entry: (text, [(op, target, value), ...]). All parsed by rules, no model.
"""

from __future__ import annotations

PHRASINGS: list[tuple[str, list[tuple[str, str | None, object]]]] = [
    ("price bigger, drop 'washed', use photo 3 as main", [
        ("resize", "price", "up"),
        ("rewrite_caption", "all", "remove: washed"),
        ("swap_photo", "1", 3),
    ]),
    ("make the price bigger", [("resize", "price", "up")]),
    ("bigger price please", [("resize", "price", "up")]),
    ("price badge smaller", [("resize", "price", "down")]),
    ("code larger", [("resize", "code", "up")]),
    ("grade badge smaller", [("resize", "condition", "down")]),
    ("use photo 2 as the hero", [("swap_photo", "1", 2)]),
    ("photo 4 first", [("swap_photo", "1", 4)]),
    ("hero photo 2", [("swap_photo", "1", 2)]),
    ("order photos 3 1 2", [("reorder_photos", None, [3, 1, 2])]),
    ("reorder 2,3,1", [("reorder_photos", None, [2, 3, 1])]),
    ("move price to top right", [("move", "price", "top-right")]),
    ("put the code bottom left", [("move", "code", "bottom-left")]),
    ("condition badge upper right", [("move", "condition", "top-right")]),
    ("hide the cta", [("toggle", "cta", "off")]),
    ("remove the new in nairobi line", [("toggle", "anchor", "off")]),
    ("show the condition badge", [("toggle", "condition", "on")]),
    ("price 1800", [("set_field", "price", 1800)]),
    ("change price to 1,800", [("set_field", "price", 1800)]),
    ("price to 2.5k", [("set_field", "price", 2500)]),
    ("grade A", [("set_field", "grade", "A")]),
    ("age 0-12m", [("set_field", "age_range", "0-12m")]),
    ("ref 8500", [("set_field", "ref_new_price", 8500)]),
    ("bought for 600", [("set_field", "buy_price", 600)]),
    ("title Graco FastAction Fold stroller", [
        ("set_field", "title", "Graco FastAction Fold stroller")]),
    ("use the bold template", [("set_template", None, "bold")]),
    ("switch to classic style", [("set_template", None, "classic")]),
    ("crop photo 2 to the top", [("crop", "2", "top")]),
    ("photo 1 focus left", [("crop", "1", "left")]),
    ('remove "small mark" from the caption', [
        ("rewrite_caption", "all", "remove: small mark")]),
    ("drop washed from the tiktok caption", [
        ("rewrite_caption", "tiktok", "remove: washed")]),
    ("ig caption: make it shorter", [("rewrite_caption", "ig", "make it shorter")]),
    ("caption more playful", [("rewrite_caption", "all", "more playful")]),
]

# Phrasings rules do not cover: they go to the model (or a question).
UNPARSED = [
    "make it pop more",
    "less busy overall",
    "the main photo should be the one with the canopy up",
]
