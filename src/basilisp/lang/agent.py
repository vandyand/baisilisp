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
            return self._active or bool(self._queue)

    def submit(self, executor: Executor, f: Callable[..., T], *args: Any) -> "Agent[T]":
        with self._condition:
            if self._error is not None and self._error_mode == "fail":
                return self
            self._queue.append((executor, f, args))
            if not self._active:
                self._schedule_next()
            return self

    def submit_args(
        self, executor: Executor, f: Callable[..., T], args: tuple[Any, ...] | None
    ) -> "Agent[T]":
        """Submit an action when its argument sequence is already collected."""
        return self.submit(executor, f, *(args or ()))

    def await_completion(self, timeout: float | None = None) -> bool:
        with self._condition:
            return self._condition.wait_for(lambda: not self._active and not self._queue, timeout)

    def clear_error(self) -> None:
        with self._condition:
            self._error = None
            self._condition.notify_all()

    def restart(self, state: T | None = None, clear_actions: bool = False) -> "Agent[T]":
        with self._condition:
            if state is not None:
                self._validate(state)
                old = self._state
                self._state = state
                self._notify_watches(old, state)
            self._error = None
            if clear_actions:
                self._queue.clear()
            if not self._active and self._queue:
                self._schedule_next()
            self._condition.notify_all()
            return self

    def set_error_mode(self, mode: str) -> None:
        if mode not in {"fail", "continue"}:
            raise ValueError("Agent error mode must be 'fail' or 'continue'")
        with self._lock:
            self._error_mode = mode

    def set_error_handler(self, handler) -> None:
        with self._lock:
            self._error_handler = handler

    def _schedule_next(self) -> None:
        if not self._queue:
            self._active = False
            self._condition.notify_all()
            return
        executor, _, _ = self._queue[0]
        self._active = True
        executor.submit(self._run_one)

    def _run_one(self) -> None:
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
            with self._condition:
                self._error = exc
                handler = self._error_handler
                if self._error_mode == "fail":
                    self._queue.clear()
                self._active = False
                self._condition.notify_all()
            if handler is not None:
                handler(self, exc)
            with self._condition:
                if self._error_mode == "continue":
                    self._schedule_next()
            return

        with self._condition:
            old = self._state
            self._state = new_state
            self._notify_watches(old, new_state)
            self._active = False
            self._schedule_next()
