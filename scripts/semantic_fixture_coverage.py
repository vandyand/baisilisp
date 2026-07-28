#!/usr/bin/env python3
"""Audit direct semantic fixture coverage for standard namespace public Vars.

The standard namespace surface matrix proves whether public names exist. This
script answers a different question: which public names are directly exercised
by shared Clojure/Basilisp conformance fixtures?

The scanner is deliberately conservative. It counts explicit ``alias/symbol``
references in ``tests/conformance/*_cases.cljc`` files after discovering
``require`` aliases for audited Clojure and Basilisp namespaces. Quoted public
surface lists, indirect calls through ``resolve``, and values reached only by
macro expansion are not counted as direct semantic coverage.
"""

from __future__ import annotations

import argparse
import csv
import re
import shlex
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import standard_namespace_surface_matrix as surface_matrix  # noqa: E402

DEFAULT_FIXTURE_DIRECTORY = ROOT / "tests" / "conformance"

_REQUIRE_ALIAS_RE = re.compile(
    r"\[\s*([a-zA-Z][\w.-]*(?:\.[\w.-]+)+)\s+:as\s+([^\s\]\)]+)"
)
_SYMBOL_BOUNDARY = r"(?<![A-Za-z0-9_.$*+!\-?'<>:=/])"
_SYMBOL_BODY = r"([^\s\[\]\{\}\(\)\";,]+)"


@dataclass(frozen=True)
class NamespaceCoverage:
    """Direct fixture coverage for one audited Basilisp namespace."""

    basilisp_namespace: str
    clojure_namespace: str
    public_count: int
    covered_symbols: tuple[str, ...]
    uncovered_symbols: tuple[str, ...]
    fixture_count: int
    reference_count: int

    @property
    def covered_count(self) -> int:
        return len(self.covered_symbols)

    @property
    def coverage_percent(self) -> float:
        if self.public_count == 0:
            return 100.0
        return self.covered_count * 100.0 / self.public_count


def _fixture_paths(fixtures: Sequence[Path] | None) -> list[Path]:
    """Return explicitly selected fixtures or the default conformance corpus."""

    if fixtures:
        return [Path(fixture) for fixture in fixtures]
    return sorted(DEFAULT_FIXTURE_DIRECTORY.glob("*_cases.cljc"))


def _namespace_lookup(
    pairs: Sequence[surface_matrix.NamespacePair],
) -> dict[str, surface_matrix.NamespacePair]:
    lookup: dict[str, surface_matrix.NamespacePair] = {}
    for pair in pairs:
        lookup[pair.clojure_ns] = pair
        lookup[pair.basilisp_ns] = pair
    return lookup


def aliases_by_namespace(
    source: str,
    pairs: Sequence[surface_matrix.NamespacePair],
) -> dict[str, set[str]]:
    """Return fixture aliases grouped by audited Basilisp namespace."""

    lookup = _namespace_lookup(pairs)
    aliases: dict[str, set[str]] = defaultdict(set)
    for namespace, alias in _REQUIRE_ALIAS_RE.findall(source):
        if pair := lookup.get(namespace):
            aliases[pair.basilisp_ns].add(alias)
    return dict(aliases)


def direct_references_by_namespace(
    fixture_paths: Sequence[Path],
    pairs: Sequence[
        surface_matrix.NamespacePair
    ] = surface_matrix.STANDARD_NAMESPACE_PAIRS,
) -> dict[str, dict[str, set[Path]]]:
    """Return direct ``alias/symbol`` fixture references by Basilisp namespace."""

    references: dict[str, dict[str, set[Path]]] = defaultdict(lambda: defaultdict(set))
    for fixture in fixture_paths:
        source = fixture.read_text(encoding="utf-8")
        aliases = aliases_by_namespace(source, pairs)
        for basilisp_namespace, namespace_aliases in aliases.items():
            for alias in namespace_aliases:
                pattern = re.compile(
                    rf"{_SYMBOL_BOUNDARY}{re.escape(alias)}/{_SYMBOL_BODY}"
                )
                for match in pattern.finditer(source):
                    references[basilisp_namespace][match.group(1)].add(fixture)
    return {
        namespace: dict(symbols)
        for namespace, symbols in sorted(references.items(), key=lambda item: item[0])
    }


def coverage_rows(
    pairs: Sequence[surface_matrix.NamespacePair],
    basilisp_publics: Mapping[str, set[str]],
    references: Mapping[str, Mapping[str, set[Path]]],
) -> list[NamespaceCoverage]:
    """Return coverage rows for audited namespace pairs."""

    rows: list[NamespaceCoverage] = []
    for pair in pairs:
        publics = basilisp_publics.get(pair.basilisp_ns, set())
        direct_refs = references.get(pair.basilisp_ns, {})
        covered = tuple(sorted(set(direct_refs) & publics))
        uncovered = tuple(sorted(publics - set(covered)))
        fixture_count = len(
            {fixture for symbol in covered for fixture in direct_refs[symbol]}
        )
        reference_count = sum(len(direct_refs[symbol]) for symbol in covered)
        rows.append(
            NamespaceCoverage(
                basilisp_namespace=pair.basilisp_ns,
                clojure_namespace=pair.clojure_ns,
                public_count=len(publics),
                covered_symbols=covered,
                uncovered_symbols=uncovered,
                fixture_count=fixture_count,
                reference_count=reference_count,
            )
        )
    return rows


def _live_basilisp_publics(
    pairs: Sequence[surface_matrix.NamespacePair], command_prefix: str
) -> dict[str, set[str]]:
    return surface_matrix._run_publics(
        shlex.split(command_prefix), [pair.basilisp_ns for pair in pairs]
    )


def _write_rows(rows: Sequence[NamespaceCoverage]) -> None:
    writer = csv.DictWriter(
        sys.stdout,
        fieldnames=(
            "clojure_namespace",
            "basilisp_namespace",
            "public_count",
            "covered_count",
            "coverage_percent",
            "fixture_count",
            "reference_count",
            "uncovered_symbols",
        ),
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "clojure_namespace": row.clojure_namespace,
                "basilisp_namespace": row.basilisp_namespace,
                "public_count": row.public_count,
                "covered_count": row.covered_count,
                "coverage_percent": f"{row.coverage_percent:.1f}",
                "fixture_count": row.fixture_count,
                "reference_count": row.reference_count,
                "uncovered_symbols": " ".join(row.uncovered_symbols),
            }
        )


def _coverage_sort_key(row: NamespaceCoverage) -> tuple[float, int, str]:
    return (row.coverage_percent, -row.public_count, row.basilisp_namespace)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit direct semantic conformance coverage for standard namespaces."
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        action="append",
        help="Fixture to scan; repeat to select multiple fixtures. Defaults to the corpus.",
    )
    parser.add_argument(
        "--basilisp-command",
        default="basilisp run -c",
        help="command prefix used to inspect Basilisp publics",
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=None,
        help="fail if any non-empty audited namespace has less direct coverage",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="print only the N lowest-coverage rows",
    )
    args = parser.parse_args()

    pairs = surface_matrix.STANDARD_NAMESPACE_PAIRS
    fixtures = _fixture_paths(args.fixture)
    references = direct_references_by_namespace(fixtures, pairs)
    basilisp_publics = _live_basilisp_publics(pairs, args.basilisp_command)
    rows = sorted(
        coverage_rows(pairs, basilisp_publics, references), key=_coverage_sort_key
    )
    if args.limit is not None:
        rows = rows[: args.limit]
    _write_rows(rows)

    if args.min_coverage is None:
        return 0
    failing = [
        row
        for row in rows
        if row.public_count and row.coverage_percent < args.min_coverage
    ]
    if failing:
        for row in failing:
            print(
                f"{row.basilisp_namespace} direct coverage "
                f"{row.coverage_percent:.1f}% < {args.min_coverage:.1f}%",
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
