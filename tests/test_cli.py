"""The CLI: a subcommand per declared transition, the TOC, and the contract.

The group is built inside `main`, so a malformed ``plan.toml`` is
catchable in-process and only the operator's contract — rc 2, one ``ERROR:``
line on stderr, no traceback, no stdout — needs a subprocess. That is the
whole reason 1-1 built it there.

Everything drives the *fixture's* vocabulary. The control at the bottom is
the one that matters most in this sub-phase: no verb the repo declares
appears under ``src/`` at all, because there is no per-verb code to name it.
"""

from __future__ import annotations

import ast
import datetime as dt
import io
import json
import os
import re
import socket
import subprocess
import sys
import tokenize
from pathlib import Path

import click
import pytest
from dulwich.repo import Repo

from conftest import DERIVABLE_KEYS, FIXTURE_FILES

from fileplan import claim, render, subphase
from fileplan.cli import (
    CHECK,
    FILING,
    INTO,
    MINTING,
    NOTE,
    PLACEMENT,
    RECORD,
    SEEDING,
    main,
)
from fileplan.declaration import load
from fileplan.item import read as item_read

#: The tool's own option words, built here from the constants that spell
#: them. It is a **test**'s roster rather than the tool's: nothing under
#: `src/` reads it, so it is assembled where its only reader is.
RESERVED_OPTIONS = (
    CHECK,
    NOTE,
    RECORD,
    INTO,
    SEEDING,
    *(flag for flag, *_ in PLACEMENT),
    *(flag for flag, *_ in MINTING),
    *(flag for flag, *_ in FILING),
)

# Sibling test modules, not a package: `tests/` is on `sys.path` at
# collection. Imported so that what a citation looks like, and what a pid
# that is honestly dead is, each have one home rather than a copy in every
# test that needs them.
from test_claim import TAKEN, exited
from test_docs import CITATION

FIXTURES = Path(__file__).resolve().parent / "fixtures"
REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A tree the CLI discovers the way an operator's would: cwd plus the
    environment override, both pointed at a copy of the fixture."""
    for name in FIXTURE_FILES:
        (tmp_path / name).write_text((FIXTURES / name).read_text())
    for state in load(tmp_path / "plan.toml").states.values():
        (tmp_path / state.path).mkdir(parents=True)
    monkeypatch.setenv("FILEPLAN_PLAN_TOML", str(tmp_path / "plan.toml"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


# --------------------------------------------------------------------------
# Registration: every transition is a subcommand, in declared order
# --------------------------------------------------------------------------


def test_every_declared_transition_registers_as_a_subcommand(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--help"]) == 0
    out = capsys.readouterr().out
    for name in load(tree / "plan.toml").transitions:
        assert name in out


def test_help_lists_transitions_in_toml_order_not_alphabetically(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`plan.toml` declares `transplant` before `sprout` on purpose: document
    order is not alphabetical order, which is what makes this mean something.
    The workflow's order is the sequence work moves through."""
    main(["--help"])
    out = capsys.readouterr().out
    assert out.index("transplant") < out.index("sprout")


def test_each_subcommand_carries_its_declared_help(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["--help"])
    out = capsys.readouterr().out
    for transition in load(tree / "plan.toml").transitions.values():
        assert transition.help in out


def test_a_transitions_set_keys_become_its_options(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["sprout", "--help"])
    out = capsys.readouterr().out
    assert "--cultivar" in out
    # A key with declared `values` becomes a click.Choice.
    assert "heirloom" in out and "hybrid" in out
    assert "Which cultivar the seedling is." in out


def test_a_moving_transition_takes_the_handle_and_no_body(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["transplant", "--help"])
    out = capsys.readouterr().out
    assert "ITEM" in out
    assert "--body" not in out
    assert "--rootstock" in out


def test_the_read_takes_three_filters_and_no_option_named_after_a_key(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The 13-3 cut, as the guard the old one was read the other way round.
    `list` is not a declared transition — it moves nothing and takes no lock —
    and its whole filter vocabulary is three words. A key is something `--has`
    *names*, so no key's name is an option, and no key's name is written in
    the CLI either way."""
    assert main(["list", "--help"]) == 0
    out = capsys.readouterr().out
    assert "--state" in out and "--json" in out
    assert "--has" in out and "--lacks" in out
    declared = load(tree / "plan.toml")
    options = re.findall(r"^\s+(--[a-z-]+)", out, re.MULTILINE)
    assert sorted(options) == ["--has", "--help", "--json", "--lacks", "--state"]
    # click wraps the roster and hyphenates where it breaks, so the line ends
    # are joined back up before a key name is looked for.
    roster = re.sub(r"-\n\s+", "-", out)
    for name in declared.carried:
        assert name in roster


def places(capsys: pytest.CaptureFixture[str], verb: str) -> int:
    """How many of the three order options ``verb`` carries."""
    capsys.readouterr()
    assert main([verb, "--help"]) == 0
    out = capsys.readouterr().out
    return sum(one in out for one in ("--above", "--below", "--at"))


def test_a_transition_arriving_in_a_queued_state_carries_the_placement_options(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The first arm. Generated by the capability, exactly as a transition's
    `sets` keys become its `--options`: `transplant` moves into `orchard`,
    which is the fixture's `queued` state, so the tree arrives with no place
    and the run gives it one."""
    assert main(["transplant", "--help"]) == 0
    out = capsys.readouterr().out
    assert "--above" in out and "--below" in out and "--at" in out
    assert "ITEM" in out and "N" in out


def test_a_same_state_verb_that_only_places_carries_them_too(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The second arm, and the only shape that needs one: `respace` stays in
    `orchard` and writes nothing else, so where the tree goes in the row is
    the whole of what it has to say."""
    assert places(capsys, "respace") == 3


def test_a_same_state_verb_that_writes_something_else_carries_none(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**The 13-3 cut.** Before it, every verb whose destination state was
    ordered took all three, whether or not moving was what the verb was for —
    so a verb that marks a bullet took three options about the item's place.
    A cursor, a mint and a mark, each in `orchard`."""
    assert places(capsys, "graft-on") == 0
    assert places(capsys, "espalier") == 0
    assert places(capsys, "ripen") == 0
    assert places(capsys, "thin") == 0


def test_a_transition_into_a_plain_state_carries_none_of_them(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`harvest` moves *out* of the orchard, into `cold-frame`. Nothing about
    the source state puts an option on a verb — it is where the item lands
    that gives it a place."""
    assert places(capsys, "harvest") == 0


def test_a_verb_that_loses_an_option_says_so_rather_than_ignoring_it(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Why the cut can be derived rather than declared: a consumer whose verb
    took `--at` yesterday gets click's own refusal at rc 2, not a run that
    quietly places nothing: the polarity that fails loud."""
    orchard(tree, "First tree")
    capsys.readouterr()
    assert main(["ripen", "first-tree", "1-1", "--at", "50"]) == 2
    assert "No such option" in capsys.readouterr().err


def test_a_sets_key_colliding_with_a_placement_option_refuses_by_name(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The `--body` precedent, unchanged: one option cannot mean two things.
    The declaration is otherwise well formed — the key is declared and its doc
    heading added — so this refusal is the only reason it could fail."""
    plan = (tree / "plan.toml").read_text().replace(
        'sets     = ["rootstock", "pest"]', 'sets     = ["rootstock", "above"]'
    )
    (tree / "plan.toml").write_text(plan + '\n[keys.above]\ndoc = "method.md#above"\n')
    (tree / "method.md").write_text((tree / "method.md").read_text() + "\n## above\n")
    assert main(["--help"]) == 2
    err = capsys.readouterr().err
    assert 'transitions.transplant.sets names "above"' in err
    assert "One option cannot mean two things" in err


def test_a_declared_transition_named_list_refuses_by_name(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The way a creating transition whose `sets` names `body` refuses: one
    command cannot mean two things. The declaration is otherwise well formed —
    the `doc` heading is added too — so this refusal is the only reason it
    could fail."""
    plan = (tree / "plan.toml").read_text()
    (tree / "plan.toml").write_text(
        plan.replace("[transitions.sprout]", "[transitions.list]")
    )
    (tree / "method.md").write_text(
        (tree / "method.md").read_text() + "\n## list\n"
    )
    assert main(["--help"]) == 2
    assert "transitions.list takes the name of the read" in capsys.readouterr().err


# --------------------------------------------------------------------------
# A list-valued key: the option that repeats
# --------------------------------------------------------------------------
#
# The fixture's `pest` is closed *and* list-valued, which is the pair worth
# driving through the CLI: `values` grades each occurrence and `list-valued`
# says how many of them the head carries.


def pested(tree: Path, *pests: str) -> dict:
    """A seedling transplanted with the pests given, and its head read back."""
    assert main(["sprout", "A seedling", "--body", "P.", "--cultivar", "heirloom"]) == 0
    given = [word for pest in pests for word in ("--pest", pest)]
    assert main(["transplant", "a-seedling", *given]) == 0
    declaration = load(tree / "plan.toml")
    path = tree / declaration.states["orchard"].path / "a-seedling.md"
    return dict(item_read(path, declaration).head)


def test_an_option_given_twice_writes_both_values_as_a_list(tree: Path) -> None:
    """The whole point of the field: one run, two occurrences, one TOML list
    that the head reader reads back as the two values it holds."""
    assert pested(tree, "aphid", "canker")["pest"] == ["aphid", "canker"]


def test_one_occurrence_writes_a_list_of_one(tree: Path) -> None:
    """Not a bare string. The shape a key holds is the declaration's answer
    rather than the run's, so a filter or a `refuses` reads the same head
    whether one pest was found or three."""
    assert pested(tree, "aphid")["pest"] == ["aphid"]


def test_the_option_not_given_writes_no_key_at_all(tree: Path) -> None:
    """Click hands back an empty tuple rather than `None` for an option that
    repeats, so without the normalisation this would write `pest = []` — a key
    the item does not carry, spelled as one it does."""
    assert "pest" not in pested(tree)


def test_the_help_says_the_option_repeats(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Click renders no repeat marker of its own, so `--pest [aphid|canker|
    scab]` would read exactly like a scalar. The `...` is ours, and the
    second half of this test is what keeps the `[a|b]` before it from
    drifting: it is click's own rendering of the same `Choice`, and this
    builds a scalar option over that `Choice` to say so."""
    assert main(["transplant", "--help"]) == 0
    out = capsys.readouterr().out
    assert "[aphid|canker|scab]..." in out

    values = load(tree / "plan.toml").keys["pest"].values
    scalar = click.Option(["--pest", "pest"], type=click.Choice(values))
    context = click.Context(click.Command("transplant"))
    rendered, _ = scalar.get_help_record(context)
    assert f"{rendered}..." in out


def test_a_refused_entry_stops_the_next_verb_and_names_it(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """End to end, and the reason D4 is in this sub-phase: `harvest` refuses
    canker, and before this a list-valued head matched nothing — the rule read
    like it was running and never fired."""
    pested(tree, "aphid", "canker")
    capsys.readouterr()
    assert main(["harvest", "a-seedling"]) == 2
    assert 'harvest refuses pest = "canker"' in capsys.readouterr().err


def test_a_list_head_carrying_nothing_refused_is_taken(tree: Path) -> None:
    pested(tree, "aphid")
    assert main(["harvest", "a-seedling"]) == 0


# --------------------------------------------------------------------------
# The read: one traversal, two renderings
# --------------------------------------------------------------------------


def filed(tree: Path) -> None:
    """Two items in two states, one carrying a key the other does not."""
    assert main(["sprout", "A seedling", "--body", "Prose.", "--cultivar", "heirloom"]) == 0
    assert main(["sprout", "Another seedling", "--body", "More prose."]) == 0
    assert main(["transplant", "a-seedling", "--rootstock", "M26"]) == 0


def test_a_word_in_a_title_finds_the_item_ignoring_case(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--has title=review` is an exact match, so a session piped `list`
    through grep. `~` is a substring, any case, over any text key."""
    filed(tree)
    capsys.readouterr()
    assert main(["list", "--has", "title~ANOTHER", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [row["slug"] for row in payload["rows"]] == ["another-seedling"]
    assert main(["list", "--has", "title~seed", "--json"]) == 0
    assert len(json.loads(capsys.readouterr().out)["rows"]) == 2


def test_a_word_search_over_a_key_with_declared_values_refuses(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Declared values compare by order, so a substring over them is the
    wrong question, and the refusal names the right ones."""
    filed(tree)
    capsys.readouterr()
    assert main(["list", "--has", "cultivar~heir"]) == 2
    err = capsys.readouterr().err
    assert err.startswith('ERROR: --has asks "cultivar~heir"')
    assert "compare by order" in err


def test_a_hand_edited_value_its_key_does_not_declare_is_named(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A value is graded when a verb writes it and never again. The default
    read names one written by hand, in both renderings, and still lists
    everything: it gates nothing."""
    filed(tree)
    path = tree / "orchard" / "a-seedling.md"
    path.write_text(
        path.read_text().replace('cultivar = "heirloom"', 'cultivar = "XXL"'),
        encoding="utf-8",
    )
    capsys.readouterr()

    assert main(["list"]) == 0
    printed = capsys.readouterr()
    assert "a-seedling" in printed.out and "another-seedling" in printed.out
    assert (
        'undeclared value: a-seedling carries "XXL" in cultivar, which its '
        "values do not declare (orchard/a-seedling.md)"
    ) in printed.err

    assert main(["list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["undeclared"] == [
        {
            "slug": "a-seedling",
            "key": "cultivar",
            "value": "XXL",
            "path": "orchard/a-seedling.md",
        }
    ]


def test_the_listing_prints_a_record_per_item(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    filed(tree)
    capsys.readouterr()
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert "a-seedling" in out and "another-seedling" in out
    assert "  title" in out


def test_text_and_json_are_two_renderings_of_one_traversal(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**The control.** The JSON rows are rendered through the *text*
    renderer and compared against what the text run actually printed. A second
    traversal beside the first would pass every other test in this file and
    fail this one — which is exactly what happened in the old tool before its
    § 9, when every listing interpolated its own text inside the loop that
    found the data."""
    filed(tree)
    capsys.readouterr()

    main(["list"])
    printed = capsys.readouterr().out.splitlines()

    main(["list", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert render.records(payload["rows"]) == printed


def test_the_control_holds_through_a_filter(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Filtering must narrow the *rows*, not one rendering of them."""
    filed(tree)
    capsys.readouterr()

    main(["list", "--state", "orchard"])
    printed = capsys.readouterr().out.splitlines()

    main(["list", "--state", "orchard", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert render.records(payload["rows"]) == printed
    assert [row["slug"] for row in payload["rows"]] == ["a-seedling"]


def test_a_state_is_listed_by_its_declared_name_not_its_path(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**One spelling per state**, end to end. `cold-frame` lives in
    `beds/hardening-off`, so a listing that read the directory for itself
    would say the wrong word here."""
    (tree / "beds" / "hardening-off" / "a-seedling.md").write_text(
        '+++\ntitle = "A seedling"\n+++\n\nProse.\n'
    )
    assert main(["list", "--json"]) == 0
    (row,) = json.loads(capsys.readouterr().out)["rows"]
    assert row["state"] == "cold-frame"
    assert row["path"] == "beds/hardening-off/a-seedling.md"


def test_the_counts_line_goes_to_stderr_never_stdout(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`fileplan list | ...` carries the records and nothing else."""
    filed(tree)
    capsys.readouterr()
    assert main(["list", "--state", "orchard"]) == 0
    captured = capsys.readouterr()
    assert "1 of 2 items" in captured.err
    assert "items" not in captured.out


def test_stderr_is_silent_under_json(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Which is why the counts moved into the envelope: a consumer parses one
    thing, and there is no second frame to strip."""
    filed(tree)
    capsys.readouterr()
    assert main(["list", "--json"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["matched"] == 2 and payload["read"] == 2


def test_a_refusal_emits_no_json(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """1-1's deferred assertion, assertable now that `--json` exists. A
    consumer must never get a parseable document describing a run that did not
    happen — rc 2, `ERROR:` on stderr, and stdout empty."""
    (tree / "plan.toml").write_text("[states.greenhouse]\npath = 3\n")
    assert main(["list", "--json"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("ERROR: ")
    assert "{" not in captured.err  # not even as a fragment on the error stream


def test_a_broken_item_file_refuses_the_listing_with_no_json(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Every `*.md` in a state directory is claimed to be an item, so one that
    is not refuses rather than being skipped — including under `--json`."""
    (tree / "greenhouse" / "README.md").write_text("# What goes in here\n")
    assert main(["list", "--json"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "README.md" in captured.err


def test_an_empty_tree_lists_nothing_and_still_succeeds(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["list"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "0 of 0 items" in captured.err


def test_a_filter_value_may_carry_a_comparison(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--has 'cultivar>=hybrid'` orders by the key's declared `values`, which
    is the only reason `>=` means anything here."""
    filed(tree)
    capsys.readouterr()
    assert main(["list", "--has", "cultivar>=hybrid", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["rows"] == []
    assert main(["list", "--has", "cultivar<=heirloom", "--json"]) == 0
    (row,) = json.loads(capsys.readouterr().out)["rows"]
    assert row["slug"] == "a-seedling"


def test_has_and_lacks_ask_about_presence(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    filed(tree)
    capsys.readouterr()
    assert main(["list", "--lacks", "cultivar", "--json"]) == 0
    (row,) = json.loads(capsys.readouterr().out)["rows"]
    assert row["slug"] == "another-seedling"


def test_two_filters_narrow_together(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    filed(tree)
    capsys.readouterr()
    assert main(["list", "--state", "orchard", "--has", "cultivar=hybrid", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["rows"] == []


def test_a_filter_value_outside_a_keys_values_refuses_by_name(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`click.Choice` cannot see past a `>=`, so the check lives in
    `read.comparison` — and still refuses by name, listing what is declared.
    The refusal names `--has`, which is how the caller spelled it."""
    assert main(["list", "--has", "cultivar=windfall"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--has" in captured.err and "heirloom, hybrid" in captured.err


def test_an_unknown_state_filter_refuses_by_name(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["list", "--state", "zzz"]) == 2
    assert "greenhouse" in capsys.readouterr().err


def test_has_naming_something_that_is_not_a_key_refuses_by_name(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--has` takes a key name rather than a value, so it gets the typo
    detector `head_errors` gives a head."""
    assert main(["list", "--has", "cultivarr"]) == 2
    assert 'not a key an item carries' in capsys.readouterr().err


@pytest.mark.parametrize("given", [["--has", "state=plan"], ["--lacks", "state"]])
def test_has_naming_a_field_the_row_reads_off_the_tree_says_so(
    tree: Path, capsys: pytest.CaptureFixture[str], given: list[str]
) -> None:
    """Every row has a `state` field, so naming it here is an easy slip. The
    refusal names `--state`, the one filter that reaches where an item is."""
    assert main(["list", *given]) == 2
    out, err = capsys.readouterr()
    assert "a row reads off the tree" in err
    assert "--state" in err
    assert out == ""


def test_has_naming_a_row_field_no_filter_reaches_points_nowhere(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`path` is a row field too, but nothing filters on it, so the refusal
    stops at saying what it is: no `--state`, and no carried list."""
    assert main(["list", "--has", "path"]) == 2
    err = capsys.readouterr().err
    assert "a row reads off the tree" in err
    assert "--state" not in err
    assert "carried:" not in err


#: The corpus 14-2 measured the finding against: three seedlings carrying
#: pests, one of them carrying a pest nobody asked about, and one carrying
#: none at all.
INFESTED = (("One", ("aphid",)), ("Mixed", ("aphid", "canker")),
            ("Two", ("aphid", "scab")), ("Clean", ()))


def infested(tree: Path) -> None:
    """`INFESTED` filed, each seedling sprouted and then transplanted."""
    for title, pests in INFESTED:
        assert main(["sprout", title, "--body", "P.", "--cultivar", "heirloom"]) == 0
        given = [word for pest in pests for word in ("--pest", pest)]
        assert main(["transplant", title.lower(), *given]) == 0


def test_the_all_of_filter_answers_where_inclusion_cannot(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """What inclusion cannot answer, end to end. `=aphid` returns `mixed`,
    which carries canker too, and reads as clean of everything else.
    `:aphid,scab` is the question the guard meant."""
    infested(tree)
    assert [row["slug"] for row in rows(capsys, "--has", "pest=aphid")] == [
        "one",
        "mixed",
        "two",
    ]
    assert [row["slug"] for row in rows(capsys, "--has", "pest:aphid,scab")] == [
        "one",
        "two",
    ]


def test_a_value_the_colon_names_is_refused_by_name_before_the_walk(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The shape every bad filter has: rc 2, `ERROR:` on stderr, no JSON, and
    no traversal — the refusal is in the parse."""
    assert main(["list", "--has", "pest:aphid,windfall", "--json"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "ERROR:" in captured.err and '"windfall"' in captured.err
    assert main(["list", "--has", "pest:"]) == 2
    assert "empty value" in capsys.readouterr().err


def test_the_read_names_the_operator_in_its_own_help(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A word the read takes and does not spell is a word only somebody
    reading `src/` finds, which is what section 14 is about."""
    assert main(["list", "--help"]) == 0
    assert "pest:aphid,scab" in capsys.readouterr().out


# --------------------------------------------------------------------------
# The table of contents
# --------------------------------------------------------------------------


def test_the_bare_command_prints_states_and_transitions(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([]) == 0
    out = capsys.readouterr().out
    declaration = load(tree / "plan.toml")
    assert out.index("States") < out.index("Transitions")
    for state in declaration.states.values():
        assert state.name in out
        assert f"{state.path}/" in out
    for transition in declaration.transitions.values():
        assert transition.help in out


def test_the_toc_lists_states_in_declared_order(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main([])
    out = capsys.readouterr().out
    assert out.index("greenhouse") < out.index("orchard") < out.index("cold-frame")


def declared(out: str) -> dict[str, str]:
    """The `Declares` block of a table of contents, as `{verb: halves}`."""
    block = out.partition("\nDeclares\n")[2].partition("\n\n")[0]
    rows = [line.split(maxsplit=1) for line in block.splitlines() if line.strip()]
    return {name: halves.strip() for name, halves in rows}


def test_the_toc_indexes_the_halves_each_transition_declares(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """6-3's read: a session composing several runs asks *which verb declares
    which half* once, rather than opening every contract in turn
    (`docs/method.md#the-interpreter`). Graded over the whole declaration —
    one verb would pass while the block quietly dropped the rest."""
    assert main([]) == 0
    out = capsys.readouterr().out
    assert out.index("Transitions") < out.index("Declares")
    assert declared(out) == {
        "pot-up": "claims",
        "tend": "claims",
        "espalier": "mints",
        "strike": "seeds",
        "mist": "mints",
        "pot-on": "marks",
        "line-out": "files, marks",
        "ripen": "marks",
        "thin": "marks",
        "grub-out": "archives",
        "fell": "archives, dissolves",
        "compost": "dissolves",
        "inarch": "dissolves, absorbs",
    }


def test_a_transition_declaring_no_half_is_absent_from_the_block(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Absence is the signal, the shape `Declares` already has in the contract
    and `Running it` has since 6-2 — `harvest` against `espalier`, the pair
    the `Running it` control used. A row reading `harvest` and nothing else
    would say the question had been asked and answered emptily, which is not
    what a verb that declares no half means."""
    assert main([]) == 0
    index = declared(capsys.readouterr().out)
    assert "espalier" in index and "harvest" not in index
    for name in ("transplant", "sprout", "bench", "bed-out", "graft-on"):
        assert name not in index


def test_the_toc_index_and_the_contract_cannot_disagree(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One `HALVES` tuple off one `Transition`, rendered twice — the
    `list`-and-`show` relationship this tool already ships. A second home for
    what a verb declares could drift; two renderings of one fact cannot."""
    declaration = load(tree / "plan.toml")
    assert main([]) == 0
    index = declared(capsys.readouterr().out)
    for name in declaration.transitions:
        epilog = helped(name, capsys)
        block = epilog.partition("Declares\n")[2].partition("\n\n")[0]
        halves = [line.strip() for line in block.splitlines() if line.strip()]
        assert index.get(name, "") == ", ".join(halves), name


def test_a_declaration_whose_verbs_declare_nothing_carries_no_block(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other half of the same rule, and the shape `Transitions` already
    has: a heading over an empty list would be the tool asking a question its
    declaration never poses."""
    halfless(tree)
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "Transitions" in out and "Declares" not in out


def halfless(tree: Path) -> None:
    """The same declaration with no transition declaring a half.

    `unnumbered`'s three go first, since `archives` and `mints` each answer a
    state's opt-in and cannot come off alone; `claimed` goes the same way. The
    three dissolving verbs go out **whole** rather than losing a flag: they
    name no `to`, so a `dissolves` taken off one would refuse at load — an
    item leaving a state for nowhere. `propagator` and its three verbs go out
    whole for the same kind of reason: the state's `bulleted` and the `mints`
    on the verb are one rule read from two ends, so neither can leave alone,
    and the verb that `marks` into it would then mark a state that is not
    there. Its `files` table goes with the verb that declares it — a table is
    a chunk of its own to the split below, and a `files` whose verb had gone
    would be a table under nothing. What is left still moves items between four states, which is what
    makes the absent block mean something.
    """
    unnumbered(tree)
    text = (tree / "plan.toml").read_text()
    gone = (
        "[states.propagator]",
        "[transitions.strike]",
        "[transitions.mist]",
        "[transitions.pot-on]",
        "[transitions.line-out]",
        "[transitions.line-out.files]",
    )
    kept = [
        re.sub(r"(?m)^(?:claims|absorbs)\s*=.*\n", "", chunk)
        for chunk in re.split(r"(?m)^(?=\[)", text)
        if not (chunk.startswith("[transitions.") and "dissolves" in chunk)
        and not chunk.startswith(gone)
    ]
    (tree / "plan.toml").write_text(
        "".join(kept).replace('capabilities = ["claimed"]\n', "")
    )


# --------------------------------------------------------------------------
# The table of contents, as JSON: the declaration in one read
# --------------------------------------------------------------------------


def declaration_json(capsys: pytest.CaptureFixture[str]) -> dict:
    """`fileplan --json`, parsed. One object, on one line."""
    assert main(["--json"]) == 0
    out = capsys.readouterr().out
    assert out.count("\n") == 1, "one object on one line, the shape every read has"
    return json.loads(out)


def test_the_declaration_renders_as_one_json_object(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """14-3's done line: a consumer gets every verb's declared halves *and*
    its contract blocks in one invocation, rather than one `--help` run per
    verb and prose parsing. `Declares` alone is not always the answer, because
    halves are shared — here `marks` is four verbs — and `Reading` is what
    tells them apart."""
    payload = declaration_json(capsys)
    declaration = load(tree / "plan.toml")
    assert payload["version"] == render.SCHEMA_VERSION
    assert payload["kind"] == "declaration"
    assert payload["source"] == str(tree / "plan.toml")
    assert payload["states"] == [
        {"name": state.name, "path": state.path}
        for state in declaration.states.values()
    ]


def test_every_declared_transition_is_a_row_in_declared_order(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Declared order, not alphabetical: the same order the text prints, and
    the workflow's own sequence."""
    payload = declaration_json(capsys)
    assert [row["name"] for row in payload["rows"]] == list(
        load(tree / "plan.toml").transitions
    )


def contract_json(name: str, capsys: pytest.CaptureFixture[str]) -> dict:
    """One verb's contract, out of the declaration read."""
    rows = {row["name"]: row for row in declaration_json(capsys)["rows"]}
    return rows[name]


def test_a_moving_verb_carries_every_block_the_contract_has(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`transplant` is the one verb declaring all four of `requires`,
    `refuses`, `sets` and `drops`."""
    row = contract_json("transplant", capsys)
    assert row["from"] == "greenhouse" and row["to"] == "orchard"
    assert row["requires"] == ["cultivar"]
    assert row["refuses"] == {"cultivar": ["hybrid"]}
    assert row["sets"] == ["rootstock", "pest"]
    assert row["drops"] == ["tag"]
    assert row["help"] == load(tree / "plan.toml").transitions["transplant"].help


def test_a_creating_verb_spells_its_absent_source_as_null(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`null` rather than omission, the split the listing already documents: a
    consumer can test `null` and cannot test a key that is not there."""
    row = contract_json("sprout", capsys)
    assert row["from"] is None and row["to"] == "greenhouse"


def test_a_dissolving_verb_spells_its_absent_destination_as_null(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other end of the same rule: `compost` names no `to` at all."""
    row = contract_json("compost", capsys)
    assert row["to"] is None and row["declares"] == ["dissolves"]


def test_a_refusal_of_a_list_valued_key_reads_as_a_list_of_values(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`harvest` refuses one value of a head that carries several."""
    assert contract_json("harvest", capsys)["refuses"] == {"pest": ["canker"]}


def test_a_verb_with_a_procedure_carries_its_pointer(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`policy` is the second pointer, and `espalier` is the verb that has
    one."""
    row = contract_json("espalier", capsys)
    assert row["policy"] == "training.md#training-a-branch"
    assert row["reading"] == {"espalier": "method.md#espalier"}


def test_a_verb_declaring_nothing_carries_the_empty_keys_anyway(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Present-always, which is the listing's corpus-independence rule one
    level up: the shape a consumer writes against must not depend on which
    verbs a declaration happens to declare. The text form goes on omitting an
    empty block, because a person reading help wants the blocks that say
    something."""
    row = contract_json("harvest", capsys)
    assert row["declares"] == [] and row["policy"] is None
    assert row["requires"] == [] and row["drops"] == [] and row["sets"] == []
    assert "Declares" not in helped("harvest", capsys)


def test_the_reading_block_answers_the_shared_half_question(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The finding this sub-phase answers: two verbs declare `claims`, so the
    half alone does not say which to run. `Reading` is what disambiguates, and
    it is in the same read."""
    rows = declaration_json(capsys)["rows"]
    claiming = {row["name"]: row["reading"] for row in rows if "claims" in row["declares"]}
    assert claiming == {
        "pot-up": {
            "pot-up": "method.md#pot-up",
            "cultivar": "method.md#cultivar",
        },
        "tend": {"tend": "method.md#tend", "rootstock": "method.md#rootstock"},
    }


def rebuilt(row: dict) -> str:
    """One verb's text epilog, rebuilt from its JSON object alone.

    The test's own copy of the rendering rules, so that a second block list
    beside `contract` — a block added to the help and never to the data — has
    nowhere to hide.
    """
    if row["from"] is None:
        going = f"into {row['to']}"
    elif "dissolves" in row["declares"]:
        going = f"out of {row['from']}, and the file is deleted"
    elif row["from"] == row["to"]:
        going = f"stays in {row['from']}"
    else:
        going = f"out of {row['from']} and into {row['to']}"
    width = max(len(name) for name in row["reading"])
    blocks = [("Where the item goes", [going])]
    for title, lines in (
        ("Requires", row["requires"]),
        (
            "Refuses",
            [
                f'{key} = "{value}"'
                for key, values in row["refuses"].items()
                for value in values
            ],
        ),
        ("Drops", row["drops"]),
        ("Declares", row["declares"]),
    ):
        if lines:
            blocks.append((title, lines))
    blocks.append(
        (
            "Reading",
            [f"{name:<{width}}  {pointer}" for name, pointer in row["reading"].items()],
        )
    )
    if row["policy"]:
        blocks.append(("Running it", [row["policy"]]))
    return "\n\n".join(
        "\n".join([title, *(f"  {line}" for line in lines)]) for title, lines in blocks
    )


def printed_epilog(out: str) -> str:
    """The contract as `--help` printed it, undented: everything from the
    first block on. Click indents an epilog paragraph by two."""
    tail = out[out.index("  Where the item goes\n") :].rstrip("\n")
    return "\n".join(line[2:] for line in tail.splitlines())


def test_the_text_contract_and_the_json_are_two_renderings_of_one_function(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**The control**, in the shape
    `test_text_and_json_are_two_renderings_of_one_traversal` has: every
    verb's text epilog is rebuilt from that verb's JSON object and compared
    against what the help run actually printed. Graded over the whole
    declaration, because one verb would pass while the rest drifted."""
    rows = {row["name"]: row for row in declaration_json(capsys)["rows"]}
    assert rows
    for name, row in rows.items():
        assert printed_epilog(helped(name, capsys)) == rebuilt(row), name


def test_a_command_beside_the_declarations_json_refuses(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Loud rather than ignored, and loud rather than answering about
    something else: make problems visible by default. The flag
    before the command asks what the declaration is; the command asks about
    the tree. The refusal's shape is every refusal's: rc 2, `ERROR:` on
    stderr, nothing on stdout."""
    assert main(["--json", "list"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("ERROR:") and "list --json" in captured.err


def test_a_reads_own_json_is_untouched_by_the_groups(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same word after the command still means the read, and it is still
    the read's rows rather than the declaration."""
    assert main(["list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["kind"] == "items"


def test_the_text_table_of_contents_is_unchanged_by_the_option(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A flag nobody passed changes nothing a person sees."""
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "--json" not in out
    assert out.index("States") < out.index("Transitions") < out.index("Declares")


# --------------------------------------------------------------------------
# The operator's contract
# --------------------------------------------------------------------------


def test_a_creating_transition_writes_the_file_and_echoes_its_path(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["sprout", "A seedling", "--body", "Prose."]) == 0
    assert capsys.readouterr().out.strip() == "greenhouse/a-seedling.md"
    assert (tree / "greenhouse" / "a-seedling.md").exists()


def test_a_body_of_a_dash_is_read_from_stdin(
    tree: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """So a heredoc works. There is no `$EDITOR` fallback: the main caller is
    an agent, and an editor would block it."""
    monkeypatch.setattr(sys, "stdin", io.StringIO("Prose from a heredoc.\n"))
    assert main(["sprout", "A seedling", "--body", "-"]) == 0
    filed = (tree / "greenhouse" / "a-seedling.md").read_text()
    assert "Prose from a heredoc." in filed


def test_a_body_is_taken_from_a_file_by_redirect(tree: Path) -> None:
    """Through the real console script, because a redirect is the shell's:
    `--body - < notes.md` needs no heredoc, and no `--body-file` spelling."""
    notes = tree / "notes.md"
    notes.write_text("Prose from a file.\n\nTwo paragraphs of it.\n")
    with notes.open() as stdin:
        run = subprocess.run(
            ["fileplan", "sprout", "A seedling", "--body", "-"],
            stdin=stdin,
            capture_output=True,
            text=True,
            cwd=tree,
            env={**os.environ, "FILEPLAN_PLAN_TOML": str(tree / "plan.toml")},
        )
    assert run.returncode == 0, run.stderr
    filed = (tree / "greenhouse" / "a-seedling.md").read_text()
    assert "Prose from a file.\n\nTwo paragraphs of it." in filed


def test_an_unquoted_multi_word_title_refuses_rather_than_joining(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One positional, never variadic. Joining the words would file an item
    under a name the operator did not type."""
    assert main(["sprout", "A", "seedling", "--body", "Prose."]) == 2
    assert list((tree / "greenhouse").iterdir()) == []


def test_a_value_outside_a_keys_values_refuses_through_click_choice(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    invocation = ["sprout", "A seedling", "--body", "Prose.", "--cultivar", "windfall"]
    assert main(invocation) == 2
    assert list((tree / "greenhouse").iterdir()) == []


def test_a_failed_precondition_refuses_by_name_with_rc_2(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tree / "greenhouse" / "a-seedling.md"
    source.write_text('+++\ntitle = "A seedling"\n+++\n\nProse.\n')
    before = source.read_bytes()
    assert main(["transplant", "a-seedling"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("ERROR: ")
    assert 'transplant requires "cultivar"' in captured.err
    assert source.read_bytes() == before


def test_a_malformed_plan_toml_refuses_at_a_subcommand_and_writes_nothing(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Validation runs at *every* invocation, before any subcommand acts."""
    (tree / "plan.toml").write_text("[states.greenhouse]\npath = 3\n")
    assert main(["sprout", "A seedling", "--body", "Prose."]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("ERROR: ")
    assert list((tree / "greenhouse").iterdir()) == []


def test_a_refusal_is_one_error_line_then_one_line_per_defect(tree: Path) -> None:
    """The operator's contract, through the real console script: rc 2, one
    `ERROR:` line on stderr, nothing on stdout, no traceback. Section 23: each
    further defect goes on an indented line of its own, where four used to
    share one line joined by semicolons."""
    (tree / "plan.toml").write_text(
        "".join(f"[states.s{n}]\npath = {n}\n" for n in range(4))
    )
    run = subprocess.run(
        ["fileplan", "sprout", "A seedling"],
        capture_output=True,
        text=True,
        cwd=tree,
        env={**os.environ, "FILEPLAN_PLAN_TOML": str(tree / "plan.toml")},
    )
    assert run.returncode == 2
    assert run.stdout == ""
    headline, *defects = run.stderr.strip().splitlines()
    assert headline.startswith("ERROR: ") and "not a usable plan.toml" in headline
    assert defects == [f"  states.s{n}.path must be a string" for n in range(4)]
    assert "Traceback" not in run.stderr


# --------------------------------------------------------------------------
# Naming a file: from the root, the way a row does
# --------------------------------------------------------------------------
#
# A consumer's commit hook runs fileplan on a temporary copy, from a cwd outside it.
# Each run below does the same, so a path relative to the cwd would carry the
# copy's whole prefix. See docs/method.md#the-listing


def from_outside(tree: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """The console script, run from a sibling directory outside `tree`."""
    elsewhere = tree.parent / f"{tree.name}-elsewhere"
    elsewhere.mkdir(exist_ok=True)
    return subprocess.run(
        ["fileplan", *args],
        capture_output=True,
        text=True,
        cwd=elsewhere,
        env={**os.environ, "FILEPLAN_PLAN_TOML": str(tree / "plan.toml")},
    )


def prefixed(tree: Path, said: str) -> bool:
    """Whether `said` carries the tree's own absolute prefix, either spelling."""
    return f"{tree}/" in said or f"{tree.resolve()}/" in said


def test_a_refusal_names_a_broken_item_file_from_the_root(tree: Path) -> None:
    (tree / "greenhouse" / "b-seedling.md").write_text("no head here at all\n")
    run = from_outside(tree, "list")
    assert run.returncode == 2
    assert "greenhouse/b-seedling.md is not a usable item file" in run.stderr
    assert not prefixed(tree, run.stderr)


def test_a_refusal_names_a_claim_record_from_the_root(tree: Path) -> None:
    record = claim.path(tree, "a-seedling")
    record.parent.mkdir(parents=True)
    record.write_text("pid = 4213\n")
    run = from_outside(tree, "list")
    assert run.returncode == 2
    assert "local/claims/a-seedling.toml is not a usable claim record" in run.stderr
    assert not prefixed(tree, run.stderr)


def test_a_run_notice_names_the_file_from_the_root(tree: Path) -> None:
    """Both streams: a check says its sentence on stdout, and a run that takes
    a file away says so on stderr."""
    for title in ("A seedling", "B seedling"):
        assert main(["sprout", title, "--body", "Prose.", "--cultivar", "heirloom"]) == 0

    checked = from_outside(tree, "transplant", "a-seedling", "--check")
    assert checked.returncode == 0
    assert "would move greenhouse/a-seedling.md to orchard/a-seedling.md" in checked.stdout
    assert not prefixed(tree, checked.stdout)

    gone = from_outside(tree, "compost", "b-seedling")
    assert gone.returncode == 0
    assert "greenhouse/b-seedling.md is gone: compost took it away" in gone.stderr
    assert gone.stdout == "greenhouse/b-seedling.md\n"
    assert not prefixed(tree, gone.stderr + gone.stdout)


def test_a_plan_toml_refusal_names_the_declaration_as_given(tree: Path) -> None:
    """`plan.toml` is what says which declaration was read, so a hook pointed at
    the wrong copy hears which. What it points at is named from the root."""
    declared = tree / "plan.toml"
    text = declared.read_text()
    assert text.count('"method.md#compost"') == 1
    declared.write_text(text.replace('"method.md#compost"', '"nowhere.md#compost"'))
    run = from_outside(tree, "list")
    assert run.returncode == 2
    assert run.stderr.startswith(f"ERROR: {declared} is not a usable plan.toml")
    assert "transitions.compost.doc names nowhere.md, which does not exist" in run.stderr


# --------------------------------------------------------------------------
# The queued capability, end to end
# --------------------------------------------------------------------------


def orchard(tree: Path, title: str, *placement: str) -> None:
    assert main(["sprout", title, "--body", "Prose.", "--cultivar", "heirloom"]) == 0
    slug = title.lower().replace(" ", "-")
    assert main(["transplant", slug, *placement]) == 0


def test_the_count_of_sub_phases_reaches_both_renderings(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole sub-phase, end to end: a body with three strict bullets under
    the declared heading reads as three, in the record and in the document,
    from one traversal."""
    orchard(tree, "First tree")
    path = tree / "orchard" / "first-tree.md"
    path.write_text(
        path.read_text()
        + "\n### Steps\n\n*Prose that opens the span, and is not a bullet.*\n\n"
        "- **1 — the first.**\n  1. an indented decision, not a sub-phase\n"
        "- **2 — the second.**\n- **3 — the third.**\n"
    )
    capsys.readouterr()

    assert main(["list", "--state", "orchard"]) == 0
    assert "sub-phases       3" in capsys.readouterr().out

    assert main(["list", "--state", "orchard", "--json"]) == 0
    (row,) = json.loads(capsys.readouterr().out)["rows"]
    assert row["sub-phases"] == 3


def test_a_section_nobody_has_decomposed_reads_as_zero_rather_than_absent(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`0` is a real value and a record must print it. A record drops a `None`
    line, so a zero that collapsed into `None` would vanish from the listing —
    and an undecomposed section going invisible is the failure the count
    exists to make loud."""
    orchard(tree, "First tree")
    capsys.readouterr()
    assert main(["list", "--state", "orchard"]) == 0
    printed = capsys.readouterr().out
    assert "  sub-phases       0" in printed
    # And no next: a body with no bullets has nothing to point at. The pair is
    # what a reader tells the two apart by — `0` with no next is a section
    # waiting to be cut up, and no count at all is a state that counts none.
    assert subphase.NEXT not in printed


def test_a_malformed_sub_phase_bullet_refuses_the_listing_by_name(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """John's constraint: bullets get written inconsistently, and that is what
    causes parsing errors. Here it is a refusal that names the line and the
    file rather than a number that is quietly wrong."""
    orchard(tree, "First tree")
    path = tree / "orchard" / "first-tree.md"
    path.write_text(path.read_text() + "\n### Steps\n- fine\n* starred\n")
    capsys.readouterr()

    assert main(["list"]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err.startswith("ERROR: ")
    assert "first-tree.md" in printed.err
    assert "body line 6" in printed.err


def stepped(tree: Path, *steps: str) -> Path:
    """A seedling in the orchard whose body carries `steps` as sub-phases."""
    orchard(tree, "First tree")
    path = tree / "orchard" / "first-tree.md"
    path.write_text(
        path.read_text() + "\n### Steps\n" + "".join(f"- {one}\n" for one in steps)
    )
    return path


def named(tree: Path, *names: str) -> Path:
    """The same, in the strict **named** form a cursor may point at."""
    return stepped(tree, *(f"**{one} — step {one}.**" for one in names))


def test_a_cursor_the_body_does_not_carry_refuses_naming_the_names_available(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The done line, end to end: the verb that advances the cursor is graded
    against the sub-phases the body actually carries, before anything is
    written. A typo is caught the same way a reference past the end is —
    which is what membership buys over an ordinal's range check."""
    path = named(tree, "graft-1", "graft-2", "graft-3")
    before = path.read_bytes()
    capsys.readouterr()

    assert main(["graft-on", "first-tree", "--graft", "graft-9"]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err.startswith("ERROR: ")
    assert 'names sub-phase "graft-9"' in printed.err
    assert "graft-1, graft-2, graft-3" in printed.err
    # A refused run leaves the source byte-identical.
    assert path.read_bytes() == before


def test_a_cursor_naming_an_unnamed_bullet_refuses_rather_than_counting(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Nothing falls back to an ordinal: `2` is not "the second bullet", it is
    a name the body has not got, and the refusal says which line needs one."""
    path = stepped(tree, "one", "two", "three")
    before = path.read_bytes()
    capsys.readouterr()

    assert main(["graft-on", "first-tree", "--graft", "2"]) == 2
    printed = capsys.readouterr()
    assert "no named sub-phase at all" in printed.err
    assert "named by the bold it opens with" in printed.err
    assert path.read_bytes() == before


def test_a_cursor_naming_a_sub_phase_the_body_carries_is_written(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = named(tree, "graft-1", "graft-2", "graft-3")
    capsys.readouterr()
    assert (
        main(["graft-on", "first-tree", "--graft", "graft-2", "--graft-status", "done"])
        == 0
    )
    assert 'graft = "graft-2"' in path.read_text()


def test_a_cursor_survives_a_bullet_inserted_above_the_one_it_names(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The reason for the whole sub-phase, end to end. Under ordinals this
    insert would leave the head pointing at the bullet *above* the work — a
    wrong state nothing would report. Under names the cursor still grades, and
    still names the same step."""
    path = named(tree, "graft-1", "graft-2", "graft-3")
    assert main(["graft-on", "first-tree", "--graft", "graft-3"]) == 0
    path.write_text(
        path.read_text().replace(
            "- **graft-1 — step graft-1.**",
            "- **graft-0 — step graft-0.**\n- **graft-1 — step graft-1.**",
        )
    )

    assert main(["graft-on", "first-tree", "--graft-status", "done"]) == 0
    assert 'graft = "graft-3"' in path.read_text()
    capsys.readouterr()
    assert main(["list", "--state", "orchard", "--json"]) == 0
    (row,) = json.loads(capsys.readouterr().out)["rows"]
    assert (row["graft"], row["sub-phases"]) == ("graft-3", 4)


def rows(capsys: pytest.CaptureFixture[str], *given: str) -> list[dict]:
    """``list --json`` over ``given``, as the rows it found."""
    capsys.readouterr()
    assert main(["list", "--json", *given]) == 0
    return json.loads(capsys.readouterr().out)["rows"]


def test_the_next_sub_phase_is_in_the_default_read_and_moves_with_the_verb(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Both arms end to end, with the cursor written by one verb and the mark
    by another. Behind no flag, in both renderings: a cursor left on a
    finished step is exactly the defect that hides otherwise, and the default
    record is where it has to show."""
    named(tree, "graft-1", "graft-2", "graft-3")
    capsys.readouterr()

    # Nothing picked up: the first step is what to pick up.
    assert main(["list", "--state", "orchard"]) == 0
    assert "next-sub-phase   graft-1" in capsys.readouterr().out

    # Picked up and not marked: the current step is still what to do.
    assert main(["ripen", "first-tree", "graft-1"]) == 0
    assert main(["graft-on", "first-tree", "--graft", "graft-2"]) == 0
    assert main(["graft-on", "first-tree", "--graft-status", "in progress"]) == 0
    (row,) = rows(capsys, "--state", "orchard")
    assert row["next-sub-phase"] == "graft-2"

    # Marked: the step after it, and the cursor stays where the mark went on.
    assert main(["ripen", "first-tree", "graft-2"]) == 0
    (row,) = rows(capsys, "--state", "orchard")
    assert (row["graft"], row["next-sub-phase"]) == ("graft-2", "graft-3")


def test_a_finished_last_sub_phase_leaves_the_count_and_no_next(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The pair is what distinguishes the two silences. `sub-phases 3` with no
    next is a decomposition that is finished; no count at all is a state that
    counts none."""
    named(tree, "graft-1", "graft-2", "graft-3")
    assert main(["graft-on", "first-tree", "--graft", "graft-3"]) == 0
    for one in ("graft-1", "graft-2", "graft-3"):
        assert main(["ripen", "first-tree", one]) == 0

    (row,) = rows(capsys, "--state", "orchard")
    assert row["sub-phases"] == 3
    assert row["next-sub-phase"] is None
    # A record drops a `None` line, so the count is what is left showing.
    assert main(["list", "--state", "orchard"]) == 0
    printed = capsys.readouterr().out
    assert "sub-phases       3" in printed
    assert "next-sub-phase" not in printed


def test_both_renderings_agree_on_the_count_left(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One traversal, two renderings, end to end. `sub-phases-left` is in the
    default record behind no flag, for `next-sub-phase`'s reason exactly: what
    it makes visible is a sub-phase nobody marked, and a flag you have to know
    to pass is that defect hiding with extra steps."""
    named(tree, "graft-1", "graft-2", "graft-3")
    assert main(["ripen", "first-tree", "graft-1"]) == 0
    capsys.readouterr()

    assert main(["list", "--state", "orchard"]) == 0
    assert "sub-phases-left  2" in capsys.readouterr().out

    (row,) = rows(capsys, "--state", "orchard")
    assert (row["sub-phases"], row["sub-phases-left"]) == (3, 2)

    # And zero prints rather than vanishing: a record drops a `None` line, so
    # a finished section says so out loud in the text form too.
    for one in ("graft-2", "graft-3"):
        assert main(["ripen", "first-tree", one]) == 0
    capsys.readouterr()
    assert main(["list", "--state", "orchard"]) == 0
    assert "sub-phases-left  0" in capsys.readouterr().out


def test_the_count_left_is_a_filter_of_its_own(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Generated off the derived roster like every other row field, so
    `--sub-phases-left 0` is the sections with nothing left in them and no
    named report had to be built to ask it."""
    named(tree, "graft-1", "graft-2")
    orchard(tree, "Second tree")
    for one in ("graft-1", "graft-2"):
        assert main(["ripen", "first-tree", one]) == 0

    assert [one["slug"] for one in rows(capsys, "--has", "sub-phases-left=0")] == [
        "first-tree",
        # `second-tree` carries no bullets at all, so nothing is left in it
        # either — the filter is the superset and the *pair* is what tells an
        # undecomposed section from a finished one.
        "second-tree",
    ]
    assert [one["slug"] for one in rows(capsys, "--has", "sub-phases-left>=1")] == []


def test_a_stale_cursor_is_visible_in_the_default_read(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The polarity this whole field exists for. A cursor left on a finished
    step while later ones shipped used to read as ordinary progress; now the
    listing says which step is next and the answer is one already behind."""
    named(tree, "graft-1", "graft-2", "graft-3")
    assert main(["graft-on", "first-tree", "--graft", "graft-1"]) == 0
    assert main(["ripen", "first-tree", "graft-1"]) == 0

    (row,) = rows(capsys, "--state", "orchard")
    assert (row["graft"], row["next-sub-phase"]) == ("graft-1", "graft-2")


def test_the_row_names_an_earlier_open_step_over_the_one_the_cursor_is_on(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Out-of-order completion, end to end and through real verbs: the first
    step is finished, the last is skipped, the middle one is untouched, and
    the cursor sits on the last. The row names the middle one — which is the
    answer a `(cursor, status)` pair in the head could not give at all."""
    named(tree, "graft-1", "graft-2", "graft-3")
    assert main(["ripen", "first-tree", "graft-1"]) == 0
    assert main(["thin", "first-tree", "graft-3"]) == 0
    assert main(["graft-on", "first-tree", "--graft", "graft-3"]) == 2

    (row,) = rows(capsys, "--state", "orchard")
    assert row["next-sub-phase"] == "graft-2"


def test_a_cursor_moved_onto_a_marked_sub_phase_refuses_naming_its_mark(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Picking a cursor **up** and putting it on work already disposed of.
    Refused before anything is written, and the refusal names the mark."""
    path = named(tree, "graft-1", "graft-2", "graft-3")
    assert main(["ripen", "first-tree", "graft-2"]) == 0
    before = path.read_bytes()
    capsys.readouterr()

    assert main(["graft-on", "first-tree", "--graft", "graft-2"]) == 2
    printed = capsys.readouterr()
    assert printed.err.startswith("ERROR:")
    assert 'graft names sub-phase "graft-2"' in printed.err
    assert "**ripened**" in printed.err
    assert path.read_bytes() == before


def test_marking_a_sub_phase_the_cursor_is_on_is_not_refused_by_the_cursor_check(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other half, and the one that makes marking work at all. A verb that
    marks the step the cursor is on writes no cursor, so the arm above is not
    asked — and a cursor resting on a marked step is the **ordinary** state
    right after the mark went on."""
    named(tree, "graft-1", "graft-2", "graft-3")
    assert main(["graft-on", "first-tree", "--graft", "graft-2"]) == 0
    assert main(["ripen", "first-tree", "graft-2"]) == 0

    (row,) = rows(capsys, "--state", "orchard")
    assert (row["graft"], row["next-sub-phase"]) == ("graft-2", "graft-1")


def test_no_status_in_the_head_moves_what_comes_next(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`done` is a value `graft-status` declares, so this is a real status and
    not a refusal — and it moves nothing. Completion is stored **once**, on
    the bullet, which is what stops the two from ever disagreeing."""
    named(tree, "graft-1", "graft-2", "graft-3")
    assert main(["graft-on", "first-tree", "--graft", "graft-1"]) == 0
    for status in ("open", "planned", "in progress", "done"):
        assert main(["graft-on", "first-tree", "--graft-status", status]) == 0
        (row,) = rows(capsys, "--state", "orchard")
        assert row["next-sub-phase"] == "graft-1"


def test_has_and_lacks_reach_the_next_sub_phase(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Generated like every other filter, off what a row carries. `--has
    next-sub-phase` is the sections with something left to pick up, which is
    the read a composed session chooses with."""
    named(tree, "graft-1", "graft-2")
    orchard(tree, "Second tree", "--at", "200")

    assert [row["slug"] for row in rows(capsys, "--has", "next-sub-phase")] == [
        "first-tree"
    ]
    assert [row["slug"] for row in rows(capsys, "--lacks", "next-sub-phase")] == [
        "second-tree"
    ]

    # Finish both steps and it drops out of the ready half by itself.
    assert main(["ripen", "first-tree", "graft-1"]) == 0
    assert main(["ripen", "first-tree", "graft-2"]) == 0
    assert rows(capsys, "--has", "next-sub-phase") == []


def test_the_next_sub_phase_is_a_filter_of_its_own(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One `--<field>` per row field, the `--position` rule again. Untyped: a
    step's name comes off a body rather than out of `plan.toml`, so there is
    no declared set to refuse a value against."""
    named(tree, "graft-1", "graft-2")
    assert [
        row["slug"] for row in rows(capsys, "--has", "next-sub-phase=graft-1")
    ] == ["first-tree"]
    assert rows(capsys, "--has", "next-sub-phase=graft-2") == []


def test_a_status_outside_the_declared_values_refuses(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The workflow's `values`, not the tool's words. Pinned here against the
    cursor's own key so the closed set is known to cover it."""
    stepped(tree, "one")
    capsys.readouterr()
    assert main(["graft-on", "first-tree", "--graft-status", "shipped"]) == 2
    assert "shipped" in capsys.readouterr().err


def test_a_started_section_with_no_sub_phases_is_named_by_the_default_read(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Behind no flag, in both renderings. Hiding is the failure mode, and a
    flag you have to know to pass is the same failure with extra steps."""
    orchard(tree, "First tree")
    assert main(["graft-on", "first-tree", "--graft-status", "open"]) == 0
    capsys.readouterr()

    assert main(["list"]) == 0
    printed = capsys.readouterr()
    assert "started but not decomposed: first-tree" in printed.err
    # An exception report about the tree, not a row of it: stdout is clean.
    assert "started but not decomposed" not in printed.out

    assert main(["list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["undecomposed"] == ["first-tree"]


def test_a_section_nobody_has_started_is_not_named_however_few_it_carries(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Started means the item carries the status key **at all**. A queued,
    untouched section legitimately has no sub-phases, and flagging every one
    of those would be false alarms that train the reader to ignore the line."""
    orchard(tree, "First tree")
    capsys.readouterr()
    assert main(["list"]) == 0
    printed = capsys.readouterr()
    assert "started but not decomposed" not in printed.err
    assert main(["list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["undecomposed"] == []


def test_the_body_is_never_read_to_find_the_status(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Done line: the status comes from the head. A bullet that *says* it is
    done changes nothing — the count is derived from the document and the
    cursor is declared state, and nothing reads a bullet to find out where the
    work is."""
    path = stepped(tree, "**one.** Done 2026-09-03.", "**two.** in progress")
    assert main(["graft-on", "first-tree", "--graft-status", "open"]) == 0
    capsys.readouterr()

    assert main(["list", "--state", "orchard", "--json"]) == 0
    (row,) = json.loads(capsys.readouterr().out)["rows"]
    assert row["graft-status"] == "open"
    assert row["sub-phases"] == 2
    assert "Done" in path.read_text()


def test_the_undecomposed_report_is_unchanged_by_the_drop(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The interaction worth pinning rather than reasoning about. The report
    needs the status key present **and** no sub-phases at all, so a section
    with a finished one has bullets and can neither start nor stop firing
    because a marking verb took the key off. Both directions, in one test."""
    named(tree, "graft-1", "graft-2")
    assert main(["graft-on", "first-tree", "--graft-status", "open"]) == 0
    capsys.readouterr()
    assert main(["list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["undecomposed"] == []

    assert main(["ripen", "first-tree", "graft-1"]) == 0
    capsys.readouterr()
    assert main(["list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["undecomposed"] == []


def test_no_filter_narrows_the_undecomposed_report(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`stranded`'s rule, for `stranded`'s reason: it is an exception report
    about the tree rather than a row of it."""
    orchard(tree, "First tree")
    assert main(["graft-on", "first-tree", "--graft-status", "open"]) == 0
    capsys.readouterr()
    assert main(["list", "--state", "greenhouse", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["rows"] == []
    assert payload["undecomposed"] == ["first-tree"]


def test_the_listing_shows_a_queued_state_in_its_own_order(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The done line: a place can be inserted between two existing ones
    without renumbering, and the listing reads top to bottom in that order."""
    orchard(tree, "First tree")
    orchard(tree, "Second tree")
    orchard(tree, "A wedge", "--above", "second-tree")
    capsys.readouterr()

    assert main(["list", "--state", "orchard", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert [(row["slug"], row["position"]) for row in rows] == [
        ("first-tree", 100),
        ("a-wedge", 150),
        ("second-tree", 200),
    ]


def test_the_record_shows_the_place_under_the_slug(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    orchard(tree, "First tree")
    capsys.readouterr()
    assert main(["list", "--state", "orchard"]) == 0
    out = capsys.readouterr().out
    assert "first-tree" in out
    # The labels are padded to the widest field the listing carries, which is
    # now `sub-phases` rather than `position`.
    assert "  position         100" in out


def test_the_place_filter_compares_as_a_number(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """As text, `"50"` sorts above `"100"`. The filter exists because a row
    carries the key, and it compares the way the key is written."""
    orchard(tree, "First tree")
    orchard(tree, "A wedge", "--at", "50")
    capsys.readouterr()

    assert main(["list", "--has", "position>=100", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert [row["slug"] for row in rows] == ["first-tree"]


# --------------------------------------------------------------------------
# Dependencies: what an item waits on, and the edge that names nothing
# --------------------------------------------------------------------------
#
# The re-pin the old tool got wrong is `test_an_edge_naming_no_filed_item_...`
# below: `_plan_dir.unmet_after` kept only the slugs that were present, so a
# **typo'd** one was never present either and read as a satisfied dependency,
# silently. Here the complement is a line in the default read.
#
# No verb in the fixture writes `after`, and none should — an edge is prose a
# person writes, and section 5's archiver is what edits one mechanically. So
# these write the head line directly, the way the sub-phase tests write
# bullets into a body.


def waits(tree: Path, slug: str, *edges: str) -> None:
    """Write ``slug``'s ``after`` edges into its head, in the fixture's word."""
    path = tree / "orchard" / f"{slug}.md"
    named = ", ".join(f'"{one}"' for one in edges)
    path.write_text(path.read_text().replace("+++", f"+++\nafter = [{named}]", 1))


def test_an_item_waiting_on_a_filed_item_carries_it_in_blocked_by(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The row field, off the key `[states.orchard]` names. `after` is the
    fixture's word — the tool spells only `blocked-by`."""
    orchard(tree, "First tree")
    orchard(tree, "Second tree", "--at", "200")
    waits(tree, "second-tree", "first-tree")

    found = {row["slug"]: row["blocked-by"] for row in rows(capsys)}
    assert found == {"first-tree": None, "second-tree": ["first-tree"]}
    assert main(["list", "--state", "orchard"]) == 0
    assert "blocked-by       first-tree" in capsys.readouterr().out


def test_show_prints_what_waits_on_an_item(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Before declining or reworking an item a session wants to know who
    depends on it. `blocks` is `blocked-by` read the other way round."""
    orchard(tree, "First tree")
    orchard(tree, "Second tree", "--at", "200")
    waits(tree, "second-tree", "first-tree")
    capsys.readouterr()
    assert main(["show", "first-tree"]) == 0
    assert "blocks           second-tree" in capsys.readouterr().out
    assert main(["list", "--has", "blocks=second-tree", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [row["slug"] for row in payload["rows"]] == ["first-tree"]


def test_an_item_waiting_on_nothing_carries_null(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`null` in the document and no line at all in the record, which is how
    the two renderings each spell absent."""
    orchard(tree, "First tree")
    (row,) = rows(capsys)
    assert "blocked-by" in row and row["blocked-by"] is None
    assert main(["list", "--state", "orchard"]) == 0
    assert "blocked-by" not in capsys.readouterr().out


def test_an_edge_naming_no_filed_item_is_named_rather_than_read_as_satisfied(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**The re-pin**, and the test whose absence was the old tool's bug.
    Absence used to mean satisfied, so a typo was invisible; now it means
    unknown, and unknown is named in the default read. It is deliberately not
    in `blocked-by`: "waiting on X" and "X does not exist" are different
    facts."""
    orchard(tree, "First tree")
    waits(tree, "first-tree", "no-such-tree")
    capsys.readouterr()

    assert main(["list"]) == 0
    printed = capsys.readouterr()
    assert (
        'unknown dependency: first-tree names "no-such-tree" in after, and no '
        "item carries that slug"
    ) in printed.err
    # An exception report about the tree, not a row of it: stdout is clean.
    assert "unknown dependency" not in printed.out

    (row,) = rows(capsys)
    assert row["blocked-by"] is None


def test_an_edge_pointing_later_in_the_order_is_named_by_the_default_read(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Behind no flag. `position` sorts and an edge reports, so two statements
    that disagree are said out loud rather than settled by the tool."""
    orchard(tree, "First tree")
    orchard(tree, "Second tree", "--at", "200")
    waits(tree, "first-tree", "second-tree")
    capsys.readouterr()

    assert main(["list"]) == 0
    assert (
        "misordered dependency: first-tree at place 100 waits on "
        "second-tree at place 200. An item cannot wait on something later "
        "in the order"
    ) in capsys.readouterr().err


def test_the_listing_s_order_is_unchanged_by_any_edge(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two keys, two jobs. The old tool ran Kahn's walk over `after` and
    reordered; here an edge naming an item later in the queue is *named*, and
    the queue is exactly as `position` left it."""
    orchard(tree, "First tree")
    orchard(tree, "Second tree", "--at", "200")
    before = [row["slug"] for row in rows(capsys)]
    waits(tree, "first-tree", "second-tree")
    assert [row["slug"] for row in rows(capsys)] == before == [
        "first-tree",
        "second-tree",
    ]


def test_both_reports_reach_both_renderings(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One traversal, two renderings — and four exception reports that stay
    four arrays rather than one merged list, because the envelope key is how a
    consumer selects the one it cares about."""
    orchard(tree, "First tree")
    orchard(tree, "Second tree", "--at", "200")
    waits(tree, "first-tree", "second-tree", "no-such-tree")
    capsys.readouterr()

    assert main(["list"]) == 0
    err = capsys.readouterr().err
    assert "unknown dependency: first-tree" in err
    assert "misordered dependency: first-tree" in err

    assert main(["list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [one["names"] for one in payload["unknown"]] == ["no-such-tree"]
    assert [one["names"] for one in payload["misordered"]] == ["second-tree"]
    assert payload["misordered"][0]["place"] == 100


def test_no_filter_narrows_either_dependency_report(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Hiding is the failure mode, and a filter that quietly dropped the line
    would be that failure with the filter as its excuse. The filter here
    excludes the very item both reports name."""
    orchard(tree, "First tree")
    orchard(tree, "Second tree", "--at", "200")
    waits(tree, "first-tree", "second-tree", "no-such-tree")
    capsys.readouterr()

    assert main(["list", "--state", "greenhouse", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["rows"] == []
    assert [one["names"] for one in payload["unknown"]] == ["no-such-tree"]
    assert [one["names"] for one in payload["misordered"]] == ["second-tree"]


def test_the_blocked_by_filter_narrows_and_has_lacks_reach_it(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One `--<field>` per row field, the `--position` rule a fourth time.
    `--lacks blocked-by` is the work nothing filed is in the way of."""
    orchard(tree, "First tree")
    orchard(tree, "Second tree", "--at", "200")
    waits(tree, "second-tree", "first-tree")

    assert [row["slug"] for row in rows(capsys, "--has", "blocked-by=first-tree")] == [
        "second-tree"
    ]
    assert rows(capsys, "--has", "blocked-by=no-such-tree") == []
    assert [row["slug"] for row in rows(capsys, "--has", "blocked-by")] == [
        "second-tree"
    ]
    assert [row["slug"] for row in rows(capsys, "--lacks", "blocked-by")] == [
        "first-tree"
    ]


def test_a_declaration_with_no_dependencies_carries_neither_field_nor_filter(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Generated by the state's opt-in, so where nothing names a key there is
    no field, no filter and no report — the `--position` rule's other half."""
    source = tree / "plan.toml"
    source.write_text(source.read_text().replace('dependencies      = "after"', ""))
    orchard(tree, "First tree")

    (row,) = rows(capsys)
    assert "blocked-by" not in row
    capsys.readouterr()
    assert main(["list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "unknown" not in payload and "misordered" not in payload

    assert main(["list", "--help"]) == 0
    assert "--blocked-by" not in capsys.readouterr().out
    assert main(["list", "--has", "blocked-by=first-tree"]) == 2


def test_an_unresolvable_edge_does_not_refuse_the_listing(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Reported, never refused. 4-6's precedent: `head_errors` grades an
    item's *shape*, and grading values at read time would break a whole
    listing over one item."""
    orchard(tree, "First tree")
    waits(tree, "first-tree", "no-such-tree")
    capsys.readouterr()

    assert main(["list"]) == 0
    printed = capsys.readouterr()
    assert "first-tree" in printed.out
    assert "1 of 1 items" in printed.err


def test_an_unresolvable_edge_does_not_narrow_the_offer(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """It gates nothing. A gate would make a precondition depend on a derived
    fact, and `offer_errors` would stop being pure over a head — so
    blocked work is still offered, and the reports reach the offer because
    they are about the tree rather than about the offer."""
    orchard(tree, "First tree")
    orchard(tree, "Second tree", "--at", "200")
    waits(tree, "first-tree", "second-tree", "no-such-tree")

    assert offered(capsys, "harvest") == ["first-tree", "second-tree"]
    capsys.readouterr()
    assert main(["next", "harvest", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [one["names"] for one in payload["unknown"]] == ["no-such-tree"]
    assert [one["names"] for one in payload["misordered"]] == ["second-tree"]


# --------------------------------------------------------------------------
# The dated capability, end to end
# --------------------------------------------------------------------------

# The fixture's `cold-frame` is the dated state and `harvest` is the way in.
# The repos are built in-process with dulwich, like `test_stale.py`'s: no
# subprocess runs, and no clock is mocked — a commit is written with an
# explicit author timestamp instead.

GARDENER = b"A Gardener <gardener@example.invalid>"


def hardened(tree: Path, title: str) -> str:
    """One item filed all the way into the dated state. Returns its slug."""
    orchard(tree, title)
    slug = title.lower().replace(" ", "-")
    assert main(["harvest", slug]) == 0
    return slug


def committed(tree: Path, *slugs: str, ago: int) -> None:
    """Commit the dated state's files, authored ``ago`` days ago at local noon.

    Noon rather than "now minus N days" so the date the tool reads is exactly
    that many days back whatever hour the suite happens to run at.
    """
    when = dt.datetime.combine(
        dt.date.today() - dt.timedelta(days=ago), dt.time(12)
    ).astimezone()
    here = load(tree / "plan.toml").states["cold-frame"].path
    started = Repo(str(tree)) if (tree / ".git").exists() else Repo.init(str(tree))
    with started as repo:
        worktree = repo.get_worktree()
        worktree.stage([f"{here}/{slug}.md".encode() for slug in slugs])
        worktree.commit(
            b"filed",
            committer=GARDENER,
            author=GARDENER,
            author_timestamp=int(when.timestamp()),
            author_timezone=int(when.utcoffset().total_seconds()),
            commit_timestamp=int(when.timestamp()),
            commit_timezone=0,
        )


def test_stale_days_reaches_both_renderings(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Read out of git, stamped nowhere: the item's head carries no anchor and
    the number is there anyway."""
    hardened(tree, "First tree")
    committed(tree, "first-tree", ago=7)

    (row,) = rows(capsys)
    assert row["stale-days"] == 7
    filed = tree / "beds" / "hardening-off" / "first-tree.md"
    assert "stale" not in filed.read_text()

    assert main(["list", "--state", "cold-frame"]) == 0
    assert "stale-days  7" in capsys.readouterr().out


def test_a_second_commit_moves_it_and_nothing_is_rewritten(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Any commit touching the file resets it — the number says *days since
    anybody was near this*, which is what reading git rather than a stamp
    buys."""
    hardened(tree, "First tree")
    committed(tree, "first-tree", ago=30)
    assert [one["stale-days"] for one in rows(capsys)] == [30]

    filed = tree / "beds" / "hardening-off" / "first-tree.md"
    filed.write_text(filed.read_text() + "\nOne more line.\n")
    committed(tree, "first-tree", ago=2)
    assert [one["stale-days"] for one in rows(capsys)] == [2]


def test_the_stale_days_filter_narrows_and_has_lacks_reach_it(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One `--<field>` per row field, the `--position` rule a fifth time — and
    it compares as a **number**, so `>=9` keeps 30 and drops 3."""
    hardened(tree, "First tree")
    hardened(tree, "Second tree")
    committed(tree, "first-tree", ago=30)
    committed(tree, "second-tree", ago=3)
    fresh = hardened(tree, "Third tree")

    assert [one["slug"] for one in rows(capsys, "--has", "stale-days>=9")] == [
        "first-tree"
    ]
    assert [one["slug"] for one in rows(capsys, "--has", "stale-days=3")] == [
        "second-tree"
    ]
    assert sorted(one["slug"] for one in rows(capsys, "--has", "stale-days")) == [
        "first-tree",
        "second-tree",
    ]
    assert [one["slug"] for one in rows(capsys, "--lacks", "stale-days")] == [fresh]


def test_a_tree_that_is_not_a_git_repo_lists_with_every_value_null(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A tree that is not a repo, and the arm that must not raise: rc 0, no
    traceback, and `stale-days` present and `null` on every row."""
    hardened(tree, "First tree")
    assert not (tree / ".git").exists()

    found = rows(capsys)
    assert found and all(one["stale-days"] is None for one in found)
    printed = capsys.readouterr()
    assert "Traceback" not in printed.err and "ERROR" not in printed.err


def test_a_declaration_with_no_dated_state_carries_neither_field_nor_filter(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Generated by the state's opt-in, so where nothing opts in there is no
    field and no filter — and no git work at all."""
    source = tree / "plan.toml"
    source.write_text(source.read_text().replace('capabilities = ["dated"]', ""))
    hardened(tree, "First tree")

    (row,) = rows(capsys)
    assert "stale-days" not in row

    assert main(["list", "--help"]) == 0
    assert "--stale-days" not in capsys.readouterr().out
    assert main(["list", "--has", "stale-days>=1"]) == 2


# --------------------------------------------------------------------------
# The register: a number minted from the state plus the archive
# --------------------------------------------------------------------------


def test_the_number_reaches_both_renderings_and_its_own_filter(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Generated by the capability, exactly as `--position` is: the row
    carries the key and the filter reaches it, off one list rather than a
    `has(...)` test at each site."""
    orchard(tree, "First tree")
    capsys.readouterr()

    assert main(["list", "--state", "orchard", "--json"]) == 0
    (row,) = json.loads(capsys.readouterr().out)["rows"]
    assert row["number"] == 2

    assert main(["list", "--state", "orchard"]) == 0
    # Padded to the widest label the listing carries, `sub-phases-left`.
    assert "  number           2" in capsys.readouterr().out

    assert main(["list", "--has", "number>=2", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert [one["slug"] for one in rows] == ["first-tree"]


def test_a_lost_archive_heading_refuses_with_the_operator_contract(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """rc 2, one `ERROR:` line, nothing on stdout, and the line named. The
    heading is the only record a closed item's number is taken, so the tool
    stops rather than minting over it."""
    (tree / "orchard-archive.md").write_text("## Section 1: A felled tree\n")
    assert main(["sprout", "A tree", "--body", "Prose.", "--cultivar", "heirloom"]) == 0
    capsys.readouterr()

    assert main(["transplant", "a-tree"]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err.startswith("ERROR: ")
    assert "Section 1: A felled tree" in printed.err
    assert list((tree / "orchard").iterdir()) == []


def test_an_archive_the_tree_does_not_hold_refuses_at_every_invocation(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Graded like a `doc =` pointer, so even `--help` says so: a state that
    mints numbers cannot be lying about where its closed ones are recorded."""
    (tree / "orchard-archive.md").unlink()
    assert main(["--help"]) == 2
    err = capsys.readouterr().err
    assert "states.orchard.archive names" in err
    assert "which does not exist" in err


def gapped(tree: Path) -> None:
    """A register short of 2 — the item that vanished without an exit.

    The archive holds 1, two trees mint 2 and 3, and the one holding 2 is
    deleted by hand rather than through a declared verb. That is the whole
    defect this reports: nothing says what happened to it.
    """
    orchard(tree, "First tree")
    orchard(tree, "Second tree", "--at", "200")
    (tree / "orchard" / "first-tree.md").unlink()


def unread(tree: Path) -> None:
    """A `##` in the archive the register cannot read — the old tool's own."""
    path = tree / "orchard-archive.md"
    path.write_text(path.read_text() + "\n## Section 168: Something\n")


def test_both_register_reports_reach_both_renderings(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Done line 2, end to end. Seven exception reports now, still seven
    arrays rather than one merged list of notices: a gap is a *number* and a
    lost close-out is a *document line*, and the envelope key is how a
    consumer selects the one it cares about."""
    gapped(tree)
    unread(tree)
    capsys.readouterr()

    assert main(["list"]) == 0
    printed = capsys.readouterr()
    assert (
        "register gap: number 2 is missing from orchard and from "
        "orchard-archive.md, so nothing says what happened to the item that "
        "carried number 2"
    ) in printed.err
    assert "lost close-out: orchard-archive.md:" in printed.err
    assert (
        "`## Section 168: Something` is not a heading the numbered register "
        "can read, so the number that heading names is free to be minted again"
    ) in printed.err
    # Reports about the register, not rows of the tree: stdout is clean.
    assert "register gap" not in printed.out and "lost close-out" not in printed.out

    assert main(["list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["gaps"] == [
        {"state": "orchard", "archive": "orchard-archive.md", "number": 2}
    ]
    (one,) = payload["lost"]
    assert (one["state"], one["archive"]) == ("orchard", "orchard-archive.md")
    assert one["text"] == "## Section 168: Something"


def test_the_read_reports_the_gap_the_mint_still_refuses_on(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The two polarities in one test, which is the point of the sub-phase.
    The listing **reports** — rc 0, so a session that has to fix the register
    can still read the tree — and the writer **refuses**, on the same
    arithmetic, before minting on top of it."""
    gapped(tree)
    capsys.readouterr()

    assert main(["list"]) == 0
    assert "register gap: number 2" in capsys.readouterr().err

    assert main(["sprout", "A tree", "--body", "P.", "--cultivar", "heirloom"]) == 0
    capsys.readouterr()
    assert main(["transplant", "a-tree"]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert "register runs to 3 with 1 gap(s): 2" in printed.err


def test_no_filter_narrows_either_register_report(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Hiding is the failure mode, and a filter that quietly dropped the line
    would be that failure with the filter as its excuse. The filter here
    excludes the whole state whose register is short."""
    gapped(tree)
    unread(tree)
    capsys.readouterr()

    assert main(["list", "--state", "greenhouse", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["rows"] == []
    assert [one["number"] for one in payload["gaps"]] == [2]
    assert [one["text"] for one in payload["lost"]] == ["## Section 168: Something"]


def test_an_offer_carries_the_register_reports_too(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An offer narrows *rows* and narrows no report, so `next <verb>` says
    the register is short exactly as `list` does."""
    gapped(tree)
    unread(tree)
    capsys.readouterr()

    assert main(["next", "transplant", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [one["number"] for one in payload["gaps"]] == [2]
    assert len(payload["lost"]) == 1


def test_a_clean_register_carries_both_arrays_empty(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Present whenever the declaration mints at all, empty or not — the
    corpus-independence rule every other report keeps, so the shape a consumer
    writes against does not depend on what happens to be filed."""
    orchard(tree, "First tree")
    capsys.readouterr()

    assert main(["list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["gaps"] == [] and payload["lost"] == []

    assert main(["list"]) == 0
    err = capsys.readouterr().err
    assert "register gap" not in err and "lost close-out" not in err


def test_the_register_reaches_both_renderings(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The register itself, in both forms, on a corpus with nothing wrong. It
    is part of the frame rather than an eighth report, so the text line goes
    to stderr beside the counts and stdout stays the records alone."""
    orchard(tree, "First tree")
    capsys.readouterr()

    assert main(["list"]) == 0
    printed = capsys.readouterr()
    assert (
        "register orchard: floor 1, highest 2, in orchard-archive.md"
        in printed.err
    )
    assert "register orchard" not in printed.out

    assert main(["list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["register"] == [
        {
            "state": "orchard",
            "archive": "orchard-archive.md",
            "floor": 1,
            "highest": 2,
        }
    ]


def test_a_consumer_answers_is_n_a_section_from_the_envelope_alone(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The question the sub-phase exists for, asked the way a commit gate
    asks it. The archive holds 1, the trees minted 2 and 3, and the one
    holding 2 was deleted by hand. One `list --json` answers all four cases,
    with no second invocation and no parse of the archive."""
    gapped(tree)
    capsys.readouterr()

    assert main(["list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    (record,) = payload["register"]
    missing = {one["number"] for one in payload["gaps"]}

    def section(number: int) -> bool:
        return (
            record["floor"] <= number <= (record["highest"] or 0)
            and number not in missing
        )

    assert [section(one) for one in (1, 2, 3, 4)] == [True, False, True, False]


def unnumbered(tree: Path) -> None:
    """The same declaration with nothing numbered: the state stays, so every
    `from`/`to` still resolves and the capability is the only difference.

    `unclaimed`'s shape, and every half goes together because each alone
    refuses at load: the state's opt-in, the `archive` only a register reads,
    the `archives = true` on the two verbs that file an entry, and `bulleted`
    with the two fields that only a state which mints bullets may carry.
    `orchard`'s name form goes with them because it names `{number}`, which is
    a key an unnumbered state does not give, and its two dispositions lose
    their `marks` for the same reason the mint goes — a word written onto a
    bullet needs a state that has bullets, so `bulleted` cannot come off
    alone. The verbs themselves stay, halfless: an orchard → orchard edge that
    still resolves. `propagator` is left exactly as it is, and that is the
    point: it is bulleted, it is not numbered, and it goes on minting here.
    """
    plan = (tree / "plan.toml").read_text()
    (tree / "plan.toml").write_text(
        plan.replace(
            'capabilities      = ["queued", "numbered", "bulleted"]',
            'capabilities      = ["queued"]',
        )
        .replace('archive           = "orchard-archive.md"\n', "")
        .replace('sub-phase-name    = "{number}-{ordinal}"\n', "")
        .replace(
            'sub-phase-pending = "**unpruned — Say what the rest of the '
            'training is.**"\n',
            "",
        )
        .replace("archives = true\n", "")
        .replace("archives  = true\n", "")
        .replace("mints  = true\n", "")
        .replace('marks = "ripened"\n', "")
        .replace('marks = "thinned"\n', "")
    )


def test_a_declaration_with_no_numbered_state_carries_neither_report(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other half of the same rule: where nothing is numbered there is no
    register to be short of anything, so both arrays are absent rather than
    empty."""
    unnumbered(tree)
    orchard(tree, "First tree")
    capsys.readouterr()

    assert main(["list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "gaps" not in payload and "lost" not in payload


def test_a_declaration_with_no_numbered_state_carries_no_register(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Absent rather than an empty array, which is the rule `gaps` and `lost`
    keep one key over. One rule for the whole envelope beats a third rule
    inside it, and a consumer gating on the key gates once for all three."""
    unnumbered(tree)
    orchard(tree, "First tree")
    capsys.readouterr()

    assert main(["list", "--json"]) == 0
    assert "register" not in json.loads(capsys.readouterr().out)

    assert main(["list"]) == 0
    assert "register " not in capsys.readouterr().err


def test_a_number_is_not_a_handle(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Settled 2026-09-02 and not reopened by 4-5: an item is named by its
    slug and by nothing else. A number that resolved would be a second answer
    to "which item is this", and the two can disagree."""
    orchard(tree, "First tree")
    capsys.readouterr()
    assert main(["graft-on", "2"]) == 2
    assert "no item starts with" in capsys.readouterr().err


def test_a_number_as_a_handle_is_told_where_numbers_are_found(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Still not a handle, and now the refusal says where a number is found,
    each part on its own line under the `ERROR:` one."""
    orchard(tree, "First tree")
    capsys.readouterr()
    assert main(["show", "1-1"]) == 2
    headline, pointer = capsys.readouterr().err.strip().splitlines()
    assert headline == 'ERROR: no item starts with "1-1"'
    assert "`fileplan list --has number=N`" in pointer


@pytest.mark.parametrize(
    "argv, said",
    [
        pytest.param(["list", "orchard"], "did you mean --state orchard?", id="state"),
        pytest.param(
            ["next", "ripen", "--check"],
            "--check belongs to the command: fileplan ripen ITEM --check",
            id="check",
        ),
        pytest.param(["ripen"], "fileplan next ripen lists what it can take", id="item"),
        pytest.param(["show"], "fileplan list lists every item", id="show"),
    ],
)
def test_a_usage_error_points_at_the_documented_way_through(
    tree: Path, capsys: pytest.CaptureFixture[str], argv: list[str], said: str
) -> None:
    """Click's own refusal stays, and the line after it says where to go. A
    consumer's sessions hit `list plan` forty-odd times."""
    capsys.readouterr()
    assert main(argv) == 2
    err = capsys.readouterr().err
    assert "Error: " in err
    assert err.strip().splitlines()[-1] == said


def test_an_extra_argument_naming_no_state_gets_only_clicks_refusal(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The pointer is a fact about the declaration, so it is never a guess."""
    capsys.readouterr()
    assert main(["list", "226"]) == 2
    assert capsys.readouterr().err.strip().endswith("(226)")


def test_a_repeated_state_filter_refuses_by_name(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Click kept the last `--state` and dropped the first, silently."""
    capsys.readouterr()
    assert main(["list", "--state", "orchard", "--state", "greenhouse"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("ERROR: --state was given 2 times (orchard, greenhouse)")


def test_an_in_place_verb_leaves_the_order_alone(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """4-4's defect, end to end. `graft-on` is an in-place verb into the
    ordered state, and it is about the cursor — so a run of it must not move
    the item. Before the rule it appended past the last row, which is an order
    somebody set deliberately being destroyed by a verb about something
    else."""
    orchard(tree, "First tree")
    orchard(tree, "Second tree")
    orchard(tree, "Third tree")
    capsys.readouterr()

    assert main(["graft-on", "first-tree", "--graft-status", "open"]) == 0
    capsys.readouterr()
    assert main(["list", "--state", "orchard", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert [(row["slug"], row["position"]) for row in rows] == [
        ("first-tree", 100),
        ("second-tree", 200),
        ("third-tree", 300),
    ]


def test_an_in_place_verb_still_places_when_asked(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Staying put is the default, not a refusal to move: the three placement
    options are what `--at`-as-respacing-tool depends on, and they are
    untouched. Asked of `respace`, which is the same-state verb that places
    and does nothing else — 13-3 took the options off the same-state verbs
    that write something instead."""
    orchard(tree, "First tree")
    orchard(tree, "Second tree")
    capsys.readouterr()

    assert main(["respace", "first-tree", "--below", "second-tree"]) == 0
    capsys.readouterr()
    assert main(["list", "--state", "orchard", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert [(row["slug"], row["position"]) for row in rows] == [
        ("second-tree", 200),
        ("first-tree", 300),
    ]


def test_a_taken_place_refuses_with_the_operator_contract(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    orchard(tree, "First tree")
    capsys.readouterr()
    assert main(["sprout", "A wedge", "--body", "Prose.", "--cultivar", "heirloom"]) == 0
    capsys.readouterr()
    assert main(["transplant", "a-wedge", "--at", "100"]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err.startswith("ERROR: ")
    assert '100 is already held by "first-tree"' in printed.err


def test_the_control_holds_over_a_queued_state(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Ordering happens in the *traversal*, so both renderings get it. A
    renderer that sorted for itself would pass every other test here."""
    orchard(tree, "First tree")
    orchard(tree, "A wedge", "--at", "50")
    capsys.readouterr()

    main(["list", "--state", "orchard"])
    printed = capsys.readouterr().out.splitlines()

    main(["list", "--state", "orchard", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert render.records(payload["rows"]) == printed
    assert [row["slug"] for row in payload["rows"]] == ["a-wedge", "first-tree"]


def test_has_and_lacks_reach_a_capabilitys_key(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--has` asks about any key an item *carries*, which is intrinsic plus
    capability-given plus declared — not the declared list alone."""
    orchard(tree, "First tree")
    assert main(["sprout", "A seedling", "--body", "Prose."]) == 0
    capsys.readouterr()

    assert main(["list", "--has", "position", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert [row["slug"] for row in rows] == ["first-tree"]

    assert main(["list", "--lacks", "position", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert [row["slug"] for row in rows] == ["a-seedling"]


# --------------------------------------------------------------------------
# `release`: the command a capability generates, and the name it reserves
# --------------------------------------------------------------------------
#
# The fixture's `potting-bench` is the claimed state, and `bench` is the verb
# into it. Every test here sets `GREENHOUSE_PID`, the first name the fixture's
# `[identity]` declares: an identity with no pid is refused at the take.
#
# A **second session is written by hand** — a record carrying another pid or
# another host is exactly what a sibling session leaves behind.

#: This session, as the fixture reads it. The real pid, so `--json`-free
#: wording about what the probe found is deterministic.
MINE = os.getpid()

#: A pid that is certainly alive and certainly not this session's. `os.kill(1,
#: 0)` either succeeds or raises PermissionError, and both are "alive".
ANOTHER_LIVE_SESSION = 1


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch) -> str:
    """Who this session is, for the length of one test."""
    monkeypatch.setenv("GREENHOUSE_PID", str(MINE))
    monkeypatch.delenv("SPROUT_PID", raising=False)
    return socket.gethostname()


def unclaimed(tree: Path) -> None:
    """The same declaration with nothing claimed: the state stays, so every
    `from`/`to` still resolves and the capability is the only difference.

    Both halves go together — the state's opt-in and the `claims = true` on
    the verbs that take one — because either alone refuses at load.
    """
    plan = (tree / "plan.toml").read_text()
    (tree / "plan.toml").write_text(
        plan.replace('capabilities = ["claimed"]\n', "").replace(
            "claims = true\n", ""
        )
    )


def benched(tree: Path, title: str = "A seedling") -> str:
    """One item on the potting bench, claimed by this session and worked on.

    The `tend` is not decoration: it is the verb that claims the item, so
    without it the bench holds a seedling nobody has picked up.
    """
    assert main(["sprout", title, "--body", "Prose.", "--cultivar", "heirloom"]) == 0
    slug = title.lower().replace(" ", "-")
    assert main(["bench", slug]) == 0
    assert main(["tend", slug, "--rootstock", "M9"]) == 0
    return slug


def sibling(tree: Path, slug: str, *, pid: int, host: str | None = None) -> Path:
    path = claim.path(tree, slug)
    claim.write(
        path, {"host": host or socket.gethostname(), "pid": pid, "taken": TAKEN}
    )
    return path


def test_release_registers_only_where_a_state_claims_something(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The `--position` precedent: a capability generates what it needs and
    nothing else. This repo's own declaration has no claimed state, and its
    `--help` carries no `release` either."""
    assert main(["--help"]) == 0
    assert "release" in capsys.readouterr().out

    unclaimed(tree)
    assert main(["--help"]) == 0
    assert "release" not in capsys.readouterr().out


def test_a_declared_transition_named_release_refuses_by_name(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Reserved **unconditionally** — this declaration claims nothing, so the
    command is not even registered, and the name is still refused. Otherwise
    the same plan.toml would break the day it grew a claimed state."""
    unclaimed(tree)
    plan = (tree / "plan.toml").read_text()
    (tree / "plan.toml").write_text(
        plan.replace("[transitions.sprout]", "[transitions.release]")
    )
    (tree / "method.md").write_text(
        (tree / "method.md").read_text() + "\n## release\n"
    )
    assert main(["--help"]) == 2
    err = capsys.readouterr().err
    assert "transitions.release takes the name of the release" in err
    assert "one command cannot mean two things" in err


def test_a_transition_takes_no_option_for_a_claim(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A claim takes no argument: who holds it and since when are read, not
    typed. `bench` moves into the claimed state and carries nothing for it —
    unlike a transition into the ordered state, which carries three."""
    assert main(["bench", "--help"]) == 0
    out = capsys.readouterr().out
    assert "ITEM" in out
    assert "--claim" not in out and "--above" not in out


def test_release_frees_your_own_claim(
    tree: Path, session: str, capsys: pytest.CaptureFixture[str]
) -> None:
    slug = benched(tree)
    capsys.readouterr()
    assert main(["release", slug]) == 0
    assert f"released {slug}, held by {session} pid {MINE} (running)" in (
        capsys.readouterr().out
    )
    assert not claim.path(tree, slug).exists()


def test_release_frees_a_dead_sessions_claim_naming_whose_it_was(
    tree: Path, session: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """The crashed session, which is the case `release` exists for. It is
    named as it is freed — nothing is ever released quietly, or on its own."""
    slug = benched(tree)
    gone = exited()
    sibling(tree, slug, pid=gone)
    capsys.readouterr()

    assert main(["release", slug]) == 0
    out = capsys.readouterr().out
    assert f"pid {gone} (not running)" in out
    assert not claim.path(tree, slug).exists()


def test_release_refuses_a_live_sessions_claim(
    tree: Path, session: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """A claim is freed when its holder is gone, not to take an item off
    somebody."""
    slug = benched(tree)
    held = sibling(tree, slug, pid=ANOTHER_LIVE_SESSION).read_bytes()
    capsys.readouterr()

    assert main(["release", slug]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err.startswith("ERROR: ")
    assert f"pid {ANOTHER_LIVE_SESSION} (running)" in printed.err
    assert claim.path(tree, slug).read_bytes() == held


def test_release_refuses_a_claim_from_another_host_naming_the_record(
    tree: Path, session: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """This machine cannot probe that one, so a person there — or `rm` — is
    the only honest answer, and the refusal says which file."""
    slug = benched(tree)
    path = sibling(tree, slug, pid=MINE, host="another-host")
    capsys.readouterr()

    assert main(["release", slug]) == 2
    err = capsys.readouterr().err
    assert "another-host" in err and str(path) in err
    assert path.exists()


def test_release_on_an_item_holding_no_claim_refuses(
    tree: Path, session: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["sprout", "A seedling", "--body", "Prose."]) == 0
    capsys.readouterr()
    assert main(["release", "a-seedling"]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert "holds no claim" in printed.err


def test_release_takes_the_handle_like_every_other_command(
    tree: Path, session: str, capsys: pytest.CaptureFixture[str]
) -> None:
    slug = benched(tree)
    capsys.readouterr()
    assert main(["release", "a-see"]) == 0
    assert not claim.path(tree, slug).exists()


# --------------------------------------------------------------------------
# The done line: two sessions cannot work on one item
# --------------------------------------------------------------------------


def test_a_second_session_cannot_pick_up_a_claimed_item(
    tree: Path, session: str, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Concurrency end to end and in one test: this session claims an item
    by moving it into the claimed state, a second session's attempt to move it
    on refuses by name, and the holder's own completion frees the claim."""
    slug = benched(tree)
    assert claim.path(tree, slug).exists()
    capsys.readouterr()

    # The second session: the same tree, the same host, another pid.
    monkeypatch.setenv("GREENHOUSE_PID", str(ANOTHER_LIVE_SESSION))
    assert main(["bed-out", slug]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err.startswith("ERROR: ")
    assert f"pid {MINE} (running)" in printed.err
    assert (tree / "potting-bench" / f"{slug}.md").exists()

    # And the holder completes it, which is what drops the claim.
    monkeypatch.setenv("GREENHOUSE_PID", str(MINE))
    assert main(["bed-out", slug]) == 0
    assert (tree / "orchard" / f"{slug}.md").exists()
    assert not claim.path(tree, slug).exists()


def test_taking_a_claim_with_no_pid_set_refuses_by_name_end_to_end(
    tree: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The operator's contract on the refusal that decision 2 added: rc 2, one
    `ERROR:` line, nothing on stdout, and the names to export. It is the
    *claiming* verb that needs a pid — `bench` moves in and takes nothing, so
    it runs without one, and `tend` is where the refusal lives."""
    monkeypatch.setenv("GREENHOUSE_PID", str(MINE))
    assert main(["sprout", "A seedling", "--body", "Prose."]) == 0
    assert main(["bench", "a-seedling"]) == 0
    before = (tree / "potting-bench" / "a-seedling.md").read_bytes()
    for name in ("GREENHOUSE_PID", "SPROUT_PID"):
        monkeypatch.delenv(name, raising=False)
    capsys.readouterr()

    assert main(["tend", "a-seedling"]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert "GREENHOUSE_PID, SPROUT_PID" in printed.err
    assert (tree / "potting-bench" / "a-seedling.md").read_bytes() == before
    assert not claim.path(tree, "a-seedling").exists()


# --------------------------------------------------------------------------
# The reads: which items are claimed, and by whom
# --------------------------------------------------------------------------


def test_the_claims_filters_register_only_where_a_state_claims(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The `--position` precedent, over fields read from outside the item
    file: given by the capability, and absent from the `--has` roster entirely
    where no state opts in. Since 13-3 the roster is where a key is offered —
    there is no option named after one — so this is the same control read one
    surface over."""
    assert main(["list", "--help"]) == 0
    out = capsys.readouterr().out
    assert claim.BY in out and claim.STATUS in out

    unclaimed(tree)
    assert main(["list", "--help"]) == 0
    out = capsys.readouterr().out
    assert claim.BY not in out and claim.STATUS not in out


def test_the_listing_names_the_holder_under_the_item(
    tree: Path, session: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """The done line's second half: one read shows every state's items and
    which are claimed, by whom."""
    slug = benched(tree)
    capsys.readouterr()

    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert f"claimed-by    {session} pid {MINE}" in out
    assert f"claim-status  {claim.ALIVE}" in out


def test_a_second_session_is_not_offered_claimed_work(
    tree: Path, session: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """**Section 2's done line**, end to end: with one item claimed, the pick
    read does not offer it. Until section 3 spells that read as `next`, it is
    `--lacks claimed-by` — and `--claim-status dead` is the other half, what
    needs releasing."""
    claimed = benched(tree, "A seedling")
    free = benched(tree, "Another seedling")
    assert main(["bed-out", free]) == 0  # out of the claimed state, so unheld
    capsys.readouterr()

    assert main(["list", "--lacks", "claimed-by", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert [row["slug"] for row in rows] == [free]

    assert main(["list", "--has", "claimed-by", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert [row["slug"] for row in rows] == [claimed]


def test_arriving_in_a_claimed_state_leaves_the_item_on_offer(
    tree: Path, session: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """**4-4's reason for existing**, in the fixture's vocabulary: `bench`
    moves an item into the claimed state and claims nothing, so the pick read
    still offers it.

    This repo's `queue` is the same shape — it commits an idea to `plan`,
    which claims. Under claim-on-entry every freshly-queued item would have
    been stamped in the queueing session's name and never released, which is
    what forced the claim onto the verb. Pinned here rather than against this
    repo's own declaration, for the reason the whole suite runs on the
    fixture."""
    assert main(["sprout", "A seedling", "--body", "Prose."]) == 0
    assert main(["bench", "a-seedling"]) == 0
    capsys.readouterr()

    assert not claim.path(tree, "a-seedling").exists()
    assert main(["list", "--lacks", "claimed-by", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert "a-seedling" in [row["slug"] for row in rows]


def test_two_sessions_divide_the_work_and_neither_item_moves(
    tree: Path, session: str, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """**4-4's done line**, end to end: two sessions' pick reads return
    disjoint items, the second's attempt on a held one refuses naming the
    holder, `release` frees it — and nothing ever left the state it was
    claimed in. The claim is on the item where it stands, which is the whole
    point of moving it off arrival."""
    for title in ("A seedling", "Another seedling"):
        assert main(["sprout", title, "--body", "Prose."]) == 0
        assert main(["bench", title.lower().replace(" ", "-")]) == 0
    assert main(["tend", "a-seedling"]) == 0
    capsys.readouterr()

    # This session sees only what it does not hold; the other item is free.
    assert main(["list", "--state", "potting-bench", "--lacks", "claimed-by", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert [row["slug"] for row in rows] == ["another-seedling"]

    # A second session: the same tree, the same host, another pid. Its pick
    # read offers the other item, and taking up this one refuses by name.
    monkeypatch.setenv("GREENHOUSE_PID", str(ANOTHER_LIVE_SESSION))
    assert main(["tend", "a-seedling"]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err.startswith("ERROR: ")
    assert f"pid {MINE} (running)" in printed.err
    assert main(["tend", "another-seedling"]) == 0
    capsys.readouterr()

    # The holder ends its session, and the item is on offer again — still in
    # the state it was claimed in, which it never left.
    monkeypatch.setenv("GREENHOUSE_PID", str(MINE))
    assert main(["release", "a-seedling"]) == 0
    capsys.readouterr()
    assert main(["list", "--state", "potting-bench", "--lacks", "claimed-by", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert [row["slug"] for row in rows] == ["a-seedling"]
    assert (tree / "potting-bench" / "a-seedling.md").exists()


def test_a_dead_claim_is_reported_by_name_and_found_by_its_status(
    tree: Path, session: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """**Section 2's third done line.** The crashed session's claim is named
    by the listing rather than freed behind anybody's back, and the filter
    that finds it is what a person runs before `release`."""
    live = benched(tree, "A seedling")
    dead = benched(tree, "Another seedling")
    gone = exited()
    sibling(tree, dead, pid=gone)
    capsys.readouterr()

    assert main(["list", "--has", f"claim-status={claim.DEAD}", "--json"]) == 0
    (row,) = json.loads(capsys.readouterr().out)["rows"]
    assert row["slug"] == dead
    assert row["claimed-by"] == f"{session} pid {gone}"

    assert main(["list", "--has", f"claim-status={claim.ALIVE}", "--json"]) == 0
    (row,) = json.loads(capsys.readouterr().out)["rows"]
    assert row["slug"] == live


def test_an_unclaimed_item_carries_both_fields_as_null(
    tree: Path, session: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """`null`, not absent, and on an item in an unclaimed state too: the shape
    depends on the declaration, never on the corpus."""
    assert main(["sprout", "A seedling", "--body", "Prose."]) == 0
    capsys.readouterr()
    assert main(["list", "--json"]) == 0
    (row,) = json.loads(capsys.readouterr().out)["rows"]
    assert row["claimed-by"] is None and row["claim-status"] is None


def test_the_control_holds_with_the_claims_fields(
    tree: Path, session: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """**The control**, over a row carrying a fact from outside the item file.
    The claim is read once, in the one traversal, and both renderings come off
    the rows it produced — a second read beside the text form would pass every
    other test here and fail this one."""
    benched(tree, "A seedling")
    assert main(["sprout", "Another seedling", "--body", "Prose."]) == 0
    capsys.readouterr()

    main(["list"])
    printed = capsys.readouterr().out.splitlines()

    main(["list", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert render.records(payload["rows"]) == printed
    assert any(row["claimed-by"] for row in payload["rows"])


def test_a_stranded_claim_is_named_in_both_renderings(
    tree: Path, session: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """A record whose item is gone is a leftover a person resolves, so it is
    reported rather than skipped — and it is not a row, so no filter narrows
    it away: it goes to stderr beside the counts, and into the envelope where
    the counts already live."""
    benched(tree)
    sibling(tree, "ghost-seedling", pid=ANOTHER_LIVE_SESSION)
    capsys.readouterr()

    assert main(["list"]) == 0
    printed = capsys.readouterr()
    assert "ghost-seedling" not in printed.out
    assert "stranded claim: ghost-seedling" in printed.err
    assert "local/claims/ghost-seedling.toml" in printed.err

    assert main(["list", "--state", "greenhouse", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["rows"] == []
    (one,) = payload["stranded"]
    assert one["slug"] == "ghost-seedling"
    assert one["claim-status"] == claim.ALIVE


def test_the_stranded_array_is_present_wherever_the_declaration_claims(
    tree: Path, session: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Empty rather than missing, so a consumer's shape does not depend on the
    corpus — and gone entirely where nothing claims, because there is then
    nothing that could strand."""
    assert main(["list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["stranded"] == []

    unclaimed(tree)
    assert main(["list", "--json"]) == 0
    assert "stranded" not in json.loads(capsys.readouterr().out)


def test_a_claim_status_the_probe_never_answers_refuses_by_name(
    tree: Path, session: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--state zzz`'s rule, over the probe's closed set."""
    assert main(["list", "--has", "claim-status=zzz"]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert "zzz" in printed.err
    assert ", ".join(claim.STATUSES) in printed.err


def test_a_malformed_claim_record_refuses_the_listing_with_no_json(
    tree: Path, session: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """The operator's contract on the asymmetry: a *missing* record reads as
    unclaimed, and one that cannot be read refuses — rc 2, one `ERROR:` line,
    and no JSON for a consumer to mistake for an empty tree."""
    benched(tree)
    path = claim.path(tree, "a-seedling")
    path.write_text("pid = 4213\n")
    capsys.readouterr()

    assert main(["list", "--json"]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err.startswith("ERROR: ")
    assert str(path.relative_to(tree)) in printed.err


def test_this_repo_claims_its_own_work_so_its_listing_carries_the_holder(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """**Supersedes `…_declares_no_claimed_state_so_its_listing_is_unchanged`**,
    which asserted the opposite through 2-2, 4-2 and 4-3. 4-4 is where this
    repo adopts the capability, so its own listing gains the two fields and
    the `stranded` report — the fields are still generated by the capability
    rather than by the tool, and this is the same proof read the other way
    round. The behavioural half stays graded against `tests/fixtures/`."""
    monkeypatch.setenv("FILEPLAN_PLAN_TOML", str(REPO / "plan.toml"))
    monkeypatch.chdir(REPO)
    assert main(["list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "stranded" in payload
    if not payload["rows"]:
        # Empty is the ordinary shape in a clone of the published tree, which
        # ships with no items, so the missing haystack is skipped rather than
        # failed. The tree this suite was written in has its own control that
        # the rows are there, so the skip cannot go quiet unnoticed.
        pytest.skip("the listing has no rows, so there is no holder to carry")
    for row in payload["rows"]:
        assert "claimed-by" in row and "claim-status" in row


# --------------------------------------------------------------------------
# `archives`: the entry that outlives the file
# --------------------------------------------------------------------------
#
# `grub-out` is the fixture's archiving verb, out of `orchard` — the numbered
# state — and into `firewood`. It is not this repo's `decline` and does not
# leave this repo's `plan`, which is the point: the flexibility John asked for
# is that any state can declare a verb of this shape.


def archived(tree: Path) -> str:
    return (tree / "orchard-archive.md").read_text()


def claimable(tree: Path) -> None:
    """The same declaration with the *numbered* state claimed as well.

    The shared fixture keeps `numbered` and `claimed` on separate states, so
    that each is graded without the other. This repo's own `plan` carries
    both, and the one question that needs them together is what an archiving
    verb does when somebody else holds the item — so the declaration is
    amended here rather than in the fixture, which is `unclaimed`'s precedent
    read the other way round.
    """
    plan = (tree / "plan.toml").read_text().replace(
        'capabilities      = ["queued", "numbered", "bulleted"]',
        'capabilities      = ["queued", "numbered", "bulleted", "claimed"]',
    )
    (tree / "plan.toml").write_text(
        plan
        + '\n[transitions.pick]\ndoc  = "method.md#pick"\n'
        'help = "Take up a tree."\nfrom = "orchard"\nto   = "orchard"\n'
        "claims = true\n"
    )
    method = tree / "method.md"
    method.write_text(method.read_text() + "\n## pick\n")


def test_an_archiving_verb_files_its_entry_and_says_so(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole run, from the command line: the item moves, the entry lands
    under the number it carried, the path is on stdout and the notice — what
    was minted, and that a record goes under it — is on stderr where a pipe
    does not carry it."""
    orchard(tree, "First tree")
    capsys.readouterr()

    assert main(["grub-out", "first-tree"]) == 0
    printed = capsys.readouterr()
    assert printed.out.strip() == "firewood/first-tree.md"
    assert "## 2. First tree" in printed.err
    assert "## 2. First tree" in archived(tree)
    assert (tree / "firewood" / "first-tree.md").exists()


def test_the_number_outlives_the_file_end_to_end(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**The load-bearing check.** Delete the abandoned file — which the state
    exists to make safe — and the register is unchanged, so the next commitment
    mints past it rather than over it."""
    orchard(tree, "First tree")
    assert main(["grub-out", "first-tree"]) == 0
    (tree / "firewood" / "first-tree.md").unlink()

    orchard(tree, "Second tree")
    capsys.readouterr()
    assert main(["show", "second-tree", "--json"]) == 0
    (row,) = json.loads(capsys.readouterr().out)["rows"]
    assert row["number"] == 3


def test_the_archiving_verb_has_a_next_read_like_any_other(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Generated from the declaration, so a listing is named by the verb that
    would act on it — no report flag, and no verb name in the CLI."""
    orchard(tree, "First tree")
    orchard(tree, "Second tree", "--at", "200")
    assert offered(capsys, "grub-out") == ["first-tree", "second-tree"]


def test_an_edge_to_an_abandoned_item_blocks_rather_than_reading_as_unknown(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The reason this verb **moves** rather than dissolving. The item keeps a
    file, so it keeps a slug: an item waiting on it is *blocked*, not pointing
    at nothing. It is not misordered either — it has no place any more, and a
    place it does not have cannot be later than anything."""
    orchard(tree, "First tree")
    orchard(tree, "Second tree", "--at", "200")
    waits(tree, "second-tree", "first-tree")
    assert main(["grub-out", "first-tree"]) == 0
    capsys.readouterr()

    assert main(["list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    blocked = {row["slug"]: row["blocked-by"] for row in payload["rows"]}
    assert blocked["second-tree"] == ["first-tree"]
    assert payload["unknown"] == [] and payload["misordered"] == []


def test_a_claim_another_session_holds_refuses_and_touches_neither_file(
    tree: Path, session: str, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """"This is not yours" is prior to everything else, and it is answered
    before the archive is so much as read: rc 2, one `ERROR:` line, nothing on
    stdout, the item where it was and the archive byte for byte."""
    claimable(tree)
    orchard(tree, "First tree")
    assert main(["pick", "first-tree"]) == 0
    before, document = (tree / "orchard" / "first-tree.md").read_bytes(), archived(tree)
    capsys.readouterr()

    monkeypatch.setenv("GREENHOUSE_PID", str(ANOTHER_LIVE_SESSION))
    assert main(["grub-out", "first-tree"]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err.count("ERROR: ") == 1
    assert f"pid {MINE} (running)" in printed.err
    assert (tree / "orchard" / "first-tree.md").read_bytes() == before
    assert archived(tree) == document
    assert not (tree / "firewood" / "first-tree.md").exists()


def test_the_holder_files_it_and_the_claim_is_freed(
    tree: Path, session: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other half: the claim drops on the way out, because `firewood`
    claims nothing — the capability's own rule, with no verb declaring it."""
    claimable(tree)
    orchard(tree, "First tree")
    assert main(["pick", "first-tree"]) == 0
    assert claim.path(tree, "first-tree").exists()

    assert main(["grub-out", "first-tree"]) == 0
    assert not claim.path(tree, "first-tree").exists()
    assert "## 2. First tree" in archived(tree)


# --------------------------------------------------------------------------
# The control: no per-verb code exists
# --------------------------------------------------------------------------


def code_only(source: str) -> str:
    """``source`` with its comments and docstrings removed — the code alone.

    Prose is what a module says *about* itself; code is what runs. A string
    that opens a logical line is a docstring, and everything else — including
    a string literal in an expression, which is exactly how a verb would be
    special-cased — survives untouched.
    """
    kept: list[str] = []
    opening = True
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            continue
        if token.type == tokenize.STRING and opening:
            continue
        if token.type not in _LAYOUT:
            kept.append(token.string)
        if token.type not in (tokenize.COMMENT,):
            opening = token.type in _LAYOUT
    return "\n".join(kept)


#: Tokens that carry no code: line breaks, indentation, and the file's ends.
#: A token after one of these opens a logical line, which is what makes a
#: string a docstring.
_LAYOUT = frozenset(
    {
        tokenize.NEWLINE,
        tokenize.NL,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.ENCODING,
        tokenize.ENDMARKER,
    }
)


# --------------------------------------------------------------------------
# The control: no ident is recognised in prose
# --------------------------------------------------------------------------

#: One line of the prose a tool that guessed would go looking in, carrying an
#: ident of **both** shapes this repo declares: a sub-phase off a register and
#: a finding off nothing but its ordinal. It is deliberately a sentence rather
#: than a bullet — the strict form is *meant* to be read, and this is what a
#: reader must not reach into.
PROSE = "Carried → 22-3 and f4 were filed as slug-name on 2026-09-05."

#: What an ident of either shape looks like, for asking whether a match caught
#: one. Written here and nowhere in ``src/``, which is the whole point.
AN_IDENT = re.compile(r"\d+-\d+|\bf\d+\b")


def patterns() -> list[tuple[Path, str]]:
    """Every regex ``src/`` builds, as (file, pattern). Read with `ast`.

    Both spellings, because the tool uses both: `re.compile` for the
    module-level constants, and `re.sub` inline — `item.py` and
    `declaration.py` between them hold six of the latter, so a walk that
    looked only for `compile` would grade two thirds of the tree.
    """
    found: list[tuple[Path, str]] = []
    for path in (REPO / "src").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Call):
                continue
            call = node.func
            if not (isinstance(call, ast.Attribute) and isinstance(call.value, ast.Name)):
                continue
            if call.value.id != "re" or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                found.append((path, first.value))
    return found


def test_no_regex_anywhere_under_src_reads_an_ident_out_of_prose() -> None:
    """**7-1's control.** The draft's rule, mechanically: idents are minted and
    referenced as *data*, never recognised in prose with a regex.

    The distinction it draws is the one that matters. Reading a name out of the
    **strict form** — a mechanically written shape whose writer and reader are
    the same module — is fine, and is what `NAMED` does: it is anchored at `^`
    and matches a bullet the tool wrote. Finding an ident by **pattern in
    running prose** is what this refuses, because a tool that scanned bodies
    for a digit-hyphen-digit run would turn a date, a version and a page range
    into
    references, and would silently stop finding `f4` the moment a workflow
    declared a form the pattern did not know.

    Every pattern in the tree is searched against one line of prose carrying
    an ident of both shapes, and each must either miss or match something that
    is not an ident. Today all of them miss with room to spare — `NAME_END`
    matches a space, and `ORDINAL`, `BULLET`, `NAMED` and `HEADING` are
    anchored — so this is a tripwire rather than a boundary the tree is
    pressed against.
    """
    built = patterns()
    assert built, "no regex was found under src/, so this control proves nothing"
    for path, pattern in built:
        found = re.search(pattern, PROSE)
        assert found is None or not AN_IDENT.search(found.group(0)), (
            str(path),
            pattern,
        )


def test_the_ident_control_catches_a_regex_that_reads_one_out_of_prose() -> None:
    """The mutation check. A hand-written pattern of exactly the shape the
    control exists to catch really does find `22-3` in that line, and the
    assertion really does fail on it — so a passing run above is the tree
    being clean rather than the prose being unreachable."""
    found = re.search(r"\b\d+-\d+\b", PROSE)
    assert found is not None and AN_IDENT.search(found.group(0))
    assert found.group(0) == "22-3"


def test_the_ident_control_reaches_the_inline_calls_compile_would_miss() -> None:
    """The mutation check on the *walk*. `re.compile` alone would grade only
    the module-level constants, and the tree really does build patterns the
    other way — so the walk is checked against both spellings rather than
    asserted to cover them."""
    built = patterns()
    modules = {path.name for path, _ in built}
    assert {"subphase.py", "item.py", "declaration.py"} <= modules
    inline = [
        pattern
        for path, pattern in built
        if path.name in ("item.py", "declaration.py")
    ]
    assert inline, "no inline re.* call was found, so the walk proves nothing"


# --------------------------------------------------------------------------
# `bulleted`: the capability that writes the body
# --------------------------------------------------------------------------

#: The fixture's pending bullet, as `orchard` declares it.
UNPRUNED = "**unpruned — Say what the rest of the training is.**"


#: The `propagator`'s, as that state declares it. The second bulleted state
#: exists to prove the name form is the state's business, so its vocabulary is
#: its own down to the marker.
UNSTRUCK = "**unstruck — Say what the rest of the batch is.**"


def test_a_state_with_no_register_names_its_bullets_off_its_own_form(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**7-1's done line, end to end.** `propagator` is `bulleted` and nothing
    else — no `numbered`, so no number, so no `<number>-` to name a bullet
    from. Its form is `c{ordinal}`, and what the mint writes is `c1` then
    `c2`: no separator the tool supplied, and no register it did not have."""
    assert main(["strike", "A batch of cuttings", "--body", "Prose."]) == 0
    capsys.readouterr()
    path = tree / "propagator" / "a-batch-of-cuttings.md"

    assert main(["mist", "a-batch", "--title", "Bottom heat"]) == 0
    assert main(["mist", "a-batch", "--title", "Rooting hormone"]) == 0
    capsys.readouterr()
    body = path.read_text()
    assert "- **c1 — Bottom heat**" in body
    assert "- **c2 — Rooting hormone**" in body
    assert f"- {UNSTRUCK}" in body


def test_the_bullets_of_a_state_with_no_register_are_counted_like_any_other(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """And the readers beside the writer agree, which is the whole reason the
    form lives next to `next_ordinal`: the same count and the same names come
    back out of a state whose bullets are named nothing like this repo's."""
    assert main(["strike", "A batch of cuttings", "--body", "Prose."]) == 0
    assert main(["mist", "a-batch", "--title", "Bottom heat", "--last"]) == 0
    capsys.readouterr()

    assert main(["list", "--state", "propagator", "--json"]) == 0
    (row,) = json.loads(capsys.readouterr().out)["rows"]
    assert row["sub-phases"] == 1
    # The row's shape is the *declaration's*, so the key is there — carried by
    # the state that mints one, empty for the state that does not. That the
    # bullets were counted anyway is the half this state proves.
    assert row["number"] is None


def test_a_verb_that_mints_carries_the_minting_options(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Generated by the capability, the way the placement options are — but
    asked of the *transition*, because writing a body is something a verb opts
    into rather than something arriving does."""
    assert main(["espalier", "--help"]) == 0
    out = capsys.readouterr().out
    assert "--title" in out and "--last" in out


def test_a_verb_into_the_same_state_that_mints_nothing_carries_neither(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`graft-on` is an in-place verb into the same `bulleted` state. Without
    `mints` it carries no option, which is the whole point of the opt-in:
    otherwise every verb into the state could cut a section up."""
    assert main(["graft-on", "--help"]) == 0
    out = capsys.readouterr().out
    assert "--title" not in out and "--last" not in out


def test_a_sets_key_colliding_with_a_minting_option_refuses_by_name(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The `--body` and `--above` precedent, unchanged. Graded through
    `--last`, because `--title` cannot reach this guard: `title` is intrinsic
    to every item, so `sets = ["title"]` refuses one layer earlier, back in
    `plan.toml`. The guard covers both anyway rather than singling one out —
    a rule with an exception is a rule somebody has to remember."""
    plan = (tree / "plan.toml").read_text().replace(
        "mints  = true", 'mints  = true\nsets   = ["last"]'
    )
    (tree / "plan.toml").write_text(plan + '\n[keys.last]\ndoc = "method.md#tag"\n')
    assert main(["--help"]) == 2
    err = capsys.readouterr().err
    assert 'transitions.espalier.sets names "last"' in err
    assert "One option cannot mean two things" in err


def test_a_sets_key_naming_the_title_refuses_one_layer_earlier(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other half, stated so nobody reads the guard above as the only
    thing standing between `--title` and the positional."""
    plan = (tree / "plan.toml").read_text().replace(
        "mints  = true", 'mints  = true\nsets   = ["title"]'
    )
    (tree / "plan.toml").write_text(plan)
    assert main(["--help"]) == 2
    assert "which is intrinsic to every item" in capsys.readouterr().err


def test_opening_a_decomposition_writes_the_heading_and_the_pending_bullet(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The first done line, end to end: an item that had neither gets both,
    and nothing else in the body changes."""
    orchard(tree, "First tree")
    path = tree / "orchard" / "first-tree.md"
    was = path.read_text()
    capsys.readouterr()

    assert main(["espalier", "first-tree"]) == 0
    assert capsys.readouterr().err == ""
    assert path.read_text() == was.rstrip("\n") + f"\n\n### Steps\n- {UNPRUNED}\n"


def test_a_minted_bullet_is_counted_and_pointable_at_with_no_hand_editing(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The done line that matters most. What the mint writes is what 4-1
    counts and what 4-3 lets a cursor point at, because all three are the one
    strict form in the one module — and nothing here touches the file."""
    orchard(tree, "First tree")
    assert main(["espalier", "first-tree", "--title", "The register"]) == 0
    capsys.readouterr()

    assert main(["list", "--state", "orchard", "--json"]) == 0
    (row,) = json.loads(capsys.readouterr().out)["rows"]
    # The register already holds 1 (a closed tree in `orchard-archive.md`), so
    # this tree is 2 and its first step is `2-1`.
    assert row["number"] == 2
    assert row["sub-phases"] == 2

    assert main(["graft-on", "first-tree", "--graft", "2-1"]) == 0
    capsys.readouterr()
    assert main(["list", "--state", "orchard", "--json"]) == 0
    (row,) = json.loads(capsys.readouterr().out)["rows"]
    assert row["graft"] == "2-1"


def test_a_decomposition_runs_open_mint_mint_close_and_re_open(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole cycle in one place, in the order a session runs it."""
    orchard(tree, "First tree")
    path = tree / "orchard" / "first-tree.md"

    assert main(["espalier", "first-tree"]) == 0
    assert main(["espalier", "first-tree", "--title", "The register"]) == 0
    assert main(["espalier", "first-tree", "--title", "The bullet"]) == 0
    capsys.readouterr()
    assert path.read_text().endswith(
        "### Steps\n"
        "- **2-1 — The register**\n"
        "- **2-2 — The bullet**\n"
        f"- {UNPRUNED}\n"
    )

    assert main(["espalier", "first-tree", "--last"]) == 0
    assert capsys.readouterr().err == ""
    assert path.read_text().endswith(
        "### Steps\n- **2-1 — The register**\n- **2-2 — The bullet**\n"
    )

    # And minting again re-opens it, rather than refusing.
    assert main(["espalier", "first-tree", "--title", "One more"]) == 0
    printed = capsys.readouterr()
    assert "re-opens it" in printed.err
    assert "re-opens it" not in printed.out
    assert path.read_text().endswith(
        "- **2-3 — One more**\n" f"- {UNPRUNED}\n"
    )


def test_a_decomposition_stopped_half_way_goes_on_reading_as_pending(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """John's decision 2, 2026-09-03: no row field and no third exception
    report. The pending bullet **counts** like any other, so an opened section
    reads 1 rather than 0 and leaves the started-but-not-decomposed report the
    moment it is opened — the bullet is the signal, and a cursor reaching it is
    what surfaces it in a read."""
    orchard(tree, "First tree")
    assert main(["graft-on", "first-tree", "--graft-status", "open"]) == 0
    capsys.readouterr()
    assert main(["list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["undecomposed"] == ["first-tree"]

    assert main(["espalier", "first-tree"]) == 0
    capsys.readouterr()
    assert main(["list", "--state", "orchard", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["undecomposed"] == []
    (row,) = payload["rows"]
    assert row["sub-phases"] == 1

    # And the pending bullet is a sub-phase like any other, so a cursor may
    # point at it — which is how 4-7 will walk to an unfinished decomposition.
    assert main(["graft-on", "first-tree", "--graft", "unpruned"]) == 0


def test_a_title_that_would_break_the_strict_form_refuses_and_writes_nothing(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """rc 2, one ERROR: line on stderr, nothing on stdout, source untouched."""
    orchard(tree, "First tree")
    path = tree / "orchard" / "first-tree.md"
    assert main(["espalier", "first-tree"]) == 0
    before = path.read_bytes()
    capsys.readouterr()

    assert main(["espalier", "first-tree", "--title", "A **bold** one"]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err.startswith("ERROR: ")
    assert 'carries "**"' in printed.err
    assert path.read_bytes() == before


# --------------------------------------------------------------------------
# `next VERB`: the read named by the verb
# --------------------------------------------------------------------------
#
# Section 3's first sub-phase, and the whole of the old tool's middle tier of
# named report flags. The fixture divides the work: `transplant` has both
# `requires` and `refuses`, so a precondition has something to fail; `tend` is
# the in-place verb on the claimed bench, so the claim rule has somewhere to
# be true; and `sprout` and `pot-up` create, so there is a verb nothing can
# ever be next for.

#: What the fixture declares that *moves* an item, and what merely creates
#: one. Read off the declaration rather than listed here — a verb added to the
#: fixture later is covered without anyone remembering this.
def moving(tree: Path) -> list[str]:
    return [
        name
        for name, transition in load(tree / "plan.toml").transitions.items()
        if transition.source is not None
    ]


def creating(tree: Path) -> list[str]:
    return [
        name
        for name, transition in load(tree / "plan.toml").transitions.items()
        if transition.source is None
    ]


def greenhoused(cultivar: str | None, title: str) -> str:
    """One seedling in the greenhouse, with or without a cultivar."""
    argv = ["sprout", title, "--body", "Prose."]
    if cultivar is not None:
        argv += ["--cultivar", cultivar]
    assert main(argv) == 0
    return title.lower().replace(" ", "-")


def offered(capsys: pytest.CaptureFixture[str], *argv: str) -> list[str]:
    capsys.readouterr()
    assert main(["next", *argv, "--json"]) == 0
    return [row["slug"] for row in json.loads(capsys.readouterr().out)["rows"]]


def test_every_declared_transition_that_moves_an_item_has_a_next_read(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One subcommand per verb that moves, in declared order and carrying that
    verb's own help — generated from `plan.toml`, so no verb's name is written
    in the CLI and a workflow with other words gets other subcommands."""
    assert main(["next", "--help"]) == 0
    out = capsys.readouterr().out
    for name in moving(tree):
        assert name in out
    for name in creating(tree):
        assert name not in out
    assert out.index("transplant") < out.index("harvest")


def test_a_verb_this_declaration_does_not_have_refuses_by_name(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """click's own answer is `No such command`. The refusal names what is
    available instead, which is the declaration's vocabulary rather than
    click's."""
    assert main(["next", "frobnicate"]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err.startswith("ERROR: ")
    assert "frobnicate is not a declared transition" in printed.err
    for name in moving(tree):
        assert name in printed.err


def test_a_creating_transition_has_no_next_and_says_why(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The interesting half of the refusal, and the polarity that fails loud: an
    always-empty offer would read as "nothing is ready", where the truth is
    that the question does not apply. `sprout` is a declared verb — this is
    not a typo being caught."""
    assert "sprout" in load(tree / "plan.toml").transitions
    assert main(["next", "sprout"]) == 2
    err = capsys.readouterr().err
    assert "sprout creates an item rather than moving one" in err


def test_an_item_failing_a_precondition_is_absent_and_a_satisfied_one_is_present(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`transplant` requires a cultivar and refuses `hybrid`, so the three
    seedlings divide between the two halves of the same rule. No new
    precondition logic was written for this: it is `offer_errors`, which
    the verb itself runs."""
    ready = greenhoused("heirloom", "A seedling")
    greenhoused(None, "B seedling")
    greenhoused("hybrid", "C seedling")
    assert offered(capsys, "transplant") == [ready]


def test_a_section_another_session_holds_is_not_offered(
    tree: Path, session: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Concurrency through the read this time: a sibling's record is
    written by hand, because that is what a sibling leaves behind."""
    assert main(["sprout", "A seedling", "--body", "Prose."]) == 0
    assert main(["sprout", "B seedling", "--body", "Prose."]) == 0
    assert main(["bench", "a-seedling"]) == 0
    assert main(["bench", "b-seedling"]) == 0
    sibling(tree, "a-seedling", pid=ANOTHER_LIVE_SESSION)
    assert offered(capsys, "tend") == ["b-seedling"]


def test_a_section_this_session_holds_is_offered_because_work_would_take_it(
    tree: Path, session: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Decision 1, and the pair of the test above it. The offer is what the
    verb would **not refuse** — and a verb keeps a claim this session already
    holds rather than re-stamping it — so the item picked up yesterday is
    still what `next` hands back today. `--lacks claimed-by` is how the
    stricter question is asked, and the two answers differ here on purpose."""
    slug = benched(tree, "A seedling")
    assert claim.path(tree, slug).exists()
    assert offered(capsys, "tend") == [slug]
    # The verb agrees: it takes the item the read offered.
    assert main(["tend", slug, "--rootstock", "M9"]) == 0

    capsys.readouterr()
    assert main(["list", "--lacks", "claimed-by", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert slug not in [row["slug"] for row in rows]


def test_the_offer_is_one_traversal_in_two_renderings(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**The control**, over the second read. It holds by construction rather
    than by agreement: `next` is `list`'s own parameters and `list`'s own body
    with one predicate handed to the traversal, so there is one call to each
    renderer in the package."""
    greenhoused("heirloom", "A seedling")
    greenhoused("heirloom", "B seedling")
    greenhoused(None, "C seedling")
    capsys.readouterr()

    main(["next", "transplant"])
    printed = capsys.readouterr()

    main(["next", "transplant", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert render.records(payload["rows"]) == printed.out.splitlines()
    # The frame counts off the traversal, not off the offer: two of three,
    # never "2 of 2", which would hide the seedling that cannot go.
    assert "2 of 3 items" in printed.err
    assert payload["matched"] == 2 and payload["read"] == 3


# --------------------------------------------------------------------------
# A disposition's offer: the traversal's second row kind
# --------------------------------------------------------------------------
#
# `pot-on` marks into `propagator`, so its offer lists **cuttings** rather
# than batches. `orchard`'s `Steps` are deliberately left unmarked by
# anything, which is what makes "walked is the whole traversal's bullets"
# something a test can see rather than an assertion about intent.


def cuttings(*titles: str, close: bool = True) -> None:
    """One batch under mist, with a cutting minted for each title given."""
    assert main(["strike", "A batch", "--body", "Prose."]) == 0
    for number, title in enumerate(titles):
        last = ["--last"] if close and number == len(titles) - 1 else []
        assert main(["mist", "a-batch", "--title", title, *last]) == 0


def test_a_dispositions_offer_is_one_traversal_in_two_renderings(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**The control, over the second row kind.** The same property and the
    same means: one traversal, one call to each renderer, and the JSON rows
    rendered back through the record renderer must be what the text run
    printed. A bullet renderer beside the item one would fail exactly here."""
    cuttings("The first", "The second")
    capsys.readouterr()

    main(["next", "pot-on"])
    printed = capsys.readouterr()

    main(["next", "pot-on", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert render.records(payload["rows"], heading=render.BULLET_HEADING) == (
        printed.out.splitlines()
    )
    assert [row["name"] for row in payload["rows"]] == ["c1", "c2"]


def test_a_finding_row_carries_the_bullet_and_the_item_holding_it(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A row is not an item: it heads with the bullet's name and the item,
    and `mark` is present and null on an unmarked one — the corpus-
    independence rule every item row field already follows."""
    cuttings("The first")
    capsys.readouterr()
    assert main(["next", "pot-on", "--json"]) == 0
    (row,) = json.loads(capsys.readouterr().out)["rows"]
    assert row == {
        "name": "c1",
        "item": "a-batch",
        "state": "propagator",
        "title": "The first",
        "mark": None,
        "path": "propagator/a-batch.md",
    }


def test_the_frame_counts_the_whole_traversals_bullets_in_the_tools_noun(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two things at once, and they are the same rule the item read keeps.
    `walked` is every bullet the traversal read — the orchard's steps
    included, though `pot-on` could take none of them — and the noun is
    `sub-phases`, the tool's own word: "cuttings" is the workflow's heading
    and the tool may no more say it than it may say `done`."""
    orchard(tree, "First tree")
    path = tree / "orchard" / "first-tree.md"
    path.write_text(path.read_text() + "\n### Steps\n- **2-1 — A step**\n")
    cuttings("The first", "The second")
    capsys.readouterr()

    main(["next", "pot-on"])
    printed = capsys.readouterr()
    assert "2 of 3 sub-phases" in printed.err

    main(["next", "pot-on", "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "sub-phases"
    assert payload["transition"] == "pot-on"
    assert payload["matched"] == 2 and payload["read"] == 3


def test_a_marked_finding_leaves_the_offer_and_the_others_stay(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """What the read is for. Every disposition lists the same findings until
    one of them runs, and after that they differ by exactly the one taken."""
    cuttings("The first", "The second")
    assert main(["pot-on", "a-batch", "c1"]) == 0
    capsys.readouterr()
    assert main(["next", "pot-on", "--json"]) == 0
    assert [row["name"] for row in json.loads(capsys.readouterr().out)["rows"]] == ["c2"]


def test_the_pending_bullet_is_in_the_count_and_in_neither_half_of_the_offer(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The two reads disagreeing is the honest signal, and it is a difference
    a session can see rather than one it has to know. The marker **counts** as
    a sub-phase like any other — `list` says 2 — and it is not something a
    verb may dispose of, so it is in neither the offer's rows nor its
    denominator: 1 of 1, off a body carrying 2."""
    cuttings("The first", close=False)
    capsys.readouterr()

    assert main(["list", "--json"]) == 0
    (item,) = json.loads(capsys.readouterr().out)["rows"]
    assert item["sub-phases"] == 2

    assert main(["next", "pot-on", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [row["name"] for row in payload["rows"]] == ["c1"]
    assert payload["matched"] == 1 and payload["read"] == 1


def test_a_dispositions_offer_takes_no_filters(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`show`'s rule arrived at from the other end: every filter names a key
    an *item* carries, and a row here is not an item. `--json` is the one flag
    it does take, which is what keeps the two renderings one word apart."""
    cuttings("The first")
    assert main(["next", "pot-on", "--state", "propagator"]) == 2
    assert main(["next", "pot-on", "--json"]) == 0
    capsys.readouterr()
    assert main(["next", "pot-on", "--help"]) == 0
    assert "--tag" not in capsys.readouterr().out


def test_the_item_reads_are_untouched_by_a_mark(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`list` and `show` walk items and show the row rather than the body, so
    a mark appears in neither — and there is still no fourth read."""
    cuttings("The first")
    assert main(["pot-on", "a-batch", "c1"]) == 0
    capsys.readouterr()
    assert main(["list", "--json"]) == 0
    (row,) = json.loads(capsys.readouterr().out)["rows"]
    assert row["slug"] == "a-batch" and row["sub-phases"] == 1
    assert "rooted" not in json.dumps(row)


def scribbled(tree: Path) -> Path:
    """A batch whose one cutting carries prose outside its bold run.

    Minted through the verb and then edited by hand: `mist` writes markable
    bullets only, so this is a person's edit rather than anything the tool
    produces.
    """
    cuttings("The first")
    path = tree / "propagator" / "a-batch.md"
    path.write_text(
        path.read_text().replace(
            "- **c1 — The first**", "- **c1 — The first** and a note somebody typed"
        ),
        encoding="utf-8",
    )
    return path


def test_a_bullet_a_mark_could_not_be_read_on_refuses_the_run(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The report's own case, at the edge: rc 2, `ERROR:` on stderr, stdout
    empty, and the bullet as it was. The quiet arm was a word written where
    nothing reads it and a count that never falls."""
    path = scribbled(tree)
    before = path.read_bytes()
    capsys.readouterr()
    assert main(["pot-on", "a-batch", "c1"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("ERROR: ")
    assert 'carries "and a note somebody typed" after its bold run' in captured.err
    assert path.read_bytes() == before


def test_the_check_refuses_the_same_bullet_in_the_same_words(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--check` runs the identical path, so a refusal computed before the
    first write is one both invocations reach. No second code path to keep in
    step with the run's."""
    path = scribbled(tree)
    before = path.read_bytes()
    capsys.readouterr()
    assert main(["pot-on", "a-batch", "c1", "--check"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert 'carries "and a note somebody typed" after its bold run' in captured.err
    assert path.read_bytes() == before


def test_a_bullet_no_mark_could_be_read_on_is_named_by_the_default_read(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The seventh exception report, in both renderings. 14-1 made the verb
    refuse such a bullet, and nothing said so until a session reached for the
    verb. The default read is where a defect nobody is looking for gets
    found."""
    path = scribbled(tree)
    capsys.readouterr()
    lines = path.read_text().split("\n")
    line = 1 + next(
        at for at, text in enumerate(lines) if text.startswith("- **c1 — The first**")
    )

    assert main(["list"]) == 0
    printed = capsys.readouterr()
    assert "unmarkable" not in printed.out
    assert (
        f"unmarkable bullet: c1 in a-batch (propagator/a-batch.md:{line})"
        in printed.err
    )
    assert 'carries "and a note somebody typed" after its bold run' in printed.err

    assert main(["list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["unmarkable"] == [
        {
            "item": "a-batch",
            "name": "c1",
            "rest": "and a note somebody typed",
            "line": line,
            "path": "propagator/a-batch.md",
        }
    ]


def test_the_offer_for_every_marking_verb_passes_over_it(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The offer is what the verb would not refuse. Both of the propagator's
    dispositions refuse this bullet, so neither names it — and the report is
    on the offer's stderr too, so nothing goes quiet by being passed over.
    `walked` still counts it: what the traversal read, not what it offered."""
    scribbled(tree)
    assert main(["mist", "a-batch", "--title", "The second", "--last"]) == 0
    capsys.readouterr()

    for verb in ("pot-on", "line-out"):
        assert main(["next", verb, "--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert [row["name"] for row in payload["rows"]] == ["c2"]

    assert main(["next", "pot-on"]) == 0
    printed = capsys.readouterr()
    assert "1 of 2 sub-phases" in printed.err
    assert "unmarkable bullet: c1 in a-batch" in printed.err


def test_a_bullet_whose_trailing_text_is_only_whitespace_is_not_reported(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A markable bullet's line ends at the closing `**`, and whitespace after
    it is fine. The report reads the same `rest` the refusal does, so the two
    cannot come to different answers about a line with spaces on the end."""
    cuttings("The first")
    path = tree / "propagator" / "a-batch.md"
    path.write_text(
        path.read_text().replace(
            "- **c1 — The first**", "- **c1 — The first**   "
        ),
        encoding="utf-8",
    )
    capsys.readouterr()

    assert main(["list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["unmarkable"] == []
    assert main(["pot-on", "a-batch", "c1"]) == 0


def test_a_marked_bullet_and_its_note_are_not_unmarkable(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A note rides outside the closing `**` of the *mark*, so the disposed
    bullet carries rest. It is not waiting on any verb, and the report leaves
    it alone. This is the test that fails if the question ever loses its
    `mark is None` half and starts naming every marked bullet."""
    cuttings("The first")
    assert main(["pot-on", "a-batch", "c1", "--note", "it struck early"]) == 0
    capsys.readouterr()

    assert main(["list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["unmarkable"] == []
    assert main(["show", "a-batch", "c1", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["rows"][0]["mark"] == "rooted"


def test_no_filter_narrows_the_unmarkable_report(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`stranded`'s rule, for `stranded`'s reason: it is a report about the
    tree rather than a row of it. A filter that could hide it would be the
    flag-you-have-to-know-to-pass failure, inverted."""
    scribbled(tree)
    capsys.readouterr()

    assert main(["list", "--state", "greenhouse", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["rows"] == []
    assert [one["name"] for one in payload["unmarkable"]] == ["c1"]


def test_a_second_bold_run_holding_an_undeclared_word_is_open_and_reported(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Section 23: `**Note:** prose` read as a mark, so the count fell and
    nothing was said. The mark is a declared word, so this bullet is open,
    unmarkable, and named by the default read."""
    cuttings("The first")
    path = tree / "propagator" / "a-batch.md"
    path.write_text(
        path.read_text().replace(
            "- **c1 — The first**", "- **c1 — The first** **Note:** it struck early"
        ),
        encoding="utf-8",
    )
    capsys.readouterr()

    assert main(["list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["rows"][0]["sub-phases-left"] == 1
    assert [(one["name"], one["rest"]) for one in payload["unmarkable"]] == [
        ("c1", "**Note:** it struck early")
    ]
    assert main(["pot-on", "a-batch", "c1"]) == 2


def test_a_title_carrying_a_lone_asterisk_refuses(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The tool wrote `- **f1 — *moves* thing**` itself, and then no reader
    could name it. A lone `*` is the same second author as `**`."""
    cuttings("The first", close=False)
    path = tree / "propagator" / "a-batch.md"
    before = path.read_bytes()
    capsys.readouterr()
    assert main(["mist", "a-batch", "--title", "*moves* thing"]) == 2
    assert 'a lone "*"' in capsys.readouterr().err
    assert path.read_bytes() == before


def hidden(tree: Path, old: str, new: str) -> Path:
    """The batch with one hand edit, which `mist` would never have written."""
    path = tree / "propagator" / "a-batch.md"
    path.write_text(path.read_text().replace(old, new), encoding="utf-8")
    return path


def test_a_bullet_the_reader_cannot_name_is_reported_and_stops_a_mint(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Hand-written bullets still arrive. The read side makes one loud rather
    than making it work: the default read names it, and a mint refuses,
    because highest-plus-one over the names it can read would mint c1 again."""
    cuttings("The first", close=False)
    path = hidden(tree, "- **c1 — The first**", "- **c1 — *moves* thing**")
    capsys.readouterr()
    line = 1 + path.read_text().split("\n").index("- **c1 — *moves* thing**")

    assert main(["list", "--json"]) == 0
    (one,) = json.loads(capsys.readouterr().out)["unread"]
    assert {key: one[key] for key in ("item", "name", "line", "path")} == {
        "item": "a-batch",
        "name": "c1",
        "line": line,
        "path": "propagator/a-batch.md",
    }
    assert main(["list"]) == 0
    assert (
        f"unread bullet: c1 in a-batch (propagator/a-batch.md:{line})"
        in capsys.readouterr().err
    )

    before = path.read_bytes()
    assert main(["mist", "a-batch", "--title", "The second"]) == 2
    err = capsys.readouterr().err
    assert "passes over" in err and f"propagator/a-batch.md:{line}:" in err
    assert path.read_bytes() == before


def test_a_bullet_a_heading_cut_off_from_its_span_is_reported_and_stops_a_mark(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A consumer saw 40 findings read as 18. Where a span ends does not
    change, and the bullets past it are named rather than dropped."""
    cuttings("The first", "The second")
    path = tree / "propagator" / "a-batch.md"
    path.write_text(
        path.read_text() + "\n## Aside\n\n- **c3 — The third**\n", encoding="utf-8"
    )
    capsys.readouterr()

    assert main(["list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["rows"][0]["sub-phases"] == 2
    assert [one["name"] for one in payload["unread"]] == ["c3"]
    assert '"## Aside"' in payload["unread"][0]["reason"]

    before = path.read_bytes()
    assert main(["pot-on", "a-batch", "c1"]) == 2
    assert "passes over" in capsys.readouterr().err
    # A mint would hand out c3 a second time.
    assert main(["mist", "a-batch", "--title", "The fourth"]) == 2
    assert "passes over" in capsys.readouterr().err
    assert path.read_bytes() == before


def test_a_dispositions_help_takes_the_item_and_then_the_bullet(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two positionals in that order — which item, then which of its bullets
    — and the half in the contract's `Declares` block, which is what lets a
    composed session pick a disposition by half rather than by name."""
    assert main(["pot-on", "--help"]) == 0
    out = capsys.readouterr().out
    assert "Usage: fileplan pot-on [OPTIONS] ITEM NAME" in out
    assert declared_by(out) == ["marks"]

    assert main(["mist", "--help"]) == 0
    other = capsys.readouterr().out
    assert "Usage: fileplan mist [OPTIONS] ITEM" in other
    assert declared_by(other) == ["mints"]


def declared_by(epilog: str) -> list[str]:
    """The halves one contract's `Declares` block names."""
    block = epilog.partition("Declares")[2].strip().splitlines()[0]
    return [name.strip() for name in block.split(",")]


# --------------------------------------------------------------------------
# The filing disposition, end to end
# --------------------------------------------------------------------------


def test_a_filing_run_names_both_files_on_stderr_and_the_carrier_on_stdout(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The uniform rule, over the run that touches two files: stdout carries
    the destination of the item the run *moved*, so `fileplan line-out ITEM
    NAME` piped somewhere carries that and nothing else. What it did that
    nobody asked for — an item appearing in another state — is the operator's,
    and goes to stderr."""
    cuttings("The first", "The second")
    capsys.readouterr()
    assert main(["line-out", "a-batch", "c1", "--body", "Prose."]) == 0
    printed = capsys.readouterr()
    assert printed.out.strip() == "propagator/a-batch.md"
    assert printed.err.strip() == (
        "greenhouse/the-first.md: filed from c1 in propagator/a-batch.md, "
        'which this run marked "lined"'
    )
    assert (tree / "greenhouse" / "the-first.md").is_file()


def test_which_items_came_from_this_carrier_is_one_read(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The join the pair of keys exists to make, and it needs nothing new:
    `--batch` is the filter every declared key already gets."""
    cuttings("The first", "The second")
    assert main(["line-out", "a-batch", "c1", "--body", "Prose."]) == 0
    assert main(["line-out", "a-batch", "c2", "--body", "More prose."]) == 0
    capsys.readouterr()

    assert main(["list", "--has", "batch=a-batch", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert [(row["slug"], row["cutting"]) for row in rows] == [
        ("the-first", "c1"),
        ("the-second", "c2"),
    ]


def test_which_findings_are_still_open_is_the_offer(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The other direction, off the same run: a filed cutting leaves the
    offer, because the mark and the filing are one run rather than two."""
    cuttings("The first", "The second")
    assert main(["line-out", "a-batch", "c1", "--body", "Prose."]) == 0
    capsys.readouterr()
    assert main(["next", "line-out", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)["rows"]
    assert [row["name"] for row in rows] == ["c2"]


def test_a_filings_help_takes_two_positionals_two_options_and_both_halves(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole generated surface in one read: the disposition's positionals,
    the filing's two options, and both halves in `Declares` — which is what
    lets a composed session reach for this verb by the half it declares rather
    than by its name."""
    assert main(["line-out", "--help"]) == 0
    out = capsys.readouterr().out
    assert "Usage: fileplan line-out [OPTIONS] ITEM NAME" in out
    assert "--title TEXT" in out and "--body TEXT" in out
    assert out.partition("Declares")[2].split("Reading")[0].split() == [
        "files",
        "marks",
    ]


def test_a_filing_with_no_body_refuses_in_the_executors_words(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Taken as a value rather than made `required=True`, so the refusal is
    the executor's one rule rather than click's second spelling of it — and it
    is rc 2 with `ERROR:` on stderr like every other refusal."""
    cuttings("The first")
    capsys.readouterr()
    assert main(["line-out", "a-batch", "c1"]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err.startswith("ERROR: line-out needs a body. An item is a title")


def test_the_offer_takes_the_listing_s_filters(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Deliberately not a poorer surface. Diverging would be a second
    vocabulary to keep in step with the first, for no gain — `--state` on an
    offer is redundant rather than wrong, and it narrows further."""
    greenhoused("heirloom", "A seedling")
    greenhoused("heirloom", "B seedling")
    assert offered(capsys, "transplant", "--has", "tag=spring") == []
    assert offered(capsys, "transplant", "--lacks", "tag") == [
        "a-seedling",
        "b-seedling",
    ]
    assert offered(capsys, "transplant", "--state", "greenhouse") == [
        "a-seedling",
        "b-seedling",
    ]
    assert offered(capsys, "transplant", "--state", "orchard") == []


def test_the_offer_s_envelope_names_which_transition_it_is(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A consumer reading a pipe can tell one offer from another, and both
    from the listing. The kind alone would say "an offer" and leave out the
    half that says what of."""
    greenhoused("heirloom", "A seedling")
    capsys.readouterr()
    assert main(["next", "transplant", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "next"
    assert payload["transition"] == "transplant"

    assert main(["list", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["kind"] == "items"


def test_a_transition_named_next_refuses(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The third of the tool's own words, reserved the way `list` and
    `release` are: one command cannot mean two things. The declaration is
    otherwise well formed, so this refusal is the only reason it could fail."""
    plan = (tree / "plan.toml").read_text()
    (tree / "plan.toml").write_text(
        plan.replace("[transitions.sprout]", "[transitions.next]")
    )
    (tree / "method.md").write_text(
        (tree / "method.md").read_text() + "\n## next\n"
    )
    assert main(["--help"]) == 2
    err = capsys.readouterr().err
    assert (
        "transitions.next takes the name of the read named by the command" in err
    )


def test_no_declared_verb_is_named_anywhere_under_src() -> None:
    """The done line of 1-3, mutation-checked and still live. If any verb were
    special-cased in code — an `if` on its name, a function per verb, a
    template picked by name — this is what would fail. It reads the repo's own
    declaration rather than a hard-coded list, so a verb added later is
    covered without anyone remembering to add it here.

    **The match is on word boundaries**, which is what the control always
    meant: a verb being *named*, not a substring appearing. 1-5 is what forced
    it — `queued` is a capability and contains a declared verb's name — and it
    loosens nothing that matters, because `if transition.name == "queue"`
    anywhere still fails.

    **It grades the code and not the prose**, which is the same narrowing for
    the third time. 1-6 stripped citations, because `queued.py` cites
    `docs/method.md#the-queue` and a pointer at prose is not code that
    special-cases a verb. 4-4 is what forced the general form: this repo
    declares a verb called `work`, and "work" is an ordinary English word that
    a docstring about picking items up cannot avoid. The alternative was to
    ban a word from the tool's own prose forever, which would make the prose
    worse to satisfy a mechanical check — and a consumer whose workflow
    declares `read`, `set` or `open` would hit the same wall on day one, which
    is not a thing a *declared* workflow may punish. What the control protects
    is unchanged and is stated exactly: **no per-verb code**. A string literal
    in an expression is code and survives the strip, so every dispatch-on-name
    shape it exists to catch still fails it.

    The citation strip stays, because a citation can appear in a string the
    tool prints as well as in prose, and it uses `test_docs.CITATION` so that
    "what a citation looks like" keeps one home.

    The limit, stated rather than discovered: **a string literal is still
    graded**, help text included, because a string literal is precisely where
    a dispatch would hide. A `--help` line that wants to say "work" says it
    another way, which costs a word; a docstring does not.

    **And the hole, named rather than left to be found.** A verb named after
    one of the tool's own option words is skipped, because at that point the
    two are indistinguishable: the tool spells `RESERVED_OPTIONS` for its own
    reasons whatever the workflow calls things, and a word it must spell
    cannot also be a word it may not spell. 11-6 is what forced it — this repo
    declares a verb called `note`, and the option that says *why* a
    disposition disposed of a finding is `--note`. A verb and an option are
    two namespaces that never meet on one command line, so the declaration
    stays legal and this control loses its teeth over exactly those words.
    What that costs is stated: per-verb code named after a reserved word would
    pass. The roster is a dozen words the tool owns, assembled at the
    top of this module out of the constants `cli` spells them with — so the
    three table-driven halves track by themselves, and a new scalar option is
    covered only when somebody adds it here."""
    source = "\n".join(
        code_only(path.read_text()) for path in (REPO / "src").rglob("*.py")
    )
    source = CITATION.sub("", source)
    verbs = [
        verb
        for verb in load(REPO / "plan.toml").transitions
        if verb not in RESERVED_OPTIONS
    ]
    assert verbs, "the repo declares no transitions, so this control proves nothing"
    for verb in verbs:
        assert not re.search(rf"\b{re.escape(verb)}\b", source), verb


def test_the_control_skips_the_tools_own_words_and_nothing_else() -> None:
    """The mutation check on the narrowing, and the whole of what it gives up.
    A verb named after a reserved option is out of the control's reach; every
    other verb this repo declares is still in it, and the roster does not
    quietly grow to cover one."""
    declared = set(load(REPO / "plan.toml").transitions)
    skipped = declared & set(RESERVED_OPTIONS)
    assert skipped == {"note"}, skipped
    assert declared - skipped, "the narrowing may not empty the control"
    # And the shape it can no longer catch, said out loud rather than implied.
    assert re.search(r'\bnote\b', 'if transition.name == "note":')


def test_the_control_still_catches_a_verb_named_inside_a_word() -> None:
    """The mutation check on the check. A word-boundary match must still fail
    on the thing the control exists to catch, and must not fail on a longer
    word that merely contains a verb's name."""
    assert re.search(r"\bqueue\b", 'if transition.name == "queue":')
    assert not re.search(r"\bqueue\b", 'CAPABILITIES = ("queued",)')
    assert CITATION.sub("", "cites ``docs/method.md#the-queue`` here") == "cites ```` here"
    assert CITATION.sub("", 'if name == "queue":') == 'if name == "queue":'


def test_the_control_reads_code_and_not_the_prose_around_it() -> None:
    """The mutation check on the strip. Every shape a verb could be
    special-cased in survives it; a docstring and a comment saying the same
    word do not — which is the whole of what 4-4 loosened."""
    dispatch = 'def go(name):\n    """Do the work."""\n    # work happens here\n'
    assert "work" not in code_only(dispatch)

    for shape in (
        'if name == "work":\n',
        'HANDLERS = {"work": run}\n',
        "def work():\n    pass\n",
        'getattr(self, "work")()\n',
    ):
        assert re.search(r"\bwork\b", code_only(shape)), shape



# --------------------------------------------------------------------------
# The derived roster, reached from the command line
# --------------------------------------------------------------------------


def test_every_derived_key_is_reachable_by_a_filter(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**The reachability control.** A field on every row that no filter can
    name is a fact you have to read every line to find, and that is exactly
    what `--sub-phases` was before 3-4. Since 13-3 there is one roster and
    `--has` reaches all of it, so this holds by construction — and the
    mutation below says it is not vacuous."""
    declared = load(tree / "plan.toml")
    assert declared.derived, "the fixture derives nothing, so this proves nothing"
    assert set(declared.derived) <= set(DERIVABLE_KEYS)
    assert main(["list", "--help"]) == 0
    roster = re.sub(r"-\n\s+", "-", capsys.readouterr().out)
    for key in declared.derived:
        assert key in roster


def test_a_key_the_roster_grows_is_filterable_without_a_second_table(
    tree: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mutation check on the control above, and what the 13-3 fold bought:
    a derived key added to the roster is reachable by `--has` with nothing
    else written anywhere. Before the fold this raised `KeyError`, because a
    second table said how each key *read* on the command line and it had no
    row for the new one."""
    from fileplan.declaration import DERIVED_KEYS

    monkeypatch.setattr(
        "fileplan.declaration.DERIVED_KEYS",
        (*DERIVED_KEYS, (lambda one: True, ("invented",))),
    )
    assert main(["list", "--help"]) == 0
    assert "invented" in capsys.readouterr().out
    assert main(["list", "--has", "invented"]) == 0


def test_the_sub_phase_count_filters_and_zero_is_a_value(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The defect the fold found. `--sub-phases 0` is a section somebody
    started and nobody decomposed — the same fact the `undecomposed` report
    names, now askable as a question. The zero survives because a zero is a
    real count and only `""` and `[]` read as absent."""
    named(tree, "graft-1", "graft-2")
    orchard(tree, "Second tree")

    assert [one["slug"] for one in rows(capsys, "--has", "sub-phases=2")] == ["first-tree"]
    assert [one["slug"] for one in rows(capsys, "--has", "sub-phases=0")] == ["second-tree"]
    assert sorted(one["slug"] for one in rows(capsys, "--has", subphase.NAME)) == [
        "first-tree",
        "second-tree",
    ]


# --------------------------------------------------------------------------
# show: the same read, narrowed by a handle
# --------------------------------------------------------------------------


def test_show_names_one_item_by_its_handle(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    filed(tree)
    capsys.readouterr()
    assert main(["show", "a-seedling"]) == 0
    out = capsys.readouterr().out
    assert "a-seedling" in out and "another-seedling" not in out


def test_show_resolves_a_unique_prefix(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The handle, not a slug: the same three rules every verb resolves by,
    because they are the same function."""
    filed(tree)
    capsys.readouterr()
    assert main(["show", "ano"]) == 0
    assert "another-seedling" in capsys.readouterr().out


def test_show_refuses_an_ambiguous_prefix_naming_its_candidates(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    filed(tree)
    capsys.readouterr()
    assert main(["show", "a"]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert '"a" names 2 items' in printed.err
    assert "a-seedling" in printed.err and "another-seedling" in printed.err


def test_show_refuses_a_handle_matching_nothing_naming_near_misses(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    filed(tree)
    capsys.readouterr()
    assert main(["show", "a-seedlingg"]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert 'no item starts with "a-seedlingg"' in printed.err
    assert "nearest: a-seedling" in printed.err


def test_show_renders_the_row_list_builds(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**The control, over `show`.** Its two renderings come off one row, and
    that row is the one `list` built — which is what "no second traversal"
    means when it is checked rather than claimed."""
    filed(tree)
    capsys.readouterr()

    main(["show", "a-seedling"])
    printed = capsys.readouterr().out.splitlines()

    main(["show", "a-seedling", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert render.records(payload["rows"]) == printed

    main(["list", "--state", "orchard", "--json"])
    assert payload["rows"] == json.loads(capsys.readouterr().out)["rows"]


def test_show_carries_the_keys_the_file_does_not_hold(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """What `show` adds over `cat`: the computed keys. Every derived name the
    declaration carries is on the row, which is the roster again — so a key
    that grows later is on `show` without a line here."""
    filed(tree)
    capsys.readouterr()
    assert main(["show", "a-seedling", "--json"]) == 0
    (row,) = json.loads(capsys.readouterr().out)["rows"]
    for key in load(tree / "plan.toml").derived:
        assert key in row


def test_show_frames_and_reports_over_the_whole_tree(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`1 of 2`, because `2` is what the traversal read — and a stranded claim
    is still named. No read narrows a report: `show` would be the first to
    hide one, for no reason but tidiness."""
    filed(tree)
    sibling(tree, "a-ghost", pid=ANOTHER_LIVE_SESSION)
    capsys.readouterr()

    assert main(["show", "a-seedling"]) == 0
    err = capsys.readouterr().err
    assert "1 of 2 items" in err
    assert "stranded claim: a-ghost" in err


def test_shows_envelope_names_one_item_and_the_whole_traversal(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`item` against `items` and `next`: a consumer reading a pipe can tell a
    read of one from a read of many without counting rows."""
    filed(tree)
    capsys.readouterr()
    assert main(["show", "a-seedling", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "item"
    assert payload["matched"] == 1 and payload["read"] == 2
    assert payload["stranded"] == [] and payload["unknown"] == []


def test_show_takes_no_filters(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A filter narrows a set and `show` has been told which item. `--state`
    on an item somewhere else would say "no such item" about an item that
    exists — the failure tree-wide resolution was adopted to end."""
    filed(tree)
    capsys.readouterr()
    assert main(["show", "--help"]) == 0
    printed = capsys.readouterr().out
    assert "ITEM" in printed
    # The options, not the prose above them: `show --help` says *why* it
    # takes no `--state`, and saying so must not read as offering one.
    options = printed.split("Options:")[-1]
    assert "--json" in options
    assert "--state" not in options and "--has" not in options
    for key in load(tree / "plan.toml").derived:
        assert f"--{key}" not in options

    assert main(["show", "a-seedling", "--state", "greenhouse"]) == 2
    assert "--state" in capsys.readouterr().err


# --------------------------------------------------------------------------
# show ITEM NAME: the third read, narrowed to the subject the second offers
# --------------------------------------------------------------------------
#
# Not a fourth read. `next <disposition>` already lists bullets, so a bullet
# is already a subject of this tool's read surface — and the one thing that
# could not be done with it was reading one (`docs/method.md#show`).

#: The continuation the fixture's first cutting grows: an indented paragraph
#: and a fenced transcript whose lines are somebody else's document. This
#: repo's own carrier has one-line findings and would notice none of it. A
#: consumer's carrier is where transcripts live inside a finding, which is
#: the case this is for.
CONTINUATION = (
    "  What was observed:\n"
    "\n"
    "  ```\n"
    "  $ fileplan list\n"
    "- a bullet at column zero, inside the fence\n"
    "\n"
    "### Nor a heading\n"
    "  ```\n"
)


def batched(tree: Path, *, close: bool = True) -> Path:
    """A batch of two cuttings, the first carrying a real continuation."""
    cuttings("The first", "The second", close=close)
    path = tree / "propagator" / "a-batch.md"
    was = path.read_text()
    assert "- **c1 — The first**\n" in was
    path.write_text(
        was.replace("- **c1 — The first**\n", "- **c1 — The first**\n" + CONTINUATION)
    )
    return path


def test_show_names_one_bullet_and_prints_what_it_says(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Answering "what does c1 actually say" without opening a carrier that
    may run to 100k tokens. The bullet's own line and its continuation, on
    stdout, and no row — a row is what `show ITEM` is for."""
    batched(tree)
    capsys.readouterr()
    assert main(["show", "a-batch", "c1"]) == 0
    printed = capsys.readouterr()
    assert printed.out == "- **c1 — The first**\n" + CONTINUATION
    assert "propagator/a-batch.md" not in printed.out


def test_a_fenced_transcript_inside_a_bullet_comes_back_whole(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The column-zero bullet and the column-zero heading inside the fence are
    somebody else's document being shown, so neither truncates the read."""
    batched(tree)
    capsys.readouterr()
    assert main(["show", "a-batch", "c1"]) == 0
    out = capsys.readouterr().out
    assert "- a bullet at column zero, inside the fence" in out
    assert "### Nor a heading" in out
    assert "c2" not in out


def test_show_without_a_name_is_the_row_read_unchanged(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The name not given changes nothing: the branch is entered only where
    there is a bullet to read, so `show ITEM` is byte-identical by
    construction rather than by a test that two paths agree. What is asserted
    here is that the control still holds over it — the two renderings still
    come off the one row `list` built."""
    batched(tree)
    capsys.readouterr()

    assert main(["show", "a-batch"]) == 0
    printed = capsys.readouterr()

    main(["show", "a-batch", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert render.records(payload["rows"]) == printed.out.splitlines()
    assert payload["kind"] == "item"
    assert "1 of 1 items" in printed.err


def test_a_name_the_body_does_not_carry_refuses_in_the_dispositions_words(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One home for that sentence since 11-4, so a typo is a read the operator
    can fix out of what the refusal said — the same words, from the same code,
    whichever of the two asked."""
    batched(tree)
    capsys.readouterr()
    assert main(["show", "a-batch", "c9"]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert 'carries no "c9", and the names it carries are c1, c2' in printed.err


def test_an_unnamed_bullet_is_nothing_show_can_be_pointed_at(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`bullets` drops it and the read gates on `bullets`, so it needs no arm
    of its own — exactly as the disposition documents. A bullet nobody can
    type is nothing a read could name."""
    path = batched(tree)
    path.write_text(
        path.read_text().replace(
            "- **c2 — The second**", "- **c2 — The second**\n- a bullet with no name"
        )
    )
    capsys.readouterr()
    assert main(["show", "a-batch", "a"]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert 'carries no "a", and the names it carries are c1, c2' in printed.err


def test_the_pending_marker_refuses_as_a_name_the_body_does_not_carry(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """It marks the decomposition as unfinished rather than being work, and it
    is dropped by the same reader — one refusal rather than two."""
    path = batched(tree, close=False)
    assert f"- {UNSTRUCK}" in path.read_text()
    capsys.readouterr()
    assert main(["show", "a-batch", "unstruck"]) == 2
    assert 'carries no "unstruck"' in capsys.readouterr().err


def test_an_item_whose_state_counts_no_sub_phases_refuses_by_name(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Reachable the moment `show` takes a second positional, and printing
    nothing is the polarity the make-problems-visible rule rejects:
    there is no bullet here for a name to point at, and the refusal says which
    state that is."""
    filed(tree)
    capsys.readouterr()
    assert main(["show", "another-seedling", "c1"]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert "greenhouse" in printed.err and "sub-phases" in printed.err


def test_a_bullet_read_frames_and_reports_over_the_whole_tree(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """"And nothing else" governs **stdout**. A read that hid a stranded claim
    because you asked about one bullet would be the first read in this tool to
    hide one — `show`'s own rule, one level in. The frame counts **items**,
    because the traversal walked items and the narrowing that happened first
    was item-narrowing; `next <disposition>` counts bullets because its rows
    are bullets, and here there are no rows."""
    batched(tree)
    sibling(tree, "a-ghost", pid=ANOTHER_LIVE_SESSION)
    capsys.readouterr()

    assert main(["show", "a-batch", "c2"]) == 0
    printed = capsys.readouterr()
    assert printed.out == "- **c2 — The second**\n"
    assert "1 of 1 items" in printed.err
    assert "stranded claim: a-ghost" in printed.err


def test_the_bullet_read_carries_the_same_facts_in_both_renderings(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Not more facts, and not a row: `name`, `title` and `mark` are extracted
    *from* the verbatim text a person reads, shaped for the consumer that
    would otherwise re-parse the bold. The envelope's kind is the singular, so
    a consumer can tell `show ITEM` from `show ITEM NAME`."""
    batched(tree)
    capsys.readouterr()

    assert main(["show", "a-batch", "c1", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "sub-phase"
    assert payload["matched"] == 1 and payload["read"] == 1
    assert payload["stranded"] == [] and payload["unknown"] == []

    (row,) = payload["rows"]
    assert row == {
        "name": "c1",
        "item": "a-batch",
        "title": "The first",
        "mark": None,
        "text": row["text"],
    }

    main(["show", "a-batch", "c1"])
    assert row["text"] + "\n" == capsys.readouterr().out


def test_show_returns_the_mark_on_a_sub_phase_bullet(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """12-1's premise from the read side, over `orchard` — the state that
    carries a cursor. `bullets` finds the word mechanically whatever state the
    bullet is in, so a disposition on a plan-shaped state needed nothing added
    here: `mark` was already the field, and it is null until a verb writes
    one."""
    orchard(tree, "First tree")
    assert main(["espalier", "first-tree", "--title", "The first", "--last"]) == 0
    assert main(["ripen", "first-tree", "2-1", "--note", "It held."]) == 0
    capsys.readouterr()

    assert main(["show", "first-tree", "2-1"]) == 0
    assert capsys.readouterr().out == (
        "- **2-1 — The first** **ripened** It held.\n"
    )

    assert main(["show", "first-tree", "2-1", "--json"]) == 0
    (row,) = json.loads(capsys.readouterr().out)["rows"]
    assert row["name"] == "2-1" and row["mark"] == "ripened"


def test_show_help_says_the_exception_to_row_never_body(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The sentence that would otherwise lie. A positional is not a flag, so
    the named-report control is untouched."""
    assert main(["show", "--help"]) == 0
    out = capsys.readouterr().out
    assert "ITEM [NAME]" in out
    assert "NAME" in out.split("Options:")[0]


def test_a_bullet_read_takes_no_filters_either(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`show`'s rule, and this run has been told which item **and** which
    bullet."""
    batched(tree)
    capsys.readouterr()
    assert main(["show", "a-batch", "c1", "--state", "propagator"]) == 2
    assert "--state" in capsys.readouterr().err


def test_a_declared_transition_named_show_refuses_by_name(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The tool's fourth word, reserved the way the other three are: one
    command cannot mean two things."""
    plan = (tree / "plan.toml").read_text()
    (tree / "plan.toml").write_text(
        plan.replace("[transitions.sprout]", "[transitions.show]")
    )
    (tree / "method.md").write_text(
        (tree / "method.md").read_text() + "\n## show\n"
    )
    assert main(["--help"]) == 2
    err = capsys.readouterr().err
    assert "transitions.show takes the name of the read of one item" in err


def test_the_table_of_contents_names_show(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([]) == 0
    assert "fileplan show ITEM" in capsys.readouterr().out


# --------------------------------------------------------------------------
# `dissolves`: the file that goes away, from the command line
# --------------------------------------------------------------------------
#
# `fell` declares both halves out of `orchard`; `compost` declares only the
# deletion half, out of the unnumbered `greenhouse`. Neither is this repo's
# `archive-plan`, which is the point: any state can declare a verb of either
# shape.

RECORD = "What it was, and why it came down."


def test_a_dissolving_verb_takes_the_file_and_says_what_it_did(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole run: the item is gone, the entry and its record are in the
    archive, **stdout is the archive** — the file the run wrote, since the
    item's own path names nothing now — and every notice is on stderr."""
    orchard(tree, "First tree")
    capsys.readouterr()

    assert main(["fell", "first-tree", "--record", RECORD]) == 0
    printed = capsys.readouterr()
    assert printed.out.strip() == "orchard-archive.md"
    assert not (tree / "orchard" / "first-tree.md").exists()
    assert f"## 2. First tree\n\n{RECORD}\n" in archived(tree)
    assert "first-tree.md is gone" in printed.err


def test_a_dissolve_that_archives_nothing_reports_the_path_it_removed(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`compost`, out of the unnumbered state. There is no second file to name,
    so the removed path is what there is to report — and stderr says it is
    gone, so nothing reads the line as a file to open."""
    assert main(["sprout", "A seedling", "--body", "Prose.", "--cultivar", "heirloom"]) == 0
    document = archived(tree)
    capsys.readouterr()

    assert main(["compost", "a-seedling"]) == 0
    printed = capsys.readouterr()
    assert printed.out.strip() == "greenhouse/a-seedling.md"
    assert not (tree / "greenhouse" / "a-seedling.md").exists()
    assert "a-seedling.md is gone" in printed.err
    assert archived(tree) == document


def test_the_record_is_required_on_a_verb_that_archives_and_dissolves(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**The polarity.** A minted heading with nothing under it plus a deleted
    item is the lost close-out the register exists to prevent, and a forgotten
    record has to fail at the one moment it can still be supplied. Nothing is
    written."""
    orchard(tree, "First tree")
    document = archived(tree)
    capsys.readouterr()

    assert main(["fell", "first-tree"]) != 0
    assert "--record" in capsys.readouterr().err
    assert (tree / "orchard" / "first-tree.md").exists()
    assert archived(tree) == document


def test_the_record_option_is_only_on_the_verb_that_needs_it(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Generated by what the verb declares, like every other capability's
    options. `grub-out` moves the item, so its source material survives and the
    session fills the entry in; `compost` archives nothing to write under."""
    for name in ("fell", "grub-out", "compost", "transplant"):
        assert main([name, "--help"]) == 0
        assert ("--record" in capsys.readouterr().out) == (name == "fell")


def test_the_record_reads_stdin_so_a_heredoc_works(
    tree: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--body -`'s precedent, and the case it is for: a close-out entry is
    paragraphs, not a shell argument."""
    orchard(tree, "First tree")
    monkeypatch.setattr("sys.stdin", io.StringIO("One.\n\nTwo.\n"))
    assert main(["fell", "first-tree", "--record", "-"]) == 0
    assert "## 2. First tree\n\nOne.\n\nTwo.\n" in archived(tree)


def test_the_cleared_edges_are_named_on_stderr_one_line_each(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """stdout carries the path and nothing else, so `fileplan fell ... | xargs`
    still works; what the run did to *other* items is for the operator."""
    orchard(tree, "First tree")
    orchard(tree, "Second tree")
    orchard(tree, "Third tree")
    for slug in ("second-tree", "third-tree"):
        path = tree / "orchard" / f"{slug}.md"
        path.write_text(path.read_text().replace(
            "title = ", 'after = ["first-tree"]\ntitle = '
        ))
    capsys.readouterr()

    assert main(["fell", "first-tree", "--record", RECORD]) == 0
    printed = capsys.readouterr()
    assert printed.out.strip() == "orchard-archive.md"
    cleared = [one for one in printed.err.splitlines() if "out of after" in one]
    assert len(cleared) == 2
    assert "orchard/second-tree.md" in printed.err
    assert "orchard/third-tree.md" in printed.err
    assert "after" not in (tree / "orchard" / "second-tree.md").read_text()


def test_the_cleared_edges_leave_no_unknown_dependency_in_the_listing(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**The invariant, end to end.** Absence means *unknown*, and what makes
    that safe is this: the verb that takes an item away takes the edges to it
    away too, so a close-out leaves the default read clean."""
    orchard(tree, "First tree")
    orchard(tree, "Second tree")
    path = tree / "orchard" / "second-tree.md"
    path.write_text(path.read_text().replace(
        "title = ", 'after = ["first-tree"]\ntitle = '
    ))
    assert main(["fell", "first-tree", "--record", RECORD]) == 0
    capsys.readouterr()

    assert main(["list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["unknown"] == []
    assert [row["blocked-by"] for row in payload["rows"]] == [None]


def test_a_claim_another_session_holds_refuses_and_deletes_nothing(
    tree: Path, session: str, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """"This is not yours" is prior to everything else, and here it is what
    stands between a stranger and an item somebody is mid-way through: rc 2,
    one `ERROR:` line, nothing on stdout, and the file still there."""
    claimable(tree)
    orchard(tree, "First tree")
    assert main(["pick", "first-tree"]) == 0
    document = archived(tree)
    capsys.readouterr()

    monkeypatch.setenv("GREENHOUSE_PID", str(ANOTHER_LIVE_SESSION))
    assert main(["fell", "first-tree", "--record", RECORD]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err.count("ERROR: ") == 1
    assert (tree / "orchard" / "first-tree.md").exists()
    assert archived(tree) == document


def test_the_holder_dissolves_it_and_the_claim_is_freed(
    tree: Path, session: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """A dissolving verb enters nothing, so it can only ever *free* a claim —
    which is what it should do: the file the record was about is gone."""
    claimable(tree)
    orchard(tree, "First tree")
    assert main(["pick", "first-tree"]) == 0
    assert claim.path(tree, "first-tree").exists()

    assert main(["fell", "first-tree", "--record", RECORD]) == 0
    assert not claim.path(tree, "first-tree").exists()
    assert not (tree / "orchard" / "first-tree.md").exists()


def test_a_dissolving_verb_has_a_next_read_like_any_other_that_moves(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """It leaves its state, so it is a verb something could be next for — which
    is what makes `fileplan next archive-plan` the old tool's `--closeable`."""
    orchard(tree, "First tree")
    assert offered(capsys, "fell") == ["first-tree"]
    assert offered(capsys, "compost") == []


def test_a_dissolving_verbs_offer_narrows_by_its_own_preconditions(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`archive-plan`'s completion conditions are `requires`/`refuses` on the
    verb, so this is the shape that makes them a listing: only trees that pass
    are offered, and the rest are not."""
    plan = tree / "plan.toml"
    plan.write_text(plan.read_text().replace(
        'from      = "orchard"\narchives  = true\ndissolves = true\n',
        'from      = "orchard"\narchives  = true\ndissolves = true\n'
        'requires  = ["rootstock"]\n',
    ))
    orchard(tree, "First tree")
    orchard(tree, "Second tree")
    path = tree / "orchard" / "second-tree.md"
    path.write_text(path.read_text().replace(
        "title = ", 'rootstock = "quince"\ntitle = '
    ))
    assert offered(capsys, "fell") == ["second-tree"]


# --------------------------------------------------------------------------
# The seal as a gate: a close-out over a carrier still holding work
# --------------------------------------------------------------------------
#
# `fell` archives **and** dissolves, so it refuses; `grub-out` archives and
# moves, so it does not. Every move through the CLI, because what is pinned
# here is the seam the operator meets: `--check` refusing in the run's own
# words, and the offer not handing back work the verb would turn down.


def opened(tree: Path, *, title: str = "First tree") -> None:
    """A tree in the orchard and a batch struck for it, holding two findings.

    It needs no history at all — the gate reads the tree, never git — which
    is why nothing here commits.

    Its own steps are **marked**, so the only thing standing between this tree
    and a close is the batch. The tests below are about the carrier gate, and
    a tree whose steps were open would refuse for a second reason and stop
    saying which gate it was.
    """
    named(tree, "graft-1", "graft-2")
    for step in ("graft-1", "graft-2"):
        assert main(["ripen", "first-tree", step]) == 0
    assert (
        main(
            [
                "strike",
                "A batch",
                "--body",
                "Prose.",
                "--for-tree",
                "first-tree",
                "--for-step",
                "graft-1",
            ]
        )
        == 0
    )
    assert main(["mist", "a-batch", "--title", "The first"]) == 0
    assert main(["mist", "a-batch", "--title", "The second", "--last"]) == 0


def rooted(tree: Path) -> None:
    """Every cutting in the batch disposed of."""
    for name in ("c1", "c2"):
        assert main(["pot-on", "a-batch", name]) == 0


# --- the note beside the word -----------------------------------------------


def test_the_note_option_is_on_every_marking_verb_and_no_other(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Generated by the half, like `--record` and `--into`, so nothing in the
    CLI knows which verb carries it — and **optional** unlike those two: a
    disposition with no reason is the ordinary case. `line-out` is the filing
    one, and it takes a note for the same reason `pot-on` does."""
    for name in ("pot-on", "line-out", "espalier", "fell", "transplant"):
        assert main([name, "--help"]) == 0
        printed = capsys.readouterr().out
        assert ("--note" in printed) == (name in ("pot-on", "line-out"))
        if name == "pot-on":
            assert "[required]" not in printed


def test_a_note_rides_a_disposition_end_to_end_and_narrows_nothing(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The done line from the command line, and the read beside it: the offer
    narrows on the **mark**, which is what the note was written outside the
    bold run to leave alone."""
    cuttings("The first", "The second")
    assert main(["pot-on", "a-batch", "c1", "--note", "Roots to the wall."]) == 0
    assert (
        "- **c1 — The first** **rooted** Roots to the wall."
        in (tree / "propagator" / "a-batch.md").read_text()
    )
    capsys.readouterr()
    assert main(["next", "pot-on", "--json"]) == 0
    assert [row["name"] for row in json.loads(capsys.readouterr().out)["rows"]] == ["c2"]


def test_a_sets_key_colliding_with_the_note_option_refuses_by_name(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The `--last` and `--check` precedent, over the option a **marking**
    verb carries. It needs the check that `--record` and `--into` do not: both
    of those ride on `dissolves`, which refuses `sets` back in `plan.toml`,
    while a marking verb may declare `sets` freely."""
    plan = (tree / "plan.toml").read_text().replace(
        'marks = "rooted"', 'marks = "rooted"\nsets  = ["note"]'
    )
    (tree / "plan.toml").write_text(plan + '\n[keys.note]\ndoc = "method.md#note"\n')
    (tree / "method.md").write_text((tree / "method.md").read_text() + "\n## note\n")
    assert main(["--help"]) == 2
    err = capsys.readouterr().err
    assert 'transitions.pot-on.sets names "note"' in err
    assert "One option cannot mean two things" in err


def test_a_check_over_an_open_carrier_refuses_by_name_and_touches_nothing(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The done line, end to end: rc 2, one `ERROR:` line naming the batch,
    the declared key and the count, nothing on stdout, and the tree, the batch
    and the archive all where they were."""
    opened(tree)
    document = archived(tree)
    batch = (tree / "propagator" / "a-batch.md").read_text()
    capsys.readouterr()

    assert main(["fell", "first-tree", "--record", RECORD, "--check"]) == 2
    printed = capsys.readouterr()
    assert printed.out == ""
    assert printed.err.count("ERROR: ") == 1
    assert "a-batch.md" in printed.err
    assert "for-tree" in printed.err
    assert f"2 of its 2 {subphase.NAME}" in printed.err
    assert (tree / "orchard" / "first-tree.md").exists()
    assert archived(tree) == document
    assert (tree / "propagator" / "a-batch.md").read_text() == batch


def test_the_close_out_goes_through_once_every_finding_is_disposed_of(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The same run, after the work: the check passes at rc 0 with its one
    sentence, and the real run then takes the tree down."""
    opened(tree)
    rooted(tree)
    capsys.readouterr()

    assert main(["fell", "first-tree", "--record", RECORD, "--check"]) == 0
    assert "would take" in capsys.readouterr().out
    assert main(["fell", "first-tree", "--record", RECORD]) == 0
    assert not (tree / "orchard" / "first-tree.md").exists()
    assert f"## 2. First tree\n\n{RECORD}\n" in archived(tree)


def test_an_archiving_verb_that_moves_the_item_is_unaffected(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Where the two archiving verbs differ, from the command line: giving up
    on a tree is one run however much its batch still holds, because the tree
    lives on in `firewood` and the batch goes on naming something filed."""
    opened(tree)
    capsys.readouterr()

    assert main(["grub-out", "first-tree"]) == 0
    assert (tree / "firewood" / "first-tree.md").exists()
    assert "## 2. First tree" in archived(tree)


def test_the_offer_hands_back_no_item_the_verb_would_refuse(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Through the same function the verb refuses with, so the two cannot
    disagree. The frame still counts the **whole** traversal either way: an
    offer narrows rows and narrows no report."""
    opened(tree)
    assert offered(capsys, "fell") == []
    assert main(["next", "fell"]) == 0
    assert "0 of 2 items" in capsys.readouterr().err

    rooted(tree)
    assert offered(capsys, "fell") == ["first-tree"]
    assert main(["next", "fell"]) == 0
    assert "1 of 2 items" in capsys.readouterr().err


# --------------------------------------------------------------------------
# The close as a gate: a section still holding an unmarked sub-phase
# --------------------------------------------------------------------------


def test_a_section_holding_an_unmarked_sub_phase_cannot_be_archived(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The done line, from the command line. Nothing is written: the item is
    byte-identical afterwards and the archive document is untouched."""
    named(tree, "graft-1", "graft-2", "graft-3")
    assert main(["ripen", "first-tree", "graft-1"]) == 0
    path = tree / "orchard" / "first-tree.md"
    before = path.read_bytes()
    capsys.readouterr()

    assert main(["fell", "first-tree", "--record", RECORD]) == 2
    printed = capsys.readouterr()
    assert printed.err.startswith("ERROR:")
    assert "2 of 3 sub-phases with no mark: graft-2, graft-3" in printed.err
    assert path.read_bytes() == before
    assert "First tree" not in archived(tree)


def test_archive_plan_check_refuses_in_the_words_the_real_run_uses(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """6-1's identical-path rule over the new arm: `--check` runs the same
    grader and stops at the same place, so the two refusals match byte for
    byte and a session can ask before it commits to the record."""
    named(tree, "graft-1", "graft-2")
    capsys.readouterr()

    assert main(["fell", "first-tree", "--record", RECORD, "--check"]) == 2
    checked = capsys.readouterr().err
    assert main(["fell", "first-tree", "--record", RECORD]) == 2
    assert capsys.readouterr().err == checked


def test_a_section_whose_every_bullet_is_marked_closes(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The window 12-2 opened, shut. `skip` closes a bullet as squarely as
    `finish` does, so the section below is finished with one of each."""
    named(tree, "graft-1", "graft-2")
    assert main(["ripen", "first-tree", "graft-1"]) == 0
    assert main(["thin", "first-tree", "graft-2"]) == 0
    capsys.readouterr()

    assert main(["fell", "first-tree", "--record", RECORD]) == 0
    assert not (tree / "orchard" / "first-tree.md").exists()
    assert f"## 2. First tree\n\n{RECORD}\n" in archived(tree)


def test_a_section_abandoned_half_done_is_not_refused_by_the_unmarked_rule(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`decline`'s shape, from the command line: `grub-out` archives and
    **moves**, so a section with every bullet open goes in one run. Being half
    done is the whole content of that decision."""
    named(tree, "graft-1", "graft-2")
    capsys.readouterr()

    assert main(["grub-out", "first-tree"]) == 0
    assert (tree / "firewood" / "first-tree.md").exists()


def test_the_close_out_offer_drops_a_section_with_an_unmarked_bullet(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Through the same function the verb refuses with, so `next` stays the
    old tool's `--closeable` rather than handing back a run that would be
    refused. The frame still counts the whole traversal."""
    named(tree, "graft-1", "graft-2")
    assert offered(capsys, "fell") == []

    assert main(["ripen", "first-tree", "graft-1"]) == 0
    assert offered(capsys, "fell") == []

    assert main(["ripen", "first-tree", "graft-2"]) == 0
    assert offered(capsys, "fell") == ["first-tree"]


def test_a_section_whose_every_step_is_marked_still_takes_a_cursor(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The deadlock 16-1 removed, as the sequence a session performs. Cut a
    tree into steps, mark every one of them, and only then move the cursor —
    which is the order that locked this repo's own section 15 out of its close
    on 2026-09-11, because the cursor key a closing verb requires had become
    unwritable. The cursor lands, and no status rides with it."""
    path = named(tree, "graft-1", "graft-2")
    assert main(["ripen", "first-tree", "graft-1"]) == 0
    assert main(["thin", "first-tree", "graft-2"]) == 0
    capsys.readouterr()

    assert main(["graft-on", "first-tree", "--graft", "graft-2"]) == 0
    head = path.read_text()
    assert 'graft = "graft-2"' in head
    assert "graft-status" not in head

    assert main(["fell", "first-tree", "--record", RECORD, "--check"]) == 0


# --------------------------------------------------------------------------
# `absorbs`: the survivor the edges are pointed at, from the command line
# --------------------------------------------------------------------------
#
# `inarch` is the fixture's absorbing verb, out of the unnumbered
# `greenhouse`: `merge`'s shape, and not this repo's `merge`, which is the
# point. Its referents live in `orchard`, the one fixture state that declares
# `dependencies`.


def test_the_into_option_is_only_on_the_verb_that_absorbs(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Generated by what the verb declares, like every other option, and
    **required** there: an absorbing run with no survivor has nothing to point
    the edges at. The other dissolving verbs take the edges out instead, so
    offering them a survivor would be an option that means nothing."""
    for name in ("inarch", "compost", "fell", "grub-out", "transplant"):
        assert main([name, "--help"]) == 0
        printed = capsys.readouterr().out
        assert ("--into" in printed) == (name == "inarch")
        if name == "inarch":
            assert "[required]" in printed


def test_a_merge_with_no_survivor_refuses_and_deletes_nothing(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The polarity again: the option is required, so a forgotten survivor
    fails at the one moment it can still be supplied."""
    assert main(["sprout", "A seedling", "--body", "Prose.", "--cultivar", "heirloom"]) == 0
    capsys.readouterr()

    assert main(["inarch", "a-seedling"]) != 0
    assert "--into" in capsys.readouterr().err
    assert (tree / "greenhouse" / "a-seedling.md").exists()


def test_a_merge_repoints_every_edge_and_says_so_on_stderr(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """**The done line, end to end.** The original is gone, stdout carries the
    path it removed — there is no second file to name — and stderr names each
    item it edited and the key."""
    for title in ("A seedling", "B seedling"):
        assert main(["sprout", title, "--body", "Prose.", "--cultivar", "heirloom"]) == 0
    orchard(tree, "First tree")
    orchard(tree, "Second tree")
    for slug in ("first-tree", "second-tree"):
        path = tree / "orchard" / f"{slug}.md"
        path.write_text(path.read_text().replace(
            "title = ", 'after = ["a-seedling"]\ntitle = '
        ))
    document = archived(tree)
    capsys.readouterr()

    assert main(["inarch", "a-seedling", "--into", "b-seedling"]) == 0
    printed = capsys.readouterr()
    assert printed.out.strip() == "greenhouse/a-seedling.md"
    assert not (tree / "greenhouse" / "a-seedling.md").exists()
    assert archived(tree) == document

    repointed = [one for one in printed.err.splitlines() if "pointed" in one]
    assert len(repointed) == 2
    assert 'orchard/first-tree.md: pointed "a-seedling" at "b-seedling" in after' in (
        printed.err
    )
    assert 'orchard/second-tree.md: pointed "a-seedling" at "b-seedling" in after' in (
        printed.err
    )
    assert "a-seedling.md is gone" in printed.err
    assert '"b-seedling"' in (tree / "orchard" / "first-tree.md").read_text()


def test_a_merge_leaves_no_unknown_dependency_in_the_listing(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The invariant from the absorbing end: absence means *unknown*, and a
    merge leaves the default read clean because every edge now names an item
    that is still filed."""
    for title in ("A seedling", "B seedling"):
        assert main(["sprout", title, "--body", "Prose.", "--cultivar", "heirloom"]) == 0
    orchard(tree, "First tree")
    path = tree / "orchard" / "first-tree.md"
    path.write_text(path.read_text().replace(
        "title = ", 'after = ["a-seedling"]\ntitle = '
    ))
    assert main(["inarch", "a-seedling", "--into", "b-seedling"]) == 0
    capsys.readouterr()

    assert main(["list", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["unknown"] == []
    assert sorted(
        row["blocked-by"] for row in payload["rows"] if row["blocked-by"]
    ) == [["b-seedling"]]


# --------------------------------------------------------------------------
# `seeds`: the template option, from the command line
# --------------------------------------------------------------------------
#
# `strike` is the fixture's one seeding verb, and `hardwood`/`softwood` are its
# two templates. `sprout` beside it creates without the half, which is what
# makes "generated by what the verb declares" provable rather than asserted.


def test_the_from_option_is_only_on_the_verb_that_seeds(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Generated by the half, like `--record` and `--into`, and **not**
    required there: a seeding verb still takes `--body`, because `seeds` says
    the verb may be bodied from a template rather than that it must be."""
    for name in ("strike", "sprout", "pot-up", "mist", "transplant"):
        assert main([name, "--help"]) == 0
        printed = capsys.readouterr().out
        assert ("--from" in printed) == (name == "strike")
        if name == "strike":
            assert "[required]" not in printed


def test_the_from_option_names_the_templates_the_declaration_holds(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """6-1's rule over the newest option: a session that had to learn the
    names some other way would parse `plan.toml` for itself, and a name you
    can only discover by triggering a refusal is hiding with extra steps."""
    # Normalized, because click wraps a help line at the terminal width and
    # the names are what is being graded, not where the wrap falls.
    printed = " ".join(helped("strike", capsys).split())
    assert "One of: hardwood, softwood." in printed


def test_a_seeding_verb_with_no_templates_says_so_rather_than_listing_nothing(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The shape the loader deliberately leaves legal, and the reason the
    option is not a `click.Choice`: an empty choice is unconstructible, and a
    help line trailing off after "One of:" would read as a bug."""
    text = (tree / "plan.toml").read_text()
    (tree / "plan.toml").write_text(
        "".join(
            chunk
            for chunk in re.split(r"(?m)^(?=\[)", text)
            if not chunk.startswith("[templates.")
        )
    )
    printed = " ".join(helped("strike", capsys).split())
    assert "--from" in printed and "One of:" not in printed
    assert "This plan.toml declares none." in printed


def test_a_sets_key_called_from_refuses_by_name(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The `--body`, `--above` and `--check` precedent, over the one generated
    option that can collide: `--record` and `--into` ride on `dissolves`,
    which refuses `sets` back in `plan.toml`, while a seeding verb has no such
    refusal and `from` is a legal key name."""
    plan = (tree / "plan.toml").read_text().replace(
        'sets  = ["for-tree", "for-step"]', 'sets  = ["for-tree", "for-step", "from"]'
    )
    (tree / "plan.toml").write_text(plan + '\n[keys.from]\ndoc = "method.md#from"\n')
    (tree / "method.md").write_text((tree / "method.md").read_text() + "\n## from\n")
    assert main(["--help"]) == 2
    err = capsys.readouterr().err
    assert 'transitions.strike.sets names "from"' in err
    assert "One option cannot mean two things" in err


def test_a_seeded_run_files_the_named_document(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole feature from the command line: the option reaches the arm
    that reads it rather than being swept into the head with the `sets`
    keys, and what comes out is an ordinary item."""
    assert main(["strike", "A batch", "--from", "softwood"]) == 0
    filed = tree / "propagator" / "a-batch.md"
    assert capsys.readouterr().out.strip() == str(filed.relative_to(tree))
    prose = (tree / "softwood-cuttings.md").read_text()
    assert filed.read_text().endswith(prose.strip("\n") + "\n")
    assert "template" not in filed.read_text()


def test_a_seeded_run_and_a_bodied_one_cannot_be_asked_for_together(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The executor's refusal, in the executor's words, reaching the operator
    as every refusal does: rc 2, one `ERROR:` line on stderr, nothing filed."""
    assert main(["strike", "A batch", "--from", "hardwood", "--body", "Prose."]) == 2
    assert "both --from and --body" in capsys.readouterr().err
    assert list((tree / "propagator").iterdir()) == []


# --------------------------------------------------------------------------
# The contract: what `--help` hands the caller after the options
# --------------------------------------------------------------------------
#
# Generated from the `Transition` the command is generated from, so these are
# graded over the *whole fixture declaration* rather than over one verb: a
# consumer's verbs get the epilog identically, and there is no verb-shaped
# branch for a test to have to pick a side of. docs/method.md#the-contract.


def helped(name: str, capsys: pytest.CaptureFixture[str]) -> str:
    assert main([name, "--help"]) == 0
    return capsys.readouterr().out


def test_every_transitions_help_names_its_own_doc_and_every_key_it_sets(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The `Reading` block, and the done line it serves: `pointer_errors`
    proves every pointer resolves, and this is what lets a caller follow one.
    A key's `help` was always on its option and says what to pass; its `doc`
    says what the value *is*, and was surfaced nowhere."""
    declaration = load(tree / "plan.toml")
    for transition in declaration.transitions.values():
        out = helped(transition.name, capsys)
        assert "Reading" in out
        assert transition.doc in out, transition.name
        for key in transition.sets:
            assert declaration.keys[key].doc in out, (transition.name, key)


def test_the_help_says_where_the_item_goes_in_each_of_the_four_shapes(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A verb declares where the item goes, or that it goes nowhere. The
    in-place shape is the one worth spelling: `from orchard to orchard` would
    read as a move that happens not to move."""
    assert "into greenhouse" in helped("sprout", capsys)
    assert "out of greenhouse and into orchard" in helped("transplant", capsys)
    assert "stays in orchard" in helped("graft-on", capsys)
    assert "out of orchard, and the file is deleted" in helped("fell", capsys)


def test_the_help_spells_what_the_verb_requires_and_refuses(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = helped("transplant", capsys)
    assert "Requires" in out and "cultivar" in out
    assert "Refuses" in out and 'cultivar = "hybrid"' in out


def test_the_contract_names_the_keys_the_run_drops(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A key going off the head is as much a fact about the run as one going
    on, and a caller that read the contract and then found a key gone would
    have met an effect nothing named, which is hiding with extra steps.

    Its neighbour is the control: `thin` marks the same body out of the same
    state and drops nothing, so the block is absent there. Absence is the
    signal, the shape `Declares` and `Running it` already have."""
    declaration = load(tree / "plan.toml")
    dropping = declaration.transitions["ripen"].drops
    assert dropping, "the fixture's ripen drops nothing, so this proves nothing"
    out = helped("ripen", capsys)
    assert "Drops" in out
    for key in dropping:
        assert key in out

    assert not declaration.transitions["thin"].drops
    assert "Drops" not in helped("thin", capsys)


def test_the_help_names_the_halves_the_verb_declares(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """So the interpreter knows a claim will be taken before it takes one."""
    assert "Declares" in helped("tend", capsys) and "claims" in helped("tend", capsys)
    out = helped("inarch", capsys)
    assert "dissolves" in out and "absorbs" in out
    assert "Declares" not in helped("harvest", capsys)


def test_the_help_of_a_verb_with_a_policy_carries_a_running_it_block(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The second pointer, in a block of its own rather than a labelled line
    inside `Reading`: one says what the verb *means*, the other what a session
    *does*, and a caller should not have to read a label to tell them apart.
    docs/method.md#the-interpreter."""
    declaration = load(tree / "plan.toml")
    policy = declaration.transitions["espalier"].policy
    assert policy, "the fixture declares no policy, so this proves nothing"
    out = helped("espalier", capsys)
    assert "Running it" in out
    assert policy in out
    # And it is not folded into the block that answers the other question.
    reading, _, running = out.partition("Running it")
    assert policy not in reading and declaration.transitions["espalier"].doc in reading
    assert running


def test_the_help_of_a_verb_with_no_policy_carries_no_running_it_block(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Absence is the signal, the shape `Declares` already has: silence is how
    the interpreter is told there is nothing further to read. `graft-on` is
    `espalier`'s neighbour — same state, same direction — so what differs is
    the declaration and nothing else."""
    assert load(tree / "plan.toml").transitions["graft-on"].policy is None
    assert "Running it" not in helped("graft-on", capsys)


# --------------------------------------------------------------------------
# `--check`: the run, stopped at the seam
# --------------------------------------------------------------------------


def tracked(tree: Path) -> dict[str, bytes]:
    """The tree as `--check` promises to leave it: everything but the run
    lock, which every mutating path takes and a check takes too."""
    return {
        str(path.relative_to(tree)): path.read_bytes() if path.is_file() else b""
        for path in sorted(tree.rglob("*"))
        if not str(path.relative_to(tree)).startswith("local")
    }


def test_every_generated_transition_carries_the_check_flag(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Uniform arms over a bespoke rule — the creating verbs included, because
    the reservation one of them makes partway through is the write a bespoke
    rule would have let through."""
    for name in load(tree / "plan.toml").transitions:
        assert "--check" in helped(name, capsys), name


def test_a_check_that_passes_prints_its_sentence_and_writes_nothing(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["sprout", "A seedling", "--body", "Prose.", "--cultivar", "heirloom"]) == 0
    capsys.readouterr()
    before = tracked(tree)

    assert main(["transplant", "a-seedling", "--check"]) == 0
    printed = capsys.readouterr()
    assert printed.out.startswith("transplant would move ")
    assert printed.err == ""
    assert tracked(tree) == before


def test_a_check_that_refuses_is_the_refusal_a_real_run_gives(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Byte-identical stderr, empty stdout, rc 2 — because it is the same code
    raising it. This is the property the flag exists for."""
    assert main(["sprout", "A seedling", "--body", "Prose."]) == 0
    capsys.readouterr()
    before = tracked(tree)

    assert main(["transplant", "a-seedling", "--check"]) == 2
    checked = capsys.readouterr()
    assert checked.out == ""
    assert checked.err.count("ERROR: ") == 1
    assert tracked(tree) == before

    assert main(["transplant", "a-seedling"]) == 2
    assert capsys.readouterr().err == checked.err


def test_a_check_on_a_creating_verb_reserves_no_filename(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The trap: `_create`'s reservation is a write partway through the arm,
    so this is the assertion the other checks could not make for it."""
    before = tracked(tree)
    assert main(["sprout", "A seedling", "--body", "Prose.", "--check"]) == 0
    assert "a-seedling.md" in capsys.readouterr().out
    assert tracked(tree) == before


def test_a_check_on_a_dissolving_verb_leaves_the_item_and_the_archive(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    orchard(tree, "First tree")
    capsys.readouterr()
    before = tracked(tree)

    assert main(["fell", "first-tree", "--record", "Because.", "--check"]) == 0
    assert "file `## 2. First tree` in" in capsys.readouterr().out
    assert tracked(tree) == before

    # And the run it was checking really does all three, so the check was
    # reporting an effect rather than a no-op.
    assert main(["fell", "first-tree", "--record", "Because."]) == 0
    assert tracked(tree) != before
    assert not (tree / "orchard" / "first-tree.md").exists()


def test_the_check_says_which_key_a_run_would_drop(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A run that removed a key the check had not named would be doing
    something the check did not say — which is the whole property the flag
    buys, and the make-problems-visible failure if it is missed."""
    named(tree, "graft-1", "graft-2")
    assert main(["graft-on", "first-tree", "--graft", "graft-1", "--graft-status", "open"]) == 0
    capsys.readouterr()
    before = tracked(tree)

    assert main(["ripen", "first-tree", "graft-1", "--check"]) == 0
    printed = capsys.readouterr()
    assert "drop graft-status" in printed.out
    assert tracked(tree) == before

    # And the run it was checking really does it, so the clause reports an
    # effect rather than a form of words.
    assert main(["ripen", "first-tree", "graft-1"]) == 0
    assert "graft-status" not in (tree / "orchard" / "first-tree.md").read_text()


def test_a_run_says_nothing_about_dropping_a_key_the_item_lacks(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The clause is built from what this run **resolved**, not from what the
    declaration names — `_would`'s rule, from the side that would regress
    silently. The verb is the same one; only the head differs, and a tree
    whose status key was never written has nothing to lose."""
    named(tree, "graft-1", "graft-2")
    capsys.readouterr()
    assert "graft-status" not in (tree / "orchard" / "first-tree.md").read_text()

    assert main(["ripen", "first-tree", "graft-1", "--check"]) == 0
    assert "drop" not in capsys.readouterr().out


def test_a_finished_sub_phase_leaves_a_cursor_and_no_status(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """End to end, and the shape the listing is meant to read in afterwards: a
    cursor saying where the last session was, and no status saying it is still
    at work. The pair is what tells the three cases apart — no cursor and no
    status is a section never started, a cursor alone is a session that
    finished what it was on, and both is work in flight."""
    named(tree, "graft-1", "graft-2")
    assert main(["graft-on", "first-tree", "--graft", "graft-1", "--graft-status", "in progress"]) == 0
    capsys.readouterr()

    assert main(["list", "--state", "orchard"]) == 0
    working = capsys.readouterr().out
    assert "graft            graft-1" in working
    assert "graft-status     in progress" in working

    assert main(["ripen", "first-tree", "graft-1"]) == 0
    capsys.readouterr()
    assert main(["list", "--state", "orchard"]) == 0
    finished = capsys.readouterr().out
    assert "graft            graft-1" in finished
    assert "graft-status" not in finished


def test_a_sets_key_colliding_with_the_check_flag_refuses_by_name(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The `--body`, `--above` and `--last` precedent, over the one flag that
    is on **every** generated command: a declared key called `check` becomes
    `--check` too, and one option cannot mean two things."""
    plan = (tree / "plan.toml").read_text().replace(
        'sets     = ["rootstock", "pest"]', 'sets     = ["rootstock", "check"]'
    )
    (tree / "plan.toml").write_text(plan + '\n[keys.check]\ndoc = "method.md#check"\n')
    (tree / "method.md").write_text((tree / "method.md").read_text() + "\n## check\n")
    assert main(["--help"]) == 2
    err = capsys.readouterr().err
    assert 'transitions.transplant.sets names "check"' in err
    assert "One option cannot mean two things" in err
