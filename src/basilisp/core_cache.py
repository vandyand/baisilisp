"""Persistent cache policies used by :mod:`basilisp.core.cache`.

This module is a deliberately small, Python-native implementation of the
portable algorithms from ``clojure.core.cache``.  The cache values remain
ordinary persistent maps, so caches can be used with ``assoc``, ``dissoc``,
``conj``, ``seq``, and ``count`` just like their Clojure counterparts.

``SoftCache`` is intentionally not implemented here: Clojure's version has a
JVM-specific ``SoftReference``/``ReferenceQueue`` contract which Python's
``weakref`` cannot reproduce.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any

from basilisp.lang import map as lmap
from basilisp.lang.interfaces import IMapEntry, IPersistentMap
from basilisp.lang.map import PersistentMap

_MISSING = object()
_FREE = object()


def _as_map(value: Mapping[Any, Any]) -> PersistentMap:
    if isinstance(value, PersistentMap):
        return value
    return lmap.map(value)


def _now_millis() -> int:
    return time.time_ns() // 1_000_000


class PersistentCache(PersistentMap):
    """Common persistent-map behavior for ``clojure.core.cache`` policies."""

    __slots__ = ()

    def __init__(self, cache: Mapping[Any, Any], meta: IPersistentMap | None = None):
        base = _as_map(cache)
        super().__init__(base._inner, meta=base.meta if meta is None else meta)

    @property
    def cache(self) -> PersistentMap:
        """The underlying map, matching the public ``cache`` deftype field."""
        return PersistentMap(self._inner, meta=self._meta)

    def cache_lookup(self, item: Any, not_found: Any = _MISSING) -> Any:
        if not_found is _MISSING:
            return self._inner.get(item)
        return self._inner.get(item, not_found)

    def cache_has(self, item: Any) -> bool:
        return item in self._inner

    def cache_hit(self, item: Any) -> "PersistentCache":
        return self

    def cache_miss(self, item: Any, result: Any) -> "PersistentCache":
        return self._with_cache(self.cache.assoc(item, result))

    def cache_evict(self, item: Any) -> "PersistentCache":
        return self._with_cache(self.cache.dissoc(item))

    def cache_seed(self, base: Mapping[Any, Any]) -> "PersistentCache":
        return self._with_cache(_as_map(base))

    def _with_cache(self, cache: PersistentMap, **_kwargs: Any) -> "PersistentCache":
        return type(self)(cache, meta=self._meta)

    def with_meta(self, meta: IPersistentMap | None):
        """Retain the concrete cache policy when metadata is replaced."""
        clone = object.__new__(type(self))
        for cls in type(self).__mro__:
            for slot in getattr(cls, "__slots__", ()):
                if slot not in {"__dict__", "__weakref__"}:
                    setattr(clone, slot, getattr(self, slot))
        clone._meta = meta
        return clone

    def __contains__(self, item: Any) -> bool:
        return self.cache_has(item)

    def __getitem__(self, item: Any) -> Any:
        if not self.cache_has(item):
            raise KeyError(item)
        return self.cache_lookup(item)

    def __call__(self, key: Any, default: Any = None) -> Any:
        return self.cache_lookup(key, default)

    def val_at(self, key: Any, default: Any = None) -> Any:
        return self.cache_lookup(key, default)

    def contains(self, key: Any) -> bool:
        return self.cache_has(key)

    def entry(self, key: Any):
        if not self.cache_has(key):
            return None
        return lmap.MapEntry.of(key, self.cache_lookup(key))

    def items(self):
        """Expose the physical backing entries, as Clojure's ``seq`` does.

        TTL expiration affects ``has?``/``lookup`` but does not mutate the map
        until the next miss, so mapping's default ``items`` implementation is
        too eager for an expired entry.
        """
        return self._inner.items()

    def assoc(self, *kvs: Any):
        if len(kvs) % 2:
            raise ValueError("Cache assoc requires an even number of arguments")
        result: PersistentCache = self
        for key, value in zip(kvs[::2], kvs[1::2]):
            result = result.cache_miss(key, value)
        return result

    def dissoc(self, *keys: Any):
        result: PersistentCache = self
        for key in keys:
            result = result.cache_evict(key)
        return result

    def cons(self, *elems: Any):
        base = self.cache.cons(*elems)
        return self.cache_seed(base)

    def empty(self):
        return self.cache_seed(lmap.EMPTY.with_meta(self._meta))


class BasicCache(PersistentCache):
    """A pluggable cache with no eviction policy."""


class FnCache(BasicCache):
    """A basic cache whose lookup values are transformed by ``f``."""

    __slots__ = ("_f",)

    def __init__(
        self, cache: Mapping[Any, Any], f: Callable[[Any], Any], meta=None
    ) -> None:
        super().__init__(cache, meta=meta)
        self._f = f

    @property
    def f(self):
        return self._f

    def cache_lookup(self, item: Any, not_found: Any = _MISSING) -> Any:
        value = self._inner.get(item, _MISSING)
        if value is _MISSING:
            return None if not_found is _MISSING else not_found
        return self._f(value)

    # This intentionally returns BasicCache, as the upstream implementation does.
    def cache_miss(self, item: Any, result: Any) -> BasicCache:
        return BasicCache(self.cache.assoc(item, result), meta=self._meta)

    def cache_evict(self, item: Any) -> BasicCache:
        return BasicCache(self.cache.dissoc(item), meta=self._meta)

    def cache_seed(self, base: Mapping[Any, Any]) -> BasicCache:
        return BasicCache(_as_map(base), meta=self._meta)


class FIFOCache(PersistentCache):
    __slots__ = ("_q", "_limit")

    def __init__(self, cache: Mapping[Any, Any], q=(), limit: int = 32, meta=None):
        if limit <= 0:
            raise ValueError("FIFO cache threshold must be positive")
        super().__init__(cache, meta=meta)
        self._q = tuple(q)
        self._limit = limit

    @property
    def q(self):
        return self._q

    @property
    def limit(self):
        return self._limit

    def _with_cache(self, cache: PersistentMap, **kwargs: Any):
        return FIFOCache(cache, kwargs.get("q", self._q), self._limit, meta=self._meta)

    def cache_miss(self, item: Any, result: Any):
        q = self._q or (_FREE,) * self._limit
        head, rest = q[0], q[1:]
        base = self.cache.dissoc(head) if len(self) >= self._limit else self.cache
        return FIFOCache(
            base.assoc(item, result), rest + (item,), self._limit, meta=self._meta
        )

    def cache_evict(self, item: Any):
        if not self.cache_has(item):
            return self
        q = (_FREE,) + tuple(entry for entry in self._q if entry != item)
        return FIFOCache(self.cache.dissoc(item), q, self._limit, meta=self._meta)

    def cache_seed(self, base: Mapping[Any, Any]):
        base = _as_map(base)
        entries = list(base.items())
        keeping = entries[max(0, len(entries) - self._limit) :]
        queue = (_FREE,) * (self._limit - len(keeping)) + tuple(
            key for key, _ in keeping
        )
        return FIFOCache(
            lmap.PersistentMap.from_coll(keeping), queue, self._limit, meta=self._meta
        )


class LRUCache(PersistentCache):
    __slots__ = ("_lru", "_tick", "_limit")

    def __init__(
        self, cache: Mapping[Any, Any], lru=None, tick=0, limit: int = 32, meta=None
    ):
        if limit <= 0:
            raise ValueError("LRU cache threshold must be positive")
        super().__init__(cache, meta=meta)
        self._lru = dict(lru or {})
        self._tick = tick
        self._limit = limit

    @property
    def lru(self):
        return lmap.map(self._lru)

    @property
    def tick(self):
        return self._tick

    @property
    def limit(self):
        return self._limit

    def cache_hit(self, item: Any):
        tick = self._tick + 1
        lru = dict(self._lru)
        if self.cache_has(item):
            lru[item] = tick
        return LRUCache(self.cache, lru, tick, self._limit, meta=self._meta)

    def cache_miss(self, item: Any, result: Any):
        tick = self._tick + 1
        lru = dict(self._lru)
        base = self.cache
        if len(lru) >= self._limit:
            victim = item if item in lru else min(lru, key=lru.__getitem__)
            base = base.dissoc(victim)
            lru.pop(victim, None)
        lru[item] = tick
        return LRUCache(
            base.assoc(item, result), lru, tick, self._limit, meta=self._meta
        )

    def cache_evict(self, item: Any):
        if not self.cache_has(item):
            return self
        lru = dict(self._lru)
        lru.pop(item, None)
        return LRUCache(
            self.cache.dissoc(item), lru, self._tick + 1, self._limit, meta=self._meta
        )

    def cache_seed(self, base: Mapping[Any, Any]):
        base = _as_map(base)
        return LRUCache(base, {key: 0 for key in base}, 0, self._limit, meta=self._meta)


class TTLCacheQ(PersistentCache):
    __slots__ = ("_ttl", "_q", "_gen", "_ttl_ms", "_clock")

    def __init__(
        self,
        cache: Mapping[Any, Any],
        ttl=None,
        q=(),
        gen=0,
        ttl_ms: int = 2000,
        meta=None,
        clock: Callable[[], int] | None = None,
    ):
        if ttl_ms < 0:
            raise ValueError("TTL cache ttl must not be negative")
        super().__init__(cache, meta=meta)
        self._ttl = dict(ttl or {})
        self._q = tuple(q)
        self._gen = gen
        self._ttl_ms = ttl_ms
        self._clock = _now_millis if clock is None else clock

    @property
    def ttl(self):
        return lmap.map(self._ttl)

    @property
    def q(self):
        return self._q

    @property
    def gen(self):
        return self._gen

    @property
    def ttl_ms(self):
        return self._ttl_ms

    def cache_has(self, item: Any) -> bool:
        generation, created = self._ttl.get(item, (0, -self._ttl_ms))
        del generation
        return item in self._inner and self._clock() - created < self._ttl_ms

    def _prune(self, now: int):
        queue = self._q
        keys = []
        while queue and now - queue[0][2] > self._ttl_ms:
            key, generation, _ = queue[0]
            queue = queue[1:]
            if self._ttl.get(key, (None,))[0] == generation:
                keys.append(key)
        return keys, queue

    def cache_miss(self, item: Any, result: Any):
        now = self._clock()
        stale, queue = self._prune(now)
        base = self.cache.dissoc(*stale).assoc(item, result)
        ttl = {key: value for key, value in self._ttl.items() if key not in stale}
        ttl[item] = (self._gen, now)
        return TTLCacheQ(
            base,
            ttl,
            queue + ((item, self._gen, now),),
            self._gen + 1,
            self._ttl_ms,
            meta=self._meta,
            clock=self._clock,
        )

    def cache_evict(self, item: Any):
        ttl = dict(self._ttl)
        ttl.pop(item, None)
        return TTLCacheQ(
            self.cache.dissoc(item),
            self._ttl if item not in self._ttl else ttl,
            self._q,
            self._gen,
            self._ttl_ms,
            meta=self._meta,
            clock=self._clock,
        )

    def cache_seed(self, base: Mapping[Any, Any]):
        base = _as_map(base)
        now = self._clock()
        return TTLCacheQ(
            base,
            {key: (self._gen, now) for key in base},
            self._q + tuple((key, self._gen, now) for key in base),
            self._gen + 1,
            self._ttl_ms,
            meta=self._meta,
            clock=self._clock,
        )


class LUCache(PersistentCache):
    __slots__ = ("_lu", "_limit")

    def __init__(self, cache: Mapping[Any, Any], lu=None, limit: int = 32, meta=None):
        if limit <= 0:
            raise ValueError("LU cache threshold must be positive")
        super().__init__(cache, meta=meta)
        self._lu = dict(lu or {})
        self._limit = limit

    @property
    def lu(self):
        return lmap.map(self._lu)

    @property
    def limit(self):
        return self._limit

    def cache_hit(self, item: Any):
        lu = dict(self._lu)
        lu[item] = lu[item] + 1
        return LUCache(self.cache, lu, self._limit, meta=self._meta)

    def cache_miss(self, item: Any, result: Any):
        lu = dict(self._lu)
        base = self.cache
        if len(lu) >= self._limit:
            victim = item if item in lu else min(lu, key=lu.__getitem__)
            base = base.dissoc(victim)
            lu.pop(victim, None)
        lu[item] = lu.get(item, 0) + 1
        return LUCache(base.assoc(item, result), lu, self._limit, meta=self._meta)

    def cache_evict(self, item: Any):
        if not self.cache_has(item):
            return self
        lu = dict(self._lu)
        lu.pop(item, None)
        return LUCache(self.cache.dissoc(item), lu, self._limit, meta=self._meta)

    def cache_seed(self, base: Mapping[Any, Any]):
        base = _as_map(base)
        return LUCache(base, {key: 0 for key in base}, self._limit, meta=self._meta)


def _oldest(table: dict[Any, int]) -> Any:
    return min(table, key=table.__getitem__)


class LIRSCache(PersistentCache):
    """Persistent implementation of the LIRS S/Q history algorithm."""

    __slots__ = ("_lru_s", "_lru_q", "_tick", "_limit_s", "_limit_q")

    def __init__(
        self,
        cache: Mapping[Any, Any],
        lru_s=None,
        lru_q=None,
        tick=0,
        limit_s: int = 32,
        limit_q: int = 32,
        meta=None,
    ):
        if limit_s <= 0 or limit_q <= 0:
            raise ValueError("LIRS history limits must be positive")
        super().__init__(cache, meta=meta)
        self._lru_s = dict(lru_s or {})
        self._lru_q = dict(lru_q or {})
        self._tick = tick
        self._limit_s = limit_s
        self._limit_q = limit_q

    @property
    def lruS(self):
        return lmap.map(self._lru_s)

    @property
    def lruQ(self):
        return lmap.map(self._lru_q)

    @property
    def tick(self):
        return self._tick

    @property
    def limitS(self):
        return self._limit_s

    @property
    def limitQ(self):
        return self._limit_q

    @staticmethod
    def _prune(lru_s: dict[Any, int], lru_q: dict[Any, int], cache: PersistentMap):
        lru_s = dict(lru_s)
        while lru_s:
            key = _oldest(lru_s)
            if key in lru_q or key not in cache:
                lru_s.pop(key)
            else:
                break
        return lru_s

    def cache_hit(self, item: Any):
        tick = self._tick + 1
        s, q = dict(self._lru_s), dict(self._lru_q)
        if item not in s:  # 2.3
            s[item] = tick
            q[item] = tick
        else:
            oldest_s = _oldest(s)
            if item in q:  # 2.2
                q.pop(item)
                q[oldest_s] = tick
                s.pop(oldest_s)
                s[item] = tick
                s = self._prune(s, q, self.cache)
            else:  # 2.1
                s[item] = tick
                s = self._prune(s, q, self.cache)
        return LIRSCache(
            self.cache, s, q, tick, self._limit_s, self._limit_q, meta=self._meta
        )

    def cache_miss(self, item: Any, result: Any):
        tick = self._tick + 1
        s, q = dict(self._lru_s), dict(self._lru_q)
        if len(self) < self._limit_s:  # 1.1
            oldest_s = _oldest(s)
            s.pop(oldest_s)
            s[item] = tick
            base = self.cache.assoc(item, result)
        else:
            oldest_q = _oldest(q)
            q.pop(oldest_q)
            base = self.cache.dissoc(oldest_q).assoc(item, result)
            if item in s:  # 1.3
                last_s = _oldest(s)
                s.pop(last_s)
                s[item] = tick
                s = self._prune(s, q, base)
                q[last_s] = tick
            else:  # 1.2
                s[item] = tick
                q[item] = tick
        return LIRSCache(
            base, s, q, tick, self._limit_s, self._limit_q, meta=self._meta
        )

    def cache_evict(self, item: Any):
        if not self.cache_has(item):
            return self
        s, q = dict(self._lru_s), dict(self._lru_q)
        s.pop(item, None)
        q.pop(item, None)
        return LIRSCache(
            self.cache.dissoc(item),
            s,
            q,
            self._tick,
            self._limit_s,
            self._limit_q,
            meta=self._meta,
        )

    def cache_seed(self, base: Mapping[Any, Any]):
        base = _as_map(base)
        return LIRSCache(
            base,
            {key: key for key in range(-self._limit_s, 0)},
            {key: key for key in range(-self._limit_q, 0)},
            0,
            self._limit_s,
            self._limit_q,
            meta=self._meta,
        )


def basic_cache_factory(base: Mapping[Any, Any]) -> BasicCache:
    return BasicCache(_as_map(base))


# Module-level adapters are imported by the Lisp namespace.  Keeping them here
# also lets CacheProtocol dispatch stay independent from Python method munging.
def cache_lookup(cache: PersistentCache, item: Any, not_found: Any = _MISSING) -> Any:
    return cache.cache_lookup(item, not_found)


def cache_has(cache: PersistentCache, item: Any) -> bool:
    return cache.cache_has(item)


def cache_hit(cache: PersistentCache, item: Any) -> PersistentCache:
    return cache.cache_hit(item)


def cache_miss(cache: PersistentCache, item: Any, result: Any) -> PersistentCache:
    return cache.cache_miss(item, result)


def cache_evict(cache: PersistentCache, item: Any) -> PersistentCache:
    return cache.cache_evict(item)


def cache_seed(cache: PersistentCache, base: Mapping[Any, Any]) -> PersistentCache:
    return cache.cache_seed(base)


def fifo_cache_factory(base: Mapping[Any, Any], threshold: int = 32) -> FIFOCache:
    return FIFOCache(lmap.EMPTY, (), threshold).cache_seed(_as_map(base))


def lru_cache_factory(base: Mapping[Any, Any], threshold: int = 32) -> LRUCache:
    return LRUCache(lmap.EMPTY, {}, 0, threshold).cache_seed(_as_map(base))


def ttl_cache_factory(base: Mapping[Any, Any], ttl: int = 2000) -> TTLCacheQ:
    return TTLCacheQ(lmap.EMPTY, {}, (), 0, ttl).cache_seed(_as_map(base))


def lu_cache_factory(base: Mapping[Any, Any], threshold: int = 32) -> LUCache:
    return LUCache(lmap.EMPTY, {}, threshold).cache_seed(_as_map(base))


def lirs_cache_factory(
    base: Mapping[Any, Any], s_history_limit: int = 32, q_history_limit: int = 32
) -> LIRSCache:
    return LIRSCache(
        lmap.EMPTY, {}, {}, 0, s_history_limit, q_history_limit
    ).cache_seed(_as_map(base))


def soft_cache_factory(_base: Mapping[Any, Any]):
    """Reject the JVM-only soft-reference cache explicitly.

    Python weak references do not model Java soft references (notably their
    memory-pressure retention behavior), so a strong-reference substitute would
    be misleading.
    """
    raise NotImplementedError(
        "soft-cache-factory requires JVM SoftReference semantics and is not available"
    )


def wrapped_lookup_or_miss(
    cache_atom: Any,
    item: Any,
    wrap_fn: Callable[[Callable[[Any], Any], Any], Any],
    value_fn: Callable[[Any], Any],
) -> Any:
    """Atomically retrieve or populate an atom-wrapped persistent cache.

    The cache is inspected and populated while holding Basilisp Atom's reentrant
    lock. This avoids duplicate value computations under contention. Errors from
    the value function leave the cache unchanged.
    """
    lock = getattr(cache_atom, "_lock", None)
    if lock is None:
        raise TypeError("lookup-or-miss expects a Basilisp atom")
    with lock:
        cache = cache_atom.deref()
        if not isinstance(cache, PersistentCache):
            raise TypeError("lookup-or-miss expects an atom containing a cache")
        if cache.cache_has(item):
            return cache.cache_lookup(item)
        value = wrap_fn(value_fn, item)
        updated = cache.cache_miss(item, value)
        cache_atom.reset(updated)
        return updated.cache_lookup(item)


def wrapped_through(
    cache_atom: Any,
    item: Any,
    wrap_fn: Callable[[Callable[[Any], Any], Any], Any],
    value_fn: Callable[[Any], Any],
) -> PersistentCache:
    """Atomically run the cache hit/miss transition used by wrapped ``through``."""
    lock = getattr(cache_atom, "_lock", None)
    if lock is None:
        raise TypeError("wrapped through expects a Basilisp atom")
    with lock:
        cache = cache_atom.deref()
        if not isinstance(cache, PersistentCache):
            raise TypeError("wrapped through expects an atom containing a cache")
        updated = (
            cache.cache_hit(item)
            if cache.cache_has(item)
            else cache.cache_miss(item, wrap_fn(value_fn, item))
        )
        cache_atom.reset(updated)
        return updated
