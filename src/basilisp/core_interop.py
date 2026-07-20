"""Python-host equivalents for selected Clojure core interop utilities."""

from __future__ import annotations

import dataclasses
import inspect
import traceback
import types
import urllib.parse
from collections.abc import Iterable, Mapping
from typing import Any

from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap
from basilisp.lang import symbol as sym
from basilisp.lang import vector as vec
from basilisp.lang.interfaces import IExceptionInfo
from basilisp.lang.seq import iterator_sequence

_AT = kw.keyword("at")
_CAUSE = kw.keyword("cause")
_DATA = kw.keyword("data")
_MESSAGE = kw.keyword("message")
_PHASE = kw.keyword("phase")
_CLOJURE_ERROR_PHASE = kw.keyword("phase", "clojure.error")
_TRACE = kw.keyword("trace")
_TYPE = kw.keyword("type")
_VIA = kw.keyword("via")


def bean(value: Any):
    """Return public Python object state as a Clojure-style keyword map.

    This is the host-equivalent of Clojure's JavaBeans helper. Mapping values,
    dataclasses, named tuples, public instance attributes, and ``@property``
    descriptors are supported. Properties that raise are omitted, matching the
    practical expectation that inspection should not make an otherwise useful
    object unusable.
    """
    include_properties = not isinstance(value, Mapping)
    if isinstance(value, Mapping):
        fields = dict(value)
    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        fields = {
            field.name: getattr(value, field.name)
            for field in dataclasses.fields(value)
        }
    elif hasattr(value, "_asdict"):
        fields = dict(value._asdict())
    else:
        fields = {
            name: field
            for name, field in vars(value).items()
            if not name.startswith("_")
        }
    if include_properties:
        for name, descriptor in inspect.getmembers(
            type(value), lambda v: isinstance(v, property)
        ):
            if name.startswith("_") or name in fields:
                continue
            try:
                fields[name] = getattr(value, name)
            except Exception:  # properties are observational, not mandatory
                continue
    result = {
        name if isinstance(name, kw.Keyword) else kw.keyword(str(name)): field
        for name, field in fields.items()
    }
    result[kw.keyword("class")] = type(value)
    return lmap.map(result)


def enumeration_seq(enumeration: Any):
    """Lazily sequence Python iterators and Java-style enumerations.

    A host object exposing ``hasMoreElements``/``nextElement`` is accepted as a
    direct analogue of ``java.util.Enumeration``; ordinary Python iterables and
    iterators are accepted for useful Python interop.
    """
    if hasattr(enumeration, "hasMoreElements") and hasattr(enumeration, "nextElement"):

        def elements():
            while enumeration.hasMoreElements():
                yield enumeration.nextElement()

        return iterator_sequence(elements())
    if not isinstance(enumeration, Iterable):
        raise TypeError("enumeration-seq expects an iterable or enumeration")
    return iterator_sequence(iter(enumeration))


def uri_qmark(value: Any) -> bool:
    """Return whether value is Python's parsed-URI counterpart to ``java.net.URI``."""
    return isinstance(value, (urllib.parse.ParseResult, urllib.parse.SplitResult))


def stack_trace_element_to_vec(frame: Any):
    """Convert a Python traceback frame to Clojure's four-element trace shape."""
    if isinstance(frame, traceback.FrameSummary):
        module = frame.filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].rsplit(".", 1)[0]
        return vec.vector((module, frame.name, frame.filename, frame.lineno))
    if isinstance(frame, types.TracebackType):
        code = frame.tb_frame.f_code
        module = frame.tb_frame.f_globals.get("__name__", "<unknown>")
        return vec.vector((module, code.co_name, code.co_filename, frame.tb_lineno))
    if isinstance(frame, tuple) and len(frame) == 4:
        return vec.vector(frame)
    raise TypeError("StackTraceElement->vec expects a traceback frame")


def _exception_type(exc: BaseException):
    cls = type(exc)
    return sym.symbol(f"{cls.__module__}.{cls.__qualname__}")


def _exception_data(exc: BaseException):
    return exc.data if isinstance(exc, IExceptionInfo) else None


def _cause(exc: BaseException):
    if exc.__cause__ is not None:
        return exc.__cause__
    return None if exc.__suppress_context__ else exc.__context__


def _trace(exc: BaseException):
    if exc.__traceback__ is None:
        return vec.EMPTY
    return vec.vector(
        stack_trace_element_to_vec(frame)
        for frame in traceback.extract_tb(exc.__traceback__)
    )


def throwable_to_map(exc: BaseException):
    """Create the Clojure ``Throwable->map`` shape for a Python exception chain."""
    if not isinstance(exc, BaseException):
        raise TypeError("Throwable->map expects a Python exception")

    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = _cause(current)

    def base(error: BaseException):
        entry: dict[Any, Any] = {_TYPE: _exception_type(error)}
        if message := str(error):
            entry[_MESSAGE] = message
        if (data := _exception_data(error)) is not None:
            entry[_DATA] = data
        trace = _trace(error)
        if trace:
            entry[_AT] = trace[0]
        return lmap.map(entry)

    root = chain[-1]
    result: dict[Any, Any] = {
        _VIA: vec.vector(base(error) for error in chain),
        _TRACE: _trace(root),
    }
    if message := str(root):
        result[_CAUSE] = message
    if (data := _exception_data(root)) is not None:
        result[_DATA] = data
    if (outer_data := _exception_data(exc)) is not None:
        phase = outer_data.val_at(_CLOJURE_ERROR_PHASE)
        if phase is not None:
            result[_PHASE] = phase
    return lmap.map(result)
