import math
from decimal import Decimal
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from basilisp.lang import symbol as sym


def _num(core_ns):
    var = core_ns.find(sym.symbol("num"))
    assert var is not None
    return var.value


@pytest.mark.parametrize("value", [None, 0, -1, 1.5, Fraction(2, 3), Decimal("1.0")])
def test_num_returns_supported_values_unchanged(core_ns, value):
    num = _num(core_ns)

    result = num(value)

    assert result == value
    assert type(result) is type(value)


def test_num_preserves_nan_and_complex_values(core_ns):
    num = _num(core_ns)

    result = num(float("nan"))
    assert math.isnan(result)
    assert num(1 + 2j) == 1 + 2j


@given(
    st.one_of(
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=True),
        st.decimals(allow_nan=False, allow_infinity=False),
        st.fractions(),
        st.complex_numbers(allow_nan=False, allow_infinity=False),
    )
)
def _check_num_is_identity(num, value):
    result = num(value)

    assert result == value
    assert type(result) is type(value)


def test_num_is_identity_for_random_numeric_values(core_ns):
    num = _num(core_ns)

    _check_num_is_identity(num)


@given(
    st.one_of(
        st.booleans(),
        st.text(),
        st.binary(),
        st.lists(st.integers(), max_size=8),
        st.dictionaries(st.text(max_size=4), st.integers(), max_size=8),
        st.sets(st.integers(), max_size=8),
    )
)
def _check_num_rejects_non_numeric(num, value):
    with pytest.raises(TypeError, match="Expected a number"):
        num(value)


def test_num_rejects_random_non_numeric_values(core_ns):
    num = _num(core_ns)

    _check_num_rejects_non_numeric(num)
