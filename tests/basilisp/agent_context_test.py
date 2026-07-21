from __future__ import annotations

import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from basilisp.lang import agent as agent_module
from basilisp.lang import runtime
from basilisp.lang import symbol as sym


def _core_var(core_ns, name: str):
    var = core_ns.find(sym.symbol(name))
    assert var is not None
    return var


@settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(st.lists(st.integers(min_value=0, max_value=4), min_size=1, max_size=120))
def test_agent_context_tracks_each_target_under_parallel_fuzzing(core_ns, targets):
    current_agent_var = _core_var(core_ns, "*agent*")
    new_agent = _core_var(core_ns, "agent")
    send_via = _core_var(core_ns, "send-via")
    agents = [new_agent.value(0) for _ in range(5)]
    observed = []
    observed_lock = threading.Lock()

    def action(state, target):
        assert current_agent_var.value is target
        assert agent_module.current_agent() is target
        with observed_lock:
            observed.append(target)
        return state + 1

    with ThreadPoolExecutor(max_workers=5) as executor:
        for target_index in targets:
            target = agents[target_index]
            assert send_via.value(executor, target, action, target) is target
        for target in agents:
            assert target.await_completion(timeout=5)

    expected = Counter(targets)
    assert Counter(observed) == Counter(
        target for index, target in enumerate(agents) for _ in range(expected[index])
    )
    assert [target.deref() for target in agents] == [
        expected[index] for index in range(5)
    ]
    assert current_agent_var.value is None
    assert agent_module.current_agent() is None


def test_agent_context_overrides_caller_binding_and_unwinds_after_failure(core_ns):
    current_agent_var = _core_var(core_ns, "*agent*")
    new_agent = _core_var(core_ns, "agent")
    send_via = _core_var(core_ns, "send-via")
    target = new_agent.value(0)
    observed = []

    def failing_action(_state):
        observed.append(current_agent_var.value is target)
        raise ValueError("agent action failure")

    with ThreadPoolExecutor(max_workers=1) as executor:
        with runtime.bindings({current_agent_var: "caller"}):
            assert send_via.value(executor, target, failing_action) is target
            assert current_agent_var.value == "caller"
        assert target.await_completion(timeout=2)
        # Re-use the exact worker after the failure: no dynamic frame may leak.
        assert (
            executor.submit(lambda: current_agent_var.value).result(timeout=2) is None
        )

    assert observed == [True]
    assert isinstance(target.error, ValueError)
    assert current_agent_var.value is None
