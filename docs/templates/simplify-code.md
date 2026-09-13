# Simplify the code

A simplification pass is another level of **check** in plan/do/check/act. The
cycle's check grades one change; this one grades the whole tree, and what it
is for is that the codebase stays easy to maintain and modify.

**What to read.** Both, in this order:

- **What has changed since the last pass** — the commits since the last
  simplify item closed.
- **The whole tree.** A pass that reads only the diff misses what has been
  growing quietly for three sections.

**What to look for.**

- **One home per meaning.** A fact written in two places is a fact that will
  disagree with itself.
- **Redundant code and logic** — two spellings of one rule, an arm that is a
  special case of the one beside it, a helper with one caller.
- **Documentation out of alignment with the code.** Prose describing what the
  code stopped doing is worse than no prose.
- **Content that has grown a lot.** Anything much larger than the last pass
  left it: read it and trim it.
- **Whatever every session reads first, especially.** It is read at the top
  of every run, so a stale or redundant line in it is paid for every time.
- **Unknown unknowns** — traps and issues nobody has noticed, the things we
  would not have thought to grep for.
- **Whether the system is working well as a whole**, not only whether each
  part is small.

**How to run it.** Fan the reading out to subagents, and pick the model to fit
the job — a smaller one for the broad reads — so a comprehensive pass costs
what it is worth. This is the wide pass over the whole tree, rather than a
narrow one over what changed recently.

**Done when:** the suite is green with its count reported, what was simplified
is committed, and what was looked at and deliberately left alone is written
down with the reason — so the next pass does not re-derive it.
