"""Clojure-compatible chunk and chunked-sequence runtime values.

Chunks deliberately are *not* sequences: they are indexed, counted slices used by
chunked sequences to expose a batch of elements without changing the ordinary
``first``/``rest`` sequence contract.
"""

from collections.abc import Iterator, Sequence
from typing import Any, TypeVar

from basilisp.lang.interfaces import IChunkedSeq, IIndexed, ISeq, ISequential, IWithMeta

T = TypeVar("T")

DEFAULT_CHUNK_SIZE = 32


class ArrayChunk(IIndexed[T]):
    """An immutable, counted and indexed slice used by a chunked sequence.

    It intentionally does not implement ``ISeqable``: as in Clojure, callers
    consume a chunk through ``count`` and ``nth`` rather than ``seq``.
    """

    __slots__ = ("_array", "_end", "_offset")

    def __init__(self, array: Sequence[T], offset: int = 0, end: int | None = None):
        end = len(array) if end is None else end
        if offset < 0 or end < offset or end > len(array):
            raise IndexError(
                f"Invalid ArrayChunk bounds offset={offset}, end={end}, length={len(array)}"
            )
        self._array = array
        self._offset = offset
        self._end = end

    def __bool__(self) -> bool:
        # Empty chunks, like every Clojure value except nil and false, are truthy.
        return True

    def __len__(self) -> int:
        return self._end - self._offset

    def nth(self, k: int, notfound=IIndexed.NTH_SENTINEL):
        if 0 <= k < len(self):
            return self._array[self._offset + k]
        if notfound is not IIndexed.NTH_SENTINEL:
            return notfound
        raise IndexError(k)

    def drop_first(self) -> "ArrayChunk[T]":
        if len(self) == 0:
            raise IndexError("Cannot drop the first item from an empty chunk")
        return ArrayChunk(self._array, self._offset + 1, self._end)


class ChunkBuffer:
    """A fixed-capacity, one-shot builder for an :class:`ArrayChunk`."""

    __slots__ = ("_capacity", "_items")

    def __init__(self, capacity: int):
        if not isinstance(capacity, int) or isinstance(capacity, bool):
            raise TypeError("Chunk buffer capacity must be an integer")
        if capacity < 0:
            raise ValueError("Chunk buffer capacity must be non-negative")
        self._capacity = capacity
        self._items: list[Any] | None = []

    def append(self, value: T) -> "ChunkBuffer":
        if self._items is None:
            raise RuntimeError("Chunk buffer has already been converted to a chunk")
        if len(self._items) >= self._capacity:
            raise IndexError("Chunk buffer capacity exceeded")
        self._items.append(value)
        return self

    def chunk(self) -> ArrayChunk:
        if self._items is None:
            raise RuntimeError("Chunk buffer has already been converted to a chunk")
        chunk = ArrayChunk(tuple(self._items))
        self._items = None
        return chunk


class _ChunkedSeqBase(IChunkedSeq[T], ISeq[T], ISequential):
    """Shared immutable sequence behavior for contiguous chunked sequences."""

    __slots__ = ()

    def __bool__(self) -> bool:
        return True

    def empty(self):
        from basilisp.lang.seq import EMPTY

        return EMPTY

    def cons(self, *elems: T):
        from basilisp.lang.seq import Cons

        result: ISeq[T] = self
        for elem in elems:
            result = Cons(elem, result)
        return result


class ChunkedCons(_ChunkedSeqBase[T]):
    """An ``ISeq`` whose current elements are represented by one ArrayChunk."""

    __slots__ = ("_chunk", "_offset", "_rest")

    def __init__(self, chunk: ArrayChunk[T], rest: ISeq[T] | None, offset: int = 0):
        if len(chunk) == 0:
            raise ValueError("ChunkedCons requires a non-empty chunk")
        if not 0 <= offset < len(chunk):
            raise IndexError(offset)
        self._chunk = chunk
        self._offset = offset
        self._rest = rest

    @property
    def first(self) -> T:
        return self._chunk.nth(self._offset)

    @property
    def is_empty(self) -> bool:
        return False

    @property
    def rest(self) -> ISeq[T]:
        from basilisp.lang.seq import EMPTY

        if self._offset + 1 < len(self._chunk):
            return ChunkedCons(self._chunk, self._rest, self._offset + 1)
        return self.chunked_rest()

    def chunked_first(self) -> ArrayChunk[T]:
        return ArrayChunk(
            self._chunk._array, self._chunk._offset + self._offset, self._chunk._end
        )  # pylint: disable=protected-access

    def chunked_rest(self) -> ISeq[T]:
        from basilisp.lang.seq import EMPTY

        return self._rest if self._rest is not None else EMPTY

    def chunked_next(self) -> ISeq[T] | None:
        return self._rest

    def __iter__(self) -> Iterator[T]:
        current = self.chunked_first()
        for index in range(len(current)):
            yield current.nth(index)
        if self._rest is not None:
            yield from self._rest


class ChunkedVectorSeq(_ChunkedSeqBase[T], IWithMeta):
    """A chunked view over an indexed immutable collection such as a vector."""

    __slots__ = ("_chunk_end", "_meta", "_offset", "_source")

    def __init__(
        self,
        source: Sequence[T],
        offset: int = 0,
        chunk_end: int | None = None,
        meta=None,
    ):
        if not 0 <= offset < len(source):
            raise IndexError(offset)
        self._source = source
        self._offset = offset
        self._chunk_end = (
            min(offset + DEFAULT_CHUNK_SIZE, len(source))
            if chunk_end is None
            else chunk_end
        )
        self._meta = meta

    @property
    def first(self) -> T:
        return self._source[self._offset]

    @property
    def is_empty(self) -> bool:
        return False

    @property
    def meta(self):
        return self._meta

    def with_meta(self, meta):
        return ChunkedVectorSeq(self._source, self._offset, self._chunk_end, meta)

    @property
    def rest(self) -> ISeq[T]:
        if self._offset + 1 < self._chunk_end:
            return ChunkedVectorSeq(self._source, self._offset + 1, self._chunk_end)
        return self.chunked_rest()

    def chunked_first(self) -> ArrayChunk[T]:
        return ArrayChunk(self._source, self._offset, self._chunk_end)

    def chunked_rest(self) -> ISeq[T]:
        from basilisp.lang.seq import EMPTY

        if self._chunk_end == len(self._source):
            return EMPTY
        return ChunkedVectorSeq(self._source, self._chunk_end)

    def chunked_next(self) -> ISeq[T] | None:
        if self._chunk_end == len(self._source):
            return None
        return ChunkedVectorSeq(self._source, self._chunk_end)

    def __iter__(self) -> Iterator[T]:
        for index in range(self._offset, len(self._source)):
            yield self._source[index]


def array_chunk(
    _manager: Any, array: Sequence[T], offset: int, end: int
) -> ArrayChunk[T]:
    """Python-host factory corresponding to Clojure's ``->ArrayChunk``.

    Clojure uses ``ArrayManager`` to read JVM primitive arrays. Python sequences
    do not require that manager, so its positional slot is retained and ignored.
    """
    return ArrayChunk(array, offset, end)


def chunk_buffer(capacity: int) -> ChunkBuffer:
    return ChunkBuffer(capacity)


def chunk_append(buffer: ChunkBuffer, value: T) -> None:
    buffer.append(value)
    return None


def chunk(buffer: ChunkBuffer) -> ArrayChunk:
    return buffer.chunk()


def chunk_cons(chunk_: ArrayChunk[T], rest: ISeq[T] | None) -> ISeq[T] | None:
    if not isinstance(chunk_, ArrayChunk):
        raise TypeError(f"chunk-cons requires an ArrayChunk, got {type(chunk_)}")
    if len(chunk_) == 0:
        return rest
    return ChunkedCons(chunk_, rest)


def chunk_first(seq: IChunkedSeq[T]) -> ArrayChunk[T]:
    if not isinstance(seq, IChunkedSeq):
        raise TypeError(f"chunk-first requires a chunked sequence, got {type(seq)}")
    return seq.chunked_first()


def chunk_rest(seq: IChunkedSeq[T]) -> ISeq[T]:
    if not isinstance(seq, IChunkedSeq):
        raise TypeError(f"chunk-rest requires a chunked sequence, got {type(seq)}")
    return seq.chunked_rest()


def chunk_next(seq: IChunkedSeq[T]) -> ISeq[T] | None:
    if not isinstance(seq, IChunkedSeq):
        raise TypeError(f"chunk-next requires a chunked sequence, got {type(seq)}")
    return seq.chunked_next()


def is_chunked_seq(value: Any) -> bool:
    return isinstance(value, IChunkedSeq)


def chunked_vector_seq(source: Sequence[T]) -> ChunkedVectorSeq[T] | None:
    if len(source) == 0:
        return None
    return ChunkedVectorSeq(source)


__all__ = (
    "ArrayChunk",
    "ChunkBuffer",
    "ChunkedCons",
    "ChunkedVectorSeq",
    "DEFAULT_CHUNK_SIZE",
    "array_chunk",
    "chunk",
    "chunk_append",
    "chunk_buffer",
    "chunk_cons",
    "chunk_first",
    "chunk_next",
    "chunk_rest",
    "chunked_vector_seq",
    "is_chunked_seq",
)
