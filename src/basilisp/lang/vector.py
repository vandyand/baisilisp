from collections.abc import Iterable, Iterator, Sequence
from functools import total_ordering
from typing import Any, TypeVar, Union, cast, overload

from typing_extensions import Unpack

from basilisp.lang.chunk import ChunkedVectorSeq, chunked_vector_seq
from basilisp.lang.interfaces import (
    IEvolveableCollection,
    IIndexed,
    ILispObject,
    IMapEntry,
    IPersistentMap,
    IPersistentVector,
    IReduce,
    IReduceKV,
    ISeq,
    ITransientVector,
    IWithMeta,
    ReduceFunction,
    ReduceKVFunction,
    seq_equals,
    seq_hash,
)
from basilisp.lang.obj import PrintSettings
from basilisp.lang.obj import seq_lrepr as _seq_lrepr
from basilisp.lang.reduced import Reduced
from basilisp.lang.seq import iterator_sequence
from basilisp.util import partition

T = TypeVar("T")
T_reduce = TypeVar("T_reduce")
V_contra = TypeVar("V_contra", contravariant=True)
K = TypeVar("K")
V = TypeVar("V")

BRANCH_BITS = 5
BRANCH_FACTOR = 1 << BRANCH_BITS
BRANCH_MASK = BRANCH_FACTOR - 1


class VectorNode:
    """An immutable branch in Basilisp's persistent-vector tree.

    ``edit`` deliberately remains a public field because it occupies the same
    position as Clojure's ``VecNode`` edit token. Persistent Basilisp vectors
    keep it as ``None``; it is retained for faithful construction and
    inspection of the public vector representation rather than for a JVM-style
    transient mutation protocol.
    """

    __slots__ = ("arr", "edit")

    def __init__(self, edit: Any, arr: Iterable[Any]):
        self.edit = edit
        self.arr = tuple(arr)


def _empty_branch() -> tuple[None, ...]:
    return (None,) * BRANCH_FACTOR


EMPTY_NODE = VectorNode(None, _empty_branch())


def _branch(node: VectorNode) -> tuple[Any, ...]:
    if len(node.arr) != BRANCH_FACTOR:
        raise ValueError(
            f"Vector node arrays must contain {BRANCH_FACTOR} entries, got {len(node.arr)}"
        )
    return node.arr


def _replace(node: VectorNode, index: int, value: Any) -> VectorNode:
    arr = list(_branch(node))
    arr[index] = value
    return VectorNode(node.edit, arr)


def _tail_offset(count: int) -> int:
    if count < BRANCH_FACTOR:
        return 0
    return ((count - 1) >> BRANCH_BITS) << BRANCH_BITS


def _new_path(level: int, node: VectorNode) -> VectorNode:
    if level == 0:
        return node
    return VectorNode(
        None, (_new_path(level - BRANCH_BITS, node),) + (None,) * (BRANCH_FACTOR - 1)
    )


class TransientVector(ITransientVector[T]):
    """An isolated mutable staging buffer for a persistent vector.

    Transients never mutate their source vector. They intentionally use a
    plain list: Python has no equivalent to Clojure's owner-thread edit token,
    and converting once at ``persistent!`` preserves the public transient
    contract without leaking mutable nodes into persistent values.
    """

    __slots__ = ("_items",)

    def __init__(self, items: Iterable[T]) -> None:
        self._items = list(items)

    def __bool__(self):
        return True

    def __contains__(self, item):
        return item in self._items

    def __eq__(self, other):
        return self is other

    def __len__(self):
        return len(self._items)

    def __call__(self, k: int) -> T | None:
        return self._items[k]

    @staticmethod
    def _index(index: int, count: int, *, allow_end: bool = False) -> int:
        if not isinstance(index, int):
            raise TypeError("Vector index must be an integer")
        if index < 0:
            index += count
        upper_bound = count if allow_end else count - 1
        if not 0 <= index <= upper_bound:
            raise IndexError(index)
        return index

    def cons_transient(self, *elems: T) -> "TransientVector[T]":  # type: ignore[override]
        self._items.extend(elems)
        return self

    def assoc_transient(self, *kvs: T) -> "TransientVector[T]":
        for pair in partition(kvs, 2):
            key = pair[0]
            value = pair[1] if len(pair) == 2 else None
            index = self._index(key, len(self._items), allow_end=True)
            if index == len(self._items):
                self._items.append(value)
            else:
                self._items[index] = value
        return self

    def contains_transient(self, k: int) -> bool:
        return isinstance(k, int) and 0 <= k < len(self._items)

    def entry_transient(self, k: int) -> IMapEntry[int, T] | None:
        try:
            return MapEntry.of(k, self._items[k])
        except IndexError:
            return None

    def val_at(self, k: int, default=None):
        try:
            return self._items[k]
        except (IndexError, TypeError):
            return default

    def nth(self, k: int, notfound=IIndexed.NTH_SENTINEL):
        try:
            return self._items[k]
        except IndexError:
            if notfound is not IIndexed.NTH_SENTINEL:
                return notfound
            raise

    def pop_transient(self) -> "TransientVector[T]":
        if not self._items:
            raise IndexError("Cannot pop an empty vector")
        self._items.pop()
        return self

    def to_persistent(self) -> "PersistentVector[T]":
        return vector(self._items)


@total_ordering
class PersistentVector(
    IReduce,
    IReduceKV,
    IPersistentVector[T],
    IEvolveableCollection[TransientVector],
    ILispObject,
    IWithMeta,
):
    """A Clojure-shaped immutable 32-way persistent vector.

    Values before ``_tail`` live in a path-copying tree of :class:`VectorNode`
    instances. The at-most-32 element tail makes append and pop cheap while
    preserving immutable structural sharing between every persistent version.
    """

    __slots__ = ("_count", "_meta", "_root", "_shift", "_tail")

    def __init__(
        self,
        count: int,
        shift: int,
        root: VectorNode,
        tail: Iterable[T],
        meta: IPersistentMap | None = None,
    ) -> None:
        self._count = count
        self._shift = shift
        self._root = root
        self._tail = tuple(tail)
        self._meta = meta

    @staticmethod
    def _index(index: int, count: int) -> int:
        if not isinstance(index, int):
            raise TypeError("Vector index must be an integer")
        if index < 0:
            index += count
        if not 0 <= index < count:
            raise IndexError(index)
        return index

    def _array_for(self, index: int) -> tuple[T, ...]:
        if index >= _tail_offset(self._count):
            return self._tail

        node = self._root
        for level in range(self._shift, 0, -BRANCH_BITS):
            child = _branch(node)[(index >> level) & BRANCH_MASK]
            if not isinstance(child, VectorNode):
                raise ValueError("Vector tree is missing a required branch node")
            node = child
        return cast(tuple[T, ...], _branch(node))

    def _nth(self, index: int) -> T:
        index = self._index(index, self._count)
        return self._array_for(index)[index & BRANCH_MASK]

    def _push_tail(
        self, level: int, parent: VectorNode, tail_node: VectorNode
    ) -> VectorNode:
        subindex = ((self._count - 1) >> level) & BRANCH_MASK
        if level == BRANCH_BITS:
            child = tail_node
        else:
            existing = _branch(parent)[subindex]
            if existing is None:
                child = _new_path(level - BRANCH_BITS, tail_node)
            elif isinstance(existing, VectorNode):
                child = self._push_tail(level - BRANCH_BITS, existing, tail_node)
            else:
                raise ValueError("Vector tree contains a non-node branch value")
        return _replace(parent, subindex, child)

    def _pop_tail(self, level: int, node: VectorNode) -> VectorNode | None:
        subindex = ((self._count - 2) >> level) & BRANCH_MASK
        if level > BRANCH_BITS:
            child = _branch(node)[subindex]
            if not isinstance(child, VectorNode):
                raise ValueError("Vector tree is missing a required branch node")
            new_child = self._pop_tail(level - BRANCH_BITS, child)
            if new_child is None and subindex == 0:
                return None
            return _replace(node, subindex, new_child)
        if subindex == 0:
            return None
        return _replace(node, subindex, None)

    def _do_assoc(
        self, level: int, node: VectorNode, index: int, value: T
    ) -> VectorNode:
        if level == 0:
            return _replace(node, index & BRANCH_MASK, value)
        subindex = (index >> level) & BRANCH_MASK
        child = _branch(node)[subindex]
        if not isinstance(child, VectorNode):
            raise ValueError("Vector tree is missing a required branch node")
        return _replace(
            node, subindex, self._do_assoc(level - BRANCH_BITS, child, index, value)
        )

    def _append(self, value: T) -> "PersistentVector[T]":
        if len(self._tail) < BRANCH_FACTOR:
            return PersistentVector(
                self._count + 1,
                self._shift,
                self._root,
                self._tail + (value,),
                self._meta,
            )

        tail_node = VectorNode(None, self._tail)
        if (self._count >> BRANCH_BITS) > (1 << self._shift):
            new_root = VectorNode(
                None,
                (self._root, _new_path(self._shift, tail_node))
                + (None,) * (BRANCH_FACTOR - 2),
            )
            new_shift = self._shift + BRANCH_BITS
        else:
            new_root = self._push_tail(self._shift, self._root, tail_node)
            new_shift = self._shift
        return PersistentVector(
            self._count + 1, new_shift, new_root, (value,), self._meta
        )

    def _assoc_one(self, index: int, value: T) -> "PersistentVector[T]":
        if not isinstance(index, int):
            raise TypeError("Vector index must be an integer")
        if index < 0:
            index += self._count
        if index == self._count:
            return self._append(value)
        if not 0 <= index < self._count:
            raise IndexError(index)
        if index >= _tail_offset(self._count):
            tail = list(self._tail)
            tail[index & BRANCH_MASK] = value
            return PersistentVector(
                self._count, self._shift, self._root, tail, self._meta
            )
        return PersistentVector(
            self._count,
            self._shift,
            self._do_assoc(self._shift, self._root, index, value),
            self._tail,
            self._meta,
        )

    def __bool__(self):
        return True

    def __contains__(self, item):
        return any(item == value for value in self)

    def __eq__(self, other):
        if self is other:
            return True
        return seq_equals(self, other)

    def __getitem__(self, item):
        if isinstance(item, slice):
            return vector(
                (self._nth(index) for index in range(*item.indices(self._count)))
            )
        return self._nth(item)

    def __hash__(self):
        return seq_hash(self)

    def __iter__(self) -> Iterator[T]:
        for index in range(self._count):
            yield self._nth(index)

    def __len__(self):
        return self._count

    def __call__(self, k: int) -> T | None:
        return self._nth(k)

    def __lt__(self, other):
        if other is None:  # pragma: no cover
            return False
        if not isinstance(other, PersistentVector):
            return NotImplemented
        if len(self) != len(other):
            return len(self) < len(other)

        for x, y in zip(self, other):
            if x < y:
                return True
            if y < x:
                return False
        return False

    def _lrepr(self, **kwargs: Unpack[PrintSettings]) -> str:
        return _seq_lrepr(self, "[", "]", meta=self._meta, **kwargs)

    @property
    def meta(self) -> IPersistentMap | None:
        return self._meta

    def with_meta(self, meta: IPersistentMap | None) -> "PersistentVector[T]":
        return PersistentVector(self._count, self._shift, self._root, self._tail, meta)

    def cons(self, *elems: T) -> "PersistentVector[T]":  # type: ignore[override]
        result: PersistentVector[T] = self
        for elem in elems:
            result = result._append(elem)
        return result

    def assoc(self, *kvs: T) -> "PersistentVector[T]":
        if len(kvs) % 2:
            raise TypeError("assoc requires an even number of key/value arguments")
        result: PersistentVector[T] = self
        for key, value in cast(Iterable[tuple[int, T]], partition(kvs, 2)):
            result = result._assoc_one(key, value)
        return result

    def contains(self, k: Any) -> bool:
        return isinstance(k, int) and 0 <= k < self._count

    def entry(self, k: int) -> IMapEntry[int, T] | None:
        try:
            return MapEntry.of(k, self._nth(k))
        except IndexError:
            return None

    def val_at(self, k: int, default: T | None = None) -> T | None:
        try:
            return self._nth(k)
        except (IndexError, TypeError):
            return default

    def nth(self, k: int, notfound=IIndexed.NTH_SENTINEL):
        try:
            return self._nth(k)
        except IndexError:
            if notfound is not IIndexed.NTH_SENTINEL:
                return notfound
            raise

    def empty(self) -> "PersistentVector[T]":
        return EMPTY.with_meta(self._meta)

    def seq(self) -> ISeq[T] | None:  # type: ignore[override]
        return chunked_vector_seq(self)

    def peek(self) -> T | None:
        if self._count == 0:
            return None
        return self._nth(self._count - 1)

    def pop(self) -> "PersistentVector[T]":
        if self._count == 0:
            raise IndexError("Cannot pop an empty vector")
        if self._count == 1:
            return EMPTY.with_meta(self._meta)
        if len(self._tail) > 1:
            return PersistentVector(
                self._count - 1,
                self._shift,
                self._root,
                self._tail[:-1],
                self._meta,
            )

        new_tail = self._array_for(self._count - 2)
        new_root = self._pop_tail(self._shift, self._root)
        if new_root is None:
            new_root = EMPTY_NODE
        new_shift = self._shift
        if new_shift > BRANCH_BITS and _branch(new_root)[1] is None:
            first = _branch(new_root)[0]
            if not isinstance(first, VectorNode):
                raise ValueError("Vector tree is missing its root branch node")
            new_root = first
            new_shift -= BRANCH_BITS
        return PersistentVector(
            self._count - 1, new_shift, new_root, new_tail, self._meta
        )

    def rseq(self) -> ISeq[T]:
        return iterator_sequence(reversed(self))

    def to_transient(self) -> TransientVector[T]:
        return TransientVector(self)

    @overload
    def reduce(self, f: ReduceFunction[T_reduce, V_contra]) -> T_reduce: ...

    @overload
    def reduce(  # pylint: disable=arguments-differ
        self, f: ReduceFunction[T_reduce, V_contra], init: T_reduce
    ) -> T_reduce: ...

    def reduce(self, f, init=IReduce.REDUCE_SENTINEL):
        iterator = iter(self)
        if init is IReduce.REDUCE_SENTINEL:
            try:
                init = next(iterator)
            except StopIteration:
                return f()
        for item in iterator:
            init = f(init, item)
            if isinstance(init, Reduced):
                return init.deref()
        return init

    def reduce_kv(self, f: ReduceKVFunction, init: T_reduce) -> T_reduce:
        for idx, item in enumerate(self):
            init = f(init, idx, item)
            if isinstance(init, Reduced):
                return init.deref()
        return init


class MapEntry(IMapEntry[K, V], PersistentVector[Union[K, V]]):
    __slots__ = ()

    def __init__(self, members: Sequence[Union[K, V]]) -> None:
        values = tuple(members)
        assert len(values) == 2, "Vector arg to map conj must be a pair"
        built = vector(values)
        super().__init__(built._count, built._shift, built._root, built._tail)

    @property
    def key(self) -> K:
        return cast(K, self[0])

    @property
    def value(self) -> V:
        return cast(V, self[1])

    @staticmethod
    def of(k: K, v: V) -> "MapEntry[K, V]":
        return MapEntry((k, v))

    @staticmethod
    def from_vec(v: Sequence[K | V]) -> "MapEntry[K, V]":
        try:
            if len(v) != 2:
                raise ValueError("Vector arg to map conj must be a pair")
        except TypeError as e:
            raise TypeError(f"Cannot make map entry from {type(v)}") from e
        return MapEntry(v)


EMPTY: PersistentVector = PersistentVector(0, BRANCH_BITS, EMPTY_NODE, ())


def vector(
    members: Iterable[T], meta: IPersistentMap | None = None
) -> PersistentVector[T]:
    """Create a persistent vector from ``members``."""
    result: PersistentVector[T] = EMPTY
    for member in members:
        result = result._append(member)
    return result if meta is None else result.with_meta(meta)


def v(*members: T, meta: IPersistentMap | None = None) -> PersistentVector[T]:
    """Create a persistent vector from positional ``members``."""
    return vector(members, meta=meta)


def vec_node(edit: Any, arr: Iterable[Any]) -> VectorNode:
    """Construct a public ``VecNode``-shaped immutable node."""
    return VectorNode(edit, arr)


def vec_from_components(
    _manager: Any,
    count: int,
    shift: int,
    root: VectorNode,
    tail: Iterable[T],
    meta: IPersistentMap | None,
) -> PersistentVector[T]:
    """Construct a vector from the portable ``Vec`` component shape.

    The JVM ``ArrayManager`` position is retained for source compatibility and
    ignored. Nodes and tail data are immutable Python tuples rather than JVM
    object arrays.
    """
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise TypeError("Vec count must be a non-negative integer")
    if (
        not isinstance(shift, int)
        or isinstance(shift, bool)
        or shift < BRANCH_BITS
        or shift % BRANCH_BITS
    ):
        raise TypeError("Vec shift must be a positive multiple of 5")
    if not isinstance(root, VectorNode):
        raise TypeError("Vec root must be a VectorNode")
    tail_values = tuple(tail)
    expected_tail_count = count - _tail_offset(count)
    if len(tail_values) != expected_tail_count:
        raise ValueError(
            f"Vec tail has {len(tail_values)} entries; expected {expected_tail_count}"
        )
    result = PersistentVector(count, shift, root, tail_values, meta)
    if count:
        # Force a complete structural check so malformed public constructor
        # components fail at construction rather than much later at lookup.
        for index in range(_tail_offset(count)):
            result._array_for(index)
    return result


def vec_seq(
    _manager: Any,
    source: PersistentVector[T],
    anode: Iterable[T] | VectorNode,
    index: int,
    offset: int,
    meta: IPersistentMap | None,
) -> ChunkedVectorSeq[T]:
    """Construct the chunked ``VecSeq`` view for a persistent vector.

    The manager slot is ignored as it is for ``->ArrayChunk``. ``anode`` is
    validated against the vector's actual leaf so callers cannot manufacture a
    sequence whose chunk disagrees with its source.
    """
    if not isinstance(source, PersistentVector):
        raise TypeError("VecSeq source must be a PersistentVector")
    if not isinstance(index, int) or not isinstance(offset, int):
        raise TypeError("VecSeq index and offset must be integers")
    if index < 0 or index % BRANCH_FACTOR:
        raise IndexError("VecSeq index must begin at a vector chunk boundary")
    expected = source._array_for(index)
    supplied = anode.arr if isinstance(anode, VectorNode) else tuple(anode)
    if tuple(supplied) != expected:
        raise ValueError("VecSeq node does not match the source vector chunk")
    if not 0 <= offset < len(expected):
        raise IndexError(offset)
    absolute_offset = index + offset
    if absolute_offset >= len(source):
        raise IndexError(absolute_offset)
    return ChunkedVectorSeq(
        source,
        absolute_offset,
        min(index + len(expected), len(source)),
        meta=meta,
    )


__all__ = (
    "BRANCH_BITS",
    "BRANCH_FACTOR",
    "BRANCH_MASK",
    "EMPTY",
    "EMPTY_NODE",
    "MapEntry",
    "PersistentVector",
    "TransientVector",
    "VectorNode",
    "v",
    "vec_from_components",
    "vec_node",
    "vec_seq",
    "vector",
)
