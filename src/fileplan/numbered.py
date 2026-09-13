"""The `numbered` capability: the register, and the number a new item is given.

A state opts into `numbered`, and every item there carries a `number`. The
number is minted on entry. The key is not declared, and declaring it refuses.

The register is derived and never stored. Two sources make it, with two
different writers. Every item in the state carries its own `number`. The
`archive` document the state names carries one `## <n>. <title>` heading per
closed item.

A heading is a closed item's only record. A heading the parse cannot read
drops its number silently. The gapless walk bounds itself by the highest
number it found. A number lost at the top is a loss the walk cannot catch.

Everything here is pure and raises nothing but `Refusal`.

See docs/method.md#the-register
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from fileplan.declaration import Refusal

#: The capability a state opts into. The same word plan.toml spells.
NAME = "numbered"

#: The key it gives an item. Declared nowhere; a redeclaration is refused in
#: `fileplan.declaration.CAPABILITY_KEYS`.
KEY = "number"

#: The state field naming the document closed numbers are recorded in. A
#: state's, because the register needs it before any transition writes.
ARCHIVE = "archive"

#: The number a legibly empty corpus mints, and `FIRST_NUMBER`'s default, so
#: neither the mint nor the gap walk branches around a declared floor.
FIRST = 1

#: The state field declaring where this register begins: the first number it
#: may hold, inclusive. A bound on the derived register and never a third
#: source, so a source claiming a number below it refuses at the mint.
FIRST_NUMBER = "first-number"

#: An archive entry's heading: the number, a full stop, a space, the title.
#: `entry` writes what this reads, so the two cannot drift into two parsers.
HEADING = re.compile(r"^##[ \t]+(?P<number>\d+)\.[ \t]+\S")

#: Any `##` line at all: `HEADING` says whether a heading parses, this says
#: it was meant to be one. Every `##` is an entry, and there is no allowlist.
ARCHIVE_HEADING = re.compile(r"^##[ \t]")

#: The state a register belongs to, in the record the two reports carry: a
#: register is per numbered state, named by its declared name.
STATE = "state"

#: Where a lost close-out is, and what it says: the 1-based line number in
#: the archive, and the line itself.
LINE, TEXT = "line", "text"

#: The two numbers a register's own record carries: where it begins, and the
#: highest number it holds. `FLOOR` is always a number, a state declaring no
#: `FIRST_NUMBER` beginning at `FIRST`. `HIGHEST` is `None` for a register
#: holding nothing at all, which is a different fact from holding 1.
FLOOR, HIGHEST = "floor", "highest"


def missing(held: Mapping[int, Iterable[str]], *, first: int = FIRST) -> list[int]:
    """Every number the register is short of, in order. Pure.

    `first` is where this register begins (`FIRST_NUMBER`): everything below
    it is recorded in an archive this does not read, so a cutover at 192 is a
    register with no gaps rather than one with 191. One arithmetic, two
    readers — `next_number` refuses on it at the mint, the listing reports it
    on every read. The walk bounds itself by `max`, so a number lost at the
    top leaves what remains gapless. See docs/method.md#the-register
    """
    if not held:
        return []
    return sorted(set(range(first, max(held) + 1)) - set(held))


def unreadable(text: str) -> list[tuple[int, str]]:
    """Every `##` the register cannot read, as `(line number, line)`.

    The complement of `numbers`, and the assertion that walk cannot make on
    its own: a parse that silently matches nothing looks exactly like an empty
    archive. Every `##` is graded, with no allowlist. `heading_errors` refuses
    on this walk and the listing reports it.
    """
    return [
        (number, line.strip())
        for number, line in enumerate(text.splitlines(), start=1)
        if ARCHIVE_HEADING.match(line) and not HEADING.match(line)
    ]


def lost(state: str, archive: str, line: int, text: str) -> dict[str, Any]:
    """One heading the register cannot read as the record a listing carries.

    Named for the defect, the word docs/method.md#the-register already uses. A
    second record shape rather than a discriminator on the gap record.
    """
    return {STATE: state, ARCHIVE: archive, LINE: line, TEXT: text}


def taken(numbers: Mapping[str, Any]) -> dict[int, list[str]]:
    """`{number: [slug, …]}` for every source, so a number two sources claim
    can be refused naming both."""
    held: dict[int, list[str]] = {}
    for slug, value in numbers.items():
        if isinstance(value, int) and not isinstance(value, bool):
            held.setdefault(value, []).append(slug)
    return held


def next_number(
    held: Mapping[int, Iterable[str]],
    *,
    current: int | None = None,
    first: int = FIRST,
) -> int:
    """The next free number, or raise `Refusal`. Pure.

    `current` is the number the item already holds here, and `None` for one
    arriving from elsewhere: an item that is not going anywhere keeps its
    number, so an in-place verb does not re-mint. `first` is where this
    register begins, the same number `missing` walks from.

    Three refusals and one bootstrap. A number two sources claim refuses
    naming both. A number below the floor refuses naming it and its source,
    rather than being clamped into a hole the gap walk could never report. A
    gap refuses, the number above it possibly being spoken for. An empty
    register mints `first`, which `heading_errors` running on every mint is
    what makes safe: an unreadable archive has already refused.

    Only the duplicate refusal runs before `current`, the other two being
    about minting where `entry` is about filing.
    """
    for number, slugs in sorted(held.items()):
        named = sorted(slugs)
        if len(named) > 1:
            raise Refusal(
                f"{KEY} {number} is claimed by {' and '.join(named)}. A "
                "number is what an item is called in the archive after its "
                "file is gone, so two of them would leave one closed item "
                "unfindable — give one of them another number"
            )

    if current is not None:
        return current
    if not held:
        return first

    for number, slugs in sorted(held.items()):
        if number < first:
            raise Refusal(
                f"{KEY} {number} is claimed by {' and '.join(sorted(slugs))}, "
                f"and this register begins at {first}. A {FIRST_NUMBER} says "
                "every number below it is recorded somewhere this register "
                "does not read, so a source holding one contradicts the "
                f"declaration — renumber it, or lower the {FIRST_NUMBER}"
            )

    highest = max(held)
    if gaps := missing(held, first=first):
        raise Refusal(
            f"the {NAME} register runs to {highest} with "
            f"{len(gaps)} gap(s): {', '.join(str(one) for one in gaps)}. "
            "Every closed item is covered by its own heading in the archive "
            "and every open one carries its own number, so a gap is a "
            "declaration this cannot see — and the number above it may "
            "already be spoken for. Fix the register before minting on top "
            "of it"
        )
    return highest + 1


def numbers(text: str) -> list[int]:
    """Every number the archive's headings declare, in document order."""
    return [
        int(found["number"])
        for line in text.splitlines()
        if (found := HEADING.match(line))
    ]


def heading_errors(lost: list[tuple[int, str]], where: str) -> list[str]:
    """Every line `unreadable` named, worded as a refusal.

    The writer's half of `unreadable`: this refuses a mint and a filing, where
    the listing reports the same walk. The caller runs the walk, so this holds
    the wording and nothing else.
    """
    return [
        f"{where}:{number}: `{line}` is not a heading the {NAME} "
        f"register can read. An entry opens `## <number>. <title>` — the "
        "number, a full stop, a space, then the title. That heading is the "
        "**only** record of a closed item, since its file is deleted, so one "
        "this cannot parse drops the number silently and frees it to be "
        "minted again — and the gap check cannot see the loss, because it "
        "bounds itself by the highest number left"
        for number, line in lost
    ]


def errors(head: Mapping[str, Any]) -> list[str]:
    """Every way `head`'s number is not one: a quoted number refuses rather
    than being read as text that happens to look like one."""
    value = head.get(KEY)
    if value is None or (isinstance(value, int) and not isinstance(value, bool)):
        return []
    return [
        f"{KEY} holds {value!r}, which is not a whole number. A number is "
        f'arithmetic — "10" sorts ahead of "9" as text — so it is written as '
        "a bare integer"
    ]


def entry(text: str, number: int, title: str, record: str = "") -> str:
    """`text` with `## <number>. <title>` inserted at its register place.

    `record` is the prose that goes under the heading, stripped of its blank
    lines and separated by one. Empty — the default — writes the heading
    alone, which is what a verb that moves the item files; a verb that
    dissolves it hands the record in with the run (docs/method.md#dissolving).

    Inserted, never appended: before the first readable heading whose number
    is greater, and at the end when there is none, so the archive stays in
    register order however out of order the close-outs were. A duplicate
    refuses through `next_number`, called with `current` so the duplicate loop
    runs and the mint arithmetic does not.
    """
    held: dict[str, Any] = {
        f"§ {one}. in the archive": one for one in numbers(text)
    }
    held[f'"{title}"'] = number
    next_number(taken(held), current=number)

    lines = text.splitlines()
    cut = len(lines)
    for index, line in enumerate(lines):
        if (found := HEADING.match(line)) and int(found["number"]) > number:
            cut = index
            break

    # Exactly one blank line on each side of the heading. Trailing blanks
    # above the cut are dropped rather than added to, so an insertion into a
    # document ending in whitespace does not grow a second gap.
    before = list(lines[:cut])
    while before and not before[-1].strip():
        before.pop()

    written = [f"## {number}. {title}"]
    if stripped := record.strip("\n"):
        written += ["", *stripped.splitlines()]
    if before:
        written = [*before, "", *written]
    if after := lines[cut:]:
        written += ["", *after]
    return "\n".join(written) + "\n"
