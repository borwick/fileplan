"""The read: one traversal over the declared states, and the handle that uses it.

One walk of the tree serves the listing, both of its renderings, and the
resolution of an item handle. A second traversal would be two readers of one
corpus, free to disagree.

`items` is the one function here that touches a disk. `listing` composes
`items` with `fileplan.claim.holders` and touches nothing itself. `rows`,
`matching` and `comparison` are pure.

Every `*.md` in a declared state directory is claimed to be an item. So a
`README.md` filed among them refuses the listing by name. Every defect is
collected and reported at once.

See docs/method.md#the-listing for the traversal and its filters.
See docs/method.md#the-handle for the prefix rule `resolve` applies.
"""

from __future__ import annotations

import datetime as dt
import difflib
import operator as operators
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

from fileplan import claim, depends, item, numbered, queued, stale, subphase
from fileplan.declaration import (
    CAPABILITY_KEYS,
    CLAIM_KEYS,
    CLAIMED,
    DATED,
    INTRINSIC_KEYS,
    Declaration,
    Refusal,
    collecting,
)
from fileplan.item import Item

#: The fields a row carries off the tree rather than out of a head, in the
#: order a row spells them. `declaration.RESERVED_KEYS` is the same list, and
#: it is why no declared key may take one of these names.
SLUG, STATE, PATH = "slug", "state", "path"

#: The fields a bullet row carries, in the order it spells them, with `PATH`
#: closing it as it closes an item row. `mark` is present and `null` on an
#: unmarked bullet, by the corpus-independence rule every row field follows.
#: An offer over these takes no filters, because every filter names a key an
#: item carries. See docs/method.md#the-next-read
BULLET_NAME, BULLET_ITEM, BULLET_TITLE, BULLET_MARK = "name", "item", "title", "mark"

#: What a bullet carries after its name's bold run, spelled after
#: `subphase.Bullet.rest` — one spelling for one meaning, and the refusal
#: quotes the same value. It appears in the `unmarkable` report's records
#: rather than in a row. See docs/method.md#marking
BULLET_REST = "rest"

#: The comparison operators a filter value may carry, longest first so `>=`
#: is never read as `>`. A bare value means `=`.
OPERATORS = ("!=", ">=", "<=", "=", ">", "<", ":")

#: `drawn from`: the one operator taking several values, and the one that asks
#: about the whole of what a key carries rather than about an entry of it.
#: `:` prefix-collides with no other operator, so its place above is free.
DRAWN = ":"

#: The two tests that ask about presence rather than value. They come from
#: `--has` / `--lacks`, not from a value's prefix, and carry no value.
PRESENT, MISSING = "has", "lacks"

_ORDERED: Mapping[str, Callable[[Any, Any], bool]] = {
    "<": operators.lt,
    "<=": operators.le,
    ">": operators.gt,
    ">=": operators.ge,
}


@dataclass(frozen=True)
class Test:
    """One filter, parsed: which key, which comparison, against what.

    `order` is the key's declared `values` when it has them, and it is the
    whole of what makes `<` mean anything: `S`, `M`, `L`, `XL` are ordered
    because plan.toml lists them in that order, not because the tool knows
    sizes. A key with no `values` compares as text.
    """

    key: str
    operator: str
    value: str = ""
    order: tuple[str, ...] | None = None


# --------------------------------------------------------------------------
# The traversal: the one function here that touches a disk
# --------------------------------------------------------------------------


def items(declaration: Declaration) -> list[Item]:
    """Every item in the tree, in declared-state order then slug, or refuse.

    A state whose directory does not exist yet is empty, not broken. A `path`
    is a literal directory, so the glob is flat and a file below one is in no
    state at all.

    A state with the `queued` capability comes back in its own order instead:
    by place, then by slug, because the slug sort below is stable. An item
    there carrying no place sorts last and shows none.
    """
    found: list[Item] = []
    errors: list[str] = []
    for state in declaration.states.values():
        directory = declaration.root / state.path
        if not directory.is_dir():
            continue
        here: list[Item] = []
        paths = sorted(directory.glob(f"*{item.SUFFIX}"), key=lambda p: p.stem)
        for path, one in collecting(
            lambda p: item.read(p, declaration), paths, errors
        ):
            here.append(one)
            if state.sub_phases:
                errors += [
                    f"{path.name}: {message}"
                    for message in subphase.errors(one.body, state.sub_phases)
                ]
        found += queued.order(here) if state.has(queued.NAME) else here
    if errors:
        raise Refusal(errors)
    return found


# --------------------------------------------------------------------------
# The row layer: pure, and the reason two renderers cannot disagree
# --------------------------------------------------------------------------


def head_keys(declaration: Declaration) -> tuple[str, ...]:
    """The head keys this declaration's capabilities give, in mapping order.

    One answer to "which keys does a row carry because of where an item is",
    read by the listing, by the filters the CLI generates and by the grading
    in `fileplan.item`. A fifth copy of the question is how a capability ends
    up carried by the row and unreachable by the filter.

    Present whenever the declaration has such a state, never depending on
    which items happen to be filed.
    """
    return tuple(
        key
        for capability, key in CAPABILITY_KEYS.items()
        if declaration.has(capability)
    )


def rows(
    declaration: Declaration,
    found: Sequence[Item],
    *,
    claimed: Mapping[str, Mapping[str, Any]] = MappingProxyType({}),
    blocking: Mapping[str, tuple[str, ...]] = MappingProxyType({}),
    ages: Mapping[str, int] = MappingProxyType({}),
) -> list[dict[str, Any]]:
    """`found` as mappings, one per item, every declared key present.

    A key an item does not carry is `None` rather than absent, so the shape a
    consumer writes against does not depend on which items happen to be filed.
    How `None` prints is the renderer's business. `state` is the declared
    name, never the directory it resolves to.

    The derived fields come between `state` and the declared keys, each
    present whenever the declaration has such a state at all: a capability's
    key, then the three counted off the body, then `blocked-by`, then
    `stale-days`. A `0` sub-phase count is a section nobody has decomposed,
    where `None` is a state that counts none, and the pair is what tells a
    finished decomposition from a state with no bullets at all. See
    docs/method.md#the-listing and docs/method.md#the-cursor

    `claimed`, `blocking` and `ages` are the facts read from outside the item
    file, each a mapping by slug. Working them out is `listing`'s, so this
    function stays pure over what it is handed. `blocked-by` names only what
    is still filed, because "waiting on X" and "X does not exist" are
    different facts (docs/method.md#dependencies). A slug git could not answer
    about is absent from `ages`, so the `None` is spelled once, here
    (docs/method.md#stale-days).
    """
    given = head_keys(declaration)
    held = CLAIM_KEYS if declaration.has(CLAIMED) else ()
    counts = declaration.counts_sub_phases
    waits = declaration.has_dependencies
    dated = declaration.has(DATED)
    return [
        {
            SLUG: one.slug,
            STATE: one.state.name,
            **{key: one.get(key) for key in given},
            **{key: claimed.get(one.slug, {}).get(key) for key in held},
            **(
                {
                    subphase.NAME: (
                        subphase.count(one.body, one.state.sub_phases)
                        if one.state.sub_phases
                        else None
                    ),
                    subphase.LEFT: (
                        len(subphase.unmarked(one.body, one.state.sub_phases))
                        if one.state.sub_phases
                        else None
                    ),
                    subphase.NEXT: (
                        subphase.upcoming(
                            one.body,
                            one.state.sub_phases,
                            cursor=one.get(one.state.cursor)
                            if one.state.cursor
                            else None,
                        )
                        if one.state.sub_phases
                        else None
                    ),
                }
                if counts
                else {}
            ),
            **(
                {depends.BLOCKED: list(blocking.get(one.slug, ())) or None}
                if waits
                else {}
            ),
            **({stale.DAYS: ages.get(one.slug)} if dated else {}),
            **{key: one.get(key) for key in INTRINSIC_KEYS},
            **{key: one.get(key) for key in declaration.keys},
            PATH: str(one.path.relative_to(declaration.root)),
        }
        for one in found
    ]


@dataclass(frozen=True)
class Listing:
    """What one read of the tree found: its rows, and the claims beside them.

    `stranded` is not a narrower list of `rows`: a stranded claim is a record,
    not an item. Both renderings report it, and neither filter touches it.
    """

    rows: list[dict[str, Any]]
    stranded: list[dict[str, Any]]
    #: How many items the traversal read, which is not `len(rows)` once an
    #: offering narrows them. It is what the frame counts of: a read that
    #: offers three of twelve says `3 of 12` rather than `3 of 3`.
    walked: int
    #: The slugs of started sections carrying no sub-phases at all. An
    #: exception report about the tree rather than a row of it, said by both
    #: renderings and narrowed by no filter. See docs/method.md#the-cursor
    undecomposed: list[str] = field(default_factory=list)
    #: The edges naming nothing filed, and the edges pointing later in the
    #: order — one record each, naming the item, the key and what it named.
    #: Exception reports like the one above. See docs/method.md#dependencies
    #:
    #: Seven reports and no merged `notices` array: each carries a different
    #: shape, and the envelope key is how a consumer selects one. A merged
    #: array would be a union mostly empty at every read.
    unknown: list[dict[str, Any]] = field(default_factory=list)
    misordered: list[dict[str, Any]] = field(default_factory=list)
    #: The two register reports, one record each: a number in neither the
    #: state nor the document its `archive` names, and a `##` in that document
    #: the register cannot read. The arithmetic is
    #: `fileplan.numbered.missing`, the same one the mint refuses on. See
    #: docs/method.md#the-register
    gaps: list[dict[str, Any]] = field(default_factory=list)
    lost: list[dict[str, Any]] = field(default_factory=list)
    #: The bullets no verb could mark: unmarked, in a state some verb marks
    #: into, and carrying text after the name's bold run. One record each,
    #: naming the item, the bullet and what is in the way. The seventh
    #: exception report. See docs/method.md#marking
    unmarkable: list[dict[str, Any]] = field(default_factory=list)
    #: **Not** one of the seven. One record per numbered state, saying what
    #: the register holds rather than what is wrong with it: its name, its
    #: archive, its floor and the highest number it holds. A report is silent
    #: when nothing is wrong; this prints on every read. See
    #: docs/method.md#the-register
    register: list[dict[str, Any]] = field(default_factory=list)


def listing(
    declaration: Declaration,
    *,
    offering: Callable[[Item], bool] | None = None,
    marking: Callable[[subphase.Bullet], bool] | None = None,
) -> Listing:
    """The composed read: the traversal, the claims, and the rows they make.

    One entry point, so no caller can walk the tree, forget the claims and
    render every item as free. `rows` stays public and pure beside it because
    the filter table is graded against it with no `tmp_path`.

    A claim belongs to an item in a claimed state, and every other record is
    stranded: one whose slug names no item, and one naming an item that has
    since moved to a state which claims nothing. The rule is the executor's,
    so the listing and the transition cannot disagree. A stranded claim is
    named, never filtered and never removed. A declaration with no claimed
    state reads no records at all. See docs/method.md#the-listing

    `offering` narrows which items become rows, and nothing else. The
    predicate is the caller's, so this module goes on knowing nothing about
    transitions. It is asked of an `Item` rather than of a row, because a row
    spells an absent key `None` and a precondition read over one would offer
    everything.

    `marking` switches the rows to the second kind, one per named bullet
    rather than one per item, which is what makes a carrier of a hundred
    findings a read. The two compose: a row survives when its item passes
    `offering` and its bullet passes this. See docs/method.md#the-next-read

    `walked` stays the size of the whole traversal either way, and every
    exception report is computed over all of it: an offer is a filter, and a
    report about the tree is narrowed by none. The dependency facts have to be
    computed over all of `found` for the second reason as well.

    This is where the clock is read, once, beside `local/claims/`
    (docs/method.md#stale-days), and where each numbered state's archive is
    read, for the two reports and the register record `_register` builds
    (docs/method.md#the-register).
    """
    found = items(declaration)
    offered = [one for one in found if offering(one)] if offering else found
    blocking, unknown, misordered = _dependencies(found)
    gaps, lost, register = _register(declaration, found)
    unmarkable = _unmarkable(declaration, found)
    ages = stale.ages(
        declaration.root,
        [(one.slug, one.path) for one in found if one.state.has(DATED)],
        dt.date.today(),
    )
    # Started means the item carries the status key at all, never that its
    # status has passed some particular word: the words are the workflow's.
    undecomposed = [
        one.slug
        for one in found
        if one.state.status
        and one.state.sub_phases
        and one.state.status in one.head
        and subphase.count(one.body, one.state.sub_phases) == 0
    ]
    # The claims first, then the rows, then one return: what varies between
    # the two row kinds is the two lines below, so that is what branches.
    held: dict[str, Mapping[str, Any]] = {}
    stranded: list[dict[str, Any]] = []
    if declaration.has(CLAIMED):
        claimed = claim.holders(declaration)
        here = {one.slug for one in found if one.state.has(CLAIMED)}
        held = {slug: fields for slug, fields in claimed.items() if slug in here}
        stranded = [
            {
                SLUG: slug,
                **fields,
                PATH: str(
                    claim.path(declaration.root, slug).relative_to(declaration.root)
                ),
            }
            for slug, fields in claimed.items()
            if slug not in here
        ]

    if marking is not None:
        made, walked = _bullets(declaration, found, offered, marking)
    else:
        made = rows(
            declaration, offered, claimed=held, blocking=blocking, ages=ages
        )
        walked = len(found)

    return Listing(
        rows=made,
        stranded=stranded,
        walked=walked,
        undecomposed=undecomposed,
        unknown=unknown,
        misordered=misordered,
        gaps=gaps,
        lost=lost,
        unmarkable=unmarkable,
        register=register,
    )


def _bullets(
    declaration: Declaration,
    found: Sequence[Item],
    offered: Sequence[Item],
    marking: Callable[[subphase.Bullet], bool],
) -> tuple[list[dict[str, Any]], int]:
    """The bullet rows, and how many bullets the traversal read.

    Every named bullet of every item in a state that carries bullets is
    walked, whether or not its item was offered: `walked` is what the
    traversal read rather than what it offered. A state with no sub-phase
    heading contributes nothing rather than an empty row.

    What `fileplan.subphase.bullets` leaves out is left out of `walked` too —
    an unnamed bullet and the pending marker are not things any verb could
    take, so counting them would make an offer read as passing over work.
    """
    offering = {one.slug for one in offered}
    made: list[dict[str, Any]] = []
    walked = 0
    for one in found:
        if not one.state.sub_phases:
            continue
        for bullet in subphase.bullets(
            one.body, one.state.sub_phases, pending=one.state.pending
        ):
            walked += 1
            if one.slug in offering and marking(bullet):
                made.append(
                    {
                        BULLET_NAME: bullet.name,
                        BULLET_ITEM: one.slug,
                        STATE: one.state.name,
                        BULLET_TITLE: bullet.title,
                        BULLET_MARK: bullet.mark,
                        PATH: str(one.path.relative_to(declaration.root)),
                    }
                )
    return made, walked


def _unmarkable(
    declaration: Declaration, found: Sequence[Item]
) -> list[dict[str, Any]]:
    """The bullets in marked-into states that no mark could be read on.

    `subphase.Bullet.unmarkable` is the question, so the report and the
    refusal that stops the run cannot disagree about where a bold run ends.
    A state nothing marks into contributes nothing: a bullet there is not
    waiting on a verb. See docs/method.md#marking
    """
    marked = declaration.marked_states
    said: list[dict[str, Any]] = []
    for one in found:
        heading = one.state.sub_phases
        if heading is None or one.state.name not in marked:
            continue
        said += [
            {BULLET_ITEM: one.slug, BULLET_NAME: bullet.name, BULLET_REST: bullet.rest}
            for bullet in subphase.bullets(
                one.body, heading, pending=one.state.pending
            )
            if bullet.unmarkable
        ]
    return said


def _register(
    declaration: Declaration, found: Sequence[Item],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """The two register reports and the register itself, over one read of
    each archive.

    The archive's existence is guaranteed by the declaration and checked at
    every invocation, so there is no missing-file arm here. A register is per
    numbered state, and each record says which it belongs to by the state's
    declared name.

    The mapping below is `fileplan.transition._mint`'s, with one difference:
    nothing is excluded, because a read has no item it is moving. The
    arithmetic over it is `fileplan.numbered.missing`, which the mint refuses
    on.

    Neither report refuses. A heading the register cannot read still refuses
    every mint, where a write is about to happen; here it is named, because a
    listing that refused would wedge the read a person would use to find it.

    The third return is the register's own record, off the same two sources
    and the same mapping the gap walk reads. Its `floor` is the effective one,
    so a consumer needs no default of its own. Its `highest` is the number
    `fileplan.numbered.next_number` adds one to on a clean register, and a
    test pins that tie rather than a shared call.
    """
    gaps: list[dict[str, Any]] = []
    lost: list[dict[str, Any]] = []
    register: list[dict[str, Any]] = []
    for state in declaration.states.values():
        if not state.has(numbered.NAME):
            continue
        # A `numbered` state with no `archive` refuses at load.
        assert state.archive is not None
        where = state.archive
        text = (declaration.root / where).read_text(encoding="utf-8")
        lost += [
            numbered.lost(state.name, where, line, said)
            for line, said in numbered.unreadable(text)
        ]
        held: dict[str, Any] = {
            one.slug: one.get(numbered.KEY)
            for one in found
            if one.state.name == state.name
        }
        held.update({f"{where} § {one}.": one for one in numbered.numbers(text)})
        held_numbers = numbered.taken(held)
        gaps += [
            {
                numbered.STATE: state.name,
                numbered.ARCHIVE: where,
                numbered.KEY: number,
            }
            for number in numbered.missing(held_numbers, first=state.first_number)
        ]
        register.append(
            {
                numbered.STATE: state.name,
                numbered.ARCHIVE: where,
                numbered.FLOOR: state.first_number,
                numbered.HIGHEST: max(held_numbers, default=None),
            }
        )
    return gaps, lost, register


def _dependencies(
    found: Sequence[Item],
) -> tuple[
    dict[str, tuple[str, ...]], list[dict[str, Any]], list[dict[str, Any]]
]:
    """The three facts an edge gives, over one traversal: blocked, unknown,
    misordered.

    One walk of `found` rather than three, because all three ask about the
    same two mappings: what is filed, and where each filed item sits in its
    order.

    A state that names no dependency key contributes nothing. An item may
    still carry the declared key there; a fact nothing was declared to read is
    not read.
    """
    filed = {one.slug for one in found}
    places = {one.slug: one.get(queued.KEY) for one in found}
    blocking: dict[str, tuple[str, ...]] = {}
    unknown: list[dict[str, Any]] = []
    misordered: list[dict[str, Any]] = []
    for one in found:
        key = one.state.dependencies
        edges = depends.edges(one.head, key)
        if not edges or key is None:
            continue
        blocking[one.slug] = depends.blocking(edges, filed)
        unknown += [
            {depends.SLUG: one.slug, depends.KEY: key, depends.NAMES: named}
            for named in depends.unknown(edges, filed)
        ]
        misordered += depends.misordered(
            one.slug, places.get(one.slug), edges, places, key=key
        )
    return blocking, unknown, misordered


def comparison(
    key: str,
    given: str,
    values: tuple[str, ...] | None = None,
    option: str | None = None,
) -> Test:
    """One `[OP]VALUE` as a `Test`, or refuse. Pure.

    `L` is `=L`; `>=L` and `!=L` say so. A missing operator means equality
    rather than being an error, because the bare form is the common one.

    A value outside a key's declared `values` refuses by name, listing what is
    declared. The check is here rather than in `click.Choice`, which cannot
    see past the `>=`.

    `:` is the one operator naming several values, and each is refused on its
    own, so a typo among them names itself. A `:` naming no value at all
    refuses too, rather than taking the empty set and matching nothing.

    `option` is how the caller spelled it, because that is what a refusal has
    to name: a key asked through `--has` was never typed as `--<key>`. It
    defaults to `--<key>`, which keeps `--state` saying its own word.
    """
    option = option or f"--{key}"
    for candidate in OPERATORS:
        if given.startswith(candidate):
            found, wanted = candidate, given[len(candidate) :].strip()
            break
    else:
        found, wanted = "=", given

    named = _drawn(wanted) if found == DRAWN else [wanted]
    if found == DRAWN and not all(named):
        raise Refusal(
            f'{option} names an empty value in "{key}{found}{wanted}". `{DRAWN}` '
            f"names the whole set {key} may be drawn from, and an empty one "
            "matches nothing"
        )
    if values is not None:
        for one in named:
            if one not in values:
                raise Refusal(
                    f'{option} names "{one}", which is not a declared value of '
                    f'{key} (declared: {", ".join(values)})'
                )
    return Test(key=key, operator=found, value=wanted, order=values)


def filtering(declaration: Declaration, given: str) -> Test:
    """One `--has KEY[OP]VALUE` as a `Test`, or refuse. Pure.

    The read's whole filter vocabulary over a key, in one function: which key
    is being asked about, and what is being asked of it. A bare `KEY` asks
    about presence, there being nothing else it could mean.
    """
    found = [given.find(one) for one in OPERATORS if one in given]
    at = min(found, default=-1)
    key = known(declaration, "--has", (given if at < 0 else given[:at]).strip())
    if at < 0:
        return presence(key, carried=True)
    return comparison(key, given[at:].strip(), _closed(declaration, key), "--has")


def _closed(declaration: Declaration, key: str) -> tuple[str, ...] | None:
    """The set a key's value is refused against, or `None` where it has none.

    A declared key's `values`, and one derived key's: `claim-status` holds the
    probe's own words, which the tool owns rather than the tree. Every other
    key holds whatever the corpus put there.
    """
    if key == claim.STATUS:
        return claim.STATUSES
    declared = declaration.keys.get(key)
    return declared.values if declared is not None else None


def known(declaration: Declaration, option: str, key: str) -> str:
    """`--has` and `--lacks` name a key rather than a value, so the typo
    detector is here rather than in the parse."""
    if key in declaration.carried:
        return key
    raise Refusal(
        f'{option} names "{key}", which is not a key an item carries '
        f"(carried: {', '.join(declaration.carried)})"
    )


def presence(key: str, *, carried: bool) -> Test:
    """`--has KEY` and `--lacks KEY` as a `Test`.

    A key present but empty carries nothing, so it reads as missing — the rule
    a transition's `requires` uses, rather than a second one beside it.
    """
    return Test(key=key, operator=PRESENT if carried else MISSING)


def matching(
    rows: Sequence[Mapping[str, Any]], tests: Sequence[Test]
) -> list[dict[str, Any]]:
    """The rows that satisfy every test. Pure; AND, because narrowing is what
    a second filter is for."""
    return [dict(row) for row in rows if all(_satisfies(row, test) for test in tests)]


def _satisfies(row: Mapping[str, Any], test: Test) -> bool:
    value = row.get(test.key)
    if test.operator == PRESENT:
        return not _empty(value)
    if test.operator == MISSING:
        return _empty(value)
    if test.operator == "=":
        return carries(value, test.value)
    if test.operator == "!=":
        # `--lacks` is the question about absence; this is about value.
        return not carries(value, test.value)
    if test.operator == DRAWN:
        return _drawn_from(value, test.value)
    return _compares(value, test)


def _empty(value: Any) -> bool:
    return value is None or value in ("", [])


def carries(value: Any, wanted: str) -> bool:
    """A filter is text, and it matches a value's text — or any entry of a list.

    A list is the several values it holds rather than one value, so filtering
    a list-valued key on one entry asks the question a person means by it.

    Public, and read by `fileplan.transition` too: `refuses` asks exactly this
    of a head, and a second copy of the rule is how the filter and the
    precondition come to disagree about what a value is. See
    docs/method.md#the-listing
    """
    return any(str(entry) == wanted for entry in _entries(value))


def _entries(value: Any) -> list[Any]:
    """The several values a head value holds, whether it holds one or many.

    Below `carries` rather than beside it: this is the shape question, and
    `carries` is the one home of the text-match rule. Every reader
    of a value at this layer asks it, so none of them can come to a different
    answer about what a list is.
    """
    if value is None:
        return []
    return list(value) if isinstance(value, list) else [value]


def _drawn(given: str) -> list[str]:
    """The several values a `:` names, split and stripped.

    One home, asked twice: by `comparison`, which refuses each of them against
    the key's declared `values`, and by `_drawn_from`, which matches on them. A
    declared value carrying a comma cannot be named this way, and refuses by
    name there rather than matching nothing here.
    """
    return [one.strip() for one in given.split(",")]


def _drawn_from(value: Any, wanted: str) -> bool:
    """Every value the head carries is one of the several `wanted` names.

    A key the item does not carry is **false**, unlike `!=`: `--has` is the
    presence word, and a guard has to be conservative about an item that says
    nothing. Over a single-valued key this degenerates to "is one of", which
    is the same rule rather than a second one. See docs/method.md#the-listing
    """
    if _empty(value):
        return False
    named = _drawn(wanted)
    return all(
        any(carries(entry, one) for one in named) for entry in _entries(value)
    )


def _compares(value: Any, test: Test) -> bool:
    entries = _entries(value)
    return any(
        (pair := _pair(entry, test)) is not None
        and _ORDERED[test.operator](*pair)
        for entry in entries
        if entry is not None
    )


def _pair(entry: Any, test: Test) -> tuple[Any, Any] | None:
    """`(this entry, what it is tested against)`, comparable, or `None`.

    Three rules, first match wins: a closed key orders by its declared
    `values`; numbers compare as numbers when both sides are ones, so
    `position >= 100` does not exclude `50` by the accident of how text sorts;
    anything else compares as text.
    """
    if test.order is not None:
        here = _place(entry, test.order)
        return None if here is None else (here, _place(test.value, test.order))
    here, against = _number(entry), _number(test.value)
    if here is not None and against is not None:
        return (here, against)
    return (str(entry), test.value)


def _number(value: Any) -> float | None:
    """`value` as a number, or `None` if it is not one."""
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _place(entry: Any, order: tuple[str, ...]) -> int | None:
    """Where `entry` sits in a closed key's declared `values`, or nowhere.

    A value the key never declared has no place, so it matches no ordered test
    rather than being sorted somewhere arbitrary.
    """
    return order.index(str(entry)) if str(entry) in order else None


# --------------------------------------------------------------------------
# The handle: a unique slug prefix, tree-wide
# --------------------------------------------------------------------------


def resolve(declaration: Declaration, handle: str) -> Item:
    """The one item `handle` names, or refuse. Never guesses.

    Tree-wide, because it is the same traversal the listing is: a verb aimed
    at an item in the wrong state would otherwise say "no such item". The
    caller compares states itself and says where the item actually is.

    Three rules: a full slug always names itself, ahead of a longer slug it
    prefixes; an ambiguous prefix names its candidates; one matching nothing
    names its near misses. The arithmetic is `chosen`, so `show` applies them
    to the rows it already has. See docs/method.md#the-handle
    """
    found = items(declaration)
    slug = chosen([(one.slug, str(one.path)) for one in found], handle)
    return next(one for one in found if one.slug == slug)


def chosen(named: Sequence[tuple[str, str]], handle: str) -> str:
    """The one slug `handle` names, or refuse. Pure.

    `named` is `(slug, where)`, `where` being whatever text names the file:
    the only refusal that needs it is the duplicated slug, and what a reader
    wants there is somewhere to look. One home for the three rules, because
    two callers have them — the handle a verb resolves and the handle `show`
    names.
    """
    exact = [where for slug, where in named if slug == handle]
    if len(exact) == 1:
        return handle
    if exact:
        raise Refusal(
            f'the slug "{handle}" is held by {len(exact)} files — '
            f'{", ".join(exact)}. A slug is unique '
            "across every state, because it is the one handle an item answers to"
        )

    matches = [slug for slug, _ in named if slug.startswith(handle)]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise Refusal(
            f'"{handle}" names {len(matches)} items — '
            f'{", ".join(matches)}. Say more'
        )

    near = difflib.get_close_matches(
        handle, [slug for slug, _ in named], n=3, cutoff=0.4
    )
    nearest = f" (nearest: {', '.join(near)})" if near else ""
    raise Refusal(f'no item starts with "{handle}"{nearest}')
