#!/usr/bin/env python3
"""Audit direct semantic fixture coverage for ``clojure.core`` public Vars.

``scripts/core_parity_matrix.py`` proves public surface presence. This script
answers the next question: which shared ``clojure.core`` names are directly
referenced by the portable conformance corpus?

The scanner is intentionally source-level and conservative. It counts explicit
``clojure.core/symbol`` references, aliases required with ``:as``, and
unqualified symbols used as list heads, e.g. ``(map ...)``. It does not attempt
whole-program analysis of locals, macroexpansion, runtime ``resolve`` calls, or
quoted public-name inventories.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shlex
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import core_parity_matrix  # noqa: E402

DEFAULT_FIXTURE_DIRECTORY = ROOT / "tests" / "conformance"
CORE_NAMESPACES = ("clojure.core", "basilisp.core")

_REQUIRE_ALIAS_RE = re.compile(
    r"\[\s*(clojure\.core|basilisp\.core)\s+:as\s+([^\s\]\)]+)"
)
_CALL_HEAD_RE = re.compile(r"\(\s*([^\s\[\]\{\}\(\)\";,]+)")
_SYMBOL_BOUNDARY = r"(?<![A-Za-z0-9_.$*+!\-?'<>:=/])"
_SYMBOL_BODY = r"([^\s\[\]\{\}\(\)\";,]+)"
_VALUE_REFERENCE_PUBLICS = frozenset(
    {
        "*1",
        "*2",
        "*3",
        "*e",
        "*'",
        "EMPTY-NODE",
        "Inst",
        "default-data-readers",
        "primitives-classnames",
        "unquote",
        "unquote-splicing",
    }
)


@dataclass(frozen=True)
class CoreReference:
    """Direct references to one ``clojure.core`` public Var."""

    symbol: str
    modes_by_fixture: Mapping[Path, frozenset[str]]

    @property
    def fixture_count(self) -> int:
        return len(self.modes_by_fixture)

    @property
    def reference_modes(self) -> tuple[str, ...]:
        return tuple(
            sorted({mode for modes in self.modes_by_fixture.values() for mode in modes})
        )

    @property
    def fixtures(self) -> tuple[str, ...]:
        return tuple(sorted(path.name for path in self.modes_by_fixture))


@dataclass(frozen=True)
class CoreCoverageRow:
    """Coverage row for one ``clojure.core`` public name."""

    symbol: str
    in_clojure: bool
    in_basilisp: bool
    reference: CoreReference | None

    @property
    def status(self) -> str:
        if self.in_clojure and self.in_basilisp:
            return "shared"
        if self.in_clojure:
            return "missing-in-basilisp"
        return "basilisp-extension"

    @property
    def coverage_status(self) -> str:
        if self.status == "missing-in-basilisp":
            return "surface-gap"
        if self.status == "basilisp-extension":
            return "extension"
        if self.reference is None:
            return "uncovered"
        return "covered"

    @property
    def fixture_count(self) -> int:
        return 0 if self.reference is None else self.reference.fixture_count

    @property
    def reference_modes(self) -> tuple[str, ...]:
        return () if self.reference is None else self.reference.reference_modes

    @property
    def fixtures(self) -> tuple[str, ...]:
        return () if self.reference is None else self.reference.fixtures


def _fixture_paths(fixtures: Sequence[Path] | None) -> list[Path]:
    if fixtures:
        return [Path(fixture) for fixture in fixtures]
    return sorted(DEFAULT_FIXTURE_DIRECTORY.glob("*_cases.cljc"))


def _mask_comments_and_strings(source: str) -> str:
    """Replace comments and strings with spaces while preserving character spans."""

    chars = list(source)
    index = 0
    in_string = False
    while index < len(chars):
        char = chars[index]
        if in_string:
            if char == "\\":
                chars[index] = " "
                if index + 1 < len(chars):
                    chars[index + 1] = " "
                    index += 2
                    continue
            if char == '"':
                in_string = False
            chars[index] = " "
            index += 1
            continue
        if char == '"':
            in_string = True
            chars[index] = " "
            index += 1
            continue
        if char == ";":
            while index < len(chars) and chars[index] != "\n":
                chars[index] = " "
                index += 1
            continue
        index += 1
    return "".join(chars)


def core_aliases(source: str) -> set[str]:
    """Return aliases explicitly required for ``clojure.core``/``basilisp.core``."""

    masked = _mask_comments_and_strings(source)
    return {alias for _namespace, alias in _REQUIRE_ALIAS_RE.findall(masked)}


def _unqualified_symbol(token: str) -> str | None:
    if token == "/":
        return token
    if "/" in token or token.startswith(":"):
        return None
    return token


def _qualified_symbol(token: str, aliases: set[str]) -> tuple[str, str] | None:
    namespace_or_alias, separator, symbol = token.partition("/")
    if not separator or not symbol:
        return None
    if namespace_or_alias in CORE_NAMESPACES or namespace_or_alias in aliases:
        return symbol, namespace_or_alias
    return None


def _is_unqualified_value_reference(symbol: str) -> bool:
    return (
        symbol in _VALUE_REFERENCE_PUBLICS
        or (len(symbol) > 2 and symbol.startswith("*") and symbol.endswith("*"))
    )


def direct_core_references(
    fixture_paths: Sequence[Path], core_publics: set[str]
) -> dict[str, CoreReference]:
    """Return directly referenced ``clojure.core`` publics by symbol."""

    references: dict[str, dict[Path, set[str]]] = defaultdict(lambda: defaultdict(set))
    qualified_pattern = re.compile(
        rf"{_SYMBOL_BOUNDARY}"
        rf"({'|'.join(re.escape(namespace) for namespace in CORE_NAMESPACES)})/"
        rf"{_SYMBOL_BODY}"
    )

    for fixture in fixture_paths:
        source = fixture.read_text(encoding="utf-8")
        masked = _mask_comments_and_strings(source)
        aliases = core_aliases(masked)

        for match in _CALL_HEAD_RE.finditer(masked):
            token = match.group(1)
            if qualified := _qualified_symbol(token, aliases):
                symbol, namespace_or_alias = qualified
                if symbol in core_publics:
                    mode = (
                        "qualified-call"
                        if namespace_or_alias in CORE_NAMESPACES
                        else "alias-call"
                    )
                    references[symbol][fixture].add(mode)
                continue
            if (symbol := _unqualified_symbol(token)) and symbol in core_publics:
                references[symbol][fixture].add("unqualified-call")

        unqualified_pattern = re.compile(rf"{_SYMBOL_BOUNDARY}{_SYMBOL_BODY}")
        for match in unqualified_pattern.finditer(masked):
            token = match.group(1)
            if (
                "/" not in token
                and not token.startswith(":")
                and token in core_publics
                and _is_unqualified_value_reference(token)
            ):
                references[token][fixture].add("unqualified-reference")

        alias_pattern = re.compile(
            rf"{_SYMBOL_BOUNDARY}"
            rf"({'|'.join(re.escape(alias) for alias in aliases)})/"
            rf"{_SYMBOL_BODY}"
        ) if aliases else None
        for pattern, mode in (
            (qualified_pattern, "qualified-reference"),
            (alias_pattern, "alias-reference"),
        ):
            if pattern is None:
                continue
            for match in pattern.finditer(masked):
                symbol = match.group(2)
                if symbol in core_publics:
                    references[symbol][fixture].add(mode)

    return {
        symbol: CoreReference(
            symbol=symbol,
            modes_by_fixture={
                fixture: frozenset(modes) for fixture, modes in sorted(fixtures.items())
            },
        )
        for symbol, fixtures in sorted(references.items())
    }


def coverage_rows(
    clojure_publics: set[str],
    basilisp_publics: set[str],
    references: Mapping[str, CoreReference],
) -> list[CoreCoverageRow]:
    """Return one row for each public name in either core namespace."""

    return [
        CoreCoverageRow(
            symbol=symbol,
            in_clojure=symbol in clojure_publics,
            in_basilisp=symbol in basilisp_publics,
            reference=references.get(symbol),
        )
        for symbol in sorted(clojure_publics | basilisp_publics)
    ]


def _run_publics(command_prefix: str, expression: str) -> set[str]:
    return core_parity_matrix._run_publics_command(
        [*_split_command(command_prefix), expression]
    )


def _split_command(command: str) -> list[str]:
    """Split a command prefix without eating Windows path separators."""

    return shlex.split(command, posix=os.name != "nt")


def _live_clojure_publics(command_prefix: str | None) -> set[str]:
    command = (
        _split_command(command_prefix)
        if command_prefix
        else core_parity_matrix._default_clojure_command()
    )
    return core_parity_matrix._run_publics_command(
        [*command, core_parity_matrix.CLOJURE_CORE_PUBLICS]
    )


def _live_basilisp_publics(command_prefix: str) -> set[str]:
    return _run_publics(command_prefix, core_parity_matrix.BASILISP_CORE_PUBLICS)


def _sort_key(row: CoreCoverageRow) -> tuple[int, int, str]:
    coverage_rank = {
        "uncovered": 0,
        "surface-gap": 1,
        "extension": 2,
        "covered": 3,
    }[row.coverage_status]
    return (coverage_rank, row.fixture_count, row.symbol)


def _write_rows(rows: Sequence[CoreCoverageRow]) -> None:
    writer = csv.DictWriter(
        sys.stdout,
        fieldnames=(
            "symbol",
            "status",
            "coverage_status",
            "fixture_count",
            "reference_modes",
            "fixtures",
        ),
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "symbol": row.symbol,
                "status": row.status,
                "coverage_status": row.coverage_status,
                "fixture_count": row.fixture_count,
                "reference_modes": " ".join(row.reference_modes),
                "fixtures": " ".join(row.fixtures),
            }
        )


def _summary(rows: Sequence[CoreCoverageRow]) -> str:
    shared = [row for row in rows if row.status == "shared"]
    covered = [row for row in shared if row.coverage_status == "covered"]
    missing = [row for row in rows if row.status == "missing-in-basilisp"]
    extensions = [row for row in rows if row.status == "basilisp-extension"]
    coverage = 100.0 if not shared else len(covered) * 100.0 / len(shared)
    return (
        f"shared={len(shared)} covered={len(covered)} "
        f"uncovered={len(shared) - len(covered)} "
        f"coverage={coverage:.1f}% "
        f"missing_in_basilisp={len(missing)} basilisp_extensions={len(extensions)}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit direct semantic conformance coverage for clojure.core."
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
        "--clojure-command",
        help=(
            "command prefix used to inspect Clojure; defaults to CLOJURE_COMMAND, "
            f"native clojure with Clojure {core_parity_matrix.CLOJURE_VERSION}, "
            "or WSL on Windows"
        ),
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=None,
        help="fail if shared clojure.core direct fixture coverage is lower",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="print only the N weakest rows",
    )
    args = parser.parse_args(argv)

    fixtures = _fixture_paths(args.fixture)
    clojure_publics = _live_clojure_publics(args.clojure_command)
    basilisp_publics = _live_basilisp_publics(args.basilisp_command)
    shared_publics = clojure_publics & basilisp_publics
    references = direct_core_references(fixtures, shared_publics)
    rows = sorted(
        coverage_rows(clojure_publics, basilisp_publics, references), key=_sort_key
    )

    print(_summary(rows), file=sys.stderr)
    if args.limit is not None:
        rows = rows[: args.limit]
    _write_rows(rows)

    if args.min_coverage is None:
        return 0
    shared = [row for row in rows if row.status == "shared"]
    covered = [row for row in shared if row.coverage_status == "covered"]
    coverage = 100.0 if not shared else len(covered) * 100.0 / len(shared)
    if coverage < args.min_coverage:
        print(
            f"clojure.core direct coverage {coverage:.1f}% < {args.min_coverage:.1f}%",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
