import importlib
import itertools
import math
from functools import cache

from hypothesis import given, settings
from hypothesis import strategies as st

from basilisp import main
from basilisp.lang import runtime
from basilisp.lang import symbol as sym


@cache
def _combinatorics_fn(name):
    main.init()
    importlib.import_module("basilisp.math.combinatorics")
    var = runtime.Var.find(sym.symbol(name, ns="basilisp.math.combinatorics"))
    assert var is not None
    return var.value


def _unique_in_order(values):
    seen = set()
    return [value for value in values if not (value in seen or seen.add(value))]


@settings(deadline=None, max_examples=60)
@given(
    items=st.lists(st.integers(-3, 3), max_size=7),
    data=st.data(),
)
def test_combinations_match_unique_itertools_reference(items, data):
    size = data.draw(st.integers(min_value=0, max_value=len(items)))
    actual = [tuple(value) for value in _combinatorics_fn("combinations")(items, size)]
    distinct_items = _unique_in_order(items)
    expected = [
        values
        for values in itertools.combinations_with_replacement(distinct_items, size)
        if all(values.count(item) <= items.count(item) for item in distinct_items)
    ]

    assert expected == actual
    assert len(actual) == _combinatorics_fn("count-combinations")(items, size)
    assert actual == [
        tuple(_combinatorics_fn("nth-combination")(items, size, index))
        for index in range(len(actual))
    ]


@settings(deadline=None, max_examples=60)
@given(st.lists(st.integers(-2, 2), max_size=5))
def test_permutations_and_direct_index_operations_match_reference(items):
    actual = [tuple(value) for value in _combinatorics_fn("permutations")(items)]
    expected = _unique_in_order(itertools.permutations(items))

    assert set(expected) == set(actual)
    assert len(expected) == len(actual)
    assert math.factorial(len(items)) // math.prod(
        math.factorial(items.count(item)) for item in set(items)
    ) == _combinatorics_fn("count-permutations")(items)
    assert actual == [
        tuple(_combinatorics_fn("nth-permutation")(items, index))
        for index in range(len(actual))
    ]
    assert actual == [
        tuple(value) for value in _combinatorics_fn("drop-permutations")(items, 0)
    ]

    sorted_actual = [
        tuple(value) for value in _combinatorics_fn("permutations")(sorted(items))
    ]
    assert list(range(len(sorted_actual))) == [
        _combinatorics_fn("permutation-index")(value) for value in sorted_actual
    ]


@settings(deadline=None, max_examples=60)
@given(st.lists(st.integers(-3, 3), max_size=6))
def test_subsets_and_selections_have_their_counted_public_contract(items):
    subsets = [tuple(value) for value in _combinatorics_fn("subsets")(items)]

    assert len(subsets) == _combinatorics_fn("count-subsets")(items)
    assert subsets == [
        tuple(_combinatorics_fn("nth-subset")(items, index))
        for index in range(len(subsets))
    ]

    selections = [
        tuple(value) for value in (_combinatorics_fn("selections")(items, 2) or ())
    ]
    assert (len(items) ** 2 if items else 0) == len(selections)
    assert all(len(selection) == 2 for selection in selections)
