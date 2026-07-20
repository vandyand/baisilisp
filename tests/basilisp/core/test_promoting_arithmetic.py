import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

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


@given(
    st.one_of(
        st.lists(st.integers(), max_size=80),
        st.lists(st.floats(allow_nan=False, allow_infinity=False), max_size=40),
        st.lists(
            st.decimals(allow_nan=False, allow_infinity=False, places=6), max_size=40
        ),
    )
)
def _check_promoting_arithmetic_matches_normal(normal, promoting, values):
    actual = promoting(*values)
    expected = normal(*values)
    assert actual == expected or (
        isinstance(actual, float)
        and isinstance(expected, float)
        and math.isnan(actual)
        and math.isnan(expected)
    )


@pytest.mark.parametrize(("operator", "promoting_operator"), [("+", "+'"), ("*", "*'")])
def test_promoting_arithmetic_matches_normal_for_random_numeric_sequences(
    core_ns, operator, promoting_operator
):
    _check_promoting_arithmetic_matches_normal(
        _core_fn(core_ns, operator), _core_fn(core_ns, promoting_operator)
    )


@pytest.mark.parametrize("operator", ["+'", "*'"])
@pytest.mark.parametrize("value", [None, "1", [], {}, True, False])
def test_promoting_arithmetic_rejects_nonnumeric_values(core_ns, operator, value):
    promoting = _core_fn(core_ns, operator)

    with pytest.raises(TypeError):
        promoting(1, value)
