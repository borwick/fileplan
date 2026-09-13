"""Counting the sub-phase bullets a section's body carries.

Every test here runs with **no ``tmp_path``**: `fileplan.subphase` is
pure over a string, so the whole table is a table. That is the split 1-1
through 2-5 all keep, and it is why the counting rule can be argued about in
one place rather than through a tree.

The heading is fixture vocabulary — ``Steps`` rather than this repo's own
``Sub-phases`` — so nothing here passes by accidentally agreeing with
``plan.toml``. That a *declared* heading works at all is the point: a fixed
word would be one workflow's convention baked into the tool.
"""

from __future__ import annotations

import pytest

from fileplan import declaration, subphase

HEADING = "Steps"


def body(*lines: str) -> str:
    """A body as an item file carries it, with the lines given verbatim."""
    return "\n".join(lines) + "\n"


# --- counting ----------------------------------------------------------------


@pytest.mark.parametrize(
    "lines, expected",
    [
        pytest.param(("### Steps", "- one", "- two", "- three"), 3, id="three"),
        pytest.param(("### Steps", "- only"), 1, id="one"),
        pytest.param(("### Steps",), 0, id="heading-and-nothing"),
        pytest.param(("### Steps", "", "", ""), 0, id="heading-and-blank-lines"),
        pytest.param(("no heading at all", "- one"), 0, id="no-heading"),
        pytest.param((), 0, id="empty-body"),
    ],
)
def test_the_count_is_the_strict_bullets_under_the_heading(lines, expected):
    assert subphase.count(body(*lines), HEADING) == expected


def test_bullets_under_another_heading_are_not_counted():
    """The reason the heading is declared at all. This repo's own items carry
    bullets under "Back burner" and "Done when"; counting any top-level bullet
    would read an undecomposed section as a decomposed one, and the highlight
    that catches an undecomposed section would never fire."""
    text = body(
        "**Back burner:**",
        "- not a sub-phase",
        "- nor this",
        "",
        "### Steps",
        "- one",
        "",
        "### Done when",
        "- nor this either",
    )
    assert subphase.count(text, HEADING) == 1


def test_bold_prose_does_not_close_a_span_and_that_is_deliberate():
    """A span ends at the next **heading**, and bold prose is not one. Closing
    on it would mean interpreting prose to guess where a list stops, and the
    guesses are unbounded — ``**Done when:**``, ``_Done when:_``, ``Done
    when:``. The rule stays mechanical, and the convention it asks for is
    written into ``docs/method.md#sub-phases``: put the sub-phases last, or
    close them with a real heading."""
    text = body("### Steps", "- one", "", "**Done when:**", "- counted, by design")
    assert subphase.count(text, HEADING) == 2


def test_an_indented_bullet_is_continuation_rather_than_a_sub_phase():
    """A sub-phase's own bullet carries nested lists and paragraphs — section
    2's carried numbered decisions under four of its six. None of that is a
    sub-phase, and indentation is the whole of the rule."""
    text = body(
        "### Steps",
        "- one",
        "  - a nested note",
        "  1. a numbered decision",
        "  continuation prose",
        "- two",
    )
    assert subphase.count(text, HEADING) == 2


def test_prose_at_column_zero_is_ignored_however_it_starts():
    """The defect this repo's own item would have hit: a body opens with an
    italic paragraph at column zero, and ``*Each is one session…*`` is not a
    bullet. Markdown agrees — the space after a marker is what makes one."""
    text = body(
        "### Steps",
        "*Each is one session: plan it, accept the plan, clear, work it.*",
        "**The shape the seven share.** Done line 1 wants a status set by",
        "transitions; the resolved back burner says sub-phases stay bullets.",
        "- one",
    )
    assert subphase.count(text, HEADING) == 1
    assert subphase.errors(text, HEADING) == []


def test_the_span_ends_at_the_next_heading_of_any_level():
    text = body("### Steps", "- one", "#### A note", "- not counted")
    assert subphase.count(text, HEADING) == 1


def test_the_heading_is_matched_on_its_text_at_any_depth():
    """A consumer that writes ``## Steps`` is not forced into this repo's
    nesting to be counted."""
    for depth in ("#", "##", "###", "####"):
        assert subphase.count(body(f"{depth} Steps", "- one"), HEADING) == 1


# --- refusing the rest -------------------------------------------------------


@pytest.mark.parametrize(
    "line, marker",
    [
        pytest.param("* starred", "*", id="asterisk"),
        pytest.param("+ plussed", "+", id="plus"),
        pytest.param("1. numbered", "1.", id="numbered-dot"),
        pytest.param("2) parenthesised", "2)", id="numbered-paren"),
    ],
)
def test_a_bullet_shaped_line_in_any_other_form_refuses_naming_it(line, marker):
    """John's constraint from the big project: the bullets there are written
    inconsistently, and that is what causes parsing errors. The answer is to
    count the one form and **name** the rest rather than guess."""
    text = body("### Steps", "- fine", line)
    (message,) = subphase.errors(text, HEADING)
    assert "body line 3" in message
    assert f'begins "{marker}"' in message
    assert line in message


def test_every_malformed_bullet_is_named_rather_than_only_the_first():
    text = body("### Steps", "* one", "+ two", "1. three")
    assert len(subphase.errors(text, HEADING)) == 3


def test_a_heading_that_appears_twice_refuses_by_name():
    """Two spans are two answers to one question. Taking the first silently is
    exactly the drift counting was chosen to avoid."""
    text = body("### Steps", "- one", "## Other", "### Steps", "- two")
    (message,) = subphase.errors(text, HEADING)
    assert '2 "Steps" headings' in message
    assert "body lines 1, 4" in message


def test_a_well_formed_body_has_nothing_to_say():
    assert subphase.errors(body("### Steps", "- one", "- two"), HEADING) == []


def test_a_body_with_no_such_heading_has_nothing_to_say():
    """A state may declare a heading that a given item simply does not use —
    an item filed and not yet decomposed. That is zero, not broken."""
    text = body("**Decides from:** a draft section.", "- a top-level bullet")
    assert subphase.errors(text, HEADING) == []
    assert subphase.count(text, HEADING) == 0


def test_the_count_still_answers_when_the_bullets_are_malformed():
    """`count` is total over any string. The listing refuses on the
    errors beside it, so a caller cannot act on a number that hid a defect —
    but the number itself is never a crash."""
    text = body("### Steps", "- one", "* two")
    assert subphase.count(text, HEADING) == 1
    assert subphase.errors(text, HEADING) != []


# --- names ------------------------------------------------------------------

NAMED_BODY = body(
    "### Steps",
    "*Prose that opens the span, and is not a bullet.*",
    "- **graft-1 — the first.** Prose, and then",
    "  - an indented note that is not a step",
    "- **graft-2 — the second.**",
    "- **graft-3 — the third.**",
)


def test_a_name_is_the_first_token_of_the_bullets_leading_bold():
    assert subphase.names(NAMED_BODY, HEADING) == ["graft-1", "graft-2", "graft-3"]


@pytest.mark.parametrize(
    "line, expected",
    [
        pytest.param("- **4-1 — Counting the body.**", "4-1", id="em-dash"),
        pytest.param("- **4-1 – Counting.**", "4-1", id="en-dash"),
        pytest.param("- **4-1 - Counting.**", "4-1", id="hyphen-space"),
        pytest.param("- **4-1—Counting.**", "4-1", id="em-dash-unspaced"),
        pytest.param("- **4-1.**", "4-1.", id="no-separator-at-all"),
        pytest.param("- **one two — three.**", "one", id="first-token-wins"),
    ],
)
def test_a_hyphen_stays_in_the_name_and_a_dash_or_a_space_ends_it(line, expected):
    """``4-1`` has to survive whole, so a bare hyphen is not a separator; a
    dash with or without spaces around it is. The name is one token either
    way, which is what a person types and — from 4-4 on — what a claim record
    carries in its filename."""
    assert subphase.names(body("### Steps", line), HEADING) == [expected]


def test_inserting_a_bullet_above_leaves_every_other_name_unchanged():
    """The whole reason a name replaced the ordinal. Under ordinals this
    insert renumbers everything below it and every reference silently
    re-points; under names nothing moves."""
    before = subphase.names(NAMED_BODY, HEADING)
    after = subphase.names(
        NAMED_BODY.replace(
            "- **graft-1 — the first.**",
            "- **graft-0 — inserted above.**\n- **graft-1 — the first.**",
        ),
        HEADING,
    )
    assert before == ["graft-1", "graft-2", "graft-3"]
    assert after == ["graft-0", *before]


def test_a_bullet_with_no_bold_run_is_counted_and_has_no_name():
    """Naming is additive: 4-1's count is what it always was, and an unnamed
    sub-phase is simply not something anything may point at."""
    text = body("### Steps", "- **named — one.**", "- plain, with no bold at all")
    assert subphase.count(text, HEADING) == 2
    assert subphase.names(text, HEADING) == ["named"]
    assert subphase.errors(text, HEADING) == []


@pytest.mark.parametrize(
    "line",
    [
        pytest.param("- prose **bold, but not leading** here", id="bold-not-leading"),
        pytest.param("- ** — nothing before the dash.**", id="empty-name"),
        pytest.param("- **unclosed bold", id="unclosed"),
    ],
)
def test_a_bullet_that_is_not_the_named_form_carries_no_name(line):
    """No name rather than a guessed one. An empty name is no name: a
    reference nobody can type is not a reference."""
    text = body("### Steps", line)
    assert subphase.count(text, HEADING) == 1
    assert subphase.names(text, HEADING) == []


def test_two_bullets_sharing_a_name_refuse_listing_both_lines():
    """The duplicate heading's defect one level down: a name that answers to
    two sub-phases is not a reference."""
    text = body("### Steps", "- **dup — one.**", "- **other — two.**", "- **dup — three.**")
    (message,) = subphase.errors(text, HEADING)
    assert '2 sub-phases named "dup"' in message
    assert "body lines 2, 4" in message


# --- the cursor --------------------------------------------------------------

CURSOR_BODY = NAMED_BODY


def cursor(head, *, written=True):
    return subphase.cursor_errors(
        head, CURSOR_BODY, key="graft", heading=HEADING, written=written
    )


@pytest.mark.parametrize("at", ["graft-1", "graft-2", "graft-3"])
def test_a_cursor_naming_a_sub_phase_the_body_carries_is_fine(at):
    assert cursor({"graft": at}) == []


def test_a_head_carrying_no_cursor_is_not_graded():
    """An item filed and not yet started has none. That is the ordinary case
    rather than a defect, so no caller needs an ``is None`` arm."""
    assert cursor({}) == []


@pytest.mark.parametrize(
    "value",
    ["graft-9", "graft1", 2, "2"],
    ids=["out-of-range", "typo", "an-ordinal", "an-ordinal-as-text"],
)
def test_a_cursor_the_body_does_not_carry_refuses_naming_the_names_available(value):
    """Membership rather than arithmetic, which is the strictly better check:
    it catches a typo'd reference as well as one past the end, and an ordinal
    left over from before this sub-phase is caught rather than honoured."""
    (message,) = cursor({"graft": value})
    assert f'names sub-phase "{value}"' in message
    assert "graft-1, graft-2, graft-3" in message


def test_a_cursor_on_a_body_with_no_sub_phases_refuses():
    """The undecomposed case said the other way round: a cursor pointing into
    a section nobody has cut up yet has nothing to point at."""
    (message,) = subphase.cursor_errors(
        {"graft": "graft-1"},
        body("no heading here"),
        key="graft",
        heading=HEADING,
        written=True,
    )
    assert "carries none at all" in message


def test_a_cursor_on_a_body_whose_bullets_are_unnamed_says_which_line_needs_one():
    """Nothing falls back to an ordinal — a silent fallback is the failure
    being removed — so the refusal says what to do instead."""
    (message,) = subphase.cursor_errors(
        {"graft": "graft-1"},
        body("### Steps", "- one", "- two"),
        key="graft",
        heading=HEADING,
        written=True,
    )
    assert "no named sub-phase at all" in message
    assert "body lines 2, 3" in message
    assert "named by the bold it opens with" in message


def test_an_unnamed_bullet_is_named_beside_the_names_that_are_available():
    """A partly named body says both halves: here are the names, and here is
    the line that has not got one."""
    (message,) = subphase.cursor_errors(
        {"graft": "graft-2"},
        body("### Steps", "- **graft-1 — named.**", "- unnamed"),
        key="graft",
        heading=HEADING,
        written=True,
    )
    assert "graft-1" in message
    assert "body line 3" in message


# --- a cursor put onto a bullet already marked --------------------------------

#: The fixture's marks, and the fixture's alone. **Neither is ``done``**: this
#: repo's own word would let a tool that had learned it pass by agreeing
#: rather than by reading the bullet, and the two words together are what say
#: that *any* mark ends a sub-phase rather than one particular one.
RIPENED, THINNED = "ripened", "thinned"


def marked(*marks: str | None) -> str:
    """`NAMED_BODY`'s three steps with the marks given put on them."""
    lines = ["### Steps", "*Prose that opens the span, and is not a bullet.*"]
    for number, mark in enumerate(marks, start=1):
        said = f" **{mark}**" if mark else ""
        lines.append(f"- **graft-{number} — step {number}.**{said}")
    return body(*lines)


def test_a_cursor_moved_onto_a_marked_sub_phase_refuses_naming_its_mark():
    """Picking a cursor **up** and putting it on work already disposed of.
    The refusal names the value and the mark, so what is wrong is readable out
    of the refusal rather than out of the body.

    One half of the rule 16-1 narrowed: ``graft-3`` carries no mark here, so
    open work remains and the refusal is the one that fires. The other half is
    below, where nothing is open at all. The body is left exactly as it was,
    because what changed is when the arm is reached rather than what it says.
    """
    (message,) = subphase.cursor_errors(
        {"graft": "graft-2"},
        marked(RIPENED, THINNED, None),
        key="graft",
        heading=HEADING,
        written=True,
    )
    assert 'names sub-phase "graft-2"' in message
    assert f"**{THINNED}**" in message


def test_a_cursor_already_resting_on_a_marked_sub_phase_is_not_re_refused():
    """The other half of the same rule, and the one that makes marking work at
    all: a verb that marks the sub-phase the cursor is on writes no cursor, so
    it is not asked. A cursor resting on a marked bullet is the **ordinary**
    state right after the mark went on."""
    assert (
        subphase.cursor_errors(
            {"graft": "graft-1"},
            marked(RIPENED, None, None),
            key="graft",
            heading=HEADING,
            written=False,
        )
        == []
    )


def test_a_cursor_onto_a_marked_sub_phase_is_fine_where_nothing_is_open():
    """The deadlock 16-1 removed. Once every named step is marked there is no
    open bullet left for a cursor to point at, so the refusal protects nothing
    — and the cursor is still the true record of where the last session was.
    Refused, the cursor key becomes unwritable, and a verb that requires it
    could never run again on that section."""
    assert (
        subphase.cursor_errors(
            {"graft": "graft-2"},
            marked(RIPENED, THINNED, RIPENED),
            key="graft",
            heading=HEADING,
            written=True,
        )
        == []
    )


def test_the_pending_marker_counts_as_open():
    """`unmarked` is asked with ``pending=None``, so a decomposition that is
    not finished still counts as open. Every named step below is marked and
    the marker is not, which is a section with work nobody has written down
    yet — the arm stays refused there."""
    text = body(
        "### Steps",
        "- **graft-1 — the first.** **ripened**",
        "- **graft-2 — the second.** **thinned**",
        "- **unpruned — say what the rest of the training is.**",
    )
    (message,) = subphase.cursor_errors(
        {"graft": "graft-2"},
        text,
        key="graft",
        heading=HEADING,
        written=True,
    )
    assert f"**{THINNED}**" in message


def test_the_cursor_and_the_close_check_read_one_list():
    """The property the narrowing rests on, asserted rather than described.
    Both arms read `unmarked`, so a cursor may be written onto a marked bullet
    **exactly** when the section could close. Two spellings of the condition
    could drift; one reader with two callers cannot."""
    for marks in [
        (None, None, None),
        (RIPENED, None, None),
        (RIPENED, THINNED, None),
        (None, RIPENED, THINNED),
        (RIPENED, THINNED, RIPENED),
    ]:
        text = marked(*marks)
        refused = subphase.cursor_errors(
            {"graft": "graft-1"},
            text,
            key="graft",
            heading=HEADING,
            written=True,
        )
        open_bullets = subphase.unmarked(text, HEADING)
        # `graft-1` unmarked leaves the arm unreached, which is the one case
        # the equivalence is not about: the mark arm decides nothing there.
        if marks[0] is None:
            assert refused == []
            continue
        assert bool(refused) is bool(open_bullets)


def test_membership_is_graded_whether_the_run_writes_the_cursor_or_not():
    """`written` gates the mark arm and nothing else. A cursor naming a bullet
    the body has not got is wrong however it got there."""
    for written in (True, False):
        (message,) = cursor({"graft": "graft-9"}, written=written)
        assert 'names sub-phase "graft-9"' in message


# --- which one comes next ----------------------------------------------------


def upcoming(*, cursor=None, text=NAMED_BODY):
    return subphase.upcoming(text, HEADING, cursor=cursor)


def test_no_cursor_means_the_first_sub_phase_is_next():
    """A section nobody has picked up yet: the first bullet is what to pick
    up, and the head says nothing at all."""
    assert upcoming() == "graft-1"


def test_a_cursor_on_an_unmarked_sub_phase_is_itself_what_is_next():
    """The current sub-phase is not over, so nothing has moved past it — and
    the head is not consulted at all. What says a sub-phase is finished is the
    mark on its bullet, which is the one place it is written."""
    assert upcoming(cursor="graft-2", text=marked(RIPENED, None, None)) == "graft-2"


def test_a_cursor_on_a_marked_sub_phase_advances_to_the_next_unmarked_one():
    assert upcoming(cursor="graft-2", text=marked(None, RIPENED, None)) == "graft-1"
    assert upcoming(cursor="graft-1", text=marked(RIPENED, None, None)) == "graft-2"


def test_a_cursor_on_a_marked_bullet_is_not_what_comes_next_and_an_earlier_unmarked_one_is():
    """The case section 12 exists for, and the one a `(cursor, status)` pair
    could not say: *C5 done, C6 open, C7 done*. The cursor sits on the last,
    the first and the last carry marks, and the answer is the middle one."""
    assert upcoming(cursor="graft-3", text=marked(RIPENED, None, THINNED)) == "graft-2"


def test_the_first_unmarked_bullet_is_next_whatever_order_they_were_marked_in():
    """The same rule with no cursor at all. Order of *marking* is not order of
    reading: the body is walked in document order every time."""
    assert upcoming(text=marked(THINNED, None, RIPENED)) == "graft-2"
    assert upcoming(text=marked(None, RIPENED, RIPENED)) == "graft-1"


def test_a_skip_ends_a_sub_phase_as_squarely_as_a_finish():
    """Two marks, one rule. Nothing in `src/` knows either word, so a
    workflow's second disposition needs no line here."""
    assert upcoming(cursor="graft-1", text=marked(THINNED, None, None)) == "graft-2"


def test_a_body_whose_bullets_are_all_marked_has_no_next_sub_phase():
    """The decomposition is done. The count still shows beside this in a row,
    which is how a finished section is told apart from a state that counts
    none — neither field has to carry both facts."""
    assert upcoming(text=marked(RIPENED, THINNED, RIPENED)) is None
    assert upcoming(cursor="graft-3", text=marked(RIPENED, THINNED, RIPENED)) is None


def test_a_body_whose_bullets_are_all_marked_has_no_next_sub_phase_without_a_cursor():
    """A **carrier** is the shape this arm is really about: no cursor, no
    register, and a name form of its own. Every finding disposed of means the
    row leaves the listing, where reading `found[0]` had it still pointing at
    the first one long after the pass closed."""
    findings = body(
        "### Findings",
        "- **f1 — the first.** **fixed**",
        "- **f2 — the second.** **dismissed**",
    )
    assert subphase.upcoming(findings, "Findings", cursor=None) is None


def test_a_body_with_no_sub_phases_has_none_next():
    assert upcoming(text=body("no heading here")) is None
    assert upcoming(text=body("### Steps")) is None


def test_unnamed_bullets_are_counted_and_cannot_be_next():
    """Naming is additive: a bullet with no bold run is counted and is not
    something anything may point at. So a body of nothing but unnamed bullets
    has no next, and one that mixes them skips to the named one."""
    unnamed = body("### Steps", "- one", "- two")
    assert subphase.count(unnamed, HEADING) == 2
    assert upcoming(text=unnamed) is None

    mixed = body("### Steps", "- one", "- **graft-2 — named.**")
    assert upcoming(text=mixed) == "graft-2"


def test_the_pending_marker_is_still_what_comes_next_once_every_bullet_is_marked():
    """`bullets` is asked with ``pending=None`` deliberately, and this is the
    answer that would have gone silently otherwise: a decomposition that is
    not finished says so, and a composed session reads exactly this to tell
    "cut this up" from "work the next one". The marker can carry no mark and
    sits last, so it is reached only once every real bullet is marked."""
    text = body(
        "### Steps",
        "- **graft-1 — the first.** **ripened**",
        "- **pending — there are more steps to write.**",
    )
    assert subphase.upcoming(text, HEADING, cursor=None) == "pending"
    assert subphase.upcoming(text, HEADING, cursor="graft-1") == "pending"


def test_an_unmarked_bullet_is_reached_before_the_pending_marker():
    """The other side of it: the marker is last in document order, so real
    work outranks it without a line saying so."""
    text = body(
        "### Steps",
        "- **graft-1 — the first.**",
        "- **pending — there are more steps to write.**",
    )
    assert subphase.upcoming(text, HEADING, cursor=None) == "graft-1"


def test_a_cursor_the_body_does_not_carry_falls_to_the_first_unmarked_bullet():
    """`cursor_errors` refuses one of these at the moment it is written, so
    this reads what that guaranteed. A body edited out from under a cursor
    some other way must still list — nothing here may die over one item — and
    what is left to say is more useful than the cursor itself."""
    assert upcoming(cursor="graft-9", text=marked(RIPENED, None, None)) == "graft-2"
    assert upcoming(cursor="graft-9", text=marked(RIPENED, RIPENED, RIPENED)) is None


# --- minting: the declared name form -----------------------------------------

#: The two forms this repo's own `plan.toml` and the fixture between them
#: prove: one over a key the state mints, one over nothing but the ordinal.
NUMBERED_FORM, BARE_FORM = "{number}-{ordinal}", "c{ordinal}"


@pytest.mark.parametrize(
    "form, expected",
    [
        pytest.param(NUMBERED_FORM, ["number", "ordinal"], id="a-key-and-the-slot"),
        pytest.param(BARE_FORM, ["ordinal"], id="the-slot-alone"),
        pytest.param("{a}{b}{ordinal}", ["a", "b", "ordinal"], id="in-order"),
        pytest.param("plain", [], id="no-fields-at-all"),
        pytest.param("{}", [""], id="an-empty-field-is-still-one"),
    ],
)
def test_the_fields_of_a_form_are_read_in_the_order_it_writes_them(form, expected):
    """The **one** parse of a form: the loader grades against this rather than
    reading the template a second way and reaching a different answer."""
    assert subphase.fields(form) == expected


@pytest.mark.parametrize("form", [NUMBERED_FORM, BARE_FORM, "{a}-{b}/{ordinal}"])
def test_a_usable_form_has_nothing_to_say(form):
    assert subphase.form_errors(form, "where") == []


@pytest.mark.parametrize(
    "form, said",
    [
        pytest.param("", "is empty", id="empty"),
        pytest.param("step-", 'carries no "{ordinal}"', id="no-slot"),
        pytest.param("{number}-", 'carries no "{ordinal}"', id="a-field-but-no-slot"),
        pytest.param("{ordinal}a", "is not the end of it", id="a-suffix"),
        pytest.param("{ordinal}-{number}", "is not the end of it", id="a-field-after"),
        pytest.param("{ordinal}{ordinal}", "2 times", id="twice"),
        pytest.param("{ordinal", "leaves a brace unclosed", id="unclosed"),
        pytest.param("ordinal}", "leaves a brace unclosed", id="unopened"),
    ],
)
def test_a_form_that_is_not_one_is_refused_by_name(form, said):
    """One complaint per defect, naming ``where`` — the shape
    `pending_errors` has, and for its reason: what the workflow declares is
    graded by the reader that will have to read it again."""
    (complaint,) = subphase.form_errors(form, "states.orchard.sub-phase-name")
    assert complaint.startswith("states.orchard.sub-phase-name")
    assert said in complaint


def test_a_brace_that_is_unclosed_is_one_complaint_and_not_also_a_missing_slot():
    """The `{ordinal` case carries no readable field at all, so the arms below
    it stay quiet: a form the braces do not close has nothing worth grading."""
    assert len(subphase.form_errors("{ordinal", "where")) == 1


@pytest.mark.parametrize(
    "form, head, expected",
    [
        pytest.param(NUMBERED_FORM, {"number": 7}, "7-", id="a-key-the-state-mints"),
        pytest.param(BARE_FORM, {}, "c", id="nothing-but-a-literal"),
        pytest.param("{ordinal}", {}, "", id="the-slot-alone-has-no-prefix"),
        pytest.param(
            "{a}/{b}-{ordinal}", {"a": "x", "b": 2}, "x/2-", id="two-fields"
        ),
    ],
)
def test_the_prefix_is_the_form_with_its_ordinal_taken_off(form, head, expected):
    """What `mint` writes in front of the ordinal and `next_ordinal` strips
    back off — which is why the two live beside each other."""
    assert subphase.prefix(form, head) == expected


def test_the_prefix_and_the_reader_agree_on_what_a_bullet_is_called():
    """The writer-beside-the-reader rule, stated as a round trip: a bullet
    minted under a declared form is found again by the ordinal reader, with no
    separator spelled anywhere but the form."""
    for form, head, first in (
        (NUMBERED_FORM, {"number": 7}, "7-1"),
        (BARE_FORM, {}, "c1"),
    ):
        prefix = subphase.prefix(form, head)
        assert subphase.next_ordinal((), prefix) == 1
        assert subphase.next_ordinal((first,), prefix) == 2


# --- minting: the ordinal ----------------------------------------------------

#: The fixture's pending bullet, as its content after `- `. Fixture words for
#: the heading's reason: nothing here may pass by agreeing with this repo's
#: own `plan.toml`.
PENDING = "**unpruned — Say what the rest of the training is.**"

#: The prefix a section numbered 7 mints under.
PREFIX = "7-"


@pytest.mark.parametrize(
    "names, expected",
    [
        pytest.param((), 1, id="nothing-minted-yet"),
        pytest.param(("7-1",), 2, id="one"),
        pytest.param(("7-1", "7-2", "7-3"), 4, id="three"),
        pytest.param(("7-3", "7-1"), 4, id="out-of-order"),
        pytest.param(("7-1", "7-2a"), 3, id="a-split-contributes-its-integer"),
        pytest.param(("unpruned",), 1, id="a-name-with-no-ordinal-contributes-nothing"),
        pytest.param(("9-4",), 1, id="another-sections-bullet-is-not-ours"),
        pytest.param(("7-1", "unpruned", "9-4"), 2, id="all-three-at-once"),
    ],
)
def test_the_next_ordinal_is_the_leading_integer_after_the_prefix(names, expected):
    """The old tool's rule, and the two things that fall out of it rather than
    needing an arm each: `7-2a` — a sub-phase split while it was planned —
    contributes 2, and a name that is not an ordinal contributes nothing."""
    assert subphase.next_ordinal(names, PREFIX) == expected


def test_the_ordinal_is_not_the_count():
    """Minting from the count would hand out a name the body already carries:
    three bullets where one has been split are four names, and the next free
    ordinal is 4 rather than 5."""
    names = ("7-1", "7-2", "7-2a", "7-3")
    assert len(names) == 4 and subphase.next_ordinal(names, PREFIX) == 4


# --- minting: the three steps ------------------------------------------------


def minted(*lines: str, title=None, last=False) -> str:
    return subphase.mint(
        body(*lines),
        heading=HEADING,
        prefix=PREFIX,
        pending=PENDING,
        title=title,
        last=last,
    )


def test_opening_a_decomposition_writes_the_heading_and_the_pending_bullet():
    """A body that carries neither. The heading is created at `###` — the one
    place the writer picks a depth, and only because the body has none."""
    assert minted("", "Some prose.") == body(
        "", "Some prose.", "", "### Steps", f"- {PENDING}"
    )


def test_opening_leaves_everything_the_body_already_said_alone():
    """Nothing but the heading and the bullet is added: 4-5a writes a body and
    must not rewrite one."""
    prose = ("", "Some prose.", "", "**Done when:**", "- a bullet under prose", "")
    assert minted(*prose).startswith(body(*prose).rstrip("\n").rstrip())


def test_a_minted_bullet_lands_above_the_pending_one_in_the_strict_form():
    assert minted("### Steps", f"- {PENDING}", title="The register") == body(
        "### Steps", "- **7-1 — The register**", f"- {PENDING}"
    )


def test_a_second_mint_takes_the_next_ordinal():
    assert minted(
        "### Steps", "- **7-1 — The register**", f"- {PENDING}", title="Close-out"
    ) == body(
        "### Steps",
        "- **7-1 — The register**",
        "- **7-2 — Close-out**",
        f"- {PENDING}",
    )


def test_last_takes_the_pending_bullet_out():
    assert minted(
        "### Steps", "- **7-1 — The register**", f"- {PENDING}", last=True
    ) == body("### Steps", "- **7-1 — The register**")


def test_last_with_a_title_mints_and_closes_in_one_run():
    assert minted(
        "### Steps", "- **7-1 — The register**", f"- {PENDING}",
        title="Close-out", last=True,
    ) == body("### Steps", "- **7-1 — The register**", "- **7-2 — Close-out**")


def test_minting_into_a_finished_decomposition_re_opens_it():
    """The old tool needed `--reopen` and three refusals around it, because
    the marker was a head key somebody had to clear. Here the third step is
    unconditional and asks nothing about what came before, so the section
    simply is unfinished again — which is true."""
    assert minted("### Steps", "- **7-1 — The register**", title="More") == body(
        "### Steps",
        "- **7-1 — The register**",
        "- **7-2 — More**",
        f"- {PENDING}",
    )


def test_last_on_a_body_with_nothing_pending_changes_nothing():
    """Idempotent, because the rule is about the bullet's presence rather than
    about a flag somebody set: closing a closed decomposition is a no-op."""
    finished = ("### Steps", "- **7-1 — The register**")
    assert minted(*finished, last=True) == body(*finished)


def test_the_existing_heading_is_left_at_whatever_depth_it_carries():
    """The reader matches the heading's text at any depth on purpose, so a
    consumer writing `## Steps` is never rewritten into this repo's nesting."""
    assert minted("## Steps", title="One") == body(
        "## Steps", "- **7-1 — One**", f"- {PENDING}"
    )


def test_a_bullet_joins_the_list_rather_than_the_end_of_the_span():
    """A new sub-phase goes directly after the last one, so a span that ends
    in prose or in the blank lines that close it keeps the list contiguous —
    a bullet written past them would read as a paragraph of its own."""
    assert minted(
        "### Steps", "- **7-1 — One.**", "", "Trailing prose.", "",
        title="Two", last=True,
    ) == body(
        "### Steps", "- **7-1 — One.**", "- **7-2 — Two**", "",
        "Trailing prose.", "",
    )


def test_a_bullet_joins_the_list_after_the_last_ones_continuation():
    """A consumer's defect, 2026-09-13: 231-5 was written under 231-4's first
    line, so 231-4's indented description read as 231-5's. The last bullet is
    the lines `text` says it owns, and the new one goes after all of them —
    ahead of the blank lines that close the span, as before."""
    assert minted(
        "### Steps", "- **7-1 — One**", "  Said at length,", "",
        "  and continued.", f"- {PENDING}", "", "Trailing prose.",
        title="Two",
    ) == body(
        "### Steps", "- **7-1 — One**", "  Said at length,", "",
        "  and continued.", "- **7-2 — Two**", f"- {PENDING}", "",
        "Trailing prose.",
    )


def test_a_fenced_transcript_in_the_last_bullet_stays_with_it():
    """The continuation rule read by the writer too, fence included: a
    column-zero line inside the transcript is not where the bullet ends."""
    last = (
        "### Steps", "- **7-1 — One**", "  What was run:", "  ```",
        "- somebody else's bullet, at column zero", "  ```",
    )
    assert minted(*last, title="Two", last=True) == body(*last, "- **7-2 — Two**")


def test_a_span_with_no_bullets_at_all_takes_one_after_what_is_written():
    """The other arm: nothing to join, so it lands after the last thing the
    span says and ahead of the blank lines that close it."""
    assert minted("### Steps", "Nothing cut up yet.", "", "") == body(
        "### Steps", "Nothing cut up yet.", f"- {PENDING}", "", ""
    )


def test_nothing_after_the_span_is_touched():
    """A heading of any depth closes the span, so what follows one is another
    section of the body and not this capability's business."""
    written = minted(
        "### Steps", f"- {PENDING}", "", "### Done when", "- untouched",
        title="One",
    )
    assert written.endswith(body("### Done when", "- untouched"))


def test_a_minted_bullet_is_counted_and_named_by_the_readers_beside_it():
    """The done line that matters most, at the level where it can be argued
    about: what the writer writes is what the counter counts and the namer
    names, because they are the same strict form in one module."""
    written = minted("### Steps", title="The register")
    assert subphase.count(written, HEADING) == 2
    assert subphase.names(written, HEADING) == ["7-1", "unpruned"]
    assert subphase.errors(written, HEADING) == []
    assert (
        subphase.cursor_errors(
            {"graft": "7-1"}, written, key="graft", heading=HEADING, written=True
        )
        == []
    )


def test_the_pending_bullet_counts_like_any_other():
    """John's decision 2, 2026-09-03: an unfinished decomposition gets no new
    surface. An opened section reads 1 rather than 0, which is what takes it
    out of the started-but-not-decomposed report — the bullet is the signal."""
    assert subphase.count(minted(""), HEADING) == 1


# --- minting: what it refuses ------------------------------------------------


def test_opens_says_whether_a_mint_would_re_open():
    pending = ("### Steps", f"- {PENDING}")
    finished = ("### Steps", "- **7-1 — One.**")
    ask = lambda lines: subphase.opens(body(*lines), heading=HEADING, pending=PENDING)
    assert ask(pending) is False
    assert ask(finished) is True
    assert ask(("no heading at all",)) is True


@pytest.mark.parametrize(
    "title, said",
    [
        pytest.param("", "needs a title", id="empty"),
        pytest.param("   ", "needs a title", id="whitespace"),
        pytest.param("One\ntwo", "carries a newline", id="newline"),
        pytest.param("A **bold** one", 'carries "**"', id="bold"),
    ],
)
def test_a_title_that_would_break_the_strict_form_is_named(title, said):
    (complaint,) = subphase.title_errors(title)
    assert said in complaint


def test_an_ordinary_title_has_nothing_to_say():
    assert subphase.title_errors("The register") == []


@pytest.mark.parametrize(
    "pending, said",
    [
        pytest.param("", "not a named sub-phase", id="empty"),
        pytest.param("Decompose the rest.", "not a named sub-phase", id="unnamed"),
        pytest.param("**   ** and more", "not a named sub-phase", id="empty-bold"),
        pytest.param("**a**\n**b**", "carries a newline", id="newline"),
    ],
)
def test_a_declared_pending_bullet_that_is_not_one_is_named(pending, said):
    """Graded through the reader that has to find it again: what the tool asks
    of the declared sentence is exactly what `_name` asks of a body line."""
    (complaint,) = subphase.pending_errors(pending, "states.orchard.sub-phase-pending")
    assert complaint.startswith("states.orchard.sub-phase-pending")
    assert said in complaint


def test_the_fixtures_own_pending_bullet_parses():
    assert subphase.pending_errors(PENDING, "where") == []


def test_the_state_field_names_are_the_ones_the_declaration_spells():
    """Two copies of a word are safe only where something pins them together;
    `declaration.py` reads these off this module rather than respelling them."""
    assert subphase.PENDING == "sub-phase-pending"
    assert declaration.BULLETED == "bulleted"
    assert declaration.BULLETED in declaration.CAPABILITIES
    assert declaration.BULLETED not in declaration.CAPABILITY_KEYS


# --- marking: reading the bullets -------------------------------------------


MARKED_BODY = body(
    "Prose before it.",
    "",
    "### Steps",
    "- **c1 — The first cutting** **rooted**",
    "- **c2 — The second**",
    "- a bullet with no name",
    f"- {PENDING}",
    "",
    "### Done when",
    "- **c9 — Not under the heading**",
)


def test_bullets_reads_the_named_ones_in_document_order():
    """`names` with what each name is attached to, off the same walk: the
    title is the rest of the bold run and the mark is the second one."""
    assert subphase.bullets(MARKED_BODY, HEADING, pending=PENDING) == [
        subphase.Bullet(
            name="c1", title="The first cutting", mark="rooted", rest="**rooted**"
        ),
        subphase.Bullet(name="c2", title="The second", mark=None, rest=None),
    ]


def test_an_unnamed_bullet_is_absent_and_still_counts():
    """The honest signal, stated as the difference between two numbers: a
    bullet nobody can type is nothing a verb could act on, and pretending it
    is not there at all would make the count disagree with the offer."""
    found = subphase.bullets(MARKED_BODY, HEADING, pending=PENDING)
    assert [one.name for one in found] == ["c1", "c2"]
    assert subphase.count(MARKED_BODY, HEADING) == 4


def test_the_pending_bullet_is_dropped_the_way_the_mint_drops_it():
    """It marks the decomposition as unfinished rather than being work, so a
    run that disposed of it would be marking the marker."""
    assert PENDING.startswith("**unpruned")
    found = subphase.bullets(MARKED_BODY, HEADING, pending=PENDING)
    assert "unpruned" not in [one.name for one in found]
    # And a state that declares none drops nothing, which is what makes it
    # visible again rather than silently gone.
    assert "unpruned" in [
        one.name for one in subphase.bullets(MARKED_BODY, HEADING, pending=None)
    ]


def test_bullets_under_another_heading_are_not_read():
    assert "c9" not in [
        one.name for one in subphase.bullets(MARKED_BODY, HEADING, pending=PENDING)
    ]


def test_a_bare_name_carries_no_title():
    """`_name`'s rule one field over: a value nobody could read is not one."""
    (one,) = subphase.bullets(body("### Steps", "- **c1**"), HEADING, pending=None)
    assert one == subphase.Bullet(name="c1", title=None, mark=None, rest=None)


def test_rest_reads_what_the_line_carries_past_the_name_and_nothing_for_a_bare_one():
    """The fact a disposition gates on: `mark` appends at the end of the line
    and `MARKED` is anchored, so the two agree only where there is nothing
    out here. Whitespace is nothing, since a mark still lands readably."""
    bare, prose, spaced = subphase.bullets(
        body(
            "### Steps",
            "- **c1 — A bare bold run.**",
            "- **c2 — A finding.** with prose after it",
            "- **c3 — Trailing space.**   ",
        ),
        HEADING,
        pending=None,
    )
    assert bare.rest is None
    assert prose.rest == "with prose after it"
    assert spaced.rest is None


def test_a_marked_bullets_rest_is_its_own_mark_run():
    """What the refusal order rests on: a disposition asks "already marked?"
    before "markable?", because every marked bullet answers this one too."""
    (one,) = subphase.bullets(
        body("### Steps", "- **c1 — The first cutting** **rooted**"),
        HEADING,
        pending=None,
    )
    assert (one.mark, one.rest) == ("rooted", "**rooted**")


def test_a_body_with_no_such_heading_carries_no_bullets():
    assert subphase.bullets(body("- **c1 — Loose**"), HEADING, pending=None) == []


# --- one bullet's own lines --------------------------------------------------
#
# `bullets` says which bullets a body carries; `text` says what one of them
# *is*. The rule it keeps is `_numbered_span`'s read the other way round —
# that reader says which lines count, this one says which lines belong — and
# the fence rule is the whole reason it exists: a carrier's finding quotes a
# transcript, and a transcript comes back whole or it comes back wrong.


def test_a_one_line_bullet_is_its_own_line_and_nothing_else():
    """The shape this repo's own carrier has today."""
    assert subphase.text(MARKED_BODY, HEADING, name="c2") == "- **c2 — The second**"


CONTINUED = body(
    "### Steps",
    "- **c1 — The first**",
    "  Said at more length,",
    "",
    "  over an indented continuation.",
    "- **c2 — The second**",
    "",
    "### Done when",
    "- **c9 — Elsewhere**",
)


def test_an_indented_continuation_comes_back_verbatim():
    """Indentation and the blank line inside it, exactly as written: what a
    person reads is the file, so anything reflowed here would be a second
    rendering of a document the tool does not own."""
    assert subphase.text(CONTINUED, HEADING, name="c1") == "\n".join(
        (
            "- **c1 — The first**",
            "  Said at more length,",
            "",
            "  over an indented continuation.",
        )
    )


TRANSCRIPT = body(
    "### Steps",
    "- **c1 — The first**",
    "  What was run:",
    "",
    "  ```",
    "  $ fileplan list",
    "- this is somebody else's bullet, at column zero",
    "",
    "### Nor is this a heading",
    "  ```",
    "  and a last word after it.",
    "- **c2 — The second**",
)


def test_a_fenced_transcript_comes_back_whole():
    """**The case this exists for.** A consumer's finding quotes what it saw, and
    a transcript carries column-zero lines that are somebody else's document
    — a bullet, a heading, a blank line. None of them ends the continuation,
    because a fenced line is not a line at all (`subphase.FENCE`). This
    is 11-1's mask read the other way round."""
    found = subphase.text(TRANSCRIPT, HEADING, name="c1")
    assert found is not None
    assert found.startswith("- **c1 — The first**")
    assert found.endswith("  and a last word after it.")
    assert "- this is somebody else's bullet, at column zero" in found
    assert "### Nor is this a heading" in found
    assert "c2" not in found


def test_the_continuation_stops_at_the_next_bullet():
    assert "c2" not in (subphase.text(CONTINUED, HEADING, name="c1") or "")


def test_the_continuation_stops_at_the_next_heading():
    """The span's own end, and the reason a sub-phase is a bullet rather than
    a heading: a heading of any depth closes what it follows."""
    found = subphase.text(CONTINUED, HEADING, name="c2")
    assert found == "- **c2 — The second**"


def test_trailing_blank_lines_are_trimmed():
    """Blank lines *inside* are kept — they are the paragraph breaks a person
    wrote — and the ones at the end are the gap before the next bullet rather
    than anything this bullet says."""
    text = body("### Steps", "- **c1 — The first**", "  Said.", "", "", "### Done when")
    assert subphase.text(text, HEADING, name="c1") == "- **c1 — The first**\n  Said."


def test_a_name_the_body_does_not_carry_has_no_text():
    assert subphase.text(MARKED_BODY, HEADING, name="c9") is None
    assert subphase.text(MARKED_BODY, HEADING, name="nothing") is None


def test_text_is_total_and_ungated():
    """It reads `_counted` rather than `bullets`, so it will hand back the
    pending marker's own line. That is deliberate: the gate belongs to the
    caller, and it is the same gate a disposition uses — which is what makes
    the two refusals identical for free rather than by agreement. A gate here
    would give the caller two."""
    assert subphase.text(MARKED_BODY, HEADING, name="unpruned") == f"- {PENDING}"
    assert "unpruned" not in [
        one.name for one in subphase.bullets(MARKED_BODY, HEADING, pending=PENDING)
    ]


# --- one home for "carries no such bullet" ----------------------------------


def test_unknown_names_the_value_and_the_names_the_body_carries():
    """`cursor_errors`' message shape, whose docstring already said so — now
    one function rather than two spellings, because `show` needs it byte for
    byte (`docs/method.md#marking`)."""
    carried = subphase.bullets(MARKED_BODY, HEADING, pending=PENDING)
    said = subphase.unknown("propagator/a-batch.md", "c9", carried, HEADING)
    assert said == (
        'propagator/a-batch.md carries no "c9", and the names it carries are c1, c2'
    )


def test_unknown_over_a_body_carrying_none_says_so_rather_than_naming_nothing():
    said = subphase.unknown("propagator/a-batch.md", "c1", [], HEADING)
    assert said == (
        'propagator/a-batch.md carries no "c1", and it carries no named bullet '
        f'at all under "{HEADING}"'
    )


# --- marking: writing one line ----------------------------------------------


def test_the_mark_is_a_second_bold_run_at_the_end_of_the_line():
    written = subphase.mark(MARKED_BODY, heading=HEADING, name="c2", word="potted")
    assert "- **c2 — The second** **potted**" in written


def test_marking_changes_one_line_and_leaves_every_other_byte_alone():
    """The whole of what a disposition may do to a file: not the heading, not
    the bullets either side, not the prose above or the span below."""
    written = subphase.mark(MARKED_BODY, heading=HEADING, name="c2", word="potted")
    before, after = MARKED_BODY.splitlines(), written.splitlines()
    assert len(before) == len(after)
    differing = [n for n, (one, two) in enumerate(zip(before, after)) if one != two]
    assert [before[n] for n in differing] == ["- **c2 — The second**"]


def test_a_mark_reads_back_through_the_reader_that_wrote_it():
    """The property that keeps the writer and the reader one rule: what `mark`
    writes is what `bullets` finds, rather than a form a test agreed with."""
    written = subphase.mark(MARKED_BODY, heading=HEADING, name="c2", word="potted")
    found = {one.name: one.mark for one in subphase.bullets(written, HEADING, pending=PENDING)}
    assert found == {"c1": "rooted", "c2": "potted"}


def test_a_mark_reads_back_exactly_where_rest_says_it_will():
    """The property one field over, and the one the refusal is derived from:
    a bullet whose `rest` is `None` reads its new mark back, and one whose
    `rest` is not does not. Writer and reader stay one rule."""
    written = body(
        "### Steps",
        "- **c1 — A bare bold run.**",
        "- **c2 — A finding.** with prose after it",
    )
    for one in subphase.bullets(written, HEADING, pending=None):
        marked = subphase.mark(written, heading=HEADING, name=one.name, word="potted")
        (back,) = [
            found
            for found in subphase.bullets(marked, HEADING, pending=None)
            if found.name == one.name
        ]
        assert (back.mark == "potted") is (one.rest is None)


def test_marking_a_name_the_body_does_not_carry_writes_nothing():
    """Total over any string, like everything else here: the caller resolves
    the name and refuses, so this cannot be the one to guess."""
    assert subphase.mark(MARKED_BODY, heading=HEADING, name="c7", word="potted") == MARKED_BODY
    assert subphase.mark(MARKED_BODY, heading="Nowhere", name="c2", word="potted") == MARKED_BODY


def test_marking_touches_the_first_matching_bullet_only():
    """Two bullets sharing a name is a body the mint cannot produce, and
    marking both would be one run disposing of two findings."""
    written = subphase.mark(
        body("### Steps", "- **c1 — One**", "- **c1 — Again**"),
        heading=HEADING,
        name="c1",
        word="potted",
    )
    assert written == body("### Steps", "- **c1 — One** **potted**", "- **c1 — Again**")


# --- marking: what a declared word may not be -------------------------------


@pytest.mark.parametrize(
    "word, said",
    [
        pytest.param("", "is empty", id="empty"),
        pytest.param("   ", "is empty", id="whitespace"),
        pytest.param("root\ned", "carries a newline", id="newline"),
        pytest.param("**rooted**", 'carries "**"', id="bold"),
    ],
)
def test_a_declared_mark_that_could_not_be_written_is_named(word, said):
    """`title_errors`' three cases, for its reason: each is a way the strict
    form the writer exists to write would come out unreadable."""
    (complaint,) = subphase.mark_errors(word, "transitions.pot-on.marks")
    assert complaint.startswith("transitions.pot-on.marks")
    assert said in complaint


def test_an_ordinary_word_is_no_complaint():
    assert subphase.mark_errors("rooted", "where") == []


# --- marking: the note that rides beside the word ---------------------------


def test_a_note_is_written_outside_the_bold_run_the_mark_is_read_from():
    """What the whole change rests on: the word stays the second bold run and
    the note is prose after it, so the reader is untouched."""
    written = subphase.mark(
        MARKED_BODY, heading=HEADING, name="c2", word="potted", note="Roots to the wall."
    )
    assert "- **c2 — The second** **potted** Roots to the wall." in written
    found = {one.name: one.mark for one in subphase.bullets(written, HEADING, pending=PENDING)}
    assert found == {"c1": "rooted", "c2": "potted"}


def test_no_note_writes_what_it_always_wrote():
    """The parameter defaults, so every existing caller is untouched — and
    what it writes is byte-identical to the run before it existed."""
    assert subphase.mark(
        MARKED_BODY, heading=HEADING, name="c2", word="potted", note=None
    ) == subphase.mark(MARKED_BODY, heading=HEADING, name="c2", word="potted")


def test_a_note_spelling_the_mark_word_changes_nothing_the_reader_reads():
    """The mark is the **second bold run**, and prose after it is prose. A
    note is the operator's sentence, so it may say any word at all."""
    written = subphase.mark(
        MARKED_BODY,
        heading=HEADING,
        name="c2",
        word="potted",
        note="not rooted, and never potted",
    )
    (found,) = [
        one for one in subphase.bullets(written, HEADING, pending=PENDING) if one.name == "c2"
    ]
    assert found.mark == "potted"
    assert found.title == "The second"


@pytest.mark.parametrize(
    "note, said",
    [
        pytest.param("", "with nothing in it", id="empty"),
        pytest.param("   ", "with nothing in it", id="whitespace"),
        pytest.param("costs\nmore", "carries a newline", id="newline"),
        pytest.param("it is **not** worth it", 'carries "**"', id="bold"),
    ],
)
def test_a_note_that_may_not_ride_on_a_bullet_is_named(note, said):
    """`title_errors`' three cases, one function over: a note is the
    operator's text, so it is graded at the run the way a title is."""
    (complaint,) = subphase.note_errors(note)
    assert said in complaint


def test_an_ordinary_note_is_no_complaint():
    assert subphase.note_errors("Nobody has measured it.") == []


def test_a_note_carrying_a_newline_mints_a_bullet_nobody_wrote():
    """**The measurement, pinned.** This is why the newline refuses, and it is
    not a matter of taste: the second line is a counted, *named* bullet the
    carrier's register now has to live with. `count` moves, `names` gains a
    finding nobody wrote, and `next_ordinal` jumps past it — 11-1's class of
    bug, punching a permanent hole in a register.

    The `**` case beside it is the ownership rule instead, and this test says
    nothing about it, because there is nothing here to measure."""
    smuggled = subphase.mark(
        body("### Steps", "- **f1 — One**", "- **f2 — Two**", "- **f3 — Three**"),
        heading=HEADING,
        name="f1",
        word="dismissed",
        note="costs more\n- **f9 — smuggled**",
    )
    assert subphase.count(smuggled, HEADING) == 4
    assert subphase.names(smuggled, HEADING) == ["f1", "f9", "f2", "f3"]
    assert subphase.next_ordinal(subphase.names(smuggled, HEADING), "f") == 10


# --- fences ------------------------------------------------------------------

FENCED = body(
    "### Steps",
    "- **f1 — The first finding.**",
    "",
    "```",
    "$ pysmelly src/",
    "- **f9 — A finding quoted as evidence.**",
    "```",
    "",
    "- **f2 — The second finding.**",
)


def test_a_bullet_inside_a_fence_is_not_a_sub_phase():
    """A carrier quotes transcripts in its own body, and a transcript holding
    a bullet-shaped line is evidence rather than work."""
    assert subphase.count(FENCED, HEADING) == 2
    assert subphase.names(FENCED, HEADING) == ["f1", "f2"]


def test_a_fenced_bullet_does_not_move_the_next_ordinal():
    """`next_ordinal` takes the maximum and adds one, so a quoted ordinal
    would punch a permanent hole in the register a carrier mints from."""
    assert subphase.next_ordinal(subphase.names(FENCED, HEADING), "f") == 3


def test_a_fenced_bullet_carries_no_title_and_no_mark():
    assert [one.name for one in subphase.bullets(FENCED, HEADING, pending=PENDING)] == [
        "f1",
        "f2",
    ]


def test_a_malformed_bullet_inside_a_fence_is_not_complained_about():
    """The complaint is about bullets, and a fenced line is not one — a
    transcript of somebody else's list is not this body's defect."""
    assert subphase.errors(FENCED, HEADING) == []
    assert (
        subphase.errors(
            body("### Steps", "- **f1 — One.**", "```", "+ a quoted list", "```"),
            HEADING,
        )
        == []
    )


def test_a_fenced_copy_of_the_declared_heading_is_not_a_heading():
    """`declaration.heading_slugs` already reads a heading inside a fence as
    not a heading; this is that same rule reaching the second reader."""
    quoted = body(
        "### Steps",
        "- **f1 — One.**",
        "```",
        "### Steps",
        "- **f9 — Quoted.**",
        "```",
        "- **f2 — Two.**",
    )
    assert subphase.errors(quoted, HEADING) == []
    assert subphase.count(quoted, HEADING) == 2


def test_a_fenced_heading_does_not_close_the_span():
    """A shell transcript's `# comment` lines are heading-shaped, and a span
    that ended at one would silently read short."""
    transcript = body(
        "### Steps",
        "- **f1 — One.**",
        "```",
        "# tidy up first",
        "$ uv run pytest",
        "```",
        "- **f2 — Two.**",
    )
    assert subphase.count(transcript, HEADING) == 2


def test_a_tilde_fence_is_a_fence_too():
    tilde = body("### Steps", "- **f1 — One.**", "~~~", "- **f9 — Quoted.**", "~~~")
    assert subphase.names(tilde, HEADING) == ["f1"]


def test_an_indented_fence_is_a_fence_too():
    """Section 10's own body carries 2-space-indented fenced controls, so a
    column-zero-only rule would miss the realistic shape in this very tree."""
    indented = body(
        "### Steps",
        "- **f1 — One.**",
        "  ```",
        "- **f9 — Quoted.**",
        "  ```",
        "- **f2 — Two.**",
    )
    assert subphase.names(indented, HEADING) == ["f1", "f2"]


def test_an_unclosed_fence_in_the_span_refuses_by_name():
    """The polarity a forgotten backtick fails loud in: the mask would hide
    every line after it and the section would quietly read short."""
    (said,) = subphase.errors(
        body("### Steps", "- **f1 — One.**", "```", "- **f9 — Quoted.**"),
        HEADING,
    )
    assert "body line 3" in said
    assert "fence" in said


def test_a_closed_fence_is_no_complaint():
    assert subphase.errors(FENCED, HEADING) == []


def test_marking_a_name_that_appears_only_inside_a_fence_writes_nothing():
    """A disposition that edited quoted evidence would rewrite the frozen
    measurement a carrier exists to keep verbatim."""
    assert subphase.mark(FENCED, heading=HEADING, name="f9", word="fixed") == FENCED


def test_a_fenced_pending_marker_does_not_close_a_decomposition():
    """`opens` reads the marker by the same rule the readers read a bullet."""
    marker = body("### Steps", "- **f1 — One.**", "```", f"- {PENDING}", "```")
    assert subphase.opens(marker, heading=HEADING, pending=PENDING) is True


def test_a_mint_preserves_a_fenced_block_byte_for_byte():
    """The one way to get this change catastrophically wrong: a mask that
    became a filtered list would delete every transcript in the span."""
    written = subphase.mint(
        FENCED, heading=HEADING, prefix="f", pending=PENDING, title="A third."
    )
    assert "$ pysmelly src/" in written
    assert "- **f9 — A finding quoted as evidence.**" in written
    assert "- **f3 — A third.**" in written
    assert written.splitlines()[2:7] == FENCED.splitlines()[2:7]


def test_a_mint_leaves_a_fenced_pending_marker_in_the_body():
    """The pending-bullet filter is fence-aware too, so the quoted marker is
    evidence rather than this body's own unfinished decomposition. The fence
    is f1's continuation by `text`'s rule, so f2 lands after it."""
    quoted = body("### Steps", "- **f1 — One.**", "```", f"- {PENDING}", "```")
    written = subphase.mint(
        quoted, heading=HEADING, prefix="f", pending=PENDING, title="Two.", last=True
    )
    assert written.splitlines() == [
        "### Steps",
        "- **f1 — One.**",
        "```",
        f"- {PENDING}",
        "```",
        "- **f2 — Two.**",
    ]


# --- minting: what a reader reads back ---------------------------------------

#: Every body shape the module builds, plus the ones a consumer writes that
#: this repo's own one-line carrier never did. Indexed by what each is for.
SHAPES = {
    "named": NAMED_BODY,
    "marked": MARKED_BODY,
    "continued": CONTINUED,
    "transcript": TRANSCRIPT,
    "fenced": FENCED,
    "described-last": body(
        "### Steps",
        "- **7-1 — One**",
        "- **7-2 — Two, described**",
        "  One helper answering the question,",
        "  and the done line under it.",
        f"- {PENDING}",
    ),
    "column-zero-fence-last": body(
        "### Steps", "- **7-1 — One.**", "```", "- quoted", "### quoted", "```"
    ),
    "described-then-prose": body(
        "### Steps", "- **7-1 — One**", "  Said.", "", "", "Trailing prose.", "",
        "### Done when", "- untouched",
    ),
}


@pytest.mark.parametrize("last", [False, True], ids=["open", "last"])
@pytest.mark.parametrize("shape", SHAPES.values(), ids=SHAPES.keys())
def test_a_mint_changes_no_bullet_a_reader_already_reads(shape, last):
    """What a consumer's 231-5 broke, stated for every shape rather than one:
    minting adds a bullet and takes the pending one out, and every other
    bullet's `text` comes back exactly as it did. The new bullet owns its own
    line and nothing else, so it cannot have taken a neighbour's description.

    `count` and `names` agreeing was never enough: the defect kept both right
    and moved four lines of prose from one bullet to the next."""
    before = {
        one.name: subphase.text(shape, HEADING, name=one.name)
        for one in subphase.bullets(shape, HEADING, pending=PENDING)
    }
    written = subphase.mint(
        shape, heading=HEADING, prefix=PREFIX, pending=PENDING, title="New", last=last
    )
    after = {
        one.name: subphase.text(written, HEADING, name=one.name)
        for one in subphase.bullets(written, HEADING, pending=PENDING)
    }
    (new,) = set(after) - set(before)
    assert after.pop(new) == f"- **{new} — New**"
    assert after == before
    assert subphase.errors(written, HEADING) == []
