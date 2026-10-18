"""The refusal table for ``plan.toml``.

Most of these are pure over dicts: no ``tmp_path``, no cwd, no filesystem.
That is the whole reason `shape_errors` is split from `load` —
the old tool's ~40 refusal tests ran instantly for the same reason.

The operator contract — rc 2, one ``ERROR:`` line on stderr, no traceback —
is pinned below. "A refusal emits no JSON" was deferred here until ``--json``
existed; it now lives in ``tests/test_cli.py``, beside the flag it is about.
"""

from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import tomllib
from importlib.metadata import version
from pathlib import Path

import pytest

from conftest import DERIVABLE_KEYS

from fileplan import depends, subphase
from fileplan.cli import main
from fileplan.declaration import (
    CAPABILITIES,
    CAPABILITY_KEYS,
    CLAIM_KEYS,
    COMMAND_KEYS,
    DERIVED_KEYS,
    FIRST_NUMBER,
    IDENTITY,
    ARCHIVING_HELP,
    DISSOLVING,
    EDIT_WRITES,
    KIND_HELP,
    KINDS,
    STAYING,
    PLAN_TOML_ENV,
    OPENED_FOR,
    STALE_KEYS,
    Declaration,
    Refusal,
    State,
    load,
    named,
    pointer_errors,
    shape_errors,
)

from conftest import FIXTURE_FILES

REPO = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"

#: Names that exist only in the suite's vocabulary. See the control tests.
CONTROLS = ("greenhouse", "sprout", "cultivar")


def well_formed() -> dict:
    """A minimal document that must produce no errors."""
    return copy.deepcopy(
        {
            "states": {
                "greenhouse": {"path": "greenhouse", "doc": "method.md#greenhouse"},
                "orchard": {
                    "path": "orchard",
                    "doc": "method.md#orchard",
                    "capabilities": ["queued"],
                    "sort": "position",
                },
            },
            "keys": {
                "cultivar": {
                    "doc": "method.md#cultivar",
                    "help": "Which cultivar.",
                    "values": ["heirloom", "hybrid"],
                },
                "rootstock": {"doc": "method.md#rootstock"},
            },
            "transitions": {
                "sprout": {
                    "kind": "create",
                    "doc": "method.md#sprout",
                    "help": "Start a seedling.",
                    "to": "greenhouse",
                    "sets": ["cultivar"],
                },
                "transplant": {
                    "kind": "move",
                    "doc": "method.md#transplant",
                    "help": "Move it out.",
                    "from": "greenhouse",
                    "to": "orchard",
                    "requires": ["cultivar"],
                    "refuses": {"cultivar": ["hybrid"]},
                    "sets": ["rootstock"],
                },
            },
        }
    )


# --------------------------------------------------------------------------
# Shape
# --------------------------------------------------------------------------


def test_a_well_formed_document_has_no_errors() -> None:
    assert shape_errors(well_formed()) == []


def test_unknown_top_level_table_refuses_by_name() -> None:
    document = well_formed()
    document["policy"] = "docs/policy.md"
    assert (
        "policy is not a plan.toml table "
        "(known tables: states, keys, transitions, identity, fileplan)"
    ) in shape_errors(document)


@pytest.mark.parametrize(
    ("table", "name", "noun"),
    [
        ("states", "greenhouse", "state"),
        ("keys", "cultivar", "key"),
        ("transitions", "sprout", "transition"),
    ],
)
def test_unknown_field_refuses_by_name(table: str, name: str, noun: str) -> None:
    document = well_formed()
    document[table][name]["colour"] = "green"
    assert f"{table}.{name}.colour is not a {noun} field" in shape_errors(document)


def test_a_state_declaring_an_exit_check_refuses_by_name() -> None:
    """13-1 withdrew the field, so the same arm that catches a typo catches a
    declaration written against the old vocabulary. It went because a state
    with a *second* way out meaning the opposite of the first — this repo's
    `archive-plan` against its `decline` — could never carry one rule, so the
    completion conditions live on the completing verb's own `requires` and
    `refuses` and grade one way out at a time."""
    document = well_formed()
    document["states"]["greenhouse"]["exit"] = {"requires": ["rootstock"]}
    assert "states.greenhouse.exit is not a state field" in shape_errors(document)


def test_a_key_declaring_a_companion_refuses_by_name() -> None:
    """Its neighbour, withdrawn in the same sub-phase and for its own reason:
    the whole of `companion` was one load-time refusal of a `drops` naming the
    key, for the one key that declared it, and this repo wrote that rule a
    second time as a test over its own `plan.toml`
    (`test_no_transition_this_repo_declares_drops_the_draft`)."""
    document = well_formed()
    document["keys"]["rootstock"]["companion"] = True
    assert "keys.rootstock.companion is not a key field" in shape_errors(document)


def test_a_state_with_no_path_is_at_its_name_under_the_root(tmp_path: Path) -> None:
    """32-2: `path` defaults to the state's name, under `[fileplan].root`
    where one is given. A state writing its own `path` is not moved by the
    root."""
    document = well_formed()
    del document["states"]["greenhouse"]["path"]
    assert shape_errors(document) == []
    source = tmp_path / "plan.toml"
    source.write_text(
        '[fileplan]\nroot = "docs"\n\n[states.greenhouse]\n\n'
        '[states.orchard]\npath = "trees"\n'
    )
    states = load(source).states
    assert states["greenhouse"].path == "docs/greenhouse"
    assert states["orchard"].path == "trees"
    source.write_text("[states.greenhouse]\n")
    assert load(source).states["greenhouse"].path == "greenhouse"


@pytest.mark.parametrize(
    ("kind", "fields", "said"),
    [
        ("create", {"to": "greenhouse"}, "Create an item in greenhouse."),
        ("move", {"from": "greenhouse", "to": "orchard"}, "Move an item from greenhouse to orchard."),
        ("reorder", {"from": "orchard"}, "Move an item to another place in orchard's order."),
        ("edit", {"from": "orchard", "sets": ["cultivar"]}, "Edit an item in orchard where it stands."),
        ("close", {"from": "greenhouse"}, "Close an item in greenhouse out, and take its file away."),
    ],
)
def test_a_transition_with_no_help_says_its_kind(
    tmp_path: Path, kind: str, fields: dict, said: str
) -> None:
    """32-2: `help` defaults from the kind, said with the states it names,
    so a repo writes one only to say something better."""
    document = well_formed()
    document["transitions"] = {"graft-on": {"kind": kind, **fields}}
    assert shape_errors(document) == []
    lines = [
        '[states.greenhouse]\n',
        '[states.orchard]\ncapabilities = ["queued"]\n',
        "[keys.cultivar]\n",
        f'[transitions.graft-on]\nkind = "{kind}"\n'
        + "".join(f"{k} = {json.dumps(v)}\n" for k, v in fields.items()),
    ]
    (tmp_path / "plan.toml").write_text("\n".join(lines))
    assert load(tmp_path / "plan.toml").transitions["graft-on"].help == said


@pytest.mark.parametrize("field", ["to"])
def test_transition_missing_a_required_field_refuses(field: str) -> None:
    document = well_formed()
    del document["transitions"]["sprout"][field]
    assert f"transitions.sprout has no {field}" in shape_errors(document)


def test_a_key_and_a_transition_with_no_doc_load(tmp_path: Path) -> None:
    """32-1: `doc` is optional everywhere, as it already was on a state. A
    declaration naming no document at all loads with no document beside
    it, and the loaded entries carry `None`."""
    document = well_formed()
    for table in ("states", "keys", "transitions"):
        for entry in document[table].values():
            entry.pop("doc", None)
    assert shape_errors(document) == []
    assert pointer_errors(document, tmp_path) == []
    source = tmp_path / "plan.toml"
    source.write_text(
        '[states.greenhouse]\npath = "greenhouse"\n\n'
        '[keys.cultivar]\nhelp = "Which cultivar."\n\n'
        '[transitions.sprout]\nkind = "create"\nhelp = "Start one."\n'
        'to = "greenhouse"\nsets = ["cultivar"]\n'
    )
    declaration = load(source)
    assert declaration.keys["cultivar"].doc is None
    assert declaration.transitions["sprout"].doc is None


def test_to_naming_an_undeclared_state_refuses() -> None:
    document = well_formed()
    document["transitions"]["sprout"]["to"] = "cold-frame"
    assert 'transitions.sprout.to names undeclared state "cold-frame"' in shape_errors(
        document
    )


def test_from_naming_an_undeclared_state_refuses() -> None:
    document = well_formed()
    document["transitions"]["transplant"]["from"] = "cold-frame"
    assert (
        'transitions.transplant.from names undeclared state "cold-frame"'
        in shape_errors(document)
    )


# --------------------------------------------------------------------------
# Kinds: what a transition is, said once. See docs/method.md#kinds
# --------------------------------------------------------------------------


def test_a_transition_with_no_from_is_a_create() -> None:
    """A create has no item to start from, so it names a `to` and no
    `from`."""
    document = well_formed()
    transplant = document["transitions"]["transplant"]
    transplant["kind"] = "create"
    del transplant["from"]
    # The three fields that read the item it no longer has go with it.
    for field in ("requires", "refuses", "drops"):
        transplant.pop(field, None)
    assert shape_errors(document) == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("requires", ["cultivar"]),
        ("refuses", {"cultivar": ["hybrid"]}),
        ("drops", ["cultivar"]),
        ("marks", "taken"),
        ("files", {"state": "orchard", "item": "cultivar", "name": "rootstock"}),
        ("archives", True),
    ],
)
def test_a_create_cannot_grade_or_edit_an_item(field: str, value: object) -> None:
    """One table, not a rule per field: a create has no item to read, so
    the fields that read one, or that write onto one, are not among the ones
    it takes."""
    document = well_formed()
    document["transitions"]["sprout"][field] = value
    assert (
        f"transitions.sprout.{field} is set, and a create does not take it "
        "(a create takes claims, sets, to)" in shape_errors(document)
    )


@pytest.mark.parametrize(
    ("fields", "kind"),
    [
        ({"to": "greenhouse"}, "create"),
        ({"from": "greenhouse", "to": "orchard"}, "move"),
        ({"from": "orchard", "to": "orchard"}, "reorder"),
        ({"from": "orchard", "to": "orchard", "sets": ["cultivar"]}, "edit"),
        ({"from": "orchard", "to": "orchard", "retitles": True}, "rename"),
        ({"from": "orchard", "dissolves": True}, "close"),
        ({"from": "orchard", "dissolves": True, "absorbs": True}, "merge"),
        ({"from": "orchard", "to": "orchard", "mints": True}, "add-bullet"),
        ({"from": "orchard", "to": "orchard", "marks": "done"}, "mark-bullet"),
    ],
)
def test_a_transition_with_no_kind_refuses_naming_the_kind_its_fields_spell(
    fields: dict, kind: str
) -> None:
    """30-1: `kind` is required, and a plan.toml written before it refuses
    with the line to write. The kind is read off the fields that spelled it,
    so the refusal is the migration."""
    document = well_formed()
    document["transitions"]["graft-on"] = {
        "doc": "method.md#graft",
        "help": "Graft one on.",
        **fields,
    }
    article = "an" if kind[0] in "aeiou" else "a"
    assert (
        f"transitions.graft-on has no kind. Its fields spell {article} {kind}, "
        f'so write kind = "{kind}"'
    ) in shape_errors(document)


@pytest.mark.parametrize(
    ("field", "kind"),
    [
        ("mints", "add-bullet"),
        ("retitles", "rename"),
        ("dissolves", "close"),
        ("absorbs", "merge"),
    ],
)
def test_a_field_that_spelled_a_kind_refuses_naming_the_kind(
    field: str, kind: str
) -> None:
    """The four fields whose only job was to say which kind a verb is are
    gone. Each refuses by name, and says the line that replaces it."""
    document = well_formed()
    graft = {"doc": "method.md#graft", "help": "Graft.", "from": "orchard"}
    graft[field] = True
    if field == "absorbs":
        graft["dissolves"] = True
    document["transitions"]["graft-on"] = graft
    assert (
        f"transitions.graft-on.{field} is no longer a transition field, "
        f'because the kind says it. Write kind = "{kind}", and drop the '
        f"{field}"
    ) in shape_errors(document)


@pytest.mark.parametrize("field", ["mints", "dissolves", "absorbs", "retitles", "writes"])
def test_a_transition_carries_no_field_a_kind_replaced(field: str) -> None:
    """30-2's done line: what the four fields said is the kind now, and the
    placement gate reads the kind too. With no attribute left to read, a
    branch in `cli.py` or `transition.py` that still asked would fail the
    first time it ran, rather than answering from a second writer."""
    assert not hasattr(load(FIXTURES / "plan.toml").transitions["espalier"], field)


def test_an_unknown_kind_refuses_naming_the_kinds() -> None:
    document = well_formed()
    document["transitions"]["transplant"]["kind"] = "transplant"
    assert (
        "transitions.transplant.kind is 'transplant', which is not a kind "
        "(kinds: create, move, reorder, edit, rename, close, merge, "
        "add-bullet, mark-bullet)"
    ) in shape_errors(document)


@pytest.mark.parametrize(
    ("kind", "says"),
    [
        ("edit", "an edit stays in its from state"),
        ("close", "a close takes the item's file away, so it lands nowhere"),
    ],
)
def test_a_to_on_a_kind_that_does_not_move_refuses(kind: str, says: str) -> None:
    """One spelling: a kind that stays declares only its `from`, and one that
    takes the item away declares no destination at all. A `to` beside either
    is loud rather than ignored."""
    document = well_formed()
    document["transitions"]["graft-on"] = {
        "kind": kind,
        "doc": "method.md#graft",
        "help": "Graft.",
        "from": "orchard",
        "to": "orchard",
    }
    errors = shape_errors(document)
    assert f"transitions.graft-on.to is set, and {says}. Drop the to" in errors


def test_a_kind_that_stays_lands_where_it_started() -> None:
    """The loader fills a staying kind's `to` from its `from`, once, so
    everything downstream reads where the item is when the run is over."""
    declaration = load(FIXTURES / "plan.toml")
    tend = declaration.transitions["tend"]
    assert (tend.kind, tend.source, tend.to) == (
        "edit",
        "potting-bench",
        "potting-bench",
    )
    fell = declaration.transitions["fell"]
    assert (fell.kind, fell.to) == ("close", None)


def test_a_move_to_its_own_state_refuses_naming_the_kinds_that_stay() -> None:
    document = well_formed()
    document["transitions"]["transplant"]["to"] = "greenhouse"
    assert (
        'transitions.transplant is a move from "greenhouse" to itself. A move '
        'leaves its state. Write kind = "edit", or kind = "reorder" for one '
        "that only changes the item's place"
    ) in shape_errors(document)


def test_a_reorder_in_a_state_with_no_order_refuses_by_name() -> None:
    document = well_formed()
    document["transitions"]["respace"] = {
        "kind": "reorder",
        "doc": "method.md#respace",
        "help": "Respace.",
        "from": "greenhouse",
    }
    assert (
        'transitions.respace is a reorder, and states.greenhouse does not name '
        '"queued" in its capabilities, so its items have no order to change. '
        'Name "queued" in states.greenhouse.capabilities, or give '
        "transitions.respace another kind"
    ) in shape_errors(document)


def test_an_edit_that_writes_nothing_refuses_by_name() -> None:
    document = well_formed()
    document["transitions"]["graft-on"] = {
        "kind": "edit",
        "doc": "method.md#graft",
        "help": "Graft.",
        "from": "orchard",
    }
    assert (
        "transitions.graft-on is an edit, and it writes nothing: it names no "
        "sets, no drops and no claims. Name what it writes, or drop the "
        "transition"
    ) in shape_errors(document)


def test_a_mark_bullet_with_no_word_refuses_by_name() -> None:
    document = well_formed()
    document["transitions"]["ripen"] = {
        "kind": "mark-bullet",
        "doc": "method.md#ripen",
        "help": "Ripen.",
        "from": "orchard",
    }
    assert "transitions.ripen has no marks" in shape_errors(document)


def test_without_every_kind_the_rules_across_tables_stay_quiet() -> None:
    """One complaint per defect. A verb with no kind does not say where it
    writes, so a bulleted state would otherwise be refused for having no
    verb writing into it, which is the same defect said twice."""
    document = well_formed()
    document["states"]["orchard"].update(
        {
            "capabilities": ["queued", "bulleted"],
            "sub-phases": "Steps",
            "sub-phase-pending": "**pending — more.**",
            "sub-phase-name": "s{ordinal}",
        }
    )
    document["transitions"]["espalier"] = {
        "doc": "method.md#espalier",
        "help": "Train.",
        "from": "orchard",
        "to": "orchard",
        "mints": True,
    }
    errors = shape_errors(document)
    assert not [error for error in errors if error.startswith("states.orchard")]
    assert any(error.startswith("transitions.espalier has no kind") for error in errors)


@pytest.mark.parametrize(
    "source",
    [
        REPO / "plan.toml",
        REPO / "src" / "fileplan" / "starter" / "plan.toml",
        FIXTURES / "plan.toml",
    ],
    ids=["this-repo", "starter", "fixture"],
)
def test_every_shipped_declaration_gives_every_transition_a_kind(
    source: Path,
) -> None:
    """30-1's done line: the three declarations this repo keeps all load, and
    every transition in each says its kind."""
    document = tomllib.loads(source.read_text())
    assert all(
        entry["kind"] in KINDS for entry in document["transitions"].values()
    )
    assert shape_errors(document) == []


@pytest.mark.parametrize("field", ["requires", "sets", "drops"])
def test_a_key_reference_to_an_intrinsic_key_refuses_by_name(field: str) -> None:
    """`sets = ["title"]` is not a typo — it is a retitle, which is a real
    transition whose rule for inbound `after` edges is section 3's. Reading as
    "undeclared key" would send someone to write `[keys.title]`, which refuses
    too, one message later."""
    document = well_formed()
    document["transitions"]["transplant"][field] = ["title"]
    assert (
        f'transitions.transplant.{field} names "title", which is intrinsic to '
        "every item rather than a declared key" in shape_errors(document)
    )


def test_declaring_an_intrinsic_key_refuses_by_name() -> None:
    document = well_formed()
    document["keys"]["title"] = {"doc": "method.md#cultivar"}
    assert [error for error in shape_errors(document) if "title" in error] == [
        'keys.title redeclares "title", which every item carries '
        "intrinsically. An item is a head, a body, a location and a name, and "
        "the tool already knows all four. Drop keys.title"
    ]


@pytest.mark.parametrize("name", ["slug", "state", "path"])
def test_declaring_a_key_a_listing_reads_off_the_tree_refuses_by_name(
    name: str,
) -> None:
    """`state` is the load-bearing one — location *is* state, and a `state`
    key in a head would be a second answer to a question the tree already
    answers, with the head's copy the one that lies. `slug` and `path` go with
    it because a row is a mapping and a silent overwrite is worse than a
    refusal. (1-4's rule, in 1-1's validator: this is where a redeclaration
    has to be refused.)"""
    document = well_formed()
    document["keys"][name] = {"doc": "method.md#cultivar"}
    assert [error for error in shape_errors(document) if f"keys.{name} " in error] == [
        f'keys.{name} redeclares "{name}", which every listing reads off the '
        "tree (reserved: slug, state, path). An item's state is the directory "
        "it sits in, and a key beside the tree can only disagree with it. "
        f"Drop keys.{name}"
    ]


def test_declaring_the_sub_phase_count_as_a_key_refuses_by_name() -> None:
    """The count is derived from the body, so a key beside it is a second
    answer that can drift out of step with the bullets — which is the whole
    reason sub-phases are counted rather than marked."""
    document = well_formed()
    document["keys"][subphase.NAME] = {"doc": "method.md#cultivar"}
    assert [
        error for error in shape_errors(document) if f"keys.{subphase.NAME} " in error
    ] == [
        f'keys.{subphase.NAME} redeclares "{subphase.NAME}", which every '
        "listing counts off the item's own body. How many sub-phases a section "
        "carries is counted from the bullets, and a key beside them can only "
        f"drift. Drop keys.{subphase.NAME}"
    ]


@pytest.mark.parametrize("field", ["requires", "sets", "drops", "refuses"])
def test_a_transition_naming_the_sub_phase_count_refuses(field: str) -> None:
    """Read, not written: there is nothing here for a verb to set."""
    document = well_formed()
    named = (
        {subphase.NAME: ["x"]} if field == "refuses" else [subphase.NAME]
    )
    document["transitions"]["transplant"][field] = named
    assert any(
        f'transitions.transplant.{field} names "{subphase.NAME}"' in error
        for error in shape_errors(document)
    )


def test_a_declared_key_called_sub_phases_left_refuses_as_a_redeclaration() -> (
    None
):
    """The rule `sub-phases` and `next-sub-phase` already keep, over the field
    that says how much of a section is left. The message names its own source
    — the bullets carrying no mark — because that sentence is what tells an
    operator where to go and look, which is why these are not folded into one.
    A key beside it is a counter somebody has to remember to decrement, and
    the whole reason completion sits on the bullet is that it cannot be."""
    document = well_formed()
    document["keys"][subphase.LEFT] = {"doc": "method.md#cultivar"}
    assert [
        error for error in shape_errors(document) if f"keys.{subphase.LEFT} " in error
    ] == [
        f'keys.{subphase.LEFT} redeclares "{subphase.LEFT}", which every '
        "listing counts off the bullets carrying no mark. A key beside the "
        "bullets is a counter somebody has to remember to decrement. Drop "
        f"keys.{subphase.LEFT}"
    ]


@pytest.mark.parametrize("field", ["requires", "sets", "drops", "refuses"])
def test_a_transition_naming_the_count_left_refuses(field: str) -> None:
    """Read, not written, and it reaches this by being in
    `subphase.DERIVED` — one arm over all three derived sets rather than a
    third message spelled out."""
    document = well_formed()
    named = {subphase.LEFT: ["x"]} if field == "refuses" else [subphase.LEFT]
    document["transitions"]["transplant"][field] = named
    assert any(
        f'transitions.transplant.{field} names "{subphase.LEFT}"' in error
        for error in shape_errors(document)
    )


def test_a_state_may_declare_no_sub_phase_heading() -> None:
    """Absence is the ordinary case and grades nothing. A state that counts no
    sub-phases is not a broken one."""
    document = well_formed()
    document["states"]["greenhouse"].pop(subphase.NAME, None)
    assert [error for error in shape_errors(document) if "sub-phase" in error] == []


def test_an_empty_sub_phase_heading_refuses_rather_than_opting_out() -> None:
    """Present and empty is a defect, not an opt-out: a heading of `""` would
    match no line and every section in the state would silently count zero —
    the same silent miscount the strict bullet form exists to prevent. Leaving
    the field out is how a state counts none."""
    document = well_formed()
    document["states"]["orchard"][subphase.NAME] = "   "
    assert [error for error in shape_errors(document) if "sub-phase" in error] == [
        f"states.orchard.{subphase.NAME} is empty, so no heading would ever "
        "match. Every section here would count zero sub-phases. Leave the "
        "field out to count none"
    ]


def with_cursor(document: dict) -> dict:
    """`well_formed()` plus a counted state and a declared cursor over it."""
    document["states"]["orchard"][subphase.NAME] = "Steps"
    document["states"]["orchard"][subphase.CURSOR] = "graft"
    document["states"]["orchard"][subphase.STATUS] = "graft-status"
    document["keys"]["graft"] = {"doc": "method.md#cultivar"}
    document["keys"]["graft-status"] = {
        "doc": "method.md#cultivar",
        "values": ["open", "done"],
    }
    return document


def test_a_cursor_naming_an_undeclared_key_refuses_by_name() -> None:
    """The typo class ``pointer_errors`` catches for documents, applied to
    keys: a state pointing at a key nobody wrote is a defect, not a cursor."""
    document = with_cursor(well_formed())
    document["states"]["orchard"][subphase.CURSOR] = "grafft"
    assert any(
        f'states.orchard.{subphase.CURSOR} names undeclared key "grafft"' in error
        for error in shape_errors(document)
    )


def test_a_status_key_with_no_closed_set_refuses_by_name() -> None:
    """A status that can hold anything makes a typo one more status. The
    closed set is the *shape* the tool needs; the words stay the workflow's."""
    document = with_cursor(well_formed())
    document["keys"]["graft-status"].pop("values")
    assert [
        error for error in shape_errors(document) if subphase.STATUS in error
    ] == [
        f'states.orchard.{subphase.STATUS} names "graft-status", which '
        "declares no values. A status that can hold anything makes a typo one "
        "more status. Declare keys.graft-status.values"
    ]


def test_a_cursor_on_a_state_that_counts_nothing_refuses() -> None:
    """A cursor with nothing to count against cannot be graded."""
    document = with_cursor(well_formed())
    document["states"]["orchard"].pop(subphase.NAME)
    assert any(
        "declares no sub-phases heading. A cursor with nothing to count "
        "against cannot be graded" in error
        for error in shape_errors(document)
    )


def test_a_cursor_naming_a_key_the_tool_owns_refuses() -> None:
    """Reuses the arms a transition's `sets` is graded by, rather than a
    second set of messages that could drift from them."""
    document = with_cursor(well_formed())
    document["states"]["orchard"][subphase.CURSOR] = "position"
    assert any(
        '"position"' in error and subphase.CURSOR in error
        for error in shape_errors(document)
    )


def test_a_state_may_declare_sub_phases_with_no_cursor() -> None:
    """Counting and pointing are separate opt-ins. A state that counts but has
    no verb to advance a cursor yet is not a broken one — which is exactly
    what this repo's own plan.toml is until 4-6."""
    document = with_cursor(well_formed())
    document["states"]["orchard"].pop(subphase.CURSOR)
    document["states"]["orchard"].pop(subphase.STATUS)
    assert [error for error in shape_errors(document) if "sub-phase" in error] == []


def test_a_sub_phase_heading_that_is_not_a_string_refuses() -> None:
    document = well_formed()
    document["states"]["orchard"][subphase.NAME] = 3
    assert f"states.orchard.{subphase.NAME} must be a string" in shape_errors(document)


@pytest.mark.parametrize("field", ["requires", "sets", "drops"])
def test_key_reference_to_an_undeclared_key_refuses(field: str) -> None:
    document = well_formed()
    document["transitions"]["sprout"][field] = ["provenance"]
    assert (
        f'transitions.sprout.{field} names undeclared key "provenance"'
        in shape_errors(document)
    )


def test_refuses_naming_an_undeclared_key_refuses() -> None:
    document = well_formed()
    document["transitions"]["sprout"]["refuses"] = {"provenance": ["unknown"]}
    assert 'transitions.sprout.refuses names undeclared key "provenance"' in shape_errors(
        document
    )


def test_refuses_naming_a_value_outside_the_keys_values_refuses() -> None:
    document = well_formed()
    document["transitions"]["transplant"]["refuses"] = {"cultivar": ["too-big"]}
    assert (
        'transitions.transplant.refuses.cultivar names "too-big", '
        "which is not a declared value of keys.cultivar" in shape_errors(document)
    )


def test_refuses_against_a_free_text_key_is_allowed() -> None:
    document = well_formed()
    document["transitions"]["transplant"]["refuses"] = {"rootstock": ["anything"]}
    assert shape_errors(document) == []


def test_refuses_on_presence_loads_beside_a_value_list(tmp_path: Path) -> None:
    """`key = true` refuses any value at all, and sits in the same table as a
    value list. The two are kept apart on the transition, so nothing reading
    `refuses` meets a boolean where it expected values."""
    for name in FIXTURE_FILES:
        (tmp_path / name).write_text((FIXTURES / name).read_text())
    plan = (tmp_path / "plan.toml").read_text().replace(
        'refuses  = { cultivar = ["hybrid"] }',
        'refuses  = { cultivar = ["hybrid"], rootstock = true }',
    )
    (tmp_path / "plan.toml").write_text(plan)
    transplant = load(tmp_path / "plan.toml").transitions["transplant"]
    assert transplant.refuses == {"cultivar": ("hybrid",)}
    assert transplant.refuses_any == ("rootstock",)


def test_refuses_false_refuses_by_name() -> None:
    """`false` would read as "refuse nothing", which is saying nothing, so it
    refuses and says the two spellings there are."""
    document = well_formed()
    document["transitions"]["transplant"]["refuses"] = {"rootstock": False}
    assert (
        "transitions.transplant.refuses.rootstock is false, which refuses "
        "nothing. Write true, or a list of values" in shape_errors(document)
    )


def test_refuses_on_presence_of_an_undeclared_key_refuses() -> None:
    document = well_formed()
    document["transitions"]["transplant"]["refuses"] = {"provenance": True}
    assert (
        'transitions.transplant.refuses names undeclared key "provenance"'
        in shape_errors(document)
    )


def test_declaring_a_capabilitys_key_refuses_by_name() -> None:
    """`position` is not the workflow's vocabulary — it is what the `queued`
    capability gives an item in a state that opts in, written on the way in
    and dropped on the way out. Declaring it would be a second spelling of a
    rule the tool already keeps, and the two can disagree."""
    document = well_formed()
    document["keys"]["position"] = {"doc": "method.md#cultivar"}
    assert [
        error for error in shape_errors(document) if "keys.position" in error
    ] == [
        'keys.position redeclares "position", which the queued capability '
        "gives an item in a state that opts into it. The queued capability "
        "writes the key on the way in and drops it on the way out. Drop "
        "keys.position"
    ]


@pytest.mark.parametrize("field", ["requires", "sets", "drops"])
def test_a_transition_naming_a_capabilitys_key_refuses_by_name(field: str) -> None:
    document = well_formed()
    document["transitions"]["transplant"][field] = ["position"]
    assert (
        f'transitions.transplant.{field} names "position", which the queued '
        "capability writes on entry and drops on exit by itself. Naming the "
        "key here would be a second spelling that can disagree with the "
        f'capability. Drop "position" from transitions.transplant.{field}'
        in shape_errors(document)
    )


def test_refuses_naming_a_capabilitys_key_refuses_by_name() -> None:
    document = well_formed()
    document["transitions"]["transplant"]["refuses"] = {"position": ["100"]}
    assert any(
        "which the queued capability writes on entry" in error
        for error in shape_errors(document)
    )


@pytest.mark.parametrize("name", CLAIM_KEYS)
def test_declaring_a_key_the_claim_reads_off_the_tree_refuses_by_name(
    name: str,
) -> None:
    """The names 2-4 reserves. A claim is not a key in a head — it is a record
    under `local/claims/` — so a declared key of any of those names would be a second
    answer to a question the record already answers. Reserved **without**
    `well_formed()` claiming anything, like `position`: a plan.toml that grows
    a claimed state later must not break a key that was legal before it."""
    document = well_formed()
    assert not any(
        "claimed" in state.get("capabilities", [])
        for state in document["states"].values()
    )
    document["keys"][name] = {"doc": "method.md#cultivar"}
    assert [error for error in shape_errors(document) if f"keys.{name} " in error] == [
        f'keys.{name} redeclares "{name}", which the claimed capability reads '
        "off the tree (read: claimed-by, claim-status, claim-holder). Who "
        "holds an item "
        "lives in local/claims/ rather than in a head. Drop keys."
        f"{name}"
    ]


@pytest.mark.parametrize("field", ["requires", "sets", "drops"])
def test_a_transition_naming_a_claims_field_refuses_by_name(field: str) -> None:
    """Its own words, and they are the reason: `position` is *written* by the
    capability, so a transition naming it would be a second spelling of that;
    a claim's fields are **read**, so there is nothing here to set at all."""
    document = well_formed()
    document["transitions"]["transplant"][field] = ["claimed-by"]
    assert (
        f'transitions.transplant.{field} names "claimed-by", which the claimed '
        "capability reads off local/claims/ rather than out of a head. A "
        "claim's fields are read rather than written, so there is nothing "
        f'here to set. Drop "claimed-by" from transitions.transplant.{field}'
        in shape_errors(document)
    )


def test_refuses_naming_a_claims_field_refuses_by_name() -> None:
    document = well_formed()
    document["transitions"]["transplant"]["refuses"] = {"claim-status": ["dead"]}
    assert any(
        "which the claimed capability reads off local/claims/" in error
        for error in shape_errors(document)
    )


def test_a_state_knows_which_capabilities_it_has() -> None:
    declaration = load(FIXTURES / "plan.toml")
    assert declaration.states["orchard"].has("queued")
    assert not declaration.states["greenhouse"].has("queued")
    assert declaration.has("queued")


def test_a_capabilitys_key_is_carried_but_not_declared() -> None:
    """`carried` is what an item may hold; `keys` is what `plan.toml`
    declares. A capability's key is in the first and never the second."""
    declaration = load(FIXTURES / "plan.toml")
    assert "position" in declaration.carried
    assert "position" not in declaration.keys
    assert declaration.states["orchard"].capability_keys == ("position", "number")
    assert declaration.states["greenhouse"].capability_keys == ()


def test_the_claimed_capability_is_implemented_and_gives_no_head_key() -> None:
    """The second capability. Its state is a file under `local/claims/` rather
    than a line in a head, so it appears in `CAPABILITIES` and nowhere in
    `CAPABILITY_KEYS` — and an item in a claimed state carries no key by being
    there."""
    assert CAPABILITIES == ("queued", "claimed", "numbered", "bulleted")
    assert "claimed" not in CAPABILITY_KEYS
    declaration = load(FIXTURES / "plan.toml")
    bench = declaration.states["potting-bench"]
    assert bench.has("claimed") and bench.capability_keys == ()
    assert declaration.has("claimed")


def test_the_claims_fields_are_carried_only_where_a_state_claims() -> None:
    """`carried` is what `--has` and `--lacks` reach. A declaration that
    claims has both names; one with the capability dropped carries neither —
    the fields are given by the capability, exactly as `position` is.

    The negative half is graded on a document rather than on this repo's own
    `plan.toml`, which claims from 4-4 onwards. That is the 1-1 lesson: the
    suite must not depend on the host repo's vocabulary in either direction.
    """
    declaration = load(FIXTURES / "plan.toml")
    assert declaration.has("claimed")
    for name in CLAIM_KEYS:
        assert name in declaration.carried
        assert name not in declaration.keys

    plain = Declaration(
        source=FIXTURES / "plan.toml",
        root=FIXTURES,
        states={"greenhouse": State(name="greenhouse", path="greenhouse")},
        keys={},
        transitions={},
    )
    assert not plain.has("claimed")
    for name in CLAIM_KEYS:
        assert name not in plain.carried


def claiming(document: dict, into: str = "orchard") -> dict:
    """``document`` with ``into`` claimed, and the verb that claims into it.

    Both halves, always: from 4-4 a claimed state that no transition claims
    into refuses on its own, so a helper that wrote only the capability would
    be building a declaration the tool rightly rejects.
    """
    document["states"][into]["capabilities"] = ["claimed"]
    document["transitions"]["transplant"]["claims"] = True
    return document


def test_a_claimed_state_with_no_identity_refuses_by_name() -> None:
    """2-1's deferred question, answered. A claim records the session that
    holds it, so a state that could never say whose a claim is cannot take
    one — and the operator hears it when the declaration is read rather than
    the first time a transition into it runs."""
    document = claiming(well_formed())
    assert [
        error for error in shape_errors(document) if "capabilities" in error
    ] == [
        'states.orchard.capabilities names "claimed", and this plan.toml has '
        "no [identity] table. A claim records the session that holds the item. "
        "Declare [identity].pid — the environment variable names a session's "
        "pid may be read from — or drop the capability"
    ]


def test_a_claimed_state_with_an_identity_is_well_formed() -> None:
    """The other half: it is the missing table that refuses, not the
    capability."""
    document = claiming(well_formed())
    document["states"]["orchard"]["capabilities"] = ["queued", "claimed"]
    document["identity"] = {"pid": ["GREENHOUSE_PID"]}
    assert shape_errors(document) == []


def test_a_malformed_identity_is_one_complaint_not_two() -> None:
    """One complaint per defect: the table is there, so what is wrong with it
    is what gets said. Repeating "and it claims things" would be noise."""
    document = claiming(well_formed())
    document["identity"] = {"pid": []}
    errors = shape_errors(document)
    assert not [error for error in errors if "capabilities" in error]
    assert any("identity.pid is empty" in error for error in errors)


def fixture_needing(tmp_path: Path, minimum: str, extra: str = "") -> Path:
    """The fixture, declaring the oldest tool it reads under, and whatever
    `extra` a newer release might have taught it."""
    for name in FIXTURE_FILES:
        (tmp_path / name).write_text((FIXTURES / name).read_text())
    source = tmp_path / "plan.toml"
    source.write_text(f'[fileplan]\nminimum = "{minimum}"\n\n{source.read_text()}{extra}')
    return source


def test_a_plan_toml_for_a_newer_tool_says_upgrade_before_anything_else(
    tmp_path: Path,
) -> None:
    """26-1: the tool's age, said as the tool's age. The unknown table beside
    it is what a newer release's field looks like to this one, and it would
    blame the declaration; the minimum is checked first, so it never does."""
    installed = version("fileplan")
    source = fixture_needing(tmp_path, "999.0", extra="\n[orangery]\nglass = true\n")
    with pytest.raises(Refusal) as refused:
        load(source)
    assert refused.value.messages == [
        f"{source} needs fileplan 999.0 or newer, and this is fileplan "
        f"{installed}: upgrade fileplan to read it"
    ]


@pytest.mark.parametrize("spelled", ["installed", "trailing zero"])
def test_a_minimum_this_tool_meets_loads(tmp_path: Path, spelled: str) -> None:
    """Equal is enough, and `0.6` is `0.6.0`: dotted integers, trailing zeros
    stripped."""
    installed = re.match(r"\d+(\.\d+)*", version("fileplan")).group()
    minimum = installed if spelled == "installed" else installed + ".0"
    load(fixture_needing(tmp_path, minimum))


@pytest.mark.parametrize(
    ("table", "complaint"),
    [
        ('fileplan = "0.6.0"', "fileplan must be a table"),
        ("[fileplan]", "fileplan is empty"),
        ("[fileplan]\nroot = 1", "fileplan.root must be a string"),
        ('[fileplan]\nminimum = "v1"', "fileplan.minimum must be a version of dotted integers"),
        ("[fileplan]\nminimum = 1", "fileplan.minimum must be a version of dotted integers"),
        ('[fileplan]\nminimum = "0.1"\nmaximum = "9"', "fileplan.maximum is not a tool field"),
        ('[fileplan]\nignore = "AGENTS.md"', "fileplan.ignore must be a list of strings"),
        ("[fileplan]\nignore = [1]", "fileplan.ignore must be a list of strings"),
        ("[fileplan]\nignore = []", "fileplan.ignore is empty"),
        (
            '[fileplan]\nignore = ["AGENTS.md", "AGENTS.md"]',
            'fileplan.ignore names "AGENTS.md" twice',
        ),
        ('[fileplan]\nignore = ["notes/AGENTS.md"]', 'fileplan.ignore: "notes/AGENTS.md" is a path'),
        ('[fileplan]\nignore = ["AGENTS.txt"]', 'fileplan.ignore: "AGENTS.txt" does not end in .md'),
    ],
)
def test_a_malformed_tool_table_refuses_by_name(table: str, complaint: str) -> None:
    """An empty table is vacuous, the way `[identity]` without a pid is, and so
    is an empty `ignore`. 35-1: a name in `ignore` is applied in every state
    directory, so a path is not one; and a name without the item suffix is
    never read, so listing it would skip nothing."""
    document = well_formed() | tomllib.loads(table)
    assert any(error.startswith(complaint) for error in shape_errors(document))


def test_the_ignore_list_is_carried_on_the_declaration(tmp_path: Path) -> None:
    """35-1: `[fileplan].ignore` loads as the set the traversal reads, and a
    table holding only `ignore` is not vacuous. Without the table the set is
    empty, so every `*.md` in a state directory is an item."""
    source = fixture_needing(tmp_path, "0.1")
    assert load(source).ignore == frozenset()
    source.write_text('[fileplan]\nignore = ["AGENTS.md", "NOTES.md"]\n\n[states.greenhouse]\n')
    assert load(source).ignore == {"AGENTS.md", "NOTES.md"}


def test_a_transition_carries_what_it_claims() -> None:
    """4-4's field, read off the declaration like every other. The fixture's
    `tend` claims where it stands and `bench` — which arrives in the same
    state — does not, which is the whole of the change stated as data."""
    declaration = load(FIXTURES / "plan.toml")
    assert declaration.transitions["tend"].claims
    assert declaration.transitions["pot-up"].claims
    assert not declaration.transitions["bench"].claims
    assert not declaration.transitions["bed-out"].claims
    assert not declaration.transitions["transplant"].claims


def test_a_claims_that_is_not_a_boolean_refuses() -> None:
    """A real boolean, not a string that reads like one. `claims = "false"` is
    truthy, so the spelling that looks safest is the one that would silently
    claim — which is exactly the polarity this repo refuses."""
    document = claiming(well_formed())
    document["transitions"]["transplant"]["claims"] = "true"
    document["identity"] = {"pid": ["GREENHOUSE_PID"]}
    assert "transitions.transplant.claims must be true or false" in shape_errors(
        document
    )


def test_claiming_into_a_state_that_does_not_claim_refuses_by_name() -> None:
    """A claim with no state to live in — the shape a cursor on a state that
    counts no sub-phases already refuses. The verb would take a record on an
    item nothing reports as held, which is a guarantee nobody can see."""
    document = well_formed()
    document["transitions"]["transplant"]["claims"] = True
    assert (
        'transitions.transplant.claims is true, and states.orchard does not '
        'name "claimed" in its capabilities. A claim lives in the state the '
        'item is claimed into. Name "claimed" in states.orchard.capabilities, '
        "or drop the claims" in shape_errors(document)
    )


def test_a_claimed_state_no_transition_claims_into_refuses_by_name() -> None:
    """The other end of the same rule. From 4-4 nothing else can take a claim,
    so a state that opts in with no verb claiming into it holds one session at
    a time in name only — the make-problems-visible rule, and cheap
    to satisfy."""
    document = well_formed()
    document["states"]["orchard"]["capabilities"] = ["claimed"]
    document["identity"] = {"pid": ["GREENHOUSE_PID"]}
    assert (
        'states.orchard.capabilities names "claimed", and no transition '
        "claims into orchard. A claim is taken by the transition that declares "
        "`claims = true`, never by an item arriving. Name a transition that "
        "claims into orchard, or drop the capability" in shape_errors(document)
    )


def test_a_verb_claiming_where_it_stands_satisfies_the_state() -> None:
    """An in-place verb is what this repo's `plan` uses, and it counts: the
    rule is that *some* transition claims into the state, not that one arrives
    from elsewhere. That is what lets work be claimed where it stands rather
    than having to move into a directory to be picked up."""
    document = well_formed()
    document["states"]["orchard"]["capabilities"] = ["queued", "claimed"]
    document["transitions"]["graft-on"] = {
        "kind": "edit",
        "doc": "method.md#graft",
        "help": "Work on it where it stands.",
        "from": "orchard",
        "claims": True,
    }
    document["identity"] = {"pid": ["GREENHOUSE_PID"]}
    assert shape_errors(document) == []


# --------------------------------------------------------------------------
# The dependency key: which declared key holds what an item waits on
# --------------------------------------------------------------------------
#
# `sub-phase-cursor`'s shape one key over, so the arms are the cursor's arms:
# the field names a **declared** key, and the row field derived from it is the
# tool's and may not be redeclared. What is *new* here is nothing at all —
# which is the point, because `_key_reference_error` already refuses every
# name a dependency key may not be.


def with_dependencies(document: dict) -> dict:
    """`well_formed()` plus a state that reads dependencies out of a key."""
    document["states"]["orchard"][depends.FIELD] = "after"
    document["keys"]["after"] = {"doc": "method.md#cultivar"}
    return document


def test_a_state_may_read_no_dependencies_at_all() -> None:
    """Absence is the ordinary case and grades nothing."""
    assert [
        error for error in shape_errors(well_formed()) if depends.FIELD in error
    ] == []


def test_a_dependency_key_naming_an_undeclared_key_refuses_by_name() -> None:
    """The cursor's typo class: a state pointing at a key nobody wrote is a
    defect rather than a dependency."""
    document = with_dependencies(well_formed())
    document["states"]["orchard"][depends.FIELD] = "aftre"
    assert (
        f'states.orchard.{depends.FIELD} names undeclared key "aftre"'
        in shape_errors(document)
    )


@pytest.mark.parametrize("name", ["position", "title", "blocked-by", "blocks"])
def test_a_dependency_key_naming_a_key_the_tool_owns_refuses(name: str) -> None:
    """Through `_key_reference_error` and with no message of its own: a
    capability-given key, an intrinsic one and a derived one are already
    things a reference may not name, so this arm cost the tool no new words."""
    document = with_dependencies(well_formed())
    document["states"]["orchard"][depends.FIELD] = name
    assert any(
        f'states.orchard.{depends.FIELD} names "{name}"' in error
        for error in shape_errors(document)
    )


def test_a_dependency_key_that_is_not_a_string_refuses() -> None:
    document = with_dependencies(well_formed())
    document["states"]["orchard"][depends.FIELD] = ["after"]
    assert f"states.orchard.{depends.FIELD} must be a string" in shape_errors(document)


def test_declaring_the_blocked_by_field_as_a_key_refuses_by_name() -> None:
    """It is derived from the tree — what an item waits on, against what is
    still filed — so a key beside it is a second answer that can drift out of
    step with both."""
    document = well_formed()
    document["keys"][depends.BLOCKED] = {"doc": "method.md#cultivar"}
    assert [
        error for error in shape_errors(document) if f"keys.{depends.BLOCKED} " in error
    ] == [
        f'keys.{depends.BLOCKED} redeclares "{depends.BLOCKED}", which every '
        "listing derives from the tree around the item. What an item waits on, "
        "and what waits on it, is read off the key its state names, against "
        "what is still filed. "
        f"Drop keys.{depends.BLOCKED}"
    ]


@pytest.mark.parametrize("field", ["requires", "sets", "drops", "refuses"])
def test_a_transition_naming_the_blocked_by_field_refuses(field: str) -> None:
    """Read, not written: there is nothing here for a verb to set."""
    document = well_formed()
    named = {depends.BLOCKED: ["x"]} if field == "refuses" else [depends.BLOCKED]
    document["transitions"]["transplant"][field] = named
    assert any(
        f'transitions.transplant.{field} names "{depends.BLOCKED}"' in error
        for error in shape_errors(document)
    )


def test_a_declaration_reading_dependencies_carries_the_derived_field() -> None:
    """The fixture's `orchard` names one, so `--has blocked-by` reaches it."""
    declaration = load(FIXTURES / "plan.toml")
    assert declaration.has_dependencies
    assert {depends.BLOCKED, depends.BLOCKS} <= set(declaration.carried)


def test_a_declaration_with_no_dependencies_carries_neither(
    tmp_path: Path,
) -> None:
    """`counts_sub_phases`' rule one field over: the field and its filter are
    present on the one question, so where no state names a key there is
    nothing for `--has` to reach."""
    source = tmp_path / "plan.toml"
    source.write_text(
        (FIXTURES / "plan.toml").read_text().replace('dependencies      = "after"', "")
    )
    for name in FIXTURE_FILES[1:]:
        (tmp_path / name).write_text((FIXTURES / name).read_text())
    declaration = load(source)
    assert not declaration.has_dependencies
    assert not {depends.BLOCKED, depends.BLOCKS} & set(declaration.carried)


# --------------------------------------------------------------------------
# `references`: slug edges that block nothing, with a derived inverse
# --------------------------------------------------------------------------
#
# Each key is graded as a reference, the dependency key's arms, and each
# inverse as a row field nothing else may already be. The cross-state rules
# read the whole document: one key, one inverse, both ways round.


def with_references(document: dict, *states: str) -> dict:
    """`well_formed()` plus `replaces`, a reference read back as
    `replaced-by`, on each of `states` (both by default)."""
    document["keys"]["replaces"] = {"doc": "method.md#cultivar", "list-valued": True}
    for name in states or ("greenhouse", "orchard"):
        document["states"][name]["references"] = {
            "replaces": {"inverse": "replaced-by"}
        }
    return document


def test_the_same_reference_on_two_states_loads_clean() -> None:
    """The decision-record workflow declares one on its drafts and one on
    its decisions, so the same pair twice is one reference, not a clash."""
    assert shape_errors(with_references(well_formed())) == []


def test_a_state_carries_its_references_and_the_declaration_its_inverses() -> None:
    declaration = load(FIXTURES / "plan.toml")
    assert dict(declaration.states["greenhouse"].references) == {
        "replaces": "replaced-by"
    }
    assert dict(declaration.states["cold-frame"].references) == {}
    assert declaration.has_references
    assert declaration.inverses == ("replaced-by",)
    assert declaration.derived[-1] == "replaced-by"
    assert "replaced-by" in declaration.carried


@pytest.mark.parametrize(
    ("value", "said"),
    [
        ("replaces", "states.orchard.references must be a table of KEY = "),
        ({"replaces": "replaced-by"}, "states.orchard.references.replaces must be a table"),
        ({"replaces": {}}, "states.orchard.references.replaces declares no inverse"),
        (
            {"replaces": {"inverse": 3}},
            "states.orchard.references.replaces.inverse must be a string",
        ),
        (
            {"replaces": {"inverse": "replaced-by", "blocks": True}},
            "states.orchard.references.replaces.blocks is not a reference field",
        ),
        (
            {"replaces": {"inverse": "Replaced By"}},
            'states.orchard.references.replaces.inverse names "Replaced By", '
            "which is not a usable name",
        ),
    ],
)
def test_a_reference_of_the_wrong_shape_refuses_by_name(value: object, said: str) -> None:
    document = with_references(well_formed(), "orchard")
    document["states"]["orchard"]["references"] = value
    assert any(error.startswith(said) for error in shape_errors(document))


@pytest.mark.parametrize(
    ("key", "said"),
    [
        ("replacse", 'names undeclared key "replacse"'),
        ("title", 'names "title", which is intrinsic'),
        ("position", 'names "position", which the queued capability'),
        ("blocks", 'names "blocks", which every listing derives'),
    ],
)
def test_a_reference_key_the_tool_cannot_read_refuses(key: str, said: str) -> None:
    """`_key_reference_error`'s arms, with no message of their own."""
    document = with_references(well_formed(), "orchard")
    document["states"]["orchard"]["references"] = {key: {"inverse": "replaced-by"}}
    assert any(
        error.startswith(f"states.orchard.references {said}")
        for error in shape_errors(document)
    )


@pytest.mark.parametrize("field", [depends.FIELD, OPENED_FOR])
def test_a_reference_key_the_state_already_reads_slugs_out_of_refuses(
    field: str,
) -> None:
    """One key, one meaning: a key that blocks and records at once would do
    whichever the reader of the moment looked at."""
    document = with_references(well_formed(), "orchard")
    document["states"]["orchard"][field] = "replaces"
    assert (
        f'states.orchard.references names "replaces", which '
        f"states.orchard.{field} already reads slugs out of"
    ) in "\n".join(shape_errors(document))


def test_an_inverse_with_a_declared_keys_name_refuses_naming_the_state() -> None:
    document = with_references(well_formed(), "orchard")
    document["keys"]["replaced-by"] = {"doc": "method.md#cultivar"}
    assert any(
        error.startswith(
            'keys.replaced-by redeclares "replaced-by", which states.orchard '
            "derives as the inverse of replaces"
        )
        for error in shape_errors(document)
    )


@pytest.mark.parametrize(
    "inverse", ["title", "slug", "state", "path", "blocks", "position", "claimed-by"]
)
def test_an_inverse_a_row_already_carries_refuses(inverse: str) -> None:
    document = with_references(well_formed(), "orchard")
    document["states"]["orchard"]["references"] = {"replaces": {"inverse": inverse}}
    assert any(
        error.startswith(
            f'states.orchard.references.replaces.inverse names "{inverse}", '
            "which a row already carries"
        )
        for error in shape_errors(document)
    )


def test_one_key_declaring_two_inverses_refuses() -> None:
    document = with_references(well_formed())
    document["states"]["orchard"]["references"]["replaces"]["inverse"] = "ousted-by"
    assert [error for error in shape_errors(document) if "inverse" in error] == [
        'states.orchard.references.replaces.inverse names "ousted-by", and '
        'states.greenhouse.references.replaces names "replaced-by". One key '
        "reads back under one inverse. Name the same one on both"
    ]


def test_two_keys_sharing_one_inverse_refuses() -> None:
    document = with_references(well_formed(), "greenhouse")
    document["keys"]["ousts"] = {"doc": "method.md#cultivar"}
    document["states"]["orchard"]["references"] = {"ousts": {"inverse": "replaced-by"}}
    assert [error for error in shape_errors(document) if "inverse" in error] == [
        'states.orchard.references.ousts.inverse names "replaced-by", which '
        "states.greenhouse.references.replaces already reads back. One inverse "
        "reads back one key, or the row could not say which edge it came from. "
        "Name another inverse"
    ]


@pytest.mark.parametrize("field", ["requires", "sets", "drops"])
def test_a_transition_naming_an_inverse_refuses_as_undeclared(field: str) -> None:
    """Nothing new: the inverse is no declared key, so a verb cannot name it."""
    document = with_references(well_formed())
    document["transitions"]["transplant"][field] = ["replaced-by"]
    assert (
        f'transitions.transplant.{field} names undeclared key "replaced-by"'
        in shape_errors(document)
    )


def test_a_declaration_with_no_references_carries_no_inverse(tmp_path: Path) -> None:
    source = tmp_path / "plan.toml"
    source.write_text(
        re.sub(r"(?m)^references\s*=.*\n", "", (FIXTURES / "plan.toml").read_text())
    )
    for name in FIXTURE_FILES[1:]:
        (tmp_path / name).write_text((FIXTURES / name).read_text())
    declaration = load(source)
    assert not declaration.has_references
    assert declaration.inverses == ()
    assert "replaced-by" not in declaration.carried


# --------------------------------------------------------------------------
# `opened-for`: which declared key says what an item here was opened for
# --------------------------------------------------------------------------
#
# The dependency key's shape a second time, and since 13-2 literally the same
# code: both fields go through `_key_field_errors`, so nothing new is graded
# here and the two cannot drift apart. What the field gates is one refusal,
# `fileplan.transition.dangle_errors`, and that is graded there.


def with_an_owner(document: dict) -> dict:
    """`well_formed()` plus a state saying what its items were opened for."""
    document["states"]["greenhouse"][OPENED_FOR] = "batch"
    document["keys"]["batch"] = {"doc": "method.md#cultivar"}
    return document


def test_a_state_may_name_no_owner_at_all() -> None:
    """Absence is the ordinary case and grades nothing — which is also the
    whole gate: a state naming none is looked up by nothing."""
    document = well_formed()
    assert [
        error for error in shape_errors(document) if OPENED_FOR in error
    ] == []


def test_the_field_loads_clean() -> None:
    assert shape_errors(with_an_owner(well_formed())) == []


def test_an_owner_naming_an_undeclared_key_refuses_by_name() -> None:
    """The cursor's typo class: a state pointing at a key nobody wrote is a
    defect rather than a reference."""
    document = with_an_owner(well_formed())
    document["states"]["greenhouse"][OPENED_FOR] = "btach"
    assert (
        f'states.greenhouse.{OPENED_FOR} names undeclared key "btach"'
        in shape_errors(document)
    )


@pytest.mark.parametrize("name", ["position", "title", "blocked-by", "blocks", "stale-days"])
def test_an_owner_naming_a_key_the_tool_owns_refuses(name: str) -> None:
    """Through `_key_reference_error` and with no message of its own: an
    intrinsic, a capability-given and a derived name are already things a
    reference may not be, so this field cost the tool no new words."""
    document = with_an_owner(well_formed())
    document["states"]["greenhouse"][OPENED_FOR] = name
    assert any(
        f'states.greenhouse.{OPENED_FOR} names "{name}"' in error
        for error in shape_errors(document)
    )


def test_an_owner_field_that_is_not_a_string_refuses() -> None:
    document = with_an_owner(well_formed())
    document["states"]["greenhouse"][OPENED_FOR] = ["batch"]
    assert (
        f"states.greenhouse.{OPENED_FOR} must be a string" in shape_errors(document)
    )


def test_both_fields_the_shared_grader_serves_refuse_in_the_same_words() -> None:
    """13-2 collapsed two identical graders into `_key_field_errors`, and this
    is what pins the collapse: the dependency field and the owner field are
    the same rule, so a defect in either comes out in the same sentence with
    only the field name differing."""
    document = with_an_owner(well_formed())
    document["states"]["greenhouse"][OPENED_FOR] = "btach"
    document["states"]["greenhouse"][depends.FIELD] = "btach"
    errors = shape_errors(document)
    for field in (OPENED_FOR, depends.FIELD):
        assert (
            f'states.greenhouse.{field} names undeclared key "btach"' in errors
        )


def test_a_state_pinned_to_the_old_sealing_vocabulary_refuses_by_name() -> None:
    """`sealed-at` was the second half of the pair 13-2 took out with the
    `edited` report. A declaration still carrying it must fail **loudly**
    rather than have a field it declares silently ignored, which is what
    `_unknown_fields` gives once the word leaves `STATE_FIELDS`."""
    document = with_an_owner(well_formed())
    document["states"]["greenhouse"]["sealed-at"] = "cutting"
    assert any(
        "states.greenhouse" in error and "sealed-at" in error
        for error in shape_errors(document)
    )


def test_the_fixtures_carrier_state_reads_its_owner_off_the_declaration() -> None:
    """The fixture's carrier names a **tree of `orchard`**, in the fixture's
    own words — so nothing about the check can pass by agreeing with this
    repo's `opened-for`, `sub-phase` or `done`."""
    declaration = load(FIXTURES / "plan.toml")
    assert declaration.states["propagator"].opened_for == "for-tree"


def test_naming_an_owner_gives_a_row_no_key_at_all() -> None:
    """Unlike every capability, this derives no field: what comes out of it is
    a refusal at the close, not a value beside an item. So there is nothing
    here for `--has` to reach, and nothing to refuse a redeclaration of."""
    declaration = load(FIXTURES / "plan.toml")
    assert OPENED_FOR not in declaration.carried


# --------------------------------------------------------------------------
# `stale-days`: carried by every row, and stored nowhere
# --------------------------------------------------------------------------


def test_declaring_the_stale_days_field_as_a_key_refuses_by_name() -> None:
    for name in STALE_KEYS:
        graded = well_formed()
        graded["keys"][name] = {"doc": "method.md#cultivar"}
        assert [
            error for error in shape_errors(graded) if f"keys.{name} " in error
        ] == [
            f'keys.{name} redeclares "{name}", which every listing derives '
            "from git's record of when the file last changed. Nothing is "
            "stored to make it, so a key beside git's record can only go "
            f"stale. Drop keys.{name}"
        ]


@pytest.mark.parametrize("field", ["requires", "sets", "drops", "refuses"])
def test_a_transition_naming_the_stale_days_field_refuses(field: str) -> None:
    """Read, not written — and the third source phrase the one generalised
    arm carries, beside the body's and the tree's."""
    document = well_formed()
    name = STALE_KEYS[0]
    document["transitions"]["transplant"][field] = (
        {name: ["1"]} if field == "refuses" else [name]
    )
    assert (
        f'transitions.transplant.{field} names "{name}", which every listing '
        "derives from git's record of when the file last changed. A derived "
        "key is read rather than written, so there is nothing here to set. "
        f'Drop "{name}" from transitions.transplant.{field}'
        in shape_errors(document)
    )


def test_the_stale_field_is_carried_by_every_declaration() -> None:
    """31-1: the age needs no switch, so even a declaration of one plain
    state carries it, and `--has` and `--lacks` reach it everywhere."""
    plain = Declaration(
        source=FIXTURES / "plan.toml",
        root=FIXTURES,
        states={"greenhouse": State(name="greenhouse", path="greenhouse")},
        keys={},
        transitions={},
    )
    for name in STALE_KEYS:
        assert name in plain.carried
        assert name not in load(FIXTURES / "plan.toml").keys


# --------------------------------------------------------------------------
# `bulleted`: the capability that writes a body
# --------------------------------------------------------------------------

#: The fixture's pending bullet, in the fixture's vocabulary.
UNPRUNED = "**unpruned — Say what the rest of the training is.**"


def bulleted(document: dict) -> dict:
    """``well_formed`` with `orchard` minting sub-phases, and a verb that does."""
    document["states"]["orchard"].update(
        {
            "capabilities": ["queued", "numbered", "bulleted"],
            "archive": "orchard-archive.md",
            "sub-phases": "Steps",
            "sub-phase-pending": UNPRUNED,
            "sub-phase-name": "{number}-{ordinal}",
        }
    )
    document["transitions"]["espalier"] = {
        "kind": "add-bullet",
        "doc": "method.md#espalier",
        "help": "Train one more branch.",
        "from": "orchard",
    }
    return document


def test_a_state_that_mints_bullets_and_a_verb_that_writes_them_is_well_formed() -> None:
    assert shape_errors(bulleted(well_formed())) == []


def test_bulleted_without_a_sub_phases_heading_refuses_by_name() -> None:
    """There is nothing to mint *under*: the writer would have no span to
    append to, and the counter would count nothing it wrote."""
    document = bulleted(well_formed())
    del document["states"]["orchard"]["sub-phases"]
    assert (
        'states.orchard.capabilities names "bulleted", and this state '
        "declares no sub-phases heading. A sub-phase is a bullet under a "
        "heading, so there is nothing here to mint one under. Add "
        "states.orchard.sub-phases, or drop the capability"
        in shape_errors(document)
    )


def test_bulleted_without_a_name_form_refuses_by_name() -> None:
    """The tool supplies the ordinal and the workflow supplies the rest of the
    name, so a state that opts in without saying what its bullets are called
    has not said the one thing only it can say."""
    document = bulleted(well_formed())
    del document["states"]["orchard"]["sub-phase-name"]
    assert (
        'states.orchard.capabilities names "bulleted", and this state '
        "declares no sub-phase-name. A bullet is named from the ordinal the "
        "tool supplies and the form the workflow declares. Add "
        "states.orchard.sub-phase-name, or drop the capability"
        in shape_errors(document)
    )


def test_a_name_form_on_a_state_that_mints_nothing_refuses_by_name() -> None:
    """The pending bullet's shape one field over: a form nothing writes and
    nothing reads."""
    document = well_formed()
    document["states"]["orchard"]["sub-phase-name"] = "{number}-{ordinal}"
    assert (
        "states.orchard.sub-phase-name says what this state's bullets are "
        'called, and this state does not opt into "bulleted". Nothing writes '
        'the field and nothing reads it. Add "bulleted" to '
        "states.orchard.capabilities, or drop the field"
        in shape_errors(document)
    )


def test_a_form_naming_a_capability_key_the_state_does_not_give_refuses() -> None:
    """`bulleted`-requires-`numbered`, as a graded rule rather than a hard
    coupling. The form is what names the key now, so the refusal is conditional
    on the form naming it — and it names the capability, generically, rather
    than spelling one key's name into the message."""
    document = bulleted(well_formed())
    document["states"]["orchard"]["capabilities"] = ["queued", "bulleted"]
    del document["states"]["orchard"]["archive"]
    assert (
        'states.orchard.sub-phase-name names "{number}", which the numbered '
        "capability gives an item, and this state does not name \"numbered\" "
        "in its capabilities. A state that names its bullets from a key is the "
        'state that mints the key. Add "numbered" to '
        "states.orchard.capabilities, or name another field"
        in shape_errors(document)
    )


def test_a_bulleted_state_that_needs_no_register_loads_clean() -> None:
    """**The whole point of 7-1.** A state with no register, naming its
    bullets off nothing but the ordinal, is a declaration the tool had no way
    to express before the form was declared — `bulleted` required `numbered`
    outright."""
    document = bulleted(well_formed())
    document["states"]["orchard"]["capabilities"] = ["queued", "bulleted"]
    del document["states"]["orchard"]["archive"]
    document["states"]["orchard"]["sub-phase-name"] = "f{ordinal}"
    assert shape_errors(document) == []


def test_a_form_naming_a_key_nothing_declares_refuses_by_name() -> None:
    """The defect the old coupling could not see at all: a field no item here
    can hold would be spelled into every name as nothing at all."""
    document = bulleted(well_formed())
    document["states"]["orchard"]["sub-phase-name"] = "{vintage}-{ordinal}"
    assert (
        'states.orchard.sub-phase-name names "{vintage}", which is not '
        '"{ordinal}" and is not a key an item here can carry. A field nothing '
        "fills would be spelled into every bullet name as nothing at all. "
        'Name "{ordinal}", or a key an item here carries'
        in shape_errors(document)
    )


def test_a_form_may_name_an_ordinary_declared_key() -> None:
    """The other side of that rule, and the reason it is about what an item
    *carries* rather than about capabilities: `rootstock` is an ordinary
    declared key, so a workflow may name its bullets from it."""
    document = bulleted(well_formed())
    document["states"]["orchard"]["sub-phase-name"] = "{rootstock}/{ordinal}"
    assert shape_errors(document) == []


@pytest.mark.parametrize(
    "form, said",
    [
        pytest.param("", "is empty", id="empty"),
        pytest.param("step-", 'carries no "{ordinal}"', id="no-ordinal"),
        pytest.param("{ordinal}a", "is not the end of it", id="not-last"),
        pytest.param("{ordinal}{ordinal}", "2 times", id="twice"),
        pytest.param("{ordinal", "leaves a brace unclosed", id="unbalanced"),
    ],
)
def test_a_form_that_is_not_one_is_named_at_load(form: str, said: str) -> None:
    """Graded through `subphase.form_errors`, which is the reader that will
    have to strip a prefix off a name — the rule the pending bullet already
    follows."""
    document = bulleted(well_formed())
    document["states"]["orchard"]["sub-phase-name"] = form
    (complaint,) = [
        one for one in shape_errors(document) if one.startswith("states.orchard.sub-phase-name")
    ]
    assert said in complaint


def test_bulleted_without_a_pending_bullet_refuses_by_name() -> None:
    """The marker is the bullet rather than a head key, so a state that mints
    without one could not say a section is still being cut up — and a section
    half decomposed would read as a finished one."""
    document = bulleted(well_formed())
    del document["states"]["orchard"]["sub-phase-pending"]
    assert (
        'states.orchard.capabilities names "bulleted", and this state '
        "declares no sub-phase-pending. An unfinished decomposition is marked "
        "by a bullet, so a section half cut up would otherwise read as a "
        "finished one. Add states.orchard.sub-phase-pending, or drop the "
        "capability" in shape_errors(document)
    )


def test_a_pending_bullet_on_a_state_that_mints_nothing_refuses_by_name() -> None:
    """The other way round, and `archive`'s shape one capability over: a
    sentence nothing writes and nothing reads."""
    document = well_formed()
    document["states"]["orchard"]["sub-phase-pending"] = UNPRUNED
    assert (
        "states.orchard.sub-phase-pending says how an unfinished "
        "decomposition is marked, and this state does not opt into "
        '"bulleted". Nothing writes the field and nothing reads it. Add '
        '"bulleted" to states.orchard.capabilities, or drop the field'
        in shape_errors(document)
    )


@pytest.mark.parametrize(
    "pending, said",
    [
        pytest.param("Say what the rest is.", "not a named sub-phase", id="unnamed"),
        pytest.param("", "not a named sub-phase", id="empty"),
        pytest.param("**a**\n**b**", "carries a newline", id="newline"),
    ],
)
def test_a_pending_bullet_that_is_not_a_named_bullet_refuses_by_name(
    pending: str, said: str
) -> None:
    """Graded at load **through the tool's own reader**, so the declaration is
    checked by the same code that will have to find the bullet again."""
    document = bulleted(well_formed())
    document["states"]["orchard"]["sub-phase-pending"] = pending
    assert any(
        error.startswith("states.orchard.sub-phase-pending") and said in error
        for error in shape_errors(document)
    )


def test_a_pending_bullet_that_is_not_a_string_is_one_complaint() -> None:
    """One complaint per defect: the arm that would read it as a bullet stays
    quiet."""
    document = bulleted(well_formed())
    document["states"]["orchard"]["sub-phase-pending"] = 7
    errors = shape_errors(document)
    assert "states.orchard.sub-phase-pending must be a string" in errors
    assert len([one for one in errors if "sub-phase-pending" in one]) == 1


def test_a_transition_carries_what_it_mints() -> None:
    """`claims`' field, read off the declaration the same way. The fixture's
    `espalier` mints and `graft-on` — an in-place verb into the same state —
    does not, which is what says the option comes from the verb."""
    declaration = load(FIXTURES / "plan.toml")
    assert declaration.transitions["espalier"].kind == "add-bullet"
    assert declaration.transitions["graft-on"].kind == "edit"
    assert declaration.transitions["harvest"].kind == "move"


def test_minting_into_a_state_that_mints_nothing_refuses_by_name() -> None:
    """A write with no body rule behind it — `claims` into a state that does
    not claim, one capability over."""
    document = well_formed()
    document["transitions"]["espalier"] = {
        "kind": "add-bullet",
        "doc": "method.md#espalier",
        "help": "Train one more branch.",
        "from": "orchard",
    }
    assert (
        "transitions.espalier is an add-bullet, and states.orchard does not "
        'name "bulleted" in its capabilities. A sub-phase is a bullet under a '
        "heading, and states.orchard is what declares the heading and the "
        'pending bullet. Name "bulleted" in states.orchard.capabilities, or '
        "give espalier another kind"
        in shape_errors(document)
    )


def test_a_bulleted_state_no_transition_mints_into_refuses_by_name() -> None:
    """The other end of the same rule. Nothing else writes a sub-phase, so the
    capability would be inert and the operator would find out by a section
    that never decomposes."""
    document = bulleted(well_formed())
    del document["transitions"]["espalier"]
    assert (
        'states.orchard.capabilities names "bulleted", and no add-bullet '
        "transition writes into orchard. A sub-phase is written by a "
        "transition of that kind, never by an item arriving. Declare one from "
        "orchard, or drop the capability"
        in shape_errors(document)
    )


# --------------------------------------------------------------------------
# `marks`: the transition half that disposes of one bullet
# --------------------------------------------------------------------------


def marking(document: dict) -> dict:
    """``bulleted`` with a **disposition** beside the verb that mints."""
    document = bulleted(document)
    document["transitions"]["pot-on"] = {
        "kind": "mark-bullet",
        "doc": "method.md#pot-on",
        "help": "Say a branch has taken.",
        "from": "orchard",
        "marks": "taken",
    }
    return document


def test_a_state_that_mints_bullets_and_a_verb_that_marks_one_is_well_formed() -> None:
    assert shape_errors(marking(well_formed())) == []


def test_a_transition_carries_the_word_it_marks() -> None:
    """`mints`' field one shape along: a **string**, because the word is the
    workflow's and the tool supplies only the bold around it. The fixture's
    `pot-on` marks and `mist` — the verb that writes the bullets it marks —
    does not, which is what says the positional comes from the verb."""
    declaration = load(FIXTURES / "plan.toml")
    assert declaration.transitions["pot-on"].marks == "rooted"
    assert declaration.transitions["mist"].marks is None
    assert declaration.transitions["espalier"].marks is None


def test_a_marks_that_is_not_a_string_refuses() -> None:
    document = marking(well_formed())
    document["transitions"]["pot-on"]["marks"] = True
    assert "transitions.pot-on.marks must be a string" in shape_errors(document)


def test_marking_into_a_state_that_carries_no_bullets_refuses_by_name() -> None:
    """`mints`' rule from the same end: a mark has to have a bullet to go on,
    and a state that declares none has nothing for the word to land on."""
    document = well_formed()
    document["transitions"]["pot-on"] = {
        "kind": "mark-bullet",
        "doc": "method.md#pot-on",
        "help": "Say a branch has taken.",
        "from": "orchard",
        "marks": "taken",
    }
    assert (
        "transitions.pot-on is a mark-bullet, and states.orchard does not "
        'name "bulleted" in its capabilities. A mark goes on a bullet, and '
        "states.orchard is what declares the heading those bullets live "
        'under. Name "bulleted" in states.orchard.capabilities, or give '
        "pot-on another kind" in shape_errors(document)
    )


def test_two_verbs_marking_one_state_with_the_same_word_refuse_naming_both() -> None:
    """One rule with two spellings, and the bullet afterwards cannot say which
    of them ran — the `values` argument, over a word two verbs write."""
    document = marking(well_formed())
    document["transitions"]["pot-off"] = dict(
        document["transitions"]["pot-on"], doc="method.md#pot-off"
    )
    assert (
        'transitions.pot-off and pot-on both mark orchard with "taken". A '
        'bullet carrying "taken" cannot say which of the two transitions ran. '
        "Give each transition its own word" in shape_errors(document)
    )


def test_two_verbs_marking_one_state_with_different_words_are_well_formed() -> None:
    """Which is the whole point of the field being a word: a state's
    vocabulary is what the verbs marking into it declare between them."""
    document = marking(well_formed())
    document["transitions"]["pot-off"] = dict(
        document["transitions"]["pot-on"], doc="method.md#pot-off", marks="failed"
    )
    assert shape_errors(document) == []


def test_a_word_that_could_not_be_written_is_graded_at_load() -> None:
    """Through `subphase.mark_errors`, the reader that has to find it again —
    `pending_errors`' shape, one field over. It is the declaration's word
    rather than the operator's, so it is found when the file is read."""
    document = marking(well_formed())
    document["transitions"]["pot-on"]["marks"] = "**taken**"
    assert [
        one for one in shape_errors(document) if one.startswith("transitions.pot-on.marks")
    ] == [
        'transitions.pot-on.marks carries "**", which would close the bold run '
        "it is written in — the mark would end early and the rest would read "
        "as prose"
    ]


def test_a_bulleted_state_nothing_marks_into_loads_clean() -> None:
    """**No inert-half rule**, and the asymmetry is deliberate. A `bulleted`
    state nothing *mints* into can never do anything and refuses; one nothing
    *marks* into is a real shape, graded here over a synthetic document.
    `plan` was the local instance until section 12 gave it dispositions, and
    nothing in this repo or the fixture is that shape now — which is why the
    document under test is the only witness left. `_archiving_errors` records
    the same asymmetry for `archives`."""
    assert shape_errors(bulleted(well_formed())) == []


# --------------------------------------------------------------------------
# `files`: the transition half that creates a second item
# --------------------------------------------------------------------------


def filing(document: dict) -> dict:
    """``marking`` with the disposition **filing** what it disposes of.

    Into `greenhouse`, which is the plain state: `orchard` is `queued` and a
    filed item is filed rather than placed. The two provenance keys are
    declared like any others, because they are the workflow's words.
    """
    document = marking(document)
    document["keys"]["batch"] = {"doc": "method.md#batch"}
    document["keys"]["cutting"] = {"doc": "method.md#cutting"}
    document["transitions"]["pot-on"]["files"] = {
        "state": "greenhouse",
        "item": "batch",
        "name": "cutting",
    }
    return document


def test_a_verb_that_files_and_marks_is_well_formed() -> None:
    assert shape_errors(filing(well_formed())) == []


def test_a_transition_carries_the_table_it_files_by() -> None:
    """`marks`' field one half along: a **table**, because the three facts are
    one capability and each role wants a name. The fixture's `line-out` files
    and `pot-on` beside it does not, which is what says the options come from
    the verb rather than from the state they share."""
    declaration = load(FIXTURES / "plan.toml")
    assert declaration.transitions["line-out"].files == {
        "state": "greenhouse",
        "item": "batch",
        "name": "cutting",
        "sets": ["cultivar"],
    }
    assert declaration.transitions["pot-on"].files is None
    assert declaration.transitions["mist"].files is None


def test_a_filing_verb_reads_the_keys_it_writes_onto_the_filed_item() -> None:
    """`files_sets` is the table's `sets`, so no caller reaches into it, and
    the carrier's own `sets` stays empty: the key lands where it is written."""
    declaration = load(FIXTURES / "plan.toml")
    assert declaration.transitions["line-out"].files_sets == ("cultivar",)
    assert declaration.transitions["line-out"].sets == ()
    assert declaration.transitions["pot-on"].files_sets == ()


def test_a_files_that_is_not_a_table_refuses_and_the_rest_stay_quiet() -> None:
    """One complaint per defect: a `files` that is not a table has no roles to
    grade, so grading them would be four messages about one mistake."""
    document = filing(well_formed())
    document["transitions"]["pot-on"]["files"] = "greenhouse"
    assert [
        one for one in shape_errors(document) if one.startswith("transitions.pot-on.files")
    ] == [
        "transitions.pot-on.files must be a table naming state, item, name — "
        "where the filed item goes, and which declared keys record the item "
        "and the bullet it came from"
    ]


def test_an_unknown_filing_role_refuses_by_name() -> None:
    document = filing(well_formed())
    document["transitions"]["pot-on"]["files"]["title"] = "cutting"
    assert (
        "transitions.pot-on.files.title is not a filing field"
        in shape_errors(document)
    )


@pytest.mark.parametrize("role", ["state", "item", "name"])
def test_a_missing_filing_role_refuses_by_name(role: str) -> None:
    """The other direction, and it is checkable because the roster is
    **fixed**: a filing names all three or it is not a filing."""
    document = filing(well_formed())
    del document["transitions"]["pot-on"]["files"][role]
    assert (
        f"transitions.pot-on.files has no {role}, and a filing names all of "
        "state, item, name — where the item goes, and the two keys that say "
        "where it came from" in shape_errors(document)
    )


@pytest.mark.parametrize("role", ["state", "item", "name"])
def test_a_filing_role_that_is_not_a_string_refuses(role: str) -> None:
    document = filing(well_formed())
    document["transitions"]["pot-on"]["files"][role] = True
    assert f"transitions.pot-on.files.{role} must be a string" in shape_errors(document)


def test_filing_into_an_undeclared_state_refuses_naming_it() -> None:
    document = filing(well_formed())
    document["transitions"]["pot-on"]["files"]["state"] = "nursery"
    assert (
        'transitions.pot-on.files.state names undeclared state "nursery"'
        in shape_errors(document)
    )


@pytest.mark.parametrize("capability", ["queued", "numbered"])
def test_filing_into_a_state_that_writes_on_arrival_refuses_by_name(
    capability: str,
) -> None:
    """**A filed item is filed, not placed.** Each of the two writes a head
    key on arrival, and honouring one would mean running the entry arms
    against a second destination — machinery with one caller."""
    document = filing(well_formed())
    document["states"]["greenhouse"]["capabilities"] = [capability]
    assert (
        f'transitions.pot-on.files.state names "greenhouse", which declares '
        f'"{capability}". The {capability} capability writes a head key on '
        "arrival, and a filed item is filed rather than placed. File into a "
        "plain state, and move the item afterwards" in shape_errors(document)
    )


def test_filing_into_a_claimed_state_refuses_for_the_claims_reason() -> None:
    """34-2 f6: a claimed state writes no head key, so it is refused for its
    own reason — only a claiming transition enters it — not the placing
    one."""
    document = filing(well_formed())
    document["states"]["greenhouse"]["capabilities"] = ["claimed"]
    assert (
        'transitions.pot-on.files.state names "greenhouse", which declares '
        '"claimed". An item enters a claimed state only by a transition that '
        "claims it, and a filing claims nothing. File into a plain state, and "
        "move the item afterwards" in shape_errors(document)
    )


def test_the_kind_tables_agree() -> None:
    """34-2 f4, f5 and f7: the partition, the edit's fields and the help are
    each derived from `KINDS` or held to it here."""
    assert STAYING | DISSOLVING == {
        kind for kind, fields in KINDS.items() if "to" not in fields and "from" in fields
    }
    assert not STAYING & DISSOLVING
    assert set(KIND_HELP) == set(KINDS)
    assert set(ARCHIVING_HELP) <= {k for k, f in KINDS.items() if "archives" in f}
    assert set(EDIT_WRITES) == KINDS["edit"] - KINDS["reorder"]


@pytest.mark.parametrize("role", ["item", "name"])
def test_a_filing_role_naming_an_undeclared_key_refuses(role: str) -> None:
    """Through `_key_reference_error`, so the message is the one `requires`
    and `sets` already give — one rule, and the refusal an operator has
    already read once."""
    document = filing(well_formed())
    document["transitions"]["pot-on"]["files"][role] = "cuttng"
    assert (
        f'transitions.pot-on.files.{role} names undeclared key "cuttng"'
        in shape_errors(document)
    )


def test_a_filing_role_naming_an_intrinsic_key_refuses_as_intrinsic() -> None:
    """The same helper's other arm, and the one that matters most here: the
    filed item's title is written by the filing itself."""
    document = filing(well_formed())
    document["transitions"]["pot-on"]["files"]["item"] = "title"
    assert (
        'transitions.pot-on.files.item names "title", which is intrinsic to '
        "every item rather than a declared key" in shape_errors(document)
    )


def test_one_key_holding_both_halves_of_the_provenance_refuses() -> None:
    """Two facts, two keys. A single key holding the carrier and the bullet is
    a value nothing can join on, which is the whole reason the pair is a
    pair."""
    document = filing(well_formed())
    document["transitions"]["pot-on"]["files"]["name"] = "batch"
    assert (
        'transitions.pot-on.files.item and transitions.pot-on.files.name both '
        'name "batch". One key holding both the carrier and the bullet is a '
        "value nothing can join on. Name a separate key for each"
        in shape_errors(document)
    )


def test_a_filing_with_no_keys_of_its_own_loads_clean() -> None:
    """`sets` is the one optional field, not a fourth role: a `files` table
    naming only the three roles is the shape this repo's own `plan.toml`
    has."""
    document = filing(well_formed())
    assert "sets" not in document["transitions"]["pot-on"]["files"]
    assert shape_errors(document) == []


def test_a_filing_that_sets_a_declared_key_loads_clean() -> None:
    document = filing(well_formed())
    document["transitions"]["pot-on"]["files"]["sets"] = ["cultivar"]
    assert shape_errors(document) == []


def test_sets_beside_files_refuses_and_names_files_sets() -> None:
    """**Which head does the key land on?** A transition-level `sets` on a
    verb that files would say nothing about it, and the run used to write the
    key onto the carrier without a word. The dissolve rule is the precedent:
    a field the verb's own halves make wrong refuses at load, by name."""
    document = filing(well_formed())
    document["transitions"]["pot-on"]["sets"] = ["cultivar"]
    assert (
        "transitions.pot-on.sets is set, and pot-on files an item. Say which "
        "head each key lands on: a key for the filed item goes in "
        "transitions.pot-on.files.sets, and pot-on writes none onto the item "
        "it moves" in shape_errors(document)
    )


@pytest.mark.parametrize("value", ["cultivar", ["cultivar", 3]])
def test_a_files_sets_that_is_not_a_list_of_strings_refuses(value: object) -> None:
    document = filing(well_formed())
    document["transitions"]["pot-on"]["files"]["sets"] = value
    assert (
        "transitions.pot-on.files.sets must be a list of strings"
        in shape_errors(document)
    )


def test_a_files_sets_naming_an_undeclared_key_refuses() -> None:
    """Through `_key_reference_error`, as the two roles are."""
    document = filing(well_formed())
    document["transitions"]["pot-on"]["files"]["sets"] = ["cultvar"]
    assert (
        'transitions.pot-on.files.sets names undeclared key "cultvar"'
        in shape_errors(document)
    )


def test_a_files_sets_naming_an_intrinsic_key_refuses_as_intrinsic() -> None:
    """The filed item's title comes from `--title` or the bullet."""
    document = filing(well_formed())
    document["transitions"]["pot-on"]["files"]["sets"] = ["title"]
    assert (
        'transitions.pot-on.files.sets names "title", which is intrinsic to '
        "every item rather than a declared key" in shape_errors(document)
    )


@pytest.mark.parametrize("role", ["item", "name"])
def test_a_files_sets_naming_a_provenance_key_refuses(role: str) -> None:
    """The tool writes both provenance keys itself, so naming one here would
    be a second writer of the same value."""
    document = filing(well_formed())
    files = document["transitions"]["pot-on"]["files"]
    files["sets"] = [files[role]]
    assert (
        f'transitions.pot-on.files.sets names "{files[role]}", which '
        f"transitions.pot-on.files.{role} names too. The tool writes that key "
        "onto the filed item itself, and a second writer could disagree with "
        f'it. Drop "{files[role]}" from transitions.pot-on.files.sets'
        in shape_errors(document)
    )


def test_a_files_sets_naming_its_own_transition_refuses() -> None:
    """`Reading` names the doc of every key the caller supplies, whichever
    head it lands on, so the own-name collision is the same one."""
    document = filing(well_formed())
    document["keys"]["pot-on"] = {"doc": "method.md#pot-on"}
    document["transitions"]["pot-on"]["files"]["sets"] = ["pot-on"]
    assert (
        'transitions.pot-on.files.sets names "pot-on", a key of its own name. '
        "The transition's pointer and the key's pointer share one line in "
        "Reading, so one would be lost. Rename the key, or rename the "
        "transition" in shape_errors(document)
    )


def test_a_state_nothing_files_into_loads_clean() -> None:
    """**Filing has no state half at all**, which is `dated`'s shape inverted:
    nothing about a state says items may be filed into it, so there is no
    inert half to refuse. `greenhouse` in `well_formed` is filed into by
    nothing and is a legitimate declaration."""
    assert shape_errors(well_formed()) == []


# --------------------------------------------------------------------------
# `first-number`: where a register begins
# --------------------------------------------------------------------------


def floored(document: dict, first: object) -> dict:
    """``well_formed`` with `orchard` numbered and its register declaring a floor."""
    document["states"]["orchard"].update(
        {
            "capabilities": ["queued", "numbered"],
            "archive": "orchard-archive.md",
            FIRST_NUMBER: first,
        }
    )
    return document


def test_a_numbered_state_declaring_a_floor_is_well_formed() -> None:
    """A consumer's cutover shape: a fresh archive whose register starts at 192
    because everything below it is recorded somewhere this tool never reads."""
    assert shape_errors(floored(well_formed(), 192)) == []


@pytest.mark.parametrize(
    "first",
    [pytest.param("192", id="string"), pytest.param(1.5, id="float"),
     pytest.param(True, id="bool")],
)
def test_a_floor_that_is_not_a_whole_number_refuses_by_name(first: object) -> None:
    """`numbered.errors`' and `queued`'s rule one field over, for their
    reason: the key is arithmetic, and a bool is an `int` in Python and is not
    a number here — `tomllib` reads `first-number = true` as one."""
    assert (
        f"states.orchard.{FIRST_NUMBER} holds {first!r}, which is not a whole "
        'number. A floor is compared as a number, and "10" sorts ahead of "9" '
        "when a number is read as text. Write the floor as a bare integer"
        in shape_errors(floored(well_formed(), first))
    )


@pytest.mark.parametrize("first", [0, -1])
def test_a_floor_below_one_refuses_by_name(first: int) -> None:
    """There is no section 0. The field moves where a register begins; it does
    not make one begin before the first number there is."""
    assert (
        f"states.orchard.{FIRST_NUMBER} is {first}, and a register begins at "
        "1 or above. The floor names the first number this state may hold, and "
        "there is no section 0" in shape_errors(floored(well_formed(), first))
    )


def test_a_floor_on_a_state_that_mints_no_number_refuses_by_name() -> None:
    """Exactly `archive`'s second arm: a bound on a register the state does
    not have is a field nothing reads."""
    document = well_formed()
    document["states"]["orchard"][FIRST_NUMBER] = 192
    assert (
        f"states.orchard.{FIRST_NUMBER} says where this state's register "
        'begins, and this state does not opt into "numbered". Nothing reads '
        'the floor this state names. Add "numbered" to '
        "states.orchard.capabilities, or drop the field"
        in shape_errors(document)
    )


def test_a_numbered_state_with_no_floor_loads_and_begins_at_one() -> None:
    """The asymmetry with `archive`, deliberately: an archive is a document
    that must exist to be read, and a floor is a bound with a correct default.
    Absence is the ordinary case and this repo's own declaration is it."""
    document = floored(well_formed(), 192)
    del document["states"]["orchard"][FIRST_NUMBER]
    assert shape_errors(document) == []
    declaration = load(FIXTURES / "plan.toml")
    assert declaration.states["orchard"].first_number == 1


def test_pointers_are_chased_only_once_the_shape_holds(tmp_path: Path) -> None:
    """`load` runs `shape_errors` first and reaches `pointer_errors` only on
    an empty result, and `_pointers` **relies** on that: it carries no type
    guards, because by then a table is a table and an entry is a table.

    This is the machine-checked reason those guards were safe to delete
    (10-6a, f24). Nothing else pinned the ordering, so a reorder would have
    brought the crash back silently — the f5 lesson inverted, where a guard
    was kept *because* a test pinned it.

    Three shape defects, one per deleted guard. Only the first is **loud** if
    the ordering is inverted — `"nope".items()` raises — and that is the one
    that gives this test its teeth; the other two would go quiet instead,
    reading a `doc` out of a string by substring, which is worse. All three
    are here so the contract is stated where it is relied on rather than only
    where it happens to bite.
    """
    for name in FIXTURE_FILES:
        (tmp_path / name).write_text((FIXTURES / name).read_text())
    written = (tmp_path / "plan.toml").read_text()

    defects = {
        # entries is not a table
        "states": '\nstates = "nope"\n',
        # an entry is not a table
        "states.orchard": '\n[states]\norchard = "nope"\n',
        # the identity table is not a table
        IDENTITY: f'\n{IDENTITY} = "nope"\n',
    }
    for where, replacement in defects.items():
        source = tmp_path / f"{where}.toml"
        source.write_text(replacement)
        with pytest.raises(Refusal) as raised:
            load(source)
        assert any(f"{where} must be a table" in one for one in raised.value.messages)

    assert load(tmp_path / "plan.toml").source == (tmp_path / "plan.toml").resolve()
    assert written


def test_a_declared_floor_reaches_the_state(tmp_path: Path) -> None:
    """The field is read off the declaration rather than recomputed, which is
    what the two call sites hand to `numbered`."""
    for name in FIXTURE_FILES:
        (tmp_path / name).write_text((FIXTURES / name).read_text())
    written = (tmp_path / "plan.toml").read_text()
    (tmp_path / "plan.toml").write_text(
        written.replace(
            'archive           = "orchard-archive.md"',
            'archive           = "orchard-archive.md"'
            f"\n{FIRST_NUMBER}      = 192",
        )
    )
    assert load(tmp_path / "plan.toml").states["orchard"].first_number == 192


# --------------------------------------------------------------------------
# `archives`: the transition half that files an entry
# --------------------------------------------------------------------------


def archiving(document: dict) -> dict:
    """``well_formed`` with `orchard` numbered, and a verb that files entries out."""
    document["states"]["orchard"].update(
        {
            "capabilities": ["queued", "numbered"],
            "archive": "orchard-archive.md",
        }
    )
    document["states"]["firewood"] = {
        "path": "firewood",
        "doc": "method.md#firewood",
    }
    document["transitions"]["grub-out"] = {
        "kind": "move",
        "doc": "method.md#grub-out",
        "help": "Give up on a tree.",
        "from": "orchard",
        "to": "firewood",
        "archives": True,
    }
    return document


def test_a_numbered_state_and_a_verb_that_files_entries_out_is_well_formed() -> None:
    assert shape_errors(archiving(well_formed())) == []


def test_a_transition_carries_whether_it_archives() -> None:
    """`claims`' and `mints`' field, read off the declaration the same way.
    The fixture's `grub-out` archives and `espalier`, which stays in the same
    state, does not, so the flag comes from the verb rather than from either
    state it names. Every way out of `orchard` archives, because the state is
    numbered."""
    declaration = load(FIXTURES / "plan.toml")
    assert declaration.transitions["grub-out"].archives
    assert not declaration.transitions["espalier"].archives


def test_an_archives_that_is_not_a_boolean_refuses() -> None:
    """`claims`' and `mints`' rule, for their reason: `archives = "false"` is
    truthy, so the spelling that looks safest is the one that silently files."""
    document = archiving(well_formed())
    document["transitions"]["grub-out"]["archives"] = "true"
    assert (
        "transitions.grub-out.archives must be true or false"
        in shape_errors(document)
    )


def test_archives_out_of_a_state_that_mints_no_number_refuses_by_name() -> None:
    """An entry's heading is `## <number>. <title>`, and a state that mints no
    number has nothing to name one by. It covers the archive document too: a
    numbered state with none already refuses, so one rule reaches both."""
    document = archiving(well_formed())
    document["states"]["orchard"]["capabilities"] = ["queued"]
    del document["states"]["orchard"]["archive"]
    assert (
        "transitions.grub-out.archives is true, and states.orchard does not "
        'name "numbered" in its capabilities. An archive entry is '
        "`## <number>. <title>`, and an item leaving orchard carries no "
        'number. Name "numbered" in states.orchard.capabilities, or drop the '
        "archives" in shape_errors(document)
    )


def test_archives_on_a_kind_that_stays_refuses_by_name() -> None:
    """The number is dropped on the way *out*. A verb that stays would file
    the number in the archive and leave the item carrying it as well — two
    claimants for one number. Only a move and a close take `archives`, and
    both leave, so the kind table is the whole rule."""
    document = archiving(well_formed())
    grub_out = document["transitions"]["grub-out"]
    grub_out.update(kind="edit", sets=["rootstock"])
    del grub_out["to"]
    assert (
        "transitions.grub-out.archives is set, and an edit does not take it "
        "(an edit takes claims, drops, from, refuses, requires, sets)"
        in shape_errors(document)
    )


def test_a_numbered_state_no_verb_archives_out_of_does_not_refuse() -> None:
    """**The asymmetry, pinned.** A `claimed` state nothing claims into and a
    `bulleted` state nothing mints into both refuse, because the capability
    could then never do anything. This one is different and must stay
    different: the `archive` field has a second reader — the register, which
    counts closed numbers whether or not a verb has ever written one — and an
    empty archive is a repo that has closed nothing. Refusing the shape would
    refuse a legitimate declaration."""
    document = archiving(well_formed())
    del document["transitions"]["grub-out"]
    assert shape_errors(document) == []


def test_a_move_out_of_a_numbered_state_that_does_not_archive_refuses() -> None:
    """**Every way out of a numbered state archives.** A move that does not
    drops the number with no entry, and the next mint refuses on the gap, far
    from the cause. If the item held the highest number, nothing refuses at
    all and the number is minted again. `archives = false` is the same verb
    written out. See docs/method.md#the-register"""
    for archives in (None, False):
        document = archiving(well_formed())
        grub_out = document["transitions"]["grub-out"]
        del grub_out["archives"]
        if archives is not None:
            grub_out["archives"] = archives
        assert shape_errors(document) == [
            "transitions.grub-out leaves states.orchard, which is numbered, and "
            "does not archive. The number it carries would be dropped with no "
            "entry, and the next mint would refuse on the gap. Write archives = "
            "true in transitions.grub-out"
        ]


def test_a_close_out_of_a_numbered_state_that_does_not_archive_refuses() -> None:
    """The consumer's case: a close takes the file away, and the number with
    it."""
    document = dissolving(well_formed())
    del document["transitions"]["grub-out"]["archives"]
    assert (
        "transitions.grub-out leaves states.orchard, which is numbered, and "
        "does not archive. The number it carries would be dropped with no "
        "entry, and the next mint would refuse on the gap. Write archives = "
        "true in transitions.grub-out"
    ) in shape_errors(document)


def test_a_merge_out_of_a_numbered_state_refuses_outright() -> None:
    """A merge cannot archive, so there is no line to add to it. The refusal
    names the two shapes that work instead."""
    document = archiving(well_formed())
    document["transitions"]["inarch"] = {
        "kind": "merge",
        "doc": "method.md#inarch",
        "help": "Graft trees into one.",
        "from": "orchard",
    }
    assert shape_errors(document) == [
        "transitions.inarch merges items out of states.orchard, which is "
        "numbered, and a merge cannot archive. The numbers the absorbed items "
        "carry would be dropped with no entry, and the next mint would refuse "
        'on the gap. Write kind = "close" with archives = true, or merge out of '
        "a state that numbers nothing"
    ]


def test_ways_out_of_a_state_that_numbers_nothing_need_no_archives() -> None:
    """The control. `transplant` moves into the numbered `orchard` out of the
    unnumbered `greenhouse`, and a close and a merge out of `greenhouse` take
    nothing a register counts."""
    document = archiving(well_formed())
    for name, kind in (("compost", "close"), ("inarch", "merge")):
        document["transitions"][name] = {
            "kind": kind,
            "doc": f"method.md#{name}",
            "help": "Out.",
            "from": "greenhouse",
        }
    assert shape_errors(document) == []


# --------------------------------------------------------------------------
# `dissolves`: the transition half that takes the file away
# --------------------------------------------------------------------------


def dissolving(document: dict) -> dict:
    """``archiving`` with `grub-out` turned into the shape that also deletes."""
    document = archiving(document)
    del document["transitions"]["grub-out"]["to"]
    document["transitions"]["grub-out"]["kind"] = "close"
    return document


def test_a_verb_that_archives_and_dissolves_is_well_formed() -> None:
    """Both halves on one verb, which is what `archive-plan` declares. Nothing
    ties them together and nothing keeps them apart."""
    assert shape_errors(dissolving(well_formed())) == []


def test_a_verb_that_dissolves_alone_is_well_formed() -> None:
    """**`dissolves` is not a rider on `archives`.** 5-3's `merge` dissolves an
    unnumbered item, which cannot archive at all, so a refusal tying the two
    together would make that declaration impossible to write."""
    document = dissolving(well_formed())
    del document["transitions"]["grub-out"]["archives"]
    document["transitions"]["grub-out"]["from"] = "greenhouse"
    assert shape_errors(document) == []


def test_a_transition_carries_whether_it_dissolves() -> None:
    """The fixture's two shapes, read off the declaration: `fell` archives and
    dissolves, `compost` only dissolves, and `grub-out` — which archives out of
    the same state `fell` does — dissolves nothing."""
    declaration = load(FIXTURES / "plan.toml")
    assert declaration.transitions["fell"].kind == "close"
    assert declaration.transitions["fell"].archives
    assert declaration.transitions["compost"].kind == "close"
    assert not declaration.transitions["compost"].archives
    assert declaration.transitions["grub-out"].kind == "move"


def test_a_dissolving_verb_names_no_destination() -> None:
    """`to` is `None` rather than a state, which is what lets the executor ask
    "is there a destination?" instead of every arm re-deriving it."""
    declaration = load(FIXTURES / "plan.toml")
    assert declaration.transitions["fell"].to is None
    assert declaration.transitions["grub-out"].to == "firewood"


def test_a_dissolving_verb_leaves_its_source_state() -> None:
    """`_leaves` is true of a `None` destination, so a dissolving verb is
    graded like any other leaving verb's. It is pinned because nothing else
    would notice if it stopped being true."""
    declaration = load(FIXTURES / "plan.toml")
    assert declaration.transitions["fell"].leaves
    assert declaration.transitions["compost"].leaves


def test_a_move_with_no_to_refuses() -> None:
    """A move says where the item goes. With no `to` it has not said what
    it does with the item."""
    document = archiving(well_formed())
    del document["transitions"]["grub-out"]["to"]
    assert "transitions.grub-out has no to" in shape_errors(document)


@pytest.mark.parametrize(
    "field, value",
    [
        ("sets", ["rootstock"]),
        ("drops", ["tag"]),
        ("marks", "taken"),
        ("claims", True),
    ],
)
def test_a_field_that_writes_the_item_refuses_on_a_close(
    field: str, value: object
) -> None:
    """The kind table, not a rule per field: each of these would write, keep
    or grade something on a file that is about to be gone."""
    document = dissolving(well_formed())
    document["transitions"]["grub-out"][field] = value
    assert (
        f"transitions.grub-out.{field} is set, and a close does not take it "
        "(a close takes archives, from, refuses, requires)"
        in shape_errors(document)
    )


@pytest.mark.parametrize("field", ["requires", "refuses", "archives"])
def test_what_grades_or_records_survives_beside_dissolves(field: str) -> None:
    """The complement of the arm above, and the reason it is not five fields.
    `requires` and `refuses` read the head *before* it goes; `archives` exists
    precisely so something outlives the file."""
    document = dissolving(well_formed())
    document["transitions"]["grub-out"][field] = (
        {"cultivar": ["hybrid"]} if field == "refuses"
        else True if field == "archives"
        else ["cultivar"]
    )
    assert shape_errors(document) == []


# --------------------------------------------------------------------------
# `absorbs`: the half that points the edges at a survivor
# --------------------------------------------------------------------------


def absorbing(document: dict) -> dict:
    """``dissolving`` with `grub-out` turned into `merge`'s shape.

    Out of `greenhouse` and with no `archives`, because that is what an
    absorbing verb is: the unnumbered state is the one it is safe to delete
    from.
    """
    document = dissolving(document)
    del document["transitions"]["grub-out"]["archives"]
    document["transitions"]["grub-out"]["from"] = "greenhouse"
    document["transitions"]["grub-out"]["kind"] = "merge"
    return document


def test_a_verb_that_dissolves_and_absorbs_is_well_formed() -> None:
    """Both halves of the *other* pair, which is what `merge` declares."""
    assert shape_errors(absorbing(well_formed())) == []


def test_a_transition_carries_whether_it_absorbs() -> None:
    """The fixture's shapes read off the declaration: `inarch` absorbs, and
    the three verbs that dissolve or archive without absorbing do not."""
    declaration = load(FIXTURES / "plan.toml")
    assert declaration.transitions["inarch"].kind == "merge"
    assert declaration.transitions["compost"].kind == "close"
    assert declaration.transitions["fell"].kind == "close"


def test_a_dissolving_verb_that_archives_out_of_an_unnumbered_state_refuses(
) -> None:
    """The `to`-less shape must not slip past `_archiving_errors`. Skipping it
    there would let this load and fail at the *run* instead, which is the
    polarity this repo refuses."""
    document = dissolving(well_formed())
    document["transitions"]["grub-out"]["from"] = "greenhouse"
    assert (
        "transitions.grub-out.archives is true, and states.greenhouse does "
        'not name "numbered" in its capabilities.' in "\n".join(shape_errors(document))
    )


def test_a_numbered_state_with_no_archive_refuses_by_name() -> None:
    """An item's file is deleted when it closes, so its archive heading is the
    only thing left saying its number is taken. A state that mints with no
    archive to read would hand the next item a number a closed one holds."""
    document = well_formed()
    document["states"]["orchard"]["capabilities"] = ["queued", "numbered"]
    assert (
        'states.orchard.capabilities names "numbered", and this state declares '
        "no archive. An item's file is deleted when it closes, so the next "
        "number would be minted over a closed item's. Add "
        "states.orchard.archive, or drop the capability"
        in shape_errors(document)
    )


def test_an_archive_on_a_state_that_mints_nothing_refuses_by_name() -> None:
    """The other end of the same rule, and the shape 4-2's cursor and 4-4's
    `claims` both already refuse: a field nothing reads is a declaration that
    silently does nothing."""
    document = well_formed()
    document["states"]["orchard"]["archive"] = "archive.md"
    assert (
        "states.orchard.archive names where closed items are recorded, and "
        'this state does not opt into "numbered". Nothing reads the archive '
        'this state names. Add "numbered" to states.orchard.capabilities, or '
        "drop the field" in shape_errors(document)
    )


def test_an_archive_that_is_not_a_string_refuses() -> None:
    document = well_formed()
    document["states"]["orchard"]["archive"] = ["archive.md"]
    assert "states.orchard.archive must be a string" in shape_errors(document)


def test_both_halves_of_numbered_together_are_well_formed() -> None:
    document = well_formed()
    document["states"]["orchard"]["capabilities"] = ["queued", "numbered"]
    document["states"]["orchard"]["archive"] = "archive.md"
    assert shape_errors(document) == []


def test_an_archive_the_repo_does_not_ship_refuses_at_every_invocation(
    tmp_path: Path,
) -> None:
    """A filesystem question, so it is `pointer_errors`' half rather than the
    shape's — graded the way a `doc =` pointer is, at load. A state that opts
    in cannot be lying about where its closed items are recorded."""
    document = well_formed()
    document["states"]["orchard"]["capabilities"] = ["numbered"]
    document["states"]["orchard"]["archive"] = "nowhere.md"
    # Filtered by the field's own prefix: the tmp directory's name contains
    # "archive" too, and the `doc =` pointers refuse in this bare tmp tree.
    (error,) = [
        one
        for one in pointer_errors(document, tmp_path)
        if one.startswith("states.orchard.archive")
    ]
    assert "names nowhere.md, which" in error
    assert "which does not exist" in error


def test_an_empty_archive_file_is_a_repo_that_has_closed_nothing(
    tmp_path: Path,
) -> None:
    """The bootstrap, and the reason existence is what is checked rather than
    content: a consumer's first run touches the file and mints 1."""
    document = well_formed()
    document["states"]["orchard"]["capabilities"] = ["numbered"]
    document["states"]["orchard"]["archive"] = "archive.md"
    (tmp_path / "archive.md").write_text("")
    assert not [
        one
        for one in pointer_errors(document, tmp_path)
        if one.startswith("states.orchard.archive")
    ]


def test_the_register_key_is_carried_and_never_declared() -> None:
    """`number` is the tool's, like `position`: minted on entry and dropped on
    exit, so a declaration naming it would be a second spelling of that rule."""
    declaration = load(FIXTURES / "plan.toml")
    assert "number" in declaration.carried
    assert "number" not in declaration.keys


def test_declaring_the_register_key_refuses_by_name() -> None:
    document = well_formed()
    document["keys"]["number"] = {"doc": "method.md#cultivar"}
    assert [error for error in shape_errors(document) if "keys.number" in error] == [
        'keys.number redeclares "number", which the numbered capability gives '
        "an item in a state that opts into it. The numbered capability writes "
        "the key on the way in and drops it on the way out. Drop keys.number"
    ]


def test_a_transition_setting_a_key_of_its_own_name_refuses_by_name() -> None:
    """The contract's Reading block is keyed by name, so the verb's own
    pointer and the key's would share one line and the key's would win."""
    document = well_formed()
    document["keys"]["transplant"] = {"doc": "method.md#transplant"}
    document["transitions"]["transplant"]["sets"] = ["transplant"]
    assert [
        error for error in shape_errors(document) if error.startswith("transitions.")
    ] == [
        'transitions.transplant.sets names "transplant", a key of its own '
        "name. The transition's pointer and the key's pointer share one line "
        "in Reading, so one would be lost. Rename the key, or rename the "
        "transition"
    ]


def test_a_transition_setting_a_key_of_another_name_loads_clean() -> None:
    """So the refusal above is the collision, and not `sets` itself."""
    document = well_formed()
    document["keys"]["scion"] = {"doc": "method.md#scion"}
    document["transitions"]["transplant"]["sets"] = ["rootstock", "scion"]
    assert shape_errors(document) == []


def test_the_shipped_declaration_and_the_fixture_both_still_load() -> None:
    """The refusal is a real rule, so this says neither tree tripped it."""
    for path in (REPO / "plan.toml", FIXTURES / "plan.toml"):
        assert load(path).transitions


@pytest.mark.parametrize("field", ["requires", "sets", "drops"])
def test_a_transition_naming_the_register_key_refuses_by_name(field: str) -> None:
    """The generic refusal reads `CAPABILITY_KEYS` rather than naming a key,
    so the second capability cost it no line at all — this is what says so."""
    document = well_formed()
    document["transitions"]["transplant"][field] = ["number"]
    assert (
        f'transitions.transplant.{field} names "number", which the numbered '
        "capability writes on entry and drops on exit by itself. Naming the "
        "key here would be a second spelling that can disagree with the "
        f'capability. Drop "number" from transitions.transplant.{field}'
        in shape_errors(document)
    )


def test_unknown_capability_refuses_by_name() -> None:
    """`sized` is nobody's yet, so it is still refused by name. The example
    moved off `numbered` when 4-5 implemented it, off `bulleted` when 4-5a
    did and off `dated` when 3-3 did — which is the discipline working, not a
    test going stale."""
    document = well_formed()
    document["states"]["orchard"]["capabilities"] = ["sized"]
    assert (
        'states.orchard.capabilities names unknown capability "sized" '
        "(known: queued, claimed, numbered, bulleted)"
        in shape_errors(document)
    )


@pytest.mark.parametrize("name", ["Greenhouse", "green_house", "2nd-bed", "-bed", "béd", ""])
@pytest.mark.parametrize("table", ["states", "keys", "transitions"])
def test_a_name_outside_the_grammar_refuses(table: str, name: str) -> None:
    document = well_formed()
    document[table][name] = dict(next(iter(document[table].values())))
    assert any(
        error.startswith(f"{table}.{name} is not a usable name")
        for error in shape_errors(document)
    )


def test_values_not_a_list_of_strings_refuses_once() -> None:
    """One complaint per defect: the `refuses` arm that reads `values` is quiet."""
    document = well_formed()
    document["keys"]["cultivar"]["values"] = ["heirloom", 3]
    assert shape_errors(document) == ["keys.cultivar.values must be a list of strings"]


def test_empty_values_is_a_closed_set_with_nothing_in_it() -> None:
    """No special case: `refuses` against it simply has nothing to match."""
    document = well_formed()
    document["keys"]["cultivar"]["values"] = []
    document["transitions"]["transplant"]["refuses"] = {"cultivar": ["hybrid"]}
    assert shape_errors(document) == [
        'transitions.transplant.refuses.cultivar names "hybrid", '
        "which is not a declared value of keys.cultivar"
    ]


# --------------------------------------------------------------------------
# list-valued: a key whose head value is several
# --------------------------------------------------------------------------
#
# The field the fixture's `pest` declares. It answers a different question
# from `values`, which is the closed set a key may hold: this one says how
# many of them the head carries. The refusals below are the two that would
# otherwise be silent — a `list-valued = "true"` that reads as truthy, and a
# field where the tool itself puts or reads exactly one value.


def list_valued(document: dict) -> dict:
    """`well_formed()` with `rootstock` declared list-valued."""
    document["keys"]["rootstock"]["list-valued"] = True
    return document


def test_a_list_valued_key_is_well_formed_and_carries_the_flag(
    tmp_path: Path,
) -> None:
    """Declaring it is legal, and it reaches the loaded `Key`: the option
    repeats, the executor grades the shape, and both read the flag."""
    assert shape_errors(list_valued(well_formed())) == []
    for name in FIXTURE_FILES:
        (tmp_path / name).write_text((FIXTURES / name).read_text())
    declaration = load(tmp_path / "plan.toml")
    assert declaration.keys["pest"].list_valued is True
    assert declaration.keys["cultivar"].list_valued is False


def test_a_list_valued_flag_that_is_not_a_boolean_refuses() -> None:
    """`claims`' and `mints`' rule, one table over and for their reason:
    `list-valued = "true"` is truthy, so the spelling that looks safest is the
    one that would silently write a scalar into a key meant to hold several."""
    document = well_formed()
    document["keys"]["rootstock"]["list-valued"] = "true"
    assert "keys.rootstock.list-valued must be true or false" in shape_errors(document)



#: Every field where the tool itself puts or reads exactly one value, with
#: where it is declared in the fixture. Graded over the fixture rather than
#: over `well_formed()` because all six are declared there already: the two
#: cursor fields on `orchard`, the owner field on `propagator`, and the
#: two filing roles on `line-out`.
SINGLE_VALUE = [
    ("states.orchard", subphase.CURSOR),
    ("states.orchard", subphase.STATUS),
    ("states.propagator", OPENED_FOR),
    ("transitions.line-out.files", "item"),
    ("transitions.line-out.files", "name"),
]


def fixture_document() -> dict:
    return tomllib.loads((FIXTURES / "plan.toml").read_text())


@pytest.mark.parametrize(("where", "field"), SINGLE_VALUE)
def test_a_single_value_field_naming_a_list_valued_key_refuses(
    where: str, field: str
) -> None:
    """One rule over a roster rather than six rules beside six fields. The
    cursor half already refused at runtime, loudly and unreadably; the filing
    roles are the silent half — the run stamps a bare slug into a key declared
    to hold a list and nothing says a word."""
    document = fixture_document()
    assert shape_errors(document) == [], "the fixture loads before it is edited"
    table = document
    for step in where.split("."):
        table = table[step]
    table[field] = "pest"
    assert shape_errors(document) == [
        f'{where}.{field} names "pest", which is list-valued. The tool puts '
        "or reads exactly one value here, and a list-valued key holds "
        "several. Name a key that is not list-valued"
    ]


def test_dependencies_naming_a_list_valued_key_loads_clean() -> None:
    """The deliberate exception, and the reason is `depends`' own: a bare
    string is one edge and a list is many, so a list-valued dependency key is
    the case that already works rather than the one that breaks."""
    document = fixture_document()
    document["states"]["orchard"][depends.FIELD] = "pest"
    assert shape_errors(document) == []


# --------------------------------------------------------------------------
# `sets` as a table: options and fixed values
# --------------------------------------------------------------------------
#
# One table holds both: `true` takes the key as an option, as `refuses` reads
# `true` as any value, and anything else is the value the run writes of its
# own. The list form is shorthand for every key `true`.


def stamping(document: dict, **sets: object) -> dict:
    """`well_formed()` with `transplant`'s `sets` written as the table `sets`."""
    document["transitions"]["transplant"]["sets"] = sets
    return document


def test_a_table_of_options_and_fixed_values_is_well_formed() -> None:
    document = stamping(well_formed(), rootstock=True, cultivar="heirloom")
    assert shape_errors(document) == []
    document = stamping(list_valued(well_formed()), rootstock=["m9", "{today}"])
    assert shape_errors(document) == []


@pytest.mark.parametrize(
    ("value", "says"),
    [
        (
            False,
            "transitions.transplant.sets.rootstock is false, which writes "
            "nothing. Write true for an option, or the value to write",
        ),
        (
            "",
            "transitions.transplant.sets.rootstock must be true, or a non-empty "
            "string, because keys.rootstock holds one value",
        ),
        (
            ["m9"],
            "transitions.transplant.sets.rootstock must be true, or a non-empty "
            "string, because keys.rootstock holds one value",
        ),
        (
            3,
            "transitions.transplant.sets.rootstock must be true, or a non-empty "
            "string, because keys.rootstock holds one value",
        ),
        (
            "{tomorrow}",
            'transitions.transplant.sets.rootstock is "{tomorrow}", and {today} '
            "is the one substitution a fixed value takes. Drop the other braces",
        ),
        (
            "m9 {today}}",
            'transitions.transplant.sets.rootstock is "m9 {today}}", and '
            "{today} is the one substitution a fixed value takes. Drop the "
            "other braces",
        ),
    ],
)
def test_a_fixed_value_a_single_valued_key_cannot_hold_refuses(
    value: object, says: str
) -> None:
    assert shape_errors(stamping(well_formed(), rootstock=value)) == [says]


@pytest.mark.parametrize("value", ["m9", [], ["m9", ""]])
def test_a_fixed_value_a_list_valued_key_cannot_hold_refuses(value: object) -> None:
    """A string given to a list-valued key, and an empty list or an empty
    entry, which would write a key that carries nothing."""
    assert shape_errors(stamping(list_valued(well_formed()), rootstock=value)) == [
        "transitions.transplant.sets.rootstock must be true, or a non-empty "
        "list of non-empty strings, because keys.rootstock is list-valued"
    ]


def test_a_fixed_value_outside_the_closed_set_refuses() -> None:
    assert shape_errors(stamping(well_formed(), cultivar="grafted")) == [
        'transitions.transplant.sets.cultivar names "grafted", which is not a '
        "declared value of keys.cultivar"
    ]


def test_a_table_key_is_graded_as_a_list_entry_is() -> None:
    assert shape_errors(stamping(well_formed(), title="Tree")) == [
        'transitions.transplant.sets names "title", which is intrinsic to every '
        "item rather than a declared key"
    ]
    assert shape_errors(stamping(well_formed(), graft=True)) == [
        'transitions.transplant.sets names undeclared key "graft"'
    ]


def test_sets_that_is_neither_a_list_nor_a_table_refuses() -> None:
    document = well_formed()
    document["transitions"]["transplant"]["sets"] = "rootstock"
    assert shape_errors(document) == [
        "transitions.transplant.sets must be a list of strings, or a table of "
        "key = true or key = the value to write"
    ]


def test_the_list_form_is_the_table_with_every_key_true(tmp_path: Path) -> None:
    """Shorthand, so no `plan.toml` written before the table changes."""
    loaded = []
    for sets in ('["rootstock"]', "{ rootstock = true }"):
        source = tmp_path / "plan.toml"
        source.write_text(
            '[states.greenhouse]\n\n[states.orchard]\n\n'
            "[keys.rootstock]\n\n"
            '[transitions.transplant]\nkind = "move"\nfrom = "greenhouse"\n'
            f'to = "orchard"\nsets = {sets}\n'
        )
        loaded.append(load(source).transitions["transplant"])
    assert loaded[0] == loaded[1]
    assert loaded[0].sets == ("rootstock",) and dict(loaded[0].fixed) == {}


def test_a_table_loads_its_options_and_its_fixed_values_apart(
    tmp_path: Path,
) -> None:
    """`sets` keeps its meaning, the option keys, and `fixed` holds the rest as
    declared, `{today}` not yet substituted. `lands` is both."""
    source = tmp_path / "plan.toml"
    source.write_text(
        '[states.greenhouse]\n\n[states.orchard]\n\n'
        '[keys.rootstock]\n\n[keys.planted]\n\n'
        '[keys.cultivar]\nvalues = ["heirloom", "hybrid"]\n\n'
        '[transitions.transplant]\nkind = "move"\nfrom = "greenhouse"\n'
        'to = "orchard"\nrequires = ["rootstock"]\n'
        'sets = { cultivar = "hybrid", rootstock = true, planted = "{today}" }\n'
    )
    transplant = load(source).transitions["transplant"]
    assert transplant.sets == ("rootstock",)
    assert dict(transplant.fixed) == {"cultivar": "hybrid", "planted": "{today}"}
    assert transplant.lands == ("rootstock", "cultivar", "planted")


# --------------------------------------------------------------------------
# Whether a verb ends the state it starts in
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "leaves"),
    [("bed-out", True), ("tend", False), ("pot-up", False)],
)
def test_a_transition_knows_whether_it_ends_the_state_it_is_in(
    name: str, leaves: bool
) -> None:
    """One predicate, so the validator and the executor cannot disagree about
    which verbs end a state: `bed-out` leaves the bench, `tend` writes in
    place, and `pot-up` has no state to leave."""
    assert load(FIXTURES / "plan.toml").transitions[name].leaves is leaves


# --------------------------------------------------------------------------
# `[identity]`: who a session is, declared rather than compiled in
# --------------------------------------------------------------------------
#
# The table is here rather than in `test_claim.py` because these are defects
# in a *declaration*, and this is the refusal table for one. What the tool
# does with a valid `[identity]` — reading it, probing it, owning a record —
# is `test_claim.py`.


def with_identity(**fields: object) -> dict:
    document = well_formed()
    document["identity"] = {"pid": ["GREENHOUSE_PID"], **fields}
    return document


def test_a_well_formed_identity_has_no_errors() -> None:
    assert shape_errors(with_identity(doc="method.md#the-identity")) == []


def test_no_identity_table_is_not_an_error() -> None:
    """There is no default and no requirement: an absent `[identity]` means
    no identity is available. Whether a `claimed` state may be declared
    without one is 2-2's refusal to write, not this one's."""
    assert "identity" not in well_formed()
    assert shape_errors(well_formed()) == []


def test_an_unknown_identity_field_refuses_by_name() -> None:
    document = with_identity(session=["GREENHOUSE_SESSION"])
    assert (
        "identity.session is not a session identity field"
        in shape_errors(document)
    )


def test_an_identity_that_is_not_a_table_refuses() -> None:
    document = well_formed()
    document["identity"] = "GREENHOUSE_PID"
    assert "identity must be a table" in shape_errors(document)


def test_an_identity_with_no_pid_refuses() -> None:
    document = well_formed()
    document["identity"] = {"doc": "method.md#the-identity"}
    assert any(
        error.startswith("identity has no pid") for error in shape_errors(document)
    )


@pytest.mark.parametrize("pid", ["GREENHOUSE_PID", 4213, ["GREENHOUSE_PID", 4213]])
def test_a_pid_that_is_not_a_list_of_strings_refuses(pid: object) -> None:
    """A bare string is the one to watch: TOML would take it happily, and the
    tool would then iterate its characters."""
    document = well_formed()
    document["identity"] = {"pid": pid}
    assert "identity.pid must be a list of strings" in shape_errors(document)


def test_an_empty_pid_list_refuses_rather_than_meaning_no_identity() -> None:
    """An empty list says "read the pid from none of these", which no name
    could ever satisfy. Dropping the table is how you say there is none."""
    document = well_formed()
    document["identity"] = {"pid": []}
    assert any("identity.pid is empty" in error for error in shape_errors(document))


def test_a_name_declared_twice_refuses_by_name() -> None:
    """The list is ordered and the first name that is set wins, so a repeat is
    a second answer to a question the first one already answered."""
    document = well_formed()
    document["identity"] = {"pid": ["GREENHOUSE_PID", "SPROUT_PID", "GREENHOUSE_PID"]}
    errors = shape_errors(document)
    assert len(errors) == 1
    assert 'identity.pid names "GREENHOUSE_PID" twice' in errors[0]


def test_an_identity_doc_that_is_not_a_string_refuses() -> None:
    document = with_identity(doc=["method.md#the-identity"])
    assert "identity.doc must be a string" in shape_errors(document)


def test_the_identity_doc_is_graded_like_every_other_pointer() -> None:
    """At every invocation, and by name: nothing in the tool may cite a
    document the repo does not ship."""
    document = with_identity(doc="method.md#no-such-heading")
    assert pointer_errors(document, FIXTURES) == [
        'identity.doc names anchor "#no-such-heading", '
        "which is not a heading in method.md"
    ]


def test_a_loaded_declaration_carries_the_declared_names_in_order() -> None:
    declaration = load(FIXTURES / "plan.toml")
    assert declaration.pid_names == ("GREENHOUSE_PID", "SPROUT_PID")


# --------------------------------------------------------------------------
# What something simpler replaced, refused by name (31-1)
# --------------------------------------------------------------------------


def test_a_templates_table_refuses_naming_what_replaces_it() -> None:
    """A template copied a document into a new item. `--body - < FILE` does
    the same with no declaration at all, so the table refuses and says so."""
    document = well_formed()
    document["templates"] = {"hardwood": {"doc": "hardwood-cuttings.md"}}
    assert (
        "templates is no longer a plan.toml table. Copy a document into a new "
        "item's body with `--body - < FILE`, and drop the table"
    ) in shape_errors(document)


@pytest.mark.parametrize("value", [True, False])
def test_seeds_refuses_naming_what_replaces_it(value: bool) -> None:
    """Presence is what is graded, as for every field the tool no longer
    reads: `seeds = false` says something about a transition that cannot be
    true of it any more."""
    document = well_formed()
    document["transitions"]["sprout"]["seeds"] = value
    assert (
        "transitions.sprout.seeds is no longer a transition field. Copy a "
        "document into the new item's body with `--body - < FILE`, and drop "
        "the seeds"
    ) in shape_errors(document)


@pytest.mark.parametrize(
    ("field", "value", "said"),
    [
        (
            "policy",
            "method.md#transplant",
            "Link the procedure from the section the transition's doc names, "
            "and drop the policy",
        ),
        (
            "carries",
            True,
            "A merge always appends the absorbed bodies to the survivor. Drop "
            "the carries",
        ),
    ],
)
def test_a_field_31_2_folded_away_refuses_naming_what_replaces_it(
    field: str, value: object, said: str
) -> None:
    """31-2: one pointer per transition, and a merge that always carries."""
    document = well_formed()
    document["transitions"]["transplant"][field] = value
    assert (
        f"transitions.transplant.{field} is no longer a transition field. {said}"
    ) in shape_errors(document)


def test_dated_refuses_naming_what_replaces_it() -> None:
    document = well_formed()
    document["states"]["greenhouse"]["capabilities"] = ["dated"]
    assert (
        'states.greenhouse.capabilities names "dated", which is no longer a '
        "capability. Every row carries stale-days whenever the tree is in "
        "git, with nothing to switch on. Drop it"
    ) in shape_errors(document)


# --------------------------------------------------------------------------
# Pointers
# --------------------------------------------------------------------------


def test_a_valid_pointer_has_no_errors() -> None:
    assert pointer_errors(well_formed(), FIXTURES) == []


def test_a_path_outside_the_root_is_named_as_given(tmp_path: Path) -> None:
    """A message names a file the way a row does, from the folder holding
    plan.toml. A path outside it has no such form, so it is named as given.
    See docs/method.md#the-listing"""
    root = tmp_path / "tree"
    assert named(root / "greenhouse" / "x.md", root) == "greenhouse/x.md"
    assert named(Path("/elsewhere/x.md"), root) == "/elsewhere/x.md"


def test_a_root_reached_through_a_symlink_still_names_from_the_root(
    tmp_path: Path,
) -> None:
    """The case `state_at` resolves for: a `/tmp` that is itself a symlink."""
    real = tmp_path / "real"
    (real / "greenhouse").mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(real)
    assert named(real / "greenhouse" / "x.md", link) == "greenhouse/x.md"
    assert named(link / "greenhouse" / "x.md", real) == "greenhouse/x.md"


def test_a_missing_doc_file_refuses_naming_the_path_tried() -> None:
    document = well_formed()
    document["keys"]["cultivar"]["doc"] = "nowhere.md#cultivar"
    (error,) = pointer_errors(document, FIXTURES)
    assert error == "keys.cultivar.doc names nowhere.md, which does not exist"


def test_a_missing_heading_refuses_naming_the_anchor() -> None:
    document = well_formed()
    document["keys"]["cultivar"]["doc"] = "method.md#no-such-heading"
    (error,) = pointer_errors(document, FIXTURES)
    assert (
        error == 'keys.cultivar.doc names anchor "#no-such-heading", '
        "which is not a heading in method.md"
    )


def test_a_heading_inside_a_code_fence_is_not_a_heading() -> None:
    document = well_formed()
    document["keys"]["cultivar"]["doc"] = "method.md#fenced-not-a-heading"
    assert pointer_errors(document, FIXTURES) != []


@pytest.mark.parametrize("pointer", ["method.md", "#cultivar", "method.md#"])
def test_a_pointer_with_no_anchor_refuses(pointer: str) -> None:
    document = well_formed()
    document["keys"]["cultivar"]["doc"] = pointer
    assert pointer_errors(document, FIXTURES) == [
        f'keys.cultivar.doc is "{pointer}", which names no #heading'
    ]


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------


def test_no_plan_toml_anywhere_refuses_naming_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(PLAN_TOML_ENV, raising=False)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(Refusal) as raised:
        load()
    assert str(tmp_path) in str(raised.value)
    assert "plan.toml" in str(raised.value)


def test_plan_toml_is_found_by_walking_up_from_a_subdirectory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(PLAN_TOML_ENV, raising=False)
    for name in FIXTURE_FILES:
        (tmp_path / name).write_text((FIXTURES / name).read_text())
    deep = tmp_path / "one" / "two"
    deep.mkdir(parents=True)
    monkeypatch.chdir(deep)

    declaration = load()

    assert declaration.source == (tmp_path / "plan.toml").resolve()


def test_the_env_override_does_not_fall_back_when_it_names_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A typo'd override must refuse, not silently grade against another file."""
    monkeypatch.chdir(REPO)  # a real plan.toml sits right here to fall back to
    missing = tmp_path / "typo.toml"
    monkeypatch.setenv(PLAN_TOML_ENV, str(missing))

    with pytest.raises(Refusal) as raised:
        load()

    message = str(raised.value)
    assert str(missing) in message
    assert str(REPO / "plan.toml") not in message


def test_a_refusal_names_the_file_it_read_not_the_default_spelling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    malformed = tmp_path / "elsewhere.toml"
    malformed.write_text("states = [\n")
    monkeypatch.setenv(PLAN_TOML_ENV, str(malformed))

    with pytest.raises(Refusal) as raised:
        load()

    assert str(malformed.resolve()) in str(raised.value)


def test_an_empty_env_override_still_does_not_fall_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """It fails the existence check like any other path; no special case."""
    monkeypatch.chdir(REPO)
    monkeypatch.setenv(PLAN_TOML_ENV, "")
    with pytest.raises(Refusal) as raised:
        load()
    assert PLAN_TOML_ENV in str(raised.value)


# --------------------------------------------------------------------------
# Order
# --------------------------------------------------------------------------


def test_transitions_iterate_in_toml_document_order() -> None:
    """1-3 registers subcommands from this order, so it is not incidental."""
    declaration = load(FIXTURES / "plan.toml")
    assert list(declaration.transitions) == [
        "transplant",
        "sprout",
        "harvest",
        "pot-up",
        "bench",
        "tend",
        "bed-out",
        "graft-on",
        "respace",
        "espalier",
        "strike",
        "mist",
        "pot-on",
        "line-out",
        "ripen",
        "thin",
        "grub-out",
        "fell",
        "compost",
        "inarch",
        "relabel",
        "relabel-batch",
        "relabel-pot",
    ]
    assert list(declaration.transitions) != sorted(declaration.transitions)


def test_a_states_path_is_carried_through_verbatim() -> None:
    declaration = load(FIXTURES / "plan.toml")
    assert declaration.states["orchard"].path == "orchard"


def test_the_next_sub_phase_field_is_carried_where_a_state_counts() -> None:
    """`--has` and `--lacks` reach what a row carries, so a body-derived field
    that no filter could name would be a fact you have to read every line to
    find."""
    declaration = load(FIXTURES / "plan.toml")
    assert declaration.counts_sub_phases
    assert subphase.NEXT in declaration.carried
    assert subphase.NEXT not in declaration.keys


def test_nothing_is_carried_for_a_declaration_that_counts_no_sub_phases() -> None:
    """Corpus-independent, and declaration-dependent: a workflow with no
    counted state has no such field on a row and none in its filters."""
    plain = Declaration(
        source=FIXTURES / "plan.toml",
        root=FIXTURES,
        states={"greenhouse": State(name="greenhouse", path="greenhouse")},
        keys={},
        transitions={},
    )
    assert not plain.counts_sub_phases
    assert subphase.NEXT not in plain.carried


# --------------------------------------------------------------------------
# The operator contract
# --------------------------------------------------------------------------


def test_main_returns_zero_on_a_good_declaration() -> None:
    assert main([]) == 0


def test_main_returns_two_on_a_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    malformed = tmp_path / "plan.toml"
    malformed.write_text("states = [\n")
    monkeypatch.setenv(PLAN_TOML_ENV, str(malformed))

    assert main([]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("ERROR: ")


def test_the_console_script_refuses_a_malformed_plan_toml(tmp_path: Path) -> None:
    """The one subprocess test: what an operator actually sees."""
    malformed = tmp_path / "plan.toml"
    malformed.write_text("states = [\n")
    environment = {**os.environ, PLAN_TOML_ENV: str(malformed)}

    result = subprocess.run(
        ["fileplan"], capture_output=True, text=True, env=environment
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "Traceback" not in result.stderr
    lines = [line for line in result.stderr.splitlines() if line.strip()]
    assert len(lines) == 1
    assert lines[0].startswith("ERROR: ")
    assert str(malformed.resolve()) in lines[0]


# --------------------------------------------------------------------------
# Controls (mutation-checked)
# --------------------------------------------------------------------------


def test_the_suite_reads_the_fixture_not_the_repos_own_plan_toml() -> None:
    declaration = load()
    assert set(CONTROLS) <= (
        set(declaration.states) | set(declaration.transitions) | set(declaration.keys)
    )


def test_the_control_names_appear_nowhere_in_the_tool_or_the_repos_declaration() -> None:
    """If the loader were secretly specific to this repo's vocabulary, or the
    suite were secretly reading the repo's file, this is what would fail."""
    haystack = (REPO / "plan.toml").read_text()
    haystack += "\n".join(
        source.read_text() for source in (REPO / "src").rglob("*.py")
    )
    for control in CONTROLS:
        assert control not in haystack


def test_the_repos_own_plan_toml_loads_clean() -> None:
    declaration = load(REPO / "plan.toml")
    assert set(declaration.states) == {
        "someday-maybe",
        "plan",
        "abandoned",
        "carrier",
    }
    assert list(declaration.transitions) == [
        "idea",
        "queue",
        "requeue",
        "retitle",
        "retitle-idea",
        "decompose",
        "work",
        "finish",
        "skip",
        "decline",
        "discard",
        "archive-plan",
        "merge",
        "investigate",
        "note",
        "fix-it",
        "dismiss",
        "file-it",
    ]


def test_this_repos_plan_state_declares_two_marking_verbs() -> None:
    """Section 12's premise, as a fact about the shipped declaration rather
    than about the tool: completion is a word on the bullet, so `plan` carries
    dispositions the way `carrier` does. Two words rather than one, because a
    sub-phase nobody will do needs an exit that is not a `done` that lies."""
    declaration = load(REPO / "plan.toml")
    finish, skip = declaration.transitions["finish"], declaration.transitions["skip"]
    assert (finish.marks, skip.marks) == ("done", "skipped")
    for verb in (finish, skip):
        assert (verb.source, verb.to) == ("plan", "plan")



# --------------------------------------------------------------------------
# The derived roster: one answer to "which keys does a row carry"
# --------------------------------------------------------------------------


def test_derived_lists_the_gated_names_in_table_order() -> None:
    """The fixture opts into every gate, so `derived` is the whole roster
    — and in the roster's order, which is the order a row spells them."""
    declaration = load(FIXTURES / "plan.toml")
    assert declaration.derived == (*DERIVABLE_KEYS, *declaration.inverses)
    assert declaration.derived == (
        *CLAIM_KEYS,
        *subphase.DERIVED,
        *depends.DERIVED,
        *STALE_KEYS,
        *COMMAND_KEYS,
        "replaced-by",
    )


def test_a_declaration_with_no_such_state_derives_only_the_age() -> None:
    """Each gate off, so each name absent — the corpus-independence rule from
    the other side — except `stale-days`, which needs no switch (31-1).
    Graded on a document rather than on this repo's own `plan.toml`, which
    claims and counts from section 4 onwards."""
    plain = Declaration(
        source=FIXTURES / "plan.toml",
        root=FIXTURES,
        states={"greenhouse": State(name="greenhouse", path="greenhouse")},
        keys={},
        transitions={},
    )
    assert plain.derived == STALE_KEYS
    for name in DERIVABLE_KEYS:
        assert (name in plain.carried) == (name in STALE_KEYS)


def test_every_derived_name_is_carried() -> None:
    """`carried` is what `--has` and `--lacks` reach, so a derived key it
    omitted would be a field on every row that no filter could name. That is
    exactly what `sub-phases` was before 3-4, and the fold is what showed
    it."""
    declaration = load(FIXTURES / "plan.toml")
    assert set(declaration.derived) <= set(declaration.carried)
    assert subphase.NAME in declaration.carried


def test_no_derived_name_is_also_a_declared_key() -> None:
    """The roster's names are the tool's, and every one of them refuses as a
    redeclaration — which the refusal tests above grade one at a time. Here
    is the same fact said over the whole roster at once."""
    declaration = load(FIXTURES / "plan.toml")
    for name in DERIVABLE_KEYS:
        assert name not in declaration.keys


def test_the_roster_gates_read_the_declaration_and_nothing_else() -> None:
    """Each entry is a predicate over a `Declaration`, so a gate that reached
    for a corpus — which items happen to be filed — could not be written this
    way. Graded by calling every one of them on a declaration with no tree
    behind it at all."""
    plain = Declaration(
        source=FIXTURES / "plan.toml",
        root=FIXTURES / "nowhere",
        states={"greenhouse": State(name="greenhouse", path="greenhouse")},
        keys={},
        transitions={},
    )
    assert [group.gate(plain) for group in DERIVED_KEYS] == [
        False,
        False,
        False,
        True,
        False,
    ]


# --------------------------------------------------------------------------
# A state reached by name rather than by the loop that guards it
# --------------------------------------------------------------------------
#
# `_state_errors` walks the states table and skips an entry that is not a
# table, having said so once. Two arms do not reach a state that way: they
# are handed a *name* by a transition and look it up. Both then asked the
# entry what capabilities it declares, and a string does not answer — so a
# `plan.toml` that should have refused by name raised an AttributeError
# instead, which is the one outcome `docs/method.md` says a malformed
# declaration never produces.


def test_a_filing_state_that_is_not_a_table_refuses_rather_than_raising() -> None:
    """`files.state` reaches its state by name, so it has to tolerate the
    shape `_state_errors` already complained about."""
    document = well_formed()
    document["states"]["potting-shed"] = "potting-shed"
    document["transitions"]["pot-on"] = {
        "doc": "method.md#pot-on",
        "help": "File a finding.",
        "from": "greenhouse",
        "to": "greenhouse",
        "marks": "cultivar",
        "files": {
            "state": "potting-shed",
            "item": "cultivar",
            "name": "rootstock",
        },
    }
    assert "states.potting-shed must be a table" in shape_errors(document)


def test_an_archiving_source_that_is_not_a_table_refuses_rather_than_raising() -> None:
    """`archives` reaches its source state by name, one arm over, and had the
    same hole — one defect with two sites, so it gets two tests."""
    document = well_formed()
    document["states"]["compost"] = "compost"
    document["transitions"]["clear-out"] = {
        "doc": "method.md#clear-out",
        "help": "Take it away.",
        "from": "compost",
        "archives": True,
        "dissolves": True,
    }
    assert "states.compost must be a table" in shape_errors(document)


# --------------------------------------------------------------------------
# `retitles`: a rider on a move. See docs/method.md#retitle
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# A state's declared sort
# --------------------------------------------------------------------------


def test_a_queued_state_without_a_sort_sorts_by_position(tmp_path: Path) -> None:
    """32-2: `position` is the one sensible sort for a queued state, so it
    is the default rather than a refusal. The overview prints it."""
    document = well_formed()
    del document["states"]["orchard"]["sort"]
    assert shape_errors(document) == []
    (tmp_path / "plan.toml").write_text(
        '[states.orchard]\ncapabilities = ["queued"]\n\n[states.greenhouse]\n'
    )
    states = load(tmp_path / "plan.toml").states
    assert states["orchard"].sort == "position"
    assert states["greenhouse"].sort is None


def test_a_sort_by_position_on_a_state_that_is_not_queued_refuses() -> None:
    document = well_formed()
    document["states"]["greenhouse"]["sort"] = "position"
    (error,) = shape_errors(document)
    assert error.startswith(
        'states.greenhouse.sort names "position", which no item in this state '
        "carries, so every item would list as unsorted"
    )


def test_a_sort_naming_an_unknown_key_lists_what_the_state_carries() -> None:
    document = well_formed()
    document["states"]["orchard"]["sort"] = "-rootstok"
    assert (
        'states.orchard.sort names "rootstok", which no item in this state '
        "carries, so every item would list as unsorted (this state carries: "
        "title, cultivar, rootstock, position, stale-days)"
    ) in shape_errors(document)


def test_a_sort_that_is_not_a_string_refuses() -> None:
    document = well_formed()
    document["states"]["orchard"]["sort"] = ["position", "title"]
    assert "states.orchard.sort must be a string" in shape_errors(document)


@pytest.mark.parametrize("given", ["-title", "rootstock", "-position"])
def test_a_sort_naming_a_key_the_state_carries_loads(given: str) -> None:
    document = well_formed()
    document["states"]["orchard"]["sort"] = given
    assert shape_errors(document) == []


def test_a_sort_naming_a_derived_key_the_state_gives_loads() -> None:
    document = well_formed()
    document["states"]["greenhouse"]["sort"] = "-stale-days"
    assert shape_errors(document) == []


def test_the_fixture_orchard_carries_its_declared_sort() -> None:
    declaration = load(FIXTURES / "plan.toml")
    assert declaration.states["orchard"].sort == "position"
    assert declaration.states["greenhouse"].sort is None


def test_a_sort_naming_a_derived_key_the_state_does_not_give_refuses() -> None:
    """`claim-status` is carried where a state claims, and `greenhouse` does
    not, though the key exists elsewhere in the tool."""
    document = well_formed()
    document["states"]["greenhouse"]["sort"] = "claim-status"
    (error,) = shape_errors(document)
    assert error.startswith('states.greenhouse.sort names "claim-status"')


@pytest.mark.parametrize("name", DERIVABLE_KEYS)
def test_every_derived_key_refuses_as_a_key_and_as_a_reference(name: str) -> None:
    """34-2 f2: the whole roster, not a hand-written list of it. A derived key
    is read rather than written, so declaring one or naming one in `requires`
    refuses, whichever group it belongs to."""
    document = well_formed()
    document["keys"][name] = {"doc": "method.md#cultivar"}
    assert any(
        error.startswith(f'keys.{name} redeclares "{name}"')
        for error in shape_errors(document)
    )
    document = well_formed()
    document["transitions"]["transplant"]["requires"] = [name]
    assert any(
        error.startswith(f'transitions.transplant.requires names "{name}"')
        for error in shape_errors(document)
    )


def test_a_derived_group_added_to_the_roster_refuses_with_no_words_of_its_own(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mutation check: a group nobody wrote a message for is refused by
    the generic arms rather than accepted."""
    from fileplan import declaration

    monkeypatch.setattr(declaration, "DERIVABLE", (*declaration.DERIVABLE, "invented"))
    document = well_formed()
    document["keys"]["invented"] = {"doc": "method.md#cultivar"}
    document["transitions"]["transplant"]["requires"] = ["invented"]
    errors = shape_errors(document)
    assert 'keys.invented redeclares "invented", which every listing derives from outside the item\'s head. Drop keys.invented' in errors
    assert any(e.startswith('transitions.transplant.requires names "invented"') for e in errors)


def test_a_state_sorts_by_each_derived_group_it_carries() -> None:
    """34-2 f1: a state's `sort` is graded against `DERIVED_KEYS`' own
    per-state rule, so a group added to the roster reaches it. `commands` is
    a list of command names, which orders nothing, and the roster says so."""
    carrying = {
        CLAIM_KEYS: {"capabilities": ["claimed"]},
        subphase.DERIVED: {"sub-phases": "Steps"},
        depends.DERIVED: {"dependencies": "rootstock"},
        STALE_KEYS: {},
    }
    for group in DERIVED_KEYS:
        if group.sorts is None:
            assert group.names == COMMAND_KEYS
            continue
        fields = carrying[group.names]
        assert group.sorts(fields)
        for name in group.names:
            document = well_formed()
            document["states"]["greenhouse"].update(fields, sort=name)
            assert not [e for e in shape_errors(document) if ".sort " in e], name
    document = well_formed()
    document["states"]["greenhouse"]["sort"] = "commands"
    assert any("greenhouse.sort names" in e for e in shape_errors(document))


# --------------------------------------------------------------------------
# `listed`: a state left out of a `list` given no `--state`
# --------------------------------------------------------------------------


def test_a_state_without_listed_is_listed() -> None:
    """Absent means listed, so a forgotten field hides nothing."""
    declaration = load(FIXTURES / "plan.toml")
    assert declaration.states["greenhouse"].listed is True
    assert declaration.states["firewood"].listed is False


def test_listed_true_is_the_default_written_out() -> None:
    document = well_formed()
    document["states"]["orchard"]["listed"] = True
    assert shape_errors(document) == []


@pytest.mark.parametrize("value", ["no", 0])
def test_a_listed_that_is_not_a_bool_refuses_by_name(value: object) -> None:
    document = well_formed()
    document["states"]["orchard"]["listed"] = value
    assert "states.orchard.listed must be true or false" in shape_errors(document)


def test_the_declaration_names_its_unlisted_states(tmp_path: Path) -> None:
    assert load(FIXTURES / "plan.toml").unlisted == ("firewood",)
    for name in FIXTURE_FILES:
        (tmp_path / name).write_text((FIXTURES / name).read_text())
    plan = tmp_path / "plan.toml"
    plan.write_text(plan.read_text().replace("listed = false\n", ""))
    assert load(plan).unlisted == ()
