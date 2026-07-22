"""Python-host equivalents for selected Clojure core interop utilities."""

from __future__ import annotations

import dataclasses
import importlib
import inspect
import os
import sys
import threading
import traceback
import types
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping
from typing import Any, Callable

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

_CLASSPATH_LOCK = threading.RLock()


class PrintWriterOn:
    """A buffered, callback-backed Python counterpart to ``PrintWriter-on``.

    The writer accumulates text until ``flush``. Closing flushes once, invokes the
    optional close callback, and prevents subsequent writes. It intentionally
    exposes the common Python text-writer methods as well as ``print`` and
    ``println`` for Clojure-shaped use from Basilisp.
    """

    __slots__ = ("_autoflush", "_buffer", "_close_fn", "_closed", "_flush_fn", "_lock")

    def __init__(
        self,
        flush_fn: Callable[[str], Any],
        close_fn: Callable[[], Any] | None = None,
        autoflush: bool = False,
    ):
        if not callable(flush_fn):
            raise TypeError("PrintWriter-on requires a callable flush function")
        if close_fn is not None and not callable(close_fn):
            raise TypeError("PrintWriter-on close function must be callable or None")
        self._flush_fn = flush_fn
        self._close_fn = close_fn
        self._autoflush = bool(autoflush)
        self._buffer: list[str] = []
        self._closed = False
        self._lock = threading.RLock()

    @property
    def closed(self) -> bool:
        """Whether this writer has been closed."""
        return self._closed

    def _ensure_open(self) -> None:
        if self._closed:
            raise ValueError("I/O operation on closed PrintWriter-on")

    @staticmethod
    def _text(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, int) and not isinstance(value, bool):
            try:
                return chr(value & 0xFFFF)
            except ValueError as e:  # pragma: no cover - masked into range
                raise ValueError("PrintWriter-on character code is invalid") from e
        if isinstance(value, bytes):
            raise TypeError("PrintWriter-on cannot write bytes; write text instead")
        try:
            return "".join(str(char) for char in value)
        except TypeError as e:
            raise TypeError(
                "PrintWriter-on write expects text or an iterable of chars"
            ) from e

    def write(self, value: Any, offset: int | None = None, length: int | None = None):
        """Buffer text, optionally selecting the Java Writer-style range."""
        text = self._text(value)
        if offset is None and length is not None:
            raise TypeError("PrintWriter-on write length requires an offset")
        if offset is not None:
            if isinstance(offset, bool) or not isinstance(offset, int):
                raise TypeError("PrintWriter-on offset must be an integer")
            if (
                length is None
                or isinstance(length, bool)
                or not isinstance(length, int)
            ):
                raise TypeError("PrintWriter-on length must be an integer")
            if offset < 0 or length < 0 or offset + length > len(text):
                raise ValueError("PrintWriter-on write range is outside the input")
            text = text[offset : offset + length]
        with self._lock:
            self._ensure_open()
            if text:
                self._buffer.append(text)
        return None

    def flush(self):
        """Deliver the buffered text once, retaining it if the callback fails."""
        with self._lock:
            self._ensure_open()
            if not self._buffer:
                return None
            text = "".join(self._buffer)
            self._flush_fn(text)
            self._buffer.clear()
        return None

    def close(self):
        """Flush once, run the optional close callback, and close this writer."""
        with self._lock:
            if self._closed:
                return None
            self.flush()
            try:
                if self._close_fn is not None:
                    self._close_fn()
            finally:
                self._closed = True
        return None

    def print(self, value: Any = ""):
        """Write the host string representation of ``value`` without flushing."""
        return self.write(str(value))

    def println(self, value: Any = ""):
        """Write a value and the platform newline, flushing when configured."""
        self.print(value)
        self.write(os.linesep)
        if self._autoflush:
            self.flush()
        return None

    def check_error(self) -> bool:
        """Return false; callback failures propagate as normal Python exceptions."""
        return False

    checkError = check_error


def print_writer_on(
    flush_fn: Callable[[str], Any],
    close_fn: Callable[[], Any] | None = None,
    autoflush: bool = False,
) -> PrintWriterOn:
    """Create a callback-backed text writer matching Clojure's ``PrintWriter-on``."""
    return PrintWriterOn(flush_fn, close_fn, autoflush)


def _classpath_entry(value: Any) -> str:
    """Normalize a Python path or file URL into an absolute import search path."""
    if isinstance(value, (urllib.parse.ParseResult, urllib.parse.SplitResult)):
        value = value.geturl()
    try:
        raw = os.fspath(value)
    except TypeError as e:
        raise TypeError("add-classpath expects a path-like value or file URL") from e
    if isinstance(raw, bytes):
        raise TypeError("add-classpath expects a text path or file URL")
    if os.path.isabs(raw) or os.path.splitdrive(raw)[0]:
        path = raw
    else:
        parsed = urllib.parse.urlsplit(raw)
        if not parsed.scheme:
            path = raw
        elif parsed.scheme != "file":
            raise ValueError("add-classpath supports only local file URLs")
        else:
            if parsed.query or parsed.fragment:
                raise ValueError(
                    "add-classpath file URLs may not contain query or fragment"
                )
            path = urllib.request.url2pathname(urllib.parse.unquote(parsed.path))
            if parsed.netloc and parsed.netloc != "localhost":
                path = f"//{parsed.netloc}{path}"
    return os.path.abspath(os.path.expanduser(path))


def add_classpath(url: Any) -> None:
    """Append a local import path and invalidate Python's import caches.

    This is the Python-host equivalent of Clojure's deprecated classpath
    mutation helper. It accepts a path-like object or a ``file:`` URL, preserves
    existing import precedence by appending, and suppresses normalized duplicates.
    """
    entry = _classpath_entry(url)
    normalized_entry = os.path.normcase(os.path.normpath(entry))
    with _CLASSPATH_LOCK:
        known_entries = {
            os.path.normcase(os.path.normpath(os.path.abspath(existing)))
            for existing in sys.path
            if isinstance(existing, str)
        }
        if normalized_entry not in known_entries:
            sys.path.append(entry)
        importlib.invalidate_caches()
    return None


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


def _exception_message(exc: BaseException):
    """Return Clojure's separate message field for an exception.

    ``ExceptionInfo.__str__`` deliberately includes its data map for Python
    diagnostics, but ``Throwable->map`` must retain Clojure's separate
    ``:message`` and ``:data`` fields.
    """
    return exc.message if isinstance(exc, IExceptionInfo) else str(exc)


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
        if message := _exception_message(error):
            entry[_MESSAGE] = message
        if (data := _exception_data(error)) is not None:
            entry[_DATA] = data
        trace = _trace(error)
        # Persistent collections are truthy even when empty, unlike Python lists.
        # An explicitly supplied cause may be an exception that has never been
        # raised, and therefore legitimately has no traceback or ``:at`` frame.
        if len(trace) > 0:
            entry[_AT] = trace[0]
        return lmap.map(entry)

    root = chain[-1]
    result: dict[Any, Any] = {
        _VIA: vec.vector(base(error) for error in chain),
        _TRACE: _trace(root),
    }
    if message := _exception_message(root):
        result[_CAUSE] = message
    if (data := _exception_data(root)) is not None:
        result[_DATA] = data
    if (outer_data := _exception_data(exc)) is not None:
        phase = outer_data.val_at(_CLOJURE_ERROR_PHASE)
        if phase is not None:
            result[_PHASE] = phase
    return lmap.map(result)
