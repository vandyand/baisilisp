from concurrent.futures import ThreadPoolExecutor

import pytest
from hypothesis import given
from hypothesis import strategies as st

from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap
from basilisp.lang import runtime
from basilisp.lang import symbol as sym
from basilisp.lang import vector as vec


def _seq_to_map():
    core = runtime.Namespace.get_or_create(runtime.CORE_NS_SYM)
    return core.find(sym.symbol("seq-to-map-for-destructuring")).value


_VALUES = st.one_of(st.integers(), st.text(), st.builds(kw.keyword, st.text()))


@given(st.lists(st.tuples(_VALUES, _VALUES), min_size=1, max_size=64))
def test_seq_to_map_builds_maps_from_even_flat_sequences(pairs):
    flat = [value for pair in pairs for value in pair]

    assert _seq_to_map()(vec.vector(flat)) == lmap.map(dict(pairs))


@given(_VALUES)
def test_seq_to_map_returns_a_singleton_value_unchanged(value):
    assert _seq_to_map()(vec.vector((value,))) == value


@given(
    st.lists(_VALUES, min_size=3, max_size=65).filter(lambda values: len(values) % 2)
)
def test_seq_to_map_rejects_odd_sequences_with_more_than_one_value(values):
    with pytest.raises(ValueError):
        _seq_to_map()(vec.vector(values))


def test_seq_to_map_is_safe_under_parallel_persistent_inputs():
    def convert(value: int):
        return _seq_to_map()(vec.vector((kw.keyword("value"), value)))

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(convert, range(256)))

    assert results == [lmap.map({kw.keyword("value"): value}) for value in range(256)]
