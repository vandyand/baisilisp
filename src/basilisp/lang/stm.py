"""An optimistic, in-memory software transactional memory implementation."""

from __future__ import annotations

import contextvars
import inspect
from contextlib import ExitStack
from typing import Any, Callable, Generic, TypeVar

from basilisp.lang import map as lmap
from basilisp.lang.interfaces import IPersistentMap, RefValidator
from basilisp.lang.reference import RefBase

T = TypeVar("T")
R = TypeVar("R")


class Ref(RefBase[T], Generic[T]):
    """A versioned reference whose updates are committed by ``run_transaction``."""

    __slots__ = ("_meta", "_state", "_version", "_lock", "_watches", "_validator")

    def __init__(
        self,
        state: T,
        meta: IPersistentMap | None = None,
        validator: RefValidator[T] | None = None,
    ) -> None:
        import threading

        self._meta = meta
        self._state = state
        self._version = 0
        self._lock = threading.RLock()
        self._watches = lmap.EMPTY
        self._validator = validator
        if validator is not None:
            self._validate(state)

    def deref(self) -> T:
        transaction = _CURRENT_TRANSACTION.get()
        if transaction is not None:
            return transaction.read(self)
        with self._lock:
            return self._state

    @property
    def version(self) -> int:
        """Return the committed version, primarily for diagnostics and tests."""
        with self._lock:
            return self._version

    def _read_committed(self) -> tuple[T, int]:
        with self._lock:
            return self._state, self._version


class _Transaction:
    def __init__(self) -> None:
        self._reads: dict[Ref[Any], tuple[Any, int]] = {}
        self._writes: dict[Ref[Any], Any] = {}

    def read(self, ref: Ref[T]) -> T:
        if ref in self._writes:
            return self._writes[ref]
        read = self._reads.get(ref)
        if read is None:
            read = ref._read_committed()
            self._reads[ref] = read
        return read[0]

    def alter(self, ref: Ref[T], f: Callable[..., T], *args: Any) -> T:
        value = f(self.read(ref), *args)
        self._writes[ref] = value
        return value

    def ref_set(self, ref: Ref[T], value: T) -> T:
        self.read(ref)
        self._writes[ref] = value
        return value

    def commit(self) -> list[tuple[Ref[Any], Any, Any]] | None:
        """Commit all writes, or return ``None`` when a read version changed."""
        refs = sorted(set(self._reads) | set(self._writes), key=id)
        with ExitStack() as locks:
            for ref in refs:
                locks.enter_context(ref._lock)
            if any(
                ref._version != version for ref, (_, version) in self._reads.items()
            ):
                return None

            changes = [(ref, ref._state, value) for ref, value in self._writes.items()]
            for ref, _old, value in changes:
                ref._validate(value)
            for ref, _old, value in changes:
                ref._state = value
                ref._version += 1
            return changes


_CURRENT_TRANSACTION: contextvars.ContextVar[_Transaction | None] = (
    contextvars.ContextVar("basilisp_stm_transaction", default=None)
)


def in_transaction() -> bool:
    """Return whether the current execution context is in a transaction."""
    return _CURRENT_TRANSACTION.get() is not None


def run_transaction(thunk: Callable[[], R]) -> R:
    """Run ``thunk`` transactionally, retrying when a read version conflicts."""
    if _CURRENT_TRANSACTION.get() is not None:
        return _evaluate_transaction_body(thunk)

    while True:
        transaction = _Transaction()
        token = _CURRENT_TRANSACTION.set(transaction)
        try:
            result = _evaluate_transaction_body(thunk)
            changes = transaction.commit()
        finally:
            _CURRENT_TRANSACTION.reset(token)
        if changes is None:
            continue
        for ref, old, new in changes:
            ref._notify_watches(old, new)
        return result


def alter(ref: Ref[T], f: Callable[..., T], *args: Any) -> T:
    """Stage ``f`` applied to the in-transaction value of ``ref``."""
    return _require_transaction().alter(ref, f, *args)


def ref_set(ref: Ref[T], value: T) -> T:
    """Stage ``value`` as the new in-transaction value of ``ref``."""
    return _require_transaction().ref_set(ref, value)


def _evaluate_transaction_body(thunk: Callable[[], R]) -> R:
    result = thunk()
    if inspect.isawaitable(result):
        close = getattr(result, "close", None)
        if callable(close):
            close()
        raise TypeError("a transaction body must not return an awaitable")
    return result


def _require_transaction() -> _Transaction:
    transaction = _CURRENT_TRANSACTION.get()
    if transaction is None:
        raise RuntimeError("this operation requires an active transaction")
    return transaction
