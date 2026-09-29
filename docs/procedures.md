# The procedures

What a session **does** around a run: the questions to ask before it, what a
value commits you to, what the run costs that nothing else warns you about.
`docs/method.md` says what each transition and key *means*. This document says
what to do. A transition reaches its section through
[`policy =`](method.md#the-interpreter).

Sections are named after the **procedure**, not after the transition that
points at one. A consumer's workflow has different transitions and the same
procedures. The
pointer is what joins the two, so nothing here is titled with a word out of
this repo's own `plan.toml`.

## decomposing a section

A section arrives with a decision, a done line and no sub-phases. What comes
out is a body of bullets, each one session's worth.

1. **Ask the section's deferred questions, one per turn**, with
   `AskUserQuestion`. They are listed in the item under *Back burner to ask
   when planned*, and they were held back deliberately to this moment.
   Batching them hides the course-correction signal. That signal is what
   deferring them buys.
2. Propose the sub-phases, and propose **as few as the work needs**. Each is
   **one session**: plan it, accept, clear, run it, commit. Each carries a
   *done when* a stranger could check from the tree and the tool's output —
   not from the conversation that produced it.

   The count is a **cost**, not a description of the work. One sub-phase buys
   one planning session, one saved plan, one clear and one commit. That
   overhead is the same whether the sub-phase is four lines or forty. Token
   spend is the governing requirement, and a plan is discarded by design, so a
   section cut finer than the work spends the budget on planning rather than
   on the work. Cut where the shape **changes on contact** with the previous
   sub-phase's code. Where it does not change, do not cut.

   **The close-out is a job, not automatically a bullet of its own.** Where one
   session can do the work and close the section, mint one sub-phase and say
   so in the body. Name the cost while you are there: a close-out sharing a
   session with code is where a close-out gets skimped.
3. Present with `ExitPlanMode`. On acceptance this is a **document edit, not
   code**: apply it in the same session rather than saving a plan for the
   next one.
4. **Mint the bullets with the command**, one run per sub-phase, and mark the
   final one `--last`. The heading, the names and the *pending* bullet all
   come from the tool, in the strict form it counts and reads
   ([bulleted](method.md#bulleted)). The names take the form the state
   declares, `<number>-<ordinal>` here. Until `--last` lands the section goes
   on reading as pending, and a decomposition stopped half way says so.
5. **Then fill each bullet in by hand.** `--title` mints only the bold line,
   and a title carrying `**`, a lone `*` or a newline refuses — so the
   sentences and the *done when* under each bullet are written after the
   mint. This is **mint, then fill**, not one command.
6. Commit, staging that one path.

## planning and working a sub-phase

The listing names which sub-phase is next in `next-sub-phase`, computed off
the body. Do not go looking for it in the body yourself. It comes with two
others. `sub-phases` is the count, and `sub-phases-left` is how many of them
carry no mark. Read the trio together. A count with no `next-sub-phase` and
nothing left is a decomposition that is **finished**. No count at all is an
item in a state that counts none.

**Planning it.** Read the item, the draft section it decides from, and the
code the sub-phase touches.

- **The decomposition is a proposal, not a contract.** A sub-phase here has
  been folded into its neighbour while that neighbour was being planned. The
  two were one seam, and shipping them apart would have left a worse middle
  state. Another's filed bullet was wrong about a record's shape and was
  corrected before any code was written. If a bullet is wrong, say so and
  propose the change — that is the gate working.
- **Decide what the documents already answer; ask what they do not.** Where
  you decide, record the short rationale in the plan, so it reaches the item
  body when the change commits. Where a real fork remains, ask **one**
  question. Expect roughly one such decision per sub-phase, and expect it to
  be load-bearing.
- The plan must **stand on its own**: the executing session will not have the
  planning conversation. Name the files, the decisions and their rationale,
  the done line and the verification. Save it under `local/plans/`, named for
  the item.
- **The done line names the section's own governing measure.** A section is
  graded on a number or a rule of its own. The done line has to name that
  measure. The suite and whatever else the sub-phase turns on go beside it. A
  done line that leaves the measure out lets work pass. The section then has
  to redo it. One section gated a sub-phase on its pasted transcripts
  matching. The prose floor was the measure, and the done line never named it.
  Eight sections of two documents then shipped unread against that floor. A
  later sub-phase had to widen to catch them.

**`planned` means exactly that**: a plan is saved in `local/plans/` and is
waiting for a session to pick it up
([sub-phase-status](method.md#sub-phase-status)). Say the plan is saved, and
**stop**. The plan surviving a `/clear` is what stopping buys.

**Running it.** The plan is the spec. If it turns out to be wrong mid-flight,
say so in a sentence and keep going under a stated assumption rather than
silently re-scoping. If a fork appears that the plan did not anticipate, ask
one question. Then verify and report faithfully. That means the suite green
with its count, the listing in the shape the plan predicted, and
`git show --stat` naming the paths the plan named and no others.

**Then update the item body**: record the decisions made along the way in
that sub-phase's own bullet. This is the durable record. The section's archive
entry is assembled from it.

**Then mark the bullet with the command, never by hand.** It is the transition
the bare `fileplan` listing shows declaring `marks`, whose subject is the
*bullet* rather than the item. Pass `--note` for why, where the word alone
does not say it ([marking](method.md#marking)). The run takes the status key
off the head as it goes, so the next listing shows a cursor and no status.
That is where the last session was, with nothing claiming it is still at work
([sub-phase-status](method.md#sub-phase-status)).

**The cursor moves with the command, never by hand**, and it moves *before*
the commit. The head change then rides in the sub-phase's own commit rather
than trailing it. The head is not the body, and updating the bullet does not
cover it. That is how a cursor goes stale, left naming one sub-phase while two
more are planned and shipped. **A stale key is worse than an absent one.** The
listing presents it with the same authority as the fields the tool writes and
cannot get wrong. Nothing auto-releases, and ending the session is its own run
([release](method.md#release)). Afterwards, `rm` the saved plan: it is spent,
and its content is in the item body and the commit now.

## closing a section out

Closing out is the **last** sub-phase's job, whether or not that sub-phase is
only the close-out. Where it is only the close-out it is **not a writing
session**. Each `docs/method.md` section lands in the sub-phase that
introduced its vocabulary. The one-home guards run at every commit, so a
`doc =` written before its section is a red suite in between. A section of one
sub-phase satisfies that rule the same way. Its vocabulary and its close-out
are the same session, so nothing can land early. The close-out does three
things. It reconciles the method document. It fixes what the section
superseded **outside** it, starting with whatever file every session reads
first. And it writes the archive entry, mirroring the previous section's
exactly.

A section closes on **evidence**. Every done line is named with the passing
test that checks it, by test name rather than by line number. A mark on a
bullet is read by `next-sub-phase`, by `sub-phases-left` and by the
close-out's own refusal. What it says is that a session *finished the
sub-phase*, not that the done line was met. The entry's done lines are what
the close rests on, and a test name is what each of them rests on.

What the run costs, so the next close-out does not rediscover it:

- the record is **required** and the item body is **deleted by the same run**,
  so compose the entry in full *before* running the command. Mint-then-fill
  cannot work here ([dissolving](method.md#dissolving));
- the command mints the `## <number>. <title>` heading itself, so the record
  is **prose only**, with no `##` line of its own. `###` subheadings inside it
  are safe: the register grades `##` alone;
- it **clears every inbound edge** and names each edited file on stderr, so
  no referent is hand-edited;
- **every named sub-phase has to carry a mark first**, the close-out's own
  included, and the run names the ones that do not. Where the cursor sits
  gates nothing ([the close check](method.md#the-close-check)). So `fileplan
  next` for the transition whose `policy =` points here is the read that says
  whether a section is closeable. A forgotten sub-phase blocks the close
  rather than passing it;
- the claim is freed by the run itself, so nothing is released afterwards;
- `git add` the deleted path to stage the removal; there is no `git rm`;
- if the entry needs fixing afterwards, edit the archive document. The item
  body is gone from the tree, and only git has it.
