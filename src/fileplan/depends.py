"""Dependencies: what an item waits on, and what names nothing.

A state says which declared key holds an item's dependencies. So the word a
workflow spells them with appears nowhere in `src/`.

Absence does not mean satisfied. A dependency naming an item that is not filed
reads as `unknown`, never as met. Reading it as met would let a mistyped slug
pass silently. What is still filed is `blocking`, and the default read prints
both.

A dissolving transition clears every dependency pointing at the item it takes
away. So the tree never holds a dependency on a closed item. Nothing stores a
closed slug, so the tool cannot tell "gone because closed" from "never
existed". The tool does not try (John, 2026-09-04).

A dependency pointing later in the queue than the item holding it is
`misordered`. A misordered dependency is named rather than acted on. Nothing
here refuses and nothing gates.

Everything is pure.

See docs/method.md#dependencies
"""

from __future__ import annotations

from typing import Any, Container, Iterable, Mapping

# The import runs one way: `fileplan.declaration` imports this module, so
# this module imports nothing from the package.

#: The state field naming which declared key holds an item's dependencies:
#: the field name is the tool's and the key name is the workflow's.
FIELD = "dependencies"

#: The row field derived from it: the slugs this item waits on that are
#: still filed. Declared nowhere, and a transition naming it refuses too,
#: because it is read off the tree rather than written into a head.
BLOCKED = "blocked-by"

#: The row fields derived here, read as a tuple by `fileplan.declaration`.
DERIVED = (BLOCKED,)

#: The fields an exception report's record carries: which item the edge is
#: written on, which key it is written in, and what it names. Both reports
#: spell them the same way, being the same three facts.
SLUG, KEY, NAMES = "slug", "key", "names"

#: The two places `misordered` compares: the item's own, and the one it waits
#: on. Spelled here rather than imported from `fileplan.queued`.
PLACE, NAMED_PLACE = "place", "names-place"


def edges(head: Mapping[str, Any], key: str | None) -> tuple[str, ...]:
    """The slugs `head` names in `key`, in the order it names them.

    A bare string is one edge and a list is many, `fileplan.read.carries`'
    rule at the other end. `""` and `[]` are no edges at all, and `key` is
    `None` for a state that names none. An entry that is not a string is
    spelled as text and kept: no filed item can answer to it, so it lands in
    `unknown`, and dropping it would be the silence this module removes.
    """
    if key is None:
        return ()
    value = head.get(key)
    if value is None:
        return ()
    entries = value if isinstance(value, list) else [value]
    return tuple(str(entry) for entry in entries if str(entry).strip())


def without(value: Any, slug: str) -> Any | None:
    """`value` with every entry naming `slug` gone, or `None` when none is.

    The writer beside the readers, so the function that clears an edge and
    the ones that classify one cannot disagree about what "names this slug"
    means: the comparison is `str(entry) == slug`, exactly `blocking`'s.

    Shape in, shape out: a list stays a list and a bare string stays one. A
    value the clearing empties comes back `None`, and the caller drops the key
    rather than writing an empty one. See docs/method.md#dissolving
    """
    entries = value if isinstance(value, list) else [value]
    kept = [entry for entry in entries if str(entry) != slug]
    if not kept:
        return None
    return kept if isinstance(value, list) else kept[0]


def repoint(value: Any, slug: str, into: str, *, own: str) -> Any | None:
    """`value` with every entry naming `slug` naming `into` instead.

    `without`'s sibling and here for its reason. A dissolving verb that
    absorbs moves the edges to the item the work continues as, and two entries
    contribute nothing rather than being written: `into == own`, which would
    write a self-edge, and an `into` already among the entries, since a
    referent that waited on both still waits on one thing. Everything else is
    kept verbatim, and `without`'s shape rules hold. See
    docs/method.md#dissolving
    """
    entries = value if isinstance(value, list) else [value]
    present = {str(entry) for entry in entries if str(entry) != slug}
    kept: list[Any] = []
    for entry in entries:
        if str(entry) != slug:
            kept.append(entry)
            continue
        if into == own or into in present:
            continue
        kept.append(into)
        present.add(into)
    if not kept:
        return None
    return kept if isinstance(value, list) else kept[0]


def blocking(edges: Iterable[str], filed: Container[str]) -> tuple[str, ...]:
    """The edges naming an item that is still filed: what this one waits on.
    `unknown` keeps the rest, so an edge naming nothing cannot leave here
    looking like a satisfied one."""
    return tuple(slug for slug in edges if slug in filed)


def unknown(edges: Iterable[str], filed: Container[str]) -> tuple[str, ...]:
    """The edges naming nothing filed: the ones a session goes looking for.

    Exactly the complement of `blocking`, so the two partition the edges with
    nothing lost. Deliberately not part of `blocked-by`: "waiting on X" and "X
    does not exist" are different facts.
    """
    return tuple(slug for slug in edges if slug not in filed)


def misordered(
    slug: str,
    place: Any,
    edges: Iterable[str],
    places: Mapping[str, Any],
    *,
    key: str,
) -> list[dict[str, Any]]:
    """Every edge of `slug`'s naming an item later in the order.

    Named, never acted on: an order somebody set deliberately is not
    rearranged by a key about something else. An item with no place at either
    end is ignored.
    """
    if not isinstance(place, int) or isinstance(place, bool):
        return []
    found: list[dict[str, Any]] = []
    for named in edges:
        against = places.get(named)
        if not isinstance(against, int) or isinstance(against, bool):
            continue
        if against > place:
            found.append(
                {
                    SLUG: slug,
                    KEY: key,
                    NAMES: named,
                    PLACE: place,
                    NAMED_PLACE: against,
                }
            )
    return found

