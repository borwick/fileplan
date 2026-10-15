# Initializing fileplan

From nothing to a tree an agent can work in.

Every command below was run and its output pasted from that run. The walk
from `fileplan init` on was re-run on 2026-10-06 against the working tree,
through `uv run`; the install, `--version` and `--skills` blocks are from the
2026-09-12 run against a built wheel. Two blocks are trimmed. The install
block leaves out uv's dependency lines, and `fileplan --skills` prints the
ordinary install location rather than the throwaway directory that run
installed into.

## what you are getting

A directory for each stage your work goes through, and one command for each
move between the directories. `plan.toml` names the directories and the moves.
fileplan builds all of it out of `plan.toml`: the commands, the filters on the
listing, and a refusal by name for anything the declaration does not allow.

The names in this walk come from the example `plan.toml` that `fileplan init`
writes. None of them is fileplan's own word, and renaming them is the first
thing you do.

**If your tree already has work in it, this is not your walk.** `fileplan init`
has nothing to collide with there, so it writes its own example *beside* your
directories rather than over them.
[Retrofitting fileplan](retrofit.md) starts from the directories you already
have.

## installing it

Once fileplan is on PyPI:

```
$ uv tool install fileplan
```

Today it is not, so install from a built wheel:

```
$ uv build --no-sources
Building source distribution...
Building wheel from source distribution...
Successfully built dist/fileplan-0.4.0.tar.gz
Successfully built dist/fileplan-0.4.0-py3-none-any.whl

$ uv tool install ./dist/fileplan-0.4.0-py3-none-any.whl
Installed 1 executable: fileplan
```

Either way you get the `fileplan` console script. `python -m fileplan` runs
the same code. Check what you installed:

```
$ fileplan --version
fileplan, version 0.4.0
```

`--version` answers anywhere. Every other command reads a `plan.toml`, and you
do not have one yet:

```
$ fileplan
ERROR: no plan.toml in /private/tmp/fileplan-example or any parent directory (set FILEPLAN_PLAN_TOML to name one, or run `fileplan init` to write a first one here)
```

## a first declaration

The refusal names the way out. Run `fileplan init` in an empty directory:

```
$ fileplan init .
inbox
plan
local
archive.md
plan.toml
local/.gitignore
```

Two directories for your work, a `plan.toml`, the archive document a closed
item's entry is filed in, and `local/`, where fileplan keeps session state
such as its lock. `local/.gitignore` holds `*`, so none of that is ever
committed. `fileplan init` writes nothing over a file that is already there,
and refuses inside a tree that already has a `plan.toml` above it, so running
`fileplan init` twice costs you nothing.

Now fileplan has a declaration to build its commands from:

```
$ fileplan
/private/tmp/fileplan-example/plan.toml

States
  inbox    inbox/
  plan     plan/   sorted by position

Transitions
  capture  Create an item in inbox.
  queue    Move an item from inbox to plan.
  work     Edit an item in plan where it stands.
  archive  Close an item in plan out: file its archive entry, and take its file away.

Declares
  capture  create
  queue    move
  work     edit
  archive  close, archives

Run `fileplan list` to see what is filed.
Run `fileplan show ITEM` to see one item's row.
Run `fileplan COMMAND --help` to see what COMMAND takes.
```

`States` and `Transitions` are `plan.toml` read back to you. Add a state to
the declaration and it appears here. **`Declares`** gives each command's
kind: `capture` creates an item, `queue` moves one, `work` edits one where it
stands, and `archive` closes one out, writing a record as it takes the item
away.

## making it yours

**Every name in what `init` wrote is a placeholder.** `inbox`, `plan`,
`capture`, `queue`, `work`, `archive`, `status` — none of them is fileplan's,
and fileplan has no opinion about them. Open `plan.toml` and rename them to
your work's own words.

The starter `plan.toml` declares one loop: log an idea, commit to it, work it,
close it out. Every line in it is there because the loop needs it:

- **`[states.inbox]`** is a directory called `inbox`. A state with no `path`
  is at its own name.
- **`[states.plan]`** declares `queued`, which gives each item a place in an
  order, and `numbered`, which gives each item a number as it arrives. A
  queued state lists by place unless it names another `sort`. `archive` is the
  document a closed item's entry is filed in, under its number.
- **`[keys.status]`** is a fact an item can carry. `values` closes the set,
  so any other word refuses by name. There is no `done`: an item that is done
  is archived, and its file goes away with it.
- **Each transition says its `kind`.** `capture` is a `create`, so it has no
  `from` and takes a title. `queue` is a `move` from `inbox` to `plan`, and
  because `plan` is ordered it also takes `--above`, `--below` and `--at`.
  `work` is an `edit`, which leaves the file where it is, and its `sets` is
  what gives it a `--status` option. `archive` is a `close`, which takes the
  file away, so it names no `to`; `archives = true` files the entry first,
  from `--record`, because the body goes with the file.
- **No transition writes a `help` line.** Each one's help is said from its
  kind and the states it names. Write `help = "..."` to say something better.
- **Nothing points at a document yet.** Give a key or a transition a `doc`,
  such as `doc = "notes.md#work"`, when you want a section that says what the
  word means;
  `fileplan` then checks that the heading exists every time it runs. A
  section can link on to a procedure a session follows around a run.

fileplan does more than that loop asks for. An item can be claimed by one
session at a time, cut into named bullets and marked off one by one, or given
a list of what it waits on. A `[fileplan]` table can name the oldest release
the file needs, so an older fileplan says to upgrade instead of blaming the
file, a `root` the states sit under, or the file names a state directory
does not read as items. Each of those stays off until
`plan.toml` turns it on, and [the method](method.md) describes them one at a
time.

Two commands read your declaration back to you. The bare `fileplan` above
lists everything `plan.toml` declares. `fileplan COMMAND --help` gives one
command's whole contract:

```
$ fileplan work --help
Usage: fileplan work [OPTIONS] ITEM

  Edit an item in plan where it stands.

Options:
  --status [in progress|waiting]  How the work is going.
  --check                         Say what this run would do, and stop before
                                  writing anything. A refusal under --check is
                                  the refusal a real run gives.
  --help                          Show this message and exit.

  Where the item goes
    stays in plan

  Declares
    edit
```

Once `work` and `status` carry a `doc`, the contract grows a **`Reading`**
block naming the sections that say what this command and its values *mean*.
Where a session also has something to *do* around a run, that section links
to a procedure. Both are documents in your own tree, and fileplan prints the
pointers and never writes the prose behind them. With no `Reading` block, the
help line is the whole of what a session reads.

## the loop, run end to end

Four commands: log an idea, commit to it, work it, close it out. A command
with no `from` **creates** an item:

```
$ fileplan capture "Rename the states" --body "The names init wrote are placeholders."
inbox/rename-the-states.md
```

An item is a Markdown file with a head:

```
$ cat inbox/rename-the-states.md
+++
title = "Rename the states"
+++

The names init wrote are placeholders.
```

`list` walks the directories and prints what it finds. There is no database:

```
$ fileplan list
rename-the-states  inbox
  commands  queue
  title     Rename the states
  path      inbox/rename-the-states.md

showing 1 of 1 items
```

Each row's `commands` names what could take the item right now: `queue`, the
one command whose `from` is `inbox`. So a filter on it is the listing
narrowed to what one command could take:

```
$ fileplan list --has commands=queue
rename-the-states  inbox
  commands  queue
  title     Rename the states
  path      inbox/rename-the-states.md

showing 1 of 1 items
```

Add `--check` to any command to see what the command would do. The check takes
the same path as the run and stops before the first write, and it names what it
would write into the head as well as the move:

```
$ fileplan queue rename-the-states --check
queue would move inbox/rename-the-states.md to plan/rename-the-states.md, and would write position 100 and write number 1
```

Take the `--check` off to do it:

```
$ fileplan queue rename-the-states
plan/rename-the-states.md

$ fileplan list
rename-the-states  plan
  position  100
  number    1
  commands  work, archive
  title     Rename the states
  path      plan/rename-the-states.md

showing 1 of 1 items
```

The file moved, and two columns appeared that nobody typed. The `plan` state
is declared `queued` and `numbered`, so an item arriving in `plan` is given a
place and a number of its own. A queued state sorts by place, so the listing
reads `plan` in place order. The order is
what makes the listing answer *what is next* rather than *what exists*.

`work` leaves the item where it is and stamps a key into its head:

```
$ fileplan work rename-the-states --status "in progress"
plan/rename-the-states.md

$ fileplan list
rename-the-states  plan
  position  100
  number    1
  commands  work, archive
  title     Rename the states
  status    in progress
  path      plan/rename-the-states.md

showing 1 of 1 items
```

A value the declaration does not allow is refused by name rather than filed:

```
$ fileplan work rename-the-states --status nobody
Usage: fileplan work [OPTIONS] ITEM
Try 'fileplan work --help' for help.

Error: Invalid value for '--status': 'nobody' is not one of 'in progress', 'waiting'.
```

The declared values are `in progress` and `waiting`. An item that is done is
archived instead, and `archive` is the last command in the loop:

```
$ fileplan archive rename-the-states --record "Renamed everything to our own words."
archive.md: filed `## 1. Rename the states` at its place in the register, with the record under it
plan/rename-the-states.md is gone: archive took it away
archive.md
```

The item file goes away, so the entry is written from `--record` rather than
from the body:

```
$ cat archive.md
# Archive

Closed items are filed here, newest last. Each one goes under its own number.

## 1. Rename the states

Renamed everything to our own words.

$ fileplan list

showing 0 of 0 items
Nothing is filed. `fileplan capture TITLE --body TEXT` files one in inbox.
```

That heading is now the only record that number 1 is taken, which is why the
next item queued gets 2, and the empty listing names the command that files
the next one. That is the whole loop. Everything you add to it is a
line in `plan.toml`.

## reading the plan from a commit hook

If a gate grades the plan before a commit lands, give the gate the tree that
commit will make rather than the working copy. **fileplan reads a tree, not an
index.** Materialize the index into a scratch directory, and point fileplan at
the `plan.toml` inside the scratch copy:

```
$ staged=$(mktemp -d) && git checkout-index -a --prefix="$staged/"
$ FILEPLAN_PLAN_TOML="$staged/plan.toml" fileplan list --json
{"version":1,"kind":"items","matched":2,"read":2,"gaps":[],"lost":[],"register":[{"state":"plan","archive":"archive.md","floor":1,"highest":1}],"undeclared":[],"unsorted":[],"rows":[{"slug":"wire-the-commit-gate","state":"inbox","position":null,"number":null,"stale-days":null,"commands":["queue"],"title":"Wire the commit gate","status":null,"path":"inbox/wire-the-commit-gate.md"},{"slug":"rename-the-states","state":"plan","position":100,"number":1,"stale-days":null,"commands":["work","archive"],"title":"Rename the states","status":null,"path":"plan/rename-the-states.md"}]}
```

That run is the declaration above. The item is
queued rather than closed out, and a second capture is staged but not
committed. The staged item is on the row list.

`FILEPLAN_PLAN_TOML` is the middle of three ways fileplan finds the
declaration. A `path` argument comes first, then `FILEPLAN_PLAN_TOML`, then a
walk upward from the working directory. Naming the file turns the walk off,
so a gate cannot wander up into the developer's own tree.

The scratch copy is not a git repository, and that costs nothing.
**`stale-days` reads `null` on every row and nothing refuses.** Ages come out
of git, so a tree git knows nothing about has no ages. Running fileplan
outside a repository is the same case, and it is not an error there either.

One `list --json` is the whole read a gate needs, because the envelope beside
the rows carries the rest. `gaps` and `register` together say whether a number
is still held. The register does not reach below `floor`, and nothing above
`highest` has been minted. In between, a number is held unless it is a gap.
`unmarkable` says whether a bullet can be marked, and sits in the envelope
wherever a command of yours marks at all. `unread` names a bullet the count
passed over, wherever a state counts sub-phases. None of them is a flag you
have to know to pass, and none asks you to read a body.

## giving an agent the interpreter

fileplan ships the skills an agent reads to run your workflow, and prints
where the skills are:

```
$ fileplan --skills
/Users/you/.local/share/uv/tools/fileplan/lib/python3.13/site-packages/fileplan/skills
```

Ask fileplan rather than Python. `uv tool install` puts fileplan in a virtual
environment of its own, so importing the package from your own interpreter
finds nothing. Copy the skills wherever your harness reads skills from. For
Claude Code that is `.claude/skills/`:

```
$ mkdir -p .claude/skills && cp -R "$(fileplan --skills)"/* .claude/skills/
$ ls .claude/skills/
do-next
fileplan
```

**`/fileplan` runs one command, whichever it is.** The skill asks fileplan for
the contract, checks the item against the contract, reads the sections the
contract names, does what those sections say, and runs the command. The skill
branches on what the declaration says a command *declares*, never on the
command's name. So it works for a command it has never seen, including yours.
Your `Reading` pointers, and the procedures their sections link to, are the
program, and the skill is the interpreter.

**`/do-next` is a worked example of composing runs.** It reads the tree, works
out which of three arms a session is in, and hands every move to `/fileplan`.
It acts on the head item, or on the one a section number, a sub-phase name or
a slug prefix names, and it stops rather than guessing when the name matches
nothing.
`/do-next` expects a workflow that has grown sub-phases and a cursor over them,
so it has nothing to act on in the loop `init` writes. Read `/do-next` once
your declaration has more than that loop in it. A repo that already has a
`/do-next` of its own copies `"$(fileplan --skills)"/fileplan` alone, so the
example does not land on top of the composition it was meant to inform.

Copy both skills, or copy `fileplan/` alone. Neither skill names a command any
particular workflow declares.

## where this goes

A copied skill goes stale when fileplan is upgraded. The native route in 2026
is a **plugin**. That is a manifest plus a marketplace file that a harness
installs and updates from a git repository, rather than a directory you copy
by hand. A plugin needs a remote, which is what publishing to PyPI needs too,
and this project has neither yet. When the remote arrives, the skills come
with it and this section becomes one command.
