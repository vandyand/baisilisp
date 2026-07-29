import io
import math
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from basilisp.lang import character, obj, reader, runtime
from basilisp.lang import set as lset
from basilisp.lang import vector as vec


def read_one(source: str):
    return next(reader.read_str(source))


def _utf16_units(value: str) -> list[str]:
    encoded = value.encode("utf-16-le", "surrogatepass")
    return [
        chr(int.from_bytes(encoded[offset : offset + 2], "little"))
        for offset in range(0, len(encoded), 2)
    ]


def _utf16_slice(value: str, start: int, end: int) -> str:
    return "".join(_utf16_units(value)[start:end])


def _utf16_bytes(value: str) -> bytes:
    return value.encode("utf-16-le", "surrogatepass")


@pytest.mark.parametrize(
    ("source", "value", "printed"),
    [
        (r"\a", "a", r"\a"),
        (r"\space", " ", r"\space"),
        (r"\newline", "\n", r"\newline"),
        (r"\tab", "\t", r"\tab"),
        (r"\backspace", "\b", r"\backspace"),
        (r"\formfeed", "\f", r"\formfeed"),
        (r"\return", "\r", r"\return"),
        (r"\u03A9", "Ω", r"\Ω"),
        (r"\uD83D", "\ud83d", r"\uD83D"),
        (r"\[", "[", r"\["),
        (r"\\", "\\", r"\\"),
    ],
)
def test_reader_and_printer_preserve_character_identity(source, value, printed):
    result = read_one(source)

    assert result == character.Character(value)
    assert result != value
    assert obj.lrepr(result) == printed
    assert obj.lrepr(result, human_readable=True) == value
    assert obj.lstr(result) == value
    assert read_one(obj.lrepr(result)) == result


@given(st.integers(min_value=0, max_value=0xFFFF).map(chr))
def test_character_reader_printer_fuzz_round_trip(value):
    original = character.Character(value)
    rendered = obj.lrepr(original)

    assert read_one(rendered) == original
    assert obj.lrepr(read_one(rendered)) == rendered


@given(st.text())
def test_string_sequence_fuzz_produces_distinct_utf16_characters(value):
    text = f"x{value}y"
    units = _utf16_units(text)
    expected = [character.Character(unit) for unit in units]

    assert list(runtime.to_seq(text)) == expected
    assert runtime.count(text) == len(expected)
    assert runtime.vector(text) == vec.v(*expected)
    for index, expected_character in enumerate(expected):
        assert runtime.nth(text, index) == expected_character
        assert runtime.get(text, index) == expected_character
    assert runtime.nth(text, -1, "missing") == "missing"
    assert runtime.get(text, -1, "missing") == "missing"


@given(st.integers(min_value=0, max_value=0xFFFF).map(chr))
def test_character_scalar_fuzz_never_inherits_string_collection_behavior(value):
    char_value = character.Character(value)
    string_value = str(char_value)

    assert char_value != string_value
    assert runtime.to_py(char_value) == string_value
    assert runtime._interop_arg(char_value) == string_value

    for coercion in (runtime.to_seq, runtime.to_set, runtime.vector, runtime.count):
        with pytest.raises(TypeError):
            coercion(char_value)


@given(
    value=st.text(),
    start_offset=st.integers(min_value=0, max_value=50),
    end_offset=st.integers(min_value=0, max_value=50),
)
def test_utf16_substring_fuzz_matches_code_unit_slice(value, start_offset, end_offset):
    units = _utf16_units(value)
    start = min(start_offset, len(units))
    end = min(start + end_offset, len(units))

    expected = _utf16_bytes(_utf16_slice(value, start, end))

    assert _utf16_bytes(character.utf16_substring(value, start, end)) == expected
    assert (
        character.utf16_substring(
            value, Fraction(start * 10 + 9, 10), Fraction(end * 10 + 9, 10)
        ).encode("utf-16-le", "surrogatepass")
        == expected
    )
    assert character.utf16_substring(value, math.nan) == value


def test_utf16_substring_rejects_explicit_nil_bool_and_infinite_indexes():
    with pytest.raises(TypeError):
        character.utf16_substring("abc", None)
    with pytest.raises(TypeError):
        character.utf16_substring("abc", 1, None)
    with pytest.raises(TypeError):
        character.utf16_substring("abc", True)
    with pytest.raises(TypeError):
        character.utf16_substring("abc", 1, False)
    with pytest.raises(ValueError):
        character.utf16_substring("abc", math.inf)


@given(st.text())
def test_interop_argument_fuzz_preserves_each_utf16_code_unit(value):
    """Python text sinks receive native strings without changing Lisp strings.

    Astral scalar values become two Character values at the Basilisp boundary,
    so compare encoded UTF-16 units rather than Python's scalar-value strings.
    """
    writer = io.StringIO()
    for value_unit in runtime.to_seq(value) or ():
        writer.write(runtime._interop_arg(value_unit))

    assert writer.getvalue().encode("utf-16-le", "surrogatepass") == value.encode(
        "utf-16-le", "surrogatepass"
    )


def test_character_is_distinct_and_safe_in_collections_and_python_interop():
    char_a = character.Character("a")
    characters = vec.v(char_a)

    assert char_a != "a"
    assert hash(char_a) == ord("a")
    assert lset.s(char_a, "a") == lset.s(char_a, "a")
    assert len(lset.s(char_a, "a")) == 2
    assert runtime.to_set("aa") == lset.s(char_a)
    assert runtime.to_py(char_a) == "a"
    assert runtime._interop_arg(char_a) == "a"
    # Interop call conversion is intentionally shallow; callers can opt into
    # recursive conversion with to_py when passing a Lisp collection to Python.
    assert runtime._interop_arg(characters) is characters
    assert runtime.compare(character.Character("a"), character.Character("b")) < 0


@pytest.mark.parametrize("value", ["", "ab", "😀", 1, None])
def test_character_rejects_invalid_host_values(value):
    with pytest.raises(ValueError):
        character.Character(value)
