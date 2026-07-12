from __future__ import annotations

from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap
from basilisp.lang.compiler.exception import CompilerException, CompilerPhase
from basilisp.lang.diagnostics import exception_data
from basilisp.lang.exception import ExceptionInfo


def test_exception_data_keeps_operation_and_compiler_context() -> None:
    cause = ExceptionInfo("invalid input", lmap.map({kw.keyword("field"): "name"}))
    error = CompilerException(
        "unable to compile",
        CompilerPhase.ANALYZING,
        "diagnostic-test.lpy",
    )
    error.__cause__ = cause

    diagnostic = exception_data(error, phase=kw.keyword("execution"))

    assert diagnostic.val_at(kw.keyword("phase")) == kw.keyword("execution")
    assert diagnostic.val_at(kw.keyword("type")) == "CompilerException"
    assert diagnostic.val_at(kw.keyword("class")) == (
        "basilisp.lang.compiler.exception.CompilerException"
    )
    assert diagnostic.val_at(kw.keyword("data")).val_at(
        kw.keyword("phase")
    ) == kw.keyword("analyzing")
    assert diagnostic.val_at(kw.keyword("source")).val_at(kw.keyword("file")) == (
        "diagnostic-test.lpy"
    )

    causes = diagnostic.val_at(kw.keyword("causes"))
    assert len(causes) == 1
    nested = causes[0]
    assert nested.val_at(kw.keyword("type")) == "ExceptionInfo"
    assert nested.val_at(kw.keyword("data")).val_at(kw.keyword("field")) == "name"


def test_exception_data_uses_unsuppressed_context_and_avoids_cycles() -> None:
    context = ValueError("inner")
    error = RuntimeError("outer")
    error.__context__ = context
    context.__context__ = error

    diagnostic = exception_data(error)

    causes = diagnostic.val_at(kw.keyword("causes"))
    assert len(causes) == 1
    nested = causes[0]
    assert nested.val_at(kw.keyword("type")) == "ValueError"
    cyclic = nested.val_at(kw.keyword("causes"))[0]
    assert cyclic.val_at(kw.keyword("message")) == "cyclic exception cause"
