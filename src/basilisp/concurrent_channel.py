"""Asyncio-native channels for Basilisp's Python concurrency API."""

from __future__ import annotations

import asyncio
import inspect
import random
import threading
from collections import deque
from collections.abc import Callable, Iterable, Sequence
from typing import Any

from basilisp.lang.keyword import Keyword, keyword
from basilisp.lang.reduced import Reduced

_POLICIES = frozenset({"fixed", "sliding", "dropping"})
_BLOCKED = object()
_MISSING = object()
_NOT_READY = object()
DEFAULT_PORT = keyword("default")
_BLOCKING_LOOP: asyncio.AbstractEventLoop | None = None
_BLOCKING_LOOP_LOCK = threading.Lock()


class _NilTransducerOutput(ValueError):
    """Raised internally when a channel transducer emits nil."""


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

    def __init__(
        self,
        capacity: int = 0,
        *,
        policy: str = "fixed",
        xform: Callable[..., Any] | None = None,
        error_handler: Callable[[BaseException], Any] | None = None,
    ):
        if capacity < 0:
            raise ValueError("channel capacity must be non-negative")
        if policy not in _POLICIES:
            raise ValueError(f"unsupported channel buffer policy: {policy}")
        if capacity == 0 and policy != "fixed":
            raise ValueError("sliding and dropping buffers require positive capacity")
        if xform is not None and not callable(xform):
            raise TypeError("channel transducer must be callable")
        if error_handler is not None and not callable(error_handler):
            raise TypeError("channel transducer error handler must be callable")

        self._capacity = capacity
        self._policy = policy
        self._closed = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._buffer: deque[Any] = deque()
        self._puts: deque[tuple[Any, _Waiter]] = deque()
        self._takes: deque[_Waiter] = deque()
        self._xform_waiters: deque[asyncio.Future[None]] = deque()
        self._xform_lock: asyncio.Lock | None = None
        self._xform_reducing = xform(self._xform_emit) if xform is not None else None
        self._xform_state = (
            self._xform_reducing() if self._xform_reducing is not None else None
        )
        self._xform_error_handler = error_handler
        self._xform_emitted: list[Any] | None = None
        self._xform_done = False

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        self._bind_loop()
        if self._closed:
            return
        self._emit_transformed_values(self._complete_xform())
        self._closed = True
        self._discard_inactive()
        while self._puts:
            _, waiter = self._puts.popleft()
            waiter.resolve(False)
        while self._xform_waiters:
            waiter = self._xform_waiters.popleft()
            if not waiter.done():
                waiter.set_result(None)
        if not self._buffer:
            while self._takes:
                self._takes.popleft().resolve(None)

    def offer(self, value: Any) -> bool:
        """Try to put ``value`` without waiting."""
        if self._xform_reducing is not None:
            return self._offer_transformed(value)
        return self._try_put(value) is True

    def poll(self) -> Any | None:
        """Try to take a value without waiting, returning ``None`` when unavailable."""
        value = self._try_take()
        return None if value is _NOT_READY else value

    async def put(self, value: Any) -> bool:
        if self._xform_reducing is not None:
            return await self._put_transformed(value)
        return await self._put_raw(value)

    async def _put_raw(self, value: Any) -> bool:
        result = self._try_put(value)
        if result is not _BLOCKED:
            return bool(result)
        future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self._puts.append((value, _Waiter(self, future=future)))
        try:
            return await future
        finally:
            self._discard_inactive()

    async def _put_transformed(self, value: Any) -> bool:
        Channel._validate_value(value)
        async with self._get_xform_lock():
            if self._closed or self._xform_done:
                return False
            await self._wait_for_xform_admission()
            if self._closed or self._xform_done:
                return False
            emitted, done = self._transform_value(value)
            self._emit_transformed_values(emitted)
            if done:
                self.close()
            return True

    def _offer_transformed(self, value: Any) -> bool:
        Channel._validate_value(value)
        if (
            self._closed
            or self._xform_done
            or not self._can_admit_xform_input()
            or self._has_live_xform_waiters()
        ):
            return False
        emitted, done = self._transform_value(value)
        self._emit_transformed_values(emitted)
        if done:
            self.close()
        return True

    async def take(self) -> Any | None:
        value = self._try_take()
        if value is not _NOT_READY:
            return value
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._takes.append(_Waiter(self, future=future))
        self._wake_xform_waiter()
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
            self._wake_xform_waiter()
            return value
        while self._puts:
            value, waiter = self._puts.popleft()
            if waiter.resolve(True):
                self._wake_xform_waiter()
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
        self._wake_xform_waiter()

    def _fill_buffer(self) -> None:
        self._discard_inactive()
        while self._puts and len(self._buffer) < self._capacity:
            value, waiter = self._puts.popleft()
            if waiter.resolve(True):
                self._buffer.append(value)

    def _get_xform_lock(self) -> asyncio.Lock:
        if self._xform_lock is None:
            self._xform_lock = asyncio.Lock()
        return self._xform_lock

    def _has_live_xform_waiters(self) -> bool:
        self._discard_inactive_xform_waiters()
        return bool(self._xform_waiters)

    def _discard_inactive_xform_waiters(self) -> None:
        self._xform_waiters = deque(
            waiter for waiter in self._xform_waiters if not waiter.done()
        )

    def _can_admit_xform_input(self) -> bool:
        self._discard_inactive()
        if self._closed or self._xform_done:
            return False
        if self._takes:
            return True
        if self._capacity == 0:
            return False
        if self._policy in {"sliding", "dropping"}:
            return True
        return len(self._buffer) < self._capacity

    async def _wait_for_xform_admission(self) -> None:
        while not self._can_admit_xform_input():
            if self._closed or self._xform_done:
                return
            future: asyncio.Future[None] = asyncio.get_running_loop().create_future()
            self._xform_waiters.append(future)
            try:
                await future
            finally:
                self._discard_inactive_xform_waiters()

    def _wake_xform_waiter(self) -> None:
        if not self._can_admit_xform_input():
            return
        self._discard_inactive_xform_waiters()
        while self._xform_waiters:
            waiter = self._xform_waiters.popleft()
            if not waiter.done():
                waiter.set_result(None)
                return

    def _emit_transformed_values(self, values: Iterable[Any]) -> None:
        for value in values:
            self._validate_value(value)
            self._discard_inactive()
            delivered = False
            while self._takes:
                if self._takes.popleft().resolve(value):
                    delivered = True
                    break
            if not delivered:
                self._buffer.append(value)

    def _xform_emit(self, *args: Any) -> Any:
        if not args:
            return []
        if len(args) == 1:
            return args[0]
        result, item = args
        if item is None:
            raise _NilTransducerOutput("channels do not accept nil values")
        assert self._xform_emitted is not None
        self._xform_emitted.append(item)
        return result

    def _transform_value(self, value: Any) -> tuple[list[Any], bool]:
        assert self._xform_reducing is not None
        self._xform_emitted = []
        try:
            result = self._xform_reducing(self._xform_state, value)
        except _NilTransducerOutput:
            raise
        except BaseException as error:
            if self._xform_error_handler is None:
                return [], False
            replacement = self._xform_error_handler(error)
            if replacement is not None:
                self._validate_value(replacement)
                self._xform_emitted.append(replacement)
            return self._xform_emitted, False
        finally:
            emitted = self._xform_emitted
            self._xform_emitted = None

        if isinstance(result, Reduced):
            self._xform_state = result.value
            self._xform_done = True
            return emitted, True
        self._xform_state = result
        return emitted, False

    def _complete_xform(self) -> list[Any]:
        if self._xform_reducing is None or self._xform_done:
            return []
        self._xform_done = True
        self._xform_emitted = []
        try:
            result = self._xform_reducing(self._xform_state)
            self._xform_state = result.value if isinstance(result, Reduced) else result
            return self._xform_emitted
        finally:
            self._xform_emitted = None

    def _discard_inactive(self) -> None:
        self._puts = deque(
            (value, waiter) for value, waiter in self._puts if waiter.active
        )
        self._takes = deque(waiter for waiter in self._takes if waiter.active)

    def _bind_loop(self) -> None:
        """Bind the channel to the current loop or the shared blocking loop."""
        loop = _current_running_loop() or _blocking_loop()
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
        super().__init__()
        self._loop = _current_running_loop() or _blocking_loop()
        assert self._loop is not None
        self._timer = self._loop.call_later(max(0, delay_ms) / 1000, self.close)

    @property
    def timer_cancelled(self) -> bool:
        return self._timer.cancelled()

    def close(self) -> None:
        self._timer.cancel()
        super().close()


class PromiseChannel(Channel):
    """A channel which realizes at most one value and returns it repeatedly."""

    def __init__(
        self,
        *,
        xform: Callable[..., Any] | None = None,
        error_handler: Callable[[BaseException], Any] | None = None,
    ):
        super().__init__(xform=xform, error_handler=error_handler)
        self._has_value = False
        self._value: Any = None

    def _bind_optional_loop(self) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if self._loop is None:
            self._loop = loop
        elif self._loop is not loop:
            raise RuntimeError("a channel cannot be shared across event loops")

    def close(self) -> None:
        self._bind_optional_loop()
        if self._closed:
            return
        if not self._has_value:
            emitted = self._complete_xform()
            if emitted:
                self._realize(emitted[0])
        self._closed = True
        self._discard_inactive()
        while self._puts:
            _, waiter = self._puts.popleft()
            waiter.resolve(False)
        while self._takes:
            self._takes.popleft().resolve(self._value if self._has_value else None)

    def _realize(self, value: Any) -> None:
        self._validate_value(value)
        self._has_value = True
        self._value = value
        self._closed = True
        self._discard_inactive()
        while self._takes:
            self._takes.popleft().resolve(value)

    def _try_put(self, value: Any) -> bool | object:
        self._bind_optional_loop()
        self._validate_value(value)
        if self._has_value:
            return True
        if self._closed:
            return False
        self._realize(value)
        return True

    async def _put_transformed(self, value: Any) -> bool:
        Channel._validate_value(value)
        async with self._get_xform_lock():
            if self._has_value:
                return True
            if self._closed or self._xform_done:
                return False
            emitted, done = self._transform_value(value)
            if emitted:
                self._realize(emitted[0])
            elif done:
                self.close()
            else:
                return False
            return True

    def _offer_transformed(self, value: Any) -> bool:
        Channel._validate_value(value)
        if self._has_value:
            return True
        if self._closed or self._xform_done:
            return False
        emitted, done = self._transform_value(value)
        if emitted:
            self._realize(emitted[0])
            return True
        if done:
            self.close()
            return False
        return False

    def _try_take(self) -> Any | object:
        self._bind_optional_loop()
        self._discard_inactive()
        if self._has_value:
            return self._value
        if self._closed:
            return None
        return _NOT_READY

    def _enqueue_take(self, selection: _Selection) -> None:
        self._bind_loop()
        if self._has_value:
            selection.resolve(self._value, self)
        elif self._closed:
            selection.resolve(None, self)
        else:
            self._takes.append(_Waiter(self, selection=selection))


def _parse_port(port: Any) -> tuple[Channel, Any | object]:
    if isinstance(port, Channel):
        return port, _MISSING
    if not isinstance(port, Sequence) or isinstance(port, (bytes, str)):
        raise TypeError("an alts port must be a channel or a [channel value] pair")
    if len(port) != 2 or not isinstance(port[0], Channel):
        raise TypeError("an alts put operation must be a [channel value] pair")
    Channel._validate_value(port[1])
    return port[0], port[1]


def _run_loop_forever(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


def _blocking_loop() -> asyncio.AbstractEventLoop:
    global _BLOCKING_LOOP  # pylint: disable=global-statement
    with _BLOCKING_LOOP_LOCK:
        if _BLOCKING_LOOP is None or _BLOCKING_LOOP.is_closed():
            loop = asyncio.new_event_loop()
            thread = threading.Thread(
                target=_run_loop_forever,
                args=(loop,),
                name="basilisp-channel-blocking-loop",
                daemon=True,
            )
            thread.start()
            _BLOCKING_LOOP = loop
        return _BLOCKING_LOOP


def _current_running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


def _owner_loop(channels: Iterable[Channel]) -> asyncio.AbstractEventLoop:
    owner: asyncio.AbstractEventLoop | None = None
    for channel in channels:
        loop = channel._loop  # pylint: disable=protected-access
        if loop is None:
            continue
        if loop.is_closed() or not loop.is_running():
            raise RuntimeError("channel owner event loop is not running")
        if owner is None:
            owner = loop
        elif owner is not loop:
            raise RuntimeError(
                "blocking channel operations require one owner event loop"
            )
    return owner if owner is not None else _blocking_loop()


def _run_blocking(
    awaitable_factory: Callable[[], Any],
    loop: asyncio.AbstractEventLoop,
    operation: str,
) -> Any:
    current = _current_running_loop()
    if current is loop:
        raise RuntimeError(f"{operation} cannot block the owning event loop")
    return asyncio.run_coroutine_threadsafe(awaitable_factory(), loop).result()


def submit_coroutine(coro: Any) -> Any:
    """Schedule ``coro`` on the current loop or the background blocking loop."""
    current = _current_running_loop()
    if current is not None:
        return current.create_task(coro)
    return asyncio.run_coroutine_threadsafe(coro, _blocking_loop())


def blocking_put(channel: Channel, value: Any) -> bool:
    """Block until ``value`` is put on ``channel`` or the channel is closed."""
    loop = _owner_loop([channel])
    return bool(_run_blocking(lambda: channel.put(value), loop, "blocking put"))


def blocking_take(channel: Channel) -> Any | None:
    """Block until a value is taken from ``channel`` or it closes."""
    loop = _owner_loop([channel])
    return _run_blocking(channel.take, loop, "blocking take")


async def _close_channel(channel: Channel) -> None:
    channel.close()


def blocking_close(channel: Channel) -> None:
    """Close ``channel`` from a blocking caller."""
    loop = _owner_loop([channel])
    _run_blocking(lambda: _close_channel(channel), loop, "blocking close")


def blocking_alts(
    ports: Iterable[Any],
    *,
    priority: bool = False,
    default: Any = _MISSING,
    has_default: bool | None = None,
) -> tuple[Any, Channel | Keyword]:
    """Blocking counterpart to :func:`alts`."""
    port_list = list(ports)
    operations = [_parse_port(port) for port in port_list]
    if has_default is None:
        has_default = default is not _MISSING
    if not operations and not has_default:
        raise ValueError("alts requires a port or a default value")
    loop = _owner_loop(channel for channel, _ in operations)
    return _run_blocking(
        lambda: alts(
            port_list, priority=priority, default=default, has_default=has_default
        ),
        loop,
        "blocking alts",
    )


def try_alts(
    ports: Iterable[Any],
    *,
    priority: bool = False,
    default: Any = _MISSING,
    has_default: bool | None = None,
) -> tuple[bool, tuple[Any, Channel | Keyword] | None]:
    """Try one ready take or put operation without enqueuing waiters."""
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
            return True, (result, channel)
    if has_default:
        return True, (default, DEFAULT_PORT)
    return False, None


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


def _transduce_one(xform: Callable[..., Any], value: Any) -> list[Any]:
    """Apply a synchronous transducer independently to one channel value.

    A fresh reducing function is created for every value. This deliberately
    gives ``pipeline`` per-input semantics: a transducer may emit zero, one, or
    many values, but state is never shared accidentally between workers.
    """

    emitted: list[Any] = []

    def emit(*args: Any) -> Any:
        if not args:
            return []
        if len(args) == 1:
            return args[0]
        result, item = args
        if item is None:
            raise ValueError("channels do not accept nil values")
        emitted.append(item)
        return result

    reducing_fn = xform(emit)
    result = reducing_fn()
    result = reducing_fn(result, value)
    if isinstance(result, Reduced):
        return emitted
    reducing_fn(result)
    return emitted


async def _pipe(source: Channel, destination: Channel, *, close_output: bool) -> None:
    try:
        while (value := await source.take()) is not None:
            if not await destination.put(value):
                return
    finally:
        if close_output:
            destination.close()


def pipe(
    source: Channel, destination: Channel, *, close_output: bool = True
) -> asyncio.Task[None]:
    """Forward values from ``source`` to ``destination`` in a caller-owned task.

    Closing the source drains already-buffered values. Closing the destination
    stops upstream consumption. By default the destination closes when the
    source closes; pass ``close_output=False`` when another owner controls it.
    """

    return submit_coroutine(_pipe(source, destination, close_output=close_output))


async def _pipeline(
    parallelism: int,
    source: Channel,
    destination: Channel,
    xform: Callable[..., Any],
    *,
    close_output: bool,
    error_handler: Callable[[BaseException, Any], Iterable[Any] | None] | None,
) -> None:
    pending: dict[int, tuple[Any, asyncio.Task[list[Any]]]] = {}
    completed: dict[int, list[Any]] = {}
    input_closed = False
    next_sequence = 0
    next_output = 0

    try:
        while not input_closed or pending:
            while not input_closed and len(pending) < parallelism:
                value = await source.take()
                if value is None:
                    input_closed = True
                    break
                pending[next_sequence] = (
                    value,
                    asyncio.create_task(
                        asyncio.to_thread(_transduce_one, xform, value)
                    ),
                )
                next_sequence += 1

            if not pending:
                continue

            done, _ = await asyncio.wait(
                [task for _, task in pending.values()],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for sequence, (value, task) in list(pending.items()):
                if task not in done:
                    continue
                del pending[sequence]
                try:
                    completed[sequence] = task.result()
                except BaseException as exc:
                    if error_handler is None:
                        raise
                    replacement = await asyncio.to_thread(error_handler, exc, value)
                    completed[sequence] = (
                        [] if replacement is None else list(replacement)
                    )

            while next_output in completed:
                for value in completed.pop(next_output):
                    if not await destination.put(value):
                        return
                next_output += 1
    finally:
        for _, task in pending.values():
            task.cancel()
        if pending:
            await asyncio.gather(
                *(task for _, task in pending.values()), return_exceptions=True
            )
        if close_output:
            destination.close()


def pipeline(
    parallelism: int,
    source: Channel,
    destination: Channel,
    xform: Callable[..., Any],
    *,
    close_output: bool = True,
    error_handler: Callable[[BaseException, Any], Iterable[Any] | None] | None = None,
) -> asyncio.Task[None]:
    """Transform source values concurrently and emit results in input order.

    ``xform`` is a normal synchronous Basilisp/Python transducer. Each input is
    processed independently and may emit zero or more values. Work admission is
    bounded by ``parallelism``; transformations run in worker threads so a
    blocking synchronous transform does not stall the owning event loop.

    A transform failure ends the returned task unless ``error_handler`` is
    supplied. The handler receives ``(exception, input)`` and may return an
    iterable of replacement output values, or ``None`` to drop the input.
    """

    if isinstance(parallelism, bool) or not isinstance(parallelism, int):
        raise TypeError("pipeline parallelism must be a positive integer")
    if parallelism < 1:
        raise ValueError("pipeline parallelism must be a positive integer")
    if not callable(xform):
        raise TypeError("pipeline xform must be callable")
    if error_handler is not None and not callable(error_handler):
        raise TypeError("pipeline error_handler must be callable")
    return submit_coroutine(
        _pipeline(
            parallelism,
            source,
            destination,
            xform,
            close_output=close_output,
            error_handler=error_handler,
        )
    )


async def _collect_channel(channel: Channel) -> list[Any]:
    values: list[Any] = []
    while (value := await channel.take()) is not None:
        values.append(value)
    return values


async def _call_async_pipeline_function(
    function: Callable[[Any, Channel], Any], value: Any, output: Channel
) -> list[Any]:
    result = function(value, output)
    if not inspect.isawaitable(result):
        return await _collect_channel(output)

    runner = asyncio.ensure_future(result)
    collector = asyncio.create_task(_collect_channel(output))
    try:
        done, _ = await asyncio.wait(
            {runner, collector}, return_when=asyncio.FIRST_EXCEPTION
        )
        if runner in done and (exception := runner.exception()) is not None:
            collector.cancel()
            await asyncio.gather(collector, return_exceptions=True)
            raise exception
        values = await collector
        await runner
        return values
    except BaseException:
        for task in (runner, collector):
            if not task.done():
                task.cancel()
        await asyncio.gather(runner, collector, return_exceptions=True)
        raise


async def _pipeline_async(
    parallelism: int,
    source: Channel,
    destination: Channel,
    function: Callable[[Any, Channel], Any],
    *,
    close_output: bool,
) -> None:
    pending: dict[int, asyncio.Task[list[Any]]] = {}
    completed: dict[int, list[Any]] = {}
    input_closed = False
    next_sequence = 0
    next_output = 0

    try:
        while not input_closed or pending:
            while not input_closed and len(pending) < parallelism:
                value = await source.take()
                if value is None:
                    input_closed = True
                    break
                result_channel = Channel(1)
                pending[next_sequence] = asyncio.create_task(
                    _call_async_pipeline_function(function, value, result_channel)
                )
                next_sequence += 1

            if not pending:
                continue

            done, _ = await asyncio.wait(
                pending.values(), return_when=asyncio.FIRST_COMPLETED
            )
            for sequence, task in list(pending.items()):
                if task not in done:
                    continue
                del pending[sequence]
                completed[sequence] = task.result()

            while next_output in completed:
                for value in completed.pop(next_output):
                    if not await destination.put(value):
                        return
                next_output += 1
    finally:
        for task in pending.values():
            task.cancel()
        if pending:
            await asyncio.gather(*pending.values(), return_exceptions=True)
        if close_output:
            destination.close()


def pipeline_async(
    parallelism: int,
    source: Channel,
    destination: Channel,
    function: Callable[[Any, Channel], Any],
    *,
    close_output: bool = True,
) -> asyncio.Task[None]:
    """Run callback-shaped asynchronous channel work with ordered output.

    ``function`` receives ``(input, output_channel)``. It may synchronously
    arrange work and return, or return a coroutine. Results are read from the
    per-input output channel until it closes, and then emitted to
    ``destination`` in source order.
    """

    if isinstance(parallelism, bool) or not isinstance(parallelism, int):
        raise TypeError("pipeline parallelism must be a positive integer")
    if parallelism < 1:
        raise ValueError("pipeline parallelism must be a positive integer")
    if not callable(function):
        raise TypeError("pipeline_async function must be callable")
    return submit_coroutine(
        _pipeline_async(
            parallelism,
            source,
            destination,
            function,
            close_output=close_output,
        )
    )
