"""Two renderings of one traversal: a record for a person, JSON for an agent.

Both functions are pure, and both are total over the rows `fileplan.read`
produces. A row appearing in one rendering appears in the other by
construction.

The text form is one multi-line record per item. A listing has to be easy for
a person to read, and an agent reads the JSON instead.

Absent is spelled by omission in a record and by `null` in the document. No
sentinel is written, so a consumer cannot confuse absence with a legal value.

The document is an object and never a bare array. The object carries
`version`, `kind` and the counts the text form puts on stderr. An array would
have nowhere to grow.

See docs/method.md#the-listing
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

#: The read contract's version. Bumped only for a change a consumer parsing
#: the previous shape could not survive — a field removed or retyped. Adding a
#: field is not such a change, which is why the envelope is an object.
SCHEMA_VERSION = 1

#: The two fields a record spells in its header line rather than as body
#: lines. Everything else is a field of the record, in the row's own order.
HEADING = ("slug", "state")

#: And the two a bullet record heads with. One renderer, two headings, for
#: the reason there is one renderer at all: a second row kind rendered by a
#: second function is two things that can drift, and the control comparing the
#: two renderings would have nothing to say about the new kind.
BULLET_HEADING = ("name", "item")

_INDENT = "  "
_GAP = "  "


def records(
    rows: Sequence[Mapping[str, Any]],
    *,
    heading: tuple[str, str] = HEADING,
) -> list[str]:
    """The readable form: one multi-line record per row, blank line between.

    Returns lines, not blocks, so a caller echoes them one by one and the
    control test compares against `stdout.splitlines()` directly.

    A key the row carries as `None` is dropped: omission is how a record
    spells "absent". `heading` says which two of the row's fields go on the
    header line, a parameter rather than a second function because everything
    else about a record is the same for either row kind.
    """
    if not rows:
        return []

    first, second = heading
    left_width = max(len(_spell(row.get(first))) for row in rows)
    label_width = max(
        (
            len(name)
            for row in rows
            for name, value in row.items()
            if name not in heading and value is not None
        ),
        default=0,
    )

    lines: list[str] = []
    for row in rows:
        if lines:
            lines.append("")
        head = f"{_spell(row.get(first)):<{left_width}}{_GAP}{_spell(row.get(second))}"
        lines.append(head.rstrip())
        lines += [
            f"{_INDENT}{name:<{label_width}}{_GAP}{_spell(value)}"
            for name, value in row.items()
            if name not in heading and value is not None
        ]
    return lines


def document(kind: str, rows: Sequence[Mapping[str, Any]], **meta: Any) -> str:
    """The agent's form: one object, on one line, ending in a newline.

    `kind` names which read this is, so a consumer reading a pipe can tell one
    listing from another. `meta` is whatever the text form's counts line was
    carrying, which is why that line can be suppressed rather than parsed.

    Compact separators and one line: a pipe format, not a file. `default=str`
    is for the values TOML has and JSON does not — a date goes out as its ISO
    spelling rather than refusing the whole listing over one field.
    """
    payload = {
        "version": SCHEMA_VERSION,
        "kind": kind,
        **meta,
        "rows": list(rows),
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=False, default=str) + "\n"


def _spell(value: Any) -> str:
    """One value as a record prints it. A list joins into one line."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return str(value)
