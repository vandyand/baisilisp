import random
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor

import pytest

from basilisp.lang import agent as agent
from basilisp.lang import futures


class FailingExecutor:
    def submit(self, _f, *_args):
        future = Future()
        future.set_exception(RuntimeError("executor rejected action"))
        return future


class DeferredFailingExecutor:
    def __init__(self):
        self.future = Future()

    def submit(self, _f, *_args):
        return self.future

    def fail(self):
        self.future.set_exception(RuntimeError("executor rejected action"))


def test_agent_restart_can_replace_state_with_none():
    a = agent.Agent(1)

    assert a.restart(None) is a
    assert a.deref() is None


def test_current_agent_marker_is_visible_only_while_running_an_action():
    observed = []
    a = agent.Agent(0)

    def action(state):
        observed.append(agent.current_agent())
        return state + 1

    with ThreadPoolExecutor(max_workers=1) as executor:
        a.submit(executor, action)
        assert a.await_completion(timeout=2)

    assert observed == [a]
    assert agent.current_agent() is None


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


def test_submit_failure_error_handler_runs_without_holding_agent_lock():
    handler_started = threading.Event()
    inspection_finished = threading.Event()

    def error_handler(_agent, _error):
        handler_started.set()
        assert inspection_finished.wait(timeout=2)

    a = agent.Agent(0, error_handler=error_handler)
    executor = ThreadPoolExecutor(max_workers=1)
    executor.shutdown()

    def inspect_agent():
        assert handler_started.wait(timeout=2)
        a.pending()
        inspection_finished.set()

    inspector = threading.Thread(target=inspect_agent)
    inspector.start()
    with pytest.raises(RuntimeError):
        a.submit(executor, lambda state: state + 1)
    inspector.join(timeout=2)

    assert not inspector.is_alive()


def test_pre_start_executor_failure_does_not_wedge_an_agent_queue():
    a = agent.Agent(0)

    assert a.submit(FailingExecutor(), lambda state: state + 1) is a
    assert a.await_completion(timeout=2)
    assert isinstance(a.error, RuntimeError)
    assert not a.pending()


def test_continue_mode_processes_actions_queued_after_pre_start_failure():
    failing_executor = DeferredFailingExecutor()
    a = agent.Agent(0, error_mode="continue")
    with ThreadPoolExecutor(max_workers=1) as executor:
        a.submit(failing_executor, lambda state: state + 1)
        a.submit(executor, lambda state: state + 1)
        failing_executor.fail()

        assert a.await_completion(timeout=2)

    assert a.deref() == 1
    assert isinstance(a.error, RuntimeError)
    assert not a.pending()


def test_raising_error_handler_still_observes_a_queued_executor_failure():
    def action_that_fails(_state):
        raise ValueError("action failed")

    def error_handler(_agent, _error):
        raise RuntimeError("error handler failed")

    a = agent.Agent(0, error_mode="continue", error_handler=error_handler)
    with ThreadPoolExecutor(max_workers=1) as executor:
        a.submit(executor, action_that_fails)
        a.submit(FailingExecutor(), lambda state: state + 1)
        a.submit(executor, lambda state: state + 1)

        assert a.await_completion(timeout=2)

    assert a.deref() == 1
    assert isinstance(a.error, RuntimeError)
    assert not a.pending()


def test_process_executor_submission_failure_does_not_wedge_an_agent_queue():
    a = agent.Agent(0)
    with futures.ProcessPoolExecutor(max_workers=1) as executor:
        assert a.submit(executor, lambda state: state + 1) is a
        assert a.await_completion(timeout=5)

    assert a.error is not None
    assert not a.pending()


@pytest.mark.parametrize("error_mode", ["fail", "continue"])
def test_submit_failure_preserves_or_continues_queued_actions(error_mode):
    action_started = threading.Event()
    release_action = threading.Event()

    def blocking_action(state):
        action_started.set()
        assert release_action.wait(timeout=2)
        return state + 1

    rejected_executor = ThreadPoolExecutor(max_workers=1)
    rejected_executor.shutdown()
    a = agent.Agent(0, error_mode=error_mode)
    with ThreadPoolExecutor(max_workers=1) as executor:
        a.submit(executor, blocking_action)
        assert action_started.wait(timeout=2)
        a.submit(rejected_executor, lambda state: state + 1)
        a.submit(executor, lambda state: state + 1)
        release_action.set()

        assert a.await_completion(timeout=2)
        if error_mode == "fail":
            a.restart()
            assert a.await_completion(timeout=2)
            assert a.error is None
        else:
            assert isinstance(a.error, RuntimeError)

    assert a.deref() == 2


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


def test_failure_blocking_wait_returns_after_restart():
    action_started = threading.Event()
    release_action = threading.Event()
    wait_finished = threading.Event()

    def action_that_fails(_state):
        action_started.set()
        assert release_action.wait(timeout=2)
        raise ValueError("action failed")

    a = agent.Agent(0)
    with ThreadPoolExecutor(max_workers=1) as executor:
        a.submit(executor, action_that_fails)
        assert action_started.wait(timeout=2)
        release_action.set()
        assert a.await_completion(timeout=2)

        waiter = threading.Thread(
            target=lambda: a.await_completion(wait_on_failure=True)
            and wait_finished.set()
        )
        waiter.start()
        assert not wait_finished.wait(timeout=0.1)

        a.restart()
        assert wait_finished.wait(timeout=2)
        waiter.join(timeout=2)

    assert not waiter.is_alive()


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
