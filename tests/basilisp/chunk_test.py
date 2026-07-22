from concurrent.futures import ThreadPoolExecutor

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from basilisp.lang import chunk
from basilisp.lang import range as lrange
from basilisp.lang import runtime
from basilisp.lang import symbol as sym
from basilisp.lang import vector as vec
from basilisp.lang.interfaces import ISeqable


def _items(value) -> list[object]:
    return [runtime.nth(value, index) for index in range(runtime.count(value))]


def _core_fn(name: str):
    core = runtime.Namespace.get_or_create(runtime.CORE_NS_SYM)
    value = core.find(sym.symbol(name))
    assert value is not None
    return value.value


def test_chunk_buffer_is_bounded_one_shot_and_chunks_are_not_sequences():
    buffer = chunk.chunk_buffer(2)
    assert chunk.chunk_append(buffer, "a") is None
    assert chunk.chunk_append(buffer, "b") is None
    with pytest.raises(IndexError, match="capacity"):
        chunk.chunk_append(buffer, "overflow")

    result = chunk.chunk(buffer)
    assert ["a", "b"] == _items(result)
    assert result
    assert not isinstance(result, ISeqable)
    with pytest.raises(TypeError):
        runtime.to_seq(result)
    with pytest.raises(RuntimeError, match="already"):
        chunk.chunk(buffer)
    with pytest.raises(RuntimeError, match="already"):
        chunk.chunk_append(buffer, "later")


def test_chunk_cons_preserves_partial_chunk_and_tail_boundaries():
    buffer = chunk.chunk_buffer(3)
    for value in (1, 2, 3):
        chunk.chunk_append(buffer, value)
    seq = chunk.chunk_cons(chunk.chunk(buffer), runtime.to_seq([4, 5]))

    assert chunk.is_chunked_seq(seq)
    assert [1, 2, 3, 4, 5] == list(seq)
    assert [1, 2, 3] == _items(chunk.chunk_first(seq))
    assert [2, 3] == _items(chunk.chunk_first(seq.rest))
    assert [4, 5] == list(chunk.chunk_rest(seq))
    assert [4, 5] == list(chunk.chunk_next(seq))
    assert [4, 5] == list(seq.rest.rest.rest)


def test_empty_chunk_cons_returns_the_original_tail_and_nonchunks_fail_clearly():
    empty_chunk = chunk.chunk(chunk.chunk_buffer(0))
    tail = runtime.to_seq(["tail"])
    assert tail is chunk.chunk_cons(empty_chunk, tail)

    for fn in (chunk.chunk_first, chunk.chunk_rest, chunk.chunk_next):
        with pytest.raises(TypeError, match="chunked sequence"):
            fn(runtime.to_seq([1]))
    with pytest.raises(TypeError, match="ArrayChunk"):
        chunk.chunk_cons(runtime.to_seq([1]), tail)

    for capacity in (True, 1.0, "1"):
        with pytest.raises(TypeError, match="integer"):
            chunk.chunk_buffer(capacity)


@given(
    values=st.lists(st.integers(), max_size=96),
    start=st.integers(min_value=0, max_value=96),
    width=st.integers(min_value=0, max_value=96),
)
@settings(max_examples=200, deadline=None)
def test_array_chunk_fuzzes_all_valid_slices(values: list[int], start: int, width: int):
    start = min(start, len(values))
    end = min(start + width, len(values))
    result = chunk.array_chunk(None, values, start, end)

    assert values[start:end] == _items(result)
    assert bool(result)
    assert runtime.nth(result, len(result), "missing") == "missing"
    with pytest.raises(IndexError):
        runtime.nth(result, len(result))


@pytest.mark.parametrize(
    "array,offset,end",
    [
        ((), -1, 0),
        ((), 0, 1),
        ((1,), 1, 0),
        ((1,), 0, 2),
    ],
)
def test_array_chunk_rejects_invalid_bounds(array, offset, end):
    with pytest.raises(IndexError, match="Invalid ArrayChunk bounds"):
        chunk.array_chunk(None, array, offset, end)


def test_vector_sequences_are_chunked_at_clojure_sized_boundaries():
    source = vec.vector(range(70))
    seq = source.seq()

    assert chunk.is_chunked_seq(seq)
    assert list(range(32)) == _items(chunk.chunk_first(seq))
    assert list(range(1, 32)) == _items(chunk.chunk_first(seq.rest))
    assert list(range(32, 64)) == _items(chunk.chunk_first(chunk.chunk_next(seq)))
    assert list(range(64, 70)) == _items(
        chunk.chunk_first(chunk.chunk_rest(chunk.chunk_next(seq)))
    )
    assert list(range(70)) == list(seq)


@given(values=st.lists(st.integers(), max_size=96))
@settings(max_examples=100, deadline=None)
def test_chunk_aware_lazy_transforms_fuzz_vector_inputs(values: list[int]):
    source = vec.vector(values)
    mapped = runtime.to_seq(_core_fn("map")(lambda value: value + 1, source))
    filtered = runtime.to_seq(_core_fn("filter")(lambda value: value % 2 == 0, source))
    kept = runtime.to_seq(
        _core_fn("keep")(lambda value: value if value % 3 else None, source)
    )
    concatenated = runtime.to_seq(_core_fn("concat")(source, vec.vector([99])))

    assert [value + 1 for value in values] == ([] if mapped is None else list(mapped))
    assert bool(values) is chunk.is_chunked_seq(mapped)
    assert [value for value in values if value % 2 == 0] == (
        [] if filtered is None else list(filtered)
    )
    assert [value for value in values if value % 3] == (
        [] if kept is None else list(kept)
    )
    assert [*values, 99] == list(concatenated)
    assert chunk.is_chunked_seq(concatenated)


def test_realizing_one_mapped_vector_item_evaluates_exactly_its_chunk():
    seen: list[int] = []
    mapped = _core_fn("map")(
        lambda value: seen.append(value) or value, vec.vector(range(40))
    )

    assert runtime.first(mapped) == 0
    assert list(range(32)) == seen


def test_range_sequences_are_chunked_at_clojure_sized_boundaries():
    seq = lrange.range(0, 70)

    assert chunk.is_chunked_seq(seq)
    assert list(range(32)) == _items(chunk.chunk_first(seq))
    assert list(range(1, 32)) == _items(chunk.chunk_first(seq.rest))
    assert list(range(32, 64)) == _items(chunk.chunk_first(chunk.chunk_next(seq)))
    assert list(range(64, 70)) == _items(
        chunk.chunk_first(chunk.chunk_rest(chunk.chunk_next(seq)))
    )
    assert list(range(70)) == list(seq)


def test_range_chunks_support_negative_and_infinite_ranges():
    negative = lrange.range(10, 0, -3)
    zero_step = lrange.range(1, 10, 0)
    infinite = lrange.range()

    assert [10, 7, 4, 1] == list(negative)
    assert [10, 7, 4, 1] == _items(chunk.chunk_first(negative))
    assert [1, 1, 1, 1, 1] == [runtime.nth(zero_step, index) for index in range(5)]
    assert not chunk.is_chunked_seq(zero_step)
    assert list(range(32)) == _items(chunk.chunk_first(infinite))
    assert list(range(1, 32)) == _items(chunk.chunk_first(infinite.rest))


def test_realizing_one_mapped_range_item_evaluates_exactly_its_chunk():
    seen: list[int] = []
    mapped = _core_fn("map")(
        lambda value: seen.append(value) or value, lrange.range(40)
    )

    assert runtime.first(mapped) == 0
    assert list(range(32)) == seen


def test_chunk_construction_is_independent_under_parallel_stress():
    def make_chunk(seed: int) -> tuple[list[int], list[int]]:
        buffer = chunk.chunk_buffer(8)
        values = list(range(seed, seed + 8))
        for value in values:
            chunk.chunk_append(buffer, value)
        seq = chunk.chunk_cons(chunk.chunk(buffer), None)
        assert seq is not None
        return _items(chunk.chunk_first(seq)), list(seq)

    with ThreadPoolExecutor(max_workers=16) as pool:
        observed = list(pool.map(make_chunk, range(256)))

    for seed, (first_chunk, seq_values) in enumerate(observed):
        expected = list(range(seed, seed + 8))
        assert expected == first_chunk == seq_values
