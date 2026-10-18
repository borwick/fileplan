"""Section 36's close-out: the consumer's decision-record workflow, end to end.

``tests/fixtures/decision-records.toml`` is the ``plan.toml`` the consumer
asked for, so this test is what grades the snippet it is handed. Each of its
five requests is declared there and run here: the numbered state with no way
out (36-1's exit rule has nothing to refuse), the required option and the
fixed value on `finalise` (36-1), the derived `superseded-by` (36-2), and
`decisions` left out of a plain `list` (36-3).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fileplan.cli import main
from fileplan.declaration import load

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "decision-records.toml"


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The consumer's tree: its `plan.toml`, and the empty archive its
    comment says to create."""
    (tmp_path / "plan.toml").write_text(FIXTURE.read_text())
    (tmp_path / "decisions-archive.md").write_text("")
    monkeypatch.setenv("FILEPLAN_PLAN_TOML", str(tmp_path / "plan.toml"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def rows(capsys: pytest.CaptureFixture[str], *given: str) -> dict[str, dict]:
    capsys.readouterr()
    assert main(["list", "--json", *given]) == 0
    return {row["slug"]: row for row in json.loads(capsys.readouterr().out)["rows"]}


def test_the_snippet_loads_with_no_refusal(tree: Path) -> None:
    declaration = load(tree / "plan.toml")
    assert declaration.unlisted == ("decisions",)
    assert list(declaration.transitions) == [
        "propose",
        "compact",
        "finalise",
        "deprecate",
    ]


def test_the_decision_record_workflow_runs_end_to_end(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["propose", "Use TOML", "--body", "The first take."]) == 0
    assert main(["propose", "Use TOML again", "--body", "The second take."]) == 0
    assert main(["compact", "use-toml-again", "--into", "use-toml"]) == 0
    assert "The second take." in (tree / "drafts" / "use-toml.md").read_text()
    assert not (tree / "drafts" / "use-toml-again.md").exists()

    # `decided` is required and set, so the option is required.
    capsys.readouterr()
    assert main(["finalise", "use-toml"]) == 2
    assert "--decided" in capsys.readouterr().err
    assert main(["finalise", "use-toml", "--decided", "2026-10-18"]) == 0
    head = rows(capsys, "--state", "decisions")["use-toml"]
    assert (head["number"], head["decided"], head["status"]) == (
        1,
        "2026-10-18",
        "accepted",
    )

    # Superseding is a set on the new record alone.
    assert main(["propose", "Use JSON", "--body", "B.", "--supersedes", "use-toml"]) == 0
    assert main(["finalise", "use-json", "--decided", "2026-10-18"]) == 0
    assert main(["deprecate", "use-json"]) == 0

    decided = rows(capsys, "--state", "decisions")
    assert decided["use-toml"]["superseded-by"] == ["use-json"]
    assert decided["use-toml"]["status"] == "accepted"
    assert decided["use-json"]["number"] == 2
    assert decided["use-json"]["status"] == "deprecated"
    assert decided["use-json"]["supersedes"] == ["use-toml"]

    assert rows(capsys) == {}
    assert main(["list"]) == 0
    err = capsys.readouterr().err
    assert "showing 0 of 2 items" in err
    assert "not listed: decisions (2). --state decisions lists them" in err
