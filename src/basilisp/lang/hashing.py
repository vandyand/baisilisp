"""Portable Clojure ``hash`` / ``hasheq`` algorithms.

Clojure's public ``hash`` is deliberately separate from a host object's native
hash code.  It uses signed 32-bit Murmur3-based hashes for values participating
in language equality, making hashes deterministic across processes and keeping
the collection contract consistent with ``=``.  Python's built-in hashes are
salted for strings and vary in width, so they cannot implement that contract.
"""

from __future__ import annotations

import decimal
import math
import struct
from collections.abc import Mapping, Set
from fractions import Fraction
from typing import Any, Iterable

from basilisp.lang.character import Character, iter_utf16_units
from basilisp.lang.interfaces import IMapEntry, INamed, ISeq, ISequential

_MASK_32 = (1 << 32) - 1
_MASK_64 = (1 << 64) - 1
_INT_32_SIGN = 1 << 31
_GOLDEN_RATIO_32 = -1640531527


def _int32(value: int) -> int:
    """Return ``value`` narrowed to a signed JVM ``int``."""

    value &= _MASK_32
    return value - (1 << 32) if value & _INT_32_SIGN else value


def _uint32(value: int) -> int:
    return value & _MASK_32


def _rotate_left_32(value: int, amount: int) -> int:
    value = _uint32(value)
    return _uint32((value << amount) | (value >> (32 - amount)))


def _mix_k1(value: int) -> int:
    value = _uint32(value * 0xCC9E2D51)
    value = _rotate_left_32(value, 15)
    return _uint32(value * 0x1B873593)


def _mix_h1(hash_basis: int, value: int) -> int:
    hash_basis = _uint32(hash_basis) ^ _uint32(value)
    hash_basis = _rotate_left_32(hash_basis, 13)
    return _uint32(hash_basis * 5 + 0xE6546B64)


def _fmix(hash_basis: int, length: int) -> int:
    hash_basis = _uint32(hash_basis) ^ _uint32(length)
    hash_basis ^= hash_basis >> 16
    hash_basis = _uint32(hash_basis * 0x85EBCA6B)
    hash_basis ^= hash_basis >> 13
    hash_basis = _uint32(hash_basis * 0xC2B2AE35)
    hash_basis ^= hash_basis >> 16
    return _int32(hash_basis)


def _hash_long(value: int) -> int:
    if value == 0:
        return 0
    unsigned_value = value & _MASK_64
    hash_basis = _mix_h1(0, _mix_k1(unsigned_value & _MASK_32))
    hash_basis = _mix_h1(hash_basis, _mix_k1(unsigned_value >> 32))
    return _fmix(hash_basis, 8)


def _big_integer_hash(value: int) -> int:
    """Mirror ``java.math.BigInteger.hashCode`` for arbitrary Python ints."""

    if value == 0:
        return 0
    magnitude = abs(value)
    words: list[int] = []
    while magnitude:
        words.append(magnitude & _MASK_32)
        magnitude >>= 32
    hash_basis = 0
    for word in reversed(words):
        hash_basis = _int32(31 * hash_basis + word)
    return _int32(hash_basis if value > 0 else -hash_basis)


def _integer_hash(value: int) -> int:
    if -(1 << 63) <= value < (1 << 63):
        return _hash_long(value)
    return _big_integer_hash(value)


def _double_hash(value: float) -> int:
    # Clojure normalizes -0.0 before delegating to Double.hashCode.  Java's
    # doubleToLongBits canonicalizes all NaN payloads as well.
    if value == 0.0:
        return 0
    if math.isnan(value):
        bits = 0x7FF8000000000000
    else:
        bits = struct.unpack(">Q", struct.pack(">d", value))[0]
    return _int32((bits ^ (bits >> 32)) & _MASK_32)


def _decimal_hash(value: decimal.Decimal) -> int:
    """Mirror Clojure's normalized ``BigDecimal`` hash behavior."""

    if value.is_zero():
        return 0
    if not value.is_finite():
        # Clojure BigDecimal cannot represent infinities or NaN. Preserve a
        # deterministic host fallback for values only Python can construct.
        return _string_hash(str(value))
    sign, digits, exponent = value.as_tuple()
    # Decimal.normalize() observes the active Python decimal context and can
    # round a large coefficient. Java BigDecimal.stripTrailingZeros() does
    # not, so remove zeroes directly from the exact representation.
    digits = list(digits)
    while len(digits) > 1 and digits[-1] == 0:
        digits.pop()
        exponent += 1
    unscaled = 0
    for digit in digits:
        unscaled = unscaled * 10 + digit
    if sign:
        unscaled = -unscaled
    scale = -exponent
    # Clojure reader BigDecimals retain an arbitrary-precision coefficient;
    # its hasheq consequently follows BigInteger.hashCode even when a value
    # would fit JVM long storage.
    return _int32(31 * _big_integer_hash(unscaled) + scale)


def _ratio_hash(value: Fraction) -> int:
    # Clojure Ratio delegates to its Java BigInteger numerator/denominator
    # hash codes rather than their ``hasheq`` values.
    return _int32(
        _big_integer_hash(value.numerator) ^ _big_integer_hash(value.denominator)
    )


def _java_string_hash(value: str) -> int:
    hash_basis = 0
    for unit in iter_utf16_units(value):
        hash_basis = _int32(31 * hash_basis + ord(unit))
    return hash_basis


def _string_hash(value: str) -> int:
    return _hash_int(_java_string_hash(value))


def _hash_int(value: int) -> int:
    if value == 0:
        return 0
    return _fmix(_mix_h1(0, _mix_k1(value)), 4)


def _hash_unencoded_chars(value: str) -> int:
    units = [ord(unit) for unit in iter_utf16_units(value)]
    hash_basis = 0
    for index in range(0, len(units) - 1, 2):
        word = units[index] | (units[index + 1] << 16)
        hash_basis = _mix_h1(hash_basis, _mix_k1(word))
    if len(units) % 2:
        hash_basis ^= _mix_k1(units[-1])
    return _fmix(hash_basis, 2 * len(units))


def _hash_combine(left: int, right: int) -> int:
    return _int32(left ^ (right + _GOLDEN_RATIO_32 + (left << 6) + (left >> 2)))


def _symbol_hash(value: INamed) -> int:
    return _hash_combine(
        _hash_unencoded_chars(value.name), _java_string_hash(value.ns or "")
    )


def _named_hash(value: INamed) -> int:
    symbol_hash = _symbol_hash(value)
    if type(value).__module__ == "basilisp.lang.keyword":
        return _int32(symbol_hash + _GOLDEN_RATIO_32)
    return symbol_hash


def hash_ordered(values: Iterable[Any]) -> int:
    """Return Clojure's ``Murmur3.hashOrdered`` for an iterable."""

    hash_basis = 1
    count = 0
    for value in values:
        hash_basis = _int32(31 * hash_basis + clojure_hash(value))
        count += 1
    return mix_collection_hash(hash_basis, count)


def hash_unordered(values: Iterable[Any]) -> int:
    """Return Clojure's ``Murmur3.hashUnordered`` for an iterable."""

    hash_basis = 0
    count = 0
    for value in values:
        hash_basis = _int32(hash_basis + clojure_hash(value))
        count += 1
    return mix_collection_hash(hash_basis, count)


def mix_collection_hash(hash_basis: int, count: int) -> int:
    """Return Clojure's ``Murmur3.mixCollHash`` result."""

    return _fmix(_mix_h1(0, _mix_k1(hash_basis)), count)


def clojure_hash(value: Any) -> int:
    """Return the portable signed 32-bit Clojure hash for ``value``.

    Basilisp language values are handled before the generic host fallback.  A
    Python-only object without a Clojure analogue retains its native hash, but
    is narrowed so the result still has the Clojure ``int`` shape.
    """

    if value is None:
        return 0
    if isinstance(value, bool):
        return 1231 if value else 1237
    if isinstance(value, int):
        return _integer_hash(value)
    if isinstance(value, Fraction):
        if value.denominator == 1:
            return _integer_hash(value.numerator)
        return _ratio_hash(value)
    if isinstance(value, decimal.Decimal):
        return _decimal_hash(value)
    if isinstance(value, float):
        return _double_hash(value)
    if isinstance(value, Character):
        return ord(value.value)
    if isinstance(value, str):
        return _string_hash(value)
    if isinstance(value, INamed):
        return _named_hash(value)
    if isinstance(value, IMapEntry):
        return hash_ordered((value.key, value.value))
    if isinstance(value, Mapping):
        hash_basis = 0
        count = 0
        for key, member in value.items():
            # ``Murmur3.hashUnordered`` receives map entries, whose hasheq is
            # their ordered two-item hash. Do not feed the resulting integer
            # back through ``clojure_hash`` a second time.
            hash_basis = _int32(hash_basis + hash_ordered((key, member)))
            count += 1
        return mix_collection_hash(hash_basis, count)
    if isinstance(value, Set):
        return hash_unordered(value)
    if isinstance(value, (ISequential, ISeq)):
        return hash_ordered(value)
    return _int32(hash(value))
