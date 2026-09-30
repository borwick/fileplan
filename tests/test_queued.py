"""The placement table: the whole of the ``queued`` capability's arithmetic.

**No ``tmp_path`` anywhere in this file.** `fileplan.queued.place` is a
total function of the places already taken plus what the operator asked for,
and every refusal happens there — before the executor writes anything. That is
the split 1-1, 1-2, 1-3 and 1-4 all keep, and it is why the interesting half
of this sub-phase costs no filesystem to test.

The vocabulary is the fixture's — `orchard` is the ``queued`` state — but
nothing here needs a declaration at all: a place is a number and a slug is a
string.
"""

from __future__ import annotations

import pytest

from fileplan import queued
from fileplan.declaration import Refusal

TAKEN = {"first": 100, "second": 200, "third": 300}


# --------------------------------------------------------------------------
# Appending: the bare form
# --------------------------------------------------------------------------


def test_the_first_placed_takes_the_spacing() -> None:
    assert queued.place({}) == queued.SPACING


def test_a_bare_place_appends_past_the_last() -> None:
    assert queued.place(TAKEN) == 400


def test_a_bare_place_ignores_an_item_carrying_none() -> None:
    """An item in the state with no place of its own is not the last row —
    it is a row to be fixed, and it must not drag the next one on top of it."""
    assert queued.place({**TAKEN, "stray": None}) == 400


def test_the_last_row_is_the_largest_place_not_the_last_entry() -> None:
    """`taken` is a mapping, and mapping order is filesystem order. The
    arithmetic reads the numbers, never the order they arrived in."""
    assert queued.place({"z": 100, "a": 300, "m": 200}) == 400


# --------------------------------------------------------------------------
# Beside another item: the midpoint, which is what the spacing buys
# --------------------------------------------------------------------------


def test_above_takes_the_midpoint_of_its_two_neighbours() -> None:
    assert queued.place(TAKEN, above="second") == 150


def test_below_takes_the_midpoint_of_its_two_neighbours() -> None:
    assert queued.place(TAKEN, below="second") == 250


def test_an_insert_touches_no_other_row() -> None:
    """The load-bearing property: `place` returns one number and cannot
    return a renumbering, so a place cited last sitting still means the same
    item. The mapping it was given is not touched either."""
    before = dict(TAKEN)
    assert queued.place(TAKEN, above="third") == 250
    assert TAKEN == before


def test_above_the_first_row_halves_it() -> None:
    """The floor is 0, not a refusal: the first row can always be got in
    front of."""
    assert queued.place(TAKEN, above="first") == 50


def test_below_the_last_row_appends() -> None:
    assert queued.place(TAKEN, below="third") == 400


def test_an_exhausted_gap_refuses_and_names_the_respacing() -> None:
    """**Nothing renumbers a neighbour.** A queue that respaces itself is one
    the operator cannot cite between two sittings, so the refusal says what to
    do rather than doing it — and says it in the vocabulary the tool owns, not
    by naming a verb."""
    with pytest.raises(Refusal) as refusal:
        queued.place({"first": 100, "second": 101}, above="second")
    said = str(refusal.value)
    assert "no place between 100 and 101" in said
    assert f"{queued.SPACING} apart with --at" in said


def test_an_exhausted_gap_below_refuses_too() -> None:
    with pytest.raises(Refusal, match="no place between 100 and 101"):
        queued.place({"first": 100, "second": 101}, below="first")


def test_no_room_ahead_of_the_first_row_refuses() -> None:
    """The floor is 0 and a place is positive, so an item at 1 has nowhere
    ahead of it. It refuses rather than writing a place nothing can hold."""
    with pytest.raises(Refusal, match="no place between 0 and 1"):
        queued.place({"first": 1}, above="first")


def test_an_anchor_carrying_no_place_refuses() -> None:
    """There is nothing to sit beside. The listing shows the stray row with
    no place, and `--at` is how it gets one."""
    with pytest.raises(Refusal) as refusal:
        queued.place({**TAKEN, "stray": None}, above="stray")
    assert '"stray" carries no place of its own' in str(refusal.value)
    assert "--at" in str(refusal.value)


def test_an_anchor_that_is_not_in_the_state_refuses_the_same_way() -> None:
    """`taken` is everything in the state minus the item being placed, so an
    item asked to sit beside *itself* arrives here as an unknown anchor."""
    with pytest.raises(Refusal, match="carries no place of its own"):
        queued.place(TAKEN, below="itself")


# --------------------------------------------------------------------------
# `--at`: the explicit place, and the respacing tool
# --------------------------------------------------------------------------


def test_at_takes_the_place_it_names() -> None:
    assert queued.place(TAKEN, at=250) == 250


def test_at_may_name_a_place_past_the_last() -> None:
    """Which is how a gap gets respaced: give the rows around it places
    `SPACING` apart, then ask again."""
    assert queued.place(TAKEN, at=1000) == 1000


def test_at_on_a_place_another_item_holds_refuses_naming_that_item() -> None:
    """Two items at one place is an order decided by the tiebreak rather than
    by the operator."""
    with pytest.raises(Refusal) as refusal:
        queued.place(TAKEN, at=200)
    assert '200 is already held by "second"' in str(refusal.value)


@pytest.mark.parametrize("at", [0, -1, -100])
def test_a_place_that_is_not_positive_refuses(at: int) -> None:
    with pytest.raises(Refusal) as refusal:
        queued.place(TAKEN, at=at)
    assert f"--at {at} is not a place" in str(refusal.value)


# --------------------------------------------------------------------------
# Staying put: an item already in the state keeps its place
# --------------------------------------------------------------------------
#
# 4-4 is what forced this: `work` is the first in-place verb into an ordered
# state, and without the rule it would have moved section 4 from 100 to the
# back of the queue every time a session said which sub-phase it was on —
# silently destroying an order somebody set deliberately, on a verb about
# something else entirely.
#
# The cost, taken with eyes open: a bare `requeue` stops meaning "send it to
# the back". That behaviour was undocumented and untested, and the new one is
# what `#requeue` says in words — "move an item to *another place*", and
# naming no place is not a request.


def test_an_item_already_here_keeps_its_place() -> None:
    """The rule. `current` is the place the item holds today; a verb that asks
    for no placement is not asking to be moved."""
    assert queued.place({"first": 100, "third": 300}, current=200) == 200


def test_an_item_arriving_from_elsewhere_still_appends() -> None:
    """`current` is `None` for an item that is not in this state yet, which is
    every move between states — so nothing about arriving changed."""
    assert queued.place(TAKEN, current=None) == 400


def test_the_first_row_of_an_empty_state_keeps_its_place_too() -> None:
    """No other rows to append past, and still nothing to move it: the two
    arms cannot disagree because staying put is decided first."""
    assert queued.place({}, current=700) == 700


@pytest.mark.parametrize(
    ("request_", "expected"),
    [
        ({"above": "second"}, 150),
        ({"below": "second"}, 250),
        ({"at": 250}, 250),
    ],
)
def test_a_placement_option_still_moves_an_item_that_is_here(
    request_: dict, expected: int
) -> None:
    """Staying put is the *default*, not a refusal to move. Each of the three
    ways to ask still names the place, which is what keeps `requeue` a
    respacing tool."""
    assert queued.place(TAKEN, current=999, **request_) == expected


# --------------------------------------------------------------------------
# One request at a time
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "request_",
    [
        {"above": "first", "below": "second"},
        {"above": "first", "at": 250},
        {"below": "first", "at": 250},
        {"above": "first", "below": "second", "at": 250},
    ],
)
def test_two_requests_at_once_refuse(request_: dict) -> None:
    """Two ways to say the same thing, said at once. It refuses and writes
    nothing rather than picking one — the same rule as never guessing which
    item a prefix meant."""
    with pytest.raises(Refusal) as refusal:
        queued.place(TAKEN, **request_)
    said = str(refusal.value)
    assert "an item takes one place" in said
    for flag in request_:
        assert f"--{flag}" in said


# --------------------------------------------------------------------------
# The value: a place is arithmetic
# --------------------------------------------------------------------------


def test_a_bare_integer_place_is_no_error() -> None:
    assert queued.errors({queued.KEY: 100}) == []


def test_a_head_with_no_place_is_no_error() -> None:
    assert queued.errors({"title": "A seedling"}) == []


def test_a_quoted_place_refuses_because_the_key_is_arithmetic() -> None:
    """`"1000"` sorts ahead of `"200"` as text, and an order that depends on
    how a value was spelled is not an order."""
    (error,) = queued.errors({queued.KEY: "100"})
    assert "is not a whole number" in error
    assert '"1000" sorts ahead of "200"' in error


@pytest.mark.parametrize("value", [1.5, True, ["100"], "not a number"])
def test_anything_that_is_not_a_whole_number_refuses(value: object) -> None:
    """`True` included: a bool is an `int` in Python, and 1-2's writer already
    keeps that distinction on the way out."""
    assert queued.errors({queued.KEY: value})
