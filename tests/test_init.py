"""`fileplan init`: the starter tree, and what it refuses to write over.

The example declaration is the one artifact a consumer receives unmodified, so
the controls here are mostly about **identity**: that the bytes written are
the package's own, that they resolve through `importlib.resources` rather than
by walking up from a repo that will not be there after an install, and that
the tree those bytes make is one the real loader accepts and a declared verb
runs against. An unvalidated example is a policy path that rotted.

The mutation check is the other half. A guard that loads the shipped example
and passes could pass because the loader accepts anything, so one test breaks
a key in those same bytes and asserts the loader refuses.

`init` runs before the declaration loads, which is why the last test here is a
subprocess in an empty directory: that is where the arm in `main` actually
bites, and `main` called in-process is running under the suite's own
`FILEPLAN_PLAN_TOML`.
"""

from __future__ import annotations

import os
import re
import subprocess
from importlib import resources
from pathlib import Path

import pytest

from fileplan import scaffold
from fileplan.cli import SKILLS_FLAG, main
from fileplan.declaration import PLAN_TOML_ENV, PLAN_TOML_NAME, Refusal, load

REPO = Path(__file__).resolve().parent.parent

#: The starter declaration's own vocabulary — the four verbs of its loop and
#: the two states they run between. Named here rather than inlined: these are
#: the *example's* words, and a test asserting on them should say so.
CAPTURE = "capture"
QUEUE = "queue"
WORK = "work"
ARCHIVE = "archive"
INBOX = "inbox"
PLAN = "plan"

#: A comment line that is really a declaration: an assignment or a table
#: header, commented out in place. The starter used to teach every capability
#: this way, which put four lines in five of it beyond the funnel it declared.
COMMENTED_OUT = re.compile(r"^\s*#\s*(\[[\w.-]+\]|[\w-]+\s*=)")

#: One of the lines this pattern was written to catch, kept as the mutation
#: check on it: the guard below passes trivially if the pattern never fires.
WAS_COMMENTED_OUT = '# archive           = "docs/archive.md"'


@pytest.fixture
def installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fresh install, with the environment pointed at it the way an
    operator's cwd would be."""
    assert main(["init", str(tmp_path)]) == 0
    monkeypatch.setenv(PLAN_TOML_ENV, str(tmp_path / PLAN_TOML_NAME))
    monkeypatch.chdir(tmp_path)
    return tmp_path


# --------------------------------------------------------------------------
# What it writes
# --------------------------------------------------------------------------


def test_init_on_an_empty_directory_writes_a_tree_the_loader_accepts(
    tmp_path: Path,
) -> None:
    """The real loader, not a re-implementation of it: every `doc =` and
    `policy =` pointer is chased, so a starter naming a heading the shipped
    documents do not have refuses here."""
    assert main(["init", str(tmp_path)]) == 0

    declaration = load(tmp_path / PLAN_TOML_NAME)

    assert declaration.states and declaration.transitions
    for state in declaration.states.values():
        assert (tmp_path / state.path).is_dir()


def test_the_four_command_loop_runs_end_to_end_against_a_fresh_install(
    installed: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Log an idea, move it into the plan, work it, archive it — the ideal
    13-4 was opened on, run in the example's own vocabulary. A starter that
    could file and move but never close would be the loop with no end, which
    is what the funnel it replaced was."""
    assert main([CAPTURE, "A first thing", "--body", "Prose."]) == 0
    captured = installed / INBOX / "a-first-thing.md"
    assert captured.is_file()

    assert main([QUEUE, "a-first-thing"]) == 0
    queued = installed / PLAN / "a-first-thing.md"
    assert not captured.exists() and queued.is_file()

    assert main([WORK, "a-first-thing", "--status", "in progress"]) == 0

    capsys.readouterr()
    assert main(["list"]) == 0
    listed = capsys.readouterr().out
    assert "a-first-thing" in listed and "in progress" in listed

    assert main([ARCHIVE, "a-first-thing", "--record", "Done with it."]) == 0

    # The item file goes with the run, so the entry under its number is the
    # only thing left saying the number is taken.
    assert not queued.exists()
    assert "## 1. A first thing" in (installed / "docs" / "archive.md").read_text()


def test_the_shipped_example_is_copied_byte_for_byte(tmp_path: Path) -> None:
    """Verbatim is the whole decision: no templating, no substitution. This is
    what stops a later session growing a placeholder into it."""
    assert main(["init", str(tmp_path)]) == 0

    for name in (
        "plan.toml",
        "docs/method.md",
        "docs/procedures.md",
        "docs/archive.md",
    ):
        shipped = resources.files("fileplan").joinpath(f"{scaffold.STARTER}/{name}")
        assert (tmp_path / name).read_bytes() == shipped.read_bytes()


def test_the_starter_declares_no_capability_commented_out_in_place(
    tmp_path: Path,
) -> None:
    """What is live in the starter is the whole of what it teaches. The
    catalogue of every capability the tool has used to sit under the tables
    as commented lines, so four lines in five of the file were about a
    workflow it did not declare; the reference is that catalogue's home. A
    comment saying what a table means is fine — one that *is* a table, or an
    assignment, is the catalogue growing back."""
    assert main(["init", str(tmp_path)]) == 0

    offenders = [
        line
        for line in (tmp_path / PLAN_TOML_NAME).read_text().splitlines()
        if COMMENTED_OUT.match(line)
    ]

    assert not offenders, f"declared, then commented out: {offenders}"
    # The mutation check: a pattern that matches nothing would pass above.
    assert COMMENTED_OUT.match(WAS_COMMENTED_OUT)


def test_a_mutation_of_the_shipped_example_is_caught_by_the_loader(
    tmp_path: Path,
) -> None:
    """The mutation check on the guard above it. A control that loads the
    example and passes proves nothing unless the same loader, fed the same
    bytes with one key broken, refuses."""
    assert main(["init", str(tmp_path)]) == 0
    plan = tmp_path / PLAN_TOML_NAME
    plan.write_text(plan.read_text().replace("path = ", "paths = ", 1))

    with pytest.raises(Refusal) as refusal:
        load(plan)

    assert "path" in str(refusal.value)


def test_the_example_resolves_from_the_package_rather_than_the_repo(
    tmp_path: Path,
) -> None:
    """After `pip install fileplan` there is no repo to walk up from, so the
    lookup must go through `importlib.resources`. This goes red if somebody
    replaces it with a path relative to the source tree."""
    shipped = resources.files("fileplan").joinpath(
        f"{scaffold.STARTER}/{PLAN_TOML_NAME}"
    )
    assert shipped.is_file()

    # And nothing found by walking up from an installed tree would answer:
    # `init` writes into directories that have no repo above them at all.
    assert main(["init", str(tmp_path)]) == 0
    assert not any(
        (directory / PLAN_TOML_NAME).is_file() for directory in tmp_path.parents
    )


# --------------------------------------------------------------------------
# What it refuses, computing every refusal before the first write
# --------------------------------------------------------------------------


def test_init_over_an_existing_install_refuses_by_name_and_writes_nothing(
    installed: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = sorted(path.name for path in installed.iterdir())
    capsys.readouterr()

    assert main(["init", str(installed)]) == 2

    assert "already a fileplan install" in capsys.readouterr().err
    assert sorted(path.name for path in installed.iterdir()) == before


def test_init_under_an_existing_install_refuses_naming_the_one_it_found(
    installed: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Discovery walks up like git, so a nested declaration would shadow the
    tree above it — and shadowing is the failure nobody would guess, which is
    why the refusal names the file it found rather than only the directory."""
    nested = installed / "somewhere" / "deeper"
    nested.mkdir(parents=True)
    capsys.readouterr()

    assert main(["init", str(nested)]) == 2

    error = capsys.readouterr().err
    assert "under a tree that is already a fileplan install" in error
    assert str(installed / PLAN_TOML_NAME) in error
    assert list(nested.iterdir()) == []


def test_init_refuses_where_a_file_it_would_write_already_exists(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Not an install — there is no `plan.toml` — but a tree that already
    holds one of the documents. Refused before the first write, so the
    `plan.toml` that would have gone beside it is not there either."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "method.md").write_text("Mine.\n")

    assert main(["init", str(tmp_path)]) == 2

    assert "already exists" in capsys.readouterr().err
    assert (tmp_path / "docs" / "method.md").read_text() == "Mine.\n"
    assert not (tmp_path / PLAN_TOML_NAME).exists()


def test_init_refuses_where_a_state_directory_is_a_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The declaration says it is a directory and the tree says otherwise.
    Refused by name, before anything is written."""
    state = next(
        iter(load(REPO / "src/fileplan/starter" / PLAN_TOML_NAME).states.values())
    )
    (tmp_path / state.path).write_text("Not a directory.\n")

    assert main(["init", str(tmp_path)]) == 2

    assert "is a file, and the declaration names it as a directory" in (
        capsys.readouterr().err
    )
    assert not (tmp_path / PLAN_TOML_NAME).exists()


# --------------------------------------------------------------------------
# The tool's own word, and the tree it is for
# --------------------------------------------------------------------------


def test_a_transition_named_init_refuses_by_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The `RESERVED` half, pinned the way `release` is: one command cannot
    mean two things, and the refusal comes at group build rather than the
    first time somebody runs the verb."""
    assert main(["init", str(tmp_path)]) == 0
    plan = tmp_path / PLAN_TOML_NAME
    plan.write_text(plan.read_text().replace(f"[transitions.{CAPTURE}]", "[transitions.init]"))
    (tmp_path / "docs" / "method.md").write_text(
        (tmp_path / "docs" / "method.md").read_text() + "\n### init\n"
    )

    with pytest.raises(Refusal) as refusal:
        from fileplan.cli import _build_group

        _build_group(load(plan))

    assert "transitions.init takes the name of the scaffold" in str(refusal.value)


def test_outside_a_plan_tree_the_refusal_names_init(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A newcomer's first experience of the tool is this refusal, so the way
    out is in it. A way out you have to already know is hiding with extra
    steps."""
    monkeypatch.delenv(PLAN_TOML_ENV, raising=False)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(Refusal) as refusal:
        load()

    assert "fileplan init" in str(refusal.value)


def test_the_skills_flag_refuses_an_extra_argument_before_the_declaration_loads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--skills` takes nothing else, and the refusal has to reach the operator
    from *outside* a plan tree — the arm runs before the declaration loads, so a
    refusal that only fired where a `plan.toml` exists would be the wrong one.
    Found by section 10's pysmelly pass rather than by a check: the arm shipped
    with no test reaching it, which is the shape `docs/method.md#the-skills`'s
    "answers before the declaration loads" makes easy to leave uncovered."""
    monkeypatch.delenv(PLAN_TOML_ENV, raising=False)
    monkeypatch.chdir(tmp_path)

    assert main([SKILLS_FLAG, "extra"]) == 2

    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err.startswith("ERROR: ")
    assert "takes nothing else" in printed.err


def test_init_runs_outside_a_plan_tree_through_the_console_script(
    tmp_path: Path,
) -> None:
    """Where the arm in `main` actually bites: a real invocation in a
    directory every other command refuses in. rc 0, and no traceback."""
    environment = {
        key: value for key, value in os.environ.items() if key != PLAN_TOML_ENV
    }

    refused = subprocess.run(
        ["fileplan", "list"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=environment,
    )
    assert refused.returncode == 2
    assert "fileplan init" in refused.stderr

    result = subprocess.run(
        ["fileplan", "init"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=environment,
    )

    assert result.returncode == 0
    assert "Traceback" not in result.stderr
    assert (tmp_path / PLAN_TOML_NAME).is_file()
    assert str(tmp_path / PLAN_TOML_NAME) not in result.stdout
    assert PLAN_TOML_NAME in result.stdout.splitlines()
