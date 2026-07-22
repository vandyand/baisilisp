from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap
from basilisp.lang import reduced, runtime
from basilisp.lang import symbol as sym


def _core_fn(name: str):
    var = runtime.Var.find(sym.symbol(name, ns="basilisp.core"))
    assert var is not None, name
    return var.value


class CountingIterator(Iterator[int]):
    """A one-shot iterator that exposes exactly how far a terminal op advanced it."""

    def __init__(self, values: list[int]):
        self._values = values
        self.next_calls = 0

    def __iter__(self) -> CountingIterator:
        return self

    def __next__(self) -> int:
        if self.next_calls >= len(self._values):
            raise StopIteration
        value = self._values[self.next_calls]
        self.next_calls += 1
        return value


class FakeCursor:
    """Minimal DB-API cursor double that detects unwanted eager row reads."""

    def __init__(self, description: Any, rows: list[tuple[Any, ...]]):
        self.description = description
        self._rows = iter(rows)
        self.fetches = 0

    def fetchone(self):
        self.fetches += 1
        return next(self._rows, None)


@st.composite
def _cursor_cases(draw):
    labels = draw(
        st.lists(
            st.from_regex(r"[A-Za-z][A-Za-z0-9_]{0,10}", fullmatch=True),
            unique_by=str.lower,
            max_size=8,
        )
    )
    rows = draw(
        st.lists(
            st.lists(
                st.one_of(st.integers(-1000, 1000), st.text(max_size=12), st.none()),
                min_size=len(labels),
                max_size=len(labels),
            ).map(tuple),
            max_size=24,
        )
    )
    return labels, rows


@given(
    values=st.lists(
        st.integers(min_value=-100, max_value=100), min_size=1, max_size=80
    ),
    stop_index=st.integers(min_value=0, max_value=79),
)
@settings(max_examples=150, deadline=None)
def test_stream_reduce_fuzzes_early_termination_without_overconsumption(
    values: list[int], stop_index: int
):
    stop_index %= len(values)
    stream = CountingIterator(values)
    seen: list[int] = []

    def reducer(acc: int, value: int):
        seen.append(value)
        result = acc + value
        return reduced.Reduced(result) if len(seen) - 1 == stop_index else result

    result = _core_fn("stream-reduce!")(reducer, 0, stream)
    assert result == sum(values[: stop_index + 1])
    assert seen == values[: stop_index + 1]
    assert stream.next_calls == stop_index + 1
    if stop_index + 1 < len(values):
        assert next(stream) == values[stop_index + 1]
    else:
        with pytest.raises(StopIteration):
            next(stream)


def test_stream_seq_and_resultset_are_lazy_and_preserve_row_shape():
    stream = CountingIterator([1, 2, 3])
    seq = _core_fn("stream-seq!")(stream)
    assert stream.next_calls == 0
    assert next(iter(seq)) == 1
    assert stream.next_calls == 1

    cursor = FakeCursor(
        (("ID", None), ("Display_Name", None)), [(1, "Ada"), (2, "Grace")]
    )
    rows = _core_fn("resultset-seq")(cursor)
    assert cursor.fetches == 0
    assert next(iter(rows)) == lmap.map(
        {kw.keyword("id"): 1, kw.keyword("display_name"): "Ada"}
    )
    assert cursor.fetches == 1
    assert list(rows) == [
        lmap.map({kw.keyword("id"): 1, kw.keyword("display_name"): "Ada"}),
        lmap.map({kw.keyword("id"): 2, kw.keyword("display_name"): "Grace"}),
    ]


def test_resultset_rejects_duplicate_labels_eagerly_without_fetching_rows():
    cursor = FakeCursor((("ID", None), ("id", None)), [(1, 2)])
    with pytest.raises(ValueError, match="unique column labels"):
        _core_fn("resultset-seq")(cursor)
    assert cursor.fetches == 0


@given(_cursor_cases())
@settings(max_examples=120, deadline=None)
def test_resultset_fuzzes_dbapi_row_projection(
    case: tuple[list[str], list[tuple[Any, ...]]],
):
    labels, values = case
    cursor = FakeCursor(tuple((label, None) for label in labels), values)
    actual = list(_core_fn("resultset-seq")(cursor))
    expected = [
        lmap.map(
            {kw.keyword(label.lower()): value for label, value in zip(labels, row)}
        )
        for row in values
    ]
    assert actual == expected
    # Result exhaustion performs at most the expected terminal fetch, never a row prefetch.
    assert cursor.fetches == len(values) + 1


def test_resultset_rejects_unexecuted_cursor_and_propagates_fetch_failure_lazily():
    with pytest.raises(ValueError, match="executed DB-API cursor"):
        _core_fn("resultset-seq")(FakeCursor(None, []))

    class ExplodingCursor(FakeCursor):
        def fetchone(self):
            self.fetches += 1
            raise RuntimeError("cursor read failed")

    cursor = ExplodingCursor((("id", None),), [])
    rows = _core_fn("resultset-seq")(cursor)
    assert cursor.fetches == 0
    with pytest.raises(RuntimeError, match="cursor read failed"):
        next(iter(rows))
    assert cursor.fetches == 1
