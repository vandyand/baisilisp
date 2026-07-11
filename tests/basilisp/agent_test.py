import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from basilisp.lang import agent as agent


def test_agent_restart_can_replace_state_with_none():
    a = agent.Agent(1)

    assert a.restart(None) is a
    assert a.deref() is None


def test_agent_continues_after_raising_error_handler():
    def action_that_fails(_state):
        raise ValueError("action failed")

    def error_handler(_agent, _error):
        raise RuntimeError("error handler failed")

    a = agent.Agent(0, error_mode="continue", error_handler=error_handler)
    with ThreadPoolExecutor(max_workers=2) as executor:
        a.submit(executor, action_that_fails)
        a.submit(executor, lambda state: state + 1)

        assert a.await_completion(timeout=2)

    assert a.deref() == 1
    assert isinstance(a.error, ValueError)


def test_agent_keeps_its_execution_lease_while_handling_an_error():
    handler_started = threading.Event()
    release_handler = threading.Event()
    action_started = threading.Event()

    def action_that_fails(_state):
        raise ValueError("action failed")

    def error_handler(_agent, _error):
        handler_started.set()
        assert release_handler.wait(timeout=2)

    def action(state):
        action_started.set()
        return state + 1

    a = agent.Agent(0, error_mode="continue", error_handler=error_handler)
    with ThreadPoolExecutor(max_workers=2) as executor:
        a.submit(executor, action_that_fails)
        assert handler_started.wait(timeout=2)
        a.submit(executor, action)

        assert not action_started.wait(timeout=0.1)
        release_handler.set()
        assert a.await_completion(timeout=2)

    assert a.deref() == 1


def test_watcher_failure_does_not_wedge_an_agent_queue():
    def failing_watcher(_key, _agent, _old, _new):
        raise RuntimeError("watcher failed")

    a = agent.Agent(0)
    a.add_watch("failing", failing_watcher)
    with ThreadPoolExecutor(max_workers=2) as executor:
        a.submit(executor, lambda state: state + 1)
        a.submit(executor, lambda state: state + 1)

        assert a.await_completion(timeout=2)

    assert a.deref() == 2
    assert not a.pending()


def test_rejected_executor_does_not_wedge_an_agent_queue():
    a = agent.Agent(0)
    executor = ThreadPoolExecutor(max_workers=1)
    executor.shutdown()

    with pytest.raises(RuntimeError):
        a.submit(executor, lambda state: state + 1)

    assert isinstance(a.error, RuntimeError)
    assert not a.pending()


def test_restart_rejects_an_agent_with_an_active_action():
    action_started = threading.Event()
    release_action = threading.Event()

    def action(state):
        action_started.set()
        assert release_action.wait(timeout=2)
        return state + 1

    a = agent.Agent(0)
    with ThreadPoolExecutor(max_workers=1) as executor:
        a.submit(executor, action)
        assert action_started.wait(timeout=2)

        with pytest.raises(RuntimeError, match="Cannot restart"):
            a.restart(10)

        release_action.set()
        assert a.await_completion(timeout=2)

    assert a.deref() == 1


@pytest.mark.parametrize("clear_actions", [False, True])
def test_restart_controls_actions_queued_before_a_failure(clear_actions):
    action_started = threading.Event()
    release_action = threading.Event()

    def action_that_fails(_state):
        action_started.set()
        assert release_action.wait(timeout=2)
        raise ValueError("action failed")

    a = agent.Agent(0)
    with ThreadPoolExecutor(max_workers=1) as executor:
        a.submit(executor, action_that_fails)
        assert action_started.wait(timeout=2)
        a.submit(executor, lambda state: state + 1)
        release_action.set()

        assert a.await_completion(timeout=2)
        assert not a.pending()
        a.restart(clear_actions=clear_actions)
        assert a.await_completion(timeout=2)

    assert a.deref() == (0 if clear_actions else 1)


@pytest.mark.parametrize("seed", range(24))
def test_agent_serializes_random_parallel_submissions(seed):
    producer_count = 5
    actions_per_producer = 80
    random_source = random.Random(seed)
    increments = [
        [random_source.randint(-5, 9) for _ in range(actions_per_producer)]
        for _ in range(producer_count)
    ]
    a = agent.Agent(0)
    start = threading.Barrier(producer_count + 1)
    running = 0
    max_running = 0
    running_lock = threading.Lock()

    def action(state, increment):
        nonlocal max_running, running
        with running_lock:
            running += 1
            max_running = max(max_running, running)
        time.sleep(0.0001)
        with running_lock:
            running -= 1
        return state + increment

    def produce(values, executor):
        start.wait()
        for value in values:
            a.submit(executor, action, value)

    with ThreadPoolExecutor(max_workers=8) as executor:
        producers = [
            threading.Thread(target=produce, args=(values, executor))
            for values in increments
        ]
        for producer in producers:
            producer.start()
        start.wait()
        for producer in producers:
            producer.join()

        assert a.await_completion(timeout=10)

    assert a.deref() == sum(sum(values) for values in increments)
    assert max_running == 1
    assert not a.pending()


@pytest.mark.parametrize("mode", ["", "abort", "FAIL", None])
def test_agent_rejects_invalid_error_modes(mode):
    with pytest.raises(ValueError, match="Agent error mode"):
        agent.Agent(0, error_mode=mode)
