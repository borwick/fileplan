# The method

What every word in this repo's `plan.toml` means. Each section below is the
**one home** for one meaning. Something names every one of them: a `doc =`
pointer, or an anchored citation from the code that implements it. Nothing
here restates what is written elsewhere.

`plan.toml` holds the *vocabulary* the tool needs to grade items and build the
CLI: which states exist, which transitions move between them, and which keys
an item may carry. The meaning of each of those names is here. The split
between the vocabulary and its meaning is the whole design, and every section
below is one half of it.

## States

A state is a directory, and its `path` says which, relative to the folder
holding `plan.toml`. A state that writes no `path` is at its own name. A
`[fileplan]` table may name a `root`, such as `root = "docs"`, and a state
with no `path` is then at `docs/` and its name. A state that writes its own
`path` is not moved by the root. The bare `fileplan` overview prints every
state's path, defaulted or not.

### someday-maybe

Where an idea lands when it is filed. An idea here has not been committed to
yet. `idea` files one here, and nothing else does.

The state is **unordered** on purpose. A place in an order is what committing
to an item looks like. Nothing here has been committed to, so there is nothing
to put in order yet.

`queue` is the way out. [`merge`](#merge) is the other one: an idea may be
absorbed into another item and deleted. Deleting is safe **here** because
nothing in this state is [numbered](#the-register). A deletion punches no hole
in the register.

### plan

Work that is committed to, **in the order it will be picked up**. The order is
the point of the state. So `plan` opts into the [`queued`](#the-queue)
capability, and every item here carries a place. An item arrives by
[`queue`](#queue) and moves within the order by [`requeue`](#requeue).

A section here also carries a **number**. [`queue`](#queue) mints it on
arrival, and [the register](#the-register) reads it. The number is what the
section is known by once its file is gone and only its archive entry is left.
The number is a key, not a [handle](#the-handle), and not part of the title.

A section here is also **worked in place**. `plan` opts into
[`claimed`](#the-claimed-state). [`work`](#work) is the transition that picks
one up and carries [the cursor](#the-cursor) — which sub-phase the session is
on, and how far it has got. A section is worked where it sits, rather than
moving to a directory of its own, and a claim taken by a transition rather
than by arrival is what makes working in place possible.
[`release`](#release) is the session boundary.

### abandoned

Work that was committed to and then **set aside**: we chose not to do it.
[`decline`](#decline) is the way in, and there is no way out. An item here is
finished with, in one sense: nothing is waiting on a decision about it.

The state declares **no capabilities**. Nothing here is ordered, numbered or
claimed. An order is the sequence work is picked up in, and this work
is not being picked up. The [number](#the-register) the item carried was
dropped on the way out, like every other capability key. What is left is the
item's title, its prose, and whatever declared keys it was carrying.

**Its files are free to delete**, whenever anyone wants the directory tidy.
Deleting one is safe because [`decline`](#decline) files an [archive
entry](#the-register) as it moves the item. The number is spoken for by the
entry rather than by the file, so the register stays contiguous with the file
gone.

Deleting the file changes one thing: [the edges](#dependencies) pointing at
it. Those edges name nothing filed any more, so they turn from *blocked* into
the default read's `unknown dependency:` line. A closed item's dangling edge
is the same loud shape, and it has the same answer. A person takes the edge
out, because the tool cannot tell an abandoned dependency from a typo and will
not guess.

An item left in place is still **filed**, which is the difference between
declining something and dissolving it. An abandoned item has a slug, so it
[resolves](#the-handle). An [edge](#dependencies) naming it reads as
*blocking* rather than as unknown. A plan item may say it waits on something
abandoned, and that item really is waiting on something that is not going to
happen. Somebody should have to read that sentence, which is why declining is
a **move** rather than a deletion.

**The state is [not listed](#listed).** A plain `fileplan list` leaves its
items out and says how many it left out. Set-aside work is finished with, and
reading it on every listing buries the work that is open. `--state abandoned`
lists it.

### carrier

An item that exists to **hold findings** while a question is being answered.
[`investigate`](#investigate) opens one, and [`note`](#note) writes into it. A
carrier holds a body of bullets and nothing else:

```toml
[states.carrier]
path              = "carriers"
capabilities      = ["bulleted"]
sub-phases        = "Findings"
sub-phase-pending = "**pending — The investigation is still open.**"
sub-phase-name    = "f{ordinal}"
```

The `bulleted` capability is the whole of the state. Nothing here is
[ordered](#the-queue), [numbered](#the-register) or
[claimed](#the-claimed-state). An order is the
sequence work is picked up in, and an investigation is not work being picked
up. A number names a section in an archive, and a carrier is never archived. A
claim is one session at a time, and reading a carrier is not holding it.

**The carrier is the state that makes the name form load-bearing.** A
finding's ident is an ordinal the tool supplies on its own, because there is
no register here to take one off. So the form says `f{ordinal}`. Until the
form was declared, [`bulleted`](#bulleted) required
[`numbered`](#the-register), and a state shaped like this one could not be
written down.

**The pending bullet is required here too.** An open investigation reads as
pending. The run that writes the last finding takes the marker out with
`--last`. Forgetting `--last` leaves the carrier saying the question is still
open, which is loud and harmless. The opposite polarity would quietly close an
investigation nobody had finished.

Beside the capability the state declares **[what the carrier was opened
for](#the-dangle-check)** — one state field naming one declared key. A
transition closing a section reads that field to find the carriers opened for
it. The field is read rather than written onto a row, so it gives a row no key
and what the tool derives from it is a refusal.

## Keys

### draft

The document an item's design lives in: the model, the alternatives and the
reasoning the item's own preamble is too short to hold. The value is a
repo-relative path, spelled the way a `doc =` pointer is. So a pointer at
prose has one form everywhere in the tool.

`draft` names a whole **document** rather than a section of one. Which part
an item decides from is prose in the item's body, on its **Decides from**
line. An item may decide from more than one section, and an anchor in the head
beside that line would be two homes for one fact.

No transition this repo declares drops `draft`, which is a fact about this
workflow rather than about the tool. `draft` is an ordinary declared key, and
nothing under `src/` knows the word.

The key is optional. An item carrying no `draft` has no design document, and a
section whose preamble says everything needs none.

**This repo's `draft` declares no [`directory`](#directory).** No item here
carries `draft`, and `docs/drafts/` holds the design every session reads
first. Declaring the directory would report each of those documents as
orphaned on every read, and a report that is always there teaches a reader to
skip it. A workflow that writes one draft per item declares the directory, and
the listing then names a `draft` pointing at no file and a draft that no item
names.

### size

How much work the item is: `S`, `M`, `L`, `XL`. A **closed set**, and an
ordered one. The values are declared in that order in `plan.toml`, which
is what makes `--has 'size>=L'` mean anything. A value outside the set refuses
by name, at the point it is written and at the point it is filtered on.

The key is optional. An item carrying no `size` has not been sized, which is a
different thing from being small.

### sub-phase-status

How far the current sub-phase has got: `open`, `planned`, `in progress`. A
**closed set**, like [`size`](#size), so a typo refuses rather than becoming
one more status. A closed set is the shape [the cursor](#the-cursor) requires
of whichever key a state names as its status.

The words are **this workflow's**, not the tool's, and they are what
[`/do-next`](#work) has always meant by a sub-phase's state. `open` is filed
and untouched. `planned` has a plan saved in `local/plans/`, and is waiting
for a session to work it. `in progress` is being worked now. A workflow whose
sub-phases go *todo / doing* declares those words instead, and nothing in
`src/` changes.

**A sub-phase that is over says so on its own bullet**, as a
[mark](#marking) — `done` here, from a transition that declares
`marks = "done"`. The status key held a fourth word for it once. Written in
both places, completion can disagree with itself, and of the two shapes a head
key is the one that goes stale: a cursor here sat two sub-phases behind what
had shipped. The bullet is also the shape that can say *5 done, 6 open, 7
done*. A real corpus reaches that arrangement routinely, and one cursor naming
one bullet cannot express it at all.

**A sub-phase that is over leaves no status at all.** Every one of the words
says what a session *is* doing, so none of them is true once the work has
stopped. The transitions that end a sub-phase say so by dropping the key
rather than by holding a fourth word. [`finish`](#finish) and [`skip`](#skip)
both declare the drop, because both end a sub-phase.

So absence means two things. The **pair** is what tells them apart, the way
[the cursor](#the-cursor)'s own two silences already do:

| cursor | status | what it says |
|---|---|---|
| absent | absent | nobody has started the section |
| set | absent | the last session finished what it was on |
| set | set | that sub-phase is in flight |

The cursor stays because a cursor is a **true record**. `sub-phase 12-4` says
where the last session was, and that does not stop being so when the sub-phase
ends. The status is the key that would be lying. A head key whose declared
meaning is false is exactly the defect completion-on-the-bullet was moved to
fix, one field over.

The first row is also what keeps a queued, undecomposed section out of the
undecomposed report. The report reads the key's presence. So a section nobody
has picked up is not named, and neither is the *count* of a section whose
sub-phases exist.

### carried-from

The carrier an item was [filed](#filing) from, by its slug. The transition
that files writes the key, never a person. An ordinary declared key is what
makes `fileplan list --carried-from cache-misses` one read: the filter every
key gets is the whole of the machinery.

The key is optional, and its absence is the common case. Most items are not
filed from anything. An item carrying `carried-from` carries
[`carried`](#carried) too: one run writes them both, and either alone would be
half a join.

Nothing clears `carried-from` when the carrier's file goes away, which is
deliberate and is the one place this key differs from
[`after`](#dependencies). An edge says an item *waits on* a live thing.
`carried-from` says where an item *came from*, which stays true once the
investigation is closed.

### carried

The finding an item was [filed](#filing) from, by the name its bullet carries:
`f1`, `f2`, … , the form [`carrier`](#carrier) declares. `carried` sits beside
[`carried-from`](#carried-from) rather than folded into it. Two facts, two
keys. A single key holding `cache-misses/f1` would put a join character back
inside the tool, and a bullet's own ident is what took it out.

A `carried` naming a bullet its carrier no longer has is named by the
listing's `unfound` report ([the listing](#the-listing)). That is what a split
bullet leaves behind until each item is pointed at the half it meant.

### opened-for

The section a [carrier](#carrier) was opened for, by its slug.
[The dangle check](#the-dangle-check) looks the owner up by this key. The
state names it, and a transition closing that section reads it to find the
carriers still holding findings about it.

`opened-for` is written by hand, on the run that opens the carrier, and
nothing writes it afterwards. The value is a slug rather than a pointer into a
document, so there is nothing to keep current as the section moves.

### opened-in

The sub-phase a [carrier](#carrier) was opened for, by the name its bullet
carries. `opened-in` sits beside [`opened-for`](#opened-for), for the reason
[`carried`](#carried) sits beside [`carried-from`](#carried-from). Two facts,
two keys. One value holding `7-4` would put a name form back inside the tool,
and the declared form is what took it out.

The tool reads nothing off `opened-in`. The value is provenance for a person,
and no state field names it, which is what makes `opened-in` an ordinary key
where [`opened-for`](#opened-for) is a field the state points at.

## Item files

### the head

An item is one file: a `+++`-fenced TOML head over a body. The head holds the
declared keys the item carries, one flat line each. The body is prose, which
the tool never interprets and preserves byte for byte.

**A comment inside a head is dropped when the tool writes the file.**
`tomllib` reads TOML and does not surface comments. Keeping them would mean a
second TOML parser beside `tomllib`, and this tool takes two runtime
dependencies. The head is data. Commentary goes in the body, which survives
every write untouched. Dropping a comment is the one lossy point in the
design.

An item's **state is the directory it sits in**. The directory is the only
answer, and a `state` key beside it would be a second one that can disagree
with the tree.

**A run writes the working tree and never writes git's index.** A move leaves
the old path deleted and the new one untracked, and a run that takes an item
away leaves a deletion, all unstaged. Staging is the session's act, because a
sibling session may have its own work in the same index. The recipe is to
stage the paths the run printed, and to `git add` a deleted path, since there
is no `git rm`.

### ignore

[The listing](#the-listing) claims every `*.md` in a state directory to be an
item, and a file that is not one refuses the listing by name. One kind of file
is placed in a state directory without being an item: the file an agent tool
reads from the directory it works in, such as `AGENTS.md`. With that file in
place every `fileplan list` refuses, saying there is no `+++` head on line 1.
`ignore` names such files, and every state directory skips them:

```toml
[fileplan]
ignore = ["AGENTS.md"]
```

The list holds **exact file names**, not globs, so the rule stays one
sentence: a file whose name is in the list is left out of the walk, and every
other `*.md` is still claimed to be an item. A broken item beside an ignored
file still refuses the listing, and the refusal names the broken item alone.

The load refuses a list that could skip nothing, each by name. The value must
be a list of strings. An empty list refuses, since it says nothing. A name
written twice refuses. A name holding a path separator refuses, because the
list holds file names and each one is applied in every state directory. A
name without the `.md` suffix refuses, because the traversal never reads
such a file, so listing it would skip nothing.

Two other shapes were refused. A list built into the tool would put an agent
vendor's file name under `src/`, and would be a rule a consumer has to know
exists rather than read in their own `plan.toml`. Skipping any file without a
`+++` head would make every broken item silently absent, which is the hiding
the listing's refusal was written against.

`show` has no arm for an ignored name. A handle is a slug, and `fileplan show
AGENTS.md` refuses as any handle that matches no item does. A refusal that
says the declaration ignores the file would be a special case with nothing to
buy.

This repo's own list holds two agent files and not `README.md`. A state's
meaning has one home, the section its `doc =` points at, and a README beside
the items is a second copy of that meaning. A consumer may list a README; this
tree does not.

### title

The one line that names the item — **intrinsic**, not a declared key. An item
is a head, a body, a location and a name. The tool knows all of them without
being told, so `[keys.title]` refuses as a redeclaration. A transition's
`sets` naming `title` refuses too.

A retitle is a real transition, and [retitle](#retitle) is its home. The
slug is the item's one handle, so a new title that makes a new slug moves the
file, and every reference naming the old slug is pointed at the new one in the
same run.

The **body is the description**. An item needs a title and a body to exist, so
a transition that creates one refuses without prose.

**A title does not carry a number.** Where a state opts into
[`numbered`](#the-register) the number is a key beside the title rather than a
prefix inside it. Two homes for one fact can disagree, and the one in the
prose is the one that lies.

### list-valued

A key may declare that its head value is **several**:

```toml
[keys.interaction-type]
values      = ["pair", "solo"]
list-valued = true
```

The head then holds a TOML list. Every reader treats the value as
[the several values it holds](#the-listing) rather than as one value: a filter
matches an entry, a comparison compares each entry, and a `refuses` fires on
an entry. The refusal names **that entry** rather than the list. A
`refuses` of `true` fires on any list that is not empty. One filter
asks about the **whole** list instead, and the filter that does is
[`--has 'KEY:VALUE,…'`](#the-listing).

**`list-valued` and `values` answer different questions, and they compose.**
`values` is the closed set an entry may come from. `list-valued` says how many
entries the head carries. A free-text key may be list-valued with no `values`
beside it, and a closed key may hold exactly one.

The option a transition's `sets` gives a list-valued key **repeats** —
`--pest aphid --pest canker` — and its metavar ends in `...`. Click renders no
marker of its own, so an option you may give once would otherwise look
identical. Given no times the option writes **no key at all**, which is what
an option not given has always meant. The empty list is not a value the item
carries.

Shapes that refuse **by name**, each a silent failure rather than a loud one:

* a run that gives a list-valued key **one value**, or a single-valued key
  **a list**. Neither is reachable through the CLI, which always hands the
  shape the declaration asks for. Both are reachable from the executor, which
  is what a consumer's own tooling calls. The refusal comes before the first
  write, so [`--check`](#the-check) gives it in the same words.
* a **field where the tool itself puts or reads exactly one value** naming a
  list-valued key, refused when the declaration loads. The fields are the two
  [cursor](#the-cursor) fields, [the dangle check](#the-dangle-check)'s field,
  and the two [filing](#filing) roles. Each writes or reads a bare value, so a
  list-valued key there would silently hold the wrong shape.

[`dependencies`](#dependencies) is the deliberate exception and refuses
nothing. A bare string is already one edge and a list is already many, so a
list-valued dependency key is the case that works.

A key says it holds several, or it holds one. Holding one is the default,
which is what every key had before the field existed.

### directory

A key may declare that its values are **files in one directory**:

```toml
[keys.sketch]
directory = "sketches"
```

Each value is then a repo-relative path naming a file directly inside
`sketches/`. The listing compares the two sides and says where they disagree:

* **`missing`** is a value naming no file in the directory. That covers a file
  that does not exist and a path outside the directory. A list-valued key is
  asked entry by entry.
* **`orphaned`** is a file in the directory that no item names in that key.
  Every item in every state counts as naming a file, listed or not.

The files in the directory are the `*.md` files directly inside it, the same
rule a [register](#the-register) kept as a directory reads by. A file below a
subdirectory and a file with another extension are left alone. Paths compare
as POSIX paths, so `./sketches/a.md` and `sketches/a.md` name one file, and
`sketches/` and `sketches` are one directory.

Neither report refuses anything, for the reason
[dependencies](#dependencies) gives. A wrong path is a fact to report, and
refusing the listing over one item would hide every other item.

Two shapes refuse when the declaration loads, at every invocation:

* **a directory that does not exist**, or a file where the directory should
  be. A typo there would report every value as missing and no file as
  orphaned, which buries the typo among findings that look real. Create the
  directory, empty if nothing has been written there yet.
* **two keys naming one directory**. A file one key names would read as
  orphaned under the other, and an orphan would stop meaning one thing. The
  refusal names both keys.

`directory` must be a non-empty string, and a key without one is not asked
about paths at all.

### the lock

Every transition that writes holds one exclusive lock, `local/.plan.lock`, for
the whole of its run — creating transitions included. The filename an item
takes is its own reservation. But the check that a slug is free *across every
state* is a check-then-act, and the lock is what covers that check.

`local/` is session-local and gitignored. If another session is holding the
lock, the wait is announced once on stderr, naming the host and pid that hold
it. A silent wait reads as a hang, and a tree may be shared between
sessions.

### the claim

A **claim** says an item is being worked on, by whom, and since when. A claim
lives at `local/claims/<slug>.toml`, one flat TOML table. The record is the
same shape as a head and unfenced, so `cat` shows something a reader can
parse. The slug is the record's location and never a field inside it.

A claim outlives the process that took it, where [the lock](#the-lock) does
not. The lock serializes one write for milliseconds, and the kernel releases
it when its holder dies. A claim lasts a session and is **a file left on
disk**, so nothing reclaims it for free.

**Who a session is, is declared, not compiled in.** `plan.toml`'s
`[identity]` names the environment variables a session's pid may be read
from, in order. The first one that is set wins:

```toml
[identity]
pid = ["CLAUDE_PID", "FILEPLAN_PID"]
```

Another agent's variables, or a `FILEPLAN_PID` you export yourself, go here
instead. A name set to something other than a positive whole number refuses by
name, rather than falling through to the next one. A declaration with no
`[identity]` gives the tool no identity to record. Nothing is assumed in its
place.

An identity is **a host and a pid**. `local/` is gitignored, but a tree may
sit on a syncing filesystem. Records then reach machines that never ran the
session that wrote them. The host is what makes the pid mean anything at all.
The host also tells a person which machine to go and look at.

**A pid is one agent process, not one conversation.** An agent such as Claude
Code runs many conversations in a row inside one process. Its `/clear` starts
a new conversation and keeps the process, so the pid does not change. A claim
the old conversation took is still this session's, and the new conversation
has no memory of it. A sibling cannot free it either, because
[`release`](#release) refuses while the holder's pid is alive. What catches
the forgotten claim is the next claim this session takes, which [refuses and
names it](#the-claimed-state). To ask before that, `fileplan list --has
claim-holder=this-session` [lists what this session holds](#the-claimed-state).

The liveness probe is `os.kill(pid, 0)`, asked only about a record written on
**this** host. On any other host the tool reports the claim as held elsewhere
and never signals anything. The answers are alive, dead, held elsewhere, and
unknown — a record carrying no pid.

**A dead claim is named, never auto-released.** The listing reports the item
as claimed by a session that is gone. Freeing the claim is a command somebody
runs. Nothing changes behind the operator's back. The listing is where you
find out what to fix. The cost is that a crashed session leaves an item that
has to be freed explicitly.

**The known limit is pid reuse.** A dead session's pid can be recycled by an
unrelated process, and the probe would then report a claim alive whose owner
is gone. The failure is in the safe direction. The tool never hands one item
to two sessions. The tool occasionally says a claim is held when it is not,
and releasing the claim is the fix. Closing the hole would cost a second identifier on
every record, or a process start-time check that needs a subprocess this tool
does not take.

**A claim stays on the host that took it.** `local/` is not committed, so a
second clone of the tree sees no claims at all. Committing the claim records
would make that worse. The liveness probe answers only on the host that wrote
a record, so every other clone would read a committed claim as held
elsewhere, and [`release`](#release) refuses a claim taken on another host. A
crashed session on one machine would then block every other machine, and
nobody there could tell whether the session was dead. Every pick and every
release would also cost a commit, in every tree, for a case only a tree
worked from several machines has.

**What crosses clones is the commit.** A head key the claiming transition
sets is committed with the item. In this repo, `work` sets the `sub-phase`
cursor and `sub-phase-status = "planned"`, so a clone that pulls sees which
sub-phase is taken and how far it has got. Where several machines work one
tree, pull before picking an item up, then commit and push the claiming
transition before the work starts. When git refuses the push as not a fast
forward, somebody else got there first: pull, and read the listing again
before going on. A clone that has not pulled still sees the item as free,
because [a missing record means unclaimed](#the-claimed-state), and the
refused push is what catches the collision.

### the claimed state

A state may opt into the **`claimed` capability**. An item in such a state is
being worked on by a single session. Whether an item is claimed lives outside
the item file rather than in its head, so a claim is not a key. A transition's
`sets` or `drops` has nothing to name, and there is no `[keys.…]` to
redeclare.

**The claim is taken by a transition that declares it**, not by arriving:

```toml
[transitions.work]
kind   = "edit"
from   = "plan"
claims = true
```

The two halves say different things. A **state** says items here *are*
claimable, one session at a time, and the listing reports who holds what. A
**transition** says *this transition is the one that picks an item up*.
Coupling the halves — claiming on arrival — makes claiming a consequence of
*moving*, and work then has to move to a directory to be worked on.
[`queue`](#queue) would stamp a claim on every freshly-committed idea, in the
queueing session's name, and nothing would ever release it. Where a file lives
is this workflow's business rather than a mechanism the tool imposes (John,
2026-09-03). So [`plan`](#plan) claims a section **where it stands**.

A workflow that does want claim-on-arrival writes `claims = true` on the
transition that arrives. Arriving takes nothing by default. Both halves are
graded when `plan.toml` is read, and both refuse **by name**. `claims = true`
into a state that does not opt in is a claim with no state to live in. A
claimed state no transition claims into is a guarantee that silently is not
there.

A state that opts in with no [`[identity]`](#the-claim) refuses **by name**
when `plan.toml` is read. A claim records the session that holds it, so a
state that could never say whose a claim is cannot take one.

A transition that claims nothing is still bound by the claim. **The ownership
refusal runs on every transition touching an item in a claimed state.** A
second session cannot walk over work in progress with a transition that
happens to take nothing. And the drop belongs to the state rather than to the
transition: **a claim is dropped on exit**, by whichever transition leaves,
exactly as [the queue](#the-queue) drops a place.

**Taking a claim requires a pid.** Running a claiming transition when none of
the variables `[identity]` names is set refuses by name, saying which to
export. Without that rule two pid-less sessions on one host would own each
other's claims, and the guarantee would quietly become host-level. A record
that already carries no pid is untouched by the rule. Such a record is owned
by its host, so a claim taken at a shell stays completable and releasable.

**A missing record means unclaimed**, deliberately. `local/` is gitignored, so
a fresh clone has items in claimed states and no records at all. Refusing
there would deadlock a tree with no way out, since [`release`](#release) would
have nothing to free either. Reading a missing record as unclaimed fails in
the safe direction.

A **malformed record refuses the listing by name**, which is the other half of
the same rule. A record that is not there means unclaimed. A record that
exists and cannot be read says something the tool does not understand about
who holds an item. Reading an unreadable record as free is the one direction a
claim must never fail in.

Who may move a claimed item: the session that holds it, or anyone when the
item is unheld. A second session's transition refuses **before** the item is
graded.
The refusal is rc 2, naming the holder and what the probe says of it. "This is
not yours" comes before "it lacks a key". A refused transition writes nothing
and leaves the item byte for byte as it was.

A claim this session already holds is **kept** rather than re-stamped, however
many times a claiming transition is re-run. A place is *where in a state* an
item sits, so moving within the state re-places it. A claim is *who took it
and when*, and the same holder re-taking is the same claim. Re-stamping would
lose "since when" for nothing. Keeping the claim is also what lets one
transition both pick a section up and, run again, say where the session has
got to. The alternative is a second transition that would be the same rule
spelled twice.

**A claiming run refuses while this session holds a claim on another item.**
The refusal is rc 2, and it names each item this session holds beside the
`fileplan release` command that frees it. A refused run writes nothing, and
`--check` refuses in the same words. This is the loud polarity. A session that
ended without `release`, or a conversation that was cleared, is found out at
the next claim, which is the moment the forgotten claim matters. Freeing the
old claim silently was turned down (John, 2026-09-29). It would act on an item
the command did not name, and it would hide the mistake the refusal exists to
show.

**`--keep-claims` holds several on purpose.** Every transition that declares
`claims` takes the flag. It allows the less safe thing, so the default stays
the refusal, and a session passes the flag only when it means to hold two.
Ownership here is the same as everywhere else, so a record with no pid on this
host counts as this session's. A **stranded** record does not count: one whose
item is gone, or whose item has moved to a state that claims nothing. [The
listing](#the-listing) already names each stranded record with the `rm` that
removes it, and `release` may not resolve its slug at all. Counting it would
give a refusal whose own fix fails.

**A claiming run given nothing else is supported.** It takes the claim, leaves
the item's file as it was, and exits 0, and stderr says the file is unchanged
because only the claim was taken. A session can therefore claim an item before
a long read and write its result with the same transition afterwards, without
a sibling picking the item up in between.

The item file is written **before** the record. A crash between the two leaves
an item in a claimed state with no record, which reads as unclaimed and is
recoverable. The other order would leave a claim on an item that never moved,
which blocks work and needs a person. Both writes are under
[the lock](#the-lock), and the order decides which half-state a crash leaves
behind.

**To see who holds what**, run [the listing](#the-listing). Every row carries
`claimed-by`, `claim-status` and `claim-holder` where a state claims. `--has
claim-status=dead` is the claims waiting for somebody to free them. `--has
claim-holder=this-session` is what this session holds, which is the read a
session resuming work starts from. Matching on `claimed-by` cannot ask that
exactly: `--has claimed-by~4213` also matches a sibling's pid 42131.

### release

`fileplan release ITEM` frees a claim. `release` is a word of the tool's own
rather than a declared transition, like [the listing](#the-listing). The
command is registered only where some state opts into the capability, the way
the placement options appear only on a transition into an ordered state. Its
**name is reserved either way**. A declared transition called `release`
refuses by name even in a `plan.toml` with no claims, so a tree that adds a
claimed state later cannot break.

`release` takes the [handle](#the-handle) and nothing else — who holds a claim
and since when are read, not typed. The outcomes:

- **Your own claim**: freed.
- **A claim held on this host by a session that is no longer running**: freed,
  naming whose it was.
- **A claim a live session holds**: refuses. A claim is freed when its holder
  is gone, not to take an item off somebody.
- **A claim taken on another host**: refuses, naming the host and the record's
  path. This machine cannot probe that one, so a person there — or `rm` — is
  the only honest answer.

**Nothing is ever auto-released**, which is [the claim](#the-claim)'s rule and
the reason `release` exists. A dead claim is named by the listing and freed by
somebody running the command.

### init

`fileplan init [DIRECTORY]` writes a first declaration. `init` is the tool's
own word, like [release](#release) and [the listing](#the-listing). `init`
answers **before** the declaration loads, as [the version](#the-version) and
[the skills](#the-skills) do. Every other command presupposes a `plan.toml`.
The tree `init` is for is the tree those commands refuse in. So the name is
reserved the way `release` is, and a declared transition called `init` refuses
by name.

What `init` writes is **one shipped example, copied verbatim**: no templating
and no codegen. The example's value is that it is readable and diffable.
Generating the example from a string literal would be the same file with the
reviewability taken out. So the bytes a consumer receives are the bytes the
package shipped.

The example is a **tree** rather than a file — `plan.toml` plus the archive
document its numbered state names, because the declaration does not load
without it. The example names no other document: every `doc` is optional, so
a first tree needs no stub to point at. A tree is what lets the scaffolder
read the example through the real loader instead of parsing it again. The state directories `init` makes come out of that loaded
declaration. Nothing in the tool's source knows what the example calls them.
The example ships as package data, because after an install there is no repo
to walk up from.

What `init` declares is **one loop and nothing else**: two states with
placeholder names, the four transitions of capturing, queueing, working and
closing an item, one key, and the two capabilities the close needs, `queued`
and `numbered`. The starter fits one screen, and the initialization document
says what each line does. The whole
roster — [the queue](#the-queue), [the claim](#the-claim),
[the register](#the-register), [sub-phases](#sub-phases),
[stale-days](#stale-days), the [close and merge](#dissolving) kinds,
`[identity]`, `[fileplan]` — is in this document, one section each. A first
tree files items, moves them and closes them, and does nothing else. Nothing in the roster is a fact about somebody else's work until they
say so. Shipping this repo's own workflow trimmed would be the
planning-shaped default the design refuses.

Every refusal is computed **before the first write**, the way a transition's
are. A refused `init` leaves nothing behind. `init` refuses over a `plan.toml`
here, and over one in **any parent**. Discovery walks up like git, so a nested
declaration would silently shadow the tree above it. `init` refuses over any
single path it would write that is already there.

A tree that merely has work in it is not a collision. `init` succeeds there,
and writes a funnel beside somebody's existing directories rather than over
them. Retrofitting is therefore a walk of its own in `docs/retrofit.md`, and
its first instruction is not to run `init`.

`init` takes no `--check`. A `--check` belongs to a transition and its
[contract](#the-contract). A run of `init` already finds out what would refuse
without writing, because every refusal comes before the first write.

`init` writes **`local/.gitignore` holding `*`**, so the session state the
tool keeps under `local/` — the lock, the claims — is never committed. That
file is the tool's own, inside the tool's own directory, so it edits no
`.gitignore` a repo already has. `init` writes no `.claude/`. Writing one
would compile an agent vendor's directory into the tool. [The claim](#the-claim) keeps that same hazard out of the source for
environment variables. The skills a consumer wants are shipped rather than
scaffolded, and [the skills](#the-skills) is where they are. One flag prints
the directory, and the consumer's own harness says where a copy goes.

The way out is named where a newcomer meets it: the refusal every read gives
outside a plan tree says to run `init`. Nobody has to know the command
beforehand.

### the version

`fileplan --version` prints the number. The option answers **outside a plan
tree**, as [the skills](#the-skills) does. The number is a fact about the
*tool*. Which states and transitions exist is a fact about the workflow. A
stranger who has just installed the package wants to know what they installed,
which is a question about the tool. Refusing to answer tells that stranger the
tool is broken. The tool is merely unconfigured.

`--help` does **not** answer outside a tree. The help is generated per
declared transition. Outside a tree there is nothing to generate the help
from. The refusal `--help` gives already names [init](#init), which is more
use than a help page listing one command. The tool refuses rather than
guessing what an operator without a declaration meant.

**The number is declared once and worded once.** Once in `pyproject.toml`,
read back at runtime through the installed package metadata. Nothing under
`src/` spells a version literal, and there is no `__version__` to drift from
the declaration. And once as a click option, built by a single function that
both the group and the pre-declaration answer use. Two constructions of the
same option would be two places for a `prog_name` or a format to diverge. A
second construction is the same failure as a second declaration of the number,
one artifact further out. The number is bumped by the tool that owns
`pyproject.toml`, never by hand, which is what keeps one declaration true.

**A `plan.toml` can name the oldest release it needs**, in the `[fileplan]`
table, which also holds `root` ([States](#states)) and [`ignore`](#ignore):

```toml
[fileplan]
minimum = "0.7.0"
```

`minimum` is a version of dotted integers, compared number by number, with
trailing zeros ignored, so `0.7` and `0.7.0` are the same release. There is
no maximum and no range. An empty `[fileplan]` table refuses, since it says
nothing.

The minimum is checked **before every other load error**. A `plan.toml`
written for a newer release may use a field the installed tool does not know.
Without the minimum, the installed tool reports that field as the
declaration's mistake. With it, the tool refuses once, naming both versions
and the cure:

```
ERROR: plan.toml needs fileplan 0.9.0 or newer, and this is fileplan 0.7.0: upgrade fileplan to read it
```

**The check has one honest limit.** A release older than the first one to
know `[fileplan]` cannot read the table either. That release says `fileplan
is not a plan.toml table`, which names the table and not the cure.

### the skills

`fileplan --skills` prints the directory the tool's own **interpreter** ships
in. The skills of [the interpreter](#the-interpreter) ship as files, in
whatever place the install put them. The option answers outside a plan tree,
for [the version](#the-version)'s reason. Where the tool keeps its own files
is a fact about the *tool*.

**The tool holds the skills because nothing else can.** A skill is read by a
consumer's agent harness, out of a directory that harness names. This tool
knows no harness. So the shipped copy travels in the package, where an install
of any shape carries it. The consumer's own harness decides where a copy
lands, and [`init`](#init) deliberately writes none.

**Asked of the tool rather than of Python.** The obvious one-liner is to
import the package and print its `__file__`. That one-liner fails for exactly
the install a stranger performs. `uv tool install` puts fileplan in a virtual
environment of its own, and the interpreter a consumer types `python` into is
not that one. `--skills` also serves a tree that already exists, where `init`
refuses and could answer nothing. Where the package is not on a real
filesystem, `--skills` refuses by name. The alternative is printing a
temporary directory that will be gone by the time anybody reads it.

What ships is the generic interpreter and one composition over it. Neither
names a transition this repo declares, which is what makes them worth shipping
at all. A skill that spelled this workflow's vocabulary would be this repo's,
not a consumer's.

**A shipped skill cites nothing the install lacks.** The package carries the
skills and not `docs/`, so a skill points at what travels with the tool:
`--help`, whose `Reading` block names the consumer's own
documents, and `--json`. The skills spell the command as plain `fileplan`, so
a consumer's copy needs no edit, and say once that this source tree runs it
through `uv run`. A test reads the built wheel and follows every link a skill
makes.

`docs/initialization.md` walks the copy.

### the listing

`fileplan list` is the one read, and it is **one traversal with two
renderings**. The listing is a read rather than a transition: it moves
nothing, writes nothing, and takes no lock. The traversal walks the declared
states in declared order. The traversal claims every `*.md` in a state to be
an item. A file that is not an item refuses the listing by name rather than
being skipped. Silence would make a broken file look merely absent. The one
exception is a name the declaration lists in [`ignore`](#ignore), which every
state directory skips. A state whose directory does not exist yet is empty,
not broken.

**States come in declared order, and each state says how its items are
ordered.** A state's `sort` field names one key, in `--sort`'s spelling:
`sort = "position"`, or `sort = "-stale-days"` for descending. Items in that
state come by that key, then by slug. Items in a state with no `sort` come by
slug. [`plan`](#plan) declares `sort = "position"`, so `plan` lists in the
order [`queue`](#queue) and [`requeue`](#requeue) set.

The load checks that a state's `sort` names a key an item in that state can
carry. That covers `title`, every declared key, and the keys this state's own
capabilities and fields give. `position` counts only on a
[queued](#the-queue) state, and [`stale-days`](#stale-days) counts on every
state. Any other key refuses by name, and the refusal lists
what the state carries. A key no item in the state could carry would put every
item under `unsorted` on every read. A mistake in the declaration belongs at
load, not on every read.

`--sort KEY` orders the items **inside each state** by KEY, then by slug, and
replaces every state's declared `sort` for that read. The states keep their
declared order. `--sort -KEY` sorts descending.
Give `--sort` again to break ties, the first key first. A sort compares the
way `--has` does, with one change: a comparison may decline to rank two
unlike values, and a sort must rank every pair. So a value the key declares
comes first, in declared order. A number comes next, by size, so `9` sorts
before `10`. Any other value comes last, as text. That includes a value a
closed key never declared. A list sorts by its entries, in order. An item
without KEY comes after the rest, whichever way the sort runs, and the
listing names it under `unsorted`.

A sort never ranks one state's items against another's. A queued state's
order is a decision made by moving items. A key such as value or cost is only
an input to that decision, so a rank across states would say something
nothing can act on.

The traversal produces a **row**: a mapping carrying every declared key, with
`null` where the item does not carry the key. So the shape a consumer writes
against does not depend on which items happen to be filed. A row reports a
state by its declared **name**, never by its directory — one spelling per
state.

A row names its file by `path`, relative to the folder holding `plan.toml`.
Every other message names a path the same way. That covers a refusal, a
notice, and the path a run prints. So there is one spelling per file too. A
consumer reading a refusal beside a row matches the two without stripping a
prefix. Two paths are named as given. One is `plan.toml` itself, because it
says which declaration was read. The other is any path outside that folder,
which has no relative form.

A row also carries what sits **beside** the item. Where a state opts into the
[`claimed` capability](#the-claimed-state), every row carries `claimed-by`,
`claim-status` and `claim-holder`. `claimed-by` is the holder, spelled
`hostname pid 4213`. `claim-status` is [the liveness probe](#the-claim)'s own
word: `alive`, `dead`, `elsewhere` or `unknown`. `claim-holder` says whether
the holder is the session reading the row: `this-session` or
`another-session`. Ownership is the rule [a claiming run
refuses by](#the-claimed-state), so the pid is compared as a whole number and
a record from another host is never this session's. A record with no pid on
this host is this session's, as it is for the refusal.

The claim fields are read off `local/claims/` rather than out of any head. So
`[keys.claimed-by]` refuses by name, the way `slug`, `state` and `path` do. A
transition naming a claim field refuses too, because the claim fields are read
rather than written and there is nothing to set. The claim fields are `null`
on an item nothing claims. They are present on every row whenever the
declaration claims at all, so the shape does not depend on which items are
filed. They filter like any declared key. `--lacks claimed-by` is the
unclaimed work, `--has claim-status=dead` is what needs releasing, and `--has
claim-holder=this-session` is what this session holds.

Beside the claim fields, every row carries
**[`stale-days`](#stale-days)**: the whole days since the item file's last
commit. The tool reads `stale-days`
out of git rather than storing it anywhere, and writes `null` wherever git has
no answer. `[keys.stale-days]` refuses by name for the reason the claim
fields do, and so does a transition naming it. `stale-days` is derived rather
than written, so there is nothing to set.

More fields come off the item's **own body**, wherever the declaration counts
[sub-phases](#sub-phases) at all: the count itself, then
**`sub-phases-left`**, then [`next-sub-phase`](#the-cursor). Each field has
its home where its meaning is — the count under sub-phases, which bullet to
pick up under the cursor. `sub-phases-left` is at home here, because what
`sub-phases-left` is for is a property of the **read**.

`sub-phases-left` is how many of a section's named bullets carry no
[mark](#marking), which is how much of the section is left. The field counts
what is **left** rather than what is finished, and that polarity is
deliberate. A sub-phase somebody forgot to mark is a number that will not go
down. The number stays on the row, in the default read, saying there is work
in a section that looks finished. Counted the other way round, the forgotten
sub-phase would be an increase that never happened, which looks like nothing
at all. `0` is a real value and prints. A section that is finished says so out
loud, rather than by a field going quiet. `sub-phases-left` is also the number
the [close check](#the-close-check) refuses a close-out with, off the same
reading of the same bullets. So the row and the refusal cannot come to
disagree about one body. The field filters like any other: `--has
sub-phases-left=0` is the sections with nothing left in them.

Last among the derived fields, every row carries
**[`commands`](#commands)**: what could take the item right now, wherever
some transition starts from an item. `--has commands=VERB` is what `VERB`
could take.

**An empty tree says how to file the first item.** Where the traversal
found nothing at all, the text form ends with one line per create
transition, such as ``Nothing is filed. `fileplan capture TITLE --body
TEXT` files one in inbox.`` A listing that filters a tree down to nothing
says nothing more, because the tree is not empty.

A claim belongs to an item **in a claimed state**, and every other record is
**stranded**. There are two kinds. One kind's slug names no item. The other
kind names an item that has since moved to a state which claims nothing. A
transition already keeps that same rule, so the listing and the transition
agree. Otherwise one of the two would report a claim the other will not
honour. A stranded claim is **named, never filtered and never removed**. Each
stranded claim is one line on stderr in the text form, and one entry in a
`stranded` array in `--json`'s envelope. The array is present whenever the
declaration claims. [`release`](#release) or `rm` is how a stranded claim goes
away. The tool never removes one for you.

Every **exception report** the listing carries works the way a stranded claim
does. Each report is a line per record on stderr in the text form, and its own
array in the envelope under `--json`. Each report is computed over the whole
tree, and narrowed by no filter. These are the reports:

* `stranded` is a claim with no item.
* `undecomposed` is a started section carrying no [sub-phases](#sub-phases).
* `unknown` and `misordered` are the two [dependency](#dependencies) reports.
* `unresolved` is a [reference](#references) naming nothing filed.
* `gaps` is a number in neither its state nor that state's archive. `lost` is
  an archive heading the register cannot read. Both belong to [the
  register](#the-register), which is their one home.
* `unmarkable` is a bullet no transition could mark: unmarked, and carrying
  text after its bold run. The listing says so before a session reaches for
  the command. [Marking](#marking) is where the rule lives. Each record
  carries the item's `path` and the bullet's `line`. The `line` counts from 1
  over the whole item file, head included. So `path:line` is where an editor
  opens.
* `undeclared` is a head value its key's `values` do not declare. A verb
  grades a value when it writes one, and nothing grades it again, so a hand
  edit lands here. Each record carries the item's `slug`, the `key`, the
  `value` and the `path`, one per entry of a list. It gates nothing, for the
  reason [dependencies](#dependencies) gives.
* `missing` is a value of a key declaring a [`directory`](#directory) that
  names no file in that directory. Each record carries the item's `slug`, the
  `key`, the `value`, the item's `path` and the `directory`, one per entry of
  a list.
* `orphaned` is a file in a key's [`directory`](#directory) that no item
  names in that key. Each record carries the `key`, the `directory` and the
  file's `path`, so `path` is what an editor opens.
* `unread` is a bullet the reader passes over that was plainly meant as a
  sub-phase. [Sub-phases](#sub-phases) says which two cases it names. Each
  record carries `item`, `name`, `line`, `path` and a `reason`. The `name` is
  what the name would be, or `null`.
* `unfound` is a [`carried`](#carried) value naming a bullet that its
  carrier, the item [`carried-from`](#carried-from) names, no longer has. A
  split bullet leaves one behind. It is reported only while the carrier is
  filed, because provenance outlives the carrier. Each record carries `slug`,
  `path`, `key`, `value` and `carrier`. It gates nothing.

The reports stay separate arrays rather than one merged list of notices. Each
report carries a different shape, and the envelope key is how a consumer
selects the report it cares about.

**The envelope is one object, and these are its fields.** Every read carries
`version`, `kind`, `matched`, `read` and `rows`. The rest are arrays, each
present whenever the declaration could fill it and absent otherwise:

* `version` is the envelope's version, an integer.
* `kind` names the read: `items` for `list`, `item` for `show` and
  `sub-phase` for `show ITEM NAME`. It is a word, never the array. The rows
  are always under `rows`.
* `matched` is how many rows the read returns, and `read` is how many the
  traversal walked.
* `stranded` is present wherever a state claims.
* `undecomposed` is present wherever a state carries a cursor.
* `unknown` and `misordered` are present wherever a state reads dependencies.
* `unresolved` is present wherever a state declares references.
* `gaps`, `lost` and `register` are present wherever a state is numbered.
  `register` is not a report, and [the register](#the-register) is its home.
* `unmarkable` is present wherever a command marks.
* `unread` is present wherever a state counts sub-phases.
* `undeclared` is present wherever a key declares its values.
* `missing` is present wherever a key declares a directory.
* `orphaned` is present wherever a key declares a directory.
* `unfound` is present wherever a command [files](#filing) an item.
* `unsorted` is present wherever the read sorts anything: `--sort` was given,
  or a state declares a `sort`. It names each row the read put last for
  missing a sort key, and covers only the rows shown.
* `unlisted` is present wherever a state is not listed, on `list`. It names
  each state the read left out and how many rows it lost.
  [`listed`](#listed) is its home.
* `rows` is the rows, always last.

**What `version` promises.** It goes up only when a field is removed, or
changes type. A field added is not a change a consumer parsing the old shape
could trip on, so it is not a bump. That is why the envelope is an object
rather than a bare array. What each command takes is a different contract,
read with [`fileplan --json`](#the-contract).

Both renderings come off the row and nothing else. The text form is a
multi-line record per item. The text form drops a key the item does not carry,
because omission is how a record spells "absent". `--json` is one object on
one line and keeps the `null`s. A consumer can test `null` and cannot test a
dash. Neither rendering walks the tree itself, so the two cannot disagree.

`--json` puts the counts in its envelope and leaves **stderr silent**, so a
consumer parses one thing. In the text form the counts go to stderr, so
`fileplan list | ...` carries the records and nothing else. A refusal emits
**no JSON** either way: rc 2, an `ERROR:` line and one indented line for each
further defect, empty stdout.

There are **three** filters, and several narrow together. `--has
KEY[OP]VALUE` is the filter over a key. `--has` names a key, then says
something about that key. A value may carry a **comparison**: `--has
'size>=L'`, `--has 'stale-days>=14'`. A key with declared `values` orders by
that list. So `>=` means something only because `plan.toml` puts the values in
order. A key the filter does not know refuses by name, listing what an item
can carry. A field the row reads off the tree (`slug`, `state`, `path`) is not
a key. It refuses as a row field, and `state` points at `--state`. A value
outside a key's `values` refuses by name too.

`:` reads as **drawn from**, and `:` is the one operator naming several
values. `--has 'pest:aphid,scab'` asks whether every value the key carries is
one of the named values. Over a [list-valued](#list-valued) key, `:` asks the
subset question. Over a single-valued key, `:` degenerates to "is one of". So
`:` is one rule rather than a special case for a list-valued key. Each named
value is refused against the key's `values` on its own, so a typo among them
names itself. A declared value carrying a comma cannot be named this way. A
`:` naming no value refuses rather than matching nothing.

`~` reads as **contains**. `--has 'title~review'` finds every item whose
title holds the word, ignoring case. Over a list-valued key it asks each
entry. It is a substring and not a pattern, because a pattern would be a
second language to document. The body is not searched, since the body is not
in the row. A key with declared `values` refuses `~` by name. Those values
compare by order, so a substring of one is the wrong question.

`--has` reaches **every key an item can carry** — intrinsic, declared, given
by a capability, and derived from outside the item file — off one roster. So
no key needs a filter of its own: a key that reaches a row reaches `--has`.
`--has KEY` with no comparison asks about **presence**. A key present but
empty carries nothing, the same rule `requires` uses. `--lacks KEY` is the
opposite question and keeps its own word.

The two operators asking about a value **differ on an item carrying nothing**,
and each polarity is deliberate. `--has 'KEY!=VALUE'` is true of that item. An
item with no `size` is genuinely not `L`, and absence is what `--lacks` asks
about. `--has 'KEY:VALUE,…'` is false of that item. `--has` is the presence
word, and a guard has to be conservative about an item saying nothing.

`--state [OP]STATE` is the third filter, and the one that is not a key.
`--state` says where an item **is**, which is the tool's own axis rather than
the workflow's vocabulary. The declared states are a closed list like a key's
`values`. So `--state '!=plan'` is spelled the same way, and `--state zzz`
refuses by name rather than matching nothing. `--state ':plan,carrier'` is
that operator over the same closed list, and nothing reaches for it.

**`--state` is given once.** `--has` and `--lacks` repeat and narrow
together, so a repeated `--state` looks as if it should too. Click would keep
the last one and drop the rest without a word. So a second `--state` refuses,
naming both. `fileplan list plan` names a state as an argument, and click
refuses it. The line after click's says `did you mean --state plan?`.

A state can leave its rows out of a `list` given no `--state`, and the read
says what it left out. [`listed`](#listed) is that field's home.

A bad filter refuses **before the tree is walked**. The parse is where a
refusal happens, so `--state zzz` costs no traversal to reject.

[`show`](#show) is the same read again, narrowed by a handle rather than by a
filter. `show` takes no filter at all.

### listed

A state may declare `listed = false`. A `list` given no `--state` then leaves
that state's rows out. This repo's [`abandoned`](#abandoned) declares it:

```toml
[states.abandoned]
path   = "abandoned"
listed = false
```

**A state left without the field is listed.** So a forgotten field hides
nothing. `listed = true` is legal, and it is the default written out. Any
value that is not `true` or `false` refuses at load by name.

**The read says what it left out.** After the `showing 4 of 7 items` frame,
the text form prints one line on stderr for each state that lost a row:

```
not listed: abandoned (3). --state abandoned lists them
```

The frame's second number is still everything the traversal walked, so the
`4` and the `3` add up to the `7`. A state that lost nothing gets no line.
Hiding the rows without that line would make abandoned work look gone.

**Any `--state` turns the hiding off.** `--state abandoned`, `--state
'!=plan'` and `--state ':plan,abandoned'` are all comparisons, and the
comparison does the narrowing. So a state is shown whenever `--state` names
it, and there is one rule rather than one per operator. [`show`](#show) names
its item, so it finds an item in an unlisted state too.

**The other filters do not turn it off.** `--has commands=discard` still
leaves the unlisted rows out, and the line counts the rows the hiding took
**after** the filters. So `list --has commands=discard` says `not listed:
abandoned (2)` when two abandoned items matched. That count is what makes a
miss loud: the read says there were matches it did not show.

**`--json` leaves out the same rows as the text form.** Both renderings come
off one list of rows, and a JSON read that disagreed with the text read would
be two answers to one question. The envelope's `unlisted` array says what was
left out instead: one `{"state": "abandoned", "count": 3}` record per state,
in declared order. The array is present on every `list` wherever some state
is not listed, and it is empty when nothing was left out or `--state` was
given. `matched` counts the rows shown and `read` counts the rows walked, as
they always do. A program that wants the rows passes `--state`.

**The exception reports are unchanged.** They are computed over the whole
tree, and no filter narrows them. So an `unknown dependency:` line still names
an item in an unlisted state. Leaving rows out of the read hides no problem.

[`fileplan`](#the-contract) with no command marks the state `not listed` in
its overview, and `fileplan --json` gives each state a `listed` field. So the
default can be read back without opening `plan.toml`.

### commands

Every row carries **`commands`**: the commands that could take the item right
now, in `plan.toml`'s order, or `null` where none could. The field is present
whenever some transition starts from an item, whatever is filed.

```
lower-the-floor                                   plan
  ...
  commands  requeue, retitle, decompose, work, decline
```

A command is named when everything its own run checks about the item holds:

* the item is **in the transition's `from` state**;
* the item's head satisfies everything the transition [`requires` and
  `refuses`](#transitions), counting a required option as met, because the
  run supplies it;
* no **other** session holds the item's [claim](#the-claim), where the
  transition enters or leaves a claimed state;
* no open [carrier](#carrier) names the item, where the transition is a close
  that archives ([the dangle check](#the-dangle-check));
* every sub-phase carries a mark, under the same close ([the close
  check](#the-close-check));
* the item carries a number, where the transition archives ([the
  register](#the-register));
* no bullet in the body is one the reader passes over, where the transition
  writes or marks a bullet ([sub-phases](#sub-phases)), and the item carries
  what its state's name form needs, counting any key the run writes;
* for a [mark-bullet](#marking), the item has a bullet a mark could still go
  on.

Each check is the function the run refuses through, composed once rather than
spelled a second time. So the row and the run agree by construction, instead
of by a test that two lists match.

**What could a command take is a filter.** `fileplan list --has
commands=archive-plan` is the sections that could close right now, which is
the old tool's `--closeable`. Earlier releases spelled it as a third read,
`fileplan next COMMAND`. Folding it into the row left two reads, `list` and
[`show`](#show), and every filter, sort and rendering a listing has.

**A transition that stays in its state is named again after it runs.**
Running it again is legal. A workflow that means "once" says so in the
declaration, with `refuses = { KEY = true }` on the key the transition sets
([transitions](#transitions)).

A claim excludes an item only when the claim is **another session's**. A
transition keeps a claim the running session already holds, so the section
this session picked up yesterday still names `work` today. `--lacks
claimed-by` is how you ask the stricter question: work nobody at all has
picked up.

A transition with **no `from` creates** an item, so no row ever names it.

**The row grades one item.** A transition can still refuse for a defect in
the **tree**, such as a gap in the register, or over the values a particular
run was given. Those block every item alike, and [`list`](#the-listing) is
where a tree defect is reported. So a row can name a command the run then
refuses. What a row cannot do is leave out a command the run would have
taken.

The row answers **yes or no and never why not**. [`--check`](#the-check) is
where a single item asks why not, and `--check` asks the transition rather
than a second copy of the rules.

**A mark-bullet's subject is one bullet, not the item.** The row names the
command while any bullet is left to mark. Which one is the next is
`next-sub-phase` ([the cursor](#the-cursor)), and [`show ITEM NAME`](#show)
reads one bullet. A bullet carrying text after its bold run cannot be marked,
and the listing reports it rather than counting it as left
([marking](#marking)).

**A usage error points here.** A transition run with no `ITEM` says
`fileplan list --has commands=VERB` is the way to see what it can take.
`show` and `release` are not transitions, so theirs is `fileplan list`.

### show

`fileplan show ITEM` is [the listing](#the-listing)'s row for **one item**.
The item is resolved by [the handle](#the-handle) rather than by a filter.
ITEM may also be a live section's number, such as `28`, and `show 28-1` is
the same read as `show ITEM 28-1`. `show` is the one verb that names an item
and writes nothing, so it is the one verb that reads a number.
`show` is the same traversal again — one walk, both renderings off the same
row. So `show` prints what `list` would print, narrowed to one item.

`show` takes **no filters**. A filter narrows a *set*, and `show` has already
been told which item. Worse, `--state` on an item that is somewhere else would
report "no such item" about an item that plainly exists. `show` reporting no
such item is the exact failure tree-wide resolution was adopted to end. The
one flag `show` does take is `--json`, because how a row is rendered is not a
narrowing.

`show` prints the **row**, never the body. `cat` the `path` the row names to
read the prose. What the row adds is everything the file does not hold —
`claimed-by`, `claim-status` and `claim-holder`, `blocked-by` and `blocks`,
`stale-days`, `commands`, and the fields counted off the body. Putting the body in the row would put the body in
*every* `list --json` as well. The token budget rules that out. Putting the
body in only one rendering would break the very thing that makes both
renderings agree.

The one exception is a **bullet**. `fileplan show ITEM NAME` prints that
bullet of the item's body and its continuation, verbatim, and nothing else on
stdout. The body still never reaches a *row*, because a bullet read is not a
row read. A bullet has its own record in both renderings, carrying `name`,
`item`, `title`, `mark` and `text`, and its own `kind`. So a consumer can tell
a bullet record from a row off the envelope. The record carries the same facts
the verbatim lines carry, not more. `title`, `mark` and `text` are extracted
*from* the lines a person reads. The three extracted fields are shaped for the
audience that would otherwise re-parse the bold.

[`annotate`](#annotate) is the write that pairs with this read: it writes the
continuation that `show ITEM NAME` prints.

A bullet read is `show` narrowed one step further. A
[mark-bullet](#commands)'s subject is a bullet, so a bullet is already a
subject of the read surface. `show ITEM NAME` narrows to one. A finding
in a [carrier](#carrier) can therefore be read one bullet at a time. The
alternative is opening a file that may run to a hundred thousand tokens. A
fenced transcript inside a finding comes back whole, because [a fenced line is
not a line at all](#sub-phases).

A name the body has not got refuses in the same words a disposition refuses
one. The refusal comes out of the same code. An [unnamed bullet](#marking) and
the state's pending marker are dropped by the reader both `show` and the
disposition gate on. So each refuses as "no such name" rather than through an
arm of its own. An item whose state counts no sub-phases refuses by name.
There is nothing in such an item for a name to point at.

The counts frame and every [exception report](#the-listing) are the **whole
tree's**, unnarrowed. [The register](#the-register) is unnarrowed too, in
`--json`'s envelope. The frame under `show` reads `showing 1 of 12 items`. The `12` is what the traversal read, which is what the frame counts
of. A read that hid a stranded claim or an unknown edge because you asked
about one item would be the first read to hide one.

### the contract

`fileplan COMMAND --help` is what a transition promises. First the options the
command takes, then the **contract**. The contract says where the item goes,
what the transition requires, what it refuses, and what it takes off the head.
The contract also says the transition's [kind](#kinds) and the options it
declares, and names the sections that hold the meaning of all of it.

```
Where the item goes
  stays in plan

Declares
  edit
  claims

Reading
  work              docs/method.md#work
  sub-phase         docs/method.md#the-cursor
  sub-phase-status  docs/method.md#sub-phase-status
```

The contract is generated from the same `Transition` the command itself is
generated from. So a consumer's transitions get the same contract, and no
transition of this repo's is written anywhere in the tool.

The **`Reading` block** hands the pointers over. `doc =` has been graded at
every invocation since the loader existed. A pointer at a document the repo
does not ship refuses. The transition's own `doc` is the **program**: the
section that says what running this transition means, and what a session reads
before doing the work. Each key the transition takes as an option names the
section that says what the key's value means, and so does each key a filing
transition writes onto the filed item. The key's `help` was always on the option, and
the `help` says what to pass rather than what the key is.

**`doc` is optional on every entry.** A transition or a key whose meaning
needs no section of its own names none, and its line is left out of
`Reading`. A transition naming none, with no key naming one either, carries
no `Reading` block at all, and then its `help` line is the whole of what a
session reads. That pulls against the design's rule that the process lives
in documents a transition points at, and the way through is that the rule
is still kept by any workflow that writes a section: the pointer is graded
exactly as before wherever it is given. What changed is that a new repo is
no longer made to write an empty heading per word before its first run.

The tool surfaces the pointers rather than leaving a reader to find them. A
skill that opened `plan.toml` to look up a pointer would be **a second parser
of the declaration**. The skill is the one artifact whose whole premise is
that it interprets rather than reimplements.

`Reading` is keyed by name. So a transition setting a key of the transition's
own name refuses at load. The two pointers would share one line, the key's
pointer would win, and the transition's own program would be lost. The loader
names the collision rather than dropping a pointer.

A key refused on presence reads `KEY (any value)` in `Refuses`, and `true`
under `refuses` in `--json`, the way `plan.toml` spells it.

`Drops` sits with `Requires` and `Refuses`, because `Drops` is the same
subject read one step later. `Requires` and `Refuses` say what the head must
hold for the run to go. `Drops` says what the head will not hold afterwards.
`Drops` stays **out** of `Reading`, which names what the values a session
*supplies* mean. A dropped key has no value to mean, and the key's own section
is one `fileplan` read away. A transition that drops nothing carries no `Drops`
block, the shape `Files` already has.

A transition that writes a [fixed value](#transitions) carries a **`Writes`
block**, after `Drops`. It is the same subject: what the head holds after the
run. Each line is one value, written as declared, so `{today}` reads as
`{today}` rather than as a date:

```
  Writes
    status = "accepted"
    decided = "{today}"
```

A fixed value stays out of `Reading` too, because no session supplies it. In
`--json` the block is `writes`: the table of fixed values as declared, `{}`
for a transition that writes none. `sets` keeps its meaning there, the keys
the run takes as options. A required option is `"required": true` among the
`options`, and `[required]` beside the option in `--help`.

A transition that [files](#filing) an item carries a **`Files` block**, after
`Declares`. The block says where the filed item goes and which keys the run
writes onto it: `into someday-maybe, writing defect`. Every other option a run
takes for a key lands on the item the run moves. So the `Files` block is how
`--help` says which item each key lands on. In `--json` the block is `files`:
the declared table with its `sets`, or `null` for a transition that files
nothing.

**`--help` describes the declaration.** [`list`](#the-listing), [`next
COMMAND`](#commands) and [`show`](#show) walk the **tree** and are the
whole of that read surface. `--help` and the bare `fileplan` table of contents
answer a different question, with different answers and no items in them.
Nothing in a contract counts, filters or resolves a handle.

**`fileplan --json` renders every contract at once.** The bare table of
contents grows the flag, and the flag renders the whole declaration. The
states come first, then one object per declared transition. Each object
carries every block above, under the block's own name. So a composing session
asks once, instead of running `--help` per command. In `--json`, `kind` is
its own field and `declares` holds the options alone. `Declares` alone is not
always the answer, because two transitions can share a kind. `Reading` is
what tells two edits apart, and `Reading` is in the same read.

The states carry a name and a path, as the text prints them. What a
declaration says about itself is already in the consumer's own `plan.toml`.
What only the tool knows is what the tool **derives** from that file.

Every key is present always, empty where the text would omit the block. The
shape a consumer writes against must not depend on which transitions a
declaration declares. [The listing](#the-listing)'s rows do not depend on
which items are filed, for the same reason. The text form goes on omitting an
empty block, because a person reading help wants the blocks that say
something.

**The JSON also says what each command takes**, so a consumer never has to
scrape `--help`. Each transition's object carries `options`, one entry per
option `--help` prints, leaving out `--help` itself. An option entry has six
fields:

* `name`, the spelling, such as `--title`;
* `takes`, the placeholder `--help` shows, or `null` for a flag;
* `required` and `multiple`, each `true` or `false`;
* `values`, the allowed values of a key with a closed set, or `null`;
* `help`, the option's help text, or `null`.

The entries are read off the same click parameters `--help` renders, so the
JSON and the help cannot disagree. A test runs `--help` for every command and
holds each option it prints to the JSON.

`commands` holds the tool's own words: `list`, `show`, `init`, and `release`
where some state is claimed. Each command has a `name`, a `help`, `options`
and `commands`, which is empty: none of them nests another. The tool's own
words are not transition objects, because a transition object's `from`, `to`
and blocks would all be empty for them.

`keys` holds every declared key, with its `name`, `help`, `doc` and `values`.
`values` is the closed set, or `null` for free text.

Adding these fields did not change `version`. A field added is never a bump,
as [the listing](#the-listing)'s "What `version` promises" says.

A command beside the flag **refuses**. `fileplan --json list` asks about the
declaration and about the tree at once. A read spells its own `--json`, after
the command. Both renderings come off one function. So a block cannot reach
the help text without reaching the data first.

### the check

`fileplan COMMAND ITEM --check` says what that run would do, and does none of
it.

* if the transition would **take** the item, the check prints one sentence on
  stdout and exits 0. The sentence reads `work would rewrite
  plan/a-section.md, which stays in plan, and would take the claim`;
* if the transition would **refuse** the item, the check gives the refusal a
  real run gives: rc 2, the `ERROR:` lines on stderr, nothing on stdout.

The refusal is the real one because there is **one path**. `--check` is the
run, stopped at the seam, rather than a second implementation of the
preconditions. Every arm of the executor already resolves everything it needs
before writing anything. Resolving first is what makes a refusal leave the
tree byte-identical. So the check returns at the seam instead of carrying on:

| the kind | the seam it stops at |
|---|---|
| `create` | the reservation, `open("x")` on the destination |
| `close` and `merge` | `unlink()` on the item |
| every other kind | the write, inside `_place`, after the head is graded |

A check that could disagree with its run would be exactly the second home the
flag exists to avoid. So nothing is extracted into a shared prefix, and
nothing branches earlier than those seams. The check takes the run lock too. A
check that took a different path to avoid the lock would be a second path, and
runs are brief.

The sentence is built from the effects the run has **already computed**. The
effects are the place and number the run would write, the keys it would take
off the head, the claim, the archive entry, and the edges it would clear. None
of those effects is re-read off the declaration, so the sentence cannot claim
something the run would not do. [The register](#the-register) computes its
notices from what the head actually got, for the same reason.

The dropped keys are named `drop <key>` beside the writes. A run that quietly
removed a key the check had not mentioned would be doing something the check
did not say. Saying so first is the whole of what the flag is for. A
transition whose `drops` names a key **this item does not carry** removes
nothing, so the check says nothing about that key. Absence is an answer here,
not a gap.

**A run that would leave the item's file as it was is checked as one.** The
check says `would leave PATH unchanged`, then the reason the run itself prints
on stderr. Both come from one comparison: the bytes on disk against the bytes
the run would write. A check that said "would rewrite" for a run that writes
nothing would be claiming something the run does not do. A run that stays in
its state names only the head values it changes. A place and a number the
item already holds go unsaid, which is why the example above names neither.

**Every** generated transition carries `--check`, a creating transition
included. A creating transition's filename reservation is a write that happens
partway through. A rule that skipped creating transitions would leave an empty
file behind on every check.

`--check` checks a **run**, not a transition in the abstract. A run's required
options are still required, and `archive-plan --check` still wants its
`--record`. The question `--check` answers is "what would *this run* do". A
check that quietly accepted a different set of arguments would be answering
about something else.

There is no `--json`. A check is about **one run**. What the tree holds is
[`list --json`](#the-listing), and what the declaration holds is [`fileplan
--json`](#the-contract). A check answers neither question. The check's
consumer is the agent about to act, and one sentence is what that agent needs.
A second rendering with no reader is recorded rather than built, the way [the
listing](#the-listing) does.

A declared key called `check` refuses **by name** when the command group is
built. A key called `body`, `above` or `last` refuses the same way. The flag
is generated on every transition, and one option cannot mean two things. The
reserved words are a **roster** — `check`, `note`, `record`, `into`, `from`,
`above`, `below`, `at`, `title`, `last`, `body` — and this list is where the
roster is kept. The constants that spell those words are in `src/`, one per
option beside the check that reserves it. Nothing in `src/` gathers them.
Each collision still refuses in its own sentence, because each sentence says
what its option is *for*. A **transition** of the same name is a different
namespace and stays legal. A key and an option meet on one command line; a
transition and an option never do. So this repo can declare [`note`](#note)
while every marking transition takes [`--note`](#marking).

### kinds

Every transition says what kind of transition it is, in one field:

```toml
[transitions.decompose]
kind = "add-bullet"
doc  = "docs/method.md#decompose"
help = "Write the next sub-phase into a section."
from = "plan"
```

There are ten kinds, and the kind decides which other fields the
transition takes. A field the kind does not take refuses by name, and the
refusal lists the fields the kind does take.

| Kind | What it does | `from` and `to` | Its own fields |
|---|---|---|---|
| `create` | writes a new item | `to` only | `sets`, `claims` |
| `move` | moves an item to another state | both, and they differ | `sets`, `drops`, `claims`, `archives` |
| `reorder` | changes an item's place in a queued state | `from` only | none |
| `edit` | writes keys, or takes a claim, where the item is | `from` only | `sets`, `drops`, `claims` |
| `rename` | gives an item a new title and slug | `from` only | none |
| `close` | takes the item's file away | `from` only | `archives` |
| `merge` | takes the item away into a survivor | `from` only | none |
| `add-bullet` | writes the next bullet into the item's body | `from` only | `sets` |
| `mark-bullet` | writes a word onto one bullet | `from` only | `marks`, `sets`, `drops`, `files`, `merges` |
| `write-bullet` | writes text under one bullet | `from` only | none |

Every kind that starts from an item also takes `requires` and `refuses`, and
every kind takes `doc` and `help`. A transition with no `help` gets one from
its kind, said with the states it names: a move from `inbox` to `plan` reads
"Move an item from inbox to plan." A repo writes `help` only to say something
better. A kind that stays in its state
writes only `from`, because the item does not go anywhere. A `to` beside it
refuses, rather than being ignored. A `close` or a `merge` names no `to` at
all, because the item lands nowhere.

Three rules go beyond the table. A move whose `to` is its `from` refuses, and
says to write `edit` or `reorder`. A reorder refuses in a state that is not
`queued`, because the items there have no order to change. An edit that names
no `sets`, no `drops` and no `claims` refuses, because it would write nothing.

**Why a kind is declared.** Before kinds, a transition never said what
it was. Six true/false fields said it between them, and each refused some of
the others: `mints` and `marks` could not go together, `absorbs` needed
`dissolves`, and `dissolves` refused a `to`. A reader had to learn those rules
to predict which options a command would take. The command line was then
worked out from the fields in many separate places. Every transition in this
repo, in the starter and in the consumer's workflow fits exactly one kind, so
the kind is now written down and those rules collapse into the table above.

A plan.toml written before kinds refuses by name, and the refusal says the
line to write. The kind it suggests is read off the fields that used to spell
it: no `from` is a create, `mints` an add-bullet, `marks` a mark-bullet,
`retitles` a rename, `dissolves` a close, and `dissolves` with `absorbs` a
merge. A `to` that differs from `from` is a move. A transition staying where
it is becomes an edit if it writes a key or a claim, and a reorder if it does
not. The four fields that did nothing but spell a kind (`mints`, `retitles`,
`dissolves` and `absorbs`) refuse by name too.

### the interpreter

One skill runs any single declared transition, and the sections the contract
names are the program that skill runs. The skill asks the tool for the
[contract](#the-contract), then asks with [`--check`](#the-check) whether this
item passes. The skill then reads the sections the contract names, does what
those sections say, and runs the command. The skill branches on the
[kind](#kinds) and the options the contract says the transition **declares**,
never on the transition's name. So one procedure covers a create, an edit and
a close. A stranger can follow the same procedure for a transition nobody has seen
before.

Nothing in the skill is this workflow's. The worked example is *generated*:
step one is `fileplan COMMAND --help`, so the example a reader gets is the
command they actually have.

**A procedure is reached by a link from the transition's own section.** The
`doc` a transition names says what the transition and its values **mean**.
Where a session also has something to **do** around the run — questions to
ask first, what a value commits you to, what the run costs that nothing else
warns about — that section links to a section of the procedures document:

```
What a session does around a run of `decompose` is [decomposing a
section](procedures.md#decomposing-a-section).
```

Most transitions have no procedure beyond their meaning, and their section
links to none. One pointer per transition keeps the declaration to one field
for one question. Earlier releases had a second field, `policy =`, and a
`Running it` block in the contract. A plan.toml that still declares `policy`
refuses by name and says to move the link into the section. This repo's
tests grade that every section of the procedures document is linked from the
section of a transition that uses it.

The claim is taken by **the run**, not before the run. A claim is taken by a
transition that declares `claims` ([the claimed state](#the-claimed-state)),
so there is no generic way to take a claim first. A transition invented to
take one would be a second spelling of a state's rule. `--check` is the
ownership guard instead: the foreign-claim refusal runs on every transition
touching a claimed item, checks included. Two sessions can both check, and
only one run can succeed. The window between them costs wasted effort rather
than a collision. The guarantee that two sessions never hold one item is the
claim's.

The postconditions need nothing new. Every refusal a transition can raise is
computed before that transition writes anything. A run that exited 0 has
already satisfied the postconditions. There is no "check afterwards" step to
run.

**Composition.** A session that runs several transitions in sequence has to
name each transition before asking for its contract. Naming a transition by
*name* would put the workflow's vocabulary back into the interpreter. One name
changed in `plan.toml` and the composed procedure stops working, silently, on
the arm that never runs. So a composed procedure selects by kind and
declared option, exactly as the single-transition procedure branches on them.
The bare table of contents carries a `Declares` block for that selection: one
line per transition, its kind and then its options. One read says which
transition is which kind, against opening every contract in turn. The block is
what the epilog renders per transition, indexed instead of listed.
[`list`](#the-listing) and [`show`](#show) already have that relationship: two
renderings of one fact. A session wanting the `Reading` blocks beside the
kinds reads [`fileplan --json`](#the-contract), which is every transition's
contract in one read. Where two transitions match one need, the composed
procedure reads their `help` lines and chooses. Choosing is a
judgment, and judgment belongs in the skill rather than in the declaration.

So a **composed** procedure lives in a skill rather than in the procedures
document. Every section of the procedures document is reached by a link from
a transition's section. A section describing a session that is not a
transition could be linked from nothing, and the orphan check would refuse
it. What one run needs is linked from its transition. What composes several
runs is not the declaration's business at all.

### dependencies

An item may **wait on other items**, and a state says which declared key
holds them:

```toml
[states.plan]
dependencies = "after"
```

The key is the workflow's. It is `after` here, and `[keys.after]` declares it
like any other. The field that names it is the tool's, and so is the row field
derived from it. A workflow whose items wait on one another under some other
word names it here, and nothing in the tool changes.

Every row then carries **`blocked-by`**. The field holds the slugs this item
waits on that are **still filed**, and `null` where it waits on nothing.
`blocked-by` is present whenever the declaration has such a state at all,
whether or not any item is filed in one. The field filters like any other:
`--has blocked-by=<slug>`, `--has blocked-by`, and `--lacks blocked-by` for
the work nothing filed is in the way of. A state that names no key reads none.
So an item carrying the key *there* carries a fact nothing was declared to
read.

Beside it is **`blocks`**, the same edges read the other way round. It holds
the filed items whose edges name this one, or `null` where nothing waits on
it. It comes off the walk that gives `blocked-by`, so it costs no second one.
Before declining or reworking an item, `show` says who depends on it.

**An edge naming nothing is named, never read as satisfied.** The old tool's
rule was the other way round. A dependency was satisfied by *absence*, and
deliberately so: a closed section's file is deleted, so "has it finished?" and
"is its file gone?" were one question. The cost was that a **typo'd slug is
never present either**. It read as satisfied, and nothing ever said so. Here
the complement is kept. What is filed is `blocked-by`, and an edge naming
nothing filed is a line in the **default** read —

```
unknown dependency: skills-as-interpreter names "exits-archve" in after, and
no item carries that slug
```

— which is the [make-problems-visible](#the-cursor) polarity. The forgotten
step fails loudly, and the default read is what shows it. An unknown edge is
deliberately **not** in `blocked-by`. "Waiting on X" and "X does not exist"
are different facts. A field spelling both would let the second hide inside
the first.

What makes reversing the rule safe is the rule at the other end. **When an
item is taken away, the close or merge that takes it clears the met edge from
every item naming it.** The edge is taken out, or, when the transition is a
[merge](#dissolving), pointed at the item the work continues as. The run
says on stderr which items it edited. So the tree never holds an edge to an
item that has closed or merged. An edge naming nothing is then a typo or a
rename, rather than a finished dependency. Nothing anywhere stores a closed
item's slug, since [the archive](#the-register) records its *number and
title*. So the tool could not tell the two apart if the tree did hold one. It
does not guess: it names the edge, and a person resolves it. Enforcing the
clearing is [`archive-plan`](#archive-plan)'s.

**A transition that does not dissolve clears nothing.** [`decline`](#decline)
moves an item to [`abandoned`](#abandoned) and leaves every inbound edge
alone. The item is still filed, so the edge still resolves and still reads as
blocking. An item waiting on something that has been abandoned really is
blocked, by a decision rather than by unfinished work. The row saying so is
what makes somebody go and look.

The same reading answers a **rename**. A slug is the item's one handle. So a
file renamed by hand leaves every inbound edge naming a slug nothing carries,
and the default read names every one of them. A
[retitle](#retitle) rewrites those edges the way a dissolving transition
clears them.

[`position`](#the-queue) is the order work is picked up in. An edge is the
statement that one item waits on another. A place and an edge are not the same
job. An edge pointing *later* in the order is therefore a third report rather
than a reordering —

```
misordered dependency: exits-archive at 400 waits on skills-as-interpreter at
500, which is later in the order
```

— because an order somebody set deliberately is not rearranged by a key about
something else. Two statements that disagree are a person's to settle.

**Both reports gate nothing and refuse nothing.** An unresolvable edge does
not refuse the listing. Grading a head *value* at read time would break a
whole listing over one item. An unresolvable edge does not take a command off
a row's [`commands`](#commands) either. A gate would make a precondition
depend on a derived fact, and the checks behind `commands` stay pure over a
head. So an unknown
edge costs an item nothing mechanically. The edge is a line in the default
read, and a session goes and looks.

**A run handed an edge naming nothing refuses it.** That is a transition's
check on a value it was given, not a report, and the reports above are
unchanged. The tree is in hand when a run writes the key, so a slug no item
carries refuses before anything is written, naming the near misses the way
[a handle](#the-handle) does. `--check` gives the same refusal. The slug has
to be exact: nothing is resolved from a prefix or rewritten. An edge that
dangles later, after a rename or an abandon, is still only reported.

### references

An item may **name other items as a record**, without waiting on them. A
decision record that supersedes an older one is the case that earned it. A
state says which declared keys hold such slugs, and what each is read back as
on the item it names:

```toml
[states.decisions]
references = { supersedes = { inverse = "superseded-by" } }

[keys.supersedes]
doc         = "method.md#supersedes"
list-valued = true
```

Both names are the workflow's. `supersedes` is declared under `[keys]` like
any other key, and a run writes it like any other key. `superseded-by` is
declared nowhere else. It is **derived on each read and never stored**: every
row carries it, holding the filed items whose `supersedes` names this one, or
`null` where nothing does. It filters like any row field, so `--has
superseded-by` lists every record something has superseded. Its value is
found wherever the referent is filed, in any state.

A reference shares the [dependency](#dependencies) machinery, apart from the
blocking:

* **A run handed a slug nothing carries refuses it**, with the near misses,
  exactly as a dependency does.
* **A slug that dangles later is a line in the default read**, and gates
  nothing:

  ```
  unresolved reference: use-sqlite names "use-postgress" in supersedes, and
  no item carries that slug
  ```

  It is its own report rather than an `unknown dependency:` line, because
  nothing waits on anything here.
* **A [merge](#dissolving) repoints a reference** at the survivor, because
  the work continues as the survivor. **A [retitle](#retitle) repoints it** at
  the new slug.
* **A move clears nothing.** The item is still filed, so the edge still
  names something.

A reference gives **no `blocked-by`, no `misordered` and no gate**. Nothing
waits on a record, and its place in an order means nothing about the record
it names.

**A close refuses while a filed item references the item it would take
away** (John, 2026-10-18). A dependency's edge is cleared at a close, because
the wait is over. A reference is history, so clearing it would erase the
record. Leaving it would turn history into a permanent `unresolved
reference:` line that looks the same as a typo. So the close refuses, naming
each referent and the key, and the row's [`commands`](#commands) does not
offer it. Take the slug out of the referent first, if the record really
should go, or merge the item into the one that continues it.

**The rules a declaration is held to**, each refused by name at load:

* each key is a declared key, and not one the tool owns;
* a key holds one kind of edge, so it is not also the state's `dependencies`
  or `opened-for` key;
* each key declares an `inverse`, and nothing else;
* an inverse is a usable name, and no row already carries it: not a declared
  key, and not a name the tool derives or reserves;
* one key reads back under one inverse, and one inverse reads back one key.
  The same pair on several states is one reference, and legal. A drafts state
  and a decisions state can both declare `supersedes`.

A transition cannot name an inverse in `requires`, `sets`, `drops` or
`refuses`. It is not a declared key, so it refuses as an undeclared one.

**Why it is built beside `dependencies` and not folded into it** (John,
2026-10-18). `dependencies = "after"` keeps its spelling, and no `plan.toml`
changes. The two share one implementation of what an edge is, so each rule
still has one writer. Folding the two declarations together can be an item of
its own later.

### stale-days

Every row carries **`stale-days`**: the whole days between the item file's
**last commit** and today. Nothing is declared to switch it on.

**Nothing is stored to make that number.** There is no head key, no stamp a
transition writes, no counter anywhere. The anchor is already in git, and git
is read when the listing runs. (John settled that on 2026-09-04, asked as: the
file's last commit, its first commit, or a sha a transition stamps.) A stored
grade would be true on the day it was written, and true-looking forever after.
The rule this repo keeps is that stale data is worse than none, and that
nothing cheap to re-derive gets stored. Unlike `claims` or an `add-bullet`
there is nothing for a transition to write, and nobody should go looking for
the missing one.

Two consequences follow from reading the *last* commit:

* **Any commit touching the file resets it.** The number therefore reads as
  *"days since anybody was near this"* rather than *"days since the
  judgment"*.
* **An uncommitted edit does not reset it**, because the field counts
  commits and not keystrokes. Where work is committed promptly that is a
  feature. Work that is not committed is work that can be lost, and a count
  that ignores it says so.

The date read is the commit's **author** date, in the **author's own
timezone**. Author rather than committer, because a rebase rewrites every
committer date at once. That would silently reset the whole tree's staleness,
where author time is when the work actually happened. The author's own zone,
because "the day they did it" is what a person means by a date.

`stale-days` is `null` wherever git has no answer. No answer is a tree that is
not a git repo, or a file git has never been given. A tree that is not a repo
**lists normally**: every value `null`, no traceback, rc 0. A consumer's tree
need not be in git, and that costs them nothing.

**Why there is no switch.** Earlier releases had a state opt into a `dated`
capability, so no history was walked where nobody asked for one. The walk
costs milliseconds, and a switch is a setting a newcomer has to learn about
before seeing a number that every listing can show. A plan.toml that still
names `dated` refuses by name and says to drop it.

`stale-days` filters like any other field. `--has 'stale-days>=14'` is what
nobody has been near in a fortnight. The comparison is numeric, because both
sides are numbers. `--has stale-days` is the items git has an answer about.
`--lacks stale-days` is the ones it does not, the items filed today among
them.

**`stale-days` reports, and it does not gate.** No row's
[`commands`](#commands) depends on it, and no precondition reads it. A gate would make a precondition
depend on a derived fact. The precondition checks would then stop being pure
over a head, and every one of their tests would need a tree on disk. A filter
is how you act on the number.

The **cost of the read** is one history walk per item. Each stops at the
first commit that touched that file. At this repo's scale that is
milliseconds. One walk inspecting every commit's changes for all the paths at
once is the optimisation, if a tree ever holds thousands of items. That walk
is not built, because n is tens.

A grade recorded under a **rubric that has since changed** is the other half
of the same worry. Nothing in this repo writes a graded value, since `size-it`
is a session rather than a declared transition. So there is nothing yet whose
rubric could drift. A hash of a key's `doc` section recorded beside its values
would be machinery for n=0.

### the close check

A record is filed and the body it was written from is taken away in **one
run**. So a [`close`](#dissolving) that declares `archives` refuses while
any named sub-phase carries no [mark](#marking).

The close check is a rule over the kind and the option, never over a
transition's name. [The dangle check](#the-dangle-check) beside it reads the
same pair for the same reason. The harm is the deletion. A sub-phase nobody
marked is a piece of the section the entry does not have in it. Once the body
is gone nothing is left to write it from. [`decline`](#decline) archives and
is a move, so it does not inherit the rule. A section abandoned *half
done* is the whole content of that decision.

**The close check reads the body, so it fires at the close rather than as a
precondition.** A closing condition that has to look at every named sub-phase
can be neither a `requires` nor a `refuses`. Both are pure over a head by
construction. Purity over a head is what makes every precondition testable
without a tree on disk.

The refusal **names the bullets**, where the dangle check gives a count and a
path. The bullets are in the file the operator already has open. The state's
[pending marker](#bulleted) is among them and always blocks. The pending
marker is the tool saying the decomposition itself is unfinished. The dangle
check's reading of a forgotten marker as *loud and harmless* stays true of
[carriers](#carrier). A row's [`commands`](#commands) is worked out through
the same function the run refuses through, so `fileplan list --has
commands=archive-plan` says exactly which sections could close.

**What the close check does not reach.** What a body-reading rule reaches is a
mark the tool itself wrote, never prose. The check can say "this bullet is
marked", never "the draft is updated". A half-done item can sit in a state
forever. The check fires at the close and nowhere else, and nothing nags. And
an item moved between directories by hand bypasses the check entirely, as it
bypasses every other precondition. Location is state, and `mv` is not a
transition.

### the dangle check

A [carrier](#carrier) is opened to answer one [sub-phase](#sub-phases)'s
question. It holds that work's findings. A state says which declared key holds
the item its carriers were opened for:

```toml
[states.carrier]
opened-for = "opened-for"
```

The field is the tool's word, and the value is the workflow's. This repo's
declaration reads `opened-for = "opened-for"`, because it chose the obvious
word for its own key.

`opened-for` sits on the **state** rather than on a transition. `files` is a
transition table, because only the *writer* needs to know it creates a second
item. `opened-for` is a state field, because the **reader** needs it: the
listing reads the field while walking the state. `sub-phase-cursor`,
`sub-phase-status` and the [dependency](#dependencies) key all sit on a state
for that reason.

Declaring it is optional, and declaring **nothing** is the ordinary case. A
state naming no owner is looked up by nothing at all. That is how the check
gates itself, without a capability whose only job would be a second way to
spell "absent". The key it names is an ordinary `sets` key. A session names it
on the run that opens the carrier, and no transition writes it by itself.

**What the field gates is one refusal.** A [`close`](#dissolving) that
declares `archives` takes the item away and writes the record that outlives
it. So the transition **refuses** while a carrier still
names that item and holds a finding nothing has [marked](#marking). The
refusal names the carrier's file, the declared key it names the item in, and
how many of its bullets carry no mark. The kind and the option are both
needed, because the harm is the **dangle**. Only a transition that takes the
file away creates a dangle. A section given up on instead lives on where the
transition moved it, so what named it still resolves and nothing is orphaned.
The dangle check is a rule over the kind and its options, never over a
transition's name. And the check keeps
abandoning a half-done section one run, rather than one run per open finding.

The dangle check has a **sibling over the same pair**, one file nearer.
The closing item's *own* unmarked sub-phases refuse the same run. That
sibling's home is [the close check](#the-close-check), which is where the two
are told apart. The dangle check reads a carrier's bullets through the key the
state names. The close check reads the item's own.

The check reads the **tree**: what the state names, and what the bullets under
it carry. That is what every other precondition already reads. Nothing it asks
is derived from git, and that is the line [`stale-days`](#stale-days) draws. A
precondition reading history would stop being pure over a head, and every test
of it would need a repo on disk. A row's [`commands`](#commands) reads it
through the same function the transition refuses with. So the read and the run
cannot disagree about which items are affected. What the check does not add is
another [exception report](#the-listing). The refusal is where a forgotten
close-out is made loud, and a second reporter naming open carriers would be
machinery ahead of need.

**What the dangle check does not see.** An `opened-for` value **naming
nothing filed** is not reported. Such a value is a broken reference of the
kind [`unknown`](#dependencies) names, in a different record shape. A second
report where nothing yet exists to report on is machinery ahead of need.

### the register

A state may opt into the **`numbered` capability**, and [`plan`](#plan) does.
Every item in such a state carries a `number`, this workflow's section number.
Like a [place](#the-queue) it is the *tool's* key rather than this workflow's.
So `[keys.number]` refuses as a redeclaration, and so does a transition naming
it. It is minted on the way into the state and dropped on the way out,
automatically. [`queue`](#queue) is what mints one, because committing to work
is when an item earns a number. An idea in
[`someday-maybe`](#someday-maybe) has not earned an ordering.

**A number is for reading and for the archive.** A verb that writes names
an item by [its slug](#the-handle) and by nothing else. `fileplan show 4`
reads the live item carrying 4, and `fileplan work 4` does not resolve and
must not. The number names an item in the archive, where the item's file no
longer exists. While the item is still filed, a writing verb's refusal names
it and the command that reaches it ([the handle](#the-handle)), and the
refusal stays a refusal.

**The register is derived, never stored.** There is no high-water mark. The
corpus decides what is taken, so a renumber cannot leave a registry behind to
disagree with it. The register has **two sources with two writers**. Every
item in the state carries its own `number`. And the document the state's
`archive` field names carries one heading per item that has **closed**:

```toml
[states.plan]
capabilities = ["queued", "claimed", "numbered"]
archive      = "docs/plan-archive.md"
```

A `numbered` state with no `archive` refuses. An `archive` on a state that
mints nothing refuses too, since nothing would read it. The named path must
**exist**, checked at every invocation like a `doc =` pointer. It may be a
file or a directory, and the directory form is described further down. An
*empty* file or directory is the legitimate case: a repo that has
closed nothing.

**A register may declare where it begins.** `first-number` is the first number
the state may hold, **inclusive**, and it defaults to 1:

```toml
[states.plan]
capabilities = ["queued", "claimed", "numbered"]
archive      = "docs/plan-archive.md"
first-number = 192
```

An empty corpus then mints **192**. The gap walk starts at 192, rather than
reporting 191 numbers as missing. That is what a consumer cutting over from a
tool whose sections run to 191 needs: a fresh archive for the new register,
and the old one left where it is.

**`first-number` bounds the derived register.** Every number the register
holds still comes from the two writers above. The floor says only where the
walk starts. The floor claims nothing about what is below it. A stored
high-water mark is a fact about the corpus kept somewhere the corpus does not
control, and it can therefore disagree with the corpus. The old tool's
archived range line was such a mark, and a `numbered-through = 191` would
assert one in its own name. A source that *does* claim a number below the
floor **refuses at the mint**, naming the number and the source that holds it.
The declaration and its own corpus contradict each other. Clamping the mint up
to the floor instead would leave a hole the gap walk starts above and could
never report. Filing is not minting, so an item already carrying a below-floor
number can still be filed. The gap elsewhere in the register that does not
refuse a filing below is the same rule, one field over.

**A state declaring no floor does not refuse**, unlike one declaring no
`archive`. An archive is a document that must exist to be read, and a floor is
a bound with a correct default. This repo declares none. Its register starts
at 1, so absence is the worked example. A declared floor is graded at load. A
value that is not a whole number, one below 1, and one on a state that opts
into no register each refuse by name.

**The read carries the register itself**, one record per numbered state. The
record names the state, its archive, its floor and the highest number it
holds. `highest` is `null` where the register holds nothing at all. The floor,
the highest and [the gaps](#the-listing) answer **is N a section**, with
nothing re-derived. Below the floor is recorded elsewhere by declaration.
Above the highest nothing has been minted. Between them a number is held
unless it is a gap. The record says what the register holds rather than what
is wrong with it, so it is in `--json`'s envelope on every read and nowhere in
the text form. A person meets the register only when something is wrong
with it, as a gap or a lost close-out; "floor" is a word a newcomer never has
to learn to read a listing.

An **archive entry's heading is `## <number>. <title>`**. That is the number,
a full stop, a space, then the title. The register reads that form and the
archiver writes it, so the two cannot drift into disagreeing parsers.

**Every `##` in the archive must parse.** One that does not is a **lost
close-out**. A lost close-out refuses every write by name, naming the line,
and [the listing](#the-listing) names it on every read. There is no allowlist,
because an allowlist covers only the lost close-outs somebody remembered to
name. A closed item's heading is the **only** record that its number is taken.
So a heading the parse cannot read drops that number silently, and frees the
next item to mint it again. It happened in the old tool: `## Section 168:`
shipped where `## 168.` was needed. The gap check below structurally cannot
catch it.

Three more rules, and then what is left blind:

- **A gap refuses**, naming the missing numbers. A gap is a declaration this
  parser cannot see, and the number above it may already be spoken for. A gap
  is also **named in the default read**, by [the listing](#the-listing) and
  off the same arithmetic. Refusing at mint time alone would leave a section
  deleted by hand invisible until somebody happened to mint. The mint refuses,
  and the listing reports.
- **Two items claiming one number refuse**, naming both. A closed item that
  shares its number with a live one is unfindable in the archive.
- **An item already in the state keeps its number.** An in-place transition
  such as [`work`](#work) is about the cursor. Such a transition says nothing
  about identity, so it re-mints nothing.
- **The top of the range is blind to a number with no heading at all.** Such a
  loss produces no gap. It lowers the maximum. A *malformed* heading there is
  named as a lost close-out instead, which is what the second report narrows
  this to. What closes the rest of the window is the archive entry and the
  item's deletion landing in one commit.

**Three holes are left.** An **unnumbered** item that vanishes leaves no trace
at all. The register is the only mechanism that can name an absence, and it
covers numbered states alone. The only fix would be a stored list of
everything that ever existed, which is the one thing this design refuses. A
numbered item lost **at the
maximum with no heading at all** lowers the maximum and leaves the register
gapless. And **two items claiming one number** punch no hole in the
arithmetic, so there is no third report. The mint still refuses, naming both.
Unlike a gap it is not hidden: two live items carrying one number both print
it in the default read.

**The other half writes an entry.** A transition out of a `numbered` state
opts in:

```toml
[transitions.decline]
kind     = "move"
from     = "plan"
to       = "abandoned"
archives = true
```

and the run files `## <number>. <title>` into the document that state's
`archive` names. That is the same field the register reads. So where closed
items go has one home, rather than a state's copy and a transition's copy to
keep in step.

**The entry is inserted at its place in the register, never appended.** The
entry goes before the first entry whose number is greater, and at the end when
there is none. Sections close out of order routinely — one that is queued
later can be finished first — and a transition that appended would leave such
a document reading 1, 2, 4, 3. The parser and the writer are in one module. So
the form the entry is written in and the form the register reads cannot drift
apart.

**Recording an item and deleting it are two different choices.** A move
that sets an item aside records it and moves the file. A close records it and
takes the file away. `archives` is the recording alone, an option on a
`move` or a `close`, and the deletion is the close's kind. Every transition
that archives takes `--record`, the prose that goes under the heading. A
close requires `--record`, and a move does not ([dissolving](#dissolving)
says why).

**An archive may be a directory, with one file per entry.** What is on disk
decides the form. There is no extra field to declare it.

```toml
[states.plan]
capabilities = ["queued", "claimed", "numbered"]
archive      = "docs/plan-archive"
```

The directory form exists for **several sessions sharing one working tree**.
With a single archive file, two close-outs at once both write and commit that
one file, and they collide. With a directory, the two close-outs write two
different files.

An entry is filed as **`<number>-<slug>.md`**, such as `37-a-worked-example.md`.
The number keeps the file findable by what the register calls it. The slug
makes a directory listing readable. The file holds exactly what an entry in a
single archive file holds: `## <number>. <title>`, a blank line, then the
record. Filing writes that one new file and touches no other file in the
directory.

The register reads **every `*.md` directly inside the directory**. It does not
read subdirectories, and it ignores other extensions, so a `.gitkeep` is fine.
Each file is read the way a single archive file is read, so the numbering, the
gaps and the register's own record come out the same in either form. A lost
close-out names the entry file and its line.

**A `.md` file there with no readable heading is a lost close-out**, named at
line 1. The file *is* the entry, so a file the register cannot number from has
dropped its number, the same as a `##` the parse cannot read. A stray
`README.md` in the directory is therefore reported rather than skipped. A file
holding two readable headings is read as two entries, as in a single file.

Two refusals guard the write, and both run before anything is written. A
number another entry file already holds refuses, naming both files. And a file
already at the entry's name refuses: it holds some other number, and writing
over it would drop that number.

**The item is written first and the entry second**, which is
[the claim record](#the-claimed-state)'s order. A crash between the two leaves
an item that has moved with no entry. An item with no entry is a gap, which is
reported and which a person fixes by hand. The other order would leave an
entry for an item that is still live. An entry for a live item is two
claimants for one number, which refuses every later mint. Every refusal is
computed before either write, so a refused run leaves both files
byte-identical.

Five things refuse, and one deliberately does not:

- `archives = true` **out of a state that mints no number** refuses at load.
  An entry is named by its number, and there would be nothing to name it by.
- `archives = true` **on a kind that stays** refuses at load, because only a
  move and a close take it. The number is dropped on the way *out*, so an
  in-place transition would file the number and leave the item carrying it
  too.
- **A way out of a `numbered` state that does not archive** refuses at load,
  naming the transition and the line to write. A move or a close without
  `archives = true` drops the number with no entry. The next mint refuses on
  the gap, far from the run that made it. And if the item held the highest
  number, nothing refuses at all: the next mint hands that number out again,
  and two items have carried it. That silent reuse is why the rule covers
  every way out, and not only the shapes a consumer happened to hit. A
  `merge` out of a `numbered` state refuses outright, because a merge cannot
  archive. Write a close with `archives = true`, or merge out of a state that
  numbers nothing.
- An item carrying **no number** refuses at the run, by name.
- A number the archive **already holds** refuses at the run, naming both
  claimants. It is the same refusal a mint gives, because it is the same
  question.
- A `numbered` state that **no transition leaves** does *not*
  refuse. That is an asymmetry with [`claimed`](#the-claimed-state) and
  [`bulleted`](#bulleted), where an unused capability means the declaration
  cannot do what it says. Here it does not. The `archive` field has a second
  reader: this register, which counts closed numbers whether or not any
  transition has ever written one. And an empty archive is blessed above as a
  repo that has closed nothing. Refusing the shape would refuse a legitimate
  declaration, which is the worse fault.

A **gap elsewhere in the register does not refuse a filing**, though it does
refuse a mint. Filing is what fills gaps in. Refusing there would be the tool
declining to accept the fix.

### dissolving

Two [kinds](#kinds) **take the item's file away** instead of moving it, a
`close` and a `merge`:

```toml
[transitions.archive-plan]
kind     = "close"
from     = "plan"
archives = true
```

A close that declares [`archives`](#the-register) records the item, then
removes it. That is how a section is closed out. [`decline`](#decline) is a
move that declares `archives`, and keeps the file.

**A close or a merge names no `to`**, and a `to` beside one refuses. So does
everything else that would put something on the file afterwards. `sets` and
`drops` are what its head would carry, and `claims` is a record about a file
that will not be there. None of them is a field either kind takes. What stays
is what grades or records. `requires` and `refuses` read the head before it
goes, and `archives` has as its whole job that something outlives the file.

**A close need not archive.** A close out of an *unnumbered* state can
archive nothing, since there is no number to name an entry by. And
[`merge`](#merge), which takes a [`someday-maybe`](#someday-maybe) item into
another, is exactly that shape.

**The order is delete, file, clear, free**, and every refusal is computed
before any of it. So a refused run leaves the item, the archive and every
referent byte-identical. Each other order was rejected by which half-state it
leaves on a crash:

- **filing the entry first** would leave an entry for an item that is still
  live. That is two claimants for one number, which refuses every later mint
  and a re-run that refuses as a duplicate. Blocking;
- **clearing the edges first** would leave referents whose edge to a
  still-live item had silently gone. That is precisely the read-as-satisfied
  silence [dependencies](#dependencies) exists to remove;
- **deleting first** leaves a register gap and dangling `unknown dependency:`
  lines. Both are named in the **default** read and both are a person's to
  fix.

**The edges to the item are cleared — taken out, or pointed at the
survivor**, which is the invariant [dependencies](#dependencies) rests on.
Every item in every state is read through **its own state's** `dependencies`
key, and a merge reads its [`references`](#references) keys as well. An item
in a state that declares none is not touched, because it is carrying a fact
nothing was declared to read.

**A close refuses over a reference.** A reference is a record, and a close
would leave it naming nothing. [References](#references) says why, and what
to do instead. One line per edited item goes to
stderr, naming the file and the key:

```
plan/adoption-init-retrofit.md: took "exits-archive-decline-and-merge" out of after
```

A line each rather than a count, so a session can check every edit. A list
loses the entry and stays a list. A value the clearing empties **loses the
key**, rather than keeping `after = []`. An empty key carries nothing, and
would be a fact the head states and nothing means.

**A body that still names the gone item gets a line too.** Clearing edits
dependency keys, and prose can name the item as well. After a real run, every
item left in the tree is read, the survivor included. Each body naming a gone
slug gets one line on stderr:

```
plan/some-section.md: its prose still names "a-idea" and "b-idea", which merge took away
```

The match is on the whole slug. So `someday-maybe/a-idea.md` counts, and
`a-idea-two` does not. Only the body is read, because the head's edges are
the clearing's job. The notice warns and never rewrites. Rewriting would be
the tool editing what a person wrote. The exit stays 0. A `--check` prints no
such line, because the check says what the run would do.

**The listing does not report a slug cited in prose** (John, 2026-10-18). A
consumer asked for that report, and for the citations to be repointed when a
merge or a [retitle](#retitle) takes a slug away. Prose has no citation form, so the
listing cannot tell a slug from an ordinary word that happens to match one.
Nothing stores the slug of an item that has closed, so a later read cannot know
that a slug is gone. The run that takes the item away is the one moment the
tool does know, and that run prints the line above. A workflow that cites in a
fixed form can check its citations with its own script. Rewriting the
citations stays no, for the reason the notice gives.

The stderr lines come in the order the run works. The archive entry comes
first, then the edges, then the prose, then one line per item removed.

**A merge points an item's edges at a survivor instead of removing them.**
[`merge`](#merge) is this workflow's transition of that kind:

```toml
[transitions.merge]
kind = "merge"
from = "someday-maybe"
```

A merge takes **`--into ITEM`, required**. A merge with no survivor has
nothing to point the edges at. The handle
resolves **tree-wide**, like every other. So `merge some-idea --into
a-plan-section` is a legitimate run. An idea continues as a queued section,
and the tool owns no judgment about where work continues. The survivor's head
is neither graded nor edited, so its state is unconstrained. Its body gains
the absorbed bodies ([merge](#merge)), so the run grades the body it composes
and refuses a survivor another session holds. The survivor's head carries
**no record of what it absorbed** (John, 2026-09-04): every reference now
points at the survivor. Two more refusals, both computed before any write: a
handle naming nothing, and a survivor that *is* the item. Merging an item
into itself would delete it and leave every edge pointing at something gone.

The same walk and the same three rules apply, and what the head actually got
is what the notice says:

```
orchard/second-tree.md: pointed "a-seedling" at "b-seedling" in after
orchard/b-seedling.md: took "a-seedling" out of after — it is this item now
```

The second is the **self-edge**. The survivor may be in a state that declares
`dependencies`, so its own head can name the item being absorbed. A `plan`
section may wait on a `someday-maybe` idea. Repointing that entry would write
an item waiting on itself. That one entry is **dropped** instead, and stderr
says which item and which key. Refusing the whole run on the self-edge was
offered and declined (John, 2026-09-04). The self-edge has one correct answer,
and the tool applies it rather than stopping a close-out. An entry whose value
the drop empties loses the key, `without`'s rule unchanged. And a referent
that already named the survivor keeps one entry rather than two, because an
edge is named once.

**A merge always takes the item away.** Pointing every edge at a survivor
while the item is **still filed** would leave two items where the workflow
says one. The edges to the first would then read as satisfied against an item
still standing there. That is the read-as-satisfied silence
[dependencies](#dependencies) exists to remove, and it is why repointing and
deleting are one kind rather than two settings.

**A referent another session holds is edited anyway.** Refusing would let an
unrelated claim on an unrelated item block a close-out. Skipping would leave
the dangling edge the invariant forbids. The edit is mechanical (John,
2026-09-04). The referent's head is not graded either. The edit only removes a
value, so it cannot introduce a defect. Grading would let a stranger's
pre-existing defect refuse a close-out that has nothing to do with it. The
listing is still where that defect shows.

**The prose comes in with the run.** A close that archives takes `--record`,
and it is **required**:

```
fileplan archive-plan exits-archive --record - <<'END'
What the section decided, and the done lines it closed on.
END
```

`-` reads stdin, so a long entry comes in from a heredoc. A redirect works
too, with no heredoc: `--record - < entry.md`. It is required
because [mint-then-fill](#decompose) cannot work here. The body the record is
written from is deleted by the same run. A minted heading with nothing under
it, plus a deleted item, is the lost close-out
[the register](#the-register) exists to prevent. A forgotten record has to
fail at the one moment it can still be supplied. The refusal is click's,
followed by one line saying what a record is: the entry filed under the
item's number in the archive, what it decided and what it shipped.

**A move that archives takes `--record` too, and there it is optional.** The
moved item survives in its new state, so mint-then-fill still works.
[`decline`](#decline) given `--record` files the heading with the prose under
it in one run. Without `--record`, `decline` mints the heading alone, exactly
as it did before the option existed, and the prose is written under it by
hand. A move can declare `sets`, so a key called `record` there refuses **by
name**, which is [the check](#the-check)'s rule.

**What the run prints.** stdout is the **archive document** when the
transition archives. The run returns the file it wrote, and the item's own
path names something that is not there any more. A close that archives
nothing has only the path it removed to report. A merge is included in that,
because what it writes is *referents*, and the survivor is not something the
run wrote.
Either way stderr says the item is gone, beside the entry's line and the
cleared edges'.

### the queue

A state may opt into the **`queued` capability**, and [`plan`](#plan) does.
Every item in such a state carries a `position`: a place in the state. The key
is **not declared** and may not be. The key is the
*tool's* rather than this workflow's. So `[keys.position]` refuses as a
redeclaration, and so does a transition naming it in `requires`, `sets`,
`drops` or `refuses`. A position is written on the way into the state and
dropped on the way out, automatically. A second spelling of that rule could
disagree with the first. An item carrying a `position` in a state that
is not queued refuses by name.

**A queued state sorts by `position` unless it says otherwise.** The
`queued` capability holds places, and the state's `sort` is what lists items
by them, so `position` is the one sensible default. Earlier releases refused
a queued state with no `sort` and said to add the line; a default does the
same job without the refusal, and the bare `fileplan` overview prints
`sorted by position` beside the state, so the choice is never hidden. Any key
the state carries may be the sort.

**Places are 100 apart**, so there is room between any two. A new place is
the midpoint of its two neighbours. So filing something between two items
touches no other row, and a place cited last sitting still means the same
item. A bare placement appends 100 past the last. `--above ITEM` and `--below
ITEM` take the midpoint beside that item. `--at N` names the place outright,
and is also the tool for respacing. A place another item holds refuses, naming
that item. Two items at one place would be ordered by the tiebreak rather than
by the operator.

**Which commands take those three options** is derived from the
transition's [kind](#kinds). A `create` or a `move` the item **arrives** on
takes them. The item has no place in the state yet, and the run gives it one.
[`queue`](#queue) is the shape. So does a `reorder`, which stays in the state
and **does nothing else**. Where the item goes in the order is the whole of
what a reorder has to say. [`requeue`](#requeue) is the shape, and it is the
only one this repo declares. Every other kind takes none of them.
[`work`](#work) says which sub-phase a session is on, and
[`finish`](#finish) marks a bullet. Neither is about the order. A command that
offered three options about the item's place while writing something else was
the surface saying it did more than it does.

No field declares this. A command that loses an option it used to take refuses
by name at rc 2, click's own `no such option`. The refusal is the loud failure
that makes the two arms safe to derive, rather than something every arriving
transition has to opt into.

**An item already in the state keeps its place** unless one of those options
asks otherwise. Naming no place is not a request to be moved. Appending
instead would let a run silently destroy an order somebody set deliberately.

**Nothing renumbers a neighbour.** A gap can be exhausted, with two rows
already adjacent. The tool then refuses and names the respacing, rather than
shifting rows to make room: give the rows around it places 100 apart with
`--at`, then ask again. A queue that respaces itself is one the operator
cannot cite between two sittings.

A place is a **bare integer**, never quoted, because the key is arithmetic.
`"1000"` sorts ahead of `"200"` as text. For the same reason `--has
'position>=200'` compares as a number. An item in a queued state carrying no
place comes last, and the listing names it under `unsorted`. The listing is
how you find out what to fix.

### sub-phases

A section decomposes into **sub-phases**, each sized to one session. They stay
**bullets in the section's own body**, not files, and with no marker key
beside them. So the tool needs exactly one thing from them: how many there
are. It **counts, never interprets**. A count is derived from what is written,
so unlike a marker it cannot drift out of step with the document. And one
number is the whole of what a read needs.

A state says which heading to count under, and a state that declares none
counts none:

```toml
[states.plan]
sub-phases = "Sub-phases"
```

There is **no default heading**. A fixed word would be one workflow's
convention baked into the tool. And *any* top-level bullet would be wrong on
this repo's own items, which carry bullets under "Back burner" and "Done when"
as well. The heading is matched on its **text**, at any `#` depth. So a
consumer that writes `## Steps` is not forced into another repo's nesting. A
heading that appears twice refuses by name. Two spans are two answers to one
question, and taking the first silently is the drift counting was chosen to
avoid.

**Only bullet-shaped lines are graded**, and only `- ` counts. A line is
bullet-shaped when a marker (`-`, `*`, `+`, or `1.`) is followed by
whitespace. Every other bullet-shaped line refuses, naming the line and what
it holds. Prose at column zero is ignored however it starts. An italic
`*Each is one session…*` opens a body and is not a bullet, which is how
Markdown reads it too. The space after the marker is what separates the two.
Indented lines are **continuation** and are never counted, so the numbered
list inside a sub-phase's own bullet stays invisible here. **Fenced lines are
not lines at all.** Inside a ``` or `~~~` block nothing is a bullet, nothing
is this heading and nothing is the pending marker. A [carrier](#carrier)
quotes transcripts in the same body it holds findings in, and a quoted
`- **f9 — …**` is evidence rather than work. The writer keeps that rule too. A
mint puts every fenced line back byte for byte, and neither it nor a
[mark](#marking) touches one. A fence that opens under the heading and never
closes would hide the rest of the span, so it refuses by name.

The tool counts the one form and **names** the rest. The tool does not guess
and report a number that is quietly wrong. A silent miscount is the failure
this counting exists to prevent.

**A sub-phase may carry a name, and that is how anything points at one.** The
strict form extends to `- **<name> — …**`. The name is the first token of the
bold run the bullet opens with, so `- **4-1 — Counting the body.**` is named
`4-1`. A hyphen inside the token is part of the name. Whitespace, an em-dash
or an en-dash ends it. Extending the strict form this way is the same kind of
mechanical rule as the bullet marker itself. A sub-phase therefore stays a
bullet rather than becoming a heading with a real anchor. A heading of any
depth *closes* a span, so heading-per-sub-phase would break the counting rule
the name is there to serve.

Naming is **additive**. A bullet with no bold run is still counted, and the
count is what it always was. Such a bullet simply has no name, so nothing may
point at it. A reference to it refuses, saying which body line needs one. Two
bullets sharing a name refuse by name, listing both lines. One name pointing
at two bullets is two answers to one question.

**A span ends at a heading, and bold prose is not one.** `**Done when:**`
followed by bullets goes on being counted. Closing a span on prose would mean
guessing where a list stops, and the guesses are unbounded: `**Done when:**`,
`_Done when:_`, `Done when:`. **Put the sub-phases last in the body**, or
close them with a real heading.
This repo's items do the first.

**What the span passes over, the tool names.** A bullet after the heading
that ends the span is not counted. Where its name has the state's form, it
was plainly meant as a sub-phase. So the [`unread` report](#the-listing)
names it, with its line. The same report names a bullet whose bold run the
reader cannot name, because a lone `*` sits in it or it never closes. A
mint or a mark into such a body refuses, naming the line. A mint hands out
the highest ordinal it can read plus one, so the hidden name would be minted
twice.

The count is a field on every row wherever the declaration counts at all.
`null` means the item's *state* counts no sub-phases. `0` means a section
nobody has decomposed yet. Those are different facts, and the zero is a real
value rather than an absence. A section reading `0` is one waiting to be cut
up. It filters like any other field, so `--has sub-phases=0` is that set. That
is **not** the same set as the [`undecomposed` report](#the-listing), though
the two are one word apart. The report names a section somebody has
**started** and left uncut, which is the alarm. The filter names every section
carrying no sub-phases, including the queued ones nobody has touched. There
zero is simply what a section looks like before it is picked up. Asking the
question gets the superset. The report is the subset worth interrupting a
reader about.

Beside the count on every row is **`sub-phases-left`**, the number of bullets
carrying no [mark](#marking). A count of what is open is what a reader
scanning the tree needs, so [the listing](#the-listing) is where that count is
explained. `sub-phases-left` reading zero and `sub-phases` reading zero are
different facts, and the **pair** is what tells them apart. A row reading
`sub-phases 0` and `sub-phases-left 0` is a section nobody has cut up. One
reading `sub-phases 6` and `sub-phases-left 0` is a section where every bullet
is disposed of. Neither number has to carry both facts.

`[keys.sub-phases]` refuses as a redeclaration, and so does a transition
naming it. The count is read off the body rather than written into a head, so
there is nothing to set. `[keys.sub-phases-left]` refuses because it too is
read off the body, one step on. A key beside it is a counter somebody has to
remember to decrement, and completion sitting on the bullet is exactly so that
nobody has to.

Which of them is current, and how far it has got, is
[the cursor](#the-cursor).

### the cursor

The count says how many sub-phases a section has. **The cursor says which one
a session picked up or [finished](#marking) last**, and it lives in the
section's *head*, never in the bullets. The count is derived from the document and cannot drift. The cursor
is declared state a transition writes.

Whether that sub-phase is *over* is read off its bullet, below. Whether one is
in flight is the status key beside the cursor, which a sub-phase that has
stopped leaves behind ([sub-phase-status](#sub-phase-status)). So a cursor
standing on its own is the ordinary case rather than a defect. Neither fact
was ever the cursor's to hold twice.

The two keys are the **workflow's**, declared like any other, and the state
says which is which. This repo's own declaration is the worked example:

```toml
[states.plan]
path             = "plan"
doc              = "docs/method.md#plan"
capabilities     = ["queued", "claimed"]
sort             = "position"
sub-phases       = "Sub-phases"
sub-phase-cursor = "sub-phase"
sub-phase-status = "sub-phase-status"

[keys.sub-phase]
doc  = "docs/method.md#the-cursor"
help = "Which sub-phase is current, by the name its bullet carries."

[keys.sub-phase-status]
doc    = "docs/method.md#sub-phase-status"
help   = "How far the current sub-phase has got."
values = ["open", "planned", "in progress"]
```

The cursor key's own home is this section. The status key's is
[`sub-phase-status`](#sub-phase-status), because its three *words* are a
meaning of their own.

**Name the pair.** A status key is the cursor key plus `-status`. So the two
read as halves of one thing wherever they appear. The two appear in a head, in
a row, and in the options the transitions that write them take. The state
names both keys, so any two words would work. The alternative is a reader
having to open `plan.toml` to learn which status belongs to which cursor.

The two keys are the workflow's because the words are the workflow's. A
workflow whose sub-phases go *todo / doing / shipped* writes that. Baking one
set into the code is what the design refuses. The keys are named on the state
all the same, and naming them is what lets the tool grade a cursor **against
the body**. A cursor pointing at a sub-phase nobody wrote is a wrong state
nothing would otherwise notice.

So the declaration is graded three ways. Each field must name a key the
declaration declares. A cursor may not be declared on a state that counts no
sub-phases, because there is nothing to grade it against. And the status's key
**must declare `values`**. A status that can hold anything makes a typo one
more status. The closed set is the shape the tool needs, rather than the
words, which stay the workflow's.

**A cursor holds a sub-phase's name**, not its ordinal. An ordinal is not a
stable reference. Insert a bullet, reorder two, or expand a *pending further
decomposition* bullet into three real ones. Then "sub-phase 3" silently means
different work. Within a single session that drift is survivable. The drift
stops being survivable the moment a reference outlives the session. A claim
record names the sub-phase it holds in its **filename**, and this tree is on a
syncing filesystem. So every live claim on every machine would re-point at
once, with nothing to notice it. Removing the failure costs nothing before
anything persists a reference, and a great deal afterwards. So the reference
is a [name](#sub-phases) from the start.

A cursor is checked **before anything is written**, on any transition that
sets it. A value naming no sub-phase this body carries refuses, naming the
value and the names available. That catches a typo'd reference as well as one
that points past the end. A range check caught only the second. A value
naming an unnamed bullet refuses the same way, saying which body line needs a
name. Nothing falls back to an ordinal, because a silent fallback is the
failure being removed. A section that has not started carries no cursor at
all, which is the ordinary case and is not a defect.

**What says a sub-phase is over is a [mark](#marking) on its bullet**, and
the head says nothing about it at all. There is no third field naming which
status word is terminal. There was one, and it went, because completion
written in both places is completion that can disagree with itself. Any
declared mark ends a sub-phase. Which one it is says *how* it ended, and nothing in `src/`
knows either word.

**A mark on the bullet is what buys `next-sub-phase`**, a field on every row
wherever the declaration counts sub-phases. The field comes after the count
and the [count of what is left](#the-listing). It has two arms. A cursor
naming a bullet that carries **no mark** is itself what comes next, because
that sub-phase is in flight. Otherwise the field names the **first bullet
carrying no mark**, or nothing where every one of them is marked.
`next-sub-phase` is derived from the body like the count, and is a computed
field rather than a named report. The reports dissolve, and what stays code is
the facts a head does not hold.

Reading the bullets rather than a pair in the head is what lets a row say *5
done, 6 open, 7 done*. The answer is 6, whatever order they were marked in.
No cursor has to be walked backwards to find it.

The two silences stay apart the way the count's two do, and by the same
means: **the pair**. A row with `sub-phases 9` and no next is a decomposition
that is finished. A row with neither is in a state that counts none. Neither
field has to carry both facts. [`sub-phases-left`](#the-listing) beside it
says how many are open outright, rather than leaving a reader to read the
number off a silence. `--has next-sub-phase` is then the sections with
something left to pick up. And `[keys.next-sub-phase]` refuses as a
redeclaration, because it too is read off the body.

**`next-sub-phase` is in the default read, behind no flag.** The failure it
exists to catch is a cursor somebody forgot to move. A cursor here sat two
sub-phases behind what had shipped, and nothing in the written process moved
it. A process step is a flag you have to know to pass. A line in the default
listing saying the next sub-phase is one already behind needs no flag at all.

**And a cursor is refused onto a marked bullet, at the moment it is
written.** This is the one place the rule reversed. What reversed it is that a
mark is data the tool wrote, rather than `**Done**` read out of prose. A run
that *sets* the cursor onto a sub-phase already marked refuses before anything
is written. The refusal names the value and the mark the bullet carries.
Picking a cursor **up** and putting it on something already disposed of is the
defect.

**Where every named sub-phase carries a mark, that refusal does not fire.**
The refusal protects nothing there. No open bullet is left for a cursor to
point at. And the cursor is still a true record of where the last session was.
The arm asks the same list the [close check](#the-close-check) refuses on. So
a cursor may be written exactly when the section could close.

**A transition that *marks* moves the cursor onto the bullet it marks**,
wherever the state keeps a cursor. [`archive-plan`](#archive-plan) requires
the cursor key. Three sections in a row marked every sub-phase without a
session ever running [`work`](#work), and each was locked out of the close
until somebody ran it by hand. A process step is a flag you have to know to
pass. The mark is the run every sub-phase ends with, so writing the cursor
there keeps it current by construction (2026-10-06). The cursor then says
which sub-phase a session last picked up **or** last finished.

The refusal above does not catch a mark, and cannot. A cursor resting on a
marked bullet is the ordinary state right after the mark went on, so a mark's
cursor is not asked whether its bullet is open. Gating on whether the run
*sets* the cursor is what tells the two apart. Membership is graded either way. A cursor naming a bullet the
body has not got is wrong however it got there. The listing still never dies
over one item. A cursor a body no longer carries falls through to the first
unmarked bullet rather than raising.

**A started section with no sub-phases is named by the listing**, in both
renderings and behind no flag. Started means the item carries the status key
at all. It does not mean its status has passed some particular word, which
would mean the tool knowing which one means not-started. A section that is
queued and untouched carries no status, so it is not started and is not named.
One somebody has begun and never decomposed is exactly what needs saying out
loud. It is reported the way a [stranded claim](#the-listing) is: beside the
rows rather than among them, and no filter narrows it.

### bulleted

[sub-phases](#sub-phases) are counted and [the cursor](#the-cursor) points at
one. **`bulleted` is the capability that writes them.** A state opts in, and an
`add-bullet` transition writes them:

```toml
[states.plan]
capabilities      = ["queued", "claimed", "numbered", "bulleted"]
sub-phases        = "Sub-phases"
sub-phase-pending = "**pending — Decompose the rest of this section.**"
sub-phase-name    = "{number}-{ordinal}"

[transitions.decompose]
kind = "add-bullet"
from = "plan"
```

A state says its items' bodies *may* be written. A transition says *this* is
the one that writes them. A [merge](#merge) into an item in a `bulleted`
state mints too, one sub-phase per absorbed idea. [The claim](#the-claimed-state) is declared in two
halves too. Coupling the two to arrival would put `--title` on every
transition into the state, and any of them could cut a section up on a run
about something else. Either half alone refuses by name.

`bulleted` is the first capability whose state is the item's **body**. The
other three write a head key or a file beside the item. `bulleted` writes
prose, in the strict form the reader already knows. So a mint and a count
cannot drift into two parsers that disagree.

**What a bullet is called is declared too.** `sub-phase-name` is the whole
ident form. `{ordinal}` is where the tool supplies the number, and every other
field names a value the item carries. `plan` declares `{number}-{ordinal}`, so
`4-9` is what the listing shows, what a cursor holds and what a commit message
says. [`carrier`](#carrier) declares `f{ordinal}`, and its findings are `f1`,
`f2`, …. The separator is in `plan.toml` and not in `src/` for the same reason
the heading and the pending sentence are: it is the workflow's word. And the
separator is what lets a state with no register carry bullets at all. The
alternative was being stuck with a bare integer nobody would type on a command
line.

The ordinal is the next free one. Take the **prefix**, which is the form with
its `{ordinal}` taken off and every other field filled in from what the item
carries. Strip that off every name the body holds. Read the leading integer of
what is left, take the maximum and add one. `4-5a` therefore contributes 5, so
splitting a sub-phase in two while planning it does not break the next mint.
And a name that is not an ordinal contributes nothing at all, which is what
makes the pending bullet invisible here. The ordinal is read off the names the
body already holds. Minting from the count would hand out a name the body
already carries.

The form is graded at load, **by name** on every way it can be wrong. Those
are: empty; carrying no `{ordinal}`; carrying one that is not at the end,
since the prefix is what precedes it and there is nothing to strip a suffix
with; carrying two, which is two answers to which part of the name the ordinal
is; or leaving a brace unclosed. Its *fields* are graded too, against what an
item in that state can actually hold. `{number}` on a state that is not
[numbered](#the-register) refuses, saying which capability gives it. And a
field nothing declares refuses as itself. The second rule is why `bulleted`
does **not** require `numbered`. One hard coupling in the code became one
graded rule in the declaration. The graded rule is the stricter of the two,
because it can also see a field the coupling never spelled.

`bulleted` also requires a `sub-phases` heading, since there is nothing to
mint under without one. It requires a `sub-phase-name` too, and each
requirement refuses by name. The heading is **created only where the body has
none**, at `###`. Where the body has one it is left exactly as written, at
whatever depth. The reader matches its text at any depth, and a consumer
writing `## Steps` is not to be forced into this repo's nesting.

**An unfinished decomposition is marked by a bullet, not by a key.**
`sub-phase-pending` declares that bullet's content after `- `. The words are
the workflow's. What the tool asks of them is that they parse as a named
bullet, graded at load through the same reader that has to find it again. The
bullet's name is `pending` in this repo, and that is what a cursor points at
when a session reaches it.

`decompose` takes `--title`, `--last`, both or neither, and `--after` beside
`--title`:

```
fileplan decompose exits                            # open the decomposition
fileplan decompose exits --title "The register"     # write one sub-phase
fileplan decompose exits --title "Close-out" --last # write the last, and close
fileplan decompose exits --last                     # close, writing nothing
fileplan decompose exits --title "Numbering" --after 4-2  # write one after 4-2
```

Three steps are applied in this order to the body. **Drop** the pending bullet
if it is there. **Append** the new sub-phase, if `--title` was given.
**Append** the pending bullet unless `--last` was.

**`--after NAME` puts the new sub-phase directly after the bullet NAME**,
below every line that bullet owns, instead of at the end of the list. It is
how a sub-phase is split where it stands. The pending bullet still goes at
the end. `--after` needs `--title`, since without one there is nothing to
place, and it refuses alone. NAME may be marked: new work after a finished
sub-phase is the ordinary case. A name the body has not got refuses in the
words [`show`](#show) uses, and the pending bullet is not a name here either.

**Only the place changes, not the name.** `--after 4-2` in a body that holds
`4-5` writes `4-6`, and puts it between `4-2` and `4-3`. The name is still
the next free ordinal, because a name is an identity, not a position. The
order of the list was never meaningful. A letter suffix such as `4-2a` would
be a second naming rule, and it could collide with a name somebody split by
hand.

**A bare run on a section that is already open changes nothing.** It drops
the pending bullet and puts the same bullet back, so the file is left byte for
byte as it was. The run still exits 0 and prints the path, and stderr says the
item is unchanged and why. Without that line, a run that wrote and a run that
did nothing would look the same on both streams. Any run that leaves the
item's file as it was says so the same way, and so does its check, in the
same words.

**The marker being the bullet means a section half cut up reads as half cut
up.** Forget `--last` and the bullet goes on saying the section is pending,
which is loud and harmless. A forgotten head key would instead leave a
half-decomposed section looking finished. The polarity is why the pending
bullet gets no row field and no exception report of its own. The pending
bullet **counts** as a sub-phase like any other. So an opened section reads
`sub-phases 1` rather than `0`, and drops out of the
started-but-not-decomposed report the moment it is opened. The bullet is the
signal, and a session's cursor reaching it is what surfaces the section in a
read.

The polarity is also why **minting into a finished section re-opens it**
rather than refusing. A finished section is one whose heading is there with no
pending bullet under it. A body with no heading was never decomposed, so its
first mint re-opens nothing and says nothing. The last step is unconditional and asks nothing about
what came before. So the section simply is unfinished again, which is true,
and is what the operator just asked for. The old tool needed a `--reopen` flag
and three refusals around it, purely to guard a `decomposed = true` head key
somebody had to clear. With the marker in the document there is nothing left
to refuse. The re-open **is announced on stderr**, because a state change
nobody asked for should be loud.

A title carrying `**`, a lone `*` or a newline refuses and writes nothing.
Each would break the strict form the mint is there to write.

**A `write-bullet` writes under one bullet.** A mint writes a bullet's own
line, and a mark writes onto the end of it. A `write-bullet` writes the lines
under it: its continuation, which is what [`show ITEM NAME`](#show) reads
back. The tool indents every line, so the text lines up under the bullet's
own. An indented line is [never counted](#sub-phases), so ordinary text
cannot add a bullet. The text goes after what the bullet already holds, or
replaces it with `--replace`. The bullet's own line is never touched, so its
mark and the cursor naming it stay where they were.

**A write that would change what the reader counts refuses before it writes a
byte.** The run works out the new body first and compares the bullets in it
with the bullets in the old one: how many there are, and each one's line. Only
a fence can make them differ. An odd number of fence lines in the text hides
every line after them, so a bullet below would vanish, or the fence would never
close. The refusal says which. A `write-bullet` from a state that is not
`bulleted` refuses at load by name, as a mark does. It is not the second half
of the capability: a `bulleted` state still needs an add-bullet.
[`annotate`](#annotate) is this repo's.

`bulleted` gives an item **no head key**. What it writes is the body, which is
the workflow's prose rather than a line the tool keeps. So there is nothing to
declare and nothing to redeclare.

### marking

[bulleted](#bulleted) writes a bullet. **A `mark-bullet` disposes of one.**
The transition says which word it writes in `marks`, and its subject is the
bullet rather than the item:

```toml
[transitions.fix-it]
kind  = "mark-bullet"
from  = "carrier"
marks = "fixed"
```

```
fileplan fix-it cache-misses f1
```

Usage is `COMMAND [OPTIONS] ITEM NAME`. `ITEM` is [the handle](#the-handle),
resolved tree-wide as always. `NAME` is the bullet's own name, resolved
**within** that item. `NAME` is a positional rather than a flag, because a
disposition's subject *is* the finding. An option reads as a parameter of the
run, and the bullet is what the run acts on.

A mark is a **second bold run** at the end of the line:

```
- **f1 — The index is rebuilt per call** **fixed**
```

**A markable bullet's line ends at that closing `**`.** Whitespace after it is
fine, and anything else is not. A bullet carrying prose out there **refuses**,
quoting what is in the way. Two ways to clear it, and both keep the prose.
Move it inside the bold run, which is what [a sub-phase](#sub-phases) is
already written as. Or move it onto an indented continuation line under the
bullet, which [`show ITEM NAME`](#show) prints.

The reader reads the run straight after the name's, so a mark written past
prose lands where nothing finds it. Reading the *last* bold run instead would
make every such bullet markable with nobody told. A mark is written once, so
the quiet arm here is a mark nobody can read and a count that never falls.
[The listing](#the-listing) names such a bullet before any run reaches it.

**A second bold run is a mark only if its word is declared.** Take
`- **9-1 — Parse** **Note:** fences are hard`. It has a mark's shape, and
nobody marked it. So the run counts as a mark only where a transition marks
that word into the bullet's state. Any other word leaves the bullet open and
unmarkable, and the listing names it. The line is not anchored at its end
instead, because `--note` writes prose after the mark, as below. A state nothing
marks into has no words declared, so any word reads there.

Nothing new is declared for it. The tool already owns every character of this
bullet's punctuation: the marker, the bold, the dash. So the second run is
read by the same mechanical rule as the first. A state saying what its marks
look like would be machinery with one caller. A [title](#sub-phases) carrying
`**` or a lone `*` already refuses, so the two runs can never be confused.

**The word is the workflow's, and it lives on the transition.** `marks` is a
string, not a flag. `fixed` and `dismissed` are this repo's vocabulary, and
the tool supplies only the bold around them. A state's **vocabulary** is what
the transitions marking into it declare between them. There is no third field
listing it. A list beside the transitions is a second spelling that can
disagree with the first.

A transition of any other kind carries no second positional.

Each of these refuses **by name** at load:

- a mark-bullet into a state that is not [`bulleted`](#bulleted) — there is
  no bullet for the word to go on;
- two transitions marking one state with the **same word**. That is one rule
  with two spellings, and the bullet afterwards could not say which ran;
- a word that is empty, carries a newline, or carries `**`. Each breaks the
  form the writer exists to write, graded through the reader that has to find
  it again.

**A `bulleted` state no add-bullet writes into refuses**, because the capability
could then never do anything. **A `bulleted` state nothing *marks* into loads
clean**, because it is a real shape. [The register](#the-register) records the
same asymmetry for `archives`. Refusing a legitimate declaration is the worse
fault.

**A finding is disposed of once.** Marking one that already carries a mark
refuses, naming the mark it carries. There is one answer on the bullet, rather
than a history nobody can read an answer out of. A name the body does not
carry refuses too, naming the names it does. The [pending bullet](#bulleted)
is not among them. So a run aimed at the marker refuses as "no such name",
rather than marking the thing that says the decomposition is unfinished.

**`--note` says why, and it is the one optional half-generated option.** The
mark says *what* was decided. Every marking command also takes a note, written
on the same line **after** the closing `**`:

```
fileplan dismiss cache-misses f1 --note "Nobody has measured it."
```

```
- **f1 — The index is rebuilt per call** **dismissed** Nobody has measured it.
```

The note is outside the run the mark is read from, so nothing derived moves.
The name, the title, the mark and the count are what they were. And a
[filing](#filing) disposition's default title is still the bullet's own text.
The note is **optional**, unlike `--into` and a close's `--record`, because a
disposition with no reason is the ordinary case. A required one would make
eight runs over a carrier type eight sentences to say nothing. A declared key
called `note` refuses **by name**, which is [the check](#the-check)'s rule. A
marking transition may declare `sets` freely, and so may a move that
archives. So `--note` and a move's `--record` are the two options that can
collide with a key.

Three notes refuse, and for two different reasons rather than one stated three
times. **Empty** says a finding was disposed of for a reason and does not give
it. A **newline** is a measured corruption. A second line opening with `- ` is
a counted, *named* bullet nobody wrote. So the count moves, the names gain
one, and [the ordinal](#sub-phases) jumps past it. `**` breaks nothing today,
since the mark is read out of the second bold run and stops there. It refuses
on the ownership rule above instead. The tool owns every character of this
bullet's punctuation, so emphasis typed into it is a second author of the
form.

**Nothing reads a note back as a field.** Not a row, not [`show`](#show)'s
bullet record, not a head. A field would have to be read out of prose by
pattern, everything after the second bold run. Every other ident this tool
carries is minted and referenced as data. The note is already in `show`'s
verbatim text, which is the read that was buying it before the tool would
write one.

The run writes **one line** and leaves every other byte of the file identical.
Before the run writes any of it, [`--check`](#the-check) says which bullet,
which word, and whether there is a note. The check says the note's presence,
never its content, which is a sentence the operator typed a moment ago. All
three refusals above happen before that first write.

**A disposition can fold its bullet into another.** `merges = true` is a
second rider on `marks`, as [`files`](#filing) is the first, and the two
never sit on one transition. A disposition does one second write, not two. A
folding run takes `--into NAME`, which is required. NAME is the survivor,
another bullet of the same item. The run does three things:

- it marks the bullet with the transition's word, as any mark does;
- it writes the note `Into NAME.`, followed by `--note` when one is given;
- it moves the bullet's continuation under the survivor, so the text has one
  copy. The moved lines are headed `*From 4-3 — Its title:*`.

```
- **4-2 — Parse the head**
  What 4-2 said before.
  *From 4-3 — Parse the body:*
  What 4-3 said.
- **4-3 — Parse the body** **merged** Into 4-2.
```

**The folded bullet is marked, not deleted.** A name never disappears, so no
cursor, no `carried` and no `opened-in` is left naming nothing, and the
[close check](#the-close-check) is satisfied as for any mark. The heading line
over the moved prose is the tool's own, with no workflow word in it, as a
[merge](#merge)'s `### <title>` heading has none.

A fold refuses, writing nothing, on a bullet that is already marked, as every
disposition does. It also refuses on a survivor the body has not got (the
pending bullet included), on the bullet itself as its own survivor, and on a
marked survivor: prose moved under a finished sub-phase is work nobody will
pick up. Last, it refuses on a move that would change the bullets the reader
counts, as [a `write-bullet`](#bulleted) does. Each moved line gives up one
indent and the writer adds it back. So prose lines up as it did, and a fenced
line at column zero gains the indent.

At load, `merges` must be true or false, it is refused beside `files`, and it
is refused on any kind but a mark-bullet. A declared key called `into`
refuses by name, as one called `note` does. [`fold`](#fold) is this repo's.

`marks` gives an item **no head key**, like [bulleted](#bulleted): what it
writes is the body.

### filing

[marking](#marking) disposes of a bullet. **`files` turns it into an item.**
The transition declares where that item goes and which of its keys record
where it came from, in a table:

```toml
[transitions.file-it]
kind  = "mark-bullet"
from  = "carrier"
marks = "filed"

[transitions.file-it.files]
state = "someday-maybe"
item  = "carried-from"
name  = "carried"
```

```
fileplan file-it cache-misses f1 --body "Cache it across calls."
```

One run does three things. It writes the item, it stamps it with where it came
from, and it marks the bullet. Dealing with a carrier means doing that eight
times. The stamping is what turns the carrier's judgment from something thrown
away at filing into a **join**. "Which items came from this carrier" is one
read, and so is "which of its findings are still open".

**Three roles, and each wants a name.** `state` is where the filed item goes.
`item` is the declared key that records the carrier's slug, and `name` the one
that records the bullet's. Those are the tool's own two words, because they
are already what [a bullet's row](#commands) calls them. So a filing
writes down the two halves of the row it acted on. An unknown role refuses by
name, and so does a missing one. The roster is fixed, so both directions are
checkable.

**All three facts are the transition's.** The cursor fields beside
[`sub-phases`](#sub-phases) are on the *state*, because a **reader** needs
them while walking it. The tool reads a cursor off any item in `plan` without
knowing which transition wrote it. Nothing reads provenance in a tool-specific
way.
`--has carried-from=<slug>` is the ordinary filter over a declared key. Only
the **writer** needs to know, so the writer declares it.

**Only a `mark-bullet` takes `files`.** The item is written *from* a bullet.
So a transition that filed without disposing of the bullet would have nothing
saying the finding had been dealt with. The transition would file the finding
again on the next run, which is [marking](#marking)'s "disposed of once"
undone. `files` on any other kind refuses at load, by name.

**A filed item is filed, not placed.** A `files.state` naming a state that
declares `queued`, `numbered` or `claimed` refuses **by name**, saying which
capability. Each of those writes a head key on arrival. Honouring them would
mean running the entry arms against a second destination. Machinery with one
caller is the trap this design is against. The refusal says what to do
instead. File into a plain state, and move the item afterwards with the
command that already does that.

**The title comes from the bullet**, and `--title` overrides it. Eight
findings, eight runs, no prose retyped. The override earns its place twice. A
colliding slug would otherwise be a dead end, and a finding is a *symptom*
where an item is *work*. The provenance lives in keys, so the item's title
need not match the bullet's for the join to hold.

**`--body` is required**, in the words [`idea`](#idea) already refuses with.
An item with no prose is intent somebody pays to re-derive. That rule does not
weaken because the run had a bullet to start from. The finding says what was
observed, and the item says what to do about it. A title that collides refuses
the same way a creating transition's does, through the same helper: one rule,
two callers.

**Both files are named on stderr; stdout stays the item the run moved.** A run
returns the destination of the item it was *given*, uniformly. So
`fileplan file-it ITEM NAME` piped somewhere carries that and nothing else.
[`--check`](#the-check) names the file it would write and reserves nothing.

**A key for the filed item goes inside the `files` table.** Take a workflow
that declares a `defect` key and wants each filed item to carry one. The
workflow names the key under `files.sets`:

```toml
[transitions.file-it.files]
state = "someday-maybe"
item  = "carried-from"
name  = "carried"
sets  = ["defect"]
```

Each key in `files.sets` becomes an option on the run, so `file-it` takes
`--defect`. The run writes the value onto the filed item's head, after the two
provenance keys, and never onto the carrier. A bad value refuses before
either file is written. [The contract](#the-contract) shows the same thing in
a `Files` block: `into someday-maybe, writing defect`.

**`sets` beside `files` refuses at load, by name.** A key in a transition's
own `sets` is written onto the item the run moves, and for a filing
transition that item is the carrier. A workflow writing `sets = ["defect"]`
there almost always meant the filed item. Before the refusal, the run put the
key on the carrier and said nothing. So the refusal names `files.sets` as the
place to write the key. A [close or a merge](#dissolving) takes no `sets` for
the same reason: the transition's own kind makes the field wrong.
`files.sets` also refuses the two provenance keys, because the tool writes
both of them itself.

**To tag an item that is already filed, declare a transition from its state
to itself.** No filing is involved. The transition `sets` the key, and the run
writes the key onto the item where it stands:

```toml
[transitions.tag-defect]
kind = "edit"
from = "someday-maybe"
sets = ["defect"]
```

The transition also needs the `help` every transition carries.
`fileplan tag-defect cache-misses --defect NAME` then rewrites the item in
place.

### the handle

An item is named by a **unique prefix of its slug**, git-style. It resolves
over the whole tree rather than one directory. A full slug always names
itself, ahead of a longer slug it prefixes. Otherwise filing
`item-files-the-head` would make `item-files` unaddressable for the rest of
its life. An ambiguous prefix refuses, naming its candidates. One matching
nothing refuses, naming its near misses. The tool never guesses which item was
meant.

**An ambiguous prefix names ten candidates**, one per line, then how many
more there are. So nothing is hidden, and the refusal stays readable.

**A near miss is scored against the start of each slug.** The handle is
compared with each slug's prefix of the same length. A short typo is then
measured against what it was the start of, and a long slug is not beaten by
short strangers. Ties go to the slug sharing more hyphen-words, and three at
most are offered. Nothing below a cutoff is offered at all.

**`show` also finds a live item by its number.** `fileplan show 28` prints
the row of the item in [the register](#the-register) carrying 28. `fileplan
show 28-1` prints the same record as `fileplan show SLUG 28-1`: that item,
and its bullet named 28-1. The bullet name goes through the same reader as
any other, so a name the body has not got refuses as "no such name". Giving
two different sub-phase names, as in `show 28-1 28-2`, refuses, because the
tool never guesses which was meant.

**A slug outranks a number.** `show 28` tries the number only when no slug
starts with `28`. This is the rule above, one step further: a full slug
names itself ahead of a longer slug it prefixes, and a slug names itself
ahead of a number. The number is tried only where the slug rules found
nothing.

**A number is never a handle for a verb that writes.** Only `show` reads a
number. A number is minted when an item enters the state and dropped when it
leaves, so an item that goes out and comes back carries a new number. A verb
that acted on a number could act on an item other than the one the person
had in mind. The row `show` prints carries the slug, so every verb after it
has its handle. A handle that is all digits, or that starts with digits and
a hyphen, gets one more line when a writing verb refuses it. Where a filed
item carries that number, the line names the item and the command that
reaches it:

```
ERROR: no item starts with "24-1"
  24-1 is a sub-phase of `exits`: `fileplan show exits 24-1`
```

Where no filed item carries it, the number is an archived section's, if it
is anyone's. `show` refuses it too, and so does every other verb. The line
then says that [`fileplan show`](#show) finds a live section by its number,
and that a verb that writes takes a slug.

Resolution is tree-wide. So a transition aimed at an item in another state
says **where the item actually is**, rather than that no such item exists.

## Transitions

Each transition below is declared in `plan.toml`, and two of its fields say
what an item's head must hold for the run to go. `requires` lists keys the
head must carry. `refuses` is a table, and each entry takes one of two forms.
A list of values refuses an item carrying any of them. `true` refuses an item
carrying the key at all, whatever its value:

```toml
refuses = { decision = true, size = ["XL"] }
```

A key present but empty carries nothing, so it passes either form. `false`
refuses at load, because it would say nothing: write `true`, or a list. Both
forms are checked by the same function a row's [`commands`](#commands) uses,
so the row and the run agree. `refuses` reads the head as it is before the
run.

A third field says what the run writes. `sets` is a list or a table. In the
list, each key becomes an option on the run, `--decided DATE` for `decided`.
In the table, `true` means the same thing, the way `true` means any value
under `refuses`. Anything else in the table is a **fixed value**: the run
writes it, and nobody passes it. The list is shorthand for a table with every
key `true`. A decision record's `finalise` needs both halves:

```toml
[transitions.finalise]
kind     = "move"
from     = "drafts"
to       = "decisions"
requires = ["decided"]
sets     = { decided = true, status = "accepted" }
```

A fixed value is graded at load. A key holding one value takes a string, and
a list-valued key takes a list of strings. Neither may be empty, and each
value must be in the key's `values` where it declares some. `{today}` is the
one substitution: the run writes its local date there, in the shape
`--decided 2026-10-18` writes. Any other brace refuses at load, so there is
no escape syntax to learn.

**A fixed value is never an option, and never a default.** A session cannot
override it. If it could, `deprecate` could write `status = "accepted"`, and
the transition's name would no longer say what it writes.

**A key in both `requires` and the options is a required option.** Above,
`finalise` takes a draft that carries no `decided` yet, because this run
supplies one. Without `--decided` the run refuses, and `--help` marks the
option `[required]`. The row's `commands` counts the key as met, since the
item cannot carry a value the session has not given yet. `refuses` still
reads the head before the run, so a transition stamping a value it also
refuses does not refuse itself. A key in `requires` with a fixed value keeps
the plain meaning: the head must already carry it.

### idea

File a new idea into [`someday-maybe`](#someday-maybe). The title is its one
positional argument. The description is `--body`, and `--body -` reads stdin,
so a heredoc works:

```
fileplan idea "A worked example" --body "Why this is worth keeping."
fileplan idea "A worked example" --body - < notes.md
```

The second line takes the body from a file. A redirect needs no heredoc, so
a hook that inspects command text has nothing to trip over.

**Both are required.** An item is a [title](#title) and a description: one
with no prose is intent that somebody pays to re-derive later. Prose kept in
a document of its own comes in the same way: `--body - < docs/templates/simplify-code.md`
files an item bodied from that document.

**At a terminal, a missing body opens `$EDITOR`.** Where stdin and stdout are
both a terminal, a create given no `--body` opens the editor on a short
template whose `#` lines are left out of the item. Closing it with nothing
written files nothing. Anywhere else — a script, a pipe, an agent's session
— the run refuses in one line, `capture needs a body: pass --body TEXT, or
--body - to read it from stdin`, exactly as before the editor existed. The
reason an item needs prose lives here rather than in the refusal.

### queue

Commit to an idea: move it out of [`someday-maybe`](#someday-maybe) and into
[`plan`](#plan), where it takes a place in the order. It takes the
[handle](#the-handle) — a unique slug prefix — and, optionally, where in the
order it goes:

```
fileplan queue a-worked-example                 # appends, 100 past the last
fileplan queue a-worked-example --above item-files
fileplan queue a-worked-example --at 250
```

It is the [first arm](#the-queue) of what generates `--above`, `--below` and
`--at`. The item arrives in the ordered state, so it has no place there yet,
and the run gives it one. See [the queue](#the-queue) for the arithmetic and
for what it refuses.

### requeue

Move an item to another place in [`plan`](#plan)'s order. The same state on
both sides, so it is an in-place write rather than a move. Only the position
changes, and the file does not go anywhere.

It is the [second arm](#the-queue) of what generates `--above`, `--below` and
`--at`: a same-state transition that writes nothing else, so placing the item
is all it does. That is why it carries the three options. [`work`](#work) and
[`decompose`](#decompose) stand in the same ordered state and carry none.

```
fileplan requeue a-worked-example --above item-files
fileplan requeue a-worked-example --at 250      # and the respacing tool
```

Naming no place is **not** a request. `fileplan requeue a-worked-example` on
its own leaves the item exactly where it is, because an item already in the
state [keeps its place](#the-queue) unless asked otherwise.

### retitle

Give an item a new title. The slug is made from the title, so a new slug
moves the file, and every reference to the old slug is pointed at the new
one. The new title is the second positional:

```
fileplan retitle a-worked-example "A better name"
```

`retitle` stays in [`plan`](#plan), and
[`retitle-idea`](#retitle-idea) is the same thing for an idea. Both are of
the [kind](#kinds) `rename`, which stays in its state. A rename is its own
kind rather than an edit, because the tool has to know that the run renames.

The title is a positional rather than `--title`. An
[add-bullet](#bulleted) or a [filing](#filing) already takes `--title`, where
it names something new.

**What gets repointed** is every head value the tool reads as a slug:

* each state's [`dependencies`](#dependencies) key, which is `after` here;
* the key each filing transition names for where an item came from, which is
  [`carried-from`](#carried-from) here;
* each state's [`references`](#references) keys;
* each state's [`opened-for`](#opened-for) key.

`opened-for` is included because a carrier still naming the old slug would
drop out of [the dangle check](#the-dangle-check) without a word. Each edited
file is named on stderr. The same run names each item whose prose still
mentions the old slug, the renamed item included. The tool never rewrites
prose.

**The claim follows the slug.** A claim another session holds refuses, as it
does for any transition. A claim this session holds is moved to the new slug.

**Order of writes.** Every refusal is decided before anything is written.
Then the new file is written, the old one removed, the claim moved and the
references rewritten. A crash partway leaves two files, or `unknown
dependency:` lines, and the default read names both.

**A title that keeps the slug** rewrites the title in place. A change of case
or punctuation is one. Nothing moves and nothing is repointed. A new slug held
by any other file refuses, and so does a title with no letters or digits.

[When a handle changes](procedures.md#when-a-handle-changes) says what a
session does after the run.

### retitle-idea

Give an idea a new title. It is [`retitle`](#retitle) in
[`someday-maybe`](#someday-maybe), and everything said there holds here. What
a session does afterwards is the same too:
[when a handle changes](procedures.md#when-a-handle-changes).

```
fileplan retitle-idea a-worked-example "A better name"
```

### work

Take up a section, and say which sub-phase you are on. The same state on both
sides, like [`requeue`](#requeue), so the section is worked **where it stands**
and never moves to be worked on:

```
fileplan work sub-phases --sub-phase 4-5 --sub-phase-status planned
fileplan work sub-phases --sub-phase-status "in progress"
fileplan release sub-phases
```

It declares `claims = true`, so the first of those [takes the
claim](#the-claimed-state) and the rest keep it. The same holder re-taking is
the same claim, so picking a section up and advancing [the
cursor](#the-cursor) are one transition. `--sub-phase` is graded against the
[sub-phases](#sub-phases) the body carries, before anything is written. It
also refuses onto a bullet already [marked](#marking), which is where saying a
sub-phase is *finished* happens instead.

[`release`](#release) is the session boundary, and nothing auto-releases. A
session that ends without it is caught at its next claim, which [refuses and
names the held item](#the-claimed-state), rather than at a sibling's listing.
Two sessions running the pick read — `list --state plan --lacks claimed-by` — get
disjoint items.

What a session does around a run of `work` is [planning and working a
sub-phase](procedures.md#planning-and-working-a-sub-phase).

### decompose

Write the next sub-phase into a section, or close the decomposition. The same
state on both sides, like [`requeue`](#requeue) and [`work`](#work), so a
section is cut up **where it stands**:

```
fileplan decompose sub-phases
fileplan decompose sub-phases --title "The register"
fileplan decompose sub-phases --title "Close-out" --last
fileplan decompose sub-phases --last
```

`--after NAME` writes the new sub-phase directly after NAME rather than at the
end, and still names it with the next free ordinal:

```
fileplan decompose sub-phases --title "Split from 3" --after 9-3
```

It is an `add-bullet`. That [kind](#kinds) is what gives it `--title`,
`--last` and `--after`, and what keeps them off [`queue`](#queue), [`requeue`](#requeue)
and [`work`](#work). See [bulleted](#bulleted) for the naming, the ordinal, the
pending bullet and the re-open.

It takes **no claim**. Deciding how a section divides is reading and writing
the section, not picking it up. [`work`](#work) is what claims, and its
ownership check still runs here: a section somebody else holds refuses before
anything is written.

What a session does around a run of `decompose` is [decomposing a
section](procedures.md#decomposing-a-section).

### finish

Say a sub-phase is finished, writing `done` onto its bullet. A
[disposition](#marking): its subject is one of the section's
[sub-phases](#sub-phases) rather than the section. So it takes the bullet's
name as a second positional.

```
fileplan show out-of-order              # next-sub-phase names the one to take
fileplan finish out-of-order 12-1       # take one
fileplan finish out-of-order 12-1 --note "The premise held."
```

**Completion is a fact about the sub-phase, and it lives on the sub-phase.**
[The cursor](#the-cursor) is one pair naming **one** bullet. So a section whose
5th and 7th sub-phases are finished, while its 6th is not, has nowhere in its
head to say so. A bullet each has somewhere. That is what the word moving home
buys, and the word itself does not change: `done` is what a finished sub-phase
has always been called.

Same state on both sides, like [`decompose`](#decompose) and [`work`](#work) —
a section is worked where it stands. It takes **no claim**: marking a bullet
is writing the section, not picking it up. [`work`](#work)'s ownership check
still runs, and a section somebody else holds refuses before anything is
written.

It also takes the status key off the head. A sub-phase that is finished is not
at any of the three stages that key names
([sub-phase-status](#sub-phase-status)). And it moves [the
cursor](#the-cursor) onto the bullet it marks.

### skip

Say a sub-phase will not be done at all, writing `skipped` onto its bullet.
[`finish`](#finish)'s shape with the other word, and the second half of what
makes the pair usable. Without it, a sub-phase nobody is going to do has two
exits: a `done` that lies, and a section that can never be finished.

```
fileplan skip out-of-order 12-4 --note "Folded into 12-3."
```

It takes the status key off the head too. A sub-phase nobody is going to do
has stopped as squarely as one that is finished
([sub-phase-status](#sub-phase-status)).

`done` and `skipped` are two words in one vocabulary, and nothing here grades
which a session reaches for. That judgment is the session's, and `--note` is
where its reason goes. A sub-phase is disposed of once, so a bullet already
carrying either word refuses [by name](#marking).

### annotate

Write under a sub-phase: what was planned, what was decided in building, or
what was found. It is a `write-bullet`, so its subject is one bullet, named
as [`finish`](#finish) names one:

```
fileplan annotate out-of-order 12-1 --text - < decided.md
fileplan annotate out-of-order 12-1 --text "One more line."
fileplan annotate out-of-order 12-1 --text - --replace < plan.md
```

`--text` is required, and `-` reads it from stdin. Without `--replace` the
text goes after the lines already under the bullet. With `--replace` it takes
their place. Forget `--replace` and the run appends, which leaves a visible
duplicate and loses nothing. That is the polarity a forgotten flag should fail
in. The tool indents each line, and a blank line stays empty. A replace that
writes back what was there leaves the file unchanged, and says so.

It leaves the bullet's own line alone: its name, its title, its mark and its
note. So a marked bullet takes a write too. This repo writes a sub-phase's
*Decided in building* record at the same moment it marks the bullet. It takes
**no claim**, as [`finish`](#finish) does not, and a section somebody else
holds refuses before anything is written.

It refuses, writing nothing, on a name the body has not got (in the words
[`show`](#show) uses), on empty text, and on text that would change the
bullets the reader counts ([bulleted](#bulleted)). `--check` says which bullet
and how many lines, never the text: `append 3 lines under 12-1`, or `replace
12 lines under 12-1 with 3`.

What a session does around it is [planning and working a
sub-phase](procedures.md#planning-and-working-a-sub-phase).

### fold

Fold one sub-phase into another. It marks the first `merged`, and moves its
prose under the second, which it names with `--into`:

```
fileplan fold out-of-order 12-4 --into 12-3
fileplan fold out-of-order 12-4 --into 12-3 --note "One seam, not two."
```

It is a mark-bullet that [merges](#marking). The folded bullet keeps its name
and gains `**merged** Into 12-3.`, so anything naming it still finds it. Its
continuation goes after everything 12-3 already holds, headed `*From 12-4 —
Its title:*`. [The cursor](#the-cursor) goes to 12-3, not to the bullet
marked, because 12-3 is where the work continues. It takes the status key off
the head, as [`finish`](#finish) and [`skip`](#skip) do.

Both bullets must be unmarked, and they must be two. A section offers `fold`
only while it carries two unmarked bullets. It takes **no claim**.
`--check` gives counts, never the text: `mark 12-4 "merged" with a note, and
move 3 lines under 12-3`. To split a sub-phase instead, see
[`decompose`](#decompose)'s `--after`.

What a session does around it is [decomposing a
section](procedures.md#decomposing-a-section).

### decline

Set a section aside: we chose not to do it. It moves the item out of
[`plan`](#plan) and into [`abandoned`](#abandoned). On the way it **files
the section's [archive entry](#the-register)**. The two are one run, because
the number the entry is filed under is dropped by the move.

```
fileplan decline a-worked-example --record - <<'END'
Why the section was set aside, and how far it got.
END
```

`--record` files the entry with its prose in one run, and `--record -` reads
the prose from stdin. Without `--record` the heading is minted alone, at its
place in the register, and the prose under it is the session's to write by
hand. Minting before filling, as [`decompose`](#decompose) does, is safe here
only because `decline` **moves** the item rather than deleting it. Everything
the record is written from is still readable in `abandoned/`. A transition
that dissolved the item could not fill in afterwards from something that had
gone, which is why [`archive-plan`](#archive-plan) requires `--record`.

It takes **no claim**, like [`decompose`](#decompose). The ownership check
still runs: a section somebody else is holding refuses before either file is
touched. It edits **no inbound edges**, and [dependencies](#dependencies) says
why.

Any state may declare a transition of this shape. `decline` is out of
[`plan`](#plan) here because that is where this workflow's committed work
lives. The tool knows the transition only as "leaves a
[numbered](#the-register) state and files an entry".

### discard

Discard an idea: we are not going to do it. It moves the item out of
[`someday-maybe`](#someday-maybe) and into [`abandoned`](#abandoned).

```
fileplan discard a-worked-example
```

It is a `move` that declares nothing else, and that is its whole difference
from [`decline`](#decline). The difference comes from the state rather than from
the decision. `decline` leaves a [numbered](#the-register) state, so the
number it held has to be released, and filing the entry is what releases it.
`someday-maybe` numbers nothing. There is no entry to file, so the run is a
plain move, like [`queue`](#queue) one direction over.

So the reason lives in the commit rather than in the register. An idea nobody
committed to never earned a section number. Minting one to say it was discarded
would have the record invent work that never happened.

The item is **moved rather than deleted**, like `decline` and for a sharper
reason. An idea is often filed to record an argument rather than to propose
work, and the argument outlives the decision. Everything it held is still
readable in `abandoned/`.

It takes **no claim**. The ownership check still runs.

Without it an idea could be committed to or absorbed and never simply set
aside. [`queue`](#queue) and [`merge`](#merge) were the only ways out, so the
one state whose whole job is holding what nobody has committed to had no way
of letting go. That gap stood until 2026-09-11.

Any state may declare a transition of this shape. `discard` is out of
[`someday-maybe`](#someday-maybe) here because that is where this workflow's
uncommitted ideas live. The tool knows the transition only as "moves an item",
which is what [`queue`](#queue) is too.

### archive-plan

Close a section out: file its [archive entry](#the-register) and remove the
item. It is a [`close`](#dissolving), which takes the file away, and it
declares `archives = true`, which records it. The prose comes in with the run.
The body it is written from goes away with it:

```
fileplan archive-plan exits-archive --record -
```

**Every named sub-phase must be [marked](#marking)**. The head says only that
the section was picked up:

```toml
requires = ["sub-phase"]
```

The `requires` is on this transition. There it grades one way out of `plan`,
and leaves [`decline`](#decline) alone. What a `requires` **cannot** express
lives in [the close check](#the-close-check) instead.
`fileplan list --has commands=archive-plan` is the listing of sections that
could close right now. That is the old tool's `--closeable`, read off
[`commands`](#commands) rather than a flag of its own, and it narrows through
both.

`requires` is the floor a head can carry, and it is what stops a queued,
never-decomposed item closing clean. "Every named bullet is marked" is
**vacuously true** of a section carrying no bullets at all. Which *value* the
status holds gates nothing any more: completion left the head in favour of the
bullet ([the cursor](#the-cursor)).

It takes **no claim**, like [`decline`](#decline). The ownership check still
runs: a section somebody else is holding refuses before anything is deleted.
Unlike `decline` it **clears every inbound edge**, so nothing is left naming
an item that has gone ([dependencies](#dependencies)). It also names every
item whose prose still mentions the section's slug, and rewrites none of that
prose ([dissolving](#dissolving)).

Any state may declare a transition of this shape. `archive-plan` is out of
[`plan`](#plan) here because that is where this workflow's committed work
lives. The tool knows the transition only as "leaves a
[numbered](#the-register) state, files an entry and takes the file away".

What a session does around a run of `archive-plan` is [closing a section
out](procedures.md#closing-a-section-out).

### merge

Absorb an idea into another: the work continues as that one. It is the way out
of [`someday-maybe`](#someday-maybe) that is not [`queue`](#queue). It is
also the fourth way an item leaves.

```
fileplan merge a-second-take-on-drafts --into workflow-as-data
```

It is a [`merge`](#dissolving): the run takes the idea's file away, and points
every edge naming it at the survivor, rather than removing it. `--into` is
**required**, and it resolves tree-wide. The work may continue as an item in
any state.

**Several ideas can merge in one run.** Name each idea before `--into`:

```
fileplan merge a-idea b-idea --into a-section
```

The run takes the lock once. Every idea is checked before anything is
written. If one idea refuses, no idea is merged. The refusal names every
failing idea, one per line. `--check` prints one line per idea, saying what
the run would do to that idea. A real run prints each removed path on
stdout, one per line.

Only a merge takes several items.

**It archives nothing**. `someday-maybe` mints no [number](#the-register), so
there is no entry to name and nothing to write. That is exactly what makes
deleting the original safe here. A deletion in an unnumbered state punches no
hole in the register. Taking the file away without archiving is what lets
this transition be declared at all.

**A merge keeps the absorbed text.** Each absorbed body is appended to the
survivor's body, in the order the ideas were named, with blank lines trimmed
from either end. Where each body goes depends on the survivor's state.

**Into a section whose state is [`bulleted`](#bulleted), each idea becomes a
sub-phase.** The bullet is named by the next free ordinal and titled by the
idea's title, and the idea's body is the bullet's prose, indented under it.
Merging two ideas into a section whose last sub-phase is `37-6` adds these
two bullets ahead of the pending bullet:

```
- **37-7 — Scratch one**
  One.
- **37-8 — Scratch two**
  Two.
```

**The bullet is the record of what was absorbed.** A section keeps each unit
of its work as a sub-phase, so the idea arrives where the section's other
work already is. Every bullet transition works on it at once:
[`annotate`](#annotate) writes under it, [`fold`](#fold) moves its prose under
another bullet, and [`finish`](#finish) or [`skip`](#skip) closes it. Without
this, the section's body has to be rewritten by hand to turn each `###`
block into a bullet, and the commit message is the only list of what went
in.

A section with no sub-phases heading gets one, with the pending bullet. A
section whose decomposition was finished is **re-opened**: the pending bullet
comes back, and the run says so on stderr. The section now holds work that
nobody has planned, and the pending bullet is what asks for another look.

**Anywhere else, each idea goes under a `### <its title>` heading.** An idea
merged into another idea is the usual case.

The survivor's head is not touched, the cursor included, and nothing else
records what was absorbed: every reference now points at the survivor, and
the text is in its body. Absorbed ideas are often the specification, as when
several small fixes become one section, and losing their text would mean
composing the survivor's body by hand first.

**There is no split transition.** Once an absorbed idea is a bullet, filing
it back out as an item is what the [`files`](#filing) rider on a marking
transition already does. A split transition would be new machinery for a
case the rider covers. This repo's `plan` declares no such filing
transition, because no section here has needed one.

**This is not a second copy.** The absorbed file is deleted in the same run,
so only one copy of the text remains. The fact has moved house rather than
been duplicated. Earlier releases kept the survivor byte-identical unless the
run passed `--carry`. Nobody merged without it, so the carry is now what a
merge does, and a plan.toml still declaring `carries` refuses by name.

A merge has two refusals of its own beside the ones every run has, and both
come before any write. The first is a composed body that its state's
[sub-phase](#sub-phases) check refuses. A second `Sub-phases` heading carried
in under `###` would otherwise break the next listing. The second is a
survivor another session holds, because a merge writes prose into a body
that session may be rewriting. Have the claim released to get past it.

A merge into a `bulleted` section has three more, also before any write, and
one refusing idea stops the whole run:

- **An idea whose title the bullet cannot carry.** A title holding `**`, a
  lone `*` or a newline would break the bold run that names the bullet. The
  refusal names the idea.
- **A section missing a field its `sub-phase-name` needs.** The bullet would
  have no name. The refusal names the field.
- **An idea whose body would change the bullets the section reads.** The
  body is indented, so only a fence can do that: a fence the idea opens and
  never closes hides every bullet after it.

An idea that brings its own `Sub-phases` heading is not refused here,
because the indented heading is prose under the bullet.

It takes **no claim**, like [`decline`](#decline) and
[`archive-plan`](#archive-plan). The ownership check runs on the idea being
absorbed, and on the survivor, which the run writes to.

Any state may declare a transition of this shape. `merge` is out of
[`someday-maybe`](#someday-maybe) here for two reasons. That is where this
workflow's uncommitted ideas live, and it is the state that is safe to delete
from. The tool knows the transition only as "leaves its state, takes the file
away, points the edges at a survivor, and carries the body there".

### investigate

Open a carrier for an investigation. It creates rather than moves, like
[`idea`](#idea), so its positional is the title and its prose comes in with
`--body`:

```
fileplan investigate "Why the listing is slow" --body "..."
```

It is a `create` that declares nothing else. Creating the item is the whole
of it, and the findings arrive afterwards, one [`note`](#note) at a time. A
create's body comes from `--body`. Writing a bullet reads a body first, which is why that is
an `add-bullet` of its own, and [`bulleted`](#bulleted) says what it reads it
for.

### note

Write a finding into an open carrier. The same state on both sides, like
[`decompose`](#decompose), so a carrier accumulates findings **where it
stands**:

```
fileplan note listing-is-slow --title "The index is rebuilt per call"
fileplan note listing-is-slow --title "…and never cached" --last
```

It is an `add-bullet`, which is what gives it `--title` and `--last`. The
bullets it writes are named `f1`, `f2`, … — the form [`carrier`](#carrier)
declares. Everything else is [bulleted](#bulleted)'s: the three steps, the
ordinal, the pending bullet and the re-open, exactly as they are for
[`decompose`](#decompose). This transition is the same mechanism, pointed at a
state with no register.

### fix-it

Say a finding is fixed. A [disposition](#marking): its subject is one bullet of
the carrier, and it writes `fixed` onto it.

```
fileplan show listing-is-slow           # next-sub-phase names the first open one
fileplan fix-it listing-is-slow f1      # take one
```

**If it's simple, consider just fixing it.** Dealing with a carrier very often
means filing eight new items. Some of them are trivial things that would have
been cheaper to do on the spot than to file, triage and pick up again. The rule
lives here rather than in prose nobody opens, because a session that asks this
transition for its contract meets it on the way past.

It declares `marks`. That is what gives it the second positional, and what
makes `next fix-it` a read of findings rather than of items. It is otherwise
the same state on both sides, like [`note`](#note): a carrier is disposed of
where it stands.

### dismiss

Say a finding is not worth acting on, writing `dismissed` onto its bullet.
[`fix-it`](#fix-it)'s shape with the other word.

A finding is disposed of once, so a bullet already carrying either word refuses
[by name](#marking). Which of the two a session reaches for is a judgment
nothing here grades. They are two words in the same vocabulary, and what
separates them is the [`doc`](#the-contract) each one carries.

### file-it

File a finding as an item of its own, writing `filed` onto its bullet. The
third [disposition](#marking), and the one the carrier exists for. The other
two say a finding is dealt with, and this one says it is **work**.

```
fileplan file-it cache-misses f1 --body "Cache it across calls."
```

**If it's simple, consider just fixing it.** Dealing with a carrier very often
means filing eight new items. Some of them are trivial things that would have
been cheaper to do on the spot than to file, triage and pick up again. So
[`fix-it`](#fix-it) carries the same rule, and this is the transition the rule
is aimed away from. It lives here rather than in prose nobody opens, because a
session that asks this transition for its contract meets it on the way past.

It declares `marks` **and** [`files`](#filing). That is what gives it the
second positional, `--title` and `--body`, and what makes one run file the item
and dispose of the finding together. The item lands in
[`someday-maybe`](#someday-maybe) carrying [`carried-from`](#carried-from) and
[`carried`](#carried). [`queue`](#queue) is what commits to it afterwards.
Filing a finding is not deciding to do it.
