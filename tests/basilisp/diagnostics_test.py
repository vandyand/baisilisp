from __future__ import annotations

import builtins

from hypothesis import given
from hypothesis import strategies as st

from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap
from basilisp.lang.compiler.exception import CompilerException, CompilerPhase
from basilisp.lang.diagnostics import exception_data
from basilisp.lang.exception import ExceptionInfo, print_exception
from basilisp.lang import reader


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


def test_print_exception_appends_the_normalized_diagnostic(capsys) -> None:
    error = RuntimeError("diagnostic output")

    print_exception(error)

    rendered = capsys.readouterr().err
    assert "RuntimeError: diagnostic output" in rendered
    assert "Basilisp diagnostic:" in rendered
    assert ':type "RuntimeError"' in rendered
    assert ':class "builtins.RuntimeError"' in rendered
    assert ':message "diagnostic output"' in rendered


def test_print_exception_keeps_compiler_cause_and_source_data(capsys) -> None:
    error = CompilerException(
        "unable to compile",
        CompilerPhase.ANALYZING,
        "diagnostic-test.lpy",
    )
    error.__cause__ = ValueError("nested cause")

    print_exception(error)

    rendered = capsys.readouterr().err
    assert "Basilisp diagnostic:" in rendered
    assert ':type "CompilerException"' in rendered
    assert ":phase :analyzing" in rendered
    assert ':source {:file "diagnostic-test.lpy"}' in rendered
    assert ':type "ValueError"' in rendered


def test_exception_data_exposes_reader_syntax_error_source() -> None:
    error = reader.SyntaxError(
        "bad reader form", line=12, col=5, filename="diagnostic-reader.lpy"
    )

    diagnostic = exception_data(error, phase=kw.keyword("read-source"))

    assert diagnostic.val_at(kw.keyword("phase")) == kw.keyword("read-source")
    assert diagnostic.val_at(kw.keyword("type")) == "SyntaxError"
    source = diagnostic.val_at(kw.keyword("source"))
    assert source.val_at(kw.keyword("file")) == "diagnostic-reader.lpy"
    assert source.val_at(kw.keyword("line")) == 12
    assert source.val_at(kw.keyword("col")) == 5


def test_exception_data_preserves_nested_reader_source() -> None:
    error = RuntimeError("outer execution failure")
    error.__cause__ = reader.SyntaxError(
        "bad nested reader form", line=4, col=2, filename="nested-reader.lpy"
    )

    diagnostic = exception_data(error)

    nested = diagnostic.val_at(kw.keyword("causes"))[0]
    source = nested.val_at(kw.keyword("source"))
    assert nested.val_at(kw.keyword("type")) == "SyntaxError"
    assert source.val_at(kw.keyword("file")) == "nested-reader.lpy"
    assert source.val_at(kw.keyword("line")) == 4
    assert source.val_at(kw.keyword("col")) == 2


def test_exception_data_exposes_python_syntax_error_source() -> None:
    error = builtins.SyntaxError(
        "invalid syntax",
        ("diagnostic-python.py", 3, 7, "bad code", 3, 10),
    )

    diagnostic = exception_data(error)

    source = diagnostic.val_at(kw.keyword("source"))
    assert source.val_at(kw.keyword("file")) == "diagnostic-python.py"
    assert source.val_at(kw.keyword("line")) == 3
    assert source.val_at(kw.keyword("col")) == 7
    assert source.val_at(kw.keyword("end-line")) == 3
    assert source.val_at(kw.keyword("end-col")) == 10


@given(
    line=st.integers(min_value=1, max_value=100_000),
    col=st.integers(min_value=0, max_value=10_000),
)
def test_reader_syntax_error_source_diagnostics_fuzz(line: int, col: int) -> None:
    error = reader.SyntaxError("generated reader failure", line=line, col=col)

    source = exception_data(error).val_at(kw.keyword("source"))

    assert source.val_at(kw.keyword("line")) == line
    assert source.val_at(kw.keyword("col")) == col
    assert source.val_at(kw.keyword("file")) is None
