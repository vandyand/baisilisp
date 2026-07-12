import math
import random
import sys

import pytest

from basilisp import main
from basilisp.lang import runtime
from basilisp.lang import symbol as sym


@pytest.fixture(scope="module", autouse=True)
def initialize_runtime():
    main.init()
    __import__("basilisp.math")


def _math_var(name: str):
    var = runtime.Var.find(sym.symbol(name, ns="basilisp.math"))
    assert var is not None
    return var.value


def _same_float(actual: float, expected: float) -> bool:
    if math.isnan(expected):
        return math.isnan(actual)
    if math.isinf(expected):
        return actual == expected
    return actual == expected


def test_public_api_matches_clojure_math_surface():
    expected = {
        "E",
        "PI",
        "sin",
        "cos",
        "tan",
        "asin",
        "acos",
        "atan",
        "to-radians",
        "to-degrees",
        "exp",
        "log",
        "log10",
        "sqrt",
        "cbrt",
        "IEEE-remainder",
        "ceil",
        "floor",
        "rint",
        "atan2",
        "pow",
        "round",
        "random",
        "add-exact",
        "subtract-exact",
        "multiply-exact",
        "increment-exact",
        "decrement-exact",
        "negate-exact",
        "floor-div",
        "floor-mod",
        "ulp",
        "signum",
        "sinh",
        "cosh",
        "tanh",
        "hypot",
        "expm1",
        "log1p",
        "copy-sign",
        "get-exponent",
        "next-after",
        "next-up",
        "next-down",
        "scalb",
    }
    ns = runtime.Namespace.get(sym.symbol("basilisp.math"))
    assert ns is not None
    assert expected == {
        str(name) for name, var in ns.interns.items() if not var.is_private
    }


def test_seeded_floating_point_differential_fuzz():
    rng = random.Random(0xBA5115)
    unary = {
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "atan": math.atan,
        "exp": math.exp,
        "log": math.log,
        "log10": math.log10,
        "sqrt": math.sqrt,
        "cbrt": math.cbrt,
        "sinh": math.sinh,
        "cosh": math.cosh,
        "tanh": math.tanh,
        "expm1": math.expm1,
        "log1p": math.log1p,
        "ulp": math.ulp,
    }

    for _ in range(2_000):
        positive = rng.uniform(1e-300, 700.0)
        signed = rng.uniform(-20.0, 20.0)
        for name, py_fn in unary.items():
            value = (
                positive
                if name in {"log", "log10", "sqrt"}
                else rng.uniform(-0.99, 20.0) if name == "log1p" else signed
            )
            expected = py_fn(value)
            actual = _math_var(name)(value)
            assert _same_float(actual, expected), (name, value, actual, expected)

        x = rng.uniform(-1e150, 1e150)
        y = rng.uniform(-1e150, 1e150)
        for name, py_fn in {
            "atan2": math.atan2,
            "hypot": math.hypot,
            "copy-sign": math.copysign,
            "next-after": math.nextafter,
        }.items():
            expected = py_fn(x, y)
            actual = _math_var(name)(x, y)
            assert _same_float(actual, expected), (name, x, y, actual, expected)

        base = rng.uniform(0.0, 100.0)
        exponent = rng.uniform(-10.0, 10.0)
        assert _same_float(_math_var("pow")(base, exponent), math.pow(base, exponent))

        scale = rng.randrange(-900, 900)
        value = rng.uniform(-1.0, 1.0)
        assert _same_float(_math_var("scalb")(value, scale), math.ldexp(value, scale))


def test_seeded_integer_and_navigation_stress():
    rng = random.Random(0xC10C0DE)
    floor_div = _math_var("floor-div")
    floor_mod = _math_var("floor-mod")
    add_exact = _math_var("add-exact")
    subtract_exact = _math_var("subtract-exact")
    multiply_exact = _math_var("multiply-exact")
    get_exponent = _math_var("get-exponent")
    next_up = _math_var("next-up")
    next_down = _math_var("next-down")

    for _ in range(5_000):
        x = rng.randrange(-(10**120), 10**120)
        y = rng.randrange(-(10**120), 10**120) or 1
        assert floor_div(x, y) == x // y
        assert floor_mod(x, y) == x % y
        assert x == y * floor_div(x, y) + floor_mod(x, y)
        assert add_exact(x, y) == x + y
        assert subtract_exact(x, y) == x - y
        assert multiply_exact(x, y) == x * y

        value = rng.uniform(-1e300, 1e300)
        assert get_exponent(value) == math.frexp(value)[1] - 1
        assert next_up(value) == math.nextafter(value, math.inf)
        assert next_down(value) == math.nextafter(value, -math.inf)


def test_cbrt_fallback_and_adversarial_float_cases():
    cbrt_fallback = _math_var("cbrt-fallback")
    for value in (-1e300, -27.0, -1.0, 1.0, 8.0, 1e300):
        assert math.isclose(cbrt_fallback(value), math.cbrt(value), rel_tol=1e-14)
    assert math.copysign(1.0, cbrt_fallback(-0.0)) == -1.0
    assert cbrt_fallback(math.inf) == math.inf
    assert cbrt_fallback(-math.inf) == -math.inf
    assert math.isnan(cbrt_fallback(math.nan))

    ceil = _math_var("ceil")
    floor = _math_var("floor")
    rint = _math_var("rint")
    signum = _math_var("signum")
    get_exponent = _math_var("get-exponent")
    ieee_remainder = _math_var("IEEE-remainder")
    log = _math_var("log")
    sqrt = _math_var("sqrt")
    pow_fn = _math_var("pow")

    assert math.copysign(1.0, ceil(-0.5)) == -1.0
    assert math.copysign(1.0, floor(-0.0)) == -1.0
    assert math.copysign(1.0, rint(-0.0)) == -1.0
    assert math.copysign(1.0, signum(-0.0)) == -1.0
    assert get_exponent(0.0) == -1023
    assert get_exponent(math.nextafter(0.0, math.inf)) == -1023
    assert get_exponent(sys.float_info.min) == -1022
    assert get_exponent(math.inf) == get_exponent(math.nan) == 1024
    assert math.isnan(ieee_remainder(math.inf, 1.0))
    assert math.isnan(ieee_remainder(1.0, 0.0))
    assert log(0.0) == -math.inf
    assert math.isnan(log(-1.0))
    assert math.isnan(sqrt(-1.0))
    assert math.isnan(pow_fn(-1.0, 0.5))
