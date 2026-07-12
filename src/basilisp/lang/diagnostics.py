"""Structured exception data shared by interactive Basilisp surfaces."""

from __future__ import annotations

from typing import Any

from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap
from basilisp.lang import vector as vec
from basilisp.lang.interfaces import IExceptionInfo, IPersistentMap

_CAUSES = kw.keyword("causes")
_CLASS = kw.keyword("class")
_DATA = kw.keyword("data")
_FILE = kw.keyword("file")
_FORM = kw.keyword("form")
_MESSAGE = kw.keyword("message")
_PHASE = kw.keyword("phase")
_SOURCE = kw.keyword("source")
_TYPE = kw.keyword("type")
_SOURCE_KEYS = (
    _FILE,
    kw.keyword("line"),
    kw.keyword("col"),
    kw.keyword("end-line"),
    kw.keyword("end-col"),
    _FORM,
)


def exception_data(
    exc: BaseException, *, phase: kw.Keyword | None = None
) -> IPersistentMap:
    """Return transport-independent data describing ``exc`` and its causes.

    ``phase`` belongs to the caller's operation, such as ``:execution`` for a
    pREPL event. Compiler-specific phase and source data remain available under
    ``:data`` and the selected source fields are also exposed under ``:source``.
    This function deliberately does not format a traceback or choose a wire
    protocol.
    """
    return _exception_data(exc, phase=phase, seen=set())


def _exception_data(
    exc: BaseException,
    *,
    phase: kw.Keyword | None,
    seen: set[int],
) -> IPersistentMap:
    if id(exc) in seen:
        return lmap.map({_TYPE: type(exc).__name__, _MESSAGE: "cyclic exception cause"})

    seen.add(id(exc))
    try:
        exc_type = type(exc)
        data = exc.data if isinstance(exc, IExceptionInfo) else None
        diagnostic: dict[kw.Keyword, Any] = {
            _TYPE: exc_type.__name__,
            _CLASS: f"{exc_type.__module__}.{exc_type.__qualname__}",
            _MESSAGE: str(exc),
        }
        if phase is not None:
            diagnostic[_PHASE] = phase
        elif isinstance(data, IPersistentMap) and (data_phase := data.val_at(_PHASE)):
            diagnostic[_PHASE] = data_phase

        if data is not None:
            diagnostic[_DATA] = data
            source = {
                key: data.val_at(key)
                for key in _SOURCE_KEYS
                if data.val_at(key) is not None
            }
            if source:
                diagnostic[_SOURCE] = lmap.map(source)

        if cause := _cause(exc):
            diagnostic[_CAUSES] = vec.vector(
                [_exception_data(cause, phase=None, seen=seen)]
            )
        return lmap.map(diagnostic)
    finally:
        seen.remove(id(exc))


def _cause(exc: BaseException) -> BaseException | None:
    if exc.__cause__ is not None:
        return exc.__cause__
    if exc.__suppress_context__:
        return None
    return exc.__context__
