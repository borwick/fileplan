"""The guards over this repo's own artifacts: what they cite, and what they say.

Four behaviours. The first two were pinned from an earlier implementation:

* **Nothing in the tool cites a document the tree does not ship.** The old
  tool's version (its `scripts/tests/test_plan.py`, §
  `test_nothing_in_scripts_cites_a_document_this_repo_does_not_ship`) was a
  blacklist of ten stale needles, which catches only what someone remembered
  to name. This one *extracts* the citations instead, so a citation nobody
  anticipated is graded the same as one that was.
* **A key's meaning has exactly one home, and a test asserts no second copy.**
  Three mechanical teeth — a shared anchor, an uncited section, a term defined
  in two documents. No prose diffing: that grades style and drifts.

The third is 3-1's, and it grades an *absence*: **no named report flag exists
anywhere in the CLI.** The old tool's five (`--ready`, `--closeable`,
`--stale`, `--candidates`, `--unsized`) were one question asked five times,
and `next VERB` asks it once. A guard over a thing that is not there is the
only kind that can keep it from coming back.

The fourth is 6-1's, and it grades **output** rather than source: no verb's
[contract](../docs/method.md#the-contract) names another verb this repo
declares. `test_cli.py`'s control says no per-verb *code* exists; this says
no per-verb *line* reached the help text either, which is what the epilog
being generated from the `Transition` buys.

`declaration.pointer_errors` already grades the `doc =` fields at *every*
invocation. What it structurally cannot see is a citation in a comment or a
docstring, which is not a `doc =` field — `plan.toml`'s `# See
docs/method.md#title` is exactly that, and so is every `docs/method.md#…` in
`src/`. Both readers ask `declaration.heading_slugs` what headings a
document has, so there is one answer to that question rather than two.

**This module grades the repo's own artifacts on purpose**, like the controls
in `test_cli.py` and `test_declaration.py` beside it. That is a different
thing from 1-1's lesson — the suite must never grade *behaviour* against the
repo's vocabulary, which is what `tests/fixtures/plan.toml` is for. A document
is not behaviour; there is only one of it, and grading it anywhere else would
be grading a copy.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import click
import pytest

from conftest import FIXTURE_FILES

from fileplan import read
from fileplan.cli import HALVES, LIST_HELP, _build_group, contract, main
from fileplan.declaration import heading_slugs, load

REPO = Path(__file__).resolve().parent.parent
METHOD = Path("docs/method.md")

#: The filed items. They cite prose two ways — a `draft` pointer in the head
#: and `§`-style references in the body — and both are the same kind of
#: pointer as a `doc =`: a claim that this repo ships a document. The tool
#: deliberately does not grade a head value at read time (one bad value would
#: break a whole listing rather than one item), so this is where a `draft`
#: naming a document the repo does not ship is caught.
#:
#: **Every declared state, not `plan/` alone** (8-5, 2026-09-06). The scope
#: was `plan/` for as long as `plan/` was where the items were, and section 8
#: closing emptied it — which turned the mutation check below vacuous and, in
#: doing so, named the hole it had been standing next to all along: a
#: `someday-maybe/` item's pointers were graded by nothing, and one of them
#: names a document under `docs/templates/`. The directories come out of
#: `load()` rather than being listed here, for `scaffold.py`'s reason: a
#: second reader of the declaration is what the contract exists to prevent.
ITEMS = tuple(
    Path(state.path) for state in load(REPO / "plan.toml").states.values()
)

#: The head line an item spells its draft on. Read as text rather than
#: through the loader: this module grades the repo's artifacts as documents,
#: and a head that would not parse is `test_item.py`'s complaint, not this
#: one's.
DRAFT = re.compile(r'^draft = "([^"]*)"$', re.MULTILINE)

#: A citation, wherever it appears: a path under `docs/` to a Markdown file,
#: optionally naming a section with `#anchor`. One pattern, because the
#: verb-name control in `test_cli.py` strips citations out of its haystack
#: with this same regex — a citation is a pointer to prose, not code that
#: names a verb.
CITATION = re.compile(r"docs/[A-Za-z0-9_./-]+\.md(?:#([A-Za-z0-9_-]+))?")

#: Everything that may cite and is in the shipping set: the tool, its
#: declaration, its packaging and the documents a consumer gets. Every name is
#: read unconditionally, so one going missing is loud. `pyproject.toml` is here
#: because its comments cite too, and while it was not a citation shipped a
#: pointer to a document this repo keeps for itself.
SOURCES = (
    "plan.toml",
    "pyproject.toml",
    "README.md",
    "docs/method.md",
    "docs/procedures.md",
    "docs/initialization.md",
    "docs/retrofit.md",
    "docs/index.md",
    "docs/ai-disclosure.md",
)

#: The four that may cite and do **not** ship. This module ships, so in a
#: built tree they are simply absent — and `read_text()` on an absent file
#: raises rather than failing a claim. They are graded where they are and
#: skipped where they are not.
#:
#: Written out here rather than read from the private tree's own publishing
#: code, because that does not ship and a shipped test importing it would not
#: run in the built tree. The control that these two lists agree with what is
#: shipped lives on the side of the fence that has both.
OWN_SOURCES = (
    "CLAUDE.md",
    "docs/pysmelly-adjudication.md",
    "docs/publishing.md",
    "docs/releasing.md",
    "docs/writing-style.md",
)

#: The skills this repo ships. They are the **interpreter**
#: (`../docs/method.md#the-interpreter`), and an interpreter is nothing but
#: pointers at the program: a skill citing a section the repo does not ship
#: sends a session to read a document that is not there, which is the exact
#: failure the guard over `src/` exists for, one artifact further out.
#:
#: Their real home, not the `.claude/skills` link at it. That link is this
#: tree's own harness wiring: a session working here discovers skills only
#: under `.claude/`, and one home with a link at the other is how the two
#: paths cannot drift. Reading through it made the link part of the shipping
#: set, which put a `.claude/` into a repository no session works in. Read at
#: the real path, these guards also grade what the wheel carries, which is
#: the copy a consumer actually installs.
SKILLS = Path("src/fileplan/skills")

#: The document a `policy =` points at: what a session *does* around a run,
#: against `docs/method.md`'s what a verb means.
PROCEDURES = Path("docs/procedures.md")

#: The release procedure, and a document **nothing points at with a
#: `policy =`**: it is not a transition, so the orphan guard over `PROCEDURES`
#: would refuse it. It stopped shipping on 2026-09-12 (John), because what it
#: walks is *this* project's release — the account, the name on the index,
#: which of two trees uploads — and a consumer who installed the tool has no
#: use for any of it. So it is in `OWN_SOURCES` for `ADJUDICATION`'s reason,
#: and graded where it is there for the same two things: its citations
#: resolve, and its headings do not repeat a meaning that already has a home.
RELEASING = Path("docs/releasing.md")

#: The walk from an empty directory, and the second shipped document nothing
#: points at with a `policy =`. It was the *adoption* walk until 2026-09-12
#: (John). Two documents told apart only by their starting state cannot be
#: named by two words that mean the same thing, and adoption and retrofit are
#: near synonyms. `init` is the command one walk runs and the other refuses
#: by name, so the command names the walk. Graded beside the others for the
#: same two things: its citations resolve, and its headings do not repeat a
#: meaning that has a home.
INITIALIZATION = Path("docs/initialization.md")

#: The other half of the pair, and the third shipped document nothing points
#: at with a `policy =`: `initialization.md` walks an empty directory, this
#: one walks a tree that already has work in it. Two documents rather than two
#: halves of one, because a reader of either never needs the other's starting
#: state — and so the one-home guard has to hold them apart, which is what it
#: is here for.
RETROFIT = Path("docs/retrofit.md")

#: How the tool was written, and the fifth shipped document nothing points at
#: with a `policy =`. It is about the *project* rather than about the tool,
#: which is why no verb reaches it — but it ships, so it is graded beside the
#: others for the same two things: its citations resolve, and its headings do
#: not repeat a meaning that already has a home. The README says the fact in
#: one sentence and this holds what the fact means, which is the split every
#: other pair here uses.
DISCLOSURE = Path("docs/ai-disclosure.md")

#: The index over everything under `docs/`. Graded here for the two things
#: every shipped document is graded for — its citations resolve, and its
#: headings do not repeat a meaning that has a home — plus one of its own,
#: below: an index that names a document is a promise, and the promise is
#: only kept while every document is named and every name resolves.
INDEX = Path("docs/index.md")

#: The harness a `pysmelly` pass is adjudicated under, and the fourth
#: document nothing points at with a `policy =`. Nothing can: the pass is a
#: **session** rather than a transition — like `do-next` — so there is no verb
#: for a `policy =` to hang on, and a section of it in `docs/procedures.md`
#: would be an orphan the guard over `PROCEDURES` refuses. Graded here for the
#: same two things as the three above: its citations resolve, and its headings
#: do not repeat a meaning that already has a home — the tool's own guidance
#: holds what the tool means, and this holds only what this repo has to answer
#: for itself. It is in `OWN_SOURCES` rather than `SOURCES`, so every guard that
#: reads it reads it only where it is there.
ADJUDICATION = Path("docs/pysmelly-adjudication.md")

#: How the public copy is built: the two trees, the three gates, and what
#: nobody automated. It is the account of `publish/`, which does not ship, so
#: it does not either — and it names the strings the checker suppresses, so it
#: could not. It is in `OWN_SOURCES` for `ADJUDICATION`'s reason, and graded
#: here for the same two things: its citations resolve, and its headings do not
#: repeat a meaning that already has a home.
PUBLISHING = Path("docs/publishing.md")

#: How this repo writes the documents people read, and the fifth document
#: nothing points at with a `policy =`. It does not ship, for `PUBLISHING`'s
#: reason: it is about this tree's practice rather than about the tool, and it
#: quotes prose the README has since cut. Graded where it is there for the
#: same two things as the others: its citations resolve, and its headings do
#: not repeat a meaning that already has a home.
STYLE = Path("docs/writing-style.md")

#: Headings that hold other headings rather than a meaning. A pointer names a
#: leaf; these are the shelves the leaves sit on.
CONTAINERS = frozenset(
    {"the-method", "states", "keys", "item-files", "transitions"}
)


#: One fenced block, opening and closing fence at the start of a line.
FENCED = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)

#: What makes a fenced block a **transcript** rather than an example: a shell
#: prompt, in the style every walked document here pastes output in.
PROMPT = re.compile(r"^\$ ", re.MULTILINE)


def prose(text: str) -> str:
    """``text`` with pasted terminal output taken out.

    A transcript shows what the **reader's** tree prints, so a `docs/….md` in
    one is a pointer into *their* documents rather than one this repo offers —
    `docs/initialization.md` walks the starter declaration, whose contract names
    sections of the stub documents `init` wrote. Grading those against this
    repo asks the wrong tree.

    Structural rather than a list of exempted documents, which is what 1-6
    declined when it chose extraction: a name list catches only what somebody
    remembered to add, and the next walked document would have to remember
    itself. It costs nothing that was being graded — a fenced *example* has no
    prompt in it, so `docs/method.md`'s TOML snippets, which really do name
    this repo's own sections, stay in the haystack.
    """
    return FENCED.sub(
        lambda block: "" if PROMPT.search(block.group(0)) else block.group(0), text
    )


def citations(text: str) -> list[tuple[str, str | None]]:
    """Every `(relative path, anchor or None)` cited in ``text``."""
    return [
        (match.group(0).split("#")[0], match.group(1))
        for match in CITATION.finditer(text)
    ]


def _filed() -> list[Path]:
    """Every item file, in every declared state, sorted.

    A state whose directory does not exist yet is empty rather than broken,
    which is the listing's own rule; an empty *tree* is a legitimate resting
    state and this returns nothing for it, so the guards that need a haystack
    say so themselves rather than passing vacuously.
    """
    return sorted(
        path
        for state in ITEMS
        for path in (REPO / state).glob("*.md")
    )


def _own_sources() -> list[str]:
    """The names in `OWN_SOURCES` this tree actually has.

    All of them, here. None of them in a tree built from the manifest, which
    is the only reason this function exists — see `OWN_SOURCES`.
    """
    return [name for name in OWN_SOURCES if (REPO / name).exists()]


def _haystack() -> list[Path]:
    """Every file `_cited()` extracts from.

    Apart from `_cited()` so a guard can ask what was **read** rather than
    what was found. The two differ for any file that cites nothing, and a
    filed item citing nothing is the ordinary case rather than a defect.
    """
    files = [REPO / name for name in (*SOURCES, *_own_sources())]
    files += sorted((REPO / "src").rglob("*.py"))
    files += _filed()
    files += sorted((REPO / SKILLS).rglob("*.md"))
    return files


def _cited() -> list[tuple[str, str, str | None]]:
    """Every citation in the repo, as `(where, relative path, anchor)`."""
    found: list[tuple[str, str, str | None]] = []
    for path in _haystack():
        where = str(path.relative_to(REPO))
        found += [
            (where, target, anchor)
            for target, anchor in citations(prose(path.read_text()))
        ]
    return found


def _pointers() -> list[tuple[str, str]]:
    """Every `doc =` in the repo's own declaration, as `(what, pointer)`."""
    declaration = load(REPO / "plan.toml")
    entries = (
        list(declaration.states.values())
        + list(declaration.keys.values())
        + list(declaration.transitions.values())
    )
    found = [(entry.name, entry.doc) for entry in entries if entry.doc]
    # And the transition's second pointer. A `policy` and a `doc` naming one
    # section would be two homes for one meaning exactly as two `doc`s would,
    # so they are graded in one list rather than two.
    found += [
        (f"{transition.name} (policy)", transition.policy)
        for transition in declaration.transitions.values()
        if transition.policy
    ]
    return found


def _anchors_into_the_method() -> set[str]:
    """Every section of `docs/method.md` something names, however it names it."""
    named = {
        anchor
        for _, target, anchor in _cited()
        if target == str(METHOD) and anchor
    }
    named |= {
        pointer.partition("#")[2]
        for _, pointer in _pointers()
        if pointer.startswith(f"{METHOD}#")
    }
    return named


# --------------------------------------------------------------------------
# The citation guard: nothing cites a document this repo does not ship
# --------------------------------------------------------------------------


def test_every_citation_names_a_document_this_repo_ships() -> None:
    """Each cited file exists, and each anchor is a heading in it. This covers
    what `pointer_errors` cannot reach: comments and docstrings."""
    cited = _cited()
    assert cited, "the extractor found no citations, so this guard proves nothing"
    for where, target, anchor in cited:
        path = REPO / target
        assert path.exists(), f"{where} cites {target}, which this repo does not ship"
        if anchor is None:
            continue
        slugs = heading_slugs(path)
        assert slugs is not None
        assert anchor in slugs, f'{where} cites "#{anchor}", not a heading in {target}'


def test_the_citation_guard_catches_a_fabricated_citation() -> None:
    """The mutation check. Fed a document that does not exist and an anchor
    that is not a heading, the same extractor must produce both — a guard that
    silently matched nothing would pass the check above forever."""
    fabricated = "See docs/nowhere.md and docs/method.md#no-such-section."
    assert citations(fabricated) == [
        ("docs/nowhere.md", None),
        ("docs/method.md", "no-such-section"),
    ]
    assert not (REPO / "docs/nowhere.md").exists()
    slugs = heading_slugs(REPO / METHOD)
    assert slugs is not None and "no-such-section" not in slugs


def test_the_transcript_strip_takes_out_pasted_output_and_nothing_else() -> None:
    """The mutation check on `prose`. Both halves, because a strip that took
    everything would pass the guard above forever and a strip that took
    nothing would have fixed nothing: a fenced block with a prompt in it goes,
    a fenced block without one stays, and prose either side of both is
    untouched."""
    transcript = "Before.\n\n```\n$ fileplan x --help\n  x  docs/method.md#x\n```\n\nAfter."
    assert citations(transcript) == [("docs/method.md", "x")]
    assert citations(prose(transcript)) == []
    assert "Before." in prose(transcript) and "After." in prose(transcript)

    example = '```toml\ndoc = "docs/method.md#work"\n```'
    assert citations(prose(example)) == [("docs/method.md", "work")]

    # And the shape that made this necessary: this repo really does ship a
    # walked document whose every citation is inside a transcript, and really
    # does ship examples that are not.
    walked = (REPO / INITIALIZATION).read_text()
    assert citations(walked), "the walk cites nothing, so this proves nothing"
    assert citations(prose(walked)) == []
    method = (REPO / METHOD).read_text()
    assert citations(prose(method)), "the method's examples were stripped too"


def test_the_citation_guard_reads_every_source_it_can_be_sure_of() -> None:
    """The two halves of the source list, each graded the way it can be.

    `SOURCES` ships, so every name must be there and a missing one is a
    defect. `OWN_SOURCES` does not, so absence is the built tree's ordinary
    shape rather than a defect.

    The tolerance is the risk, and it is halved here and halved next door.
    Here: every own source that *was* read has to have contributed a citation,
    so a file that stopped being read is not silently skipped. There: whether
    this tree has both of them at all is `publish/test_publish.py`'s to say,
    because only that side knows which tree it is looking at."""
    missing = [name for name in SOURCES if not (REPO / name).exists()]
    assert missing == [], missing

    cited = _cited()
    assert cited, "the extractor found no citations, so this guard proves nothing"
    for name in _own_sources():
        assert any(where == name for where, _, _ in cited), name


def test_the_citation_guard_reads_every_filed_item() -> None:
    """The mutation check on the item files being in the haystack at all. A
    `draft` naming a document this repo does not ship is a dead pointer the
    tool never grades — `item.head_errors` grades an item's *shape*, and
    grading values at read time would break a whole listing over one item —
    so it is caught here or nowhere. Every item file in **every declared
    state**, not a sample and not one state: one left out is one whose
    pointers nothing checks.

    Over what the extractor **reads**, not over what it found. Asking what it
    found passes only while every filed item happens to cite something, and
    the first one that cites nothing then reads as unguarded when it is
    simply quiet. A carrier's filed findings are where that showed up."""
    filed = {str(path.relative_to(REPO)) for path in _filed()}
    if not filed:
        # A tree with nothing filed is a legitimate resting state, and a
        # clone of the published repo is one: it ships with an empty plan by
        # design. So the missing haystack is skipped rather than asserted
        # away — a skip says out loud that nothing was proved, which a
        # vacuous pass does not, and `pytest -q` prints the count. The
        # control that *this* tree has the haystack lives in `publish/`,
        # which is the side of the fence that knows it is the private one.
        pytest.skip("no items are filed, so there is no haystack to read")
    read = {str(path.relative_to(REPO)) for path in _haystack()}
    assert filed <= read, sorted(filed - read)


def test_a_draft_in_a_head_is_a_citation_the_guard_grades() -> None:
    """The head value really does reach the extractor. A `draft` is a pointer
    at prose spelled the way a `doc =` is, so the same regex finds it — which
    is why catching a dead one cost the tool no code at all.

    Graded on a **constructed** head as well as on whatever is filed, because
    `draft` belongs to one state's items and a tree can legitimately hold
    none: with `plan/` empty this asserted over nothing and passed, which is
    the vacuum an assertion on a real item's key cannot see itself falling
    into (8-5, 2026-09-06).
    """
    head = '+++\ndraft = "docs/method.md"\n+++\n'
    assert [match.group(1) for match in DRAFT.finditer(head)] == ["docs/method.md"]
    assert ("docs/method.md", None) in citations(head)

    for path in _filed():
        text = path.read_text()
        for match in DRAFT.finditer(text):
            assert (match.group(1), None) in citations(text)


def test_the_citation_guard_reads_every_skill_and_no_skill_cites_a_document() -> None:
    """The skills are in the haystack, every one, and none of them cites a
    document under `docs/`. The wheel carries the skills and not `docs/`, so a
    citation there sends an installed session to a file it does not have.
    What travels with the tool is `--help` and `--json`, and the `Reading`
    and `Running it` blocks name the consumer's own documents."""
    shipped = {path for path in (REPO / SKILLS).rglob("*.md")}
    assert shipped, "this repo ships no skills, so this guard proves nothing"
    assert shipped <= set(_haystack())
    names = {str(path.relative_to(REPO)) for path in shipped}
    assert [cited for cited in _cited() if cited[0] in names] == []


def test_every_skill_this_repo_ships_opens_with_a_name_and_a_description() -> None:
    """A skill whose frontmatter is missing or malformed silently never loads,
    which is the one failure nothing else here catches: every guard in this
    module grades what a skill *says*, and a skill nobody reads says nothing.
    The fields are graded, not the whole shape — `name` is what `/name`
    resolves and `description` is what decides whether it is the right one."""
    shipped = sorted((REPO / SKILLS).rglob("*.md"))
    assert shipped, "this repo ships no skills, so this guard proves nothing"
    for path in shipped:
        where = path.relative_to(REPO)
        lines = path.read_text().splitlines()
        assert lines and lines[0] == "---", f"{where} opens with no frontmatter"
        closed = lines.index("---", 1)
        fields = {
            line.split(":", 1)[0]
            for line in lines[1:closed]
            if ":" in line and not line.startswith((" ", "\t"))
        }
        assert {"name", "description"} <= fields, (str(where), sorted(fields))


def test_the_citation_guard_reads_the_comment_pointer_errors_cannot() -> None:
    """`plan.toml` cites `docs/method.md#title` in a *comment*, because
    `title` is intrinsic and has no table to hold a `doc =`. `pointer_errors`
    reads `doc =` fields only, so that citation is unchecked by the loader and
    checked here — the class this guard exists for."""
    declared = {pointer for _, pointer in _pointers()}
    assert f"{METHOD}#title" not in declared
    assert (str(METHOD), "title") in citations((REPO / "plan.toml").read_text())


# --------------------------------------------------------------------------
# The one-home guard: a meaning is written down exactly once
# --------------------------------------------------------------------------


def test_no_two_doc_pointers_name_the_same_anchor() -> None:
    """One section that is the meaning of two things is the drift, stated
    directly: whichever of the two the section stops describing is the one
    that now has no home."""
    pointers = [pointer for _, pointer in _pointers()]
    assert len(set(pointers)) == len(pointers), sorted(pointers)


def test_the_shared_anchor_check_catches_two_things_pointing_at_one_section() -> None:
    """The mutation check on it."""
    pointers = [f"{METHOD}#plan", f"{METHOD}#plan"]
    assert len(set(pointers)) != len(pointers)


def test_every_section_of_the_method_is_cited() -> None:
    """An orphan section is either a second copy waiting to happen or one left
    behind by a verb that was removed. Every leaf heading must be named by a
    `doc =` pointer or by an anchored citation from code or prose; the
    container headings hold sections rather than meanings and are exempt."""
    leaves = heading_slugs(REPO / METHOD, level=3)
    assert leaves, "docs/method.md has no ### sections, so this guard proves nothing"
    assert not leaves & CONTAINERS, "a container heading is not a leaf"
    assert leaves - _anchors_into_the_method() == set()


def test_the_orphan_check_would_catch_an_uncited_section() -> None:
    """The mutation check. A section nothing names is a difference the guard
    reports, and every container heading really is a heading of `method.md` —
    so the exemption list names sections that exist rather than typos."""
    assert {"an-orphan"} - _anchors_into_the_method() == {"an-orphan"}
    assert CONTAINERS <= (heading_slugs(REPO / METHOD) or set())


def test_every_procedure_is_named_by_a_policy_pointer() -> None:
    """The orphan guard over the new document, mirroring the method's. A
    procedure nothing points at is one no session will ever be sent to read —
    either a verb lost its `policy` or the procedure was written for a verb
    that was never declared. Sections are named after the **procedure** rather
    than the verb, so this is the only thing that joins the two."""
    procedures = heading_slugs(REPO / PROCEDURES, level=2)
    assert procedures, "the procedures document has no sections to check"
    named = {
        pointer.partition("#")[2]
        for _, pointer in _pointers()
        if pointer.startswith(f"{PROCEDURES}#")
    }
    assert procedures - named == set()


def test_the_procedure_orphan_check_would_catch_one_nothing_points_at() -> None:
    """The mutation check on it, the shape the method's orphan check has."""
    named = {
        pointer.partition("#")[2]
        for _, pointer in _pointers()
        if pointer.startswith(f"{PROCEDURES}#")
    }
    assert named, "no transition declares a policy, so this proves nothing"
    assert {"an-orphan"} - named == {"an-orphan"}


def test_no_heading_is_a_heading_in_two_shipped_documents() -> None:
    """A term is defined once. `README.md` says what the tool is; the meaning
    of every word in `plan.toml` is `docs/method.md`; and the procedures say
    what a session *does*, which is the one thing the method deliberately does
    not. A heading in two of them would be two homes for one meaning, and the
    procedures are the likeliest place for it — a procedure that re-explained
    what a verb means would be the second copy.

    `ADJUDICATION`, `PUBLISHING`, `RELEASING` and `STYLE` are graded where they
    are there and skipped where they are not, for `OWN_SOURCES`' reason: none
    of the four ships and this module does, so in a built tree `heading_slugs`
    would be asked about a file that is absent."""
    names = [
        "README.md", METHOD, PROCEDURES,
        INITIALIZATION, RETROFIT, INDEX, DISCLOSURE,
    ]
    names += [
        name
        for name in (ADJUDICATION, PUBLISHING, RELEASING, STYLE)
        if (REPO / name).exists()
    ]
    shipped = {name: heading_slugs(REPO / name) for name in names}
    assert all(slugs for slugs in shipped.values())
    for name, slugs in shipped.items():
        for other, others in shipped.items():
            if name is not other:
                assert slugs & others == set(), (str(name), str(other))


def test_the_two_document_check_catches_a_term_defined_twice() -> None:
    """The mutation check: overlapping heading sets really do intersect."""
    assert ({"the-queue", "fileplan"} & {"the-queue"}) == {"the-queue"}


# --------------------------------------------------------------------------
# The draft, over this repo's own declaration
# --------------------------------------------------------------------------


def test_no_transition_this_repo_declares_drops_the_draft() -> None:
    """The control 4-6 was filed with, and since 13-1 the **only** guard on
    the fact. `draft` was a `companion` — a declared field whose whole runtime
    meaning was one load-time refusal — and the field went because this test
    was the same rule written a second time, for the one key that had it.

    A control over the repo's own file on purpose, like the guards above it.
    What is graded is this workflow's choice, not the tool's: `draft` is an
    ordinary declared key, and nothing under `src/` knows the word. The key is
    named here rather than found by a flag, and the declaration is asserted
    first so the loop cannot pass over a key that is no longer there."""
    document = tomllib.loads((REPO / "plan.toml").read_text())
    assert "draft" in document["keys"], "this repo no longer declares draft"
    for name, transition in document["transitions"].items():
        assert "draft" not in transition.get("drops", ()), name


def _requiring_a_dropped_key(document: dict) -> list[tuple[str, str, str]]:
    """Every ``(verb, marking verb, key)`` where the first requires what the
    second takes off the head, out of the same state.

    Same state because that is where the sequence exists: a marking verb only
    reaches an item in the state it works on, so a `requires` on a verb
    somewhere else can never have been undermined by it.
    """
    transitions = document["transitions"]
    return [
        (name, marker, key)
        for name, entry in transitions.items()
        for key in entry.get("requires", ())
        for marker, other in transitions.items()
        if "marks" in other
        and other.get("from") == entry.get("from")
        and key in other.get("drops", ())
    ]


def test_no_verb_this_repo_declares_requires_a_key_a_marking_verb_drops() -> None:
    """The window 12-2 opened and 12-3 shut, kept shut against a second route
    in. The close-out sequence is *mark the last sub-phase, then close*, so a
    verb requiring a key one of this state's marking verbs drops is a
    precondition its own predecessor destroys — a section that cannot be
    closed at all, discovered at the close.

    Every verb rather than the archiving one alone: the sequence is what
    makes it a defect, and singling out one half would be the special case
    this repo's named trap warns about. The rule is over this repo's own
    `plan.toml` because that is where such a declaration would live; a
    load-time refusal would be too strong, since a verb that `sets` the key
    can always write it back."""
    document = tomllib.loads((REPO / "plan.toml").read_text())
    marking = [
        name
        for name, entry in document["transitions"].items()
        if "marks" in entry and entry.get("drops")
    ]
    assert marking, "no marking verb here drops a key, so this proves nothing"
    assert _requiring_a_dropped_key(document) == []


def test_the_dropped_key_control_catches_a_requires_its_neighbour_destroys() -> None:
    """The mutation check. The key a marking verb drops, put back into a
    `requires` out of the same state, really is found — otherwise the control
    above would pass forever by grading nothing."""
    document = tomllib.loads((REPO / "plan.toml").read_text())
    marker, entry = next(
        (name, one)
        for name, one in document["transitions"].items()
        if "marks" in one and one.get("drops")
    )
    victim = next(
        name
        for name, one in document["transitions"].items()
        if name != marker and one.get("from") == entry.get("from")
    )
    key = entry["drops"][0]
    document["transitions"][victim]["requires"] = [key]
    assert (victim, marker, key) in _requiring_a_dropped_key(document)


# --------------------------------------------------------------------------
# The middle tier: dissolved by never being built
# --------------------------------------------------------------------------

#: The old tool's five named report flags (§ "Queries — and the named
#: reports dissolve"). Every one of them derived a fact no head holds, and
#: every one asked the same question: which items satisfy transition X's preconditions.
#: `next VERB` asks it once, generated from the declarations, so none of these
#: has anywhere to come back.
NAMED_REPORTS = ("--ready", "--closeable", "--stale", "--candidates", "--unsized")


def _flags(command: click.Command, ctx: click.Context) -> set[str]:
    """Every option name this command and everything under it accepts."""
    found = {
        name
        for param in command.params
        for name in (*param.opts, *param.secondary_opts)
        if name.startswith("--")
    }
    if isinstance(command, click.Group):
        for name in command.list_commands(ctx):
            found |= _flags(command.get_command(ctx, name), ctx)
    return found


def _repo_flags() -> set[str]:
    group = _build_group(load(REPO / "plan.toml"))
    return _flags(group, click.Context(group))


def test_no_named_report_flag_exists_anywhere_in_the_cli() -> None:
    """The whole group and every subgroup, not just `list`: a report flag
    added to `next work` would be the middle tier growing back one verb at a
    time. A control over the repo's own declaration, like the guards above it
    — the *behaviour* is graded in the fixture's vocabulary, in
    `test_cli.py`."""
    flags = _repo_flags()
    assert flags, "the walker found no options, so this guard proves nothing"
    assert not flags & set(NAMED_REPORTS), sorted(flags & set(NAMED_REPORTS))


def test_the_read_names_every_operator_a_filter_may_carry() -> None:
    """`LIST_HELP` spells the operator table by hand, so it is a second copy
    of `read.OPERATORS` and drifts the way a second copy drifts. 14-2 added
    the seventh, which is where the drift became reachable.

    The help is where a consumer meets the vocabulary: an operator the parse
    takes and the help does not spell is a word only somebody reading `src/`
    finds, which is the gap section 14 is about."""
    assert read.OPERATORS, "the parse takes no operators, so this proves nothing"
    for one in read.OPERATORS:
        assert f"`{one}`" in LIST_HELP, one


def test_the_operator_control_catches_one_missing_from_the_help() -> None:
    """The mutation check: an operator nothing in the help spells really is
    found missing, so the control above cannot pass by grading punctuation
    every paragraph happens to hold."""
    invented = "~="
    assert invented not in read.OPERATORS, "pick one the parse does not take"
    assert f"`{invented}`" not in LIST_HELP
    assert f"`{invented}`" in f"A comparison may be `{invented}`."


def test_the_flag_control_reaches_inside_a_subgroup() -> None:
    """The mutation check. A flag hand-added below the top level really is
    found — otherwise the guard above would pass forever by looking in the
    wrong place, which is exactly how the old tool's blacklist rotted."""
    group = _build_group(load(REPO / "plan.toml"))
    inner = group.commands["next"]
    assert isinstance(inner, click.Group), "next is the subgroup this walks into"
    inner.add_command(
        click.Command(
            name="fabricated",
            params=[click.Option(["--ready"], is_flag=True)],
            callback=lambda **_: None,
        )
    )
    assert "--ready" in _flags(group, click.Context(group))


# --------------------------------------------------------------------------
# The contract, over this repo's own declaration
# --------------------------------------------------------------------------


def _epilogs() -> dict[str, str]:
    """Every declared transition's `--help` epilog, as the group builds it."""
    group = _build_group(load(REPO / "plan.toml"))
    ctx = click.Context(group)
    return {
        name: command.epilog or ""
        for name in group.list_commands(ctx)
        if (command := group.get_command(ctx, name)) is not None
        and name in load(REPO / "plan.toml").transitions
    }


def _verb(name: str) -> str:
    """A verb's name as a whole word, where a hyphen is part of the word: the
    slug boundary `transition._mentions` reads prose with. 27-1 forced it,
    because `retitle-idea`'s contract names itself and so held `retitle`."""
    return rf"(?<![\w-]){re.escape(name)}(?![\w-])"


def _named(epilog: str) -> str:
    """An epilog with its citations taken out, the way the no-per-verb-code
    control strips them: a `doc =` pointer is a pointer at prose, and the
    `Reading` block is nothing but pointers."""
    return CITATION.sub("", epilog)


def test_no_transitions_contract_names_another_verb_this_repo_declares() -> None:
    """The epilog is generated from the `Transition` the command is generated
    from, so a verb's contract can name that verb and nothing else. The
    control in `test_cli.py` grades the *source*; this grades the **output**,
    which is where a hand-written line about one workflow's verb would show up
    even though no code named it.

    A control over the repo's own declaration, like the guards above it."""
    epilogs = _epilogs()
    assert epilogs, "the repo declares no transitions, so this proves nothing"
    for name, epilog in epilogs.items():
        others = set(epilogs) - {name}
        for verb in others:
            assert not re.search(_verb(verb), _named(epilog)), (
                name,
                verb,
            )


def test_the_contract_control_catches_a_verb_written_into_an_epilog() -> None:
    """The mutation check. A verb's name hand-added to another's contract is
    found, and the citation strip does not swallow it — otherwise the guard
    above would pass forever by looking at nothing."""
    epilogs = _epilogs()
    verb = next(iter(epilogs))
    assert re.search(_verb(verb), _named(f"Run {verb} first"))
    assert not re.search(_verb(verb), _named(f"docs/method.md#{verb}"))
    # A hyphen joins a name, so `retitle` is not named by `retitle-idea`.
    assert not re.search(_verb("retitle"), "Reading retitle-idea")


# --------------------------------------------------------------------------
# The skills: no verb of this repo's in any of them, and no second home
# --------------------------------------------------------------------------


def _skills() -> dict[str, str]:
    """Every shipped skill, keyed by path, with its citations taken out.

    Stripped the way the no-per-verb-code control strips `src/`: a citation is
    a pointer at prose, and a `policy` pointer's anchor is a procedure's name
    rather than a verb's — but an anchor that happened to spell one would
    still not be a per-verb line, which is what these controls are about.
    """
    return {
        str(path.relative_to(REPO)): CITATION.sub("", path.read_text())
        for path in sorted((REPO / SKILLS).rglob("*.md"))
    }


def test_no_skill_this_repo_ships_names_a_verb_this_repo_declares() -> None:
    """One procedure for any declared transition, and one composition over
    them, which is only true if neither holds a clause about a particular
    verb. The tool's own control says no per-verb *code* exists and 6-1's says
    no per-verb *line* reached the help text; this says none reached the
    skills either — the artifacts section 8 most wants to re-ship unchanged.

    6-3 widened it from the generic skill to **every** skill. It was scoped
    while `/next` still spelled this repo's verbs in its invocations; with
    those dissolved into `/do-next`, nothing needs excepting, and a whitelist
    of what is graded would be the blacklist 1-6 rejected one shape over."""
    skills = _skills()
    assert skills, "this repo ships no skills, so this control proves nothing"
    verbs = list(load(REPO / "plan.toml").transitions)
    assert verbs, "the repo declares no transitions, so this control proves nothing"
    for where, source in skills.items():
        assert source, f"{where} is empty, so this control proves nothing"
        for verb in verbs:
            assert not re.search(rf"\b{re.escape(verb)}\b", source), (where, verb)


def test_the_verb_name_control_catches_a_verb_written_into_a_skill() -> None:
    """The mutation check. A verb's name in a sentence of a skill is found,
    and the citation strip does not swallow it — otherwise the control above
    would pass forever by grading nothing."""
    verb = next(iter(load(REPO / "plan.toml").transitions))
    assert re.search(rf"\b{re.escape(verb)}\b", CITATION.sub("", f"Then run {verb}."))
    assert not re.search(
        rf"\b{re.escape(verb)}\b", CITATION.sub("", f"docs/method.md#{verb}")
    )


def test_no_skill_re_explains_a_section_of_a_shipped_document() -> None:
    """The one-home guard, reading the skills as shipped documents. A meaning
    has one home (`test_no_heading_is_a_heading_in_two_shipped_documents`),
    and a skill is where the second copy would most easily land: it is the
    artifact a session actually reads at the moment it needs the meaning.

    `##` and deeper, never the `#` title, and the reason is principled rather
    than a fudge: a skill's title is its **name** the way an item's `title` is
    intrinsic, so `# /fileplan` against `README.md`'s `# fileplan` is one
    artifact named after another and not one meaning written twice.

    Graded against the documents, never against each other: two skills
    sharing a procedural heading is not a second home for a meaning, because
    the meanings all live in the documents."""
    documents: set[str] = set()
    for name in ("README.md", METHOD, PROCEDURES):
        slugs = heading_slugs(REPO / name)
        assert slugs, f"{name} has no headings, so this guard proves nothing"
        documents |= slugs
    shipped = sorted((REPO / SKILLS).rglob("*.md"))
    assert shipped, "this repo ships no skills, so this guard proves nothing"
    for path in shipped:
        # `level=1` is the name; everything under it is prose that could
        # explain something twice.
        titles = heading_slugs(path, level=1) or set()
        deeper = (heading_slugs(path) or set()) - titles
        assert deeper, f"{path.relative_to(REPO)} has no sections to grade"
        assert deeper & documents == set(), (str(path.relative_to(REPO)), deeper)


def test_the_second_home_check_catches_a_skill_re_explaining_a_section(
    tmp_path: Path,
) -> None:
    """The mutation check: a fabricated `## the cursor` in a skill really is
    caught, and the `#` title beside it really is not graded."""
    skill = tmp_path / "SKILL.md"
    skill.write_text("# /fileplan\n\n## the cursor\n\nWhat it means.\n")
    documents = (heading_slugs(REPO / METHOD) or set()) | (
        heading_slugs(REPO / "README.md") or set()
    )
    titles = heading_slugs(skill, level=1) or set()
    deeper = (heading_slugs(skill) or set()) - titles
    assert deeper & documents == {"the-cursor"}
    # And the half deliberately not graded: the title *would* collide, with
    # `README.md`'s `# fileplan`, which is the artifact's name rather than a
    # meaning written twice.
    assert titles & documents == {"fileplan"}


def test_the_interpreter_tells_a_session_to_ask_the_tool_first() -> None:
    """What makes the verb-name control satisfiable rather than a gag: the
    worked example is *generated*, so the skill can name no verb and still
    show one. A stranger's example is the verb they actually have.

    Named rather than graded over every skill, because it is about the one
    artifact that runs a transition: the composed skill delegates to this one
    rather than asking the tool itself."""
    source = (REPO / SKILLS / "fileplan" / "SKILL.md").read_text()
    assert "--help" in source and "--check" in source


def test_the_interpreter_names_every_half_the_tool_declares() -> None:
    """Step 4 branches on the halves a contract can name, so a half the tool
    grew and the procedure never learned is a `Declares` block naming
    something the interpreter says nothing about — a session meeting it has
    nothing to act on, and nothing goes red. That is the gap the
    make-problems-visible rule names, and it has now happened twice: 7-5
    found two halves missing after four sub-phases, and 9-3 a third.

    Named at the one artifact that *runs* a transition, for
    `test_the_interpreter_tells_a_session_to_ask_the_tool_first`'s reason:
    the composed skill delegates to this one rather than asking the tool
    itself, so grading every skill would fail it correctly and for the wrong
    reason."""
    halves = HALVES
    assert halves, "the tool declares no halves, so this control proves nothing"
    source = (REPO / SKILLS / "fileplan" / "SKILL.md").read_text()
    for half in halves:
        assert f"`{half}`" in source, half


def test_the_half_control_catches_a_half_the_interpreter_never_learned() -> None:
    """The mutation check: a half nothing in the procedure names really is
    found missing, so the control above cannot pass by grading a word every
    document happens to hold."""
    invented = "scatters"
    assert invented not in HALVES, "pick a word the tool does not declare"
    source = (REPO / SKILLS / "fileplan" / "SKILL.md").read_text()
    assert f"`{invented}`" not in source
    assert f"`{invented}`" in f"* **`{invented}`** \u2014 what its bullet would say."


def _declared_json() -> list[dict]:
    """This repo's own declaration, as `fileplan --json` renders it."""
    declaration = load(REPO / "plan.toml")
    return [contract(declaration, one) for one in declaration.transitions.values()]


def test_the_declaration_read_carries_every_half_the_tool_declares() -> None:
    """The same gap as the control above, one artifact over: a half the tool
    grew and the machine-readable form never learned is a composing session
    selecting on a half and finding nobody declares it. Nothing goes red, and
    the arm silently never runs — which is the whole failure
    `docs/method.md#the-interpreter` says selecting by half rather than by
    name exists to avoid.

    Graded both ways, over every half. A verb declaring it and missing from
    the JSON is the gap; a verb in the JSON declaring it and not in the
    declaration would be the tool answering about a workflow nobody wrote."""
    rows = _declared_json()
    declaration = load(REPO / "plan.toml")
    assert HALVES, "the tool declares no halves, so this control proves nothing"
    for half in HALVES:
        declaring = [
            one.name
            for one in declaration.transitions.values()
            if getattr(one, half)
        ]
        assert [row["name"] for row in rows if half in row["declares"]] == declaring, half


def test_the_declaration_control_catches_a_half_the_json_never_learned() -> None:
    """The mutation check: a half stripped out of the rendering really is
    found missing, so the control above cannot pass by grading a list that
    happens to be there."""
    declaration = load(REPO / "plan.toml")
    forgotten = "marks"
    declaring = [
        one.name for one in declaration.transitions.values() if getattr(one, forgotten)
    ]
    assert declaring, "pick a half this repo's declaration actually declares"
    rows = [
        {**row, "declares": [half for half in row["declares"] if half != forgotten]}
        for row in _declared_json()
    ]
    assert [row["name"] for row in rows if forgotten in row["declares"]] != declaring


def test_every_transitions_contract_names_the_section_it_decides_from() -> None:
    """Done line 1, made reachable: `pointer_errors` proves the pointer
    resolves at every invocation, and this is what hands it over."""
    declaration = load(REPO / "plan.toml")
    for name, epilog in _epilogs().items():
        transition = declaration.transitions[name]
        assert transition.doc in epilog, name
        for key in transition.sets:
            assert declaration.keys[key].doc in epilog, (name, key)


# --------------------------------------------------------------------------
# The mark: written by the verb, and by nothing else
# --------------------------------------------------------------------------
#
# Section 12 moved completion onto the bullet, and the verb is what writes it
# there. A document telling a session to type the word by hand is a second
# writer of a fact the tool owns — the hand-step 4-1 removed for the cursor,
# one artifact out — and it goes stale the moment the word or its bold run
# changes. So the words come out of the **declaration** rather than being
# listed here.


def _marked(document: dict) -> set[str]:
    """Every word this repo's verbs write onto a bullet."""
    return {
        entry["marks"]
        for entry in document["transitions"].values()
        if "marks" in entry
    }


def _hand_written(text: str, words: set[str]) -> list[str]:
    """Every mark `text` writes in the form the tool writes it.

    Matched as `**<word>` and case-insensitively, because that is the shape a
    document reaches for: the tool writes the bold run and the word together,
    so a `**Done` opening a line is the tool's output typed out by hand
    whatever follows it. A bare mention of the word is not — a document may
    say a sub-phase is done in a sentence, and this is about the *form*.
    """
    return [
        word
        for word in sorted(words)
        if re.search(rf"\*\*{re.escape(word)}", text, re.IGNORECASE)
    ]


def _process() -> dict[str, str]:
    """The documents that tell a session what to do: the procedures, and every
    shipped skill.

    `docs/method.md` is deliberately outside this set. It is where the mark is
    **explained**, so the form has to appear in it — one home, not an
    exemption list, which is the distinction 1-6 drew when it chose extraction
    over a blacklist.
    """
    return {str(PROCEDURES): (REPO / PROCEDURES).read_text(), **_skills()}


def test_no_skill_or_procedure_writes_a_mark_in_the_form_the_tool_writes() -> None:
    """The done line, and the reason it is a control rather than a proofread:
    the two instances this replaced had been true when they were written and
    were false by the time anybody read them again. A guard over the form is
    what keeps the next one from being written."""
    document = tomllib.loads((REPO / "plan.toml").read_text())
    words = _marked(document)
    assert words, "this repo declares no marks, so this control proves nothing"
    for where, text in _process().items():
        assert text, f"{where} is empty, so this control proves nothing"
        assert _hand_written(text, words) == [], where


def test_the_hand_written_mark_control_catches_one_typed_into_a_procedure() -> None:
    """The mutation check, in both directions: the form is caught whatever
    case it is typed in, and a sentence that merely uses the word is not — a
    control that fired on the bare word would make the documents unwritable
    and be turned off."""
    word = sorted(_marked(tomllib.loads((REPO / "plan.toml").read_text())))[0]
    assert _hand_written(f"mark the bullet `**{word.title()} 2026-09-08.**`", {word})
    assert _hand_written(f"a **{word}** marker is a claim", {word})
    assert _hand_written(f"say the sub-phase is {word}", {word}) == []


# --------------------------------------------------------------------------
# The index, and the README it fronts
# --------------------------------------------------------------------------


#: A Markdown link, taken for its target alone. The index writes its links
#: **relative** — `docs/initialization.md` and `docs/procedures.md` already
#: do, and
#: a `docs/`-prefixed link renders broken on GitHub from inside `docs/` — so
#: `CITATION`, which only matches a path beginning `docs/`, cannot see one of
#: them. This is what grades them instead.
LINK = re.compile(r"\[[^\]]*\]\(([^)#]+)(?:#[^)]*)?\)")


def _prompts(text: str) -> list[str]:
    """Every shell prompt line in ``text``, stripped of trailing space."""
    return [line.rstrip() for line in text.splitlines() if line.startswith("$ ")]


def _linked() -> list[Path]:
    """Every link in the index, resolved against `docs/`."""
    text = (REPO / INDEX).read_text()
    return [
        (REPO / INDEX.parent / target).resolve()
        for target in LINK.findall(text)
    ]


def test_the_index_reaches_every_document_this_repo_ships() -> None:
    """An index that misses a document is worse than no index: a reader who
    trusts it stops looking. The floor is every `.md` under `docs/` and both
    shipped skills — the skills because they are package data a consumer
    installs, so an index omitting them misses the artifact a consumer most
    wants reachable."""
    documents = {
        path.resolve()
        for path in (REPO / "docs").rglob("*.md")
        if path.resolve() != (REPO / INDEX).resolve()
    }
    documents |= {path.resolve() for path in (REPO / SKILLS).rglob("*.md")}
    assert documents, "this repo ships no documents, so this guard proves nothing"
    missing = documents - set(_linked())
    assert missing == set(), sorted(str(path) for path in missing)


def test_every_link_in_the_index_resolves() -> None:
    """The other half. The first says nothing was left out; this says nothing
    named is absent — a renamed document leaves a link behind, and a pointer
    nothing follows is the artifact the citation guard exists to refuse."""
    linked = _linked()
    assert linked, "the extractor found no links, so this guard proves nothing"
    for path in linked:
        assert path.exists(), f"{INDEX} links {path}, which this repo does not ship"


def test_the_link_extractor_finds_a_relative_link_and_not_a_citation() -> None:
    """The mutation check, both directions: the extractor really does read a
    relative link with an anchor on it, and it is not reading the anchor as
    part of the path — a `#` left in the target would resolve to nothing and
    make the guard above unpassable rather than meaningless."""
    assert LINK.findall("see [the method](method.md#the-queue) for it") == [
        "method.md"
    ]
    assert LINK.findall("[a skill](../src/fileplan/skills/fileplan/SKILL.md)") == [
        "../src/fileplan/skills/fileplan/SKILL.md"
    ]
    assert LINK.findall("no link here") == []


def test_every_command_in_the_readme_is_one_the_initialization_walk_runs() -> None:
    """The README's transcripts are cut from `docs/initialization.md`, and
    this is what says so. "The two must agree" is otherwise a sentence nobody
    re-checks: the walk is the one place a command is executed, and the README
    is a strict excerpt of it, so a command the walk does not run is a command
    whose output nobody has seen. If the README needs a line, the walk gains
    it first."""
    walk = set(_prompts((REPO / INITIALIZATION).read_text()))
    assert walk, "the walk runs no commands, so this guard proves nothing"
    shown = _prompts((REPO / "README.md").read_text())
    assert shown, "the README shows no commands, so this guard proves nothing"
    for line in shown:
        assert line in walk, f"README.md runs `{line}`, which {INITIALIZATION} does not"


def test_the_excerpt_check_catches_a_command_the_walk_does_not_run() -> None:
    """The mutation check: a prompt line the walk has no copy of is found by
    the same reader, and a line it does have is not mistaken for one."""
    walk = _prompts((REPO / INITIALIZATION).read_text())
    assert _prompts("```\n$ fileplan invent-a-verb\n```") == ["$ fileplan invent-a-verb"]
    assert "$ fileplan invent-a-verb" not in walk
    assert "$ fileplan list" in walk



# --------------------------------------------------------------------------
# The archive guard: nothing points a reader into this repo's own record
# --------------------------------------------------------------------------


def _archives() -> set[str]:
    """Every path a declared state files its archive entries into.

    Read off the declaration rather than spelled here, for the reason the
    citation guard extracts rather than blacklists: a second state gaining an
    `archive` would otherwise be ungraded, and nobody would notice.
    """
    return {
        state.archive
        for state in load(REPO / "plan.toml").states.values()
        if state.archive
    }


def _unfenced(text: str) -> str:
    """``text`` with every fenced block taken out.

    Wider than `prose`, and only for this guard. `prose` keeps a fence with no
    prompt in it, because `docs/method.md`'s TOML snippets really do name this
    repo's own sections and the existence guard has to grade them. Here they
    are the opposite: a snippet showing `archive = "…"` is the **declaration**
    quoted back, which is what the archive path is *for*, not somewhere a
    reader is being sent. A fenced line is not a line at all (11-1), and this
    is that rule at one more artifact.
    """
    return FENCED.sub("", text)


def test_no_shipped_document_points_a_reader_into_the_plan_archive() -> None:
    """John, 2026-09-11: the archive is a record, never a reference.

    An entry is written once, at close-out, about a moment. A document citing
    it sends a session to act on what was true that day, with every later
    narrowing invisible — the shape `docs/method.md` exists to hold instead,
    one section per meaning, kept current. Section 18 sharpens it: the archive
    is excluded from the published tree, so a pointer into it is not merely
    stale for a consumer, it resolves to nothing.

    Scoped to what a reader is *sent* to: the shipped documents, the file
    every session reads, `src/`, and the skills. Not the filed items and not
    the design draft —
    both are dated records themselves, and a record citing a record is the one
    shape this rule has no quarrel with. `plan.toml` is the declaration that
    *names* the archive, so it is where the path is allowed to be.
    """
    archives = _archives()
    assert archives, "no state declares an archive, so this guard proves nothing"
    graded = [
        REPO / name
        for name in (*SOURCES, *_own_sources())
        if name != "plan.toml"
    ]
    graded += sorted((REPO / "src").rglob("*.py"))
    graded += sorted((REPO / SKILLS).rglob("*.md"))
    for path in graded:
        where = str(path.relative_to(REPO))
        named = {
            target
            for target, _ in citations(_unfenced(path.read_text()))
            if target in archives
        }
        assert not named, f"{where} points a reader into {', '.join(sorted(named))}"


def test_the_archive_pointer_control_catches_a_fabricated_one() -> None:
    """The mutation check, in three parts, because this guard has three ways
    to pass while proving nothing.

    The reader must find a pointer in prose; it must not find the declaration
    quoted in a fence, which is the exemption doing its job rather than a hole;
    and the path it grades must be the one the declaration gives, not a string
    typed here that a rename would strand.
    """
    archive = sorted(_archives())[0]
    assert archive == "docs/plan-archive.md", "the fixtures below assume this path"

    fabricated = f"The decision is in `{archive}`, section 15."
    assert citations(_unfenced(fabricated)) == [(archive, None)]

    declared = f'```toml\n[states.plan]\narchive = "{archive}"\n```'
    assert citations(_unfenced(declared)) == []

    states = load(REPO / "plan.toml").states
    assert states["plan"].archive == archive
    assert any(state.archive is None for state in states.values()), (
        "every state archives, so the filter above is never exercised"
    )


# --------------------------------------------------------------------------
# The listing's JSON envelope, held against what `list --json` emits
# --------------------------------------------------------------------------

#: How the account of the envelope opens in `docs/method.md#the-listing`.
ENVELOPE = "**The envelope is one object, and these are its fields.**"


def _envelope_account(text: str) -> str:
    """The envelope's paragraph and the list under it, and nothing else, so
    a field named elsewhere in the section cannot stand in for it."""
    blocks = text.split("\n\n")
    (at,) = [n for n, block in enumerate(blocks) if block.startswith(ENVELOPE)]
    return blocks[at] + blocks[at + 1]


def _unaccounted(keys: list[str], text: str) -> list[str]:
    account = _envelope_account(text)
    return [key for key in keys if f"`{key}`" not in account]


def _emitted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> list[str]:
    """Every top-level key `list --json` emits over the fixture declaration,
    which turns on every conditional array: it claims, carries a cursor,
    reads dependencies, numbers, marks, counts sub-phases and closes a key."""
    fixtures = REPO / "tests" / "fixtures"
    for name in FIXTURE_FILES:
        (tmp_path / name).write_text((fixtures / name).read_text())
    for state in load(tmp_path / "plan.toml").states.values():
        (tmp_path / state.path).mkdir(parents=True)
    monkeypatch.setenv("FILEPLAN_PLAN_TOML", str(tmp_path / "plan.toml"))
    monkeypatch.chdir(tmp_path)
    capsys.readouterr()
    assert main(["list", "--json"]) == 0
    return list(json.loads(capsys.readouterr().out))


def test_every_field_of_the_listing_envelope_is_written_down(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Section 23: scripts a consumer's sessions wrote crashed on the
    envelope twice, reading `items`, which is the `kind`, as the array. The
    account is in one place now, and this holds it against the code."""
    emitted = _emitted(tmp_path, monkeypatch, capsys)
    assert len(emitted) > 6, "the fixture turned on no arrays, so this proves little"
    assert _unaccounted(emitted, (REPO / METHOD).read_text()) == []


def test_the_envelope_guard_catches_a_field_the_account_leaves_out() -> None:
    """The mutation check, kept: a field dropped from the account is found,
    so the guard cannot pass by reading the whole section."""
    text = (REPO / METHOD).read_text()
    assert "`undeclared`" in _envelope_account(text)
    dropped = text.replace("* `undeclared` is present wherever", "* It is present wherever")
    assert _unaccounted(["undeclared"], dropped) == ["undeclared"]
