"""Portable implementation of the public ``clojure.core.memoize`` API."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from basilisp.core_cache import (
    BasicCache,
    FIFOCache,
    LRUCache,
    LUCache,
    PersistentCache,
    TTLCacheQ,
    basic_cache_factory,
    fifo_cache_factory,
    lru_cache_factory,
    lu_cache_factory,
    ttl_cache_factory,
)
from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap
from basilisp.lang import vector as vec
from basilisp.lang.atom import Atom
from basilisp.lang.interfaces import IDeref, IPending
from basilisp.lang.seq import iterator_sequence

_CACHE_KEY = kw.keyword("cache", "clojure.core.memoize")
_ORIGINAL_KEY = kw.keyword("original", "clojure.core.memoize")
_ARGS_FN_KEY = kw.keyword("args-fn", "clojure.core.memoize")
_MISSING = object()


def cache_lookup(cache: Any, item: Any, not_found: Any = _MISSING):
    return cache.cache_lookup(item, not_found)


def cache_has(cache: Any, item: Any) -> bool:
    return cache.cache_has(item)


def cache_hit(cache: Any, item: Any):
    return cache.cache_hit(item)


def cache_miss(cache: Any, item: Any, result: Any):
    return cache.cache_miss(item, result)


def cache_evict(cache: Any, item: Any):
    return cache.cache_evict(item)


def cache_seed(cache: Any, base: Mapping[Any, Any]):
    return cache.cache_seed(base)


class RetryingDelay(IDeref, IPending):
    """A thread-safe delay which retries its function after an exception."""

    __slots__ = ("_fun", "_available", "_value", "_lock")

    def __init__(self, fun: Callable[[], Any]):
        self._fun = fun
        self._available = False
        self._value = None
        self._lock = threading.Lock()

    def deref(self):
        if self._available:
            return self._value
        with self._lock:
            if self._available:
                return self._value
            # Keep the delay unrealized if fun raises so a later invocation
            # retries, matching core.memoize's RetryingDelay.
            value = self._fun()
            self._value = value
            self._available = True
            return value

    @property
    def is_realized(self) -> bool:
        return self._available


class _ValueDelay(IDeref, IPending):
    """A realized derefable used for user-provided seed and swap values."""

    __slots__ = ("_value",)

    def __init__(self, value: Any):
        self._value = value

    def deref(self):
        return self._value

    @property
    def is_realized(self) -> bool:
        return True


def _is_derefable(value: Any) -> bool:
    return isinstance(value, IDeref)


def _derefable_seed(seed: Mapping[Any, Any]) -> lmap.PersistentMap:
    return lmap.PersistentMap.from_coll(
        (key, value if _is_derefable(value) else _ValueDelay(value))
        for key, value in seed.items()
    )


class PluggableMemoization:
    """A cache-protocol-shaped wrapper retained for core.memoize API parity."""

    __slots__ = ("f", "cache")

    def __init__(self, f: Callable[..., Any], cache: Any):
        self.f = f
        self.cache = cache

    def cache_lookup(self, item: Any, not_found: Any = _MISSING):
        return self.cache.cache_lookup(item, not_found)

    def cache_has(self, item: Any) -> bool:
        return self.cache.cache_has(item)

    def cache_hit(self, item: Any):
        return PluggableMemoization(self.f, self.cache.cache_hit(item))

    def cache_miss(self, item: Any, result: Any):
        return PluggableMemoization(self.f, self.cache.cache_miss(item, result))

    def cache_evict(self, item: Any):
        return PluggableMemoization(self.f, self.cache.cache_evict(item))

    def cache_seed(self, base: Mapping[Any, Any]):
        return PluggableMemoization(
            self.f, self.cache.cache_seed(_derefable_seed(base))
        )


def _cache_backing(cache: Any):
    """Return the map which physically contains cached delays."""
    while isinstance(cache, PluggableMemoization):
        cache = cache.cache
    return cache.cache if isinstance(cache, PersistentCache) else cache


def _cache_id(f: Any):
    meta = getattr(f, "meta", None)
    return meta.get(_CACHE_KEY) if isinstance(meta, Mapping) else None


def _key_function(f: Any) -> Callable[[Any], Any]:
    meta = getattr(f, "meta", None)
    if isinstance(meta, Mapping):
        key_fn = meta.get(_ARGS_FN_KEY)
        if key_fn is not None:
            return key_fn
    return lambda args: args


def _cache_key(value: Any):
    if value is None or value is False:
        return vec.EMPTY
    # A normal variadic Python call arrives as a tuple. Normalize it to a
    # persistent vector so memo seeds such as {[42] value} line up naturally.
    if isinstance(value, tuple):
        return vec.vector(value)
    return value


class MemoizedFunction:
    """Callable carrying a manipulable cache atom in normal Basilisp metadata."""

    __slots__ = ("_f", "_cache_atom", "_key_fn", "_lock", "meta")

    def __init__(self, f: Callable[..., Any], cache_atom: Atom, key_fn=None, meta=None):
        self._f = f
        self._cache_atom = cache_atom
        self._key_fn = _key_function(f) if key_fn is None else key_fn
        self._lock = threading.RLock()
        self.meta = (
            lmap.map({_CACHE_KEY: cache_atom, _ORIGINAL_KEY: f})
            if meta is None
            else meta
        )

    def __call__(self, *args):
        key = _cache_key(self._key_fn(args))
        with self._lock:
            cache = self._cache_atom.deref()
            if cache.cache_has(key):
                updated = cache.cache_hit(key)
            else:
                delay = RetryingDelay(lambda: self._f(*args))
                updated = cache.cache_miss(key, delay)
            self._cache_atom.reset(updated)
            value = updated.cache_lookup(key, _MISSING)
        if value is _MISSING:
            # This can only occur when an external concurrent cache mutation
            # races our access. Re-enter through the normal retry path.
            return self(*args)
        return value.deref()

    def with_meta(self, meta):
        return MemoizedFunction(self._f, self._cache_atom, self._key_fn, meta=meta)


def _memoized(f: Callable[..., Any], cache: Any, seed: Mapping[Any, Any] | None = None):
    if seed is not None:
        cache = cache.cache_seed(_derefable_seed(seed))
    return MemoizedFunction(f, Atom(cache))


def memoizer(f: Callable[..., Any], cache: Any, seed: Mapping[Any, Any] | None = None):
    return _memoized(f, PluggableMemoization(f, cache), seed)


def build_memoizer(
    cache_factory: Callable[..., Any], f: Callable[..., Any], *args: Any
):
    return _memoized(f, cache_factory(f, *args))


def memo(f: Callable[..., Any], seed: Mapping[Any, Any] | None = None):
    return memoizer(f, basic_cache_factory({}), {} if seed is None else seed)


def fifo(
    f: Callable[..., Any], base: Mapping[Any, Any] | None = None, threshold: int = 32
):
    return memoizer(f, fifo_cache_factory({}, threshold), {} if base is None else base)


def lru(
    f: Callable[..., Any], base: Mapping[Any, Any] | None = None, threshold: int = 32
):
    return memoizer(f, lru_cache_factory({}, threshold), {} if base is None else base)


def ttl(
    f: Callable[..., Any], base: Mapping[Any, Any] | None = None, threshold: int = 32
):
    return memoizer(f, ttl_cache_factory({}, threshold), {} if base is None else base)


def lu(
    f: Callable[..., Any], base: Mapping[Any, Any] | None = None, threshold: int = 32
):
    return memoizer(f, lu_cache_factory({}, threshold), {} if base is None else base)


def memoized_qmark(f: Any) -> bool:
    return _cache_id(f) is not None


def snapshot(f: Any):
    cache_atom = _cache_id(f)
    if cache_atom is None:
        return None
    backing = _cache_backing(cache_atom.deref())
    return lmap.PersistentMap.from_coll(
        (vec.vector(key), value.deref()) for key, value in backing.items()
    )


def lazy_snapshot(f: Any) -> Iterable[tuple[Any, Any]] | None:
    cache_atom = _cache_id(f)
    if cache_atom is None:
        return None
    backing = _cache_backing(cache_atom.deref())
    return iterator_sequence(
        vec.vector((vec.vector(key), value.deref())) for key, value in backing.items()
    )


def memo_clear(f: Any, args: Any = _MISSING):
    cache_atom = _cache_id(f)
    if cache_atom is None:
        return None
    if args is _MISSING:
        return cache_atom.reset(cache_atom.deref().cache_seed({}))
    return cache_atom.reset(cache_atom.deref().cache_evict(args))


def memo_reset(f: Any, base: Mapping[Any, Any]):
    cache_atom = _cache_id(f)
    if cache_atom is None:
        return None
    return cache_atom.reset(cache_atom.deref().cache_seed(_derefable_seed(base)))


def memo_swap(f: Any, swap_fn_or_base: Any, args: Any = _MISSING, *results: Any):
    if args is _MISSING:
        return memo_reset(f, swap_fn_or_base)
    cache_atom = _cache_id(f)
    if cache_atom is None:
        return None
    return cache_atom.swap(
        lambda cache: swap_fn_or_base(
            cache, args, *(_ValueDelay(result) for result in results)
        )
    )


def memo_unwrap(f: Any):
    meta = getattr(f, "meta", None)
    return meta.get(_ORIGINAL_KEY) if isinstance(meta, Mapping) else None
