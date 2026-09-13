# How this was written

`fileplan` was written with Claude Code. This page says what that means, so
nobody has to guess from the commit log.

## the level

**AI-generated with human prompting and review.** That is one of the four
levels in the W3C AI content disclosure vocabulary, and it is the one that
fits. The other three do not. No part of this tree is unreviewed output, and
no part of it is hand-written code an assistant only tidied.

## who did what

John Borwick directed the work. He made every design call, and reviewed every
line before it landed. Claude Code wrote the code, the tests and the
documents. The models were Claude Opus 5 and Claude Fable 5.1.

The copyright and the licence are John Borwick's, in [LICENSE](../LICENSE).
Claude is not named as an author in `pyproject.toml`, and that is deliberate.
The US Copyright Office holds that purely machine-generated material carries
no copyright. A co-author line there would assert something this project does
not mean.

## why the git history does not say it

Claude Code writes a `Co-Authored-By` trailer into each commit it makes. The
history behind this repository was rewritten before publication, and those
trailers did not survive it. This page is where that record lives now. That
is why the disclosure is a document rather than a commit convention.

## no endorsement

Anthropic did not build `fileplan`. Anthropic does not sponsor it, and does
not endorse it. Claude Code is Anthropic's tool, and it was used here the way
any tool is used.
