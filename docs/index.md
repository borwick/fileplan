# The documents

What this repo ships to be read, and what each one is for. The `README.md` is
the first five minutes. These are the rest.

## start here

- [README.md](../README.md) — what the tool is, and the shipped loop run end
  to end.
- [initialization.md](initialization.md) — the walk from an empty folder to a
  tree an agent can work in. `init` is the first command, and every command in
  it was run.
- [retrofit.md](retrofit.md) — the other walk. Your tree already has work in
  it, and `init` is the wrong first command.

## the vocabulary

- [reference.md](reference.md) — the reference. One section per word a plan file can
  hold, and the one home for each. Every `doc =` in the worked example points
  here.
- [procedures.md](procedures.md) — what a session *does* around a run, which
  the reference leaves out on purpose. A transition's section of the method
  links here where it has a procedure.

## the interpreter an agent reads

- [fileplan/SKILL.md](../src/fileplan/skills/fileplan/SKILL.md) — runs one
  declared transition, whichever it is. The skill reads what a transition
  declares, never its name.
- [do-next/SKILL.md](../src/fileplan/skills/do-next/SKILL.md) — the worked
  example of composing runs. `do-next` picks an arm, then hands each
  transition to the skill above.

## the worked example

- [examples/plan.toml](../examples/plan.toml) — fileplan's own workflow, as a
  declaration to read or copy. Every word it holds has its section in the
  reference. Its register, [examples/plan-archive.md](../examples/plan-archive.md),
  sits beside it, empty, as a fresh tree's is.
- [templates/simplify-code.md](templates/simplify-code.md) — the pass that
  keeps the code easy to change. File it as an item with
  `fileplan idea "Simplify the code" --body - < docs/templates/simplify-code.md`.

## provenance

- [ai-disclosure.md](ai-disclosure.md) — how this tool was written, and by
  what. The disclosure level, who did what, and why the git history does not
  carry it.

