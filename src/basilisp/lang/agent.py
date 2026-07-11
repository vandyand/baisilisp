"""Serialized, executor-backed state agents."""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable
from concurrent.futures import Executor
from typing import Any, Generic, TypeVar

from basilisp.lang import map as lmap
from basilisp.lang.interfaces import IPersistentMap, RefValidator
from basilisp.lang.reference import RefBase

T = TypeVar("T")
_UNSET = object()


class Agent(RefBase[T], Generic[T]):
    """A mutable reference whose submitted actions execute sequentially."""

    __slots__ = (
        "_meta",
        "_state",
        "_lock",
        "_watches",
        "_validator",
        "_condition",
        "_queue",
        "_active",
        "_error",
        "_error_mode",
        "_error_handler",
    )

    def __init__(
        self,
        state: T,
        meta: IPersistentMap | None = None,
        validator: RefValidator | None = None,
        error_mode: str = "fail",
        error_handler: Callable[["Agent[T]", BaseException], Any] | None = None,
    ) -> None:
        self._meta = meta
        self._state = state
        self._lock = threading.RLock()
        self._watches = lmap.EMPTY
        self._validator = validator
        self._condition = threading.Condition(self._lock)
        self._queue: deque[tuple[Executor, Callable[..., T], tuple[Any, ...]]] = deque()
        self._active = False
        self._error: BaseException | None = None
        if error_mode not in {"fail", "continue"}:
            raise ValueError("Agent error mode must be 'fail' or 'continue'")
        self._error_mode = error_mode
        self._error_handler = error_handler
        if validator is not None:
            self._validate(state)

    def deref(self) -> T:
        with self._lock:
            return self._state

    @property
    def error(self) -> BaseException | None:
        with self._lock:
            return self._error

    def get_error(self) -> BaseException | None:
        return self.error

    @property
    def error_mode(self) -> str:
        with self._lock:
            return self._error_mode

    def get_error_mode(self) -> str:
        return self.error_mode

    @property
    def error_handler(self):
        with self._lock:
            return self._error_handler

    def get_error_handler(self):
        return self.error_handler

    def pending(self) -> bool:
        with self._lock:
            return (
                self._active
                or (self._error is None or self._error_mode == "continue")
                and bool(self._queue)
            )

    def submit(self, executor: Executor, f: Callable[..., T], *args: Any) -> "Agent[T]":
        scheduled = None
        scheduling_error = None
        with self._condition:
            if self._error is not None and self._error_mode == "fail":
                raise RuntimeError(
                    "Cannot send an action to a failed agent"
                ) from self._error
            self._queue.append((executor, f, args))
            if not self._active:
                try:
                    scheduled = self._schedule_next()
                except BaseException as exc:
                    self._queue.popleft()
                    scheduling_error = exc
        if scheduled is not None:
            self._observe_scheduled_action(scheduled)
        if scheduling_error is not None:
            self._handle_failure(scheduling_error)
            raise scheduling_error
        return self

    def submit_args(
        self, executor: Executor, f: Callable[..., T], args: tuple[Any, ...] | None
    ) -> "Agent[T]":
        """Submit an action when its argument sequence is already collected."""
        return self.submit(executor, f, *(args or ()))

    def await_completion(
        self, timeout: float | None = None, *, wait_on_failure: bool = False
    ) -> bool:
        """Wait for queued work, optionally retaining Clojure await1 failure semantics."""
        with self._condition:
            return self._condition.wait_for(
                lambda: not self._active
                and (
                    not self._queue
                    or self._error is not None
                    and self._error_mode == "fail"
                )
                and (
                    not wait_on_failure
                    or self._error is None
                    or self._error_mode != "fail"
                ),
                timeout,
            )

    def clear_error(self) -> None:
        with self._condition:
            self._error = None
            self._condition.notify_all()

    def restart(self, state: Any = _UNSET, clear_actions: bool = False) -> "Agent[T]":
        scheduled = None
        scheduling_error = None
        with self._condition:
            if self._active:
                raise RuntimeError("Cannot restart an agent while an action is running")
            if state is not _UNSET:
                self._validate(state)
                old = self._state
                self._state = state
                self._notify_watches(old, state)
            self._error = None
            if clear_actions:
                self._queue.clear()
            if not self._active and self._queue:
                try:
                    scheduled = self._schedule_next()
                except BaseException as exc:
                    self._queue.popleft()
                    scheduling_error = exc
            self._condition.notify_all()
        if scheduled is not None:
            self._observe_scheduled_action(scheduled)
        if scheduling_error is not None:
            self._handle_failure(scheduling_error)
            raise scheduling_error
        return self

    def set_error_mode(self, mode: str) -> None:
        if mode not in {"fail", "continue"}:
            raise ValueError("Agent error mode must be 'fail' or 'continue'")
        with self._lock:
            self._error_mode = mode

    def set_error_handler(self, handler) -> None:
        with self._lock:
            self._error_handler = handler

    def _schedule_next(self):
        if not self._queue:
            self._active = False
            self._condition.notify_all()
            return None
        executor, _, _ = self._queue[0]
        execution_started = threading.Event()
        self._active = True
        future = executor.submit(self._run_one, execution_started)
        return future, execution_started

    def _observe_scheduled_action(self, scheduled) -> None:
        future, execution_started = scheduled
        future.add_done_callback(
            lambda completed: self._handle_pre_start_failure(
                completed, execution_started
            )
        )

    def _handle_pre_start_failure(
        self, future, execution_started: threading.Event
    ) -> None:
        if execution_started.is_set():
            return
        try:
            error = future.exception()
        except BaseException as exc:
            error = exc
        if error is None:
            error = RuntimeError("Agent executor completed without starting its action")
        with self._condition:
            if not self._active:
                return
            self._queue.popleft()
        self._handle_failure(error)

    def _run_one(self, execution_started: threading.Event) -> None:
        execution_started.set()
        with self._condition:
            if not self._queue:
                self._active = False
                self._condition.notify_all()
                return
            _, f, args = self._queue.popleft()
            state = self._state

        try:
            new_state = f(state, *args)
            self._validate(new_state)
        except BaseException as exc:  # preserve user action failures on the agent
            self._handle_failure(exc)
            return

        with self._condition:
            old = self._state
            self._state = new_state
            watcher_error = None
            scheduled = None
            scheduling_error = None
            try:
                self._notify_watches(old, new_state)
            except BaseException as exc:
                watcher_error = exc
            finally:
                self._active = False
                try:
                    scheduled = self._schedule_next()
                except BaseException as exc:
                    self._queue.popleft()
                    scheduling_error = exc
        if scheduled is not None:
            self._observe_scheduled_action(scheduled)
        if scheduling_error is not None:
            self._handle_failure(scheduling_error)
        if watcher_error is not None:
            raise watcher_error

    def _handle_failure(self, error: BaseException) -> None:
        scheduled = None
        scheduling_error = None
        handler_error = None
        with self._condition:
            self._error = error
            handler = self._error_handler
        try:
            if handler is not None:
                handler(self, error)
        except BaseException as exc:
            handler_error = exc
        finally:
            with self._condition:
                self._active = False
                if self._error_mode == "continue":
                    try:
                        scheduled = self._schedule_next()
                    except BaseException as exc:
                        self._queue.popleft()
                        scheduling_error = exc
                else:
                    self._condition.notify_all()
        if scheduled is not None:
            self._observe_scheduled_action(scheduled)
        if scheduling_error is not None:
            self._handle_failure(scheduling_error)
        if handler_error is not None:
            raise handler_error
