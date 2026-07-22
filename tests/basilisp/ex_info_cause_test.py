from __future__ import annotations

import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap
from basilisp.lang import runtime
from basilisp.lang import symbol as sym
from basilisp.lang.exception import ExceptionInfo
from basilisp.lang.runtime import RuntimeException
from tests.basilisp.helpers import CompileFn


@pytest.fixture
def test_ns() -> str:
    return "ex-info-cause-test"


@pytest.fixture
def compiler_file_path() -> str:
    return "<ex-info cause test>"


def _core_fn(name: str):
    var = runtime.Var.find(sym.symbol(name, ns="basilisp.core"))
    assert var is not None, name
    return var.value


def test_ex_info_three_arity_preserves_an_explicit_python_cause(
    lcompile: CompileFn,
):
    outer = lcompile(
        '(let [cause (ex-info "inner" {:layer :inner})] '
        '(ex-info "outer" {:layer :outer} cause))'
    )
    assert isinstance(outer, ExceptionInfo)
    assert outer.message == "outer"
    assert outer.data == lmap.map({kw.keyword("layer"): kw.keyword("outer")})
    cause = _core_fn("ex-cause")(outer)
    assert isinstance(cause, ExceptionInfo)
    assert cause.message == "inner"
    assert cause.data == lmap.map({kw.keyword("layer"): kw.keyword("inner")})
    assert outer.__cause__ is cause
    assert outer.__suppress_context__ is True


def test_ex_info_two_arity_keeps_a_nil_cause_and_validates_arity(lcompile: CompileFn):
    two_arity = lcompile('(ex-info "ordinary" {:kind :two})')
    assert _core_fn("ex-cause")(two_arity) is None
    with pytest.raises(RuntimeException):
        lcompile('(ex-info "too few")')
    with pytest.raises(RuntimeException):
        lcompile('(ex-info "too many" {} nil :extra)')


def test_ex_info_cause_integrates_with_python_tracebacks_and_throwable_map():
    root = ValueError("root cause")
    outer = _core_fn("ex-info")(
        "wrapper", lmap.map({kw.keyword("kind"): kw.keyword("outer")}), root
    )

    try:
        raise outer
    except ExceptionInfo as caught:
        assert _core_fn("ex-cause")(caught) is root
        rendered = "".join(traceback.format_exception(caught))
        assert "root cause" in rendered
        assert "wrapper" in rendered
        assert "direct cause" in rendered
        mapped = _core_fn("Throwable->map")(caught)

    via = mapped[kw.keyword("via")]
    assert len(via) == 2
    assert via[0][kw.keyword("message")] == "wrapper"
    assert via[0][kw.keyword("data")] == lmap.map(
        {kw.keyword("kind"): kw.keyword("outer")}
    )
    assert via[1][kw.keyword("message")] == "root cause"
    assert kw.keyword("at") not in via[1]


def test_ex_info_rejects_non_exception_causes(lcompile: CompileFn):
    with pytest.raises(TypeError, match="exception cause"):
        lcompile('(ex-info "invalid" {} :not-an-exception)')


def test_ex_info_preserves_any_python_base_exception_cause():
    root = KeyboardInterrupt("interrupt")
    outer = _core_fn("ex-info")("wrapper", lmap.EMPTY, root)
    assert _core_fn("ex-cause")(outer) is root
    assert _core_fn("ex-message")(root) == "interrupt"


def test_throwable_to_map_bounds_a_manually_cyclic_explicit_cause_chain():
    ex_info = _core_fn("ex-info")
    first = ex_info("first", lmap.EMPTY)
    second = ex_info("second", lmap.EMPTY, first)
    first.__cause__ = second

    mapped = _core_fn("Throwable->map")(first)
    assert [entry[kw.keyword("message")] for entry in mapped[kw.keyword("via")]] == [
        "first",
        "second",
    ]


@given(
    messages=st.lists(st.text(min_size=1, max_size=30), min_size=1, max_size=12),
    values=st.lists(
        st.one_of(st.integers(-10_000, 10_000), st.text(max_size=30), st.none()),
        min_size=1,
        max_size=12,
    ),
)
@settings(max_examples=150, deadline=None)
def test_ex_info_fuzzes_explicit_cause_chains(messages: list[str], values: list[Any]):
    ex_info = _core_fn("ex-info")
    ex_cause = _core_fn("ex-cause")
    cause: BaseException = ValueError("terminal")
    expected = [cause]
    for index, message in enumerate(messages):
        data = lmap.map(
            {
                kw.keyword("index"): index,
                kw.keyword("value"): values[index % len(values)],
            }
        )
        cause = ex_info(message, data, cause)
        expected.append(cause)

    observed: list[BaseException] = []
    current: BaseException | None = cause
    while current is not None:
        observed.append(current)
        current = ex_cause(current)

    assert observed == list(reversed(expected))
    for index, exception in enumerate(observed[:-1]):
        assert isinstance(exception, ExceptionInfo)
        assert exception.data.val_at(kw.keyword("index")) == len(messages) - index - 1


def test_ex_info_causes_are_isolated_across_threads():
    ex_info = _core_fn("ex-info")
    ex_cause = _core_fn("ex-cause")

    def create(index: int) -> tuple[int, BaseException, BaseException]:
        root = RuntimeError(f"root-{index}")
        outer = ex_info(f"outer-{index}", lmap.map({kw.keyword("index"): index}), root)
        return index, outer, ex_cause(outer)

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(create, range(256)))

    for index, outer, cause in results:
        assert cause is outer.__cause__
        assert str(cause) == f"root-{index}"
        assert outer.data.val_at(kw.keyword("index")) == index
