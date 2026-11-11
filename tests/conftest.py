"""Point the whole suite at the fixture declaration, not at the repo's own.

This runs at collection, before any test module imports the package. It uses
``setdefault`` so an operator can still aim the suite somewhere else from the
outside.
"""

import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "tests" / "fixtures"
FIXTURE = FIXTURES / "plan.toml"

#: The worked example, the declaration fileplan ships for a reader to copy.
#: Every test that grades the product against a real declaration reads this
#: one: the vocabulary, the contracts, the orphans and the self-load. This
#: repo's own `plan.toml` at the root is a different file with a different
#: job, and a built tree does not have it.
EXAMPLE = REPO / "examples" / "plan.toml"

os.environ.setdefault("FILEPLAN_PLAN_TOML", str(FIXTURE))


#: Every file a tmp-tree copy of the fixture declaration needs beside it: the
#: declaration, the document its `doc =` pointers resolve against, and the
#: archive the `numbered` register reads. Every one of them is graded at
#: **every** invocation, so a copy short of one refuses rather than quietly
#: running.
FIXTURE_FILES = (
    "plan.toml",
    "method.md",
    "orchard-archive.md",
)

#: The fixture's pending bullets: `orchard`'s, and `propagator`'s, whose
#: vocabulary is its own down to the marker, so the name form is shown to be
#: the state's business.
UNPRUNED = "**unpruned — Say what the rest of the training is.**"
UNSTRUCK = "**unstruck — Say what the rest of the batch is.**"

#: The record a deleting verb is given.
RECORD_TEXT = "What it was, and why it came down."

#: The identity variables the fixture declares, in its order.
DECLARED = ("GREENHOUSE_PID", "SPROUT_PID")


def copy_fixture(into: Path, plan: str | None = None) -> Path:
    """Copy `FIXTURE_FILES` into `into` and return its `plan.toml`, written
    as `plan` when one is given."""
    for name in FIXTURE_FILES:
        (into / name).write_text((FIXTURES / name).read_text())
    if plan is not None:
        (into / "plan.toml").write_text(plan)
    return into / "plan.toml"


@pytest.fixture(autouse=True)
def _no_declared_pid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test from an environment naming no declared identity
    variable, so a real ``GREENHOUSE_PID`` in the operator's shell cannot
    decide a result."""
    for name in DECLARED:
        monkeypatch.delenv(name, raising=False)
