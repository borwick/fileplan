"""What a stranger installs: the wheel, the version, and no tracebacks.

Everything here grades an **artifact** rather than behaviour — the built
distribution, `pyproject.toml`, and the two entry points a stranger reaches
after `pip install fileplan`. That is the same exception `test_docs.py` claims:
there is only one of these, and grading a copy would prove nothing.

Four subjects.

* **The wheel.** Building and installing are cheap — `uv build` is well under a
  second and `uvx --from <wheel>` about one — so what 8-1 proved by hand is a
  control here rather than pasted output that rots. It builds from the sdist,
  so a file missing from either is missing from both.
* **The version, declared once.** The old backlog carried "click's version
  declared once" as a behaviour to re-pin. It has two teeth, because there are
  two things that can be declared twice: the *number* (`pyproject.toml`, read
  back through installed metadata — no literal and no `__version__` under
  `src/`) and the *option* (one `click.version_option` call, shared by the
  group and the answer that precedes a declaration). Both extractors have a
  mutation check: a guard that could never go red proves nothing.
* **The metadata a project page is built from.** The licence expression, the
  file behind it, the repository links and the classifiers, read off the built
  wheel. A stranger meets this package as a PyPI page before they meet the
  tool, and a page with an unknown licence and no way back to the source is a
  packaging defect nothing else here would catch.
* **No traceback outside a git repo.** The other inherited behaviour. The git
  reader answers `None` where git does not answer, and `test_stale.py` pins
  that at the unit. What is left is the operator's contract, and a traceback is a thing a *process* prints — so this drives the
  console script in a tree that is not a repo and has none above it.

`docs/method.md#the-version` is where the one-declaration rule these controls
exist to keep honest is written down.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

from conftest import FIXTURE_FILES
from fileplan.declaration import PLAN_TOML_ENV, PLAN_TOML_NAME, load

REPO = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SRC = REPO / "src"

#: What the starter declaration calls the verb that files, so the stranger's
#: walk can be driven without spelling this repo's own vocabulary.
CAPTURE = "capture"

#: The fixture's own walk into the one state that asks git something: the
#: `dated` state, reached in three moves. Spelled out because these are the
#: **fixture's** verbs, which the suite names freely — the rule against naming
#: a verb is over `src/` and the shipped skills, where a verb's name would be
#: per-verb code.
INTO_THE_GIT_READING_STATE = (
    ["sprout", "A seedling", "--body", "Prose.", "--cultivar", "heirloom"],
    ["transplant", "a-seedling"],
    ["harvest", "a-seedling"],
)


def without_the_override() -> dict[str, str]:
    """The environment a stranger has: no `FILEPLAN_PLAN_TOML` pointing at the
    suite's fixture. `conftest` sets it for every other module here."""
    return {k: v for k, v in os.environ.items() if k != PLAN_TOML_ENV}


@pytest.fixture(scope="module")
def wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One built wheel, shared: the build is cheap but not free, and every
    control below wants the same artifact rather than its own."""
    out = tmp_path_factory.mktemp("dist")
    subprocess.run(
        ["uv", "build", "--wheel", "--no-sources", "-o", str(out)],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    built = sorted(out.glob("*.whl"))
    assert len(built) == 1, built
    return built[0]


# --------------------------------------------------------------------------
# The wheel
# --------------------------------------------------------------------------


def test_uv_build_yields_one_wheel(wheel: Path) -> None:
    """The packaging done line section 1 left open."""
    assert wheel.suffix == ".whl"
    assert wheel.stat().st_size > 0


def test_the_wheel_carries_what_the_tool_reads_at_runtime(wheel: Path) -> None:
    """`py.typed` and the whole starter tree. `uv_build` ships the package
    directory without an include list to forget, which is exactly why this is
    worth asserting: nothing would say so if it stopped."""
    carried = set(zipfile.ZipFile(wheel).namelist())

    assert "fileplan/py.typed" in carried
    shipped = {
        f"fileplan/starter/{path.relative_to(SRC / 'fileplan' / 'starter')}"
        for path in (SRC / "fileplan" / "starter").rglob("*")
        if path.is_file()
    }
    assert shipped, "the starter tree is empty, so this guard proves nothing"
    assert shipped <= carried


def test_the_wheel_carries_the_interpreter_skills(wheel: Path) -> None:
    """The skills are the **interpreter** (`docs/method.md#the-skills`), and a
    consumer's harness reads them out of a directory this tool knows nothing
    about — so the package is the only thing that can carry them to a stranger.
    The repo keeps one home for each: the real files are here, and
    `.claude/skills` is a symlink at them. This is the control that goes red if
    that link is ever made the other way round, when the wheel would carry an
    empty directory and nobody would notice until an install was tried."""
    carried = set(zipfile.ZipFile(wheel).namelist())

    shipped = {
        f"fileplan/skills/{path.relative_to(SRC / 'fileplan' / 'skills')}"
        for path in (SRC / "fileplan" / "skills").rglob("*.md")
    }
    assert shipped, "no skills ship, so this guard proves nothing"
    assert shipped <= carried


def test_every_link_in_a_shipped_skill_resolves_inside_the_wheel(wheel: Path) -> None:
    """A skill copied out of an install has the wheel and nothing else, so a
    relative link has to land on a wheel member, and a `docs/` document is
    never one. Graded against the built wheel's file list, not the source
    tree, because the source tree has `docs/` and would pass either way."""
    archive = zipfile.ZipFile(wheel)
    carried = set(archive.namelist())
    skills = [name for name in carried if name.endswith("/SKILL.md")]
    assert skills, "the wheel carries no skills, so this guard proves nothing"
    linked = 0
    for name in skills:
        text = archive.read(name).decode()
        assert not re.search(r"docs/[A-Za-z0-9_./-]+\.md", text), name
        for target in re.findall(r"\]\(([^)#:]+)(?:#[^)]*)?\)", text):
            linked += 1
            resolved = os.path.normpath(f"{os.path.dirname(name)}/{target}")
            assert resolved in carried, (name, target)
    assert linked, "no skill links anywhere, so the resolution half proves nothing"


def test_the_skills_flag_prints_a_directory_that_holds_them(
    wheel: Path, tmp_path: Path
) -> None:
    """`--skills` answers outside a plan tree, like `--version`, and out of the
    install rather than out of the source tree — which is the half that matters:
    `uv tool install` puts fileplan in a virtual environment of its own, so
    asking Python where the package is finds nothing. One line, and a real
    directory with a skill in it."""
    result = subprocess.run(
        ["uvx", "--from", str(wheel), "fileplan", "--skills"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=without_the_override(),
    )

    assert result.returncode == 0, result.stderr
    printed = result.stdout.splitlines()
    assert len(printed) == 1, printed
    installed = Path(printed[0])
    assert installed.is_dir()
    shipped = {
        path.relative_to(SRC / "fileplan" / "skills")
        for path in (SRC / "fileplan" / "skills").rglob("*.md")
    }
    assert shipped, "no skills ship, so this guard proves nothing"
    for relative in shipped:
        assert (installed / relative).is_file(), relative


def test_the_installed_wheel_prints_the_transitions(wheel: Path) -> None:
    """The done line's own sentence, run against this repo's declaration."""
    result = subprocess.run(
        ["uvx", "--from", str(wheel), "fileplan"],
        cwd=REPO,
        capture_output=True,
        text=True,
        env=without_the_override(),
    )

    assert result.returncode == 0, result.stderr
    declared = load(REPO / PLAN_TOML_NAME).transitions
    for name in declared:
        assert name in result.stdout


def test_the_installed_wheel_scaffolds_and_then_runs(
    wheel: Path, tmp_path: Path
) -> None:
    """The stranger's whole walk, from a directory with nothing in it."""
    environment = without_the_override()

    assert subprocess.run(
        ["uvx", "--from", str(wheel), "fileplan", "init", "."],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=environment,
    ).returncode == 0

    filed = subprocess.run(
        ["uvx", "--from", str(wheel), "fileplan", CAPTURE, "A thing", "--body", "Prose."],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert filed.returncode == 0, filed.stderr
    assert (tmp_path / PLAN_TOML_NAME).is_file()
    state = next(iter(load(tmp_path / PLAN_TOML_NAME).states.values()))
    assert list((tmp_path / state.path).glob("*.md"))


def test_the_module_entry_point_reaches_the_same_cli(wheel: Path) -> None:
    """`python -m fileplan` and the console script are one CLI. Run out of the
    installed wheel rather than the source tree, because that is where a
    missing `__main__` would actually bite."""
    result = subprocess.run(
        ["uvx", "--from", str(wheel), "python", "-m", "fileplan", "--version"],
        capture_output=True,
        text=True,
        env=without_the_override(),
    )

    assert result.returncode == 0, result.stderr
    assert declared_version() in result.stdout


# --------------------------------------------------------------------------
# The project page: what PyPI reads off the wheel
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def metadata(wheel: Path) -> str:
    """The wheel's own `METADATA`, which is the whole of what a project page
    is built from. Read out of the built artifact rather than off
    `pyproject.toml`, because the question here is what the backend emitted."""
    carried = zipfile.ZipFile(wheel)
    (name,) = [one for one in carried.namelist() if one.endswith("/METADATA")]
    return carried.read(name).decode("utf-8")


def test_the_wheel_declares_the_licence(wheel: Path, metadata: str) -> None:
    """The expression, the file it names, and the text itself.

    All three, because an expression with no file behind it is a claim with no
    notice: PyPI would print `BSD-3-Clause` beside a package carrying nobody's
    copyright. `uv build` refuses a `license-files` glob that matches nothing,
    so the middle line is what makes the third reachable at all."""
    lines = metadata.splitlines()
    assert "License-Expression: BSD-3-Clause" in lines

    named = [one.removeprefix("License-File: ") for one in lines
             if one.startswith("License-File: ")]
    assert "LICENSE" in named, named

    carried = zipfile.ZipFile(wheel)
    (path,) = [one for one in carried.namelist() if one.endswith("/LICENSE")]
    assert "BSD 3-Clause" in carried.read(path).decode("utf-8")


def test_the_wheel_carries_the_project_urls(metadata: str) -> None:
    """Every `[project.urls]` entry, as a `Project-URL` line.

    The table is read rather than repeated, so a URL edited in one place
    cannot pass here while the page shows the other. It is asserted non-empty
    first, because a guard over an empty table grades nothing and would stay
    green through the whole of the links being deleted."""
    urls = tomllib.loads((REPO / "pyproject.toml").read_text())["project"]["urls"]
    assert urls, "no project URLs are declared, so this guard proves nothing"

    lines = set(metadata.splitlines())
    missing = [
        f"Project-URL: {name}, {target}"
        for name, target in urls.items()
        if f"Project-URL: {name}, {target}" not in lines
    ]
    assert missing == [], missing


def test_no_license_classifier_rides_beside_the_expression(metadata: str) -> None:
    """The PEP 639 trap, by name.

    `License ::` classifiers are deprecated and must not be uploaded beside a
    `License-Expression`; the build refuses one. It is the kind of line
    somebody adds out of habit while adding the others, so it is asserted
    rather than remembered. Non-empty first, for the reason above."""
    declared = [one for one in metadata.splitlines()
                if one.startswith("Classifier: ")]
    assert declared, "no classifiers are declared, so this guard proves nothing"

    forbidden = [one for one in declared if one.startswith("Classifier: License ::")]
    assert forbidden == [], forbidden


# --------------------------------------------------------------------------
# The version, declared once
# --------------------------------------------------------------------------


#: A version declared in `pyproject.toml`, at the top level of a table. The
#: extractor is deliberately dumber than a TOML parser: a second declaration
#: is a thing somebody *writes*, and a parser would silently keep the last one.
VERSION_LINE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)

#: A version spelled in the source: a `__version__`, or a literal handed to
#: click. Either would be a second answer to "what version is this".
VERSION_IN_SOURCE = re.compile(r'__version__|version\s*=\s*"\d')

#: The option, wherever it is constructed.
VERSION_OPTION = re.compile(r"click\.version_option\(")


def declared_version() -> str:
    """The one number `pyproject.toml` declares."""
    return tomllib.loads((REPO / "pyproject.toml").read_text())["project"]["version"]


def source() -> str:
    return "\n".join(
        path.read_text() for path in sorted(SRC.rglob("*.py"))
    )


def test_the_version_is_declared_in_exactly_one_place() -> None:
    """One number, in the file that owns it; one construction of the option,
    shared by the group and the answer that precedes a declaration."""
    assert len(VERSION_LINE.findall((REPO / "pyproject.toml").read_text())) == 1
    assert VERSION_IN_SOURCE.search(source()) is None
    assert len(VERSION_OPTION.findall(source())) == 1


def test_the_version_control_catches_a_second_declaration() -> None:
    """The mutation check on all three extractors. Each is fed the shape it
    exists to refuse, and must report it — a guard that matched nothing would
    pass the control above forever."""
    twice = 'version = "0.1.0"\n[tool.other]\nversion = "9.9.9"\n'
    assert len(VERSION_LINE.findall(twice)) == 2
    assert VERSION_IN_SOURCE.search('__version__ = "0.1.0"') is not None
    assert VERSION_IN_SOURCE.search('option(version = "0.1.0")') is not None
    assert len(VERSION_OPTION.findall("click.version_option(\nclick.version_option(")) == 2


def test_both_entry_points_report_the_number_pyproject_declares() -> None:
    """Moved here from `test_cli.py`, which asserted only that the word
    `fileplan` appeared. The number is the half that can drift."""
    for argv in (["fileplan"], [sys.executable, "-m", "fileplan"]):
        out = subprocess.run(
            [*argv, "--version"], capture_output=True, text=True, check=True
        )
        assert "fileplan" in out.stdout
        assert declared_version() in out.stdout


def test_the_version_answers_outside_a_plan_tree(tmp_path: Path) -> None:
    """A stranger's first command after installing. The number is a fact about
    the tool; which states exist is a fact about the workflow, and refusing the
    first because the second has no answer yet would read as a broken install.
    See docs/method.md#the-version."""
    result = subprocess.run(
        ["fileplan", "--version"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=without_the_override(),
    )

    assert result.returncode == 0
    assert declared_version() in result.stdout
    assert "ERROR:" not in result.stderr


def test_the_help_still_refuses_outside_a_plan_tree(tmp_path: Path) -> None:
    """The other half of the same decision, pinned so the arm cannot widen
    quietly. The help **is** the declaration — generated per declared
    transition — so outside a tree there is nothing to show, and the refusal
    names the way out instead."""
    result = subprocess.run(
        ["fileplan", "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env=without_the_override(),
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "fileplan init" in result.stderr


# --------------------------------------------------------------------------
# No traceback outside a git repo
# --------------------------------------------------------------------------


@pytest.fixture
def unversioned(tmp_path: Path) -> Path:
    """A fixture tree that is not a git repo, with items in the state that
    asks git something. `tmp_path` is under the system temp directory, which
    has no `.git` above it, so the reader is asked and cannot answer."""
    for name in FIXTURE_FILES:
        (tmp_path / name).write_text((FIXTURES / name).read_text())
    declaration = load(tmp_path / PLAN_TOML_NAME)
    for state in declaration.states.values():
        (tmp_path / state.path).mkdir(parents=True, exist_ok=True)
    assert not any((d / ".git").exists() for d in (tmp_path, *tmp_path.parents))

    environment = {
        **without_the_override(),
        PLAN_TOML_ENV: str(tmp_path / PLAN_TOML_NAME),
    }
    for argv in INTO_THE_GIT_READING_STATE:
        filed = subprocess.run(
            ["fileplan", *argv],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env=environment,
        )
        assert filed.returncode == 0, (argv, filed.stderr)

    # The reader must actually be asked, or the control below is vacuous:
    # nothing filed asks git nothing, and a null column would then prove only
    # that the tree was empty.
    dated = next(
        state for state in declaration.states.values() if "dated" in state.capabilities
    )
    assert list((tmp_path / dated.path).glob("*.md"))
    return tmp_path


def test_no_invocation_outside_a_git_repo_raises_a_traceback(
    unversioned: Path,
) -> None:
    """The inherited behaviour, at the operator's contract rather than the
    unit. The declaration's `dated` state is what puts the one git reader on
    the path, so a `NotGitRepository` escaping it would surface here as a
    traceback rather than as a null column."""
    environment = {
        **without_the_override(),
        PLAN_TOML_ENV: str(unversioned / PLAN_TOML_NAME),
    }
    reads = (["list"], ["list", "--json"], ["show", "--help"], ["next", "--help"])

    for argv in reads:
        result = subprocess.run(
            ["fileplan", *argv],
            cwd=unversioned,
            capture_output=True,
            text=True,
            env=environment,
        )
        assert result.returncode == 0, (argv, result.stderr)
        assert "Traceback" not in result.stderr, argv
        assert "NotGitRepository" not in result.stderr, argv

    document = subprocess.run(
        ["fileplan", "list", "--json"],
        cwd=unversioned,
        capture_output=True,
        text=True,
        env=environment,
    )
    json.loads(document.stdout)
