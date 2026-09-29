"""The generic executor: preconditions, creating, moving, and the handle.

Everything grades against ``tests/fixtures/plan.toml``, never the repo's own
declaration — 1-1's rule, and the reason `sprout` and `transplant` are what
these tests drive. The fixture holds both shapes: `sprout` creates into
`greenhouse` with no ``from``; `transplant` moves greenhouse → orchard with
``requires``, ``refuses``, ``sets`` and ``drops``. One executor runs both, and
no code anywhere knows either name. `harvest` moves back out of `orchard`,
which is the fixture's ``queued`` state, so the capability has a declared path
in and a declared path out.

The precondition half takes no ``tmp_path``: `offer_errors` is pure
over a head and a transition, the same split `fileplan.declaration` and
`fileplan.item` keep.
"""

from __future__ import annotations

import dataclasses
import os
import re
import socket
from pathlib import Path

import pytest

from conftest import FIXTURE_FILES

from fileplan import claim, lock, numbered, subphase
from fileplan.claim import Identity
from fileplan.declaration import (
    Declaration,
    Refusal,
    Transition,
    load,
)
from fileplan.item import Item, read, write
from fileplan.read import items as read_items
from fileplan.read import rows as read_rows
from fileplan.transition import (
    execute,
    offer_errors,
    dangle_errors,
    unmarked_errors,
    value_errors,
)

# Sibling test modules, not a package: `tests/` is on `sys.path` at
# collection. Imported for the two things a second session needs — a stamp,
# and a pid that is honestly dead — so each has one home rather than a copy.
from test_claim import TAKEN, exited

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def tree(tmp_path: Path) -> Declaration:
    """The fixture declaration copied into ``tmp_path``, its directories made."""
    for name in FIXTURE_FILES:
        (tmp_path / name).write_text((FIXTURES / name).read_text())
    declaration = load(tmp_path / "plan.toml")
    for state in declaration.states.values():
        (tmp_path / state.path).mkdir(parents=True)
    return declaration


def seedling(declaration: Declaration, name: str, text: str) -> Path:
    path = declaration.root / declaration.states["greenhouse"].path / f"{name}.md"
    path.write_text(text, encoding="utf-8")
    return path


READY = '''\
+++
title = "A seedling"
cultivar = "heirloom"
tag = "spring"
+++

# A seedling

The body starts here.
'''


#: The same seedling once `tend` has been run on it. The fixture's
#: `potting-bench` will not let one leave without a `rootstock`, so a test
#: that hand-places an item there and beds it out starts from this rather
#: than from a `tend` — which would take a claim and change what it proves.
TENDED = READY.replace(
    'cultivar = "heirloom"', 'cultivar = "heirloom"\nrootstock = "M9"'
)


# --------------------------------------------------------------------------
# Preconditions: pure
# --------------------------------------------------------------------------


@pytest.fixture
def transplant(tree: Declaration) -> Transition:
    return tree.transitions["transplant"]


def test_a_missing_required_key_refuses_naming_it(transplant: Transition) -> None:
    assert offer_errors({"title": "A seedling"}, transplant) == [
        'transplant requires "cultivar", which this item does not carry'
    ]


def test_a_refused_value_refuses_naming_the_key_and_the_value(
    transplant: Transition,
) -> None:
    assert offer_errors({"cultivar": "hybrid"}, transplant) == [
        'transplant refuses cultivar = "hybrid"'
    ]


def test_a_value_outside_the_keys_values_but_not_refused_passes(
    transplant: Transition,
) -> None:
    """`refuses` is the grading a transition does. A value the key never
    declared is not thereby refused — that would be a second rule, spelled
    somewhere else, that could disagree with this one."""
    assert offer_errors({"cultivar": "windfall"}, transplant) == []


def test_a_satisfied_head_produces_no_errors(transplant: Transition) -> None:
    head = {"cultivar": "heirloom", "tag": "spring"}
    assert offer_errors(head, transplant) == []


def test_a_key_present_but_empty_reads_as_missing(transplant: Transition) -> None:
    assert offer_errors({"cultivar": ""}, transplant) == [
        'transplant requires "cultivar", which this item does not carry'
    ]


@pytest.fixture
def harvest(tree: Declaration) -> Transition:
    """The fixture's verb out of the orchard, and the one that refuses over a
    list-valued head: no tree with canker on it comes indoors."""
    return tree.transitions["harvest"]


def test_a_scalar_given_for_a_list_valued_key_refuses_by_name(
    tree: Declaration, transplant: Transition
) -> None:
    """The CLI cannot produce this — a repeating option always hands back a
    list — but `execute(values=…)` is the API a consumer's own tooling calls,
    and a head silently holding the wrong shape is what this refuses."""
    assert value_errors({"pest": "aphid"}, transplant, tree.keys) == [
        'transplant sets "pest", which is list-valued, and this run gave it '
        "one value rather than a list"
    ]


def test_a_list_given_for_a_key_that_is_not_refuses_by_name(
    tree: Declaration, transplant: Transition
) -> None:
    assert value_errors({"rootstock": ["M9", "M26"]}, transplant, tree.keys) == [
        'transplant sets "rootstock", which holds one value, and this run '
        "gave it a list"
    ]


def test_each_shape_given_as_declared_passes(
    tree: Declaration, transplant: Transition
) -> None:
    given = {"rootstock": "M9", "pest": ["aphid", "canker"]}
    assert value_errors(given, transplant, tree.keys) == []


def test_a_refused_entry_of_a_list_head_refuses_naming_that_entry(
    harvest: Transition,
) -> None:
    """`read.carries`' rule, one module over: a list is the several values it
    holds. The refusal names the **entry**, never the list — a message reading
    `pest = "[\'aphid\', \'canker\']"` names nothing a person declared."""
    assert offer_errors({"pest": ["aphid", "canker"]}, harvest) == [
        'harvest refuses pest = "canker"'
    ]


def test_a_list_head_carrying_none_of_the_refused_values_passes(
    harvest: Transition,
) -> None:
    assert offer_errors({"pest": ["aphid", "scab"]}, harvest) == []


def test_a_scalar_refusal_reads_exactly_as_it_did(transplant: Transition) -> None:
    """One rule for both shapes means the scalar message goes through the new
    arm too, so this pins that it comes out byte for byte unchanged."""
    assert offer_errors({"cultivar": "hybrid"}, transplant) == [
        'transplant refuses cultivar = "hybrid"'
    ]


def test_an_empty_list_still_reads_as_missing(harvest: Transition) -> None:
    """`_missing`'s rule, untouched: a key present but empty carries nothing,
    so a head with `pest = []` is refused by nothing and satisfies nothing."""
    assert offer_errors({"pest": []}, harvest) == []
    requiring = Transition(
        name="harvest",
        doc="method.md#harvest",
        help="Bring a tree in.",
        source="orchard",
        to="cold-frame",
        requires=("pest",),
    )
    assert offer_errors({"pest": []}, requiring) == [
        'harvest requires "pest", which this item does not carry'
    ]


# --------------------------------------------------------------------------
# Creating: a transition with no `from`
# --------------------------------------------------------------------------


def test_creating_writes_the_slug_into_the_destination_state(tree: Declaration) -> None:
    path = execute(
        tree, tree.transitions["sprout"], name="A seedling", body="Prose."
    )
    assert path == tree.root / "greenhouse" / "a-seedling.md"
    assert read(path, tree).head == {"title": "A seedling"}


def test_the_title_lands_in_the_head_without_being_declared(tree: Declaration) -> None:
    """`title` is intrinsic: the fixture declares no `[keys.title]`, and a head
    carrying one still reads clean."""
    assert "title" not in tree.keys
    path = execute(tree, tree.transitions["sprout"], name="A seedling", body="Prose.")
    assert read(path, tree)["title"] == "A seedling"


def test_a_set_key_lands_in_the_head(tree: Declaration) -> None:
    path = execute(
        tree,
        tree.transitions["sprout"],
        name="A seedling",
        body="Prose.",
        values={"cultivar": "heirloom"},
    )
    assert read(path, tree).head == {"title": "A seedling", "cultivar": "heirloom"}


def test_a_set_key_left_out_is_simply_absent(tree: Declaration) -> None:
    """Every `--option` is optional: a key that must be *present* is enforced
    by the next transition's `requires`, which already does that job."""
    path = execute(
        tree,
        tree.transitions["sprout"],
        name="A seedling",
        body="Prose.",
        values={"cultivar": None},
    )
    assert "cultivar" not in read(path, tree).head


def test_the_body_becomes_the_items_prose(tree: Declaration) -> None:
    path = execute(
        tree, tree.transitions["sprout"], name="A seedling", body="Why this matters."
    )
    assert path.read_text() == (
        '+++\ntitle = "A seedling"\n+++\n\nWhy this matters.\n'
    )


@pytest.mark.parametrize("body", [None, "", "   \n"])
def test_creating_without_a_body_refuses(tree: Declaration, body: str | None) -> None:
    """An item is a title and a description. One with no prose is intent that
    somebody pays to re-derive later, and re-deriving what was cheap to
    write down is the cost this repo refuses."""
    with pytest.raises(Refusal, match="needs a body"):
        execute(tree, tree.transitions["sprout"], name="A seedling", body=body)
    assert list((tree.root / "greenhouse").iterdir()) == []


def test_a_slug_taken_in_another_state_refuses_naming_the_file(
    tree: Declaration,
) -> None:
    """A slug is unique tree-wide, not per directory: a prefix that could name
    two items cannot resolve, and an `after` edge naming two cannot say which."""
    taken = tree.root / "orchard" / "a-seedling.md"
    taken.write_text(READY)
    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["sprout"], name="A seedling", body="Prose.")
    assert str(taken.relative_to(tree.root)) in str(refusal.value)
    assert list((tree.root / "greenhouse").iterdir()) == []


def test_a_slug_taken_in_the_destination_state_refuses(tree: Declaration) -> None:
    seedling(tree, "a-seedling", READY)
    with pytest.raises(Refusal, match="already held by"):
        execute(tree, tree.transitions["sprout"], name="A seedling", body="Prose.")
    assert seedling(tree, "a-seedling", READY).read_text() == READY


def test_a_title_that_reduces_to_nothing_refuses(tree: Declaration) -> None:
    with pytest.raises(Refusal, match="empty filename"):
        execute(tree, tree.transitions["sprout"], name="?!", body="Prose.")


# --------------------------------------------------------------------------
# `seeds`: the creating arm's third content source
# --------------------------------------------------------------------------
#
# `strike` is the fixture's **one** seeding verb, and `hardwood`/`softwood`
# are its two templates: a template is selected by name at the run, so a
# declaration with one has nothing to select between. `sprout` beside it
# creates without the half, which is what makes "on this verb and no other"
# provable rather than asserted.


def document(tree: Declaration, name: str) -> str:
    """The prose a declared template names, as the tree holds it."""
    return (tree.root / tree.templates[name].doc).read_text()


def struck(tree: Declaration) -> Path:
    """The batch `strike --from hardwood` files, with nothing else asked."""
    return execute(
        tree,
        tree.transitions["strike"],
        name="A batch",
        asked={"template": "hardwood"},
    )


def test_a_seeded_item_carries_the_named_document_byte_for_byte(
    tree: Declaration,
) -> None:
    """Verbatim: no substitution, no placeholders, nothing recording where it
    came from. The one difference from the file on disk is `_prose`'s
    separator, which is what a body looks like in *any* item file."""
    path = struck(tree)
    assert read(path, tree).body == "\n" + document(tree, "hardwood").strip("\n") + "\n"


def test_a_seeded_item_is_an_ordinary_item_of_the_creating_verb(
    tree: Declaration,
) -> None:
    """The body is the only thing the template supplies. The head is the
    verb's own — the title it was given and the keys it `sets` — so every
    other verb and every read already works on what comes out."""
    path = execute(
        tree,
        tree.transitions["strike"],
        name="A batch",
        values={"for-tree": "a-seedling", "for-step": "2-1"},
        asked={"template": "softwood"},
    )
    assert path == tree.root / "propagator" / "a-batch.md"
    assert read(path, tree).head == {
        "title": "A batch",
        "for-tree": "a-seedling",
        "for-step": "2-1",
    }
    assert read(path, tree).body.strip("\n") == document(tree, "softwood").strip("\n")


def test_a_template_and_a_body_in_one_run_refuse_naming_both(
    tree: Declaration,
) -> None:
    """Two content sources for one run is a **question**, not a default: an
    item has one body, and quietly letting either win would file prose the
    operator did not mean to file."""
    with pytest.raises(Refusal, match="both --from and --body"):
        execute(
            tree,
            tree.transitions["strike"],
            name="A batch",
            body="Prose.",
            asked={"template": "hardwood"},
        )
    assert list((tree.root / "propagator").iterdir()) == []


def test_an_undeclared_template_refuses_by_name_saying_what_is_declared(
    tree: Declaration,
) -> None:
    """By name, and with the names that would have worked: a refusal the
    operator can fix from what it said, which is `_disposing`'s shape over the
    other thing a run names and the declaration may not hold."""
    with pytest.raises(Refusal) as refusal:
        execute(
            tree,
            tree.transitions["strike"],
            name="A batch",
            asked={"template": "hardwod"},
        )
    said = str(refusal.value)
    assert 'no template is called "hardwod"' in said
    assert "hardwood, softwood" in said
    assert list((tree.root / "propagator").iterdir()) == []


def test_a_seeding_verb_with_no_templates_declared_says_so(tmp_path: Path) -> None:
    """The shape 9-1 deliberately left legal — a verb that seeds and a
    declaration holding nothing to seed from — and the one refusal that cannot
    name an alternative. It says the declaration is unfinished rather than
    listing nothing, which is `Declares`' absence-is-a-signal rule applied to
    a sentence."""
    for name in FIXTURE_FILES:
        (tmp_path / name).write_text((FIXTURES / name).read_text())
    text = (tmp_path / "plan.toml").read_text()
    (tmp_path / "plan.toml").write_text(
        "".join(
            chunk
            for chunk in re.split(r"(?m)^(?=\[)", text)
            if not chunk.startswith("[templates.")
        )
    )
    declaration = load(tmp_path / "plan.toml")
    assert declaration.templates == {}
    (tmp_path / declaration.states["propagator"].path).mkdir(parents=True)

    with pytest.raises(Refusal, match="No templates are declared"):
        execute(
            declaration,
            declaration.transitions["strike"],
            name="A batch",
            asked={"template": "hardwood"},
        )


def test_a_seeding_verb_given_neither_refuses_in_the_bodiless_words(
    tree: Declaration,
) -> None:
    """The existing refusal, unchanged and reached by the path it always was:
    `seeds` says a verb *may* be bodied from a template, so a run that names
    none is a run with no body at all."""
    with pytest.raises(Refusal, match="needs a body"):
        execute(tree, tree.transitions["strike"], name="A batch")
    assert list((tree.root / "propagator").iterdir()) == []


def test_a_seeded_run_whose_slug_is_taken_refuses_through_the_same_helper(
    tree: Declaration,
) -> None:
    """The collision is the creating verb's own, not a second spelling that
    could soften: a template says what the body is and nothing about which
    slugs are free."""
    struck(tree)
    with pytest.raises(Refusal, match="already held by"):
        struck(tree)


def test_a_check_on_a_seeded_run_names_the_template_and_reserves_nothing(
    tree: Declaration,
) -> None:
    """Built from what the arm **resolved**, so two runs that write different
    files do not print one sentence. The reservation is a write partway
    through this arm, so a seeded check must leave no file either."""
    before = snapshot(tree)
    said = execute(
        tree,
        tree.transitions["strike"],
        name="A batch",
        asked={"template": "hardwood"},
        check=True,
    )
    assert isinstance(said, str)
    assert "a-batch.md" in said
    assert 'take its body from the "hardwood" template' in said
    assert snapshot(tree) == before


def test_a_check_on_an_unseeded_run_says_nothing_about_a_template(
    tree: Declaration,
) -> None:
    """Absence is meaningful, the shape every other clause of the sentence
    has: the run would take its body from `--body`, and there is no template
    to name."""
    said = execute(
        tree,
        tree.transitions["strike"],
        name="A batch",
        body="Prose.",
        check=True,
    )
    assert "template" not in str(said)


def test_a_refused_seeding_check_gives_the_runs_own_refusal(
    tree: Declaration,
) -> None:
    """Byte for byte, because it is the same code raising it — the property
    the flag buys, over the arm's newest refusals."""
    with pytest.raises(Refusal) as checked:
        execute(
            tree,
            tree.transitions["strike"],
            name="A batch",
            asked={"template": "nowhere"},
            check=True,
        )
    with pytest.raises(Refusal) as ran:
        execute(
            tree,
            tree.transitions["strike"],
            name="A batch",
            asked={"template": "nowhere"},
        )
    assert str(checked.value) == str(ran.value)


# --------------------------------------------------------------------------
# Moving: a transition with a `from`
# --------------------------------------------------------------------------


def test_moving_moves_the_file_sets_and_drops(tree: Declaration) -> None:
    source = seedling(tree, "a-seedling", READY)
    path = execute(
        tree,
        tree.transitions["transplant"],
        name="a-seed",
        values={"rootstock": "M26"},
    )
    assert path == tree.root / "orchard" / "a-seedling.md"
    assert not source.exists()
    moved = read(path, tree)
    assert moved.state.name == "orchard"
    assert moved.head == {
        "title": "A seedling",
        "cultivar": "heirloom",
        "rootstock": "M26",
        # `orchard` is `queued`, so entering it writes a place. Nothing in
        # the declaration says so, and nothing should: see the capability's
        # own section below.
        "position": 100,
        # And `numbered`, so entering it mints a number. **2**, not 1: the
        # fixture's archive carries `## 1. A felled tree`, and a closed item's
        # heading is the only record that its number is taken.
        "number": 2,
    }


def test_a_move_drops_a_named_key_and_keeps_every_other(
    tree: Declaration,
) -> None:
    """One verb, both arms. `transplant` declares `drops = ["tag"]` and says
    nothing about `notebook`, so the same move that throws one fact away
    carries the other through. There is no code here to point at: `_move`
    keeps every head key the transition does not name. This is what that
    guarantee looks like from outside."""
    seedling(
        tree,
        "a-seedling",
        READY.replace('tag = "spring"', 'tag = "spring"\nnotebook = "notes.md"'),
    )
    path = execute(tree, tree.transitions["transplant"], name="a-seedling")
    head = read(path, tree).head
    assert "tag" not in head
    assert head["notebook"] == "notes.md"


def test_the_body_survives_a_move_byte_for_byte(tree: Declaration) -> None:
    """`str.splitlines()` would rewrite the form feed and the lone `\\r` as
    newlines. The body is prose the tool never interprets."""
    body = "# A seedling\n\nOne\x0ctwo\rthree\n\nNo trailing newline."
    seedling(tree, "a-seedling", f'+++\ncultivar = "heirloom"\n+++\n{body}')
    path = execute(tree, tree.transitions["transplant"], name="a-seedling")
    assert read(path, tree).body == body


def test_a_failed_precondition_refuses_and_writes_nothing(tree: Declaration) -> None:
    source = seedling(tree, "a-seedling", '+++\ntitle = "A seedling"\n+++\n\nProse.\n')
    before = source.read_bytes()
    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["transplant"], name="a-seedling")
    assert 'transplant requires "cultivar"' in str(refusal.value)
    assert source.read_bytes() == before
    assert list((tree.root / "orchard").iterdir()) == []


def test_a_refused_value_refuses_by_name_and_writes_nothing(tree: Declaration) -> None:
    source = seedling(tree, "a-seedling", '+++\ncultivar = "hybrid"\n+++\n\nProse.\n')
    before = source.read_bytes()
    with pytest.raises(Refusal, match='refuses cultivar = "hybrid"'):
        execute(tree, tree.transitions["transplant"], name="a-seedling")
    assert source.read_bytes() == before
    assert list((tree.root / "orchard").iterdir()) == []


def test_a_state_to_itself_transition_is_an_in_place_write(tree: Declaration) -> None:
    """No arm of its own: the source is unlinked only if the destination
    differs, so a self-loop falls out of the same code."""
    source = seedling(tree, "a-seedling", READY)
    prune = Transition(
        name="prune",
        doc="method.md#transplant",
        help="Prune a seedling where it stands.",
        to="greenhouse",
        source="greenhouse",
        drops=("tag",),
    )
    path = execute(tree, prune, name="a-seedling")
    assert path == source
    assert source.exists()
    assert "tag" not in read(path, tree).head


def test_a_slug_held_in_two_states_refuses_naming_both_files(
    tree: Declaration,
) -> None:
    """A slug is unique tree-wide, so this tree is already broken before the
    verb runs — and 1-4's resolver is what notices. It refuses naming both
    files rather than picking one, which is the same rule as the ambiguous
    prefix: never guess. (`_move`'s destination check is still there as the
    backstop for a duplicate appearing between the read and the write.)"""
    source = seedling(tree, "a-seedling", READY)
    blocker = tree.root / "orchard" / "a-seedling.md"
    blocker.write_text(READY)
    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["transplant"], name="a-seedling")
    assert "is held by 2 files" in str(refusal.value)
    assert str(source.relative_to(tree.root)) in str(refusal.value)
    assert str(blocker.relative_to(tree.root)) in str(refusal.value)
    assert source.exists()


# --------------------------------------------------------------------------
# The handle: a unique slug prefix, tree-wide
# --------------------------------------------------------------------------
#
# The rules themselves are 1-4's and are tested against `read.resolve` in
# `test_read.py`. What is re-pinned here is that the *executor* reaches them —
# 1-3 had its own resolver over one directory, and this is what would fail if
# a second one came back.


def test_a_unique_prefix_resolves(tree: Declaration) -> None:
    seedling(tree, "a-seedling", READY)
    assert execute(tree, tree.transitions["transplant"], name="a-s").name == (
        "a-seedling.md"
    )


def test_an_ambiguous_prefix_refuses_naming_its_candidates(tree: Declaration) -> None:
    seedling(tree, "a-seedling", READY)
    seedling(tree, "a-second-seedling", READY)
    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["transplant"], name="a-se")
    assert refusal.value.messages == [
        '"a-se" names 2 items. Say more',
        "a-second-seedling",
        "a-seedling",
    ]
    assert list((tree.root / "orchard").iterdir()) == []


def test_a_full_slug_always_names_itself(tree: Declaration) -> None:
    """Otherwise filing `a-seedling` would make `a-seed` unaddressable for the
    rest of its life."""
    seedling(tree, "a-seed", READY)
    seedling(tree, "a-seedling", READY)
    assert execute(tree, tree.transitions["transplant"], name="a-seed").name == (
        "a-seed.md"
    )


def test_a_prefix_matching_nothing_refuses_naming_near_misses(
    tree: Declaration,
) -> None:
    seedling(tree, "a-seedling", READY)
    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["transplant"], name="a-seedlingg")
    assert 'no item starts with "a-seedlingg"' in str(refusal.value)
    assert "nearest: a-seedling" in str(refusal.value)


def test_a_prefix_matching_nothing_at_all_refuses_without_guessing(
    tree: Declaration,
) -> None:
    seedling(tree, "a-seedling", READY)
    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["transplant"], name="zzzz")
    assert str(refusal.value) == 'no item starts with "zzzz"'


def test_an_item_in_another_state_refuses_by_naming_the_state_it_is_in(
    tree: Declaration,
) -> None:
    """1-3 resolved within the `from` state alone, so this said "no item in
    greenhouse" — true of that one directory, and useless to somebody who has
    just watched the item go past. The resolver is tree-wide now, so the
    refusal can say where the item actually is."""
    stranded = tree.root / "orchard" / "a-seedling.md"
    stranded.write_text(READY)
    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["transplant"], name="a-seedling")
    assert f"{stranded.relative_to(tree.root)} is in orchard" in str(refusal.value)
    assert "transplant moves an item out of greenhouse" in str(refusal.value)
    assert stranded.read_text() == READY


# --------------------------------------------------------------------------
# The `queued` capability: written on entry, dropped on exit
# --------------------------------------------------------------------------
#
# `orchard` is the fixture's `queued` state; `transplant` moves into it and
# `harvest` moves out of it to `cold-frame`. Neither declares anything about a
# place, and neither may — the key is written and dropped by the capability
# alone, so a `sets` or a `drops` naming it refuses back in `plan.toml`.
#
# The arithmetic itself is `tests/test_queued.py`, pure. What is pinned here
# is the seam: that the executor reaches it, on both shapes, before it writes.


def orchard(tree: Declaration, name: str, at: int | None = None) -> Path:
    """One seedling, transplanted into the orchard at a place."""
    seedling(tree, name, READY)
    return execute(
        tree, tree.transitions["transplant"], name=name, asked={"at": at}
    )


def places(tree: Declaration) -> dict[str, int | None]:
    return {
        one.slug: one.get("position")
        for one in read_items(tree)
        if one.state.name == "orchard"
    }


def test_a_move_into_a_queued_state_writes_a_place(tree: Declaration) -> None:
    seedling(tree, "a-seedling", READY)
    path = execute(tree, tree.transitions["transplant"], name="a-seedling")
    assert read(path, tree)["position"] == 100


def test_a_second_item_appends_past_the_first(tree: Declaration) -> None:
    orchard(tree, "a-seedling")
    orchard(tree, "b-seedling")
    assert places(tree) == {"a-seedling": 100, "b-seedling": 200}


def test_a_move_out_of_a_queued_state_drops_the_place(tree: Declaration) -> None:
    """`harvest` declares no `drops`, and must not: a place is a fact about
    being in the state, so it goes when the item does."""
    orchard(tree, "a-seedling")
    path = execute(tree, tree.transitions["harvest"], name="a-seedling")
    moved = read(path, tree)
    assert moved.state.name == "cold-frame"
    assert "position" not in moved.head
    assert moved["title"] == "A seedling"


def test_a_creating_transition_into_a_queued_state_gets_a_place(
    tree: Declaration,
) -> None:
    """The same seam. The fixture has no creating transition into `orchard`,
    so this builds one — what is being pinned is that `_create` and `_move`
    share the capability's code rather than each carrying a copy."""
    orchard(tree, "a-seedling")
    direct = Transition(
        name="direct-sow",
        doc="method.md#sprout",
        help="Sow straight into the orchard.",
        to="orchard",
    )
    path = execute(tree, direct, name="B seedling", body="Prose.")
    assert read(path, tree)["position"] == 200


def test_a_state_to_itself_move_replaces_without_a_duplicate(
    tree: Declaration,
) -> None:
    """The item being placed is left out of the places already taken, so it
    does not collide with itself — and it keeps one place, not two."""
    orchard(tree, "a-seedling")
    orchard(tree, "b-seedling")
    again = Transition(
        name="thin",
        doc="method.md#transplant",
        help="Move a tree in the orchard's order.",
        to="orchard",
        source="orchard",
    )
    execute(tree, again, name="b-seedling", asked={"above": "a-seedling"})
    assert places(tree) == {"b-seedling": 50, "a-seedling": 100}


def test_a_place_is_written_as_a_bare_integer(tree: Declaration) -> None:
    """Never quoted: the key is arithmetic, and `"1000"` sorts ahead of
    `"200"` as text."""
    path = orchard(tree, "a-seedling")
    assert "\nposition = 100\n" in path.read_text()


# --------------------------------------------------------------------------
# Placement refusals: every one of them writes nothing
# --------------------------------------------------------------------------


def test_an_anchor_in_another_state_refuses_naming_where_it_is(
    tree: Declaration,
) -> None:
    """Tree-wide resolution, so it says where the item actually is — the same
    refusal a transition aimed at the wrong state gives."""
    orchard(tree, "a-seedling")
    source = seedling(tree, "b-seedling", READY)
    stranger = seedling(tree, "c-seedling", READY)
    before = source.read_bytes()
    with pytest.raises(Refusal) as refusal:
        execute(
            tree,
            tree.transitions["transplant"],
            name="b-seedling",
            asked={"above": "c-seedling"},
        )
    assert f"{stranger.relative_to(tree.root)} is in greenhouse" in str(refusal.value)
    assert "a place beside it would be a place in orchard" in str(refusal.value)
    assert source.read_bytes() == before
    assert list(places(tree)) == ["a-seedling"]


def test_an_anchor_resolves_by_unique_prefix(tree: Declaration) -> None:
    orchard(tree, "a-seedling")
    seedling(tree, "b-seedling", READY)
    execute(
        tree,
        tree.transitions["transplant"],
        name="b-seedling",
        asked={"above": "a-s"},
    )
    assert places(tree) == {"b-seedling": 50, "a-seedling": 100}


def test_a_taken_place_refuses_and_writes_nothing(tree: Declaration) -> None:
    orchard(tree, "a-seedling")
    source = seedling(tree, "b-seedling", READY)
    before = source.read_bytes()
    with pytest.raises(Refusal) as refusal:
        execute(
            tree,
            tree.transitions["transplant"],
            name="b-seedling",
            asked={"at": 100},
        )
    assert '100 is already held by "a-seedling"' in str(refusal.value)
    assert source.read_bytes() == before
    assert list(places(tree)) == ["a-seedling"]


def test_an_exhausted_gap_refuses_and_writes_nothing(tree: Declaration) -> None:
    orchard(tree, "a-seedling", at=100)
    orchard(tree, "b-seedling", at=101)
    source = seedling(tree, "c-seedling", READY)
    before = source.read_bytes()
    with pytest.raises(Refusal, match="no place between 100 and 101"):
        execute(
            tree,
            tree.transitions["transplant"],
            name="c-seedling",
            asked={"above": "b-seedling"},
        )
    assert source.read_bytes() == before
    assert places(tree) == {"a-seedling": 100, "b-seedling": 101}


def test_a_refused_placement_on_a_creating_transition_leaves_no_file(
    tree: Declaration,
) -> None:
    """The reservation — `open(..., "x")` — is itself a write, so the place
    has to be resolved before it. Otherwise a refusal would leave an empty
    file holding the slug for the rest of the item's life."""
    orchard(tree, "a-seedling")
    direct = Transition(
        name="direct-sow",
        doc="method.md#sprout",
        help="Sow straight into the orchard.",
        to="orchard",
    )
    with pytest.raises(Refusal, match="already held by"):
        execute(tree, direct, name="B seedling", body="Prose.", asked={"at": 100})
    assert list(places(tree)) == ["a-seedling"]
    assert not (tree.root / "orchard" / "b-seedling.md").exists()


def test_two_placement_requests_at_once_refuse_and_write_nothing(
    tree: Declaration,
) -> None:
    orchard(tree, "a-seedling")
    source = seedling(tree, "b-seedling", READY)
    before = source.read_bytes()
    with pytest.raises(Refusal, match="an item takes one place"):
        execute(
            tree,
            tree.transitions["transplant"],
            name="b-seedling",
            asked={"above": "a-seedling", "at": 250},
        )
    assert source.read_bytes() == before
    assert list(places(tree)) == ["a-seedling"]


def test_a_stray_place_in_a_non_queued_state_refuses_the_move(
    tree: Declaration,
) -> None:
    """A hand edit, or a file dragged out of the orchard. The item refuses to
    be read at all, which is where every other head defect surfaces too."""
    seedling(tree, "a-seedling", '+++\ncultivar = "heirloom"\nposition = 100\n+++\n')
    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["transplant"], name="a-seedling")
    assert '"position" is what the queued capability gives an item' in str(
        refusal.value
    )


# --------------------------------------------------------------------------
# The `numbered` capability: minted from the corpus, kept, dropped on exit
# --------------------------------------------------------------------------
#
# `orchard` is the fixture's numbered state as well as its ordered one, so one
# state proves the two head-key capabilities compose. Its archive carries
# `## 1. A felled tree` — a closed item, whose file is gone and whose heading
# is the only record that its number is taken.


def archive(tree: Declaration, text: str) -> None:
    """Rewrite the fixture archive under this tree."""
    (tree.root / tree.states["orchard"].archive).write_text(text, encoding="utf-8")


def test_a_number_is_minted_over_the_closed_ones_in_the_archive(
    tree: Declaration,
) -> None:
    """**The reason for the whole capability.** The archive holds 1, so the
    first tree into the orchard is 2 — a register that read only the state
    would hand back 1 and collide with an item nobody can see any more."""
    seedling(tree, "a-seedling", READY)
    path = execute(tree, tree.transitions["transplant"], name="a-seedling")
    assert read(path, tree)["number"] == 2


def test_the_next_item_is_minted_past_the_live_ones_too(tree: Declaration) -> None:
    seedling(tree, "a-seedling", READY)
    seedling(tree, "b-seedling", READY.replace("A seedling", "B seedling"))
    execute(tree, tree.transitions["transplant"], name="a-seedling")
    path = execute(tree, tree.transitions["transplant"], name="b-seedling")
    assert read(path, tree)["number"] == 3


def test_an_empty_archive_mints_the_first_number(tree: Declaration) -> None:
    """The bootstrap: a consumer's fresh repo, which has closed nothing."""
    archive(tree, "")
    seedling(tree, "a-seedling", READY)
    path = execute(tree, tree.transitions["transplant"], name="a-seedling")
    assert read(path, tree)["number"] == 1



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


def test_a_declared_floor_mints_itself_over_an_empty_corpus(
    tree: Declaration,
) -> None:
    """**The whole point of 11-2**, end to end: a consumer whose sections run
    to 191 in an archive it will not rewrite declares where the new register
    begins, and the first mint is that number rather than 1. Without the
    field the same tree mints 1 (above); with it, 192 — and the declaration is
    the only thing that changed."""
    archive(tree, "")
    declaration = floored(tree, 192)
    seedling(declaration, "a-seedling", READY)
    path = execute(declaration, declaration.transitions["transplant"], name="a-seedling")
    assert read(path, declaration)["number"] == 192


def test_a_gap_left_by_a_lost_archive_entry_refuses_and_writes_nothing(
    tree: Declaration,
) -> None:
    """A closed item's declaration gone: the register runs 2, 3 with 1
    missing, and the number above the gap may already be spoken for. Refused
    before anything is written, like every other capability's refusal."""
    seedling(tree, "a-seedling", READY)
    execute(tree, tree.transitions["transplant"], name="a-seedling")
    archive(tree, "# The orchard's archive\n")
    source = seedling(tree, "b-seedling", READY.replace("A seedling", "B seedling"))
    before = source.read_bytes()

    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["transplant"], name="b-seedling")
    assert "gap(s): 1" in str(refusal.value)
    assert source.read_bytes() == before


def test_an_archive_heading_the_parse_cannot_read_refuses_by_name(
    tree: Declaration,
) -> None:
    """The check the gap check structurally cannot make. The heading is there
    and unreadable, so the number leaves the register with nothing else
    covering it — which is how the old tool minted 168 twice."""
    archive(tree, "## Section 1: A felled tree\n")
    seedling(tree, "a-seedling", READY)
    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["transplant"], name="a-seedling")
    said = str(refusal.value)
    assert "Section 1: A felled tree" in said
    assert "`## <number>. <title>`" in said
    assert list((tree.root / "orchard").iterdir()) == []


def test_an_in_place_verb_leaves_the_number_alone(tree: Declaration) -> None:
    """`graft-on` is about the cursor and says nothing about identity. Without
    the keep-what-you-have rule every cursor move would re-mint."""
    seedling(tree, "a-seedling", READY)
    path = execute(tree, tree.transitions["transplant"], name="a-seedling")
    assert read(path, tree)["number"] == 2
    execute(tree, tree.transitions["graft-on"], name="a-seedling")
    assert read(path, tree)["number"] == 2


def test_leaving_a_numbered_state_sheds_the_number(tree: Declaration) -> None:
    """`_move` sheds every capability key, and no declaration says so —
    `harvest` declares no `drops` and may not. An item that leaves keeps its
    number nowhere: 5-1 settled that by giving the number a home that outlives
    the file rather than an exemption on the way out — see the `archives`
    table below."""
    seedling(tree, "a-seedling", READY)
    execute(tree, tree.transitions["transplant"], name="a-seedling")
    path = execute(tree, tree.transitions["harvest"], name="a-seedling")
    assert read(path, tree).state.name == "cold-frame"
    assert "number" not in read(path, tree).head


def test_a_shed_number_with_no_archive_entry_is_the_gap_the_register_names(
    tree: Declaration,
) -> None:
    """The failure the archive heading exists to prevent, reproduced in
    miniature: `harvest` takes a tree out and nothing records its number, so
    the register has a hole and the next mint refuses rather than filling it."""
    for name in ("a-seedling", "b-seedling"):
        seedling(tree, name, READY.replace("A seedling", name))
        execute(tree, tree.transitions["transplant"], name=name)
    execute(tree, tree.transitions["harvest"], name="a-seedling")

    seedling(tree, "c-seedling", READY.replace("A seedling", "C seedling"))
    with pytest.raises(Refusal, match=r"gap\(s\): 2"):
        execute(tree, tree.transitions["transplant"], name="c-seedling")


def test_the_two_head_key_capabilities_compose_on_one_move(
    tree: Declaration,
) -> None:
    """One entry writes both, and neither arm knows about the other — the same
    thing `bed-out` proves for a place and a claim."""
    seedling(tree, "a-seedling", READY)
    path = execute(tree, tree.transitions["transplant"], name="a-seedling")
    one = read(path, tree)
    assert (one["position"], one["number"]) == (100, 2)


# --------------------------------------------------------------------------
# The `archives` half: the entry that outlives the file
# --------------------------------------------------------------------------
#
# `grub-out` is the fixture's archiving verb: `orchard` — the numbered state —
# to `firewood`, which declares nothing. It is deliberately **not** out of the
# state this repo's own `decline` leaves, so a tool that had learned which
# state archives would pass its own suite and fail here.
#
# It **moves** the tree. Recording an item and deleting it are two opt-ins,
# and this is the recording one on its own.


def grubbed(tree: Declaration, name: str) -> Path:
    """One tree, transplanted into the orchard and then given up on."""
    orchard(tree, name)
    return execute(tree, tree.transitions["grub-out"], name=name)


def filed(tree: Declaration) -> str:
    return (tree.root / tree.states["orchard"].archive).read_text(encoding="utf-8")


def test_a_verb_that_archives_moves_the_item_like_any_other(
    tree: Declaration,
) -> None:
    """No new shape: the file lands in the destination state and sheds every
    capability key on the way, exactly as `harvest` does. What is added is the
    entry, not a second kind of move."""
    path = grubbed(tree, "a-seedling")
    one = read(path, tree)
    assert one.state.name == "firewood"
    assert "number" not in one.head and "position" not in one.head
    assert not (tree.root / "orchard" / "a-seedling.md").exists()


def test_the_entry_is_filed_under_the_number_the_item_carried(
    tree: Declaration,
) -> None:
    """**The whole point.** The number is dropped by the move, and what speaks
    for it afterwards is the heading — so the register still counts it with
    the item's own file no longer carrying it."""
    grubbed(tree, "a-seedling")
    assert "## 2. A seedling" in filed(tree)
    assert numbered.numbers(filed(tree)) == [1, 2]


def test_the_entry_lands_at_its_place_in_the_register_not_at_the_end(
    tree: Declaration,
) -> None:
    """Inserted, never appended — this repo's section 4 closed before its
    section 3, and an appending verb would have left the document out of
    order. The archive is rewritten after the mint so that the number being
    filed really does belong in the middle."""
    orchard(tree, "a-seedling")
    archive(tree, "## 1. A felled tree\n\n## 5. A late one\n")
    execute(tree, tree.transitions["grub-out"], name="a-seedling")
    assert numbered.numbers(filed(tree)) == [1, 2, 5]
    assert "## 2. A seedling\n\n## 5. A late one" in filed(tree)


def test_the_register_stays_contiguous_so_the_next_mint_does_not_refuse(
    tree: Declaration,
) -> None:
    """The failure this sub-phase exists to prevent, from the other side:
    `harvest` sheds a number and leaves a gap that refuses the next mint
    (above), and `grub-out` sheds the same number and does not."""
    grubbed(tree, "a-seedling")
    seedling(tree, "b-seedling", READY.replace("A seedling", "B seedling"))
    path = execute(tree, tree.transitions["transplant"], name="b-seedling")
    assert read(path, tree)["number"] == 3


def test_the_number_outlives_the_file(tree: Declaration) -> None:
    """**The load-bearing check**, and the reason the entry is written at all:
    an abandoned item's file is free to delete, because the record is
    somewhere else. Delete it and the register is unchanged."""
    path = grubbed(tree, "a-seedling")
    path.unlink()
    seedling(tree, "b-seedling", READY.replace("A seedling", "B seedling"))
    minted = execute(tree, tree.transitions["transplant"], name="b-seedling")
    assert read(minted, tree)["number"] == 3


def test_a_verb_that_does_not_archive_writes_no_entry(tree: Declaration) -> None:
    """The control. `harvest` leaves the same state and records nothing — the
    entry comes from the verb's opt-in, not from leaving."""
    before = filed(tree)
    orchard(tree, "a-seedling")
    execute(tree, tree.transitions["harvest"], name="a-seedling")
    assert filed(tree) == before


def test_the_run_says_what_it_minted_and_that_a_record_goes_under_it(
    tree: Declaration,
) -> None:
    """Mint-then-fill, and it is safe here because the item **moved**: what
    the record is written from is still readable. A verb that deleted the item
    could not fill in afterwards, which is why that half decides separately."""
    said: list[str] = []
    orchard(tree, "a-seedling")
    execute(
        tree,
        tree.transitions["grub-out"],
        name="a-seedling",
        announce=said.append,
    )
    (notice,) = said
    assert "## 2. A seedling" in notice
    assert "a-seedling is still filed" in notice


def test_an_item_carrying_no_number_refuses_and_writes_nothing(
    tree: Declaration,
) -> None:
    """An entry with no number is the lost close-out the register cannot read.
    Hand-placed, because no verb into the orchard can produce one."""
    stray = tree.root / "orchard" / "a-stray.md"
    stray.write_text(READY, encoding="utf-8")
    before, document = stray.read_bytes(), filed(tree)

    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["grub-out"], name="a-stray")
    assert "carries no number" in str(refusal.value)
    assert stray.read_bytes() == before and filed(tree) == document


def test_an_unreadable_heading_refuses_before_either_file_is_written(
    tree: Declaration,
) -> None:
    """`heading_errors` runs on every filing as it runs on every mint: the
    entry would join a document whose other entries are not all being counted,
    and the number about to be filed may be one of the lost ones."""
    path = orchard(tree, "a-seedling")
    archive(tree, "## Section 1: A felled tree\n")
    before, document = path.read_bytes(), filed(tree)

    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["grub-out"], name="a-seedling")
    assert "Section 1: A felled tree" in str(refusal.value)
    assert path.read_bytes() == before and filed(tree) == document


def test_a_number_the_archive_already_holds_refuses_naming_both(
    tree: Declaration,
) -> None:
    """The mint's refusal, reached by the filing: two claimants for one number
    leave one of them unfindable once its file is gone."""
    path = orchard(tree, "a-seedling")
    archive(tree, "## 1. A felled tree\n\n## 2. Something else\n")
    document = filed(tree)

    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["grub-out"], name="a-seedling")
    said = str(refusal.value)
    assert "number 2 is claimed by" in said and "A seedling" in said
    assert path.exists() and filed(tree) == document


def test_a_gap_elsewhere_in_the_register_does_not_refuse_a_filing(
    tree: Declaration,
) -> None:
    """A gap refuses a *mint* and must not refuse a filing: filing is what
    fills a gap in, and refusing there would be the tool declining the fix."""
    orchard(tree, "a-seedling")
    archive(tree, "## 5. A late one\n")
    execute(tree, tree.transitions["grub-out"], name="a-seedling")
    assert numbered.numbers(filed(tree)) == [2, 5]


def test_a_declined_item_is_still_filed_so_an_edge_to_it_resolves(
    tree: Declaration,
) -> None:
    """The reason declining is a **move**. The item keeps a file, so it keeps
    a slug, so an item waiting on it is *blocked* rather than pointing at
    nothing — which is loud and correct, and the opposite of what a dissolve
    would leave."""
    grubbed(tree, "a-seedling")
    assert [one.slug for one in read_items(tree) if one.state.name == "firewood"] == [
        "a-seedling"
    ]


# --------------------------------------------------------------------------
# The `claimed` capability: taken on entry, held, dropped on exit
# --------------------------------------------------------------------------
#
# `potting-bench` is the fixture's claimed state. `pot-up` creates into it,
# `bench` moves in, `tend` moves within it and `bed-out` leaves for `orchard`
# — which is the `queued` state, so that one verb also proves the two
# capabilities compose rather than colliding.
#
# The second arm of the seam, beside `_entering`, and the reason there is no
# protocol between them: this one keeps its state in a file outside the item
# and adds an ownership precondition the other has no analogue for.
#
# **A second session is written by hand**: a record carrying another pid or
# another host is exactly what a sibling session leaves behind, and it needs
# no subprocess.
#
# **Every test here sets a declared variable.** An identity with no pid is
# refused at the take and owned host-wide at the check, so a test that forgot
# would be testing the wrong thing.

#: This session's pid, as the fixture's `[identity]` reads it. Arbitrary: it
#: is compared, never signalled — a claim of this session's own is owned
#: before the probe is reached.
MINE = 4213


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch) -> Identity:
    """Who this session is, for the length of one test."""
    monkeypatch.setenv("GREENHOUSE_PID", str(MINE))
    monkeypatch.delenv("SPROUT_PID", raising=False)
    return Identity(host=socket.gethostname(), pid=MINE)


def benched(tree: Declaration, name: str = "a-seedling") -> Path:
    """One seedling on the potting bench, claimed by this session.

    Two verbs, because arrival is not a claim: `bench` brings it in and takes
    nothing, and `tend` — the verb that declares `claims` — picks it up. The
    `tend` is passed no values, so the head is what `bench` left.
    """
    seedling(tree, name, READY)
    execute(tree, tree.transitions["bench"], name=name)
    return execute(tree, tree.transitions["tend"], name=name)


def tended(tree: Declaration, name: str = "a-seedling") -> Path:
    """The work `potting-bench` exists for: `tend` sets a `rootstock` in
    place, without ending anything."""
    return execute(
        tree, tree.transitions["tend"], name=name, values={"rootstock": "M9"}
    )


def record(tree: Declaration, slug: str = "a-seedling") -> dict:
    return claim.read(claim.path(tree.root, slug), tree.root)


def someone_else(
    tree: Declaration,
    slug: str = "a-seedling",
    *,
    pid: int | None = None,
    host: str | None = None,
) -> Path:
    """A record a sibling session left behind, written by hand."""
    path = claim.path(tree.root, slug)
    written = {"host": host or socket.gethostname(), "taken": TAKEN}
    if pid is not None:
        written["pid"] = pid
    claim.write(path, written)
    return path


def test_moving_into_a_claimed_state_takes_nothing_by_itself(
    tree: Declaration, session: Identity
) -> None:
    """An earlier version of this test asserted the opposite. Arriving is
    not picking work up: `bench`
    declares no `claims`, so a seedling can stand on the bench with nobody on
    it. Coupling the two would mean an item had to *move* to be claimed, and
    where work stands is the declaration's business (John, 2026-09-03)."""
    seedling(tree, "a-seedling", READY)
    path = execute(tree, tree.transitions["bench"], name="a-seedling")
    assert path == tree.root / "potting-bench" / "a-seedling.md"
    assert not claim.path(tree.root, "a-seedling").exists()


def test_a_transition_that_declares_claims_takes_the_claim(
    tree: Declaration, session: Identity
) -> None:
    """The other half. Nothing but `claims = true` says so, and nothing else
    can: the record is the capability's, and a `sets` naming a claim would
    have no key to name."""
    path = benched(tree)
    assert path == tree.root / "potting-bench" / "a-seedling.md"
    held = record(tree)
    assert held["host"] == session.host and held["pid"] == MINE


def test_the_claim_is_a_file_beside_the_tree_not_a_key_in_the_head(
    tree: Declaration, session: Identity
) -> None:
    """`queued` writes a key into the head; this capability's state lives
    outside the item file entirely, which is the whole reason the two arms
    stayed two."""
    path = benched(tree)
    assert read(path, tree).head == {
        "title": "A seedling",
        "cultivar": "heirloom",
        "tag": "spring",
    }
    assert claim.path(tree.root, "a-seedling").exists()


def test_the_claim_is_stamped_with_an_aware_moment(
    tree: Declaration, session: Identity
) -> None:
    """This tree is shared, and a naive stamp means a different moment on each
    machine that reads it."""
    benched(tree)
    taken = record(tree)["taken"]
    assert taken.tzinfo is not None and taken.utcoffset() is not None


def test_creating_straight_into_a_claimed_state_takes_a_claim(
    tree: Declaration, session: Identity
) -> None:
    """The same seam on the other shape: `pot-up` has no `from`, so only the
    destination arm can do anything, and it does the same thing."""
    execute(tree, tree.transitions["pot-up"], name="A seedling", body="Prose.")
    assert record(tree)["pid"] == MINE


def test_a_claiming_verb_re_run_keeps_the_claim_rather_than_restamping(
    tree: Declaration, session: Identity
) -> None:
    """A place is *where in this state* an item sits, so a state-to-itself
    move re-places it. A claim is *who took it and when*, and the same holder
    re-taking is the same claim — re-stamping would lose "since when" for
    nothing. It is also what lets one verb both pick an item up and, run
    again, say where the session has got to."""
    benched(tree)
    before = claim.path(tree.root, "a-seedling").read_bytes()
    execute(tree, tree.transitions["tend"], name="a-seedling", values={"rootstock": "M26"})
    assert claim.path(tree.root, "a-seedling").read_bytes() == before


def test_leaving_a_claimed_state_drops_the_claim(
    tree: Declaration, session: Identity
) -> None:
    """The completion. The claim goes with the item, and no declaration says
    so — `bed-out` declares no `drops` and may not."""
    benched(tree)
    tended(tree)
    path = execute(tree, tree.transitions["bed-out"], name="a-seedling")
    assert read(path, tree).state.name == "orchard"
    assert not claim.path(tree.root, "a-seedling").exists()


def test_the_two_capabilities_compose_on_one_move(
    tree: Declaration, session: Identity
) -> None:
    """`bed-out` leaves the claimed state for the ordered one: the claim drops
    on exit exactly as the place is written on entry, in one transition, with
    neither arm knowing about the other."""
    benched(tree)
    tended(tree)
    path = execute(tree, tree.transitions["bed-out"], name="a-seedling")
    assert read(path, tree)["position"] == 100
    assert not claim.path(tree.root, "a-seedling").exists()


def test_a_missing_record_means_unclaimed_and_the_transition_proceeds(
    tree: Declaration, session: Identity
) -> None:
    """Deliberately. `local/` is gitignored, so a consumer's fresh clone has
    items in claimed states and no records at all; refusing there would
    deadlock a tree with no way out, since `release` would have nothing to
    free either."""
    seedling(tree, "a-seedling", READY)
    stranded = tree.root / "potting-bench" / "a-seedling.md"
    stranded.write_text(TENDED)
    (tree.root / "greenhouse" / "a-seedling.md").unlink()
    assert not claim.path(tree.root, "a-seedling").exists()

    path = execute(tree, tree.transitions["bed-out"], name="a-seedling")
    assert read(path, tree).state.name == "orchard"


def test_a_claim_this_session_holds_lets_it_move_the_item(
    tree: Declaration, session: Identity
) -> None:
    benched(tree)
    tended(tree)
    path = execute(tree, tree.transitions["bed-out"], name="a-seedling")
    assert path == tree.root / "orchard" / "a-seedling.md"


def test_another_sessions_claim_refuses_naming_the_holder(
    tree: Declaration, session: Identity
) -> None:
    """Concurrency, at the point it becomes behaviour: a second session
    cannot pick up an item somebody is working on."""
    seedling(tree, "a-seedling", READY)
    someone_else(tree, pid=os.getpid())
    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["bench"], name="a-seedling")
    assert "a-seedling is claimed by" in str(refusal.value)
    assert f"{session.host} pid {os.getpid()} (running)" in str(refusal.value)


def test_a_refused_claim_leaves_the_source_byte_identical(
    tree: Declaration, session: Identity
) -> None:
    """Resolved before anything is written, like every other capability's
    refusal: a second session's attempt changes nothing at all."""
    source = seedling(tree, "a-seedling", READY)
    before = source.read_bytes()
    held = someone_else(tree, pid=os.getpid()).read_bytes()

    with pytest.raises(Refusal, match="is claimed by"):
        execute(tree, tree.transitions["bench"], name="a-seedling")

    assert source.read_bytes() == before
    assert list((tree.root / "potting-bench").iterdir()) == []
    assert claim.path(tree.root, "a-seedling").read_bytes() == held


def test_a_second_sessions_completion_refuses(
    tree: Declaration, session: Identity
) -> None:
    """The other half of the same rule: an item in a claimed state is moved
    *out* by the session holding it, not by whoever runs the verb next."""
    benched(tree)
    someone_else(tree, pid=os.getpid())
    with pytest.raises(Refusal, match="is claimed by"):
        execute(tree, tree.transitions["bed-out"], name="a-seedling")
    assert (tree.root / "potting-bench" / "a-seedling.md").exists()
    assert list((tree.root / "orchard").iterdir()) == []


def test_a_dead_holder_is_named_as_dead_rather_than_stolen(
    tree: Declaration, session: Identity
) -> None:
    """Nothing is auto-released, not even a claim the probe says is over. The
    refusal says what the probe found, and freeing it is `release`, which a
    person runs."""
    seedling(tree, "a-seedling", READY)
    someone_else(tree, pid=exited())
    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["bench"], name="a-seedling")
    assert "(not running)" in str(refusal.value)
    assert "fileplan release a-seedling" in str(refusal.value)
    assert claim.path(tree.root, "a-seedling").exists()


def test_a_claim_from_another_host_refuses_and_is_never_probed(
    tree: Declaration, session: Identity
) -> None:
    """A pid means nothing on another machine, and this tree is on a syncing
    filesystem — records reach machines that never ran the session that
    wrote them."""
    seedling(tree, "a-seedling", READY)
    someone_else(tree, pid=MINE, host="another-host")
    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["bench"], name="a-seedling")
    assert "another-host pid 4213 (another machine" in str(refusal.value)


def test_a_pidless_record_on_this_host_is_this_hosts_to_move(
    tree: Declaration, session: Identity
) -> None:
    """2-1's ownership rule, untouched: a claim taken at a shell stays
    completable. What 2-2 adds is a refusal at the *taking* end, not here."""
    seedling(tree, "a-seedling", READY)
    stranded = tree.root / "potting-bench" / "a-seedling.md"
    stranded.write_text(TENDED)
    (tree.root / "greenhouse" / "a-seedling.md").unlink()
    someone_else(tree)

    execute(tree, tree.transitions["bed-out"], name="a-seedling")
    assert not claim.path(tree.root, "a-seedling").exists()


def test_taking_a_claim_with_no_pid_available_refuses_by_name(
    tree: Declaration, monkeypatch: pytest.MonkeyPatch
) -> None:
    """John, 2026-09-02. Without this, two pid-less sessions on one host own
    each other's claims and the one-session-at-a-time guarantee silently
    drops to host-level. Either a claim names the session holding it or it is not
    taken."""
    seedling(tree, "a-seedling", READY)
    monkeypatch.setenv("GREENHOUSE_PID", str(MINE))
    # `bench` claims nothing, so it needs no pid: the refusal belongs to the
    # verb that takes a claim, which is the one run without one.
    source = execute(tree, tree.transitions["bench"], name="a-seedling")
    before = source.read_bytes()
    for name in ("GREENHOUSE_PID", "SPROUT_PID"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["tend"], name="a-seedling")
    assert "no session pid is set" in str(refusal.value)
    assert "GREENHOUSE_PID, SPROUT_PID" in str(refusal.value)
    assert source.read_bytes() == before
    assert not claim.path(tree.root, "a-seedling").exists()


def test_creating_into_a_claimed_state_with_no_pid_leaves_no_file(
    tree: Declaration, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reservation is itself a write, so the claim is resolved before it —
    the same reason a refused placement leaves no empty file behind."""
    for name in ("GREENHOUSE_PID", "SPROUT_PID"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(Refusal, match="no session pid is set"):
        execute(tree, tree.transitions["pot-up"], name="A seedling", body="Prose.")
    assert list((tree.root / "potting-bench").iterdir()) == []


def test_the_claim_precondition_comes_before_the_items_shortcomings(
    tree: Declaration, session: Identity
) -> None:
    """"This is not yours" is prior to "it lacks a key": a second session has
    no business being told about the item's shortcomings."""
    benched(tree)
    someone_else(tree, pid=os.getpid())
    inspect = Transition(
        name="inspect",
        doc="method.md#tend",
        help="Bed out only what has a rootstock.",
        to="orchard",
        source="potting-bench",
        requires=("rootstock",),
    )
    with pytest.raises(Refusal) as refusal:
        execute(tree, inspect, name="a-seedling")
    assert "is claimed by" in str(refusal.value)
    assert "rootstock" not in str(refusal.value)


def test_a_non_claiming_verb_still_refuses_another_sessions_claim(
    tree: Declaration, session: Identity
) -> None:
    """The ownership refusal is not the taking. `bench` takes nothing, and it
    still may not walk an item out from under the session holding it —
    otherwise "arriving claims nothing" would have quietly opened a hole where
    a second session could move somebody's work around."""
    seedling(tree, "a-seedling", READY)
    someone_else(tree, pid=os.getpid())
    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["bench"], name="a-seedling")
    assert "a-seedling is claimed by" in str(refusal.value)
    assert list((tree.root / "potting-bench").iterdir()) == []


def test_leaving_frees_a_claim_no_verb_on_the_way_out_declares(
    tree: Declaration, session: Identity
) -> None:
    """The drop stayed the state's rather than the verb's. `bed-out` declares
    no `claims` and never did: taking is opt-in, freeing on the way out is
    not, because a claim outliving the state it was taken in is the deadlock
    `release` exists to dig out of."""
    benched(tree)
    tended(tree)
    assert not tree.transitions["bed-out"].claims
    execute(tree, tree.transitions["bed-out"], name="a-seedling")
    assert not claim.path(tree.root, "a-seedling").exists()


def test_a_transition_between_unclaimed_states_writes_no_record(
    tree: Declaration, session: Identity
) -> None:
    """The arm does nothing at all where no state opts in, which is every
    transition in a declaration with no claimed state."""
    seedling(tree, "a-seedling", READY)
    execute(tree, tree.transitions["transplant"], name="a-seedling")
    assert not (tree.root / "local" / "claims").exists()


# --------------------------------------------------------------------------
# The third arm: `mints`, and the body it writes
# --------------------------------------------------------------------------
#
# The arithmetic itself is `tests/test_subphase.py`, pure and with no
# `tmp_path`. What is pinned here is the seam: that a verb that mints reaches
# it, that one that does not never does, and that a refusal from it leaves the
# source byte-identical.

#: The fixture's pending bullet, as `orchard` declares it.
UNPRUNED = "**unpruned — Say what the rest of the training is.**"


def trained(tree: Declaration, *asked: object, name: str = "a-seedling") -> Path:
    """One tree in the orchard, run through `espalier` once."""
    title, last = (asked + (None, False))[:2]
    return execute(
        tree,
        tree.transitions["espalier"],
        name=name,
        asked={"title": title, "last": bool(last)},
    )


def test_a_verb_that_mints_writes_the_heading_and_the_pending_bullet(
    tree: Declaration,
) -> None:
    """Opening a decomposition on an item that carries neither. Nothing else
    in the body changes, which is what `_move` writing a body rather than
    copying one has to keep true."""
    was = read(orchard(tree, "a-seedling"), tree).body
    body = read(trained(tree), tree).body
    assert body == was.rstrip("\n") + f"\n\n### Steps\n- {UNPRUNED}\n"


def test_a_minted_bullet_is_named_from_the_number_the_state_minted(
    tree: Declaration,
) -> None:
    """`orchard-archive.md` already holds number 1, so the first tree in mints
    2 — and its first step is `2-1`. The prefix comes from the register rather
    than from anything this arm decides."""
    orchard(tree, "a-seedling")
    item = read(trained(tree, "The register"), tree)
    assert item["number"] == 2
    assert "- **2-1 — The register**" in item.body


def test_a_verb_that_mints_nothing_never_reaches_the_arm(tree: Declaration) -> None:
    """`graft-on` is an in-place verb into the same state and declares no
    `mints`, so it gets the body it was given back. Without the opt-in every
    verb into the state could decompose an item on a run about something
    else."""
    path = orchard(tree, "a-seedling")
    was = read(path, tree).body
    execute(tree, tree.transitions["graft-on"], name="a-seedling")
    assert read(path, tree).body == was


def test_a_run_that_re_opens_a_decomposition_says_so(tree: Declaration) -> None:
    """A state change the operator did not ask for is announced rather than
    refused: the section really is unfinished again, which is correct."""
    orchard(tree, "a-seedling")
    trained(tree, "One", True)
    said: list[str] = []
    execute(
        tree,
        tree.transitions["espalier"],
        name="a-seedling",
        asked={"title": "Two"},
        announce=said.append,
    )
    (notice,) = said
    assert "re-opens it" in notice and UNPRUNED in notice
    assert f"- {UNPRUNED}" in read_items(tree)[0].body


def test_a_run_that_leaves_a_decomposition_open_announces_nothing(
    tree: Declaration,
) -> None:
    """The other arm. Nothing changed that was not asked for, so nothing is
    said — a notice on every mint would be noise nobody reads."""
    orchard(tree, "a-seedling")
    trained(tree)
    said: list[str] = []
    execute(
        tree,
        tree.transitions["espalier"],
        name="a-seedling",
        asked={"title": "One"},
        announce=said.append,
    )
    assert said == []


def test_a_title_that_would_break_the_strict_form_refuses_and_writes_nothing(
    tree: Declaration,
) -> None:
    """The arm is resolved before anything is written, like the other two, so
    a refusal leaves the source byte-identical."""
    path = orchard(tree, "a-seedling")
    trained(tree)
    before = path.read_bytes()
    with pytest.raises(Refusal) as refusal:
        trained(tree, "A **bold** title")
    assert 'carries "**"' in str(refusal.value)
    assert path.read_bytes() == before


def test_the_cursor_is_graded_against_the_body_this_run_would_write(
    tree: Declaration,
) -> None:
    """The reordering 4-5a paid for. `_cursor_errors` read `original.body`
    while nothing wrote one, which was right by accident; a verb that mints a
    bullet and points the cursor at it in the same run would otherwise refuse
    the name it had just created."""
    orchard(tree, "a-seedling")
    espalier = tree.transitions["espalier"]
    pointing = Transition(
        name=espalier.name,
        doc=espalier.doc,
        help=espalier.help,
        to=espalier.to,
        source=espalier.source,
        sets=("graft",),
        mints=True,
    )
    path = execute(
        tree,
        pointing,
        name="a-seedling",
        values={"graft": "2-1"},
        asked={"title": "The register"},
    )
    item = read(path, tree)
    assert item["graft"] == "2-1"
    assert "- **2-1 — The register**" in item.body


# --------------------------------------------------------------------------
# The same arm's other half: `marks`, and the one line it rewrites
# --------------------------------------------------------------------------
#
# `pot-on` marks into `propagator`, the fixture's **registerless** bulleted
# state, so a tool that reached for a number to name a bullet by would fail
# here and nowhere else. The writing itself is `tests/test_subphase.py`; what
# is pinned here is the seam — that the name resolves, that both refusals
# happen before the first write, and that `--check` gets the run's own words
# because it is the run's own code raising them.

#: The fixture's pending bullet, as `propagator` declares it.
UNSTRUCK = "**unstruck — Say what the rest of the batch is.**"


def batch(
    tree: Declaration, *titles: str, close: bool = True, owner: str | None = None
) -> Path:
    """One batch under mist, with a cutting minted for each title given.

    ``close`` says whether the last mint takes the pending bullet out. A batch
    left open is what proves the marker is not something a disposition can
    reach.

    ``owner`` seals it to a tree, through the two keys `strike` sets and
    `propagator` names. Absent, the batch was struck for nothing in
    particular, which is the shape every test written before the seal used.
    """
    path = execute(
        tree,
        tree.transitions["strike"],
        name="A batch",
        body="Prose.",
        values={"for-tree": owner, "for-step": "2-1"},
    )
    for number, title in enumerate(titles):
        path = execute(
            tree,
            tree.transitions["mist"],
            name="a-batch",
            asked={"title": title, "last": close and number == len(titles) - 1},
        )
    return path


def test_a_verb_that_marks_writes_the_word_it_declares(tree: Declaration) -> None:
    """The word is the declaration's — the tool supplies the bold and nothing
    else — and the bullet is named within the item rather than tree-wide."""
    path = batch(tree, "The first", "The second")
    execute(tree, tree.transitions["pot-on"], name="a-batch", asked={"name": "c1"})
    body = read(path, tree).body
    assert "- **c1 — The first** **rooted**" in body
    assert "- **c2 — The second**" in body


def test_marking_rewrites_one_line_and_leaves_every_other_byte_alone(
    tree: Declaration,
) -> None:
    path = batch(tree, "The first", "The second")
    before = path.read_text().splitlines()
    execute(tree, tree.transitions["pot-on"], name="a-batch", asked={"name": "c2"})
    after = path.read_text().splitlines()
    assert len(before) == len(after)
    differing = [n for n, (one, two) in enumerate(zip(before, after)) if one != two]
    assert [before[n] for n in differing] == ["- **c2 — The second**"]


def test_a_verb_that_marks_nothing_never_reaches_the_arm(tree: Declaration) -> None:
    """`mist` writes bullets into the same state and declares no `marks`, so a
    run of it takes no name and marks none — the `mints` opt-in's argument,
    read from the other half."""
    assert tree.transitions["mist"].marks is None
    path = batch(tree, "The first")
    was = read(path, tree).body
    execute(tree, tree.transitions["mist"], name="a-batch", asked={"last": True})
    assert read(path, tree).body == was


def test_a_name_the_body_does_not_carry_refuses_naming_the_ones_it_does(
    tree: Declaration,
) -> None:
    """`cursor_errors`' message shape, for its reason: a typo is a run the
    operator can fix out of what the refusal said."""
    path = batch(tree, "The first", "The second")
    before = path.read_bytes()
    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["pot-on"], name="a-batch", asked={"name": "c9"})
    assert 'carries no "c9", and the names it carries are c1, c2' in str(refusal.value)
    assert path.read_bytes() == before


def test_the_refusal_is_the_one_home_of_that_sentence(tree: Declaration) -> None:
    """11-4 lifted it into `subphase.unknown`, because `show ITEM NAME`
    needs it **byte for byte** and two spellings of one refusal is the drift
    this repo refuses everywhere else. The disposition's words are unchanged,
    which is what this asserts — against the function, not against a copy of
    the string."""
    path = batch(tree, "The first", "The second")
    carried = subphase.bullets(read(path, tree).body, "Cuttings", pending=None)
    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["pot-on"], name="a-batch", asked={"name": "c9"})
    assert str(refusal.value) == subphase.unknown(
        str(path.relative_to(tree.root)), "c9", carried, "Cuttings"
    )


def test_the_pending_bullet_refuses_as_a_name_the_body_does_not_carry(
    tree: Declaration,
) -> None:
    """It marks the decomposition as unfinished rather than being work, and
    `bullets` drops it — so a run aimed at the marker needs no arm of its own,
    which is one refusal rather than two."""
    path = batch(tree, "The first", close=False)
    assert UNSTRUCK in path.read_text()
    with pytest.raises(Refusal) as refusal:
        execute(
            tree, tree.transitions["pot-on"], name="a-batch", asked={"name": "unstruck"}
        )
    assert 'carries no "unstruck"' in str(refusal.value)


def test_a_body_carrying_no_named_bullet_refuses_saying_so(tree: Declaration) -> None:
    """The other arm of the same message: naming an empty list would be a
    refusal that told the operator nothing."""
    batch(tree)
    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["pot-on"], name="a-batch", asked={"name": "c1"})
    assert 'no named bullet at all under "Cuttings"' in str(refusal.value)


def test_a_finding_already_disposed_of_refuses_naming_the_mark_it_carries(
    tree: Declaration,
) -> None:
    """One answer on the bullet rather than a history nobody can read an
    answer out of — and the refusal names which answer is already there."""
    path = batch(tree, "The first")
    execute(tree, tree.transitions["pot-on"], name="a-batch", asked={"name": "c1"})
    before = path.read_bytes()
    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["pot-on"], name="a-batch", asked={"name": "c1"})
    assert 'already disposed of c1: it is marked "rooted"' in str(refusal.value)
    assert path.read_bytes() == before


def scribbled(tree: Declaration, said: str = "and a note somebody typed") -> Path:
    """A batch whose one cutting carries prose outside its bold run.

    Minted through the verb and then edited by hand, because `batch` mints
    markable bullets only — this is the shape a person's edit produces and
    the tool never writes.
    """
    path = batch(tree, "The first")
    path.write_text(
        path.read_text().replace(
            "- **c1 — The first**", f"- **c1 — The first** {said}"
        ),
        encoding="utf-8",
    )
    return path


def test_a_bullet_carrying_prose_outside_its_bold_run_refuses_quoting_it(
    tree: Declaration,
) -> None:
    """`mark` appends at the end of the line and `MARKED` reads only the run
    immediately after the name's, so the word would land where nothing finds
    it. The loud arm: refuse, and quote what is in the way."""
    path = scribbled(tree)
    before = path.read_bytes()
    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["pot-on"], name="a-batch", asked={"name": "c1"})
    said = str(refusal.value)
    assert "cannot mark c1" in said
    assert 'carries "and a note somebody typed" after its bold run' in said
    assert "Move the prose inside the bold run" in said
    assert path.read_bytes() == before


def test_an_already_marked_bullet_refuses_as_marked_rather_than_as_unmarkable(
    tree: Declaration,
) -> None:
    """The ordering test. A marked bullet's rest is its own mark run, so the
    third question would answer yes for every second disposition — and the
    operator would be told to move prose that is the tool's own punctuation."""
    batch(tree, "The first")
    execute(tree, tree.transitions["pot-on"], name="a-batch", asked={"name": "c1"})
    with pytest.raises(Refusal) as refusal:
        execute(tree, tree.transitions["pot-on"], name="a-batch", asked={"name": "c1"})
    said = str(refusal.value)
    assert 'already disposed of c1: it is marked "rooted"' in said
    assert "cannot mark c1" not in said


def test_a_check_says_which_bullet_and_which_word(tree: Declaration) -> None:
    """Marking one bullet out of forty is the whole of what the run is, so the
    check says which — built from what the arm resolved rather than read back
    off the declaration."""
    path = batch(tree, "The first")
    before = path.read_bytes()
    said = execute(
        tree,
        tree.transitions["pot-on"],
        name="a-batch",
        asked={"name": "c1"},
        check=True,
    )
    assert said.startswith("pot-on would rewrite ")
    assert said.endswith(
        'propagator/a-batch.md, which stays in propagator, and would mark c1 "rooted"'
    )
    assert path.read_bytes() == before


# --- marking: a bullet in a state that carries a cursor ---------------------
#
# 12-1's premise, and the fixture is what makes it a test rather than an
# assertion about this repo. `pot-on` above marks `propagator`, which has no
# register and no cursor; `graft-on` moves a cursor over bullets nothing
# marks. `ripen` and `thin` mark into `orchard` — queued, numbered, claimed
# and cursored — so a mark and a cursor meet over one body for the first time.
# Nothing here is a new arm: what is pinned is that the existing one reaches a
# state it was never run against, which is what "no `src/` change" means.


def pruned(tree: Declaration, *, close: bool = True) -> Path:
    """One tree in the orchard with two steps trained into it.

    ``close`` says whether the second mint takes the pending bullet out, the
    way `batch` does one state over. The numbers are `2-1` and `2-2`:
    `orchard-archive.md` already holds 1, so the first tree in mints 2.
    """
    orchard(tree, "a-seedling")
    trained(tree, "The first")
    return trained(tree, "The second", close)


def test_a_marking_verb_writes_onto_a_bullet_in_a_state_that_has_a_cursor(
    tree: Declaration,
) -> None:
    """The whole of 12-1's premise in one run. The word is `orchard`'s own —
    the state carries a register, a claim and a cursor, and none of the three
    is anything the marking arm asks about."""
    path = pruned(tree)
    before = path.read_text().splitlines()
    execute(tree, tree.transitions["ripen"], name="a-seedling", asked={"name": "2-1"})
    after = path.read_text().splitlines()
    assert len(before) == len(after)
    differing = [n for n, (one, two) in enumerate(zip(before, after)) if one != two]
    assert [after[n] for n in differing] == ["- **2-1 — The first** **ripened**"]


def test_marking_a_sub_phase_leaves_the_cursor_where_it_was(
    tree: Declaration,
) -> None:
    """A mark is a fact about the **bullet**, so nothing about where the cursor
    points changes: the run writes the word and leaves `graft` alone.

    The status is a different question and it does go, because `ripen`
    declares a `drops` over it — the arm
    `test_a_marking_verb_that_drops_a_key_takes_it_off_the_head` is about.
    Asserted here too so the two halves of one head are pinned in one place:
    a run that quietly took the cursor with the status would pass every test
    that looked at only one of them."""
    pruned(tree)
    path = execute(
        tree,
        tree.transitions["graft-on"],
        name="a-seedling",
        values={"graft": "2-1", "graft-status": "in progress"},
    )
    execute(tree, tree.transitions["ripen"], name="a-seedling", asked={"name": "2-1"})
    item = read(path, tree)
    assert item["graft"] == "2-1"
    assert "graft-status" not in item.head
    assert "- **2-1 — The first** **ripened**" in item.body


def test_the_pending_marker_refuses_as_a_name_the_body_does_not_carry(
    tree: Declaration,
) -> None:
    """`test_the_pending_bullet_refuses_as_a_name_the_body_does_not_carry`'s
    property over the **cursored** state, which is where a session running the
    cycle would actually meet it: the marker says the decomposition is
    unfinished rather than being work, and `bullets` drops it, so the refusal
    is "no such name" and lists the names there are."""
    path = pruned(tree, close=False)
    assert UNPRUNED in path.read_text()
    before = path.read_bytes()
    with pytest.raises(Refusal) as refusal:
        execute(
            tree,
            tree.transitions["ripen"],
            name="a-seedling",
            asked={"name": "unpruned"},
        )
    assert 'carries no "unpruned", and the names it carries are 2-1, 2-2' in str(
        refusal.value
    )
    assert path.read_bytes() == before


def test_a_sub_phase_marked_twice_refuses_naming_the_mark_it_carries(
    tree: Declaration,
) -> None:
    """One answer per bullet, and the two verbs share the one answer: a step
    said to be finished cannot then be said to be one nobody will do. The
    refusal names the word already there, so the operator can see which of the
    two ran."""
    path = pruned(tree)
    execute(tree, tree.transitions["ripen"], name="a-seedling", asked={"name": "2-1"})
    before = path.read_bytes()
    with pytest.raises(Refusal) as refusal:
        execute(
            tree, tree.transitions["thin"], name="a-seedling", asked={"name": "2-1"}
        )
    assert 'already disposed of 2-1: it is marked "ripened"' in str(refusal.value)
    assert path.read_bytes() == before


# --- marking: the key a disposition takes off the head ----------------------
#
# A mark ends a step, and a status key says how far the current one has got —
# so a step that is over leaves none. The mechanism is `drops`, which the
# executor has honoured since it existed; what is new is a marking verb
# declaring one. `ripen` does and `thin` does not, so absence is graded beside
# presence and nothing can pass by assuming the half implies the field.


def test_a_marking_verb_that_drops_a_key_takes_it_off_the_head(
    tree: Declaration,
) -> None:
    """No new arm: `_move` rebuilds the head without every key the verb
    ``drops``, and a state-to-itself disposition goes through that rebuild
    like any other move. The cursor stays, which is the point of dropping the
    one and not the other."""
    pruned(tree)
    path = execute(
        tree,
        tree.transitions["graft-on"],
        name="a-seedling",
        values={"graft": "2-1", "graft-status": "planned"},
    )
    assert read(path, tree)["graft-status"] == "planned"

    execute(tree, tree.transitions["ripen"], name="a-seedling", asked={"name": "2-1"})
    item = read(path, tree)
    assert "graft-status" not in item.head
    assert item["graft"] == "2-1"


def test_a_marking_verb_that_drops_nothing_leaves_the_head_alone(
    tree: Declaration,
) -> None:
    """The absence control, and it is why the fixture declares the field on
    one of its two dispositions rather than on both: `thin` marks the same
    body out of the same state and takes nothing off, so a tool that dropped
    on `marks` rather than on `drops` fails here and passes everywhere else."""
    pruned(tree)
    path = execute(
        tree,
        tree.transitions["graft-on"],
        name="a-seedling",
        values={"graft": "2-2", "graft-status": "planned"},
    )
    execute(tree, tree.transitions["thin"], name="a-seedling", asked={"name": "2-2"})
    item = read(path, tree)
    assert (item["graft"], item["graft-status"]) == ("2-2", "planned")


# --- marking: the note beside the word --------------------------------------
#
# The word says *what* was decided; a note says why. It is optional, it rides
# on `marks` — every disposition, filing ones included — and nothing derived
# reads it back. `docs/method.md#marking`.


def test_a_note_is_written_beside_the_word_and_nothing_else_moves(
    tree: Declaration,
) -> None:
    """`test_marking_rewrites_one_line_and_leaves_every_other_byte_alone`'s
    shape, one line over: a note is more of the same line, never a second."""
    path = batch(tree, "The first", "The second")
    before = path.read_text().splitlines()
    execute(
        tree,
        tree.transitions["pot-on"],
        name="a-batch",
        asked={"name": "c2", "note": "Roots to the wall."},
    )
    after = path.read_text().splitlines()
    assert len(before) == len(after)
    differing = [n for n, (one, two) in enumerate(zip(before, after)) if one != two]
    assert [after[n] for n in differing] == [
        "- **c2 — The second** **rooted** Roots to the wall."
    ]


def test_a_run_with_no_note_writes_what_it_always_wrote(tree: Declaration) -> None:
    """The ordinary case, and every run this repo has made: a disposition with
    no reason is not a lesser one, so the option is not required."""
    path = batch(tree, "The first")
    execute(tree, tree.transitions["pot-on"], name="a-batch", asked={"name": "c1"})
    assert "- **c1 — The first** **rooted**\n" in path.read_text()


@pytest.mark.parametrize(
    "note", ["", "   ", "costs more\n- **f9 — smuggled**", "it is **not** worth it"]
)
def test_a_note_that_may_not_ride_refuses_before_the_first_write(
    tree: Declaration, note: str
) -> None:
    """`subphase.note_errors`' three cases, reached through a run: the file is
    byte-identical afterwards, and a check refuses in the same words because
    it is the same code raising them."""
    path = batch(tree, "The first")
    before = path.read_bytes()
    with pytest.raises(Refusal) as refusal:
        execute(
            tree,
            tree.transitions["pot-on"],
            name="a-batch",
            asked={"name": "c1", "note": note},
        )
    assert "cannot take that note" in str(refusal.value)
    assert path.read_bytes() == before

    with pytest.raises(Refusal) as checked:
        execute(
            tree,
            tree.transitions["pot-on"],
            name="a-batch",
            asked={"name": "c1", "note": note},
            check=True,
        )
    assert str(checked.value) == str(refusal.value)
    assert path.read_bytes() == before


def test_a_check_says_there_is_a_note_and_not_what_it_says(
    tree: Declaration,
) -> None:
    """Its **presence**, never its content: a note is what the operator typed
    a moment ago on the same command line, so echoing it back verifies nothing
    they cannot see. A clause's absence is meaningful the way `_would`'s
    already are, so a run with no note says nothing about one."""
    batch(tree, "The first")
    said = execute(
        tree,
        tree.transitions["pot-on"],
        name="a-batch",
        asked={"name": "c1", "note": "Nobody has measured it."},
        check=True,
    )
    assert said.endswith('and would mark c1 "rooted" with a note')
    assert "measured" not in said

    without = execute(
        tree,
        tree.transitions["pot-on"],
        name="a-batch",
        asked={"name": "c1"},
        check=True,
    )
    assert without.endswith('and would mark c1 "rooted"')


def test_a_filing_disposition_takes_one_and_it_stays_out_of_the_item(
    tree: Declaration,
) -> None:
    """Every marking verb, `files` ones included — uniform arms over a bespoke
    rule. The note goes outside the **first** bold run as well as the second,
    so the filed item's default title is the bullet's own text still."""
    carrier = lined(tree, note="Filed where the reader is.")
    assert (
        "- **c1 — The first** **lined** Filed where the reader is."
        in read(carrier, tree).body
    )
    filed = tree.root / "greenhouse" / "the-first.md"
    assert filed.is_file()
    assert read(filed, tree).head["title"] == "The first"


@pytest.mark.parametrize("wanted", ["c9", "c1"])
def test_a_check_refuses_in_the_words_a_real_run_refuses_in(
    tree: Declaration, wanted: str
) -> None:
    """Byte for byte, because it is the same code raising it: both refusals
    happen before the first write, which is what makes the identity hold by
    construction rather than by two messages agreeing."""
    batch(tree, "The first")
    execute(tree, tree.transitions["pot-on"], name="a-batch", asked={"name": "c1"})

    def run(check: bool) -> str:
        with pytest.raises(Refusal) as refusal:
            execute(
                tree,
                tree.transitions["pot-on"],
                name="a-batch",
                asked={"name": wanted},
                check=check,
            )
        return str(refusal.value)

    assert run(check=True) == run(check=False)


# --------------------------------------------------------------------------
# The `files` half: the second item a disposition creates
# --------------------------------------------------------------------------
#
# `line-out` files into `greenhouse` — the fixture's **plain** state, because
# a filed item is filed rather than placed — while marking `lined` onto the
# cutting it was written from. It sits beside `pot-on`, which marks and files
# nothing, so one state carries two dispositions and the rider is visible from
# a declaration that loads.


def lined(tree: Declaration, **asked: object) -> Path:
    """A batch of two, with `c1` lined out under whatever was asked for."""
    batch(tree, "The first", "The second")
    return execute(
        tree,
        tree.transitions["line-out"],
        name="a-batch",
        asked={"name": "c1", "body": "Prose for the seedling.", **asked},
    )


def test_a_filing_run_writes_both_files(tree: Declaration) -> None:
    """One run, two items: the carrier it was given and the seedling it made.
    What comes *back* is the carrier — the destination of the item the run
    moved, uniformly, so a pipe carries that and nothing else."""
    moved = lined(tree)
    assert moved == tree.root / "propagator" / "a-batch.md"
    filed = tree.root / "greenhouse" / "the-first.md"
    assert filed.is_file()
    assert read(filed, tree).body.strip() == "Prose for the seedling."


def test_the_filed_item_carries_the_provenance_the_table_names(
    tree: Declaration,
) -> None:
    """Two facts in two keys, the fixture's own words — the carrier's slug and
    the bullet's name — which is what makes the reverse direction a join
    rather than a correspondence read off matching titles."""
    lined(tree)
    head = read(tree.root / "greenhouse" / "the-first.md", tree).head
    assert head == {"title": "The first", "batch": "a-batch", "cutting": "c1"}


def test_the_same_run_marks_the_bullet_it_filed_from(tree: Declaration) -> None:
    """The rider, from the run's end: a verb that filed without disposing of
    the bullet would file the same finding again on the next run."""
    moved = lined(tree)
    body = read(moved, tree).body
    assert "- **c1 — The first** **lined**" in body
    assert "- **c2 — The second**" in body


def test_the_title_comes_from_the_bullet_and_title_overrides_it(
    tree: Declaration,
) -> None:
    """Zero typing is the point — eight findings, eight runs — and the
    override earns its place because a finding is a *symptom* where an item is
    *work*. The provenance is in keys, so the titles need not match."""
    lined(tree, title="Line this one out properly")
    filed = tree.root / "greenhouse" / "line-this-one-out-properly.md"
    assert read(filed, tree).head["cutting"] == "c1"
    assert not (tree.root / "greenhouse" / "the-first.md").exists()


def test_a_colliding_slug_refuses_in_the_creating_verbs_words_and_writes_neither(
    tree: Declaration,
) -> None:
    """`_create`'s refusal, reached through `_create`'s own helpers: one rule
    with two callers rather than a second spelling that could soften. It is
    raised before the first write, so the carrier is byte-identical too."""
    execute(tree, tree.transitions["sprout"], name="The first", body="Prose.")
    batch(tree, "The first")
    carrier = tree.root / "propagator" / "a-batch.md"
    before = carrier.read_bytes()
    with pytest.raises(Refusal) as refusal:
        execute(
            tree,
            tree.transitions["line-out"],
            name="a-batch",
            asked={"name": "c1", "body": "Prose."},
        )
    assert 'the slug "the-first" is already held by' in str(refusal.value)
    assert carrier.read_bytes() == before


@pytest.mark.parametrize("body", [None, "   "])
def test_a_filing_with_no_prose_refuses_in_the_creating_verbs_words(
    tree: Declaration, body: str | None
) -> None:
    """The rule does not weaken because the run had a bullet to start from:
    the finding says what was observed, the item says what to do about it."""
    batch(tree, "The first")
    with pytest.raises(Refusal) as refusal:
        execute(
            tree,
            tree.transitions["line-out"],
            name="a-batch",
            asked={"name": "c1", "body": body},
        )
    assert str(refusal.value).startswith("line-out needs a body. An item is a title")


def test_a_bullet_with_no_title_refuses_saying_it_has_nothing_to_name_by(
    tree: Declaration,
) -> None:
    """A bullet may be its name alone. There is then nothing to call the item,
    and guessing one would file work under a label nobody wrote."""
    batch(tree, "The first")
    path = tree.root / "propagator" / "a-batch.md"
    path.write_text(
        path.read_text().replace("- **c1 — The first**", "- **c1**"), encoding="utf-8"
    )
    with pytest.raises(Refusal) as refusal:
        execute(
            tree,
            tree.transitions["line-out"],
            name="a-batch",
            asked={"name": "c1", "body": "Prose."},
        )
    assert "says only its name, so line-out has nothing to call the item" in str(
        refusal.value
    )


def test_a_finding_already_disposed_of_refuses_and_files_nothing(
    tree: Declaration,
) -> None:
    """`_disposing` runs once and first, so the "disposed of once" rule holds
    for the verb that files exactly as it does for the one that does not —
    and no second item is left behind by the refused run."""
    lined(tree)
    with pytest.raises(Refusal) as refusal:
        execute(
            tree,
            tree.transitions["line-out"],
            name="a-batch",
            asked={"name": "c1", "body": "Again.", "title": "Another go"},
        )
    assert 'already disposed of c1: it is marked "lined"' in str(refusal.value)
    assert not (tree.root / "greenhouse" / "another-go.md").exists()


def test_a_check_names_the_file_it_would_write_and_reserves_nothing(
    tree: Declaration,
) -> None:
    """The reservation `_file_it` makes is a **write**, and so is the
    directory it makes — both run after the seam, so a check leaves the tree
    no directory heavier and no filename reserved.

    The `greenhouse` directory is taken away first, because the fixture makes
    every declared state's directory up front: asserting against a directory
    something else created would grade nothing, which is how this test read
    before 7-4 noticed."""
    batch(tree, "The first")
    (tree.root / "greenhouse").rmdir()
    carrier = tree.root / "propagator" / "a-batch.md"
    before = carrier.read_bytes()
    said = execute(
        tree,
        tree.transitions["line-out"],
        name="a-batch",
        asked={"name": "c1", "body": "Prose."},
        check=True,
    )
    assert said.endswith(
        f'which stays in propagator, and would mark c1 "lined" and file '
        "greenhouse/the-first.md"
    )
    assert not (tree.root / "greenhouse").exists()
    assert carrier.read_bytes() == before


@pytest.mark.parametrize("asked", [{"name": "c9"}, {"body": " "}, {"title": "  "}])
def test_a_filing_check_refuses_in_the_words_a_real_run_refuses_in(
    tree: Declaration, asked: dict
) -> None:
    """Byte for byte, over each of the three refusals a filing adds: they all
    happen before the first write, so it is the run's own code raising them."""
    batch(tree, "The first")
    execute(tree, tree.transitions["sprout"], name="The first", body="Prose.")

    def run(check: bool) -> str:
        with pytest.raises(Refusal) as refusal:
            execute(
                tree,
                tree.transitions["line-out"],
                name="a-batch",
                asked={"name": "c1", "body": "Prose.", **asked},
                check=check,
            )
        return str(refusal.value)

    assert run(check=True) == run(check=False)


def test_the_notice_names_both_files(tree: Declaration) -> None:
    """An item appeared somewhere nobody asked for a file, and a bullet
    elsewhere was marked — `_archiving`'s notice, over the other second file.
    """
    carrier = batch(tree, "The first")
    said: list[str] = []
    execute(
        tree,
        tree.transitions["line-out"],
        name="a-batch",
        asked={"name": "c1", "body": "Prose."},
        announce=said.append,
    )
    assert said == [
        "greenhouse/the-first.md: filed from c1 in "
        f"{carrier.relative_to(tree.root)}, which this run marked \"lined\""
    ]


# --------------------------------------------------------------------------
# The `dissolves` half: the file that goes away, and the edges it clears
# --------------------------------------------------------------------------
#
# `fell` is the fixture's verb that declares **both** halves: out of `orchard`
# — the numbered state, and the only one declaring `dependencies` — with no
# `to` at all. `compost` beside it dissolves out of `greenhouse`, which is
# unnumbered and so cannot archive: 5-3's `merge` shape, and the proof that
# `dissolves` is not a rider on `archives`.
#
# `grub-out` stays the control throughout: same source state, same `archives`,
# and it moves the tree.

RECORD = "What it was, and why it came down."


def felled(tree: Declaration, name: str = "a-seedling", record: str = RECORD) -> Path:
    """One tree, put in the orchard and then taken down."""
    orchard(tree, name)
    return execute(
        tree, tree.transitions["fell"], name=name, asked={"record": record}
    )


def waits(tree: Declaration, name: str, on: object) -> Path:
    """``name``'s head, rewritten to wait on ``on``.

    By hand because no transition ``sets`` the fixture's ``after`` — it is a
    key a person writes, which is what an edge is.
    """
    one = read(tree.root / "orchard" / f"{name}.md", tree)
    head = dict(one.head)
    head["after"] = on
    write(Item(path=one.path, state=one.state, head=head, body=one.body))
    return one.path


def test_a_verb_that_dissolves_takes_the_file_away(tree: Declaration) -> None:
    """The half 5-1 left: no destination, no file, nothing left in any state."""
    source = tree.root / "orchard" / "a-seedling.md"
    felled(tree)
    assert not source.exists()
    assert [one.slug for one in read_items(tree)] == []


def test_the_entry_is_in_the_archive_and_the_register_stays_contiguous(
    tree: Declaration,
) -> None:
    """The first done line, whole: the item is gone and the number is not."""
    felled(tree)
    assert "## 2. A seedling" in filed(tree)
    assert numbered.numbers(filed(tree)) == [1, 2]
    unread = numbered.unreadable(filed(tree))
    assert numbered.heading_errors(unread, "orchard-archive.md") == []


def test_the_record_lands_under_the_heading(tree: Declaration) -> None:
    """The decided route for the prose: it comes in with the run, because the
    body it is written from is deleted by that same run."""
    felled(tree)
    assert f"## 2. A seedling\n\n{RECORD}\n" in filed(tree)


def test_the_run_says_the_entry_is_written_rather_than_waiting(
    tree: Declaration,
) -> None:
    """`grub-out`'s notice says a record still goes under the heading, because
    the item survives to be written from. This one's must not — the entry is
    finished, and telling a session to go and fill it in would send it to a
    file that is gone."""
    said: list[str] = []
    orchard(tree, "a-seedling")
    execute(
        tree,
        tree.transitions["fell"],
        name="a-seedling",
        asked={"record": RECORD},
        announce=said.append,
    )
    assert "with the record under it" in said[0]
    assert "still filed" not in " ".join(said)
    assert any("is gone" in one for one in said)


def test_the_next_mint_carries_on_over_the_dissolved_number(
    tree: Declaration,
) -> None:
    """The whole reason the entry outlives the file, reached from the verb
    that actually deletes it."""
    felled(tree)
    seedling(tree, "b-seedling", READY.replace("A seedling", "B seedling"))
    path = execute(tree, tree.transitions["transplant"], name="b-seedling")
    assert read(path, tree)["number"] == 3


def test_a_dissolving_verb_that_archives_nothing_just_removes_the_file(
    tree: Declaration,
) -> None:
    """`compost`, out of the unnumbered state. `dissolves` stands alone, so
    5-3's `merge` — which cannot archive — has a shape to be."""
    document = filed(tree)
    source = seedling(tree, "a-seedling", READY)
    returned = execute(tree, tree.transitions["compost"], name="a-seedling")
    assert not source.exists()
    assert returned == source
    assert filed(tree) == document


def test_the_path_the_run_returns_is_the_archive_when_it_archives(
    tree: Declaration,
) -> None:
    """"The file it wrote": for a dissolving verb its own path names something
    that is not there, and the archive is what a reader wants next."""
    assert felled(tree) == tree.root / "orchard-archive.md"


def test_the_item_the_verb_dissolves_is_never_its_own_referent(
    tree: Declaration,
) -> None:
    """It is being deleted; an edge on it goes with it. Skipping it is what
    keeps the walk from writing the file it just unlinked."""
    orchard(tree, "a-seedling")
    waits(tree, "a-seedling", ["a-seedling"])
    execute(tree, tree.transitions["fell"], name="a-seedling", asked={"record": RECORD})
    assert [one.slug for one in read_items(tree)] == []


# --- the edges ------------------------------------------------------------


def test_a_referents_list_edge_loses_one_slug_and_keeps_the_rest(
    tree: Declaration,
) -> None:
    """A list loses the entry and stays a list: the value is the workflow's
    own, and a verb about something else does not reformat it."""
    orchard(tree, "a-seedling")
    orchard(tree, "b-seedling")
    orchard(tree, "c-seedling")
    waits(tree, "b-seedling", ["a-seedling", "c-seedling"])
    execute(tree, tree.transitions["fell"], name="a-seedling", asked={"record": RECORD})
    assert read(tree.root / "orchard" / "b-seedling.md", tree)["after"] == [
        "c-seedling"
    ]


def test_a_referent_whose_only_edge_was_the_dissolved_one_loses_the_key(
    tree: Declaration,
) -> None:
    """Rather than keeping `after = []`. An empty key carries nothing, so it
    would be a fact the head states and nothing means."""
    orchard(tree, "a-seedling")
    orchard(tree, "b-seedling")
    waits(tree, "b-seedling", ["a-seedling"])
    execute(tree, tree.transitions["fell"], name="a-seedling", asked={"record": RECORD})
    assert "after" not in read(tree.root / "orchard" / "b-seedling.md", tree)


def test_a_bare_string_edge_is_cleared_the_same_way(tree: Declaration) -> None:
    """A bare string is one edge, `depends.edges`' rule at the other end."""
    orchard(tree, "a-seedling")
    orchard(tree, "b-seedling")
    waits(tree, "b-seedling", "a-seedling")
    execute(tree, tree.transitions["fell"], name="a-seedling", asked={"record": RECORD})
    assert "after" not in read(tree.root / "orchard" / "b-seedling.md", tree)


def test_an_item_in_a_state_that_declares_no_dependencies_is_untouched(
    tree: Declaration,
) -> None:
    """`greenhouse` names no key, so a seedling there carrying `after` is
    carrying a fact nothing was declared to read — and reading it here would
    be the tool owning a vocabulary the declaration did not hand it."""
    orchard(tree, "a-seedling")
    stray = seedling(
        tree, "b-seedling", READY.replace('tag = "spring"', 'after = "a-seedling"')
    )
    before = stray.read_bytes()
    execute(tree, tree.transitions["fell"], name="a-seedling", asked={"record": RECORD})
    assert stray.read_bytes() == before


def test_an_item_naming_something_else_is_not_rewritten_at_all(
    tree: Declaration,
) -> None:
    """No edit means no write: an untouched referent keeps its bytes, so a
    close-out cannot silently reformat somebody's head."""
    orchard(tree, "a-seedling")
    orchard(tree, "b-seedling")
    waits(tree, "b-seedling", ["c-seedling"])
    before = (tree.root / "orchard" / "b-seedling.md").read_bytes()
    execute(tree, tree.transitions["fell"], name="a-seedling", asked={"record": RECORD})
    assert (tree.root / "orchard" / "b-seedling.md").read_bytes() == before


def test_every_edited_item_is_named_on_the_announce_callback(
    tree: Declaration,
) -> None:
    """A line each rather than a count, naming the file and the key, so a
    session can check every edit rather than being told how many there were."""
    said: list[str] = []
    orchard(tree, "a-seedling")
    orchard(tree, "b-seedling")
    orchard(tree, "c-seedling")
    waits(tree, "b-seedling", ["a-seedling"])
    waits(tree, "c-seedling", ["a-seedling"])
    execute(
        tree,
        tree.transitions["fell"],
        name="a-seedling",
        asked={"record": RECORD},
        announce=said.append,
    )
    edited = [one for one in said if "out of after" in one]
    assert len(edited) == 2
    assert any("b-seedling.md" in one for one in edited)
    assert any("c-seedling.md" in one for one in edited)


def test_a_verb_that_does_not_dissolve_clears_no_edge(tree: Declaration) -> None:
    """The control. `grub-out` archives out of the same state and leaves every
    inbound edge alone, because a moved item is still filed — which is the
    reason declining is a move (`docs/method.md#dependencies`)."""
    orchard(tree, "a-seedling")
    orchard(tree, "b-seedling")
    waits(tree, "b-seedling", ["a-seedling"])
    execute(tree, tree.transitions["grub-out"], name="a-seedling")
    assert read(tree.root / "orchard" / "b-seedling.md", tree)["after"] == [
        "a-seedling"
    ]


def test_a_referent_another_session_holds_is_edited_anyway(
    tree: Declaration, session: Identity
) -> None:
    """**The decision, pinned** (John, 2026-09-04: it is a mechanical edit,
    which is the reason for the answer). Refusing would let an unrelated claim
    on an unrelated item block a close-out; skipping would leave the dangling
    edge the invariant forbids. The claim is about who is doing that item's
    work, and clearing an edge is not doing it."""
    orchard(tree, "a-seedling")
    orchard(tree, "b-seedling")
    waits(tree, "b-seedling", ["a-seedling"])
    someone_else(tree, "b-seedling", pid=os.getpid())

    execute(tree, tree.transitions["fell"], name="a-seedling", asked={"record": RECORD})
    assert "after" not in read(tree.root / "orchard" / "b-seedling.md", tree)
    assert claim.path(tree.root, "b-seedling").exists()


def test_a_head_the_read_cannot_parse_refuses_the_run_and_writes_nothing(
    tree: Declaration,
) -> None:
    """**The limit, pinned rather than engineered around.** The referent's head
    is not *graded* by the edit — removing a value cannot introduce a defect,
    and `_place`'s destination check has no destination to run against — but
    the walk that finds referents is `read.items`, which refuses on any head in
    the tree it cannot read. So a stranger's typo does block a close-out, the
    same way it already blocks every mint into a numbered state. That is
    pre-existing and loud: the run refuses by name, having written nothing, and
    the fix is one edit to the named file."""
    source = orchard(tree, "a-seedling")
    orchard(tree, "b-seedling")
    path = tree.root / "orchard" / "b-seedling.md"
    path.write_text(
        path.read_text().replace('title = ', 'nonsense = "x"\ntitle = '),
        encoding="utf-8",
    )
    document = filed(tree)

    with pytest.raises(Refusal) as refusal:
        execute(
            tree, tree.transitions["fell"], name="a-seedling", asked={"record": RECORD}
        )
    assert "b-seedling.md" in str(refusal.value)
    assert '"nonsense" is not a declared key' in str(refusal.value)
    assert source.exists() and filed(tree) == document


# --- what a refusal leaves behind ----------------------------------------


def test_a_refused_run_leaves_the_item_the_archive_and_every_referent(
    tree: Declaration,
) -> None:
    """Every refusal is computed before **any** of the four writes, so nothing
    is half done: an unreadable `##` stops the run with the tree untouched."""
    source = orchard(tree, "a-seedling")
    orchard(tree, "b-seedling")
    referent = waits(tree, "b-seedling", ["a-seedling"])
    archive(tree, "## Section 1: A felled tree\n")
    before, held, document = (
        source.read_bytes(),
        referent.read_bytes(),
        filed(tree),
    )

    with pytest.raises(Refusal, match="Section 1: A felled tree"):
        execute(
            tree, tree.transitions["fell"], name="a-seedling", asked={"record": RECORD}
        )
    assert source.read_bytes() == before
    assert referent.read_bytes() == held
    assert filed(tree) == document


def test_an_item_with_no_number_refuses_and_the_file_survives(
    tree: Declaration,
) -> None:
    """The refusal `grub-out` already gives, and here it is load-bearing: the
    run would otherwise delete the only copy of what the entry was for."""
    stray = tree.root / "orchard" / "a-stray.md"
    stray.write_text(READY, encoding="utf-8")
    with pytest.raises(Refusal, match="carries no number"):
        execute(
            tree, tree.transitions["fell"], name="a-stray", asked={"record": RECORD}
        )
    assert stray.exists()


def test_a_verb_aimed_at_an_item_in_another_state_says_where_it_is(
    tree: Declaration,
) -> None:
    """The shared preamble, reached through the dissolving arm: one copy of
    the wrong-state refusal rather than a second spelling beside it."""
    seedling(tree, "a-seedling", READY)
    with pytest.raises(Refusal) as refusal:
        execute(
            tree, tree.transitions["fell"], name="a-seedling", asked={"record": RECORD}
        )
    assert "is in greenhouse" in str(refusal.value)


def test_a_dissolving_verbs_own_requires_is_graded_before_anything_goes(
    tree: Declaration, tmp_path: Path
) -> None:
    """`requires` and `refuses` stay declarable beside `dissolves` precisely
    because they read the head **before** it goes, and this is the shape
    `archive-plan` uses for its completion conditions."""
    plan = tree.source
    plan.write_text(
        plan.read_text().replace(
            'from      = "orchard"\narchives  = true\ndissolves = true\n',
            'from      = "orchard"\narchives  = true\ndissolves = true\n'
            'requires  = ["rootstock"]\n',
        )
    )
    amended = load(plan)
    source = orchard(amended, "a-seedling")
    with pytest.raises(Refusal, match='requires "rootstock"'):
        execute(
            amended,
            amended.transitions["fell"],
            name="a-seedling",
            asked={"record": RECORD},
        )
    assert source.exists()


# --------------------------------------------------------------------------
# The dangle check: an archiving dissolve over a carrier still holding work
# --------------------------------------------------------------------------
#
# `fell` is the fixture's verb that declares **both** halves, and `propagator`
# is the state whose items name an owner: a batch names the tree it was struck
# for in `for-tree`, which is the fixture's word and not this repo's. `grub-out` is the control
# on one side — it archives and **moves**, so it refuses nothing — and
# `compost` on the other, which dissolves and archives nothing.
#
# `dangle_errors` is pure, so the table below builds `Item`s and passes them
# in: no `tmp_path` until the last test, which is the seam.


def standing(tree: Declaration, name: str = "a-seedling") -> Item:
    """One tree in the orchard, as an item, with no file behind it."""
    return Item(
        path=tree.root / tree.states["orchard"].path / f"{name}.md",
        state=tree.states["orchard"],
        head={"title": "A seedling", "number": 2},
        body="Prose.\n",
    )


def carrying(
    tree: Declaration,
    *marks: str | None,
    owner: str = "a-seedling",
    pending: bool = False,
    state: str = "propagator",
    key: str = "for-tree",
) -> Item:
    """A batch in the propagator naming ``owner``, one cutting per mark given.

    A mark of ``None`` is a finding nobody has disposed of. ``pending`` puts
    the state's pending bullet back at the end, which is the shape a batch
    still being decomposed has.
    """
    cuttings = "".join(
        f"- **c{number} — A finding.**" + (f" **{mark}**\n" if mark else "\n")
        for number, mark in enumerate(marks, start=1)
    )
    if pending:
        cuttings += f"- {UNSTRUCK}\n"
    return Item(
        path=tree.root / tree.states["propagator"].path / "a-batch.md",
        state=tree.states[state],
        head={"title": "A batch", key: owner, "for-step": "2-1"},
        body=f"Prose.\n\n### Cuttings\n{cuttings}",
    )


def test_a_carrier_still_holding_findings_refuses_naming_the_key_and_the_count(
    tree: Declaration,
) -> None:
    """The done line, pure: the file, the **declared** key and `N of M` in the
    tool's own noun. Never the state's heading and never this repo's word for
    what the state is — both are the declaration's to choose."""
    held = carrying(tree, None, "rooted", None)
    errors = dangle_errors(standing(tree), tree.transitions["fell"], [held], tree.root)
    assert len(errors) == 1
    assert str(held.path.relative_to(tree.root)) in errors[0]
    assert "for-tree" in errors[0]
    # Off the sentence rather than off the whole line: `tmp_path` is named
    # after the test, and this test's name has both words in it.
    said = errors[0].removeprefix(str(held.path))
    assert f"2 of its 3 {subphase.NAME}" in said
    assert "Cuttings" not in said and "carrier" not in said


def test_a_carrier_whose_every_finding_is_disposed_of_stops_nothing(
    tree: Declaration,
) -> None:
    """The other polarity, and the one a close-out reaches: the work is in the
    tree, so the record filed now has it."""
    held = carrying(tree, "rooted", "lined", "rooted")
    assert dangle_errors(standing(tree), tree.transitions["fell"], [held], tree.root) == []


def test_an_archiving_verb_that_moves_the_item_refuses_nothing(
    tree: Declaration,
) -> None:
    """The decision, as a test (John, 2026-09-07). `grub-out` archives and
    **moves**, which is `decline`'s shape: the section lives on, so what named
    it still resolves and nothing is orphaned. Abandoning a half-done section
    stays one run rather than one run per open finding."""
    held = carrying(tree, None, None)
    assert dangle_errors(standing(tree), tree.transitions["grub-out"], [held], tree.root) == []


def test_a_dissolving_verb_that_archives_nothing_refuses_nothing(
    tree: Declaration,
) -> None:
    """The gate's other half. `compost` takes a file away and records nothing,
    so there is no record to be missing the work — the rule is over the pair,
    and one half of it is not the rule."""
    held = carrying(tree, None, None)
    assert dangle_errors(standing(tree), tree.transitions["compost"], [held], tree.root) == []


def test_a_carrier_struck_for_something_else_is_not_read(
    tree: Declaration,
) -> None:
    """Scope is the seal's own value, not the state: another tree's open batch
    says nothing about this one."""
    held = carrying(tree, None, None, owner="b-seedling")
    assert dangle_errors(standing(tree), tree.transitions["fell"], [held], tree.root) == []


def test_the_pending_bullet_is_not_an_open_finding(tree: Declaration) -> None:
    """`bullets` drops the marker and so does this: `docs/method.md#carrier`
    calls a forgotten one loud and harmless, and a gate over it would reverse
    a reading already written down."""
    held = carrying(tree, "rooted", "rooted", pending=True)
    assert dangle_errors(standing(tree), tree.transitions["fell"], [held], tree.root) == []


def test_an_item_whose_state_seals_nothing_is_never_read(
    tree: Declaration,
) -> None:
    """`_clearing`'s scope rule, one field over. An `orchard` tree carrying
    `for-tree` in its head is carrying a fact nothing was declared to read
    here, and a state that seals but counts no bullets has none to be open."""
    orchards = carrying(tree, None, None, state="orchard")
    assert dangle_errors(standing(tree), tree.transitions["fell"], [orchards], tree.root) == []

    seals = dataclasses.replace(tree.states["propagator"], sub_phases=None)
    tree.states["sealing-nothing"] = seals
    held = carrying(tree, None, None, state="sealing-nothing")
    assert dangle_errors(standing(tree), tree.transitions["fell"], [held], tree.root) == []


def test_an_open_carrier_refuses_the_run_and_writes_nothing(
    tree: Declaration,
) -> None:
    """The seam: one refusal before the first write, so the item, the archive
    and the batch are all byte-identical — and the close-out goes through once
    every finding has been disposed of."""
    orchard(tree, "a-seedling")
    batch(tree, "The first", "The second", owner="a-seedling")
    before = snapshot(tree)

    with pytest.raises(Refusal) as raised:
        execute(
            tree,
            tree.transitions["fell"],
            name="a-seedling",
            asked={"record": RECORD},
        )
    assert "a-batch.md" in str(raised.value)
    assert f"2 of its 2 {subphase.NAME}" in str(raised.value)
    assert snapshot(tree) == before

    for name in ("c1", "c2"):
        execute(tree, tree.transitions["pot-on"], name="a-batch", asked={"name": name})
    execute(
        tree, tree.transitions["fell"], name="a-seedling", asked={"record": RECORD}
    )
    assert not (tree.root / "orchard" / "a-seedling.md").exists()
    assert "## 2. A seedling" in filed(tree)


# --------------------------------------------------------------------------
# The close as a gate: an archiving dissolve over a section still holding work
# --------------------------------------------------------------------------
#
# `dangle_errors`' rule turned on the item itself, over the same two halves
# and with the same two controls: `grub-out` archives and **moves**, `compost`
# dissolves and archives nothing. The fixture's `orchard` is the bulleted,
# cursored state and `ripened`/`thinned` are its marks — neither is this
# repo's word, so nothing here can pass by agreeing with `plan.toml`.

#: `orchard`'s pending bullet, which is the fixture's sentence and not
#: `propagator`'s. The two states declare different ones on purpose.
UNPRUNED = "**unpruned — Say what the rest of the training is.**"


def growing(tree: Declaration, *marks: str | None, pending: bool = False) -> Item:
    """A tree in the orchard whose steps carry ``marks``, one bullet each."""
    steps = "".join(
        f"- **2-{number} — a step.**" + (f" **{mark}**\n" if mark else "\n")
        for number, mark in enumerate(marks, start=1)
    )
    if pending:
        steps += f"- {UNPRUNED}\n"
    return Item(
        path=tree.root / tree.states["orchard"].path / "a-seedling.md",
        state=tree.states["orchard"],
        head={"title": "A seedling", "number": 2},
        body=f"Prose.\n\n### Steps\n{steps}",
    )


def test_a_section_holding_an_unmarked_sub_phase_cannot_be_archived(
    tree: Declaration,
) -> None:
    """The done line, pure. It **lists the names** where `dangle_errors` gives
    a count and a path: these bullets are in the file the operator already has
    open, and the names are what the closing session acts on next."""
    (message,) = unmarked_errors(
        growing(tree, "ripened", None, None), tree.transitions["fell"]
    )
    assert message.startswith("it carries 2 of 3 sub-phases with no mark: 2-2, 2-3")
    assert "the body it is written from goes away with the run" in message


def test_the_count_left_matches_what_the_close_out_refuses_with(
    tree: Declaration,
) -> None:
    """The row and the refusal over **one body**, which is what the shared
    `fileplan.subphase.unmarked` buys. The listing was already showing
    the number this refusal opens with, so a session meeting the refusal is
    not learning a new fact — it is being stopped by the one on the row."""
    one = growing(tree, "ripened", None, None)
    (message,) = unmarked_errors(one, tree.transitions["fell"])
    (row,) = read_rows(tree, [one])
    assert message.startswith(f"it carries {row[subphase.LEFT]} of 3 ")
    assert row[subphase.LEFT] == 2


def test_a_section_whose_every_bullet_is_marked_archives_clean(
    tree: Declaration,
) -> None:
    """The other polarity, and the one that shuts the window 12-2 opened: with
    `done` gone from the status key, a mark on every bullet is the only thing
    that says a section is finished."""
    assert (
        unmarked_errors(growing(tree, "ripened", "ripened"), tree.transitions["fell"])
        == []
    )


def test_a_skipped_sub_phase_counts_as_marked_for_the_close(
    tree: Declaration,
) -> None:
    """**Any** mark, never a particular word. A step that will not be done is
    as disposed of as one that shipped, and nothing here knows either word."""
    assert (
        unmarked_errors(growing(tree, "thinned", "ripened"), tree.transitions["fell"])
        == []
    )


def test_an_unfinished_decomposition_blocks_the_close_by_its_pending_marker(
    tree: Declaration,
) -> None:
    """The one place this rule and `dangle_errors` disagree, pinned so it
    cannot be "corrected" into agreement. A carrier's forgotten marker is loud
    and harmless; a section's marker is the tool saying the decomposition
    itself is unfinished, and closing then files an entry for sub-phases
    nobody has written down yet. It is named like any other bullet."""
    (message,) = unmarked_errors(
        growing(tree, "ripened", pending=True), tree.transitions["fell"]
    )
    assert "1 of 2 sub-phases with no mark: unpruned" in message


def test_an_archiving_verb_that_moves_the_section_is_not_graded(
    tree: Declaration,
) -> None:
    """The mutation check on the halves, and `decline`'s own shape: a section
    abandoned **half done** is the whole content of that decision, so a verb
    that archives and does not dissolve may take one with every bullet open."""
    assert (
        unmarked_errors(growing(tree, None, None), tree.transitions["grub-out"]) == []
    )


def test_a_dissolving_verb_that_archives_nothing_is_not_graded(
    tree: Declaration,
) -> None:
    """The gate's other half, `dangle_errors`' control exactly: no record is
    filed, so there is no record for the section to be missing from."""
    assert unmarked_errors(growing(tree, None, None), tree.transitions["compost"]) == []


def test_a_state_that_counts_no_sub_phases_is_not_graded(
    tree: Declaration,
) -> None:
    """A consumer whose dissolving verb leaves a state with no bullets grades
    nothing — the absence rule every field here keeps."""
    assert (
        unmarked_errors(
            Item(
                path=tree.root / "greenhouse" / "a-batch.md",
                state=tree.states["greenhouse"],
                head={"title": "A batch"},
                body="Prose.\n",
            ),
            tree.transitions["compost"],
        )
        == []
    )


# --------------------------------------------------------------------------
# The `absorbs` half: the edge that is repointed rather than cleared
# --------------------------------------------------------------------------
#
# `inarch` is the fixture's absorbing verb: out of the unnumbered
# `greenhouse`, dissolving and absorbing, which is `merge`'s shape exactly. Its
# referents live in `orchard` — the one fixture state that declares
# `dependencies` — and its survivor may be a seedling or a tree, so the
# cross-state merge and the self-edge are both reachable.
#
# `compost` stays the control: same source state, same `dissolves`, and it
# takes the edges out rather than moving them.


def inarched(
    tree: Declaration,
    name: str = "a-seedling",
    into: str = "b-seedling",
    announce: object = None,
) -> Path:
    """One seedling, absorbed into another item."""
    return execute(
        tree,
        tree.transitions["inarch"],
        name=name,
        asked={"into": into},
        announce=announce,
    )


def test_a_referents_list_edge_is_repointed_at_the_survivor(
    tree: Declaration,
) -> None:
    """The whole verb in one move: the edge is not taken out, it names the item
    the work continues as. A list keeps its shape and its other entries."""
    seedling(tree, "a-seedling", READY)
    seedling(tree, "b-seedling", READY)
    orchard(tree, "c-seedling")
    waits(tree, "c-seedling", ["a-seedling", "d-seedling"])

    inarched(tree)
    assert read(tree.root / "orchard" / "c-seedling.md", tree)["after"] == [
        "b-seedling",
        "d-seedling",
    ]
    assert not (tree.root / "greenhouse" / "a-seedling.md").exists()


def test_a_bare_string_edge_is_repointed_the_same_way(tree: Declaration) -> None:
    """A bare string is one edge, `depends.edges`' rule at the other end, and
    it stays a bare string: the value is the workflow's own."""
    seedling(tree, "a-seedling", READY)
    seedling(tree, "b-seedling", READY)
    orchard(tree, "c-seedling")
    waits(tree, "c-seedling", "a-seedling")

    inarched(tree)
    assert read(tree.root / "orchard" / "c-seedling.md", tree)["after"] == "b-seedling"


def test_the_repointed_edge_is_named_on_the_announce_callback(
    tree: Declaration,
) -> None:
    """A line each, naming the file, the key **and** the survivor, so a session
    can check every edit rather than being told how many there were."""
    said: list[str] = []
    seedling(tree, "a-seedling", READY)
    seedling(tree, "b-seedling", READY)
    orchard(tree, "c-seedling")
    waits(tree, "c-seedling", ["a-seedling"])

    inarched(tree, announce=said.append)
    assert any(
        'c-seedling.md: pointed "a-seedling" at "b-seedling" in after' in one
        for one in said
    )


def test_the_survivors_own_edge_to_the_absorbed_item_is_dropped(
    tree: Declaration,
) -> None:
    """**John's decision, 2026-09-04.** `--into` resolves tree-wide, so the
    survivor may be in a state that declares `dependencies` and its own head
    can name the item being absorbed. Repointing that entry would write an
    item waiting on itself, so the one entry is dropped instead — and the
    value it empties **loses the key**, `without`'s rule unchanged."""
    said: list[str] = []
    seedling(tree, "a-seedling", READY)
    orchard(tree, "b-seedling")
    waits(tree, "b-seedling", ["a-seedling"])

    inarched(tree, announce=said.append)
    assert "after" not in read(tree.root / "orchard" / "b-seedling.md", tree)
    assert any(
        'b-seedling.md: took "a-seedling" out of after — it is this item now'
        in one
        for one in said
    )


def test_a_survivor_that_also_waits_on_something_else_keeps_that_edge(
    tree: Declaration,
) -> None:
    """The self-edge is dropped, not the key: only the entry naming the item
    being absorbed goes, and the rest of the survivor's head is untouched."""
    seedling(tree, "a-seedling", READY)
    orchard(tree, "b-seedling")
    orchard(tree, "c-seedling")
    waits(tree, "b-seedling", ["a-seedling", "c-seedling"])

    inarched(tree)
    assert read(tree.root / "orchard" / "b-seedling.md", tree)["after"] == [
        "c-seedling"
    ]


def test_an_item_in_a_state_that_declares_no_dependencies_is_untouched_by_a_merge(
    tree: Declaration,
) -> None:
    """`greenhouse` names no key, so a seedling there carrying `after` is
    carrying a fact nothing was declared to read — the same scope rule the
    clearing branch keeps, because it is one walk rather than two."""
    seedling(tree, "a-seedling", READY)
    seedling(tree, "b-seedling", READY)
    stray = seedling(
        tree, "c-seedling", READY.replace('tag = "spring"', 'after = "a-seedling"')
    )
    before = stray.read_bytes()

    inarched(tree)
    assert stray.read_bytes() == before


def test_a_merge_with_no_referents_is_not_a_special_case(
    tree: Declaration,
) -> None:
    """`_clearing` already hands back nothing when nothing names the item, and
    the absorbing branch lives inside the same loop — so a merge nothing points
    at runs the same arms and announces only the removal."""
    said: list[str] = []
    source = seedling(tree, "a-seedling", READY)
    seedling(tree, "b-seedling", READY)

    returned = inarched(tree, announce=said.append)
    assert not source.exists()
    assert returned == source
    assert len(said) == 1
    assert said[0].endswith("a-seedling.md is gone: inarch took it away")


def test_the_survivors_file_is_byte_identical_after_a_merge(
    tree: Declaration,
) -> None:
    """**The done line.** Nothing records what was absorbed (John, 2026-09-04):
    the survivor is neither graded nor edited, and the only residue of a merge
    is that every reference now points at it."""
    seedling(tree, "a-seedling", READY)
    survivor = seedling(tree, "b-seedling", READY)
    orchard(tree, "c-seedling")
    waits(tree, "c-seedling", ["a-seedling"])
    before = survivor.read_bytes()

    inarched(tree)
    assert survivor.read_bytes() == before


def test_a_merge_deletes_the_item_and_writes_no_archive(
    tree: Declaration,
) -> None:
    """It archives nothing because `greenhouse` mints no number — which is
    what makes deleting the original safe: no hole in the register."""
    document = filed(tree)
    source = seedling(tree, "a-seedling", READY)
    seedling(tree, "b-seedling", READY)

    inarched(tree)
    assert not source.exists()
    assert [one.slug for one in read_items(tree)] == ["b-seedling"]
    assert filed(tree) == document


def test_a_survivor_in_another_state_is_accepted(tree: Declaration) -> None:
    """`--into` resolves tree-wide like every other handle: an idea may
    continue as a queued section, and the tool owns no judgment about where
    work continues."""
    seedling(tree, "a-seedling", READY)
    orchard(tree, "b-seedling")
    orchard(tree, "c-seedling")
    waits(tree, "c-seedling", ["a-seedling"])

    inarched(tree, into="b-seedling")
    assert read(tree.root / "orchard" / "c-seedling.md", tree)["after"] == [
        "b-seedling"
    ]


def test_a_survivor_that_is_the_item_itself_refuses_and_writes_nothing(
    tree: Declaration,
) -> None:
    """Merging an item into itself would delete it and leave every edge
    pointing at something gone. Computed before any write, so the item, the
    survivor and every referent are byte-identical."""
    source = seedling(tree, "a-seedling", READY)
    orchard(tree, "c-seedling")
    referent = waits(tree, "c-seedling", ["a-seedling"])
    before, held = source.read_bytes(), referent.read_bytes()

    with pytest.raises(Refusal, match="cannot continue as itself"):
        inarched(tree, into="a-seedling")
    assert source.read_bytes() == before
    assert referent.read_bytes() == held


def test_a_survivor_handle_naming_nothing_refuses_before_any_write(
    tree: Declaration,
) -> None:
    """`read.resolve`'s own refusal, reached through this arm: it runs beside
    the other two, all three before the checks and all three writing nothing."""
    source = seedling(tree, "a-seedling", READY)
    orchard(tree, "c-seedling")
    referent = waits(tree, "c-seedling", ["a-seedling"])
    before, held = source.read_bytes(), referent.read_bytes()

    with pytest.raises(Refusal):
        inarched(tree, into="no-such-seedling")
    assert source.read_bytes() == before
    assert referent.read_bytes() == held


def test_a_dissolving_verb_that_does_not_absorb_still_removes_the_edge(
    tree: Declaration,
) -> None:
    """**The 5-2 regression.** `compost` dissolves out of the same state and
    takes the edges naming the seedling *out*, because that is what the
    declaration says it does — one branch, not a new default."""
    said: list[str] = []
    seedling(tree, "a-seedling", READY)
    orchard(tree, "c-seedling")
    waits(tree, "c-seedling", ["a-seedling"])

    execute(
        tree, tree.transitions["compost"], name="a-seedling", announce=said.append
    )
    assert "after" not in read(tree.root / "orchard" / "c-seedling.md", tree)
    assert any('took "a-seedling" out of after' in one for one in said)
    assert not any("pointed" in one for one in said)


# --------------------------------------------------------------------------
# `check`: the run, stopped at the seam
# --------------------------------------------------------------------------
#
# The property is **non-divergence**, so every test here is a pair: what the
# run does, and what the check says about it, from the same tree. The one
# thing a check may leave behind is nothing at all — which is why each of the
# three arms is graded on a snapshot of the whole tree rather than on the item
# it was aimed at. `_create` is the trap: its reservation is a write partway
# through the arm, so a check that stopped where the other two stop would pass
# every assertion but the snapshot. See docs/method.md#the-check.


#: The run lock and the directory it sits in, which **every** mutating path
#: takes — a check included, by design: one that took a different path to
#: avoid the lock would be a second path. So it is the one thing a check may
#: leave behind, and the snapshot below says so by name rather than skipping
#: `local/` wholesale, which is also where a claim record would land.
LOCKING = (lock.LOCAL_DIR, f"{lock.LOCAL_DIR}/{lock.LOCK_NAME}")


def snapshot(tree: Declaration) -> dict[str, bytes]:
    """Every file under the tree, by relative path. Directories included as
    keys with no content, because making one is a write too."""
    found: dict[str, bytes] = {}
    for path in sorted(tree.root.rglob("*")):
        where = str(path.relative_to(tree.root))
        if where in LOCKING:
            continue
        found[where] = path.read_bytes() if path.is_file() else b""
    return found


def test_a_check_that_passes_says_what_it_would_do_and_writes_nothing(
    tree: Declaration,
) -> None:
    seedling(tree, "a-seedling", READY)
    before = snapshot(tree)

    said = execute(
        tree, tree.transitions["transplant"], name="a-seedling", check=True
    )
    assert isinstance(said, str)
    assert said.startswith("transplant would move ")
    assert "a-seedling.md" in said
    assert snapshot(tree) == before


def test_the_check_names_the_effects_the_run_goes_on_to_have(
    tree: Declaration,
) -> None:
    """Built from what the arms resolved, so the sentence and the head agree:
    the place and the number it names are the ones the run writes."""
    seedling(tree, "a-seedling", READY)
    said = execute(
        tree, tree.transitions["transplant"], name="a-seedling", check=True
    )
    path = execute(tree, tree.transitions["transplant"], name="a-seedling")

    head = read(path, tree)
    assert f"write position {head['position']}" in str(said)
    assert f"write number {head['number']}" in str(said)


def test_a_check_on_a_refused_item_gives_the_runs_own_refusal(
    tree: Declaration,
) -> None:
    """Byte-identical, because it is the same code raising it. A check that
    could disagree with its run would be the second home the flag exists to
    avoid."""
    seedling(tree, "a-seedling", '+++\ntitle = "A seedling"\n+++\n\nProse.\n')
    before = snapshot(tree)

    with pytest.raises(Refusal) as checked:
        execute(
            tree, tree.transitions["transplant"], name="a-seedling", check=True
        )
    assert snapshot(tree) == before

    with pytest.raises(Refusal) as ran:
        execute(tree, tree.transitions["transplant"], name="a-seedling")
    assert str(checked.value) == str(ran.value)


def test_a_check_on_a_creating_verb_leaves_no_reserved_file(
    tree: Declaration,
) -> None:
    """**The trap.** `_create` reserves the filename with `open("x")` partway
    through the arm, which is a write that happens before the head is placed —
    so this is the one arm where the seam is not the last line."""
    before = snapshot(tree)
    said = execute(
        tree,
        tree.transitions["sprout"],
        name="A seedling",
        body="Prose.",
        check=True,
    )
    assert "a-seedling.md" in str(said)
    assert snapshot(tree) == before
    assert not (tree.root / "greenhouse" / "a-seedling.md").exists()


def test_a_check_makes_no_directory_for_a_state_that_has_none(
    tmp_path: Path,
) -> None:
    """The earliest write either shape performs is the destination directory,
    and `exist_ok=True` hides it in every tree whose states are already
    there. This one's are not."""
    for name in FIXTURE_FILES:
        (tmp_path / name).write_text((FIXTURES / name).read_text())
    declaration = load(tmp_path / "plan.toml")
    (tmp_path / declaration.states["greenhouse"].path).mkdir(parents=True)
    seedling(declaration, "a-seedling", READY)

    execute(
        declaration,
        declaration.transitions["transplant"],
        name="a-seedling",
        check=True,
    )
    assert not (tmp_path / declaration.states["orchard"].path).exists()


def test_a_check_reaches_the_head_grading_a_run_would_refuse_on(
    tree: Declaration,
) -> None:
    """The last refusal a moving run can raise is `_place`'s, over the head it
    is about to write — so the check stops *inside* `_place` rather than short
    of it. A stray key survives every earlier arm and is caught there."""
    seedling(
        tree,
        "a-seedling",
        READY.replace('tag = "spring"', 'tag = "spring"\nnotebook = "n.md"\nsizee = "M"'),
    )
    with pytest.raises(Refusal, match='"sizee" is not a declared key'):
        execute(
            tree, tree.transitions["transplant"], name="a-seedling", check=True
        )


def test_a_check_on_a_dissolving_verb_leaves_the_item_and_its_edges(
    tree: Declaration,
) -> None:
    """The third arm, and the one with the most to undo if it wrote anything:
    the item, the archive entry and every referent's edge to it."""
    seedling(tree, "a-seedling", READY)
    orchard(tree, "c-seedling")
    waits(tree, "c-seedling", ["a-seedling"])
    before = snapshot(tree)

    said = execute(
        tree, tree.transitions["compost"], name="a-seedling", check=True
    )
    assert "would take " in str(said) and "away" in str(said)
    assert "clear the edge to it in" in str(said)
    assert "c-seedling.md" in str(said)
    assert snapshot(tree) == before


def test_a_check_on_the_archiving_dissolve_names_the_entry_it_would_file(
    tree: Declaration,
) -> None:
    """The heading is spelled once, in `_archiving`, and both reporters quote
    it — the notice a run leaves and the sentence a check hands back."""
    path = orchard(tree, "a-seedling")
    assert read(path, tree)["number"] == 2
    before = snapshot(tree)

    said = execute(
        tree,
        tree.transitions["fell"],
        name="a-seedling",
        asked={"record": "Because."},
        check=True,
    )
    assert "file `## 2. A seedling` in" in str(said)
    assert snapshot(tree) == before


def test_a_check_says_nothing_about_a_claim_a_verb_would_not_take(
    tree: Declaration, session: Identity
) -> None:
    """A clause's absence is meaningful: it is missing because `_claiming`
    handed nothing back, not because a condition in the sentence builder
    skipped it. `bench` moves onto the claimed bench and claims nothing."""
    seedling(tree, "a-seedling", READY)
    said = str(execute(tree, tree.transitions["bench"], name="a-seedling", check=True))
    assert "claim" not in said

    taken = str(
        execute(tree, tree.transitions["pot-up"], name="B seedling",
                body="Prose.", check=True)
    )
    assert "take the claim" in taken
    assert not claim.path(tree.root, "b-seedling").exists()
