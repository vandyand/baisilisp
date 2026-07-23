import decimal
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from basilisp.lang import equality
from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap
from basilisp.lang import reader
from basilisp.lang import set as lset
from basilisp.lang import vector as vec
from basilisp.lang.reader import SyntaxError as ReaderSyntaxError
from basilisp.lang.runtime import equals, numeric_equals


def test_numeric_families_match_clojure_equality_and_numeric_comparison():
    values = (1, 1.0, decimal.Decimal("1"), Fraction(1, 1))
    assert equals(1, Fraction(1, 1))
    for left_index, left in enumerate(values):
        for right_index, right in enumerate(values):
            assert equals(left, right) is (
                left_index == right_index or {left_index, right_index} == {0, 3}
            )
            assert numeric_equals(left, right)


@given(st.integers(min_value=-(1 << 52), max_value=1 << 52))
def test_numeric_key_wrappers_preserve_family_distinctions_under_fuzz(value):
    members = (value, float(value), decimal.Decimal(value), Fraction(value, 1))
    result_map = lmap.hash_map(
        members[0],
        "integer",
        members[1],
        "floating",
        members[2],
        "decimal",
        members[3],
        "integer-replaced",
    )
    result_set = lset.s(*members)

    assert len(result_map) == 3
    assert result_map[value] == "integer-replaced"
    assert result_map[float(value)] == "floating"
    assert result_map[decimal.Decimal(value)] == "decimal"
    assert len(result_set) == 3
    assert all(member in result_set for member in members)


@given(st.integers(min_value=-(1 << 40), max_value=1 << 40))
def test_numeric_collections_keep_equality_and_hashing_in_lockstep(value):
    integer = value
    floating = float(value)
    decimal_value = decimal.Decimal(value)

    assert vec.v(integer) != vec.v(floating)
    assert lmap.hash_map(integer, "value") != lmap.hash_map(floating, "value")
    assert lset.s(integer) != lset.s(decimal_value)


def test_numeric_key_mutation_and_reader_equivalent_operations_are_family_safe():
    initial = lmap.hash_map(1, "integer")
    updated = initial.assoc(1.0, "floating").assoc(decimal.Decimal("1"), "decimal")
    assert len(updated) == 3
    assert updated.dissoc(1.0) == lmap.hash_map(
        1, "integer", decimal.Decimal("1"), "decimal"
    )

    initial_set = lset.s(1)
    updated_set = initial_set.cons(1.0, decimal.Decimal("1"))
    assert len(updated_set) == 3
    assert updated_set.disj(1.0) == lset.s(1, decimal.Decimal("1"))


def test_equivalence_keys_are_private_and_unwrap_to_original_values():
    wrapped = equality.key(decimal.Decimal("1.00"))
    assert equality.unkey(wrapped) == decimal.Decimal("1.00")
    assert equality.key(1) != equality.key(1.0)


def test_reader_preserves_numeric_key_families_but_rejects_true_duplicates():
    result_map = next(reader.read_str("{1 :integer 1.0 :floating 1M :decimal}"))
    result_set = next(reader.read_str("#{1 1.0 1M}"))
    assert len(result_map) == len(result_set) == 3
    assert result_map[1] == kw.keyword("integer")
    assert result_map[1.0] == kw.keyword("floating")
    assert result_map[decimal.Decimal("1")] == kw.keyword("decimal")
    with pytest.raises(ReaderSyntaxError):
        next(reader.read_str("{1 :integer 1/1 :duplicate}"))
    with pytest.raises(ReaderSyntaxError):
        next(reader.read_str("#{1 1/1}"))


def test_non_reflexive_nan_and_signed_zero_match_clojure_collection_behavior():
    nan = float("nan")
    nan_map = lmap.hash_map(nan, "first", nan, "second")

    assert not equals(nan, nan)
    assert nan not in nan_map
    assert nan_map.val_at(nan, "missing") == "missing"
    assert len(nan_map) == 2
    assert nan not in lset.s(nan)

    assert equals(0.0, -0.0)
    assert len(lmap.hash_map(0.0, "positive", -0.0, "negative")) == 1
    assert len(lset.s(0.0, -0.0)) == 1
