"""Chunked sequence implementation for ``basilisp.core/range``."""

from __future__ import annotations

import builtins
from collections.abc import Iterator
from typing import Any, TypeVar

from basilisp.lang.chunk import DEFAULT_CHUNK_SIZE, ArrayChunk
from basilisp.lang.interfaces import IChunkedSeq, ISeq, ISequential

T = TypeVar("T")


def _in_bounds(value: T, end: T | None, step: T) -> bool:
    if end is None:
        return True
    if step >= 0:
        return value < end
    return value > end


class RangeSeq(IChunkedSeq[T], ISeq[T], ISequential):
    """A Clojure-shaped chunked range sequence.

    The current chunk size is tracked so ``rest`` inside a chunk preserves the
    original 32-item chunk boundary, matching vector-backed chunked sequences.
    """

    __slots__ = ("_chunk_remaining", "_end", "_start", "_step")

    def __init__(
        self,
        start: T,
        end: T | None,
        step: T,
        chunk_remaining: int = DEFAULT_CHUNK_SIZE,
    ):
        if chunk_remaining < 1 or chunk_remaining > DEFAULT_CHUNK_SIZE:
            raise ValueError("Range chunk remainder must be between 1 and 32")
        self._start = start
        self._end = end
        self._step = step
        self._chunk_remaining = chunk_remaining

    def __bool__(self) -> bool:
        return True

    @property
    def first(self) -> T:
        return self._start

    @property
    def is_empty(self) -> bool:
        return False

    @property
    def rest(self) -> ISeq[T]:
        from basilisp.lang import seq as lseq

        next_start = self._start + self._step
        if not _in_bounds(next_start, self._end, self._step):
            return lseq.EMPTY
        if self._chunk_remaining > 1:
            return RangeSeq(
                next_start, self._end, self._step, self._chunk_remaining - 1
            )
        return RangeSeq(next_start, self._end, self._step)

    def empty(self):
        from basilisp.lang import seq as lseq

        return lseq.EMPTY

    def cons(self, *elems: T):
        from basilisp.lang import seq as lseq

        result: ISeq[T] = self
        for elem in elems:
            result = lseq.Cons(elem, result)
        return result

    def _chunk_values(self) -> tuple[T, ...]:
        values: list[T] = []
        current = self._start
        for _ in builtins.range(self._chunk_remaining):
            if not _in_bounds(current, self._end, self._step):
                break
            values.append(current)
            current += self._step
        return tuple(values)

    def chunked_first(self) -> ArrayChunk[T]:
        return ArrayChunk(self._chunk_values())

    def chunked_rest(self) -> ISeq[T]:
        from basilisp.lang import seq as lseq

        values = self._chunk_values()
        next_start = self._start
        for _ in builtins.range(len(values)):
            next_start += self._step
        if not _in_bounds(next_start, self._end, self._step):
            return lseq.EMPTY
        return RangeSeq(next_start, self._end, self._step)

    def chunked_next(self) -> ISeq[T] | None:
        from basilisp.lang import seq as lseq

        rest = self.chunked_rest()
        return None if rest is lseq.EMPTY else rest

    def __iter__(self) -> Iterator[T]:
        current = self._start
        while _in_bounds(current, self._end, self._step):
            yield current
            current += self._step


class _ZeroStepRangeSeq(ISeq[T], ISequential):
    """An unchunked infinite repeat sequence for Clojure's zero-step range."""

    __slots__ = ("_value",)

    def __init__(self, value: T):
        self._value = value

    def __bool__(self) -> bool:
        return True

    @property
    def first(self) -> T:
        return self._value

    @property
    def is_empty(self) -> bool:
        return False

    @property
    def rest(self) -> ISeq[T]:
        return self

    def empty(self):
        from basilisp.lang import seq as lseq

        return lseq.EMPTY

    def cons(self, *elems: T):
        from basilisp.lang import seq as lseq

        result: ISeq[T] = self
        for elem in elems:
            result = lseq.Cons(elem, result)
        return result

    def __iter__(self) -> Iterator[T]:
        while True:
            yield self._value


def range(*args: Any) -> ISeq[Any]:
    from basilisp.lang import seq as lseq

    if len(args) == 0:
        start, end, step = 0, None, 1
    elif len(args) == 1:
        start, end, step = 0, args[0], 1
    elif len(args) == 2:
        start, end, step = args[0], args[1], 1
    elif len(args) == 3:
        start, end, step = args
    else:
        raise TypeError(f"range expected 0 to 3 arguments, got {len(args)}")

    if not _in_bounds(start, end, step):
        return lseq.EMPTY
    if step == 0:
        return _ZeroStepRangeSeq(start)
    return RangeSeq(start, end, step)


__all__ = ("RangeSeq", "range")
