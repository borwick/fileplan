"""The claim record, the identity, and the liveness probe.

Almost all of it runs with no ``tmp_path``: `fileplan.claim` is pure but
for `fileplan.claim.read`, `fileplan.claim.write` and
`fileplan.claim.identity`, which reads the environment rather than the
disk. That is the split 1-1 through 1-5 all keep.

The identity's variable names come from ``tests/fixtures/plan.toml``'s
``[identity]`` — ``GREENHOUSE_PID`` and ``SPROUT_PID``, fixture vocabulary on
purpose, so the suite's existing control means something here too. Beside it
is a **new** control: no agent vendor's variable appears under ``src/`` at
all. That is the direct test of the decision that ``[identity]`` is declared
rather than compiled in (John, 2026-09-02) — if a vendor's name ever creeps
back into the code, it fails.

``[identity]``'s own refusal table lives in ``tests/test_declaration.py``,
beside the rest of ``shape_errors``, because it is a defect in a declaration
rather than in a record.
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import FIXTURE_FILES

from fileplan import claim
from fileplan.claim import ALIVE, DEAD, ELSEWHERE, UNKNOWN, Identity
from fileplan.declaration import Declaration, Refusal, load

REPO = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"

#: The names the fixture declares, in the order it declares them.
DECLARED = ("GREENHOUSE_PID", "SPROUT_PID")

#: Names a real agent sets. Declared in this repo's own `plan.toml` as the
#: worked example, and read from `src/` never.
VENDOR = ("CLAUDE_PID", "CLAUDE_CODE_SESSION_ID")

TAKEN = dt.datetime(2026, 9, 2, 14, 30, tzinfo=dt.timezone.utc)

HERE = Identity(host="this-host", pid=4213)


@pytest.fixture
def declaration() -> Declaration:
    return load(FIXTURES / "plan.toml")


@pytest.fixture(autouse=True)
def _no_declared_pid(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test from an environment naming none of them, so a real
    ``GREENHOUSE_PID`` in the operator's shell cannot decide a result."""
    for name in DECLARED:
        monkeypatch.delenv(name, raising=False)


# --------------------------------------------------------------------------
# identity: the one place the tool reads the environment
# --------------------------------------------------------------------------


def test_the_first_declared_name_that_is_set_supplies_the_pid(
    declaration: Declaration, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GREENHOUSE_PID", "111")
    monkeypatch.setenv("SPROUT_PID", "222")
    assert claim.identity(declaration).pid == 111


def test_an_unset_name_is_skipped_for_the_next_one(
    declaration: Declaration, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The list is ordered and a consumer's own variable may be second."""
    monkeypatch.setenv("SPROUT_PID", "222")
    assert claim.identity(declaration).pid == 222


def test_no_declared_name_set_yields_an_identity_with_no_pid(
    declaration: Declaration,
) -> None:
    """A person at a shell. A usable identity, not an error: it owns its own
    claims on its own host, and the probe reports them unknown."""
    assert claim.identity(declaration).pid is None


def test_the_identity_carries_this_machines_host_name(
    declaration: Declaration,
) -> None:
    import socket

    assert claim.identity(declaration).host == socket.gethostname()


@pytest.mark.parametrize("value", ["abc", "-1", "0", "12.5", "", " 7"])
def test_a_declared_name_holding_something_that_is_not_a_pid_refuses_by_name(
    declaration: Declaration, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """No silent fallback to the next name: recording an identity the operator
    did not choose and cannot see is what `FILEPLAN_PLAN_TOML` refuses too."""
    monkeypatch.setenv("GREENHOUSE_PID", value)
    monkeypatch.setenv("SPROUT_PID", "222")
    with pytest.raises(Refusal, match="GREENHOUSE_PID"):
        claim.identity(declaration)


def test_a_declaration_with_no_identity_table_offers_no_pid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """There is no default. An absent `[identity]` means no identity is
    available, which is a usable declaration as long as no state claims
    anything — a `claimed` state without one refuses at load, and that
    refusal is `test_declaration.py`'s."""
    text = (FIXTURES / "plan.toml").read_text()
    # Both halves of the capability come out together: a verb that claims into
    # a state that does not opt in refuses, which is what says the two are one
    # declaration read from its two ends.
    text = (
        text.partition("[identity]")[0]
        .replace('capabilities = ["claimed"]\n', "")
        .replace("claims = true\n", "")
    )
    (tmp_path / "plan.toml").write_text(text)
    for name in FIXTURE_FILES[1:]:
        (tmp_path / name).write_text((FIXTURES / name).read_text())
    monkeypatch.setenv("GREENHOUSE_PID", "111")

    declaration = load(tmp_path / "plan.toml")
    assert declaration.pid_names == ()
    assert claim.identity(declaration).pid is None


# --------------------------------------------------------------------------
# The record
# --------------------------------------------------------------------------


def test_a_record_is_a_flat_mapping_in_canonical_order() -> None:
    assert claim.record(HERE, taken=TAKEN) == {
        "host": "this-host",
        "pid": 4213,
        "taken": TAKEN,
    }
    assert list(claim.record(HERE, taken=TAKEN)) == list(claim.FIELDS)


def test_an_identity_with_no_pid_writes_a_record_without_one() -> None:
    written = claim.record(Identity(host="this-host"), taken=TAKEN)
    assert "pid" not in written


def test_a_naive_taken_refuses_because_the_record_is_read_elsewhere() -> None:
    with pytest.raises(Refusal, match="aware datetime"):
        claim.record(HERE, taken=dt.datetime(2026, 9, 2, 14, 30))


def test_the_slug_is_the_records_location_and_never_a_field_in_it() -> None:
    """A slug in the record would be a second answer to a question the path
    already answers — `RESERVED_KEYS`' reasoning, applied to a file name."""
    assert "slug" not in claim.FIELDS
    assert claim.path(Path("/tree"), "a-seedling") == Path(
        "/tree/local/claims/a-seedling.toml"
    )


# --------------------------------------------------------------------------
# The probe: four outcomes, and the host gate
# --------------------------------------------------------------------------


def running() -> Identity:
    """This test process: a pid that is certainly alive."""
    import socket

    return Identity(host=socket.gethostname(), pid=os.getpid())


def exited() -> int:
    """The pid of a process that has run and been reaped. `test_lock.py`
    reaches for a subprocess for the same reason: nothing else in a test can
    honestly be dead."""
    done = subprocess.Popen([sys.executable, "-c", ""])
    assert done.wait() == 0  # waited on, so the pid is not a zombie's
    return done.pid


def test_a_live_pid_on_this_host_is_alive() -> None:
    identity = running()
    assert claim.alive(claim.record(identity, taken=TAKEN), identity) == ALIVE


def test_a_pid_that_has_exited_is_dead() -> None:
    identity = running()
    record = {"host": identity.host, "pid": exited(), "taken": TAKEN}
    assert claim.alive(record, identity) == DEAD


def test_a_record_from_another_host_is_held_elsewhere() -> None:
    record = {"host": "another-host", "pid": os.getpid(), "taken": TAKEN}
    assert claim.alive(record, running()) == ELSEWHERE


def test_a_record_with_no_pid_is_unknown() -> None:
    identity = running()
    assert claim.alive({"host": identity.host, "taken": TAKEN}, identity) == UNKNOWN


def test_os_kill_is_never_called_for_another_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The host gate is load-bearing: `os.kill(pid, 0)` asks *this* kernel
    about *its* process table, so on a record from another machine it would
    answer a question nobody asked — about whatever local process happens to
    wear that number."""

    def never(*args: object, **kwargs: object) -> None:
        raise AssertionError("os.kill was called for a record from another host")

    monkeypatch.setattr(os, "kill", never)
    record = {"host": "another-host", "pid": os.getpid(), "taken": TAKEN}
    assert claim.alive(record, running()) == ELSEWHERE


def test_the_never_probed_control_would_catch_a_probe_that_did_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mutation check, run against the defect it names: the same
    monkeypatch with a *matching* host must raise, or the control above is
    testing nothing."""
    identity = running()

    def never(*args: object, **kwargs: object) -> None:
        raise AssertionError("os.kill was called for a record from another host")

    monkeypatch.setattr(os, "kill", never)
    record = {"host": identity.host, "pid": identity.pid, "taken": TAKEN}
    with pytest.raises(AssertionError, match="os.kill was called"):
        claim.alive(record, identity)


def test_a_pid_that_is_not_ours_to_signal_is_alive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The process exists, it is simply not ours to signal. The old tool's
    `_locks.py:_pid_alive` arm, kept."""

    def refused(*args: object, **kwargs: object) -> None:
        raise PermissionError

    monkeypatch.setattr(os, "kill", refused)
    identity = running()
    assert claim.alive(claim.record(identity, taken=TAKEN), identity) == ALIVE


# --------------------------------------------------------------------------
# describe: the one home for the phrase a refusal carries
# --------------------------------------------------------------------------


def test_a_holder_is_one_phrase_naming_the_host_the_pid_and_when() -> None:
    """The executor's refusal, `release`'s refusal and the listing all name a
    holder. Three spellings of one phrase would drift the way two spellings of
    one rule do, so there is one function and this is what it says."""
    assert claim.describe(claim.record(HERE, taken=TAKEN), DEAD) == (
        "this-host pid 4213 (not running), taken 2026-09-02T14:30:00+00:00"
    )


def test_the_phrase_spells_the_moment_the_way_the_record_does(
    tmp_path: Path,
) -> None:
    """A person reading the refusal and then `cat`ting the record should see
    one moment written one way: TOML writes a `T`, and `str(datetime)` does
    not."""
    path = claim.path(tmp_path, "a-seedling")
    claim.write(path, claim.record(HERE, taken=TAKEN))
    stamp = claim.describe(claim.read(path), DEAD).partition("taken ")[2]
    assert f"taken = {stamp}" in path.read_text()


@pytest.mark.parametrize(
    "status, said",
    [
        (ALIVE, "running"),
        (DEAD, "not running"),
        (ELSEWHERE, "another machine"),
        (UNKNOWN, "nothing to probe"),
    ],
)
def test_each_answer_of_the_probe_has_its_own_words(status: str, said: str) -> None:
    """`ELSEWHERE` and `UNKNOWN` say what cannot be known rather than guessing
    at "maybe dead" — the same discipline `alive` keeps."""
    assert said in claim.describe(claim.record(HERE, taken=TAKEN), status)


def test_a_record_with_no_pid_is_described_without_one() -> None:
    record = claim.record(Identity(host="this-host"), taken=TAKEN)
    assert claim.describe(record, UNKNOWN).startswith("this-host (")


def test_a_hand_edited_record_still_produces_a_sentence() -> None:
    """It is called to *explain* a refusal, so it is best effort over what it
    is given rather than a second grader: `errors` is the grader."""
    said = claim.describe({}, UNKNOWN)
    assert "an unnamed host" in said and "at no recorded time" in said


# --------------------------------------------------------------------------
# holder and fields: what a *row* carries, as values rather than a sentence
# --------------------------------------------------------------------------


def test_a_holder_is_the_host_and_the_pid_and_nothing_else() -> None:
    """The value a row carries. `describe` builds its sentence on this one
    function, so the listing and the refusals cannot spell a holder two
    ways."""
    assert claim._holder(claim.record(HERE, taken=TAKEN)) == "this-host pid 4213"


def test_a_record_with_no_pid_is_held_by_its_host_alone() -> None:
    assert claim._holder({"host": "this-host", "taken": TAKEN}) == "this-host"


def test_a_hand_edited_record_still_names_a_holder() -> None:
    """Best effort over what it is given, like `describe`: `errors` is the
    grader, and `holders` is what runs it."""
    assert claim._holder({}) == "an unnamed host"


def test_the_refusals_sentence_is_built_on_the_row_s_value() -> None:
    """The one home, asserted rather than described: whatever `_holder` says is
    what a refusal opens with."""
    record = claim.record(HERE, taken=TAKEN)
    assert claim.describe(record, DEAD).startswith(f"{claim._holder(record)} (")


def test_the_two_fields_are_the_holder_and_the_probes_own_word() -> None:
    """A row carries values, not sentences: `claim-status` holds one of the
    probe's four answers so it filters like any declared key with `values`."""
    assert claim.fields(claim.record(HERE, taken=TAKEN), DEAD) == {
        "claimed-by": "this-host pid 4213",
        "claim-status": DEAD,
    }


def test_the_field_names_have_one_home_in_the_declaration() -> None:
    """Imported rather than spelled again — the module that refuses a
    redeclaration is the module that says what the names are."""
    assert claim.CLAIM_KEYS == (claim.BY, claim.STATUS)
    assert list(claim.fields(claim.record(HERE, taken=TAKEN), ALIVE)) == [
        *claim.CLAIM_KEYS
    ]


def test_the_status_field_holds_one_of_the_probes_four_answers() -> None:
    """The closed set a filter is graded against, and the four `alive` can
    return — one list, so a fifth answer could not appear in a row without
    appearing here."""
    assert claim.STATUSES == (ALIVE, DEAD, ELSEWHERE, UNKNOWN)
    assert set(claim.SAID) == set(claim.STATUSES)


# --------------------------------------------------------------------------
# holders: the edge that reads every record, grades it and probes it
# --------------------------------------------------------------------------


@pytest.fixture
def tree(tmp_path: Path) -> Declaration:
    """The fixture declaration copied into ``tmp_path``, so records written
    under it are this test's own."""
    for name in FIXTURE_FILES:
        (tmp_path / name).write_text((FIXTURES / name).read_text())
    return load(tmp_path / "plan.toml")


def written(declaration: Declaration, slug: str, **record: object) -> Path:
    path = claim.path(declaration.root, slug)
    claim.write(path, {"taken": TAKEN, **record})
    return path


def broken(declaration: Declaration, slug: str, text: str) -> Path:
    path = claim.path(declaration.root, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_no_records_at_all_is_no_claims_not_an_error(tree: Declaration) -> None:
    """`local/` is gitignored, so a fresh clone has no directory either. That
    reads as unclaimed, which is the same rule the executor keeps."""
    assert claim.holders(tree) == {}


def test_each_record_comes_back_under_the_slug_its_location_names(
    tree: Declaration,
) -> None:
    """The stem is the slug: the record's location is the only place one is
    written, so there is no second answer beside it to disagree."""
    identity = running()
    written(tree, "a-seedling", host=identity.host, pid=identity.pid)
    written(tree, "b-seedling", host=identity.host, pid=exited())
    assert list(claim.holders(tree)) == ["a-seedling", "b-seedling"]


def test_every_record_is_graded_and_probed_once(tree: Declaration) -> None:
    """One dead, one on another machine — the two the listing has to tell
    apart, since neither is ever released on its own."""
    identity = running()
    gone = exited()
    written(tree, "a-seedling", host=identity.host, pid=gone)
    written(tree, "b-seedling", host="another-host", pid=identity.pid)
    assert claim.holders(tree) == {
        "a-seedling": {
            "claimed-by": f"{identity.host} pid {gone}",
            "claim-status": DEAD,
        },
        "b-seedling": {
            "claimed-by": f"another-host pid {identity.pid}",
            "claim-status": ELSEWHERE,
        },
    }


def test_a_malformed_record_refuses_by_name(tree: Declaration) -> None:
    """A **missing** record means unclaimed; one that exists and cannot be
    read refuses. Reading that as free is the one direction a claim must
    never fail in."""
    path = broken(tree, "a-seedling", "pid = 4213\n")
    with pytest.raises(Refusal) as refusal:
        claim.holders(tree)
    assert str(path) in str(refusal.value)
    assert "no host" in str(refusal.value)


def test_a_record_that_is_not_toml_at_all_refuses_by_name(
    tree: Declaration,
) -> None:
    broken(tree, "a-seedling", "not toml\n")
    with pytest.raises(Refusal) as refusal:
        claim.holders(tree)
    assert "a-seedling.toml is not a usable claim record" in str(refusal.value)


def test_every_defect_is_reported_at_once_across_records(
    tree: Declaration,
) -> None:
    """A tree of hand-edited records is fixed in one sitting, the way a tree
    of broken item files is."""
    broken(tree, "a-seedling", "pid = 4213\n")
    broken(tree, "b-seedling", "host = 'x'\nvine = 1\n")
    with pytest.raises(Refusal) as refusal:
        claim.holders(tree)
    assert len(refusal.value.messages) >= 4
    assert "a-seedling.toml" in str(refusal.value)
    assert "vine" in str(refusal.value)


def test_one_good_record_beside_a_broken_one_still_refuses(
    tree: Declaration,
) -> None:
    """No partial answer: a listing that returned the readable half would be
    reporting some items as free without having read what claims them."""
    written(tree, "a-seedling", host=running().host, pid=os.getpid())
    broken(tree, "b-seedling", "pid = 4213\n")
    with pytest.raises(Refusal):
        claim.holders(tree)


def test_a_record_from_another_host_is_never_probed(
    tree: Declaration, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The host gate survives the edge: `os.kill(pid, 0)` asks *this* kernel
    about *its* process table, and a whole directory of records is no reason
    to start asking it about another machine's."""

    def never(*args: object, **kwargs: object) -> None:
        raise AssertionError("os.kill was called for a record from another host")

    written(tree, "a-seedling", host="another-host", pid=os.getpid())
    monkeypatch.setattr(os, "kill", never)
    assert claim.holders(tree)["a-seedling"]["claim-status"] == ELSEWHERE


# --------------------------------------------------------------------------
# Ownership
# --------------------------------------------------------------------------


def test_the_same_host_and_pid_owns_the_claim() -> None:
    assert claim.owns(claim.record(HERE, taken=TAKEN), HERE)


def test_another_pid_on_the_same_host_does_not_own_it() -> None:
    other = Identity(host="this-host", pid=9999)
    assert not claim.owns(claim.record(HERE, taken=TAKEN), other)


def test_the_same_pid_on_another_host_does_not_own_it() -> None:
    """A pid means nothing on another machine, and this tree is shared."""
    elsewhere = Identity(host="another-host", pid=HERE.pid)
    assert not claim.owns(claim.record(HERE, taken=TAKEN), elsewhere)


def test_a_record_with_no_pid_is_owned_by_any_identity_on_its_host() -> None:
    """Which is what lets a person at a shell complete their own claim."""
    record = claim.record(Identity(host="this-host"), taken=TAKEN)
    assert claim.owns(record, HERE)
    assert not claim.owns(record, Identity(host="another-host", pid=HERE.pid))


# --------------------------------------------------------------------------
# The two edges: read and write
# --------------------------------------------------------------------------


def test_a_record_round_trips_and_a_second_write_is_byte_identical(
    tmp_path: Path,
) -> None:
    path = claim.path(tmp_path, "a-seedling")
    written = claim.record(HERE, taken=TAKEN)
    claim.write(path, written)
    once = path.read_bytes()

    assert claim.read(path) == written
    claim.write(path, claim.read(path))
    assert path.read_bytes() == once


def test_a_written_record_is_plain_unfenced_toml(tmp_path: Path) -> None:
    """`cat local/claims/x.toml` should show something a reader can parse: a
    `+++` fence is not valid TOML."""
    path = claim.path(tmp_path, "a-seedling")
    claim.write(path, claim.record(HERE, taken=TAKEN))
    assert path.read_text().splitlines() == [
        'host = "this-host"',
        "pid = 4213",
        "taken = 2026-09-02T14:30:00+00:00",
    ]


def test_write_makes_the_claims_directory_under_local(tmp_path: Path) -> None:
    path = claim.path(tmp_path, "a-seedling")
    claim.write(path, claim.record(HERE, taken=TAKEN))
    assert path.parent == tmp_path / "local" / "claims"


def test_a_chmod_on_a_claim_record_survives_the_next_write(tmp_path: Path) -> None:
    """An operator who widens a record's mode keeps it.

    Until 10-5b `claim.write` carried its own copy of the temp-file-then-replace
    dance and never chmodded, so every write narrowed the record back to the
    temp file's `0600` — silently, and nothing said so. The `0600` a *new*
    record starts at is not asserted here: that is unchanged by the patch this
    guards, and pinning it here would read as if the patch introduced it.
    """
    path = claim.path(tmp_path, "a-seedling")
    claim.write(path, claim.record(HERE, taken=TAKEN))
    os.chmod(path, 0o644)

    claim.write(path, claim.record(HERE, taken=TAKEN))
    assert path.stat().st_mode & 0o777 == 0o644


def test_a_missing_record_refuses_by_name(tmp_path: Path) -> None:
    with pytest.raises(Refusal, match="could not be read"):
        claim.read(claim.path(tmp_path, "never-claimed"))


def test_a_record_that_is_not_utf8_refuses(tmp_path: Path) -> None:
    path = claim.path(tmp_path, "a-seedling")
    path.parent.mkdir(parents=True)
    path.write_bytes(b'host = "\xff\xfe"\n')
    with pytest.raises(Refusal, match="not UTF-8"):
        claim.read(path)


@pytest.mark.parametrize(
    "text",
    ['[session]\nhost = "this-host"', 'nested = { host = "this-host" }'],
)
def test_a_nested_record_refuses_by_name(tmp_path: Path, text: str) -> None:
    """Inherited from the promoted parser: a claim record is flat for the same
    reason a head is, and it is told so in its own words."""
    path = claim.path(tmp_path, "a-seedling")
    path.parent.mkdir(parents=True)
    path.write_text(text)
    with pytest.raises(Refusal, match="a claim record is flat"):
        claim.read(path)


def test_unparseable_toml_carries_tomllibs_own_message(tmp_path: Path) -> None:
    path = claim.path(tmp_path, "a-seedling")
    path.parent.mkdir(parents=True)
    path.write_text('host = "unterminated\n')
    with pytest.raises(Refusal, match="not valid TOML"):
        claim.read(path)


def test_remove_takes_the_record_away(tmp_path: Path) -> None:
    path = claim.path(tmp_path, "a-seedling")
    claim.write(path, claim.record(HERE, taken=TAKEN))
    claim.remove(path)
    assert not path.exists()


def test_removing_a_record_that_is_not_there_is_not_an_error(
    tmp_path: Path,
) -> None:
    """A claim dropped twice leaves the same tree either way, and refusing
    would turn a crash between an item's write and its record's removal into
    something a person has to resolve. A missing record means unclaimed
    everywhere else too."""
    claim.remove(claim.path(tmp_path, "never-claimed"))


def test_remove_leaves_the_claims_directory_and_its_neighbours(
    tmp_path: Path,
) -> None:
    """One record, not the tree: a second session's claim is not this one's to
    tidy up."""
    mine = claim.path(tmp_path, "a-seedling")
    theirs = claim.path(tmp_path, "b-seedling")
    claim.write(mine, claim.record(HERE, taken=TAKEN))
    claim.write(theirs, claim.record(HERE, taken=TAKEN))
    claim.remove(mine)
    assert theirs.exists()


# --------------------------------------------------------------------------
# errors: every defect in a hand-edited record, at once
# --------------------------------------------------------------------------


def test_a_well_formed_record_has_no_errors() -> None:
    assert claim.errors(claim.record(HERE, taken=TAKEN)) == []


def test_a_record_with_no_host_refuses() -> None:
    """Without a host its pid means nothing: a pid is only a pid on the
    machine that wrote it."""
    errors = claim.errors({"pid": 4213, "taken": TAKEN})
    assert any("no host" in error for error in errors)


@pytest.mark.parametrize("pid", ["4213", -1, 0, True, 12.5])
def test_a_pid_that_is_not_a_positive_whole_number_refuses(pid: object) -> None:
    """A quoted pid is the one to watch: it is what the probe hands the
    kernel, and text there probes nothing."""
    errors = claim.errors({"host": "this-host", "pid": pid, "taken": TAKEN})
    assert any("not a pid" in error for error in errors)


def test_an_unknown_field_refuses_by_name() -> None:
    record = {"host": "this-host", "pid": 4213, "taken": TAKEN, "session": "abc"}
    assert any('"session" is not a claim record field' in error
               for error in claim.errors(record))


def test_every_defect_is_reported_at_once() -> None:
    """One sitting rather than one message at a time, like `shape_errors`."""
    assert len(claim.errors({"pid": "4213", "colour": "green"})) == 3


# --------------------------------------------------------------------------
# The control: no agent vendor is compiled into the tool
# --------------------------------------------------------------------------


def source() -> str:
    return "\n".join(path.read_text() for path in sorted((REPO / "src").rglob("*.py")))


def test_no_agents_variable_names_appear_anywhere_under_src() -> None:
    """The direct test of the decision that `[identity]` is declared rather
    than hard-coded (John, 2026-09-02). A tool whose premise is that the
    workflow is declared cannot bake one vendor into its own source — and
    `CLAUDE_PID` in `src/` is exactly that. If a name ever creeps back in,
    this is what fails."""
    haystack = source()
    for name in VENDOR:
        assert name not in haystack


def test_the_vendor_control_reads_the_files_it_claims_to() -> None:
    """The mutation check, run against the defect it names: a variable name
    that really is in `src/` must be found by the same scan, or the control
    above would pass over an empty haystack forever."""
    assert "FILEPLAN_PLAN_TOML" in source()


def test_the_repos_own_declaration_is_where_the_vendors_names_live() -> None:
    """And the other half: the control passes because the names moved to
    `plan.toml`, not because nothing uses them."""
    declaration = load(REPO / "plan.toml")
    assert declaration.pid_names == ("CLAUDE_PID", "FILEPLAN_PID")
