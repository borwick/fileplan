"""Comments in `src/` state, they do not argue.

This module grades the tells the rule names: arguing and narrating
history, over every
comment and docstring under `src/` and over nothing a person reads at the
command line: a refusal may say "on purpose" to the person it refuses.

The two dating tells, a dated ruling and a date, are graded over the
comments and docstrings in `tests/` as well. A ruling there keeps its name
and drops its day, as METHODOLOGY's *Current state only* says.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "fileplan"

#: The tree graded for a date only.
DATED = sorted((ROOT / "tests").rglob("*.py"))

#: The dating tells: a dated ruling and a date.
DATES = re.compile(r"\(John, |\b20\d\d-\d\d-\d\d\b")

#: The tells: arguing ("deliberately", "on purpose") and history (the dating
#: tells, "used to").
TELLS = re.compile(
    rf"\bdeliberate(ly)?\b|\bon purpose\b|{DATES.pattern}|\bused to\b",
    re.IGNORECASE,
)


def _prose(source: str) -> list[tuple[int, str]]:
    """Every comment and docstring in `source`, with its line."""
    found = [
        (token.start[0], token.string)
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.COMMENT
    ]
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef))
            and (text := ast.get_docstring(node, clean=False)) is not None
        ):
            found.append((node.body[0].lineno, text))
    return found


@pytest.mark.parametrize("path", sorted(SRC.rglob("*.py")), ids=lambda p: p.name)
def test_no_comment_in_src_argues_or_narrates_history(path: Path) -> None:
    """34-3's done line, per module."""
    said = [
        (line, match.group(0))
        for line, text in _prose(path.read_text())
        for match in TELLS.finditer(text)
    ]
    assert said == [], said


@pytest.mark.parametrize("path", DATED, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_no_comment_in_tests_dates_a_ruling(path: Path) -> None:
    """No comment or docstring in `tests/` dates a ruling or holds a date.
    A date in a fixture string is data, so only comments and docstrings are
    read."""
    said = [
        (line, match.group(0))
        for line, text in _prose(path.read_text())
        for match in DATES.finditer(text)
    ]
    assert said == [], said


def test_the_tells_are_found_in_a_comment_and_not_in_a_message() -> None:
    """The mutation check: a tell in a comment or a docstring is found, and
    the same words in a string a person is shown are not."""
    source = (
        '"""Deliberately so."""\n'
        "# John ruled on 2026-09-02.\n"
        'MESSAGE = "pass --keep-claims to hold them all on purpose"\n'
    )
    assert [m.group(0) for _, t in _prose(source) for m in TELLS.finditer(t)] == [
        "2026-09-02",
        "Deliberately",
    ]
