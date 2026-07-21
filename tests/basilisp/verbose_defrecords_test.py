from concurrent.futures import ThreadPoolExecutor

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from basilisp.lang import map as lmap
from basilisp.lang import runtime
from basilisp.lang import symbol as sym
from basilisp.lang.obj import lrepr
from tests.basilisp.helpers import CompileFn


@pytest.fixture
def test_ns() -> str:
    return "basilisp.verbose_defrecords_test"


@pytest.fixture
def compiler_file_path() -> str:
    return "<Verbose Defrecords Test>"


def _compile_renderer(lcompile: CompileFn):
    return lcompile("""
        (defrecord VerboseRecord [a b])
        (defn render-verbose-record [a b extra verbose?]
          (binding [*print-dup* true
                    *verbose-defrecords* verbose?]
            (pr-str (assoc (->VerboseRecord a b) :extra extra))))
        render-verbose-record
        """)


@pytest.fixture
def render_verbose_record(lcompile: CompileFn):
    return _compile_renderer(lcompile)


@given(
    a=st.integers(min_value=-(1 << 31), max_value=(1 << 31) - 1),
    b=st.integers(min_value=-(1 << 31), max_value=(1 << 31) - 1),
    extra=st.integers(min_value=-(1 << 31), max_value=(1 << 31) - 1),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_verbose_defrecords_fuzzes_generated_record_printing(
    render_verbose_record, a: int, b: int, extra: int
):
    compact = render_verbose_record(a, b, extra, False)
    verbose = render_verbose_record(a, b, extra, True)

    assert compact.endswith(f"[{a} {b} {extra}]")
    assert "{" not in compact
    assert "{" in verbose
    assert f":extra {extra}" in verbose


def test_verbose_defrecords_are_thread_local_and_restore_the_root_binding(
    lcompile: CompileFn,
):
    _compile_renderer(lcompile)
    record = lcompile("(assoc (->VerboseRecord 1 2) :extra 3)")
    verbose_var = runtime.resolve_var(
        sym.symbol("*verbose-defrecords*", ns="basilisp.core")
    )

    def render(verbose: bool) -> str:
        with runtime.bindings(lmap.map({verbose_var: verbose})):
            return lrepr(record, print_dup=True)

    with ThreadPoolExecutor(max_workers=8) as executor:
        rendered = list(executor.map(render, [False, True] * 64))

    compact = rendered[::2]
    verbose = rendered[1::2]
    assert all(value.endswith("[1 2 3]") and "{" not in value for value in compact)
    assert all("{" in value and ":extra 3" in value for value in verbose)
    assert verbose_var.value is False
