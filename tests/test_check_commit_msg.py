"""Local commit-msg check mirrors CI commitlint rules."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "check_commit_msg", Path(__file__).parent.parent / "scripts" / "check_commit_msg.py"
)
assert _SPEC and _SPEC.loader
ccm = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ccm)
PATTERN = ccm.load_pattern()


@pytest.mark.parametrize(
    ("message", "error"),
    [
        ("feat(bot): add ping command", None),
        ("feat(bot): add ping command\n\nWhy it matters.\n\nCo-Authored-By: X <x@y.z>", None),
        ("Merge branch 'x'", None),
        ("feat(bot): add PING command", "lower-case"),
        ("feat(bot): add ping\nno blank line", "blank line"),
        ("feat(bot): add ping\n\n" + "x" * 101, "longer than 100"),
        ("feature(bot): add ping", "does not match"),
    ],
)
def test_check_message(message, error):
    result = ccm.check_message(message, PATTERN)
    if error is None:
        assert result is None
    else:
        assert result is not None and error in result
