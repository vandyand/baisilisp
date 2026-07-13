"""Stateful concurrency coverage for the experimental STM implementation."""

from __future__ import annotations

import concurrent.futures
import time

from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from basilisp import main

main.init()

import basilisp.core as core  # isort: skip
from basilisp.lang import stm


class TransactionHistoryMachine(RuleBasedStateMachine):
    """Compare concurrent Ref transfers with their serialized arithmetic model."""

    def __init__(self) -> None:
        super().__init__()
        self._first = stm.Ref(0)
        self._second = stm.Ref(0)
        self._model_first = 0
        self._model_second = 0
        self._commits = 0
        self._commuted = stm.Ref(0)
        self._model_commuted = 0
        self._commute_commits = 0
        self._ensured = stm.Ref(0)
        self._model_ensured = 0
        self._ensure_commits = 0
        self._core_ref = core.ref(0)
        self._model_core = 0
        self._core_commits = 0

    @rule(
        deltas=st.lists(
            st.integers(min_value=-100, max_value=100), min_size=1, max_size=8
        ),
        workers=st.integers(min_value=1, max_value=4),
    )
    def concurrent_transfers(self, deltas: list[int], workers: int) -> None:
        def transfer(delta: int) -> None:
            def body() -> None:
                first = self._first.deref()
                second = self._second.deref()
                # Give simultaneously scheduled bodies a chance to contend.
                time.sleep(0)
                stm.ref_set(self._first, first + delta)
                stm.ref_set(self._second, second - delta)

            stm.run_transaction(body)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(workers, len(deltas))
        ) as executor:
            futures = [executor.submit(transfer, delta) for delta in deltas]
            for future in futures:
                future.result(timeout=5)

        self._model_first += sum(deltas)
        self._model_second -= sum(deltas)
        self._commits += len(deltas)

    @rule(
        deltas=st.lists(
            st.integers(min_value=-100, max_value=100), min_size=1, max_size=8
        ),
        workers=st.integers(min_value=1, max_value=4),
    )
    def concurrent_commutes(self, deltas: list[int], workers: int) -> None:
        def commute(delta: int) -> None:
            def add(value: int, amount: int) -> int:
                time.sleep(0)
                return value + amount

            stm.run_transaction(lambda: stm.commute(self._commuted, add, delta))

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(workers, len(deltas))
        ) as executor:
            futures = [executor.submit(commute, delta) for delta in deltas]
            for future in futures:
                future.result(timeout=5)

        self._model_commuted += sum(deltas)
        self._commute_commits += len(deltas)

    @rule(
        deltas=st.lists(
            st.integers(min_value=-100, max_value=100), min_size=1, max_size=8
        ),
        workers=st.integers(min_value=1, max_value=4),
    )
    def concurrent_ensured_commutes(self, deltas: list[int], workers: int) -> None:
        def ensure_and_commute(delta: int) -> None:
            def add(value: int, amount: int) -> int:
                time.sleep(0)
                return value + amount

            def body() -> None:
                stm.ensure(self._ensured)
                stm.commute(self._ensured, add, delta)

            stm.run_transaction(body)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(workers, len(deltas))
        ) as executor:
            futures = [executor.submit(ensure_and_commute, delta) for delta in deltas]
            for future in futures:
                future.result(timeout=5)

        self._model_ensured += sum(deltas)
        self._ensure_commits += len(deltas)

    @rule(
        deltas=st.lists(
            st.integers(min_value=-100, max_value=100), min_size=1, max_size=8
        ),
        workers=st.integers(min_value=1, max_value=4),
    )
    def concurrent_core_transactions(self, deltas: list[int], workers: int) -> None:
        """Exercise the public core wrappers under the same contention model."""

        def alter_core(delta: int) -> int:
            def body() -> int:
                value = self._core_ref.deref()
                time.sleep(0)
                return core.alter(self._core_ref, lambda current: current + delta)

            return core.run_transaction(body)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(workers, len(deltas))
        ) as executor:
            futures = [executor.submit(alter_core, delta) for delta in deltas]
            for future in futures:
                future.result(timeout=5)

        self._model_core += sum(deltas)
        self._core_commits += len(deltas)

    @rule(delta=st.integers(min_value=-100, max_value=100))
    def aborted_core_transaction_leaves_no_write(self, delta: int) -> None:
        """A public wrapper must preserve STM's all-or-nothing failure boundary."""

        before = self._core_ref.deref()

        def abort() -> None:
            core.alter(self._core_ref, lambda current: current + delta)
            raise RuntimeError("abort this transaction")

        try:
            core.run_transaction(abort)
        except RuntimeError as exc:
            assert "abort this transaction" == str(exc)
        else:  # pragma: no cover - Hypothesis makes this branch diagnostic only
            raise AssertionError("transaction did not propagate its failure")
        assert before == self._core_ref.deref()

    @invariant()
    def refs_match_the_serialized_model(self) -> None:
        assert self._model_first == self._first.deref()
        assert self._model_second == self._second.deref()
        assert self._commits == self._first.version
        assert self._commits == self._second.version
        assert 0 == self._first.deref() + self._second.deref()
        assert self._model_commuted == self._commuted.deref()
        assert self._commute_commits == self._commuted.version
        assert self._model_ensured == self._ensured.deref()
        assert self._ensure_commits == self._ensured.version
        assert self._model_core == self._core_ref.deref()
        assert self._core_commits == self._core_ref.version


TestTransactionHistoryMachine = TransactionHistoryMachine.TestCase
TestTransactionHistoryMachine.settings = settings(
    max_examples=40,
    stateful_step_count=16,
    deadline=None,
)
