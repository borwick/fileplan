"""Staleness: how long ago anybody was near an item, read out of git.

A state opts into the `dated` capability, and every row there carries
`stale-days`. The field is the whole days between the item file's last commit
and today. Nothing is stored to make it.

Any commit touching the file resets the count, so `stale-days` says "days
since anybody was near this" rather than "days since the judgment". An
uncommitted edit does not reset it. The value is `None` wherever git does not
answer.

Staleness reports and never gates.

See docs/method.md#stale-days
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Sequence

from dulwich.errors import NotGitRepository
from dulwich.object_store import tree_lookup_path
from dulwich.objects import Commit
from dulwich.repo import Repo

from fileplan.declaration import DATED, STALE_KEYS

# The import runs one way: this module imports `fileplan.declaration`, so
# `fileplan.declaration` may not import this module.

#: The capability a state opts into. Imported rather than re-spelled.
NAME = DATED

#: The row field it gives: whole days since the item file's last commit.
DAYS = STALE_KEYS[0]

#: The row fields derived here, for the refusals in `fileplan.declaration`
#: that read a tuple rather than naming a key.
DERIVED = (DAYS,)


def days(committed: dt.date | None, today: dt.date) -> int | None:
    """Whole days between `committed` and `today`. Pure.

    `None` in is `None` out: git not answering is not an age of zero, and a
    zero would read as "committed today". A commit dated in the future comes
    back negative rather than clamped, a clock that disagrees with the tree
    being a real defect.
    """
    if committed is None:
        return None
    return (today - committed).days


def ages(
    root: Path, filed: Sequence[tuple[str, Path]], today: dt.date
) -> dict[str, int]:
    """`filed` as slug → `days`, for the ones git can answer about.

    The whole git read, and the only impure thing in this module. A slug git
    cannot answer about is absent rather than mapped to `None`, so the caller
    spells the absence once rather than this deciding how a row prints.

    Three steps, so the common cases stay cheap: a repo discovery, where a
    tree that is not a repo yields `{}` and nothing raises; a HEAD tree lookup
    per path, so a new item filed today is not a walk of the whole history;
    and one walker per remaining path, stopping at the first commit that
    touched it.

    Paths are taken relative to the repo root, which need not be the
    declaration root. Both sides are resolved, because a directory can be
    reached by more than one path: a synced or symlinked tree, or a `/tmp`
    that is itself a symlink.

    The cost, named: one walker per dated item. A single walk inspecting every
    path at once is the optimisation if a consumer ever has thousands of
    items; it is recorded here rather than built, because n is tens.
    """
    if not filed:
        return {}
    try:
        repo = Repo.discover(str(root))
    except NotGitRepository:
        return {}
    with repo:
        try:
            head = repo[repo.head()]
        except KeyError:
            # An unborn HEAD: every file is "never committed", nothing to
            # walk.
            return {}
        base = Path(repo.path).resolve()
        found: dict[str, int] = {}
        for slug, path in filed:
            relative = _within(base, path)
            if relative is None:
                continue
            try:
                tree_lookup_path(repo.get_object, head.tree, relative)
            except KeyError:
                continue
            last = _committed(repo, relative)
            age = days(_day(last) if last is not None else None, today)
            if age is not None:
                found[slug] = age
    return found


def _within(base: Path, path: Path) -> bytes | None:
    """`path` as git spells it — posix, relative to `base`, as bytes — or
    `None` where it is not under the repo at all."""
    try:
        relative = path.resolve().relative_to(base)
    except ValueError:
        return None
    return relative.as_posix().encode("utf-8")


def _committed(repo: Repo, relative: bytes) -> Commit | None:
    """The last commit touching `relative`, or `None`.

    The commit rather than its date, because which timezone a day is counted
    in is one question and `_day` is where it is answered.
    """
    for entry in repo.get_walker(paths=[relative], max_entries=1):
        return entry.commit
    return None


def _day(commit: Commit) -> dt.date:
    """The day `commit` was authored.

    Author date rather than committer date: a rebase rewrites every committer
    date at once and would silently reset the whole tree's staleness. In the
    author's own timezone, because "the day they did it" is what a date means.
    """
    return dt.datetime.fromtimestamp(
        commit.author_time, _zone(commit.author_timezone)
    ).date()


def _zone(offset: int | None) -> dt.timezone:
    """An author's recorded offset as a timezone, or UTC where it is not one.

    A hand-written commit object can carry an offset `datetime.timezone` will
    not take. Falling back reads the date in UTC, which is a day that exists;
    refusing would break a whole listing over one commit.
    """
    try:
        return dt.timezone(dt.timedelta(seconds=offset or 0))
    except ValueError:
        return dt.timezone.utc
