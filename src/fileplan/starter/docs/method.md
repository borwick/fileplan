# Method

What every word in `plan.toml` means, in this repo. One section per word, and
one home per meaning. If a word has a section here, this is where it is
explained and nowhere else.

`fileplan init` wrote this file as a stub. Every section below is a heading
that a `doc =` pointer resolves against. The tool checks each pointer every
time it runs, so a heading you delete refuses by name. Each section also
carries one sentence saying what is yours to write. **Replace the
sentences.** Nothing writes here but you.

The tool's own words are documented with the tool, not here. Run
`fileplan COMMAND --help` for that command's contract. Run `fileplan` with
no arguments for the whole declaration.

## States

A state is a directory. An item is a file in one.

### inbox

Where an idea lands before anybody has decided about it. Write down what
belongs here, and — more usefully — what does not.

### plan

Where an idea goes once you have committed to it. Items here hold a place in
an order, and each is minted a number when it arrives. The order says what to
do next. The number names the item for good, and it is what the archive entry
is filed under. Write down what being here commits you to.

## Keys

A key is a fact an item carries in its head.

### status

How the work is going. The declared words are `in progress` and `waiting`.
Write down what each one means to you, and how long a thing may wait.

## Transitions

A transition moves an item between states, or creates one. Each is a command.

### capture

Log an idea in the inbox. Write down what a good title looks like, and how
much goes in the body this early.

### queue

Commit to an idea, and move it into the plan. Write down what you decide
before you queue something, and how you choose where in the order it goes.

### work

Say how the work is going. This is the one transition here with a procedure:
what a *session* does around a run of it is [working an
item](procedures.md#working-an-item). This section is the meaning, that one
is the procedure.

### archive

Close an item out. Its entry is filed in `docs/archive.md` under its number,
and its file is removed. Write down what a good record says, since the entry
is all that is left.
