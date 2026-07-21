"""Python-hosted representations for Clojure primitive arrays.

The Clojure constructors return mutable JVM arrays whose elements are coerced on
construction and assignment.  Basilisp uses small mutable Python containers instead:
``ByteArray`` is a ``bytearray`` subclass so it remains usable by binary Python APIs;
the other primitive arrays are typed ``list`` subclasses.  The representations retain
the important Clojure boundary behaviour--default values, fixed-width integer wrapping,
and coercion on ``aset``--without inventing JVM class objects.
"""

from __future__ import annotations

import math
import numbers
import struct
from collections.abc import Iterable, Iterator
from typing import Any, TypeVar

from basilisp.lang.character import Character, iter_utf16_units


def _integer(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, numbers.Number):
        raise TypeError(f"primitive array element must be numeric, got {value!r}")
    return int(value)


def _signed(value: Any, bits: int) -> int:
    value = _integer(value) % (1 << bits)
    sign_bit = 1 << (bits - 1)
    return value - (1 << bits) if value >= sign_bit else value


def _unsigned_byte(value: Any) -> int:
    return _integer(value) % 256


def _numeric_float(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Number):
        raise TypeError(f"primitive array element must be numeric, got {value!r}")
    return float(value)


def _float32(value: Any) -> float:
    value = _numeric_float(value)
    try:
        return struct.unpack("!f", struct.pack("!f", value))[0]
    except OverflowError:
        return math.copysign(math.inf, value)


class _PrimitiveList(list[Any]):
    """A list which coerces values whenever its contents are mutated."""

    default: Any = None

    def __init__(self, values: Iterable[Any] = ()) -> None:
        super().__init__(self._coerce(value) for value in values)

    @classmethod
    def _coerce(cls, value: Any) -> Any:
        return value

    @classmethod
    def _assignment(cls, value: Any) -> Any:
        return cls._coerce(value)

    def __setitem__(self, index: int | slice, value: Any) -> None:
        if isinstance(index, slice):
            super().__setitem__(index, (self._coerce(item) for item in value))
        else:
            super().__setitem__(index, self._coerce(value))

    def append(self, value: Any) -> None:
        super().append(self._coerce(value))

    def extend(self, values: Iterable[Any]) -> None:
        super().extend(self._coerce(value) for value in values)

    def insert(self, index: int, value: Any) -> None:
        super().insert(index, self._coerce(value))

    def clone(self) -> _PrimitiveList:
        return type(self)(self)

    def assign(self, index: int, value: Any) -> Any:
        """Apply Clojure ``aset``'s checked primitive assignment semantics."""
        super().__setitem__(index, self._assignment(value))
        return value


class BooleanArray(_PrimitiveList):
    default = False

    @classmethod
    def _coerce(cls, value: Any) -> bool:
        if not isinstance(value, bool):
            raise TypeError(f"boolean array element must be bool, got {value!r}")
        return value


class _FixedIntArray(_PrimitiveList):
    bits: int
    default = 0

    @classmethod
    def _coerce(cls, value: Any) -> int:
        return _signed(value, cls.bits)

    @classmethod
    def _assignment(cls, value: Any) -> int:
        value = _integer(value)
        limit = 1 << (cls.bits - 1)
        if not -limit <= value < limit:
            raise OverflowError(
                f"value {value!r} is outside the signed {cls.bits}-bit array range"
            )
        return value


class ShortArray(_FixedIntArray):
    bits = 16


class IntArray(_FixedIntArray):
    bits = 32


class LongArray(_FixedIntArray):
    bits = 64


class FloatArray(_PrimitiveList):
    default = 0.0

    @classmethod
    def _coerce(cls, value: Any) -> float:
        return _float32(value)


class DoubleArray(_PrimitiveList):
    default = 0.0

    @classmethod
    def _coerce(cls, value: Any) -> float:
        return _numeric_float(value)


class CharArray(_PrimitiveList):
    default = Character("\x00")

    @classmethod
    def _coerce(cls, value: Any) -> Character:
        if not isinstance(value, Character):
            raise TypeError(
                f"char array element must be a Basilisp character, got {value!r}"
            )
        return value


class ByteArray(bytearray):
    """Signed Clojure byte access over Python's unsigned binary buffer."""

    default = 0

    @staticmethod
    def _assignment(value: Any) -> int:
        value = _integer(value)
        if not -128 <= value < 128:
            raise OverflowError(
                f"value {value!r} is outside the signed 8-bit array range"
            )
        return value % 256

    def __init__(self, values: Iterable[Any] = ()) -> None:
        super().__init__(_unsigned_byte(value) for value in values)

    def __getitem__(self, index: int | slice) -> int | ByteArray:
        value = super().__getitem__(index)
        if isinstance(index, slice):
            return type(self)(value)
        return _signed(value, 8)

    def __iter__(self) -> Iterator[int]:
        return (self[index] for index in range(len(self)))

    def __setitem__(self, index: int | slice, value: Any) -> None:
        if isinstance(index, slice):
            super().__setitem__(index, (_unsigned_byte(item) for item in value))
        else:
            super().__setitem__(index, _unsigned_byte(value))

    def append(self, value: Any) -> None:
        super().append(_unsigned_byte(value))

    def extend(self, values: Iterable[Any]) -> None:
        super().extend(_unsigned_byte(value) for value in values)

    def insert(self, index: int, value: Any) -> None:
        super().insert(index, _unsigned_byte(value))

    def clone(self) -> ByteArray:
        return type(self)(self)

    def assign(self, index: int, value: Any) -> Any:
        super().__setitem__(index, self._assignment(value))
        return value


PrimitiveArray = TypeVar("PrimitiveArray", bound=_PrimitiveList | ByteArray)


def _size(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        raise TypeError(f"primitive array size must be an integer, got {value!r}")
    if value < 0:
        raise ValueError("primitive array size must not be negative")
    return int(value)


def _values(value: Any, array_type: type[PrimitiveArray]) -> Iterable[Any]:
    if value is None:
        return ()
    if array_type is CharArray and isinstance(value, str):
        return (Character(char) for char in iter_utf16_units(value))
    try:
        return iter(value)
    except TypeError as exc:
        raise TypeError(
            f"primitive array source must be iterable, got {value!r}"
        ) from exc


def _new(
    array_type: type[PrimitiveArray], size_or_values: Any, initial: Any = ...
) -> PrimitiveArray:
    if initial is ...:
        if isinstance(size_or_values, numbers.Integral) and not isinstance(
            size_or_values, bool
        ):
            return array_type([array_type.default] * _size(size_or_values))
        return array_type(_values(size_or_values, array_type))

    size = _size(size_or_values)
    if initial is None:
        return array_type([array_type.default] * size)
    try:
        values = _values(initial, array_type)
    except TypeError:
        return array_type([initial] * size)

    result = array_type([array_type.default] * size)
    for index, value in enumerate(values):
        if index == size:
            break
        result[index] = value
    return result


def boolean_array(size_or_values: Any, initial: Any = ...) -> BooleanArray:
    return _new(BooleanArray, size_or_values, initial)


def byte_array(size_or_values: Any, initial: Any = ...) -> ByteArray:
    return _new(ByteArray, size_or_values, initial)


def char_array(size_or_values: Any, initial: Any = ...) -> CharArray:
    return _new(CharArray, size_or_values, initial)


def short_array(size_or_values: Any, initial: Any = ...) -> ShortArray:
    return _new(ShortArray, size_or_values, initial)


def int_array(size_or_values: Any, initial: Any = ...) -> IntArray:
    return _new(IntArray, size_or_values, initial)


def long_array(size_or_values: Any, initial: Any = ...) -> LongArray:
    return _new(LongArray, size_or_values, initial)


def float_array(size_or_values: Any, initial: Any = ...) -> FloatArray:
    return _new(FloatArray, size_or_values, initial)


def double_array(size_or_values: Any, initial: Any = ...) -> DoubleArray:
    return _new(DoubleArray, size_or_values, initial)


def clone_array(value: Any) -> Any:
    """Copy primitive arrays without discarding their mutation/coercion contract."""
    if isinstance(value, (ByteArray, _PrimitiveList)):
        return value.clone()
    return list(value)


def aset(array: Any, index: int, value: Any) -> Any:
    """Set an element using Clojure's checked primitive-array semantics."""
    if isinstance(array, (ByteArray, _PrimitiveList)):
        return array.assign(index, value)
    array[index] = value
    return value


def vector_of(type_: Any, values: Iterable[Any]) -> list[Any]:
    """Coerce values using Clojure ``vector-of``'s checked primitive semantics."""
    name = getattr(type_, "name", str(type_).lstrip(":"))
    constructors = {
        "boolean": BooleanArray,
        "byte": ByteArray,
        "char": CharArray,
        "short": ShortArray,
        "int": IntArray,
        "long": LongArray,
        "float": FloatArray,
        "double": DoubleArray,
    }
    try:
        array_type = constructors[name]
    except KeyError as exc:
        raise ValueError(f"Unrecognized vector-of type: {type_!r}") from exc
    if array_type is ByteArray:
        return [_signed(array_type._assignment(value), 8) for value in values]
    return [array_type._assignment(value) for value in values]
