import io

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
