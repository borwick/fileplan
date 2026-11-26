"""Point the whole suite at the fixture declaration, not at the repo's own.

This runs at collection, before any test module imports the package. It uses
``setdefault`` so an operator can still aim the suite somewhere else from the
outside.
"""

import datetime as dt
import os
from pathlib import Path

import pytest
from dulwich.repo import Repo

from fileplan.declaration import Declaration, load

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

#: Who every commit the suite writes is by.
GARDENER = b"A Gardener <gardener@example.invalid>"


def copy_fixture(into: Path, plan: str | None = None) -> Path:
    """Copy `FIXTURE_FILES` into `into` and return its `plan.toml`, written
    as `plan` when one is given."""
    for name in FIXTURE_FILES:
        (into / name).write_text((FIXTURES / name).read_text())
    if plan is not None:
        (into / "plan.toml").write_text(plan)
    return into / "plan.toml"


def made_tree(into: Path) -> Declaration:
    """Copy the fixture declaration into `into`, make every declared state's
    directory, and return the declaration loaded from there. Its root is what
    a state's `path` resolves against, so it cannot be loaded from where the
    fixture lives."""
    copy_fixture(into)
    declaration = load(into / "plan.toml")
    for state in declaration.states.values():
        (into / state.path).mkdir(parents=True)
    return declaration


def cli_tree(into: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A `made_tree` the CLI discovers the way an operator's would: cwd plus
    the environment override, both pointed at it."""
    made_tree(into)
    monkeypatch.setenv("FILEPLAN_PLAN_TOML", str(into / "plan.toml"))
    monkeypatch.chdir(into)
    return into


def archived(declaration: Declaration, text: str) -> None:
    """Rewrite the archive the fixture's numbered state, `orchard`, names."""
    path = declaration.root / declaration.states["orchard"].archive
    path.write_text(text, encoding="utf-8")


def floored(tree: Declaration, first: int) -> Declaration:
    """``tree`` reloaded with `orchard`'s register declaring a floor.

    Written into the tmp copy rather than into ``tests/fixtures/plan.toml``:
    absence is the shape every other test here is about, and a fixture
    carrying a floor would make every register test read against 192.
    """
    source = tree.source
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            'archive           = "orchard-archive.md"',
            f'archive           = "orchard-archive.md"\nfirst-number      = {first}',
        ),
        encoding="utf-8",
    )
    return load(source)


def unclaimed(plan: Path) -> Path:
    """Rewrite the declaration at `plan` to claim nothing, and return it. The
    state stays, so every `from`/`to` still resolves and the capability is
    the only difference.

    Both halves go together — the state's opt-in and the `claims = true` on
    the verbs that take one — because either alone refuses at load.
    """
    plan.write_text(
        plan.read_text()
        .replace('capabilities = ["claimed"]\n', "")
        .replace("claims = true\n", "")
    )
    return plan


def staked(plan: Path) -> Path:
    """Add `stake` to the declaration at `plan`, and return it: an `edit`
    from `orchard` that sets `after` and `pest`, the shape that sets what a
    tree waits on where it stands. Its `doc` heading is added to the copied
    `method.md` beside it.

    Written into the tmp copy rather than into ``tests/fixtures/plan.toml``,
    because the fixture's order and help lists are pinned elsewhere.
    """
    plan.write_text(
        plan.read_text() + "\n[transitions.stake]\n"
        'kind = "edit"\n'
        'doc  = "method.md#stake"\n'
        'help = "Stake a tree: say what it waits on, and what is on it."\n'
        'from = "orchard"\n'
        'sets = ["after", "pest"]\n'
    )
    method = plan.parent / "method.md"
    method.write_text(method.read_text() + "\n## stake\n")
    return plan


def commit_files(root: Path, paths: list[str], when: dt.datetime) -> None:
    """Stage `paths` (relative to `root`) and commit them as `GARDENER`,
    authored at `when` in its own offset, in the repo at `root`, made if
    there is none yet."""
    started = Repo(str(root)) if (root / ".git").exists() else Repo.init(str(root))
    with started as repo:
        worktree = repo.get_worktree()
        worktree.stage([path.encode() for path in paths])
        worktree.commit(
            b"filed",
            committer=GARDENER,
            author=GARDENER,
            author_timestamp=int(when.timestamp()),
            author_timezone=int(when.utcoffset().total_seconds()),
            commit_timestamp=int(when.timestamp()),
            commit_timezone=0,
        )


@pytest.fixture
def declaration() -> Declaration:
    """The fixture declaration, loaded from where it lives."""
    return load(FIXTURE)


@pytest.fixture(autouse=True)
def _no_declared_pid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test from an environment naming no declared identity
    variable, so a real ``GREENHOUSE_PID`` in the operator's shell cannot
    decide a result."""
    for name in DECLARED:
        monkeypatch.delenv(name, raising=False)
