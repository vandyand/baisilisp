import concurrent.futures
import decimal

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


def _context(precision: int, rounding: str) -> decimal.Context:
    return decimal.Context(prec=precision, rounding=rounding)


def _context_state(context: decimal.Context) -> tuple:
    return (
        context.prec,
        context.rounding,
        context.Emin,
        context.Emax,
        context.capitals,
        context.clamp,
        tuple(
            sorted(
                (signal.__name__, enabled) for signal, enabled in context.flags.items()
            )
        ),
        tuple(
            sorted(
                (signal.__name__, enabled) for signal, enabled in context.traps.items()
            )
        ),
    )


def test_math_context_binding_controls_decimal_arithmetic(core_ns):
    math_context = _math_context_var(core_ns)

    with runtime.bindings(lmap.map({math_context: _context(2, decimal.ROUND_HALF_UP)})):
        assert numbers.divide(
            decimal.Decimal(1), decimal.Decimal(8)
        ) == decimal.Decimal("0.13")


def test_math_context_binding_is_nested_and_exception_safe(core_ns):
    math_context = _math_context_var(core_ns)
    before = decimal.getcontext().copy()
    outer = _context(2, decimal.ROUND_HALF_UP)
    inner = _context(3, decimal.ROUND_HALF_UP)

    with pytest.raises(RuntimeError, match="expected failure"):
        with runtime.bindings(lmap.map({math_context: outer})):
            assert decimal.Decimal(1) / decimal.Decimal(7) == decimal.Decimal("0.14")
            with runtime.bindings(lmap.map({math_context: inner})):
                assert decimal.Decimal(1) / decimal.Decimal(7) == decimal.Decimal(
                    "0.143"
                )
            assert decimal.Decimal(1) / decimal.Decimal(7) == decimal.Decimal("0.14")
            raise RuntimeError("expected failure")

    assert _context_state(decimal.getcontext()) == _context_state(before)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    numerator=st.integers(min_value=-(10**18), max_value=10**18),
    denominator=st.integers(min_value=1, max_value=10**9),
    precision=st.integers(min_value=1, max_value=28),
    rounding=st.sampled_from(
        [
            decimal.ROUND_CEILING,
            decimal.ROUND_DOWN,
            decimal.ROUND_FLOOR,
            decimal.ROUND_HALF_DOWN,
            decimal.ROUND_HALF_EVEN,
            decimal.ROUND_HALF_UP,
            decimal.ROUND_UP,
            decimal.ROUND_05UP,
        ]
    ),
)
def test_math_context_binding_matches_python_decimal_context(
    core_ns, numerator, denominator, precision, rounding
):
    math_context = _math_context_var(core_ns)
    context = _context(precision, rounding)

    with decimal.localcontext(context):
        expected_add = decimal.Decimal(numerator) + decimal.Decimal(denominator)
        expected_subtract = decimal.Decimal(numerator) - decimal.Decimal(denominator)
        expected_multiply = decimal.Decimal(numerator) * decimal.Decimal(denominator)
        expected = decimal.Decimal(numerator) / decimal.Decimal(denominator)

    with runtime.bindings(lmap.map({math_context: context})):
        actual_add = numbers.add(
            decimal.Decimal(numerator), decimal.Decimal(denominator)
        )
        actual_subtract = numbers.subtract(
            decimal.Decimal(numerator), decimal.Decimal(denominator)
        )
        actual_multiply = numbers.multiply(
            decimal.Decimal(numerator), decimal.Decimal(denominator)
        )
        actual = numbers.divide(
            decimal.Decimal(numerator), decimal.Decimal(denominator)
        )

    assert actual_add == expected_add
    assert actual_subtract == expected_subtract
    assert actual_multiply == expected_multiply
    assert actual == expected


def test_math_context_bindings_are_thread_isolated(core_ns):
    math_context = _math_context_var(core_ns)

    def divide_with(precision: int) -> decimal.Decimal:
        with runtime.bindings(
            lmap.map({math_context: _context(precision, decimal.ROUND_HALF_UP)})
        ):
            return decimal.Decimal(1) / decimal.Decimal(7)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(divide_with, precision) for precision in (2, 5)]
        actual = [future.result() for future in futures]

    assert actual == [decimal.Decimal("0.14"), decimal.Decimal("0.14286")]
