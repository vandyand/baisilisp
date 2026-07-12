import concurrent.futures
import threading
import time

import pytest

import basilisp.lang.interfaces
from basilisp.lang import stm
from basilisp.lang.exception import ExceptionInfo
from basilisp.lang.keyword import keyword


def test_ref_implements_reference_interfaces_and_commits_multiple_writes():
    first = stm.Ref(1)
    second = stm.Ref(2)

    assert isinstance(first, basilisp.lang.interfaces.IRef)
    assert isinstance(first, basilisp.lang.interfaces.IReference)

    def body():
        assert 1 == first.deref()
        assert 2 == second.deref()
        assert 3 == stm.alter(first, lambda value, amount: value + amount, 2)
        assert 6 == stm.ref_set(second, 6)
        return "committed"

    assert "committed" == stm.run_transaction(body)
    assert 3 == first.deref()
    assert 6 == second.deref()


def test_nested_transaction_joins_outer_transaction_and_watches_run_after_commit():
    ref = stm.Ref(1)
    watched = []
    ref.add_watch("record", lambda _key, _ref, old, new: watched.append((old, new)))

    def outer():
        assert 2 == stm.alter(ref, lambda value: value + 1)
        assert 3 == stm.run_transaction(lambda: stm.alter(ref, lambda value: value + 1))
        return ref.deref()

    assert 3 == stm.run_transaction(outer)
    assert 3 == ref.deref()
    assert [(1, 3)] == watched


def test_validator_failure_aborts_every_staged_write():
    even = stm.Ref(0, validator=lambda value: value % 2 == 0)
    other = stm.Ref("unchanged")

    def body():
        stm.alter(other, lambda _value: "new")
        return stm.alter(even, lambda value: value + 1)

    with pytest.raises(ExceptionInfo, match="Invalid reference state"):
        stm.run_transaction(body)

    assert 0 == even.deref()
    assert "unchanged" == other.deref()


def test_conflicting_transactions_retry_and_preserve_both_updates():
    ref = stm.Ref(0)
    barrier = threading.Barrier(2)
    attempts = []
    attempts_lock = threading.Lock()

    def increment():
        local_attempts = 0

        def body():
            nonlocal local_attempts
            local_attempts += 1
            value = ref.deref()
            if local_attempts == 1:
                barrier.wait(timeout=2)
            return stm.ref_set(ref, value + 1)

        result = stm.run_transaction(body)
        with attempts_lock:
            attempts.append(local_attempts)
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        assert {1, 2} == {
            future.result(timeout=2)
            for future in [
                executor.submit(increment),
                executor.submit(increment),
            ]
        }

    assert 2 == ref.deref()
    assert sum(attempts) == 3


def test_after_commit_actions_run_once_for_the_successful_retry_only():
    ref = stm.Ref(0)
    attempts = 0
    committed_attempts = []

    def body():
        nonlocal attempts
        attempts += 1
        attempt = attempts
        value = ref.deref()
        stm.after_commit(lambda: committed_attempts.append(attempt))
        if attempt == 1:
            thread = threading.Thread(
                target=lambda: stm.run_transaction(lambda: stm.ref_set(ref, 1))
            )
            thread.start()
            thread.join(timeout=2)
            assert not thread.is_alive()
        return stm.ref_set(ref, value + 1)

    assert 2 == stm.run_transaction(body)
    assert 2 == attempts
    assert [2] == committed_attempts
    assert 2 == ref.deref()


def test_max_attempts_reports_the_final_conflict_and_discards_its_actions():
    ref = stm.Ref(0)
    actions = []

    def body():
        value = ref.deref()
        stm.after_commit(lambda: actions.append("committed"))
        thread = threading.Thread(
            target=lambda: stm.run_transaction(lambda: stm.ref_set(ref, 1))
        )
        thread.start()
        thread.join(timeout=2)
        assert not thread.is_alive()
        return stm.ref_set(ref, value + 1)

    with pytest.raises(ExceptionInfo, match="conflict limit") as exc_info:
        stm.run_transaction(body, max_attempts=1)

    data = exc_info.value.data
    assert 1 == data.val_at(keyword("attempts", ns="basilisp.stm"))
    conflicts = data.val_at(keyword("conflicts", ns="basilisp.stm"))
    assert 1 == len(conflicts)
    conflict = conflicts[0]
    assert id(ref) == conflict.val_at(keyword("ref-id", ns="basilisp.stm"))
    assert 0 == conflict.val_at(keyword("read-version", ns="basilisp.stm"))
    assert 1 == conflict.val_at(keyword("current-version", ns="basilisp.stm"))
    assert 1 == ref.deref()
    assert [] == actions


@pytest.mark.parametrize("max_attempts", [0, -1])
def test_max_attempts_must_be_positive(max_attempts):
    with pytest.raises(ValueError, match="positive integer"):
        stm.run_transaction(lambda: None, max_attempts=max_attempts)


@pytest.mark.parametrize("max_attempts", [True, 1.0, "1"])
def test_max_attempts_must_be_an_integer(max_attempts):
    with pytest.raises(TypeError, match="positive integer"):
        stm.run_transaction(lambda: None, max_attempts=max_attempts)  # type: ignore[arg-type]


def test_max_attempts_allows_successful_outer_transactions_only():
    assert "committed" == stm.run_transaction(lambda: "committed", max_attempts=1)

    with pytest.raises(RuntimeError, match="outer transaction"):
        stm.run_transaction(lambda: stm.run_transaction(lambda: None, max_attempts=1))


def test_commute_returns_the_transaction_value_and_replays_at_commit():
    ref = stm.Ref(1)
    calls = []

    def add(value, amount):
        calls.append(value)
        return value + amount

    assert 3 == stm.run_transaction(lambda: stm.commute(ref, add, 2))
    assert 3 == ref.deref()
    assert [1, 1] == calls


def test_commute_replays_on_a_newer_value_without_retrying_the_body():
    ref = stm.Ref(0)
    reader_ready = threading.Event()
    writer_committed = threading.Event()
    attempts = 0

    def commute_body():
        nonlocal attempts
        attempts += 1
        ref.deref()
        if attempts == 1:
            reader_ready.set()
            assert writer_committed.wait(timeout=2)
        return stm.commute(ref, lambda value: value + 10)

    def write_new_value():
        assert reader_ready.wait(timeout=2)
        stm.run_transaction(lambda: stm.ref_set(ref, 1))
        writer_committed.set()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        commuter = executor.submit(lambda: stm.run_transaction(commute_body))
        writer = executor.submit(write_new_value)
        assert 10 == commuter.result(timeout=2)
        writer.result(timeout=2)

    assert 1 == attempts
    assert 11 == ref.deref()


def test_concurrent_commutes_preserve_every_update():
    ref = stm.Ref(0)
    calls = 0
    calls_lock = threading.Lock()
    start = threading.Barrier(2)

    def add(value):
        nonlocal calls
        with calls_lock:
            calls += 1
        return value + 1

    def increment():
        def body():
            start.wait(timeout=2)
            return stm.commute(ref, add)

        return stm.run_transaction(body)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(increment) for _ in range(2)]
        results = [future.result(timeout=2) for future in futures]

    assert len(results) == 2
    assert 2 == ref.deref()
    assert 2 == ref.version
    assert 4 == calls


def test_normal_writes_cannot_follow_a_commute_but_can_precede_one():
    ref = stm.Ref(0)

    def commute_then_alter():
        stm.commute(ref, lambda value: value + 1)
        stm.alter(ref, lambda value: value + 1)

    with pytest.raises(RuntimeError, match="after commute"):
        stm.run_transaction(commute_then_alter)
    assert 0 == ref.deref()

    calls = []

    def add(value):
        calls.append(value)
        return value + 10

    def alter_then_commute():
        stm.alter(ref, lambda value: value + 1)
        return stm.commute(ref, add)

    assert 11 == stm.run_transaction(alter_then_commute)
    assert 11 == ref.deref()
    assert [1] == calls


def test_ensure_requires_a_retry_when_a_commuted_ref_changes():
    ref = stm.Ref(0)
    reader_ready = threading.Event()
    writer_committed = threading.Event()
    attempts = 0

    def ensured_commute():
        nonlocal attempts
        attempts += 1
        expected = 0 if attempts == 1 else 1
        assert expected == stm.ensure(ref)
        if attempts == 1:
            reader_ready.set()
            assert writer_committed.wait(timeout=2)
        return stm.commute(ref, lambda value: value + 10)

    def write_new_value():
        assert reader_ready.wait(timeout=2)
        stm.run_transaction(lambda: stm.ref_set(ref, 1))
        writer_committed.set()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        commuter = executor.submit(lambda: stm.run_transaction(ensured_commute))
        writer = executor.submit(write_new_value)
        assert 11 == commuter.result(timeout=2)
        writer.result(timeout=2)

    assert 2 == attempts
    assert 11 == ref.deref()


def test_ensure_after_commute_retains_the_initial_version_for_validation():
    ref = stm.Ref(0)
    reader_ready = threading.Event()
    writer_committed = threading.Event()
    attempts = 0

    def commute_then_ensure():
        nonlocal attempts
        attempts += 1
        result = stm.commute(ref, lambda value: value + 10)
        assert result == stm.ensure(ref)
        if attempts == 1:
            reader_ready.set()
            assert writer_committed.wait(timeout=2)
        return result

    def write_new_value():
        assert reader_ready.wait(timeout=2)
        stm.run_transaction(lambda: stm.ref_set(ref, 1))
        writer_committed.set()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        commuter = executor.submit(lambda: stm.run_transaction(commute_then_ensure))
        writer = executor.submit(write_new_value)
        assert 11 == commuter.result(timeout=2)
        writer.result(timeout=2)

    assert 2 == attempts
    assert 11 == ref.deref()


def test_ensure_requires_an_active_transaction():
    with pytest.raises(RuntimeError, match="requires an active transaction"):
        stm.ensure(stm.Ref(0))


def test_after_commit_requires_a_transaction_and_callable():
    with pytest.raises(RuntimeError, match="requires an active transaction"):
        stm.after_commit(lambda: None)

    with pytest.raises(TypeError, match="must be callable"):
        stm.run_transaction(lambda: stm.after_commit(None))  # type: ignore[arg-type]


def test_after_commit_actions_follow_ref_watches():
    ref = stm.Ref(0)
    events = []
    ref.add_watch("record", lambda *_args: events.append("watch"))

    def body():
        stm.ref_set(ref, 1)
        stm.after_commit(lambda: events.append("after-commit"))

    stm.run_transaction(body)

    assert ["watch", "after-commit"] == events


def test_nested_transaction_after_commit_actions_run_with_the_outer_commit():
    events = []

    def outer():
        stm.after_commit(lambda: events.append("outer"))
        stm.run_transaction(lambda: stm.after_commit(lambda: events.append("inner")))

    stm.run_transaction(outer)

    assert ["outer", "inner"] == events


def test_after_commit_actions_run_after_a_watcher_failure():
    ref = stm.Ref(0)
    events = []

    def fail_watch(*_args):
        raise RuntimeError("watch failed")

    ref.add_watch("fail", fail_watch)

    def body():
        stm.ref_set(ref, 1)
        stm.after_commit(lambda: events.append("after-commit"))

    with pytest.raises(RuntimeError, match="watch failed"):
        stm.run_transaction(body)

    assert 1 == ref.deref()
    assert ["after-commit"] == events


def test_after_commit_failure_does_not_roll_back_committed_state():
    ref = stm.Ref(0)

    def fail_action():
        raise RuntimeError("after-commit failed")

    def body():
        stm.ref_set(ref, 1)
        stm.after_commit(fail_action)

    with pytest.raises(RuntimeError, match="after-commit failed"):
        stm.run_transaction(body)

    assert 1 == ref.deref()


def test_transaction_rejects_async_body_and_alter_requires_a_transaction():
    ref = stm.Ref(0)

    async def async_body():
        return 1

    with pytest.raises(TypeError, match="must not return an awaitable"):
        stm.run_transaction(async_body)
    with pytest.raises(RuntimeError, match="requires an active transaction"):
        stm.alter(ref, lambda value: value + 1)
    with pytest.raises(RuntimeError, match="requires an active transaction"):
        stm.ref_set(ref, 1)
    with pytest.raises(RuntimeError, match="I/O is not allowed"):
        stm.run_transaction(stm.io_bang)
    assert stm.io_bang() is None


def test_high_contention_preserves_all_multi_ref_updates():
    first = stm.Ref(0)
    second = stm.Ref(0)
    workers = 8
    updates_per_worker = 25

    def update_both():
        def body():
            first_value = first.deref()
            second_value = second.deref()
            time.sleep(0)
            stm.ref_set(first, first_value + 1)
            return stm.ref_set(second, second_value + 1)

        return stm.run_transaction(body)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(lambda: [update_both() for _ in range(updates_per_worker)])
            for _ in range(workers)
        ]
        for future in futures:
            future.result(timeout=10)

    expected = workers * updates_per_worker
    assert expected == first.deref()
    assert expected == second.deref()
    assert expected == first.version
    assert expected == second.version
