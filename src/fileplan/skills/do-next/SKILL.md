---
name: do-next
description: Run this repo's cycle on one item in `plan` — the head item, or the one a section number, sub-phase name or slug prefix names. Write its sub-phases if it has none, plan its next sub-phase if it does, or implement the pending plan if one is saved. Use when invoked as /do-next.
disable-model-invocation: true
---

# /do-next

One command for this repo's cycle. **Read the tree, then act.** Which arm you
are in is a fact about the working tree, not something to ask about.

What is here is the **composition**: which arm, what to ask, when to stop.
Every transition an arm reaches runs through
[`/fileplan`](../fileplan/SKILL.md), which asks the tool what the run takes
and what to read. Nothing below spells an invocation or an option. A second
copy of either would rot the first time the declaration changed.

Every command below is spelled `fileplan`, as installed. fileplan's own
source tree runs it as `uv run fileplan`.

## Which item

Invoked as `/do-next [WHICH]`. The argument is optional, and it says which
item in `plan` the session is for:

| What you were given | How to find the item |
|---|---|
| Nothing | the head item: the lowest position in `fileplan list --state plan` |
| Anything else: a slug prefix, a number such as `20`, or a sub-phase name such as `20-3` | `fileplan show WHICH` |

`show` finds a live section by its number, and a sub-phase name by its
section and its bullet. Either way the row it prints names the slug, and
every verb after it takes the slug, because a verb that writes never takes a
number.

If nothing matches, or the item found is not in `plan`, **stop and say so**.
Never fall back to the head item: a session on the wrong section is worse than
a session that asks.

## Which arm

Run this too, always:

```bash
ls local/plans/ 2>/dev/null   # a pending plan, if any
```

| What you find | Arm |
|---|---|
| A plan in `local/plans/` for the chosen item | **C — implement it** |
| The chosen item shows `sub-phases 0` | **A — mint the section's sub-phases** |
| Otherwise | **B — plan the next sub-phase** |

The facts come out of the listing and the `ls`. `sub-phases` is counted off
the item's body by the tool, so nothing here reads the body to find out where
the session is, and the cursor is not a thing to move by hand.

If `local/plans/` holds a plan for some other item, stop and say so. Either
the tree is in a state nobody intended, or another section's plan is waiting,
and which to take up is the user's call.

## Which transition

Ask the tool. `fileplan` prints every declared transition and, under
`Declares`, the halves each one declares — **that is what you select on, never
the transition's name.**

| What the item needs | The half |
|---|---|
| sub-phases written into its body | `mints` |
| to be picked up, and the cursor moved | `claims` |
| a sub-phase said to be over | `marks` |
| to be closed out | `archives` **and** `dissolves` |

Then run it through [`/fileplan`](../fileplan/SKILL.md), which asks the
contract for the rest.

If two transitions in the listing declare the same half, read their `help`
lines there and choose between them. That judgment is this skill's; what the
run then requires is the contract's.

`release` is the exception, and it is not an exception to the rule: it is the
tool's own reserved word, present in any declaration that claims, rather than
a transition this workflow declared. It ends the session's hold.

## Before any arm: the reading

In arms A and B, call `EnterPlanMode` **before** the reading. Both arms end by
presenting with `ExitPlanMode`, and a session that reads and drafts outside
plan mode leaves the user to type the switch themselves. Arm C does not enter
it, because arm C implements.

The repository's own agent instructions name the documents and the order.
Read them.
Read them even when the item looks self-explanatory. Then, for this item:

- The item itself — `cat` it whole.
- The section its **Decides from** line names, in the document the item's
  `draft` key points at.
- Whatever the contract's `Reading` and `Running it` blocks name, once
  `/fileplan` has asked for them. Those are the program; this skill is not.

## Arm A — mint the section's sub-phases

The item has a decision, a done line, and nothing minted into its body yet.

1. Do the reading above.
2. Take the transition that `mints` through `/fileplan`. Its contract points
   at the procedure — the questions to ask, how the sub-phases are sized, and
   why the mint comes before the prose that fills it in. One run per
   sub-phase, and the last one carries the close-out. The procedure is also
   where it says to mint **as few as the section needs**.
3. Commit staging that one path, and say the section is ready for the next
   pass.

## Arm B — plan the next sub-phase

Take the sub-phase `fileplan list` names in **`next-sub-phase`**. It comes
with `sub-phases` and `sub-phases-left`. The procedure the `claims`
transition's `Running it` block names says how to read the three together.
Read that section before planning anything.

One reading of the three is this skill's own, because it picks the arm. A
`next-sub-phase` of `pending` means the sub-phases themselves are what is
left. That is arm A again.

1. Do the reading above, plus the code the sub-phase touches.
2. Present with `ExitPlanMode`. On acceptance: `mkdir -p local/plans`, write
   the plan **verbatim** to `local/plans/<item-slug>--<n>.md`.
3. Move the cursor to that sub-phase, at the status the procedure names for a
   plan that is saved but not yet implemented. Take the transition that
   `claims` through `/fileplan`, then `release`. The cursor rides in the same
   commit as the plan.
4. Tell the user the plan is saved and they can clear, and **stop**. Do not
   start implementing. If they say to continue instead, go straight to arm C
   in this session.

The `claims` transition's contract points at a procedure. The procedure says
what a saved plan has to stand on its own without. A session that has cleared
brings no memory to the plan.

## Arm C — implement the pending plan

1. Read the plan file. It is the spec; implement it as written.
2. Build it, then follow that same procedure from *Running it* on: how to
   report, what goes in the item body, and why the head change rides in the
   sub-phase's own commit rather than trailing it.
3. Take the transition that `marks` — its subject is the **bullet**, not the
   item — and then `release`, both through `/fileplan`. Then commit staging
   the specific paths. **Never `git add -A`** — a sibling session may share
   this tree. Subject: `Sub-phase N-M: <what it did>`. Then remove the plan
   file.

## Closing a section

The last sub-phase is the close-out. **Every** named bullet has to carry a
mark, the close-out's own bullet included. Where the cursor sits gates
nothing. So the last bullet marked is the close-out's, and then the transition
that both `archives` and `dissolves` takes the item away.

Compose the archive entry **in full before that run**. The item's body is what
the entry is written from, and the body goes with the item. The contract's
`Declares` block says as much by naming both halves. The procedure the
contract points at says what the close rests on and what the run costs.

Both are single transitions, so both go through
[`/fileplan`](../fileplan/SKILL.md).

## What not to do

- **Do not batch the planning of several sub-phases.** It reads efficient and
  is not: the shape of a section changes on contact with the previous
  sub-phase's code. One sub-phase here was absorbed into its neighbour, and
  another corrected, each while the one before it was being written.
- **Do not build a capability this repo has no earned case for.** A
  capability wanted at n=1 is a guess. The trap is a generic engine with a
  planning-shaped default.
- **Do not run tree-wide destructive git**, since a sibling session may be
  holding edits in the same tree that nothing has committed yet.

## Why this skill is gated and `/fileplan` is not

`disable-model-invocation` rides here and nowhere else. `/do-next` is the
**session boundary**, and starting a session is the user's act. `/fileplan` is
what every arm delegates each transition to. Gated as well, `/fileplan` would
leave the composition unable to execute its own instructions. Each arm would
stop at the cursor move and ask the user to type the delegate. The boundary
would then sit in the middle of a session rather than at its edge. Do not add
the key to `/fileplan` for symmetry. The tool already guards every write below
this point, computing each refusal before the first write.

`do-next` is a **session**, not a transition, and the declaration can hold no
transition for a session. A `policy =` reaches a section of the workflow's
procedures, so a session nothing can point at would orphan a section. What a single run needs lives in the procedures, and what composes
several runs lives here.
