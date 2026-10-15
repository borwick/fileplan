"""The declaration: `plan.toml`'s schema, its validator, and its loader.

Everything downstream consumes the `Declaration` this module produces.

`shape_errors` and `pointer_errors` are pure over a parsed document, and touch
no filesystem. `load` is the impure half: discovery, parsing and raising.

One complaint per defect. Where a field is the wrong shape, the checks that
would read the field stay quiet.
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Iterable, Iterator, Mapping, NamedTuple

from fileplan import depends, subphase

#: The environment override, used exactly: a typo'd override refuses rather
#: than falling back on the default.
PLAN_TOML_ENV = "FILEPLAN_PLAN_TOML"

PLAN_TOML_NAME = "plan.toml"

#: The tables whose `doc` names a section of a document, matched against that
#: document's headings. `_pointers` walks this rather than `TABLES`.
ANCHORED = ("states", "keys", "transitions")

#: The tables of entries: each holds named tables.
TABLES = ANCHORED

#: The one table that is a single entry rather than a table of them.
IDENTITY = "identity"

#: The single-entry table naming the oldest tool a plan.toml was written for,
#: and its one field. Graded before every other load error, so an old tool
#: says "upgrade" rather than blaming the declaration.
#: See docs/method.md#the-version
TOOL = "fileplan"
MINIMUM = "minimum"

#: The `[fileplan]` field naming the directory a state's default `path` sits
#: under: `root = "docs"` puts a state called `plan` at `docs/plan`. A state
#: that writes its own `path` is not moved by it. See docs/method.md#states
ROOT = "root"

#: The `[fileplan]` field listing the exact file names no state directory
#: reads as items, such as the file an agent tool reads from the directory it
#: works in. Every other `*.md` there is still claimed to be an item.
#: See docs/method.md#ignore
IGNORE = "ignore"

#: An item file's suffix. The traversal reads only files carrying it, which is
#: why a name in `[fileplan].ignore` without it refuses: nothing would skip it.
SUFFIX = ".md"
DOTTED_RE = re.compile(r"^\d+(\.\d+)*$")

#: Every table a plan.toml may hold, for the refusal that names an unknown one.
KNOWN_TABLES = (*TABLES, IDENTITY, TOOL)

#: What the tool no longer reads, and what to do instead, each refused by
#: name: a table, a transition field and a capability that something simpler
#: replaced. See docs/method.md#kinds
RETIRED_TABLES: Mapping[str, str] = MappingProxyType(
    {
        "templates": "Copy a document into a new item's body with "
        "`--body - < FILE`, and drop the table",
    }
)
RETIRED_FIELDS: Mapping[str, str] = MappingProxyType(
    {
        "seeds": "Copy a document into the new item's body with "
        "`--body - < FILE`, and drop the seeds",
        "policy": "Link the procedure from the section the transition's doc "
        "names, and drop the policy",
        "carries": "A merge always appends the absorbed bodies to the "
        "survivor. Drop the carries",
    }
)
RETIRED_CAPABILITIES: Mapping[str, str] = MappingProxyType(
    {
        "dated": "Every row carries stale-days whenever the tree is in git, "
        "with nothing to switch on. Drop it",
    }
)

#: The capability whose key is minted from a corpus, and the state field naming
#: where the corpus's closed half lives. `fileplan.numbered` reads both from
#: here.
NUMBERED = "numbered"
ARCHIVE = "archive"

#: And the state field saying where that register begins: the first number it
#: may hold, inclusive, and its default, the number a legibly empty register
#: mints first. See docs/method.md#the-register
FIRST_NUMBER = "first-number"
FIRST = 1

#: The state field naming which declared key holds the item a carrier was
#: opened for. See docs/method.md#the-dangle-check
OPENED_FOR = "opened-for"

#: The state field naming the order its items list in when no `--sort` is
#: given: one key, in `--sort`'s spelling. See docs/method.md#the-listing
SORT = "sort"

#: The key field saying a head value is several.
#: See docs/method.md#list-valued
LIST_VALUED = "list-valued"

#: Every field where the tool writes or reads exactly one value of a declared
#: key. `dependencies` is left out: `fileplan.depends` reads a bare string as
#: one edge and a list as many.
SINGLE_VALUE_FIELDS = (subphase.CURSOR, subphase.STATUS, OPENED_FOR)

STATE_FIELDS = frozenset(
    {
        "path",
        "doc",
        "capabilities",
        ARCHIVE,
        FIRST_NUMBER,
        depends.FIELD,
        subphase.NAME,
        subphase.CURSOR,
        subphase.STATUS,
        subphase.PENDING,
        subphase.FORM,
        OPENED_FOR,
        SORT,
    }
)
KEY_FIELDS = frozenset({"doc", "help", "values", LIST_VALUED})

#: The fields every transition takes, whatever its kind.
TRANSITION_FIELDS = frozenset({"kind", "doc", "help"})

#: The nine kinds' names, each spelled once. Everything that asks what a
#: transition does asks its kind by one of these. See docs/method.md#kinds
CREATE, MOVE, REORDER, EDIT, RENAME = "create", "move", "reorder", "edit", "rename"
CLOSE, MERGE, ADD_BULLET, MARK_BULLET = "close", "merge", "add-bullet", "mark-bullet"

#: The nine kinds a transition can be, and the fields each takes beside
#: `TRANSITION_FIELDS`. One table, so what a kind allows is read here and
#: nowhere else, and a field its kind does not take refuses by name.
#: `from` and `to` are in it too: a create has no `from`, a move has both,
#: and every other kind stays where it is or takes the item away, so it has
#: only a `from`. See docs/method.md#kinds
#: The fields an edit writes, at least one of which it must name: an edit
#: naming none writes nothing. Read by the kind table, by the edit's refusal
#: and by `_suggested_kind`. See docs/method.md#kinds
EDIT_WRITES = ("sets", "drops", "claims")

KINDS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        CREATE: frozenset({"to", "sets", "claims"}),
        MOVE: frozenset(
            {"from", "to", "requires", "refuses", "sets", "drops", "claims", "archives"}
        ),
        REORDER: frozenset({"from", "requires", "refuses"}),
        EDIT: frozenset({"from", "requires", "refuses", *EDIT_WRITES}),
        RENAME: frozenset({"from", "requires", "refuses"}),
        CLOSE: frozenset({"from", "requires", "refuses", "archives"}),
        MERGE: frozenset({"from", "requires", "refuses"}),
        ADD_BULLET: frozenset({"from", "requires", "refuses", "sets"}),
        MARK_BULLET: frozenset(
            {"from", "requires", "refuses", "marks", "sets", "drops", "files"}
        ),
    }
)

#: The fields each kind cannot do without, beside `kind`, `doc` and `help`:
#: whichever of `from` and `to` its table takes, and a mark-bullet's word.
KIND_REQUIRES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        kind: tuple(field for field in ("from", "to") if field in fields)
        + (("marks",) if kind == MARK_BULLET else ())
        for kind, fields in KINDS.items()
    }
)

#: What a transition's `help` says when the declaration writes none: the
#: kind, said with the states it names. A repo writes `help` only to say
#: something better. See docs/method.md#kinds
KIND_HELP: Mapping[str, str] = MappingProxyType(
    {
        CREATE: "Create an item in {to}.",
        MOVE: "Move an item from {from} to {to}.",
        REORDER: "Move an item to another place in {from}'s order.",
        EDIT: "Edit an item in {from} where it stands.",
        RENAME: "Give an item in {from} a new title.",
        CLOSE: "Close an item in {from} out, and take its file away.",
        MERGE: "Merge an item in {from} into another item.",
        ADD_BULLET: "Write the next bullet into an item in {from}.",
        MARK_BULLET: "Mark a bullet of an item in {from} {marks}.",
    }
)

#: What a kind that takes `archives` says instead, where it declares it: the
#: record is what `--record` is for. Keyed by kind, as `KIND_HELP` is.
ARCHIVING_HELP: Mapping[str, str] = MappingProxyType(
    {
        CLOSE: "Close an item in {from} out: file its archive entry, and take "
        "its file away.",
    }
)

#: The kinds that take the item's file away.
DISSOLVING = frozenset({CLOSE, MERGE})

#: The kinds that leave the item in the state it started in: every kind
#: starting from an item that names no `to` and takes nothing away.
STAYING = frozenset(
    kind
    for kind, fields in KINDS.items()
    if "from" in fields and "to" not in fields and kind not in DISSOLVING
)

#: The kinds that give an item a place, when the state it lands in is
#: `queued`: the two that bring it there, and the one that only moves it in
#: the order. Every other kind leaves the place alone.
#: See docs/method.md#the-queue
PLACING = frozenset({CREATE, MOVE, REORDER})

#: The fields whose only job was to say which kind a transition is, which
#: `kind` says now. A plan.toml carrying one refuses by name, with the kind to write, which `_suggested_kind` reads off
#: the entry.
REMOVED_FIELDS = ("mints", "dissolves", "absorbs", "retitles")

IDENTITY_FIELDS = frozenset({"doc", "pid"})

#: The capability whose state lives outside the item file, in `local/claims/`.
#: Named here because this is where it has to be graded against `[identity]`.
#: See docs/method.md#the-claimed-state
CLAIMED = "claimed"

#: The capability that orders a state's items. `fileplan.queued` reads it
#: from here.
QUEUED = "queued"

#: The capability whose state is the item's body: an add-bullet writes a
#: sub-phase into it. Named here because this is where its two halves
#: have to be graded against each other. See docs/method.md#bulleted
BULLETED = "bulleted"

#: The three roles a `files` table names, and the whole roster: which state the
#: second item is filed into, which declared key records the item it was filed
#: from, and which records the bullet. Filing is a transition half with no
#: state half, so no capability name joins `CAPABILITIES` beside them and
#: there is no cross-check here. See docs/method.md#filing
FILING_ROLES = ("state", "item", "name")

#: Every field a `files` table may hold: the three roles, which it must, and
#: `sets`, which it may. `sets` is not a fourth role, because a filing with no
#: key of its own is complete. It names the declared keys the run takes as
#: options and writes onto the filed item's head, never the carrier's.
#: See docs/method.md#filing
FILING_FIELDS = (*FILING_ROLES, "sets")

#: Capabilities implemented so far. Every other name a state might opt into is
#: refused by name until whatever implements it adds it here.
CAPABILITIES = (QUEUED, CLAIMED, NUMBERED, BULLETED)

#: The key each capability gives an item's head, when it gives one at all —
#: `CLAIMED` and `BULLETED` give none. Declared nowhere, and here because this
#: is where a redeclaration has to be refused: a key of the same name refuses,
#: and so does a transition naming one in `requires`, `sets`, `drops` or
#: `refuses`. Every refusal below reads this mapping rather than naming a key.
CAPABILITY_KEYS = {QUEUED: "position", NUMBERED: "number"}

#: The keys the `CLAIMED` capability gives a row: who holds the item, what the
#: liveness probe said of that holder, and whether the holder is the session
#: reading the row. Read off `local/claims/` rather than out of any head, so a
#: key of any of the three names refuses unconditionally.
#: See docs/method.md#the-listing
CLAIM_KEYS = ("claimed-by", "claim-status", "claim-holder")

#: The key every row carries: whole days since the item file's last commit,
#: or `None` where git does not answer. Derived from git, so a key of that name
#: refuses unconditionally. See docs/method.md#stale-days
STALE_KEYS = ("stale-days",)

#: The key a row carries wherever some transition starts from an item: the
#: commands that could take this item right now, in declared order, or `None`
#: where none could. Read off the transitions' own refusals when the listing
#: runs, so a key of that name refuses unconditionally.
#: See docs/method.md#commands
COMMAND_KEYS = ("commands",)

class Derived(NamedTuple):
    """One group of keys a row carries from outside the head."""

    #: Whether a declaration carries the group at all.
    gate: Callable[["Declaration"], bool]
    names: tuple[str, ...]
    #: Whether a state's raw entry carries the group, which is what a state's
    #: `sort` may name, or `None` where the group is no sort key at all.
    sorts: Callable[[Mapping[str, Any]], bool] | None


#: Which derived keys a declaration carries, the gate each is behind, and
#: which states carry each as a sort key. One roster, read by
#: `Declaration.derived` and through it by the row layer's filters, by
#: `--has`/`--lacks` and by the CLI's option table, by a state's `sort`, and
#: by every refusal of a key that names one, so a group added here reaches
#: them all.
#:
#: Separate from `CAPABILITY_KEYS`: that is what a capability writes into a
#: head, this is what a listing reads from somewhere else. It is about presence
#: and its gate, never about the wording of a redeclaration message.
DERIVED_KEYS: tuple[Derived, ...] = (
    Derived(
        lambda one: one.has(CLAIMED),
        CLAIM_KEYS,
        lambda entry: CLAIMED in _declared_capabilities(entry),
    ),
    Derived(
        lambda one: one.counts_sub_phases,
        subphase.DERIVED,
        lambda entry: subphase.NAME in entry,
    ),
    Derived(
        lambda one: one.has_dependencies,
        depends.DERIVED,
        lambda entry: depends.FIELD in entry,
    ),
    # Every declaration: the age needs no switch. `None` outside git.
    Derived(lambda one: True, STALE_KEYS, lambda entry: True),
    # A list of command names orders nothing, so it is no sort key.
    Derived(lambda one: one.takes_items, COMMAND_KEYS, None),
)

#: Every name the roster can give a row, gates ignored: what a key or a
#: transition may never name.
DERIVABLE = tuple(name for group in DERIVED_KEYS for name in group.names)

#: Keys every item carries by being an item, declared nowhere. Here, in the
#: module that validates `plan.toml`, because that is where a redeclaration has
#: to be refused.
INTRINSIC_KEYS = ("title",)

#: Names a listing already reads off the tree, in the order a row spells them,
#: so a declared key may not take one: a head key of the same name would be a
#: second answer to a question the tree already answers, and the one in the
#: head is the one that lies.
RESERVED_KEYS = ("slug", "state", "path")

#: What a state, key or transition may be called.
NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")

_SINGULAR = {"states": "state", "keys": "key", "transitions": "transition"}


class Refusal(Exception):
    """Why the declaration was not usable. `.messages` holds every defect."""

    def __init__(self, messages: list[str] | str) -> None:
        self.messages = [messages] if isinstance(messages, str) else list(messages)
        super().__init__(str(self))

    def __str__(self) -> str:
        return "; ".join(self.messages)


def named(path: Path, root: Path) -> str:
    """`path` as a message names it: relative to `root`, the way a row's
    `path` is, and as given where it is not under `root`. Resolved on the
    second try, because a `/tmp` can be a symlink.
    See docs/method.md#the-listing
    """
    for under, above in ((path, root), (path.resolve(), root.resolve())):
        try:
            return str(under.relative_to(above))
        except ValueError:
            continue
    return str(path)


def collecting[T](
    read: Callable[[Path], T], sources: Iterable[Path], defects: list[str]
) -> Iterator[tuple[Path, T]]:
    """Yield `(source, read(source))` per source, collecting refusals.

    The one spelling of read every one, keep what each broken one said, and
    carry on. `defects` is extended in place, so a caller keeps whatever else
    it collects in the same list and the messages stay in source order. A
    source that refuses is simply not yielded.
    """
    for source in sources:
        try:
            yield source, read(source)
        except Refusal as refusal:
            defects += refusal.messages


@dataclass(frozen=True)
class State:
    """A declared directory. `path` is a literal, relative to the root."""

    name: str
    path: str
    doc: str | None = None
    capabilities: tuple[str, ...] = ()
    #: The heading a section's sub-phase bullets are counted under, or `None`
    #: where this state counts none. There is no default.
    #: See docs/method.md#sub-phases
    sub_phases: str | None = None
    #: Which declared key holds the cursor, and which holds the status, or `None`
    #: where this state has neither. See docs/method.md#the-cursor
    cursor: str | None = None
    status: str | None = None
    #: The bullet an unfinished decomposition leaves behind, as its content after
    #: `- `, or `None` where this state mints none. It must parse as a strict
    #: named bullet, graded at load. See docs/method.md#bulleted
    pending: str | None = None
    #: What this state's bullets are called: the whole ident form, with
    #: `{ordinal}` where the tool supplies the number and every other field
    #: naming a value the item carries. `None` where this state mints none.
    sub_phase_name: str | None = None
    #: Which declared key holds the slugs an item here waits on, or `None` where
    #: this state reads none. See docs/method.md#dependencies
    dependencies: str | None = None
    #: Which declared key holds the item an item here was opened for, or `None`
    #: where this state names none. On the state rather than on a transition,
    #: because the reader is what needs it.
    opened_for: str | None = None
    #: The document this state's closed items are recorded in, or `None` where it
    #: holds none. The second source of the `numbered` register, and on the state
    #: rather than on the verb that archives, because the register needs it
    #: whether or not any verb archives. See docs/method.md#the-register
    archive: str | None = None
    #: Where this state's register begins: the first number it may hold,
    #: inclusive. Unlike `archive` it has a correct default, so absence grades
    #: nothing. The literal here rather than in `fileplan.numbered`, which
    #: imports this module; the two are pinned together.
    first_number: int = FIRST
    #: The key this state's items list by when no `--sort` is given, in
    #: `--sort`'s spelling, or `None` where they list by slug. A `queued` state
    #: must declare one. See docs/method.md#the-listing
    sort: str | None = None
    #: The words the declared verbs mark into this state, or `None` where
    #: none does. A second bold run holding any other word is not a mark.
    #: Derived from the transitions at load. See docs/method.md#marking
    marks: frozenset[str] | None = None

    def has(self, capability: str) -> bool:
        """Whether this state opted into `capability`."""
        return capability in self.capabilities

    @property
    def capability_keys(self) -> tuple[str, ...]:
        """The keys an item carries by being here rather than by declaration.

        An item in another state carrying one of these refuses by name.
        """
        return tuple(
            CAPABILITY_KEYS[capability]
            for capability in self.capabilities
            if capability in CAPABILITY_KEYS
        )


@dataclass(frozen=True)
class Key:
    """A declared fact about an item, held in its head or read off its path."""

    name: str
    #: The section that says what the key means, or `None` where the
    #: declaration names none. See docs/method.md#the-contract
    doc: str | None = None
    help: str | None = None
    #: `None` means free text; a tuple means a closed set.
    values: tuple[str, ...] | None = None
    #: Whether the head carries several of them. A different question from
    #: `values`, which is the set one of them may come from.
    list_valued: bool = False


@dataclass(frozen=True)
class Transition:
    """A declared verb: what it needs, what it writes, and where it moves."""

    name: str
    #: The section that says what this transition means, or `None` where the
    #: declaration names none: then the `help` line is the whole of it.
    #: See docs/method.md#the-contract
    doc: str | None
    help: str
    #: Where the item lands, or `None` when it lands nowhere: a close or a
    #: merge. A kind that stays in its state declares no `to`, and this holds
    #: its `from`, filled in at load.
    to: str | None
    #: Which of `KINDS` this verb is. See docs/method.md#kinds
    kind: str
    #: `None` means the transition creates content rather than moving it.
    source: str | None = None
    requires: tuple[str, ...] = ()
    #: An immutable empty mapping, not `()`: a frozen dataclass cannot take a
    #: `{}` default, and a tuple default would fail the first time something
    #: built a Transition without one.
    refuses: Mapping[str, tuple[str, ...]] = MappingProxyType({})
    #: The keys refused on presence alone, written `key = true` in the same
    #: table: an item carrying any value of one is refused. How a verb that
    #: stays in its state says it runs once. See docs/method.md#commands
    refuses_any: tuple[str, ...] = ()
    sets: tuple[str, ...] = ()
    drops: tuple[str, ...] = ()
    #: Whether running this verb picks the item up: the transition half of
    #: `CLAIMED`. A state says items here are claimable; a verb says this is the
    #: one that takes a claim. Default `False`, so arriving takes nothing.
    #: See docs/method.md#the-claimed-state
    claims: bool = False
    #: The word this verb writes onto one bullet of the item's body, or `None`
    #: when it writes none. A verb that carries one is a disposition: its subject
    #: is a finding rather than the item. A string rather than a flag, because
    #: the word itself is the workflow's, and there is no third field listing a
    #: state's vocabulary. Only a mark-bullet takes one, and it must.
    #: See docs/method.md#marking
    marks: str | None = None
    #: Where this verb files a second item, and which of its keys record where it
    #: came from, or `None` when it files none. A table rather than three flat
    #: fields, because the three are one capability and each role wants a name:
    #: `FILING_ROLES` is the whole roster. The table may also hold `sets`, the
    #: keys written onto the filed item, which `files_sets` reads. All of it is
    #: the verb's, not a state's, because only the writer needs to know. Only a
    #: mark-bullet takes one. Default `None`. See docs/method.md#filing
    files: Mapping[str, Any] | None = None
    #: Whether running this verb files the item's archive entry: the number and
    #: title it carried, written into the document its source state's `archive`
    #: names. A different half from the deletion, so a verb that wants both says
    #: both. Default `False`. Only a move or a close takes it, and its source
    #: must be `NUMBERED`. See docs/method.md#the-register
    archives: bool = False
    @property
    def records(self) -> bool:
        """Whether this run files a record and takes the file away: a close
        that `archives`. The one shape that takes `--record`, and the one the
        close and dangle checks guard. See docs/method.md#dissolving"""
        return self.kind == CLOSE and self.archives

    @property
    def leaves(self) -> bool:
        """Whether this verb ends the state it starts in: a move or a close.
        A create starts in none, and a kind that stays ends nothing."""
        return self.source is not None and self.source != self.to

    @property
    def files_sets(self) -> tuple[str, ...]:
        """The keys this verb writes onto the item it files, in declared order.

        Empty where the verb files nothing, or files an item with no key of
        its own. `sets` is the carrier's, and a verb that files refuses one.
        See docs/method.md#filing
        """
        if self.files is None:
            return ()
        return tuple(self.files.get("sets", ()))


@dataclass(frozen=True)
class Declaration:
    """A parsed, validated `plan.toml`."""

    #: The file actually read — not the default spelling.
    source: Path
    #: The directory `doc` pointers resolve against.
    root: Path
    states: Mapping[str, State]
    keys: Mapping[str, Key]
    transitions: Mapping[str, Transition]
    #: The environment variable names `[identity].pid` declares, in order: the
    #: first one that is set supplies a session's pid. Empty when there is no
    #: `[identity]`, and there is no default. Names rather than a value: reading
    #: them is `fileplan.claim.identity`.
    pid_names: tuple[str, ...] = ()
    #: The file names `[fileplan].ignore` lists, which `fileplan.read.items`
    #: leaves out of every state directory. Empty when the table lists none.
    ignore: frozenset[str] = frozenset()

    def has(self, capability: str) -> bool:
        """Whether any declared state opts into `capability`.

        What a listing's shape depends on, so it does not depend on which
        items happen to be filed.
        """
        return any(state.has(capability) for state in self.states.values())

    @property
    def carried(self) -> tuple[str, ...]:
        """Every key an item may carry: intrinsic, capability-given, declared.

        May, across the whole declaration: an item carries a capability's key
        only in a state that opts into it. Every key a row carries from
        outside the head is `derived`, read off `DERIVED_KEYS` rather than
        spelled again here.
        """
        given = {key for state in self.states.values() for key in state.capability_keys}
        return (*INTRINSIC_KEYS, *sorted(given), *self.derived, *self.keys)

    @property
    def derived(self) -> tuple[str, ...]:
        """The keys a row carries from outside the head, in row order.

        `DERIVED_KEYS`' entries whose gate holds, flattened, so `carried`, the
        filters the CLI generates and the parse of what they were given cannot
        disagree. Corpus-independent like every other shape question.
        """
        return tuple(
            name for group in DERIVED_KEYS if group.gate(self) for name in group.names
        )

    @property
    def counts_sub_phases(self) -> bool:
        """Whether any declared state counts sub-phases at all.

        The one question the two body-derived row fields are present or absent
        on, asked here rather than at the row layer and at the filters
        separately. Corpus-independent.
        """
        return any(state.sub_phases for state in self.states.values())

    @property
    def takes_items(self) -> bool:
        """Whether any transition starts from an item, which is what a row's
        `commands` is present or absent on. Corpus-independent."""
        return any(one.source is not None for one in self.transitions.values())

    @property
    def has_dependencies(self) -> bool:
        """Whether any declared state reads dependencies at all.

        `counts_sub_phases`' shape, and for its reason. Corpus-independent.
        """
        return any(state.dependencies for state in self.states.values())

    @property
    def files(self) -> tuple[Mapping[str, str], ...]:
        """The `files` table of every verb that declares one, in order.

        What a retitle repoints through and the listing's unfound report reads
        through, asked once. Empty where no verb files. See
        docs/method.md#filing
        """
        return tuple(
            one.files for one in self.transitions.values() if one.files is not None
        )

    @property
    def marked_states(self) -> frozenset[str]:
        """The states some declared verb writes a mark into.

        `counts_sub_phases`' shape and its reason: what the listing's
        unmarkable report is present or absent on, asked once rather than at
        the read layer and the CLI separately. A `bulleted` state nothing
        marks into is a legal shape, and a bullet there waits on nothing.
        See docs/method.md#marking
        """
        return frozenset(
            name for name, state in self.states.items() if state.marks
        )

    def state_at(self, path: str | os.PathLike[str]) -> State | None:
        """The declared state whose directory holds `path`, or `None`.

        Location is state, and this is the one place that reads a directory to
        say which. The rule is the file's own directory, not an ancestor of
        it. Both sides are resolved, because a directory can be reached by
        more than one path: a synced or symlinked tree, or a `/tmp` that is
        itself a symlink.
        """
        directory = Path(path).parent.resolve()
        for state in self.states.values():
            if (self.root / state.path).resolve() == directory:
                return state
        return None


# --------------------------------------------------------------------------
# The pure validators
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _Corpus:
    """The whole parsed document, as the arms below grade it.

    `shape_errors` builds one and the whole-document arms take it whole; `at`
    narrows it to the one entry the per-entry arms grade. It carries nothing
    derived.
    """

    #: The states table as parsed, entries ungraded: the raw TOML, not `State`s.
    state_table: Mapping[str, Any]
    #: The transitions table, entries ungraded.
    transitions: Mapping[str, Any]
    #: Every declared key name, for `_key_reference_error`.
    keys: set[str]
    #: The values each key closes over, from `_key_errors`.
    closed_values: Mapping[str, tuple[str, ...]]
    #: Whether the document declares an `[identity]` table at all.
    identified: bool

    def at(self, where: str, entry: Mapping[str, Any]) -> "_Entry":
        """This vocabulary, pointed at one entry of one table."""
        return _Entry(where, entry, self.keys, self.closed_values)


@dataclass(frozen=True)
class _Entry:
    """One entry, and what its references are graded against.

    `keys` and `closed_values` are `_Corpus`', unchanged.
    """

    #: Where a complaint points: `states.doing`, `transitions.file-it`.
    where: str
    #: The entry itself, as parsed.
    entry: Mapping[str, Any]
    #: `_Corpus.keys`.
    keys: set[str]
    #: `_Corpus.closed_values`.
    closed_values: Mapping[str, tuple[str, ...]]


def shape_errors(document: Mapping[str, Any]) -> list[str]:
    """Every way `document` is not a plan.toml. Pure: no filesystem, no cwd."""
    errors: list[str] = []

    for name in document:
        if name in RETIRED_TABLES:
            errors.append(
                f"{name} is no longer a plan.toml table. {RETIRED_TABLES[name]}"
            )
        elif name not in KNOWN_TABLES:
            errors.append(
                f"{name} is not a plan.toml table "
                f"(known tables: {', '.join(KNOWN_TABLES)})"
            )

    tables: dict[str, dict[str, Any]] = {}
    for table in TABLES:
        value = document.get(table, {})
        if not isinstance(value, dict):
            errors.append(f"{table} must be a table")
            value = {}
        tables[table] = value

    # Names first, so a misspelled name does not also read as an undeclared
    # reference below.
    for table, entries in tables.items():
        for name in entries:
            if not NAME_RE.match(name):
                errors.append(
                    f"{table}.{name} is not a usable name "
                    "(lowercase letters, digits and hyphens, starting with a letter)"
                )

    # The whole document, so a state opting into a capability that needs another
    # table can be graded against it.
    key_errors, closed_values = _key_errors(tables["keys"])
    errors += key_errors
    corpus = _Corpus(
        state_table=tables["states"],
        transitions=tables["transitions"],
        keys=set(tables["keys"]),
        closed_values=closed_values,
        identified=IDENTITY in document,
    )
    errors += _state_errors(corpus)
    errors += _transition_errors(corpus)
    # The rules that read a verb against the state it writes into need every
    # verb's kind: without one, where it writes is not known, and a state with
    # no verb writing into it would be refused for a defect already named.
    if all(
        isinstance(entry, dict) and entry.get("kind") in KINDS
        for entry in tables["transitions"].values()
    ):
        landed = _landed(tables["transitions"])
        errors += _claim_errors(tables["states"], landed)
        errors += _mint_errors(tables["states"], landed)
        errors += _mark_errors(tables["states"], landed)
        errors += _filing_errors(corpus)
        errors += _archiving_errors(tables["states"], landed)
    errors += _single_value_errors(
        tables["states"], tables["transitions"], _list_valued(tables["keys"])
    )
    errors += _reading_errors(tables["transitions"])
    errors += _identity_errors(document.get(IDENTITY))
    errors += _tool_errors(document.get(TOOL))
    return errors


def _two_halves_errors(
    states: Mapping[str, Any],
    transitions: Mapping[str, Any],
    *,
    capability: str,
    takes: Callable[[Mapping[str, Any]], bool],
    on_verb: Callable[[str, str], str],
    on_state: Callable[[str], str],
) -> list[str]:
    """One rule read from both ends, for a capability declared at both.

    A two-halves capability is one a state opts into and a transition switches
    on. Either half alone is a declaration that cannot do what it says, and
    both are refused by name, from here, because neither table alone can see
    the other. `_mint_errors` and `_claim_errors` are the two instances.

    The four refusals stay at the callers, as `on_verb` and `on_state`: what
    is shared is the walk, not the words.
    """
    opted_in = {
        name
        for name, entry in states.items()
        if isinstance(entry, dict) and capability in _declared_capabilities(entry)
    }
    targeted: set[str] = set()

    errors: list[str] = []
    for name, entry in transitions.items():
        if not takes(entry):
            continue
        to = entry.get("to")
        if not isinstance(to, str) or to not in states:
            # An undeclared or missing `to` is one complaint, already made.
            continue
        targeted.add(to)
        if to not in opted_in:
            errors.append(on_verb(name, to))

    errors += [
        on_state(name)
        for name in states
        if name in opted_in and name not in targeted
    ]
    return errors


def _mint_errors(
    states: Mapping[str, Any], transitions: Mapping[str, Any]
) -> list[str]:
    """The two halves of `BULLETED`, graded against each other.

    `_two_halves_errors` over this capability. What a state needs of itself to
    mint at all is `_bulleted_errors`; this is the half only the two tables
    together can see.
    """
    return _two_halves_errors(
        states,
        transitions,
        capability=BULLETED,
        takes=lambda entry: entry.get("kind") == ADD_BULLET,
        on_verb=lambda name, to: (
            f"transitions.{name} is an add-bullet, and states.{to} does not "
            f'name "{BULLETED}" in its capabilities. A sub-phase is a bullet '
            f"under a heading, and states.{to} is what declares the heading "
            f'and the pending bullet. Name "{BULLETED}" in '
            f"states.{to}.capabilities, or give {name} another kind"
        ),
        on_state=lambda name: (
            f'states.{name}.capabilities names "{BULLETED}", and no add-bullet '
            f"transition writes into {name}. A sub-phase is written by a "
            "transition of that kind, never by an item arriving. Declare one "
            f"from {name}, or drop the capability"
        ),
    )


def _mark_errors(
    states: Mapping[str, Any], transitions: Mapping[str, Any]
) -> list[str]:
    """`marks` graded against the state whose body it writes into.

    Three rules, each refused by name: `marks` into a state that does not name
    `BULLETED`; two verbs marking into one state with the same word; and the
    word itself, through `subphase.mark_errors`.

    A `bulleted` state nothing marks into has no inert-half rule: it is a
    real shape, and loads clean.
    See docs/method.md#marking
    """
    bulleted = {
        name
        for name, entry in states.items()
        if isinstance(entry, dict) and BULLETED in _declared_capabilities(entry)
    }
    spoken: dict[tuple[str, str], list[str]] = {}

    errors: list[str] = []
    for name, entry in transitions.items():
        word = entry.get("marks") if isinstance(entry, dict) else None
        if not isinstance(word, str):
            # A `marks` that is not a string is one complaint, already made.
            continue
        errors += subphase.mark_errors(word, f"transitions.{name}.marks")
        to = entry.get("to")
        if not isinstance(to, str) or to not in states:
            # An undeclared `from` is one complaint, already made.
            continue
        if to not in bulleted:
            errors.append(
                f"transitions.{name} is a mark-bullet, and states.{to} does "
                f'not name "{BULLETED}" in its capabilities. A mark goes on a '
                f"bullet, and states.{to} is what declares the heading those "
                f'bullets live under. Name "{BULLETED}" in '
                f"states.{to}.capabilities, or give {name} another kind"
            )
        spoken.setdefault((to, word), []).append(name)

    errors += [
        f'transitions.{" and ".join(sorted(named))} both mark {to} with '
        f'"{word}". A bullet carrying "{word}" cannot say which of the two '
        "transitions ran. Give each transition its own word"
        for (to, word), named in spoken.items()
        if len(named) > 1
    ]
    return errors


def _filing_errors(corpus: _Corpus) -> list[str]:
    """`files` graded as a table, and as a rider on `marks`.

    The one half whose whole content is a table, so the first rule is the
    table itself and the rest stay quiet where it fails. Six rules, each
    refused by name at load: `files` that is not a table; an unknown field and
    a missing role; `files.state` naming
    an undeclared state; `files.state` naming one that declares `queued`,
    `NUMBERED` or `CLAIMED`, because a filed item is filed rather than placed;
    `files.item` or `files.name` naming a key that cannot be written; and the
    two naming the same key. Then `files.sets`, the one optional field: a list
    of strings, each a key that can be written and neither of the two the
    tool writes itself. And `sets` beside `files`, which would say nothing
    about which head its keys land on.
    See docs/method.md#filing
    """
    # Every capability that writes a head key on arrival, read off the roster.
    placing = tuple(CAPABILITY_KEYS)

    errors: list[str] = []
    for name, entry in corpus.transitions.items():
        if not isinstance(entry, dict) or "files" not in entry:
            continue
        where = f"transitions.{name}.files"
        filing = entry["files"]
        # A field the verb's own kind makes wrong. Before the table's own
        # rules, which do not depend on it.
        if "sets" in entry:
            errors.append(
                f"transitions.{name}.sets is set, and {name} files an item. "
                "Say which head each key lands on: a key for the filed item "
                f"goes in {where}.sets, and {name} writes none onto the item "
                "it moves"
            )
        if not isinstance(filing, dict):
            errors.append(
                f"{where} must be a table naming "
                f"{', '.join(FILING_ROLES)} — where the filed item goes, and "
                "which declared keys record the item and the bullet it came "
                "from"
            )
            continue

        errors += _unknown_fields(where, filing, frozenset(FILING_FIELDS), "filing")
        errors += [
            f"{where} has no {role}, and a filing names all of "
            f"{', '.join(FILING_ROLES)} — where the item goes, and the two "
            "keys that say where it came from"
            for role in FILING_ROLES
            if role not in filing
        ]
        # What each role actually says, for the roles that say a string, decided
        # once so the rules below branch on whether a role is usable.
        said = {
            role: value
            for role in FILING_ROLES
            if isinstance(value := filing.get(role), str)
        }
        errors += [
            f"{where}.{role} must be a string"
            for role in FILING_ROLES
            if role in filing and role not in said
        ]

        if (state := said.get("state")) is not None:
            if state not in corpus.state_table:
                errors.append(f'{where}.state names undeclared state "{state}"')
            else:
                declared = _declared_capabilities(corpus.state_table[state])
                errors += [
                    f'{where}.state names "{state}", which declares '
                    f'"{capability}". The {capability} capability writes a '
                    "head key on arrival, and a filed item is filed rather "
                    "than placed. File into a plain state, and move the item "
                    "afterwards"
                    for capability in placing
                    if capability in declared
                ]
                if CLAIMED in declared:
                    errors.append(
                        f'{where}.state names "{state}", which declares '
                        f'"{CLAIMED}". An item enters a claimed state only by '
                        "a transition that claims it, and a filing claims "
                        "nothing. File into a plain state, and move the item "
                        "afterwards"
                    )

        for role in ("item", "name"):
            if (named := said.get(role)) is None:
                continue
            if reference := _key_reference_error(where, role, named, corpus.keys):
                errors.append(reference)
        if "item" in said and said["item"] == said.get("name"):
            errors.append(
                f'{where}.item and {where}.name both name "{said["item"]}". '
                "One key holding both the carrier and the bullet is a value "
                "nothing can join on. Name a separate key for each"
            )

        if "sets" not in filing:
            continue
        if not _is_string_list(filing["sets"]):
            errors.append(f"{where}.sets must be a list of strings")
            continue
        for named in filing["sets"]:
            if reference := _key_reference_error(where, "sets", named, corpus.keys):
                errors.append(reference)
            errors += [
                f'{where}.sets names "{named}", which {where}.{role} names '
                "too. The tool writes that key onto the filed item itself, "
                "and a second writer could disagree with it. Drop "
                f'"{named}" from {where}.sets'
                for role in ("item", "name")
                if said.get(role) == named
            ]
    return errors


def _archiving_errors(
    states: Mapping[str, Any], transitions: Mapping[str, Any]
) -> list[str]:
    """`archives` graded against the state it files an item out of: out of a
    state that does not name `NUMBERED` it refuses by name, because an entry's
    heading is `## <number>. <title>`. Only a move or a close takes
    `archives`, and both leave, so the number is never left behind.

    A `numbered` state nothing archives out of has no inert-half rule: the
    `archive` field has a second reader in the register itself, so the state
    is a legitimate declaration.
    """
    errors: list[str] = []
    for name, entry in transitions.items():
        if not isinstance(entry, dict) or entry.get("archives") is not True:
            # One complaint per defect: a non-boolean `archives`, and a `from` or
            # `to` naming no declared state, are already made.
            continue
        source = entry.get("from")
        if not isinstance(source, str) or source not in states:
            continue
        if NUMBERED not in _declared_capabilities(states[source]):
            errors.append(
                f"transitions.{name}.archives is true, and states.{source} "
                f'does not name "{NUMBERED}" in its capabilities. An archive '
                f"entry is `## <number>. <title>`, and an item leaving "
                f'{source} carries no number. Name "{NUMBERED}" in '
                f"states.{source}.capabilities, or drop the archives"
            )
    return errors


def _claim_errors(
    states: Mapping[str, Any], transitions: Mapping[str, Any]
) -> list[str]:
    """The two halves of `CLAIMED`, graded against each other.

    A state says its items are claimable; a transition says this verb picks
    one up. Either half alone is refused by name. `_two_halves_errors` is the
    walk, shared with `_mint_errors`.
    """
    return _two_halves_errors(
        states,
        transitions,
        capability=CLAIMED,
        takes=lambda entry: entry.get("claims") is True,
        on_verb=lambda name, to: (
            f'transitions.{name}.claims is true, and states.{to} does not '
            f'name "{CLAIMED}" in its capabilities. A claim lives in the state '
            f'the item is claimed into. Name "{CLAIMED}" in '
            f"states.{to}.capabilities, or drop the claims"
        ),
        on_state=lambda name: (
            f'states.{name}.capabilities names "{CLAIMED}", and no transition '
            f"claims into {name}. A claim is taken by the transition that "
            "declares `claims = true`, never by an item arriving. Name a "
            f"transition that claims into {name}, or drop the capability"
        ),
    )


def _declared_capabilities(entry: Any) -> tuple[str, ...]:
    """What a state entry opts into, as far as the shape can be trusted.

    Including the shape where it is not a table at all: `_filing_errors` and
    `_archiving_errors` are handed a state name by a transition and look the
    entry up, outside the loop that already refused a non-table. The tolerance
    lives here so a third such arm inherits it.
    """
    if not isinstance(entry, dict):
        return ()
    declared = entry.get("capabilities", ())
    return tuple(declared) if _is_string_list(declared) else ()


def _list_valued(keys: Mapping[str, Any]) -> set[str]:
    """Which declared keys hold several values, as far as the shape can be
    trusted — `_declared_capabilities` one table over.

    A flag that is not a boolean is one complaint, already made in
    `_key_errors`, and the key stays out of this set.
    See docs/method.md#list-valued
    """
    return {
        name
        for name, entry in keys.items()
        if isinstance(entry, dict) and entry.get(LIST_VALUED) is True
    }


def _single_value_errors(
    states: Mapping[str, Any],
    transitions: Mapping[str, Any],
    list_valued: set[str],
) -> list[str]:
    """Where a list-valued key may not be named, refused by name at load.

    One walk over `SINGLE_VALUE_FIELDS` and the two filing roles, in one
    message shape, rather than a rule beside each of the six.
    """
    named: list[tuple[str, str, Any]] = [
        (f"states.{name}", field, entry.get(field))
        for name, entry in states.items()
        if isinstance(entry, dict)
        for field in SINGLE_VALUE_FIELDS
    ]
    named += [
        (f"transitions.{name}.files", role, entry["files"].get(role))
        for name, entry in transitions.items()
        if isinstance(entry, dict) and isinstance(entry.get("files"), dict)
        for role in FILING_ROLES
        if role != "state"
    ]
    return [
        f'{where}.{field} names "{key}", which is list-valued. The tool puts '
        "or reads exactly one value here, and a list-valued key holds "
        "several. Name a key that is not list-valued"
        for where, field, key in named
        if isinstance(key, str) and key in list_valued
    ]


def _reading_errors(transitions: Mapping[str, Any]) -> list[str]:
    """A verb setting a key of its own name, refused by name at load.

    The contract's `Reading` block is keyed by name: the transition's own
    pointer, then one per key it `sets`. Two pointers under one name is one
    line, and the key's wins. So the collision is refused here rather than
    read as a verb with no program.
    See docs/method.md#the-contract
    """
    errors: list[str] = []
    for name, entry in transitions.items():
        if not isinstance(entry, dict):
            continue
        filing = entry.get("files")
        # Both lists, because `Reading` names the doc of every key the caller
        # supplies, whichever head it lands on.
        for field, sets in (
            ("sets", entry.get("sets", [])),
            ("files.sets", filing.get("sets", []) if isinstance(filing, dict) else []),
        ):
            if _is_string_list(sets) and name in sets:
                errors.append(
                    f'transitions.{name}.{field} names "{name}", a key of its '
                    "own name. The transition's pointer and the key's pointer "
                    "share one line in Reading, so one would be lost. Rename "
                    "the key, or rename the transition"
                )
    return errors


def _identity_errors(entry: Any) -> list[str]:
    """Every way `[identity]` is not one. Absent is not an error.

    An absent table means the tool cannot say who a session is, which is a
    refusal at the point something needs an identity. The one exception is a
    state opting into `CLAIMED`, graded in `_capability_errors`.
    """
    if entry is None:
        return []
    if not isinstance(entry, dict):
        return [f"{IDENTITY} must be a table"]

    errors = _unknown_fields(IDENTITY, entry, IDENTITY_FIELDS, "session identity")
    errors += _string_field(IDENTITY, entry, "doc")

    if "pid" not in entry:
        return errors + [
            f"{IDENTITY} has no pid — an ordered list of the environment "
            "variable names a session's pid may be read from"
        ]
    declared = entry["pid"]
    if not _is_string_list(declared):
        return errors + [f"{IDENTITY}.pid must be a list of strings"]
    if not declared:
        return errors + [
            f"{IDENTITY}.pid is empty, so no name could ever supply a pid. "
            "Name at least one environment variable, or drop the table"
        ]

    seen: set[str] = set()
    for name in declared:
        if name in seen:
            errors.append(
                f'{IDENTITY}.pid names "{name}" twice. The list is ordered '
                "and the first name that is set wins, so the repeat is never "
                "read. Drop the repeat"
            )
        seen.add(name)
    return errors


def _tool_errors(entry: Any) -> list[str]:
    """Every way `[fileplan]` is not one. Absent is not an error; empty is,
    since a table saying nothing is vacuous, the way `[identity]` without a
    pid is."""
    if entry is None:
        return []
    if not isinstance(entry, dict):
        return [f"{TOOL} must be a table"]
    errors = _unknown_fields(TOOL, entry, frozenset({MINIMUM, ROOT, IGNORE}), "tool")
    if not entry:
        return errors + [
            f"{TOOL} is empty — name the {MINIMUM} fileplan release this "
            'plan.toml reads under, such as "1.2.3", the root its states '
            "sit under, or the file names a state directory does not read "
            "as items, or drop the table"
        ]
    errors += _string_field(TOOL, entry, ROOT)
    if IGNORE in entry:
        errors += _ignore_errors(entry[IGNORE])
    if MINIMUM not in entry:
        return errors
    if not (isinstance(entry[MINIMUM], str) and DOTTED_RE.match(entry[MINIMUM])):
        errors.append(
            f"{TOOL}.{MINIMUM} must be a version of dotted integers, "
            'such as "1.2.3"'
        )
    return errors


def _ignore_errors(value: Any) -> list[str]:
    """Every way `[fileplan].ignore` is not a list of item file names: each
    name is applied in every state directory, so a path cannot be one, and a
    name the traversal never reads cannot be skipped."""
    where = f"{TOOL}.{IGNORE}"
    if not _is_string_list(value):
        return [f"{where} must be a list of strings"]
    if not value:
        return [
            f"{where} is empty — name the files a state directory does not "
            'read as items, such as "AGENTS.md", or drop it'
        ]
    errors: list[str] = []
    seen: set[str] = set()
    for name in value:
        if name in seen:
            errors.append(f'{where} names "{name}" twice')
        seen.add(name)
        if "/" in name or os.sep in name:
            errors.append(
                f'{where}: "{name}" is a path, and the list holds file names '
                "applied in every state directory"
            )
        elif not name.endswith(SUFFIX):
            errors.append(
                f'{where}: "{name}" does not end in {SUFFIX}, and a state '
                "directory never reads it as an item"
            )
    return errors


def _dotted(spelled: str) -> tuple[int, ...]:
    """A version as integers, trailing zeros stripped, so 0.7 equals 0.7.0."""
    parts = [int(part) for part in spelled.split(".")]
    while parts and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def _too_old(document: Mapping[str, Any], source: Path) -> None:
    """Refuse when `[fileplan].minimum` is newer than this tool.

    Run before every other check: a plan.toml written for a newer release
    may use a field this one does not know, and that refusal would blame the
    declaration for the tool's age. A malformed table is `_tool_errors`'s.
    """
    entry = document.get(TOOL)
    wanted = entry.get(MINIMUM) if isinstance(entry, dict) else None
    if not (isinstance(wanted, str) and DOTTED_RE.match(wanted)):
        return
    installed = version("fileplan")
    leading = re.match(r"\d+(\.\d+)*", installed)
    if leading and _dotted(leading.group()) >= _dotted(wanted):
        return
    raise Refusal(
        f"{source} needs fileplan {wanted} or newer, and this is fileplan "
        f"{installed}: upgrade fileplan to read it"
    )


def _state_errors(corpus: _Corpus) -> list[str]:
    errors: list[str] = []
    for name, entry in corpus.state_table.items():
        where = f"states.{name}"
        if not isinstance(entry, dict):
            errors.append(f"{where} must be a table")
            continue
        errors += _unknown_fields(where, entry, STATE_FIELDS, "state")

        # `path` defaults to the state's name, under `[fileplan].root`.
        errors += _string_field(where, entry, "path")

        errors += _string_field(where, entry, "doc")
        at = corpus.at(where, entry)
        errors += _sub_phase_errors(at)
        errors += _capability_errors(where, entry, identified=corpus.identified)
        errors += _archive_errors(where, entry)
        errors += _first_number_errors(where, entry)
        errors += _bulleted_errors(at)
        errors += _key_field_errors(at, OPENED_FOR)
        errors += _sort_errors(at)
    return errors


def _sort_errors(at: _Entry) -> list[str]:
    """A state's declared sort, against the keys a row in that state carries.

    A key no row here can carry would put every item under `unsorted` on
    every read, which is a declaration defect, so it refuses here. A `queued`
    state that names none sorts by `position`, `_sorted`'s default, and the
    overview says so. See docs/method.md#the-queue
    """
    where, entry = at.where, at.entry
    declared = _declared_capabilities(entry)
    if SORT not in entry:
        return []
    named = entry[SORT]
    if not isinstance(named, str):
        return [f"{where}.{SORT} must be a string"]
    carried = [*INTRINSIC_KEYS, *sorted(at.keys)]
    carried += [CAPABILITY_KEYS[one] for one in declared if one in CAPABILITY_KEYS]
    carried += [
        name
        for group in DERIVED_KEYS
        if group.sorts is not None and group.sorts(entry)
        for name in group.names
    ]
    if named.removeprefix("-") in carried:
        return []
    return [
        f'{where}.{SORT} names "{named.removeprefix("-")}", which no item in '
        f"this state carries, so every item would list as unsorted "
        f"(this state carries: {', '.join(carried)})"
    ]


def _bulleted_errors(at: _Entry) -> list[str]:
    """What a state needs of itself to mint a sub-phase into an item's body.

    Three requirements, each refused by name: a `sub-phases` heading to mint
    under, a name form saying what the bullets are called, and a pending
    bullet marking an unfinished decomposition. The other way round, a pending
    bullet or a form on a state that mints nothing is a sentence nothing
    reads. Both are graded through `fileplan.subphase`, the reader that has to
    find them again.
    See docs/method.md#bulleted
    """
    where, entry = at.where, at.entry
    declared = _declared_capabilities(entry)
    mints = BULLETED in declared
    complaints: list[str] = []
    for field in (subphase.PENDING, subphase.FORM):
        if field in entry and not isinstance(entry[field], str):
            complaints.append(f"{where}.{field} must be a string")
    if complaints:
        return complaints

    pending, form = entry.get(subphase.PENDING), entry.get(subphase.FORM)
    if not mints:
        # One arm over both fields: each says something about bullets this state
        # does not carry.
        return [
            f"{where}.{field} {said}, and this state does not opt into "
            f'"{BULLETED}". Nothing writes the field and nothing reads it. '
            f'Add "{BULLETED}" to {where}.capabilities, or drop the field'
            for field, said, value in (
                (
                    subphase.PENDING,
                    "says how an unfinished decomposition is marked",
                    pending,
                ),
                (subphase.FORM, "says what this state's bullets are called", form),
            )
            if value is not None
        ]

    errors: list[str] = []
    if subphase.NAME not in entry:
        errors.append(
            f'{where}.capabilities names "{BULLETED}", and this state '
            f"declares no {subphase.NAME} heading. A sub-phase is a bullet "
            "under a heading, so there is nothing here to mint one under. "
            f"Add {where}.{subphase.NAME}, or drop the capability"
        )
    if form is None:
        errors.append(
            f'{where}.capabilities names "{BULLETED}", and this state '
            f"declares no {subphase.FORM}. A bullet is named from the ordinal "
            "the tool supplies and the form the workflow declares. Add "
            f"{where}.{subphase.FORM}, or drop the capability"
        )
    else:
        errors += _form_errors(where, form, declared=declared, keys=at.keys)
    if pending is None:
        errors.append(
            f'{where}.capabilities names "{BULLETED}", and this state '
            f"declares no {subphase.PENDING}. An unfinished decomposition is "
            "marked by a bullet, so a section half cut up would otherwise "
            f"read as a finished one. Add {where}.{subphase.PENDING}, or drop "
            "the capability"
        )
    else:
        errors += subphase.pending_errors(
            pending, f"{where}.{subphase.PENDING}"
        )
    return errors


def _form_errors(
    where: str, form: str, *, declared: tuple[str, ...], keys: set[str]
) -> list[str]:
    """The declared ident form: its shape, then the fields it names.

    Shape first and alone, through `fileplan.subphase.form_errors`: a form the
    braces do not close has no fields worth grading. Then the fields, which
    only this module can see, in two arms that are one rule read from its two
    ends: a capability key the state does not opt into, and anything else that
    is neither the ordinal slot nor a key an item here can carry.
    """
    if wrong := subphase.form_errors(form, f"{where}.{subphase.FORM}"):
        return wrong

    given = {
        CAPABILITY_KEYS[capability]
        for capability in declared
        if capability in CAPABILITY_KEYS
    }
    carried = {subphase.SLOT, *given, *INTRINSIC_KEYS, *keys}

    errors: list[str] = []
    for field in subphase.fields(form):
        if field in carried:
            continue
        if field in CAPABILITY_KEYS.values():
            errors.append(
                f'{where}.{subphase.FORM} names "{{{field}}}", which the '
                f"{capability_of(field)} capability gives an item, and this "
                f'state does not name "{capability_of(field)}" in its '
                "capabilities. A state that names its bullets from a key is "
                f'the state that mints the key. Add "{capability_of(field)}" '
                f"to {where}.capabilities, or name another field"
            )
            continue
        errors.append(
            f'{where}.{subphase.FORM} names "{{{field}}}", which is not '
            f'"{{{subphase.SLOT}}}" and is not a key an item here can carry. '
            "A field nothing fills would be spelled into every bullet name as "
            f'nothing at all. Name "{{{subphase.SLOT}}}", or a key an item '
            "here carries"
        )
    return errors


def _archive_errors(where: str, entry: Mapping[str, Any]) -> list[str]:
    """The two halves of `ARCHIVE`, against each other.

    A state that mints numbers needs somewhere to read the closed ones from,
    and a state that names one but mints nothing has declared a document
    nothing reads. That the named document exists is `pointer_errors`' half.
    """
    named = entry.get(ARCHIVE)
    mints = NUMBERED in _declared_capabilities(entry)
    if named is not None and not isinstance(named, str):
        return [f"{where}.{ARCHIVE} must be a string"]
    if mints and named is None:
        return [
            f'{where}.capabilities names "{NUMBERED}", and this state '
            f"declares no {ARCHIVE}. An item's file is deleted when it closes, "
            "so the next number would be minted over a closed item's. Add "
            f"{where}.{ARCHIVE}, or drop the capability"
        ]
    if named is not None and not mints:
        return [
            f"{where}.{ARCHIVE} names where closed items are recorded, and "
            f'this state does not opt into "{NUMBERED}". Nothing reads the '
            f'archive this state names. Add "{NUMBERED}" to '
            f"{where}.capabilities, or drop the field"
        ]
    return []


def _first_number_errors(where: str, entry: Mapping[str, Any]) -> list[str]:
    """Every way a declared register floor is not one. Absent grades nothing.

    `_archive_errors`' shape with one arm inverted: a floor is a bound with a
    correct default, so a state without one begins at 1. What the two share is
    the second arm: a field on a state that mints no number reads nothing. A
    bool is an `int` in Python and is not a number here.
    """
    if FIRST_NUMBER not in entry:
        return []
    named = entry[FIRST_NUMBER]
    if not isinstance(named, int) or isinstance(named, bool):
        return [
            f"{where}.{FIRST_NUMBER} holds {named!r}, which is not a whole "
            'number. A floor is compared as a number, and "10" sorts ahead of '
            '"9" when a number is read as text. Write the floor as a bare '
            "integer"
        ]
    if named < 1:
        return [
            f"{where}.{FIRST_NUMBER} is {named}, and a register begins at 1 "
            "or above. The floor names the first number this state may hold, "
            "and there is no section 0"
        ]
    if NUMBERED not in _declared_capabilities(entry):
        return [
            f"{where}.{FIRST_NUMBER} says where this state's register "
            f'begins, and this state does not opt into "{NUMBERED}". Nothing '
            f'reads the floor this state names. Add "{NUMBERED}" to '
            f"{where}.capabilities, or drop the field"
        ]
    return []


def _sub_phase_errors(at: _Entry) -> list[str]:
    """The heading sub-phases are counted under, and the cursor over them.

    Absent is the ordinary case and grades nothing. Present and empty is a
    defect rather than an opt-out, because a heading of `""` would match no
    line and the state would silently count zero for every item.

    The cursor fields name declared keys, so each is graded against the keys
    table. The status's key must declare `values`: a status that can hold
    anything makes a typo'd one a silent wrong state.
    See docs/method.md#the-cursor
    """
    where, entry = at.where, at.entry
    errors: list[str] = []
    if subphase.NAME in entry:
        errors += _string_field(where, entry, subphase.NAME)
        if not errors and not entry[subphase.NAME].strip():
            errors.append(
                f"{where}.{subphase.NAME} is empty, so no heading would ever "
                "match. Every section here would count zero sub-phases. Leave "
                "the field out to count none"
            )

    for field in (subphase.CURSOR, subphase.STATUS):
        if field not in entry:
            continue
        named = entry[field]
        if not isinstance(named, str):
            errors.append(f"{where}.{field} must be a string")
            continue
        if subphase.NAME not in entry:
            errors.append(
                f"{where}.{field} names a cursor over sub-phases, and this "
                f"state declares no {subphase.NAME} heading. A cursor with "
                "nothing to count against cannot be graded. Add "
                f"{where}.{subphase.NAME}, or drop the cursor"
            )
        if reference := _key_reference_error(where, field, named, at.keys):
            errors.append(reference)
            continue
        if field == subphase.STATUS and named not in at.closed_values:
            errors.append(
                f'{where}.{field} names "{named}", which declares no values. '
                "A status that can hold anything makes a typo one more status. "
                f"Declare keys.{named}.values"
            )

    errors += _key_field_errors(at, depends.FIELD)
    return errors


def _key_field_errors(at: _Entry, field: str) -> list[str]:
    """A state field naming a declared key, graded as a reference.

    Two fields are graded by this one function, because the rule is the same
    rule. The cursor fields stay out of it: `_sub_phase_errors` grades two
    further things about them. Nothing grades the values the named key holds —
    an edge naming nothing is reported by the listing rather than refused.
    """
    where, entry = at.where, at.entry
    if field not in entry:
        return []
    named = entry[field]
    if not isinstance(named, str):
        return [f"{where}.{field} must be a string"]
    if reference := _key_reference_error(where, field, named, at.keys):
        return [reference]
    return []


def _capability_errors(
    where: str, entry: Mapping[str, Any], *, identified: bool
) -> list[str]:
    if "capabilities" not in entry:
        return []
    declared = entry["capabilities"]
    if not _is_string_list(declared):
        return [f"{where}.capabilities must be a list of strings"]

    errors = [
        f'{where}.capabilities names "{capability}", which is no longer a '
        f"capability. {RETIRED_CAPABILITIES[capability]}"
        if capability in RETIRED_CAPABILITIES
        else f'{where}.capabilities names unknown capability "{capability}" '
        f"(known: {', '.join(CAPABILITIES)})"
        for capability in declared
        if capability not in CAPABILITIES
    ]
    if CLAIMED in declared and not identified:
        # Graded here rather than at the point a claim is taken: a state that
        # opts in with no way to say who a session is could never take one.
        errors.append(
            f'{where}.capabilities names "{CLAIMED}", and this plan.toml has '
            f"no [{IDENTITY}] table. A claim records the session that holds "
            f"the item. Declare [{IDENTITY}].pid — the environment variable "
            "names a session's pid may be read from — or drop the capability"
        )
    return errors


def _key_errors(
    keys: Mapping[str, Any],
) -> tuple[list[str], dict[str, tuple[str, ...]]]:
    """Errors, plus the closed value sets that `refuses` can be checked against.

    In declared order, not as a set: a refusal that lists a key's values says
    them in the order `plan.toml` wrote.
    """
    errors: list[str] = []
    closed_values: dict[str, tuple[str, ...]] = {}
    for name, entry in keys.items():
        where = f"keys.{name}"
        if name in INTRINSIC_KEYS:
            errors.append(
                f'{where} redeclares "{name}", which every item carries '
                "intrinsically. An item is a head, a body, a location and a "
                f"name, and the tool already knows all four. Drop {where}"
            )
            continue
        if name in CAPABILITY_KEYS.values():
            errors.append(
                f'{where} redeclares "{name}", which the '
                f"{capability_of(name)} capability gives an item in a state "
                f"that opts into it. The {capability_of(name)} capability "
                "writes the key on the way in and drops it on the way out. "
                f"Drop {where}"
            )
            continue
        if name in CLAIM_KEYS:
            errors.append(
                f'{where} redeclares "{name}", which the {CLAIMED} capability '
                f"reads off the tree (read: {', '.join(CLAIM_KEYS)}). Who "
                "holds an item lives in local/claims/ rather than in a head. "
                f"Drop {where}"
            )
            continue
        if name == subphase.NEXT:
            errors.append(
                f'{where} redeclares "{name}", which every listing reads off '
                "the item's own body. Which sub-phase comes next is the cursor "
                "read against the bullets, and a key beside them can only "
                f"drift. Drop {where}"
            )
            continue
        if name in depends.DERIVED:
            errors.append(
                f'{where} redeclares "{name}", which every listing derives '
                "from the tree around the item. What an item waits on, and what "
                "waits on it, is read off the key its state names, against what "
                "is still filed. "
                f"Drop {where}"
            )
            continue
        if name in STALE_KEYS:
            errors.append(
                f'{where} redeclares "{name}", which every listing derives '
                "from git's record of when the file last changed. Nothing is "
                "stored to make it, so a key beside git's record can only go "
                f"stale. Drop {where}"
            )
            continue
        if name in COMMAND_KEYS:
            errors.append(
                f'{where} redeclares "{name}", which every listing derives '
                "from the transitions that could take the item. A key beside "
                f"them can only disagree with what a run does. Drop {where}"
            )
            continue
        if name == subphase.NAME:
            errors.append(
                f'{where} redeclares "{name}", which every listing counts off '
                "the item's own body. How many sub-phases a section carries is "
                "counted from the bullets, and a key beside them can only "
                f"drift. Drop {where}"
            )
            continue
        if name == subphase.LEFT:
            errors.append(
                f'{where} redeclares "{name}", which every listing counts off '
                "the bullets carrying no mark. A key beside the bullets is a "
                "counter somebody has to remember to decrement. Drop "
                f"{where}"
            )
            continue
        if name in RESERVED_KEYS:
            errors.append(
                f'{where} redeclares "{name}", which every listing reads off '
                f"the tree (reserved: {', '.join(RESERVED_KEYS)}). An item's "
                "state is the directory it sits in, and a key beside the tree "
                f"can only disagree with it. Drop {where}"
            )
            continue
        if name in DERIVABLE:
            # Every group above has words of its own; a group added to the
            # roster refuses here until it is given some.
            errors.append(
                f'{where} redeclares "{name}", which every listing derives '
                f"from outside the item's head. Drop {where}"
            )
            continue
        if not isinstance(entry, dict):
            errors.append(f"{where} must be a table")
            continue
        errors += _unknown_fields(where, entry, KEY_FIELDS, "key")

        # `doc` is optional, as on a state: a key whose meaning needs no
        # section of its own says so by naming none. See docs/method.md#the-contract
        errors += _string_field(where, entry, "doc")
        errors += _string_field(where, entry, "help")

        # A real boolean, not a string that reads like one: `list-valued = "false"`
        # is truthy.
        if LIST_VALUED in entry and not isinstance(entry[LIST_VALUED], bool):
            errors.append(f"{where}.{LIST_VALUED} must be true or false")

        if "values" in entry:
            if not _is_string_list(entry["values"]):
                # The arm in `_transition_errors` that would check `refuses`
                # against this key stays quiet: one complaint per defect.
                errors.append(f"{where}.values must be a list of strings")
            else:
                closed_values[name] = tuple(entry["values"])
    return errors, closed_values


def _transition_errors(corpus: _Corpus) -> list[str]:
    errors: list[str] = []
    for name, entry in corpus.transitions.items():
        where = f"transitions.{name}"
        if not isinstance(entry, dict):
            errors.append(f"{where} must be a table")
            continue

        errors += [
            f"{where}.{field} is no longer a transition field, because the "
            f'kind says it. Write kind = "{_suggested_kind(entry)}", and drop '
            f"the {field}"
            for field in REMOVED_FIELDS
            if field in entry
        ]
        errors += [
            f"{where}.{field} is no longer a transition field. {said}"
            for field, said in RETIRED_FIELDS.items()
            if field in entry
        ]
        kind = entry.get("kind")
        if kind is None:
            suggested = _suggested_kind(entry)
            errors.append(
                f"{where} has no kind. Its fields spell {_a(suggested)}, so "
                f'write kind = "{suggested}"'
            )
            continue
        if kind not in KINDS:
            errors.append(
                f"{where}.kind is {kind!r}, which is not a kind "
                f"(kinds: {', '.join(KINDS)})"
            )
            continue

        takes = TRANSITION_FIELDS | KINDS[kind]
        for field in entry:
            if field in takes or field in REMOVED_FIELDS or field in RETIRED_FIELDS:
                continue
            if field == "to":
                errors.append(
                    f"{where}.to is set, and {_a(kind)} "
                    + (
                        "takes the item's file away, so it lands nowhere"
                        if kind in DISSOLVING
                        else "stays in its from state"
                    )
                    + ". Drop the to"
                )
            elif field in TRANSITION_FIELDS.union(*KINDS.values()):
                errors.append(
                    f"{where}.{field} is set, and {_a(kind)} does not take it "
                    f"({_a(kind)} takes {', '.join(sorted(KINDS[kind]))})"
                )
            else:
                errors.append(f"{where}.{field} is not a transition field")

        errors += [
            f"{where} has no {required}"
            for required in KIND_REQUIRES[kind]
            if required not in entry
        ]

        for field in ("doc", "help", "marks"):
            errors += _string_field(where, entry, field)

        # Real booleans, not strings that read like one: `claims = "false"` is
        # truthy too.
        errors += [
            f"{where}.{field} must be true or false"
            for field in ("claims", "archives")
            if field in entry and not isinstance(entry[field], bool)
        ]

        for field in ("to", "from"):
            if field not in entry:
                continue
            if not isinstance(entry[field], str):
                errors.append(f"{where}.{field} must be a string")
            elif entry[field] not in corpus.state_table:
                errors.append(
                    f'{where}.{field} names undeclared state "{entry[field]}"'
                )

        errors += _kind_errors(corpus, where, entry)

        for field in ("requires", "sets", "drops"):
            if field not in entry:
                continue
            if not _is_string_list(entry[field]):
                errors.append(f"{where}.{field} must be a list of strings")
                continue
            errors += [
                error
                for named in entry[field]
                if (error := _key_reference_error(where, field, named, corpus.keys))
            ]

        errors += _refuses_errors(corpus.at(where, entry))
    return errors


def _kind_errors(corpus: _Corpus, where: str, entry: Mapping[str, Any]) -> list[str]:
    """The three rules a kind's own field list cannot say: a move that does
    not leave, a reorder in a state with no order, and an edit that writes
    nothing. Each would be a verb that does not do what its kind says.
    See docs/method.md#kinds
    """
    kind, source = entry["kind"], entry.get("from")
    if kind == MOVE and source is not None and source == entry.get("to"):
        return [
            f'{where} is a move from "{source}" to itself. A move leaves its '
            f'state. Write kind = "{EDIT}", or kind = "{REORDER}" for one that '
            "only changes the item's place"
        ]
    if (
        kind == REORDER
        and isinstance(source, str)
        and source in corpus.state_table
        and QUEUED not in _declared_capabilities(corpus.state_table[source])
    ):
        return [
            f'{where} is a reorder, and states.{source} does not name "{QUEUED}" '
            "in its capabilities, so its items have no order to change. Name "
            f'"{QUEUED}" in states.{source}.capabilities, or give {where} '
            "another kind"
        ]
    if kind == EDIT and not any(
        field in entry for field in EDIT_WRITES
    ):
        return [
            f"{where} is an edit, and it writes nothing: it names no sets, no "
            "drops and no claims. Name what it writes, or drop the transition"
        ]
    return []


def _suggested_kind(entry: Mapping[str, Any]) -> str:
    """The kind an entry's fields spell, for the refusal that asks for one.

    Read off the fields a plan.toml written before kinds carried, which is
    the migration a refusal names: no `from` creates, `dissolves` closes or,
    with `absorbs`, merges, `mints`, `marks` and `retitles` each name their
    kind, a `to` elsewhere moves, and a verb staying put edits if it writes a
    key or a claim and reorders if it does not. See docs/method.md#kinds
    """
    if "from" not in entry:
        return CREATE
    if entry.get("dissolves") is True:
        return MERGE if entry.get("absorbs") is True else CLOSE
    if entry.get("mints") is True:
        return ADD_BULLET
    if "marks" in entry:
        return MARK_BULLET
    if entry.get("retitles") is True:
        return RENAME
    if "to" in entry and entry.get("to") != entry["from"]:
        return MOVE
    if any(field in entry for field in EDIT_WRITES):
        return EDIT
    return REORDER


def _helped(entry: Mapping[str, Any]) -> str:
    """The `help` a transition gets from its kind when it declares none."""
    kind = entry["kind"]
    archiving = ARCHIVING_HELP.get(kind) if entry.get("archives") is True else None
    return (archiving or KIND_HELP[kind]).format(
        to=entry.get("to"), marks=entry.get("marks"), **{"from": entry.get("from")}
    )


def _a(word: str) -> str:
    """`word` with its article."""
    return f"{'an' if word[0] in 'aeiou' else 'a'} {word}"


def _landed(transitions: Mapping[str, Any]) -> dict[str, Any]:
    """The transitions table, each kind that stays given its `from` as its
    `to`: where the item is when the run is over.

    The rules that grade a verb against the state it writes into, and the
    loader, read `to` for that state. A kind that stays declares none, so it
    is filled here, once, rather than each reader asking the kind.
    """
    return {
        name: (
            {**entry, "to": entry["from"]}
            if isinstance(entry, dict)
            and entry.get("kind") in STAYING
            and "from" in entry
            else entry
        )
        for name, entry in transitions.items()
    }


def _refuses_errors(at: _Entry) -> list[str]:
    where, entry, closed_values = at.where, at.entry, at.closed_values
    if "refuses" not in entry:
        return []
    refuses = entry["refuses"]
    if not isinstance(refuses, dict):
        return [f"{where}.refuses must be a table of key = true or key = [values]"]

    errors: list[str] = []
    for key, values in refuses.items():
        if error := _key_reference_error(where, "refuses", key, at.keys):
            errors.append(error)
            continue
        if values is True:
            # Presence: the item carries the key at all.
            continue
        if values is False:
            errors.append(
                f"{where}.refuses.{key} is false, which refuses nothing. "
                "Write true, or a list of values"
            )
            continue
        if not _is_string_list(values):
            errors.append(f"{where}.refuses.{key} must be true, or a list of strings")
            continue
        if key not in closed_values:
            # Free text, or a key whose own `values` is already complained about.
            continue
        errors += [
            f'{where}.refuses.{key} names "{value}", '
            f"which is not a declared value of keys.{key}"
            for value in values
            if value not in closed_values[key]
        ]
    return errors


def _key_reference_error(
    where: str, field: str, named: str, keys: set[str]
) -> str | None:
    """One complaint about a `requires`/`sets`/`drops`/`refuses` name.

    An intrinsic key is named apart from an undeclared one: `sets = ["title"]`
    is a real transition, and reading it as an undeclared key would send
    someone to write `[keys.title]`, which refuses too.
    """
    if named in INTRINSIC_KEYS:
        return (
            f'{where}.{field} names "{named}", which is intrinsic to every item '
            "rather than a declared key"
        )
    if named in CAPABILITY_KEYS.values():
        return (
            f'{where}.{field} names "{named}", which the '
            f"{capability_of(named)} capability writes on entry and drops on "
            "exit by itself. Naming the key here would be a second spelling "
            f'that can disagree with the capability. Drop "{named}" from '
            f"{where}.{field}"
        )
    if named in CLAIM_KEYS:
        return (
            f'{where}.{field} names "{named}", which the {CLAIMED} capability '
            "reads off local/claims/ rather than out of a head. A claim's "
            "fields are read rather than written, so there is nothing here to "
            f'set. Drop "{named}" from {where}.{field}'
        )
    if named in DERIVABLE:
        # One arm over the whole roster: what is derived is read rather than
        # written, and the difference is only which source the message names.
        source = (
            "the item's own body"
            if named in subphase.DERIVED
            else "the tree around the item"
            if named in depends.DERIVED
            else "the transitions that could take the item"
            if named in COMMAND_KEYS
            else "git's record of when the file last changed"
            if named in STALE_KEYS
            else "outside the item's head"
        )
        return (
            f'{where}.{field} names "{named}", which every listing derives '
            f"from {source}. A derived key is read rather than written, so "
            f'there is nothing here to set. Drop "{named}" from '
            f"{where}.{field}"
        )
    if named not in keys:
        return f'{where}.{field} names undeclared key "{named}"'
    return None


def capability_of(key: str) -> str:
    """Which capability gives `key`, for a refusal that names it."""
    return next(
        capability for capability, given in CAPABILITY_KEYS.items() if given == key
    )


def _unknown_fields(
    where: str, entry: Mapping[str, Any], known: frozenset[str], noun: str
) -> list[str]:
    # The article follows the noun rather than being baked into the format.
    article = "an" if noun[0] in "aeiou" else "a"
    return [
        f"{where}.{field} is not {article} {noun} field"
        for field in entry
        if field not in known
    ]


def _string_field(where: str, entry: Mapping[str, Any], field: str) -> list[str]:
    if field in entry and not isinstance(entry[field], str):
        return [f"{where}.{field} must be a string"]
    return []


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


# --------------------------------------------------------------------------
# Doc pointers: the citation guard
# --------------------------------------------------------------------------


def pointer_errors(document: Mapping[str, Any], root: Path) -> list[str]:
    """Every `doc =` pointer that does not resolve, relative to `root`.

    A pointer must carry an anchor (`path#heading`), matched against
    GitHub-style heading slugs, and this runs at every invocation alongside
    `shape_errors`. A state's `archive` names no anchor, because it is a whole
    document, and what is checked of it is that it exists: an empty archive is
    a repo that has closed nothing.
    """
    errors: list[str] = _archive_pointer_errors(document, root)
    headings: dict[Path, set[str] | None] = {}

    for where, pointer in _pointers(document):
        if "#" not in pointer:
            errors.append(f'{where} is "{pointer}", which names no #heading')
            continue
        relative, _, anchor = pointer.rpartition("#")
        if not relative or not anchor:
            errors.append(f'{where} is "{pointer}", which names no #heading')
            continue

        target = root / relative
        if target not in headings:
            headings[target] = heading_slugs(target)
        slugs = headings[target]
        if slugs is None:
            errors.append(f"{where} names {relative}, which does not exist")
        elif anchor not in slugs:
            errors.append(
                f'{where} names anchor "#{anchor}", which is not a heading in {relative}'
            )
    return errors


def _archive_pointer_errors(document: Mapping[str, Any], root: Path) -> list[str]:
    """Every `archive` a state names and the tree does not hold."""
    states = document.get("states", {})
    if not isinstance(states, dict):
        return []
    return [
        f"states.{name}.{ARCHIVE} names {entry[ARCHIVE]}, "
        "which does not exist. A register that cannot read the archive would "
        "mint a number some closed item already holds. Create the file, empty "
        "if this repo has closed nothing"
        for name, entry in states.items()
        if isinstance(entry, dict)
        and isinstance(entry.get(ARCHIVE), str)
        and not (root / entry[ARCHIVE]).is_file()
    ]


def _pointers(document: Mapping[str, Any]) -> list[tuple[str, str]]:
    # No type guards here: `load` reaches `pointer_errors` only once
    # `shape_errors` comes back empty, so by then a table is a table and a `doc`
    # that is present is a string. `tests/test_declaration.py` pins that
    # ordering, because nothing else does. What survives is two presence tests,
    # since a state's `doc` and `[identity]`'s are optional.
    found: list[tuple[str, str]] = []
    for table in ANCHORED:
        for name, entry in document.get(table, {}).items():
            if "doc" in entry:
                found.append((f"{table}.{name}.doc", entry["doc"]))

    if "doc" in document.get(IDENTITY, {}):
        found.append((f"{IDENTITY}.doc", document[IDENTITY]["doc"]))
    return found


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$")


def heading_slugs(path: Path, *, level: int | None = None) -> set[str] | None:
    """GitHub-style slugs of the headings in `path`, or `None` if absent.

    `level` narrows to headings of one depth. Numbering for a repeated slug is
    still counted across every heading, because that is how the anchor a
    browser follows is minted. A heading inside a code fence is not a heading,
    read through `subphase.FENCE`.

    Public because "what headings a document has" has one home: this grades
    the `doc =` fields, and `tests/test_docs.py` grades the citations that are
    not `doc =` fields with the same function.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    slugs: set[str] = set()
    seen: dict[str, int] = {}
    fenced = False
    for line in text.splitlines():
        if subphase.FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        match = _HEADING_RE.match(line)
        if not match:
            continue
        slug = _slug(match.group(2))
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        if level is not None and len(match.group(1)) != level:
            continue
        slugs.add(slug if count == 0 else f"{slug}-{count}")
    return slugs


def _slug(heading: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", heading)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_]", "", text)
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "-", text)


# --------------------------------------------------------------------------
# Discovery and loading
# --------------------------------------------------------------------------


def load(path: str | os.PathLike[str] | None = None) -> Declaration:
    """Find, parse and validate `plan.toml`, or raise `Refusal`.

    Discovery, in order: the `path` argument, then `FILEPLAN_PLAN_TOML`, then
    a walk up from cwd like git. The first two are used exactly.
    """
    source = _discover(path)

    try:
        with source.open("rb") as handle:
            document = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise Refusal(f"{source} is not valid TOML: {exc}") from None
    except OSError as exc:
        raise Refusal(f"{source} could not be read: {exc.strerror}") from None

    _too_old(document, source)
    root = source.parent
    errors = shape_errors(document)
    if not errors:
        # Only worth chasing pointers once the shape holds.
        errors = pointer_errors(document, root)
    if errors:
        raise Refusal([f"{source} is not a usable plan.toml", *errors])

    return Declaration(
        source=source,
        root=root,
        states=_states(
            document.get("states", {}),
            _landed(document.get("transitions", {})),
            document.get(TOOL, {}).get(ROOT),
        ),
        keys=_keys(document.get("keys", {})),
        transitions=_transitions(_landed(document.get("transitions", {}))),
        pid_names=tuple(document.get(IDENTITY, {}).get("pid", ())),
        ignore=frozenset(document.get(TOOL, {}).get(IGNORE, ())),
    )


def _discover(path: str | os.PathLike[str] | None) -> Path:
    named, origin = (
        (path, "") if path is not None
        else (os.environ.get(PLAN_TOML_ENV), f" ({PLAN_TOML_ENV})")
    )
    if named is not None:
        # No fallback: grading against a vocabulary you did not choose is worse.
        source = Path(named)
        if not source.is_file():
            raise Refusal(f"{source} does not exist{origin}")
        return source.resolve()

    start = Path.cwd()
    for directory in (start, *start.parents):
        candidate = directory / PLAN_TOML_NAME
        if candidate.is_file():
            return candidate.resolve()
    raise Refusal(
        f"no {PLAN_TOML_NAME} in {start} or any parent directory "
        f"(set {PLAN_TOML_ENV} to name one, or run `fileplan init` to write "
        "a first one here)"
    )


def _states(
    entries: Mapping[str, Any],
    transitions: Mapping[str, Any],
    root: str | None = None,
) -> dict[str, State]:
    marks: dict[str, set[str]] = {}
    for entry in transitions.values():
        if "marks" in entry and "to" in entry:
            marks.setdefault(entry["to"], set()).add(entry["marks"])
    return {
        name: State(
            name=name,
            path=entry.get("path", _path(name, root)),
            doc=entry.get("doc"),
            capabilities=tuple(entry.get("capabilities", ())),
            sub_phases=entry.get(subphase.NAME),
            cursor=entry.get(subphase.CURSOR),
            status=entry.get(subphase.STATUS),
            pending=entry.get(subphase.PENDING),
            sub_phase_name=entry.get(subphase.FORM),
            dependencies=entry.get(depends.FIELD),
            opened_for=entry.get(OPENED_FOR),
            archive=entry.get(ARCHIVE),
            first_number=entry.get(FIRST_NUMBER, FIRST),
            sort=_sorted(entry),
            marks=frozenset(marks[name]) if name in marks else None,
        )
        for name, entry in entries.items()
    }


def _path(name: str, root: str | None) -> str:
    """A state's default `path`: its name, under `root` where one is given."""
    return str(Path(root) / name) if root else name


def _sorted(entry: Mapping[str, Any]) -> str | None:
    """A state's sort: the one it declares, else `position` on a `queued`
    state, the one sensible value, else none."""
    if SORT in entry:
        return entry[SORT]
    if QUEUED in entry.get("capabilities", ()):
        return CAPABILITY_KEYS[QUEUED]
    return None


def _keys(entries: Mapping[str, Any]) -> dict[str, Key]:
    return {
        name: Key(
            name=name,
            doc=entry.get("doc"),
            help=entry.get("help"),
            values=tuple(entry["values"]) if "values" in entry else None,
            list_valued=bool(entry.get(LIST_VALUED, False)),
        )
        for name, entry in entries.items()
    }


def _transitions(entries: Mapping[str, Any]) -> dict[str, Transition]:
    # dict preserves TOML document order, which is the order subcommands are
    # registered in.
    return {
        name: Transition(
            name=name,
            doc=entry.get("doc"),
            help=entry.get("help") or _helped(entry),
            to=entry.get("to"),
            kind=entry["kind"],
            source=entry.get("from"),
            requires=tuple(entry.get("requires", ())),
            refuses={
                key: tuple(values)
                for key, values in entry.get("refuses", {}).items()
                if values is not True
            },
            refuses_any=tuple(
                key for key, values in entry.get("refuses", {}).items() if values is True
            ),
            sets=tuple(entry.get("sets", ())),
            drops=tuple(entry.get("drops", ())),
            claims=bool(entry.get("claims", False)),
            marks=entry.get("marks"),
            files=entry.get("files"),
            archives=bool(entry.get("archives", False)),
        )
        for name, entry in entries.items()
    }
