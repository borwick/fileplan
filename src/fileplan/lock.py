"""The run lock: one exclusive `flock` around every mutating transition.

Every mutating transition holds the lock, including a transition that creates
an item. `open(..., "x")` reserves one filename, not the tree-wide uniqueness
check. The uniqueness check is a check-then-act across other states, and
`open(..., "x")` stays as the backstop.

Contention is announced once, because a silent wait reads as a hang. The run
tries without blocking, writes one line to stderr naming the holder, then
acquires and waits. The holder line carries the host as well as the pid. A pid
means nothing on another machine.

See docs/method.md#the-lock
"""

from __future__ import annotations

import fcntl
import os
import socket
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import click

#: Session-local state, gitignored: the lock, and the claims beside it.
LOCAL_DIR = "local"

LOCK_NAME = ".plan.lock"


@contextmanager
def run_lock(root: Path) -> Iterator[None]:
    """Hold `local/.plan.lock` exclusively for the duration of the block.

    Released however the block leaves — return, refusal or crash — because the
    lock lives on the open file description and the `with` closes it.
    """
    path = root / LOCAL_DIR / LOCK_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            click.echo(f"waiting for {path}, held by {_holder(path)}", err=True)
            fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            _write(handle, f"{describe_session()}\n")
            yield
        finally:
            # Cleared rather than left behind, so a later contention
            # report cannot name a holder that has already gone.
            _write(handle, "")
            fcntl.flock(handle, fcntl.LOCK_UN)


def describe_session() -> str:
    """Who this process is, for a holder line: host and pid.

    `os.getpid()` rather than the session identity a claim records, and the
    two do not share a home (John, 2026-09-02): this names the process holding
    the flock, alive for the run, where `fileplan.claim.identity` names the
    session. Two questions with two answers, not drift.
    """
    return f"{socket.gethostname()} pid {os.getpid()}"


def _holder(path: Path) -> str:
    """The holder's line, best effort: it is an announcement, not a decision."""
    try:
        line = path.read_text(encoding="utf-8").strip()
    except OSError:
        line = ""
    return line or "another run"


def _write(handle, text: str) -> None:
    handle.seek(0)
    handle.truncate()
    handle.write(text)
    handle.flush()
