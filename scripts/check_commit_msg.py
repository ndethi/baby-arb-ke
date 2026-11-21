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
MAX_BODY_LINE = 100  # commitlint body-max-line-length / footer-max-line-length
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
    subject = header.split(": ", 1)[1] if ": " in header else header
    if subject != subject.lower():
        return "subject must be lower-case (commitlint subject-case)"
    return None


def check_message(message: str, pattern: re.Pattern[str]) -> str | None:
    """Check the header plus body/footer line lengths, as commitlint does in CI."""
    lines = [line for line in message.splitlines() if not line.startswith("#")]
    header = lines[0].strip() if lines else ""
    err = check_header(header, pattern)
    if err or TOOL_HEADERS.match(header):
        return err
    if len(lines) > 1 and lines[1].strip():
        return "body must start after a blank line"
    long = [n for n, line in enumerate(lines[1:], start=2) if len(line) > MAX_BODY_LINE]
    if long:
        return f"body line {long[0]} longer than {MAX_BODY_LINE} chars"
    return None


def messages_in_range(rev_range: str) -> list[tuple[str, str]]:
    """Return (short sha, full message) for every non-merge commit in a range."""
    out = subprocess.run(
        ["git", "log", "--no-merges", "--format=%h%x00%B%x1e", rev_range],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    ).stdout
    records = (rec.strip("\n").split("\x00", 1) for rec in out.split("\x1e") if rec.strip())
    return [(sha, msg.strip("\n")) for sha, msg in records]


def main(argv: list[str]) -> int:
    """Run the check; return a process exit code."""
    pattern = load_pattern()
    if len(argv) == 2 and argv[0] == "--range":
        bad = [
            (sha, msg.splitlines()[0] if msg else "", err)
            for sha, msg in messages_in_range(argv[1])
            if (err := check_message(msg, pattern))
        ]
        for sha, header, err in bad:
            print(f"[ERROR] {sha} {header!r}: {err}")
        return 1 if bad else 0
    if len(argv) == 1:
        message = Path(argv[0]).read_text()
        err = check_message(message, pattern)
        if err:
            header = message.splitlines()[0] if message else ""
            print(f"[ERROR] commit message {header!r}: {err}")
            return 1
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
