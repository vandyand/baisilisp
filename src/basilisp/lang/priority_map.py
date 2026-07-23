"""Persistent priority-ordered maps for ``basilisp.data.priority-map``."""

from __future__ import annotations

import functools
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from immutables import Map as _Map

from basilisp.lang import map as lmap
from basilisp.lang import set as lset
from basilisp.lang.interfaces import IMapEntry, IPersistentMap, IReversible
from basilisp.lang.map import MapEntry, PersistentMap, PersistentSortedMap, map_lrepr
from basilisp.lang.reduced import Reduced
from basilisp.lang.seq import iterator_sequence
from basilisp.util import partition


def _default_comparator(left: Any, right: Any) -> int:
    from basilisp.lang.runtime import compare

    return compare(left, right)


class PersistentPriorityMap(PersistentMap, IReversible):
    """An immutable map whose map-entry sequence is ordered by priority values.

    The Python implementation computes ordering lazily from the persistent backing map.
    It retains the Clojure public data contract (map operations, persistence, priority
    reassignment, ``peek``/``pop``, comparators, key functions, and metadata) without
    exposing JVM sorted-map classes.
    """

    __slots__ = ("_comparator", "_keyfn")

    def __init__(
        self,
        inner: _Map = _Map(),
        comparator: Callable[[Any, Any], int | bool] = _default_comparator,
        keyfn: Callable[[Any], Any] | None = None,
        meta: IPersistentMap | None = None,
    ) -> None:
        super().__init__(inner, meta=meta)
        self._comparator = comparator
        self._keyfn = keyfn

    @property
    def comparator(self):
        return self._comparator

    @property
    def keyfn(self):
        return self._keyfn

    def _priority(self, value: Any) -> Any:
        return self._keyfn(value) if self._keyfn is not None else value

    def _sorted_items(self) -> list[tuple[Any, Any]]:
        compare = lmap._comparator_fn(self._comparator)

        def compare_entries(left: tuple[Any, Any], right: tuple[Any, Any]) -> int:
            return compare(self._priority(left[1]), self._priority(right[1]))

        return sorted(self._inner.items(), key=functools.cmp_to_key(compare_entries))

    def _new(self, inner: _Map, meta: IPersistentMap | None = None):
        return PersistentPriorityMap(
            inner,
            comparator=self._comparator,
            keyfn=self._keyfn,
            meta=self._meta if meta is None else meta,
        )

    def __iter__(self):
        for key, _ in self._sorted_items():
            yield key

    def _lrepr(self, **kwargs):
        return map_lrepr(
            self._sorted_items, start="{", end="}", meta=self._meta, **kwargs
        )

    def with_meta(self, meta: IPersistentMap | None):
        return self._new(self._inner, meta=meta)

    def assoc(self, *kvs):
        if len(kvs) % 2:
            raise ValueError("Priority map assoc requires an even number of arguments")
        with self._inner.mutate() as mutable:
            for key, value in partition(kvs, 2):
                mutable[key] = value
            return self._new(mutable.finish())

    def dissoc(self, *keys):
        with self._inner.mutate() as mutable:
            for key in keys:
                try:
                    del mutable[key]
                except KeyError:
                    pass
            return self._new(mutable.finish())

    def cons(self, *elems):
        result: PersistentPriorityMap = self
        for elem in elems:
            if elem is None:
                continue
            if isinstance(elem, (IPersistentMap, Mapping)):
                for key, value in elem.items():
                    result = result.assoc(key, value)
            elif isinstance(elem, IMapEntry):
                result = result.assoc(elem.key, elem.value)
            else:
                entry = MapEntry.from_vec(elem)
                result = result.assoc(entry.key, entry.value)
        return result

    def empty(self):
        return self._new(_Map())

    def seq(self):
        if not self._inner:
            return None
        return iterator_sequence(
            MapEntry.of(key, value) for key, value in self._sorted_items()
        )

    def rseq(self):
        if not self._inner:
            return None
        return iterator_sequence(
            MapEntry.of(key, value) for key, value in reversed(self._sorted_items())
        )

    def reduce_kv(self, f, init):
        for key, value in self._sorted_items():
            init = f(init, key, value)
            if isinstance(init, Reduced):
                return init.deref()
        return init

    def peek(self):
        if not self._inner:
            return None
        key, value = self._sorted_items()[0]
        return MapEntry.of(key, value)

    def pop(self):
        entry = self.peek()
        if entry is None:
            raise IndexError("Can't pop empty priority map")
        return self.dissoc(entry.key)

    def priority_to_set_of_items(self):
        grouped: dict[Any, Any] = {}
        for item, value in self._inner.items():
            priority = self._priority(value)
            grouped[priority] = (
                lset.s(item)
                if priority not in grouped
                else grouped[priority].cons(item)
            )
        return PersistentSortedMap(_Map(grouped), self._comparator)


def priority_map(*keyvals: Any) -> PersistentPriorityMap:
    if len(keyvals) % 2:
        raise ValueError("priority-map requires an even number of key-value arguments")
    return PersistentPriorityMap().assoc(*keyvals)


def priority_map_by(
    comparator: Callable[[Any, Any], int | bool], *keyvals: Any
) -> PersistentPriorityMap:
    if len(keyvals) % 2:
        raise ValueError(
            "priority-map-by requires an even number of key-value arguments"
        )
    return PersistentPriorityMap(comparator=comparator).assoc(*keyvals)


def priority_map_keyfn(
    keyfn: Callable[[Any], Any], *keyvals: Any
) -> PersistentPriorityMap:
    if len(keyvals) % 2:
        raise ValueError(
            "priority-map-keyfn requires an even number of key-value arguments"
        )
    return PersistentPriorityMap(keyfn=keyfn).assoc(*keyvals)


def priority_map_keyfn_by(
    keyfn: Callable[[Any], Any],
    comparator: Callable[[Any, Any], int | bool],
    *keyvals: Any,
) -> PersistentPriorityMap:
    if len(keyvals) % 2:
        raise ValueError(
            "priority-map-keyfn-by requires an even number of key-value arguments"
        )
    return PersistentPriorityMap(comparator=comparator, keyfn=keyfn).assoc(*keyvals)


def persistent_priority_map_from_parts(
    priority_to_items: Any,
    item_to_priority: Mapping[Any, Any] | Iterable[Any],
    meta: IPersistentMap | None,
    keyfn: Callable[[Any], Any] | None,
) -> PersistentPriorityMap:
    """Create a priority map from the public positional constructor fields.

    ``clojure.data.priority-map`` exposes a generated
    ``->PersistentPriorityMap`` factory. The first argument carries priority
    ordering, so reuse its comparator when it is available; the second argument
    is the public item-to-priority mapping observed by map operations.
    """

    comparator = getattr(priority_to_items, "comparator", _default_comparator)
    if isinstance(item_to_priority, PersistentPriorityMap):
        inner = item_to_priority._inner
    elif isinstance(item_to_priority, PersistentMap):
        inner = _Map(item_to_priority.items())
    elif isinstance(item_to_priority, Mapping):
        inner = _Map(item_to_priority.items())
    else:
        inner = _Map(
            (entry.key, entry.value)
            for entry in (MapEntry.from_vec(entry) for entry in item_to_priority)
        )
    return PersistentPriorityMap(inner, comparator=comparator, keyfn=keyfn, meta=meta)


def priority_to_set_of_items(priority_map: PersistentPriorityMap):
    return priority_map.priority_to_set_of_items()


def _bound(
    priority_map: PersistentPriorityMap,
    test: Callable[[Any, Any], bool],
    key: Any,
    reverse: bool,
):
    entries: Iterable[tuple[Any, Any]] = (
        reversed(priority_map._sorted_items())
        if reverse
        else priority_map._sorted_items()
    )
    compare = lmap._comparator_fn(priority_map.comparator)
    return [
        MapEntry.of(item, value)
        for item, value in entries
        if test(compare(priority_map._priority(value), key), 0)
    ]


def _entry_seq(entries):
    return iterator_sequence(entries) if entries else None


def subseq(
    priority_map: PersistentPriorityMap,
    start_test,
    start_key,
    end_test=None,
    end_key=None,
):
    entries = _bound(priority_map, start_test, start_key, False)
    if end_test is None:
        return _entry_seq(entries)
    compare = lmap._comparator_fn(priority_map.comparator)
    return _entry_seq(
        [
            entry
            for entry in entries
            if end_test(compare(priority_map._priority(entry.value), end_key), 0)
        ]
    )


def rsubseq(
    priority_map: PersistentPriorityMap,
    start_test,
    start_key,
    end_test=None,
    end_key=None,
):
    entries = _bound(priority_map, start_test, start_key, True)
    if end_test is None:
        return _entry_seq(entries)
    compare = lmap._comparator_fn(priority_map.comparator)
    return _entry_seq(
        [
            entry
            for entry in entries
            if end_test(compare(priority_map._priority(entry.value), end_key), 0)
        ]
    )
