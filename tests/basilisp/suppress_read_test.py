from concurrent.futures import ThreadPoolExecutor

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap
from basilisp.lang import symbol as sym
from basilisp.lang import vector as vec
from basilisp.lang.tagged import TaggedLiteral
from tests.basilisp.helpers import CompileFn


@pytest.fixture
def test_ns() -> str:
    return "basilisp.suppress_read_test"


@pytest.fixture
def compiler_file_path() -> str:
    return "<Suppress Read Test>"


def _tag_symbol(tag: str) -> sym.Symbol:
    namespace, separator, name = tag.partition("/")
    return sym.symbol(
        name if separator else namespace, ns=namespace if separator else None
    )


@pytest.fixture
def read_tagged(lcompile: CompileFn):
    return lcompile("""
        (defn read-tagged-with-suppression [source suppress?]
          (binding [*suppress-read* suppress?]
            (try
              (read-string source)
              (catch basilisp.lang.reader/SyntaxError _
                :reader-error))))
        read-tagged-with-suppression
        """)


@given(
    tag=st.sampled_from(["local", "demo/tag", "vendor/thing"]),
    values=st.lists(
        st.integers(min_value=-(1 << 31), max_value=(1 << 31) - 1), max_size=30
    ),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_suppress_read_fuzzes_tagged_literal_data(
    read_tagged, tag: str, values: list[int]
):
    source = f"#{tag} [{ ' '.join(str(value) for value in values)}]"
    expected = TaggedLiteral(_tag_symbol(tag), vec.vector(values))

    assert read_tagged(source, False) == kw.keyword("reader-error")
    assert read_tagged(source, True) == expected


def test_suppress_read_is_thread_local(read_tagged):
    source = "#demo/tag {:a [1 2 3]}"

    def read_with(suppressed: bool):
        return read_tagged(source, suppressed)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(read_with, [False, True] * 64))

    assert all(result == kw.keyword("reader-error") for result in results[::2])
    assert all(
        result
        == TaggedLiteral(
            _tag_symbol("demo/tag"),
            lmap.map({kw.keyword("a"): vec.vector((1, 2, 3))}),
        )
        for result in results[1::2]
    )
