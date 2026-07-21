"""The runtime representation of Clojure UTF-16 character values.

Python has no character type and indexes strings by Unicode code point. Clojure
distinguishes a character from a one-character string and, like the JVM, makes a
character one UTF-16 code unit. The helpers here retain ordinary Python ``str``
storage for interop while exposing Clojure's code-unit operations at the language
boundary.
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
_UTF16_MAX = 0xFFFF
_SURROGATE_START = 0xD800
_SURROGATE_END = 0xDFFF


def _validate_code_unit(value: str) -> None:
    if not isinstance(value, str) or len(value) != 1 or ord(value) > _UTF16_MAX:
        raise ValueError("Character value must be a single UTF-16 code unit")


def utf16_length(value: str) -> int:
    """Return the number of UTF-16 code units in a Python string."""

    return len(value.encode("utf-16-le", "surrogatepass")) // 2


def iter_utf16_units(value: str):
    """Yield the individual UTF-16 code-unit strings in ``value``.

    ``surrogatepass`` preserves intentionally unpaired surrogates, which are valid
    Clojure character values even though they are not standalone Unicode scalar
    values.
    """

    encoded = value.encode("utf-16-le", "surrogatepass")
    for offset in range(0, len(encoded), 2):
        yield chr(int.from_bytes(encoded[offset : offset + 2], "little"))


def utf16_unit_at(value: str, index: int) -> str:
    """Return UTF-16 code unit ``index`` from ``value``.

    Negative indexes are deliberately rejected instead of inheriting Python's
    end-relative indexing, matching Clojure's indexed collection contract.
    """

    if not isinstance(index, int) or isinstance(index, bool):
        raise TypeError("string index must be an integer")
    if index < 0:
        raise IndexError(f"String index {index} out of bounds")
    encoded = value.encode("utf-16-le", "surrogatepass")
    offset = index * 2
    if offset >= len(encoded):
        raise IndexError(f"String index {index} out of bounds")
    return chr(int.from_bytes(encoded[offset : offset + 2], "little"))


def utf16_substring(value: str, start: int, end: int | None = None) -> str:
    """Slice ``value`` with Clojure/JVM UTF-16 indexes and bounds checks."""

    if not isinstance(start, int) or isinstance(start, bool):
        raise TypeError("substring start index must be an integer")
    if end is not None and (not isinstance(end, int) or isinstance(end, bool)):
        raise TypeError("substring end index must be an integer")
    length = utf16_length(value)
    actual_end = length if end is None else end
    if start < 0 or actual_end < start or actual_end > length:
        raise IndexError(
            f"substring indexes {start} through {actual_end} out of bounds for length {length}"
        )
    encoded = value.encode("utf-16-le", "surrogatepass")
    return encoded[start * 2 : actual_end * 2].decode("utf-16-le", "surrogatepass")


def lrepr(
    value: str, *, human_readable: bool = False, print_readably: bool = True
) -> str:
    """Render a character using Clojure reader syntax."""
    if human_readable or not print_readably:
        return value
    if _SURROGATE_START <= ord(value) <= _SURROGATE_END:
        # Writing an unpaired surrogate directly can fail on ordinary UTF-8 text
        # streams. The reader's standard four-hex-digit escape reconstructs it.
        return f"\\u{ord(value):04X}"
    return f"\\{_NAMES.get(value, value)}"


@functools.total_ordering
class Character:
    """A single UTF-16 code unit with Clojure character semantics."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        _validate_code_unit(value)
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
    """Return ``value`` as a :class:`Character`, validating UTF-16 unit input."""
    if isinstance(value, Character):
        return value
    return Character(value)
