"""The two renderers, pure: no filesystem, no click, no declaration.

The rows here are written by hand, not traversed: `fileplan.render` is a
total function of the row layer, and these tests show it when it stops being
one. That the *same* rows reach both renderers in a real run is graded in
``tests/test_cli.py``.
"""

from __future__ import annotations

import json

from fileplan import render

ROWS = [
    {
        "slug": "a-seedling",
        "state": "greenhouse",
        "title": "A seedling",
        "cultivar": "heirloom",
        "rootstock": None,
        "after": ["b-seedling", "c-seedling"],
        "path": "greenhouse/a-seedling.md",
    },
    {
        "slug": "b-seedling",
        "state": "cold-frame",
        "title": "B seedling",
        "cultivar": None,
        "rootstock": None,
        "after": None,
        "path": "beds/hardening-off/b-seedling.md",
    },
]


# --------------------------------------------------------------------------
# The record: what a person reads
# --------------------------------------------------------------------------


def test_a_record_heads_with_the_slug_and_the_state() -> None:
    lines = render.records(ROWS[:1])
    assert lines[0].split() == ["a-seedling", "greenhouse"]


def test_a_record_drops_an_absent_key() -> None:
    """Omission is how a record spells "absent", so there is no `-` that
    another field could legally hold."""
    text = "\n".join(render.records(ROWS[:1]))
    assert "rootstock" not in text
    assert "cultivar" in text


def test_a_record_never_spells_absence_with_a_placeholder() -> None:
    assert "-\n" not in "\n".join(render.records(ROWS)) + "\n"


def test_a_records_fields_keep_the_rows_order() -> None:
    lines = render.records(ROWS[:1])
    labels = [line.split()[0] for line in lines[1:]]
    assert labels == ["title", "cultivar", "after", "path"]


def test_a_list_value_prints_on_one_line() -> None:
    text = "\n".join(render.records(ROWS[:1]))
    assert "b-seedling, c-seedling" in text


def test_records_are_separated_by_one_blank_line() -> None:
    lines = render.records(ROWS)
    assert lines.count("") == 1
    assert lines[lines.index("") + 1].startswith("b-seedling")


def test_an_empty_result_renders_as_no_lines() -> None:
    assert render.records([]) == []


def test_no_line_carries_trailing_whitespace() -> None:
    """A record with only its header — every other field absent — must not
    leave the padding behind on the end of the line."""
    lines = render.records([{"slug": "a", "state": "greenhouse"}])
    assert lines == ["a  greenhouse"]


# --------------------------------------------------------------------------
# The columns: what `--fields` prints
# --------------------------------------------------------------------------


def test_each_column_lines_up_under_its_header() -> None:
    lines = render.columns(ROWS, ["state", "slug"])
    assert lines == [
        "state       slug",
        "greenhouse  a-seedling",
        "cold-frame  b-seedling",
    ]


def test_a_cell_spelling_empty_prints_a_dash() -> None:
    """`None`, and a list present but empty, which carries nothing."""
    rows = [{**ROWS[0], "after": []}, ROWS[1]]
    assert render.columns(rows, ["rootstock", "after", "slug"]) == [
        "rootstock  after  slug",
        "-          -      a-seedling",
        "-          -      b-seedling",
    ]


def test_a_list_cell_joins_as_the_record_joins_it() -> None:
    assert render.columns(ROWS, ["after"])[1] == "b-seedling, c-seedling"


def test_the_last_column_is_never_padded() -> None:
    lines = render.columns(ROWS, ["slug", "cultivar"])
    assert lines == ["slug        cultivar", "a-seedling  heirloom", "b-seedling  -"]
    assert all(line == line.rstrip() for line in lines)


def test_no_rows_print_no_columns() -> None:
    assert render.columns([], ["slug"]) == []


# --------------------------------------------------------------------------
# The document: what an agent reads
# --------------------------------------------------------------------------


def test_the_document_is_one_object_on_one_line_ending_in_a_newline() -> None:
    """A pipe format, not a file. A consumer that wants it readable has
    `python -m json.tool`."""
    text = render.document("items", ROWS)
    assert text.endswith("\n")
    assert len(text.splitlines()) == 1
    assert isinstance(json.loads(text), dict)


def test_the_document_keeps_the_nulls_a_record_drops() -> None:
    """`null` is a value a consumer can test. It is the same absence the
    record spells by leaving the line out."""
    payload = json.loads(render.document("items", ROWS))
    assert payload["rows"][0]["rootstock"] is None


def test_the_document_names_its_kind_and_its_version() -> None:
    payload = json.loads(render.document("items", ROWS))
    assert payload["kind"] == "items"
    assert payload["version"] == render.SCHEMA_VERSION


def test_an_empty_result_still_parses_and_still_names_its_kind() -> None:
    """An empty listing is an answer, not a failure: `--json` on a fresh tree
    has to be something a consumer can parse."""
    payload = json.loads(render.document("items", []))
    assert payload["rows"] == []
    assert payload["kind"] == "items"
    assert payload["version"] == render.SCHEMA_VERSION


def test_the_envelope_is_an_object_so_meta_has_somewhere_to_live() -> None:
    """An array has nowhere to grow, and wrapping one breaks every consumer
    at once. The counts live here because stderr is silent under `--json`."""
    payload = json.loads(render.document("items", ROWS, matched=2, read=7))
    assert payload["matched"] == 2
    assert payload["read"] == 7
    assert list(payload) == ["version", "kind", "matched", "read", "rows"]


def test_a_toml_date_goes_out_as_its_iso_spelling() -> None:
    """A head's TOML date reads back as a `datetime.date`, which JSON has no
    spelling for. It goes out as text rather than refusing the whole listing
    over one field."""
    import datetime as dt

    payload = json.loads(
        render.document("items", [{"slug": "a", "planted": dt.date(2026, 9, 1)}])
    )
    assert payload["rows"][0]["planted"] == "2026-09-01"


def test_the_document_does_not_reorder_a_rows_fields() -> None:
    payload = json.loads(render.document("items", ROWS))
    assert list(payload["rows"][0]) == list(ROWS[0])
