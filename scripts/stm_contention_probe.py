#!/usr/bin/env python3
"""Measure bounded optimistic-STM contention without changing runtime policy."""

from __future__ import annotations

import argparse
import concurrent.futures
import statistics
import threading
import time

from basilisp.lang import stm


def _positive_integer(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _run_round(workers: int, transactions: int) -> tuple[int, int, float, int, float]:
    ref = stm.Ref(0)
    attempts: list[int] = []
    attempts_lock = threading.Lock()
    start = threading.Barrier(workers)

    def worker() -> None:
        start.wait(timeout=5)
        for _ in range(transactions):
            local_attempts = 0

            def body() -> int:
                nonlocal local_attempts
                local_attempts += 1
                value = ref.deref()
                # Make the read/commit window visible without external effects.
                time.sleep(0)
                return stm.ref_set(ref, value + 1)

            stm.run_transaction(body)
            with attempts_lock:
                attempts.append(local_attempts)

    began = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(worker) for _ in range(workers)]
        for future in futures:
            future.result(timeout=30)
    elapsed = time.perf_counter() - began

    commits = workers * transactions
    assert commits == ref.deref() == ref.version
    assert commits == len(attempts)
    return (
        commits,
        sum(attempts) - commits,
        statistics.mean(attempts),
        max(attempts),
        elapsed,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run an optimistic STM contention sample and report retry counts."
    )
    parser.add_argument("--workers", type=_positive_integer, default=8)
    parser.add_argument("--transactions", type=_positive_integer, default=100)
    parser.add_argument("--rounds", type=_positive_integer, default=3)
    args = parser.parse_args()

    for round_number in range(1, args.rounds + 1):
        commits, retries, mean_attempts, max_attempts, elapsed = _run_round(
            args.workers, args.transactions
        )
        print(
            f"round={round_number} commits={commits} retries={retries} "
            f"mean_attempts={mean_attempts:.3f} max_attempts={max_attempts} "
            f"seconds={elapsed:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
