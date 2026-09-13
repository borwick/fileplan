"""The dependency arithmetic: what is waited on, what names nothing, what is late.

Pure over the values it is handed — no ``tmp_path``, no declaration, no
fixture tree — like `test_queued.py`, `test_numbered.py` and `test_subphase.py`
beside it. What an item's edges *mean* is graded here; where they come from
and how they print is `test_read.py`'s and `test_cli.py`'s.

The one that matters most is the partition. The old tool discarded the
complement of `fileplan.depends.blocking`, and a typo'd slug fell into
it silently — so "the two partition the edges with nothing lost" is the
re-pin, stated as arithmetic.
"""

from __future__ import annotations

from fileplan import depends

#: The declared key a fixture head spells its edges in. The fixture's word,
#: never this repo's: the tool reads whichever key the state names.
KEY = "after"

FILED = {"a-tree", "b-tree", "c-tree"}


# --------------------------------------------------------------------------
# Reading a value: one edge, several, or none
# --------------------------------------------------------------------------


def test_a_bare_string_is_one_edge() -> None:
    assert depends.edges({KEY: "a-tree"}, KEY) == ("a-tree",)


def test_a_list_is_the_several_edges_it_holds() -> None:
    """The row layer already treats a list value as the values it holds, so
    this is that same rule at the other end."""
    assert depends.edges({KEY: ["a-tree", "b-tree"]}, KEY) == ("a-tree", "b-tree")


def test_an_empty_value_is_no_edges_at_all() -> None:
    """Empty reads as missing, the rule a `requires` already uses."""
    assert depends.edges({KEY: ""}, KEY) == ()
    assert depends.edges({KEY: []}, KEY) == ()
    assert depends.edges({KEY: ["", "  "]}, KEY) == ()


def test_a_head_carrying_nothing_is_no_edges() -> None:
    assert depends.edges({}, KEY) == ()


def test_a_state_that_names_no_key_reads_none() -> None:
    """An item may carry the declared key in a state that says nothing about
    it. A fact nothing was declared to read is not read — the cursor's rule."""
    assert depends.edges({KEY: ["a-tree"]}, None) == ()


def test_the_key_read_is_the_one_named_and_no_other() -> None:
    assert depends.edges({KEY: "a-tree", "waits": "b-tree"}, "waits") == ("b-tree",)


# --------------------------------------------------------------------------
# The partition: blocked, and unknown
# --------------------------------------------------------------------------


def test_blocking_is_the_edges_still_filed() -> None:
    edges = depends.edges({KEY: ["a-tree", "gone-tree"]}, KEY)
    assert depends.blocking(edges, FILED) == ("a-tree",)


def test_unknown_is_the_edges_naming_nothing() -> None:
    """The complement the old tool threw away — and throwing it away is what
    made a typo'd slug read as a satisfied dependency."""
    edges = depends.edges({KEY: ["a-tree", "gone-tree"]}, KEY)
    assert depends.unknown(edges, FILED) == ("gone-tree",)


def test_the_two_partition_the_edges_with_nothing_lost() -> None:
    """Every edge is in exactly one of them. That is the whole of the re-pin:
    an edge cannot fall out of both and vanish."""
    edges = depends.edges({KEY: ["a-tree", "gone-tree", "b-tree", "typo"]}, KEY)
    blocked = depends.blocking(edges, FILED)
    unknown = depends.unknown(edges, FILED)
    assert len(blocked) + len(unknown) == len(edges)
    assert set(blocked) | set(unknown) == set(edges)
    assert set(blocked) & set(unknown) == set()


def test_an_entry_that_is_not_a_string_lands_in_unknown() -> None:
    """Rather than crashing, and rather than being dropped. No filed item can
    answer to it — a slug is a filename stem — so it is named as what it is,
    which is the visible-by-default polarity applied to a malformed value."""
    edges = depends.edges({KEY: ["a-tree", 42]}, KEY)
    assert edges == ("a-tree", "42")
    assert depends.unknown(edges, FILED) == ("42",)


def test_a_bare_non_string_value_is_read_the_same_way() -> None:
    assert depends.edges({KEY: 42}, KEY) == ("42",)


# --------------------------------------------------------------------------
# The order: named, never acted on
# --------------------------------------------------------------------------

PLACES = {"a-tree": 100, "b-tree": 200, "c-tree": 300}


def misordered(slug: str, *edges: str) -> list[dict]:
    return depends.misordered(slug, PLACES.get(slug), edges, PLACES, key=KEY)


def test_an_edge_pointing_later_in_the_order_is_named() -> None:
    (found,) = misordered("a-tree", "c-tree")
    assert found == {
        depends.SLUG: "a-tree",
        depends.KEY: KEY,
        depends.NAMES: "c-tree",
        depends.PLACE: 100,
        depends.NAMED_PLACE: 300,
    }


def test_an_order_that_agrees_names_nothing() -> None:
    assert misordered("c-tree", "a-tree", "b-tree") == []


def test_an_edge_at_the_same_place_is_not_later() -> None:
    assert depends.misordered(
        "a-tree", 100, ("b-tree",), {"b-tree": 100}, key=KEY
    ) == []


def test_an_item_with_no_place_is_ignored_rather_than_guessed_at() -> None:
    """A place it does not have cannot be later than anything, at either end.
    The listing is where a missing place shows."""
    assert depends.misordered("d-tree", None, ("a-tree",), PLACES, key=KEY) == []
    assert depends.misordered("a-tree", 100, ("d-tree",), PLACES, key=KEY) == []


def test_an_edge_naming_nothing_is_not_a_misordering() -> None:
    """It is the other report's. One defect, one complaint."""
    assert misordered("a-tree", "gone-tree") == []


def test_every_late_edge_is_named_rather_than_the_first() -> None:
    assert [one[depends.NAMES] for one in misordered("a-tree", "b-tree", "c-tree")] == [
        "b-tree",
        "c-tree",
    ]


# --------------------------------------------------------------------------
# `without`: the writer beside the readers
# --------------------------------------------------------------------------


def test_a_list_loses_the_entry_and_stays_a_list() -> None:
    """Shape in, shape out: the value is the workflow's own, and a verb about
    something else does not reformat it."""
    assert depends.without(["a-tree", "b-tree", "c-tree"], "b-tree") == [
        "a-tree",
        "c-tree",
    ]


def test_a_list_of_one_naming_the_slug_comes_back_none() -> None:
    """`None` is what tells the caller to **drop the key** rather than write
    `after = []` — an empty value carries nothing, so keeping it would be a
    fact the head states and nothing means."""
    assert depends.without(["b-tree"], "b-tree") is None


def test_a_bare_string_naming_the_slug_comes_back_none() -> None:
    """A bare string is one edge, `edges`' rule at the other end."""
    assert depends.without("b-tree", "b-tree") is None


def test_a_bare_string_naming_something_else_is_unchanged() -> None:
    assert depends.without("a-tree", "b-tree") == "a-tree"


def test_a_list_naming_the_slug_more_than_once_loses_every_copy() -> None:
    """A head somebody wrote by hand can say it twice, and clearing "the" edge
    would leave the tree holding a dead one."""
    assert depends.without(["b-tree", "a-tree", "b-tree"], "b-tree") == ["a-tree"]


def test_a_list_naming_nothing_of_the_kind_is_unchanged() -> None:
    assert depends.without(["a-tree"], "b-tree") == ["a-tree"]


def test_a_non_string_entry_is_compared_as_text_and_the_others_kept_verbatim(
) -> None:
    """`edges`' comparison exactly — `str(entry) == slug` — so an edge those
    readers can see is an edge this can clear, and one they cannot match is
    kept as it was written rather than rewritten as text."""
    assert depends.without([7, "b-tree"], "7") == ["b-tree"]
    assert depends.without([7, "b-tree"], "b-tree") == [7]


# --------------------------------------------------------------------------
# `repoint`: the edge that is moved rather than taken out
# --------------------------------------------------------------------------
#
# `without`'s sibling, and pure the same way. `own` is the item whose head is
# being rewritten, which is what makes the self-edge reachable: a survivor may
# be in a state that declares dependencies, so its own head can name the item
# it is absorbing.


def test_a_list_keeps_its_shape_and_its_other_entries() -> None:
    """Shape in, shape out, and everything else kept verbatim: a pre-existing
    oddity in somebody's head is not this verb's to tidy."""
    assert depends.repoint(
        ["a-tree", "b-tree", "c-tree"], "b-tree", "d-tree", own="e-tree"
    ) == ["a-tree", "d-tree", "c-tree"]


def test_a_bare_string_stays_a_bare_string() -> None:
    """A bare string is one edge, `edges`' rule at the other end."""
    assert depends.repoint("b-tree", "b-tree", "d-tree", own="e-tree") == "d-tree"


def test_a_survivor_already_named_collapses_to_one_entry_in_its_place() -> None:
    """An edge is named once. A referent waiting on **both** the absorbed tree
    and the survivor waits on one thing afterwards, and the entry that goes is
    the one naming the absorbed tree — so the survivor keeps the position it
    was already written in and a hand-ordered list is not reshuffled."""
    assert depends.repoint(
        ["d-tree", "a-tree", "b-tree"], "b-tree", "d-tree", own="e-tree"
    ) == ["d-tree", "a-tree"]
    assert depends.repoint(
        ["b-tree", "a-tree", "d-tree"], "b-tree", "d-tree", own="e-tree"
    ) == ["a-tree", "d-tree"]


def test_an_entry_naming_neither_is_untouched() -> None:
    assert depends.repoint(["a-tree"], "b-tree", "d-tree", own="e-tree") == ["a-tree"]


def test_the_survivors_own_edge_to_the_absorbed_item_is_dropped() -> None:
    """**The self-edge.** `own == into` means this head belongs to the
    survivor, and an item may not wait on itself — so the entry contributes
    nothing rather than being written, and the caller says which item and
    which key (John, 2026-09-04)."""
    assert depends.repoint(
        ["a-tree", "b-tree"], "b-tree", "d-tree", own="d-tree"
    ) == ["a-tree"]


def test_a_value_the_drop_empties_comes_back_none() -> None:
    """`without`'s rule unchanged: `None` tells the caller to **drop the key**
    rather than write `after = []`. Reachable only through the self-edge, since
    every other entry naming the slug is replaced rather than removed."""
    assert depends.repoint(["b-tree"], "b-tree", "d-tree", own="d-tree") is None
    assert depends.repoint("b-tree", "b-tree", "d-tree", own="d-tree") is None


def test_a_value_naming_the_slug_twice_yields_one_entry() -> None:
    """A head somebody wrote by hand can say it twice, and repointing "the"
    edge would leave the tree holding two copies of one."""
    assert depends.repoint(
        ["b-tree", "a-tree", "b-tree"], "b-tree", "d-tree", own="e-tree"
    ) == ["d-tree", "a-tree"]


def test_a_non_string_entry_is_compared_as_text_and_the_others_kept_verbatim_here(
) -> None:
    """`without`'s comparison exactly — `str(entry) == slug` — so the two
    cannot disagree about what "names this slug" means."""
    assert depends.repoint([7, "b-tree"], "7", "d-tree", own="e-tree") == [
        "d-tree",
        "b-tree",
    ]
    assert depends.repoint([7, "b-tree"], "b-tree", "d-tree", own="e-tree") == [
        7,
        "d-tree",
    ]
