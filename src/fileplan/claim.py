"""Claims: which session holds an item, and whether that session is still there.

A claim is a state change that lasts a session, and a second session can see
it. A claim is a file, and the file outlives the process that wrote it. The
run lock is the opposite, because the kernel releases the lock when the
process goes.

Nothing reclaims a claim automatically, and nothing tries to. A claim probed as dead
is named in the listing and waits for a person. So does a claim taken on a
host this one cannot reach.

Who a session is comes from plan.toml's `[identity]`, an ordered list of
environment variable names. The first name that is set wins. `identity` is the
only place in the tool that reads the environment. The identity is a host and
a pid, with no session id, so a reused pid can make a dead session's claim
look live.

Pure but for `read`, `write`, `remove`, and `identity`.

See examples/docs/reference.md#the-claim
"""

from __future__ import annotations

import datetime as dt
import os
import socket
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import fields as declared
from pathlib import Path
from typing import Any

from fileplan import item
from fileplan.declaration import (
    CLAIM_KEYS,
    CLAIMED,
    Declaration,
    Refusal,
    collecting,
    named,
    whole,
)
from fileplan.lock import LOCAL_DIR, holder

#: The capability a state opts into. The seam that takes, holds and drops a
#: claim is `fileplan.transition`, because it mutates under the lock and this
#: module takes none. See examples/docs/reference.md#the-claimed-state
NAME = CLAIMED

#: Under `local/`, beside the lock: session-local state, gitignored.
CLAIMS_DIR = "claims"

#: Plain `.toml`, unfenced: a `+++` line is not valid TOML, and a record a
#: person cats should be something they can parse.
SUFFIX = ".toml"


@dataclass(frozen=True)
class Claim:
    """One claim record: who holds an item, and since when.

    Its fields in on-disk order. The item's slug is not here: the record's
    location answers that already, and a second answer could disagree.
    """

    host: str
    pid: int | None = None
    #: Not graded: a record whose stamp is not a datetime reads, and
    #: grading it would refuse records the on-disk format already holds.
    taken: Any = None


#: What a record holds, in canonical order, read off `Claim`.
FIELDS = tuple(one.name for one in declared(Claim))

#: The outcomes of the probe. `ELSEWHERE` and `UNKNOWN` are not "maybe dead"
#: but the tool not knowing, and they end where `DEAD` ends: named, never
#: auto-released.
ALIVE = "alive"
DEAD = "dead"
ELSEWHERE = "elsewhere"
UNKNOWN = "unknown"

#: The outcomes as a closed set: what a row's status field may hold, and what a
#: filter over the key grades against, so `--has claim-status=zzz` refuses by
#: name. Ordered alive-first, the order a person reads them in.
STATUSES = (ALIVE, DEAD, ELSEWHERE, UNKNOWN)

#: Whether the session reading a row is the one holding its claim, decided by
#: `owns`: the same rule the claiming run refuses by, so a pid is compared as a
#: whole number and a record from another host is never this session's.
THIS_SESSION = "this-session"
ANOTHER_SESSION = "another-session"

#: The holders as a closed set, so `--has claim-holder=mine` refuses by name.
HOLDERS = (THIS_SESSION, ANOTHER_SESSION)

#: The fields a claim gives a row, unpacked so nothing below spells one
#: as a literal. Their one home is `fileplan.declaration.CLAIM_KEYS`, where a
#: redeclaration of any of them is refused.
BY, STATUS, HOLDER = CLAIM_KEYS


@dataclass(frozen=True)
class Identity:
    """Who a session is: the machine, and the process on it.

    `pid` is `None` when no declared variable is set — a person at a shell,
    say. That is a usable identity rather than an error: it owns its own
    claims on its own host, and the probe reports `UNKNOWN` for them.
    """

    host: str
    pid: int | None = None


def identity(declaration: Declaration) -> Identity:
    """This session's identity, per `[identity]`, or raise `Refusal`.

    The first declared name that is set supplies the pid, and one set to
    something that is not a positive whole number refuses by name rather than
    falling through: a silent fallback would record an identity the operator
    did not choose and cannot see.
    """
    host = socket.gethostname()
    for name in declaration.pid_names:
        value = os.environ.get(name)
        if value is None:
            continue
        return Identity(host=host, pid=_pid(name, value))
    return Identity(host=host)


def _pid(name: str, value: str) -> int:
    if value.isascii() and value.isdigit() and int(value) > 0:
        return int(value)
    raise Refusal(
        f'{name} is set to "{value}", which is not a pid. A session\'s pid is '
        "a positive whole number, and it is what the liveness probe asks the "
        "kernel about — text recorded in its place would probe nothing"
    )


def path(root: Path, slug: str) -> Path:
    """Where `slug`'s claim lives: `local/claims/<slug>.toml` under `root`."""
    return root / LOCAL_DIR / CLAIMS_DIR / f"{slug}{SUFFIX}"


def record(identity: Identity, *, taken: dt.datetime) -> Claim:
    """The claim `identity` takes at `taken`. Pure.

    `taken` must be aware: a record is read on machines other than the one
    that wrote it, and a naive stamp means whatever the reader's clock means.
    """
    if taken.tzinfo is None or taken.tzinfo.utcoffset(taken) is None:
        raise Refusal(
            "a claim is taken at an aware datetime, not a naive one. The "
            "record is read on other machines — this tree is shared — and a "
            "stamp with no offset means a different moment on each of them"
        )
    return Claim(host=identity.host, pid=identity.pid, taken=taken)


def owns(record: Claim, identity: Identity) -> bool:
    """Whether `identity` is the session that holds `record`.

    A record carrying no pid is owned by any identity on its host, which lets
    a person at a shell complete a claim they took at that same shell. This is
    the question; the executor is the refusal.
    """
    if record.host != identity.host:
        return False
    return record.pid is None or record.pid == identity.pid


def alive(record: Claim, identity: Identity) -> str:
    """One of `ALIVE`, `DEAD`, `ELSEWHERE`, `UNKNOWN`.

    Host-gated, and the gate is load-bearing: `os.kill(pid, 0)` asks this
    kernel about its own process table, so on a record from another machine it
    would answer about whatever local process wears that number. It is never
    called for another host. `PermissionError` is `ALIVE` — the process
    exists, it is simply not ours to signal.
    """
    if record.host != identity.host:
        return ELSEWHERE

    if record.pid is None:
        return UNKNOWN

    try:
        os.kill(record.pid, 0)
    except ProcessLookupError:
        return DEAD
    except PermissionError:
        return ALIVE
    return ALIVE


#: What each of the probe's answers says about a holder, in the phrase a
#: refusal carries.
SAID = {
    ALIVE: "running",
    DEAD: "not running",
    ELSEWHERE: "another machine, which this one cannot probe",
    UNKNOWN: "no pid on the record, so there is nothing to probe",
}


def _holder(record: Claim) -> str:
    """Who holds a claim: `a-host.local pid 4213`, or `a-host.local` alone.

    The one home for a holder's name, so the listing and the refusals cannot
    name one session two ways.
    """
    if record.pid is None:
        return record.host
    return holder(record.host, record.pid)


def describe(record: Claim, status: str) -> str:
    """A holder, as a phrase: `host pid 4213 (not running), taken <when>`.

    The English of a refusal, built on `_holder` so the sentence and the row
    agree about who. A row carries values rather than sentences, which is why
    the listing takes `fields` instead.
    """
    return f"{_holder(record)} ({SAID.get(status, status)}), taken {_when(record)}"


def fields(record: Claim, status: str, who: Identity) -> dict[str, str]:
    """The values a claim gives a row: its holder, the probe's word, and
    whether `who` is that holder, by `owns`.

    Pure, and not a sentence: `claim-status` holds one of `STATUSES` and
    `claim-holder` one of `HOLDERS`, so each filters like any declared key with
    `values`. See examples/docs/reference.md#the-claim
    """
    return {
        BY: _holder(record),
        STATUS: status,
        HOLDER: THIS_SESSION if owns(record, who) else ANOTHER_SESSION,
    }


def _when(record: Claim) -> str:
    """When the claim was taken, spelled the way the record on disk spells it.

    `str(datetime)` separates the date and the time with a space where TOML
    writes a `T`, and the phrase should agree with the file.
    """
    taken = record.taken
    if isinstance(taken, dt.datetime):
        return taken.isoformat()
    return "at no recorded time" if taken is None else str(taken)


def errors(record: Mapping[str, Any]) -> list[str]:
    """Every way `record` is not a claim record. Pure, and collected at once.

    `fileplan.declaration.shape_errors`' shape: one pass, every defect named,
    so a hand-edited record is fixed in one sitting.
    """
    found = [
        f'"{name}" is not a claim record field (a record holds: {", ".join(FIELDS)})'
        for name in record
        if name not in FIELDS
    ]

    if "host" not in record:
        found.append(
            "a claim record has no host, and without one its pid means "
            "nothing — this tree is shared, and a pid is only a pid on the "
            "machine that wrote it"
        )
    elif not isinstance(record["host"], str):
        found.append(f"host holds {record['host']!r}, which is not a host name")

    pid = record.get("pid")
    if pid is not None and not _is_pid(pid):
        found.append(
            f"pid holds {pid!r}, which is not a pid. It is written as a bare "
            "positive integer, because it is what the liveness probe asks "
            "the kernel about"
        )
    return found


def _is_pid(value: Any) -> bool:
    """Whether `value` is a pid: a positive whole number."""
    return whole(value) and value > 0


# --------------------------------------------------------------------------
# The filesystem: the edges
# --------------------------------------------------------------------------


def read(path: str | os.PathLike[str], root: Path) -> Claim:
    """One claim record, parsed and graded by `errors`, or raise `Refusal`
    naming every defect. `root` is what a refusal names the record from."""
    path = Path(path)
    text = item.read_text(path, root, "a claim record")
    try:
        parsed = item.flat(text, noun="claim record")
    except Refusal as refusal:
        raise Refusal([_not_usable(path, root), *refusal.messages]) from None
    if problems := errors(parsed):
        raise Refusal([_not_usable(path, root), *problems])
    return Claim(**parsed)


def _not_usable(path: Path, root: Path) -> str:
    return item.not_usable(path, root, "claim record")


def write(path: str | os.PathLike[str], held: Claim) -> None:
    """Put `held` in place of `path`, atomically, making `local/claims/`.

    `fileplan.item.replace` does the writing, so a second session sees either
    the whole old record or the whole new one. A field that is `None` is left
    out, so a record with no pid carries no pid line.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    written = {
        name: getattr(held, name) for name in FIELDS if getattr(held, name) is not None
    }
    item.replace(path, item.table(written, noun="claim record"))


def holders(declaration: Declaration) -> dict[str, dict[str, str]]:
    """Every claim in the tree, as slug → `fields`, or raise `Refusal`.

    The edge the listing reads a claim through: one glob of
    `local/claims/*.toml`, the slug taken from each stem, and each record
    graded and probed once. Whether a claim belongs to an item is
    `fileplan.read.listing`'s question, not this one's.

    Every defect is collected and raised at once. A malformed record refuses
    the listing, where a missing one reads as unclaimed: a fresh clone has no
    records, and a record that cannot be read says something the tool does
    not understand about who holds an item. See
    examples/docs/reference.md#the-claimed-state
    """
    who = identity(declaration)
    return {
        slug: fields(held, alive(held, who), who)
        for slug, held in _records(declaration).items()
    }


def mine(declaration: Declaration, who: Identity) -> list[str]:
    """The slugs of every record `who` owns, sorted, or raise `Refusal`.

    Ownership is `owns`, so a record with no pid on this host counts. Whether
    each slug is an item in a claimed state is the caller's question, as it is
    for `holders`. See examples/docs/reference.md#the-claimed-state
    """
    return [slug for slug, held in _records(declaration).items() if owns(held, who)]


def _records(declaration: Declaration) -> dict[str, Claim]:
    """Every record under `local/claims/`, by slug and graded, or raise
    `Refusal` naming every defect at once."""
    directory = Path(declaration.root) / LOCAL_DIR / CLAIMS_DIR
    defects: list[str] = []
    paths = sorted(directory.glob(f"*{SUFFIX}"), key=lambda one: one.stem)
    root = Path(declaration.root)
    found = {
        path.stem: held
        for path, held in collecting(lambda one: read(one, root), paths, defects)
    }
    if defects:
        raise Refusal(defects)
    return found


def remove(path: str | os.PathLike[str], root: Path) -> None:
    """Free the claim at `path`. The other edge, beside `read`, and named from
    `root` the same way.

    A record that is not there is already gone: a claim dropped twice leaves
    the same tree either way, and a missing record means unclaimed everywhere
    else too.
    """
    path = Path(path)
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise Refusal(
            f"{named(path, root)} could not be removed: {exc.strerror}"
        ) from None
