"""Command-line entry point: a subcommand per declared transition.

Nothing here is written per transition. The loop over the declaration's
transitions is the whole of the registration. A capability generates its own
options for the transitions that can use them.

Some names are the tool's own and reserved. `list` and `show` are the reads. `release` comes from a capability, and `init` writes a first
declaration.

`--version`, `--skills` and `init` answer before the declaration loads.
`--help` does not, because the help text is generated from the declaration.
"""

from __future__ import annotations

import dataclasses
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Any, Callable, Mapping

import click

from fileplan import (
    claim,
    depends,
    item,
    numbered,
    queued,
    read,
    render,
    scaffold,
    subphase,
)
from fileplan.declaration import (
    ADD_BULLET,
    MERGE,
    PLACING,
    RENAME,
    Declaration,
    Key,
    Refusal,
    Transition,
    load,
    named,
)
from fileplan.transition import INTO, KEEP_CLAIMS as KEEPING, MARKING, NOTE, RECORD
from fileplan.transition import RETITLE as RETITLING
from fileplan.transition import commands, execute, release

#: The read's own name. It is not a declared verb and cannot become one.
LIST_COMMAND = "list"

#: The listing's row for one item, registered unconditionally.
#: See docs/method.md#show
SHOW_COMMAND = "show"

#: The command that frees a claim: registered only where a state claims what
#: it holds, and reserved everywhere. See docs/method.md#release
RELEASE_COMMAND = "release"

#: The command that writes a first declaration, registered unconditionally and
#: answering before the declaration loads. See docs/method.md#init
INIT_COMMAND = "init"

#: The other two: options rather than words of their own, and the two that
#: answer outside a plan tree, because what version this is and where the
#: tool keeps its files are facts about the tool rather than the workflow.
#: See docs/method.md#the-version and docs/method.md#the-skills
VERSION_FLAG = "--version"
SKILLS_FLAG = "--skills"

#: The tool's own words, for the refusal naming a declared transition that
#: takes one. Reserved whether or not the command is registered.
RESERVED = {
    LIST_COMMAND: "the read",
    SHOW_COMMAND: "the read of one item",
    RELEASE_COMMAND: "the release",
    INIT_COMMAND: "the scaffold",
}

#: The options the `queued` capability puts on a transition into a state that
#: has it. `--above` and `--below` name another item; `--at` names the place
#: outright and is the respacing tool. See docs/method.md#the-queue
PLACEMENT = (
    ("above", "ITEM", str, "Put the item directly ahead of ITEM."),
    ("below", "ITEM", str, "Put the item directly behind ITEM."),
    (
        "at",
        "N",
        int,
        f"Put the item at place N exactly. Places are {queued.SPACING} apart, "
        "and --at is how you respace a gap.",
    ),
)

#: The options an add-bullet takes. `--last`
#: is the only way the pending bullet leaves. See docs/method.md#bulleted
MINTING = (
    (
        "title",
        "TEXT",
        str,
        "Write a sub-phase with this title into the item's body. The name "
        "comes from the form the item's state declares, plus the next free "
        "ordinal.",
    ),
    (
        "last",
        None,
        None,
        "This is the final sub-phase. Close the decomposition, leaving "
        "nothing pending.",
    ),
)

#: `RECORD` is the option a close that `archives` takes: the prose that goes
#: under the entry's heading, required, and only on that one shape. `INTO`
#: is a merge's survivor, `NOTE` a mark-bullet's reason, `MARKING` the key a
#: mark-bullet's bullet is read back under, `RETITLING` a rename's new title
#: and `KEEPING` the key `--keep-claims` is read back under. Each is the
#: executor's name, imported from `fileplan.transition`.
#: See docs/method.md#the-register

#: The options a verb that `files` takes: what to call the item it creates from
#: the bullet it disposes of, and the prose that goes in it. `--title` is
#: optional and defaults to the bullet's own text; `--body` is required by the
#: executor rather than by click. See docs/method.md#filing
FILING = (
    (
        "title",
        "TEXT",
        str,
        "Call the filed item this. Without --title, the filed item takes "
        "the bullet's own text.",
    ),
    (
        "body",
        "TEXT",
        str,
        "The filed item's description. Required. `-` reads the description "
        "from stdin, so `--body - < notes.md` takes it from a file.",
    ),
)

#: The second positional a mark-bullet takes: the bullet the run acts on.
#: Its own click parameter, because `name` is already the item handle's, and
#: its metavar. See docs/method.md#marking
BULLET, MARKING_METAVAR = "bullet", "NAME"

#: The metavar of a rename's second positional, the item's new title. A
#: positional, so it cannot collide with the `--title` a mint or a filing
#: takes. See docs/method.md#retitle
RETITLE_METAVAR = TITLE = "TITLE"

#: What a handle naming one item, or several, shows as on the command line,
#: and the option a create's prose comes in by. Read by the usage hints and
#: the empty listing's line as well as by the commands, so the three agree.
ITEM, ITEMS, BODY = "ITEM", "ITEM...", "body"

#: The flag a verb that `claims` takes: hold this claim beside the others this
#: session already holds. It needs the `sets` collision check.
#: See docs/method.md#the-claimed-state
KEEP_CLAIMS = "keep-claims"

#: The flag every generated transition carries: run the verb's whole path and
#: stop at the seam where nothing has been written. A declared key of the same
#: name refuses by name. See docs/method.md#the-check
CHECK = "check"

#: The options a transition may declare beside its kind, which the
#: `Declares` block lists after the kind, by name and nothing else: what each
#: means is a section the `Reading` block points at. See docs/method.md#kinds
DECLARED = ("claims", "files", "archives")

#: What the JSON envelope calls this listing, and the noun the text frame
#: counts in on every read whose rows are items.
LIST_KIND = "items"

#: And what it calls one item. Singular, against `items`.
SHOW_KIND = "item"

#: And what it calls the whole declaration: the states, then one contract per
#: declared transition. Not a read — it describes the declaration rather than
#: the tree. See docs/method.md#the-contract
DECLARATION_KIND = "declaration"

#: And what it calls one bullet: the tool's own noun for them, singular.
BULLET_KIND = subphase.NAME.removesuffix("s")

#: The one field a bullet read carries that a bullet row does not: the verbatim
#: lines. Not a row field, because that would put a body in every listing.
#: See docs/method.md#show
BULLET_TEXT = "text"


# The click group is built inside `main` rather than at import, so a
# malformed declaration's refusal stays catchable in-process.
def main(argv: list[str] | None = None) -> int:
    """Run fileplan. Returns the exit status; 2 for a refusal."""
    args = sys.argv[1:] if argv is None else argv
    declaration = None
    try:
        if args[:1] == [INIT_COMMAND]:
            # Before the declaration loads: it is the command that writes one.
            _init_command().main(
                args=args[1:],
                prog_name=f"fileplan {INIT_COMMAND}",
                standalone_mode=False,
            )
        elif args[:1] == [VERSION_FLAG]:
            # A fact about the tool rather than the workflow, so it answers
            # outside a plan tree. `--help` is not here: the help is the
            # declaration.
            _version_command().main(
                args=args, prog_name="fileplan", standalone_mode=False
            )
        elif args[:1] == [SKILLS_FLAG]:
            # `--version`'s reason, and it answers however fileplan was installed.
            if args[1:]:
                raise Refusal(f"`fileplan {SKILLS_FLAG}` takes nothing else")
            click.echo(scaffold.skills())
        else:
            declaration = load()
            group = _build_group(declaration)
            group.main(args=args, prog_name="fileplan", standalone_mode=False)
    except Refusal as refusal:
        return _refuse(refusal)
    except click.exceptions.Exit as exit_:
        return exit_.exit_code
    except click.ClickException as exc:
        exc.show()
        if declaration is not None and (said := _pointer(exc, declaration)):
            click.echo(said, err=True)
        return exc.exit_code
    except click.exceptions.Abort:
        click.echo("ERROR: aborted", err=True)
        return 1
    return 0


def _pointer(exc: click.ClickException, declaration: Declaration) -> str | None:
    """The documented way through a usage error click raised, or `None`.

    Three dead ends a consumer's sessions hit often enough to count. Each
    keeps click's refusal and adds where to go: nothing about what is
    accepted changes. See docs/method.md#the-listing
    """
    ctx = getattr(exc, "ctx", None)
    if ctx is None:
        return None
    name = ctx.command.name
    if isinstance(exc, click.MissingParameter) and exc.param is not None:
        if exc.param.name == RECORD and name in declaration.transitions:
            source = declaration.transitions[name].source
            archive = declaration.states[source].archive if source else None
            return (
                f"--{RECORD} is the entry filed under the item's number in "
                f"{archive}: what it decided and what it shipped. `--{RECORD} "
                "-` reads it from stdin"
            )
        # The handle every transition takes is the `name` parameter, whatever
        # its metavar says; a create's is a title, and gets no hint.
        if name in declaration.transitions and exc.param.name == "name":
            if declaration.transitions[name].source is None:
                return None
            return (
                f"fileplan {LIST_COMMAND} --has {read.COMMANDS}={name} lists "
                "what it can take"
            )
        if exc.param.human_readable_name == ITEM:
            return f"fileplan {LIST_COMMAND} lists every item"
    extra = str(exc.message).removeprefix("Got unexpected extra argument")
    if name == LIST_COMMAND and extra != exc.message:
        word = extra.lstrip("s (").rstrip(")").split()[0]
        if word in declaration.states:
            return f"did you mean --state {word}?"
    return None


def _version_option() -> Callable[[Any], Any]:
    """The `--version` option, constructed in one place.

    Two things want it: the group, and the arm in `main` that answers it
    before a declaration exists.
    See docs/method.md#the-version
    """
    return click.version_option(version("fileplan"), prog_name="fileplan")


def console_main() -> None:
    """The `fileplan` console script. Wraps `main` so rc 2 survives."""
    sys.exit(main())


class _Declared(click.Group):
    """A group that lists its commands in the order they were declared.

    click sorts alphabetically; `plan.toml`'s order is the workflow's own.
    """

    def list_commands(self, ctx: click.Context) -> list[str]:
        return list(self.commands)


def _build_group(declaration: Declaration) -> click.Group:
    @click.group(cls=_Declared, invoke_without_command=True)
    @_version_option()
    @click.pass_context
    def group(ctx: click.Context, as_json: bool) -> None:
        """Track work as files in directories, and move each file with the
        commands plan.toml declares."""
        ctx.obj = declaration
        if ctx.invoked_subcommand is not None:
            # Loud rather than ignored: the flag here asks about the
            # declaration, and a command asks about something else.
            if as_json:
                raise Refusal(
                    "`fileplan --json` describes the declaration and takes no "
                    f"command, and `{ctx.invoked_subcommand}` is one. A read "
                    "spells its own, after the command: "
                    f"`fileplan {ctx.invoked_subcommand} --json`"
                )
            return
        _contents(declaration, ctx.command, as_json)

    # The read's own flag, from the one function that spells it, rather than a
    # second spelling of the same option on the group.
    group.params.append(_json_option())

    # The reads first: finding what to act on comes before acting on it.
    group.add_command(_list_command(declaration))
    group.add_command(_show_command(declaration))
    for transition in declaration.transitions.values():
        if transition.name in RESERVED:
            raise Refusal(
                f"transitions.{transition.name} takes the name of "
                f"{RESERVED[transition.name]}. `fileplan {transition.name}` is "
                "the tool's own word, and a transition cannot take its name — "
                "one command cannot mean two things"
            )
        group.add_command(_command(declaration, transition))

    # Only where there is something to free: it repairs the workflow.
    if declaration.has(claim.NAME):
        group.add_command(_release_command(declaration))
    # And `init`, unconditionally: one implementation, registered here and
    # dispatched from `main`, so the two paths cannot drift.
    group.add_command(_init_command())
    return group


# --------------------------------------------------------------------------
# One command per transition, built from the declaration
# --------------------------------------------------------------------------


def _command(declaration: Declaration, transition: Transition) -> click.Command:
    # Each gate on what this kind takes, decided once: the parameters below
    # and the pops in `run` read the same names.
    creating = transition.source is None
    absorbing = transition.kind == MERGE
    marking = transition.marks is not None
    renaming = transition.kind == RENAME
    placed = _places(declaration, transition)
    minting = transition.kind == ADD_BULLET
    filing = transition.files is not None
    recording = transition.records
    claiming = transition.claims
    params: list[click.Parameter] = [
        # One positional, variadic only on a merge: several
        # items can continue as one survivor. See docs/method.md#merge
        click.Argument(["name"], nargs=-1, required=True, metavar=ITEMS)
        if absorbing
        else click.Argument(["name"], metavar=TITLE if creating else ITEM)
    ]
    if marking:
        # After the item's, so the usage line reads ITEM NAME.
        params.append(click.Argument([BULLET], metavar=MARKING_METAVAR))
        params.append(_note_option(transition))
    if renaming:
        # After the item's too: ITEM TITLE, as `idea TITLE` takes one.
        params.append(click.Argument([RETITLING], metavar=RETITLE_METAVAR))
    if creating:
        if BODY in transition.sets:
            raise Refusal(
                f'transitions.{transition.name}.sets names "{BODY}", and a '
                "transition that creates an item already takes --body for its "
                "prose. One option cannot mean two things"
            )
        params.append(
            click.Option(
                [f"--{BODY}"],
                metavar="TEXT",
                help=(
                    "The item's description. `-` reads the description from "
                    "stdin, so `--body - < notes.md` takes it from a file."
                ),
            )
        )
    params += [_option(declaration, key) for key in transition.sets]
    if placed:
        params += _placement_options(transition)
    if minting:
        params += _minting_options(transition)
    if filing:
        params += _filing_options(transition)
        # The filed item's keys, after its title and body: each is written onto
        # the item this run files, never the one it moves.
        params += [_option(declaration, key) for key in transition.files_sets]
    if recording:
        params.append(_record_option())
    if absorbing:
        params.append(_into_option())
    if claiming:
        params.append(_keep_claims_option(transition))
    params.append(_check_option(transition))

    def run(**given: Any) -> None:
        check = bool(given.pop(CHECK))
        asked = {flag: given.pop(flag) for flag, *_ in PLACEMENT} if placed else {}
        if minting:
            asked.update({flag: given.pop(flag) for flag, *_ in MINTING})
        if filing:
            # Before the `body` below pops it: this is the filed item's prose.
            asked.update({flag: given.pop(flag) for flag, *_ in FILING})
            asked[BODY] = _prose(asked[BODY])
        if marking:
            asked[MARKING] = given.pop(BULLET)
            asked[NOTE] = given.pop(NOTE)
        if renaming:
            asked[RETITLING] = given.pop(RETITLING)
        if recording:
            asked[RECORD] = _prose(given.pop(RECORD))
        if absorbing:
            asked[INTO] = given.pop(INTO)
        if claiming:
            asked[KEEPING] = given.pop(KEEPING)
        wrote = execute(
            declaration,
            transition,
            name=given.pop("name"),
            body=_drafted(transition, _prose(given.pop(BODY, None))),
            values={
                _key(name): _handed_back(value) for name, value in given.items()
            },
            asked=asked,
            # stderr, never stdout: a piped run carries the path and nothing else.
            announce=lambda said: click.echo(said, err=True),
            check=check,
        )
        # A check hands back its sentence rather than a path.
        # An absorbing verb hands back a tuple, one removed path per line.
        if isinstance(wrote, str):
            click.echo(wrote)
        else:
            for path in wrote if isinstance(wrote, tuple) else (wrote,):
                click.echo(named(path, declaration.root))

    return click.Command(
        name=transition.name,
        params=params,
        callback=run,
        help=transition.help,
        short_help=transition.help,
        epilog=_epilog(declaration, transition),
    )


def _handed_back(value: Any) -> Any:
    """What click gave the callback, as a head value.

    An option that repeats hands back a tuple, and an empty one where it was
    not given at all — so an empty tuple is `None`, which `execute` already
    drops, and any other tuple is the list the head will hold. Here rather
    than in a per-option callback, so no tuple can reach the codec.
    """
    if not isinstance(value, tuple):
        return value
    return list(value) or None


def _setting(transition: Transition, flag: str) -> str | None:
    """The field that makes `flag` an option of `transition`, spelled as
    `plan.toml` writes it, or `None` when no key of that name is set.

    Both lists a run takes options from: the carrier's `sets`, and the keys a
    verb that files writes onto the filed item. A verb that files refuses
    `sets` at load, so at most one of the two is ever non-empty.
    """
    if flag in transition.sets:
        return f"transitions.{transition.name}.sets"
    if flag in transition.files_sets:
        return f"transitions.{transition.name}.files.sets"
    return None


def _check_option(transition: Transition) -> click.Option:
    """Say what this verb would do to this item, and stop before the first write.

    On every generated transition, creating ones included. A `sets` key of the
    same name refuses by name.
    See docs/method.md#the-check
    """
    if (field := _setting(transition, CHECK)) is not None:
        raise Refusal(
            f'{field} names "{CHECK}", and every '
            f"transition already takes --{CHECK} for what it would do "
            "without doing it. One option cannot mean two things"
        )
    return click.Option(
        [f"--{CHECK}", CHECK],
        is_flag=True,
        help=(
            "Say what this run would do, and stop before writing anything. "
            "A refusal under --check is the refusal a real run gives."
        ),
    )


def contract(declaration: Declaration, transition: Transition) -> dict[str, Any]:
    """One verb's whole contract, as data: every block `--help` carries.

    The one home. `_epilog` renders its text out of this dict, so a block
    cannot be added to the help without going through here first — two block
    lists beside each other are two things that drift, and the text form is
    the one nothing machine-readable could catch.

    Every key is present always, empty where the verb declares nothing: the
    shape a consumer writes against must not depend on which verbs a
    declaration happens to declare. That is the listing's corpus-independence
    rule, one level up. The text form goes on omitting an empty block.
    The blocks only. A row's `options` are added by `_contents`, off the built
    command, because this runs before the command exists: `_epilog` renders
    from it while the command is being built.
    See docs/method.md#the-contract
    """
    return {
        "name": transition.name,
        "help": transition.help,
        # `from` is a Python keyword and a fine JSON key: the pair reads the
        # way `Where the item goes` says it, and `null` is a real answer on
        # each — a creating verb has no source, a dissolving one no
        # destination.
        "from": transition.source,
        "to": transition.to,
        "requires": list(transition.requires),
        # `true` where the key is refused on presence, as `plan.toml` spells it.
        "refuses": {key: list(values) for key, values in transition.refuses.items()}
        | {key: True for key in transition.refuses_any},
        "drops": list(transition.drops),
        # Not in the epilog, which names each set key in `Reading` instead.
        # Here because it is what the verb's options are, and a consumer
        # reading the contract rather than `--help` has nowhere else to get
        # them.
        "sets": list(transition.sets),
        "kind": transition.kind,
        "declares": _declared(transition),
        # The table as declared, or `null`: where the filed item goes, which
        # keys record where it came from, and under `sets` the keys this verb
        # takes as options and writes onto the filed item rather than the
        # carrier. The epilog's `Files` block says the same in a line.
        # See docs/method.md#filing
        "files": None if transition.files is None else dict(transition.files),
        "reading": _reading(declaration, transition),
    }


def _declared(transition: Transition) -> list[str]:
    """The options `transition` declares beside its kind, in `DECLARED` order."""
    return [name for name in DECLARED if getattr(transition, name)]


def _epilog(declaration: Declaration, transition: Transition) -> str:
    """The contract `--help` carries after the options.

    Where the item goes, what the verb requires, refuses and drops, its kind
    and the options it declares, where a verb that files puts the filed item
    and which keys it writes there, and the sections that hold the meaning —
    the transition's own `doc` plus the `doc` of every key it sets. A
    procedure is reached by a link from the transition's own section.

    Rendered from `contract`, which is generated from the `Transition` the
    command is generated from, and it reads the declaration rather than the
    tree, which is why it adds no fourth read. An empty block is omitted, and
    that judgment lives here: it is what a person reading help wants and what
    a consumer parsing JSON does not.
    See docs/method.md#the-contract
    """
    row = contract(declaration, transition)
    blocks = [("Where the item goes", [_going(row)])]
    if row["requires"]:
        blocks.append(("Requires", row["requires"]))
    if refused := [
        f"{key} (any value)" if values is True else f'{key} = "{value}"'
        for key, values in row["refuses"].items()
        for value in ([values] if values is True else values)
    ]:
        blocks.append(("Refuses", refused))
    # After what the verb reads off the head, and not in `Reading`: a dropped
    # key has no value to mean.
    if row["drops"]:
        blocks.append(("Drops", row["drops"]))
    blocks.append(("Declares", [row["kind"], *row["declares"]]))
    # Which head each key lands on: `sets` is the carrier's, and the keys
    # named here are the filed item's. See docs/method.md#filing
    if row["files"] is not None:
        blocks.append(("Files", [_filed(row["files"])]))
    # Absent rather than empty where nothing names a section: then the `help`
    # line is the whole procedure. See docs/method.md#the-contract
    if row["reading"]:
        blocks.append(("Reading", _named(row["reading"])))
    return "\n\n".join(
        "\b\n" + "\n".join([title, *(f"  {line}" for line in lines)])
        for title, lines in blocks
    )


def _going(row: Mapping[str, Any]) -> str:
    """Where this verb puts the item, in the four shapes a declaration has.

    The fourth is the one a reader most needs telling: a state-to-itself verb
    is an in-place write. Off the contract rather than the `Transition`, so
    the sentence and the JSON cannot describe two different moves.
    """
    source, to = row["from"], row["to"]
    if source is None:
        return f"into {to}"
    if to is None:
        return f"out of {source}, and the file is deleted"
    if source == to:
        return f"stays in {source}"
    return f"out of {source} and into {to}"


def _filed(files: Mapping[str, Any]) -> str:
    """Where a verb that files puts the filed item, and which keys it writes
    there that the caller supplies."""
    writing = files.get("sets", [])
    return f"into {files['state']}" + (
        f", writing {', '.join(writing)}" if writing else ""
    )


def _reading(declaration: Declaration, transition: Transition) -> dict[str, str]:
    """The transition's `doc`, then the `doc` of every key the caller supplies.

    The transition's is the program; a key's says what the value the caller is
    about to supply means, whichever head it lands on: the keys it `sets`, then
    those its `files` table does. A name with no `doc` is left out, so a
    transition and keys that name none have an empty `Reading`.
    """
    pointers = {
        transition.name: transition.doc,
        **{
            key: declaration.keys[key].doc
            for key in (*transition.sets, *transition.files_sets)
        },
    }
    return {name: doc for name, doc in pointers.items() if doc is not None}


def _named(pointers: Mapping[str, str]) -> list[str]:
    """A `Reading` block's lines: the names in one column, the pointers in the
    next."""
    width = max(len(name) for name in pointers)
    return [f"{name:<{width}}  {pointer}" for name, pointer in pointers.items()]


def _places(declaration: Declaration, transition: Transition) -> bool:
    """Whether giving the item a place in an order is something this run does:
    a kind that places, landing in a queued state. See docs/method.md#the-queue
    """
    return transition.kind in PLACING and declaration.states[
        str(transition.to)
    ].has(queued.NAME)


def _placement_options(transition: Transition) -> list[click.Parameter]:
    """Where in the destination state's order the item goes.

    Generated where `_places` says placing is something the run does. A `sets`
    key of the same name refuses by name.
    """
    for flag, *_ in PLACEMENT:
        if (field := _setting(transition, flag)) is not None:
            raise Refusal(
                f'{field} names "{flag}", and a '
                f"transition into a {queued.NAME} state already takes "
                f"--{flag} for where the item goes in the order. One option "
                "cannot mean two things"
            )
    return [
        click.Option([f"--{flag}", flag], metavar=metavar, type=kind, help=said)
        for flag, metavar, kind, said in PLACEMENT
    ]


def _minting_options(transition: Transition) -> list[click.Parameter]:
    """What an add-bullet takes: a sub-phase to write, or the last one.

    `_placement_options`' shape, and a `sets` key of the same name refuses by
    name. `--title` cannot collide with the positional: an add-bullet always
    has a `from`, so its positional is an item rather than a title.
    """
    for flag, *_ in MINTING:
        if (field := _setting(transition, flag)) is not None:
            raise Refusal(
                f'{field} names "{flag}", and a '
                f"transition that mints a sub-phase already takes --{flag} "
                "for what it writes into the body. One option cannot mean "
                "two things"
            )
    return [
        click.Option(
            [f"--{flag}", flag],
            metavar=metavar,
            type=kind,
            is_flag=kind is None,
            help=said,
        )
        for flag, metavar, kind, said in MINTING
    ]


def _filing_options(transition: Transition) -> list[click.Parameter]:
    """What a verb that `files` takes: a title for the item, and its prose.

    `_minting_options`' shape, and a `sets` key of the same name refuses by
    name. Neither is `required=True` here: `--title` really is optional, and
    `--body` is refused by the executor in the creating verb's own words.
    See docs/method.md#filing
    """
    for flag, *_ in FILING:
        if (field := _setting(transition, flag)) is not None:
            raise Refusal(
                f'{field} names "{flag}", and a '
                f"transition that files an item already takes --{flag} for "
                "what it writes into that item. One option cannot mean two "
                "things"
            )
    return [
        click.Option([f"--{flag}", flag], metavar=metavar, type=kind, help=said)
        for flag, metavar, kind, said in FILING
    ]


def _record_option() -> click.Option:
    """The prose a close that archives files under its entry.

    Required, and it needs no `sets` collision check: a close takes no `sets`
    in `plan.toml`. `-` reads stdin through `_prose`.
    """
    return click.Option(
        [f"--{RECORD}", RECORD],
        metavar="TEXT",
        required=True,
        help=(
            "The archive entry's prose. Required, because this command "
            "deletes the item and leaves nothing to write the entry from "
            "afterwards. `-` reads the prose from stdin, so "
            "`--record - < entry.md` takes it from a file."
        ),
    )


def _note_option(transition: Transition) -> click.Option:
    """Why a disposition disposed of the finding the way it did.

    Not required, and it needs the `sets` collision check, which the two
    options above do not. Taken as a value, and `-` is not stdin here: a note
    is one line by construction.
    """
    if (field := _setting(transition, NOTE)) is not None:
        raise Refusal(
            f'{field} names "{NOTE}", and a '
            f"transition that marks a bullet already takes --{NOTE} for why "
            "it was disposed of that way. One option cannot mean two things"
        )
    return click.Option(
        [f"--{NOTE}", NOTE],
        metavar="TEXT",
        help=(
            "Why the bullet was disposed of this way, written on the bullet "
            "beside the mark. One line, and nothing reads the note back as a "
            "field."
        ),
    )


def _keep_claims_option(transition: Transition) -> click.Option:
    """Take this claim though this session holds a claim on another item.

    A flag, and it needs the `sets` collision check. Without it the run
    refuses and names each held item. See docs/method.md#the-claimed-state
    """
    if (field := _setting(transition, KEEP_CLAIMS)) is not None:
        raise Refusal(
            f'{field} names "{KEEP_CLAIMS}", and a '
            f"transition that claims an item already takes --{KEEP_CLAIMS} to "
            "hold a second claim on purpose. One option cannot mean two things"
        )
    return click.Option(
        [f"--{KEEP_CLAIMS}", KEEPING],
        is_flag=True,
        help=(
            "Take this claim even though this session already holds a claim "
            "on another item. Without it, the run refuses and names the held "
            "items."
        ),
    )


def _into_option() -> click.Option:
    """The survivor a merge points every edge at.

    Required, and it needs no `sets` collision check. The handle resolves
    tree-wide like every other, so the work may continue as an item in any
    state.
    """
    return click.Option(
        [f"--{INTO}", INTO],
        metavar="ITEM",
        required=True,
        help=(
            "The item the work continues as. Every dependency naming the "
            "item being absorbed is pointed at ITEM instead."
        ),
    )


def _option(declaration: Declaration, key_name: str) -> click.Option:
    """The `--option` a key becomes when a transition `sets` it.

    Optional, always: a key that must be present is enforced by the next
    transition's `requires`. A cursor takes a name, so it is ordinary text. A
    list-valued key's option repeats and says so in its metavar, because click
    renders no marker of its own.
    See docs/method.md#list-valued
    """
    key = declaration.keys[key_name]
    return click.Option(
        [f"--{key_name}", _variable(key_name)],
        type=click.Choice(key.values) if key.values else None,
        multiple=key.list_valued,
        metavar=_repeated(key) if key.list_valued else None,
        help=key.help,
    )


def _repeated(key: Key) -> str:
    """What an option that may be given more than once shows in `--help`."""
    return (f"[{'|'.join(key.values)}]" if key.values else "TEXT") + "..."


def _variable(key_name: str) -> str:
    """A declared key's name as a Python identifier, prefixed so it cannot
    shadow a parameter the command owns."""
    return "key_" + key_name.replace("-", "_")


def _key(variable: str) -> str:
    return variable.removeprefix("key_").replace("_", "-")


def _prose(body: str | None) -> str | None:
    """`--body -` reads stdin, so a heredoc works."""
    return sys.stdin.read() if body == "-" else body


#: What the editor opens with for a create given no `--body`: lines starting
#: with `#` are left out of the item. See docs/method.md#idea
EDITOR_TEMPLATE = (
    "\n# Describe the new item here. Lines starting with # are left out,\n"
    "# and an empty description files nothing.\n"
)


def _drafted(transition: Transition, body: str | None) -> str | None:
    """A create's body, from `$EDITOR` when none was given and a person is at
    a terminal; otherwise the body as given, so a run with no terminal —
    an agent's, a script's — refuses exactly as before.
    See docs/method.md#idea
    """
    if body is not None or transition.source is not None or not _on_a_terminal():
        return body
    edited = click.edit(EDITOR_TEMPLATE)
    if edited is None:
        return None
    return "\n".join(
        line for line in edited.splitlines() if not line.startswith("#")
    ).strip() or None


def _on_a_terminal() -> bool:
    """Whether a person is at a terminal: stdin and stdout both are one."""
    return sys.stdin.isatty() and sys.stdout.isatty()


# --------------------------------------------------------------------------
# Writing a first declaration: the command that precedes one
# --------------------------------------------------------------------------

INIT_HELP = """Write a first plan.toml into DIRECTORY, or into this one.

Copies the example plan.toml and the archive document it names, makes the
directories it declares, and writes local/.gitignore so the tool's session
state is never committed. Rename everything in it: the states and
commands there are placeholders for your own.

`fileplan init` refuses to write over an existing plan.toml, or anywhere
under one. Discovery walks up the tree like git, so a plan.toml nested inside
another would hide it.
"""


def _version_command() -> click.Command:
    """A command carrying nothing but `_version_option`.

    click prints a version and exits from the option's own callback, so this
    exists only to give that callback somewhere to hang outside the group.
    """

    @click.command(name="fileplan", add_help_option=False)
    @_version_option()
    def show() -> None:  # pragma: no cover - the option exits before this
        """Never reached: --version is eager and exits."""

    return show


def _init_command() -> click.Command:
    """`fileplan init [DIRECTORY]`. The one command with no declaration.

    An explicit directory rather than only the working one. No `--check`: it
    is not a transition, and every refusal is already computed before the
    first write.
    See docs/method.md#init
    """

    def run(directory: str) -> None:
        for path in scaffold.install(Path(directory)):
            click.echo(path)

    return click.Command(
        name=INIT_COMMAND,
        params=[
            click.Argument(
                ["directory"],
                required=False,
                default=".",
                metavar="[DIRECTORY]",
            )
        ],
        callback=run,
        help=INIT_HELP,
        short_help="Write a first plan.toml.",
    )


# --------------------------------------------------------------------------
# Releasing a claim: the command a capability generates
# --------------------------------------------------------------------------

RELEASE_HELP = """Free the claim on ITEM.

Frees your own claim, and frees a claim left behind by a session on this host
that has stopped running. Names the session the claim was taken from.

Refuses a claim a running session holds. Refuses a claim taken on another
machine too, because this machine cannot tell whether that session is still
running. No claim is ever freed automatically.
"""


def _release_command(declaration: Declaration) -> click.Command:
    """`fileplan release ITEM`. Takes the handle and nothing else.

    No option: who holds a claim and since when are read, not typed.
    """

    def run(name: str) -> None:
        slug, record = release(declaration, name)
        # The probe again, so the line says whose claim it was in the same words.
        status = claim.alive(record, claim.identity(declaration))
        click.echo(f"released {slug}, held by {claim.describe(record, status)}")

    return click.Command(
        name=RELEASE_COMMAND,
        params=[click.Argument(["name"], metavar=ITEM)],
        callback=run,
        help=RELEASE_HELP,
        short_help="Free the claim on an item.",
    )


# --------------------------------------------------------------------------
# The read: one traversal, two renderings, filters from the declaration
# --------------------------------------------------------------------------

LIST_HELP = """List what is filed, as readable records or as JSON.

A filter narrows the listing, and several filters given together narrow it
further.

Use `--state` to name where an item is.

Use `--has` to name a key and ask something about it: `--has size=L`, or
`--has 'stale-days>=14'`, or `--has next-sub-phase` for every item carrying
the key at all. A comparison may be `>=`, `>`, `<=`, `<`, `!=` or a bare `=`.
A key with declared values compares in the order plan.toml lists them. Any
other key compares as text, or as numbers where both sides are numbers.

Use `:` for the one comparison taking several values: `--has
'pest:aphid,scab'` asks whether the key is carried and every value it carries
is one of those named.

Use `~` to find a word in a value, ignoring case: `--has 'title~review'`.
A key with declared values refuses it, since those compare by order.

Use `--lacks KEY` to find every item not carrying KEY.

States come in the order plan.toml declares them. Items within a state come
by the key the state's `sort` names, then slug, or by slug where it names
none. An item without that key comes last, and the listing names it.

Use `--sort KEY` to order the items within each state by KEY instead of any
declared sort, and `--sort -KEY` for descending. A repeat breaks the ties of the one before it,
and the slug breaks the last. KEY compares the way `--has` does. An item
without KEY comes last, and the listing names it.
"""

#: What the claim adds to the read's help, appended where a state opts in, so
#: a declaration that claims nothing is not taught a word it does not have.
CLAIM_HELP = """
A state that claims what it holds gives every row a holder. `--lacks
claimed-by` finds what nobody has picked up, `--has claim-status=dead` finds
what needs releasing, and `--has claim-holder=this-session` finds what this
session holds. A claim whose item is gone is reported beside the counts.
"""


def _list_command(declaration: Declaration) -> click.Command:
    """`fileplan list`: the one read, with its filters generated from the keys.

    Not a declared transition: it moves nothing, writes nothing and takes no
    lock. Its parameters and its whole body are `_read_params` and
    `_read_run`, which `show` calls too.
    See docs/method.md#the-listing
    """
    return click.Command(
        name=LIST_COMMAND,
        params=_read_params(declaration),
        callback=_read_run(declaration, LIST_KIND),
        help=LIST_HELP + (CLAIM_HELP if declaration.has(claim.NAME) else ""),
        short_help="List what is filed.",
    )


def _read_params(declaration: Declaration) -> list[click.Parameter]:
    """Everything a read takes: the filters, and how to render what is left.

    Built fresh per command, because two commands sharing one
    `click.Parameter` object is a shared mutable nobody asked for.
    """
    carried = declaration.carried
    return [
        # Repeatable only so a repeat can be refused by name, in `_tests`:
        # click would otherwise keep the last one and drop the rest.
        click.Option(
            ["--state"],
            metavar="[OP]STATE",
            multiple=True,
            help=(
                "Only items in this state. One of: "
                f"{', '.join(declaration.states)}."
            ),
        ),
        click.Option(
            ["--has", "has"],
            metavar="KEY[OP]VALUE",
            multiple=True,
            help=(
                "Only items whose KEY answers the comparison. Without a "
                "comparison, every item carrying KEY. One of: "
                f"{', '.join(carried)}."
            ),
        ),
        click.Option(
            ["--lacks", "lacks"],
            metavar="KEY",
            multiple=True,
            help="Only items not carrying KEY.",
        ),
        click.Option(
            ["--sort", "sort"],
            metavar="[-]KEY",
            multiple=True,
            help=(
                "Order the items within each state by KEY, and `-KEY` for "
                "descending. A repeat breaks the ties of the one before it. "
                "KEY is one --has names."
            ),
        ),
        _json_option(),
    ]


def _json_option() -> click.Option:
    """The one flag every read carries, spelled once."""
    return click.Option(
        ["--json", "as_json"],
        is_flag=True,
        help="Print one JSON object on one line, for a program rather than a person.",
    )


def _read_run(
    declaration: Declaration,
    kind: str,
    *,
    naming: str | None = None,
    bulleting: str | None = None,
    **meta: Any,
) -> Callable[..., None]:
    """One read's whole body: traverse, filter, render, frame.

    `list` and `show` call this, so there is one traversal and one call to
    each renderer. `meta` is what the envelope says about which read this is.

    `naming` is `show`'s narrowing: the parameter holding a handle, resolved
    against the rows this traversal already found, applied after the walk so
    `show` stays one traversal. `bulleting` mirrors it one level in, narrowing
    to one bullet of that item; given neither, nothing changes. A read that
    names its item takes no filters.
    See docs/method.md#show
    """

    def run(**given: Any) -> None:
        as_json = given.pop("as_json")
        handle = given.pop(naming) if naming else None
        wanted = given.pop(bulleting) if bulleting else None
        tests = [] if naming else _tests(declaration, given)
        sorts = _sorts(declaration, given.pop("sort", ()))
        # `--sort` replaces every state's declared sort, and a read naming one
        # item has nothing to sort.
        by_state = (
            {}
            if naming
            else {
                name: sorts or [read.sorting(declaration, state.sort)]
                for name, state in declaration.states.items()
                if sorts or state.sort
            }
        )
        found = read.listing(
            declaration,
            taking=lambda one, walked: commands(declaration, one, walked),
        )
        if handle is not None:
            named = [(row[read.SLUG], row[read.PATH]) for row in found.rows]
            carrying = {
                str(row[numbered.KEY]): row[read.SLUG]
                for row in found.rows
                if row.get(numbered.KEY) is not None
            }
            # Only `show` reads a number; a verb that writes stays on slugs.
            hit = read.numbered_handle(named, handle, carrying)
            if hit is None:
                slug = read.chosen(named, handle, carrying)
            else:
                slug, sub_phase = hit
                if sub_phase is not None and wanted not in (None, sub_phase):
                    raise Refusal(
                        f"{handle} and {wanted} name two sub-phases, and show "
                        "prints one: say which"
                    )
                wanted = sub_phase or wanted
            found = dataclasses.replace(
                found, rows=[row for row in found.rows if row[read.SLUG] == slug]
            )
        chosen = read.matching(found.rows, tests)
        unsorted: list[dict[str, Any]] = []
        if by_state:
            chosen, unsorted = read.ordered(
                chosen, by_state, tuple(declaration.states)
            )
        # The one narrowing that changes what a row is: after the handle's, and
        # before the renderers.
        reading, verbatim = kind, None
        if wanted is not None:
            record, verbatim = _one_bullet(declaration, chosen[0], wanted)
            chosen, reading = [record], BULLET_KIND
        # Each report wherever the declaration could fill it, empty or not, so
        # the shape does not depend on the corpus. They are about the tree, so
        # they reach `show` too.
        beside = {
            field: getattr(found, field)
            for field, gate in read.REPORTS
            if gate(declaration)
        }
        # And the unsorted report, whenever the read sorts anything: the shape
        # follows the invocation and the declaration, never the corpus.
        if by_state:
            beside["unsorted"] = unsorted
        if as_json:
            # stderr stays silent: the counts live in the envelope instead.
            click.echo(
                render.document(
                    reading,
                    chosen,
                    **meta,
                    matched=len(chosen),
                    # What the traversal read, not what it offered.
                    read=found.walked,
                    **beside,
                ),
                nl=False,
            )
            return

        printed = (
            verbatim.splitlines()
            if verbatim is not None
            else render.records(chosen, heading=render.HEADING)
        )
        for line in printed:
            click.echo(line)
        # The frame goes to stderr, never stdout, and so does every exception
        # report: they are about the tree rather than rows of it.
        click.echo(
            f"\nshowing {len(chosen)} of {found.walked} {LIST_KIND}", err=True
        )
        # An empty tree says how to file the first item, so a newcomer's first
        # listing names a command rather than a count. See docs/method.md#the-listing
        if not found.walked and handle is None:
            for said in _first_item(declaration):
                click.echo(said, err=True)
        for field, _ in read.REPORTS:
            said = REPORT_LINES[field]
            for one in getattr(found, field) if said else ():
                click.echo(said(one), err=True)
        for one in unsorted:
            click.echo(
                f"unsorted: {one[read.SLUG]} carries no {one[read.KEY]}, so it "
                f"comes last ({one[read.PATH]})",
                err=True,
            )

    return run


def _stranded(one: Mapping[str, Any]) -> str:
    """One stranded claim, as the text form's exception line.

    Named, never removed: it is a leftover a person resolves.
    """
    return (
        f"stranded claim: {one[read.SLUG]}, held by {one[claim.BY]} "
        f"({one[claim.STATUS]}). No item in a claimed state answers to that "
        f"slug, so remove the claim with `rm {one[read.PATH]}`"
    )


def _unknown(one: Mapping[str, Any]) -> str:
    """One edge naming nothing filed, as the text form's exception line.

    Named rather than read as satisfied. See docs/method.md#dependencies
    """
    return (
        f"unknown dependency: {one[depends.SLUG]} names "
        f'"{one[depends.NAMES]}" in {one[depends.KEY]}, and no item carries '
        "that slug"
    )


def _unfound(one: Mapping[str, Any]) -> str:
    """One filed item naming a bullet its carrier no longer has.

    See docs/method.md#carried
    """
    return (
        f"unfound finding: {one[read.PATH]} carries \"{one[read.VALUE]}\" from "
        f"{one[read.CARRIER]}, and no bullet there is named {one[read.VALUE]}"
    )


def _misordered(one: Mapping[str, Any]) -> str:
    """One edge pointing later in the order, as the text form's exception line.

    Named, never reordered: a place is what sorts and an edge is what reports.
    """
    return (
        f"misordered dependency: {one[depends.SLUG]} at place "
        f"{one[depends.PLACE]} waits on {one[depends.NAMES]} at place "
        f"{one[depends.NAMED_PLACE]}. An item cannot wait on something later "
        "in the order"
    )


def _gap(one: Mapping[str, Any]) -> str:
    """One missing number, as the text form's exception line.

    Named in the default read rather than only refusing at the next mint, and
    a state is named by its declared name rather than its directory.
    See docs/method.md#the-register
    """
    return (
        f"register gap: {numbered.KEY} {one[numbered.KEY]} is missing from "
        f"{one[numbered.STATE]} and from {one[numbered.ARCHIVE]}, so nothing "
        f"says what happened to the item that carried {numbered.KEY} "
        f"{one[numbered.KEY]}"
    )


def _lost(one: Mapping[str, Any]) -> str:
    """One heading the register cannot read, as the text form's exception line.

    Reported here and refused at the mint. A second report rather than a gap,
    because a lost close-out at the top of the range produces no gap.
    """
    return (
        f"lost close-out: {one[numbered.ARCHIVE]}:{one[numbered.LINE]} "
        f"`{one[numbered.TEXT]}` is not a heading the {numbered.NAME} "
        "register can read, so the number that heading names is free to be "
        "minted again"
    )


def _undecomposed(slug: str) -> str:
    """One started section carrying no sub-phases, as a line of the frame."""
    return f"started but not decomposed: {slug} carries no sub-phases"


def _undeclared(one: Mapping[str, Any]) -> str:
    """One head value its key's `values` do not declare, as a line."""
    return (
        f"undeclared value: {one[read.SLUG]} carries "
        f'"{one[read.VALUE]}" in {one[read.KEY]}, which its values '
        f"do not declare ({one[read.PATH]})"
    )


def _first_item(declaration: Declaration) -> list[str]:
    """What an empty tree's listing says to do: one line per create, in
    declared order, or nothing where the declaration creates nothing."""
    return [
        f"Nothing is filed. `fileplan {one.name} {TITLE} --{BODY} TEXT` files "
        f"one in {one.to}."
        for one in declaration.transitions.values()
        if one.source is None
    ]


def _unmarkable(one: Mapping[str, Any]) -> str:
    """One bullet no mark could be read on, as the text form's exception line.

    Reported here and refused at the verb, `_gap`'s arrangement: the two
    share the reader rather than the sentence. Named before a session reaches
    for the verb, which is what the offer passing it over would otherwise
    hide. See docs/method.md#marking
    """
    return (
        f"unmarkable bullet: {one[read.BULLET_NAME]} in {one[read.BULLET_ITEM]} "
        f"({one[read.PATH]}:{one[read.BULLET_LINE]}) "
        f'carries "{one[read.BULLET_REST]}" after its bold run, so nothing '
        "can mark that bullet. Move the prose inside the bold run, or onto a "
        "continuation line under the bullet"
    )


def _unread(one: Mapping[str, Any]) -> str:
    """One bullet the reader passed over, as the text form's exception line.

    `_unmarkable`'s form. See docs/method.md#sub-phases
    """
    name = one[read.BULLET_NAME]
    return (
        f"unread bullet: {name or 'a bullet'} in {one[read.BULLET_ITEM]} "
        f"({one[read.PATH]}:{one[read.BULLET_LINE]}) is not read as a "
        f"sub-phase: {one[read.BULLET_REASON]}"
    )



#: The text line each of `read.REPORTS` prints per record, or `None` for the
#: register, which the text form leaves to `--json`. Keyed by every report,
#: so a report with no line here fails the first listing that reads it.
REPORT_LINES: Mapping[str, Callable[[Any], str] | None] = {
    "stranded": _stranded,
    "undecomposed": _undecomposed,
    "unknown": _unknown,
    "misordered": _misordered,
    "gaps": _gap,
    "lost": _lost,
    "register": None,
    "unmarkable": _unmarkable,
    "unread": _unread,
    "undeclared": _undeclared,
    "unfound": _unfound,
}


def _tests(declaration: Declaration, given: dict[str, Any]) -> list[read.Test]:
    """Whatever was asked for, as tests.

    The parse is where a bad filter refuses, so it happens before the walk.
    """
    tests = []
    states = given.pop("state")
    if len(states) > 1:
        raise Refusal(
            f"--state was given {len(states)} times ({', '.join(states)}), and "
            "it takes one comparison. Keeping the last would drop the others "
            "without saying so"
        )
    if (state := next(iter(states), None)) is not None:
        # A state name is a closed set like any key's `values`. It is the one
        # filter that is not a key: it says where an item is.
        tests.append(read.comparison("state", state, tuple(declaration.states)))
    for asked in given.pop("has"):
        tests.append(read.filtering(declaration, asked))
    for key in given.pop("lacks"):
        key = read.known(declaration, "--lacks", key)
        tests.append(read.presence(key, carried=False))
    return tests


def _sorts(declaration: Declaration, given: tuple[str, ...]) -> list[read.Sort]:
    """Every `--sort`, parsed before the walk, or refuse.

    A key sorted twice refuses, as a repeated `--state` does: keeping one
    would drop the other without saying so.
    """
    sorts = [read.sorting(declaration, one) for one in given]
    keys = [one.key for one in sorts]
    if twice := next((key for key in keys if keys.count(key) > 1), None):
        raise Refusal(
            f"--sort names {twice} {keys.count(twice)} times, and a key sorts "
            "one way. Keeping one would drop the others without saying so"
        )
    return sorts


# --------------------------------------------------------------------------
# The read of one item: the same traversal, narrowed by a handle
# --------------------------------------------------------------------------

def _one_bullet(
    declaration: Declaration,
    row: Mapping[str, Any],
    wanted: str,
) -> tuple[dict[str, Any], str]:
    """One bullet of `row`'s item: what a consumer gets, and what a person reads.

    Two refusals, both before anything is rendered: a state that counts no
    sub-phases refuses by name, and a name the body has not got refuses
    through `subphase.unknown`, the disposition's own sentence. The record is
    not a row, because putting a body in a row would put it in every listing.
    See docs/method.md#show
    """
    one = item.read(declaration.root / row[read.PATH], declaration)
    if one.state.sub_phases is None:
        raise Refusal(
            f"{row[read.PATH]} is in {one.state.name}, which counts no "
            f"{subphase.NAME} — so it carries no bullet a name could point at"
        )
    carried = subphase.bullets(
        one.body,
        one.state.sub_phases,
        pending=one.state.pending,
        marks=one.state.marks,
    )
    found = next((each for each in carried if each.name == wanted), None)
    if found is None:
        raise Refusal(
            subphase.unknown(row[read.PATH], wanted, carried, one.state.sub_phases)
        )
    # `bullets` found it, so `_counted` did: the two read one body by one rule.
    verbatim = subphase.text(one.body, one.state.sub_phases, name=wanted)
    assert verbatim is not None
    return {
        read.BULLET_NAME: found.name,
        read.BULLET_ITEM: row[read.SLUG],
        read.BULLET_TITLE: found.title,
        read.BULLET_MARK: found.mark,
        BULLET_TEXT: verbatim,
    }, verbatim


SHOW_HELP = """The listing's row for one item.

ITEM is a unique prefix of a slug, resolved over the whole tree. A full slug
always names itself. An ambiguous prefix refuses, naming its candidates, and
a prefix matching nothing refuses, naming its near misses. Where no slug
starts with it, ITEM may be a live section's number, such as 28, or a
sub-phase name, such as 28-1, which shows that bullet.

Show prints the **row**, not the body. `cat` the path the row names to read
the prose. The row carries what the file does not: who holds the item, what
it waits on, and how long ago git last saw it.

Give NAME as well and show prints one **bullet** of the item's body,
verbatim, with the lines under it and nothing else. A name the body has not
got refuses, saying which names the body carries.

The counts and every exception report cover the whole tree, because they are
reports about the tree rather than rows of it.
"""


def _show_command(declaration: Declaration) -> click.Command:
    """`fileplan show ITEM [NAME]`: the read again, narrowed by a handle.

    Registered unconditionally, unlike `release`: reading one item is not a
    capability anything opts into. Its whole body is `_read_run` with `naming`
    set, and `bulleting` is the second positional every disposition takes.
    See docs/method.md#show
    """
    return click.Command(
        name=SHOW_COMMAND,
        params=[
            click.Argument(["name"], metavar=ITEM),
            # The disposition's own second positional, spelled by its own two
            # constants. The brackets are click's own for an optional one.
            click.Argument(
                [BULLET], metavar=f"[{MARKING_METAVAR}]", required=False
            ),
            _json_option(),
        ],
        callback=_read_run(declaration, SHOW_KIND, naming="name", bulleting=BULLET),
        help=SHOW_HELP,
        short_help="The listing's row for one item.",
    )


# --------------------------------------------------------------------------
# The table of contents
# --------------------------------------------------------------------------


def _contents(
    declaration: Declaration, group: click.Command, as_json: bool = False
) -> None:
    """What this workflow is: its states, then its verbs, in declared order.

    Both are read off `plan.toml`. A third block indexes each verb's kind and
    the options it declares, so a session composing several runs can ask
    which verb is which kind in one read.

    `--json` is the second rendering, and it carries every verb's whole
    contract rather than the kinds alone: a consumer asking which verb is an
    edit usually has to read `Reading` to tell two of them apart.
    The states ride in the envelope, as the text prints them — what a
    declaration says about its own states is in the consumer's `plan.toml`
    already, and what only the tool knows is what it derives from it.

    Each row's `options`, and the tool's own `commands`, are read off the
    built `group` rather than the declaration: the same parameters `--help`
    renders, so the two cannot drift.
    See docs/method.md#the-interpreter and docs/method.md#the-contract
    """
    if as_json:
        assert isinstance(group, click.Group)
        click.echo(
            render.document(
                DECLARATION_KIND,
                [
                    contract(declaration, one)
                    | {"options": _options(group.commands[one.name])}
                    for one in declaration.transitions.values()
                ],
                source=str(declaration.source),
                states=[
                    {"name": state.name, "path": state.path, "sort": state.sort}
                    for state in declaration.states.values()
                ],
                keys=[
                    {
                        "name": key.name,
                        "help": key.help,
                        "doc": key.doc,
                        "values": None if key.values is None else list(key.values),
                    }
                    for key in declaration.keys.values()
                ],
                commands=[
                    _described(command)
                    for name, command in group.commands.items()
                    if name not in declaration.transitions
                ],
            ),
            nl=False,
        )
        return

    click.echo(f"{declaration.source}\n")
    width = max(
        (len(name) for name in (*declaration.states, *declaration.transitions)),
        default=0,
    )

    click.echo("States")
    places = max((len(state.path) for state in declaration.states.values()), default=0)
    for state in declaration.states.values():
        # The sort, declared or defaulted, so a default is never hidden.
        sorting = f"  sorted by {state.sort}" if state.sort else ""
        click.echo(
            f"  {state.name:<{width}}  {state.path + '/':<{places + 1}}{sorting}".rstrip()
        )

    if declaration.transitions:
        click.echo("\nTransitions")
        for transition in declaration.transitions.values():
            click.echo(f"  {transition.name:<{width}}  {transition.help}")

    # Its own block rather than a fourth column: a column after the `help` lines
    # wraps into prose nobody can read a kind out of.
    if declaration.transitions:
        click.echo("\nDeclares")
        for transition in declaration.transitions.values():
            said = ", ".join([transition.kind, *_declared(transition)])
            click.echo(f"  {transition.name:<{width}}  {said}")

    click.echo(
        f"\nRun `fileplan {LIST_COMMAND}` to see what is filed.\n"
        f"Run `fileplan {SHOW_COMMAND} ITEM` to see one item's row.\n"
        "Run `fileplan COMMAND --help` to see what COMMAND takes."
    )


def _described(command: click.Command) -> dict[str, Any]:
    """One of the tool's own commands as the contract gives it, nested the
    way click holds it. None of the tool's own nests another today, so each
    `commands` is empty, and the field stays so the shape does not depend on
    that."""
    return {
        "name": command.name,
        "help": command.short_help or command.help,
        "options": _options(command),
        "commands": [
            _described(one) for one in command.commands.values()
        ]
        if isinstance(command, click.Group)
        else [],
    }


def _options(command: click.Command) -> list[dict[str, Any]]:
    """Every option `command --help` prints, `--help` itself aside, as data."""
    context = click.Context(command)
    return [
        {
            "name": param.opts[0],
            "takes": None if param.is_flag else param.make_metavar(context),
            "required": param.required,
            "multiple": param.multiple,
            "values": list(param.type.choices)
            if isinstance(param.type, click.Choice)
            else None,
            "help": param.help,
        }
        for param in command.params
        if isinstance(param, click.Option)
    ]


def _refuse(refusal: Refusal) -> int:
    """`ERROR:` on stderr, nothing on stdout, no traceback.

    The first message goes on the `ERROR:` line and each further one on an
    indented line of its own, so a plan.toml with four defects reads as four
    lines. Whitespace is collapsed per message. `Refusal`'s own `str` keeps
    its one-line join for in-process callers.
    """
    first, *rest = [" ".join(one.split()) for one in refusal.messages] or [""]
    click.echo(f"ERROR: {first}", err=True)
    for one in rest:
        click.echo(f"  {one}", err=True)
    return 2


if __name__ == "__main__":
    console_main()
