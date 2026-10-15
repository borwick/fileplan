"""Comments in `src/` state, they do not argue.

This module grades the tells the rule names: arguing and narrating
history, over every
comment and docstring under `src/` and over nothing a person reads at the
command line: a refusal may say "on purpose" to the person it refuses.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src" / "fileplan"

#: The tells: arguing ("deliberately", "on purpose") and history (a dated
#: ruling, a date, "used to").
TELLS = re.compile(
    r"\bdeliberate(ly)?\b|\bon purpose\b|\(John, |\b20\d\d-\d\d-\d\d\b|\bused to\b",
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
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
            if (text := ast.get_docstring(node, clean=False)) is not None:
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
