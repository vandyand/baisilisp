"""The runtime representation of Clojure character values.

Python has no character type: indexing a string produces another ``str``. Clojure
does distinguish a character from a one-character string, so a character must be an
independent immutable value at the Basilisp language boundary.
"""

from __future__ import annotations

import functools
from typing import Any

_NAMES = {
    "\n": "newline",
    " ": "space",
    "\t": "tab",
    "\f": "formfeed",
    "\b": "backspace",
    "\r": "return",
}


def lrepr(
    value: str, *, human_readable: bool = False, print_readably: bool = True
) -> str:
    """Render a character using Clojure reader syntax."""
    if human_readable or not print_readably:
        return value
    return f"\\{_NAMES.get(value, value)}"


@functools.total_ordering
class Character:
    """A single Unicode code point with Clojure character semantics."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        if not isinstance(value, str) or len(value) != 1:
            raise ValueError("Character value must be a string of length 1")
        self._value = value

    @property
    def value(self) -> str:
        """The host-string representation for Python interop."""
        return self._value

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return lrepr(self._value)

    def __hash__(self) -> int:
        # Clojure's character hash is its Unicode ordinal. Collisions with other
        # unequal values are permitted and preserve portable set/map ordering.
        return ord(self._value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Character) and self._value == other._value

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, Character):
            return NotImplemented
        return self._value < other._value


def character(value: str | Character) -> Character:
    """Return ``value`` as a :class:`Character`, validating host strings."""
    if isinstance(value, Character):
        return value
    return Character(value)
