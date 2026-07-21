from concurrent.futures import ThreadPoolExecutor
from io import StringIO

import pytest
from hypothesis import given
from hypothesis import strategies as st

from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap
from basilisp.lang import runtime
from basilisp.lang import symbol as sym
from basilisp.lang import vector as vec


def _core_fn(name: str):
    core = runtime.Namespace.get_or_create(runtime.CORE_NS_SYM)
    return core.find(sym.symbol(name)).value


@given(
    value=st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(),
        st.builds(
            kw.keyword,
            st.text(min_size=1, alphabet=st.characters(blacklist_characters="/")),
        ),
    )
)
def test_print_simple_matches_basilisp_str_for_metadata_free_values(value):
    writer = StringIO()

    _core_fn("print-simple")(value, writer)

    assert writer.getvalue() == ("" if value is None else runtime.lstr(value))


@given(values=st.lists(st.integers(), max_size=32))
def test_print_simple_matches_clojure_metadata_rendering_for_vectors(values):
    core = runtime.Namespace.get_or_create(runtime.CORE_NS_SYM)
    value = vec.vector(
        values,
        meta=lmap.map({kw.keyword("tag"): sym.symbol("kind")}),
    )
    writer = StringIO()

    with runtime.bindings(
        {
            core.find(sym.symbol("*print-meta*")): True,
            core.find(sym.symbol("*print-readably*")): True,
        }
    ):
        _core_fn("print-simple")(value, writer)

    assert writer.getvalue() == f"^kind ^kind {runtime.lstr(value)}"


def test_print_ctor_is_reentrant_under_parallel_calls():
    print_ctor = _core_fn("print-ctor")

    def render(value: int) -> str:
        writer = StringIO()
        print_ctor(
            value,
            lambda object_, callback_writer: callback_writer.write(str(object_)),
            writer,
        )
        return writer.getvalue()

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(render, range(256)))

    assert results == [f"#=(builtins.int. {value})" for value in range(256)]


def test_print_ctor_preserves_callback_exceptions_after_writing_prefix():
    writer = StringIO()

    def fail_callback(_object, _writer):
        raise RuntimeError("callback failed")

    with pytest.raises(RuntimeError, match="callback failed"):
        _core_fn("print-ctor")(1, fail_callback, writer)

    assert writer.getvalue() == "#=(builtins.int. "
