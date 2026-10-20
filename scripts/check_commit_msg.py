#!/usr/bin/env python3
"""Validate commit messages against the project's Conventional Commits pattern.

The allowed pattern is read from ``.cz.toml`` (``schema_pattern``) so there is
one source of truth for commit types.

Usage:
    scripts/check_commit_msg.py <commit-msg-file>     # git commit-msg hook
    scripts/check_commit_msg.py --range <base>..<head>  # check a commit range
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MAX_HEADER = 100
# Commits produced by tooling rather than by hand.
TOOL_HEADERS = re.compile(r"^(Merge |Revert \"|bump: version )")


def load_pattern() -> re.Pattern[str]:
    """Return the compiled commit header pattern from .cz.toml."""
    with (REPO_ROOT / ".cz.toml").open("rb") as f:
        cfg = tomllib.load(f)
    return re.compile(cfg["tool"]["commitizen"]["customize"]["schema_pattern"])


def check_header(header: str, pattern: re.Pattern[str]) -> str | None:
    """Return an error message for a bad header, or None if it is valid."""
    if TOOL_HEADERS.match(header):
        return None
    if len(header) > MAX_HEADER:
        return f"header longer than {MAX_HEADER} chars"
    if not pattern.fullmatch(header):
        return "does not match <type>(<scope>): <description> (types in .cz.toml)"
    return None


def headers_in_range(rev_range: str) -> list[tuple[str, str]]:
    """Return (short sha, header) for every non-merge commit in a range."""
    out = subprocess.run(
        ["git", "log", "--no-merges", "--format=%h%x09%s", rev_range],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    ).stdout
    pairs = (line.split("\t", 1) for line in out.splitlines() if line)
    return [(sha, header) for sha, header in pairs]


def main(argv: list[str]) -> int:
    """Run the check; return a process exit code."""
    pattern = load_pattern()
    if len(argv) == 2 and argv[0] == "--range":
        bad = [
            (sha, header, err)
            for sha, header in headers_in_range(argv[1])
            if (err := check_header(header, pattern))
        ]
        for sha, header, err in bad:
            print(f"[ERROR] {sha} {header!r}: {err}")
        return 1 if bad else 0
    if len(argv) == 1:
        lines = Path(argv[0]).read_text().splitlines()
        header = lines[0].strip() if lines else ""
        err = check_header(header, pattern)
        if err:
            print(f"[ERROR] commit message {header!r}: {err}")
            return 1
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
