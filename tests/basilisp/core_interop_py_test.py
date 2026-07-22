import dataclasses
import importlib
import os
import pathlib
import sys
import threading
import traceback
import urllib.parse
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from hypothesis import given
from hypothesis import strategies as st

from basilisp.core_interop import (
    PrintWriterOn,
    add_classpath,
    bean,
    enumeration_seq,
    print_writer_on,
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


def test_print_writer_on_flush_close_and_autoflush_contract():
    flushed: list[str] = []
    closed: list[None] = []
    writer = print_writer_on(flushed.append, lambda: closed.append(None), True)

    assert isinstance(writer, PrintWriterOn)
    assert writer.write("ab") is None
    assert writer.print("c") is None
    assert writer.println("d") is None
    assert flushed == [f"abcd{os.linesep}"]
    assert writer.write(65) is None
    assert writer.write(["e", "f", "g"], 1, 2) is None
    assert writer.flush() is None
    assert flushed == [f"abcd{os.linesep}", "Afg"]
    assert writer.check_error() is False
    assert writer.close() is None
    assert writer.close() is None
    assert closed == [None]
    assert writer.closed
    with pytest.raises(ValueError, match="closed"):
        writer.write("later")


@given(st.lists(st.text(max_size=12), max_size=80))
def test_print_writer_on_matches_buffering_oracle(parts: list[str]):
    flushed: list[str] = []
    writer = print_writer_on(flushed.append)
    expected = ""
    for index, part in enumerate(parts):
        writer.write(part)
        expected += part
        if index % 7 == 0:
            writer.flush()
            if expected:
                assert flushed[-1] == expected
            expected = ""
    writer.flush()
    if expected:
        assert flushed[-1] == expected
    assert "".join(flushed) == "".join(parts)


def test_print_writer_on_retains_buffer_after_failed_flush_and_validates_ranges():
    attempts = [0]
    delivered: list[str] = []

    def fail_once(text: str):
        attempts[0] += 1
        if attempts[0] == 1:
            raise RuntimeError("flush failed")
        delivered.append(text)

    writer = print_writer_on(fail_once)
    writer.write("retry")
    with pytest.raises(RuntimeError, match="flush failed"):
        writer.flush()
    writer.flush()
    assert delivered == ["retry"]

    with pytest.raises(TypeError, match="bytes"):
        writer.write(b"bytes")
    with pytest.raises(TypeError, match="length requires"):
        writer.write("text", length=1)
    with pytest.raises(ValueError, match="outside"):
        writer.write("text", 2, 9)


def test_print_writer_on_is_lossless_under_parallel_writes():
    flushed: list[str] = []
    writer = print_writer_on(flushed.append)
    values = [f"{index}\n" for index in range(256)]
    barrier = threading.Barrier(16)

    def write_group(group: list[str]):
        barrier.wait()
        for value in group:
            writer.write(value)

    groups = [values[index::16] for index in range(16)]
    with ThreadPoolExecutor(max_workers=16) as executor:
        list(executor.map(write_group, groups))
    writer.flush()
    assert sorted(flushed[0].splitlines()) == sorted(str(index) for index in range(256))


def test_add_classpath_imports_local_modules_deduplicates_and_accepts_file_urls(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
):
    module_name = f"classpath_probe_{uuid.uuid4().hex}"
    (tmp_path / f"{module_name}.py").write_text("value = 'imported'\n")
    original_path = list(sys.path)
    monkeypatch.setattr(sys, "path", original_path)
    try:
        assert add_classpath(tmp_path) is None
        assert add_classpath(tmp_path.as_uri()) is None
        normalized = os.path.normcase(os.path.normpath(str(tmp_path.resolve())))
        matches = [
            entry
            for entry in sys.path
            if os.path.normcase(os.path.normpath(os.path.abspath(entry))) == normalized
        ]
        assert len(matches) == 1
        imported = importlib.import_module(module_name)
        assert imported.value == "imported"
    finally:
        sys.modules.pop(module_name, None)
        importlib.invalidate_caches()


def test_add_classpath_rejects_nonlocal_values_and_is_thread_safe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
):
    monkeypatch.setattr(sys, "path", list(sys.path))
    with pytest.raises(ValueError, match="only local file URLs"):
        add_classpath("https://example.test/package")
    with pytest.raises(TypeError, match="text path"):
        add_classpath(b"bytes-path")

    with ThreadPoolExecutor(max_workers=16) as executor:
        list(executor.map(lambda _: add_classpath(tmp_path), range(256)))
    normalized = os.path.normcase(os.path.normpath(str(tmp_path.resolve())))
    assert (
        sum(
            os.path.normcase(os.path.normpath(os.path.abspath(entry))) == normalized
            for entry in sys.path
        )
        == 1
    )
