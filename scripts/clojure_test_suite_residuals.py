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
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ResidualCluster:
    """Auditable reason for excluding external ``clojure-test-suite`` files."""

    slug: str
    classification: str
    next_action: str
    evidence_fixtures: tuple[str, ...]
    files: tuple[str, ...]


RESIDUAL_CLUSTERS: tuple[ResidualCluster, ...] = (
    ResidualCluster(
        slug="case-numeric-dispatch-expectations",
        classification=(
            "stale Basilisp :lpy expectations around Python host numeric "
            "hash/equality behavior; local evidence now covers numeric "
            "family dispatch, signed zero, NaN, grouped constants, and "
            "duplicate-boundary behavior against JVM Clojure"
        ),
        next_action=(
            "keep case_cases.cljc as authority and do not alter case dispatch "
            "from upstream :lpy failures unless a new differential fixture "
            "proves a JVM Clojure mismatch"
        ),
        evidence_fixtures=("tests/conformance/case_cases.cljc",),
        files=("test/clojure/core_test/case.cljc",),
    ),
    ResidualCluster(
        slug="character-collection-semantics",
        classification=(
            "secondary fallout from the old char-as-string model; Clojure "
            "characters are scalar values, not one-character seqable strings"
        ),
        next_action=(
            "preserve distinct non-seqable characters; character_cases.cljc "
            "now directly guards the residual collection operations, so "
            "update upstream :lpy branches instead of making characters "
            "collection-like"
        ),
        evidence_fixtures=(
            "tests/conformance/character_cases.cljc",
            "tests/conformance/shared_core_semantics_cases.cljc",
        ),
        files=(
            "test/clojure/core_test/empty_qmark.cljc",
            "test/clojure/core_test/fnext.cljc",
            "test/clojure/core_test/last.cljc",
            "test/clojure/core_test/not_empty.cljc",
            "test/clojure/core_test/remove.cljc",
            "test/clojure/core_test/reverse.cljc",
            "test/clojure/core_test/seq.cljc",
            "test/clojure/core_test/seqable_qmark.cljc",
            "test/clojure/core_test/set.cljc",
        ),
    ),
    ResidualCluster(
        slug="character-representation",
        classification=(
            "stale Basilisp :lpy expectations from the old char-as-string "
            "runtime representation; local evidence covers predicates, "
            "printing, map/set identity, UTF-16 string indexing, and scalar "
            "collection rejection"
        ),
        next_action=(
            "preserve first-class Character values and update upstream :lpy "
            "branches rather than collapsing chars back to strings"
        ),
        evidence_fixtures=("tests/conformance/character_cases.cljc",),
        files=(
            "test/clojure/core_test/char.cljc",
            "test/clojure/core_test/char_qmark.cljc",
            "test/clojure/core_test/pr_str.cljc",
            "test/clojure/core_test/prn_str.cljc",
            "test/clojure/core_test/string_qmark.cljc",
        ),
    ),
    ResidualCluster(
        slug="map-entry-coercion",
        classification=(
            "stale Basilisp :lpy expectations for merge/conj map-entry "
            "coercion; local behavior now follows observable JVM Clojure "
            "across persistent merge/conj, transient conj!, nil, map, "
            "MapEntry, vector-pair, and invalid sequential boundaries"
        ),
        next_action=(
            "keep merge_cases.cljc as authority and do not restore older "
            "stricter first-argument guards or arbitrary sequential "
            "map-entry coercion"
        ),
        evidence_fixtures=("tests/conformance/merge_cases.cljc",),
        files=(
            "test/clojure/core_test/conj.cljc",
            "test/clojure/core_test/merge.cljc",
        ),
    ),
    ResidualCluster(
        slug="numeric-coercion-expectations",
        classification=(
            "mostly stale Basilisp :lpy numeric coercion expectations that "
            "accept Python-host conversions Clojure rejects or narrows; "
            "local evidence also guards checked integer range validation "
            "before truncation"
        ),
        next_action=(
            "keep numeric_coercion_cases.cljc as authority, preserve strict "
            "host string/collection rejection, and do not change coercion "
            "behavior unless a specific form is proven to differ from JVM "
            "Clojure"
        ),
        evidence_fixtures=("tests/conformance/numeric_coercion_cases.cljc",),
        files=(
            "test/clojure/core_test/byte.cljc",
            "test/clojure/core_test/double.cljc",
            "test/clojure/core_test/float.cljc",
            "test/clojure/core_test/int.cljc",
            "test/clojure/core_test/long.cljc",
            "test/clojure/core_test/short.cljc",
        ),
    ),
    ResidualCluster(
        slug="stale-core-helper-lpy-expectations",
        classification=(
            "external suite :lpy branches expect behavior that does not match "
            "current JVM Clojure for selected helpers: nil nthrest counts, "
            "non-canonical parse-uuid widths, and rationalize of common "
            "binary floating values"
        ),
        next_action=(
            "keep core_collection_function_cases.cljc and "
            "numeric_coercion_cases.cljc as authority; update the external "
            "suite expectations rather than changing Basilisp away from JVM "
            "Clojure"
        ),
        evidence_fixtures=(
            "tests/conformance/core_collection_function_cases.cljc",
            "tests/conformance/numeric_coercion_cases.cljc",
        ),
        files=(
            "test/clojure/core_test/nthrest.cljc",
            "test/clojure/core_test/parse_uuid.cljc",
            "test/clojure/core_test/rationalize.cljc",
        ),
    ),
    ResidualCluster(
        slug="ratio-host-alias-expectations",
        classification=(
            "external suite :lpy branches refer directly to the Python "
            "fractions/Fraction host class; local evidence covers portable "
            "numerator/denominator ratio semantics without requiring that "
            "non-portable alias"
        ),
        next_action=(
            "keep numeric_coercion_cases.cljc as authority for portable "
            "ratio accessors; revisit only if the external suite switches to "
            "portable forms or Basilisp intentionally exposes fractions as a "
            "resolvable namespace alias"
        ),
        evidence_fixtures=("tests/conformance/numeric_coercion_cases.cljc",),
        files=(
            "test/clojure/core_test/denominator.cljc",
            "test/clojure/core_test/numerator.cljc",
        ),
    ),
    ResidualCluster(
        slug="subs-python-slicing-expectations",
        classification=(
            "mostly stale Basilisp :lpy expectations using Python slicing for "
            "negative, nil, and out-of-range subs indexes; local evidence "
            "also guards Clojure numeric index coercion and explicit nil-end "
            "rejection"
        ),
        next_action=(
            "keep strict Clojure-style UTF-16 subs validation under "
            "clojure.core/subs, including numeric index truncation and "
            "explicit nil-end rejection"
        ),
        evidence_fixtures=("tests/conformance/character_cases.cljc",),
        files=("test/clojure/core_test/subs.cljc",),
    ),
)

RESIDUAL_CORE_TEST_FILES: tuple[str, ...] = tuple(
    sorted(path for cluster in RESIDUAL_CLUSTERS for path in cluster.files)
)

_CLUSTERS_BY_PATH = {
    path: cluster for cluster in RESIDUAL_CLUSTERS for path in cluster.files
}


def _dedupe(paths: Iterable[str]) -> tuple[str, ...]:
    """Return sorted unique paths while preserving an immutable public shape."""

    return tuple(sorted(set(paths)))


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


def cluster_for_path(path: str | Path) -> ResidualCluster | None:
    """Return the residual cluster for a suite-relative path, if any."""

    normalized = Path(path).as_posix()
    return _CLUSTERS_BY_PATH.get(normalized.removeprefix("./"))


def evidence_fixture_paths(repo_root: Path = _REPO_ROOT) -> tuple[Path, ...]:
    """Return local fixture paths that justify the residual exclusions."""

    root = repo_root.resolve()
    fixtures = _dedupe(
        fixture
        for cluster in RESIDUAL_CLUSTERS
        for fixture in cluster.evidence_fixtures
    )
    return tuple(root / fixture for fixture in fixtures)


def missing_evidence_paths(repo_root: Path = _REPO_ROOT) -> tuple[Path, ...]:
    """Return missing local evidence fixtures for residual classifications."""

    return tuple(
        path for path in evidence_fixture_paths(repo_root) if not path.exists()
    )


def verify_evidence_fixtures(
    repo_root: Path = _REPO_ROOT,
    *,
    clojure_command: str | None = None,
    basilisp_command: str | None = None,
    disable_basilisp_ns_cache: bool = False,
) -> None:
    """Run the local differential fixtures that justify residual exclusions."""

    root = repo_root.resolve()
    command = [
        sys.executable,
        str(root / "scripts" / "differential_conformance.py"),
    ]
    if clojure_command is not None:
        command.extend(["--clojure-command", clojure_command])
    if basilisp_command is not None:
        command.extend(["--basilisp-command", basilisp_command])
    if disable_basilisp_ns_cache:
        command.append("--disable-basilisp-ns-cache")
    for fixture in evidence_fixture_paths(root):
        command.extend(["--fixture", str(fixture)])

    result = subprocess.run(
        command,
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(
            "residual evidence fixture verification failed:\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def residual_report() -> str:
    """Return a stable human-readable report of current residual classifications."""

    lines: list[str] = []
    for cluster in sorted(RESIDUAL_CLUSTERS, key=lambda c: c.slug):
        lines.extend(
            [
                f"{cluster.slug}:",
                f"  classification: {cluster.classification}",
                f"  next action: {cluster.next_action}",
                "  evidence:",
                *(f"    - {fixture}" for fixture in cluster.evidence_fixtures),
                "  files:",
                *(f"    - {path}" for path in cluster.files),
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--suite-root",
        default=".",
        type=Path,
        help="Path to a clojure-test-suite checkout.",
    )
    parser.add_argument(
        "--repo-root",
        default=_REPO_ROOT,
        type=Path,
        help="Path to the Basilisp checkout containing local evidence fixtures.",
    )
    parser.add_argument(
        "--pytest-ignore-args",
        action="store_true",
        help="Print pytest --ignore arguments for the residual files.",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print residual classifications and local evidence fixtures.",
    )
    parser.add_argument(
        "--verify-evidence",
        action="store_true",
        help="Run the local differential fixtures that justify residual exclusions.",
    )
    parser.add_argument(
        "--clojure-command",
        default=None,
        help="Clojure command prefix passed through to differential_conformance.py.",
    )
    parser.add_argument(
        "--basilisp-command",
        default=None,
        help="Basilisp command prefix passed through to differential_conformance.py.",
    )
    parser.add_argument(
        "--disable-basilisp-ns-cache",
        action="store_true",
        help="Pass --disable-basilisp-ns-cache through to differential_conformance.py.",
    )
    args = parser.parse_args()

    missing_evidence = missing_evidence_paths(args.repo_root)
    if missing_evidence:
        formatted = "\n".join(str(path) for path in missing_evidence)
        parser.error(f"residual evidence fixtures are missing:\n{formatted}")

    if args.pytest_ignore_args:
        missing = missing_paths(args.suite_root)
        if missing:
            formatted = "\n".join(str(path) for path in missing)
            parser.error(
                f"residual files are missing from suite checkout:\n{formatted}"
            )

    if args.verify_evidence:
        try:
            verify_evidence_fixtures(
                args.repo_root,
                clojure_command=args.clojure_command,
                basilisp_command=args.basilisp_command,
                disable_basilisp_ns_cache=args.disable_basilisp_ns_cache,
            )
        except RuntimeError as exc:
            parser.error(str(exc))

    if args.report and not args.pytest_ignore_args:
        print(residual_report())
        return 0

    if args.report:
        print(residual_report())

    if args.pytest_ignore_args:
        print(" ".join(pytest_ignore_args(args.suite_root)))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
