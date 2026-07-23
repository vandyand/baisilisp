"""Helpers for the public ``clojure.core.protocols`` compatibility namespace."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from basilisp.lang.reduced import Reduced

_MISSING = object()


def iterator_reduce(iterable: Iterable[Any], f: Callable[..., Any], init=_MISSING):
    """Consume a single-use iterator with Clojure's iterator-reduce! contract."""

    iterator = iter(iterable)
    if init is _MISSING:
        try:
            acc = next(iterator)
        except StopIteration:
            return f()
    else:
        acc = init
    for value in iterator:
        acc = f(acc, value)
        if isinstance(acc, Reduced):
            return acc.deref()
    return acc
