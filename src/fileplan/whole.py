"""Whole numbers: the package's one rule for what counts as one.

A bool is an `int` in Python, so `isinstance(value, int)` would read a stored
`true` as 1. Every place, number and pid is tested here instead.

A leaf: it imports nothing from the package, so a module that
`fileplan.declaration` imports can use it too. `fileplan.declaration`
re-exports it.
"""

from __future__ import annotations

from typing import Any


def whole(value: Any) -> bool:
    """Whether `value` is a whole number: an `int` that is not a `bool`."""
    return isinstance(value, int) and not isinstance(value, bool)
