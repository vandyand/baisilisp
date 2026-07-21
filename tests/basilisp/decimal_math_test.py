import decimal
from fractions import Fraction

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from basilisp.lang import map as lmap
from basilisp.lang import numbers, runtime
from basilisp.lang import symbol as sym


def _math_context_var(core_ns):
    var = core_ns.find(sym.symbol(runtime.MATH_CONTEXT_VAR_NAME))
    assert var is not None
    return var


def _decimal(coefficient: int, exponent: int) -> decimal.Decimal:
    sign = int(coefficient < 0)
    digits = tuple(map(int, str(abs(coefficient)))) if coefficient else (0,)
    return decimal.Decimal((sign, digits, exponent))


def _fraction(value: decimal.Decimal) -> Fraction:
    numerator, denominator = value.as_integer_ratio()
    return Fraction(numerator, denominator)


decimal_values = st.tuples(
    st.integers(min_value=-(10**120), max_value=10**120),
    st.integers(min_value=-80, max_value=40),
).map(lambda values: _decimal(*values))


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(x=decimal_values, y=decimal_values)
def test_unlimited_decimal_add_subtract_and_multiply_are_exact(core_ns, x, y):
    math_context = _math_context_var(core_ns)

    with runtime.bindings(lmap.map({math_context: None})):
        add_result = numbers.add(x, y)
        subtract_result = numbers.subtract(x, y)
        multiply_result = numbers.multiply(x, y)

    assert _fraction(add_result) == _fraction(x) + _fraction(y)
    assert _fraction(subtract_result) == _fraction(x) - _fraction(y)
    assert _fraction(multiply_result) == _fraction(x) * _fraction(y)
    assert add_result.as_tuple().exponent == min(
        x.as_tuple().exponent, y.as_tuple().exponent
    )
    assert subtract_result.as_tuple().exponent == min(
        x.as_tuple().exponent, y.as_tuple().exponent
    )
    assert multiply_result.as_tuple().exponent == (
        x.as_tuple().exponent + y.as_tuple().exponent
    )


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    numerator=st.integers(min_value=-(10**80), max_value=10**80).filter(bool),
    twos=st.integers(min_value=0, max_value=40),
    fives=st.integers(min_value=0, max_value=40),
    numerator_exponent=st.integers(min_value=-40, max_value=40),
    denominator_exponent=st.integers(min_value=-40, max_value=40),
)
def test_unlimited_decimal_divide_preserves_exact_terminating_results(
    core_ns, numerator, twos, fives, numerator_exponent, denominator_exponent
):
    math_context = _math_context_var(core_ns)
    x = _decimal(numerator, numerator_exponent)
    y = _decimal(2**twos * 5**fives, denominator_exponent)

    with runtime.bindings(lmap.map({math_context: None})):
        result = numbers.divide(x, y)

    assert _fraction(result) == _fraction(x) / _fraction(y)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    numerator=st.integers(min_value=-(10**60), max_value=10**60),
    twos=st.integers(min_value=0, max_value=20),
    fives=st.integers(min_value=0, max_value=20),
)
def test_unlimited_decimal_divide_rejects_nonterminating_results(
    core_ns, numerator, twos, fives
):
    math_context = _math_context_var(core_ns)
    x = decimal.Decimal(3 * numerator + 1)
    y = decimal.Decimal(3 * 2**twos * 5**fives)

    with runtime.bindings(lmap.map({math_context: None})):
        with pytest.raises(decimal.Inexact, match="Non-terminating"):
            numbers.divide(x, y)


def test_nil_math_context_overrides_an_outer_finite_context(core_ns):
    math_context = _math_context_var(core_ns)
    finite_context = decimal.Context(prec=2, rounding=decimal.ROUND_HALF_UP)

    with runtime.bindings(lmap.map({math_context: finite_context})):
        assert numbers.divide(
            decimal.Decimal(1), decimal.Decimal(7)
        ) == decimal.Decimal("0.14")
        with runtime.bindings(lmap.map({math_context: None})):
            with pytest.raises(decimal.Inexact):
                numbers.divide(decimal.Decimal(1), decimal.Decimal(7))
        assert numbers.divide(
            decimal.Decimal(1), decimal.Decimal(7)
        ) == decimal.Decimal("0.14")
