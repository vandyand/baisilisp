"""Portable helpers for ``clojure.core.async.impl`` compatibility namespaces."""

from __future__ import annotations

import itertools
import threading
from collections import deque
from collections.abc import Callable
from typing import Any

from basilisp.lang.interfaces import IBlockingDeref, ILookup, IPending
from basilisp.lang.keyword import Keyword


class FnHandler(ILookup):
    """Small stand-in for core.async's callback handler objects."""

    def __init__(self, callback: Callable[[Any], Any], blockable: bool = True):
        if not callable(callback):
            raise TypeError("core.async handler callback must be callable")
        self._callback = callback
        self._blockable = bool(blockable)
        self._active = True

    @property
    def active(self) -> bool:
        return self._active

    @property
    def blockable(self) -> bool:
        return self._blockable

    @property
    def lock_id(self) -> int:
        return 0

    def commit(self) -> Callable[[Any], Any] | None:
        return self._callback if self._active else None

    def val_at(self, k: Any, default: Any | None = None) -> Any | None:
        if isinstance(k, Keyword):
            if k.ns == "basilisp.core.async" and k.name == "handler":
                return True
            if k.ns is None and k.name == "f":
                return self._callback
            if k.ns is None and k.name == "blockable":
                return self._blockable
        return default


class BaseBuffer:
    """Mutable queue backing for the public impl buffer shims."""

    policy = "fixed"
    unblocking = False

    def __init__(self, capacity: int):
        if capacity < 0:
            raise ValueError("buffer capacity must be non-negative")
        self._capacity = capacity
        self._data: deque[Any] = deque()

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def count(self) -> int:
        return len(self._data)

    @property
    def full(self) -> bool:
        return len(self._data) >= self._capacity

    def add(self, item: Any) -> "BaseBuffer":
        self._data.append(item)
        return self

    def remove(self) -> Any:
        return self._data.popleft()

    def close(self) -> None:
        return None


class FixedBuffer(BaseBuffer):
    policy = "fixed"


class DroppingBuffer(BaseBuffer):
    policy = "dropping"
    unblocking = True

    @property
    def full(self) -> bool:
        return False

    def add(self, item: Any) -> "DroppingBuffer":
        if len(self._data) < self._capacity:
            self._data.append(item)
        return self


class SlidingBuffer(BaseBuffer):
    policy = "sliding"
    unblocking = True

    @property
    def full(self) -> bool:
        return False

    def add(self, item: Any) -> "SlidingBuffer":
        if self._capacity == 0:
            return self
        if len(self._data) >= self._capacity:
            self._data.popleft()
        self._data.append(item)
        return self


class PromiseBuffer(BaseBuffer):
    policy = "promise"
    unblocking = True

    def __init__(self):
        super().__init__(1)
        self._realized = False
        self._value: Any = None

    @property
    def count(self) -> int:
        return 1 if self._realized else 0

    @property
    def full(self) -> bool:
        return False

    def add(self, item: Any) -> "PromiseBuffer":
        if not self._realized:
            self._realized = True
            self._value = item
        return self

    def remove(self) -> Any:
        if not self._realized:
            raise IndexError("remove from empty promise buffer")
        return self._value


class Box(IBlockingDeref, IPending):
    """Derefable value wrapper matching ``impl.channels/box`` shape."""

    def __init__(self, value: Any):
        self._value = value

    def deref(
        self, timeout: float | None = None, timeout_val: Any | None = None
    ) -> Any:
        return self._value

    @property
    def is_realized(self) -> bool:
        return True


def thread_factory(
    name_format: str,
    daemon: bool,
    init_fn: Callable[[], Any] | None = None,
) -> Callable[[Callable[[], Any]], threading.Thread]:
    """Return a Python thread factory with Clojure-shaped naming semantics."""

    counter = itertools.count()

    def make_thread(runnable: Callable[[], Any]) -> threading.Thread:
        index = next(counter)

        def run() -> None:
            if init_fn is not None:
                init_fn()
            runnable()

        name = name_format % index if "%d" in name_format else name_format
        return threading.Thread(target=run, name=name, daemon=daemon)

    return make_thread
