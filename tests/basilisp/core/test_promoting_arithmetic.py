import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from basilisp.lang import runtime
from basilisp.lang import symbol as sym


def _core_fn(core_ns, name):
    var = core_ns.find(sym.symbol(name))
    assert var is not None
    return var.value


@pytest.mark.parametrize(
    ("operator", "promoting_operator", "identity"),
    [("+", "+'", 0), ("*", "*'", 1)],
)
def test_promoting_arithmetic_matches_basilisp_unbounded_arithmetic(
    core_ns, operator, promoting_operator, identity
):
    normal = _core_fn(core_ns, operator)
    promoting = _core_fn(core_ns, promoting_operator)

    assert promoting() == identity
    assert promoting(7) == normal(7)
    assert promoting(7, -3, 11, -19) == normal(7, -3, 11, -19)
    assert promoting(10**200, 10**180) == normal(10**200, 10**180)


def test_promoting_subtraction_matches_basilisp_unbounded_arithmetic(core_ns):
    normal = _core_fn(core_ns, "-")
    promoting = _core_fn(core_ns, "-'")

    assert promoting(7) == normal(7)
    assert promoting(7, -3, 11, -19) == normal(7, -3, 11, -19)
    assert promoting(10**200, 10**180, -(10**160)) == normal(
        10**200, 10**180, -(10**160)
    )


def _numbers_match(actual, expected):
    if actual == expected:
        return True
    if isinstance(actual, float) and isinstance(expected, float):
        return math.isnan(actual) and math.isnan(expected)
    if isinstance(actual, complex) and isinstance(expected, complex):
        return _numbers_match(actual.real, expected.real) and _numbers_match(
            actual.imag, expected.imag
        )
    return False


def _assert_promoting_arithmetic_matches_normal(normal, promoting, values):
    assert _numbers_match(promoting(*values), normal(*values))


@given(
    st.one_of(
        st.lists(st.integers(), max_size=80),
        st.lists(st.floats(allow_nan=False, allow_infinity=False), max_size=40),
        st.lists(
            st.decimals(allow_nan=False, allow_infinity=False, places=6), max_size=40
        ),
        st.lists(st.fractions(max_denominator=10_000), max_size=40),
        st.lists(
            st.complex_numbers(allow_nan=False, allow_infinity=False), max_size=40
        ),
    )
)
def _check_promoting_arithmetic_matches_normal(normal, promoting, values):
    _assert_promoting_arithmetic_matches_normal(normal, promoting, values)


@given(
    st.one_of(
        st.lists(st.integers(), min_size=1, max_size=80),
        st.lists(
            st.floats(allow_nan=False, allow_infinity=False), min_size=1, max_size=40
        ),
        st.lists(
            st.decimals(allow_nan=False, allow_infinity=False, places=6),
            min_size=1,
            max_size=40,
        ),
        st.lists(st.fractions(max_denominator=10_000), min_size=1, max_size=40),
        st.lists(
            st.complex_numbers(allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=40,
        ),
    )
)
def _check_promoting_subtraction_matches_normal(normal, promoting, values):
    _assert_promoting_arithmetic_matches_normal(normal, promoting, values)


@pytest.mark.parametrize(("operator", "promoting_operator"), [("+", "+'"), ("*", "*'")])
def test_promoting_arithmetic_matches_normal_for_random_numeric_sequences(
    core_ns, operator, promoting_operator
):
    _check_promoting_arithmetic_matches_normal(
        _core_fn(core_ns, operator), _core_fn(core_ns, promoting_operator)
    )


def test_promoting_subtraction_matches_normal_for_random_numeric_sequences(core_ns):
    _check_promoting_subtraction_matches_normal(
        _core_fn(core_ns, "-"), _core_fn(core_ns, "-'")
    )


@pytest.mark.parametrize("operator", ["+'", "-'", "*'"])
@pytest.mark.parametrize("value", [None, "1", [], {}, True, False])
def test_promoting_arithmetic_rejects_nonnumeric_values(core_ns, operator, value):
    promoting = _core_fn(core_ns, operator)

    with pytest.raises(TypeError):
        promoting(1, value)


@given(
    st.one_of(
        st.none(),
        st.booleans(),
        st.text(max_size=100),
        st.lists(st.integers(), max_size=20),
        st.dictionaries(st.text(max_size=12), st.integers(), max_size=20),
    )
)
def _check_promoting_arithmetic_rejects_generated_nonnumeric_values(promoting, value):
    with pytest.raises(TypeError):
        promoting(1, value)


@pytest.mark.parametrize("operator", ["+'", "-'", "*'"])
def test_promoting_arithmetic_rejects_generated_nonnumeric_values(core_ns, operator):
    _check_promoting_arithmetic_rejects_generated_nonnumeric_values(
        _core_fn(core_ns, operator)
    )


def test_promoting_subtraction_requires_at_least_one_argument(core_ns):
    with pytest.raises(runtime.RuntimeException):
        _core_fn(core_ns, "-'")()
