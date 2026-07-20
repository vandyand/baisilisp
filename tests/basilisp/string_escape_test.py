import importlib

import pytest
from hypothesis import given
from hypothesis import strategies as st

from basilisp.lang import runtime
from basilisp.lang import symbol as sym


def _escape():
    importlib.import_module("basilisp.string")
    var = runtime.Var.find(sym.symbol("escape", ns="basilisp.string"))
    assert var is not None
    return var.value


@given(
    s=st.text(max_size=100),
    cmap=st.dictionaries(st.characters(), st.text(max_size=12), max_size=32),
)
def test_escape_matches_per_character_replacement_model(s, cmap):
    escape = _escape()

    assert escape(s, cmap) == "".join(cmap.get(ch, ch) for ch in s)


def test_escape_retains_nil_mappings_and_stringifies_mapped_values():
    escape = _escape()

    assert escape("abca", {"a": None, "b": 3, "c": False}) == "a3falsea"


@pytest.mark.parametrize("value", [None, 1, object()])
def test_escape_rejects_non_string_inputs(value):
    with pytest.raises(TypeError):
        _escape()(value, {})
