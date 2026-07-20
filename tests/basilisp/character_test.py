import pytest
from hypothesis import given
from hypothesis import strategies as st

from basilisp.lang import character
from basilisp.lang import obj
from basilisp.lang import reader
from basilisp.lang import runtime
from basilisp.lang import set as lset
from basilisp.lang import vector as vec


def read_one(source: str):
    return next(reader.read_str(source))


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


@given(st.characters(blacklist_categories=("Cs",)))
def test_character_reader_printer_fuzz_round_trip(value):
    original = character.Character(value)
    rendered = obj.lrepr(original)

    assert read_one(rendered) == original
    assert obj.lrepr(read_one(rendered)) == rendered


@given(st.characters(blacklist_categories=("Cs",)))
def test_string_sequence_fuzz_produces_distinct_characters(value):
    text = f"x{value}y"

    assert list(runtime.to_seq(text)) == [
        character.Character("x"),
        character.Character(value),
        character.Character("y"),
    ]
    assert runtime.nth(text, 1) == character.Character(value)
    assert runtime.get(text, 1) == character.Character(value)
    assert runtime.vector(text) == vec.v(
        character.Character("x"), character.Character(value), character.Character("y")
    )


def test_character_is_distinct_and_safe_in_collections_and_python_interop():
    char_a = character.Character("a")

    assert char_a != "a"
    assert hash(char_a) == ord("a")
    assert lset.s(char_a, "a") == lset.s(char_a, "a")
    assert len(lset.s(char_a, "a")) == 2
    assert runtime.to_set("aa") == lset.s(char_a)
    assert runtime.to_py(char_a) == "a"
    assert runtime.compare(character.Character("a"), character.Character("b")) < 0


@pytest.mark.parametrize("value", ["", "ab", 1, None])
def test_character_rejects_invalid_host_values(value):
    with pytest.raises(ValueError):
        character.Character(value)
