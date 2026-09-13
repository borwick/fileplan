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
    - "paths" (directories) assigned to states
    - "doc" - documentation for this state
    - capabilities
  - keys
    - attributes related to a plan file
  - transitions
    - from state
    - to state
    - "doc" - documentation for this transition
  - "identity"
    - "doc" - documentation on how agents set their identities and "claim" items
    - "pid" - environment variables to use to derive agent ID

## Getting started

Start with the default workflow:

```
$ fileplan init .
inbox
plan
docs
docs/archive.md
docs/method.md
docs/procedures.md
plan.toml
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
  title  Rename the states
  path   inbox/rename-the-states.md

showing 1 of 1 items
register plan: floor 1, nothing held yet, in docs/archive.md
```

Transition the plan file with the `queue` transition:

```
$ fileplan queue rename-the-states
plan/rename-the-states.md

$ fileplan list
rename-the-states  plan
  position  100
  number    1
  title     Rename the states
  path      plan/rename-the-states.md

showing 1 of 1 items
register plan: floor 1, highest 1, in docs/archive.md
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
docs/archive.md: filed `## 1. Rename the states` at its place in the register, with the record under it
plan/rename-the-states.md is gone: archive took it away
docs/archive.md

$ cat docs/archive.md
# Archive

Closed items are filed here, newest last. Each one goes under its own number.

## 1. Rename the states

Renamed everything to our own words.
```

## The plan.toml behind it

Here is the `plan.toml` for the workflow above, without the documentation
pointers:

```toml
[states.inbox]
path = "inbox"

[states.plan]
path         = "plan"
capabilities = ["queued", "numbered"]

[keys.status]
help   = "How the work is going."
values = ["in progress", "waiting"]

[transitions.capture]
help = "Log an idea in the inbox."
to   = "inbox"

[transitions.queue]
help = "Commit to an idea: move it into the plan."
from = "inbox"
to   = "plan"

[transitions.work]
help = "Say how the work is going."
from = "plan"
to   = "plan"
sets = ["status"]

[transitions.archive]
help      = "Close an item out: file its entry and remove the item."
from      = "plan"
archives  = true
dissolves = true
```

Every name in that file is a placeholder. `inbox`, `plan`, `capture`, `queue`,
`work` and `archive` are not fileplan's words. Rename each one to the word your
own work already uses.

A transition's `from` and `to` decide what the transition does:

  - No `from` creates a new plan file.
  - A `from` and a `to` move the plan file to another directory.
  - A `from` and a `to` that match leave the plan file where it is, and write a
    key into the plan file's frontmatter.

`archives = true` writes the closing entry into an archive document.
`dissolves = true` deletes the plan file, which is why `archive` declares no
`to`.

Capabilities give a state extra behaviour. The `plan` state above declares
`queued` and `numbered`, which is why the plan file picked up a position and a
number when it arrived there. The `register` line in the listing says which
numbers the archive document has taken.

## Asking fileplan about your workflow

The workflow above is one example. To see your own, ask fileplan rather than
a document.

Run `fileplan` with no arguments to see what your `plan.toml` declares:

```
$ fileplan
/private/tmp/fileplan-example/plan.toml

States
  inbox    inbox/
  plan     plan/

Transitions
  capture  Log an idea in the inbox.
  queue    Commit to an idea: move it into the plan.
  work     Say how the work is going.
  archive  Close an item out: file its entry and remove the item.

Declares
  archive  archives, dissolves

Run `fileplan list` to see what is filed.
Run `fileplan next COMMAND` to see what COMMAND could take right now.
Run `fileplan show ITEM` to see one item's row.
Run `fileplan COMMAND --help` to see what COMMAND takes.
```

`Declares` lists the transitions that do more than move a plan file.

Ask one transition what it takes:

```
$ fileplan work --help
Usage: fileplan work [OPTIONS] ITEM

  Say how the work is going.

Options:
  --status [in progress|waiting]  How the work is going.
  --check                         Say what this run would do, and stop before
                                  writing anything. A refusal under --check is
                                  the refusal a real run gives.
  --help                          Show this message and exit.

  Where the item goes
    stays in plan

  Reading
    work    docs/method.md#work
    status  docs/method.md#status

  Running it
    docs/procedures.md#working-an-item
```

`Reading` and `Running it` are the `doc` and `policy` pointers from your
`plan.toml`, resolved to the sections they name. The sections are in your own
documentation. fileplan prints the pointers and never writes the prose behind
them.

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
