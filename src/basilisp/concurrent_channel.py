"""Asyncio-native channels for Basilisp's Python concurrency API."""

from __future__ import annotations

import asyncio
import random
from collections import deque
from collections.abc import Iterable, Sequence
from typing import Any, Deque

from basilisp.lang.keyword import Keyword, keyword

_POLICIES = frozenset({"fixed", "sliding", "dropping"})
_BLOCKED = object()
_MISSING = object()
_NOT_READY = object()
DEFAULT_PORT = keyword("default")


class _Selection:
    """The one-shot winner shared by every operation in an ``alts`` call."""

    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.future: asyncio.Future[tuple[Any, Channel | Keyword]] = (
            loop.create_future()
        )

    @property
    def active(self) -> bool:
        return not self.future.done()

    def resolve(self, value: Any, channel: Channel) -> bool:
        if not self.active:
            return False
        self.future.set_result((value, channel))
        return True


class _Waiter:
    """A normal operation future or one branch of an ``alts`` selection."""

    def __init__(
        self,
        channel: Channel,
        *,
        future: asyncio.Future[Any] | None = None,
        selection: _Selection | None = None,
    ):
        self._channel = channel
        self._future = future
        self._selection = selection

    @property
    def active(self) -> bool:
        if self._selection is not None:
            return self._selection.active
        return self._future is not None and not self._future.done()

    def resolve(self, value: Any) -> bool:
        if self._selection is not None:
            return self._selection.resolve(value, self._channel)
        if self._future is None or self._future.done():
            return False
        self._future.set_result(value)
        return True


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
        self._puts: Deque[tuple[Any, _Waiter]] = deque()
        self._takes: Deque[_Waiter] = deque()

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        self._bind_loop()
        if self._closed:
            return
        self._closed = True
        self._discard_inactive()
        while self._puts:
            _, waiter = self._puts.popleft()
            waiter.resolve(False)
        if not self._buffer:
            while self._takes:
                self._takes.popleft().resolve(None)

    def offer(self, value: Any) -> bool:
        """Try to put ``value`` without waiting."""
        return self._try_put(value) is True

    def poll(self) -> Any | None:
        """Try to take a value without waiting, returning ``None`` when unavailable."""
        value = self._try_take()
        return None if value is _NOT_READY else value

    async def put(self, value: Any) -> bool:
        result = self._try_put(value)
        if result is not _BLOCKED:
            return bool(result)
        future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self._puts.append((value, _Waiter(self, future=future)))
        try:
            return await future
        finally:
            self._discard_inactive()

    async def take(self) -> Any | None:
        value = self._try_take()
        if value is not _NOT_READY:
            return value
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._takes.append(_Waiter(self, future=future))
        try:
            return await future
        finally:
            self._discard_inactive()

    def _try_put(self, value: Any) -> bool | object:
        self._bind_loop()
        self._validate_value(value)
        if self._closed:
            return False
        self._discard_inactive()
        while self._takes:
            if self._takes.popleft().resolve(value):
                return True
        if self._capacity == 0:
            return _BLOCKED
        if len(self._buffer) < self._capacity:
            self._buffer.append(value)
            return True
        if self._policy == "sliding":
            self._buffer.popleft()
            self._buffer.append(value)
            return True
        if self._policy == "dropping":
            return True
        return _BLOCKED

    def _try_take(self) -> Any | object:
        self._bind_loop()
        self._discard_inactive()
        if self._buffer:
            value = self._buffer.popleft()
            self._fill_buffer()
            return value
        while self._puts:
            value, waiter = self._puts.popleft()
            if waiter.resolve(True):
                return value
        if self._closed:
            return None
        return _NOT_READY

    def _enqueue_put(self, value: Any, selection: _Selection) -> None:
        self._bind_loop()
        self._puts.append((value, _Waiter(self, selection=selection)))

    def _enqueue_take(self, selection: _Selection) -> None:
        self._bind_loop()
        self._takes.append(_Waiter(self, selection=selection))

    def _fill_buffer(self) -> None:
        self._discard_inactive()
        while self._puts and len(self._buffer) < self._capacity:
            value, waiter = self._puts.popleft()
            if waiter.resolve(True):
                self._buffer.append(value)

    def _discard_inactive(self) -> None:
        self._puts = deque(
            (value, waiter) for value, waiter in self._puts if waiter.active
        )
        self._takes = deque(waiter for waiter in self._takes if waiter.active)

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


class TimeoutChannel(Channel):
    """A one-shot channel closed by the owning event loop after a delay."""

    def __init__(self, delay_ms: float):
        if delay_ms < 0:
            raise ValueError("timeout delay must be non-negative")
        super().__init__()
        self._bind_loop()
        assert self._loop is not None
        self._timer = self._loop.call_later(delay_ms / 1000, self.close)

    @property
    def timer_cancelled(self) -> bool:
        return self._timer.cancelled()

    def close(self) -> None:
        self._timer.cancel()
        super().close()


def _parse_port(port: Any) -> tuple[Channel, Any | object]:
    if isinstance(port, Channel):
        return port, _MISSING
    if not isinstance(port, Sequence) or isinstance(port, (bytes, str)):
        raise TypeError("an alts port must be a channel or a [channel value] pair")
    if len(port) != 2 or not isinstance(port[0], Channel):
        raise TypeError("an alts put operation must be a [channel value] pair")
    Channel._validate_value(port[1])
    return port[0], port[1]


async def alts(
    ports: Iterable[Any],
    *,
    priority: bool = False,
    default: Any = _MISSING,
    has_default: bool | None = None,
) -> tuple[Any, Channel | Keyword]:
    """Await exactly one ready take or put operation from ``ports``.

    A port is a :class:`Channel` for a take, or ``[channel, value]`` for a put.
    The result is ``(value, port)``. ``default`` returns immediately as
    ``(default, :default)`` when no operation is ready.
    """
    operations = [_parse_port(port) for port in ports]
    if has_default is None:
        has_default = default is not _MISSING
    if not operations and not has_default:
        raise ValueError("alts requires a port or a default value")

    if not priority:
        random.shuffle(operations)
    for channel, value in operations:
        result = channel._try_take() if value is _MISSING else channel._try_put(value)
        if result is not _NOT_READY and result is not _BLOCKED:
            return result, channel
    if has_default:
        return default, DEFAULT_PORT

    loop = asyncio.get_running_loop()
    selection = _Selection(loop)
    channels: set[Channel] = set()
    for channel, value in operations:
        channels.add(channel)
        if value is _MISSING:
            channel._enqueue_take(selection)
        else:
            channel._enqueue_put(value, selection)
    try:
        return await selection.future
    finally:
        for channel in channels:
            channel._discard_inactive()


def timeout(delay_ms: float) -> TimeoutChannel:
    """Create a channel that closes once after ``delay_ms`` milliseconds."""
    return TimeoutChannel(delay_ms)
