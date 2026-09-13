"""Item files: the fence walk, the serializer, and location-is-state.

The grammar half is pure over text — no ``tmp_path``, no cwd — for the reason
`fileplan.declaration`'s refusals are: the old tool's suite ran ~40 of
them instantly because the validator did not touch a disk. Only the
location-is-state and round-trip-on-disk sections take a ``tmp_path``.

Everything grades against ``tests/fixtures/plan.toml``, never the repo's own
declaration. That is 1-1's rule and ``conftest.py`` aims the suite at it.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from conftest import FIXTURE_FILES

from fileplan.declaration import Declaration, Refusal, load
from fileplan.item import Item, head_errors, parse, read, render, slug, table, write

FIXTURES = Path(__file__).resolve().parent / "fixtures"

CANONICAL = '''\
+++
cultivar = "heirloom"
planted = 2026-09-01
after = ["decompose-section-1"]
+++

# A seedling

The body starts here.
'''


@pytest.fixture
def declaration() -> Declaration:
    return load(FIXTURES / "plan.toml")


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Declaration:
    """A ``plan.toml`` and its method doc copied into ``tmp_path``, with the
    declared directories made. The declaration's root is what a state's `path`
    resolves against, so the fixture cannot be loaded from where it lives."""
    for name in FIXTURE_FILES:
        (tmp_path / name).write_text((FIXTURES / name).read_text())
    declaration = load(tmp_path / "plan.toml")
    for state in declaration.states.values():
        (tmp_path / state.path).mkdir(parents=True)
    return declaration


def item_at(declaration: Declaration, state: str, name: str, text: str) -> Path:
    path = declaration.root / declaration.states[state].path / name
    path.write_text(text)
    return path


# --------------------------------------------------------------------------
# Parsing: pure
# --------------------------------------------------------------------------


def test_a_well_formed_file_splits_into_head_and_body() -> None:
    head, body = parse(CANONICAL)
    assert head == {
        "cultivar": "heirloom",
        "planted": dt.date(2026, 9, 1),
        "after": ["decompose-section-1"],
    }
    assert body == "\n# A seedling\n\nThe body starts here.\n"


def test_the_head_holds_whatever_toml_says_it_holds() -> None:
    """No coercion. Every scalar TOML spells comes back as its own type, which
    is what lets the writer emit each one as it found it."""
    head, _ = parse(
        "+++\n"
        'text = "a string"\n'
        "count = 3\n"
        "ratio = 1.5\n"
        "ready = true\n"
        "day = 2026-09-01\n"
        "moment = 2026-09-01T12:30:00\n"
        "clock = 12:30:00\n"
        'list = ["a", "b"]\n'
        "+++\n"
    )
    assert head["text"] == "a string"
    assert head["count"] == 3
    assert head["ratio"] == 1.5
    assert head["ready"] is True
    assert head["day"] == dt.date(2026, 9, 1)
    assert head["moment"] == dt.datetime(2026, 9, 1, 12, 30)
    assert head["clock"] == dt.time(12, 30)
    assert head["list"] == ["a", "b"]


def test_no_opening_fence_refuses_rather_than_reading_as_headless() -> None:
    """The dangerous reading is "no frontmatter, carry on": an item with no
    head is invisible to every filter, so silence would make a broken file
    look absent rather than broken."""
    with pytest.raises(Refusal, match="no `\\+\\+\\+` head on line 1"):
        parse("# Not an item file\n\nprose\n")


def test_an_unclosed_fence_refuses_and_says_the_whole_file_is_the_head() -> None:
    with pytest.raises(Refusal, match="never closed"):
        parse('+++\ncultivar = "heirloom"\n\nprose\n')


def test_unparseable_toml_carries_tomllibs_own_message() -> None:
    with pytest.raises(Refusal, match="not valid TOML"):
        parse('+++\ncultivar = "unterminated\n+++\n')


@pytest.mark.parametrize(
    "head_text",
    [
        '[section]\nkey = "value"',
        'nested = { a = 1 }',
        '[[rows]]\na = 1',
    ],
)
def test_a_nested_table_refuses_by_name(head_text: str) -> None:
    """A head is flat, stated once here rather than handled everywhere."""
    with pytest.raises(Refusal) as raised:
        parse(f"+++\n{head_text}\n+++\n")
    assert "is a table, and a head is flat" in str(raised.value)


def test_an_empty_head_is_a_head() -> None:
    head, body = parse("+++\n+++\nprose\n")
    assert head == {}
    assert body == "prose\n"


def test_an_empty_body_is_a_body() -> None:
    head, body = parse('+++\ncultivar = "heirloom"\n+++\n')
    assert head == {"cultivar": "heirloom"}
    assert body == ""


def test_crlf_parses_and_the_body_keeps_its_line_endings() -> None:
    """A `\\r` left on a head line is dropped — tomllib refuses one not
    followed by `\\n` — but the body's are the body's."""
    head, body = parse('+++\r\ncultivar = "heirloom"\r\n+++\r\n\r\nprose\r\n')
    assert head == {"cultivar": "heirloom"}
    assert body == "\r\nprose\r\n"


# --------------------------------------------------------------------------
# Round-trip: the done line
# --------------------------------------------------------------------------


def test_a_canonical_file_round_trips_byte_identical() -> None:
    head, body = parse(CANONICAL)
    assert render(table(head), body) == CANONICAL


@pytest.mark.parametrize(
    "body",
    [
        "no final newline",
        "trailing blank lines\n\n\n",
        "trailing   whitespace   \n",
        "a form feed \x0c and a line separator   survive\n",
        "\r\nCRLF prose\r\n",
        "",
    ],
)
def test_the_body_survives_byte_for_byte(body: str) -> None:
    """`str.splitlines()` breaks on all of these; the split is on `\\n` alone
    so that a head edit cannot quietly rewrite prose it was not asked about."""
    text = f'+++\ncultivar = "heirloom"\n+++\n{body}'
    assert parse(text)[1] == body
    head, parsed_body = parse(text)
    assert render(table(head), parsed_body) == text


def test_key_order_is_preserved_from_the_source() -> None:
    text = '+++\ntag = "b"\ncultivar = "heirloom"\nrootstock = "a"\n+++\n'
    head, body = parse(text)
    assert list(head) == ["tag", "cultivar", "rootstock"]
    assert render(table(head), body) == text


def test_a_key_a_caller_adds_is_appended() -> None:
    head, body = parse('+++\ntag = "b"\ncultivar = "heirloom"\n+++\nprose\n')
    head["rootstock"] = "M26"
    assert render(table(head), body).splitlines()[1:4] == [
        'tag = "b"',
        'cultivar = "heirloom"',
        'rootstock = "M26"',
    ]


def test_rendering_twice_is_idempotent() -> None:
    """A head someone typed is not canonical; after one write, it is."""
    head, body = parse('+++ \n  cultivar   =   "heirloom"  # why\n+++\n\nprose\n')
    once = render(table(head), body)
    assert once == '+++\ncultivar = "heirloom"\n+++\n\nprose\n'
    head, body = parse(once)
    assert render(table(head), body) == once


def test_a_date_stays_a_date_and_a_quoted_date_stays_a_string() -> None:
    text = '+++\nplanted = 2026-09-01\ntag = "2026-09-01"\n+++\n'
    head, body = parse(text)
    assert head["planted"] == dt.date(2026, 9, 1)
    assert head["tag"] == "2026-09-01"
    assert render(table(head), body) == text


# --------------------------------------------------------------------------
# Serialization
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        'a "quoted" word',
        "a back\\slash",
        "a\nnewline",
        "a\ttab",
        "a café — ☃ unicode",
        "a \x00 null",
        "",
    ],
)
def test_a_string_needing_escapes_round_trips(value: str) -> None:
    """The old tool escaped `\\` and `"` only, so a title carrying a newline
    wrote a head its own reader then refused. Nothing here can."""
    text = render(table({"tag": value}), "prose\n")
    assert parse(text)[0]["tag"] == value


def test_unicode_is_written_raw_not_escaped() -> None:
    assert 'tag = "café"' in render(table({"tag": "café"}), "")


def test_an_empty_array_round_trips() -> None:
    assert render(table({"after": []}), "") == "+++\nafter = []\n+++\n"
    assert parse("+++\nafter = []\n+++\n")[0] == {"after": []}


@pytest.mark.parametrize("value", ["true", "2026-09-01", "42", "[a]"])
def test_a_value_that_would_be_ambiguous_unquoted_stays_a_string(value: str) -> None:
    assert parse(render(table({"tag": value}), ""))[0]["tag"] == value


def test_a_boolean_is_written_bare_and_reads_back_as_a_boolean() -> None:
    """`bool` is tested before `int` in the writer, and that order is the whole
    control: a `bool` *is* an `int`, so the integer arm reached first would
    write `ready = True`, which tomllib refuses to read."""
    text = render(table({"tag": True}), "")
    assert text == "+++\ntag = true\n+++\n"
    assert parse(text)[0]["tag"] is True


def test_a_value_a_head_cannot_spell_refuses_by_name() -> None:
    with pytest.raises(Refusal, match='"tag" holds a set'):
        render(table({"tag": {"a", "b"}}), "")


# --------------------------------------------------------------------------
# Location is state
# --------------------------------------------------------------------------


def test_an_item_in_greenhouse_reports_state_greenhouse(tree: Declaration) -> None:
    path = item_at(tree, "greenhouse", "a.md", '+++\ncultivar = "heirloom"\n+++\n')
    assert read(path, tree).state.name == "greenhouse"


def test_an_item_in_orchard_reports_state_orchard(tree: Declaration) -> None:
    path = item_at(tree, "orchard", "a.md", '+++\ncultivar = "heirloom"\n+++\n')
    assert read(path, tree).state.name == "orchard"


def test_the_state_is_the_declarations_answer_not_the_directorys_name(
    tree: Declaration,
) -> None:
    """`cold-frame`'s path is `beds/hardening-off`, which shares neither its
    name nor its last segment — so a caller reading the directory for itself
    cannot get this right, and this is the done line's other half."""
    path = item_at(tree, "cold-frame", "a.md", '+++\ncultivar = "heirloom"\n+++\n')
    assert path.parent.name == "hardening-off"
    assert read(path, tree).state.name == "cold-frame"


def test_an_item_in_an_undeclared_directory_refuses_by_name(
    tree: Declaration,
) -> None:
    stray = tree.root / "compost"
    stray.mkdir()
    path = stray / "a.md"
    path.write_text('+++\ncultivar = "heirloom"\n+++\n')
    with pytest.raises(Refusal, match="is not a declared state directory"):
        read(path, tree)


def test_a_file_nested_below_a_state_is_in_no_state(tree: Declaration) -> None:
    """A `path` is a literal directory, so a file below one is in no state
    rather than in the state above it — fewer special cases."""
    below = tree.root / tree.states["greenhouse"].path / "bench"
    below.mkdir()
    path = below / "a.md"
    path.write_text('+++\ncultivar = "heirloom"\n+++\n')
    with pytest.raises(Refusal, match="is not a declared state directory"):
        read(path, tree)


def test_a_file_with_no_head_refuses_by_name_naming_the_path(
    tree: Declaration,
) -> None:
    path = item_at(tree, "greenhouse", "a.md", "# Just prose\n")
    with pytest.raises(Refusal) as raised:
        read(path, tree)
    assert str(path) in str(raised.value)
    assert "no `+++` head on line 1" in str(raised.value)


def test_an_item_round_trips_through_read_and_write_unchanged(
    tree: Declaration,
) -> None:
    """The done line. Read it, write it back untouched, and the bytes match."""
    path = item_at(tree, "greenhouse", "a.md", CANONICAL)
    write(read(path, tree))
    assert path.read_text() == CANONICAL


def test_writing_twice_is_idempotent(tree: Declaration) -> None:
    typed = '+++ \n  cultivar = "heirloom"   # hand-typed\n+++\n\nprose\n'
    path = item_at(tree, "greenhouse", "a.md", typed)

    write(read(path, tree))
    once = path.read_bytes()
    write(read(path, tree))

    assert path.read_bytes() == once


def test_a_written_key_lands_and_the_body_is_untouched(tree: Declaration) -> None:
    path = item_at(tree, "greenhouse", "a.md", CANONICAL)
    item = read(path, tree)

    written = Item(
        path=item.path,
        state=item.state,
        head={**item.head, "tag": "x"},
        body=item.body,
    )
    write(written)

    reread = read(path, tree)
    assert reread["tag"] == "x"
    assert reread.body == item.body
    assert list(reread.head) == ["cultivar", "planted", "after", "tag"]


def test_write_preserves_the_file_mode(tree: Declaration) -> None:
    """The replacement is a new inode, so the mode has to be carried."""
    path = item_at(tree, "greenhouse", "a.md", CANONICAL)
    path.chmod(0o640)
    write(read(path, tree))
    assert path.stat().st_mode & 0o777 == 0o640


# --------------------------------------------------------------------------
# Key checking
# --------------------------------------------------------------------------


def test_an_undeclared_head_key_refuses_naming_it(declaration: Declaration) -> None:
    """The typo detector: `cultivarr` is caught rather than read as unset."""
    errors = head_errors({"cultivarr": "heirloom"}, declaration, None)
    assert errors == [
        '"cultivarr" is not a declared key '
        "(declared: cultivar, rootstock, tag, notebook, pest, planted, after, "
        "batch, "
        "cutting, for-tree, for-step, graft, "
        "graft-status; intrinsic: title)"
    ]


def test_a_declared_key_produces_no_error(declaration: Declaration) -> None:
    assert head_errors({"cultivar": "heirloom", "after": []}, declaration, None) == []


def test_a_value_outside_its_keys_values_does_not_refuse(
    tree: Declaration,
) -> None:
    """Grading belongs to a transition's `refuses` and to the reads. Enforced
    here, one bad value would break a whole listing rather than one item."""
    assert tree.keys["cultivar"].values == ("heirloom", "hybrid")
    path = item_at(tree, "greenhouse", "a.md", '+++\ncultivar = "windfall"\n+++\n')
    assert read(path, tree)["cultivar"] == "windfall"


def test_an_undeclared_key_refuses_at_read_naming_the_file(
    tree: Declaration,
) -> None:
    path = item_at(tree, "greenhouse", "a.md", '+++\ncultivarr = "heirloom"\n+++\n')
    with pytest.raises(Refusal) as raised:
        read(path, tree)
    assert str(path) in str(raised.value)
    assert '"cultivarr" is not a declared key' in str(raised.value)


# --------------------------------------------------------------------------
# The slug
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Ship the Thing", "ship-the-thing"),
        (
            "click's version is declared in three places",
            "click-s-version-is-declared-in-three-places",
        ),
        ("  Leading and trailing!  ", "leading-and-trailing"),
        ("Multiple   ---   separators", "multiple-separators"),
        ("Item 42: the sequel", "item-42-the-sequel"),
    ],
)
def test_a_title_becomes_a_kebab_case_filename(title: str, expected: str) -> None:
    assert slug(title) == expected


def test_the_slug_is_ascii_only_and_accents_do_not_reach_a_filename() -> None:
    assert slug("Café naïve") == "caf-na-ve"


def test_a_title_with_no_letters_or_digits_refuses() -> None:
    with pytest.raises(Refusal, match="no letters or digits"):
        slug("!!! ??? ...")


# --------------------------------------------------------------------------
# A capability's key: admitted where the state gives it, refused elsewhere
# --------------------------------------------------------------------------
#
# `orchard` is the fixture's `queued` state, so an item there may carry a
# `position`. The key is declared nowhere and may not be — see
# `test_declaration.py` — so `head_errors` has to admit it from the *state*,
# which is location-is-state read one more time.


def test_a_queued_state_admits_the_key_its_capability_gives(
    declaration: Declaration,
) -> None:
    state = declaration.states["orchard"]
    assert state.capability_keys == ("position", "number")
    head = {"title": "A tree", "position": 100, "number": 2}
    assert head_errors(head, declaration, state) == []


def test_a_non_queued_state_carrying_it_refuses_by_name(
    declaration: Declaration,
) -> None:
    """Location *is* state: what a state gives an item goes with the item's
    location rather than sitting beside it, and a stale one left by a hand
    edit would spell an order in a state that has none."""
    state = declaration.states["greenhouse"]
    (error,) = head_errors({"position": 100}, declaration, state)
    assert '"position" is what the queued capability gives an item' in error
    assert "greenhouse is not a queued state" in error


def test_the_capability_key_is_not_read_as_an_undeclared_key(
    declaration: Declaration,
) -> None:
    """Reading as "not a declared key" would send someone to write
    `[keys.position]`, which refuses too, one message later — the same reason
    an intrinsic key gets its own message."""
    (error,) = head_errors({"position": 100}, declaration, None)
    assert "not a declared key" not in error


def test_a_quoted_place_refuses_in_the_state_that_gives_it(
    declaration: Declaration,
) -> None:
    """The key is arithmetic, so its *type* is the capability's business —
    unlike a declared key's value, which is graded by `refuses` and the reads."""
    state = declaration.states["orchard"]
    (error,) = head_errors({"position": "100"}, declaration, state)
    assert "is not a whole number" in error


def test_an_item_in_a_queued_state_reads_with_its_place(tree: Declaration) -> None:
    path = item_at(tree, "orchard", "a.md", '+++\ntitle = "A tree"\nposition = 100\n+++\n')
    assert read(path, tree)["position"] == 100


def test_an_item_elsewhere_carrying_a_place_refuses_at_read(
    tree: Declaration,
) -> None:
    path = item_at(tree, "greenhouse", "a.md", "+++\nposition = 100\n+++\n")
    with pytest.raises(Refusal) as refusal:
        read(path, tree)
    assert str(path) in str(refusal.value)
    assert "greenhouse is not a queued state" in str(refusal.value)


def test_an_items_slug_is_its_filename_stem(tree: Declaration) -> None:
    """The item's one handle, read off its path like its state — never out of
    its head."""
    path = item_at(tree, "greenhouse", "a-seedling.md", CANONICAL)
    assert read(path, tree).slug == "a-seedling"
