---
name: fileplan
description: Run one declared fileplan transition end to end. Ask the tool for the contract, check the item against it, read what the contract names, then run the transition. Use when invoked as /fileplan, and whenever a composed session needs one transition run.
---

# /fileplan

One procedure for **any** transition the declaration holds — this repo's or a
consumer's. The tool holds the vocabulary. This skill only interprets the
vocabulary, and the sections the tool points at are the program.

Invoked as `/fileplan <transition> <item>`. The transition and the item are
all you bring, and everything else is asked of the tool. **Nothing below
branches on which transition it is.** Reasoning from a transition's name
rather than from the tool's answer is the bug this procedure exists to
prevent.

Every command below is spelled `fileplan`, as installed. fileplan's own
source tree runs it as `uv run fileplan`.

## 1. Ask for the contract

```bash
fileplan <transition> --help
```

What comes back is the options the run takes, and then the contract. The
contract says where the item goes, what the run `Requires` and `Refuses`, and
any keys it `Drops`. The contract also names the kind and the options the run
`Declares`, and a `Reading` block. `fileplan --json` gives every transition's
contract at once, as data.

**The contract is the example to follow.** The tool generates the contract
from the declaration you actually have. So the contract is right for a
transition nobody has ever seen before.

## 2. Ask whether this item passes

```bash
fileplan <transition> <item> --check
```

Pass whatever options the contract said the run requires; a check is of a
**run**, so a required option is still required.

* **rc 2** — report the refusal verbatim and **stop**. Nothing was written,
  and the message is the one a real run gives. Do not go on to read the
  sections or attempt the change: the point of asking first is not to spend
  the session on an item the transition was never going to take.
* **rc 0** — the sentence on stdout says what the run will do. Carry on.

The check is also the ownership guard: a claimed item held by another session
refuses here, before anything is read.

## 3. Read what the contract named

Every pointer in `Reading`. The transition's own section says what the
transition and the values it takes **mean**. Where a session also has
something to **do** around the run, that section links to a procedure: follow
the link and read the procedure too. If the section links to no procedure,
there is nothing further to read — that silence is the workflow saying so.

If the contract has no `Reading` block at all, the workflow wrote no section
for this transition, and its `help` line is the whole procedure. Read the
`help`, and carry on.

Read them before acting. They are the program.

## 4. Do what those sections say

Guided by what `Declares` names, never by the transition's name. The first
line is the transition's **kind**, and any lines after it are the options it
declares.

The kind says what the run does:

* **`create`** — the run writes a new item, titled by the first argument,
  into the state the contract names.
* **`move`** — the run moves the item to another state.
* **`reorder`** — the run changes the item's place in its state's order, and
  writes nothing else.
* **`edit`** — the run writes keys onto the item where it stands.
* **`rename`** — the run gives the item a new title, the second argument, and
  moves the file to the slug that title makes. The run repoints every head
  that named the old slug. It only names the prose that still does, so act
  on each line it prints.
* **`close`** — the item's file is deleted by the run. Read whatever you
  still need out of it first; afterwards only git has it.
* **`merge`** — each item named is deleted, its body is appended to the
  survivor `--into` names under its title, and the edges pointing at it are
  repointed at the survivor rather than cleared. Read the survivor
  afterwards.
* **`add-bullet`** — the run writes into the item's body in a strict form.
  Expect to mint first and fill the prose in afterwards.
* **`mark-bullet`** — the run's subject is one **bullet** rather than the
  item, and what it writes onto that bullet is the declaration's own word.
  The offer for such a transition lists bullets, so the second argument is a
  bullet's name.

The options after the kind add to what it does:

* **`claims`** — the run picks the item up for this session, and it is the run
  that takes it. Nothing takes a claim beforehand.
* **`files`** — the run writes a **second item**, into the state the
  declaration names, carrying the two declared keys that say where it came
  from. It rides on a `mark-bullet`, so the same run disposes of the bullet
  the new item was written from.
* **`archives`** — the run files a record of the item. On a `close`, compose
  that record **in full before running**, because what it is written from
  goes with the file.

A kind with no options after it does what the kind says and nothing else.

## 5. Run it

The same command as step 2 with `--check` taken off, and the same options.

## 6. There is no step 6

The postconditions are the tool's. Every refusal a transition can raise is
computed **before** the run writes anything. A run that exited 0 has already
satisfied every refusal, so nothing is left to verify afterwards. What the run
did that you did not ask for, the run says on stderr. What the run wrote, the
run prints on stdout.

If the run refuses at rc 2 having passed the check, the tree changed under
you. Read the refusal and stop rather than retrying.
