from concurrent.futures import ThreadPoolExecutor

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from basilisp.lang import compiler
from basilisp.lang import map as lmap
from basilisp.lang import reader, runtime
from basilisp.lang import symbol as sym
from basilisp.lang.compiler.exception import CompilerException
from tests.basilisp.helpers import CompileFn


@pytest.fixture
def test_ns() -> str:
    return "unresolved-vars-test"


@pytest.fixture
def compiler_file_path() -> str:
    return "<Unresolved Vars Test>"


def _allow_unresolved_var() -> runtime.Var:
    var = runtime.Var.find(runtime.ALLOW_UNRESOLVED_VARS_VAR_SYM)
    assert var is not None
    return var


def test_allow_unresolved_vars_has_clojure_var_shape(lcompile: CompileFn):
    var = _allow_unresolved_var()

    assert var.dynamic
    assert var.meta is None
    assert var.value is False
    assert lcompile("*allow-unresolved-vars*") is False


def test_allow_unresolved_vars_defers_an_eval_error(lcompile: CompileFn):
    with pytest.raises(CompilerException):
        lcompile("(eval 'unresolved-symbol)")

    with pytest.raises(
        runtime.RuntimeException, match="UnresolvedVarExpr cannot be evalled"
    ):
        lcompile("(binding [*allow-unresolved-vars* true] (eval 'unresolved-symbol))")

    assert lcompile("*allow-unresolved-vars*") is False


def test_allow_unresolved_vars_is_captured_when_a_compiler_context_is_created():
    var = _allow_unresolved_var()
    form = next(reader.read_str("unresolved-symbol"))
    ns = runtime.Namespace.get_or_create(sym.symbol("unresolved-vars-context-test"))
    try:
        with runtime.bindings(lmap.map({var: True})):
            enabled_ctx = compiler.CompilerContext("<enabled>")

        assert enabled_ctx.analyzer_context.should_allow_unresolved_symbols
        assert enabled_ctx.analyzer_context.should_raise_unresolved_var
        with pytest.raises(
            runtime.RuntimeException, match="UnresolvedVarExpr cannot be evalled"
        ):
            compiler.compile_and_exec_form(form, enabled_ctx, ns)

        disabled_ctx = compiler.CompilerContext("<disabled>")
        with pytest.raises(CompilerException):
            compiler.compile_and_exec_form(form, disabled_ctx, ns)
    finally:
        runtime.Namespace.remove(sym.symbol("unresolved-vars-context-test"))


def test_allow_unresolved_vars_does_not_change_macroexpansion(lcompile: CompileFn):
    assert "(unresolved-macro 1)" == lcompile(
        "(binding [*allow-unresolved-vars* true] "
        "(pr-str (macroexpand '(unresolved-macro 1))))"
    )


@given(name=st.from_regex(r"unresolved_[a-z][a-z0-9_]{0,20}", fullmatch=True))
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_allow_unresolved_vars_fuzzes_unresolved_symbols(
    name: str, lcompile: CompileFn
):
    with pytest.raises(
        runtime.RuntimeException, match="UnresolvedVarExpr cannot be evalled"
    ):
        lcompile(f"(binding [*allow-unresolved-vars* true] (eval '{name}))")


@pytest.mark.parametrize("name", ["missing-ns/missing", "missing.namespace/value"])
def test_allow_unresolved_vars_defers_qualified_symbols(name: str, lcompile: CompileFn):
    with pytest.raises(
        runtime.RuntimeException, match="UnresolvedVarExpr cannot be evalled"
    ):
        lcompile(f"(binding [*allow-unresolved-vars* true] (eval '{name}))")


def test_allow_unresolved_vars_bindings_are_thread_local_and_restore_the_root():
    var = _allow_unresolved_var()

    def observe(value: bool) -> tuple[bool, bool, bool, bool]:
        before = compiler.CompilerContext("<before>").analyzer_context
        with runtime.bindings(lmap.map({var: value})):
            bound = compiler.CompilerContext("<bound>").analyzer_context
            result = (
                bound.should_allow_unresolved_symbols,
                bound.should_raise_unresolved_var,
            )
        after = compiler.CompilerContext("<after>").analyzer_context
        return (
            before.should_allow_unresolved_symbols,
            *result,
            after.should_allow_unresolved_symbols,
        )

    values = [index % 2 == 0 for index in range(256)]
    with ThreadPoolExecutor(max_workers=16) as pool:
        observed = list(pool.map(observe, values))

    for value, (before, allowed, raises, after) in zip(values, observed):
        assert (False, value, value, False) == (before, allowed, raises, after)
    assert var.value is False
