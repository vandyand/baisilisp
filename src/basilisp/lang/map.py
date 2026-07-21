import functools
import numbers
from builtins import map as pymap
from collections.abc import Callable, Iterable, Mapping
from itertools import islice
from typing import Any, TypeVar, cast

from immutables import Map as _Map
from immutables import MapMutation
from typing_extensions import Unpack

from basilisp.lang.equality import key as equivalence_key
from basilisp.lang.equality import numeric_equiv
from basilisp.lang.equality import unkey as public_key
from basilisp.lang.interfaces import (
    IEvolveableCollection,
    ILispObject,
    IMapEntry,
    INamed,
    IPersistentMap,
    IPersistentVector,
    IReduceKV,
    IReversible,
    ISeq,
    ITransientMap,
    IWithMeta,
    ReduceKVFunction,
)
from basilisp.lang.obj import (
    MAP_PRINT_SEPARATOR,
    SURPASSED_PRINT_LENGTH,
    SURPASSED_PRINT_LEVEL,
    PrintSettings,
    lrepr,
    process_lrepr_kwargs,
)
from basilisp.lang.reduced import Reduced
from basilisp.lang.seq import iterator_sequence
from basilisp.lang.vector import MapEntry
from basilisp.util import partition

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")
T_reduce = TypeVar("T_reduce")

_ENTRY_SENTINEL = object()


def _public_items(items: Iterable[tuple[Any, V]]) -> Iterable[tuple[Any, V]]:
    """Expose collection storage keys without numeric-equivalence wrappers."""

    return ((public_key(key), value) for key, value in items)


class TransientMap(ITransientMap[K, V]):
    __slots__ = ("_inner",)

    def __init__(self, evolver: "MapMutation[K, V]") -> None:
        self._inner = evolver

    def __bool__(self):
        return True

    def __call__(self, key, default=None):
        return self._inner.get(equivalence_key(key), default)

    def __contains__(self, item):
        return equivalence_key(item) in self._inner

    def __eq__(self, other):
        return self is other

    def __len__(self):
        return len(self._inner)

    def assoc_transient(self, *kvs) -> "TransientMap":
        for t in partition(kvs, 2):
            # Clojure allows assoc! to have odd numbers of arguments, setting nil for
            # the missing value.
            if len(t) == 2:
                k, v = t
                self._inner[equivalence_key(k)] = v
            else:
                self._inner[equivalence_key(t[0])] = None  # type: ignore[assignment]
        return self

    def contains_transient(self, k: K) -> bool:
        return equivalence_key(k) in self._inner

    def dissoc_transient(self, *ks: K) -> "TransientMap[K, V]":
        for k in ks:
            try:
                del self._inner[equivalence_key(k)]
            except KeyError:
                pass
        return self

    def entry_transient(self, k: K) -> IMapEntry[K, V] | None:
        storage_key = equivalence_key(k)
        v = self._inner.get(storage_key, cast("V", _ENTRY_SENTINEL))
        if v is _ENTRY_SENTINEL:
            return None
        return MapEntry.of(public_key(storage_key), v)

    def val_at(self, k, default=None):
        return self._inner.get(equivalence_key(k), default)

    def cons_transient(  # type: ignore[override]
        self,
        *elems: (
            IPersistentMap[K, V]
            | IMapEntry[K, V]
            | IPersistentVector[K | V]
            | Mapping[K, V]
        ),
    ) -> "TransientMap[K, V]":
        try:
            for elem in elems:
                if isinstance(elem, (IPersistentMap, Mapping)):
                    for k, v in elem.items():
                        self._inner[equivalence_key(k)] = v
                elif isinstance(elem, IMapEntry):
                    self._inner[equivalence_key(elem.key)] = elem.value
                elif elem is None:
                    continue
                else:
                    entry: IMapEntry[K, V] = MapEntry.from_vec(elem)
                    self._inner[equivalence_key(entry.key)] = entry.value
        except (TypeError, ValueError) as e:
            raise ValueError(
                "Argument to map conj must be another Map or castable to MapEntry"
            ) from e
        else:
            return self

    def to_persistent(self) -> "PersistentMap[K, V]":
        return PersistentMap(self._inner.finish())


def map_lrepr(  # pylint: disable=too-many-locals
    entries: Callable[[], Iterable[tuple[Any, Any]]],
    start: str,
    end: str,
    meta: IPersistentMap | None = None,
    **kwargs: Unpack[PrintSettings],
) -> str:
    """Produce a Lisp representation of an associative collection, bookended
    with the start and end string supplied. The entries argument must be a
    callable which will produce tuples of key-value pairs.

    If the keyword argument print_namespace_maps is True and all keys
    share the same namespace, then print the namespace of the keys at
    the beginning of the map instead of beside the keys.

    The keyword arguments will be passed along to lrepr for the sequence
    elements.

    """
    print_level = kwargs["print_level"]
    if isinstance(print_level, int) and print_level < 1:
        return SURPASSED_PRINT_LEVEL

    kwargs = process_lrepr_kwargs(**kwargs)

    def check_same_ns():
        """Check whether all keys in entries belong to the same
        namespace. If they do, return the namespace name; otherwise,
        return None.
        """
        nses = set()
        for k, _ in entries():
            if isinstance(k, INamed):
                nses.add(k.ns)
            else:
                nses.add(None)
            if len(nses) > 1:
                break
        return next(iter(nses)) if len(nses) == 1 else None

    ns_name_shared = check_same_ns() if kwargs["print_namespace_maps"] else None

    entries_updated = entries
    if ns_name_shared:

        def entries_ns_remove():
            for k, v in entries():
                yield (k.with_name(k.name), v)

        entries_updated = entries_ns_remove

    kw_items = kwargs.copy()
    kw_items["human_readable"] = False

    def entry_reprs():
        for k, v in entries_updated():
            yield f"{lrepr(k, **kw_items)} {lrepr(v, **kw_items)}"

    trailer = []
    print_dup = kwargs["print_dup"]
    print_length = kwargs["print_length"]
    if not print_dup and isinstance(print_length, int):
        items = list(islice(entry_reprs(), print_length + 1))
        if len(items) > print_length:
            items.pop()
            trailer.append(SURPASSED_PRINT_LENGTH)
    else:
        items = list(entry_reprs())

    seq_lrepr = MAP_PRINT_SEPARATOR.join(items + trailer)

    ns_prefix = ("#:" + ns_name_shared) if ns_name_shared else ""
    if kwargs["print_meta"] and meta:
        kwargs_meta = kwargs
        kwargs_meta["print_level"] = None
        return f"^{lrepr(meta,**kwargs_meta)} {ns_prefix}{start}{seq_lrepr}{end}"

    return f"{ns_prefix}{start}{seq_lrepr}{end}"


@lrepr.register(dict)  # type: ignore[attr-defined, untyped-decorator]
def _lrepr_py_dict(o: dict, **kwargs: Unpack[PrintSettings]) -> str:
    return f"#py {map_lrepr(o.items, '{', '}', **kwargs)}"


class PersistentMap(
    IPersistentMap[K, V],
    IEvolveableCollection[TransientMap],
    IReduceKV,
    ILispObject,
    IWithMeta,
):
    """Basilisp Map. Delegates internally to a immutables.Map object.
    Do not instantiate directly. Instead use the m() and map() factory
    methods below."""

    __slots__ = ("_inner", "_meta")

    def __init__(
        self,
        m: "_Map[K, V]",
        meta: IPersistentMap | None = None,
    ) -> None:
        self._inner = _Map((equivalence_key(key), value) for key, value in m.items())
        self._meta = meta

    @classmethod
    def from_coll(
        cls,
        members: Mapping[K, V] | Iterable[tuple[K, V]],
        meta: IPersistentMap | None = None,
    ) -> "PersistentMap[K, V]":
        return PersistentMap(
            (
                _Map((equivalence_key(key), value) for key, value in members.items())
                if isinstance(members, Mapping)
                else _Map((equivalence_key(key), value) for key, value in members)
            ),
            meta=meta,
        )

    def __bool__(self):
        return True

    def __call__(self, key, default=None):
        return self._inner.get(equivalence_key(key), default)

    def __contains__(self, item):
        return equivalence_key(item) in self._inner

    def __eq__(self, other):
        if self is other:
            return True
        if not isinstance(other, Mapping):
            return NotImplemented
        if len(self._inner) != len(other):
            return False
        return all(
            key in other and numeric_equiv(self[key], other[key]) for key in self
        )

    def __getitem__(self, item):
        return self._inner[equivalence_key(item)]

    def __hash__(self):
        return hash(self._inner)

    def __iter__(self):
        return (public_key(key) for key in self._inner)

    def __len__(self):
        return len(self._inner)

    def _lrepr(self, **kwargs: Unpack[PrintSettings]):
        return map_lrepr(
            lambda: _public_items(self._inner.items()),
            start="{",
            end="}",
            meta=self._meta,
            **kwargs,
        )

    @property
    def meta(self) -> IPersistentMap | None:
        return self._meta

    def with_meta(self, meta: IPersistentMap | None) -> "PersistentMap":
        return PersistentMap(self._inner, meta=meta)

    def assoc(self, *kvs):
        with self._inner.mutate() as m:
            for k, v in partition(kvs, 2):
                m[equivalence_key(k)] = v
            return PersistentMap(m.finish(), meta=self._meta)

    def contains(self, k):
        return equivalence_key(k) in self._inner

    def dissoc(self, *ks):
        with self._inner.mutate() as m:
            for k in ks:
                try:
                    del m[equivalence_key(k)]
                except KeyError:
                    pass
            return PersistentMap(m.finish(), meta=self._meta)

    def entry(self, k):
        storage_key = equivalence_key(k)
        v = self._inner.get(storage_key, cast("V", _ENTRY_SENTINEL))
        if v is _ENTRY_SENTINEL:
            return None
        return MapEntry.of(public_key(storage_key), v)

    def val_at(self, k, default=None):
        return self._inner.get(equivalence_key(k), default)

    def update(self, *maps: Mapping[K, V]) -> "PersistentMap":
        with self._inner.mutate() as m:
            for map_ in maps:
                for key, value in map_.items():
                    m.set(equivalence_key(key), value)
            return PersistentMap(m.finish(), meta=self._meta)

    def update_with(  # type: ignore[return]
        self, merge_fn: Callable[[V, V], V], *maps: Mapping[K, V]
    ) -> "PersistentMap[K, V]":
        with self._inner.mutate() as m:
            for map in maps:
                for k, v in map.items():
                    storage_key = equivalence_key(k)
                    m.set(
                        storage_key,
                        merge_fn(m[storage_key], v) if storage_key in m else v,
                    )
            return PersistentMap(m.finish(), meta=self._meta)

    def cons(  # type: ignore[override, return]
        self,
        *elems: (
            IPersistentMap[K, V]
            | IMapEntry[K, V]
            | IPersistentVector[K | V]
            | Mapping[K, V]
        ),
    ) -> "PersistentMap[K, V]":
        with self._inner.mutate() as m:
            try:
                for elem in elems:
                    if isinstance(elem, (IPersistentMap, Mapping)):
                        for k, v in elem.items():
                            m.set(equivalence_key(k), v)
                    elif isinstance(elem, IMapEntry):
                        m.set(equivalence_key(elem.key), elem.value)
                    elif elem is None:
                        continue
                    else:
                        entry: IMapEntry[K, V] = MapEntry.from_vec(elem)
                        m.set(equivalence_key(entry.key), entry.value)
            except (TypeError, ValueError) as e:
                raise ValueError(
                    "Argument to map conj must be another Map or castable to MapEntry"
                ) from e
            else:
                return PersistentMap(m.finish(), meta=self.meta)

    def empty(self) -> "PersistentMap":
        return EMPTY.with_meta(self._meta)

    def seq(self) -> ISeq[IMapEntry[K, V]] | None:
        if len(self._inner) == 0:
            return None
        return iterator_sequence(
            (MapEntry.of(public_key(k), v) for k, v in self._inner.items())
        )

    def to_transient(self) -> TransientMap[K, V]:
        return TransientMap(self._inner.mutate())

    def reduce_kv(self, f: ReduceKVFunction, init: T_reduce) -> T_reduce:
        for k, v in self._inner.items():
            init = f(init, public_key(k), v)
            if isinstance(init, Reduced):
                return init.deref()
        return init


def _comparator_fn(comparator: Callable[[K, K], int | bool]):
    """Normalize Basilisp boolean and three-way comparator functions."""

    def compare(left: K, right: K) -> int:
        result = comparator(left, right)
        if isinstance(result, bool):
            if result:
                return -1
            if comparator(right, left):
                return 1
            return 0
        if not isinstance(result, numbers.Number):
            raise TypeError("Sorted collection comparator must return a number or bool")
        return int(result)

    return compare


class PersistentSortedMap(PersistentMap[K, V], IReversible[IMapEntry[K, V]]):
    """An immutable map whose observable iteration order follows a comparator."""

    __slots__ = ("_comparator",)

    def __init__(
        self,
        m: "_Map[K, V]",
        comparator: Callable[[K, K], int | bool],
        meta: IPersistentMap | None = None,
    ) -> None:
        super().__init__(m, meta=meta)
        self._comparator = comparator

    @property
    def comparator(self):
        return self._comparator

    def _sorted_items(self) -> list[tuple[K, V]]:
        compare = _comparator_fn(self._comparator)

        def compare_entries(left: tuple[K, V], right: tuple[K, V]) -> int:
            return compare(left[0], right[0])

        return sorted(
            _public_items(self._inner.items()),
            key=functools.cmp_to_key(compare_entries),
        )

    def _new(self, m: "_Map[K, V]", meta: IPersistentMap | None = None):
        return PersistentSortedMap(
            m, self._comparator, meta=self._meta if meta is None else meta
        )

    def __iter__(self):
        for key, _ in self._sorted_items():
            yield key

    def _lrepr(self, **kwargs: Unpack[PrintSettings]):
        return map_lrepr(
            self._sorted_items,
            start="{",
            end="}",
            meta=self._meta,
            **kwargs,
        )

    def with_meta(self, meta: IPersistentMap | None):
        return self._new(self._inner, meta=meta)

    def assoc(self, *kvs):
        with self._inner.mutate() as m:
            for k, v in partition(kvs, 2):
                m[equivalence_key(k)] = v
            return self._new(m.finish())

    def dissoc(self, *ks):
        with self._inner.mutate() as m:
            for k in ks:
                try:
                    del m[equivalence_key(k)]
                except KeyError:
                    pass
            return self._new(m.finish())

    def update(self, *maps: Mapping[K, V]):
        return self._new(super().update(*maps)._inner)

    def update_with(self, merge_fn: Callable[[V, V], V], *maps: Mapping[K, V]):
        with self._inner.mutate() as m:
            for map_ in maps:
                for k, v in map_.items():
                    storage_key = equivalence_key(k)
                    m.set(
                        storage_key,
                        merge_fn(m[storage_key], v) if storage_key in m else v,
                    )
            return self._new(m.finish())

    def cons(self, *elems):
        updated = super().cons(*elems)
        return self._new(updated._inner)

    def empty(self):
        return self._new(_Map())

    def seq(self) -> ISeq[IMapEntry[K, V]] | None:
        if len(self._inner) == 0:
            return None
        return iterator_sequence((MapEntry.of(k, v) for k, v in self._sorted_items()))

    def rseq(self) -> ISeq[IMapEntry[K, V]] | None:
        if len(self._inner) == 0:
            return None
        return iterator_sequence(
            (MapEntry.of(k, v) for k, v in reversed(self._sorted_items()))
        )

    def reduce_kv(self, f: ReduceKVFunction, init: T_reduce) -> T_reduce:
        for k, v in self._sorted_items():
            init = f(init, k, v)
            if isinstance(init, Reduced):
                return init.deref()
        return init


EMPTY: PersistentMap = PersistentMap.from_coll(())


def map(  # pylint:disable=redefined-builtin
    kvs: Mapping[K, V] | Iterable[tuple[K, V]], meta: IPersistentMap | None = None
) -> PersistentMap[K, V]:
    """Creates a new map."""
    # For some reason, creating a new `immutables.Map` instance from an existing
    # `basilisp.lang.map.PersistentMap` instance causes issues because the `__iter__`
    # returns only the keys rather than tuple of key/value pairs, even though it
    # adheres to the `Mapping` protocol. Passing the `.items()` directly bypasses
    # this problem.
    return PersistentMap.from_coll(
        kvs.items() if isinstance(kvs, Mapping) else kvs, meta=meta
    )


def sorted_map(
    comparator: Callable[[K, K], int | bool], *pairs, meta: IPersistentMap | None = None
) -> PersistentSortedMap[K, V]:
    """Create a persistent map whose iteration order follows ``comparator``."""
    if len(pairs) % 2:
        raise ValueError("Sorted map requires an even number of key-value arguments")
    return PersistentSortedMap(
        _Map((equivalence_key(key), value) for key, value in partition(pairs, 2)),
        comparator,
        meta=meta,
    )


def m(**kvs) -> PersistentMap[str, V]:
    """Creates a new map from keyword arguments."""
    return PersistentMap.from_coll(kvs)


def from_entries(entries: Iterable[MapEntry[K, V]]) -> PersistentMap[K, V]:  # type: ignore[return]
    with _Map().mutate() as m:  # type: ignore[var-annotated]
        for entry in entries:
            m.set(equivalence_key(entry.key), entry.value)
        return PersistentMap(m.finish())


def hash_map(*pairs) -> PersistentMap:
    entries = pymap(lambda v: MapEntry.of(v[0], v[1]), partition(pairs, 2))
    return from_entries(entries)
