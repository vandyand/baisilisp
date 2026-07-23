import decimal
import fractions
import functools
import math
from fractions import Fraction
from typing import Callable, TypeVar

from basilisp.lang.typing import LispNumber

T_num = TypeVar("T_num", bound=LispNumber)


def _uses_unlimited_decimal_math() -> bool:
    """Return whether core decimal operations should use Clojure's exact mode.

    Clojure represents an unbound ``*math-context*`` as ``nil``.  In that mode
    ``BigDecimal`` arithmetic is exact rather than subject to an ambient,
    finite-precision context.  Python's ``decimal`` module always has such a
    context, so Basilisp implements the exact operations explicitly whenever
    the corresponding dynamic Var is nil.
    """

    # Import lazily: this module is used while the runtime and core namespace
    # bootstrap, before basilisp.core/*math-context* necessarily exists.
    from basilisp.lang import runtime

    math_context = runtime.Var.find(
        runtime.sym.symbol(runtime.MATH_CONTEXT_VAR_NAME, ns=runtime.CORE_NS)
    )
    return math_context is None or math_context.value is None


def _decimal_coefficient_and_exponent(value: decimal.Decimal) -> tuple[int, int]:
    """Return a finite Decimal's signed coefficient and base-ten exponent."""

    decimal_tuple = value.as_tuple()
    coefficient = int("".join(map(str, decimal_tuple.digits)) or "0")
    if decimal_tuple.sign:
        coefficient = -coefficient
    return coefficient, decimal_tuple.exponent


def _decimal_from_coefficient(coefficient: int, exponent: int) -> decimal.Decimal:
    """Build a Decimal without applying Python's active decimal context."""

    sign = int(coefficient < 0)
    digits = tuple(map(int, str(abs(coefficient)))) if coefficient else (0,)
    return decimal.Decimal((sign, digits, exponent))


def _exact_decimal_add(
    x: decimal.Decimal, y: decimal.Decimal, *, subtract: bool = False
) -> decimal.Decimal:
    """Add or subtract finite Decimals with BigDecimal's unlimited precision."""

    if not x.is_finite() or not y.is_finite():
        return x - y if subtract else x + y

    x_coefficient, x_exponent = _decimal_coefficient_and_exponent(x)
    y_coefficient, y_exponent = _decimal_coefficient_and_exponent(y)
    if subtract:
        y_coefficient = -y_coefficient
    exponent = min(x_exponent, y_exponent)
    coefficient = x_coefficient * 10 ** (
        x_exponent - exponent
    ) + y_coefficient * 10 ** (y_exponent - exponent)
    return _decimal_from_coefficient(coefficient, exponent)


def _exact_decimal_multiply(x: decimal.Decimal, y: decimal.Decimal) -> decimal.Decimal:
    """Multiply finite Decimals with BigDecimal's unlimited precision."""

    if not x.is_finite() or not y.is_finite():
        return x * y

    x_coefficient, x_exponent = _decimal_coefficient_and_exponent(x)
    y_coefficient, y_exponent = _decimal_coefficient_and_exponent(y)
    return _decimal_from_coefficient(
        x_coefficient * y_coefficient, x_exponent + y_exponent
    )


def _exact_decimal_divide(x: decimal.Decimal, y: decimal.Decimal) -> decimal.Decimal:
    """Divide finite Decimals exactly, rejecting non-terminating expansions."""

    if not x.is_finite() or not y.is_finite():
        return x / y

    x_coefficient, x_exponent = _decimal_coefficient_and_exponent(x)
    y_coefficient, y_exponent = _decimal_coefficient_and_exponent(y)
    if y_coefficient == 0:
        return x / y

    divisor = abs(y_coefficient)
    common_factor = math.gcd(abs(x_coefficient), divisor)
    numerator = x_coefficient // common_factor
    divisor //= common_factor
    twos = fives = 0
    while divisor % 2 == 0:
        divisor //= 2
        twos += 1
    while divisor % 5 == 0:
        divisor //= 5
        fives += 1
    if divisor != 1:
        raise decimal.Inexact("Non-terminating decimal expansion")

    decimal_places = max(twos, fives)
    coefficient = (
        numerator * 2 ** (decimal_places - twos) * 5 ** (decimal_places - fives)
    )
    if y_coefficient < 0:
        coefficient = -coefficient
    return _decimal_from_coefficient(
        coefficient, x_exponent - y_exponent - decimal_places
    )


def _decimal_add(x: decimal.Decimal, y: decimal.Decimal) -> decimal.Decimal:
    return _exact_decimal_add(x, y) if _uses_unlimited_decimal_math() else x + y


def _decimal_subtract(x: decimal.Decimal, y: decimal.Decimal) -> decimal.Decimal:
    return (
        _exact_decimal_add(x, y, subtract=True)
        if _uses_unlimited_decimal_math()
        else x - y
    )


def _decimal_divide(x: decimal.Decimal, y: decimal.Decimal) -> decimal.Decimal:
    return _exact_decimal_divide(x, y) if _uses_unlimited_decimal_math() else x / y


def _decimal_multiply(x: decimal.Decimal, y: decimal.Decimal) -> decimal.Decimal:
    return _exact_decimal_multiply(x, y) if _uses_unlimited_decimal_math() else x * y


def _normalize_fraction_result(
    f: Callable[[T_num, LispNumber], LispNumber],
) -> Callable[[T_num, LispNumber], LispNumber]:
    """
    Decorator for arithmetic operations to simplify `fractions.Fraction` values with
    a denominator of 1 to an integer.
    """

    @functools.wraps(f)
    def _normalize(x: T_num, y: LispNumber) -> LispNumber:
        result = f(x, y)
        # fractions.Fraction.is_integer() wasn't added until 3.12
        return (
            result.numerator
            if isinstance(result, fractions.Fraction) and result.denominator == 1
            else result
        )

    return _normalize


def _to_decimal(x: LispNumber) -> decimal.Decimal:
    """Coerce the input Lisp number to a `decimal.Decimal`.

    `fractions.Fraction` types are not accepted as direct inputs, so this is a utility
    to simplify that coercion.."""
    if isinstance(x, Fraction):
        numerator, denominator = x.as_integer_ratio()
        return _decimal_divide(decimal.Decimal(numerator), decimal.Decimal(denominator))
    return decimal.Decimal(x)


def quotient(x: LispNumber, y: LispNumber) -> LispNumber:
    """Return Clojure ``quot`` semantics without exact division first.

    ``/`` intentionally rejects non-terminating BigDecimal quotients when
    ``*math-context*`` is nil. ``quot`` is different: it truncates the quotient
    toward zero and therefore must be able to handle cases such as
    ``(quot 10 3.0M)`` without requiring an exact decimal expansion.
    """

    if isinstance(x, float) or isinstance(y, float):
        return float(math.trunc(float(x) / float(y)))
    if isinstance(x, decimal.Decimal) or isinstance(y, decimal.Decimal):
        return _to_decimal(x) // _to_decimal(y)
    return math.trunc(Fraction(x) / Fraction(y))


def remainder(x: LispNumber, y: LispNumber) -> LispNumber:
    """Return Clojure ``rem`` semantics using truncating quotient."""

    return subtract(x, multiply(y, quotient(x, y)))


@_normalize_fraction_result
def modulus(x: LispNumber, y: LispNumber) -> LispNumber:
    """Return Clojure ``mod`` semantics using floored remainder."""

    if isinstance(x, float) or isinstance(y, float):
        quotient_floor = math.floor(float(x) / float(y))
        return subtract(x, multiply(y, quotient_floor))
    if isinstance(x, decimal.Decimal) or isinstance(y, decimal.Decimal):
        decimal_x, decimal_y = _to_decimal(x), _to_decimal(y)
        rem = decimal_x % decimal_y
        if rem and ((rem > 0) != (decimal_y > 0)):
            rem += decimal_y
        return rem
    return x % y


# All the arithmetic helpers below downcast `decimal.Decimal` values down to floats
# in any binary arithmetic operation which involves one `float` and one `decimal.Decimal`.
# This perhaps peculiar behavior, but it is what Clojure does. I suspect that is due
# to the potential loss of precision with any calculation between these two types, so
# Clojure errs on the side of returning the less precise type to indicate the potential
# lossiness of the calculation.


@functools.singledispatch
@_normalize_fraction_result
def add(x: LispNumber, y: LispNumber) -> LispNumber:
    """Add two numbers together and return the result."""
    return x + y  # type: ignore[operator]


@add.register(float)
@_normalize_fraction_result
def _add_float(x: float, y: LispNumber) -> LispNumber:
    if isinstance(y, decimal.Decimal):
        return float(_decimal_add(decimal.Decimal(x), y))
    return x + y


@add.register(int)
@_normalize_fraction_result
def _add_int(x: int, y: LispNumber) -> LispNumber:
    if isinstance(y, decimal.Decimal):
        return _decimal_add(decimal.Decimal(x), y)
    return x + y


@add.register(decimal.Decimal)
@_normalize_fraction_result
def _add_decimal(x: decimal.Decimal, y: LispNumber) -> LispNumber:
    v = _decimal_add(x, _to_decimal(y))
    return float(v) if isinstance(y, float) else v


@add.register(Fraction)
@_normalize_fraction_result
def _add_fraction(x: Fraction, y: LispNumber) -> LispNumber:
    if isinstance(y, decimal.Decimal):
        return _decimal_add(_to_decimal(x), y)
    return x + y


@functools.singledispatch
@_normalize_fraction_result
def subtract(x: LispNumber, y: LispNumber) -> LispNumber:
    """Subtract `y` from `x` and return the result."""
    return x - y  # type: ignore[operator]


@subtract.register(float)
@_normalize_fraction_result
def _subtract_float(x: float, y: LispNumber) -> LispNumber:
    if isinstance(y, decimal.Decimal):
        return float(_decimal_subtract(decimal.Decimal(x), y))
    return x - y


@subtract.register(int)
@_normalize_fraction_result
def _subtract_int(x: int, y: LispNumber) -> LispNumber:
    if isinstance(y, decimal.Decimal):
        return _decimal_subtract(decimal.Decimal(x), y)
    return x - y


@subtract.register(decimal.Decimal)
@_normalize_fraction_result
def _subtract_decimal(x: decimal.Decimal, y: LispNumber) -> LispNumber:
    v = _decimal_subtract(x, _to_decimal(y))
    return float(v) if isinstance(y, float) else v


@subtract.register(Fraction)
@_normalize_fraction_result
def _subtract_fraction(x: Fraction, y: LispNumber) -> LispNumber:
    if isinstance(y, decimal.Decimal):
        return _decimal_subtract(_to_decimal(x), y)
    return x - y


@functools.singledispatch
@_normalize_fraction_result
def divide(x: LispNumber, y: LispNumber) -> LispNumber:
    """Division reducer. If both arguments are integers, return a Fraction.
    Otherwise, return the true division of x and y."""
    return x / y  # type: ignore[operator]


@divide.register(int)
@_normalize_fraction_result
def _divide_ints(x: int, y: LispNumber) -> LispNumber:
    if isinstance(y, int):
        return Fraction(x, y)
    if isinstance(y, decimal.Decimal):
        return _decimal_divide(decimal.Decimal(x), y)
    return x / y


@divide.register(float)
@_normalize_fraction_result
def _divide_float(x: float, y: LispNumber) -> LispNumber:
    if isinstance(y, decimal.Decimal):
        return float(_decimal_divide(decimal.Decimal(x), y))
    try:
        return x / y
    except ZeroDivisionError:
        if math.isnan(x):
            return math.nan
        elif x >= 0:
            return math.inf
        else:
            return -math.inf


@divide.register(decimal.Decimal)
@_normalize_fraction_result
def _divide_decimal(x: decimal.Decimal, y: LispNumber) -> LispNumber:
    v = _decimal_divide(x, _to_decimal(y))
    return float(v) if isinstance(y, float) else v


@divide.register(Fraction)
@_normalize_fraction_result
def _divide_fraction(x: Fraction, y: LispNumber) -> LispNumber:
    if isinstance(y, decimal.Decimal):
        return _decimal_divide(_to_decimal(x), y)
    return x / y


@functools.singledispatch
@_normalize_fraction_result
def multiply(x: LispNumber, y: LispNumber) -> LispNumber:
    """Multiply two numbers together and return the result."""
    return x * y  # type: ignore[operator]


@multiply.register(float)
@_normalize_fraction_result
def _multiply_float(x: float, y: LispNumber) -> LispNumber:
    if isinstance(y, decimal.Decimal):
        return float(_decimal_multiply(decimal.Decimal(x), y))
    return x * y


@multiply.register(int)
@_normalize_fraction_result
def _multiply_int(x: int, y: LispNumber) -> LispNumber:
    if isinstance(y, decimal.Decimal):
        return _decimal_multiply(decimal.Decimal(x), y)
    return x * y


@multiply.register(decimal.Decimal)
@_normalize_fraction_result
def _multiply_decimal(x: decimal.Decimal, y: LispNumber) -> LispNumber:
    v = _decimal_multiply(x, _to_decimal(y))
    return float(v) if isinstance(y, float) else v


@multiply.register(Fraction)
@_normalize_fraction_result
def _multiply_fraction(x: Fraction, y: LispNumber) -> LispNumber:
    if isinstance(y, decimal.Decimal):
        return _decimal_multiply(_to_decimal(x), y)
    return x * y


@functools.singledispatch
def trunc(x: LispNumber) -> LispNumber:
    """Truncate any fractional part of the input value, preserving the input type.

    Truncation is effectively rounding towards 0."""
    return math.trunc(x)


@trunc.register(float)
def _trunc_float(x: float) -> LispNumber:
    return float(math.trunc(x))


@trunc.register(decimal.Decimal)
def _trunc_decimal(x: decimal.Decimal) -> LispNumber:
    return decimal.Decimal(math.trunc(x))


@trunc.register(Fraction)
def _trunc_fraction(x: Fraction) -> LispNumber:
    v = fractions.Fraction(math.trunc(x))
    return v.numerator if v.denominator == 1 else v
