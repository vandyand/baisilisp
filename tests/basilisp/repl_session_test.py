from __future__ import annotations

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
        assert events == [("out", "hello"), ("out", "\n")]

        second = _evaluate(session, "[*1 *2 *3]", events)
        assert list(second.value) == [None, None, None]

        ns_change = _evaluate(session, "(ns tests.repl-session-child)", events)
        assert ns_change.value is None
        assert session.namespace.name == child_name.name
    finally:
        runtime.Namespace.remove(child_name)
        runtime.Namespace.remove(session_name)


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
