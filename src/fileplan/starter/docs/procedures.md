# Procedures

What a session *does*. `docs/method.md` says what each word in `plan.toml`
means. This document says how to run one, which is the one thing the method
deliberately leaves out.

A section here is reached by a `policy =` pointer on a transition. The
shipped `/fileplan` skill reads it out of the transition's contract. So a
section nothing points at is one no session will ever be sent to. Name a
section after the **procedure** rather than after the transition. Another
repo's transition for the same procedure has a different name.

`fileplan init` wrote this file as a stub with one section, because
`plan.toml` declares one `policy =` pointer. Most transitions need none. A
transition whose meaning is the whole of it says so by carrying no pointer,
and its contract then has no *Running it* block at all.

## working an item

Write down what you actually do when you work an item. What do you read
first? What do you decide before starting, rather than during? What do you
write down so the next session does not have to ask? And where do you stop?

Until you answer, this section is the thing a session is told to read and
finds empty. That is the loudest possible reminder that it is yours to write.
