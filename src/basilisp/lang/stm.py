"""An optimistic, in-memory software transactional memory implementation."""

from __future__ import annotations

import contextvars
import inspect
import numbers
from collections import deque
from contextlib import ExitStack
from typing import Any, Callable, Generic, TypeVar

from basilisp.lang import keyword as kw
from basilisp.lang import map as lmap
from basilisp.lang import vector as vec
from basilisp.lang.exception import ExceptionInfo
from basilisp.lang.interfaces import IPersistentMap, RefValidator
from basilisp.lang.reference import RefBase

T = TypeVar("T")
R = TypeVar("R")
_Commute = tuple[Callable[..., Any], tuple[Any, ...]]

_ATTEMPTS = kw.keyword("attempts", ns="basilisp.stm")
_CONFLICTS = kw.keyword("conflicts", ns="basilisp.stm")
_REF_ID = kw.keyword("ref-id", ns="basilisp.stm")
_READ_VERSION = kw.keyword("read-version", ns="basilisp.stm")
_CURRENT_VERSION = kw.keyword("current-version", ns="basilisp.stm")
_NO_HISTORY_VALUE = object()


def _history_limit(value: Any, kind: str) -> int:
    """Coerce a Clojure numeric history control to a signed 32-bit integer."""
    if isinstance(value, bool) or not isinstance(value, numbers.Number):
        raise TypeError(f"Ref {kind} history must be numeric")
    try:
        limit = int(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"Ref {kind} history must be a finite integer") from exc
    if not -(2**31) <= limit < 2**31:
        raise OverflowError(f"Ref {kind} history integer overflow")
    return limit


class Ref(RefBase[T], Generic[T]):
    """A versioned reference whose updates are committed by ``run_transaction``."""

    __slots__ = (
        "_history",
        "_lock",
        "_max_history",
        "_meta",
        "_min_history",
        "_state",
        "_validator",
        "_version",
        "_watches",
    )

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
        # Clojure's default is to retain no history eagerly, while allowing a
        # transaction implementation to grow up to ten entries when it needs
        # old snapshots. Basilisp's optimistic transactions retain their own
        # read values, so the minimum history is the portable observable
        # retention requirement here.
        self._history: deque[T] = deque()
        self._min_history = 0
        self._max_history = 10
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

    def history_count(self) -> int:
        """Return the number of retained committed Ref values."""
        with self._lock:
            return len(self._history)

    def min_history(self) -> int:
        """Return the configured minimum number of retained values."""
        with self._lock:
            return self._min_history

    def set_min_history(self, value: Any) -> "Ref[T]":
        """Set the minimum committed-value history retained by this Ref.

        As with Clojure, changing a control does not eagerly discard values
        which were already retained. Later commits grow the history until the
        new non-negative minimum is satisfied.
        """
        with self._lock:
            self._min_history = _history_limit(value, "minimum")
        return self

    def max_history(self) -> int:
        """Return the configured maximum number of retained values."""
        with self._lock:
            return self._max_history

    def set_max_history(self, value: Any) -> "Ref[T]":
        """Set the maximum history control and return this Ref.

        Basilisp transactions do not consume historical snapshots, unlike the
        JVM STM. The control is still retained because it is public Ref state;
        a minimum history always takes precedence over a smaller maximum, as
        it does in Clojure.
        """
        with self._lock:
            self._max_history = _history_limit(value, "maximum")
        return self

    def _record_history(self, value: T) -> None:
        """Retain a prior committed value when the configured minimum needs it.

        The caller holds ``_lock``. History is intentionally never trimmed by
        changing a control: Clojure retains entries already accumulated under
        an earlier minimum. A later commit therefore only fills a higher
        minimum and leaves existing values intact.
        """
        target = max(0, self._min_history)
        if len(self._history) < target:
            self._history.append(value)


class _Transaction:
    def __init__(self) -> None:
        self._reads: dict[Ref[Any], tuple[Any, int]] = {}
        self._writes: dict[Ref[Any], Any] = {}
        self._commutes: dict[Ref[Any], list[_Commute]] = {}
        self._commuted_values: dict[Ref[Any], Any] = {}
        self._ensures: set[Ref[Any]] = set()
        self._after_commit: list[Callable[[], Any]] = []
        self._conflicts: tuple[tuple[Ref[Any], int, int], ...] = ()

    def read(self, ref: Ref[T]) -> T:
        if ref in self._writes:
            return self._writes[ref]
        if ref in self._commuted_values:
            return self._commuted_values[ref]
        read = self._reads.get(ref)
        if read is None:
            read = ref._read_committed()
            self._reads[ref] = read
        return read[0]

    def alter(self, ref: Ref[T], f: Callable[..., T], *args: Any) -> T:
        if ref in self._commutes:
            raise RuntimeError("cannot alter a Ref after commute")
        value = f(self.read(ref), *args)
        self._writes[ref] = value
        return value

    def ref_set(self, ref: Ref[T], value: T) -> T:
        if ref in self._commutes:
            raise RuntimeError("cannot ref-set a Ref after commute")
        self.read(ref)
        self._writes[ref] = value
        return value

    def commute(self, ref: Ref[T], f: Callable[..., T], *args: Any) -> T:
        """Stage a commutative update for replay against the committed value."""
        if ref in self._writes:
            value = self._writes[ref]
        elif ref in self._commuted_values:
            value = self._commuted_values[ref]
        elif ref in self._reads:
            value = self._reads[ref][0]
        else:
            value, version = ref._read_committed()
            self._reads[ref] = (value, version)

        result = f(value, *args)
        self._commutes.setdefault(ref, []).append((f, args))
        if ref in self._writes:
            self._writes[ref] = result
        else:
            self._commuted_values[ref] = result
        return result

    def ensure(self, ref: Ref[T]) -> T:
        """Protect ``ref`` from version changes until this transaction commits."""
        value = self.read(ref)
        self._ensures.add(ref)
        return value

    def after_commit(self, action: Callable[[], Any]) -> None:
        self._after_commit.append(action)

    @property
    def after_commit_actions(self) -> tuple[Callable[[], Any], ...]:
        return tuple(self._after_commit)

    @property
    def conflicts(self) -> tuple[tuple[Ref[Any], int, int], ...]:
        """Return the read versions which invalidated the last commit attempt."""
        return self._conflicts

    def commit(self) -> list[tuple[Ref[Any], Any, Any]] | None:
        """Commit all writes, or return ``None`` when a read version changed."""
        pure_commutes = set(self._commutes) - set(self._writes)
        refs = sorted(
            set(self._reads) | set(self._writes) | set(self._commutes), key=id
        )
        with ExitStack() as locks:
            for ref in refs:
                locks.enter_context(ref._lock)
            conflicts = tuple(
                (ref, version, ref._version)
                for ref, (_, version) in self._reads.items()
                if (ref not in pure_commutes or ref in self._ensures)
                and ref._version != version
            )
            if conflicts:
                self._conflicts = conflicts
                return None

            changes = [(ref, ref._state, value) for ref, value in self._writes.items()]
            for ref in pure_commutes:
                value = ref._state
                for f, args in self._commutes[ref]:
                    value = f(value, *args)
                changes.append((ref, ref._state, value))
            for ref, _old, value in changes:
                ref._validate(value)
            for ref, _old, value in changes:
                ref._record_history(ref._state)
                ref._state = value
                ref._version += 1
            return changes


_CURRENT_TRANSACTION: contextvars.ContextVar[_Transaction | None] = (
    contextvars.ContextVar("basilisp_stm_transaction", default=None)
)


def in_transaction() -> bool:
    """Return whether the current execution context is in a transaction."""
    return _CURRENT_TRANSACTION.get() is not None


def run_transaction(thunk: Callable[[], R], *, max_attempts: int | None = None) -> R:
    """Run ``thunk`` transactionally, retrying when a read version conflicts.

    ``max_attempts`` is an experimental outer-transaction control. When set to
    a positive integer, exhausting it raises ``ExceptionInfo`` containing the
    attempt count and the Ref versions which conflicted on the final attempt.
    """
    _validate_max_attempts(max_attempts)
    if _CURRENT_TRANSACTION.get() is not None:
        if max_attempts is not None:
            raise RuntimeError("max_attempts may only be set on an outer transaction")
        return _evaluate_transaction_body(thunk)

    attempts = 0
    while True:
        attempts += 1
        transaction = _Transaction()
        token = _CURRENT_TRANSACTION.set(transaction)
        try:
            result = _evaluate_transaction_body(thunk)
            changes = transaction.commit()
        finally:
            _CURRENT_TRANSACTION.reset(token)
        if changes is None:
            if max_attempts is not None and attempts >= max_attempts:
                raise _conflict_error(attempts, transaction.conflicts)
            continue
        try:
            for ref, old, new in changes:
                ref._notify_watches(old, new)
        finally:
            for action in transaction.after_commit_actions:
                action()
        return result


def alter(ref: Ref[T], f: Callable[..., T], *args: Any) -> T:
    """Stage ``f`` applied to the in-transaction value of ``ref``."""
    return _require_transaction().alter(ref, f, *args)


def ref_set(ref: Ref[T], value: T) -> T:
    """Stage ``value`` as the new in-transaction value of ``ref``."""
    return _require_transaction().ref_set(ref, value)


def commute(ref: Ref[T], f: Callable[..., T], *args: Any) -> T:
    """Stage ``f`` for commit-time replay against ``ref``'s latest value.

    ``f`` runs once against the in-transaction value and again during a
    successful commit. It must therefore be retry-safe and commutative, or the
    caller must accept last-writer-wins behavior.
    """
    return _require_transaction().commute(ref, f, *args)


def ensure(ref: Ref[T]) -> T:
    """Return and protect ``ref``'s in-transaction value until commit.

    Ordinary reads are already validated by this optimistic engine. ``ensure``
    is significant when a Ref is otherwise updated only by ``commute``, which
    normally permits newer committed values at the replay point.
    """
    return _require_transaction().ensure(ref)


def ref_history_count(ref: Ref[Any]) -> int:
    """Return the number of committed values retained by ``ref``."""
    return _require_ref(ref).history_count()


def ref_min_history(ref: Ref[Any], value: Any = _NO_HISTORY_VALUE) -> int | Ref[Any]:
    """Get, or set and return, ``ref``'s minimum history control."""
    checked_ref = _require_ref(ref)
    if value is _NO_HISTORY_VALUE:
        return checked_ref.min_history()
    return checked_ref.set_min_history(value)


def ref_max_history(ref: Ref[Any], value: Any = _NO_HISTORY_VALUE) -> int | Ref[Any]:
    """Get, or set and return, ``ref``'s maximum history control."""
    checked_ref = _require_ref(ref)
    if value is _NO_HISTORY_VALUE:
        return checked_ref.max_history()
    return checked_ref.set_max_history(value)


def after_commit(action: Callable[[], Any]) -> None:
    """Run ``action`` once after the current transaction commits successfully.

    Actions registered by failed or retried transaction attempts are discarded.
    An action runs after committed Ref watches and cannot roll back the already
    published transaction state.
    """
    if not callable(action):
        raise TypeError("an after-commit action must be callable")
    _require_transaction().after_commit(action)


def io_bang() -> None:
    """Reject an explicitly marked impure operation within a transaction."""
    if in_transaction():
        raise RuntimeError("I/O is not allowed within a transaction")


def _validate_max_attempts(max_attempts: int | None) -> None:
    if max_attempts is None:
        return
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int):
        raise TypeError("max_attempts must be a positive integer or None")
    if max_attempts < 1:
        raise ValueError("max_attempts must be a positive integer")


def _conflict_error(
    attempts: int, conflicts: tuple[tuple[Ref[Any], int, int], ...]
) -> ExceptionInfo:
    return ExceptionInfo(
        "Transaction conflict limit exceeded",
        lmap.map(
            {
                _ATTEMPTS: attempts,
                _CONFLICTS: vec.vector(
                    lmap.map(
                        {
                            _REF_ID: id(ref),
                            _READ_VERSION: read_version,
                            _CURRENT_VERSION: current_version,
                        }
                    )
                    for ref, read_version, current_version in conflicts
                ),
            }
        ),
    )


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


def _require_ref(ref: Any) -> Ref[Any]:
    if not isinstance(ref, Ref):
        raise TypeError("Ref history operations require a Ref")
    return ref
