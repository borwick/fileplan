"""Point the whole suite at the fixture declaration, not at the repo's own.

This runs at collection, before any test module imports the package. It uses
``setdefault`` so an operator can still aim the suite somewhere else from the
outside.
"""

import os
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "plan.toml"

os.environ.setdefault("FILEPLAN_PLAN_TOML", str(FIXTURE))


#: Every file a tmp-tree copy of the fixture declaration needs beside it: the
#: declaration, the document its `doc =` pointers resolve against, the one its
#: `policy =` pointer does, the archive the `numbered` register reads, and the
#: two documents its templates name. Named here rather than repeated in each
#: module's `tree` fixture — 4-5 added a name, 6-2 another and 9-1 two more,
#: and six copies of a two-name tuple is how the seventh copy ends up missing
#: one. Every one of them is graded at **every** invocation, so a copy short
#: of one refuses rather than quietly running.
FIXTURE_FILES = (
    "plan.toml",
    "method.md",
    "training.md",
    "orchard-archive.md",
    "hardwood-cuttings.md",
    "softwood-cuttings.md",
)


#: Every name `fileplan.declaration.DERIVED_KEYS` could give a row,
#: gates ignored. The suite's own flatten, and test scaffolding rather than a
#: constant in the tool: nothing under `src/` compares against the ungated
#: roster — `Declaration.derived` is the *gated* one and is what the row
#: layer and the filters read — so a copy there was a name only the tests
#: loaded. Imported here, after the environment above is set, so the three
#: modules that grade "no key is carried and unreachable" share one answer
#: instead of spelling the flatten three times.
from fileplan.declaration import DERIVED_KEYS  # noqa: E402

DERIVABLE_KEYS = tuple(name for _, names in DERIVED_KEYS for name in names)
