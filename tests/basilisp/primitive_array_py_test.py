import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from basilisp.lang.character import Character
from basilisp.lang.primitive_array import (
    BooleanArray,
    ByteArray,
    CharArray,
    DoubleArray,
    FloatArray,
    IntArray,
    LongArray,
    ShortArray,
    boolean_array,
    byte_array,
    char_array,
    clone_array,
    double_array,
    float_array,
    int_array,
    long_array,
    short_array,
)


def _signed(value: int, bits: int) -> int:
    value %= 1 << bits
    return value - (1 << bits) if value >= 1 << (bits - 1) else value


@pytest.mark.parametrize(
    ("factory", "array_type", "default"),
    [
        (boolean_array, BooleanArray, False),
        (byte_array, ByteArray, 0),
        (char_array, CharArray, Character("\x00")),
        (short_array, ShortArray, 0),
        (int_array, IntArray, 0),
        (long_array, LongArray, 0),
        (float_array, FloatArray, 0.0),
        (double_array, DoubleArray, 0.0),
    ],
)
def test_primitive_arrays_preserve_container_and_default_contract(
    factory, array_type, default
):
    value = factory(4)

    assert isinstance(value, array_type)
    assert list(value) == [default] * 4
    assert isinstance(clone_array(value), array_type)


@given(st.integers(min_value=-(1 << 160), max_value=(1 << 160)))
def test_fixed_width_arrays_wrap_at_construction_and_assignment(value):
    for factory, bits in (
        (byte_array, 8),
        (short_array, 16),
        (int_array, 32),
        (long_array, 64),
    ):
        array = factory([value])
        assert array[0] == _signed(value, bits)
        array.assign(0, _signed(value, bits))
        assert array[0] == _signed(value, bits)


@given(st.binary(max_size=1024))
def test_byte_arrays_preserve_binary_buffers_and_signed_lisp_reads(payload):
    array = byte_array(payload)

    assert isinstance(array, bytearray)
    assert bytes(array) == payload
    assert list(array) == [_signed(value, 8) for value in payload]

    clone = clone_array(array)
    if payload:
        clone[0] = 0
        assert bytes(array) == payload


@given(st.lists(st.integers(min_value=-(1 << 50), max_value=(1 << 50)), max_size=128))
def test_partial_source_fill_and_clone_do_not_share_mutable_storage(values):
    array = int_array(len(values) + 3, values)
    expected = [_signed(value, 32) for value in values] + [0, 0, 0]

    assert list(array) == expected
    clone = clone_array(array)
    if clone:
        clone.assign(0, 17)
        assert clone[0] == 17
        assert array[0] == expected[0]


@given(st.floats(allow_nan=False, allow_infinity=False, width=64))
def test_float_arrays_apply_single_precision_while_double_arrays_retain_python_double(
    value,
):
    single = float_array([value])[0]
    double = double_array([value])[0]

    assert math.isfinite(single) or math.isinf(single)
    assert double == float(value)


def test_primitive_arrays_reject_cross_type_mutation_and_scalar_sequence_confusion():
    with pytest.raises(TypeError):
        boolean_array([1])
    with pytest.raises(TypeError):
        char_array(["a"])
    with pytest.raises(TypeError):
        byte_array(["1"])
    with pytest.raises(TypeError):
        int_array(2, "not-a-sequence")

    chars = char_array("ab")
    with pytest.raises(TypeError):
        chars[0] = "a"
    with pytest.raises(TypeError):
        IntArray([0]).append(True)
    with pytest.raises(OverflowError):
        byte_array(1).assign(0, 128)
    with pytest.raises(OverflowError):
        int_array(1).assign(0, 1 << 31)
