"""The generic executor: one code path for every declared transition.

`execute` holds the run lock for the whole of its body. `execute` then
branches three ways on what the declaration says. A transition with no `from`
creates an item. A transition declaring `dissolves` takes the file away.
Everything else moves the file between directories, and one declaring
`retitles` moves it to a new name as well. No transition's name
appears here, or anywhere under `src/`.

The capability arms resolve before anything is written. So every refusal
leaves the source byte for byte as it was. `--check` stops at that seam. The
arms share no protocol, and each hands back a different kind of thing.

`release` lives here too, because releasing a claim mutates under the run
lock.

See docs/method.md#the-check
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from fileplan import claim, depends, item, numbered, queued, read, subphase
from fileplan.declaration import (
    CAPABILITY_KEYS,
    Declaration,
    Key,
    Refusal,
    State,
    Transition,
    named,
)
from fileplan.lock import run_lock


# --------------------------------------------------------------------------
# Preconditions: pure over a head
# --------------------------------------------------------------------------


def offer_errors(head: Mapping[str, Any], transition: Transition) -> list[str]:
    """Every way `head` is not something `transition` could take right now.

    Its `requires` and `refuses`, and nothing else. A key present but empty
    carries nothing, so it reads as missing rather than as satisfied, and
    `refuses` asks `read.carries` so a list is the several values it holds.
    A key refused on presence refuses any value at all.
    Pure: no filesystem, no cwd.
    See docs/method.md#the-next-read
    """
    errors = [
        f'{transition.name} requires "{key}", which this item does not carry'
        for key in transition.requires
        if _missing(head, key)
    ]
    errors += [
        f'{transition.name} refuses {key} = "{entry}"'
        for key, refused in transition.refuses.items()
        if not _missing(head, key)
        for entry in refused
        if read.carries(head[key], entry)
    ]
    errors += [
        f'{transition.name} refuses an item carrying "{key}"'
        for key in transition.refuses_any
        if not _missing(head, key)
    ]
    return errors


def value_errors(
    given: Mapping[str, Any],
    transition: Transition,
    keys: Mapping[str, Key],
) -> list[str]:
    """Every way what a run was given is the wrong shape for the key.

    A list-valued key given one value, and a single-valued key given a list,
    each refuse by name before either arm.
    See docs/method.md#list-valued
    """
    errors: list[str] = []
    for key in transition.sets:
        if key not in given:
            continue
        declared = keys.get(key)
        holds_several = declared is not None and declared.list_valued
        given_several = isinstance(given[key], list)
        if holds_several and not given_several:
            errors.append(
                f'{transition.name} sets "{key}", which is list-valued, and '
                "this run gave it one value rather than a list"
            )
        elif given_several and not holds_several:
            errors.append(
                f'{transition.name} sets "{key}", which holds one value, and '
                "this run gave it a list"
            )
    return errors


def dangle_errors(
    owner: item.Item,
    transition: Transition,
    others: Sequence[item.Item],
    root: Path,
) -> list[str]:
    """Every way `owner` is not something `transition` may take away yet.

    Fires on a verb that both `archives` and `dissolves`, over every other
    item read through its own state's `opened-for` key. Pure.
    See docs/method.md#the-dangle-check
    """
    if not (transition.archives and transition.dissolves):
        return []

    errors: list[str] = []
    for one in others:
        key = one.state.opened_for
        if one.path == owner.path or key is None or not one.state.sub_phases:
            continue
        if str(one.get(key, "")) != owner.slug:
            continue
        carried = subphase.bullets(
            one.body,
            one.state.sub_phases,
            pending=one.state.pending,
            marks=one.state.marks,
        )
        # The pending bullet is dropped. See docs/method.md#carrier
        undisposed = [bullet for bullet in carried if bullet.mark is None]
        if not undisposed:
            continue
        errors.append(
            f"{named(one.path, root)} names it in {key}, and {len(undisposed)} of its "
            f"{len(carried)} {subphase.NAME} carry no mark. A record filed "
            "now would not have that work in it, and taking the item away "
            f"leaves nothing for {key} to name"
        )
    return errors


def unmarked_errors(owner: item.Item, transition: Transition) -> list[str]:
    """Every sub-phase of `owner` that `transition` would file a record over.

    Fires on a verb that both `archives` and `dissolves`, and the pending
    marker counts here where `dangle_errors` drops it. Pure.
    See docs/method.md#the-close-check
    """
    heading = owner.state.sub_phases
    if not (transition.archives and transition.dissolves) or not heading:
        return []
    marks = owner.state.marks
    carried = subphase.bullets(owner.body, heading, pending=None, marks=marks)
    if not (open_ := subphase.unmarked(owner.body, heading, marks)):
        return []
    return [
        f"it carries {len(open_)} of {len(carried)} {subphase.NAME} with "
        f"no mark: {', '.join(open_)}. A record filed now would not have "
        "them in it, and the body it is written from goes away with the run"
    ]


def _missing(head: Mapping[str, Any], key: str) -> bool:
    return key not in head or head[key] in ("", [])


# --------------------------------------------------------------------------
# The edge: one execution for both shapes
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _Running:
    """One run of one transition: what `execute` was given, threaded down.

    Carries nothing derived, so a field on it is a thing the caller said.
    """

    declaration: Declaration
    transition: Transition
    #: The title of a verb that creates, the item handle of one that moves.
    name: str
    #: `--body` as given. What a run writes is `_bulleting`'s answer.
    body: str | None
    #: The verb's `sets` keys, the ones given nothing already dropped.
    given: Mapping[str, Any]
    #: What the destination state's capabilities were asked for.
    asked: Mapping[str, Any]
    #: Where a run says something it was not asked to do.
    say: Callable[[str], None]
    #: Stop at the seam each arm documents, having written nothing.
    check: bool = False


def execute(
    declaration: Declaration,
    transition: Transition,
    *,
    name: str | Sequence[str],
    body: str | None = None,
    values: Mapping[str, Any] | None = None,
    asked: Mapping[str, Any] | None = None,
    announce: Callable[[str], None] | None = None,
    check: bool = False,
) -> Path | str | tuple[Path, ...]:
    """Run `transition`, returning the file it wrote, or raise `Refusal`.

    `name` is the title of a verb that creates, the item handle of one that
    moves. A verb that absorbs also takes a sequence of handles, and then
    hands back a tuple of paths, or its check's sentences one per line: the
    shape follows what was passed, never how many. `values` holds the verb's
    `sets` keys, `asked` what the destination state's capabilities were asked
    for, and `announce` is where a run says something it was not asked to do. `check` runs this identical path and
    stops at the seam each arm documents, handing back `_would`'s sentence
    instead of a path.
    See docs/method.md#the-check
    """
    given = {key: value for key, value in (values or {}).items() if value is not None}
    # Before the lock and before either arm, so `--check` says it in the same words.
    if wrong := value_errors(given, transition, declaration.keys):
        raise Refusal(wrong)
    several = not isinstance(name, str)
    handles = (name,) if isinstance(name, str) else tuple(name)
    if several and not transition.absorbs:
        raise Refusal(
            f"{transition.name} takes one item, and only a transition that "
            "absorbs takes several"
        )
    running = _Running(
        declaration=declaration,
        transition=transition,
        name="" if several else handles[0],
        body=body,
        given=given,
        asked=dict(asked or {}),
        say=announce or _unheard,
        check=check,
    )
    with run_lock(declaration.root):
        if transition.source is None:
            return _create(running)
        if transition.dissolves:
            wrote = _dissolve(running, handles)
            return wrote if several or isinstance(wrote, str) else wrote[0]
        return _move(running)


def _unheard(said: str) -> None:
    """The default `announce`: a caller that asked for no notices gets none."""


# --------------------------------------------------------------------------
# The check: what a run would do, said at the seam it stops at
# --------------------------------------------------------------------------


def _would(
    opening: str,
    root: Path,
    *,
    entering: Mapping[str, Any] | None = None,
    dropping: Sequence[str] | None = None,
    claiming: _Claiming | None = None,
    archiving: _Archiving | None = None,
    clearing: _Clearing | None = None,
    filing: _Filing | None = None,
    writing: str | None = None,
    renaming: _Renaming | None = None,
    carrying: Path | None = None,
) -> str:
    """The one sentence `--check` prints: what this run would do.

    Built from the effects the arm has already resolved, never re-read off the
    declaration, so a clause's absence is meaningful. `dropping` is the keys
    the head actually carries that this verb takes away.
    See docs/method.md#the-check
    """
    said: list[str] = []
    if entering is not None:
        if (place := entering.get(queued.KEY)) is not None:
            said.append(f"write {queued.KEY} {place}")
        if (number := entering.get(numbered.KEY)) is not None:
            said.append(f"write {numbered.KEY} {number}")
    # Beside the head keys the run writes: what the head will carry afterwards.
    said += [f"drop {key}" for key in dropping or ()]
    if claiming is not None:
        if claiming.take is not None:
            said.append("take the claim")
        elif claiming.free:
            said.append("free the claim")
    if writing is not None:
        said.append(writing)
    if renaming is not None:
        said.append(f'title it "{renaming.title}"')
        if renaming.follows:
            said.append(f"move the claim to {renaming.slug}")
        if renaming.clearing.edits:
            where = ", ".join(named(one.path, root) for one in renaming.clearing.edits)
            said.append(f"repoint the references to it in {where}")
    if filing is not None:
        said.append(f"file {named(filing.path, root)}")
    if archiving is not None:
        said.append(
            f"file `{archiving.heading}` in {named(archiving.path, root)}"
        )
    if clearing is not None and clearing.edits:
        where = ", ".join(named(one.path, root) for one in clearing.edits)
        said.append(f"clear the edge to it in {where}")
    if carrying is not None:
        said.append(f"carry its body into {named(carrying, root)}")
    return f"{opening}, and would {_listed(said)}" if said else opening


def _listed(said: list[str]) -> str:
    """`a`, `a and b`, `a, b and c` — a sentence rather than a list."""
    if len(said) == 1:
        return said[0]
    return ", ".join(said[:-1]) + f" and {said[-1]}"


def _create(running: _Running) -> Path | str:
    body = running.body
    # The seeding refusals first, all above the reservation below.
    template = running.asked.get(_TEMPLATE)
    if template is not None:
        if body is not None and body.strip():
            raise Refusal(
                f"{running.transition.name} was given both --from and --body, and an "
                "item has one body. Two content sources for one run is a "
                "question rather than a default: pass the template, or pass "
                "the prose"
            )
        seeding = running.declaration.templates.get(str(template))
        if seeding is None:
            declared = ", ".join(running.declaration.templates)
            raise Refusal(
                f'no template is called "{template}". '
                + (
                    f"The templates declared are {declared}"
                    if declared
                    else "No templates are declared at all, which is a "
                    "workflow that has not written one yet"
                )
            )
        # Existence and emptiness are `declaration.pointer_errors`' half.
        body = (running.declaration.root / seeding.doc).read_text()
    if body is None or not body.strip():
        raise Refusal(_bodiless(running.transition))

    stem = item.slug(running.name)
    held = _held_by(running.declaration, stem)
    if held is not None:
        raise Refusal(_taken(stem, held, running.declaration.root))
    state = running.declaration.states[running.transition.to]
    if errors := read.edge_errors(running.declaration, state, running.given):
        raise Refusal([f"{running.transition.name} cannot file {stem}", *errors])

    # Both before the reservation below, which is itself a write.
    claiming = _claiming(running, slug=stem)
    entering = _entering(running)

    destination = (
        _directory(running, make=not running.check) / f"{stem}{item.SUFFIX}"
    )
    if running.check:
        # The seam: the reservation below is a write, partway through this arm.
        return _would(
            f"{running.transition.name} would file {named(destination, running.declaration.root)}",
            running.declaration.root,
            entering=entering,
            claiming=claiming,
            # From what this arm resolved, like every other clause.
            writing=(
                None
                if template is None
                else f'take its body from the "{template}" template'
            ),
        )
    try:
        # The filename is the reservation: two sessions cannot both win.
        with destination.open("x"):
            pass
    except FileExistsError:
        raise Refusal(_taken(stem, destination, running.declaration.root)) from None

    head = {"title": running.name}
    head.update({key: running.given[key] for key in running.transition.sets if key in running.given})
    head.update(entering)
    _place(running, destination, head, _prose(body))
    _apply(claiming, running.declaration.root)
    return destination


def _cursor_errors(running: _Running, original: item.Item, body: str) -> list[str]:
    """Whether the cursor this run would leave behind fits the body's count.

    Graded against the destination state, on the value the run would write and
    the body it would write, not on what is already filed.
    See docs/method.md#the-cursor
    """
    state = running.declaration.states[running.transition.to]
    if not state.cursor or not state.sub_phases:
        return []

    head = dict(original.head)
    if state.cursor in running.transition.drops:
        head.pop(state.cursor, None)
    writes = state.cursor in running.transition.sets and state.cursor in running.given
    if writes:
        head[state.cursor] = running.given[state.cursor]
    return subphase.cursor_errors(
        head,
        body,
        key=state.cursor,
        heading=state.sub_phases,
        written=writes,
        marks=state.marks,
    )


def _reading(running: _Running) -> tuple[item.Item, _Claiming]:
    """The item `running.name` names, and what this verb does to its claim.

    The preamble `_move` and `_dissolve` share: resolve the handle tree-wide,
    refuse an item that is somewhere else, settle the claim. Nothing written.
    """
    assert running.transition.source is not None
    original = read.resolve(running.declaration, running.name)
    if original.state.name != running.transition.source:
        # Tree-wide, so this can say where the item actually is.
        raise Refusal(
            f"{named(original.path, running.declaration.root)} is in {original.state.name}, and "
            f"{running.transition.name} moves an item out of {running.transition.source}"
        )
    return original, _claiming(running, slug=original.slug)


def _move(running: _Running) -> Path | str:
    original, claiming = _reading(running)
    source = original.path

    # Head keys, then body, then the cursor check: each is what the next is
    # graded against. None of the three writes anything.
    entering = _entering(running, moving=original.slug)
    _unread_errors(running, original, entering)
    # Once, before the two arms that need it: the body arm and the filing arm.
    disposing = _disposing(running, original)
    body, notice, writing = _bulleting(
        running, original, entering=entering, disposing=disposing
    )
    # Before the shed below drops every capability key: an entry is filed under
    # the number the item carried in the state it is leaving.
    archiving = _archiving(running, original)
    filing = _filing(running, original, disposing)
    renaming = _renaming(running, original, claiming)

    errors = offer_errors(original.head, running.transition)
    errors += read.edge_errors(
        running.declaration, running.declaration.states[running.transition.to], running.given
    )
    errors += _cursor_errors(running, original, body)
    if errors:
        # Nothing written yet, and nothing will be.
        raise Refusal(
            [f"{named(source, running.declaration.root)} cannot {running.transition.name}", *errors]
        )

    # Resolved beside the rebuild, so the check can only name what this run
    # really takes off. The capability keys shed below are not among these.
    dropped = [key for key in running.transition.drops if key in original.head]
    head = {
        key: value
        for key, value in original.head.items()
        if key not in running.transition.drops and key not in CAPABILITY_KEYS.values()
    }
    head.update({key: running.given[key] for key in running.transition.sets if key in running.given})
    head.update(entering)
    if renaming is not None:
        head["title"] = renaming.title

    destination = _directory(running, make=not running.check) / (
        source.name if renaming is None else f"{renaming.slug}{item.SUFFIX}"
    )
    moving = destination.resolve() != source.resolve()
    if moving and destination.exists():
        # The backstop: a duplicate appearing between the read and the write.
        raise Refusal(_taken(source.stem, destination, running.declaration.root))

    # Read before the write, so a run that leaves the file as it was can say so.
    before = None if moving or running.check else source.read_bytes()
    _place(running, destination, head, body)
    if running.check:
        # The seam, inside `_place`: the head is the last thing a run refuses over.
        return _would(
            f"{running.transition.name} would move {named(source, running.declaration.root)} to "
            f"{named(destination, running.declaration.root)}"
            if moving
            else f"{running.transition.name} would rewrite "
            f"{named(source, running.declaration.root)}, which stays in {running.transition.to}",
            running.declaration.root,
            entering=entering,
            dropping=dropped,
            claiming=claiming,
            archiving=archiving,
            filing=filing,
            writing=writing,
            renaming=renaming,
        )
    if moving:
        source.unlink()
    _apply(claiming, running.declaration.root)
    if renaming is not None:
        _rename(running, original, renaming)
    _file(archiving)
    _file_it(running, filing)
    if archiving is not None:
        running.say(archiving.notice)
    if filing is not None:
        running.say(filing.notice)
    if notice is not None:
        # After the write: a notice says what a run did.
        running.say(notice)
    if before == destination.read_bytes():
        running.say(
            f"{named(destination, running.declaration.root)} is unchanged: "
            f"{_unchanged(running, claiming)}"
        )
    return destination


def _unchanged(running: _Running, claiming: _Claiming) -> str:
    """Why a run that wrote the item's file left every byte as it was.

    A claim taken with nothing else given is a real effect and exits 0, as
    does a bare mint on a section already open. The notice is what tells
    either apart from a run that wrote.
    See docs/method.md#bulleted and docs/method.md#the-claimed-state
    """
    if claiming.take is not None:
        return "the claim was taken, and nothing else was given"
    state = running.declaration.states[running.transition.to]
    if running.transition.mints and not any(running.asked.get(key) for key in _MINTING):
        return f'"{state.sub_phases}" is already open, so a bare run writes nothing'
    return "nothing given changes it"


def _entering(running: _Running, *, moving: str | None = None) -> dict[str, Any]:
    """What the destination state's capabilities give the item, or refuse.

    The one seam both shapes go through, resolved before anything is written.
    Written on entry and, because `_move` sheds every capability key first,
    dropped on exit. An item already in this state keeps its place and its
    number unless a placement option asks otherwise, and is excluded from what
    the arithmetic sees.
    """
    state = running.declaration.states[running.transition.to]
    ordered, mints = state.has(queued.NAME), state.has(numbered.NAME)
    if not ordered and not mints:
        return {}

    places: dict[str, Any] = {}
    held: dict[str, Any] = {}
    place, number = None, None
    for one in read.items(running.declaration):
        if one.state.name != state.name:
            continue
        if one.slug == moving:
            place, number = one.get(queued.KEY), one.get(numbered.KEY)
            continue
        places[one.slug] = one.get(queued.KEY)
        held[one.slug] = one.get(numbered.KEY)

    given: dict[str, Any] = {}
    if ordered:
        request = {
            flag: _anchor(running.declaration, state, value) if flag in _ANCHORS else value
            for flag in _PLACEMENT
            if (value := running.asked.get(flag)) is not None
        }
        given[queued.KEY] = queued.place(
            places, current=place if isinstance(place, int) else None, **request
        )
    if mints:
        given[numbered.KEY] = _mint(running.declaration, state, held, current=number)
    return given


def _mint(
    declaration: Declaration,
    state: State,
    held: Mapping[str, Any],
    *,
    current: Any,
) -> int:
    """The number this item takes in `state`, or raise `Refusal`.

    The register's second source, the archive headings, is read here rather
    than in `fileplan.numbered`, which is pure. Under the run lock `execute`
    holds, which makes it a reservation rather than a reading.
    See docs/method.md#the-register
    """
    assert state.archive is not None  # a numbered state with none refuses at load.
    where = state.archive
    text = (declaration.root / where).read_text(encoding="utf-8")
    if lost := numbered.heading_errors(numbered.unreadable(text), where):
        raise Refusal(lost)

    taken = dict(held)
    taken.update({f"{where} § {one}.": one for one in numbered.numbers(text)})
    return numbered.next_number(
        numbered.taken(taken),
        current=current if isinstance(current, int) else None,
        first=state.first_number,
    )


#: The placement requests that name another item rather than a place.
_ANCHORS = ("above", "below")

#: Every flag the ordered capability answers to. Each arm picks its own out
#: of `asked`, because two capabilities now put options on one verb.
_PLACEMENT = (*_ANCHORS, "at")

#: The same, for the capability that writes a body: a title to mint, and
#: whether this is the last one.
_MINTING = ("title", "last")

#: The one the `marks` half takes: which bullet this run acts on, a positional
#: on the command line. See docs/method.md#marking
_MARKING = "name"

#: The one any disposition may take beside it: why. Optional, unlike every
#: other half's option. See docs/method.md#marking
_NOTE = "note"

#: The one a verb that both archives and dissolves takes: the prose that goes
#: under the entry's heading. See docs/method.md#dissolving
_RECORD = "record"

#: The one a verb that absorbs takes: the item the work continues as, required
#: there and resolved tree-wide. See docs/method.md#dissolving
_INTO = "into"

#: The flag a verb that `carries` takes: append each absorbed item's body to
#: the survivor. See docs/method.md#merge
_CARRY = "carry"

#: The one a verb that retitles takes: the item's new title, a positional on
#: the command line. See docs/method.md#retitle
_RETITLE = "new_title"

#: The one a verb that seeds takes: the declared template the new item's body
#: is copied from, entire. The CLI spells it `--from`. See docs/method.md#seeds
_TEMPLATE = "template"

#: The one a verb that `claims` takes: hold this claim beside others this
#: session already holds, rather than refusing over them. A flag, and the
#: less safe of the two, so the default stays the loud one.
#: See docs/method.md#the-claimed-state
_KEEP_CLAIMS = "keep_claims"

#: The two a verb that files takes: what to call the item it creates, and the
#: prose that goes in it. `title` is optional, `body` is not.
#: See docs/method.md#filing
_FILING = ("title", "body")


def _unread_errors(
    running: _Running, original: item.Item, entering: Mapping[str, Any]
) -> None:
    """Refuse a mint or a mark into a body carrying a bullet the reader passes
    over, naming its line.

    A mint hands out the highest ordinal it can read plus one, so a hidden
    bullet's name comes out twice, and a mark cannot reach it at all. The
    listing reports the same bullets through `read.unread`.
    See docs/method.md#sub-phases
    """
    if running.transition.marks is None and not running.transition.mints:
        return
    state = running.declaration.states[running.transition.to]
    if passed := read.unread(state, original.body, entering):
        where = named(original.path, running.declaration.root)
        raise Refusal(
            [
                f"{where} carries a bullet the reader passes over, so this run "
                "would write beside a sub-phase nothing counts",
                *(
                    f"{where}:{original.opening + one.line}: {one.reason}"
                    for one in passed
                ),
            ]
        )


def _disposing(running: _Running, original: item.Item) -> subphase.Bullet | None:
    """The bullet this run disposes of, or `None` where it disposes of none.

    Resolved once for the two arms that need it: the body arm writes the word
    onto the bullet, the filing arm writes an item from it. All three of a
    disposition's refusals are here, before `_move` has written a byte, and
    their **order is load-bearing**: a marked bullet's rest is its own mark
    run, so asking the third question first would refuse every second
    disposition with the wrong sentence. `Bullet.unmarkable` carries that
    second clause itself, and the order is what makes reading it here the
    same question as `found.rest is not None`.
    See docs/method.md#marking
    """
    if running.transition.marks is None:
        return None
    state = running.declaration.states[running.transition.to]
    # A `marks` into a state that is not `bulleted` refuses back in plan.toml.
    assert state.sub_phases is not None
    wanted = running.asked.get(_MARKING)
    carried = subphase.bullets(
        original.body, state.sub_phases, pending=state.pending, marks=state.marks
    )
    found = next((one for one in carried if one.name == wanted), None)
    if found is None:
        # One sentence, one home: `show ITEM NAME` refuses in these words too.
        raise Refusal(
            subphase.unknown(
                named(original.path, running.declaration.root), wanted, carried, state.sub_phases
            )
        )
    if found.mark is not None:
        raise Refusal(
            f"{named(original.path, running.declaration.root)} has already disposed of "
            f"{found.name}: it is "
            f'marked "{found.mark}". A finding is disposed of once, so '
            "there is one answer on the bullet rather than a history "
            "nobody can read an answer out of"
        )
    if found.unmarkable:
        raise Refusal(
            f"{named(original.path, running.declaration.root)} cannot mark {found.name}: it carries "
            f'"{found.rest}" after its bold run, and a mark is read only '
            "immediately after that run — so the word would be written "
            "where nothing reads it. Move the prose inside the bold run, "
            "or onto a continuation line under the bullet"
        )
    return found


def _bulleting(
    running: _Running,
    original: item.Item,
    *,
    entering: Mapping[str, Any],
    disposing: subphase.Bullet | None = None,
) -> tuple[str, str | None, str | None]:
    """The body this run writes, what it changed, and what a check would say.

    The body is `original`'s, or one with a sub-phase minted into it, or one
    with a mark written onto the bullet `_disposing` resolved. One arm, not
    two: a verb declaring both `mints` and `marks` refuses back in `plan.toml`.
    A mint names its bullet from `entering`, the values this run writes, not
    from the head on disk, and re-opening a finished decomposition is
    announced rather than refused.

    The third value is the clause `--check` says about the body.
    See docs/method.md#bulleted and docs/method.md#marking
    """
    if running.transition.marks is not None:
        assert disposing is not None  # `_disposing` resolves it, or refuses.
        state = running.declaration.states[running.transition.to]
        assert state.sub_phases is not None
        note = running.asked.get(_NOTE)
        if note is not None and (wrong := subphase.note_errors(note)):
            raise Refusal(
                [f"{named(original.path, running.declaration.root)} cannot take that note", *wrong]
            )
        return (
            subphase.mark(
                original.body,
                heading=state.sub_phases,
                name=disposing.name,
                word=running.transition.marks,
                note=note,
            ),
            None,
            f'mark {disposing.name} "{running.transition.marks}"'
            # Its presence, never its content.
            + (" with a note" if note else ""),
        )

    if not running.transition.mints:
        return original.body, None, None

    state = running.declaration.states[running.transition.to]
    # A `bulleted` state missing any of the three refuses back in plan.toml.
    assert (
        state.sub_phases is not None
        and state.pending is not None
        and state.sub_phase_name is not None
    )
    # What the form names, the item has to carry.
    if absent := subphase.absent(state.sub_phase_name, entering):
        raise Refusal(
            f"{named(original.path, running.declaration.root)} carries no {', '.join(absent)}, and "
            f"{state.name} names its bullets \"{state.sub_phase_name}\" — "
            "so this run has nothing to name one from"
        )

    title = running.asked.get(_MINTING[0])
    last = bool(running.asked.get(_MINTING[1]))
    if title is not None and (wrong := subphase.title_errors(title)):
        raise Refusal(
            [f"{named(original.path, running.declaration.root)} cannot take that sub-phase", *wrong]
        )

    notice = None
    if (
        title is not None
        and not last
        and subphase.opens(
            original.body, heading=state.sub_phases, pending=state.pending
        )
    ):
        notice = (
            f"{original.slug} had no sub-phase left pending under "
            f'"{state.sub_phases}", so this re-opens it: "{state.pending}" '
            "is back. Finish with --last to take it out again"
        )

    return (
        subphase.mint(
            original.body,
            heading=state.sub_phases,
            prefix=subphase.prefix(state.sub_phase_name, entering),
            pending=state.pending,
            title=title,
            last=last,
        ),
        notice,
        "put the pending bullet back" if notice is not None else None,
    )


@dataclass(frozen=True)
class _Archiving:
    """The archive entry a transition files, resolved before anything is written.

    `text` is the finished archive, computed before the item moves, so every
    refusal an entry can raise happens with both files still byte-identical.
    """

    path: Path
    #: The archive as it will be, entry inserted at its place in the register.
    text: str
    #: What the operator is told was minted, and that a record goes under it.
    notice: str
    #: The entry's heading, spelled once and quoted by both reporters.
    heading: str = ""


def _archiving(
    running: _Running, original: item.Item, *, record: str = ""
) -> _Archiving | None:
    """The entry `transition` files for `original`, or `None`. No writes.

    Only a verb that declares `archives` files one, into the source state's
    `archive`. Three refusals, all before any write: a `##` the register
    cannot read, an item carrying no number, and a number the archive already
    holds. `record` is the prose under the heading, and is empty for every
    verb that moves the item rather than dissolving it.
    See docs/method.md#the-register
    """
    if not running.transition.archives:
        return None

    assert running.transition.source is not None
    state = running.declaration.states[running.transition.source]
    # Both halves refuse back in plan.toml, so there is always a document here.
    assert state.archive is not None
    where = state.archive
    path = running.declaration.root / where
    text = path.read_text(encoding="utf-8")
    if lost := numbered.heading_errors(numbered.unreadable(text), where):
        raise Refusal(lost)

    number = original.get(numbered.KEY)
    if not isinstance(number, int) or isinstance(number, bool):
        raise Refusal(
            f"{named(original.path, running.declaration.root)} carries no {numbered.KEY}, and "
            f"{running.transition.name} "
            f"files it in {where} as `## <number>. <title>`. An entry with no "
            "number is the record the register cannot read — fix the item's "
            f"{numbered.KEY} before filing it"
        )

    title = original.get("title")
    heading = f"## {number}. {title}"
    return _Archiving(
        path=path,
        text=numbered.entry(text, number, str(title), record),
        heading=heading,
        notice=(
            f"{where}: filed `{heading}` at its place in the "
            "register, with the record under it"
        )
        if record.strip()
        else (
            f"{where}: minted `{heading}` at its place in the "
            f"register, with nothing under it. Write the record there — "
            f"{original.slug} is still filed, so what it was is still "
            "readable"
        ),
    )


def _file(archiving: _Archiving | None) -> None:
    """The archive's half of the effect, after the item has landed.

    The item is written first and the entry second: a crash between them
    leaves a gap in the register, which is reported and which a person fixes.
    """
    if archiving is not None:
        item.replace(archiving.path, archiving.text)


@dataclass(frozen=True)
class _Filing:
    """The second item a transition creates, resolved before any write.

    Every refusal a filing can raise is raised while it is built, so a run
    that files refuses with both files byte-identical and a check reserves
    nothing.
    """

    #: Where the new item lands: the `files.state` directory, its slug.
    path: Path
    #: Its head: the title, and the two declared keys naming where it came from.
    head: Mapping[str, Any]
    body: str
    #: The one line the operator is told, naming both files.
    notice: str
    #: The state the head is graded against: the verb's, not the run's.
    state: State


def _filing(
    running: _Running, original: item.Item, disposing: subphase.Bullet | None
) -> _Filing | None:
    """The item `transition` files from `disposing`, or `None`. No writes.

    Only a verb that declares `files` files one. In order, every step before
    the first write: the title, `--title` or the bullet's own text; the body,
    `--body`, refused empty in `_bodiless`' words; the slug, through the
    creating verb's own collision helpers; the head, the title plus the two
    declared keys the `files` table names.
    See docs/method.md#filing
    """
    if running.transition.files is None:
        return None
    assert disposing is not None  # `files` rides on `marks`, refused at load.

    title = running.asked.get(_FILING[0]) or disposing.title
    if title is None or not title.strip():
        raise Refusal(
            f"{named(original.path, running.declaration.root)}'s {disposing.name} says only its name, so "
            f"{running.transition.name} has nothing to call the item it files. Give "
            "the bullet a title, or name one with --title TEXT"
        )
    body = running.asked.get(_FILING[1])
    if body is None or not str(body).strip():
        raise Refusal(_bodiless(running.transition))

    stem = item.slug(title)
    held = _held_by(running.declaration, stem)
    if held is not None:
        raise Refusal(_taken(stem, held, running.declaration.root))

    state = running.declaration.states[running.transition.files["state"]]
    path = running.declaration.root / state.path / f"{stem}{item.SUFFIX}"
    # Not made: `make=False`, because a check leaves no directory behind.
    moved = _directory(running, make=False) / original.path.name
    return _Filing(
        path=path,
        head={
            "title": title,
            running.transition.files["item"]: original.slug,
            running.transition.files["name"]: disposing.name,
        },
        body=_prose(str(body)),
        notice=(
            f"{named(path, running.declaration.root)}: filed from {disposing.name} in "
            f"{named(moved, running.declaration.root)}, which this run marked "
            f'"{running.transition.marks}"'
        ),
        state=state,
    )


def _file_it(running: _Running, filing: _Filing | None) -> None:
    """The filed item's half of the effect, after the item the run moved.

    The item the run was given is written first: a crash between them leaves a
    marked bullet with no item filed from it, which the carrier's own body
    says out loud. The filename is the reservation, as in `_create`, and the
    directory is made through `_directory` so the `make` guard has one home.
    """
    if filing is None:
        return
    _directory(running, state=filing.state)
    try:
        with filing.path.open("x"):
            pass
    except FileExistsError:
        raise Refusal(
            _taken(filing.path.stem, filing.path, running.declaration.root)
        ) from None
    _place(running, filing.path, filing.head, filing.body, state=filing.state)


@dataclass(frozen=True)
class _Clearing:
    """The referents a dissolving verb edits, resolved before anything is written.

    `edits` is empty for every verb that does not dissolve, and for a
    dissolving verb nothing in the tree names.
    """

    edits: tuple[item.Item, ...] = ()
    #: One line per edited item, naming the file, the key and any survivor.
    notices: tuple[str, ...] = ()


def _survivor(running: _Running) -> item.Item | None:
    """The item `--into` names, or `None` when the verb does not absorb.

    Resolved tree-wide, like every other handle, and neither graded nor
    edited. Resolved once per run, so a bad `--into` refuses at once rather
    than once per item. See docs/method.md#dissolving
    """
    if not running.transition.absorbs:
        return None
    return read.resolve(running.declaration, str(running.asked.get(_INTO) or ""))


def _itself(running: _Running, original: item.Item, survivor: item.Item | None) -> None:
    """Refuse a survivor that is the item being dissolved."""
    if survivor is not None and survivor.path == original.path:
        raise Refusal(
            f"{named(survivor.path, running.declaration.root)} is the item {running.transition.name} is "
            "dissolving, and an "
            "item cannot continue as itself"
        )


def _clearing(
    root: Path,
    gone: item.Item,
    into: str | None,
    tree: Sequence[item.Item],
    keys: Callable[[item.Item], Sequence[str]],
) -> _Clearing:
    """Every referent in `tree` whose `keys` name `gone`, rewritten.

    Cleared means taken out, or pointed at `into` where there is one: the
    survivor a verb that absorbs names, or the slug a retitle moves to. Four
    rules: scope is every item in every state, read through the keys `keys`
    gives for it; a list loses or repoints its entry and stays a list, while
    a value the clearing empties loses the key; a referent another session
    holds is edited anyway; and the referent's head is not graded. `tree` is
    handed in, so several items clear over each other's edits. No writes.
    See docs/method.md#dissolving and docs/method.md#retitle
    """
    edits: list[item.Item] = []
    notices: list[str] = []
    for one in tree:
        if one.path == gone.path:
            continue
        head = dict(one.head)
        where = named(one.path, root)
        for key in keys(one):
            if gone.slug not in depends.edges(head, key):
                continue
            if into is None:
                kept = depends.without(head[key], gone.slug)
            else:
                kept = depends.repoint(head[key], gone.slug, into, own=one.slug)
            if kept is None:
                del head[key]
            else:
                head[key] = kept
            # Computed from what the head actually got, not from the branch taken.
            if into is not None and into in depends.edges(head, key):
                notices.append(f'{where}: pointed "{gone.slug}" at "{into}" in {key}')
            elif into is not None:
                notices.append(
                    f'{where}: took "{gone.slug}" out of {key} — it is this item now'
                )
            else:
                notices.append(f'{where}: took "{gone.slug}" out of {key}')
        if head != one.head:
            edits.append(item.Item(path=one.path, state=one.state, head=head, body=one.body))
    return _Clearing(edits=tuple(edits), notices=tuple(notices))


def _dependency(one: item.Item) -> tuple[str, ...]:
    """The key a dissolve clears: the referent's own state's `dependencies`."""
    return () if one.state.dependencies is None else (one.state.dependencies,)


def _references(declaration: Declaration, one: item.Item) -> tuple[str, ...]:
    """Every head key the tool reads a slug out of, for an item like `one`.

    Its state's `dependencies` and `opened-for`, and the key each verb that
    `files` names for where a filed item came from. What a retitle repoints.
    See docs/method.md#retitle
    """
    carried = [files["item"] for files in declaration.files]
    named_by = (one.state.dependencies, one.state.opened_for, *carried)
    return tuple(dict.fromkeys(key for key in named_by if key is not None))


def _clear(edits: Sequence[item.Item]) -> None:
    """The referents' half of the effect, after the item is gone.

    The unlink is first: a crash between them leaves referents naming a closed
    item, which the default read names as an `unknown dependency:` line.
    """
    for one in edits:
        item.write(one)


def _dissolve(running: _Running, handles: Sequence[str]) -> tuple[Path, ...] | str:
    """Run a verb that takes each item's file away, and clear the edges to it.

    A verb that dissolves refuses `to`, `sets`, `drops`, `mints` and `claims`
    back in `plan.toml`, so what is left is the record that outlives the item
    and the edges other items hold to it, taken out or pointed at the survivor
    `--into` names. The order is delete, file, clear, free, and every refusal
    is computed before any of it. Several handles are all or nothing: each is
    checked, the refusal names every one that fails, and one handle's refusal
    is raised as it stands.
    See docs/method.md#dissolving and docs/method.md#merge
    """
    root = running.declaration.root
    verb = running.transition.name
    if len(handles) > 1 and running.transition.archives:
        raise Refusal(
            f"{verb} takes one item, because one --record is one archive "
            f"entry, and this run named {len(handles)}"
        )
    survivor = _survivor(running)
    whole = read.items(running.declaration)
    failed: dict[int, list[str]] = {}
    taken: dict[int, tuple[item.Item, _Claiming, _Archiving | None]] = {}
    for index, handle in enumerate(handles):
        one = replace(running, name=handle)
        try:
            original, claiming = _reading(one)
            if any(original.path == seen.path for seen, *_ in taken.values()):
                raise Refusal(f'"{handle}" is named twice')
            archiving = _archiving(one, original, record=str(running.asked.get(_RECORD) or ""))
            _itself(one, original, survivor)
            taken[index] = (original, claiming, archiving)
        except Refusal as refusal:
            if len(handles) == 1:
                raise
            failed[index] = refusal.messages

    # Every item being dissolved leaves the tree, so none of them is edited.
    gone = {original.path for original, *_ in taken.values()}
    tree = {one.path: one for one in whole if one.path not in gone}
    clearings: list[_Clearing] = []
    for index, (original, claiming, archiving) in taken.items():
        clearing = _clearing(
            root,
            original,
            None if survivor is None else survivor.slug,
            list(tree.values()),
            _dependency,
        )
        # Each clearing sees the last one's edits, so the edges compose.
        tree.update((one.path, one) for one in clearing.edits)
        clearings.append(clearing)
        errors = offer_errors(original.head, running.transition)
        errors += dangle_errors(original, running.transition, whole, root)
        errors += unmarked_errors(original, running.transition)
        if errors:
            refusal = [f"{named(original.path, root)} cannot {verb}", *errors]
            if len(handles) == 1:
                raise Refusal(refusal)
            failed[index] = refusal
    carried = None
    if survivor is not None and running.transition.carries and running.asked.get(_CARRY):
        if not failed:
            carried = _carrying(running, tree[survivor.path], [one for one, *_ in taken.values()])
            tree[survivor.path] = carried
    if failed:
        raise Refusal(
            [
                f"{verb} took nothing away: {len(failed)} of {len(handles)} items refuse",
                *(said for index in sorted(failed) for said in failed[index]),
            ]
        )

    runs = list(zip(taken.values(), clearings))
    if running.check:
        # The seam: one sentence per item, each from its own claim and clearing.
        return "\n".join(
            _would(
                f"{verb} would take {named(original.path, root)} away",
                root,
                claiming=claiming,
                archiving=archiving,
                clearing=clearing,
                carrying=None if carried is None else carried.path,
            )
            for (original, claiming, archiving), clearing in runs
        )

    for original, *_ in taken.values():
        original.path.unlink()
    for _, _, archiving in taken.values():
        _file(archiving)
    # One write per referent, of its head after every clearing.
    edited = dict.fromkeys(one.path for clearing in clearings for one in clearing.edits)
    if carried is not None:
        edited[carried.path] = None
    _clear([tree[path] for path in edited])
    for _, claiming, _ in taken.values():
        _apply(claiming, root)

    for _, _, archiving in taken.values():
        if archiving is not None:
            running.say(archiving.notice)
    for clearing in clearings:
        for said in clearing.notices:
            running.say(said)
    slugs = [original.slug for original, *_ in taken.values()]
    for said in _mentions(list(tree.values()), slugs, root, f"which {verb} took away"):
        running.say(said)
    for original, *_ in taken.values():
        running.say(f"{named(original.path, root)} is gone: {verb} took it away")

    # "The file it wrote": the archive, or the path it removed where it files none.
    return tuple(
        archiving.path if archiving is not None else original.path
        for original, _, archiving in taken.values()
    )


def _carrying(
    running: _Running, survivor: item.Item, gone: Sequence[item.Item]
) -> item.Item:
    """`survivor` with each of `gone`'s bodies appended, in the order given.

    Each lands under `### <its title>`, stripped of blank lines at either
    end. Two refusals, both before any write: a survivor another session
    holds, since a carry writes prose into a body that session may be
    rewriting, and a composed body its state's sub-phase check refuses, so
    the next listing cannot. The head is not graded. No writes.
    See docs/method.md#merge
    """
    root = running.declaration.root
    state = survivor.state
    if state.has(claim.NAME):
        path = claim.path(root, survivor.slug)
        if path.exists():
            _foreign(running, survivor.slug, claim.read(path, root))
    body = survivor.body.rstrip("\n")
    for one in gone:
        carried = one.body.strip("\n")
        body += f"\n\n### {one.get('title')}\n\n{carried}"
    body += "\n"
    if state.sub_phases and (errors := subphase.errors(body, state.sub_phases)):
        raise Refusal(
            [
                f"{running.transition.name} cannot carry into "
                f"{named(survivor.path, root)}",
                *errors,
            ]
        )
    return item.Item(path=survivor.path, state=state, head=survivor.head, body=body)


def _mentions(
    tree: Sequence[item.Item], gone: Sequence[str], root: Path, tail: str
) -> list[str]:
    """One line per item whose prose still names a slug this run took away.

    A whole-word match over bodies only, since the heads' edges are the
    clearing's. It warns, and never rewrites what a person wrote. `tail` says
    what happened to the slug. See docs/method.md#dissolving
    """
    patterns = {slug: re.compile(rf"(?<![\w-]){re.escape(slug)}(?![\w-])") for slug in gone}
    said: list[str] = []
    for one in tree:
        if found := [f'"{slug}"' for slug, pattern in patterns.items() if pattern.search(one.body)]:
            said.append(
                f"{named(one.path, root)}: its prose still names {_listed(found)}, "
                + tail
            )
    return said


@dataclass(frozen=True)
class _Renaming:
    """The new name a retitle gives the item, resolved before any write."""

    title: str
    #: The slug the title makes, which is the item's own where the title keeps it.
    slug: str
    #: The referents whose references to the old slug are repointed.
    clearing: _Clearing = _Clearing()
    #: Whether this session's claim record moves to the new slug.
    follows: bool = False


def _renaming(
    running: _Running, original: item.Item, claiming: _Claiming
) -> _Renaming | None:
    """The name a verb that `retitles` gives `original`, or `None`. No writes.

    Two refusals: a title that slugs to nothing, in `item.slug`'s words, and a
    slug another file holds, in `_taken`'s. A title that keeps the slug is a
    rewrite in place, and repoints nothing. A claim another session holds has
    already refused in `_claiming`, so a record still at the old slug is this
    session's, or is the one this run takes. See docs/method.md#retitle
    """
    if not running.transition.retitles:
        return None
    root = running.declaration.root
    title = str(running.asked.get(_RETITLE) or "")
    stem = item.slug(title)
    if stem == original.slug:
        return _Renaming(title=title, slug=stem)
    if (held := _held_by(running.declaration, stem)) is not None:
        raise Refusal(_taken(stem, held, root))
    clearing = _clearing(
        root,
        original,
        stem,
        read.items(running.declaration),
        lambda one: _references(running.declaration, one),
    )
    claimed = running.declaration.states[running.transition.to].has(claim.NAME)
    record = claim.path(root, original.slug)
    return _Renaming(
        title=title,
        slug=stem,
        clearing=clearing,
        follows=claimed and (record.exists() or claiming.take is not None),
    )


def _rename(running: _Running, original: item.Item, renaming: _Renaming) -> None:
    """A retitle's half of the effect, after the new file is written and the
    old one gone: the claim, then the referents, then the notices.

    A crash before the claim moves strands it, and one before the referents
    are written leaves `unknown dependency:` lines. The default read names
    both. See docs/method.md#retitle
    """
    if renaming.slug == original.slug:
        return
    root = running.declaration.root
    if renaming.follows:
        claim.path(root, original.slug).replace(claim.path(root, renaming.slug))
    _clear(renaming.clearing.edits)
    for said in renaming.clearing.notices:
        running.say(said)
    # Read after the writes, so the renamed item's own body is asked too.
    for said in _mentions(
        read.items(running.declaration),
        [original.slug],
        root,
        f'which {running.transition.name} renamed to "{renaming.slug}"',
    ):
        running.say(said)


def _anchor(declaration: Declaration, state: State, handle: str) -> str:
    """The slug an `--above`/`--below` handle names, in `state`.

    Tree-wide, like every other handle, so one naming an item somewhere else
    says where it actually is.
    """
    one = read.resolve(declaration, handle)
    if one.state.name != state.name:
        raise Refusal(
            f"{named(one.path, declaration.root)} is in {one.state.name}, and a "
            "place beside it would "
            f"be a place in {state.name}"
        )
    return one.slug


@dataclass(frozen=True)
class _Claiming:
    """What a transition does to a claim. At most one of `take`/`free`.

    Decided before anything is written and applied after the item lands.
    `path` is `None` when neither state claims anything.
    """

    path: Path | None = None
    #: The record to write, when the item is entering a claimed state unheld.
    take: Mapping[str, Any] | None = None
    #: Whether to drop the record, when the item is leaving one.
    free: bool = False


def _claiming(running: _Running, *, slug: str) -> _Claiming:
    """What this transition does to `slug`'s claim, or refuse. No writes.

    Six rules: a record another session holds refuses, on the way out as much
    as on the way in; a missing record means unclaimed; entering a claimed
    state with no pid available refuses by name; a claim this session already
    holds is kept rather than re-stamped; only a transition that declares
    `claims` takes one; and taking one while this session holds a claim on
    another item refuses, unless the run was asked to keep them.
    See docs/method.md#the-claimed-state
    """
    source = running.declaration.states[running.transition.source] if running.transition.source else None
    destination = running.declaration.states[running.transition.to] if running.transition.to else None
    # A verb that dissolves enters nothing, so it can only free a claim.
    entering = destination is not None and destination.has(claim.NAME)
    leaving = source is not None and source.has(claim.NAME)
    if not entering and not leaving:
        return _Claiming()

    path = claim.path(running.declaration.root, slug)
    held = claim.read(path, running.declaration.root) if path.exists() else None
    who = claim.identity(running.declaration)

    if held is not None:
        _foreign(running, slug, held)

    if not entering:
        return _Claiming(path=path, free=held is not None)
    if held is not None:
        # Mine already: kept rather than re-stamped.
        return _Claiming()
    if not running.transition.claims:
        # Arriving in a claimed state is not picking work up.
        # See docs/method.md#the-claimed-state
        return _Claiming()
    if who.pid is None:
        # `pid_names` is never empty here: the empty case refuses in plan.toml.
        raise Refusal(
            f"{running.transition.name} claims {slug} for this session, and no "
            "session pid is set — a claim that cannot name the session "
            "holding it is not a claim. Export one of: "
            f"{', '.join(running.declaration.pid_names)}"
        )
    if not running.asked.get(_KEEP_CLAIMS) and (others := _held(running, who, slug)):
        raise Refusal(
            f"{running.transition.name} would claim {slug}, and this session "
            f"already holds a claim on {' and '.join(others)}. A pid is one agent "
            "process, and one process runs many conversations, so a claim taken "
            "before a conversation ended is still held after it. Free "
            + ", and ".join(f"{one} with `fileplan release {one}`" for one in others)
            + ", or pass --keep-claims to hold them all on purpose"
        )
    return _Claiming(path=path, take=claim.record(who, taken=_now()))


def _foreign(running: _Running, slug: str, held: Mapping[str, Any]) -> None:
    """Refuse when `held`, the claim record on `slug`, is another session's."""
    who = claim.identity(running.declaration)
    if not claim.owns(held, who):
        raise Refusal(
            f"{slug} is claimed by {claim.describe(held, claim.alive(held, who))}, "
            f"and {running.transition.name} is that session's to run. If it is gone, "
            f"free the claim with `fileplan release {slug}`"
        )


def _held(running: _Running, who: claim.Identity, slug: str) -> list[str]:
    """The items other than `slug` that `who` holds a claim on.

    A record is counted only while its item sits in a claimed state. Any other
    record is stranded, which the listing already names with its own fix.
    Checked by path rather than by reading the tree, so an unrelated malformed
    item cannot refuse a claim. See docs/method.md#the-listing
    """
    root = running.declaration.root
    claimed = [
        state for state in running.declaration.states.values() if state.has(claim.NAME)
    ]
    return [
        one
        for one in claim.mine(running.declaration, who)
        if one != slug
        and any((root / state.path / f"{one}{item.SUFFIX}").exists() for state in claimed)
    ]


def _apply(claiming: _Claiming, root: Path) -> None:
    """The claim's half of the effect, after the item has landed.

    The item file is written first and the record second: a crash between them
    leaves an item in a claimed state with no record, which reads as unclaimed.
    """
    if claiming.path is None:
        return
    if claiming.take is not None:
        claim.write(claiming.path, claiming.take)
    elif claiming.free:
        claim.remove(claiming.path, root)


def _now() -> dt.datetime:
    """When a claim was taken. Aware, because this tree is shared."""
    return dt.datetime.now(dt.timezone.utc)


# --------------------------------------------------------------------------
# Releasing: the other mutation under the lock
# --------------------------------------------------------------------------


def release(declaration: Declaration, handle: str) -> tuple[str, dict[str, Any]]:
    """Free `handle`'s claim, returning its slug and the record that was on it.

    Here rather than in `fileplan.claim` because it takes the run lock. Four
    outcomes: your own claim is freed, a dead session's on this host is freed,
    a live session's refuses, and one from another host refuses.
    See docs/method.md#release
    """
    with run_lock(declaration.root):
        one = read.resolve(declaration, handle)
        path = claim.path(declaration.root, one.slug)
        if not path.exists():
            raise Refusal(
                f"{one.slug} holds no claim, so there is nothing to free"
            )

        held = claim.read(path, declaration.root)
        who = claim.identity(declaration)
        status = claim.alive(held, who)
        if not claim.owns(held, who) and status != claim.DEAD:
            raise Refusal(_unfreeable(one.slug, held, status, path))

        claim.remove(path, declaration.root)
        return one.slug, held


def _unfreeable(
    slug: str, held: Mapping[str, Any], status: str, path: Path
) -> str:
    described = claim.describe(held, status)
    if status == claim.ELSEWHERE:
        return (
            f"{slug} is claimed by {described}. Nothing here can ask that "
            f"machine whether the session is still running, so freeing it is "
            f"a person's call there — or `rm {path}`"
        )
    return (
        f"{slug} is claimed by {described}, and that session is still "
        "working. A claim is freed when its holder is gone, not to take an "
        "item off somebody"
    )


def _place(
    running: _Running,
    path: Path,
    head: Mapping[str, Any],
    body: str,
    *,
    state: State | None = None,
) -> None:
    """Grade the head the executor is about to write, then write it atomically.

    `running.check` returns after the grading and before the write, so the
    seam is the write rather than the call. `state` defaults to the
    transition's `to`; a verb that `files` passes the state of its own naming.
    """
    state = state or running.declaration.states[running.transition.to]
    errors = item.head_errors(head, running.declaration, state)
    if errors:
        raise Refusal([f"{named(path, running.declaration.root)} cannot be written", *errors])
    if running.check:
        return
    item.write(item.Item(path=path, state=state, head=head, body=body))


def _directory(running: _Running, *, state: State | None = None, make: bool = True) -> Path:
    """The destination state's directory, made if it is not there.

    `make` is what a check turns off: creating the directory is itself a
    write. `state` defaults to the transition's `to`, as in `_place`.
    """
    directory = running.declaration.root / (state or running.declaration.states[running.transition.to]).path
    if make:
        directory.mkdir(parents=True, exist_ok=True)
    return directory


def _held_by(declaration: Declaration, stem: str) -> Path | None:
    """The file already holding `stem`, anywhere in the tree, or `None`.

    A slug is unique across every declared state, not per directory.
    """
    for state in declaration.states.values():
        candidate = declaration.root / state.path / f"{stem}{item.SUFFIX}"
        if candidate.exists():
            return candidate
    return None


def _taken(stem: str, held: Path, root: Path) -> str:
    return (
        f'the slug "{stem}" is already held by {named(held, root)}. A slug is '
        "unique across every state, because it is the one handle an item "
        "answers to"
    )


def _bodiless(transition: Transition) -> str:
    """Why a verb that writes an item's prose refuses without any.

    One sentence with two callers: a verb that creates an item, and one that
    files one.
    """
    return (
        f"{transition.name} needs a body. An item is a title and a "
        "description; one with no prose is intent that somebody pays to "
        "re-derive later. Pass --body TEXT, or --body - to read stdin"
    )


def _prose(body: str) -> str:
    """A body as an item file carries it: a blank line after the head, then prose."""
    return "\n" + body.strip("\n") + "\n"
