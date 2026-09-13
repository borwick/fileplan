"""`fileplan init`: write the starter tree a consumer's first declaration is.

The tool ships one example declaration, and `init` copies the example
verbatim. There is no templating and no codegen.

The example is a tree rather than a file: a plan.toml, plus the documents its
pointers resolve against. So this module reads the example through
`fileplan.declaration.load` rather than parsing it again. The state
directories `init` makes come out of the loaded declaration. Nothing here
knows what they are called.

The example resolves through `importlib.resources` rather than by walking up
from this file. After an install there is no repository to walk up from.

Every refusal is computed before the first write, so a refused `init` leaves
nothing behind. `init` refuses over an existing install, and over one in any
parent directory. Discovery walks up, and a nested declaration would shadow
the tree above it.

`skills` is here for the resolution rather than for `init`, which writes no
skills.

See docs/method.md#init and docs/method.md#the-skills
"""

from __future__ import annotations

import os
from importlib import resources
from pathlib import Path

from fileplan.declaration import PLAN_TOML_NAME, Refusal, load

#: The package directory the example tree ships in.
STARTER = "starter"

#: And the one the interpreter skills ship in. Named for what ships rather
#: than after any agent vendor's directory: where a consumer puts it is their
#: harness's business. See docs/method.md#the-skills
SKILLS = "skills"


def skills() -> Path:
    """The directory the shipped interpreter skills are in.

    A fact about the tool rather than about a workflow, which is why it
    answers before a declaration loads. Asked of the package rather than of
    Python, because a tool install puts fileplan in an environment of its own.

    Raises `Refusal` where the package is not on a real filesystem, since
    printing that path would name a directory gone by the time anybody reads
    it.
    """
    resource = resources.files(__package__) / SKILLS
    try:
        here = Path(os.fspath(resource))
    except TypeError:
        here = None
    if here is None or not here.is_dir():
        raise Refusal(
            f"fileplan is installed somewhere its {SKILLS} directory is not a "
            "real one. An importer that keeps the package in an archive hands "
            "out no path. Copy the skills out of the source distribution "
            "instead"
        )
    return here


def install(target: Path) -> list[Path]:
    """Write the starter tree into `target`. Returns what it wrote, in order.

    Raises `Refusal`, writing nothing, where the tree is already an install,
    is under one, or already holds a path this would write.
    """
    target = Path(target)
    with resources.as_file(resources.files(__package__) / STARTER) as source:
        sources = sorted(path for path in source.rglob("*") if path.is_file())
        declaration = load(source / PLAN_TOML_NAME)
        # The state directories first, from the declaration rather than a
        # list here, then whatever directories the files need.
        directories = [Path(state.path) for state in declaration.states.values()]
        relatives = [path.relative_to(source) for path in sources]
        directories += sorted(
            {relative.parent for relative in relatives} - {Path(".")} - set(directories)
        )

        _refuse_an_existing_install(target)
        for relative in relatives:
            if (target / relative).exists():
                raise Refusal(
                    f"{target / relative} already exists, and `fileplan init` "
                    "writes nothing over a file that is already there"
                )
        for directory in directories:
            occupant = target / directory
            if occupant.exists() and not occupant.is_dir():
                raise Refusal(
                    f"{occupant} is a file, and the declaration names it as a "
                    "directory. Move the file aside, or run `fileplan init` "
                    "somewhere else"
                )

        written: list[Path] = []
        for directory in directories:
            (target / directory).mkdir(parents=True, exist_ok=True)
            written.append(target / directory)
        for relative, path in zip(relatives, sources):
            (target / relative).write_bytes(path.read_bytes())
            written.append(target / relative)
    return written


def _refuse_an_existing_install(target: Path) -> None:
    """Refuse where a plan.toml is already in scope for `target`.

    A parent's counts as well as its own, because discovery walks up like git:
    a declaration written here would shadow the tree above it, and every read
    would change meaning with the directory it ran from.
    """
    here = target.resolve()
    if (here / PLAN_TOML_NAME).is_file():
        return _already(here / PLAN_TOML_NAME, "already")
    for directory in here.parents:
        if (candidate := directory / PLAN_TOML_NAME).is_file():
            return _already(candidate, "under a tree that is already")
    return None


def _already(found: Path, said: str) -> None:
    raise Refusal(
        f"{found} exists, so {said} a fileplan install. `fileplan init` "
        "writes a first declaration and will not write over or under one. "
        "Read the existing plan.toml, or run somewhere else"
    )
