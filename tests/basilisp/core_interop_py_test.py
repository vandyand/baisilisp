import dataclasses
import traceback
import urllib.parse

import pytest
from hypothesis import given
from hypothesis import strategies as st

from basilisp.core_interop import (
    bean,
    enumeration_seq,
    stack_trace_element_to_vec,
    throwable_to_map,
    uri_qmark,
)
from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap
from basilisp.lang.exception import ExceptionInfo


@dataclasses.dataclass
class Point:
    x: int
    y: int

    @property
    def magnitude(self):
        return self.x * self.x + self.y * self.y

    @property
    def broken(self):
        raise RuntimeError("properties may fail")


class Enumeration:
    def __init__(self, values):
        self.values = list(values)
        self.index = 0
        self.next_calls = 0

    def hasMoreElements(self):
        return self.index < len(self.values)

    def nextElement(self):
        self.next_calls += 1
        value = self.values[self.index]
        self.index += 1
        return value


def test_bean_supports_dataclasses_properties_and_mapping_keywords():
    result = bean(Point(3, 4))
    assert result[kw.keyword("x")] == 3
    assert result[kw.keyword("y")] == 4
    assert result[kw.keyword("magnitude")] == 25
    assert kw.keyword("broken") not in result
    assert result[kw.keyword("class")] is Point

    key = kw.keyword("already-a-keyword")
    assert bean({key: 1})[key] == 1


def test_enumeration_seq_is_lazy_and_accepts_java_style_enumerations():
    source = Enumeration([1, 2, 3])
    sequence = enumeration_seq(source)
    iterator = iter(sequence)

    assert source.next_calls == 0
    assert next(iterator) == 1
    assert source.next_calls == 1
    assert list(iterator) == [2, 3]
    assert source.next_calls == 3
    with pytest.raises(TypeError, match="iterable or enumeration"):
        enumeration_seq(42)


@given(st.lists(st.integers(), max_size=60))
def test_enumeration_seq_matches_iterable_oracle(values):
    assert list(enumeration_seq(iter(values))) == values


def test_uri_predicate_accepts_only_python_uri_values():
    parsed = urllib.parse.urlparse("https://example.test/path?q=1#fragment")
    split = urllib.parse.urlsplit("mailto:user@example.test")
    assert uri_qmark(parsed)
    assert uri_qmark(split)
    assert not uri_qmark(parsed.geturl())
    assert not uri_qmark({"scheme": "https"})


def test_trace_and_throwable_map_match_clojure_shape_for_python_exceptions():
    try:
        try:
            raise ExceptionInfo("inner", lmap.map({kw.keyword("detail"): 1}))
        except ExceptionInfo as inner:
            raise RuntimeError("outer") from inner
    except RuntimeError as outer:
        mapped = throwable_to_map(outer)

    assert str(mapped[kw.keyword("cause")]) == "inner {:detail 1}"
    assert dict(mapped[kw.keyword("data")].items()) == {kw.keyword("detail"): 1}
    assert len(mapped[kw.keyword("via")]) == 2
    outer_via, inner_via = mapped[kw.keyword("via")]
    assert str(outer_via[kw.keyword("message")]) == "outer"
    assert dict(inner_via[kw.keyword("data")].items()) == {kw.keyword("detail"): 1}
    assert len(mapped[kw.keyword("trace")][0]) == 4
    assert len(outer_via[kw.keyword("at")]) == 4


def test_stack_trace_element_conversion_accepts_summary_traceback_and_tuple():
    try:
        raise ValueError("frame")
    except ValueError as error:
        summary = traceback.extract_tb(error.__traceback__)[-1]
        trace = error.__traceback__

    assert len(stack_trace_element_to_vec(summary)) == 4
    assert len(stack_trace_element_to_vec(trace)) == 4
    assert tuple(stack_trace_element_to_vec(("module", "method", "file.py", 7))) == (
        "module",
        "method",
        "file.py",
        7,
    )
    with pytest.raises(TypeError, match="traceback frame"):
        stack_trace_element_to_vec("not-a-frame")
