"""Item files: a `+++`-fenced TOML head over a body, in a state directory.

An item is one file. The head is a flat TOML table holding the declared keys
the item carries. The body is prose this module never interprets and never
alters. An item's state is the directory the file sits in. There is no `state`
key.

The grammar is pure over text, and only `read` and `write` touch the
filesystem.

TOML rather than YAML: an item file and plan.toml are one language. The fence
is `+++` rather than `---`, which nothing reads as a Markdown thematic break.

A comment in a head is dropped on write, because `tomllib` does not surface
one. The head is data. Commentary goes in the body, which is kept byte for
byte.

See docs/method.md#the-head
"""

from __future__ import annotations

import datetime as dt
import os
import re
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from fileplan import numbered, queued
from fileplan.declaration import (
    CAPABILITY_KEYS,
    INTRINSIC_KEYS,
    Declaration,
    Refusal,
    State,
    capability_of,
)

#: Three characters, not YAML's `---`, so nothing reads a head's opening line
#: as a Markdown thematic break.
FENCE = "+++"

#: What an item file is called: its slug, then this. Here beside `slug`,
#: because what an item file is called is one fact, read by the executor that
#: writes one and the traversal that finds one.
SUFFIX = ".md"


@dataclass(frozen=True)
class Item:
    """One item file, read: where it is, what state that puts it in, what it says."""

    path: Path
    #: Read off `path` by the declaration. Never off the head.
    state: State
    head: Mapping[str, Any]
    #: Verbatim. Every byte after the closing fence's newline.
    body: str

    @property
    def slug(self) -> str:
        """The item's one handle: its filename stem. Read off `path`."""
        return self.path.stem

    def get(self, key: str, default: Any = None) -> Any:
        """The value of a declared key, or `default`."""
        return self.head.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.head[key]

    def __contains__(self, key: str) -> bool:
        return key in self.head


# --------------------------------------------------------------------------
# The grammar: pure over text
# --------------------------------------------------------------------------


def parse(text: str) -> tuple[dict[str, Any], str]:
    """`(head, body)` from one item file's text, or raise `Refusal`.

    The fence walk and its three refusals. A file with no opening fence has no
    head at all and one whose fence never closes has a head running into the
    prose; neither may read as "no frontmatter, carry on", because an item
    without a head is invisible to every filter.

    The split is on `"\\n"` alone, never `str.splitlines`, so the body comes
    back byte for byte: a form feed, a lone `\\r`, a line separator and a
    missing final newline all survive.
    """
    parts = text.split("\n")
    if parts[0].strip() != FENCE:
        raise Refusal(
            f"there is no `{FENCE}` head on line 1. An item opens with a "
            f"`{FENCE}`-fenced TOML head over its prose, and the head is what "
            "every listing reads"
        )

    for close in range(1, len(parts)):
        if parts[close].strip() != FENCE:
            continue
        # A CRLF file leaves a `\r` on every line, and tomllib refuses one
        # not followed by `\n`. The head is re-serialized canonically anyway.
        head_text = "\n".join(part.removesuffix("\r") for part in parts[1:close])
        return flat(head_text), "\n".join(parts[close + 1 :])

    raise Refusal(
        f"the `{FENCE}` head opened on line 1 and never closed, so the whole "
        f"file reads as TOML. Close the head with a second `{FENCE}` line "
        "above the prose"
    )


def flat(text: str, *, noun: str = "head") -> dict[str, Any]:
    """`text` as a flat TOML table, or raise `Refusal`.

    Half of the head's codec, and public because a claim record wants exactly
    these rules: no nesting, one line per key. `parse` calls it on the fenced
    text; `fileplan.claim` calls it on a whole file, which is unfenced.

    `noun` is what the caller's table is called, so a hand-mangled claim
    record is not told about a head it does not have.
    """
    try:
        parsed = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise Refusal(f"the {noun} is not valid TOML: {exc}") from None

    nested = [name for name, value in parsed.items() if _is_table(value)]
    if nested:
        raise Refusal(
            [
                f'the {noun} key "{name}" is a table, and a {noun} is flat. '
                f"A {noun} holds one line per key. Move the table out of the "
                f"{noun}"
                for name in nested
            ]
        )
    return parsed


def _is_table(value: Any) -> bool:
    if isinstance(value, dict):
        return True
    return isinstance(value, list) and any(isinstance(item, dict) for item in value)


def render(head_table: str, body: str) -> str:
    """The canonical serialization: a fenced `head_table`, then `body`.

    Over the head's serialization rather than over the head, so a caller with
    a mapping calls `table` itself. Order is the mapping's own, which is the
    source file's, so a key a caller adds lands at the end and nothing already
    in the head moves. Any file is byte-stable after one write.
    """
    return f"{FENCE}\n{head_table}{FENCE}\n" + body


def table(mapping: Mapping[str, Any], *, noun: str = "head") -> str:
    """`mapping` as flat TOML lines — the head's serialization, unfenced.

    The other half of the codec `flat` reads: one line per key, every control
    character escaped, and the mapping's own order, so a second write of an
    unchanged record is byte-identical to the first.
    """
    lines = [
        f"{name} = {_literal(name, value, noun=noun)}"
        for name, value in mapping.items()
    ]
    return "".join(f"{line}\n" for line in lines)


#: How each head value type is spelled, tried in order. `bool` sits before
#: `int` because a `bool` is an `int` in Python, so the integer row reached
#: first would write `queued = True`, which `tomllib` then refuses to read.
#: Each spelling takes the value and the recursion, so the list row can spell
#: its items without a second arm outside the table.
_SPELLINGS: tuple[tuple[Any, Callable[[Any, Callable[[Any], str]], str]], ...] = (
    (bool, lambda value, spell: "true" if value else "false"),
    (str, lambda value, spell: _string(value)),
    (int, lambda value, spell: str(value)),
    (float, lambda value, spell: repr(value)),
    ((dt.datetime, dt.date, dt.time), lambda value, spell: value.isoformat()),
    (list, lambda value, spell: "[" + ", ".join(map(spell, value)) + "]"),
)


def _literal(name: str, value: Any, *, noun: str = "head") -> str:
    """One head value as TOML, spelled by the first row of `_SPELLINGS` the
    value is an instance of."""
    for types, spell in _SPELLINGS:
        if isinstance(value, types):
            return spell(value, lambda item: _literal(name, item, noun=noun))
    raise Refusal(
        f'the {noun} key "{name}" holds a {type(value).__name__}, which a '
        f"{noun} cannot spell. A {noun} holds strings, numbers, booleans, "
        "dates and lists of those"
    )


_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def _string(value: str) -> str:
    """A TOML basic string. Every control character is escaped, not passed through.

    Escaping only `\\` and `"` would let a title carrying a newline write a
    head this reader then refused. Unicode passes through raw: TOML is UTF-8.
    """
    return '"' + "".join(
        _ESCAPES[character] if character in _ESCAPES
        else f"\\u{ord(character):04x}"
        if character < " " or character == "\x7f" else character
        for character in value
    ) + '"'


#: Which module grades each capability key's value. A mapping rather than an
#: `if` per key, for `fileplan.read.head_keys`' reason.
CAPABILITY_ERRORS = {queued.KEY: queued.errors, numbered.KEY: numbered.errors}


def head_errors(
    head: Mapping[str, Any],
    declaration: Declaration,
    state: State | None,
) -> list[str]:
    """Every head key `declaration` does not declare. The typo detector.

    `sizee = "M"` is caught here rather than read as an unset `size`. A value
    outside a key's declared `values` is deliberately not checked: that is
    grading, and it belongs to a transition's `refuses` and to the reads,
    since one bad value at read time would break a whole listing.

    `INTRINSIC_KEYS` passes without a declaration, and is still listed in the
    complaint so a typo'd `titel` is told what it was reaching for. `state`
    admits the keys that state's capabilities give an item, and one carried
    anywhere else refuses by name: location is state, so a fact about being in
    a state travels with the item's location. A capability key that is present
    is also graded on its value, by the module that owns it.
    """
    given = state.capability_keys if state is not None else ()
    errors = [
        _stray(name, declaration, state)
        for name in head
        if name not in declaration.keys
        and name not in INTRINSIC_KEYS
        and name not in given
    ]
    for key in given:
        errors += CAPABILITY_ERRORS[key](head)
    return errors


def _stray(name: str, declaration: Declaration, state: State | None) -> str:
    """One head key that does not belong on this item, said as precisely as
    the tool can: a capability's key carried outside its state is a different
    mistake from a typo, and reading as "undeclared" would send someone to
    write `[keys.position]`, which refuses too, one message later."""
    if name in CAPABILITY_KEYS.values():
        capability = capability_of(name)
        where = f"{state.name} is not" if state is not None else "this one is not"
        return (
            f'"{name}" is what the {capability} capability gives an item, and '
            f"{where} a {capability} state. An item's state is the directory "
            "it sits in, and a key a state gives travels with the item. Drop "
            f'"{name}", or move the item into a {capability} state'
        )
    return (
        f'"{name}" is not a declared key '
        f'(declared: {", ".join(declaration.keys)}; '
        f'intrinsic: {", ".join(INTRINSIC_KEYS)})'
    )


def slug(title: str) -> str:
    """The filename stem `title` takes: kebab-case ASCII, no extension.

    Everything outside `a-z0-9` becomes one hyphen, runs collapse and the ends
    are trimmed, so case, punctuation and accents never reach a filename. The
    stem is the item's one handle for the rest of its life.

    Deliberately not truncated (John, 2026-09-02): the tool resolves a unique
    prefix instead, so length at the prompt is not what a slug has to solve,
    and a full slug says more in an edge and in a listing.

    A slug is unique across every state plus the archive, not just within one
    directory: a prefix that could name two items cannot resolve, and an edge
    naming two items cannot say which.
    """
    stem = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if not stem:
        raise Refusal(
            f'"{title}" carries no letters or digits, so it reduces to an '
            "empty filename. Give the item a name a filename can hold"
        )
    return stem


# --------------------------------------------------------------------------
# The filesystem: location is state
# --------------------------------------------------------------------------


def read(path: str | os.PathLike[str], declaration: Declaration) -> Item:
    """One item file, read and graded, or raise `Refusal`.

    Grades in one pass: the head's keys must be declared, and the directory
    must be a declared state. Which files are handed here is the traversal's
    question — everything reaching this is claimed to be an item, so a file
    that is not one refuses rather than being skipped.
    """
    path = Path(path)
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            text = handle.read()
    except UnicodeDecodeError:
        raise Refusal(f"{path} is not UTF-8, so it is not an item file") from None
    except OSError as exc:
        raise Refusal(f"{path} could not be read: {exc.strerror}") from None

    try:
        head, body = parse(text)
    except Refusal as refusal:
        raise Refusal([_not_usable(path), *refusal.messages]) from None

    # The state comes first, because it says which capability keys this item
    # may carry: the head is graded against where the file actually sits.
    state = declaration.state_at(path)
    errors = head_errors(head, declaration, state)
    if state is None:
        errors.append(
            f"{path.parent} is not a declared state directory "
            f"(declared: {', '.join(declaration.states)})"
        )
    if errors:
        raise Refusal([_not_usable(path), *errors])

    return Item(path=path, state=state, head=head, body=body)


def _not_usable(path: Path) -> str:
    return f"{path} is not a usable item file"


def write(item: Item) -> None:
    """Render `item` and put it in place of its file, atomically."""
    replace(item.path, render(table(item.head), item.body))


def replace(path: Path, text: str) -> None:
    """Put `text` in place of `path`, atomically.

    A temp file in the same directory, then `os.replace`: a reader sees either
    the whole old file or the whole new one. The replacement is a new inode,
    so an existing file's mode survives only by being copied across below, and
    a new file lands at the temp file's `0600`.

    Over a path and a string rather than over an `Item`, because the executor
    writes the archive this way too — one copy of the dance rather than a
    second that could learn a different answer about modes or cleanup.
    """
    handle = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    try:
        with handle:
            handle.write(text)
        try:
            os.chmod(handle.name, path.stat().st_mode & 0o777)
        except FileNotFoundError:
            pass  # No target to copy from: the temp file's 0600 stands.
        os.replace(handle.name, path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise
