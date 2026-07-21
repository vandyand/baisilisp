import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from basilisp.lang import vector as vec


@pytest.fixture
def test_ns() -> str:
    return "basilisp.definline_test"


@pytest.fixture
def compiler_file_path() -> str:
    return "<Definline Test>"


@settings(
    max_examples=45,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    offset=st.integers(min_value=-(10**9), max_value=10**9),
    values=st.lists(
        st.integers(min_value=-(10**9), max_value=10**9), min_size=1, max_size=16
    ),
)
def test_definline_fuzzes_generated_fixed_arity_expansions(lcompile, offset, values):
    calls = " ".join(f"(fuzz-inline {value})" for value in values)
    result = lcompile(f"""
        (definline fuzz-inline [x] `(+ {offset} ~x))
        [{calls}]
        """)

    assert result == vec.v(*(offset + value for value in values))
