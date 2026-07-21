from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from basilisp.contrib import repl_session
from basilisp.lang import compiler
from basilisp.lang import keyword as kw
from basilisp.lang import reader, runtime
from basilisp.lang import symbol as sym


def _evaluate(
    session: repl_session.ReplSession,
    source: str,
    events: list[tuple[str, str]],
):
    form = next(reader.read_str(source))
    return repl_session.evaluate_form(
        session,
        form,
        context=compiler.CompilerContext("<repl session test>"),
        emit=lambda tag, value: events.append((tag, value)),
        stdin=None,
    )


def test_repl_session_keeps_history_namespace_and_stream_events():
    session_name = sym.symbol("tests.repl-session")
    child_name = sym.symbol("tests.repl-session-child")
    events: list[tuple[str, str]] = []
    session = repl_session.ReplSession.create(session_name)
    try:
        first = _evaluate(session, '(println "hello")', events)
        assert first.value is None
        assert events == [("out", "hello"), ("out", os.linesep)]

        second = _evaluate(session, "[*1 *2 *3]", events)
        assert list(second.value) == [None, None, None]

        ns_change = _evaluate(session, "(ns tests.repl-session-child)", events)
        assert ns_change.value is None
        assert session.namespace.name == child_name.name
    finally:
        runtime.Namespace.remove(child_name)
        runtime.Namespace.remove(session_name)


def test_repl_session_binds_current_repl_var_and_restores_it():
    session_name = sym.symbol("tests.repl-session-context")
    events: list[tuple[str, str]] = []
    repl_var = runtime.Var.find(sym.symbol(runtime.REPL_VAR_NAME, ns="basilisp.core"))
    assert repl_var is not None
    session = repl_session.ReplSession.create(session_name)
    try:
        assert _evaluate(session, "*repl*", events).value is True
        assert (
            _evaluate(session, "(binding [*repl* false] *repl*)", events).value is False
        )
        assert _evaluate(session, "*repl*", events).value is True
        assert repl_var.value is False
    finally:
        runtime.Namespace.remove(session_name)


@settings(
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(st.lists(st.booleans(), min_size=1, max_size=32))
def test_repl_session_fuzzes_nested_repl_bindings(values):
    session_name = sym.symbol("tests.repl-session-context-fuzz")
    events: list[tuple[str, str]] = []
    session = repl_session.ReplSession.create(session_name)
    try:
        for value in values:
            literal = "true" if value else "false"
            result = _evaluate(
                session,
                f"(binding [*repl* {literal}] [*repl*])",
                events,
            )
            assert list(result.value) == [value]
            assert _evaluate(session, "*repl*", events).value is True
    finally:
        runtime.Namespace.remove(session_name)


def test_repl_sessions_keep_current_repl_var_thread_local():
    sessions = [
        repl_session.ReplSession.create(sym.symbol(f"tests.repl-session-thread-{i}"))
        for i in range(8)
    ]
    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(
                executor.map(
                    lambda session: _evaluate(session, "*repl*", []).value,
                    sessions,
                )
            )
        assert results == [True] * len(sessions)
        repl_var = runtime.Var.find(
            sym.symbol(runtime.REPL_VAR_NAME, ns="basilisp.core")
        )
        assert repl_var is not None
        assert repl_var.value is False
    finally:
        for session in sessions:
            runtime.Namespace.remove(session.namespace.name)


def test_repl_session_retains_exceptions_and_stops_on_repl_quit():
    session_name = sym.symbol("tests.repl-session-errors")
    events: list[tuple[str, str]] = []
    session = repl_session.ReplSession.create(session_name)
    try:
        failed = _evaluate(session, "(/ 1 0)", events)
        assert failed.error is not None
        assert session.error is failed.error

        quit_result = _evaluate(session, ":repl/quit", events)
        assert quit_result.quit
    finally:
        runtime.Namespace.remove(session_name)


def test_repl_session_can_leave_history_and_quit_to_a_batch_transport():
    session_name = sym.symbol("tests.repl-session-batch")
    events: list[tuple[str, str]] = []
    session = repl_session.ReplSession.create(session_name)
    try:
        result = repl_session.evaluate_form(
            session,
            next(reader.read_str(":repl/quit")),
            context=compiler.CompilerContext("<repl session test>"),
            emit=lambda tag, value: events.append((tag, value)),
            stdin=None,
            record_history=False,
            stop_on_quit=False,
        )

        assert result.value == kw.keyword("quit", ns="repl")
        assert not result.quit
        assert session.one is None
        repl_session.record_result(session, result.value)
        assert session.one == result.value
    finally:
        runtime.Namespace.remove(session_name)
