import importlib
from functools import cache

from hypothesis import given, settings
from hypothesis import strategies as st

from basilisp import main
from basilisp.lang import runtime
from basilisp.lang import symbol as sym


@cache
def _medley_fn(name):
    main.init()
    importlib.import_module("medley.core")
    var = runtime.Var.find(sym.symbol(name, ns="medley.core"))
    assert var is not None
    return var.value


@settings(deadline=None, max_examples=80)
@given(st.lists(st.integers(-10, 10), max_size=30))
def test_window_matches_python_sliding_prefix_oracle(values):
    size = 3
    actual = [tuple(value) for value in _medley_fn("window")(size, values)]
    expected = [
        tuple(values[max(0, index - size + 1) : index + 1])
        for index in range(len(values))
    ]

    assert expected == actual


@settings(deadline=None, max_examples=80)
@given(st.lists(st.integers(-5, 5), max_size=30))
def test_distinct_and_dedupe_preserve_their_generated_invariants(values):
    distinct = list(_medley_fn("distinct-by")(lambda value: abs(value), values))
    deduped = list(_medley_fn("dedupe-by")(abs, values))

    assert len({abs(value) for value in distinct}) == len(distinct)
    assert all(abs(left) != abs(right) for left, right in zip(deduped, deduped[1:]))
    assert all(value in values for value in distinct)
    assert all(value in values for value in deduped)


@settings(deadline=None, max_examples=80)
@given(
    values=st.lists(st.integers(-10, 10), max_size=30),
    item=st.integers(-10, 10),
    data=st.data(),
)
def test_nth_edits_and_index_of_match_python_oracles(values, item, data):
    index = data.draw(st.integers(min_value=0, max_value=len(values)))

    assert values[:index] + [item] + values[index:] == list(
        _medley_fn("insert-nth")(index, item, values)
    )
    expected_remove = values[:index] + values[index + 1 :]
    assert expected_remove == list(_medley_fn("remove-nth")(index, values))
    # Medley's upstream contract treats replacement at the end as an append.
    expected_replace = values[:index] + [item] + values[index + 1 :]
    assert expected_replace == list(_medley_fn("replace-nth")(index, item, values))
    assert (values.index(item) if item in values else None) == _medley_fn("index-of")(
        values, item
    )


@given(st.one_of(st.none(), st.booleans(), st.integers(), st.text()))
def test_boolean_predicate_matches_python_bool_type(value):
    assert isinstance(value, bool) is _medley_fn("boolean?")(value)
