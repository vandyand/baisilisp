import decimal
from fractions import Fraction

from hypothesis import given
from hypothesis import strategies as st

from basilisp.lang import character
from basilisp.lang import keyword as kw
from basilisp.lang import list as llist
from basilisp.lang import map as lmap
from basilisp.lang import set as lset
from basilisp.lang import symbol as sym
from basilisp.lang import vector as vec
from basilisp.lang.hashing import clojure_hash


def test_portable_scalar_hashes_match_clojure_reference_values():
    values = [
        (None, 0),
        (True, 1231),
        (False, 1237),
        (1, 1392991556),
        (-1, 1651860712),
        (Fraction(1, 2), 3),
        (1.0, 1072693248),
        (decimal.Decimal("1.00"), 31),
        ("abc", 74834163),
        (character.character("a"), 97),
        (kw.keyword("key", "hash"), -1519269477),
        (sym.symbol("key", "hash"), 121262050),
    ]
    assert [(clojure_hash(value), expected) for value, expected in values] == [
        (expected, expected) for _, expected in values
    ]


def test_portable_collection_hashes_match_clojure_reference_values():
    values = [
        (vec.v(1, 2, 3), 736442005),
        (llist.l(1, 2, 3), 736442005),
        (lmap.hash_map(1, kw.keyword("one"), 2, kw.keyword("two")), -1594271398),
        (lset.s(1, 2, 3), 439094965),
        (vec.v(), -2017569654),
        (lmap.hash_map(), -15128758),
        (lset.s(), -15128758),
    ]
    assert [(clojure_hash(value), expected) for value, expected in values] == [
        (expected, expected) for _, expected in values
    ]
    assert all(hash(value) == expected for value, expected in values)


@given(st.integers(min_value=-(1 << 256), max_value=1 << 256))
def test_integral_hashes_are_stable_and_match_denominator_one_ratios(value):
    ratio = Fraction(value, 1)
    assert clojure_hash(value) == clojure_hash(value)
    assert clojure_hash(value) == clojure_hash(ratio)


@given(
    st.integers(min_value=-(1 << 120), max_value=1 << 120),
    st.integers(min_value=1, max_value=1 << 80),
)
def test_ratio_hashes_are_stable_for_large_exact_values(numerator, denominator):
    ratio = Fraction(numerator, denominator)
    assert clojure_hash(ratio) == clojure_hash(ratio)
    assert -(1 << 31) <= clojure_hash(ratio) < (1 << 31)


@given(st.integers(min_value=-(1 << 120), max_value=1 << 120))
def test_decimal_trailing_zero_normalization_preserves_hash(value):
    unscaled = decimal.Decimal(value)
    sign, digits, _ = unscaled.as_tuple()
    scaled = decimal.Decimal((sign, digits, -6))
    equivalent = decimal.Decimal((sign, digits + (0, 0, 0, 0), -10))
    assert scaled == equivalent
    assert clojure_hash(scaled) == clojure_hash(equivalent)


@given(st.lists(st.integers(min_value=-(1 << 50), max_value=1 << 50), max_size=40))
def test_sequential_and_unordered_collection_hash_properties(values):
    assert clojure_hash(vec.vector(values)) == clojure_hash(llist.list(values))
    assert hash(vec.vector(values)) == clojure_hash(vec.vector(values))

    forward_set = lset.set(values)
    reverse_set = lset.set(reversed(values))
    assert clojure_hash(forward_set) == clojure_hash(reverse_set)


@given(st.text(alphabet=["a", "Z", "😀", "\ud800", "\udc00"], max_size=50))
def test_string_hashes_cover_utf16_and_unpaired_surrogates(value):
    assert clojure_hash(value) == clojure_hash(value)
    assert -(1 << 31) <= clojure_hash(value) < (1 << 31)


def test_signed_zero_nan_and_nested_collection_hashes_are_deterministic():
    assert clojure_hash(0.0) == clojure_hash(-0.0) == 0
    assert clojure_hash(float("nan")) == 2146959360
    assert (
        clojure_hash(
            vec.v(1, lmap.hash_map(kw.keyword("a"), vec.v(2, 3)), lset.s(4, 5))
        )
        == 133066916
    )
    assert (
        clojure_hash(
            lmap.hash_map(kw.keyword("a"), vec.v(1, 2), kw.keyword("b"), lset.s(3, 4))
        )
        == 1218125913
    )
