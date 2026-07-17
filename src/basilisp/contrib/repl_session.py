"""Stateful form evaluation shared by interactive Basilisp transports."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from basilisp.lang import compiler
from basilisp.lang import keyword as kw
from basilisp.lang import runtime
from basilisp.lang import symbol as sym

_CORE_NS = sym.symbol("basilisp.core")
_QUIT = kw.keyword("quit", ns="repl")


class _StreamEmitter:
    def __init__(self, emit: Callable[[str, str], None], tag: str) -> None:
        self._emit = emit
        self._tag = tag

    def flush(self) -> None:
        return None

    def write(self, value: str) -> int:
        self._emit(self._tag, value)
        return len(value)


@dataclass
class ReplSession:
    """Namespace and dynamic REPL history for an interactive evaluator."""

    namespace: runtime.Namespace
    one: Any = None
    two: Any = None
    three: Any = None
    error: BaseException | None = None

    @classmethod
    def create(cls, namespace: sym.Symbol) -> "ReplSession":
        """Create a namespace with Basilisp core referred into it."""
        eval_ns = runtime.Namespace.get_or_create(namespace)
        core_ns = runtime.Namespace.get(_CORE_NS)
        assert core_ns is not None, "basilisp.core must be initialized"
        eval_ns.refer_all(core_ns)
        return cls(eval_ns)


def create_session(namespace: sym.Symbol) -> ReplSession:
    """Create a session from Basilisp code without exposing Python class syntax."""
    return ReplSession.create(namespace)


@dataclass(frozen=True)
class Evaluation:
    """The outcome of compiling and evaluating one already-read form."""

    value: Any | None
    namespace: runtime.Namespace
    elapsed_ms: int | None
    error: BaseException | None
    quit: bool = False


def evaluate_form(
    session: ReplSession,
    form: Any,
    *,
    context: compiler.CompilerContext,
    emit: Callable[[str, str], None],
    stdin: Any,
    record_history: bool = True,
    stop_on_quit: bool = True,
) -> Evaluation:
    """Evaluate ``form`` and update ``session`` without choosing a transport format."""
    bindings = {
        _core_var("*ns*"): session.namespace,
        _core_var("*in*"): stdin,
        _core_var("*out*"): _StreamEmitter(emit, "out"),
        _core_var("*err*"): _StreamEmitter(emit, "err"),
        _core_var("*1"): session.one,
        _core_var("*2"): session.two,
        _core_var("*3"): session.three,
        _core_var("*e"): session.error,
    }
    with runtime.bindings(bindings):
        started = time.perf_counter_ns()
        try:
            value = compiler.compile_and_exec_form(form, context, session.namespace)
        except Exception as exc:
            session.namespace = runtime.get_current_ns()
            session.error = exc
            return Evaluation(None, session.namespace, None, exc)

        session.namespace = runtime.get_current_ns()
        if stop_on_quit and value == _QUIT:
            return Evaluation(value, session.namespace, None, None, quit=True)

        if record_history:
            session.three = session.two
            session.two = session.one
            session.one = value
        elapsed_ms = (time.perf_counter_ns() - started) // 1_000_000
        return Evaluation(value, session.namespace, elapsed_ms, None)


def record_result(session: ReplSession, value: Any) -> None:
    """Record a successful result when a transport uses batch history semantics."""
    session.three = session.two
    session.two = session.one
    session.one = value


def restore_session(
    namespace: runtime.Namespace,
    one: Any = None,
    two: Any = None,
    three: Any = None,
    error: BaseException | None = None,
) -> ReplSession:
    """Restore a transport-owned history into an evaluation session."""
    return ReplSession(namespace, one, two, three, error)


def _core_var(name: str) -> runtime.Var:
    var = runtime.Var.find(sym.symbol(name, ns=_CORE_NS.name))
    assert var is not None, f"missing dynamic core Var: {name}"
    return var
