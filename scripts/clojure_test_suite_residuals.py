"""Helpers for running the external ``clojure-test-suite`` gate.

The upstream suite contains Basilisp-specific ``:lpy`` branches from an older
runtime model. Several of those branches now contradict the fork's explicit
Clojure-parity fixtures, especially around distinct characters, strict numeric
coercions, UTF-16 ``subs`` bounds, ``case`` numeric dispatch, and ``merge`` edge
semantics. Keep those files out of the broad external gate until the suite is
updated upstream; the authoritative parity coverage lives in ``tests/conformance``.
"""

from __future__ import annotations

import argparse
from pathlib import Path


RESIDUAL_CORE_TEST_FILES: tuple[str, ...] = (
    "test/clojure/core_test/byte.cljc",
    "test/clojure/core_test/case.cljc",
    "test/clojure/core_test/char.cljc",
    "test/clojure/core_test/char_qmark.cljc",
    "test/clojure/core_test/conj.cljc",
    "test/clojure/core_test/double.cljc",
    "test/clojure/core_test/empty_qmark.cljc",
    "test/clojure/core_test/float.cljc",
    "test/clojure/core_test/fnext.cljc",
    "test/clojure/core_test/int.cljc",
    "test/clojure/core_test/last.cljc",
    "test/clojure/core_test/long.cljc",
    "test/clojure/core_test/merge.cljc",
    "test/clojure/core_test/not_empty.cljc",
    "test/clojure/core_test/pr_str.cljc",
    "test/clojure/core_test/prn_str.cljc",
    "test/clojure/core_test/remove.cljc",
    "test/clojure/core_test/reverse.cljc",
    "test/clojure/core_test/seq.cljc",
    "test/clojure/core_test/seqable_qmark.cljc",
    "test/clojure/core_test/set.cljc",
    "test/clojure/core_test/short.cljc",
    "test/clojure/core_test/string_qmark.cljc",
    "test/clojure/core_test/subs.cljc",
)


def ignored_paths(suite_root: Path) -> tuple[Path, ...]:
    """Return absolute paths for external-suite residual files."""

    root = suite_root.resolve()
    return tuple(root / path for path in RESIDUAL_CORE_TEST_FILES)


def missing_paths(suite_root: Path) -> tuple[Path, ...]:
    """Return residual paths missing from a checked-out external suite."""

    return tuple(path for path in ignored_paths(suite_root) if not path.exists())


def pytest_ignore_args(suite_root: Path) -> tuple[str, ...]:
    """Return pytest ``--ignore`` arguments for residual files."""

    root = suite_root.resolve()
    return tuple(
        f"--ignore={(root / path).relative_to(root).as_posix()}"
        for path in RESIDUAL_CORE_TEST_FILES
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--suite-root",
        default=".",
        type=Path,
        help="Path to a clojure-test-suite checkout.",
    )
    parser.add_argument(
        "--pytest-ignore-args",
        action="store_true",
        help="Print pytest --ignore arguments for the residual files.",
    )
    args = parser.parse_args()

    missing = missing_paths(args.suite_root)
    if missing:
        formatted = "\n".join(str(path) for path in missing)
        parser.error(f"residual files are missing from suite checkout:\n{formatted}")

    if args.pytest_ignore_args:
        print(" ".join(pytest_ignore_args(args.suite_root)))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
