"""The register: what a number is minted from, and every way it refuses.

**No ``tmp_path`` anywhere in this file.** `fileplan.numbered.next_number`
is a total function of the numbers already taken plus the one the item already
holds, and both archive readers are total over a string — so the whole table
costs no filesystem, the split every module since 1-1 keeps.

The vocabulary is deliberately not this repo's. A register is integers and
slugs; nothing here needs a declaration at all.
"""

from __future__ import annotations

import pytest

from fileplan import numbered, read
from fileplan.declaration import (
    ARCHIVE,
    CAPABILITY_KEYS,
    FIRST_NUMBER,
    NUMBERED,
    Refusal,
    State,
)

WHERE = "orchard-archive.md"


def held(*numbers: int) -> dict[int, list[str]]:
    """A register holding ``numbers``, one item each."""
    return numbered.taken({f"item-{one}": one for one in numbers})


# --------------------------------------------------------------------------
# The two spellings, pinned together
# --------------------------------------------------------------------------


def test_the_capability_is_spelled_the_same_in_both_modules() -> None:
    """`declaration.py` cannot import this module — this one imports `Refusal`
    from it, so the import runs the other way — and spells the two words for
    itself, exactly as it does for `claimed`. Two copies of a word are safe
    only while something says they agree, and this is that something."""
    assert NUMBERED == numbered.NAME
    assert ARCHIVE == numbered.ARCHIVE
    assert CAPABILITY_KEYS[numbered.NAME] == numbered.KEY


# --------------------------------------------------------------------------
# Minting: max + 1, and the one bootstrap
# --------------------------------------------------------------------------


def test_the_next_number_is_one_past_the_highest() -> None:
    assert numbered.next_number(held(1, 2, 3)) == 4


def test_an_empty_register_mints_the_first_number() -> None:
    """A repo that has closed nothing and opened nothing. Before the old tool
    had this case the only way in was to hand-write the one key that is meant
    to be derived, which broke the invariant the tool exists to hold."""
    assert numbered.next_number({}) == numbered.FIRST == 1


def test_an_item_already_here_keeps_its_number() -> None:
    """4-4's place-keeping rule over the other head-key capability. An
    in-place verb is about the cursor and says nothing about identity, so it
    must not re-mint — and the number it keeps is its own even though the
    register would hand back something else."""
    assert numbered.next_number(held(1, 2, 3), current=2) == 2


def test_a_kept_number_is_not_graded_against_the_register() -> None:
    """Deliberately: the item is not asking for a number, it already has one.
    Grading it here would refuse an in-place verb on an item whose number a
    *different* defect made odd, which is the listing's job to report."""
    assert numbered.next_number(held(1, 2), current=9) == 9


def test_the_register_reads_the_numbers_not_the_order_they_arrived_in() -> None:
    """A mapping, and mapping order is filesystem order. The arithmetic reads
    the integers, never the sequence they were walked in."""
    assert numbered.next_number(held(3, 1, 2)) == 4


def test_a_source_carrying_no_number_is_not_in_the_register() -> None:
    """An item in a numbered state with no number of its own is a row to be
    fixed, not the highest one — it must not drag the next mint on top of it."""
    assert numbered.taken({"a": 1, "b": None, "c": "2"}) == {1: ["a"]}


def test_a_boolean_is_not_a_number() -> None:
    """`True` is an `int` in Python and is not a number here. `tomllib` reads
    `number = true` as a bool, and a register that counted it would mint 2."""
    assert numbered.taken({"a": True}) == {}


# --------------------------------------------------------------------------
# The gap: a declaration this parser cannot see
# --------------------------------------------------------------------------


def test_a_gap_refuses_naming_the_missing_numbers() -> None:
    """The number above a gap may already be spoken for — by the very
    declaration the parser has stopped reading."""
    with pytest.raises(Refusal) as refusal:
        numbered.next_number(held(1, 2, 5))
    said = str(refusal.value)
    assert "runs to 5 with 2 gap(s): 3, 4" in said
    assert "may already be spoken for" in said


def test_a_gap_at_the_first_number_refuses_too() -> None:
    """The commonest real shape: an archive that is not being read at all, so
    every closed item's number is missing from the bottom up."""
    with pytest.raises(Refusal, match=r"gap\(s\): 1, 2"):
        numbered.next_number(held(3, 4))


def test_a_gapless_register_starting_at_one_is_fine() -> None:
    assert numbered.next_number(held(1, 2, 3, 4, 5, 6)) == 7


def test_an_empty_register_is_short_of_nothing() -> None:
    """A repo that has closed nothing and opened nothing. `next_number` mints
    `FIRST` into it, so a report of "1 is missing" would name a number nobody
    has lost."""
    assert numbered.missing(held()) == []


def test_a_contiguous_register_is_short_of_nothing() -> None:
    assert numbered.missing(held(1, 2, 3)) == []


def test_the_missing_numbers_come_back_in_order() -> None:
    assert numbered.missing(held(1, 5)) == [2, 3, 4]


def test_a_register_starting_above_the_first_is_short_of_what_is_below() -> None:
    """The commonest real shape: an archive nothing is reading, so every
    closed item's number is missing from the bottom up."""
    assert numbered.missing(held(3, 4)) == [1, 2]


def test_a_duplicate_produces_no_gap() -> None:
    """The limit recorded rather than built: two items claiming one number
    leave the arithmetic untouched, so there is no third report. The mint
    still refuses naming both, and two live items carrying one number both
    print it in the default read."""
    assert numbered.missing(numbered.taken({"one": 3, "two": 3, "three": 1, "x": 2})) == []


def test_the_mint_refuses_on_the_arithmetic_the_listing_reports() -> None:
    """One arithmetic, two readers. The walk moved out of `next_number` so the
    refusal at mint time and the report on every read cannot come to disagree
    about what a gap is; this is the half that says the extraction changed no
    behaviour."""
    with pytest.raises(Refusal) as refusal:
        numbered.next_number(held(1, 2, 5))
    assert "runs to 5 with 2 gap(s): 3, 4" in str(refusal.value)
    assert numbered.missing(held(1, 2, 5)) == [3, 4]


def test_two_items_claiming_one_number_refuse_naming_both() -> None:
    """The `--at` precedent, over identity rather than order: one of the two
    is about to be minted over, and a closed item that shares its number with
    a live one is unfindable in the archive."""
    with pytest.raises(Refusal) as refusal:
        numbered.next_number(numbered.taken({"one": 3, "two": 3}))
    said = str(refusal.value)
    assert "number 3 is claimed by one and two" in said


def test_a_duplicate_refuses_even_when_the_item_is_keeping_its_own() -> None:
    """Before the keep-what-you-have arm, deliberately: an in-place verb on a
    tree whose register is broken should say so rather than write over it."""
    with pytest.raises(Refusal, match="claimed by"):
        numbered.next_number(numbered.taken({"one": 3, "two": 3}), current=1)


# --------------------------------------------------------------------------
# The archive: a closed item's only record
# --------------------------------------------------------------------------


def test_the_strict_heading_form_is_read() -> None:
    assert numbered.numbers("## 1. A felled tree\n## 12. Another\n") == [1, 12]


def test_a_deeper_heading_is_not_an_entry() -> None:
    """Entries are `##`. A `###` under one is part of its record, and a `#` is
    the document's own title."""
    assert numbered.numbers("# 9. The archive\n### 4. A sub-heading\n") == []


def test_a_heading_with_no_title_is_not_an_entry() -> None:
    """`## 1.` alone names nothing, so it refuses rather than registering a
    number nobody can find again."""
    assert numbered.numbers("## 1.\n") == []
    assert numbered.heading_errors(numbered.unreadable("## 1.\n"), WHERE)


@pytest.mark.parametrize(
    "line",
    [
        "## Section 168: Something",  # the one that actually bit the old tool
        "## 168 Something",  # no full stop
        "## How these plans are written",
        "## 1: A felled tree",  # a colon, not a full stop
        "## 168-b. Something",  # a letter in the number
    ],
)
def test_a_heading_the_register_cannot_read_refuses_naming_the_line(
    line: str,
) -> None:
    """The check that earns its keep. A closed item's heading is the **only**
    record that its number is taken, so one the parse cannot read drops the
    number silently and frees the next item to mint it again — and the gap
    check structurally cannot catch it, because a loss at the top lowers the
    maximum and leaves what remains gapless."""
    (error,) = numbered.heading_errors(
        numbered.unreadable(f"# The archive\n\n{line}\n"), WHERE
    )
    assert f"{WHERE}:3:" in error
    assert line.strip() in error
    assert "`## <number>. <title>`" in error


def test_a_line_markdown_does_not_read_as_a_heading_is_left_alone() -> None:
    """`##Foo` is not a heading — ATX needs the space — so it is prose, and
    prose is not graded. The rule is the one 4-1 took for a bullet-shaped
    line: match the strict form mechanically, and leave everything that is
    not one of them alone."""
    unread = numbered.unreadable("##Not a heading\n")
    assert numbered.heading_errors(unread, WHERE) == []


def test_every_bad_heading_is_reported_not_just_the_first() -> None:
    """Collected and reported at once, like `shape_errors` — fixing one at a
    time because the tool only ever names one is the cost this avoids."""
    text = "## 1. Fine\n## Section 2: not fine\n## 3. Fine\n## Section 4: nor this\n"
    assert len(numbered.heading_errors(numbered.unreadable(text), WHERE)) == 2
    assert numbered.numbers(text) == [1, 3]


def test_an_archive_with_nothing_in_it_is_legibly_empty() -> None:
    """A repo that has closed nothing. It is not a broken parse, and it is why
    the old tool's illegibility test dissolved: `heading_errors` runs on every
    mint rather than only on an empty register, so by the time an empty
    register is reached it can only mean an empty corpus."""
    assert numbered.numbers("") == []
    assert numbered.heading_errors(numbered.unreadable(""), WHERE) == []
    assert numbered.unreadable("") == []
    assert numbered.next_number(held()) == numbered.FIRST


def test_a_heading_that_parses_is_not_a_lost_close_out() -> None:
    assert numbered.unreadable("# The archive\n\n## 1. A felled tree\n") == []


def test_a_lost_close_out_comes_back_with_its_line_and_what_it_says() -> None:
    """1-based, and stripped: a person fixing one needs to find the line and
    to see what it was written as. `## Section 168:` is the one that actually
    bit the old tool."""
    text = "# The archive\n\n## 1. A felled tree\n\n## Section 168: Something\n"
    assert numbered.unreadable(text) == [(5, "## Section 168: Something")]


def test_a_deeper_heading_is_not_a_lost_close_out() -> None:
    """`###` under an entry is part of its record and `#` is the document's
    own title. Only a `##` was ever meant to be an entry."""
    assert numbered.unreadable("# 9. The archive\n### 4. A sub-heading\n") == []


def test_every_lost_close_out_comes_back_in_document_order() -> None:
    text = "## 1. Fine\n## Section 2: not fine\n## 3. Fine\n## Section 4: nor this\n"
    assert [line for line, _ in numbered.unreadable(text)] == [2, 4]


def test_the_refusal_is_built_from_the_walk_the_report_is_built_from() -> None:
    """The other half of the extraction's regression: `heading_errors` says
    exactly what it said before, one message per line `unreadable` names, so
    the mint and the listing cannot disagree about which line is lost."""
    text = "## 1. Fine\n## Section 2: not fine\n## Section 4: nor this\n"
    said = numbered.heading_errors(numbered.unreadable(text), WHERE)
    assert len(said) == len(numbered.unreadable(text)) == 2
    for message, (line, written) in zip(said, numbered.unreadable(text)):
        assert message.startswith(f"{WHERE}:{line}: `{written}` is not a heading")


# --------------------------------------------------------------------------
# The two records a listing carries
# --------------------------------------------------------------------------


def test_the_state_field_is_spelled_the_same_in_both_modules() -> None:
    """`read.py` imports this module, so the word is spelled here and the
    import runs the other way — the shape `NAME` and `ARCHIVE` already have
    against `declaration.py`. Two copies of a word are safe only while
    something says they agree, and this is that something. Both mean the
    state's **declared name**, never its directory."""
    assert numbered.STATE == read.STATE


def test_a_lost_record_carries_the_state_the_archive_and_the_line() -> None:
    """A second record shape rather than a discriminator on the first: a gap
    is a *number* and this is a *document line*, so one merged array would be
    a union half empty at every read."""
    assert numbered.lost("orchard", WHERE, 5, "## Section 168: Something") == {
        numbered.STATE: "orchard",
        numbered.ARCHIVE: WHERE,
        numbered.LINE: 5,
        numbered.TEXT: "## Section 168: Something",
    }


# --------------------------------------------------------------------------
# The value: a number is arithmetic
# --------------------------------------------------------------------------


def test_a_bare_integer_number_is_no_error() -> None:
    assert numbered.errors({numbered.KEY: 4}) == []


def test_a_head_with_no_number_is_no_error() -> None:
    assert numbered.errors({"title": "A tree"}) == []


def test_a_quoted_number_refuses_because_the_key_is_arithmetic() -> None:
    """`"10"` sorts ahead of `"9"` as text, so a register that depended on how
    a value was spelled would not be a register."""
    (error,) = numbered.errors({numbered.KEY: "4"})
    assert "not a whole number" in error
    assert "bare integer" in error


@pytest.mark.parametrize("value", [1.5, True, [4], {"n": 4}])
def test_anything_that_is_not_a_whole_number_refuses(value: object) -> None:
    assert numbered.errors({numbered.KEY: value})


# --------------------------------------------------------------------------
# The entry: the writer beside the readers
# --------------------------------------------------------------------------

#: An archive with a preamble and two entries with a gap between them, which
#: is the shape a real one has: prose at the top that is not an entry, and
#: room for the number about to be filed. Not spelled `ARCHIVE`: that name is
#: already the state *field*, imported above and pinned against
#: `numbered.ARCHIVE` at the top of this file.
FILED = """\
# The orchard's archive

*Preamble. Not an entry, and it must still be there afterwards.*

## 1. A felled tree

What it was, and why it is gone.

## 7. A late one

Closed before the ones below it were.
"""


def test_an_entry_goes_in_before_the_first_higher_one() -> None:
    """Inserted, never appended: section 4 of this repo closed before section
    3, and a verb that appended would have written 1, 2, 4, 3."""
    written = numbered.entry(FILED, 3, "A middle one")
    assert numbered.numbers(written) == [1, 3, 7]
    assert "## 3. A middle one\n\n## 7. A late one" in written


def test_an_entry_higher_than_every_other_goes_at_the_end() -> None:
    written = numbered.entry(FILED, 8, "The newest")
    assert numbered.numbers(written) == [1, 7, 8]
    assert written.endswith("## 8. The newest\n")


def test_an_entry_lower_than_every_other_goes_above_them_all() -> None:
    """And below the preamble, which is not an entry — the insertion point is
    the first *heading* that parses, not the top of the file."""
    written = numbered.entry("# A title\n\nPreamble.\n\n## 4. Four\n", 2, "Two")
    assert numbered.numbers(written) == [2, 4]
    assert "Preamble." in written.split("## 2. Two")[0]


def test_an_entry_into_an_empty_archive_is_the_whole_document() -> None:
    """A repo that has closed nothing until now."""
    assert numbered.entry("", 1, "The first") == "## 1. The first\n"


def test_the_preamble_survives_the_insertion() -> None:
    written = numbered.entry(FILED, 9, "The newest")
    assert FILED.rstrip("\n") in written.rstrip("\n").replace(
        "\n\n## 9. The newest", ""
    )


def test_the_entry_is_the_strict_form_the_register_reads() -> None:
    """The whole reason the writer lives beside the readers. What it writes
    parses, and nothing it writes is a `##` the register cannot read — which
    is the failure `docs/method.md#the-register` records the old tool having."""
    written = numbered.entry(FILED, 3, "A middle one")
    assert numbered.heading_errors(numbered.unreadable(written), WHERE) == []


def test_the_result_re_parses_to_a_contiguous_register() -> None:
    """The end-to-end fact the insertion exists for: fill the gap and the next
    mint stops refusing."""
    written = FILED
    for number, title in ((2, "Two"), (3, "Three"), (4, "Four"), (5, "Five"), (6, "Six")):
        written = numbered.entry(written, number, title)
    numbers = numbered.numbers(written)
    assert numbers == [1, 2, 3, 4, 5, 6, 7]
    assert numbered.next_number(numbered.taken(
        {f"§ {one}.": one for one in numbers}
    )) == 8


def test_exactly_one_blank_line_sits_on_each_side_of_the_entry() -> None:
    """The shape every hand-written entry already has, so a filed one and a
    hand-written one are indistinguishable in the document."""
    written = numbered.entry(FILED, 3, "A middle one")
    lines = written.splitlines()
    at = lines.index("## 3. A middle one")
    assert lines[at - 1] == "" and lines[at + 1] == ""
    assert lines[at - 2] != "" and lines[at + 2] != ""


def test_an_archive_ending_in_blank_lines_does_not_grow_a_second_gap() -> None:
    assert numbered.entry("## 1. One\n\n\n\n", 2, "Two") == "## 1. One\n\n## 2. Two\n"


def test_a_number_the_archive_already_holds_refuses_naming_both() -> None:
    """The mint's refusal, reused rather than written a second time: it is the
    same question — two claimants for one number leave one of them unfindable
    once its file is gone."""
    with pytest.raises(Refusal) as refusal:
        numbered.entry(FILED, 7, "A second seven")
    said = str(refusal.value)
    assert "number 7 is claimed by" in said
    assert "A second seven" in said and "§ 7. in the archive" in said


def test_a_gap_elsewhere_does_not_refuse_a_filing() -> None:
    """A gap refuses a *mint*, because the number above it may be spoken for.
    Filing is what fills a gap in, and a tool that refused there would be
    declining to accept the fix. `FILED` has a five-number hole in it."""
    assert numbered.numbers(numbered.entry(FILED, 2, "Two")) == [1, 2, 7]


def test_a_heading_the_register_cannot_read_is_not_an_insertion_point() -> None:
    """It is not counted, so it does not move the entry — and it is a refusal
    the caller has already made, because `heading_errors` runs before this on
    every run that files."""
    lost = "## Section 9: not a heading this can read\n"
    assert numbered.entry(lost, 3, "Three").endswith("## 3. Three\n")


def test_a_record_goes_under_the_heading_with_one_blank_line_between() -> None:
    """The half `archive-plan` needs: mint-then-fill cannot work when the run
    deletes the body the record is written from, so the prose comes in with
    the run (`docs/method.md#dissolving`)."""
    written = numbered.entry(FILED, 3, "A middle one", "What it decided.")
    assert "## 3. A middle one\n\nWhat it decided.\n\n## 7." in written


def test_a_record_of_several_paragraphs_lands_whole() -> None:
    written = numbered.entry(FILED, 3, "A middle one", "One.\n\nTwo.\n\nThree.")
    assert "## 3. A middle one\n\nOne.\n\nTwo.\n\nThree.\n\n## 7." in written


def test_a_records_own_blank_lines_at_the_edges_are_stripped() -> None:
    """A heredoc arrives with a trailing newline and often a leading one; the
    entry must not grow a second gap because of how it was typed."""
    assert numbered.entry(FILED, 3, "A middle one", "\n\nWhat it decided.\n\n\n") == (
        numbered.entry(FILED, 3, "A middle one", "What it decided.")
    )


def test_an_empty_record_is_byte_identical_to_the_heading_alone() -> None:
    """5-1's output, unchanged: a verb that *moves* the item still mints an
    empty heading and the session fills it in, because the source material
    survives the run."""
    assert numbered.entry(FILED, 3, "A middle one", "") == numbered.entry(
        FILED, 3, "A middle one"
    )
    assert numbered.entry(FILED, 3, "A middle one", "\n\n") == numbered.entry(
        FILED, 3, "A middle one"
    )


def test_an_entry_with_a_record_still_inserts_at_the_register_position() -> None:
    """The record is prose under the heading; it does not move the heading."""
    written = numbered.entry(FILED, 3, "A middle one", "What it decided.")
    assert numbered.numbers(written) == [1, 3, 7]
    assert numbered.heading_errors(numbered.unreadable(written), WHERE) == []


def test_a_record_that_looks_like_a_heading_is_read_as_one() -> None:
    """**The limit, pinned rather than engineered around.** The record is
    written verbatim, so prose containing a `##` line becomes part of the
    document's headings — and an unreadable one refuses the *next* run, loudly,
    which is the polarity that fails loud. Nothing here parses the prose."""
    written = numbered.entry(FILED, 3, "A middle one", "## 4. Quoted")
    assert numbered.numbers(written) == [1, 3, 4, 7]


# --------------------------------------------------------------------------
# The floor: where a declared register begins
# --------------------------------------------------------------------------


def test_an_empty_register_with_a_floor_mints_the_floor_itself() -> None:
    """Inclusive, which is the whole of the field's meaning: 192 is the first
    number this register may hold, not the number the one below it stopped at.
    A consumer cutting over from an archive it will not rewrite declares the
    number it wants next and gets exactly that."""
    assert numbered.next_number({}, first=192) == 192


def test_the_gap_report_names_no_gap_below_the_floor() -> None:
    """`test_a_register_starting_above_the_first_is_short_of_what_is_below`,
    inverted by a declaration: those numbers are recorded in an archive this
    register does not read, so they are not missing from it."""
    assert numbered.missing(held(192, 193), first=192) == []


def test_a_gap_above_the_floor_still_refuses() -> None:
    """The floor moves where the walk starts and changes nothing else."""
    with pytest.raises(Refusal, match=r"gap\(s\): 193"):
        numbered.next_number(held(192, 194), first=192)


def test_a_gap_at_the_floor_refuses_too() -> None:
    """`test_a_gap_at_the_first_number_refuses_too`, one floor over: the
    commonest real shape is an archive nothing is reading, and a declared
    floor must not make that shape legible."""
    with pytest.raises(Refusal, match=r"gap\(s\): 192, 193"):
        numbered.next_number(held(194, 195), first=192)


def test_a_number_below_the_floor_refuses_naming_it_and_its_source() -> None:
    """The make-problems-visible rule, at the one step that is forgettable:
    setting the floor above something the corpus already holds. A clamp would
    absorb it into a register with a hole the gap walk starts above and can
    never report, so this refuses instead — and it names the number and the
    source that claims it, the way the duplicate refusal already reads `held`."""
    with pytest.raises(Refusal) as refusal:
        numbered.next_number(held(100), first=192)
    said = str(refusal.value)
    assert "number 100 is claimed by item-100" in said
    assert "192" in said


def test_filing_a_number_below_the_floor_does_not_refuse() -> None:
    """`current is not None` returns first, deliberately. An item already
    carrying a below-floor number must still be fileable — a filing is not a
    mint, and the register the floor guards is the one being minted into."""
    assert numbered.next_number(held(100), current=100, first=192) == 100


def test_a_register_with_no_declared_floor_starts_at_the_first_number() -> None:
    """`FIRST` is now the field's **default** rather than a constant to branch
    around: a state declaring nothing behaves exactly as it did before the
    field existed, which is why neither call site needs an `if`."""
    assert numbered.FIRST == 1
    assert numbered.next_number({}) == numbered.next_number({}, first=numbered.FIRST)
    assert numbered.missing(held(3)) == numbered.missing(held(3), first=numbered.FIRST)


def test_the_floor_field_is_spelled_the_same_in_both_modules() -> None:
    """`NAME` and `ARCHIVE`'s rule for the third word, and its default: two
    copies of a word are safe only while something says they agree. The
    default lives in `declaration.py` as a literal because the import runs
    that way — this is what pins it to the meaning."""
    assert FIRST_NUMBER == numbered.FIRST_NUMBER
    assert State(name="x", path="x").first_number == numbered.FIRST
