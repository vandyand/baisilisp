from concurrent.futures import ThreadPoolExecutor

import pytest
from hypothesis import given
from hypothesis import strategies as st

from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap


def _definition() -> lmap.StructDefinition:
    return lmap.struct_definition((kw.keyword("a"), kw.keyword("b")))


@given(
    a=st.integers(min_value=-(1 << 31), max_value=(1 << 31) - 1),
    b=st.integers(min_value=-(1 << 31), max_value=(1 << 31) - 1),
    extension=st.integers(min_value=-(1 << 31), max_value=(1 << 31) - 1),
)
def test_struct_maps_preserve_fixed_slots_under_fuzzing(a: int, b: int, extension: int):
    definition = _definition()
    record = lmap.struct_map(
        definition,
        kw.keyword("a"),
        a,
        kw.keyword("b"),
        b,
        kw.keyword("extra"),
        extension,
    )
    access_a = lmap.accessor(definition, kw.keyword("a"))

    assert list(record.items()) == [
        (kw.keyword("a"), a),
        (kw.keyword("b"), b),
        (kw.keyword("extra"), extension),
    ]
    assert access_a(record) == a
    assert record == lmap.map(
        {kw.keyword("a"): a, kw.keyword("b"): b, kw.keyword("extra"): extension}
    )
    assert hash(record) == hash(
        lmap.map(
            {kw.keyword("a"): a, kw.keyword("b"): b, kw.keyword("extra"): extension}
        )
    )
    assert record.dissoc(kw.keyword("extra")) == lmap.struct(definition, a, b)
    with pytest.raises(RuntimeError, match="Can't remove struct key"):
        record.dissoc(kw.keyword("a"))


def test_accessors_reject_different_structure_definitions_and_plain_maps():
    definition = _definition()
    other_definition = _definition()
    access_a = lmap.accessor(definition, kw.keyword("a"))

    with pytest.raises(RuntimeError, match="Accessor/struct mismatch"):
        access_a(lmap.struct(other_definition, 1, 2))
    with pytest.raises(RuntimeError, match="Accessor/struct mismatch"):
        access_a(lmap.map({kw.keyword("a"): 1, kw.keyword("b"): 2}))
    with pytest.raises(ValueError, match="Not a key of struct"):
        lmap.accessor(definition, kw.keyword("missing"))
    with pytest.raises(ValueError, match="No value supplied"):
        lmap.struct_map(definition, kw.keyword("a"))
    with pytest.raises(TypeError, match="do not support transient"):
        lmap.struct(definition, 1, 2).to_transient()


def test_struct_maps_and_accessors_are_safe_under_parallel_persistent_updates():
    definition = _definition()
    access_a = lmap.accessor(definition, kw.keyword("a"))

    def build_and_read(value: int) -> tuple[int, int, int]:
        record = lmap.struct(definition, value, value + 1).assoc(
            kw.keyword("extra"), -value
        )
        return access_a(record), record[kw.keyword("b")], record[kw.keyword("extra")]

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(build_and_read, range(256)))

    assert results == [(value, value + 1, -value) for value in range(256)]
