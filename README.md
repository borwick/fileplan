# fileplan

This project is primarily designed for AI-assisted development workflows. I didn't want to set up beads, basically.

Track project plans in directories and files rather than PLAN.md. This lets multiple agents simultaneously develop code, and reduces the cost and churn of adding, reordering, or cancelling work.

## Key elements

Create a plan file for each "phase" or set of work you want to do. The plan file is markdown with TOML frontmatter, e.g.

    todo/new-work.md:
    +++
    title = "This is a new piece of work"
    +++

    Description of work.

Then, `fileplan` reads a `plan.toml` file that defines your workflow. A `plan.toml` can be composed of:

  - states
    - "paths" (directories) assigned to states, each its own name by default
    - "doc" - optional documentation for this state
    - capabilities
  - keys
    - attributes related to a plan file
  - transitions
    - "kind" - what the transition does: create, move, edit, close, and five more
    - from state
    - to state
    - "doc" - optional documentation for this transition
  - "identity"
    - "doc" - documentation on how agents set their identities and "claim" items
    - "pid" - environment variables to use to derive agent ID

## Getting started

Start with the default workflow:

```
$ fileplan init .
inbox
plan
local
archive.md
plan.toml
local/.gitignore
```

Create an item:

```
$ fileplan capture "Rename the states" --body "The names init wrote are placeholders."
inbox/rename-the-states.md
```

`capture` writes the plan file:

    $ cat inbox/rename-the-states.md
    +++
    title = "Rename the states"
    +++
    
    The names init wrote are placeholders.

The plan file can then be found and managed via `fileplan`:

```
$ fileplan list
rename-the-states  inbox
  commands  queue
  title     Rename the states
  path      inbox/rename-the-states.md

showing 1 of 1 items
```

Transition the plan file with the `queue` transition:

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

Mark the plan file as in progress:

```
$ fileplan work rename-the-states --status "in progress"
plan/rename-the-states.md

$ fileplan work rename-the-states --status nobody
Usage: fileplan work [OPTIONS] ITEM
Try 'fileplan work --help' for help.

Error: Invalid value for '--status': 'nobody' is not one of 'in progress', 'waiting'.
```

Mark it done with `archive`:

```
$ fileplan archive rename-the-states --record "Renamed everything to our own words."
archive.md: filed `## 1. Rename the states` at its place in the register, with the record under it
plan/rename-the-states.md is gone: archive took it away
archive.md

$ cat archive.md
# Archive

Closed items are filed here, newest last. Each one goes under its own number.

## 1. Rename the states

Renamed everything to our own words.
```

## The plan.toml behind it

Here is the `plan.toml` for the workflow above, as `fileplan init` writes
it, without its comments:

```toml
[states.inbox]

[states.plan]
capabilities = ["queued", "numbered"]
archive      = "archive.md"

[keys.status]
help   = "How the work is going."
values = ["in progress", "waiting"]

[transitions.capture]
kind = "create"
to   = "inbox"

[transitions.queue]
kind = "move"
from = "inbox"
to   = "plan"

[transitions.work]
kind = "edit"
from = "plan"
sets = ["status"]

[transitions.archive]
kind     = "close"
from     = "plan"
archives = true
```

Every name in that file is a placeholder. `inbox`, `plan`, `capture`, `queue`,
`work` and `archive` are not fileplan's words. Rename each one to the word your
own work already uses.

A transition's `kind` decides what the transition does:

  - `create` writes a new plan file into the state its `to` names.
  - `move` moves the plan file from its `from` directory to its `to`.
  - `edit` leaves the plan file where it is, and writes a key into the plan
    file's frontmatter.
  - `close` deletes the plan file, which is why `archive` declares no `to`.

`archives = true` writes the closing entry into an archive document.
[The method](https://github.com/borwick/fileplan/blob/main/docs/method.md#kinds) lists every kind.

Capabilities give a state extra behaviour. The `plan` state above declares
`queued` and `numbered`, which is why the plan file picked up a position and a
number when it arrived there.

## Asking fileplan about your workflow

The workflow above is one example. To see your own, ask fileplan rather than
a document.

Run `fileplan` with no arguments to see what your `plan.toml` declares:

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

`Declares` gives each transition's kind, and any option it declares beside
the kind.

Ask one transition what it takes:

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

No transition in the starter names a document, so none of them has more to
read than its help line. Give `work` a `doc` pointing at a section and its
contract grows a `Reading` block naming that section, which fileplan checks
exists on every run. The section is your own documentation, and fileplan
never writes the prose behind it.

Add `--check` to any transition to print what the transition would do, and stop
before writing anything.

`fileplan --json` prints every transition at once, for a script or an agent
rather than for a person.

## Where to go next

  - [Initializing fileplan](https://github.com/borwick/fileplan/blob/main/docs/initialization.md) — the full walk, from
    installing fileplan to handing an agent the skills. Every command in it was
    run and its output pasted.
  - [Retrofitting fileplan](https://github.com/borwick/fileplan/blob/main/docs/retrofit.md) — the walk for a tree that
    already has work in it, where `init` is the wrong first command.
  - [The method](https://github.com/borwick/fileplan/blob/main/docs/method.md) — the reference for every word a `plan.toml`
    can hold.
  - [The documents](https://github.com/borwick/fileplan/blob/main/docs/index.md) — everything under `docs/`, plus the two
    skills an agent reads.

## Status

`uv build` produces a wheel that installs and runs. Check the package index for
which versions are published.

## AI disclosure

`fileplan` was written with Claude Code, under John Borwick's direction and
review. [How this was written](https://github.com/borwick/fileplan/blob/main/docs/ai-disclosure.md) covers the disclosure
level, who did what, and why the git history does not record it. Anthropic did
not build this tool and does not endorse it.
