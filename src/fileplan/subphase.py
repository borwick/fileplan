"""Sub-phases: counting the named bullets a section's body carries.

A section's sub-phases stay bullets in the section's own body, with no key
beside them. Every answer here is counted off the body rather than read off a
stored value.

A state declares which heading to count under, and what the bullets are
called. The tool supplies the arithmetic.

Everything is pure: a string in, a value out, and no filesystem. Nothing here
raises `Refusal`. A defect comes back as a list of complaints. The executor is
what refuses with the list.

See docs/method.md#sub-phases for the counting, and docs/method.md#bulleted
for the writing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

# The import runs one way: `fileplan.declaration` imports this module, so
# this module imports nothing from the package and raises no `Refusal`.

#: The state field that opts in, and the field a row carries. A state that
#: declares none counts nothing: there is no default heading.
NAME = "sub-phases"

#: A line trying to be a bullet: a marker followed by whitespace. The space is
#: what separates a bullet from italic prose opening with `*`.
BULLET = re.compile(r"^(?P<marker>[-*+]|\d+[.)])\s")

#: The one marker that counts. Every other bullet-shaped line refuses.
COUNTED = "-"

#: The strict named form: a counted bullet whose very first thing is a bold run.
NAMED = re.compile(r"^-\s+\*\*(?P<bold>[^*]+?)\*\*")

#: What ends a name inside that bold run. A bare hyphen is deliberately not
#: one, so `4-1` survives whole and a name is always one token.
NAME_END = re.compile(r"[\s\u2014\u2013]")

#: The strict marked form: a named bullet whose bold run is followed by a
#: second one, holding the disposition. See docs/method.md#marking
MARKED = re.compile(r"^-\s+\*\*[^*]+?\*\*\s+\*\*(?P<mark>[^*]+?)\*\*")

#: The two state fields naming which declared keys hold the cursor and the
#: status riding with it. See docs/method.md#the-cursor
CURSOR, STATUS = "sub-phase-cursor", "sub-phase-status"

#: The row field saying which sub-phase to pick up next. In the default record
#: rather than behind a flag: a cursor left on a finished sub-phase is the
#: defect that hides otherwise.
NEXT = "next-sub-phase"

#: The row field counting the named bullets that carry no mark, so a forgotten
#: sub-phase is a number that will not go down. `fileplan.transition` refuses
#: with the same `unmarked`. See docs/method.md#the-listing
LEFT = "sub-phases-left"

#: The three fields a row carries off the item's own body, in the order a row
#: spells them. A declared key of any of these names refuses in
#: `fileplan.declaration`.
DERIVED = (NAME, LEFT, NEXT)

#: The state field holding the bullet an unfinished decomposition leaves
#: behind: the content after `- `, so the tool supplies only the marker.
PENDING = "sub-phase-pending"

#: The state field holding the whole ident form a state's bullets are named
#: by, separator included, with the ordinal's place marked. It is what lets a
#: state with no register carry bullets at all. See docs/method.md#bulleted
FORM = "sub-phase-name"

#: The one field of a `FORM` the tool supplies; every other names a value the
#: item carries. Spelled `SLOT` because `ORDINAL` is the reader.
SLOT = "ordinal"

#: A field inside a form: a brace-delimited name, non-greedy and brace-free
#: inside, so an unbalanced brace is left over rather than swallowed.
FIELD = re.compile(r"\{(?P<field>[^{}]*)\}")

#: Any ATX heading, at any depth. A span ends at the next one of any level, so
#: a deeper heading inside the sub-phases closes it rather than nesting.
HEADING = re.compile(r"^(?P<depth>#+)\s+(?P<text>.*?)\s*$")

#: A fenced code block's delimiter, either marker, indentation allowed. A
#: fenced line is not a line here at all — not a bullet, not a heading, not the
#: pending marker. Public and this module's because
#: `fileplan.declaration.heading_slugs` reads it too: one fence parser, never
#: two. A toggle rather than CommonMark's matched delimiters, and an unclosed
#: fence refuses in `errors`.
FENCE = re.compile(r"^\s*(?:```|~~~)")

#: The depth the writer opens a heading at, and only where the body has none:
#: `_headings` matches a heading's text at any depth, so a consumer writing
#: `## Steps` is never forced into this repo's nesting.
DEPTH = "###"

#: What separates a minted bullet's name from its title, and one of
#: `NAME_END`'s three, so what is written stops where the reader says it does.
DASH = "—"

#: The ordinal a body with no bullets under the heading mints first.
FIRST = 1

#: The leading integer of what is left once the prefix is stripped off a name.
#: `4-5a` leaves `5a` and contributes 5.
ORDINAL = re.compile(r"^(?P<ordinal>\d+)")


@dataclass(frozen=True)
class Bullet:
    """One named bullet: what it is called, what it says, and its mark.

    `mark` is `None` where the bullet carries none, which is what an offer
    narrows on. An unnamed bullet is not one of these: it counts like any
    other, and nothing can point at it. See docs/method.md#marking
    """

    name: str
    #: What the bullet says after its name: the rest of the bold run, with the
    #: dash between them taken off. `None` where the name is the whole of it.
    title: str | None
    mark: str | None
    #: The rest of the line after the **name's** bold run, mark included, or
    #: `None` for nothing. Beside `mark` because the two answer different
    #: questions: `mark` is the second run parsed, and this is the raw
    #: remainder that decides whether a *new* mark could be read at all. A
    #: fact about the bullet rather than a row field — nothing renders it.
    rest: str | None

    @property
    def unmarkable(self) -> bool:
        """Whether a mark written on this bullet could not be read back.

        Unmarked, and carrying something after its name's bold run: a mark is
        read immediately after that run, so a word written past the prose
        would land where nothing finds it. The one home of the question, read
        by the refusal that stops the run, by the offer that passes the bullet
        over, and by the listing's report. See docs/method.md#marking
        """
        return self.mark is None and self.rest is not None


def count(body: str, heading: str) -> int:
    """How many sub-phases `body` carries under `heading`.

    Total over any string, and unnamed bullets count like any other. `errors`
    says what is malformed, and the listing calls it beside this. Zero is a
    real answer: a row carrying `None` has a state that declares no heading,
    where `0` is a section nobody has decomposed yet.
    """
    return len(_counted(body, heading))


def names(body: str, heading: str) -> list[str]:
    """The named sub-phases under `heading`, in document order.

    Order is documentary rather than meaningful: nothing indexes this list,
    because indexing it would be the ordinal reference by another spelling.
    Shorter than `count` wherever a bullet carries no bold run.
    """
    return [name for _, _, name in _counted(body, heading) if name]


def bullets(body: str, heading: str, *, pending: str | None) -> list[Bullet]:
    """The named bullets under `heading`, in document order. Pure.

    `names` with what each name is attached to, off the same walk, so a
    finding an offer lists and a finding a verb marks come from one reader.
    Two bullets are absent: an unnamed one, which `count` still counts, and
    the state's pending bullet, which marks a decomposition as unfinished
    rather than being work. `pending` is `None` for a state that declares none.
    """
    marker = _pending_name(pending)
    return [
        Bullet(name=name, title=_title(line), mark=_mark(line), rest=_rest(line))
        for _, line, name in _counted(body, heading)
        if name is not None and name != marker
    ]


def text(body: str, heading: str, *, name: str) -> str | None:
    """The lines the bullet called `name` owns, verbatim, or `None`. Pure.

    Its own line plus its continuation: the walk runs forward from where
    `_counted` found it and stops at the first line that is unfenced, non-blank
    and at column zero. Trailing blank lines are trimmed and inner ones kept.
    A column-zero bullet or heading inside a fence neither ends nor truncates
    the continuation, so a quoted transcript comes back whole.

    The first matching bullet only, and total: it reads `_counted` rather than
    `bullets`, so an unnamed bullet or the pending marker comes back if asked
    for by name. The gate is the caller's, and it is the one a disposition
    already uses.
    """
    at = [number for number, _, found in _counted(body, heading) if found == name]
    if not at:
        return None

    lines = body.splitlines()
    start = at[0] - 1
    return "\n".join(lines[start : _owned(lines, _unfenced(lines), start)])


def unmarked(body: str, heading: str) -> list[str]:
    """The names of the bullets under `heading` carrying no mark. Pure.

    The one home of which sub-phases are still open, asked by four callers
    that would each otherwise walk the body themselves: `LEFT`, `upcoming`,
    `fileplan.transition.unmarked_errors` and `cursor_errors`. The last two
    are why one reader matters rather than two spellings: a cursor may be
    written onto a marked bullet exactly when the section could close, so the
    two cannot drift into disagreeing. `pending=None` is here rather than in
    each of them, so the state's marker is in this list whenever the body
    carries one at all.
    """
    return [
        one.name for one in bullets(body, heading, pending=None) if one.mark is None
    ]


def upcoming(body: str, heading: str, *, cursor: str | None) -> str | None:
    """Which sub-phase under `heading` comes next, or `None` for none.

    Two arms over `unmarked`: a cursor naming a bullet that carries no mark is
    itself what comes next, and otherwise it is the first unmarked bullet. So
    a body marked out of order answers with the open one in between. See
    docs/method.md#the-cursor

    `None` means no next sub-phase and never "this state counts none", which
    is `count` returning `None` beside it in the row. A cursor the body does
    not carry falls through to the first unmarked bullet: `cursor_errors`
    refuses one when it is written.
    """
    found = unmarked(body, heading)
    if cursor is not None and cursor in found:
        return cursor
    return found[0] if found else None


def errors(body: str, heading: str) -> list[str]:
    """Every line under `heading` that is trying to be a bullet and is not.

    One complaint per line, so three malformed bullets say so three times.
    The heading appearing twice refuses on its own, and so do two bullets
    sharing one name: each is two answers to a question that has one.

    Line numbers are body-relative and say so, because this is pure over a
    string and has no head to offset by.
    """
    found = _headings(body, heading)
    if len(found) > 1:
        return [
            f'the body carries {len(found)} "{heading}" headings '
            f"({_lines(found, offset=1)}), so which "
            "one holds the sub-phases has no answer"
        ]

    lines = body.splitlines()
    bounds = _bounds(lines, heading)
    complaints: list[str] = []
    if bounds is not None and (opened := _unclosed(lines, *bounds)) is not None:
        complaints.append(
            f"body line {opened + 1}: a fenced block opens here and never "
            "closes, so every line after it reads as quoted and the "
            "sub-phases under it would not be counted"
        )

    complaints += [
        f"body line {number}: sub-phases are counted as "
        f'"{COUNTED} ", and this line begins "{match["marker"]}" — {line.strip()!r}'
        for number, line in _numbered_span(body, heading)
        if (match := BULLET.match(line)) and match["marker"] != COUNTED
    ]

    where: dict[str, list[int]] = {}
    for number, _, name in _counted(body, heading):
        if name:
            where.setdefault(name, []).append(number)
    complaints += [
        f'the body carries {len(at)} sub-phases named "{name}" '
        f"({_lines(at)}), so which one that name points at has no answer"
        for name, at in where.items()
        if len(at) > 1
    ]
    return complaints


def cursor_errors(
    head: Mapping[str, Any], body: str, *, key: str, heading: str, written: bool
) -> list[str]:
    """Every way `head`'s cursor fails the sub-phases `body` carries.

    A cursor holds a name, so the first question is membership rather than
    arithmetic, and the refusal names both the value and the names available.
    The second question — whether the bullet is already marked — is asked only
    where the run writes the cursor, and only while something is still open: a
    cursor resting on a marked bullet is the ordinary state right after the
    mark went on, and where every bullet is marked there is no open one left
    for a cursor to point at.

    That second condition asks `unmarked`, which is what the close check
    refuses on, so a cursor may be written exactly when the section could
    close. A head that carries no cursor is not graded. Pure, so every refusal
    happens before the executor writes anything.
    """
    if key not in head:
        return []

    cursor = head[key]
    counted = _counted(body, heading)
    if not counted:
        return [
            f'{key} names sub-phase "{cursor}", and the body carries none at '
            f'all under "{heading}" — there is nothing yet for a cursor to '
            "point at"
        ]

    named = [name for _, _, name in counted if name]
    if cursor in named:
        if not written:
            return []
        if not unmarked(body, heading):
            return []
        line = next(line for _, line, name in counted if name == cursor)
        if (mark := _mark(line)) is None:
            return []
        return [
            f'{key} names sub-phase "{cursor}", and that bullet already '
            f"carries the mark **{mark}** — a cursor may only point at a "
            "sub-phase that is still open"
        ]

    said = (
        f"the names this body carries are {', '.join(dict.fromkeys(named))}"
        if named
        else f'the body carries no named sub-phase at all under "{heading}"'
    )
    unnamed = [number for number, _, name in counted if not name]
    if unnamed:
        # Named rather than counted from: falling back to "the 3rd bullet" is
        # the silent re-pointing this reference exists to remove.
        said += (
            f" — a bullet with no name cannot be pointed at ({_lines(unnamed)}), "
            f'and a sub-phase is named by the bold it opens with: "{COUNTED} '
            '**<name> — …**"'
        )
    return [f'{key} names sub-phase "{cursor}", and {said}']


def unknown(where: str, wanted: str, carried: Sequence[Bullet], heading: str) -> str:
    """The refusal for a bullet `where`'s body has not got, spelled once.

    `cursor_errors`' message shape, and one home because two callers need it
    byte for byte: a disposition resolving the bullet it acts on, and
    `show ITEM NAME` resolving the bullet it reads. Both gate on `bullets`, so
    an unnamed bullet and the pending marker refuse through here as "no such
    name". See docs/method.md#marking

    `carried` is what `bullets` returned, empty or not, and an empty list is
    said differently. Pure: the caller is what raises.
    """
    said = (
        f"the names it carries are {', '.join(one.name for one in carried)}"
        if carried
        else f'it carries no named bullet at all under "{heading}"'
    )
    return f'{where} carries no "{wanted}", and {said}'


# --------------------------------------------------------------------------
# Writing the strict form: the `bulleted` capability's arithmetic
# --------------------------------------------------------------------------


def fields(form: str) -> list[str]:
    """The brace-delimited names `form` carries, in the order it writes them.

    Pure, and the one parse of a form: `form_errors` grades against this and
    `fileplan.declaration` grades the names against the keys a state's items
    can carry. Says nothing about whether the form is usable.
    """
    return [found["field"] for found in FIELD.finditer(form)]


def form_errors(form: str, where: str) -> list[str]:
    """Every way `form` is not an ident form, naming `where`. Pure.

    Graded at load, by the code that will have to read it. Five refusals, each
    by name: an empty form, one carrying no `SLOT`, a `SLOT` that is not last,
    a repeated `SLOT`, and an unbalanced brace. One complaint per defect.
    """
    if not form:
        return [
            f"{where} is empty, so every bullet here would be named nothing at "
            f'all. A form is the ident a bullet carries, with "{{{SLOT}}}" '
            "where the tool supplies the number"
        ]
    literal = FIELD.sub("", form)
    if "{" in literal or "}" in literal:
        return [
            f'{where} is "{form}", which leaves a brace unclosed. A field is '
            f'written "{{name}}", and anything else is spelled literally into '
            "every bullet"
        ]

    named = fields(form)
    if SLOT not in named:
        return [
            f'{where} is "{form}", which carries no "{{{SLOT}}}". Without it '
            "every bullet here would be named the same thing, and a name that "
            "answers to two bullets points at neither"
        ]
    if named.count(SLOT) > 1:
        return [
            f'{where} is "{form}", which carries "{{{SLOT}}}" '
            f"{named.count(SLOT)} times. Which part of the name the ordinal is "
            "would have two answers"
        ]
    if not form.endswith(f"{{{SLOT}}}"):
        return [
            f'{where} is "{form}", and "{{{SLOT}}}" is not the end of it. The '
            "prefix is what comes before the ordinal and the ordinal is read "
            "off what is left, so a form with a suffix has nothing to strip "
            "the suffix with"
        ]
    return []


def prefix(form: str, head: Mapping[str, Any]) -> str:
    """What every bullet named by `form` opens with, for an item like `head`.

    The form with its ordinal taken off and every other field filled in from
    the item's values, so `"{number}-{ordinal}"` over number 7 is `"7-"`. That
    string is what `mint` writes and `next_ordinal` strips back off.

    Assumes `form` graded by `form_errors` and every other field present in
    `head`, both of which the caller checks before anything is written.
    """
    before = form[: -len(f"{{{SLOT}}}")]
    return FIELD.sub(lambda found: str(head[found["field"]]), before)


def next_ordinal(names: Iterable[str], prefix: str) -> int:
    """The next free ordinal among `names`, under `prefix`. Pure.

    Strip the prefix, read the leading integer of what is left, take the
    maximum and add one. So `4-5a` contributes 5 and a name that is not an
    ordinal contributes nothing. Not the count: a decomposition that mints
    three, splits one and mints again would hand out a name the body has.
    """
    ordinals = [
        int(found["ordinal"])
        for name in names
        if name.startswith(prefix)
        and (found := ORDINAL.match(name[len(prefix) :]))
    ]
    return max(ordinals, default=FIRST - 1) + 1


def mint(
    body: str,
    *,
    heading: str,
    prefix: str,
    pending: str,
    title: str | None = None,
    last: bool = False,
) -> str:
    """`body` with the next sub-phase written in, and the pending bullet set.

    Three steps in this order: drop the pending bullet if the body carries it;
    append a new sub-phase named `<prefix><ordinal>` if `title` was given;
    append the pending bullet unless `last` was given. Nothing asks whether
    the decomposition was already finished, so minting into a finished section
    re-opens it, which is correct.

    Assumes `title` graded by `title_errors` and `pending` by `pending_errors`.
    The heading is created only where the body has none, at `DEPTH`. Total
    over any string, and it writes nothing elsewhere in the body.
    """
    lines = body.splitlines()
    bounds = _bounds(lines, heading)
    if bounds is None:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(f"{DEPTH} {heading}")
        start, end = len(lines) - 1, len(lines)
    else:
        start, end = bounds

    # The fence flag travels with the line rather than being re-derived:
    # dropping the pending bullet offsets the span's indices from the body's,
    # and keeping the two index spaces apart is what puts a transcript back
    # byte for byte.
    marker = _pending_name(pending)
    ok = _unfenced(lines)
    paired = [
        (line, ok[number])
        for number, line in enumerate(lines[start + 1 : end], start=start + 1)
        if not _is_pending(line, ok[number], marker)
    ]
    span = [line for line, _ in paired]

    # A new bullet joins the list rather than the end of the span: directly
    # after the last sub-phase already there and every line `text` says it
    # owns, or — where the span carries none — after the last thing written,
    # ahead of the blank lines that close the span, since a bullet past them
    # would read as a paragraph.
    bullets = [
        number for number, (line, live) in enumerate(paired) if live and _counts(line)
    ]
    if bullets:
        cut = _owned(span, [live for _, live in paired], bullets[-1])
    else:
        written = [number for number, line in enumerate(span) if line.strip()]
        cut = written[-1] + 1 if written else 0

    added: list[str] = []
    if title is not None:
        ordinal = next_ordinal(
            [
                name
                for line, live in paired
                if live and _counts(line) and (name := _name(line))
            ],
            prefix,
        )
        added.append(f"{COUNTED} **{prefix}{ordinal} {DASH} {title}**")
    if not last:
        added.append(_pending_line(pending))

    written = lines[: start + 1] + span[:cut] + added + span[cut:] + lines[end:]
    return "\n".join(written) + "\n" if written else ""


def mark(
    body: str, *, heading: str, name: str, word: str, note: str | None = None
) -> str:
    """`body` with one bullet's mark written, and every other byte identical.

    The mark is a second bold run, appended at the end of the line. `MARKED`
    is anchored, so it reads that run only where the line ends at the name's
    bold run — the caller gates on `Bullet.rest`, and this stays total and
    raises nothing, like everything else here. Nothing else moves: not the
    heading, not the bullets either side, not the prose around the span. The
    first matching bullet only.

    Assumes `name` is one `bullets` handed back and `word` graded by
    `mark_errors`. A name the body does not carry writes nothing at all.

    A `note` rides outside the closing `**`, which is why it changes nothing
    derived. It is graded by `note_errors` at the run, and by the caller.
    """
    lines = body.splitlines()
    bounds = _bounds(lines, heading)
    if bounds is None:
        return body
    start, end = bounds
    ok = _unfenced(lines)
    for number in range(start + 1, end):
        line = lines[number]
        if ok[number] and _counts(line) and _name(line) == name:
            written = f"{line.rstrip()} **{word}**"
            lines[number] = f"{written} {note}" if note else written
            break
    return "\n".join(lines) + "\n" if lines else ""


def opens(body: str, *, heading: str, pending: str) -> bool:
    """Whether a mint into `body` would re-open a finished decomposition.

    Asked so the executor can say so, and a question about the body rather
    than a fourth step in `mint`, because the answer is wanted whether or not
    the mint goes on to write anything.
    """
    lines = body.splitlines()
    bounds = _bounds(lines, heading)
    if bounds is None:
        return True
    marker = _pending_name(pending)
    ok = _unfenced(lines)
    start, end = bounds
    return not any(
        _is_pending(lines[number], ok[number], marker)
        for number in range(start + 1, end)
    )


def title_errors(title: str) -> list[str]:
    """Every way `title` cannot go into the strict form. Pure.

    Narrow on purpose: empty, a newline, or a `**` that would close the bold
    run its name is read from. Each is a bullet the reader beside this could
    not count or name, so it refuses before anything is written.
    """
    return _one_line_errors(
        title,
        "a sub-phase needs a title. Its bullet is what a later session "
        "reads to know what the work is, and a name with nothing beside "
        "it is intent somebody pays to re-derive",
        "a sub-phase title carries a newline, and a sub-phase is one "
        "line: a second line would be continuation rather than part of "
        "the bullet",
        'a sub-phase title carries "**", which would close the bold run '
        "its name is read from — the bullet would count and could not be "
        "pointed at",
    )


def note_errors(note: str) -> list[str]:
    """Every way `note` cannot ride beside a mark. Pure.

    `title_errors`' three cases and graded where a title is, at the run: a
    note is the operator's text, so the caller supplies the prefix, where
    `mark_errors` takes a `where` because the word is the declaration's.

    The three are not one rule stated three times. Empty says a finding was
    disposed of and does not say why. A newline is a measured corruption: a
    second line opening with `- ` is a counted, named bullet nobody wrote, and
    the next ordinal jumps past it. And `**` breaks nothing today — it refuses
    on the ownership rule, since the tool owns every character of this
    bullet's punctuation.
    """
    return _one_line_errors(
        note,
        "a note with nothing in it says a finding was disposed of for a "
        "reason and does not give the reason — the mark beside it is "
        "already the whole of what a bare disposition says",
        "a note carries a newline, and a bullet is one line: a second "
        'line opening with "- " is a counted, named bullet nobody wrote, '
        "and the register the names are minted from cannot get that back",
        'a note carries "**". Nothing breaks today — the mark is read out '
        "of the second bold run and stops there — so this refuses on the "
        "ownership rule instead: the tool owns every character of this "
        "bullet's punctuation, and emphasis typed into it is a second "
        "author of the form",
    )


def mark_errors(word: str, where: str) -> list[str]:
    """Every way `word` cannot be a mark, naming `where`. Pure.

    `title_errors`' three cases over the bold run a mark is written in.
    Graded at load, unlike a title, because the word is the declaration's: a
    mark a verb could never write is a defect in plan.toml.
    """
    return _one_line_errors(
        word,
        f"{where} is empty, and a mark is what a reader sees on the "
        "bullet — a run with nothing in it says a finding was disposed of "
        "and not how",
        f"{where} carries a newline, and a mark goes at the end of the "
        "bullet's one line — the second would be continuation rather than "
        "part of it",
        f'{where} carries "**", which would close the bold run it is '
        "written in — the mark would end early and the rest would read as "
        "prose",
    )


def pending_errors(pending: str, where: str) -> list[str]:
    """Every way the declared pending bullet is not one, naming `where`.

    What is declared is the bullet's content after `- `, and what it has to be
    is a strict named bullet, so this asks `_pending_name` rather than
    standing a second parser beside it — the thing graded is the thing
    written. The name it carries is what a cursor points at when a session
    reaches an unfinished decomposition.
    """
    if "\n" in pending:
        return [
            f"{where} carries a newline, and a sub-phase is one line — the "
            "second would be continuation rather than part of the bullet"
        ]
    if _pending_name(pending) is None:
        return [
            f'{where} is "{pending}", which is not a named sub-phase. It is '
            f'the bullet\'s content after "{COUNTED} ", and it is found again '
            f'by the name it opens with, so it is written "**<name> {DASH} '
            '…**"'
        ]
    return []


# --------------------------------------------------------------------------


def _headings(body: str, heading: str) -> list[int]:
    """Every line index whose ATX heading text is `heading`, at any depth."""
    return _found(body.splitlines(), heading)


def _found(lines: list[str], heading: str) -> list[int]:
    """`_headings` over lines already split, for the writer.

    A heading inside a fence is not a heading, the rule
    `fileplan.declaration.heading_slugs` already keeps.
    """
    ok = _unfenced(lines)
    return [
        number
        for number, line in enumerate(lines)
        if ok[number] and (found := HEADING.match(line)) and found["text"] == heading
    ]


def _bounds(lines: list[str], heading: str) -> tuple[int, int] | None:
    """`(heading line, one past the span)`, or `None` for no such heading.

    The reader's span rule over indices, because the writer has to put
    something back where it came from. A body with the heading twice is
    refused by `errors` before anything reaches here.
    """
    found = _found(lines, heading)
    if not found:
        return None
    ok = _unfenced(lines)
    start = found[0]
    for number in range(start + 1, len(lines)):
        if ok[number] and HEADING.match(lines[number]):
            return start, number
    return start, len(lines)


def _numbered_span(body: str, heading: str) -> list[tuple[int, str]]:
    """The column-zero lines under `heading`, as (1-based line number, line).

    Indented lines are dropped here rather than in each caller, and fenced
    lines with them — the mask walked from line zero, since a fence opening
    above the heading takes the heading with it.
    """
    found = _headings(body, heading)
    if not found:
        return []

    lines = body.splitlines()
    ok = _unfenced(lines)
    span: list[tuple[int, str]] = []
    for number in range(found[0] + 1, len(lines)):
        line = lines[number]
        if not ok[number]:
            continue
        if HEADING.match(line):
            break
        if line and not line[0].isspace():
            span.append((number + 1, line))
    return span


def _span(body: str, heading: str) -> list[str]:
    return [line for _, line in _numbered_span(body, heading)]


def _counted(body: str, heading: str) -> list[tuple[int, str, str | None]]:
    """Every sub-phase under `heading`, as (body line number, line, name).

    The one place a sub-phase is recognised, so "how many", "which are named"
    and "is this cursor one of them" cannot drift into three rules. `name` is
    `None` where the bullet carries no bold run.
    """
    return [
        (number, line, _name(line))
        for number, line in _numbered_span(body, heading)
        if _counts(line)
    ]


def _unfenced(lines: list[str]) -> list[bool]:
    """A mask parallel to `lines`: true where the line is not fenced.

    Parallel and never a filtered list: `mint` rebuilds the body out of slices
    of the span, so a filtered list would silently delete every transcript in
    it. Readers skip on this mask, writers index it, and the delimiter lines
    themselves read as fenced. Walked from line zero, because being inside a
    fence is a running fact.
    """
    mask: list[bool] = []
    fenced = False
    for line in lines:
        opener = bool(FENCE.match(line))
        mask.append(not fenced and not opener)
        fenced = fenced != opener
    return mask


def _owned(lines: list[str], ok: list[bool], start: int) -> int:
    """One past the last line the bullet at index `start` owns.

    The one home of the continuation rule, read by `text` to return a bullet
    and by `mint` to write past one: the walk stops at the first line that is
    unfenced, non-blank and at column zero, and trailing blank lines go back
    to the gap. `ok` is `_unfenced`'s mask, parallel to `lines`.
    """
    end = len(lines)
    for number in range(start + 1, len(lines)):
        if ok[number] and lines[number] and not lines[number][0].isspace():
            end = number
            break
    while end > start + 1 and not lines[end - 1].strip():
        end -= 1
    return end


def _unclosed(lines: list[str], start: int, end: int) -> int | None:
    """The line index of a fence opened in `(start, end)` and never closed.

    `None` where every fence in the span closes. Asked so `errors` can refuse:
    an unclosed fence hides every line after it.
    """
    opened: int | None = None
    for number in range(start + 1, end):
        if FENCE.match(lines[number]):
            opened = None if opened is not None else number
    return opened


def _counts(line: str) -> bool:
    """Whether `line` is a sub-phase: the strict marker, at column zero.

    `BULLET` is anchored, so an indented line is not bullet-shaped here at
    all, which is why the writer needs no indentation arm of its own.
    """
    return bool((found := BULLET.match(line)) and found["marker"] == COUNTED)


def _name(line: str) -> str | None:
    """The name a counted bullet carries, or `None` where it carries none.

    An empty or whitespace-opening bold run reads as no name rather than as
    the name `""`: a reference nobody can type is not a reference.
    """
    bold = NAMED.match(line)
    if not bold:
        return None
    end = NAME_END.search(bold["bold"])
    return (bold["bold"][: end.start()] if end else bold["bold"]) or None


def _title(line: str) -> str | None:
    """What a counted bullet says after its name, or `None` for nothing.

    The bold run with the name and the dash taken off, read through
    `NAME_END`, so the reader that says where a name stops is the one that
    says where the title starts. A bare name has no title rather than an
    empty one.
    """
    bold = NAMED.match(line)
    if not bold:
        return None
    end = NAME_END.search(bold["bold"])
    if end is None:
        return None
    return bold["bold"][end.end() :].strip(" \u2014\u2013") or None


def _mark(line: str) -> str | None:
    """The mark a counted bullet carries, or `None` where it carries none.

    `_name`'s rule over the second bold run. `None` is the answer an offer
    narrows on: an unmarked finding is one every disposition could still take.
    """
    marked = MARKED.match(line)
    return (marked["mark"].strip() if marked else None) or None


def _rest(line: str) -> str | None:
    """What a counted bullet carries after its name's bold run, or `None`.

    Read through `NAMED`, so the reader that says where the bold run ends is
    the one the writer appends past. A mark counts as rest, and whitespace
    alone does not: a markable bullet's line ends at that closing `**`.
    """
    bold = NAMED.match(line)
    if not bold:
        return None
    return line[bold.end() :].strip() or None


def _pending_line(pending: str) -> str:
    """The line a declared pending sentence becomes, and the one home of it.

    What plan.toml declares is the content after `- ` (`PENDING`), so every
    reader and the writer have to put the marker back the same way. A second
    marker composer is the drift docs/method.md#bulleted refuses.
    """
    return f"{COUNTED} {pending}"


def _pending_name(pending: str | None) -> str | None:
    """The name the declared pending bullet carries, or `None` for none.

    `None` for a state that declares no pending bullet and for a sentence that
    carries no name. Only `pending_errors` can tell them apart, and it already
    knows `pending` is not `None`; for every other caller there is simply no
    bullet to find.
    """
    return None if pending is None else _name(_pending_line(pending))


def _is_pending(line: str, live: bool, marker: str | None) -> bool:
    """Whether `line` is the pending bullet, `live` off the fence mask.

    The three conjuncts in one place: unfenced, counted, and carrying the
    declared name. `live` is passed rather than derived because the mask is
    parallel to the body's lines while `mint` walks an offset span. A `None`
    `marker` matches nothing, so an unnamed bullet never reads as this one.
    """
    return live and marker is not None and _counts(line) and _name(line) == marker


def _one_line_errors(value: str, empty: str, newline: str, bold: str) -> list[str]:
    """The three one-line predicates in order, each with the caller's words.

    `value` has to survive going into a bullet's one line, and there are
    exactly three ways it does not: empty, a newline, or a `**`.
    `title_errors`, `note_errors` and `mark_errors` all ask those three, in
    that order, always all three.

    Only the scaffolding is shared. The three texts come from the caller
    positionally and are named for their cases, because the count and the
    order are fixed and no caller has a subset or a fourth case.
    """
    complaints: list[str] = []
    if not value.strip():
        complaints.append(empty)
    if "\n" in value:
        complaints.append(newline)
    if "**" in value:
        complaints.append(bold)
    return complaints


def _lines(numbers: list[int], *, offset: int = 0) -> str:
    """Body line numbers as a refusal says them, singular or plural."""
    return f"body line{'s' if len(numbers) > 1 else ''} " + ", ".join(
        str(one + offset) for one in numbers
    )
