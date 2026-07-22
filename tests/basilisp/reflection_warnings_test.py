import logging
from concurrent.futures import ThreadPoolExecutor

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from basilisp.lang import compiler
from basilisp.lang import map as lmap
from basilisp.lang import reader, runtime
from basilisp.lang import symbol as sym
from basilisp.lang.compiler import analyzer, nodes
from tests.basilisp.helpers import CompileFn


@pytest.fixture
def test_ns() -> str:
    return "reflection-warnings-test"


@pytest.fixture
def compiler_file_path() -> str:
    return "<Reflection Warnings Test>"


def _warn_on_reflection_var() -> runtime.Var:
    var = runtime.Var.find(runtime.WARN_ON_REFLECTION_VAR_SYM)
    assert var is not None
    return var


def test_warn_on_reflection_var_is_dynamic_and_defaults_false(lcompile: CompileFn):
    var = _warn_on_reflection_var()
    assert var.dynamic
    assert var.value is False
    assert lcompile("*warn-on-reflection*") is False
    assert (
        lcompile("(binding [*warn-on-reflection* true] *warn-on-reflection*)") is True
    )
    assert lcompile("*warn-on-reflection*") is False


def test_dynamic_host_calls_and_fields_warn_only_when_enabled(
    lcompile: CompileFn, caplog: pytest.LogCaptureFixture
):
    caplog.set_level(logging.WARNING, logger="basilisp.lang.compiler.analyzer")
    assert "ABC" == lcompile(
        '(binding [*warn-on-reflection* true] (eval \'(. "abc" upper)))'
    )
    assert any(
        "dynamic Python method lookup for 'upper'" in message
        for _, _, message in caplog.record_tuples
    )

    caplog.clear()
    assert "ABC" == lcompile(
        '(binding [*warn-on-reflection* true] (eval \'(. python/str upper "abc")))'
    )
    assert not any(
        logger_name == "basilisp.lang.compiler.analyzer"
        and "reflection warning" in message
        for logger_name, _, message in caplog.record_tuples
    )

    caplog.clear()
    assert callable(
        lcompile('(binding [*warn-on-reflection* true] (eval \'(.-upper "abc")))')
    )
    assert any(
        "dynamic Python field lookup for 'upper'" in message
        for _, _, message in caplog.record_tuples
    )


def test_warn_on_reflection_is_captured_when_context_is_created():
    var = _warn_on_reflection_var()
    with runtime.bindings(lmap.map({var: True})):
        enabled = compiler.CompilerContext("<reflection-enabled>").analyzer_context
    disabled = compiler.CompilerContext("<reflection-disabled>").analyzer_context
    assert enabled.warn_on_reflection is True
    assert disabled.warn_on_reflection is False


def test_static_member_probe_never_executes_descriptors(
    caplog: pytest.LogCaptureFixture,
):
    class ExplosiveDescriptor:
        def __get__(self, instance, owner):
            raise AssertionError("reflection diagnostic executed a descriptor")

    class StaticTarget:
        member = ExplosiveDescriptor()

    caplog.set_level(logging.WARNING, logger="basilisp.lang.compiler.analyzer")
    var = _warn_on_reflection_var()
    with runtime.bindings(lmap.map({var: True})):
        ctx = compiler.CompilerContext("<static-descriptor>").analyzer_context
        target = nodes.MaybeClass(
            form=sym.symbol("StaticTarget"),
            class_="StaticTarget",
            target=StaticTarget,
            env=ctx.get_node_env(),
        )
        analyzer._warn_dynamic_host_access(ctx, target, "member", "field")
    assert not caplog.record_tuples


@given(name=st.from_regex(r"[a-z][a-z0-9_]{0,20}", fullmatch=True))
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_reflection_warning_fuzzes_dynamic_member_names(
    name: str, caplog: pytest.LogCaptureFixture
):
    caplog.set_level(logging.WARNING, logger="basilisp.lang.compiler.analyzer")
    caplog.clear()
    form = next(reader.read_str(f'(. "value" {name})'))
    var = _warn_on_reflection_var()
    with runtime.bindings(lmap.map({var: True})):
        ctx = compiler.CompilerContext("<reflection-fuzz>").analyzer_context
        compiler.analyze_form(ctx, form)
    assert any(
        f"dynamic Python method lookup for '{name}'" in message
        for _, _, message in caplog.record_tuples
    )


def test_warn_on_reflection_bindings_are_thread_local_and_restore_root():
    var = _warn_on_reflection_var()

    def observe(value: bool) -> tuple[bool, bool, bool]:
        before = compiler.CompilerContext(
            "<before>"
        ).analyzer_context.warn_on_reflection
        with runtime.bindings(lmap.map({var: value})):
            bound = compiler.CompilerContext(
                "<bound>"
            ).analyzer_context.warn_on_reflection
        after = compiler.CompilerContext("<after>").analyzer_context.warn_on_reflection
        return before, bound, after

    values = [index % 2 == 0 for index in range(256)]
    with ThreadPoolExecutor(max_workers=16) as pool:
        observed = list(pool.map(observe, values))
    assert all(
        (False, value, False) == result for value, result in zip(values, observed)
    )
