"""Staleness: the arithmetic, and the one git read under it.

The pure table comes first and takes no ``tmp_path``: what a number *means*
is graded without a tree.

The git half builds its repos **in-process with dulwich**, the library the
tool reads them with. No subprocess runs and no clock is mocked: a commit is
written with an explicit ``author_timestamp`` and `fileplan.stale.ages` is
handed an explicit ``today``, so "five days ago" is arithmetic between two
stated values, not a guess about when the suite runs.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from conftest import GARDENER
from dulwich.index import commit_tree
from dulwich.objects import Blob, Commit
from dulwich.repo import Repo

from fileplan import stale

#: The day every backdated commit is measured against. Any fixed date will do.
TODAY = dt.date(2026, 9, 4)


# --------------------------------------------------------------------------
# The arithmetic: pure, no tmp_path
# --------------------------------------------------------------------------


def test_days_is_whole_days_between_the_commit_and_today() -> None:
    assert stale.days(dt.date(2026, 8, 30), TODAY) == 5


def test_a_file_committed_today_is_zero_days_stale() -> None:
    """Zero is a real answer, committed today, so git having *no* answer may
    not also be zero."""
    assert stale.days(TODAY, TODAY) == 0


def test_no_commit_is_none_rather_than_zero() -> None:
    """`None` in is `None` out. A zero would read as "committed today" for a
    file nobody has ever committed."""
    assert stale.days(None, TODAY) is None


def test_a_commit_dated_in_the_future_is_negative_rather_than_clamped() -> None:
    """A clock that disagrees with the tree is a real defect, and clamping to
    zero would hide it behind a number that looks ordinary."""
    assert stale.days(dt.date(2026, 9, 7), TODAY) == -3


# --------------------------------------------------------------------------
# The git read: repos built in-process, with the library the tool uses
# --------------------------------------------------------------------------


def started(root: Path) -> Repo:
    root.mkdir(parents=True, exist_ok=True)
    return Repo.init(str(root))


def write(root: Path, name: str, text: str = "hello") -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def noon(ago: int) -> int:
    """Noon UTC ``ago`` days before `TODAY`, as a timestamp: the date the tool
    reads is that day and no other, whatever zone the suite runs in."""
    return int(
        dt.datetime.combine(
            TODAY - dt.timedelta(days=ago), dt.time(12), tzinfo=dt.UTC
        ).timestamp()
    )


def commit(repo: Repo, *names: str, ago: int, message: bytes = b"a commit") -> None:
    """Stage ``names`` and commit them, authored at `noon` ``ago`` days
    before `TODAY`."""
    when = noon(ago)
    worktree = repo.get_worktree()
    worktree.stage([name.encode("utf-8") for name in names])
    worktree.commit(
        message,
        committer=GARDENER,
        author=GARDENER,
        author_timestamp=when,
        author_timezone=0,
        commit_timestamp=when,
        commit_timezone=0,
    )


def test_a_file_committed_n_days_ago_reads_n(tmp_path: Path) -> None:
    with started(tmp_path) as repo:
        path = write(tmp_path, "plan/a-section.md")
        commit(repo, "plan/a-section.md", ago=5)
    assert stale.ages(tmp_path, [("a-section", path)], TODAY) == {"a-section": 5}


def test_a_file_git_has_never_seen_is_absent_and_so_reads_null(
    tmp_path: Path,
) -> None:
    """The ordinary new-item case: filed today, not yet committed. It is
    **absent** from the mapping rather than mapped to `None`, so the row layer
    spells the absence once."""
    with started(tmp_path) as repo:
        committed = write(tmp_path, "plan/a-section.md")
        commit(repo, "plan/a-section.md", ago=5)
        fresh = write(tmp_path, "plan/b-section.md")
    found = stale.ages(
        tmp_path, [("a-section", committed), ("b-section", fresh)], TODAY
    )
    assert found == {"a-section": 5}


def test_a_tree_that_is_not_a_repo_answers_about_nothing(tmp_path: Path) -> None:
    """A consumer's tree need not be in git. Nothing raises,
    and every value the row layer builds from this is `null`."""
    path = write(tmp_path, "plan/a-section.md")
    assert stale.ages(tmp_path, [("a-section", path)], TODAY) == {}


def test_a_repo_with_no_commits_at_all_answers_about_nothing(
    tmp_path: Path,
) -> None:
    """An unborn HEAD. There is no tree to look a path up in, and no history
    to walk."""
    with started(tmp_path):
        path = write(tmp_path, "plan/a-section.md")
    assert stale.ages(tmp_path, [("a-section", path)], TODAY) == {}


def test_a_second_commit_to_the_file_resets_it(tmp_path: Path) -> None:
    """The last commit, not the first: the number says *days since anybody
    was near this*."""
    with started(tmp_path) as repo:
        path = write(tmp_path, "plan/a-section.md")
        commit(repo, "plan/a-section.md", ago=30)
        assert stale.ages(tmp_path, [("a-section", path)], TODAY) == {"a-section": 30}
        write(tmp_path, "plan/a-section.md", "hello again")
        commit(repo, "plan/a-section.md", ago=2, message=b"touched")
    assert stale.ages(tmp_path, [("a-section", path)], TODAY) == {"a-section": 2}


def test_a_commit_touching_another_file_leaves_this_one_alone(
    tmp_path: Path,
) -> None:
    """One walker per path, stopping at the first commit that touched *that*
    file — so a busy tree does not read as freshly tended everywhere."""
    with started(tmp_path) as repo:
        old = write(tmp_path, "plan/a-section.md")
        write(tmp_path, "plan/b-section.md")
        commit(repo, "plan/a-section.md", "plan/b-section.md", ago=30)
        write(tmp_path, "plan/b-section.md", "hello again")
        commit(repo, "plan/b-section.md", ago=1, message=b"only b")
    assert stale.ages(tmp_path, [("a-section", old)], TODAY) == {"a-section": 30}


def test_an_uncommitted_edit_does_not_reset_it(tmp_path: Path) -> None:
    """The field counts commits, not keystrokes."""
    with started(tmp_path) as repo:
        path = write(tmp_path, "plan/a-section.md")
        commit(repo, "plan/a-section.md", ago=9)
        write(tmp_path, "plan/a-section.md", "edited but not committed")
    assert stale.ages(tmp_path, [("a-section", path)], TODAY) == {"a-section": 9}


def test_paths_are_taken_relative_to_the_repo_not_the_declaration_root(
    tmp_path: Path,
) -> None:
    """A `plan.toml` may sit in a subdirectory of the checkout, so the lookup
    is relative to the repo root — which `Repo.discover` finds by walking up
    from the root it is handed."""
    with started(tmp_path) as repo:
        path = write(tmp_path, "workflow/plan/a-section.md")
        commit(repo, "workflow/plan/a-section.md", ago=4)
    assert stale.ages(tmp_path / "workflow", [("a-section", path)], TODAY) == {
        "a-section": 4
    }


def test_a_file_outside_the_repo_is_absent(tmp_path: Path) -> None:
    """Git has nothing to say about a file outside the repo, and saying
    nothing is `null`, not a refusal."""
    with started(tmp_path / "checkout") as repo:
        write(tmp_path / "checkout", "plan/a-section.md")
        commit(repo, "plan/a-section.md", ago=1)
    outside = write(tmp_path / "elsewhere", "a-section.md")
    assert stale.ages(tmp_path / "checkout", [("a-section", outside)], TODAY) == {}


def test_nothing_filed_asks_git_nothing(tmp_path: Path) -> None:
    """No dated items means no discovery, no HEAD lookup, and no walk, so the
    capability is free where nobody opts in."""
    assert stale.ages(tmp_path, [], TODAY) == {}


def raw_commit(
    repo: Repo, files: dict[str, bytes], parents: list[bytes], ago: int
) -> bytes:
    """A commit of exactly ``files`` on ``parents``, built as objects and
    pointed at by HEAD, so two branches can hold different trees with no
    worktree or index in between."""
    when = noon(ago)
    blobs = []
    for name, text in files.items():
        blob = Blob.from_string(text)
        repo.object_store.add_object(blob)
        blobs.append((name.encode("utf-8"), blob.id, 0o100644))
    made = Commit()
    made.tree = commit_tree(repo.object_store, blobs)
    made.parents = parents
    made.author = made.committer = GARDENER
    made.author_time = made.commit_time = when
    made.author_timezone = made.commit_timezone = 0
    made.message = b"a commit"
    repo.object_store.add_object(made)
    repo.refs[b"HEAD"] = made.id
    return made.id


def test_across_a_merge_each_file_follows_its_own_history(tmp_path: Path) -> None:
    """Past a merge, a file's history follows the parent its content came
    from, so a file changed only on the side branch reads that branch's
    commit, not the merge's. Above the merge one walk settles every file; a
    file it does not reach walks on alone from the merge."""
    with started(tmp_path) as repo:
        base = raw_commit(repo, {"a.md": b"a", "b.md": b"b"}, [], ago=30)
        side = raw_commit(repo, {"a.md": b"a2", "b.md": b"b"}, [base], ago=10)
        main = raw_commit(repo, {"a.md": b"a", "b.md": b"b2"}, [base], ago=5)
        merged = {"a.md": b"a2", "b.md": b"b2"}
        merge = raw_commit(repo, merged, [main, side], ago=3)
        raw_commit(repo, {**merged, "c.md": b"c"}, [merge], ago=1)
    filed = [(name, tmp_path / f"{name}.md") for name in ("a", "b", "c")]
    assert stale.ages(tmp_path, filed, TODAY) == {"a": 10, "b": 5, "c": 1}
