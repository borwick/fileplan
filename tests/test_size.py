"""The size test, as a thing that runs rather than a number somebody quoted.

This repo has always carried the model's central claim — that a workflow
*declared* costs less code than a workflow written per verb — as a pair of
line counts against the old tool. Until 6-4 the numbers came from a script that was never committed, so the pair could not
be reproduced, the ceiling could not be re-checked, and no section could tell
whether it had moved towards it. That is the shape the stale-data rule
rejects: a fact we track, kept current by somebody remembering.

So the counter ships here, and the method it uses *is* the method. One
counter, run over two file sets that are counted the same way:

* `src/fileplan/*.py` — this tool's source, one level, no `tests/`.
* `scripts/*.py` in the old tree — its source, one level, excluding the
  `scripts/tests/` that hold its 451 tests.

That pairing is the whole reason the numbers are comparable, and it is why
the ceiling below is a **constant**. The old tool is read-only reference and
not a dependency: it lives on one machine, and a suite that read it would
fail everywhere else. The date, the counter and the glob go in the comment
beside the number instead — the shape `[identity]`'s reasoning has in
`plan.toml`.

**The ceiling is no longer the other tree's size.** Until section 7 closed it
was 4,180 — the old tool's code count — on 6-4's re-framing that the old tool
is the ceiling rather than the multiple. Section 7 spent that down to 70 lines
of headroom and, on raw lines, went past the old tool outright: 9,803 against
8,754. So the code-to-code framing was one section from saying the model was
wrong about a tree that had already grown larger by the measure the original
claim was made against, which is a test grading the wrong thing rather than a
verdict. 6-4 re-framed the test on the measurement instead of the measurement
on the test; this is that rule a second time, and John set a **budget** on
2026-09-06 (`CEILING` below): a number this repo chose, with room for sections
8 and 9, and the old tool's pair kept beside it as where the number came from.

What the model claims is not "fewer lines" — the measurement has refused that
twice. It is what the difference bought: more than three times the old tool's 451
tests, the workflow declared in `plan.toml` rather than written per verb, and
no named-report tier at all. The counts stay here as a measurement, and the
budget goes red when this tree outgrows what we said it should cost.

The suite's own size is deliberately not a number in this docstring (10-6,
2026-09-07). It said "1,353 tests against 451" and was stale by more than a
hundred, which is the failure the no-written-down-counts rule took out:
nothing written down that a calculation tracks better. `451` stays spelled
out, because the old tool is read-only reference on one machine and cannot be
counted from here — the same reason `OLD` below is a frozen constant.

The counter grades *source*, which is what makes this its own module:
`test_docs.py` beside it grades documents, and the claim and the lock are
each their own behaviour too.
"""

from __future__ import annotations

import inspect
import tokenize
from pathlib import Path

#: This tool's source: one level under the package, tests excluded.
SRC = Path(__file__).resolve().parent.parent / "src" / "fileplan"

#: The budget for `src/fileplan/*.py`, in lines of code: **a number John set
#: on 2026-09-06**, not the size of another tree. Roughly section 7's own cost
#: again, for sections 8 and 9.
#:
#: Where the ceiling used to come from, kept as context: the old tool's
#: `scripts/*.py`, counted by `_counts` below on 2026-09-05 (24 files: 4,180
#: code, 3,307 doc, 1,267 blank, 8,754 raw). A constant rather than a live
#: read, then and now: the old tool is read-only reference on one machine,
#: and a suite that read it would fail on every other one.
CEILING = 5500


def _counts(paths) -> dict[str, int]:
    """Count *paths* into ``code``, ``doc``, ``blank`` and ``raw`` lines.

    ``raw`` is every physical line and ``blank`` is every line with no
    non-whitespace character. ``doc`` is a non-blank line carrying a comment,
    plus every line spanned by a string token whose physical line *begins*
    with a quote or a ``#`` — docstrings and the standalone attribute-doc
    strings beside them, but not a string used as a value. ``code`` is every
    non-blank line left, so the three partition the file.
    """
    counts = {"code": 0, "doc": 0, "blank": 0, "raw": 0}
    for path in sorted(paths):
        lines = path.read_text(encoding="utf-8").splitlines()
        blanks = {n for n, line in enumerate(lines, 1) if not line.strip()}
        prose: set[int] = set()
        with tokenize.open(path) as handle:
            for tok in tokenize.generate_tokens(handle.readline):
                if tok.type == tokenize.COMMENT:
                    prose.add(tok.start[0])
                elif tok.type == tokenize.STRING and tok.line.strip().startswith(
                    ("#", '"', "'")
                ):
                    prose.update(range(tok.start[0], tok.end[0] + 1))
        prose -= blanks
        counts["raw"] += len(lines)
        counts["blank"] += len(blanks)
        counts["doc"] += len(prose)
        counts["code"] += len(lines) - len(blanks) - len(prose)
    return counts


def test_the_tool_stays_within_its_budget() -> None:
    """The budget is a number we set, not a number we measured — so say how
    far over it is, and where the number lives."""
    code = _counts(SRC.glob("*.py"))["code"]
    assert code <= CEILING, (
        f"src/fileplan/*.py is {code:,} lines of code against a budget of "
        f"{CEILING:,} — over by {code - CEILING:,}. The budget is `CEILING` in "
        f"this file, set deliberately rather than measured: either the lines "
        f"come out, or the number moves on a decision recorded beside it."
    )


def test_the_counter_tells_code_from_doc_from_blank(tmp_path: Path) -> None:
    """Without this the ceiling test passes forever by miscounting.

    Every line of the snippet has a class known by construction, including
    the one that decides the interesting case: a statement carrying a string
    value is **code**, because its physical line does not begin with a quote.
    """
    module = tmp_path / "snippet.py"
    module.write_text(
        '# a comment\n'
        '"""Module docstring, line one.\n'
        "Line two of it.\n"
        '"""\n'
        "VALUE = 1\n"
        '"""What VALUE means."""\n'
        "\n"
        'NAME = "not a docstring"\n',
        encoding="utf-8",
    )
    assert _counts([module]) == {"code": 2, "doc": 5, "blank": 1, "raw": 8}


def test_the_ceiling_names_where_it_came_from() -> None:
    """The checkable half of the constant's provenance.

    That the number is right is not checkable from here — the tree it was
    counted over is not present. That it is a value a test reads, rather
    than a number in prose nobody re-runs, is.
    """
    assert isinstance(CEILING, int)
    assert "CEILING" in inspect.getsource(test_the_tool_stays_within_its_budget)
    assert "src/fileplan/*.py" in __doc__
    assert "scripts/*.py" in __doc__


if __name__ == "__main__":
    # The counts as a thing that runs, matching `test_prose.py` next door:
    # The rule is to read this rather than quote a number at it.
    counts = _counts(SRC.glob("*.py"))
    print(counts, "headroom", CEILING - counts["code"])
