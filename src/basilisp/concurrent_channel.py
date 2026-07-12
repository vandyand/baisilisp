"""Asyncio-native channels for Basilisp's Python concurrency API."""

from __future__ import annotations

import asyncio
from collections import deque
from typing import Any, Deque

_POLICIES = frozenset({"fixed", "sliding", "dropping"})


class Channel:
    """A loop-bound channel with Clojure-style close and buffering semantics."""

    def __init__(self, capacity: int = 0, *, policy: str = "fixed"):
        if capacity < 0:
            raise ValueError("channel capacity must be non-negative")
        if policy not in _POLICIES:
            raise ValueError(f"unsupported channel buffer policy: {policy}")
        if capacity == 0 and policy != "fixed":
            raise ValueError("sliding and dropping buffers require positive capacity")

        self._capacity = capacity
        self._policy = policy
        self._closed = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._buffer: Deque[Any] = deque()
        self._puts: Deque[tuple[Any, asyncio.Future[bool]]] = deque()
        self._takes: Deque[asyncio.Future[Any]] = deque()

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        self._bind_loop()
        if self._closed:
            return
        self._closed = True
        self._discard_cancelled()
        while self._puts:
            _, future = self._puts.popleft()
            if not future.done():
                future.set_result(False)
        if not self._buffer:
            while self._takes:
                take_future = self._takes.popleft()
                if not take_future.done():
                    take_future.set_result(None)

    def offer(self, value: Any) -> bool:
        """Try to put ``value`` without waiting."""
        self._bind_loop()
        self._validate_value(value)
        if self._closed:
            return False
        self._discard_cancelled()
        if self._takes:
            self._takes.popleft().set_result(value)
            return True
        if self._capacity == 0:
            return False
        if len(self._buffer) < self._capacity:
            self._buffer.append(value)
            return True
        if self._policy == "sliding":
            self._buffer.popleft()
            self._buffer.append(value)
            return True
        if self._policy == "dropping":
            return True
        return False

    def poll(self) -> Any | None:
        """Try to take a value without waiting, returning ``None`` when unavailable."""
        self._bind_loop()
        self._discard_cancelled()
        if self._buffer:
            value = self._buffer.popleft()
            self._fill_buffer()
            return value
        if self._puts:
            value, future = self._puts.popleft()
            future.set_result(True)
            return value
        return None

    async def put(self, value: Any) -> bool:
        self._bind_loop()
        if self.offer(value):
            return True
        if self._closed:
            return False
        future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self._puts.append((value, future))
        try:
            return await future
        finally:
            self._discard_cancelled()

    async def take(self) -> Any | None:
        self._bind_loop()
        value = self.poll()
        if value is not None:
            return value
        if self._closed:
            return None
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._takes.append(future)
        try:
            return await future
        finally:
            self._discard_cancelled()

    def _fill_buffer(self) -> None:
        self._discard_cancelled()
        while self._puts and len(self._buffer) < self._capacity:
            value, future = self._puts.popleft()
            if not future.done():
                self._buffer.append(value)
                future.set_result(True)

    def _discard_cancelled(self) -> None:
        self._puts = deque(
            (value, future) for value, future in self._puts if not future.done()
        )
        self._takes = deque(future for future in self._takes if not future.done())

    def _bind_loop(self) -> None:
        """Bind the channel to its first running event loop."""
        loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = loop
        elif self._loop is not loop:
            raise RuntimeError("a channel cannot be shared across event loops")

    @staticmethod
    def _validate_value(value: Any) -> None:
        if value is None:
            raise ValueError("channels do not accept nil values")
