import decimal
import math
import struct
from fractions import Fraction

import pytest
from hypothesis import given, strategies as st

from basilisp.lang.character import Character
from basilisp.lang import numeric_coerce as coerce


def _signed(value: int, bits: int) -> int:
    value %= 1 << bits
    return value - (1 << bits) if value >= 1 << (bits - 1) else value


@pytest.mark.parametrize("bits", [8, 16, 32, 64])
@given(st.integers())
def test_unchecked_integer_matches_independent_twos_complement_model(bits, value):
    assert coerce.unchecked_integer(value, bits) == _signed(value, bits)


@pytest.mark.parametrize("bits", [8, 16, 32, 64])
@given(st.integers())
def test_checked_integer_enforces_exact_signed_width(bits, value):
    lower, upper = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    if lower <= value <= upper:
        assert coerce.checked_integer(value, bits) == value
    else:
        with pytest.raises(ValueError):
            coerce.checked_integer(value, bits)


@pytest.mark.parametrize("bits", [8, 16, 32, 64])
def test_integer_coercions_truncate_numeric_values_and_treat_nan_like_the_jvm(bits):
    assert coerce.checked_integer(Fraction(-19, 10), bits) == -1
    assert coerce.checked_integer(decimal.Decimal("1.9"), bits) == 1
    assert coerce.checked_integer(float("nan"), bits) == 0
    assert coerce.unchecked_integer(float("inf"), bits) == (1 << (bits - 1)) - 1
    assert coerce.unchecked_integer(float("-inf"), bits) == -(1 << (bits - 1))


@pytest.mark.parametrize(
    "value",
    [None, True, False, "1", 1 + 0j],
)
def test_numeric_coercions_reject_python_only_implicit_conversions(value):
    with pytest.raises(TypeError):
        coerce.checked_integer(value, 32)
    with pytest.raises(TypeError):
        coerce.double(value)
    with pytest.raises(TypeError):
        coerce.checked_float(value)


def test_floating_coercions_reject_characters():
    with pytest.raises(TypeError):
        coerce.double(Character("1"))
    with pytest.raises(TypeError):
        coerce.checked_float(Character("1"))


def test_checked_integer_character_contract_and_unchecked_exceptions():
    character = Character("A")
    for bits in (8, 16, 32, 64):
        assert coerce.checked_integer(character, bits) == 65
    assert coerce.unchecked_integer(character, 32, allow_character=True) == 65
    with pytest.raises(TypeError):
        coerce.unchecked_integer(character, 8)


@given(st.floats(allow_nan=False, allow_infinity=False, width=64))
def test_single_precision_coercion_matches_independent_ieee754_model(value):
    try:
        expected = struct.unpack("!f", struct.pack("!f", value))[0]
    except OverflowError:
        expected = math.copysign(math.inf, value)
    if math.isinf(expected):
        with pytest.raises(ValueError):
            coerce.checked_float(value)
    else:
        assert coerce.checked_float(value) == expected
    assert coerce.unchecked_float(value) == expected


def test_float_and_double_nonfinite_contracts():
    assert math.isnan(coerce.checked_float(float("nan")))
    with pytest.raises(ValueError):
        coerce.checked_float(float("inf"))
    assert math.isinf(coerce.unchecked_float(float("inf")))
    assert math.isinf(coerce.double(float("inf")))


@given(st.integers())
def test_bigint_accepts_unbounded_numeric_values(value):
    assert coerce.bigint(value) == value


def test_bigint_and_bigdec_keep_clojures_string_exceptions_and_decimal_spelling():
    assert coerce.bigint("100000000000000000000000000000000000000") == 10**38
    assert coerce.bigdec("1.25") == decimal.Decimal("1.25")
    assert coerce.bigdec(1.1) == decimal.Decimal("1.1")
    assert coerce.bigdec(Fraction(1, 2)) == decimal.Decimal("0.5")
    for value in (True, Character("1"), float("nan"), float("inf")):
        with pytest.raises((TypeError, ValueError, OverflowError)):
            coerce.bigint(value)
        with pytest.raises(TypeError):
            coerce.bigdec(value)


@given(st.integers())
def test_unchecked_char_tracks_the_low_utf16_bits(value):
    assert ord(coerce.unchecked_char(value).value) == value % (1 << 16)
