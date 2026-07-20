import threading
import random

import pytest

from basilisp.core_cache import TTLCacheQ
from basilisp.core_memoize import memo, memoizer, snapshot
from basilisp.lang import vector as vec


def test_same_key_concurrency_computes_once():
    calls = [0]
    calls_lock = threading.Lock()
    barrier = threading.Barrier(20)
    memoized = memo(lambda value: _counted_value(value, calls, calls_lock))
    results = []

    def worker():
        barrier.wait()
        results.append(memoized("key"))

    threads = [threading.Thread(target=worker) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert calls == [1]
    assert results == ["key"] * 20


def _counted_value(value, calls, lock):
    with lock:
        calls[0] += 1
    return value


def test_exception_is_not_memoized_and_is_retried():
    calls = [0]

    def failing(_value):
        calls[0] += 1
        raise RuntimeError("retry me")

    memoized = memo(failing)
    with pytest.raises(RuntimeError, match="retry me"):
        memoized("x")
    with pytest.raises(RuntimeError, match="retry me"):
        memoized("x")
    assert calls == [2]


def test_ttl_expiry_recomputes_and_prunes_with_a_manual_clock():
    now = [10]
    calls = [0]
    cache = TTLCacheQ({}, {}, (), 0, 5, clock=lambda: now[0])
    memoized = memoizer(
        lambda value: _counted_value(value, calls, threading.Lock()), cache
    )

    assert memoized("a") == "a"
    assert memoized("a") == "a"
    assert calls == [1]
    now[0] += 5
    assert memoized("a") == "a"
    assert calls == [2]
    assert dict(snapshot(memoized).items()) == {vec.vector(["a"]): "a"}


def test_seed_snapshot_and_cache_key_transform():
    calls = [0]

    def f(first, second):
        calls[0] += 1
        return first + second

    # Exercise a seed through the public constructor and the ordinary vector key.
    seeded = memo(f, {vec.vector([1, 2]): 99})
    assert seeded(1, 2) == 99
    assert seeded(2, 3) == 5
    assert dict(snapshot(seeded).items()) == {
        vec.vector([1, 2]): 99,
        vec.vector([2, 3]): 5,
    }
    assert calls == [1]


def test_memo_policy_fuzz_matches_fifo_lru_and_lu_reference_models():
    source = random.Random(190217)
    limit = 7
    calls = {"fifo": [0], "lru": [0], "lu": [0]}

    def counted(policy):
        def f(value):
            calls[policy][0] += 1
            return value * 10

        return f

    from basilisp.core_memoize import fifo, lru, lu

    fifo_memo = fifo(counted("fifo"), threshold=limit)
    lru_memo = lru(counted("lru"), threshold=limit)
    lu_memo = lu(counted("lu"), threshold=limit)
    fifo_model, lru_model, lu_model = {}, {}, {}
    free = object()
    fifo_queue = [free] * limit
    lru_ticks, lu_counts = {}, {}
    expected_misses = {"fifo": 0, "lru": 0, "lu": 0}

    for _ in range(2500):
        key = source.randrange(35)
        assert fifo_memo(key) == lru_memo(key) == lu_memo(key) == key * 10

        if key not in fifo_model:
            expected_misses["fifo"] += 1
            victim = fifo_queue.pop(0)
            if len(fifo_model) >= limit:
                fifo_model.pop(victim, None)
            fifo_model[key] = key * 10
            fifo_queue.append(key)

        if key in lru_model:
            lru_ticks[key] = max(lru_ticks.values(), default=0) + 1
        else:
            expected_misses["lru"] += 1
            if len(lru_model) >= limit:
                victim = min(lru_ticks, key=lru_ticks.__getitem__)
                lru_model.pop(victim)
                lru_ticks.pop(victim)
            lru_model[key] = key * 10
            lru_ticks[key] = max(lru_ticks.values(), default=0) + 1

        if key in lu_model:
            lu_counts[key] += 1
        else:
            expected_misses["lu"] += 1
            if len(lu_model) >= limit:
                victim = min(lu_counts, key=lu_counts.__getitem__)
                lu_model.pop(victim)
                lu_counts.pop(victim)
            lu_model[key] = key * 10
            lu_counts[key] = 1

        assert dict(snapshot(fifo_memo).items()) == {
            vec.vector([key]): value for key, value in fifo_model.items()
        }
        assert dict(snapshot(lru_memo).items()) == {
            vec.vector([key]): value for key, value in lru_model.items()
        }
        assert dict(snapshot(lu_memo).items()) == {
            vec.vector([key]): value for key, value in lu_model.items()
        }

    assert {policy: count[0] for policy, count in calls.items()} == expected_misses
