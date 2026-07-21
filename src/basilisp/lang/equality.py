"""Clojure-shaped value equivalence and hash-key normalization.

Python deliberately makes numerically equal values of different concrete types
interchangeable: ``1 == 1.0 == Decimal("1")`` and all three share a hash.  JVM
Clojure instead makes ordinary ``=`` type-sensitive across its integer, ratio,
floating, and decimal numeric families.  Persistent maps and sets must use the
same relation as ``=`` or their lookup contract becomes inconsistent.

The wrappers below exist only inside hash-backed Basilisp collections.  Public
iteration and lookup always expose the original Python values.
"""

from __future__ import annotations

import decimal
import numbers
from fractions import Fraction
from typing import Any


def numeric_family(value: Any) -> str | None:
    """Return Clojure's portable equality family for a numeric host value."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return "integer"
    if isinstance(value, Fraction):
        # Clojure's reader and Ratio runtime normalize denominator-one values
        # back to an integer before equality or hashing observes them.
        return "integer" if value.denominator == 1 else "ratio"
    if isinstance(value, decimal.Decimal):
        return "decimal"
    if isinstance(value, float):
        # Python cannot retain a separate JVM float class. Both Clojure float
        # and double host values use this family after crossing the boundary.
        return "floating"
    return None


def numeric_equiv(left: Any, right: Any) -> bool:
    """Implement Clojure ``=`` for portable numeric families."""

    left_family, right_family = numeric_family(left), numeric_family(right)
    if left_family is None and right_family is None:
        return left == right
    if left_family != right_family:
        return False
    return left == right


def numeric_compare(left: Any, right: Any) -> bool:
    """Implement Clojure ``==`` numeric equivalence for supported values."""

    left_family, right_family = numeric_family(left), numeric_family(right)
    if left_family is None or right_family is None:
        raise TypeError(f"Expected numeric values, got {left!r} and {right!r}")
    return left == right


class EquivalenceKey:
    """A hash key that keeps Clojure-unequal numeric families distinct."""

    __slots__ = ("value", "family")

    def __init__(self, value: Any, family: str) -> None:
        self.value = value
        self.family = family

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, EquivalenceKey)
            and self.family == other.family
            and numeric_equiv(self.value, other.value)
        )

    def __hash__(self) -> int:
        # The family is part of the hash as well as equality, unlike Python's
        # raw number hashes. Decimal and Fraction retain their own exact hashes.
        return hash((self.family, self.value))


def key(value: Any) -> Any:
    """Return a private storage key for a public Basilisp value."""

    family = numeric_family(value)
    if family is None or isinstance(value, EquivalenceKey):
        return value
    return EquivalenceKey(value, family)


def unkey(value: Any) -> Any:
    """Recover the public value from a private hash-storage key."""

    return value.value if isinstance(value, EquivalenceKey) else value
