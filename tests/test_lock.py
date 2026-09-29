"""The run lock: held, contended, and released however the block leaves.

Contention needs two processes. ``flock`` is held on the *open file
description*, so a second acquisition inside this process would either
succeed (same description) or deadlock (a second one) — neither of which is
what a second session does. Both probes below therefore run in a subprocess.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from conftest import FIXTURE_FILES

from fileplan import item
from fileplan.declaration import Declaration, Refusal, load
from fileplan.lock import LOCK_NAME, LOCAL_DIR, run_lock
from fileplan.transition import execute

FIXTURES = Path(__file__).resolve().parent / "fixtures"

#: Report whether the lock is held, without waiting for it.
PROBE = """
import fcntl, sys
handle = open(sys.argv[1], "a+")
try:
    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    sys.exit(1)
sys.exit(0)
"""

#: Take the lock, stamp a holder line, announce, then hold it briefly.
HOLD = """
import fcntl, sys, time
handle = open(sys.argv[1], "a+")
fcntl.flock(handle, fcntl.LOCK_EX)
handle.seek(0); handle.truncate()
handle.write("another-host pid 999, session abc\\n"); handle.flush()
print("held", flush=True)
time.sleep(float(sys.argv[2]))
"""


@pytest.fixture
def tree(tmp_path: Path) -> Declaration:
    for name in FIXTURE_FILES:
        (tmp_path / name).write_text((FIXTURES / name).read_text())
    declaration = load(tmp_path / "plan.toml")
    for state in declaration.states.values():
        (tmp_path / state.path).mkdir(parents=True)
    return declaration


def lock_file(root: Path) -> Path:
    return root / LOCAL_DIR / LOCK_NAME


def held(root: Path) -> bool:
    """Whether another process would have to wait for the lock right now."""
    probe = subprocess.run([sys.executable, "-c", PROBE, str(lock_file(root))])
    return probe.returncode == 1


def test_the_lock_is_held_inside_the_block_and_released_after(tmp_path: Path) -> None:
    with run_lock(tmp_path):
        assert held(tmp_path)
    assert not held(tmp_path)


def test_the_lock_is_released_when_the_body_raises(tmp_path: Path) -> None:
    with pytest.raises(ZeroDivisionError):
        with run_lock(tmp_path):
            1 / 0
    assert not held(tmp_path)


def test_the_lock_file_lives_under_local(tmp_path: Path) -> None:
    """`local/` is session-local state and gitignored; the lock is never
    committed and never leaves this machine's tree."""
    with run_lock(tmp_path):
        pass
    assert lock_file(tmp_path).exists()
    assert lock_file(tmp_path).parent == tmp_path / "local"


def test_contention_is_announced_once_and_then_waited_out(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    """John runs concurrent sessions in one tree: a silent wait reads as a
    hang. The holder line carries the host as well as the pid, because this
    tree is on a syncing filesystem and a pid means nothing on another
    machine."""
    lock_file(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    holder = subprocess.Popen(
        [sys.executable, "-c", HOLD, str(lock_file(tmp_path)), "0.4"],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "held"
        with run_lock(tmp_path):
            assert held(tmp_path)  # ours now
    finally:
        holder.wait()

    announced = capfd.readouterr().err
    assert announced.count("waiting for") == 1
    assert str(lock_file(tmp_path).relative_to(tmp_path)) in announced
    assert "another-host pid 999, session abc" in announced


def test_an_uncontended_run_announces_nothing(
    tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    with run_lock(tmp_path):
        pass
    assert capfd.readouterr().err == ""


def test_a_holder_line_is_cleared_on_release(tmp_path: Path) -> None:
    """So a later contention report cannot name a holder that has gone."""
    with run_lock(tmp_path):
        pass
    assert lock_file(tmp_path).read_text() == ""


# --------------------------------------------------------------------------
# Every mutating transition holds it — creating verbs included
# --------------------------------------------------------------------------


def test_a_creating_transition_holds_the_lock_while_it_writes(
    tree: Declaration, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The old tool skipped the lock for its creating verb, because
    `open(..., "x")` is the reservation. True of one filename — and not of the
    tree-wide uniqueness check, which is a check-then-act across other states.
    One rule beats a rule with an exception."""
    seen: list[bool] = []
    written = item.write

    def probe(one: item.Item) -> None:
        seen.append(held(tree.root))
        written(one)

    monkeypatch.setattr(item, "write", probe)
    execute(tree, tree.transitions["sprout"], name="A seedling", body="Prose.")
    assert seen == [True]
    assert not held(tree.root)


def test_a_moving_transition_holds_the_lock_while_it_writes(
    tree: Declaration, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tree.root / "greenhouse" / "a-seedling.md"
    source.write_text('+++\ncultivar = "heirloom"\n+++\n\nProse.\n')
    seen: list[bool] = []
    written = item.write

    def probe(one: item.Item) -> None:
        seen.append(held(tree.root))
        written(one)

    monkeypatch.setattr(item, "write", probe)
    execute(tree, tree.transitions["transplant"], name="a-seedling")
    assert seen == [True]
    assert not held(tree.root)


def test_the_lock_is_released_when_a_transition_refuses(tree: Declaration) -> None:
    with pytest.raises(Refusal, match="needs a body"):
        execute(tree, tree.transitions["sprout"], name="A seedling", body=None)
    assert not held(tree.root)
