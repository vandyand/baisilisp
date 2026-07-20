import random
import threading

import pytest

from basilisp.core_cache import (
    BasicCache,
    FIFOCache,
    LRUCache,
    LUCache,
    TTLCacheQ,
    wrapped_lookup_or_miss,
)
from basilisp.lang.atom import Atom


def test_basic_cache_is_immutable_and_map_compatible():
    original = BasicCache({"a": 1})
    changed = original.assoc("b", 2)

    assert dict(original.items()) == {"a": 1}
    assert dict(changed.items()) == {"a": 1, "b": 2}
    assert changed.cache_lookup("missing", "fallback") == "fallback"
    assert dict(changed.dissoc("a").items()) == {"b": 2}


def test_fifo_lru_and_lu_match_independent_random_models():
    source = random.Random(84831)
    fifo = FIFOCache({}, (), 5)
    lru = LRUCache({}, {}, 0, 5)
    lu = LUCache({}, {}, 5)
    fifo_model: dict[int, int] = {}
    free = object()
    fifo_order: list[object | int] = [free] * 5
    lru_model: dict[int, int] = {}
    lru_tick: dict[int, int] = {}
    lu_model: dict[int, int] = {}
    lu_count: dict[int, int] = {}

    for _ in range(3000):
        item = source.randrange(18)
        value = source.randrange(-1000, 1000)
        if source.random() < 0.62:
            victim = fifo_order.pop(0)
            if len(fifo_model) >= 5:
                fifo_model.pop(victim, None)
            fifo_model[item] = value
            fifo_order.append(item)
            fifo = fifo.cache_miss(item, value)

            if len(lru_tick) >= 5:
                victim = (
                    item
                    if item in lru_tick
                    else min(lru_tick, key=lru_tick.__getitem__)
                )
                lru_model.pop(victim, None)
                lru_tick.pop(victim, None)
            lru_model[item] = value
            lru_tick[item] = max(lru_tick.values(), default=0) + 1
            lru = lru.cache_miss(item, value)

            if len(lu_count) >= 5:
                victim = (
                    item
                    if item in lu_count
                    else min(lu_count, key=lu_count.__getitem__)
                )
                lu_model.pop(victim, None)
                lu_count.pop(victim, None)
            lu_model[item] = value
            lu_count[item] = lu_count.get(item, 0) + 1
            lu = lu.cache_miss(item, value)
        elif item in fifo_model:
            fifo_model.pop(item)
            fifo_order = [free] + [key for key in fifo_order if key != item]
            fifo = fifo.cache_evict(item)
            if item in lru_model:
                lru_model.pop(item)
                lru_tick.pop(item)
                lru = lru.cache_evict(item)
            if item in lu_model:
                lu_model.pop(item)
                lu_count.pop(item)
                lu = lu.cache_evict(item)
        else:
            if item in lru_model:
                lru_tick[item] = max(lru_tick.values(), default=0) + 1
                lru = lru.cache_hit(item)
            if item in lu_model:
                lu_count[item] += 1
                lu = lu.cache_hit(item)

        assert dict(fifo.items()) == fifo_model
        assert dict(lru.items()) == lru_model
        assert dict(lu.items()) == lu_model


def test_ttl_boundary_and_stale_queue_pruning_with_manual_clock():
    now = [1_000]
    cache = TTLCacheQ({}, {}, (), 0, 10, clock=lambda: now[0])
    cache = cache.cache_miss("first", 1)
    now[0] += 10
    assert not cache.cache_has("first")  # expiry is strict at the boundary
    assert dict(cache.items()) == {"first": 1}  # lookup does not mutate the cache
    now[0] += 1
    cache = cache.cache_miss("second", 2)
    assert dict(cache.items()) == {"second": 2}


def test_wrapped_lookup_or_miss_computes_once_under_contention():
    atom = Atom(BasicCache({}))
    barrier = threading.Barrier(12)
    calls = [0]
    lock = threading.Lock()
    results = []

    def value_fn(_item):
        with lock:
            calls[0] += 1
        return "value"

    def worker():
        barrier.wait()
        results.append(wrapped_lookup_or_miss(atom, "key", lambda f, x: f(x), value_fn))

    threads = [threading.Thread(target=worker) for _ in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert calls == [1]
    assert results == ["value"] * 12
    assert dict(atom.deref().items()) == {"key": "value"}


def test_soft_cache_refusal_is_explicit():
    from basilisp.core_cache import soft_cache_factory

    with pytest.raises(NotImplementedError, match="SoftReference"):
        soft_cache_factory({})
