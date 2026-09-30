"""The one traversal: what it finds, what it refuses, and the handle over it.

Against ``tests/fixtures/plan.toml``, never the repo's own — 1-1's rule. The
fixture is what makes two of these mean anything: `cold-frame` has ``path =
"beds/hardening-off"``, sharing neither its own name nor its last segment, so
a row reporting `cold-frame` is only possible by reading the declaration; and
`cultivar` has declared ``values``, so an ordered filter has something to
order by.

Only `items` touches a disk. The row layer, the filter table and the
comparison parser are pure, and their tests take no ``tmp_path``.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import os
import socket
from pathlib import Path
from typing import Any

import pytest
from dulwich.repo import Repo

from conftest import DERIVABLE_KEYS, FIXTURE_FILES

from fileplan import claim, depends, numbered, read, stale, subphase
from fileplan.declaration import Declaration, Refusal, load

# A sibling test module, not a package. Imported so that a stamp a record is
# taken at, and a pid that is honestly dead, have one home rather than a copy
# in every module that needs them.
from test_claim import DECLARED, TAKEN, exited

FIXTURES = Path(__file__).resolve().parent / "fixtures"

READY = '''\
+++
title = "A seedling"
cultivar = "heirloom"
tag = "spring"
+++

The body starts here.
'''


@pytest.fixture
def tree(tmp_path: Path) -> Declaration:
    """The fixture declaration copied into ``tmp_path``. **No directories are
    made**: a state whose directory does not exist yet is what several of
    these are about, and a fixture that pre-made them would hide it."""
    for name in FIXTURE_FILES:
        (tmp_path / name).write_text((FIXTURES / name).read_text())
    return load(tmp_path / "plan.toml")


@pytest.fixture(autouse=True)
def _no_declared_pid(monkeypatch: pytest.MonkeyPatch) -> None:
    """A real ``GREENHOUSE_PID`` in the operator's shell must not decide a
    result here: `fileplan.claim.holders` asks for this session's
    identity, and a malformed one would refuse the listing."""
    for name in DECLARED:
        monkeypatch.delenv(name, raising=False)


def file(declaration: Declaration, state: str, name: str, text: str = READY) -> Path:
    path = declaration.root / declaration.states[state].path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# The traversal
# --------------------------------------------------------------------------


def test_items_come_back_in_declared_state_order_then_slug(
    tree: Declaration,
) -> None:
    """`plan.toml` declares greenhouse, orchard, cold-frame in that order,
    which is not alphabetical. The workflow's order is the order work moves
    through, and the listing teaches it."""
    file(tree, "cold-frame", "c-seedling.md")
    file(tree, "orchard", "b-seedling.md")
    file(tree, "greenhouse", "z-seedling.md")
    file(tree, "greenhouse", "a-seedling.md")
    assert [one.path.stem for one in read.items(tree)] == [
        "a-seedling",
        "z-seedling",
        "b-seedling",
        "c-seedling",
    ]


def test_a_state_with_no_directory_is_empty_not_broken(tree: Declaration) -> None:
    """A fresh clone has filed nothing. Refusing would make the first run of
    every read fail on a tree that is simply new."""
    file(tree, "greenhouse", "a-seedling.md")
    assert not (tree.root / "orchard").exists()
    assert [one.path.stem for one in read.items(tree)] == ["a-seedling"]


def test_no_state_directory_at_all_is_an_empty_listing(tree: Declaration) -> None:
    assert read.items(tree) == []


def test_a_file_that_is_not_markdown_is_not_an_item(tree: Declaration) -> None:
    file(tree, "greenhouse", "a-seedling.md")
    (tree.root / "greenhouse" / "notes.txt").write_text("not an item")
    assert [one.path.stem for one in read.items(tree)] == ["a-seedling"]


def test_a_file_nested_below_a_state_directory_is_not_an_item(
    tree: Declaration,
) -> None:
    """A `path` is a literal directory, so the glob is flat. A file below one
    is in no state — which is 1-2's `state_at` rule, read from the other end."""
    file(tree, "greenhouse", "a-seedling.md")
    nested = tree.root / "greenhouse" / "notes" / "b-seedling.md"
    nested.parent.mkdir()
    nested.write_text(READY)
    assert [one.path.stem for one in read.items(tree)] == ["a-seedling"]


def test_a_broken_item_file_refuses_the_listing_naming_it(tree: Declaration) -> None:
    """Every `*.md` in a state directory is *claimed* to be an item, so one
    that is not refuses rather than being skipped. Silence would make a broken
    file look merely absent — 1-2's reason, and this is where it lands."""
    file(tree, "greenhouse", "a-seedling.md")
    broken = file(tree, "greenhouse", "b-seedling.md", "no head here at all\n")
    with pytest.raises(Refusal) as refusal:
        read.items(tree)
    assert str(broken.relative_to(tree.root)) in str(refusal.value)
    assert "is not a usable item file" in str(refusal.value)


def test_a_readme_in_a_state_directory_refuses(tree: Declaration) -> None:
    """A state's meaning has one home — the `doc =` section it points at — so
    a second copy filed beside the items is exactly the drift that has one
    home to prevent."""
    readme = file(tree, "greenhouse", "README.md", "# What goes in here\n")
    with pytest.raises(Refusal, match="is not a usable item file"):
        read.items(tree)
    assert readme.exists()


def test_two_broken_files_are_reported_in_one_refusal(tree: Declaration) -> None:
    """Collected and reported at once, like `shape_errors`. Fixing one file at
    a time because the tool only ever names one is the cost this avoids."""
    first = file(tree, "greenhouse", "a-seedling.md", "no head\n")
    second = file(tree, "orchard", "b-seedling.md", "no head either\n")
    with pytest.raises(Refusal) as refusal:
        read.items(tree)
    assert str(first.relative_to(tree.root)) in str(refusal.value)
    assert str(second.relative_to(tree.root)) in str(refusal.value)


def test_an_undeclared_head_key_refuses_the_listing(tree: Declaration) -> None:
    """The typo detector reaches the listing: `cultivarr = "heirloom"` is
    caught rather than read as an unset `cultivar`."""
    file(tree, "greenhouse", "a-seedling.md", '+++\ncultivarr = "heirloom"\n+++\n')
    with pytest.raises(Refusal, match="not a declared key"):
        read.items(tree)


# --------------------------------------------------------------------------
# The row layer
# --------------------------------------------------------------------------


def test_a_row_carries_every_declared_key_null_when_absent(
    tree: Declaration,
) -> None:
    """The shape a consumer writes against does not depend on which items
    happen to be filed."""
    file(tree, "greenhouse", "a-seedling.md")
    (row,) = read.rows(tree, read.items(tree))
    for key in tree.keys:
        assert key in row
    assert row["rootstock"] is None
    assert row["cultivar"] == "heirloom"


def test_a_rows_fields_are_in_a_fixed_order(tree: Declaration) -> None:
    """`position` comes straight after `state` — it is *where in the state*
    the item sits, which is location — and the claim's two come straight after
    it, for the same reason: who holds an item is a fact about its being in a
    claimed state. `sub-phases` follows them: it is counted off the item's own
    **body** rather than read out of its head, so it belongs with the other
    things that sit beside the declared keys rather than among them, and
    `next-sub-phase` comes straight after it because it is derived from those
    same bullets. All five are present because the fixture declares such states
    at all, not because this item is in one.

    `blocked-by` and `blocks` come after those two and before the declared
    keys, for the
    third version of the same argument: it is derived from the **tree** rather
    than read out of a head, so it belongs with the things that sit beside the
    declared keys rather than among them. Present because the fixture has a
    state that reads dependencies at all, not because this item is in one.

    `stale-days` comes straight after it, the argument a fourth time over a
    fact derived from **git**. Present because the fixture has a dated state
    at all — `cold-frame` — and `None` here because this seedling is in
    `greenhouse`, which does not opt in.

    The head-key capabilities come in `CAPABILITY_KEYS` order — `position`
    then `number` — because that is the one place the tool says which keys a
    state's capabilities give, and the row, the filters and the grading all
    read it rather than each keeping a list."""
    file(tree, "greenhouse", "a-seedling.md")
    (row,) = read.rows(tree, read.items(tree))
    assert list(row) == [
        "slug",
        "state",
        "position",
        "number",
        *claim.CLAIM_KEYS,
        subphase.NAME,
        subphase.LEFT,
        subphase.NEXT,
        depends.BLOCKED,
        depends.BLOCKS,
        stale.DAYS,
        "title",
        *tree.keys,
        "path",
    ]
    assert row["position"] is None and row["number"] is None
    # `greenhouse` declares no heading, so this item counts none at all —
    # which is `None`, and is a different fact from a section that carries the
    # heading and has not been decomposed yet (`0`).
    assert row[subphase.NAME] is None
    assert row[subphase.LEFT] is None
    assert row[subphase.NEXT] is None
    assert row[stale.DAYS] is None


STEPPED = '''\
+++
title = "A tree"
{cursor}
+++

### Steps

- **graft-1 — the first.**{mark1}
- **graft-2 — the second.**{mark2}
- **graft-3 — the third.**{mark3}
'''

#: The fixture's marks. **Neither is `done`**: completion is a mark on the
#: bullet now, so the vocabulary independence this file used to prove over
#: `graft-status` moves onto the words `ripen` and `thin` declare.
RIPENED, THINNED = "ripened", "thinned"


def stepped(tree: Declaration, *marks: str | None, **head: str) -> None:
    """A tree in the orchard whose three named steps carry `marks`."""
    written = "\n".join(f'{key} = "{value}"' for key, value in head.items())
    said = {
        f"mark{number}": f" **{mark}**" if mark else ""
        for number, mark in enumerate((*marks, None, None, None)[:3], start=1)
    }
    file(tree, "orchard", "a-tree.md", STEPPED.format(cursor=written, **said))


def upcoming(tree: Declaration) -> object:
    (row,) = read.rows(tree, read.items(tree))
    return row[subphase.NEXT]


def test_a_row_says_which_sub_phase_comes_next(tree: Declaration) -> None:
    """A section nobody has picked up yet: the first step is what to pick up,
    and the head says nothing at all."""
    stepped(tree)
    assert upcoming(tree) == "graft-1"


def test_a_cursor_on_an_unmarked_step_is_what_comes_next(
    tree: Declaration,
) -> None:
    """The current step is not over, so nothing has moved past it — and no
    value in the head says so either way. What ends a step is the mark on its
    bullet."""
    stepped(tree, RIPENED, graft="graft-2", **{"graft-status": "in progress"})
    assert upcoming(tree) == "graft-2"


def test_a_cursor_on_a_marked_step_advances_and_runs_out_at_the_last_one(
    tree: Declaration,
) -> None:
    """The fourth answer: with every step marked there is no next, while the
    count goes on saying three. The **pair** is what tells a finished section
    from a state that counts none."""
    stepped(tree, RIPENED, RIPENED, graft="graft-2")
    assert upcoming(tree) == "graft-3"

    stepped(tree, RIPENED, RIPENED, THINNED, graft="graft-3")
    (row,) = read.rows(tree, read.items(tree))
    assert row[subphase.NEXT] is None
    assert row[subphase.NAME] == 3


def test_a_row_names_an_earlier_unmarked_step_over_the_one_the_cursor_is_on(
    tree: Declaration,
) -> None:
    """Out-of-order completion, at the row layer: the cursor sits on the last
    step, the first and the last are marked, and the row names the middle one.
    A `(cursor, status)` pair in the head could not say this at all."""
    stepped(tree, RIPENED, None, THINNED, graft="graft-3")
    assert upcoming(tree) == "graft-2"


def test_a_status_in_the_head_does_not_move_the_row_whatever_it_says(
    tree: Declaration,
) -> None:
    """The mutation check, at the row layer, and it is now about the *shape*
    rather than about a word: `graft-status` is still declared and still
    written, and no value it can hold moves what comes next. Completion is
    stored once, on the bullet."""
    for status in ("open", "planned", "in progress", "done"):
        stepped(tree, graft="graft-2", **{"graft-status": status})
        assert upcoming(tree) == "graft-2"

    # And with the mark on, every one of them says the same other thing.
    for status in ("open", "planned", "in progress", "done"):
        stepped(tree, None, RIPENED, graft="graft-2", **{"graft-status": status})
        assert upcoming(tree) == "graft-1"


def test_a_row_says_how_many_sub_phases_are_left(tree: Declaration) -> None:
    """The standing read. Three steps with the first marked leaves two, and
    the number is a fact about the bullets rather than about the cursor —
    nothing in the head moved to produce it."""
    stepped(tree, RIPENED)
    (row,) = read.rows(tree, read.items(tree))
    assert (row[subphase.NAME], row[subphase.LEFT]) == (3, 2)


def test_the_count_left_is_zero_on_a_finished_section_rather_than_absent(
    tree: Declaration,
) -> None:
    """The loud polarity, and the field that would regress silently without
    it. A record drops a `None` line, so a zero collapsed into `None` would
    take a finished section's own way of saying so away with it — and a
    section says it is finished **out loud** rather than by going quiet."""
    stepped(tree, RIPENED, THINNED, RIPENED)
    (row,) = read.rows(tree, read.items(tree))
    assert row[subphase.LEFT] == 0
    assert row[subphase.NEXT] is None


def test_an_undecomposed_section_and_a_finished_one_are_told_apart_by_the_pair(
    tree: Declaration,
) -> None:
    """Both read `sub-phases-left 0`, and the count beside it is what says
    which is which: `sub-phases 0` is a section nobody has cut up, and
    `sub-phases 3` is one where every bullet is disposed of. The pair carries
    the distinction, so neither field has to carry both facts."""
    file(tree, "orchard", "a-seedling.md")
    stepped(tree, RIPENED, THINNED, RIPENED)
    uncut, finished = sorted(
        read.rows(tree, read.items(tree)), key=lambda row: row[subphase.NAME]
    )
    assert (uncut[subphase.NAME], uncut[subphase.LEFT]) == (0, 0)
    assert (finished[subphase.NAME], finished[subphase.LEFT]) == (3, 0)


UNPRUNED = """\
+++
title = "A tree"
+++

### Steps

- **graft-1 — the first.** **{mark}**
- **unpruned — Say what the rest of the training is.**
"""


def test_the_pending_marker_counts_as_left(tree: Declaration) -> None:
    """A decomposition nobody finished is work that is left, which is the same
    answer `next-sub-phase` gives one field over and the same one the close-out
    refuses with one module over. The marker can never carry a mark, so a
    section reading `sub-phases-left 1` with every real step marked is one
    waiting to be cut up the rest of the way rather than one that is over."""
    file(tree, "orchard", "a-tree.md", UNPRUNED.format(mark=RIPENED))
    (row,) = read.rows(tree, read.items(tree))
    assert (row[subphase.NAME], row[subphase.LEFT]) == (2, 1)
    assert row[subphase.NEXT] == "unpruned"


SCRIBBLED = """\
+++
title = "A tree"
+++

### Steps

- **graft-1 — the first.** and a note somebody typed
"""


def test_the_offer_passes_over_a_bullet_no_disposition_could_mark(
    tree: Declaration,
) -> None:
    """John, 2026-09-09: the offer listed it, because hiding it took away the
    one place a consumer would learn that it exists. 15-1 gives that learning
    a place of its own, so the offer can agree with the verb. The report is
    what may not go quiet, and the offer's invariant is unchanged: it may not
    hide a bullet the verb *would* have taken."""
    file(tree, "orchard", "a-tree.md", SCRIBBLED)
    found = read.listing(
        tree, marking=lambda bullet: bullet.mark is None and not bullet.unmarkable
    )
    assert found.rows == []
    # What the traversal read, not what it offered: the bullet still counts.
    assert found.walked == 1
    assert [one[read.BULLET_NAME] for one in found.unmarkable] == ["graft-1"]
    assert [one[read.PATH] for one in found.unmarkable] == ["orchard/a-tree.md"]


def test_an_unmarkable_bullets_line_counts_the_head_as_written_on_disk(
    tree: Declaration,
) -> None:
    """`sed -n <line>p <path>` prints the bullet. The head here is longer
    than `SCRIBBLED`'s, and carries a comment and a blank line that the
    parsed head drops, so a line counted off the parse would land short."""
    text = SCRIBBLED.replace(
        '+++\ntitle = "A tree"\n+++\n',
        '+++\n# typed by hand\ntitle = "A tree"\n\ncultivar = "heirloom"\n+++\n',
    )
    path = file(tree, "orchard", "a-tree.md", text)
    (one,) = read.listing(tree).unmarkable
    # Six lines of head, then the bullet on the body's fourth line.
    assert one[read.BULLET_LINE] == 6 + 4
    assert text.split("\n")[one[read.BULLET_LINE] - 1].startswith("- **graft-1")
    assert tree.root / one[read.PATH] == path


def test_a_bullet_in_a_state_nothing_marks_into_is_reported_nowhere(
    tree: Declaration,
) -> None:
    """The gate is the declaration's, not the corpus's. A `bulleted` state
    nothing marks into is a legal shape, and a bullet there is not waiting on
    a verb — so the same body reports once under a declaration that marks and
    not at all under one that does not."""
    file(tree, "orchard", "a-tree.md", SCRIBBLED)
    assert len(read.listing(tree).unmarkable) == 1

    unmarking = dataclasses.replace(
        tree,
        transitions={
            name: one
            for name, one in tree.transitions.items()
            if one.marks is None
        },
        # What the verbs mark into is read onto each state at load.
        states={
            name: dataclasses.replace(one, marks=None)
            for name, one in tree.states.items()
        },
    )
    assert unmarking.marked_states == frozenset()
    assert read.listing(unmarking).unmarkable == []


CUT_OFF = """\
+++
title = "A tree"
{number}+++

### Steps

- **7-1 — the first.**

## Aside

- **7-2 — the second.**
"""


def test_a_bullet_past_the_span_is_found_by_the_form_the_item_fills_in(
    tree: Declaration,
) -> None:
    """The orchard names its bullets `{number}-{ordinal}`, so the prefix is
    the item's own number. An item carrying no number has no prefix, and a
    stray bullet then cannot be told from the writer's own prose."""
    path = file(tree, "orchard", "a-tree.md", CUT_OFF.format(number="number = 7\n"))
    (one,) = read.listing(tree).unread
    assert (one[read.BULLET_NAME], one[read.PATH]) == ("7-2", "orchard/a-tree.md")
    assert path.read_text().split("\n")[one[read.BULLET_LINE] - 1].startswith("- **7-2")

    file(tree, "orchard", "a-tree.md", CUT_OFF.format(number=""))
    assert read.listing(tree).unread == []


def test_a_state_that_counts_no_sub_phases_carries_none_of_the_three_fields(
    tree: Declaration,
) -> None:
    """`greenhouse` declares no heading. All three fields are `None` there —
    which is a different fact from a counted state with nothing decomposed,
    and they are present at all because the *declaration* has a counted
    state."""
    file(tree, "greenhouse", "a-seedling.md")
    (row,) = read.rows(tree, read.items(tree))
    assert row[subphase.NAME] is None and row[subphase.NEXT] is None
    assert row[subphase.LEFT] is None


WAITING = '''\
+++
title = "A tree"
after = [{edges}]
+++

Prose.
'''


def waiting(tree: Declaration, name: str, *edges: str, place: int | None = None) -> None:
    """A tree in the orchard waiting on ``edges``, at ``place`` if given."""
    head = ", ".join(f'"{one}"' for one in edges)
    text = WAITING.format(edges=head)
    if place is not None:
        text = text.replace('title = "A tree"', f'title = "A tree"\nposition = {place}')
    file(tree, "orchard", f"{name}.md", text)


def test_a_word_is_found_in_any_entry_of_a_list_ignoring_case() -> None:
    """`~` over a list asks each entry, `carries`' rule, and folds case on
    both sides."""
    found = [{"pest": ["Woolly aphid", "scab"]}, {"pest": "canker"}, {}]
    test = read.comparison("pest", "~APHID")
    assert read.matching(found, [test]) == [found[0]]


def test_a_row_carries_what_waits_on_it(tree: Declaration) -> None:
    """`blocks` is `blocked-by` the other way round, off the same walk: what
    a session wants to know before declining or reworking an item."""
    file(tree, "orchard", "a-tree.md")
    waiting(tree, "b-tree", "a-tree")
    waiting(tree, "c-tree", "a-tree", "b-tree")
    found = read.listing(tree)
    assert {row["slug"]: row[depends.BLOCKS] for row in found.rows} == {
        "a-tree": ["b-tree", "c-tree"],
        "b-tree": ["c-tree"],
        "c-tree": None,
    }
    assert [
        row["slug"]
        for row in read.matching(found.rows, [read.filtering(tree, "blocks=c-tree")])
    ] == ["a-tree", "b-tree"]


def test_a_row_carries_the_edges_it_waits_on_that_are_still_filed(
    tree: Declaration,
) -> None:
    """`blocked-by` is the old `unmet_after`'s answer, off the key the state
    names — `after` is the fixture's word, and nothing in the tool spells
    it."""
    file(tree, "orchard", "a-tree.md")
    waiting(tree, "b-tree", "a-tree")
    found = read.listing(tree)
    assert {row["slug"]: row[depends.BLOCKED] for row in found.rows} == {
        "a-tree": None,
        "b-tree": ["a-tree"],
    }


def test_an_item_waiting_on_nothing_carries_none(tree: Declaration) -> None:
    """Present because the *declaration* reads dependencies, `None` because
    this item waits on nothing — the corpus-independence rule again."""
    file(tree, "greenhouse", "a-seedling.md")
    (row,) = read.rows(tree, read.items(tree))
    assert depends.BLOCKED in row and row[depends.BLOCKED] is None


def test_an_edge_naming_nothing_filed_is_not_in_blocked_by(
    tree: Declaration,
) -> None:
    """"Waiting on X" and "X does not exist" are different facts. The second
    is the `unknown` report, and it must not hide inside the first."""
    waiting(tree, "b-tree", "gone-tree")
    found = read.listing(tree)
    (row,) = found.rows
    assert row[depends.BLOCKED] is None
    assert [one[depends.NAMES] for one in found.unknown] == ["gone-tree"]


def test_an_edge_in_a_state_that_names_no_key_is_not_read(
    tree: Declaration,
) -> None:
    """`after` is declared, so a greenhouse seedling may carry it — and
    `greenhouse` names no dependency key, so nothing reads it. A fact nothing
    was declared to read is not read."""
    file(tree, "greenhouse", "a-seedling.md", WAITING.format(edges='"gone-tree"'))
    found = read.listing(tree)
    assert found.rows[0][depends.BLOCKED] is None
    assert found.unknown == []


def test_the_unknown_report_names_the_item_the_key_and_what_it_named(
    tree: Declaration,
) -> None:
    waiting(tree, "b-tree", "gone-tree")
    (one,) = read.listing(tree).unknown
    assert one == {
        depends.SLUG: "b-tree",
        depends.KEY: "after",
        depends.NAMES: "gone-tree",
    }


def test_an_edge_pointing_later_in_the_order_is_reported(
    tree: Declaration,
) -> None:
    """Named rather than reordered: `position` sorts and an edge reports."""
    waiting(tree, "a-tree", "b-tree", place=100)
    waiting(tree, "b-tree", place=200)
    found = read.listing(tree)
    (one,) = found.misordered
    assert (one[depends.SLUG], one[depends.NAMES]) == ("a-tree", "b-tree")
    assert (one[depends.PLACE], one[depends.NAMED_PLACE]) == (100, 200)
    # And the order itself is untouched by the edge.
    assert [row["slug"] for row in found.rows] == ["a-tree", "b-tree"]


def test_an_order_that_agrees_reports_nothing(tree: Declaration) -> None:
    waiting(tree, "a-tree", place=100)
    waiting(tree, "b-tree", "a-tree", place=200)
    found = read.listing(tree)
    assert found.misordered == []
    assert found.rows[1][depends.BLOCKED] == ["a-tree"]


def test_neither_dependency_report_is_narrowed_by_an_offering(
    tree: Declaration,
) -> None:
    """3-1's rule, now with four reports to keep: an offer is a filter, and
    no filter narrows an exception report. The offering here excludes the
    very items both reports name."""
    waiting(tree, "a-tree", "gone-tree", "b-tree", place=100)
    waiting(tree, "b-tree", place=200)
    found = read.listing(tree, offering=lambda one: False)
    assert found.rows == []
    assert [one[depends.NAMES] for one in found.unknown] == ["gone-tree"]
    assert [one[depends.NAMES] for one in found.misordered] == ["b-tree"]


def test_the_reports_are_computed_over_the_whole_tree(tree: Declaration) -> None:
    """Not over the offering's narrowed set: what an item waits on is a
    question about the whole tree, and a narrowed set would answer it with
    whatever the offer happened to keep — which would turn a filed blocker
    into an unknown one."""
    file(tree, "orchard", "a-tree.md")
    waiting(tree, "b-tree", "a-tree")
    found = read.listing(tree, offering=lambda one: one.slug == "b-tree")
    (row,) = found.rows
    assert row[depends.BLOCKED] == ["a-tree"]
    assert found.unknown == []


def test_an_unresolvable_edge_does_not_refuse_the_listing(
    tree: Declaration,
) -> None:
    """Reported, never refused: grading a head value at read time would break
    a whole listing over one item."""
    waiting(tree, "a-tree", "gone-tree")
    file(tree, "greenhouse", "b-seedling.md")
    found = read.listing(tree)
    assert [row["slug"] for row in found.rows] == ["b-seedling", "a-tree"]


def test_a_declaration_with_no_dependencies_carries_no_field(
    tree: Declaration,
) -> None:
    """The field is generated by the state's opt-in, so where nothing names a
    key the row has no room for it at all."""
    file(tree, "greenhouse", "a-seedling.md")
    source = tree.source
    source.write_text(source.read_text().replace('dependencies      = "after"', ""))
    plain = load(source)
    (row,) = read.rows(plain, read.items(plain))
    assert depends.BLOCKED not in row


def test_title_comes_through_as_an_intrinsic_key(tree: Declaration) -> None:
    """The fixture declares no `[keys.title]` — it may not — and a row carries
    one anyway, because an item is a head, a body, a location and a name."""
    assert "title" not in tree.keys
    file(tree, "greenhouse", "a-seedling.md")
    (row,) = read.rows(tree, read.items(tree))
    assert row["title"] == "A seedling"


def test_a_state_is_reported_by_its_declared_name_not_its_path(
    tree: Declaration,
) -> None:
    """**One spelling per state.** `cold-frame` lives in `beds/hardening-off`,
    sharing neither its name nor its last segment, so a caller reading the
    directory for itself cannot get this right."""
    file(tree, "cold-frame", "a-seedling.md")
    (row,) = read.rows(tree, read.items(tree))
    assert row["state"] == "cold-frame"
    assert "hardening-off" not in row["state"]


def test_a_rows_path_is_relative_to_the_declarations_root(
    tree: Declaration,
) -> None:
    """A listing is about this tree, and an absolute path under a tmpdir or a
    synced mount is noise in every line of it."""
    file(tree, "cold-frame", "a-seedling.md")
    (row,) = read.rows(tree, read.items(tree))
    assert row["path"] == "beds/hardening-off/a-seedling.md"


def test_a_rows_slug_is_the_filename_stem(tree: Declaration) -> None:
    file(tree, "greenhouse", "a-seedling.md")
    (row,) = read.rows(tree, read.items(tree))
    assert row["slug"] == "a-seedling"


def test_a_head_value_keeps_its_toml_type(tree: Declaration) -> None:
    """No coercion, 1-2's rule, all the way to the row: `planted` reads back
    as a date and `after` as a list."""
    file(
        tree,
        "greenhouse",
        "a-seedling.md",
        "+++\nplanted = 2026-09-01\nafter = [\"b-seedling\"]\n+++\n",
    )
    (row,) = read.rows(tree, read.items(tree))
    assert row["planted"] == dt.date(2026, 9, 1)
    assert row["after"] == ["b-seedling"]


# --------------------------------------------------------------------------
# A queued state comes back in slug order: its sort is the listing's
# --------------------------------------------------------------------------


def placed(declaration: Declaration, name: str, position: int | None) -> Path:
    """One item in `orchard`, the fixture's `queued` state."""
    place = f"position = {position}\n" if position is not None else ""
    return file(
        declaration, "orchard", f"{name}.md", f'+++\ntitle = "A tree"\n{place}+++\n'
    )


def test_a_queued_state_comes_back_in_slug_order(tree: Declaration) -> None:
    """Place order is the declared `sort = "position"`, which `ordered`
    applies. The traversal has no special case for `queued`."""
    placed(tree, "c-tree", 100)
    placed(tree, "a-tree", 300)
    placed(tree, "b-tree", None)
    assert [one.slug for one in read.items(tree)] == ["a-tree", "b-tree", "c-tree"]
    assert read.rows(tree, read.items(tree))[1]["position"] is None


def test_a_non_queued_state_is_still_slug_ordered(tree: Declaration) -> None:
    file(tree, "greenhouse", "b-seedling.md")
    file(tree, "greenhouse", "a-seedling.md")
    assert [one.slug for one in read.items(tree)] == ["a-seedling", "b-seedling"]


def test_declared_state_order_still_comes_first(tree: Declaration) -> None:
    """A state's own order is *within* the state. The states themselves stay
    in declared order, which is the workflow's order."""
    placed(tree, "z-tree", 100)
    file(tree, "greenhouse", "a-seedling.md")
    assert [one.slug for one in read.items(tree)] == ["a-seedling", "z-tree"]


# --------------------------------------------------------------------------
# The claim: the first thing a row carries from outside the item file
# --------------------------------------------------------------------------
#
# The fixture's `potting-bench` claims and its `orchard` is ordered, so one
# declaration proves a row carrying both capabilities' fields. `rows` stays
# pure over the mapping it is handed; `listing` is the edge that reads
# `local/claims/` and decides which records belong to an item at all.

#: What one holder's two fields look like, as `claim.fields` builds them.
HOLDER = "this-host pid 4213"
HELD = {"claimed-by": HOLDER, "claim-status": claim.ALIVE}


def held(
    declaration: Declaration, slug: str, *, pid: int | None = None, host: str = ""
) -> Path:
    """One claim record on disk, the way a session leaves one behind."""
    path = claim.path(declaration.root, slug)
    claim.write(
        path,
        {
            "host": host or socket.gethostname(),
            "pid": os.getpid() if pid is None else pid,
            "taken": TAKEN,
        },
    )
    return path


def broken(declaration: Declaration, slug: str, text: str) -> Path:
    """A hand-edited record: something a person wrote and the tool cannot read."""
    path = claim.path(declaration.root, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def unclaimed(declaration: Declaration) -> Declaration:
    """The same declaration with nothing claiming: the state stays, so every
    `from`/`to` still resolves and the capability is the only difference.

    Both halves go together — the state's opt-in and the `claims = true` on
    the verbs that take one — because either alone refuses at load.
    """
    source = declaration.source
    source.write_text(
        source.read_text()
        .replace('capabilities = ["claimed"]\n', "")
        .replace("claims = true\n", "")
    )
    return load(source)


def test_a_row_carries_the_claim_beside_its_item(tree: Declaration) -> None:
    """The merge, pure: `rows` is handed slug → fields and spells them into
    the row. Nothing here reads a record — that is `listing`'s edge."""
    file(tree, "potting-bench", "a-seedling.md")
    (row,) = read.rows(tree, read.items(tree), claimed={"a-seedling": HELD})
    assert row["claimed-by"] == HOLDER
    assert row["claim-status"] == claim.ALIVE


def test_an_item_nothing_claims_carries_both_fields_as_none(
    tree: Declaration,
) -> None:
    """`null`, not absent: the shape a consumer writes against does not depend
    on which items happen to be claimed."""
    file(tree, "potting-bench", "a-seedling.md")
    (row,) = read.rows(tree, read.items(tree))
    assert row["claimed-by"] is None and row["claim-status"] is None


def test_an_item_in_an_unclaimed_state_carries_them_too(tree: Declaration) -> None:
    """Present whenever the *declaration* claims, not whenever the item's
    state does — the corpus-independence rule `position` already keeps."""
    file(tree, "greenhouse", "a-seedling.md")
    (row,) = read.rows(tree, read.items(tree))
    assert "claimed-by" in row and "claim-status" in row


def test_a_declaration_with_no_claimed_state_carries_neither_field(
    tree: Declaration,
) -> None:
    """The fields are generated by the capability, so where no state opts in
    the row has no room for them at all."""
    file(tree, "greenhouse", "a-seedling.md")
    plain = unclaimed(tree)
    (row,) = read.rows(plain, read.items(plain))
    assert "claimed-by" not in row and "claim-status" not in row


# The filters are the pure half, so these take no tmp_path.

CLAIMED_ROWS = [
    {"slug": "a", "claimed-by": "this-host pid 1", "claim-status": claim.ALIVE},
    {"slug": "b", "claimed-by": "this-host pid 2", "claim-status": claim.DEAD},
    {"slug": "c", "claimed-by": None, "claim-status": None},
]


def test_the_unclaimed_work_is_what_lacks_a_holder() -> None:
    """The pick read, until section 3 spells it as a verb: this is what
    proves section 2's done line today."""
    tests = [read.presence("claimed-by", carried=False)]
    assert slugs(read.matching(CLAIMED_ROWS, tests)) == ["c"]


def test_what_needs_releasing_is_a_dead_claim_status() -> None:
    tests = [read.comparison("claim-status", claim.DEAD, claim.STATUSES)]
    assert slugs(read.matching(CLAIMED_ROWS, tests)) == ["b"]


def test_a_holder_filters_like_any_other_value() -> None:
    tests = [read.comparison("claimed-by", "this-host pid 2")]
    assert slugs(read.matching(CLAIMED_ROWS, tests)) == ["b"]


def test_a_status_the_probe_never_answers_refuses_by_name() -> None:
    """A closed set like a key's declared `values`, so `--claim-status zzz`
    refuses rather than matching nothing."""
    with pytest.raises(Refusal) as refusal:
        read.comparison("claim-status", "zzz", claim.STATUSES)
    assert "zzz" in str(refusal.value)
    assert ", ".join(claim.STATUSES) in str(refusal.value)


# The composed edge.


def test_the_listing_carries_the_claim_on_the_item_that_holds_it(
    tree: Declaration,
) -> None:
    file(tree, "potting-bench", "a-seedling.md")
    held(tree, "a-seedling")
    found = read.listing(tree)
    (row,) = found.rows
    assert row["claimed-by"] == f"{socket.gethostname()} pid {os.getpid()}"
    assert row["claim-status"] == claim.ALIVE
    assert found.stranded == []


def test_the_listing_probes_each_record_once_and_reports_what_it_found(
    tree: Declaration,
) -> None:
    """A dead session's claim and one from another machine are two answers,
    not two ways of saying "maybe dead"."""
    file(tree, "potting-bench", "a-seedling.md")
    file(tree, "potting-bench", "b-seedling.md")
    held(tree, "a-seedling", pid=exited())
    held(tree, "b-seedling", host="another-host")
    statuses = {row["slug"]: row["claim-status"] for row in read.listing(tree).rows}
    assert statuses == {"a-seedling": claim.DEAD, "b-seedling": claim.ELSEWHERE}


def test_a_record_whose_item_is_gone_is_stranded(tree: Declaration) -> None:
    """The first flavour: nothing answers to the slug at all. Named rather
    than skipped, and `rm` is what takes it away."""
    held(tree, "a-seedling")
    found = read.listing(tree)
    assert found.rows == []
    (one,) = found.stranded
    assert one["slug"] == "a-seedling"
    assert one["claimed-by"].startswith(socket.gethostname())
    assert one["path"] == "local/claims/a-seedling.toml"


def test_a_record_for_an_item_in_an_unclaimed_state_is_stranded(
    tree: Declaration,
) -> None:
    """The second flavour, and the one a listing computed over missing items
    alone would miss: the item exists, and its state claims nothing. The
    executor already ignores this record — neither state opts in — so the
    listing agrees rather than reporting a claim no transition will honour."""
    file(tree, "greenhouse", "a-seedling.md")
    held(tree, "a-seedling")
    found = read.listing(tree)
    (row,) = found.rows
    assert row["claimed-by"] is None
    assert [one["slug"] for one in found.stranded] == ["a-seedling"]


def test_a_stranded_claim_is_never_a_row(tree: Declaration) -> None:
    """A filter narrows items, and these are not items — which is why they are
    a second field on the listing rather than rows with values missing."""
    file(tree, "potting-bench", "a-seedling.md")
    held(tree, "a-seedling")
    held(tree, "b-seedling")
    found = read.listing(tree)
    assert [row["slug"] for row in found.rows] == ["a-seedling"]
    assert [one["slug"] for one in found.stranded] == ["b-seedling"]


def test_a_declaration_with_no_claimed_state_reads_no_records_at_all(
    tree: Declaration,
) -> None:
    """No capability, nothing to read and nothing to strand — which is why
    this repo's own listing is unchanged by any of this."""
    file(tree, "greenhouse", "a-seedling.md")
    held(tree, "a-seedling")
    found = read.listing(unclaimed(tree))
    assert found.stranded == []
    assert "claimed-by" not in found.rows[0]


def test_a_malformed_record_refuses_the_listing_naming_it(
    tree: Declaration,
) -> None:
    """The deliberate asymmetry with a *missing* record: a fresh clone has no
    records and reads as unclaimed, but a record that exists and cannot be
    read says something the tool does not understand about who holds an item.
    Reading that as free is the one direction a claim must never fail in."""
    file(tree, "potting-bench", "a-seedling.md")
    broken(tree, "a-seedling", "pid = 4213\n")
    with pytest.raises(Refusal) as refusal:
        read.listing(tree)
    assert "a-seedling.toml" in str(refusal.value)
    assert "no host" in str(refusal.value)


def test_every_defect_in_the_records_is_reported_at_once(
    tree: Declaration,
) -> None:
    """One sitting, like a tree of broken item files."""
    broken(tree, "a-seedling", "pid = 4213\n")
    broken(tree, "b-seedling", "host = 'x'\nvine = 1\n")
    with pytest.raises(Refusal) as refusal:
        read.listing(tree)
    assert "a-seedling.toml" in str(refusal.value)
    assert "b-seedling.toml" in str(refusal.value)


# --------------------------------------------------------------------------
# stale-days: the second thing a row carries from outside the item file
# --------------------------------------------------------------------------

# The fixture's `cold-frame` is the dated state, and its `path` is
# `beds/hardening-off` — so a lookup that used a state's *name* rather than
# its path would find nothing here. The repos are built in-process with
# dulwich, like `test_stale.py`'s; nothing here shells out.


def dated(tree: Declaration, *slugs: str) -> None:
    """File one item per slug into the dated state and commit them all, now.

    Authored at the current local moment with the local offset, so the day
    the tool reads is the same `dt.date.today()` `fileplan.read.listing`
    asks for — which makes every value below a `0` rather than a race.
    """
    for slug in slugs:
        file(tree, "cold-frame", f"{slug}.md")
    when = dt.datetime.now().astimezone()
    with Repo.init(str(tree.root)) as repo:
        worktree = repo.get_worktree()
        worktree.stage(
            [
                str(Path(tree.states["cold-frame"].path) / f"{slug}.md").encode()
                for slug in slugs
            ]
        )
        worktree.commit(
            b"filed",
            committer=b"A Gardener <gardener@example.invalid>",
            author=b"A Gardener <gardener@example.invalid>",
            author_timestamp=int(when.timestamp()),
            author_timezone=int(when.utcoffset().total_seconds()),
            commit_timestamp=int(when.timestamp()),
            commit_timezone=0,
        )


def test_a_row_carries_stale_days_null_in_a_tree_that_is_not_a_repo(
    tree: Declaration,
) -> None:
    """A consumer's tree need not be in git. The field is there
    because the fixture has a dated state, and it is `null` because git has
    nothing to say — no refusal, no traceback."""
    file(tree, "cold-frame", "a-seedling.md")
    (row,) = read.listing(tree).rows
    assert row[stale.DAYS] is None


def test_only_an_item_in_a_dated_state_gets_a_value(tree: Declaration) -> None:
    """The claim's exact shape: the field is on every row because the
    *declaration* has such a state, and only the items **in** one are looked
    up. `greenhouse` is committed here too, so what distinguishes them is the
    capability rather than what git happens to know."""
    dated(tree, "a-seedling")
    committed = file(tree, "greenhouse", "a-sprout.md")
    with Repo(str(tree.root)) as repo:
        worktree = repo.get_worktree()
        worktree.stage([str(committed.relative_to(tree.root)).encode()])
        worktree.commit(
            b"and the sprout",
            committer=b"A Gardener <gardener@example.invalid>",
            author=b"A Gardener <gardener@example.invalid>",
        )
    ages = {row["slug"]: row[stale.DAYS] for row in read.listing(tree).rows}
    assert ages == {"a-sprout": None, "a-seedling": 0}


def test_a_declaration_with_no_dated_state_has_no_such_field(
    tree: Declaration, tmp_path: Path
) -> None:
    """The fields are generated by the capability, so where no state opts in
    the row has no room for one — and nothing asks git anything."""
    source = tmp_path / "undated" / "plan.toml"
    source.parent.mkdir()
    source.write_text(
        (FIXTURES / "plan.toml").read_text().replace('capabilities = ["dated"]', "")
    )
    for name in FIXTURE_FILES[1:]:
        (source.parent / name).write_text((FIXTURES / name).read_text())
    undated = load(source)
    file(undated, "cold-frame", "a-seedling.md")
    (row,) = read.rows(undated, read.items(undated))
    assert stale.DAYS not in row


# The filters are the pure half again, so these take no tmp_path.

DATED_ROWS = [
    {"slug": "a", stale.DAYS: 0},
    {"slug": "b", stale.DAYS: 30},
    {"slug": "c", stale.DAYS: None},
]


def test_stale_days_compares_as_a_number_not_as_text() -> None:
    """Both sides are numbers, so `>=9` includes 30 rather than excluding it
    the way text sorting would."""
    tests = [read.comparison(stale.DAYS, ">=9")]
    assert slugs(read.matching(DATED_ROWS, tests)) == ["b"]


def test_what_git_cannot_answer_about_lacks_the_field() -> None:
    tests = [read.presence(stale.DAYS, carried=False)]
    assert slugs(read.matching(DATED_ROWS, tests)) == ["c"]


# --------------------------------------------------------------------------
# The register: the fourth thing read from outside the item files
# --------------------------------------------------------------------------
#
# `orchard` is the fixture's numbered state and `orchard-archive.md` its
# archive, holding `## 1. A felled tree`. The register is that heading plus
# whatever the live trees carry, and the two reports are what it is short of
# and what it cannot read.


def numbered_tree(declaration: Declaration, name: str, number: int) -> None:
    """One tree in the orchard carrying ``number``, and nothing else."""
    file(
        declaration,
        "orchard",
        f"{name}.md",
        f'+++\ntitle = "{name}"\nnumber = {number}\n+++\n\nProse.\n',
    )


def archived(declaration: Declaration, text: str) -> None:
    """Rewrite the archive the fixture's numbered state names."""
    (declaration.root / "orchard-archive.md").write_text(text, encoding="utf-8")


def test_a_number_in_neither_the_state_nor_the_archive_is_named(
    tree: Declaration,
) -> None:
    """Done line 2, at the read. The archive holds 1 and the one live tree
    holds 3, so 2 is a number nothing says what happened to — and until now
    the tool only said so at the next mint."""
    numbered_tree(tree, "a-tree", 3)
    (one,) = read.listing(tree).gaps
    assert one == {
        numbered.STATE: "orchard",
        numbered.ARCHIVE: "orchard-archive.md",
        numbered.KEY: 2,
    }


def test_a_contiguous_register_names_nothing(tree: Declaration) -> None:
    numbered_tree(tree, "a-tree", 2)
    numbered_tree(tree, "b-tree", 3)
    found = read.listing(tree)
    assert found.gaps == [] and found.lost == []



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
            'archive           = "orchard-archive.md"\n'
            f"first-number      = {first}",
        ),
        encoding="utf-8",
    )
    return load(source)


def test_the_gap_report_starts_at_the_declared_floor(
    tree: Declaration,
) -> None:
    """The other reader of the same arithmetic. Undeclared, a register holding
    192 and 193 is short of 191 numbers and the listing would say so on every
    read; the floor says those are recorded elsewhere, so it names none — one
    arithmetic, two readers, and the field reaches both."""
    declaration = floored(tree, 192)
    archived(declaration, "# The archive\n\n## 192. A felled tree\n")
    numbered_tree(declaration, "a-tree", 193)
    found = read.listing(declaration)
    assert found.gaps == [] and found.lost == []


def test_a_state_by_its_declared_name_and_only_a_numbered_one(
    tree: Declaration,
) -> None:
    """A register is per numbered state, and `orchard` is the fixture's only
    one — so four other states hold items and contribute nothing, and the
    record says `orchard` rather than the directory it happens to live in."""
    numbered_tree(tree, "a-tree", 3)
    file(tree, "greenhouse", "a-seedling.md")
    file(tree, "cold-frame", "a-hardened.md")
    assert [one[numbered.STATE] for one in read.listing(tree).gaps] == ["orchard"]


def test_an_archive_heading_the_register_cannot_read_is_named(
    tree: Declaration,
) -> None:
    """And does **not** refuse: a listing that stopped over one bad heading
    would wedge the read a person would use to find it. The mint goes on
    refusing, where a write is about to happen."""
    archived(tree, "# The archive\n\n## 1. A felled tree\n\n## Section 2: lost\n")
    numbered_tree(tree, "a-tree", 2)
    found = read.listing(tree)
    assert found.lost == [
        {
            numbered.STATE: "orchard",
            numbered.ARCHIVE: "orchard-archive.md",
            numbered.LINE: 5,
            numbered.TEXT: "## Section 2: lost",
        }
    ]
    assert [row["slug"] for row in found.rows] == ["a-tree"]


def test_a_lost_close_out_that_also_opens_a_gap_produces_both_records(
    tree: Declaration,
) -> None:
    """Why they are two reports rather than one array with a discriminator:
    one document defect can be both facts at once, and a consumer selects the
    one it cares about by the envelope key."""
    archived(tree, "## 1. A felled tree\n\n## Section 2: lost\n")
    numbered_tree(tree, "a-tree", 3)
    found = read.listing(tree)
    assert [one[numbered.KEY] for one in found.gaps] == [2]
    assert [one[numbered.LINE] for one in found.lost] == [3]


def test_a_lost_close_out_at_the_top_of_the_range_is_named_though_it_makes_no_gap(
    tree: Declaration,
) -> None:
    """John's reason for a second report, 2026-09-04, pinned. A loss at the
    maximum lowers the maximum and leaves what remains gapless, so the gap
    report structurally cannot name it — this is what narrows that hole."""
    archived(tree, "## 1. A felled tree\n\n## Section 2: lost\n")
    found = read.listing(tree)
    assert found.gaps == []
    assert [one[numbered.LINE] for one in found.lost] == [3]


def test_neither_register_report_is_narrowed_by_an_offering(
    tree: Declaration,
) -> None:
    """Seven reports now, and the rule has not moved: an offer is a filter, and
    no filter narrows an exception report. The offering here excludes every
    item in the tree."""
    archived(tree, "## 1. A felled tree\n\n## Section 2: lost\n")
    numbered_tree(tree, "a-tree", 3)
    found = read.listing(tree, offering=lambda one: False)
    assert found.rows == []
    assert [one[numbered.KEY] for one in found.gaps] == [2]
    assert [one[numbered.LINE] for one in found.lost] == [3]


# The register itself, beside the two reports. Not an eighth report: it says
# what the register holds rather than what is wrong with it, so every one of
# these reads it on a corpus with nothing wrong.


def test_the_register_says_where_it_begins_and_how_high_it_goes(
    tree: Declaration,
) -> None:
    """The two numbers a consumer's gate needs, off the read it already
    makes. The archive holds 1 and the live tree holds 3, and the record is
    the whole of what that register says about itself."""
    numbered_tree(tree, "a-tree", 3)
    assert read.listing(tree).register == [
        {
            numbered.STATE: "orchard",
            numbered.ARCHIVE: "orchard-archive.md",
            numbered.FLOOR: 1,
            numbered.HIGHEST: 3,
        }
    ]


def test_a_number_only_the_archive_holds_counts_toward_the_highest(
    tree: Declaration,
) -> None:
    """Two sources, one register — the same rule the gap walk keeps. A closed
    item's heading is a number held, though no file carries it."""
    archived(tree, "## 1. A felled tree\n\n## 2. A second felled tree\n")
    (one,) = read.listing(tree).register
    assert one[numbered.HIGHEST] == 2


def test_a_register_holding_nothing_says_so_rather_than_naming_a_number(
    tree: Declaration,
) -> None:
    """`null`, not 0 and not `floor - 1`, both of which would be arithmetic
    the tool invented. "Nothing is held" and "1 is held" are different
    facts, and a consumer asking "is N a section" needs to tell them
    apart."""
    archived(tree, "")
    (one,) = read.listing(tree).register
    assert one[numbered.HIGHEST] is None
    assert one[numbered.FLOOR] == 1


def test_a_declared_floor_is_what_the_record_says(tree: Declaration) -> None:
    """The effective floor, so a consumer needs no default of its own —
    re-deriving that default is the duplication this removes."""
    declaration = floored(tree, 192)
    archived(declaration, "# The archive\n\n## 192. A felled tree\n")
    numbered_tree(declaration, "a-tree", 193)
    (one,) = read.listing(declaration).register
    assert (one[numbered.FLOOR], one[numbered.HIGHEST]) == (192, 193)


def test_the_highest_is_the_number_the_next_mint_adds_one_to(
    tree: Declaration,
) -> None:
    """The tie, pinned by a test rather than by a shared call. The reported
    ceiling and the mint read the same two sources, so a clean register mints
    one above what the record says it holds."""
    numbered_tree(tree, "a-tree", 2)
    (one,) = read.listing(tree).register
    held = {"a-tree": 2, "orchard-archive.md § 1.": 1}
    assert numbered.next_number(numbered.taken(held)) == one[numbered.HIGHEST] + 1


def test_the_register_is_not_narrowed_by_an_offering(tree: Declaration) -> None:
    """It is about the tree rather than about rows of it, so the rule the
    seven reports keep is the rule this keeps: an offer is a filter, and no
    filter touches it."""
    numbered_tree(tree, "a-tree", 3)
    found = read.listing(tree, offering=lambda one: False)
    assert found.rows == []
    (one,) = found.register
    assert (one[numbered.FLOOR], one[numbered.HIGHEST]) == (1, 3)


# --------------------------------------------------------------------------
# The offering: the seam `next <transition>` is built on
# --------------------------------------------------------------------------
#
# A predicate over **items**, not over rows, and this module goes on knowing
# nothing about transitions — the caller brings the question. What an offering
# may narrow is `rows` and nothing else: `walked` is the size of the
# traversal, and the exception reports are about the tree rather than about
# the rows of it.

#: A started section carrying no steps at all, so `undecomposed` names it.
#: `graft-status` is the fixture's status key, and carrying it *at all* is
#: what started means.
UNSTEPPED = """\
+++
title = "A tree"
graft-status = "open"
+++

No steps here.
"""


def test_an_offering_narrows_the_rows(tree: Declaration) -> None:
    file(tree, "greenhouse", "a-seedling.md")
    file(tree, "greenhouse", "b-seedling.md")
    found = read.listing(tree, offering=lambda one: one.slug == "a-seedling")
    assert [row["slug"] for row in found.rows] == ["a-seedling"]


def test_the_traversal_still_walked_the_whole_tree(tree: Declaration) -> None:
    """`walked` is what the frame counts *of*. Without it an offer of one out
    of three would say `1 of 1` and hide the two it passed over — the
    make-problems-visible polarity, at the seam that decides the number."""
    file(tree, "greenhouse", "a-seedling.md")
    file(tree, "greenhouse", "b-seedling.md")
    file(tree, "cold-frame", "c-seedling.md")
    found = read.listing(tree, offering=lambda one: one.slug == "a-seedling")
    assert len(found.rows) == 1
    assert found.walked == 3


def test_an_offering_does_not_narrow_the_stranded_claims(
    tree: Declaration,
) -> None:
    """A stranded claim is a *record*, not an item, so nothing that narrows
    items may touch it — and an offering is a filter. The offering here
    excludes the very item a record would have belonged to."""
    file(tree, "potting-bench", "a-seedling.md")
    held(tree, "a-seedling")
    held(tree, "b-seedling")
    found = read.listing(tree, offering=lambda one: False)
    assert found.rows == []
    assert [one["slug"] for one in found.stranded] == ["b-seedling"]


def test_an_offering_does_not_narrow_the_undecomposed_report(
    tree: Declaration,
) -> None:
    """The other exception report, by the same rule: hiding is the failure
    mode, and an offer that quietly dropped a started section carrying no
    sub-phases would be that failure with the offer as its excuse."""
    file(tree, "orchard", "a-tree.md", UNSTEPPED)
    found = read.listing(tree, offering=lambda one: False)
    assert found.rows == []
    assert found.undecomposed == ["a-tree"]


def test_no_offering_means_every_row_and_walked_is_their_count(
    tree: Declaration,
) -> None:
    """Which is why `list` is unchanged: the two numbers are equal wherever
    nothing narrows the items."""
    file(tree, "greenhouse", "a-seedling.md")
    file(tree, "cold-frame", "b-seedling.md")
    found = read.listing(tree)
    assert [row["slug"] for row in found.rows] == ["a-seedling", "b-seedling"]
    assert found.walked == len(found.rows) == 2


# --------------------------------------------------------------------------
# Filters: pure, so no tmp_path
# --------------------------------------------------------------------------

ROWS = [
    {"slug": "a", "state": "greenhouse", "cultivar": "heirloom", "after": ["b"]},
    {"slug": "b", "state": "orchard", "cultivar": "hybrid", "after": None},
    {"slug": "c", "state": "orchard", "cultivar": None, "after": []},
]

CULTIVARS = ("heirloom", "hybrid")


def slugs(rows) -> list[str]:
    return [row["slug"] for row in rows]


def test_one_filter_narrows() -> None:
    tests = [read.comparison("cultivar", "heirloom", CULTIVARS)]
    assert slugs(read.matching(ROWS, tests)) == ["a"]


def test_no_filters_is_everything() -> None:
    assert slugs(read.matching(ROWS, [])) == ["a", "b", "c"]


def test_two_filters_and_together() -> None:
    tests = [
        read.comparison("state", "orchard"),
        read.comparison("cultivar", "hybrid", CULTIVARS),
    ]
    assert slugs(read.matching(ROWS, tests)) == ["b"]


# --------------------------------------------------------------------------
# The sort: within each state, by the rules a comparison uses
# --------------------------------------------------------------------------

#: A synthetic order, because the fixture's declared values happen to be
#: alphabetical, and an order that is alphabetical proves nothing.
SIZES = ("S", "M", "L", "XL")
STATES = ("greenhouse", "orchard")


def sized(slug: str, size: Any = None, state: str = "greenhouse") -> dict[str, Any]:
    return {"slug": slug, "state": state, "size": size, "path": f"{state}/{slug}.md"}


def by_size(rows, *sorts: read.Sort) -> list[str]:
    """Every state sorted the same way, as a `--sort` does."""
    given = sorts or [read.Sort("size", order=SIZES)]
    return slugs(read.ordered(rows, dict.fromkeys(STATES, given), STATES)[0])


def test_a_sort_follows_the_declared_order_rather_than_the_alphabet() -> None:
    rows = [sized("a", "XL"), sized("b", "S"), sized("c", "L"), sized("d", "M")]
    assert by_size(rows) == ["b", "d", "c", "a"]


def test_a_sort_compares_numbers_as_numbers() -> None:
    assert by_size([sized("a", "10"), sized("b", 9)], read.Sort("size")) == ["b", "a"]


def test_a_sort_ranks_declared_values_then_numbers_then_text() -> None:
    """`_pair`'s three rules in its order, made total: a value the key never
    declared sorts after the declared ones rather than matching nothing."""
    rows = [sized("a", "zinnia"), sized("b", 3), sized("c", "XL"), sized("d", "S")]
    assert by_size(rows) == ["d", "c", "b", "a"]


def test_descending_reverses_the_values_and_a_missing_key_stays_last() -> None:
    rows = [sized("a"), sized("b", "S"), sized("c", "XL"), sized("d", "")]
    assert by_size(rows, read.Sort("size", descending=True, order=SIZES)) == [
        "c", "b", "a", "d"
    ]
    assert by_size(rows) == ["b", "c", "a", "d"]


def test_a_second_sort_breaks_the_ties_of_the_first() -> None:
    rows = [
        {**sized("a", "S"), "rank": 2},
        {**sized("b", "L"), "rank": 1},
        {**sized("c", "S"), "rank": 1},
    ]
    assert by_size(
        rows, read.Sort("size", order=SIZES), read.Sort("rank", descending=True)
    ) == ["a", "c", "b"]


def test_the_slug_is_the_last_tie_break() -> None:
    rows = [sized("c", "S"), sized("a", "S"), sized("b", "S")]
    assert by_size(rows) == ["a", "b", "c"]
    assert by_size(rows, read.Sort("size", descending=True, order=SIZES)) == [
        "a", "b", "c"
    ]


def test_a_sort_keeps_the_states_in_their_declared_order() -> None:
    rows = [sized("a", "S", "orchard"), sized("b", "XL"), sized("c", None, "greenhouse")]
    assert by_size(rows) == ["b", "c", "a"]


def test_each_state_sorts_by_its_own_sorts_and_one_with_none_by_slug() -> None:
    """The declared default: `greenhouse` by size, `orchard` by rank
    descending, and a third state named in no sort comes back by slug."""
    rows = [
        {**sized("a", "XL"), "rank": 1},
        {**sized("b", "S"), "rank": 2},
        {**sized("c", "XL", "orchard"), "rank": 1},
        {**sized("d", "S", "orchard"), "rank": 2},
        sized("f", "S", "shed"),
        sized("e", "XL", "shed"),
    ]
    sorts = {
        "greenhouse": [read.Sort("size", order=SIZES)],
        "orchard": [read.Sort("rank", descending=True)],
    }
    result, unsorted = read.ordered(rows, sorts, (*STATES, "shed"))
    assert slugs(result) == ["b", "a", "d", "c", "e", "f"]
    assert unsorted == []


def test_a_list_value_sorts_by_its_entries_in_order() -> None:
    rows = [sized("a", ["M", "S"]), sized("b", ["S", "XL"]), sized("c", ["S"])]
    assert by_size(rows) == ["c", "b", "a"]


def test_the_sort_names_each_row_missing_each_key() -> None:
    rows = [sized("a"), {**sized("b", "S"), "rank": 1}]
    given = [read.Sort("size", order=SIZES), read.Sort("rank")]
    _, unsorted = read.ordered(rows, dict.fromkeys(STATES, given), STATES)
    assert unsorted == [
        {"slug": "a", "key": "size", "path": "greenhouse/a.md"},
        {"slug": "a", "key": "rank", "path": "greenhouse/a.md"},
    ]


def test_a_sort_naming_no_key_refuses_by_name(tree: Declaration) -> None:
    with pytest.raises(Refusal) as refusal:
        read.sorting(tree, "-cultivarr")
    assert "--sort" in str(refusal.value) and "cultivarr" in str(refusal.value)


def test_a_leading_dash_sorts_descending_by_the_keys_declared_order(
    tree: Declaration,
) -> None:
    assert read.sorting(tree, "-cultivar") == read.Sort(
        "cultivar", descending=True, order=("heirloom", "hybrid")
    )
    assert read.sorting(tree, "rootstock") == read.Sort("rootstock")


def test_claim_status_sorts_in_the_probes_order(tree: Declaration) -> None:
    assert read.sorting(tree, "claim-status").order == claim.STATUSES


def test_a_value_nothing_carries_gives_no_rows() -> None:
    assert read.matching(ROWS, [read.comparison("state", "cold-frame")]) == []


def test_a_bare_value_means_equals() -> None:
    assert read.comparison("cultivar", "heirloom", CULTIVARS) == read.comparison(
        "cultivar", "=heirloom", CULTIVARS
    )


def test_a_value_outside_a_keys_values_refuses_by_name() -> None:
    """1-3 got this from `click.Choice`, which cannot see past a `>=`. The
    check moved here so the refusal survives the operator."""
    with pytest.raises(Refusal) as refusal:
        read.comparison("cultivar", ">=windfall", CULTIVARS)
    assert '--cultivar names "windfall"' in str(refusal.value)
    assert "heirloom, hybrid" in str(refusal.value)


def test_an_ordered_filter_orders_by_the_keys_declared_values() -> None:
    """`>=hybrid` means "hybrid or later" only because plan.toml lists
    heirloom before hybrid. The tool knows no cultivars."""
    tests = [read.comparison("cultivar", ">=hybrid", CULTIVARS)]
    assert slugs(read.matching(ROWS, tests)) == ["b"]
    tests = [read.comparison("cultivar", "<=hybrid", CULTIVARS)]
    assert slugs(read.matching(ROWS, tests)) == ["a", "b"]


def test_an_ordered_filter_never_matches_an_item_carrying_nothing() -> None:
    tests = [read.comparison("cultivar", ">=heirloom", CULTIVARS)]
    assert "c" not in slugs(read.matching(ROWS, tests))


def test_a_free_text_key_orders_as_text() -> None:
    rows = [{"slug": "a", "rootstock": "M26"}, {"slug": "b", "rootstock": "M9"}]
    tests = [read.comparison("rootstock", "<M5")]
    assert slugs(read.matching(rows, tests)) == ["a"]


PLACES = [
    {"slug": "a", "position": 50},
    {"slug": "b", "position": 100},
    {"slug": "c", "position": 1000},
]


def test_an_ordered_filter_compares_numbers_as_numbers() -> None:
    """As text, `"50"` sorts above `"100"` and `"1000"` below it — so the
    whole comparison would be wrong in both directions. One rule, stated
    once: a comparison is numeric when both sides parse as numbers."""
    assert slugs(read.matching(PLACES, [read.comparison("position", ">=100")])) == [
        "b",
        "c",
    ]
    assert slugs(read.matching(PLACES, [read.comparison("position", "<100")])) == ["a"]


def test_a_numeric_filter_still_matches_by_value_exactly() -> None:
    assert slugs(read.matching(PLACES, [read.comparison("position", "100")])) == ["b"]


def test_text_that_is_not_a_number_still_compares_as_text() -> None:
    """The rule is *both* sides. A key holding `M26` against `<M5` is the
    ordinary text comparison it always was."""
    rows = [{"slug": "a", "rootstock": "M26"}, {"slug": "b", "rootstock": "M9"}]
    assert slugs(read.matching(rows, [read.comparison("rootstock", "<M5")])) == ["a"]


def test_a_number_against_a_word_compares_as_text() -> None:
    """Only one side parses, so neither is treated as arithmetic — rather
    than the comparison refusing or silently matching nothing."""
    rows = [{"slug": "a", "rootstock": "100"}]
    assert slugs(read.matching(rows, [read.comparison("rootstock", ">M9")])) == []


def test_not_equal_also_matches_an_item_carrying_nothing() -> None:
    """An item with no cultivar is genuinely not heirloom. Absence is what
    `--lacks` asks about; this asks about the value."""
    tests = [read.comparison("cultivar", "!=heirloom", CULTIVARS)]
    assert slugs(read.matching(ROWS, tests)) == ["b", "c"]


def test_a_filter_matches_any_entry_of_a_list_value() -> None:
    """A list is the several values it holds, not one value, so `--after b`
    asks the question a person means by it."""
    assert slugs(read.matching(ROWS, [read.comparison("after", "b")])) == ["a"]


# --------------------------------------------------------------------------
# `:`, drawn from: the all-of question, over a list and over one value
# --------------------------------------------------------------------------
#
# The inclusion filter above answers "does this contain"; these answer "is
# every value one of these". 14-2 added the operator because inclusion is the
# dangerous direction: a section carrying `["unattended", "operator-led"]`
# matches `--has interaction-type=unattended` and reads as safe to run
# unattended when it is not.

PESTS = ("aphid", "canker", "scab")

INFESTED = [
    {"slug": "one", "pest": ["aphid"], "cultivar": "heirloom"},
    {"slug": "mixed", "pest": ["aphid", "canker"], "cultivar": "hybrid"},
    {"slug": "two", "pest": ["aphid", "scab"], "cultivar": None},
    {"slug": "clean", "pest": None, "cultivar": "heirloom"},
]


def test_drawn_from_asks_the_all_of_question_over_a_list() -> None:
    """The finding, answered: `=aphid` returns `mixed` too, and this does
    not. Both readings of the same three rows, side by side."""
    assert slugs(read.matching(INFESTED, [read.comparison("pest", "aphid", PESTS)])) == [
        "one",
        "mixed",
        "two",
    ]
    drawn = read.comparison("pest", ":aphid,scab", PESTS)
    assert slugs(read.matching(INFESTED, [drawn])) == ["one", "two"]


def test_drawn_from_degenerates_to_is_one_of_over_a_single_value() -> None:
    """One rule with two degenerations rather than a list-valued arm: over a
    key holding one value it asks the question the read had no spelling for."""
    drawn = read.comparison("cultivar", ":heirloom,hybrid", CULTIVARS)
    assert slugs(read.matching(INFESTED, [drawn])) == ["one", "mixed", "clean"]


def test_drawn_from_does_not_match_an_item_carrying_nothing() -> None:
    """The other polarity from `test_not_equal_also_matches_an_item_carrying_
    nothing` above, and read beside it. `--has` is the presence word, and a
    guard has to be conservative about an item that says nothing."""
    drawn = read.comparison("pest", ":aphid,canker,scab", PESTS)
    assert "clean" not in slugs(read.matching(INFESTED, [drawn]))


def test_a_key_present_but_empty_is_not_drawn_from_anything() -> None:
    """`_empty`'s rule, rather than a second one beside it: `pest = []`
    carries nothing, so it is the carrying-nothing case again."""
    rows = [{"slug": "a", "pest": []}]
    drawn = read.comparison("pest", ":aphid", PESTS)
    assert read.matching(rows, [drawn]) == []


def test_the_state_filter_reaches_the_operator_too() -> None:
    """The reason it is an operator rather than a fourth filter word: `--state`
    goes through the same parse, so this arrived with no arm of its own."""
    drawn = read.comparison("state", ":greenhouse,orchard", ("greenhouse", "orchard"))
    assert slugs(read.matching(ROWS, [drawn])) == ["a", "b", "c"]
    drawn = read.comparison("state", ":orchard", ("greenhouse", "orchard"))
    assert slugs(read.matching(ROWS, [drawn])) == ["b", "c"]


def test_has_and_lacks_ask_about_presence() -> None:
    assert slugs(read.matching(ROWS, [read.presence("cultivar", carried=True)])) == [
        "a",
        "b",
    ]
    assert slugs(read.matching(ROWS, [read.presence("cultivar", carried=False)])) == [
        "c"
    ]


def test_a_key_present_but_empty_reads_as_missing() -> None:
    """The same rule a transition's `requires` uses, rather than a second one
    that could disagree with it: `after = []` carries nothing."""
    assert slugs(read.matching(ROWS, [read.presence("after", carried=True)])) == ["a"]


def test_matching_does_not_alias_the_rows_it_was_given() -> None:
    (row,) = read.matching(ROWS, [read.comparison("slug", "a")])
    row["slug"] = "mutated"
    assert ROWS[0]["slug"] == "a"


# --------------------------------------------------------------------------
# `--has KEY[OP]VALUE`: the read's whole filter grammar over a key
# --------------------------------------------------------------------------
#
# Pure over a loaded declaration, so these take the fixture's file rather than
# a `tmp_path`. 13-3 folded a flag per declared key into this one parse: the
# 20 options were all doing what `--has` already did — name a key off
# `carried`, then say something about it.


@pytest.fixture
def declared() -> Declaration:
    return load(FIXTURES / "plan.toml")


@pytest.mark.parametrize(
    "given, operator, value",
    [
        ("cultivar=heirloom", "=", "heirloom"),
        ("cultivar!=heirloom", "!=", "heirloom"),
        ("position>=100", ">=", "100"),
        ("position<=100", "<=", "100"),
        ("position>100", ">", "100"),
        ("position<100", "<", "100"),
    ],
)
def test_each_operator_splits_off_the_key(
    declared: Declaration, given: str, operator: str, value: str
) -> None:
    """`>=` before `>`, which is why the longest operator is found first: the
    key is whatever stands before the earliest operator character."""
    test = read.filtering(declared, given)
    assert (test.operator, test.value) == (operator, value)
    assert test.key == given.split(operator)[0]


def test_a_bare_key_asks_about_presence(declared: Declaration) -> None:
    """Its meaning before the fold, unchanged: a key present but empty carries
    nothing, so there is nothing else the bare form could mean."""
    assert read.filtering(declared, "cultivar") == read.presence(
        "cultivar", carried=True
    )


def test_a_key_with_declared_values_still_orders_by_them(
    declared: Declaration,
) -> None:
    """The closed set survives the fold, which is the whole reason `>=` means
    anything: `heirloom` is before `hybrid` because plan.toml lists it there."""
    test = read.filtering(declared, "cultivar>=hybrid")
    assert test.order == ("heirloom", "hybrid")
    assert slugs(read.matching(ROWS, [test])) == ["b"]


def test_the_one_derived_key_with_a_closed_set_keeps_it(
    declared: Declaration,
) -> None:
    """`claim-status` holds the probe's own words, which are the tool's list
    rather than something the tree said."""
    assert read.filtering(declared, "claim-status=dead").order == claim.STATUSES
    with pytest.raises(Refusal) as refusal:
        read.filtering(declared, "claim-status=zzz")
    assert "--has" in str(refusal.value) and claim.DEAD in str(refusal.value)


def test_a_key_the_tree_answers_is_refused_against_nothing(
    declared: Declaration,
) -> None:
    """A holder, a count of days, a title: whatever the corpus put there, so
    there is no set to name and it compares as text or as a number."""
    for given in ("claimed-by=nobody", "stale-days>=14", "rootstock=M26"):
        assert read.filtering(declared, given).order is None


def test_a_key_nothing_carries_refuses_by_name(declared: Declaration) -> None:
    """`--has` names a key rather than a value, so it gets the typo detector
    `head_errors` gives a head — over the whole roster, since the fold."""
    with pytest.raises(Refusal) as refusal:
        read.filtering(declared, "cultivarr=heirloom")
    assert '--has names "cultivarr"' in str(refusal.value)
    assert "not a key an item carries" in str(refusal.value)


def test_a_value_outside_a_keys_values_names_how_it_was_asked(
    declared: Declaration,
) -> None:
    """The refusal says `--has`, because that is what the caller typed. It is
    the reason `comparison` takes the option rather than spelling `--<key>`."""
    with pytest.raises(Refusal) as refusal:
        read.filtering(declared, "cultivar>=windfall")
    assert '--has names "windfall"' in str(refusal.value)
    assert "not a declared value of cultivar" in str(refusal.value)


def test_a_comparison_with_no_key_at_all_refuses(declared: Declaration) -> None:
    """Loud rather than a filter over the empty string."""
    with pytest.raises(Refusal):
        read.filtering(declared, "=heirloom")


def test_the_option_a_refusal_names_defaults_to_the_key() -> None:
    """`--state` is the one caller that is not a key, and the default is what
    keeps its refusal saying its own word."""
    with pytest.raises(Refusal) as refusal:
        read.comparison("state", "zzz", ("greenhouse",))
    assert '--state names "zzz"' in str(refusal.value)


def test_known_names_the_option_it_was_asked_through(
    declared: Declaration,
) -> None:
    """`--lacks` is the second caller, and it names itself the same way."""
    assert read.known(declared, "--lacks", "cultivar") == "cultivar"
    with pytest.raises(Refusal) as refusal:
        read.known(declared, "--lacks", "zzz")
    assert '--lacks names "zzz"' in str(refusal.value)


def test_drawn_from_parses_as_its_own_operator(declared: Declaration) -> None:
    """The several values ride in `value` as they were typed, and are read
    back by the one splitter. A second field holding them parsed is a thing
    that can disagree with what the caller asked for."""
    test = read.filtering(declared, "pest:aphid,scab")
    assert (test.key, test.operator) == ("pest", read.DRAWN)
    assert read._drawn(test.value) == ["aphid", "scab"]


def test_every_value_a_colon_names_is_refused_on_its_own(
    declared: Declaration,
) -> None:
    """The refusal names the entry rather than the whole token, which is the
    shape the single-value refusal has used since 1-3."""
    with pytest.raises(Refusal) as refusal:
        read.filtering(declared, "pest:aphid,windfall")
    assert '--has names "windfall"' in str(refusal.value)
    assert "not a declared value of pest" in str(refusal.value)


@pytest.mark.parametrize("given", ["pest:", "pest:aphid,", "pest:,scab"])
def test_a_colon_naming_no_value_refuses(declared: Declaration, given: str) -> None:
    """Without this a key with no declared `values` would take the empty set
    and match nothing quietly, which is the failure mode the
    make-problems-visible rule names."""
    with pytest.raises(Refusal) as refusal:
        read.filtering(declared, given)
    assert "empty value" in str(refusal.value)


# --------------------------------------------------------------------------
# The resolver: the same traversal, tree-wide
# --------------------------------------------------------------------------


def test_a_unique_prefix_resolves_across_states(tree: Declaration) -> None:
    """1-3's resolver globbed one directory. This one is the listing."""
    file(tree, "orchard", "a-seedling.md")
    assert read.resolve(tree, "a-s").path.stem == "a-seedling"


def test_a_full_slug_wins_over_a_longer_sibling(tree: Declaration) -> None:
    """Otherwise filing `a-seedling` would make `a-seed` unaddressable for the
    rest of its life."""
    file(tree, "greenhouse", "a-seed.md")
    file(tree, "orchard", "a-seedling.md")
    assert read.resolve(tree, "a-seed").path.stem == "a-seed"


def test_an_ambiguous_prefix_refuses_naming_its_candidates(
    tree: Declaration,
) -> None:
    file(tree, "greenhouse", "a-seedling.md")
    file(tree, "orchard", "a-second-seedling.md")
    with pytest.raises(Refusal) as refusal:
        read.resolve(tree, "a-se")
    assert '"a-se" names 2 items' in str(refusal.value)
    assert "a-seedling" in str(refusal.value)
    assert "a-second-seedling" in str(refusal.value)


def test_a_prefix_matching_nothing_names_its_near_misses(tree: Declaration) -> None:
    file(tree, "greenhouse", "a-seedling.md")
    with pytest.raises(Refusal) as refusal:
        read.resolve(tree, "a-seedlingg")
    assert 'no item starts with "a-seedlingg"' in str(refusal.value)
    assert "nearest: a-seedling" in str(refusal.value)


def test_a_prefix_matching_nothing_at_all_refuses_without_guessing(
    tree: Declaration,
) -> None:
    file(tree, "greenhouse", "a-seedling.md")
    with pytest.raises(Refusal) as refusal:
        read.resolve(tree, "zzzz")
    assert str(refusal.value) == 'no item starts with "zzzz"'


def test_a_slug_held_in_two_states_refuses_naming_both(tree: Declaration) -> None:
    """A slug is the one handle an item answers to, so two files holding one
    is a broken tree. Refusing names both rather than picking one."""
    first = file(tree, "greenhouse", "a-seedling.md")
    second = file(tree, "orchard", "a-seedling.md")
    with pytest.raises(Refusal) as refusal:
        read.resolve(tree, "a-seedling")
    assert str(first.relative_to(tree.root)) in str(refusal.value)
    assert str(second.relative_to(tree.root)) in str(refusal.value)


def test_the_resolver_still_lists_a_duplicated_slug(tree: Declaration) -> None:
    """The listing is how you find out what to fix, so it does not refuse
    what the resolver cannot act on."""
    file(tree, "greenhouse", "a-seedling.md")
    file(tree, "orchard", "a-seedling.md")
    assert len(read.items(tree)) == 2



# --------------------------------------------------------------------------
# The rules under the handle: pure, so they grade with no tmp_path
# --------------------------------------------------------------------------

#: ``(slug, where)`` pairs, which is all `read.chosen` is given. The
#: ``where`` is only ever read back in the duplicated-slug refusal, so
#: everything else here can say the same word twice.
NAMED = (
    ("a-seed", "greenhouse/a-seed.md"),
    ("a-seedling", "orchard/a-seedling.md"),
    ("another-seedling", "orchard/another-seedling.md"),
)


def test_a_full_slug_names_itself_ahead_of_a_longer_slug_it_prefixes() -> None:
    """The rule that keeps `a-seed` addressable for the rest of its life once
    `a-seedling` is filed."""
    assert read.chosen(NAMED, "a-seed") == "a-seed"


def test_a_unique_prefix_names_the_one_slug_it_starts() -> None:
    assert read.chosen(NAMED, "ano") == "another-seedling"


def test_an_ambiguous_prefix_names_its_candidates_purely() -> None:
    with pytest.raises(Refusal) as refusal:
        read.chosen(NAMED, "a-see")
    assert '"a-see" names 2 items' in str(refusal.value)
    assert "a-seed" in str(refusal.value) and "a-seedling" in str(refusal.value)


def test_an_ambiguous_prefix_names_ten_candidates_and_counts_the_rest() -> None:
    """`show a-` printed 28 slugs on one line. Ten, one per message so each
    gets its own line at the CLI, then how many were left out, so nothing is
    hidden and the refusal is readable."""
    many = [(f"a-seed-{n:02}", f"greenhouse/a-seed-{n:02}.md") for n in range(30)]
    with pytest.raises(Refusal) as refusal:
        read.chosen(many, "a-")
    headline, *named, rest = refusal.value.messages
    assert headline == '"a-" names 30 items. Say more'
    assert named == [f"a-seed-{n:02}" for n in range(10)]
    assert rest == "and 20 more"


def test_a_near_miss_is_ranked_by_the_start_of_each_slug() -> None:
    """Over whole slugs, a short typo against a long slug scored low and three
    short strangers won. Against each slug's start it comes first."""
    meant = "a-checker-s-route-to-the-far-end-of-the-garden-and-back"
    named = [
        (slug, "x")
        for slug in (meant, "a-check", "a-cheese-route", "a-chore", "a-sheet-s-rot")
    ]
    with pytest.raises(Refusal) as refusal:
        read.chosen(named, "a-cheker-s-route")
    assert f"nearest: {meant}, " in str(refusal.value)


@pytest.mark.parametrize("handle", ["235", "23-1"])
def test_a_number_as_a_handle_is_told_where_numbers_are_found(handle) -> None:
    """A number no live item carries never resolves, and that stays. The
    refusal says so, and that `show` is where a live number is found."""
    with pytest.raises(Refusal) as refusal:
        read.chosen(NAMED, handle)
    said = str(refusal.value)
    assert f"no live item carries {handle.split('-')[0]}, so it names an archived" in said
    assert "`fileplan show` finds a live section by its number" in said
    assert "a verb that writes takes a slug" in said


@pytest.mark.parametrize(
    "handle, said",
    [
        ("23-1", "23-1 is a sub-phase of `a-seedling`: `fileplan show a-seedling 23-1`"),
        ("23-4a", "23-4a is a sub-phase of `a-seedling`: `fileplan show a-seedling 23-4a`"),
        ("23", "23 is the number `a-seedling` carries: `fileplan show a-seedling`"),
    ],
)
def test_a_live_number_as_a_handle_names_its_item_and_the_command(handle, said) -> None:
    """Still a refusal, since a number is never a handle for a verb that
    writes. A live number says which item carries it rather than calling it
    archived. `show` asks `numbered_handle` first, and never gets here."""
    with pytest.raises(Refusal) as refusal:
        read.chosen(NAMED, handle, {"23": "a-seedling"})
    assert str(refusal.value).endswith(said)
    assert "archived" not in str(refusal.value)


def test_a_number_no_live_item_carries_keeps_the_archived_wording() -> None:
    with pytest.raises(Refusal) as refusal:
        read.chosen(NAMED, "7-2", {"23": "a-seedling"})
    assert "no live item carries 7, so it names an archived section" in str(
        refusal.value
    )


@pytest.mark.parametrize(
    "handle, found",
    [
        ("23", ("a-seedling", None)),
        ("23-1", ("a-seedling", "23-1")),
        ("23-4a", ("a-seedling", "23-4a")),
        ("7", None),
        ("7-2", None),
        ("a-seed", None),
    ],
)
def test_a_live_number_is_found_for_show_and_nothing_else_is(handle, found) -> None:
    """`show`'s one extra rule. A live number gives its slug, and a sub-phase
    name gives the slug and the name. A number nobody carries, and a handle
    that is no number, give nothing, and `chosen` has the last word."""
    assert read.numbered_handle(NAMED, handle, {"23": "a-seedling"}) == found


def test_a_slug_outranks_a_number() -> None:
    """A slug starting with the digits wins, as it does in `chosen` today, so
    nothing is guessed: the number is tried only where the slugs found none."""
    named = (*NAMED, ("23-skidoo", "orchard/23-skidoo.md"))
    assert read.numbered_handle(named, "23", {"23": "a-seedling"}) is None
    assert read.chosen(named, "23", {"23": "a-seedling"}) == "23-skidoo"


def test_a_handle_matching_nothing_names_its_near_misses_purely() -> None:
    with pytest.raises(Refusal) as refusal:
        read.chosen(NAMED, "a-seedlingg")
    assert 'no item starts with "a-seedlingg"' in str(refusal.value)
    assert "nearest: a-seedling" in str(refusal.value)


def test_two_files_holding_one_slug_refuse_naming_both_wheres() -> None:
    """The one refusal that reads ``where`` back. `resolve` passes the item's
    path and `show` passes the row's, and both are true of the same file —
    which is the whole reason the pair is a pair."""
    duplicated = (("a-seedling", "greenhouse/a-seedling.md"), *NAMED[1:])
    with pytest.raises(Refusal) as refusal:
        read.chosen(duplicated, "a-seedling")
    assert "greenhouse/a-seedling.md" in str(refusal.value)
    assert "orchard/a-seedling.md" in str(refusal.value)


def test_the_resolver_and_the_pure_rules_agree(tree: Declaration) -> None:
    """The two are pinned together by `resolve`'s own tests above; this says
    out loud that they are one implementation rather than two that match."""
    file(tree, "greenhouse", "a-seed.md")
    file(tree, "orchard", "a-seedling.md")
    named = [(one.slug, str(one.path)) for one in read.items(tree)]
    assert read.resolve(tree, "a-seed").slug == read.chosen(named, "a-seed")


# --------------------------------------------------------------------------
# The roster: no key is carried and unreachable
# --------------------------------------------------------------------------


def test_a_row_carries_exactly_the_derived_keys_the_roster_names(
    tree: Declaration,
) -> None:
    """**The roster pin.** Which keys a row carries from outside the head is
    `DERIVED_KEYS`' single answer, and this is what makes "no fourth copy"
    checkable rather than asserted: a key the row layer grew without the
    roster, or one the roster gates differently from the row, fails here.

    Order too, not just membership — the roster is written in row order, and
    a filter list that named them in another order would be describing a
    different row.
    """
    file(tree, "orchard", "a-seedling.md")
    assert tree.derived, "the fixture derives nothing, so this proves nothing"
    [row] = read.rows(tree, read.items(tree))
    assert [key for key in row if key in DERIVABLE_KEYS] == list(tree.derived)


def test_a_declaration_that_derives_nothing_carries_none_of_them(
    tmp_path: Path,
) -> None:
    """The negative half, graded on a document rather than on the fixture:
    every gate off means every name absent from the row, so a field that
    arrived unconditionally would fail here rather than in whatever consumer
    tree first had no git in it."""
    (tmp_path / "plan.toml").write_text(
        '[states.greenhouse]\npath = "greenhouse"\n'
    )
    plain = load(tmp_path / "plan.toml")
    (tmp_path / "greenhouse").mkdir()
    (tmp_path / "greenhouse" / "a-seedling.md").write_text(
        '+++\ntitle = "A seedling"\n+++\n\nThe body starts here.\n'
    )
    assert plain.derived == ()
    [row] = read.rows(plain, read.items(plain))
    assert [key for key in row if key in DERIVABLE_KEYS] == []


# --------------------------------------------------------------------------
# `unfound`: a `cutting` naming a bullet its batch no longer has
# --------------------------------------------------------------------------


def lined_out(tree: Declaration, cutting: str, *, batch: bool = True) -> None:
    """A seedling lined out of `a-batch` as `cutting`, and the batch holding
    `c1` and `c2a`: what a hand split of `c2` leaves behind. ``batch=False``
    leaves the batch out, as when a closed investigation is gone."""
    if batch:
        file(
            tree,
            "propagator",
            "a-batch.md",
            '+++\ntitle = "A batch"\n+++\n\n### Cuttings\n'
            "- **c1 — The first**\n- **c2a — Half of the second**\n",
        )
    file(
        tree,
        "greenhouse",
        "a-seedling.md",
        f'+++\ntitle = "A seedling"\nbatch = "a-batch"\ncutting = "{cutting}"\n+++\n\nProse.\n',
    )


def test_the_listing_names_a_cutting_whose_bullet_is_missing(
    tree: Declaration,
) -> None:
    """**The done line's report.** A split done by hand is loud: the seedling
    still names `c2`, and no bullet in its batch is called that any more."""
    lined_out(tree, "c2")
    assert read.listing(tree).unfound == [
        {
            "slug": "a-seedling",
            "path": "greenhouse/a-seedling.md",
            "key": "cutting",
            "value": "c2",
            "carrier": "a-batch",
        }
    ]


def test_a_cutting_whose_bullet_is_there_is_not_named(tree: Declaration) -> None:
    lined_out(tree, "c2a")
    assert read.listing(tree).unfound == []


def test_a_cutting_whose_batch_is_gone_is_not_named(tree: Declaration) -> None:
    """Provenance outlives its carrier, so a closed batch is normal rather
    than a report."""
    lined_out(tree, "c2", batch=False)
    assert read.listing(tree).unfound == []
