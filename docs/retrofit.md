# Retrofitting fileplan

You have a tree with work in it already, and no `plan.toml`. This is the walk
for that. [Initializing fileplan](initialization.md) is the walk for an empty
directory, from the install onward. This walk assumes fileplan is installed,
and starts at the first command you would run inside your own repo.

Every command below was run on 2026-09-12 and its output pasted from that run.
The three refusals that name a file were run again on 2026-09-13, when
fileplan began naming a file from the folder holding `plan.toml`. The four
`fileplan list` refusals were run again on 2026-09-28, when each clause of a
refusal got a line of its own.
The tree it ran against is a **fixture**: a small repo built to provoke each
thing a retrofit meets, rather than a copy of anybody's real notes. The tree is
made up. The behaviour is not.

## a tree that already has work in it

The fixture is a git repository with two directories of Markdown in it, `adr/`
and `someday-maybe/`:

```
$ find . -path ./.git -prune -o -print | sort
.
./adr
./adr/0001-store-notes-as-files.md
./adr/0002-one-binary-not-two.md
./adr/README.md
./someday-maybe
./someday-maybe/archive
./someday-maybe/archive/drop-the-daemon.md
./someday-maybe/learn-a-typed-language.md
./someday-maybe/move-off-the-shared-drive.md
./someday-maybe/Q3 2024 retro.md
./someday-maybe/rewrite-the-importer.md
./someday-maybe/scratch.txt
```

Between them those notes carry one of each thing a retrofit trips over:

  - notes with `#` titles and no head;
  - one file carrying YAML frontmatter from another tool;
  - one carrying a TOML head with a key nothing declares;
  - a `README.md` sitting beside the items;
  - a `.txt`, and a `.md` one directory deeper;
  - one filename with spaces in it.

Your own tree will have its version of most of these.

The work is in four moves: **do not run `init`**, write the method headings and
then the declaration, give the existing files heads, and list. Nothing is
renamed and nothing is moved into a new directory — a retrofit that reorganised
your tree would break every link in your notes on its first command.

## do not run init here

`fileplan init` is for an empty directory. In a tree that already has work in
it, `fileplan init` does not refuse. It **succeeds**, and that is worse:

```
$ fileplan init .
inbox
plan
docs
docs/archive.md
docs/method.md
docs/procedures.md
plan.toml

$ ls
adr
docs
inbox
plan
plan.toml
someday-maybe
```

Two new directories and a declaration describing a workflow you do not have,
sitting beside the two directories you do. Nothing was overwritten and nothing
was lost, but the tree now looks retrofitted and is not: `inbox/` and `plan/`
are empty, and the new `plan.toml` says nothing about `adr/` or
`someday-maybe/`.

`fileplan init` refuses only where it would land on a file that is already
there. Once you have written the document your pointers name, you get this
instead:

```
$ fileplan init .
ERROR: docs/method.md already exists, and `fileplan init` writes nothing over a file that is already there
```

That refusal is the friendly outcome, and it is not the one you meet first.
Run `fileplan init` somewhere empty if you want a working example to crib from,
and copy the lines you want out of it. The example declares one small loop, and
[the method](method.md) describes everything past it. Do not run
`fileplan init` in the tree you are retrofitting.

## naming the directories you already have

A state is a directory you already have, so you are naming directories rather
than making them. Two states, one move between them and one key is enough to
start with. Here is the fixture's `plan.toml`, written by hand:

```
$ cat plan.toml
[states.someday-maybe]
path = "someday-maybe"
doc  = "docs/method.md#someday-maybe"

[states.adr]
path = "adr"
doc  = "docs/method.md#adr"

[keys.decided]
doc  = "docs/method.md#decided"
help = "The date the decision was taken."

[transitions.decide]
doc  = "docs/method.md#decide"
help = "Promote a someday-maybe note to a decision record."
from = "someday-maybe"
to   = "adr"
sets = ["decided"]
```

Every `doc =` points at the section of your own prose that says what that word
means, and **fileplan checks every pointer on every run**. The declaration will
not load until the document exists and has the headings:

```
$ fileplan list
ERROR: /private/tmp/fileplan-retrofit/plan.toml is not a usable plan.toml
  states.someday-maybe.doc names docs/method.md, which does not exist
  states.adr.doc names docs/method.md, which does not exist
  keys.decided.doc names docs/method.md, which does not exist
  transitions.decide.doc names docs/method.md, which does not exist
```

Create the document and the refusal gets narrower rather than going away. A
missing heading is the same broken pointer as a missing document:

```
$ fileplan list
ERROR: /private/tmp/fileplan-retrofit/plan.toml is not a usable plan.toml
  states.someday-maybe.doc names anchor "#someday-maybe", which is not a heading in docs/method.md
  states.adr.doc names anchor "#adr", which is not a heading in docs/method.md
  keys.decided.doc names anchor "#decided", which is not a heading in docs/method.md
  transitions.decide.doc names anchor "#decide", which is not a heading in docs/method.md
```

**This is the retrofit's chicken-and-egg, and it reads like a bug until you
know.** Write the headings first, then the declaration. One heading per name
you declared, with a sentence under each, is enough to start. You are writing
those sentences for the person who has to decide which directory something
belongs in, and that is usually you in six months.

```
$ cat docs/method.md
# The method

What the words in `plan.toml` mean here.

## someday-maybe

A note about something we might do. Nobody has decided anything.

## adr

A decision that was taken, one file per decision. It stays even when it is
superseded.

## decided

The date the decision was taken, `YYYY-MM-DD`.

## decide

Promote a note to a decision record. Write the decision into the file first;
this only moves it and stamps the date.
```

Now the declaration loads, and `fileplan` reads it back to you:

```
$ fileplan
/private/tmp/fileplan-retrofit/plan.toml

States
  someday-maybe  someday-maybe/
  adr            adr/

Transitions
  decide         Promote a someday-maybe note to a decision record.

Run `fileplan list` to see what is filed.
Run `fileplan next COMMAND` to see what COMMAND could take right now.
Run `fileplan show ITEM` to see one item's row.
Run `fileplan COMMAND --help` to see what COMMAND takes.
```

## giving the files heads

An item is a Markdown file that opens with a `+++`-fenced TOML head, and your
files do not have one yet. `fileplan list` is the worklist. It names **every**
file at once rather than stopping at the first. A file in a state directory
that is not a usable item refuses rather than being skipped. Nothing is
quietly left out of your listing.

The refusal arrives as an `ERROR:` line and one indented line for each further
clause. Each file gets a line of its own and a line saying why, so pick out the
files:

```
$ fileplan list 2>&1 | grep 'not a usable item file'
ERROR: someday-maybe/Q3 2024 retro.md is not a usable item file
  someday-maybe/learn-a-typed-language.md is not a usable item file
  someday-maybe/move-off-the-shared-drive.md is not a usable item file
  someday-maybe/rewrite-the-importer.md is not a usable item file
  adr/0001-store-notes-as-files.md is not a usable item file
  adr/0002-one-binary-not-two.md is not a usable item file
  adr/README.md is not a usable item file
```

That list is the whole job, and re-running `fileplan list` is how you know you
are done.

`adr/README.md` is on the list because a state directory holds items and
nothing else. It is not an item, so it moves out:

```
$ git mv adr/README.md docs/adr.md
```

Most of the rest is one loop. The loop below lifts the `#` title off the first
line into a head, and touches only files that start with `# `. That is what
makes the loop safe to run twice, and what makes it skip the two files that
open with something else:

```
$ for f in adr/*.md someday-maybe/*.md; do
>   first=$(head -1 "$f")
>   case "$first" in "# "*) ;; *) continue ;; esac
>   printf '+++\ntitle = "%s"\n+++\n\n' "${first#\# }" | cat - "$f" > "$f.tmp"
>   mv "$f.tmp" "$f"
> done

$ cat adr/0001-store-notes-as-files.md
+++
title = "Store notes as files"
+++

# Store notes as files

Plain Markdown on disk. Anything that needs a database can build one from
the files; nothing needs the database to read a note.
```

The `#` heading stays in the body on purpose. It is how the file reads in every
other tool that renders your notes, and a retrofit that stripped it would be
editing prose to satisfy a listing.

Run the worklist again and two files are left:

```
$ fileplan list
ERROR: someday-maybe/learn-a-typed-language.md is not a usable item file
  there is no `+++` head on line 1. An item opens with a `+++`-fenced TOML head over its prose, and the head is what every listing reads
  someday-maybe/move-off-the-shared-drive.md is not a usable item file
  "layout" is not a declared key (declared: decided; intrinsic: title)
```

Two shapes the loop could not do for you, and each refusal says which shape it
met. The first is **YAML frontmatter from another tool**, which is not a head
no matter what it holds:

```
$ head -5 someday-maybe/learn-a-typed-language.md
---
title: Learn a typed language
tags: [personal, someday]
created: 2024-11-02
---
```

Rewrite the YAML block as a TOML head, keeping the keys you declared and
dropping the ones you did not. The second refusal is what happens when you keep
a key you did not declare:

```
$ head -4 someday-maybe/move-off-the-shared-drive.md
+++
title = "Move off the shared drive"
layout = "note"
+++
```

`"layout" is not a declared key (declared: decided; intrinsic: title)` tells
you both ways out. Declare `layout` in `[keys]` if it is a fact your work
actually has, or drop the line if it belonged to the tool you are leaving. The
fixture drops the line:

```
$ sed -i '' '/^layout = /d' someday-maybe/move-off-the-shared-drive.md
```

## listing it, and moving something

```
$ fileplan list
Q3 2024 retro              someday-maybe
  title  Q3 2024 retro
  path   someday-maybe/Q3 2024 retro.md

learn-a-typed-language     someday-maybe
  title  Learn a typed language
  path   someday-maybe/learn-a-typed-language.md

move-off-the-shared-drive  someday-maybe
  title  Move off the shared drive
  path   someday-maybe/move-off-the-shared-drive.md

rewrite-the-importer       someday-maybe
  title  Rewrite the importer
  path   someday-maybe/rewrite-the-importer.md

0001-store-notes-as-files  adr
  title  Store notes as files
  path   adr/0001-store-notes-as-files.md

0002-one-binary-not-two    adr
  title  One binary, not two
  path   adr/0002-one-binary-not-two.md

showing 6 of 6 items
```

**Nothing was renamed.** `Q3 2024 retro.md` kept its name and its spaces, and
its handle is the name it has. Filenames are not fileplan's business, which
matters because renaming a note breaks every link into that note you or anyone
else has written.

Each command's own `--help` is its contract. It says what the command takes,
where the item goes, and which sections of *your* prose say what it means:

```
$ fileplan decide --help
Usage: fileplan decide [OPTIONS] ITEM

  Promote a someday-maybe note to a decision record.

Options:
  --decided TEXT  The date the decision was taken.
  --check         Say what this run would do, and stop before writing
                  anything. A refusal under --check is the refusal a real run
                  gives.
  --help          Show this message and exit.

  Where the item goes
    out of someday-maybe and into adr

  Reading
    decide   docs/method.md#decide
    decided  docs/method.md#decided
```

`--check` takes the same path as the run and stops before the first write.
That is how you try a handle you are unsure of, including a handle with spaces
in it:

```
$ fileplan decide move-off-the-shared-drive --decided 2026-09-06 --check
decide would move someday-maybe/move-off-the-shared-drive.md to adr/move-off-the-shared-drive.md

$ fileplan decide "Q3 2024 retro" --decided 2026-09-06 --check
decide would move someday-maybe/Q3 2024 retro.md to adr/Q3 2024 retro.md
```

Take the `--check` off to do it:

```
$ fileplan decide move-off-the-shared-drive --decided 2026-09-06
adr/move-off-the-shared-drive.md

$ cat adr/move-off-the-shared-drive.md
+++
title = "Move off the shared drive"
decided = "2026-09-06"
+++

Two people have overwritten each other this quarter.
```

The file moved between two directories that existed before fileplan did, and
the key it stamped is now a column in the listing. That is the retrofit: your
tree, your names, your prose, read and moved by a declaration rather than by
code.

## what this cannot retrofit

Four things, named here rather than left for you to find out.

1. **Two kinds of file are invisible, with no row and no error.** A file that
   is not `*.md`, and a `.md` in a directory *below* the state directory. The
   fixture's `someday-maybe/scratch.txt` and
   `someday-maybe/archive/drop-the-daemon.md` are both still there, and the
   listing above says `6 of 6`. A state's `path` is one literal directory, and
   its glob is flat on purpose. Pointed at a real working directory, a deeper
   glob would refuse over every `README.md`, `.gitignore` and subdirectory
   beside your items. This is the one place fileplan is quiet about something
   it did not read. If a note seems to have vanished from your listing, check
   those two shapes first.
2. **YAML frontmatter is not a head, and nothing converts it.** The `---` block
   another tool wrote does not become a `+++` head, and its keys do not become
   your keys. It is hand work. Doing it is where you decide which of those
   keys were ever facts about the work, rather than artifacts of the tool that
   wrote them.
3. **A `README.md` in a state directory is a refusal, not an exception.** Move
   the file out, or give it a head and accept that it is an item. There is no
   ignore list. A file in a state directory that cannot be read refuses rather
   than being skipped. A skipped file never appears in a listing you trust,
   and nothing tells you so.
4. **Numbers and positions are not inferred.** `0001-store-notes-as-files.md`
   listed as an item with that handle and no number, rather than becoming
   `number = 1`. Declare a `numbered` or `queued` state later and every
   existing file in it starts unplaced. A queued state lists each unplaced
   file last and names it under `unsorted`. Ordering is a fact an item carries in
   its head, not one recovered from a naming convention. Filling it in for
   existing items is hand work, once.

## growing past the funnel

Two states and one command is a start, not a ceiling. Everything else fileplan
can do is a field or a flag you add to a table you already have. An order, a
claim one session at a time takes, and minted numbers are each a line in
`plan.toml`. So are bullets cut into an item's body, a staleness column read
out of git, templates and dependencies. The example `plan.toml` that
`fileplan init` writes shows an ordered, numbered state and a command that
closes an item out. That is the pair most retrofits want next.
[The method](method.md) describes the rest. Add what your work actually has,
write the section its `doc` field names, and ask `fileplan COMMAND --help`
what the command now takes.
