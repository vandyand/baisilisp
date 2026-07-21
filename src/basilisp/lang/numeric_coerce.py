"""Clojure-compatible scalar numeric coercions on Python values.

Python constructors are intentionally more permissive than Clojure's casts:
for example, ``float("1")`` succeeds and ``int(True)`` is ``1``.  These
helpers keep those host conveniences out of the Basilisp language boundary
while retaining Python's unbounded ``int`` representation internally.
"""

from __future__ import annotations

import decimal
import math
import numbers
import struct
from fractions import Fraction
from typing import Any

from basilisp.lang import numbers as lisp_numbers
from basilisp.lang.character import Character


def _type_error(value: Any) -> TypeError:
    return TypeError(f"Expected a Clojure numeric value, got {value!r}")


def _is_number(value: Any) -> bool:
    """Return whether ``value`` belongs to Clojure's portable numeric domain."""

    return isinstance(value, decimal.Decimal) or (
        isinstance(value, numbers.Number) and not isinstance(value, (bool, complex))
    )


def _numeric(value: Any, *, allow_character: bool = False) -> Any:
    if allow_character and isinstance(value, Character):
        return ord(value.value)
    if not _is_number(value):
        raise _type_error(value)
    return value


def _truncated(
    value: Any,
    *,
    allow_character: bool = False,
    infinity_bits: int | None = None,
) -> int:
    """Truncate as a Java primitive conversion would.

    NaN narrows to zero. Infinite values either fail (checked casts) or narrow
    to the signed endpoint of the requested unchecked primitive width.
    """

    value = _numeric(value, allow_character=allow_character)
    if isinstance(value, decimal.Decimal):
        if value.is_nan():
            return 0
        if value.is_infinite():
            if infinity_bits is None:
                raise ValueError(f"Cannot coerce infinite value {value!r}")
            return (
                (1 << (infinity_bits - 1)) - 1
                if value > 0
                else -(1 << (infinity_bits - 1))
            )
    elif isinstance(value, float):
        if math.isnan(value):
            return 0
        if math.isinf(value):
            if infinity_bits is None:
                raise ValueError(f"Cannot coerce infinite value {value!r}")
            return (
                (1 << (infinity_bits - 1)) - 1
                if value > 0
                else -(1 << (infinity_bits - 1))
            )
    return int(value)


def _signed(value: int, bits: int) -> int:
    value %= 1 << bits
    sign_bit = 1 << (bits - 1)
    return value - (1 << bits) if value >= sign_bit else value


def checked_integer(value: Any, bits: int, *, allow_character: bool = True) -> int:
    """Return a checked signed primitive integer conversion."""

    result = _truncated(value, allow_character=allow_character)
    lower, upper = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    if not lower <= result <= upper:
        raise ValueError(f"Value out of range for signed {bits}-bit integer: {value!r}")
    return result


def unchecked_integer(
    value: Any,
    bits: int,
    *,
    allow_character: bool = False,
    infinity_bits: int | None = None,
) -> int:
    """Return an unchecked signed primitive conversion with two's-complement wrap."""

    return _signed(
        _truncated(
            value,
            allow_character=allow_character,
            infinity_bits=bits if infinity_bits is None else infinity_bits,
        ),
        bits,
    )


def _double(value: Any) -> float:
    value = _numeric(value)
    try:
        return float(value)
    except OverflowError:
        return math.inf if value > 0 else -math.inf


def checked_float(value: Any) -> float:
    """Return a checked JVM single-precision floating-point conversion."""

    result = _float32(value)
    if math.isinf(result):
        raise ValueError(f"Value out of range for float: {value!r}")
    return result


def unchecked_float(value: Any) -> float:
    """Return a JVM single-precision floating-point conversion."""

    return _float32(value)


def _float32(value: Any) -> float:
    value = _double(value)
    try:
        return struct.unpack("!f", struct.pack("!f", value))[0]
    except OverflowError:
        return math.inf if value > 0 else -math.inf


def double(value: Any) -> float:
    """Return a JVM double conversion, using Python's double-precision float."""

    return _double(value)


def bigint(value: Any) -> int:
    """Coerce a number or integer string to Basilisp's arbitrary-precision int."""

    if isinstance(value, str):
        return int(value)
    value = _numeric(value)
    if isinstance(value, decimal.Decimal):
        if not value.is_finite():
            raise ValueError(f"Cannot coerce non-finite value {value!r} to bigint")
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"Cannot coerce non-finite value {value!r} to bigint")
    return int(value)


def bigdec(value: Any) -> decimal.Decimal:
    """Coerce a number or numeric string to a finite decimal.Decimal."""

    if isinstance(value, str):
        result = decimal.Decimal(value)
    else:
        value = _numeric(value)
        if isinstance(value, Fraction):
            result = lisp_numbers.divide(
                decimal.Decimal(value.numerator), decimal.Decimal(value.denominator)
            )
        elif isinstance(value, float):
            # BigDecimal.valueOf(double), used by Clojure, receives the decimal
            # spelling of the double rather than Python Decimal's binary expansion.
            result = decimal.Decimal(str(value))
        else:
            result = decimal.Decimal(value)
    if not result.is_finite():
        raise TypeError(f"Expected a finite number: {value}")
    return result


def unchecked_char(value: Any) -> Character:
    """Return an unchecked UTF-16 character conversion."""

    if isinstance(value, Character):
        return value
    return Character(chr(_truncated(value, infinity_bits=64) % (1 << 16)))
