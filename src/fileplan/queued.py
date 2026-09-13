"""The `queued` capability: a place in a state's order, and its arithmetic.

A state opts into `queued`, and every item there carries a `position`. The
executor writes the position on entry and drops it on exit. The key is not
declared, and a transition may not name it in `sets` or `drops`.

Everything here is pure and raises nothing but `Refusal`. Every refusal
happens before the executor writes anything.

The spacing is what makes an insert cheap. Places are `SPACING` apart. A new
place goes between two others at their midpoint, touching no other row. When a
gap is exhausted the tool refuses and names the respacing. Shifting a
neighbour instead would move places a person has already cited.

A place is a bare integer, never a quoted one. As text, `"1000"` sorts ahead
of `"200"`.

See docs/method.md#the-queue
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from fileplan.declaration import Refusal

#: The capability a state opts into. The same word plan.toml spells.
NAME = "queued"

#: The key it gives an item. Declared nowhere; a redeclaration is refused in
#: `fileplan.declaration.CAPABILITY_KEYS`.
KEY = "position"

#: Room to insert without renumbering: 100, 200, 300.
SPACING = 100

#: The floor a place ahead of the first row halves towards. It is a floor
#: rather than a refusal, so the first row can always be got in front of.
FLOOR = 0

#: What a row is called in a listing. Spelled here rather than imported from
#: `fileplan.read`, which imports this module to order a state.
SLUG = "slug"


def place(
    taken: Mapping[str, Any],
    *,
    current: int | None = None,
    above: str | None = None,
    below: str | None = None,
    at: int | None = None,
) -> int:
    """The place an item takes, or raise `Refusal`. Pure.

    `taken` is `{slug: position}` for everything already in the state, minus
    the item being placed. An entry whose position is `None` can be sat beside
    only once it has a place of its own.

    One request at most: `above` and `below` name an item to sit beside, `at`
    names the place outright. A bare invocation appends past the last row,
    unless the item is already here.

    `current` is the place the item holds in this state today, and `None` for
    one arriving from elsewhere. An item that is not going anywhere keeps its
    place unless a placement option asks otherwise: naming no place is not a
    request to be moved to the back.
    """
    asked = [
        f"--{flag}"
        for flag, value in (("above", above), ("below", below), ("at", at))
        if value is not None
    ]
    if len(asked) > 1:
        raise Refusal(
            f"{' and '.join(asked)} were both given, and an item takes one "
            "place. Say where it goes once"
        )

    held = sorted(
        position for position in taken.values() if isinstance(position, int)
    )
    if at is not None:
        return _at(taken, at)
    if above is not None or below is not None:
        return _beside(taken, held, anchor=above or below, ahead=above is not None)
    if current is not None:
        return current
    return held[-1] + SPACING if held else SPACING


def _at(taken: Mapping[str, Any], at: int) -> int:
    """An explicit place: the operator's own arithmetic, and the respacing tool."""
    if at <= FLOOR:
        raise Refusal(
            f"--at {at} is not a place. A place is a positive whole number, "
            f"and the first row takes {SPACING}"
        )
    holders = [slug for slug, position in taken.items() if position == at]
    if holders:
        raise Refusal(
            f'{at} is already held by "{holders[0]}". Two items at one place '
            "would be ordered by the tiebreak rather than by you — pick "
            "another place, or give that one another with --at"
        )
    return at


def _beside(
    taken: Mapping[str, Any], held: list[int], *, anchor: str | None, ahead: bool
) -> int:
    """The midpoint of the anchor and its neighbour on the side asked for."""
    assert anchor is not None
    position = taken.get(anchor)
    if not isinstance(position, int):
        raise Refusal(
            f'"{anchor}" carries no place of its own, so there is nothing to '
            f"sit beside. Give it one with --at first"
        )

    if ahead:
        before = [other for other in held if other < position]
        low, high = (before[-1] if before else FLOOR), position
    else:
        after = [other for other in held if other > position]
        if not after:
            return position + SPACING
        low, high = position, after[0]

    midpoint = (low + high) // 2
    if midpoint <= low or midpoint >= high:
        raise Refusal(
            f"there is no place between {low} and {high} — they are already "
            "adjacent, and nothing here renumbers a neighbour on its own: a "
            "place cited last sitting has to still mean the same item. Give "
            f"the rows around it places {SPACING} apart with --at, then ask "
            "for this one again"
        )
    return midpoint


def errors(head: Mapping[str, Any]) -> list[str]:
    """Every way `head`'s place is not one. Pure.

    A place is arithmetic, so a quoted one refuses rather than being read as
    text that happens to look like a number.
    """
    value = head.get(KEY)
    if value is None or (isinstance(value, int) and not isinstance(value, bool)):
        return []
    return [
        f"{KEY} holds {value!r}, which is not a whole number. A place is "
        f'arithmetic — "1000" sorts ahead of "200" as text — so it is '
        "written as a bare integer"
    ]


def order(entries: Iterable[Any]) -> list[Any]:
    """`entries` in place order, then slug. Stable, so slug order carries.

    Takes rows or items: a row is a mapping and an item is not. An entry
    carrying no place sorts last and keeps none, the listing being how you
    find out what to fix.
    """
    return sorted(entries, key=_rank)


def _rank(entry: Any) -> tuple[bool, int, str]:
    position = entry.get(KEY)
    if not isinstance(position, int) or isinstance(position, bool):
        return (True, 0, _handle(entry))
    return (False, position, _handle(entry))


def _handle(entry: Any) -> str:
    if isinstance(entry, Mapping):
        return str(entry.get(SLUG, ""))
    return entry.slug
